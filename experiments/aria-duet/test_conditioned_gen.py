#!/usr/bin/env python3
"""Test conditioned generation: embedding + model-demo, matching the NeurIPS demo.

Pipeline:
  1. Compute style embedding from reference MIDI (PyTorch, CPU)
  2. Load model-demo with embedding adapter (MLX)
  3. Inject embedding into KV cache at position 0
  4. Generate with EMBEDDING_OFFSET=1 + grammar + time penalty
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


# === Step 1: Compute embedding (PyTorch, CPU) ===

def compute_embedding(embedding_checkpoint_path, midi_path):
    """Compute style embedding using the embedding model (PyTorch)."""
    from safetensors.torch import load_file
    from ariautils.tokenizer import AbsTokenizer
    from aria.model import ModelConfig, TransformerEMB
    from aria.config import load_model_config
    from aria.embedding import get_global_embedding_from_midi
    from ariautils.midi import MidiDict

    print(f"  Loading embedding model...")
    model_config = ModelConfig(**load_model_config("medium-emb"))
    model_config.set_vocab_size(AbsTokenizer().vocab_size)  # 17727 for embedding
    model = TransformerEMB(model_config)
    state_dict = load_file(filename=embedding_checkpoint_path)
    model.load_state_dict(state_dict=state_dict, strict=True)
    model = model.cpu()

    print(f"  Computing embedding from {os.path.basename(midi_path)}...")
    embedding = get_global_embedding_from_midi(
        model=model, midi_path=midi_path, device="cpu"
    )
    print(f"  Embedding shape: {embedding.shape}, norm: {embedding.norm():.2f}")
    return embedding.tolist()


# === Step 2-4: Conditioned generation (MLX) ===

KV_CHUNK_SIZE = 256
EMBEDDING_OFFSET = 1  # Position 0 is the embedding


def _max_kv_pos(pos):
    last = pos[-1].item() if hasattr(pos[-1], "item") else int(pos[-1])
    return math.ceil(last / KV_CHUNK_SIZE) * KV_CHUNK_SIZE


def prefill(model, idxs, input_pos):
    logits = model(
        idxs=idxs,
        input_pos=input_pos + EMBEDDING_OFFSET,
        max_kv_pos=math.ceil((input_pos[-1].item() + EMBEDDING_OFFSET) / KV_CHUNK_SIZE)
        * KV_CHUNK_SIZE,
        offset=input_pos[0] + EMBEDDING_OFFSET,
    )
    return logits


def decode_one(model, idxs, input_pos):
    assert input_pos.shape[-1] == 1
    logits = model(
        idxs=idxs,
        input_pos=input_pos + EMBEDDING_OFFSET,
        max_kv_pos=math.ceil((input_pos[-1].item() + EMBEDDING_OFFSET) / KV_CHUNK_SIZE)
        * KV_CHUNK_SIZE,
        offset=input_pos[0] + EMBEDDING_OFFSET,
    )[:, -1]
    return logits


def sample_min_p(logits, p_base):
    if p_base <= 0.0:
        return mx.argmax(logits, axis=-1, keepdims=True)
    if p_base >= 1.0:
        return mx.random.categorical(logits, num_samples=1)
    log_p_max = mx.max(logits, axis=-1, keepdims=True)
    log_p_scaled = mx.log(p_base) + log_p_max
    mask = logits >= log_p_scaled
    masked_logits = mx.where(~mask, -mx.inf, logits)
    return mx.random.categorical(masked_logits, num_samples=1)


def generate_conditioned(model, tokenizer, prompt, embedding_vec, max_new_tokens,
                         temp=0.95, min_p=0.03, time_penalty=3.0, max_consecutive_time=1,
                         max_gen_ms=None):
    """Generate with style embedding injected into KV cache."""
    from aria.inference import sample_top_p
    import torch
    import numpy as np

    DTYPE = mx.bfloat16
    prompt_len = len(prompt)
    total_len = prompt_len + max_new_tokens
    MAX_SEQ = total_len + 1  # +1 for embedding at position 0

    # Encode and setup
    encoded = tokenizer.encode(prompt + [tokenizer.pad_tok] * max_new_tokens)
    seq = mx.array(encoded, dtype=mx.int32).reshape(1, -1)

    model.eval()
    model.setup_cache(batch_size=1, max_seq_len=MAX_SEQ, dtype=DTYPE)

    # Inject embedding at position 0
    print(f"  Injecting style embedding into KV cache...")
    emb_array = mx.array([embedding_vec], dtype=DTYPE)
    model.fill_condition_kv(cond_emb=emb_array)

    # Precompute grammar IDs
    dim_tok_id = tokenizer.tok_to_id[tokenizer.dim_tok]
    eos_tok_id = tokenizer.tok_to_id[tokenizer.eos_tok]
    time_tok_id = tokenizer.tok_to_id[tokenizer.time_tok]
    dur_ids = [tokenizer.tok_to_id[t] for t in tokenizer.dur_tokens]
    onset_ids = [tokenizer.tok_to_id[t] for t in tokenizer.onset_tokens]
    prefix_ids = [
        tokenizer.tok_to_id[t]
        for t in tokenizer.tok_to_id
        if isinstance(t, tuple) and len(t) == 3 and t[0] == "prefix"
    ]
    _has_pedal = hasattr(tokenizer, 'ped_on_tok') and tokenizer.ped_on_tok in tokenizer.tok_to_id

    consecutive_time = 0
    gen_time_ms = 0
    time_tok_id = tokenizer.tok_to_id[tokenizer.time_tok]

    print(f"  Generating (temp={temp}, time_penalty={time_penalty}, "
          f"max_gen={max_gen_ms/1000:.0f}s, conditioned=True)...")

    from tqdm import tqdm
    for idx in tqdm(range(prompt_len, total_len), total=max_new_tokens, leave=False):
        if idx == prompt_len:
            input_pos = mx.arange(0, idx, dtype=mx.int32)
            logits = prefill(model, idxs=seq[:, :idx], input_pos=input_pos)[:, -1]
        else:
            input_pos = mx.array([idx - 1], dtype=mx.int32)
            logits = decode_one(model, idxs=seq[:, idx - 1:idx], input_pos=input_pos)

        # Mask dim_tok, prefix, eos
        logits[:, dim_tok_id] = float("-inf")
        logits[:, prefix_ids] = float("-inf")
        logits[:, eos_tok_id] = float("-inf")

        # Grammar constraints
        if idx > prompt_len:
            prev_tok = tokenizer.id_to_tok[seq[0, idx - 1].item()]
            _is_inst = isinstance(prev_tok, tuple) and (
                (len(prev_tok) == 3 and prev_tok[0] != "prefix")
                or (len(prev_tok) == 2 and prev_tok[0] == "drum")
            )
            _is_pedal = _has_pedal and prev_tok in {tokenizer.ped_on_tok, tokenizer.ped_off_tok}

            if _is_inst or _is_pedal:
                mask = mx.full(logits.shape, float("-inf"))
                for oid in onset_ids:
                    mask[:, oid] = 0.0
                logits = logits + mask
            elif isinstance(prev_tok, tuple) and prev_tok[0] == "onset":
                pp = tokenizer.id_to_tok[seq[0, idx - 2].item()]
                _pp_inst = isinstance(pp, tuple) and (
                    (len(pp) == 3 and pp[0] != "prefix") or (len(pp) == 2 and pp[0] == "drum")
                )
                if _pp_inst:
                    mask = mx.full(logits.shape, float("-inf"))
                    for did in dur_ids:
                        mask[:, did] = 0.0
                    logits = logits + mask
                else:
                    logits[:, dur_ids] = float("-inf")
                    logits[:, onset_ids] = float("-inf")
            else:
                logits[:, dur_ids] = float("-inf")
                logits[:, onset_ids] = float("-inf")

        # Time penalty
        if time_penalty > 0.0:
            logits[:, time_tok_id] -= time_penalty
            if consecutive_time >= max_consecutive_time:
                logits[:, time_tok_id] -= 10.0

        # Sample with top_p (better for standalone gen)
        if temp > 0.0:
            probs = mx.softmax(logits.astype(mx.float32) / temp, axis=-1)
            probs_t = torch.from_numpy(np.array(probs))
            next_ids = mx.array(sample_top_p(probs_t, 0.95), dtype=mx.int32).flatten()
        else:
            next_ids = mx.argmax(logits, axis=-1).flatten()

        seq[:, idx] = next_ids
        tok = tokenizer.id_to_tok[next_ids[0].item()]
        consecutive_time = consecutive_time + 1 if tok == tokenizer.time_tok else 0

        # Track generated music time
        if tok == tokenizer.time_tok:
            gen_time_ms += 5000
        elif isinstance(tok, tuple) and tok[0] == "onset":
            seg_start = (gen_time_ms // 5000) * 5000
            gen_time_ms = max(gen_time_ms, seg_start + tok[1])

        if tok == tokenizer.eos_tok:
            break
        if max_gen_ms is not None and gen_time_ms >= max_gen_ms:
            break

    result = tokenizer.decode(seq[0].tolist())
    if tokenizer.eos_tok in result:
        result = result[:result.index(tokenizer.eos_tok) + 1]
    return result


def main():
    prompt_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ARIA_DIR, "example-prompts", "nocturne.mid"
    )
    max_gen = int(sys.argv[2]) if len(sys.argv) > 2 else 2048
    save_path = sys.argv[3] if len(sys.argv) > 3 else "recordings/test_conditioned.mid"

    prompt_name = os.path.splitext(os.path.basename(prompt_path))[0]
    print(f"=== Conditioned Generation: {prompt_name} ===")

    # 1. Compute style embedding from the SAME prompt MIDI
    t0 = time.time()
    embedding = compute_embedding(
        "checkpoints/model-embedding.safetensors",
        prompt_path,
    )
    print(f"  Embedding computed in {time.time() - t0:.1f}s")

    # 2. Load model-demo (has embedding adapter)
    config_path = pathlib.Path(ARIA_DIR, "demo", "config.json")
    from ariautils.tokenizer import AbsTokenizer
    from ariautils.midi import MidiDict
    from aria.inference import get_inference_prompt
    from aria.inference.model_mlx import TransformerLM
    from aria.model import ModelConfig
    from aria.config import load_model_config

    tokenizer = AbsTokenizer(config_path=config_path)
    model_config = ModelConfig(**load_model_config("medium-emb"))
    model_config.set_vocab_size(tokenizer.vocab_size)

    DTYPE = mx.bfloat16
    weights = mx.load("checkpoints/model-demo.safetensors")
    for k, w in weights.items():
        if w.dtype != DTYPE:
            weights[k] = w.astype(DTYPE)

    model = TransformerLM(model_config)
    model.load_weights(list(weights.items()), strict=False)
    mx.eval(model.parameters())
    print(f"  Model loaded: vocab={tokenizer.vocab_size}, emb_size={model_config.emb_size}")

    # fill_condition_kv bug was fixed upstream in model_mlx.py (CHANGES.md S19)
    # No monkey-patching needed.

    # 3. Build prompt
    midi_dict = MidiDict.from_midi(prompt_path)
    prompt = get_inference_prompt(
        midi_dict=midi_dict, tokenizer=tokenizer, prompt_len_ms=10000
    )
    print(f"  Prompt: {len(prompt)} tokens")

    max_new = min(4096 - len(prompt) - 1, max_gen)  # -1 for embedding position

    # 4. Generate with conditioning
    t0 = time.time()
    result = generate_conditioned(
        model, tokenizer, prompt, embedding, max_new,
        temp=0.95, time_penalty=0.0, max_consecutive_time=99, max_gen_ms=15000,
    )
    gen_time = time.time() - t0

    # 5. Save and analyze
    gen_toks = len(result) - len(prompt)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    midi_out = tokenizer.detokenize(result)
    midi_out.to_midi().save(save_path)

    from ariautils.midi import MidiDict as MD2
    m = MD2.from_midi(save_path)
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
        print(f"  TOTAL:     {len(notes)} notes, {total_ms/1000:.1f}s ({gen_toks} tokens, {gen_time:.1f}s compute)")
    print(f"  Saved: {save_path}")


if __name__ == "__main__":
    main()
