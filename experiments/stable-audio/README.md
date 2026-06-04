# Stable Audio 3 — local + API demos

Companion code for the *Music Generation* post's Stable Audio 3 / SAME section. It
generates the same prompt set across all three tiers so you can hear what scale buys:

| Tier         | Params (DiT) | Autoencoder | Weights        | How it runs here          |
| ------------ | ------------ | ----------- | -------------- | ------------------------- |
| `small-music`| 459M         | SAME-S      | open (HF)      | local, MPS/CPU            |
| `medium`     | 1.4B         | SAME-L      | open (HF)      | local, Apple Silicon      |
| `large`      | 2.7B         | SAME-L      | **API only**   | Stability API             |

`small-music` is instrumental music only; `medium` and `large` also do sound effects.

## Setup

```bash
./setup.sh
```

This pins Python 3.11, installs `stable-audio-tools` + torch, and applies two fixes the
stock resolve misses (see `setup.sh` comments): a matched numpy/pywavelets wheel pair
(ABI mismatch otherwise crashes at import) and `pytorch_lightning` (imported at
model-build time). Always run with `uv run --no-sync` afterwards so a re-sync doesn't
revert those pins.

## Local generation (small + medium)

The SA3 weights are gated, so export a HuggingFace token that has been granted access:

```bash
export HF_TOKEN=hf_...
uv run --no-sync generate.py --model small  --duration 12
uv run --no-sync generate.py --model medium --duration 12
```

Outputs land in `outputs/sa3_<model>_<slug>.wav` plus a `manifest_<model>.json`. The
prompts and per-prompt seeds live at the top of `generate.py` and are shared across
tiers so the clips line up for A/B listening. Defaults follow the model cards: 8 steps,
`cfg_scale=1.0`, pingpong sampler (these models are adversarially post-trained for
few-step inference). `seconds_total` + `adapt_duration_to_conditioning=True` exercise
SA3's variable-length path.

Notes:
- First load downloads the T5Gemma text encoder and the DiT/SAME weights; expect a slow
  first run, fast afterwards.
- On Apple Silicon we run float32 on MPS (`PYTORCH_ENABLE_MPS_FALLBACK=1` covers the few
  ops without an MPS kernel); CUDA uses float16.

## API demos (large tier + controllability)

The 2.7B `large` model is not released as open weights, so it — and SA3's editing
features — run through the hosted API (`stable-audio-3`, ~26 credits per generation):

```bash
source ../../../uapkg/ua-assistant/.env     # provides STABILITY_API_KEY
uv run --no-sync api_demos.py --what all
```

- `ladder`    — the six prompts at 12s (the large rung of the scaling ladder)
- `longform`  — variable-length: the same prompt/seed at 8s and 60s
- `continue`  — continuation via inpaint (regenerate a region past a seed clip's end)
- `a2a`       — audio-to-audio (re-imagine a clip under a new prompt)

## Papers

- Evans et al., *Stable Audio 3* (Technical Report), arXiv:2605.17991
- Parker et al., *SAME: A Semantically-Aligned Music autoEncoder*, arXiv:2605.18613
