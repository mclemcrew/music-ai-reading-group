#!/usr/bin/env python3
"""
Stable Audio 3 — the LARGE tier + capability demos, via the Stability API.

The 2.7B `large` model is NOT released as open weights, so the only way to hear
the top of the ladder is the hosted API (model `stable-audio-3`). The API is also
where we demo SA3's signature controllability tricks that the post explains:

  * variable-length generation  (same prompt at 8s vs 60s)
  * continuation / inpainting   (extend a seed clip past its end)
  * audio-to-audio              (re-imagine a clip under a new prompt)

All endpoints are ASYNC: POST returns 202 + {id}; poll GET results/{id} until 200.
44.1 kHz stereo, ~26 credits per successful generation (failures are free).

    export STABILITY_API_KEY=...        # e.g. `source ../../../uapkg/ua-assistant/.env`
    uv run api_demos.py --what ladder        # the 6 prompts at 12s (large tier)
    uv run api_demos.py --what longform      # variable-length: 8s + 60s
    uv run api_demos.py --what continue       # continuation via inpaint
    uv run api_demos.py --what a2a            # audio-to-audio
    uv run api_demos.py --what all
"""
import argparse
import json
import os
import time
from pathlib import Path

import requests

API_BASE = "https://api.stability.ai/v2beta/audio/stable-audio"
RESULTS_BASE = "https://api.stability.ai/v2beta/audio/results"
MODEL = "stable-audio-3"
POLL_S = 4
POLL_TIMEOUT_S = 300

# Mirror generate.py so the API "large" tier lines up with the local tiers.
PROMPTS = [
    ("jazz-piano",   "a jazz piano solo, intimate late-night club, brushed drums and upright bass", 1001),
    ("lofi",         "lo-fi hip hop beat, warm vinyl crackle, mellow Rhodes chords, relaxed 85 BPM", 1002),
    ("techno",       "aggressive industrial techno, pounding distorted kick, dark warehouse, 130 BPM", 1003),
    ("cello",        "solo cello playing a melancholic baroque melody, rich resonant tone, reverberant hall", 1004),
    ("chiptune",     "upbeat 8-bit chiptune boss-battle theme, fast arpeggios, driving square-wave bass", 1005),
    ("thunderstorm", "a thunderstorm with heavy rain on a tin roof, distant rolling thunder", 1006),
]


def key() -> str:
    k = os.environ.get("STABILITY_API_KEY")
    if not k:
        raise SystemExit("STABILITY_API_KEY not set (try: source ../../../uapkg/ua-assistant/.env)")
    return k


def poll(gen_id: str) -> bytes:
    deadline = time.time() + POLL_TIMEOUT_S
    while time.time() < deadline:
        time.sleep(POLL_S)
        r = requests.get(f"{RESULTS_BASE}/{gen_id}",
                         headers={"Authorization": f"Bearer {key()}", "accept": "audio/*"})
        if r.status_code == 202:
            continue
        if r.status_code == 200:
            return r.content
        raise SystemExit(f"poll failed {r.status_code}: {r.text[:300]}")
    raise SystemExit(f"timed out polling {gen_id}")


def submit(endpoint: str, data: dict, audio_path: str | None = None) -> bytes:
    # The API requires multipart/form-data even when there's no file, so we send
    # every field as a multipart part: (name, (filename=None, value)). The binary
    # audio part, if any, goes LAST (text fields must precede it).
    fields: list = [(k, (None, str(v))) for k, v in data.items()]
    if audio_path is not None:
        with open(audio_path, "rb") as fh:
            fields.append(("audio", ("input.wav", fh.read(), "audio/wav")))
    r = requests.post(f"{API_BASE}/{endpoint}",
                      headers={"Authorization": f"Bearer {key()}", "accept": "application/json"},
                      files=fields)
    if r.status_code != 202:
        raise SystemExit(f"{endpoint} failed {r.status_code}: {r.text[:300]}")
    gen_id = r.json().get("id")
    print(f"  [{endpoint}] 202 id={gen_id} polling ...", flush=True)
    return poll(gen_id)


def common(prompt: str, duration: float, seed: int | None) -> dict:
    d = {"prompt": prompt, "model": MODEL, "output_format": "wav",
         "duration": str(int(duration)), "steps": "8", "cfg_scale": "6"}
    if seed is not None:
        d["seed"] = str(seed)
    return d


def text_to_audio(out: Path, slug: str, prompt: str, duration: float, seed: int | None) -> dict:
    print(f"[t2a] {slug} ({duration}s)")
    audio = submit("text-to-audio", common(prompt, duration, seed))
    path = out / f"sa3_large_{slug}.wav"
    path.write_bytes(audio)
    print(f"  -> {path} ({len(audio)//1024} KB)")
    return {"slug": slug, "prompt": prompt, "duration": duration, "seed": seed, "file": path.name}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--what", choices=["ladder", "longform", "continue", "a2a", "all"], default="all")
    ap.add_argument("--out-dir", default="outputs")
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    log = []

    if args.what in ("ladder", "all"):
        for slug, prompt, seed in PROMPTS:
            log.append(text_to_audio(out, slug, prompt, 12, seed))

    if args.what in ("longform", "all"):
        # Variable-length: identical prompt/seed, two very different durations.
        log.append(text_to_audio(out, "vlen-8s", PROMPTS[1][1], 8, 2002))
        log.append(text_to_audio(out, "vlen-60s", PROMPTS[1][1], 60, 2002))

    if args.what in ("continue", "all"):
        # Continuation = inpaint a region that starts at the seed clip's end.
        seed_clip = out / "sa3_large_jazz-piano.wav"
        if not seed_clip.exists():
            seed_clip = next(out.glob("sa3_*_jazz-piano.wav"), None)
        if seed_clip:
            print(f"[continue] seed={seed_clip.name}")
            data = common("a jazz piano solo that builds into a walking-bass swing groove", 24, 3003)
            data |= {"mask_start": "12", "mask_end": "24"}
            audio = submit("inpaint", data, audio_path=str(seed_clip))
            path = out / "sa3_large_continuation.wav"
            path.write_bytes(audio)
            print(f"  -> {path}")
            log.append({"slug": "continuation", "seed_clip": seed_clip.name, "file": path.name})
        else:
            print("[continue] no jazz-piano seed clip found; run ladder first")

    if args.what in ("a2a", "all"):
        seed_clip = out / "sa3_large_cello.wav"
        if not seed_clip.exists():
            seed_clip = next(out.glob("sa3_*_cello.wav"), None)
        if seed_clip:
            print(f"[a2a] seed={seed_clip.name}")
            data = common("the same melody reimagined as a warm analog synth pad, dreamy and slow", 12, 4004)
            data["strength"] = "0.75"
            audio = submit("audio-to-audio", data, audio_path=str(seed_clip))
            path = out / "sa3_large_a2a.wav"
            path.write_bytes(audio)
            print(f"  -> {path}")
            log.append({"slug": "a2a", "seed_clip": seed_clip.name, "file": path.name})
        else:
            print("[a2a] no cello seed clip found; run ladder first")

    (out / "manifest_api.json").write_text(json.dumps(log, indent=2))
    print(f"[done] {len(log)} API clips -> {out}")


if __name__ == "__main__":
    main()
