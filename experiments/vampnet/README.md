# VampNet and DAC Experiments

Companion experiments for the Music Generation session (Week 3). Two scripts demonstrate the core ideas from [VampNet: Music Generation via Masked Acoustic Token Modeling](https://arxiv.org/abs/2307.04686) (Garcia et al., 2023) and the [Descript Audio Codec](https://arxiv.org/abs/2306.06546) (Kumar et al., 2023).

**VampNet experiments** encode audio into discrete codec tokens and apply different masking strategies — periodic prompting (vamping), time-region inpainting, and beat-driven masking — then decode the result back to audio. All strategies use the same pre-trained model; only the mask pattern and sampling temperature change.

**DAC experiments** reconstruct audio from different numbers of codebook levels (1 through 9), making the residual vector quantization hierarchy audible. With one codebook you hear pitch and rhythm; with all nine, the reconstruction is perceptually transparent.

## Prerequisites

- macOS or Linux
- Python 3.9, 3.10, or 3.11 (Python 3.12+ is not supported by VampNet's dependencies)
- [uv](https://docs.astral.sh/uv/) — install with `curl -LsSf https://astral.sh/uv/install.sh | sh`
- ~2 GB free disk space for model weights and dependencies

No GPU is required. Both scripts run on CPU (Apple Silicon or x86). Generation is slower on CPU (~30–60 seconds per experiment) but produces identical results.

## Setup

```bash
cd experiments/vampnet

# One-time setup: installs deps, downloads models, patches config
./setup.sh
```

The setup script does four things:

1. Installs Python dependencies via `uv sync` (torch 2.4.1, VampNet, audiotools, etc.)
2. Creates a `DEFAULT_HF_MODEL_REPO` config file that tells VampNet to download models from [hugggof/vampnet](https://huggingface.co/hugggof/vampnet) on HuggingFace
3. Downloads the pre-trained model weights (~1.5 GB): `codec.pth`, `coarse.pth`, `c2f.pth`, and `wavebeat.pth`
4. Symlinks the wavebeat model to the path VampNet expects at runtime (`./models/vampnet/wavebeat.pth`)

If the setup script has already been run, re-running it is safe — it skips steps that are already complete.

## Running the VampNet Experiments

```bash
# With your own audio (any format, any length — trimmed to 10s automatically)
uv run vampnet_experiments.py --input path/to/audio.wav

# With a synthetic fallback (no audio file needed)
uv run vampnet_experiments.py
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--input` | synthetic sample | Path to an input audio file |
| `--prefix` | `vampnet` | Output filename prefix |
| `--style` | `wild` | Parameter preset: `wild` (high temp, sparse prompts) or `faithful` (low temp, dense prompts) |

### What each experiment does

| Experiment | Masking strategy | Description |
|-----------|-----------------|-------------|
| Vamping | Periodic prompt (every Nth token kept) | Generates a variation that preserves style and genre while replacing most of the content |
| Vamping dense | Periodic prompt (denser, every 2nd–5th token) | Stays closer to the original — subtle variation rather than transformation |
| Inpainting | Time region mask (seconds 3–7) | Replaces a 4-second window while keeping the surrounding context intact |
| Beat-driven | Keep tokens on detected beats | Preserves the rhythmic skeleton and regenerates off-beat content |

### Output

WAV files are written to `../../static/audio/` (the site's static asset directory) with the specified prefix:

```
static/audio/{prefix}_target.wav       — 10-second input excerpt
static/audio/{prefix}_vamp.wav         — vamping output
static/audio/{prefix}_vamp_dense.wav   — dense vamping output
static/audio/{prefix}_inpaint.wav      — inpainting output
static/audio/{prefix}_beat.wav         — beat-driven output
```

### Example: two genres, two styles

```bash
# Electronic loop with high temperature (creative/exploratory)
uv run vampnet_experiments.py --input ~/Downloads/electronic-loop.wav --prefix vampnet --style wild

# Guitar loop with low temperature (faithful/polished)
uv run vampnet_experiments.py --input ~/Downloads/guitar-loop.wav --prefix vampnet_guitar --style faithful
```

## Running the DAC Codec Experiments

```bash
# With your own audio
uv run dac_experiments.py --input path/to/audio.wav

# With a synthetic sample
uv run dac_experiments.py
```

This encodes the audio with the Descript Audio Codec and reconstructs it using 1, 2, 3, ..., 9 codebook levels, plus a full reconstruction. Output files are written to `static/audio/dac_codec_*.wav`.

## Troubleshooting

### `FileNotFoundError: DEFAULT_HF_MODEL_REPO`

The HuggingFace config file was not created during setup. Re-run `./setup.sh`, or create it manually:

```bash
echo "hugggof/vampnet" > .venv/lib/python3.11/site-packages/DEFAULT_HF_MODEL_REPO
```

### `FileNotFoundError: models/vampnet/wavebeat.pth`

The wavebeat symlink is missing. Re-run `./setup.sh`, or create it manually:

```bash
mkdir -p models/vampnet
ln -sf .venv/lib/python3.11/site-packages/models/vampnet/wavebeat.pth models/vampnet/wavebeat.pth
```

### `OSError: dlopen ... _torchaudio.abi3.so`

Version mismatch between torch and torchaudio. The `pyproject.toml` pins `torchaudio==2.4.1` to match VampNet's `torch==2.4.1`. If you see this error, delete the virtual environment and re-run setup:

```bash
rm -rf .venv uv.lock
./setup.sh
```

### Beat-driven masking fails

The wavebeat model requires audio with a detectable beat. Very ambient or arrhythmic material may cause the beat tracker to return no beats. This is expected — the other three experiments will still run.

### Generation sounds distorted or noisy

This is partly inherent to the DAC codec at the model's operating bitrate (~8 kbps). Lowering the temperature (use `--style faithful`) reduces sampling noise. The pre-trained model was also trained on a specific music distribution, so audio outside that distribution may produce less coherent results.

## References

- Garcia, H. F., Seetharaman, P., Kumar, R., & Pardo, B. (2023). VampNet: Music Generation via Masked Acoustic Token Modeling. *ISMIR 2023*. [arXiv:2307.04686](https://arxiv.org/abs/2307.04686)
- Kumar, R., Seetharaman, P., Luebs, A., Kumar, I., & Kumar, K. (2023). High-Fidelity Audio Compression with Improved RVQGAN. [arXiv:2306.06546](https://arxiv.org/abs/2306.06546)
