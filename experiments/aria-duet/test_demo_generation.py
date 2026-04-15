#!/usr/bin/env python3
"""Headless test of the interactive demo's generation pipeline.

Replicates exactly what demo_mlx.py does when you press Enter:
  1. Prefill the prompt (chunked)
  2. Recalculate duration tokens (speculative decoding)
  3. Beam search for first 2 tokens
  4. Autoregressive decode with min_p + PED_OFF boost

This lets us compare the demo's output quality against sweep_generate.py
without needing a keyboard or real-time MIDI setup.
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
from ariautils.tokenizer import AbsTokenizer
from ariautils.midi import MidiDict
from aria.inference import get_inference_prompt
from aria.inference.model_mlx import TransformerLM
from aria.model import ModelConfig
from aria.config import load_model_config

# --- Constants matching demo_mlx.py ---
DTYPE = mx.bfloat16
MAX_SEQ_LEN = 4096
KV_CHUNK_SIZE = 256
PREFILL_CHUNK_SIZE = 16
RECALC_DUR_PREFILL_CHUNK_SIZE = 8
RECALC_DUR_BUFFER_MS = 100
BEAM_WIDTH = 3
TIME_TOK_WEIGHTING = -5
MIN_NOTE_LENGTH_MS = 10
EMBEDDING_OFFSET = 0  # No conditioning embedding


# --- Functions copied from demo_mlx.py (unchanged) ---

def prefill(model, idxs, input_pos):
    logits = model(
        idxs=idxs,
        input_pos=input_pos + EMBEDDING_OFFSET,
        max_kv_pos=math.ceil(input_pos[-1].item() / KV_CHUNK_SIZE) * KV_CHUNK_SIZE,
        offset=input_pos[0] + EMBEDDING_OFFSET,
    )
    return logits


def decode_one(model, idxs, input_pos):
    assert input_pos.shape[-1] == 1
    logits = model(
        idxs=idxs,
        input_pos=input_pos + EMBEDDING_OFFSET,
        max_kv_pos=math.ceil(input_pos[-1].item() / KV_CHUNK_SIZE) * KV_CHUNK_SIZE,
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


def _first_bad_dur_index(tokenizer, priming_seq, pred_ids, chunk_start, last_offset_ms):
    num_time_toks = priming_seq[:chunk_start].count(tokenizer.time_tok)
    local_onset_ms = tokenizer.calc_length_ms(priming_seq[:chunk_start + 1], onset=True)

    for pos, tok_id in enumerate(
        pred_ids[:len(priming_seq) - chunk_start], start=chunk_start
    ):
        prim_tok = priming_seq[pos]
        pred_tok = tokenizer.id_to_tok[tok_id]

        if isinstance(prim_tok, tuple) and prim_tok[0] == "onset":
            local_onset_ms = num_time_toks * 5000 + prim_tok[1]
        elif prim_tok == tokenizer.time_tok:
            num_time_toks += 1
        elif isinstance(prim_tok, tuple) and prim_tok[0] == "dur":
            dur_true = prim_tok[1]
            dur_pred = pred_tok[1]
            if dur_pred > dur_true and (
                local_onset_ms + dur_true >= last_offset_ms - RECALC_DUR_BUFFER_MS
            ):
                return pos
    return None


def recalc_dur_tokens_chunked(model, priming_seq, enc_seq, tokenizer, start_idx):
    """Speculative-decoding inspired duration re-calculation (from demo_mlx.py:435)."""
    assert start_idx > 0
    priming_len = len(priming_seq)
    last_offset = tokenizer.calc_length_ms(priming_seq, onset=False)

    idx = start_idx
    while idx <= priming_len:
        end_idx = idx + RECALC_DUR_PREFILL_CHUNK_SIZE
        window_ids = mx.array(enc_seq[:, idx - 1:end_idx - 1].tolist(), dtype=mx.int32)
        window_pos = mx.arange(idx - 1, end_idx - 1, dtype=mx.int32)

        logits = prefill(model, idxs=window_ids, input_pos=window_pos)
        pred_ids = mx.argmax(logits, axis=-1).flatten().tolist()

        bad_pos = _first_bad_dur_index(tokenizer, priming_seq, pred_ids, idx, last_offset)
        if bad_pos is None:
            idx = end_idx
        else:
            new_id = pred_ids[bad_pos - idx]
            enc_seq[0, bad_pos] = new_id
            priming_seq[bad_pos] = tokenizer.id_to_tok[new_id]
            idx = bad_pos + 1

    next_logits = logits[:, priming_len - idx]
    return enc_seq, priming_seq, next_logits


def decode_first_tokens(model, first_token_logits, enc_seq, priming_seq, tokenizer):
    """Beam search for first 2 tokens (from demo_mlx.py:497)."""
    time_tok_id = tokenizer.tok_to_id[tokenizer.time_tok]
    eos_tok_id = tokenizer.tok_to_id[tokenizer.eos_tok]
    dim_tok_id = tokenizer.tok_to_id[tokenizer.dim_tok]
    ped_off_id = tokenizer.tok_to_id[tokenizer.ped_off_tok]
    onset_ids = [tokenizer.tok_to_id[t] for t in tokenizer.onset_tokens]

    logits = first_token_logits
    idx = len(priming_seq) + 1

    logits[:, dim_tok_id] = float("-inf")
    logits[:, eos_tok_id] = float("-inf")
    logits[:, ped_off_id] = float("-inf")

    log_probs = nn.log_softmax(logits, axis=-1)
    top_ids = mx.argsort(log_probs, axis=-1)[0, -BEAM_WIDTH:]
    top_log_probs = log_probs[0, top_ids]

    if time_tok_id not in top_ids.tolist():
        top_ids[0] = time_tok_id
        top_log_probs[0] = log_probs[0, time_tok_id]

    _time_tok_idx = top_ids.tolist().index(time_tok_id)
    top_log_probs[_time_tok_idx] += TIME_TOK_WEIGHTING

    top_toks = [tokenizer.id_to_tok[id] for id in top_ids.tolist()]

    best_score = float("-inf")
    best_tok_id_1, best_tok_id_2 = None, None

    for i in range(BEAM_WIDTH):
        tok = top_toks[i]
        tok_id = top_ids[i].item()
        tok_log_prob = top_log_probs[i]

        next_logits = decode_one(
            model,
            idxs=mx.array([[tok_id]], dtype=mx.int32),
            input_pos=mx.array([idx - 1], dtype=mx.int32),
        )

        next_log_probs = nn.log_softmax(next_logits, axis=-1)
        next_log_probs[:, eos_tok_id] = float("-inf")
        next_log_probs[:, dim_tok_id] = float("-inf")
        next_log_probs[:, ped_off_id] = float("-inf")

        if tok_id == time_tok_id:
            next_log_probs[:, time_tok_id] = float("-inf")

        # Grammar: after note/pedal, force onset
        _is_inst = isinstance(tok, tuple) and (
            (len(tok) == 3 and tok[0] != "prefix") or (len(tok) == 2 and tok[0] == "drum")
        )
        if tok_id == tokenizer.tok_to_id.get(tokenizer.ped_on_tok) or _is_inst:
            mask = mx.full(next_log_probs.shape, float("-inf"))
            for oid in onset_ids:
                mask[:, oid] = 0.0
            next_log_probs = next_log_probs + mask

        next_tok_log_prob = mx.max(next_log_probs, axis=-1)
        next_tok_id = mx.argmax(next_log_probs, axis=-1)
        score = tok_log_prob + next_tok_log_prob

        if score > best_score:
            best_tok_id_1, best_tok_id_2 = tok_id, next_tok_id.item()
            best_score = score

    best_tok_1 = tokenizer.id_to_tok[best_tok_id_1]
    best_tok_2 = tokenizer.id_to_tok[best_tok_id_2]
    print(f"  Beam search chose: ({best_tok_1}, {best_tok_2}) score={best_score.item():.2f}")

    enc_seq[:, idx - 1] = best_tok_id_1
    enc_seq[:, idx] = best_tok_id_2

    # Re-insert best_tok_1 to update KV cache
    mx.eval(decode_one(
        model,
        idxs=mx.array([[best_tok_id_1]], dtype=mx.int32),
        input_pos=mx.array([idx - 1], dtype=mx.int32),
    ))

    return enc_seq, idx + 1, [best_tok_1, best_tok_2]


def decode_tokens(model, enc_seq, tokenizer, idx, temperature, min_p, max_tokens=500):
    """Autoregressive decode with grammar constraints (CHANGES.md S3-S7 fixes applied)."""
    dur_ids = [tokenizer.tok_to_id[t] for t in tokenizer.dur_tokens]
    dur_mask_ids = [
        tokenizer.tok_to_id[("dur", dur_ms)]
        for dur_ms in range(0, MIN_NOTE_LENGTH_MS, 10)
    ]
    onset_ids = [tokenizer.tok_to_id[t] for t in tokenizer.onset_tokens]
    prefix_ids = [
        tokenizer.tok_to_id[t]
        for t in tokenizer.tok_to_id
        if isinstance(t, tuple) and len(t) == 3 and t[0] == "prefix"
    ]

    generated = []
    start_idx = idx
    while idx < MAX_SEQ_LEN and (idx - start_idx) < max_tokens:
        prev_tok_id = enc_seq[0, idx - 1]
        prev_tok = tokenizer.id_to_tok[prev_tok_id.item()]

        logits = decode_one(
            model,
            idxs=mx.array([[prev_tok_id]], dtype=mx.int32),
            input_pos=mx.array([idx - 1], dtype=mx.int32),
        )

        # Always mask dim_tok, prefix tokens, short durations
        logits[:, tokenizer.tok_to_id[tokenizer.dim_tok]] = float("-inf")
        logits[:, tokenizer.tok_to_id[tokenizer.eos_tok]] = float("-inf")
        logits[:, dur_mask_ids] = float("-inf")
        logits[:, prefix_ids] = float("-inf")

        # Structural grammar constraints (CHANGES.md S3-S7)
        _is_instrument = isinstance(prev_tok, tuple) and (
            (len(prev_tok) == 3 and prev_tok[0] != "prefix")
            or (len(prev_tok) == 2 and prev_tok[0] == "drum")
        )
        _is_pedal = prev_tok in {tokenizer.ped_on_tok, tokenizer.ped_off_tok}

        if _is_instrument or _is_pedal:
            # After note/drum/pedal: force onset
            mask = mx.full(logits.shape, float("-inf"))
            for oid in onset_ids:
                mask[:, oid] = 0.0
            logits = logits + mask
        elif isinstance(prev_tok, tuple) and prev_tok[0] == "onset":
            prev_prev_tok = tokenizer.id_to_tok[enc_seq[0, idx - 2].item()]
            _pp_inst = isinstance(prev_prev_tok, tuple) and (
                (len(prev_prev_tok) == 3 and prev_prev_tok[0] != "prefix")
                or (len(prev_prev_tok) == 2 and prev_prev_tok[0] == "drum")
            )
            if _pp_inst:
                # note -> onset -> must be dur
                mask = mx.full(logits.shape, float("-inf"))
                for did in dur_ids:
                    mask[:, did] = 0.0
                logits = logits + mask
            else:
                # pedal -> onset -> free (mask mid-event tokens)
                logits[:, dur_ids] = float("-inf")
                logits[:, onset_ids] = float("-inf")
        else:
            # Free position: mask mid-event tokens
            logits[:, dur_ids] = float("-inf")
            logits[:, onset_ids] = float("-inf")

        if temperature > 0.0:
            next_token_ids = sample_min_p(logits / temperature, min_p).flatten()
        else:
            next_token_ids = mx.argmax(logits, axis=-1).flatten()

        enc_seq[:, idx] = next_token_ids
        next_token = tokenizer.id_to_tok[next_token_ids[0].item()]

        generated.append(next_token)
        if next_token == tokenizer.eos_tok:
            break
        idx += 1

    return generated


def main():
    prompt_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ARIA_DIR, "example-prompts", "nocturne.mid"
    )
    max_gen_tokens = int(sys.argv[2]) if len(sys.argv) > 2 else 500
    save_path = sys.argv[3] if len(sys.argv) > 3 else "recordings/test_demo_gen.mid"

    prompt_name = os.path.splitext(os.path.basename(prompt_path))[0]
    print(f"=== Demo Pipeline Test: {prompt_name} ===")
    print(f"  Checkpoint: model-demo.safetensors (vocab 17729)")
    print(f"  Sampling: temp=0.95, min_p=0.03 (upstream defaults)")
    print(f"  Beam search: width={BEAM_WIDTH}, time_tok_weight={TIME_TOK_WEIGHTING}")
    print(f"  PED_OFF boost: +3")
    print(f"  Max gen tokens: {max_gen_tokens}")
    print()

    # 1. Load model (same as demo_mlx.py load_model)
    config_path = pathlib.Path(ARIA_DIR, "demo", "config.json")
    tokenizer = AbsTokenizer(config_path=config_path)
    model_config = ModelConfig(**load_model_config("medium-emb"))
    model_config.set_vocab_size(tokenizer.vocab_size)

    weights = mx.load("checkpoints/model-demo.safetensors")
    for key, weight in weights.items():
        if weight.dtype != DTYPE:
            weights[key] = weight.astype(DTYPE)

    model = TransformerLM(model_config)
    model.load_weights(list(weights.items()), strict=False)
    mx.eval(model.parameters())
    print(f"Model loaded: vocab={tokenizer.vocab_size}")

    # 2. Build prompt (same as demo's capture → tokenize pipeline)
    midi_dict = MidiDict.from_midi(prompt_path)
    priming_seq = get_inference_prompt(
        midi_dict=midi_dict, tokenizer=tokenizer, prompt_len_ms=15000
    )
    priming_seq_len = len(priming_seq)
    print(f"Prompt: {priming_seq_len} tokens")

    # 3. Setup cache and encode
    model.eval()
    model.setup_cache(batch_size=1, max_seq_len=MAX_SEQ_LEN, dtype=DTYPE)

    enc_seq = mx.array(
        [tokenizer.encode(priming_seq + [tokenizer.pad_tok] * (MAX_SEQ_LEN - priming_seq_len))],
        dtype=mx.int32,
    )

    # 4. Prefill (matches demo generate_tokens, simplified: full prefill instead of chunked)
    start_idx = max(2, priming_seq_len - 3 * 3 - 1)  # ~last 3 notes worth
    print(f"Prefilling positions 0..{start_idx - 1}")
    t0 = time.time()

    input_pos = mx.arange(0, start_idx, dtype=mx.int32)
    mx.eval(prefill(model, idxs=enc_seq[:, :start_idx], input_pos=input_pos))
    print(f"  Prefill: {(time.time() - t0)*1000:.0f}ms")

    # 5. Duration recalculation (speculative decoding)
    print(f"Recalculating durations from position {start_idx}...")
    t0 = time.time()
    enc_seq, priming_seq, next_logits = recalc_dur_tokens_chunked(
        model, list(priming_seq), enc_seq, tokenizer, start_idx
    )
    print(f"  Duration recalc: {(time.time() - t0)*1000:.0f}ms")

    # 6. Beam search for first 2 tokens
    print("Beam search for first 2 tokens...")
    t0 = time.time()
    enc_seq, idx, first_two = decode_first_tokens(
        model, next_logits, enc_seq, priming_seq, tokenizer
    )
    print(f"  Beam search: {(time.time() - t0)*1000:.0f}ms")

    # 7. Autoregressive decode
    print(f"Decoding up to {max_gen_tokens} tokens (temp=0.95, min_p=0.03)...")
    t0 = time.time()
    generated = first_two + decode_tokens(
        model, enc_seq, tokenizer, idx,
        temperature=0.95, min_p=0.03, max_tokens=max_gen_tokens,
    )
    decode_time = time.time() - t0
    print(f"  Decoded {len(generated)} tokens in {decode_time*1000:.0f}ms "
          f"({len(generated)/decode_time:.0f} tok/s)")

    # 8. Stats
    note_toks = sum(1 for t in generated if isinstance(t, tuple) and len(t) == 3 and t[0] != "prefix")
    time_toks = sum(1 for t in generated if t == tokenizer.time_tok)
    ped_toks = sum(1 for t in generated if t in {tokenizer.ped_on_tok, tokenizer.ped_off_tok})
    print(f"\n  Generated tokens: {len(generated)}")
    print(f"  Notes: {note_toks}, <T>: {time_toks}, Pedal: {ped_toks}")

    # 9. Save full sequence (prompt + generated)
    full_seq = priming_seq + generated
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    midi_out = tokenizer.detokenize(full_seq)
    midi_out.to_midi().save(save_path)
    print(f"  Saved: {save_path}")

    # 10. Analyze output MIDI
    midi_check = MidiDict.from_midi(save_path)
    notes = midi_check.note_msgs
    if notes:
        last_tick = max(n["data"]["end"] for n in notes)
        dur_ms = midi_check.tick_to_ms(last_tick)
        print(f"  Output: {len(notes)} notes, {dur_ms/1000:.1f}s, "
              f"{len(notes)/(dur_ms/60000):.0f} notes/min")


if __name__ == "__main__":
    main()
