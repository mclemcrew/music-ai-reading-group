#!/usr/bin/env python3
"""Test CFG (Classifier-Free Guidance) conditioned generation.

Two separate model instances: conditioned (sees embedding) vs unconditioned.
Logit blending: gamma * cond + (1-gamma) * uncond, with warmup.
"""

import sys
import os
import math
import pathlib
import time
import types

ARIA_DIR = "/Users/mclemens/Development/aria"
sys.path.insert(0, ARIA_DIR)

import mlx.core as mx
import mlx.nn as nn
import torch
import numpy as np
from tqdm import tqdm

KV_CHUNK_SIZE = 256
DTYPE = mx.bfloat16


def compute_embedding(midi_path):
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


def _max_kv(pos):
    last = pos[-1].item() if hasattr(pos[-1], "item") else int(pos[-1])
    return math.ceil(last / KV_CHUNK_SIZE) * KV_CHUNK_SIZE


def _fix_fill_condition_kv(model):
    """No-op: fill_condition_kv bug was fixed upstream (CHANGES.md S19)."""
    pass


def load_model():
    from ariautils.tokenizer import AbsTokenizer
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
    _fix_fill_condition_kv(model)
    return model, tokenizer


def prefill(model, idxs, input_pos, eo):
    ip = input_pos + eo
    return model(idxs=idxs, input_pos=ip, max_kv_pos=_max_kv(ip), offset=ip[0])


def decode_one(model, idxs, input_pos, eo):
    ip = input_pos + eo
    return model(idxs=idxs, input_pos=ip, max_kv_pos=_max_kv(ip), offset=ip[0])[:, -1]


def generate_cfg(model_cond, model_uncond, tokenizer, prompt, max_new_tokens,
                 cfg_gamma=1.5, temp=0.95, top_p=0.95, max_gen_ms=10000):
    """Generate with CFG. Stops after max_gen_ms of generated music time."""
    from aria.inference import sample_top_p

    prompt_len = len(prompt)
    total_len = prompt_len + max_new_tokens

    encoded = tokenizer.encode(prompt + [tokenizer.pad_tok] * max_new_tokens)
    seq = mx.array(encoded, dtype=mx.int32).reshape(1, -1)

    # Grammar IDs
    dim_tok_id = tokenizer.tok_to_id[tokenizer.dim_tok]
    eos_tok_id = tokenizer.tok_to_id[tokenizer.eos_tok]
    dur_ids = [tokenizer.tok_to_id[t] for t in tokenizer.dur_tokens]
    onset_ids = [tokenizer.tok_to_id[t] for t in tokenizer.onset_tokens]
    prefix_ids = [tokenizer.tok_to_id[t] for t in tokenizer.tok_to_id
                  if isinstance(t, tuple) and len(t) == 3 and t[0] == "prefix"]
    _has_pedal = hasattr(tokenizer, 'ped_on_tok') and tokenizer.ped_on_tok in tokenizer.tok_to_id

    CFG_WARM_UP_STEPS = min(250, max_new_tokens)
    curr_step = 0
    gen_time_ms = 0  # Track generated music time
    time_tok_id = tokenizer.tok_to_id[tokenizer.time_tok]

    # Conditioned model uses EMBEDDING_OFFSET=1, unconditioned uses 0
    EO_COND = 1
    EO_UNCOND = 0

    print(f"  CFG: gamma={cfg_gamma}, temp={temp}, top_p={top_p}, "
          f"max_gen={max_gen_ms/1000:.0f}s, warmup={CFG_WARM_UP_STEPS}")

    for idx in tqdm(range(prompt_len, total_len), total=max_new_tokens, leave=False):
        if idx == prompt_len:
            ip = mx.arange(0, idx, dtype=mx.int32)
            logits_c = prefill(model_cond, seq[:, :idx], ip, EO_COND)[:, -1]
            logits_u = prefill(model_uncond, seq[:, :idx], ip, EO_UNCOND)[:, -1]
        else:
            ip = mx.array([idx - 1], dtype=mx.int32)
            logits_c = decode_one(model_cond, seq[:, idx-1:idx], ip, EO_COND)
            logits_u = decode_one(model_uncond, seq[:, idx-1:idx], ip, EO_UNCOND)

        # CFG blend with warmup
        curr_step += 1
        _gamma = min(cfg_gamma, (curr_step / CFG_WARM_UP_STEPS) * cfg_gamma)
        logits = _gamma * logits_c + (1 - _gamma) * logits_u

        # Mask dim_tok, prefix, eos
        logits[:, dim_tok_id] = float("-inf")
        logits[:, prefix_ids] = float("-inf")
        logits[:, eos_tok_id] = float("-inf")

        # Grammar
        if idx > prompt_len:
            prev_tok = tokenizer.id_to_tok[seq[0, idx - 1].item()]
            _is_inst = isinstance(prev_tok, tuple) and (
                (len(prev_tok) == 3 and prev_tok[0] != "prefix")
                or (len(prev_tok) == 2 and prev_tok[0] == "drum")
            )
            _is_pedal = _has_pedal and prev_tok in {tokenizer.ped_on_tok, tokenizer.ped_off_tok}

            if _is_inst or _is_pedal:
                mask = mx.full(logits.shape, float("-inf"))
                for oid in onset_ids: mask[:, oid] = 0.0
                logits = logits + mask
            elif isinstance(prev_tok, tuple) and prev_tok[0] == "onset":
                pp = tokenizer.id_to_tok[seq[0, idx - 2].item()]
                _pp_inst = isinstance(pp, tuple) and (
                    (len(pp) == 3 and pp[0] != "prefix") or (len(pp) == 2 and pp[0] == "drum")
                )
                if _pp_inst:
                    mask = mx.full(logits.shape, float("-inf"))
                    for did in dur_ids: mask[:, did] = 0.0
                    logits = logits + mask
                else:
                    logits[:, dur_ids] = float("-inf")
                    logits[:, onset_ids] = float("-inf")
            else:
                logits[:, dur_ids] = float("-inf")
                logits[:, onset_ids] = float("-inf")

        # Sample
        if temp > 0.0:
            probs = mx.softmax(logits.astype(mx.float32) / temp, axis=-1)
            next_id = mx.array(sample_top_p(torch.from_numpy(np.array(probs)), top_p),
                               dtype=mx.int32).flatten()
        else:
            next_id = mx.argmax(logits, axis=-1).flatten()

        seq[:, idx] = next_id
        tok = tokenizer.id_to_tok[next_id[0].item()]

        # Track generated music time
        if tok == tokenizer.time_tok:
            gen_time_ms += 5000
        elif isinstance(tok, tuple) and tok[0] == "onset":
            gen_time_ms = max(gen_time_ms, gen_time_ms // 5000 * 5000 + tok[1])

        if tok == tokenizer.eos_tok or gen_time_ms >= max_gen_ms:
            break

    result = tokenizer.decode(seq[0].tolist())
    if tokenizer.eos_tok in result:
        result = result[:result.index(tokenizer.eos_tok) + 1]
    return result


def main():
    prompt_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ARIA_DIR, "example-prompts", "nocturne.mid"
    )
    max_gen = int(sys.argv[2]) if len(sys.argv) > 2 else 256
    cfg_gamma = float(sys.argv[3]) if len(sys.argv) > 3 else 1.5
    save_path = sys.argv[4] if len(sys.argv) > 4 else "recordings/test_cfg.mid"

    prompt_name = os.path.splitext(os.path.basename(prompt_path))[0]
    print(f"=== CFG Generation: {prompt_name} (gamma={cfg_gamma}) ===")

    # 1. Embedding
    embedding = compute_embedding(prompt_path)

    # 2. Two model instances: conditioned + unconditioned
    print("  Loading conditioned model...")
    model_cond, tokenizer = load_model()
    max_seq = 4096
    model_cond.eval()
    model_cond.setup_cache(batch_size=1, max_seq_len=max_seq, dtype=DTYPE)
    model_cond.fill_condition_kv(cond_emb=mx.array([embedding], dtype=DTYPE))

    print("  Loading unconditioned model...")
    model_uncond, _ = load_model()
    model_uncond.eval()
    model_uncond.setup_cache(batch_size=1, max_seq_len=max_seq, dtype=DTYPE)
    # No embedding injection -- this is the unconditioned model

    # 3. Prompt (10s)
    from ariautils.midi import MidiDict
    from aria.inference import get_inference_prompt
    midi_dict = MidiDict.from_midi(prompt_path)
    prompt = get_inference_prompt(midi_dict=midi_dict, tokenizer=tokenizer, prompt_len_ms=10000)
    print(f"  Prompt: {len(prompt)} tokens")

    max_new = min(max_seq - len(prompt) - 1, max_gen)

    # 4. Generate
    t0 = time.time()
    result = generate_cfg(model_cond, model_uncond, tokenizer, prompt, max_new,
                          cfg_gamma=cfg_gamma, max_gen_ms=10000)
    gen_time = time.time() - t0

    # 5. Save + analyze
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
        print(f"  TOTAL:     {len(notes)} notes, {total_ms/1000:.1f}s (compute: {gen_time:.1f}s)")
    print(f"  Saved: {save_path}")


if __name__ == "__main__":
    main()
