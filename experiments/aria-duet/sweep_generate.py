#!/usr/bin/env python3
"""Headless Aria generation for parameter sweeps.

Uses model-gen checkpoint with default tokenizer (vocab 17727) and top_p
sampling with structural grammar constraints. Also supports model-demo
(vocab 17729, with pedal) via auto-detection.

Style prefix tokens (--form, --genre, --composer) significantly improve
output quality by conditioning the model on the expected musical style.

Usage:
    python sweep_generate.py \
        --checkpoint checkpoints/model-gen.safetensors \
        --aria_dir /path/to/aria \
        --prompt_midi example-prompts/waltz.mid \
        --form waltz --genre classical \
        --save_path recordings/sweep/waltz__temp0.97__topp0.95.mid
"""

import argparse
import math
import os
import sys

KV_CHUNK_SIZE = 256


def parse_args():
    p = argparse.ArgumentParser(description="Headless Aria generation")
    p.add_argument("--checkpoint", required=True, help="Path to .safetensors checkpoint")
    p.add_argument("--aria_dir", required=True, help="Path to the aria repo root")
    p.add_argument("--prompt_midi", required=True, help="Path to prompt MIDI file")
    p.add_argument("--prompt_duration", type=int, default=15, help="Prompt duration in seconds")
    p.add_argument("--temp", type=float, default=0.97, help="Sampling temperature (default: 0.97)")
    p.add_argument("--top_p", type=float, default=0.95, help="Top-p sampling threshold (default: 0.95)")
    p.add_argument("--length", type=int, default=2048, help="Max new tokens to generate")
    p.add_argument("--save_path", required=True, help="Output MIDI file path")
    p.add_argument("--force_end", action="store_true", help="Force piece ending via dim token")
    p.add_argument("--time_penalty", type=float, default=3.0,
                   help="Penalty on <T> (silence) tokens (default: 3.0). "
                        "Needed because one <T> token absorbs ~18%% probability. Set 0 to disable.")
    p.add_argument("--max_consecutive_time", type=int, default=1,
                   help="Max consecutive <T> tokens before hard penalty (default: 1)")
    p.add_argument("--form", type=str, default=None,
                   help="Style prefix: waltz, sonata, prelude, nocturne, étude, mazurka, impromptu, fugue")
    p.add_argument("--genre", type=str, default=None,
                   help="Style prefix: classical, jazz")
    p.add_argument("--composer", type=str, default=None,
                   help="Style prefix: bach, beethoven, mozart, chopin, rachmaninoff, liszt, debussy, etc.")
    return p.parse_args()


def _max_kv_pos(pos):
    """Compute KV chunk-aligned max position (fixes upstream sample_mlx.py bug)."""
    last = pos[-1].item() if hasattr(pos[-1], "item") else int(pos[-1])
    return math.ceil(last / KV_CHUNK_SIZE) * KV_CHUNK_SIZE


def generate(model, tokenizer, prompt, max_new_tokens, temp, top_p,
             force_end, time_penalty=3.0, max_consecutive_time=1):
    """Generate tokens with structural grammar constraints and time penalty."""
    import mlx.core as mx
    from tqdm import tqdm
    from aria.inference import sample_top_p
    import torch
    import numpy as np

    prompt_len = len(prompt)
    total_len = prompt_len + max_new_tokens

    encoded = tokenizer.encode(prompt + [tokenizer.pad_tok] * max_new_tokens)
    seq = mx.array(encoded, dtype=mx.int32).reshape(1, -1)

    model.eval()
    model.setup_cache(batch_size=1, max_seq_len=total_len, dtype=mx.bfloat16)

    dim_tok_id = tokenizer.tok_to_id[tokenizer.dim_tok]
    eos_tok_id = tokenizer.tok_to_id[tokenizer.eos_tok]
    time_tok_id = tokenizer.tok_to_id[tokenizer.time_tok]
    dim_tok_inserted = False
    consecutive_time_toks = 0

    # Pre-compute grammar token sets
    dur_ids = [tokenizer.tok_to_id[t] for t in tokenizer.dur_tokens]
    onset_ids = [tokenizer.tok_to_id[t] for t in tokenizer.onset_tokens]
    prefix_ids = [
        tokenizer.tok_to_id[t]
        for t in tokenizer.tok_to_id
        if isinstance(t, tuple) and len(t) == 3 and t[0] == "prefix"
    ]
    _has_pedal = hasattr(tokenizer, 'ped_on_tok') and tokenizer.ped_on_tok in tokenizer.tok_to_id

    print(f"Params: temp={temp}, top_p={top_p}, time_penalty={time_penalty}, gen_len={max_new_tokens}")

    for idx in tqdm(range(prompt_len, total_len), total=max_new_tokens, leave=False):
        if idx == prompt_len:
            input_pos = mx.arange(0, idx, dtype=mx.int32)
            logits = model(
                idxs=seq[:, :idx],
                input_pos=input_pos,
                max_kv_pos=_max_kv_pos(input_pos),
                offset=input_pos[0],
            )[:, -1]
        else:
            input_pos = mx.array([idx - 1], dtype=mx.int32)
            logits = model(
                idxs=seq[:, idx - 1 : idx],
                input_pos=input_pos,
                max_kv_pos=_max_kv_pos(input_pos),
                offset=input_pos[0],
            )[:, -1]

        # Always mask dim_tok and prefix tokens during generation
        logits[:, dim_tok_id] = float("-inf")
        logits[:, prefix_ids] = float("-inf")

        if not force_end:
            logits[:, eos_tok_id] = float("-inf")
        elif force_end and idx < total_len - 130:
            logits[:, eos_tok_id] = float("-inf")

        # Structural grammar constraints
        if idx > prompt_len:
            prev_tok = tokenizer.id_to_tok[seq[0, idx - 1].item()]

            _is_instrument = isinstance(prev_tok, tuple) and (
                (len(prev_tok) == 3 and prev_tok[0] != "prefix")
                or (len(prev_tok) == 2 and prev_tok[0] == "drum")
            )
            _is_pedal = (
                _has_pedal
                and prev_tok in {tokenizer.ped_on_tok, tokenizer.ped_off_tok}
            )

            if _is_instrument or _is_pedal:
                # After note/drum/pedal: force onset
                mask = mx.full(logits.shape, float("-inf"))
                for oid in onset_ids:
                    mask[:, oid] = 0.0
                logits = logits + mask

            elif isinstance(prev_tok, tuple) and prev_tok[0] == "onset":
                prev_prev_tok = tokenizer.id_to_tok[seq[0, idx - 2].item()]
                _pp_is_instrument = isinstance(prev_prev_tok, tuple) and (
                    (len(prev_prev_tok) == 3 and prev_prev_tok[0] != "prefix")
                    or (len(prev_prev_tok) == 2 and prev_prev_tok[0] == "drum")
                )
                if _pp_is_instrument:
                    # note -> onset -> must be dur
                    mask = mx.full(logits.shape, float("-inf"))
                    for did in dur_ids:
                        mask[:, did] = 0.0
                    logits = logits + mask
                else:
                    # pedal -> onset -> free position (mask mid-event tokens)
                    logits[:, dur_ids] = float("-inf")
                    logits[:, onset_ids] = float("-inf")
            else:
                # Free position (after dur, time, etc.): mask mid-event tokens
                logits[:, dur_ids] = float("-inf")
                logits[:, onset_ids] = float("-inf")

        # Time penalty: reduce <T> dominance (see CHANGES.md S14)
        if time_penalty > 0.0:
            logits[:, time_tok_id] -= time_penalty
            if consecutive_time_toks >= max_consecutive_time:
                logits[:, time_tok_id] -= 10.0

        # Sample with top_p
        if temp > 0.0:
            probs = mx.softmax(logits.astype(mx.float32) / temp, axis=-1)
            probs_t = torch.from_numpy(np.array(probs))
            next_token_ids_t = sample_top_p(probs_t, top_p)
            next_token_ids = mx.array(next_token_ids_t, dtype=mx.int32).flatten()
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

        if next_tok == tokenizer.time_tok:
            consecutive_time_toks += 1
        else:
            consecutive_time_toks = 0

        if next_tok == tokenizer.eos_tok:
            break

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

    # Auto-detect checkpoint type from embedding shape
    weights = mx.load(args.checkpoint)
    emb_shape = weights["model.tok_embeddings.weight"].shape[0]

    if emb_shape == 17727:
        tokenizer = AbsTokenizer()
        model_config = ModelConfig(**load_model_config("medium"))
    elif emb_shape == 17729:
        demo_config_path = os.path.join(args.aria_dir, "demo", "config.json")
        tokenizer = AbsTokenizer(config_path=demo_config_path)
        model_config = ModelConfig(**load_model_config("medium-emb"))
    else:
        raise ValueError(
            f"Unexpected embedding shape {emb_shape}. "
            f"Expected 17727 (model-gen) or 17729 (model-demo)."
        )

    model_config.set_vocab_size(tokenizer.vocab_size)
    assert tokenizer.vocab_size == emb_shape, (
        f"Vocab mismatch: tokenizer={tokenizer.vocab_size}, checkpoint={emb_shape}"
    )

    for key, weight in weights.items():
        if weight.dtype != mx.bfloat16:
            weights[key] = weight.astype(mx.bfloat16)

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

    # Inject style prefix tokens before BOS
    if args.form or args.genre or args.composer:
        bos_idx = prompt.index(tokenizer.bos_tok) if tokenizer.bos_tok in prompt else len(prompt)
        extra_prefixes = []
        if args.form:
            extra_prefixes.append(("prefix", "form", args.form))
        if args.genre:
            extra_prefixes.append(("prefix", "genre", args.genre))
        if args.composer:
            extra_prefixes.append(("prefix", "composer", args.composer))
        prompt = prompt[:bos_idx] + extra_prefixes + prompt[bos_idx:]

    print(f"Prompt: {len(prompt)} tokens from {os.path.basename(args.prompt_midi)} ({args.prompt_duration}s)")
    print(f"Prefix: {[t for t in prompt if isinstance(t, tuple) and len(t)==3 and t[0]=='prefix']}")

    max_new_tokens = min(8096 - len(prompt), args.length)

    result = generate(
        model=model,
        tokenizer=tokenizer,
        prompt=prompt,
        max_new_tokens=max_new_tokens,
        temp=args.temp,
        top_p=args.top_p,
        force_end=args.force_end,
        time_penalty=args.time_penalty,
        max_consecutive_time=args.max_consecutive_time,
    )

    os.makedirs(os.path.dirname(args.save_path), exist_ok=True)
    midi_dict = tokenizer.detokenize(result)
    midi = midi_dict.to_midi()
    midi.save(args.save_path)
    print(f"Saved: {args.save_path}")


if __name__ == "__main__":
    main()
