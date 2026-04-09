#!/usr/bin/env python3
"""Headless Aria generation for parameter sweeps.

Loads the demo checkpoint (vocab 17729, with pedal tokens) and generates
a continuation of a prompt MIDI file using specified sampling parameters.
Includes the same grammar constraints as demo_mlx.py to ensure valid output.

Usage:
    python sweep_generate.py \
        --checkpoint checkpoints/model-demo.safetensors \
        --prompt_midi example-prompts/waltz.mid \
        --prompt_duration 15 \
        --temp 0.85 --min_p 0.05 \
        --length 2048 \
        --save_path recordings/sweep/waltz__temp0.85__minp0.05.mid
"""

import argparse
import math
import os
import sys

KV_CHUNK_SIZE = 256
MIN_NOTE_LENGTH_MS = 10


def parse_args():
    p = argparse.ArgumentParser(description="Headless Aria generation")
    p.add_argument("--checkpoint", required=True, help="Path to .safetensors checkpoint")
    p.add_argument("--aria_dir", required=True, help="Path to the aria repo root")
    p.add_argument("--prompt_midi", required=True, help="Path to prompt MIDI file")
    p.add_argument("--prompt_duration", type=int, default=15, help="Prompt duration in seconds")
    p.add_argument("--temp", type=float, required=True, help="Sampling temperature")
    p.add_argument("--min_p", type=float, default=None, help="min_p sampling parameter")
    p.add_argument("--top_p", type=float, default=None, help="top_p sampling parameter")
    p.add_argument("--length", type=int, default=2048, help="Max new tokens to generate")
    p.add_argument("--save_path", required=True, help="Output MIDI file path")
    p.add_argument("--force_end", action="store_true", help="Force piece ending")
    p.add_argument("--penalties", action="store_true", default=True,
                   help="Enable pedal/time penalties (default: on for standalone gen, see CHANGES.md §14)")
    p.add_argument("--no_penalties", action="store_true", help="Disable pedal/time penalties")
    p.add_argument("--no_ped_boost", action="store_true", default=True,
                   help="Disable PED_OFF +3 boost (default: off for standalone gen, see CHANGES.md §13)")
    p.add_argument("--ped_boost", action="store_true", help="Enable PED_OFF +3 boost")
    return p.parse_args()


def _max_kv_pos(pos):
    """Compute KV chunk-aligned max position (matches demo_mlx.py)."""
    last = pos[-1].item() if hasattr(pos[-1], "item") else int(pos[-1])
    return math.ceil(last / KV_CHUNK_SIZE) * KV_CHUNK_SIZE


def generate(model, tokenizer, prompt, max_new_tokens, temp, min_p, top_p,
             force_end, penalties=False, no_ped_boost=False):
    """Generate tokens with grammar constraints (matches demo_mlx.py decode_tokens)."""
    import mlx.core as mx
    from tqdm import tqdm
    from aria.inference.sample_mlx import sample_min_p_mlx, sample_top_p_mlx

    prompt_len = len(prompt)
    total_len = prompt_len + max_new_tokens

    # Encode prompt + padding
    encoded = tokenizer.encode(prompt + [tokenizer.pad_tok] * max_new_tokens)
    seq = mx.array(encoded, dtype=mx.int32).reshape(1, -1)

    model.eval()
    model.setup_cache(batch_size=1, max_seq_len=total_len, dtype=mx.float32)

    # Pre-compute token ID sets for grammar constraints
    dur_ids = [tokenizer.tok_to_id[t] for t in tokenizer.dur_tokens]
    dur_mask_ids = [
        tokenizer.tok_to_id[("dur", ms)]
        for ms in range(0, MIN_NOTE_LENGTH_MS, 10)
    ]
    onset_ids = [tokenizer.tok_to_id[t] for t in tokenizer.onset_tokens]
    prefix_ids = [
        tokenizer.tok_to_id[t]
        for t in tokenizer.tok_to_id
        if isinstance(t, tuple) and len(t) == 3 and t[0] == "prefix"
    ]
    ped_on_id = tokenizer.tok_to_id[tokenizer.ped_on_tok]
    ped_off_id = tokenizer.tok_to_id[tokenizer.ped_off_tok]
    dim_tok_id = tokenizer.tok_to_id[tokenizer.dim_tok]
    eos_tok_id = tokenizer.tok_to_id[tokenizer.eos_tok]

    time_tok_id = tokenizer.tok_to_id[tokenizer.time_tok]
    PEDAL_PENALTY = 1.5
    TIME_PENALTY = 1.5
    MAX_CONSECUTIVE_TIME = 2

    last_tok_is_pedal = False
    dim_tok_inserted = False
    consecutive_time_toks = 0

    print(f"Params: temp={temp}, min_p={min_p}, top_p={top_p}, penalties={penalties}, no_ped_boost={no_ped_boost}, gen_len={max_new_tokens}")

    for idx in tqdm(range(prompt_len, total_len), total=max_new_tokens, leave=False):
        if idx == prompt_len:
            # Prefill entire prompt
            input_pos = mx.arange(0, idx, dtype=mx.int32)
            logits = model(
                idxs=seq[:, :idx],
                input_pos=input_pos,
                max_kv_pos=_max_kv_pos(input_pos),
                offset=input_pos[0],
            )[:, -1]
        else:
            # Decode one token
            input_pos = mx.array([idx - 1], dtype=mx.int32)
            logits = model(
                idxs=seq[:, idx - 1 : idx],
                input_pos=input_pos,
                max_kv_pos=_max_kv_pos(input_pos),
                offset=input_pos[0],
            )[:, -1]

        # --- Logit masking (matches demo_mlx.py decode_tokens) ---

        # Never generate dim_tok mid-generation
        logits[:, dim_tok_id] = float("-inf")

        # Mask very short durations
        logits[:, dur_mask_ids] = float("-inf")

        # Don't allow dur after pedal
        if last_tok_is_pedal:
            logits[:, dur_ids] = float("-inf")

        # Don't allow EOS unless force_end and near the end
        if not force_end:
            logits[:, eos_tok_id] = float("-inf")
        elif force_end and idx < total_len - 130:
            logits[:, eos_tok_id] = float("-inf")

        # PED_OFF boost (upstream default) — can be disabled
        if not no_ped_boost:
            logits[:, ped_off_id] += 3

        # Mask prefix tokens (metadata, never valid during generation)
        logits[:, prefix_ids] = float("-inf")

        # Grammar constraints
        prev_tok = tokenizer.id_to_tok[seq[0, idx - 1].item()]

        _is_instrument = isinstance(prev_tok, tuple) and (
            (len(prev_tok) == 3 and prev_tok[0] != "prefix")
            or (len(prev_tok) == 2 and prev_tok[0] == "drum")
        )

        if _is_instrument or prev_tok in {tokenizer.ped_on_tok, tokenizer.ped_off_tok}:
            # After note/drum/pedal: force onset
            mask = mx.full(logits.shape, float("-inf"))
            for oid in onset_ids:
                mask[:, oid] = 0.0
            logits = logits + mask

        elif isinstance(prev_tok, tuple) and prev_tok[0] == "onset":
            # After onset: check what came before
            prev_prev_tok = tokenizer.id_to_tok[seq[0, idx - 2].item()]
            _prev_is_instrument = isinstance(prev_prev_tok, tuple) and (
                (len(prev_prev_tok) == 3 and prev_prev_tok[0] != "prefix")
                or (len(prev_prev_tok) == 2 and prev_prev_tok[0] == "drum")
            )
            if _prev_is_instrument:
                # note -> onset -> must be dur
                mask = mx.full(logits.shape, float("-inf"))
                for did in dur_ids:
                    mask[:, did] = 0.0
                logits = logits + mask
            else:
                # pedal -> onset -> free (mask mid-event tokens)
                logits[:, dur_ids] = float("-inf")
                logits[:, onset_ids] = float("-inf")
                if penalties:
                    logits[:, ped_on_id] -= PEDAL_PENALTY
                    logits[:, ped_off_id] -= PEDAL_PENALTY
                    logits[:, time_tok_id] -= TIME_PENALTY
        else:
            # Free position (after dur, time, etc.): mask mid-event tokens
            logits[:, dur_ids] = float("-inf")
            logits[:, onset_ids] = float("-inf")
            if penalties:
                logits[:, ped_on_id] -= PEDAL_PENALTY
                logits[:, ped_off_id] -= PEDAL_PENALTY
                logits[:, time_tok_id] -= TIME_PENALTY
                if consecutive_time_toks >= MAX_CONSECUTIVE_TIME:
                    logits[:, time_tok_id] -= 10.0

        # --- Sampling ---
        if temp > 0.0:
            probs = mx.softmax(logits / temp, axis=-1)
            if min_p is not None:
                next_token_ids = sample_min_p_mlx(probs, min_p).flatten()
            elif top_p is not None:
                next_token_ids = sample_top_p_mlx(probs, top_p).flatten()
        else:
            next_token_ids = mx.argmax(logits, axis=-1).flatten()

        # Handle force_end dim_tok insertion
        if force_end and idx >= total_len - 130 and not dim_tok_inserted:
            next_tok = tokenizer.id_to_tok[next_token_ids[0].item()]
            if not (isinstance(next_tok, tuple) and next_tok[0] in ("dur", "onset")):
                next_token_ids = mx.array([dim_tok_id], dtype=mx.int32)
                dim_tok_inserted = True

        seq[:, idx] = next_token_ids
        next_tok = tokenizer.id_to_tok[next_token_ids[0].item()]

        # Track pedal state and time tokens
        if next_tok in {tokenizer.ped_on_tok, tokenizer.ped_off_tok}:
            last_tok_is_pedal = True
        else:
            last_tok_is_pedal = False

        if next_tok == tokenizer.time_tok:
            consecutive_time_toks += 1
        else:
            consecutive_time_toks = 0

        # Check for EOS
        if next_tok == tokenizer.eos_tok:
            break

    # Decode back to token sequence
    result = tokenizer.decode(seq[0].tolist())
    if tokenizer.eos_tok in result:
        result = result[: result.index(tokenizer.eos_tok) + 1]

    return result


def main():
    args = parse_args()
    sys.path.insert(0, args.aria_dir)

    import mlx.core as mx
    from ariautils.midi import MidiDict
    from ariautils.tokenizer import AbsTokenizer
    from aria.inference import get_inference_prompt
    from aria.inference.model_mlx import TransformerLM
    from aria.model import ModelConfig
    from aria.config import load_model_config

    # Use the demo tokenizer config (include_pedal: true -> vocab 17729)
    demo_config_path = os.path.join(args.aria_dir, "demo", "config.json")
    tokenizer = AbsTokenizer(config_path=demo_config_path)

    # Load model with dynamic vocab sizing (same as demo_mlx.py:load_model)
    model_config = ModelConfig(**load_model_config("medium-emb"))
    model_config.set_vocab_size(tokenizer.vocab_size)

    weights = mx.load(args.checkpoint)
    emb_shape = weights["model.tok_embeddings.weight"].shape[0]
    assert tokenizer.vocab_size == emb_shape, (
        f"Vocab mismatch: tokenizer={tokenizer.vocab_size}, "
        f"checkpoint={emb_shape}. "
        f"Ensure demo config.json has include_pedal: true."
    )

    model = TransformerLM(model_config)
    model.load_weights(list(weights.items()), strict=False)
    mx.eval(model.parameters())
    print(f"Model loaded: vocab={tokenizer.vocab_size}, checkpoint={os.path.basename(args.checkpoint)}")

    # Prepare prompt
    midi_dict = MidiDict.from_midi(args.prompt_midi)
    prompt = get_inference_prompt(
        midi_dict=midi_dict,
        tokenizer=tokenizer,
        prompt_len_ms=1000 * args.prompt_duration,
    )
    print(f"Prompt: {len(prompt)} tokens from {os.path.basename(args.prompt_midi)} ({args.prompt_duration}s)")

    # Default to top_p if neither specified (min_p kills note tokens — see CHANGES.md §12)
    min_p = args.min_p
    top_p = args.top_p
    if min_p is None and top_p is None:
        top_p = 0.95

    max_new_tokens = min(8096 - len(prompt), args.length)

    # Resolve flag overrides (penalties on + no ped boost by default — see CHANGES.md §12-14)
    use_penalties = not args.no_penalties
    use_no_ped_boost = not args.ped_boost

    # Generate
    result = generate(
        model=model,
        tokenizer=tokenizer,
        prompt=prompt,
        max_new_tokens=max_new_tokens,
        temp=args.temp,
        min_p=min_p,
        top_p=top_p,
        force_end=args.force_end,
        penalties=use_penalties,
        no_ped_boost=use_no_ped_boost,
    )

    # Save
    os.makedirs(os.path.dirname(args.save_path), exist_ok=True)
    midi_dict = tokenizer.detokenize(result)
    midi = midi_dict.to_midi()
    midi.save(args.save_path)
    print(f"Saved: {args.save_path}")


if __name__ == "__main__":
    main()
