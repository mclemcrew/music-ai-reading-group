#!/usr/bin/env python3
"""Chunked generation: replicate the NeurIPS demo loop without a human.

The interactive demo produces dense, musical output because it:
  1. Uses beam search (width=3, TIME_TOK_WEIGHTING=-5) to start each turn with a NOTE
  2. Generates short bursts (~2-5s), never long enough for degeneration to snowball
  3. Has duration recalculation to prevent hanging notes
  4. Refreshes context every few seconds with human input

We replicate this headlessly by periodically re-running beam search every
~5s of generated music time. This "re-anchors" the model toward notes
and prevents the sparsity snowball.

                   ┌─────────────────────────────────┐
                   │ For each chunk (~5s music time): │
                   │  1. Beam search → note start     │
                   │  2. Autoregressive decode         │
                   │  3. Track music time              │
                   │  4. When chunk full → loop        │
                   └─────────────────────────────────┘

Usage:
    python test_chunked_gen.py [prompt_midi] [options]
    python test_chunked_gen.py waltz.mid --chunks 6 --chunk_ms 5000
"""

import sys
import os
import math
import pathlib
import time
import argparse

ARIA_DIR = "/Users/mclemens/Development/aria"
sys.path.insert(0, ARIA_DIR)

import mlx.core as mx
import mlx.nn as nn

KV_CHUNK_SIZE = 256
DTYPE = mx.bfloat16
MAX_SEQ_LEN = 4096

# Demo constants
BEAM_WIDTH = 3
TIME_TOK_WEIGHTING = -5
MIN_NOTE_LENGTH_MS = 10


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


# --- Model interface (matches demo_mlx.py with EMBEDDING_OFFSET) ---

EMBEDDING_OFFSET = 1  # Position 0 = embedding


def _max_kv_pos(pos):
    last = pos[-1].item() if hasattr(pos[-1], "item") else int(pos[-1])
    return math.ceil(last / KV_CHUNK_SIZE) * KV_CHUNK_SIZE


def prefill(model, idxs, input_pos):
    return model(
        idxs=idxs,
        input_pos=input_pos + EMBEDDING_OFFSET,
        max_kv_pos=_max_kv_pos(input_pos + EMBEDDING_OFFSET),
        offset=input_pos[0] + EMBEDDING_OFFSET,
    )


def decode_one(model, idxs, input_pos):
    assert input_pos.shape[-1] == 1
    return model(
        idxs=idxs,
        input_pos=input_pos + EMBEDDING_OFFSET,
        max_kv_pos=_max_kv_pos(input_pos + EMBEDDING_OFFSET),
        offset=input_pos[0] + EMBEDDING_OFFSET,
    )[:, -1]


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


def sample_top_p(logits, top_p, temp):
    """Sample with top_p in MLX (no torch dependency for this path)."""
    import torch
    import numpy as np
    from aria.inference import sample_top_p as _sample_top_p

    probs = mx.softmax(logits.astype(mx.float32) / temp, axis=-1)
    probs_t = torch.from_numpy(np.array(probs))
    return int(_sample_top_p(probs_t, top_p).item())


# --- Beam search (from demo_mlx.py:497, adapted for headless use) ---

def beam_search_first_two(model, logits, enc_seq, tokenizer, idx):
    """Beam search for first 2 tokens of a chunk. Returns (tok1, tok2, idx_after).

    Key mechanism: TIME_TOK_WEIGHTING=-5 strongly discourages starting
    with silence, forcing the model to begin each chunk with a note.
    """
    time_tok_id = tokenizer.tok_to_id[tokenizer.time_tok]
    eos_tok_id = tokenizer.tok_to_id[tokenizer.eos_tok]
    dim_tok_id = tokenizer.tok_to_id[tokenizer.dim_tok]
    ped_off_id = tokenizer.tok_to_id[tokenizer.ped_off_tok]
    onset_ids = [tokenizer.tok_to_id[t] for t in tokenizer.onset_tokens]

    # Mask tokens that aren't useful starts: we want NOTES, not pedal/silence
    logits[:, dim_tok_id] = float("-inf")
    logits[:, eos_tok_id] = float("-inf")
    logits[:, ped_off_id] = float("-inf")

    # The beam's ONLY job: start each chunk with a NOTE.
    # Mask everything that isn't a note instrument token.
    _has_pedal = hasattr(tokenizer, 'ped_on_tok') and tokenizer.ped_on_tok in tokenizer.tok_to_id
    if _has_pedal:
        logits[:, tokenizer.tok_to_id[tokenizer.ped_on_tok]] = float("-inf")
    logits[:, time_tok_id] = float("-inf")  # No silence starts

    # Mask onset, dur — these are mid-event tokens, not valid at free positions
    dur_ids = [tokenizer.tok_to_id[t] for t in tokenizer.dur_tokens]
    logits[:, onset_ids] = float("-inf")
    logits[:, dur_ids] = float("-inf")

    # Mask prefix tokens and non-piano instruments
    prefix_ids = [tokenizer.tok_to_id[t] for t in tokenizer.tok_to_id
                  if isinstance(t, tuple) and len(t) == 3 and t[0] == "prefix"]
    logits[:, prefix_ids] = float("-inf")
    non_piano_ids = [tokenizer.tok_to_id[t] for t in tokenizer.tok_to_id
                     if isinstance(t, tuple) and len(t) == 3
                     and t[0] not in ("prefix", "piano")]
    logits[:, non_piano_ids] = float("-inf")

    # Get top-K candidates (all should be note instrument tokens now)
    log_probs = nn.log_softmax(logits, axis=-1)
    top_ids = mx.argsort(log_probs, axis=-1)[0, -BEAM_WIDTH:]
    top_log_probs = log_probs[0, top_ids]

    top_toks = [tokenizer.id_to_tok[id] for id in top_ids.tolist()]

    best_score = float("-inf")
    best_tok_id_1, best_tok_id_2 = None, None

    for i in range(BEAM_WIDTH):
        tok = top_toks[i]
        tok_id = top_ids[i].item()
        tok_log_prob = top_log_probs[i]

        # Score the second token
        next_logits = decode_one(
            model,
            idxs=mx.array([[tok_id]], dtype=mx.int32),
            input_pos=mx.array([idx - 1], dtype=mx.int32),
        )

        next_log_probs = nn.log_softmax(next_logits, axis=-1)
        next_log_probs[:, eos_tok_id] = float("-inf")
        next_log_probs[:, dim_tok_id] = float("-inf")
        next_log_probs[:, ped_off_id] = float("-inf")

        # No double time tokens
        if tok_id == time_tok_id:
            next_log_probs[:, time_tok_id] = float("-inf")

        # Grammar: after note/pedal → force onset
        _is_inst = isinstance(tok, tuple) and (
            (len(tok) == 3 and tok[0] != "prefix")
            or (len(tok) == 2 and tok[0] == "drum")
        )
        _is_ped_on = hasattr(tokenizer, 'ped_on_tok') and tok == tokenizer.ped_on_tok
        if _is_inst or _is_ped_on:
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

    # Write tokens into sequence
    enc_seq[:, idx - 1] = best_tok_id_1
    enc_seq[:, idx] = best_tok_id_2

    # Re-insert tok_1 to fix KV cache (beam search decoded all candidates at idx-1)
    mx.eval(decode_one(
        model,
        idxs=mx.array([[best_tok_id_1]], dtype=mx.int32),
        input_pos=mx.array([idx - 1], dtype=mx.int32),
    ))

    return best_tok_1, best_tok_2, idx + 1


# --- Autoregressive decode with grammar (one chunk) ---

def decode_chunk(model, enc_seq, tokenizer, idx, temp, top_p,
                 chunk_ms, grammar_ids, initial_time_ms=0, pedal_penalty=4.0,
                 max_notes_per_chunk=40, time_penalty=3.0,
                 min_notes_before_time=4):
    """Decode tokens until chunk_ms of music time or max notes reached.

    initial_time_ms: music time already consumed by beam search tokens
    max_notes_per_chunk: cap to prevent density explosions
    time_penalty: logit penalty on <T> at free positions — forces notes over silence
    min_notes_before_time: fully mask <T> until N notes generated in this chunk,
        forcing the model to produce chords/passages before resting
    Returns (generated_tokens, next_idx, chunk_music_ms).
    """
    dur_ids, onset_ids, prefix_ids, dur_mask_ids, non_piano_ids = grammar_ids
    _has_pedal = hasattr(tokenizer, 'ped_on_tok') and tokenizer.ped_on_tok in tokenizer.tok_to_id
    if _has_pedal:
        _ped_on_id = tokenizer.tok_to_id[tokenizer.ped_on_tok]
        _ped_off_id = tokenizer.tok_to_id[tokenizer.ped_off_tok]
    _time_tok_id = tokenizer.tok_to_id[tokenizer.time_tok]

    generated = []
    chunk_time_ms = initial_time_ms
    consecutive_time = 0
    chunk_notes = 0

    while idx < MAX_SEQ_LEN:
        prev_tok_id = enc_seq[0, idx - 1]
        prev_tok = tokenizer.id_to_tok[prev_tok_id.item()]

        logits = decode_one(
            model,
            idxs=mx.array([[prev_tok_id]], dtype=mx.int32),
            input_pos=mx.array([idx - 1], dtype=mx.int32),
        )

        # Always mask
        logits[:, tokenizer.tok_to_id[tokenizer.dim_tok]] = float("-inf")
        logits[:, tokenizer.tok_to_id[tokenizer.eos_tok]] = float("-inf")
        logits[:, dur_mask_ids] = float("-inf")
        logits[:, prefix_ids] = float("-inf")
        logits[:, non_piano_ids] = float("-inf")  # Piano only

        # Grammar constraints
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
            pp = tokenizer.id_to_tok[enc_seq[0, idx - 2].item()]
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
            # Free position (after dur, time, pedal+onset)
            logits[:, dur_ids] = float("-inf")
            logits[:, onset_ids] = float("-inf")

            # Pedal penalty — push probability toward notes
            if pedal_penalty > 0.0 and _has_pedal:
                logits[:, _ped_on_id] -= pedal_penalty
                logits[:, _ped_off_id] -= pedal_penalty

            # Time penalty — the single <T> token absorbs ~18% probability
            # while each note token has <0.5%. Without this penalty, the model
            # generates <T> after 1-2 notes instead of building chords/passages.
            if time_penalty > 0.0:
                logits[:, _time_tok_id] -= time_penalty

            # Force notes before silence: fully mask <T> until we've generated
            # enough notes. This is what makes the model produce CHORDS instead
            # of single notes followed by 5s of silence.
            if chunk_notes < min_notes_before_time:
                logits[:, _time_tok_id] = float("-inf")

        # Sample
        if temp > 0.0:
            next_tok_id = sample_top_p(logits, top_p, temp)
        else:
            next_tok_id = int(mx.argmax(logits, axis=-1).item())

        enc_seq[:, idx] = next_tok_id
        tok = tokenizer.id_to_tok[next_tok_id]
        generated.append(tok)

        # Track notes and music time
        if isinstance(tok, tuple) and len(tok) == 3 and tok[0] == "piano":
            chunk_notes += 1

        if tok == tokenizer.time_tok:
            chunk_time_ms += 5000
            consecutive_time += 1
        else:
            consecutive_time = 0
            if isinstance(tok, tuple) and tok[0] == "onset":
                seg_start = (chunk_time_ms // 5000) * 5000
                chunk_time_ms = max(chunk_time_ms, seg_start + tok[1])

        idx += 1

        if tok == tokenizer.eos_tok:
            break

        # Only break at SAFE positions — after dur, time, or pedal+onset.
        # Breaking mid-triple (e.g., after piano but before onset) corrupts
        # the sequence and causes grammar violations in the next chunk.
        _is_dur = isinstance(tok, tuple) and tok[0] == "dur"
        _is_time = tok == tokenizer.time_tok
        _is_ped_onset = (isinstance(tok, tuple) and tok[0] == "onset"
                         and len(generated) >= 2
                         and generated[-2] in {tokenizer.ped_on_tok, tokenizer.ped_off_tok})
        _at_safe_position = _is_dur or _is_time or _is_ped_onset

        if not _at_safe_position:
            continue  # Keep generating until we reach a safe break point

        # End chunk conditions (only at safe positions):
        if chunk_time_ms >= chunk_ms:
            break
        if consecutive_time >= 2:
            break
        if chunk_notes >= max_notes_per_chunk:
            break

    return generated, idx, chunk_time_ms


# --- Main orchestrator ---

def generate_chunked(model, tokenizer, prompt, embedding_vec,
                     num_chunks, chunk_ms, temp, top_p, prompt_ms=10000,
                     max_notes_per_chunk=40, time_penalty=3.0,
                     min_notes_before_time=4):
    """Generate music in chunks with periodic beam search re-anchoring."""
    prompt_len = len(prompt)
    total_slots = MAX_SEQ_LEN - EMBEDDING_OFFSET

    # Encode
    encoded = tokenizer.encode(prompt + [tokenizer.pad_tok] * (total_slots - prompt_len))
    enc_seq = mx.array([encoded], dtype=mx.int32)

    # Setup cache and inject embedding
    model.eval()
    model.setup_cache(batch_size=1, max_seq_len=MAX_SEQ_LEN, dtype=DTYPE)
    emb_array = mx.array([embedding_vec], dtype=DTYPE)
    model.fill_condition_kv(cond_emb=emb_array)

    # Precompute grammar token IDs
    dur_ids = [tokenizer.tok_to_id[t] for t in tokenizer.dur_tokens]
    onset_ids = [tokenizer.tok_to_id[t] for t in tokenizer.onset_tokens]
    prefix_ids = [tokenizer.tok_to_id[t] for t in tokenizer.tok_to_id
                  if isinstance(t, tuple) and len(t) == 3 and t[0] == "prefix"]
    dur_mask_ids = [tokenizer.tok_to_id[("dur", ms)] for ms in range(0, MIN_NOTE_LENGTH_MS, 10)]

    # Mask non-piano instrument tokens and out-of-range piano tokens
    non_piano_ids = [
        tokenizer.tok_to_id[t] for t in tokenizer.tok_to_id
        if isinstance(t, tuple) and len(t) == 3
        and t[0] not in ("prefix", "piano")
    ]
    # Clamp piano to standard 88-key range (A0=21 to C8=108) and valid velocity (1-127)
    out_of_range_ids = [
        tokenizer.tok_to_id[t] for t in tokenizer.tok_to_id
        if isinstance(t, tuple) and len(t) == 3 and t[0] == "piano"
        and (t[1] < 21 or t[1] > 108 or t[2] < 1 or t[2] > 127)
    ]
    non_piano_ids.extend(out_of_range_ids)
    print(f"  Masking {len(non_piano_ids)} invalid instrument tokens "
          f"(non-piano + out-of-range)")

    grammar_ids = (dur_ids, onset_ids, prefix_ids, dur_mask_ids, non_piano_ids)

    # Prefill prompt
    print(f"  Prefilling {prompt_len} prompt tokens...")
    input_pos = mx.arange(0, prompt_len, dtype=mx.int32)
    logits = prefill(model, idxs=enc_seq[:, :prompt_len], input_pos=input_pos)[:, -1]

    idx = prompt_len + 1  # +1 because enc_seq is 0-indexed, next write is at prompt_len
    all_generated = []
    total_music_ms = 0

    # Force time advancement past the prompt boundary.
    # The prompt may not have enough <T> tokens to reach prompt_end_ms.
    # We need ceil(prompt_ms / 5000) <T> tokens total.
    time_tok_id = tokenizer.tok_to_id[tokenizer.time_tok]
    time_toks_in_prompt = prompt.count(tokenizer.time_tok)
    time_toks_needed = math.ceil(prompt_ms / 5000)
    time_toks_to_add = max(0, time_toks_needed - time_toks_in_prompt)

    if time_toks_to_add > 0:
        print(f"  Advancing {time_toks_to_add} <T> token(s) past prompt boundary "
              f"(prompt has {time_toks_in_prompt}, need {time_toks_needed})...")
        for _ in range(time_toks_to_add):
            enc_seq[:, idx - 1] = time_tok_id
            logits = decode_one(
                model,
                idxs=mx.array([[time_tok_id]], dtype=mx.int32),
                input_pos=mx.array([idx - 1], dtype=mx.int32),
            )
            all_generated.append(tokenizer.time_tok)
            idx += 1

    print(f"  Generating {num_chunks} chunks of ~{chunk_ms/1000:.0f}s each "
          f"(temp={temp}, top_p={top_p})...")
    print()

    for chunk_i in range(num_chunks):
        if idx >= MAX_SEQ_LEN - 10:
            print(f"  [chunk {chunk_i+1}] Ran out of sequence space at position {idx}")
            break

        # BEAM SEARCH: force the model to start this chunk with a note
        tok1, tok2, idx = beam_search_first_two(
            model, logits, enc_seq, tokenizer, idx
        )
        all_generated.extend([tok1, tok2])

        # Track music time from beam tokens (for this chunk's budget)
        beam_time_ms = 0
        for t in [tok1, tok2]:
            if t == tokenizer.time_tok:
                beam_time_ms += 5000
            elif isinstance(t, tuple) and t[0] == "onset":
                seg_start = (beam_time_ms // 5000) * 5000
                beam_time_ms = max(beam_time_ms, seg_start + t[1])

        # AUTOREGRESSIVE DECODE for this chunk (passing beam time so budget is accurate)
        chunk_toks, idx, chunk_ms_actual = decode_chunk(
            model, enc_seq, tokenizer, idx, temp, top_p, chunk_ms, grammar_ids,
            initial_time_ms=beam_time_ms,
            max_notes_per_chunk=max_notes_per_chunk,
            time_penalty=time_penalty,
            min_notes_before_time=min_notes_before_time,
        )
        all_generated.extend(chunk_toks)
        total_music_ms += chunk_ms_actual

        # Stats for this chunk
        chunk_all = [tok1, tok2] + chunk_toks
        notes = sum(1 for t in chunk_all
                    if isinstance(t, tuple) and len(t) == 3 and t[0] != "prefix")
        time_toks = sum(1 for t in chunk_all if t == tokenizer.time_tok)
        ped_toks = sum(1 for t in chunk_all
                       if hasattr(tokenizer, 'ped_on_tok') and t in {tokenizer.ped_on_tok, tokenizer.ped_off_tok})

        # Show first few generated tokens for debugging
        sample = chunk_all[:12]
        sample_str = ", ".join(str(t) for t in sample)
        if len(chunk_all) > 12:
            sample_str += f", ... (+{len(chunk_all)-12} more)"
        print(f"  [chunk {chunk_i+1}/{num_chunks}] beam=({tok1}, {tok2}) | "
              f"{len(chunk_all)} toks, {notes} notes, {time_toks} <T>, {ped_toks} ped | "
              f"music: +{chunk_ms_actual/1000:.1f}s (total {total_music_ms/1000:.1f}s)")
        print(f"    tokens: {sample_str}")

        # Get logits for next chunk's beam search
        # (the decode_chunk already called decode_one for the last token,
        #  so the KV cache is up to date through idx-1)
        if idx < MAX_SEQ_LEN - 1:
            prev_tok_id = enc_seq[0, idx - 1]
            logits = decode_one(
                model,
                idxs=mx.array([[prev_tok_id]], dtype=mx.int32),
                input_pos=mx.array([idx - 1], dtype=mx.int32),
            )

        if any(t == tokenizer.eos_tok for t in chunk_toks):
            break

    return prompt + all_generated, total_music_ms


def main():
    p = argparse.ArgumentParser(description="Chunked generation with periodic beam search")
    p.add_argument("prompt_midi", nargs="?",
                   default=os.path.join(ARIA_DIR, "example-prompts", "nocturne.mid"))
    p.add_argument("--chunks", type=int, default=6, help="Number of generation chunks")
    p.add_argument("--chunk_ms", type=int, default=5000, help="Target music time per chunk (ms)")
    p.add_argument("--temp", type=float, default=0.95)
    p.add_argument("--top_p", type=float, default=0.95)
    p.add_argument("--prompt_ms", type=int, default=10000, help="Prompt duration in ms")
    p.add_argument("--max_notes_per_chunk", type=int, default=40,
                   help="Max notes per chunk to prevent density explosions")
    p.add_argument("--time_penalty", type=float, default=3.0,
                   help="Logit penalty on <T> at free positions (forces notes over silence)")
    p.add_argument("--min_notes", type=int, default=4,
                   help="Min notes per chunk before <T> is allowed (forces chords)")
    p.add_argument("--save", default="recordings/test_chunked.mid")
    p.add_argument("--no_embedding", action="store_true", help="Skip style embedding")
    args = p.parse_args()

    prompt_name = os.path.splitext(os.path.basename(args.prompt_midi))[0]
    print(f"=== Chunked Generation: {prompt_name} ===")
    print(f"  {args.chunks} chunks × {args.chunk_ms/1000:.0f}s = ~{args.chunks * args.chunk_ms / 1000:.0f}s target")

    # 1. Compute embedding
    if not args.no_embedding:
        t0 = time.time()
        embedding = compute_embedding(args.prompt_midi)
        print(f"  Embedding computed in {time.time() - t0:.1f}s")
    else:
        embedding = None

    # 2. Load model-demo
    from ariautils.tokenizer import AbsTokenizer
    from ariautils.midi import MidiDict
    from aria.inference import get_inference_prompt
    from aria.inference.model_mlx import TransformerLM
    from aria.model import ModelConfig
    from aria.config import load_model_config
    import types

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
    print(f"  Model loaded: vocab={tokenizer.vocab_size}")

    # 3. Build prompt
    midi_dict = MidiDict.from_midi(args.prompt_midi)
    prompt = get_inference_prompt(
        midi_dict=midi_dict, tokenizer=tokenizer, prompt_len_ms=args.prompt_ms,
    )
    prompt_time_toks = prompt.count(tokenizer.time_tok)
    prompt_last_ms = tokenizer.calc_length_ms(prompt, onset=True)
    print(f"  Prompt: {len(prompt)} tokens ({args.prompt_ms/1000:.0f}s), "
          f"{prompt_time_toks} <T> tokens, last_onset={prompt_last_ms}ms")

    # Use zero embedding if skipping conditioning
    if embedding is None:
        embedding = [0.0] * model_config.emb_size

    # 4. Generate
    t0 = time.time()
    result, total_music_ms = generate_chunked(
        model, tokenizer, prompt, embedding,
        num_chunks=args.chunks, chunk_ms=args.chunk_ms,
        temp=args.temp, top_p=args.top_p,
        prompt_ms=args.prompt_ms,
        max_notes_per_chunk=args.max_notes_per_chunk,
        time_penalty=args.time_penalty,
        min_notes_before_time=args.min_notes,
    )
    gen_time = time.time() - t0

    # 5. Save and analyze
    os.makedirs(os.path.dirname(args.save), exist_ok=True)
    midi_out = tokenizer.detokenize(result)
    midi_out.to_midi().save(args.save)

    m = MidiDict.from_midi(args.save)
    notes = m.note_msgs
    prompt_ms = args.prompt_ms
    if notes:
        prompt_notes = [n for n in notes if m.tick_to_ms(n['data']['start']) <= prompt_ms]
        gen_notes = [n for n in notes if m.tick_to_ms(n['data']['start']) > prompt_ms]
        total_ms = m.tick_to_ms(max(n['data']['end'] for n in notes))
        gen_ms = total_ms - prompt_ms if total_ms > prompt_ms else 0

        print(f"\n{'='*60}")
        print(f"  PROMPT:    {len(prompt_notes)} notes in {prompt_ms/1000:.0f}s "
              f"({len(prompt_notes)/(prompt_ms/60000):.0f} n/min)")
        print(f"  GENERATED: {len(gen_notes)} notes in {gen_ms/1000:.1f}s", end="")
        if gen_ms > 0:
            print(f" ({len(gen_notes)/(gen_ms/60000):.0f} n/min)")
        else:
            print()
        print(f"  TOTAL:     {len(notes)} notes, {total_ms/1000:.1f}s "
              f"({gen_time:.1f}s compute)")

        # Pitch/velocity analysis
        if gen_notes:
            pp = [n['data']['pitch'] for n in prompt_notes]
            gp = [n['data']['pitch'] for n in gen_notes]
            pv = [n['data']['velocity'] for n in prompt_notes]
            gv = [n['data']['velocity'] for n in gen_notes]
            print(f"  Prompt  pitch: {min(pp)}-{max(pp)} (μ={sum(pp)/len(pp):.0f})  "
                  f"vel: {min(pv)}-{max(pv)} (μ={sum(pv)/len(pv):.0f})")
            print(f"  Gen     pitch: {min(gp)}-{max(gp)} (μ={sum(gp)/len(gp):.0f})  "
                  f"vel: {min(gv)}-{max(gv)} (μ={sum(gv)/len(gv):.0f})")
    else:
        print(f"\n  No notes in output ({gen_time:.1f}s compute)")

    print(f"  Saved: {args.save}")


if __name__ == "__main__":
    main()
