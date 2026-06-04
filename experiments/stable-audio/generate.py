#!/usr/bin/env python3
"""
Stable Audio 3 — local generation for the open-weight tiers (small-music, medium).

Both tiers load identically through stable-audio-tools; only the HF repo differs.
We generate the SAME prompt set with the SAME per-prompt seed across tiers so the
reading-group post can play them side by side and you can *hear* what scale buys.

    uv run generate.py --model small  --duration 12
    uv run generate.py --model medium --duration 12

Requires a HuggingFace token with access to the (gated) SA3 weights:
    export HF_TOKEN=hf_...        # or HUGGING_FACE_HUB_TOKEN

Notes on the knobs (see the post for the "why"):
  * steps=8, cfg_scale=1.0, sampler="pingpong" are the SA3 defaults — these models
    are adversarially post-trained for few-step inference, so 8 steps is plenty and
    classifier-free guidance is effectively baked in (cfg≈1).
  * seconds_total drives SA3's variable-length generation: the latent sequence length
    is allocated proportional to the requested duration instead of always padding to
    the model's maximum. We pass adapt_duration_to_conditioning=True to exercise that.
"""
import argparse
import json
import os
import time
from pathlib import Path

# MPS lacks a few ops stable-audio-tools touches; fall back to CPU for just those
# instead of crashing. Must be set before torch imports.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import soundfile as sf
import torch
from einops import rearrange
from stable_audio_tools import get_pretrained_model
from stable_audio_tools.inference.generation import generate_diffusion_cond_inpaint

REPOS = {
    "small": "stabilityai/stable-audio-3-small-music",  # 459M DiT / SAME-S — music only
    "medium": "stabilityai/stable-audio-3-medium",       # 1.4B DiT / SAME-L — music + SFX
}

# (slug, prompt, kind). Fixed seeds below keep tiers comparable.
# `sfx` prompts are skipped on small-music (which is instrumental-music only).
PROMPTS = [
    ("jazz-piano",   "a jazz piano solo, intimate late-night club, brushed drums and upright bass", "music"),
    ("lofi",         "lo-fi hip hop beat, warm vinyl crackle, mellow Rhodes chords, relaxed 85 BPM", "music"),
    ("techno",       "aggressive industrial techno, pounding distorted kick, dark warehouse, 130 BPM", "music"),
    ("cello",        "solo cello playing a melancholic baroque melody, rich resonant tone, reverberant hall", "music"),
    ("chiptune",     "upbeat 8-bit chiptune boss-battle theme, fast arpeggios, driving square-wave bass", "music"),
    ("thunderstorm", "a thunderstorm with heavy rain on a tin roof, distant rolling thunder", "sfx"),
]

# One stable seed per prompt slug — identical across tiers for fair A/B.
SEEDS = {
    "jazz-piano": 1001, "lofi": 1002, "techno": 1003,
    "cello": 1004, "chiptune": 1005, "thunderstorm": 1006,
}


def pick_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=list(REPOS), required=True)
    ap.add_argument("--duration", type=float, default=12.0, help="seconds per clip")
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--cfg", type=float, default=1.0)
    ap.add_argument("--out-dir", default="outputs")
    ap.add_argument("--only", default=None, help="comma-separated prompt slugs to limit to")
    args = ap.parse_args()

    device = pick_device()
    print(f"[device] {device}")

    repo = REPOS[args.model]
    print(f"[load] {repo} (first run downloads weights)")
    t0 = time.time()
    model, cfg = get_pretrained_model(repo)
    sr = cfg["sample_rate"]
    max_size = cfg["sample_size"]
    model = model.to(device)
    # float16 is a meaningful speedup on CUDA; on MPS we stay in float32 for stability.
    if device == "cuda":
        model = model.to(torch.float16)
    print(f"[load] done in {time.time()-t0:.1f}s — sample_rate={sr}, max sample_size={max_size}")

    # Allocate latent length proportional to the requested duration (multiple of the
    # 4096x downsampling factor), capped at the model maximum.
    want = int(sr * args.duration)
    sample_size = min(max_size, max(4096, (want // 4096) * 4096))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    only = set(args.only.split(",")) if args.only else None
    manifest = []
    for slug, prompt, kind in PROMPTS:
        if only and slug not in only:
            continue
        if kind == "sfx" and args.model == "small":
            print(f"[skip] {slug}: small-music is instrumental-music only")
            continue

        seed = SEEDS[slug]
        torch.manual_seed(seed)
        print(f"[gen] {args.model}/{slug} seed={seed} ...", flush=True)
        t = time.time()
        audio = generate_diffusion_cond_inpaint(
            model,
            steps=args.steps,
            cfg_scale=args.cfg,
            conditioning=[{"prompt": prompt, "seconds_total": args.duration}],
            sample_size=sample_size,
            seed=seed,
            sampler_type="pingpong",
            adapt_duration_to_conditioning=True,
            device=device,
        )
        dt = time.time() - t

        # [b, d, n] -> [channels, frames]; peak-normalize and write float32 via soundfile
        # (torchaudio 2.7 ships no write backend by default — soundfile is the writer).
        audio = rearrange(audio, "b d n -> d (b n)")
        peak = torch.max(torch.abs(audio)) + 1e-8
        wav = (audio.to(torch.float32) / peak).clamp(-1, 1).cpu().numpy()
        frames = wav.shape[-1]
        out = out_dir / f"sa3_{args.model}_{slug}.wav"
        sf.write(str(out), wav.T, sr)  # soundfile expects [frames, channels]
        print(f"[gen] -> {out}  ({dt:.1f}s, {frames/sr:.1f}s audio)")
        manifest.append({"slug": slug, "prompt": prompt, "kind": kind,
                         "seed": seed, "model": args.model, "gen_seconds": round(dt, 1),
                         "file": out.name})

    (out_dir / f"manifest_{args.model}.json").write_text(json.dumps(manifest, indent=2))
    print(f"[done] {len(manifest)} clips -> {out_dir}")


if __name__ == "__main__":
    main()
