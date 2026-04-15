#!/usr/bin/env python3
"""Batched CFG generation: single model, batch=2 (conditioned + unconditioned).

Uses the fixed sample_batch_cfg pattern from aria/inference/sample_mlx.py:
  - Even batch indices: conditioned (see embedding at KV position 0)
  - Odd batch indices: unconditioned (position 0 masked via pad_idxs)
  - Logit blending: gamma * cond + (1-gamma) * uncond, with warmup

This replaces test_cfg_gen.py's two-model approach which:
  - Uses 2x memory (two full model copies)
  - Has diverging KV caches (degraded blended logits)
  - Is 2x slower (separate forward passes)

Upstream bugs fixed:
  - model_mlx.py: fill_condition_kv missing max_kv_pos arg
  - model_mlx.py: pad_idxs shape mismatch ([:, :max_kv_pos+1] slice)
  - sample_mlx.py: prefill/decode_one missing max_kv_pos

Usage:
    python test_batched_cfg.py [prompt_midi] [max_tokens] [cfg_gamma] [save_path]
    python test_batched_cfg.py example-prompts/waltz.mid 512 1.5 recordings/test_bcfg.mid
"""

import sys
import os
import math
import pathlib
import time

ARIA_DIR = "/Users/mclemens/Development/aria"
sys.path.insert(0, ARIA_DIR)

import mlx.core as mx
import mlx.nn as nn
import torch
import numpy as np
from tqdm import tqdm

KV_CHUNK_SIZE = 256
DTYPE = mx.bfloat16
EMBEDDING_OFFSET = 1


def compute_embedding(midi_path):
    """Compute style embedding using the embedding model (PyTorch, CPU)."""
    from safetensors.torch import load_file
    from ariautils.tokenizer import AbsTokenizer
    from aria.model import ModelConfig, TransformerEMB
    from aria.config import load_model_config
    from aria.embedding import get_global_embedding_from_midi

    mc = ModelConfig(**load_model_config("medium-emb"))
    mc.set_vocab_size(AbsTokenizer().vocab_size)
    m = TransformerEMB(mc)
    m.load_state_dict(load_file("checkpoints/model-embedding.safetensors"), strict=True)
    emb = get_global_embedding_from_midi(model=m.cpu(), midi_path=midi_path, device="cpu")
    print(f"  Embedding: norm={emb.norm():.2f}")
    return emb.tolist()


def _max_kv_pos(input_pos):
    last = input_pos[-1].item() if hasattr(input_pos[-1], "item") else int(input_pos[-1])
    return math.ceil(last / KV_CHUNK_SIZE) * KV_CHUNK_SIZE


def prefill(model, idxs, input_pos, pad_idxs=None):
    return model(
        idxs=idxs,
        input_pos=input_pos,
        max_kv_pos=_max_kv_pos(input_pos),
        offset=input_pos[0],
        pad_idxs=pad_idxs,
    )


def decode_one(model, idxs, input_pos, pad_idxs=None):
    assert input_pos.shape[-1] == 1
    return model(
        idxs=idxs,
        input_pos=input_pos,
        max_kv_pos=_max_kv_pos(input_pos),
        offset=input_pos[0],
        pad_idxs=pad_idxs,
    )[:, -1]


def generate_batched_cfg(model, tokenizer, prompt, embedding_vec, max_new_tokens,
                         cfg_gamma=1.5, temp=0.95, top_p=0.95, max_gen_ms=15000,
                         time_penalty=0.0, pedal_penalty=0.0, max_consecutive_time=99):
    """Single-model batched CFG: batch[0]=conditioned, batch[1]=unconditioned."""
    from aria.inference import sample_top_p as _sample_top_p

    prompt_len = len(prompt)
    total_len = prompt_len + max_new_tokens
    batch_size = 2  # [conditioned, unconditioned]

    # Encode prompt into batch of 2 identical sequences
    encoded = tokenizer.encode(prompt + [tokenizer.pad_tok] * max_new_tokens)
    seq = mx.stack([
        mx.array(encoded, dtype=mx.int32),
        mx.array(encoded, dtype=mx.int32),
    ])  # [2, total_len]

    # Setup model with batch_size=2
    model.eval()
    model.setup_cache(batch_size=batch_size, max_seq_len=total_len + EMBEDDING_OFFSET, dtype=DTYPE)

    # Inject embedding into BOTH batch rows at KV position 0.
    # The unconditioned row will have position 0 masked out via pad_idxs.
    emb_array = mx.array([embedding_vec, embedding_vec], dtype=DTYPE)
    model.fill_condition_kv(cond_emb=emb_array)

    # pad_idxs: mask position 0 for the unconditioned (odd) batch row
    # Shape must be [batch, total_len] -- will be sliced to [:, :max_kv_pos+1] in Transformer
    pad_idxs = mx.zeros((batch_size, total_len + EMBEDDING_OFFSET), dtype=mx.bool_)
    pad_idxs[1, 0] = True  # Unconditioned row: mask the embedding position

    # Grammar IDs
    dim_tok_id = tokenizer.tok_to_id[tokenizer.dim_tok]
    eos_tok_id = tokenizer.tok_to_id[tokenizer.eos_tok]
    time_tok_id = tokenizer.tok_to_id[tokenizer.time_tok]
    dur_ids = [tokenizer.tok_to_id[t] for t in tokenizer.dur_tokens]
    onset_ids = [tokenizer.tok_to_id[t] for t in tokenizer.onset_tokens]
    prefix_ids = [tokenizer.tok_to_id[t] for t in tokenizer.tok_to_id
                  if isinstance(t, tuple) and len(t) == 3 and t[0] == "prefix"]
    _has_pedal = hasattr(tokenizer, 'ped_on_tok') and tokenizer.ped_on_tok in tokenizer.tok_to_id
    if _has_pedal:
        ped_on_id = tokenizer.tok_to_id[tokenizer.ped_on_tok]
        ped_off_id = tokenizer.tok_to_id[tokenizer.ped_off_tok]

    CFG_WARM_UP_STEPS = min(250, max_new_tokens)
    curr_step = 0
    gen_time_ms = 0
    consecutive_time = 0

    print(f"  Batched CFG: gamma={cfg_gamma}, temp={temp}, top_p={top_p}, "
          f"max_gen={max_gen_ms/1000:.0f}s, warmup={CFG_WARM_UP_STEPS}, "
          f"time_pen={time_penalty}, pedal_pen={pedal_penalty}")

    for idx in tqdm(range(prompt_len, total_len), total=max_new_tokens, leave=False):
        if idx == prompt_len:
            # Prefill: both batch rows see the same prompt
            input_pos = mx.arange(EMBEDDING_OFFSET, idx + EMBEDDING_OFFSET, dtype=mx.int32)
            logits = prefill(model, idxs=seq[:, :idx], input_pos=input_pos,
                             pad_idxs=pad_idxs)[:, -1]
        else:
            input_pos = mx.array([idx - 1 + EMBEDDING_OFFSET], dtype=mx.int32)
            logits = decode_one(model, idxs=seq[:, idx - 1:idx], input_pos=input_pos,
                                pad_idxs=pad_idxs)

        # CFG blend with warmup
        curr_step += 1
        _gamma = min(cfg_gamma, (curr_step / CFG_WARM_UP_STEPS) * cfg_gamma)
        logits_cond = logits[0:1]    # [1, vocab]
        logits_uncond = logits[1:2]  # [1, vocab]
        blended = _gamma * logits_cond + (1 - _gamma) * logits_uncond  # [1, vocab]

        # Mask dim_tok, prefix, eos
        blended[:, dim_tok_id] = float("-inf")
        blended[:, prefix_ids] = float("-inf")
        blended[:, eos_tok_id] = float("-inf")

        # Grammar constraints (applied to blended logits)
        if idx > prompt_len:
            prev_tok = tokenizer.id_to_tok[seq[0, idx - 1].item()]
            _is_inst = isinstance(prev_tok, tuple) and (
                (len(prev_tok) == 3 and prev_tok[0] != "prefix")
                or (len(prev_tok) == 2 and prev_tok[0] == "drum")
            )
            _is_pedal = _has_pedal and prev_tok in {tokenizer.ped_on_tok, tokenizer.ped_off_tok}

            if _is_inst or _is_pedal:
                mask = mx.full(blended.shape, float("-inf"))
                for oid in onset_ids:
                    mask[:, oid] = 0.0
                blended = blended + mask
            elif isinstance(prev_tok, tuple) and prev_tok[0] == "onset":
                pp = tokenizer.id_to_tok[seq[0, idx - 2].item()]
                _pp_inst = isinstance(pp, tuple) and (
                    (len(pp) == 3 and pp[0] != "prefix") or (len(pp) == 2 and pp[0] == "drum")
                )
                if _pp_inst:
                    mask = mx.full(blended.shape, float("-inf"))
                    for did in dur_ids:
                        mask[:, did] = 0.0
                    blended = blended + mask
                else:
                    blended[:, dur_ids] = float("-inf")
                    blended[:, onset_ids] = float("-inf")
            else:
                blended[:, dur_ids] = float("-inf")
                blended[:, onset_ids] = float("-inf")

        # Time and pedal penalties at free positions
        if time_penalty > 0.0:
            blended[:, time_tok_id] -= time_penalty
            if consecutive_time >= max_consecutive_time:
                blended[:, time_tok_id] -= 10.0
        if pedal_penalty > 0.0 and _has_pedal:
            blended[:, ped_on_id] -= pedal_penalty
            blended[:, ped_off_id] -= pedal_penalty

        # Sample with top_p
        if temp > 0.0:
            probs = mx.softmax(blended.astype(mx.float32) / temp, axis=-1)
            next_id_val = int(
                _sample_top_p(torch.from_numpy(np.array(probs)), top_p).item()
            )
        else:
            next_id_val = int(mx.argmax(blended, axis=-1).item())

        # Write same token to both batch rows (they must stay in sync)
        next_ids = mx.array([[next_id_val], [next_id_val]], dtype=mx.int32)
        seq[:, idx:idx+1] = next_ids

        tok = tokenizer.id_to_tok[next_id_val]
        consecutive_time = consecutive_time + 1 if tok == tokenizer.time_tok else 0

        # Track generated music time
        if tok == tokenizer.time_tok:
            gen_time_ms += 5000
        elif isinstance(tok, tuple) and tok[0] == "onset":
            gen_time_ms = max(gen_time_ms, gen_time_ms // 5000 * 5000 + tok[1])

        if tok == tokenizer.eos_tok or gen_time_ms >= max_gen_ms:
            break

    # Decode from conditioned row
    result = tokenizer.decode(seq[0].tolist())
    if tokenizer.eos_tok in result:
        result = result[:result.index(tokenizer.eos_tok) + 1]
    return result


def main():
    import argparse
    p = argparse.ArgumentParser(description="Batched CFG generation")
    p.add_argument("prompt_midi", nargs="?",
                   default=os.path.join(ARIA_DIR, "example-prompts", "nocturne.mid"))
    p.add_argument("--tokens", type=int, default=512)
    p.add_argument("--gamma", type=float, default=1.5)
    p.add_argument("--temp", type=float, default=0.95)
    p.add_argument("--top_p", type=float, default=0.95)
    p.add_argument("--max_gen_ms", type=int, default=15000)
    p.add_argument("--time_penalty", type=float, default=0.0)
    p.add_argument("--pedal_penalty", type=float, default=0.0)
    p.add_argument("--max_consecutive_time", type=int, default=99)
    p.add_argument("--save", default="recordings/test_batched_cfg.mid")
    args = p.parse_args()

    prompt_path = args.prompt_midi
    max_gen = args.tokens
    cfg_gamma = args.gamma
    save_path = args.save

    prompt_name = os.path.splitext(os.path.basename(prompt_path))[0]
    print(f"=== Batched CFG Generation: {prompt_name} (gamma={cfg_gamma}) ===")

    # 1. Compute embedding
    t0 = time.time()
    embedding = compute_embedding(prompt_path)
    print(f"  Embedding computed in {time.time() - t0:.1f}s")

    # 2. Load model-demo (has embedding adapter)
    from ariautils.tokenizer import AbsTokenizer
    from ariautils.midi import MidiDict
    from aria.inference import get_inference_prompt
    from aria.inference.model_mlx import TransformerLM
    from aria.model import ModelConfig
    from aria.config import load_model_config

    config_path = pathlib.Path(ARIA_DIR, "demo", "config.json")
    tokenizer = AbsTokenizer(config_path=config_path)
    model_config = ModelConfig(**load_model_config("medium-emb"))
    model_config.set_vocab_size(tokenizer.vocab_size)

    weights = mx.load("checkpoints/model-demo.safetensors")
    for k, w in weights.items():
        if w.dtype != DTYPE:
            weights[k] = w.astype(DTYPE)

    model = TransformerLM(model_config)
    model.load_weights(list(weights.items()), strict=False)
    mx.eval(model.parameters())
    print(f"  Model loaded: vocab={tokenizer.vocab_size}, emb_size={model_config.emb_size}")

    # 3. Build prompt
    midi_dict = MidiDict.from_midi(prompt_path)
    prompt = get_inference_prompt(
        midi_dict=midi_dict, tokenizer=tokenizer, prompt_len_ms=10000
    )
    print(f"  Prompt: {len(prompt)} tokens")

    max_new = min(4096 - len(prompt) - EMBEDDING_OFFSET, max_gen)

    # 4. Generate with batched CFG
    t0 = time.time()
    result = generate_batched_cfg(
        model, tokenizer, prompt, embedding, max_new,
        cfg_gamma=cfg_gamma, temp=args.temp, top_p=args.top_p,
        max_gen_ms=args.max_gen_ms,
        time_penalty=args.time_penalty, pedal_penalty=args.pedal_penalty,
        max_consecutive_time=args.max_consecutive_time,
    )
    gen_time = time.time() - t0

    # 5. Save and analyze
    gen_toks = len(result) - len(prompt)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    midi_out = tokenizer.detokenize(result)
    midi_out.to_midi().save(save_path)

    m = MidiDict.from_midi(save_path)
    notes = m.note_msgs
    prompt_ms = 10000
    if notes:
        prompt_notes = [n for n in notes if m.tick_to_ms(n['data']['start']) <= prompt_ms]
        gen_notes = [n for n in notes if m.tick_to_ms(n['data']['start']) > prompt_ms]
        total_ms = m.tick_to_ms(max(n['data']['end'] for n in notes))
        gen_ms = total_ms - prompt_ms if total_ms > prompt_ms else 0

        print(f"\n  PROMPT:    {len(prompt_notes)} notes in {prompt_ms/1000:.0f}s")
        print(f"  GENERATED: {len(gen_notes)} notes in {gen_ms/1000:.1f}s", end="")
        if gen_ms > 0:
            print(f" ({len(gen_notes)/(gen_ms/60000):.0f} notes/min)")
        else:
            print(" (no time advance)")
        print(f"  TOTAL:     {len(notes)} notes, {total_ms/1000:.1f}s "
              f"({gen_toks} tokens, {gen_time:.1f}s compute)")
    else:
        print(f"\n  No notes generated ({gen_toks} tokens, {gen_time:.1f}s compute)")
    print(f"  Saved: {save_path}")


if __name__ == "__main__":
    main()
