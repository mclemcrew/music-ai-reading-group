# DDSP From Scratch

Companion experiment for the Signal Processing & ML session (Week 1). This script implements the core architecture from [DDSP: Differentiable Digital Signal Processing](https://arxiv.org/abs/2001.04643) (Engel et al., 2020) in approximately 280 lines of PyTorch, then trains it on three synthetic audio targets to make the optimization process audible.

The synthesizer has two components: a **harmonic oscillator** (bank of sinusoids at integer multiples of a fundamental frequency) and a **filtered noise generator** (white noise shaped by a learned spectral envelope). Both are fully differentiable, so gradients flow from the multi-scale spectral loss back through the synthesis pipeline. The fundamental frequency f0 is provided as ground truth (analogous to the pre-trained CREPE pitch tracker used in the full DDSP pipeline); the optimizer learns only harmonic amplitudes and noise filter parameters.

## Prerequisites

- macOS, Linux, or Windows
- Python 3.10 or later
- [uv](https://docs.astral.sh/uv/) — install with `curl -LsSf https://astral.sh/uv/install.sh | sh`

No GPU is required. All three experiments complete in under 5 minutes on a modern CPU. Apple Silicon (MPS) and CUDA are used automatically when available.

## Setup and Running

```bash
cd experiments/ddsp

# Install dependencies
uv sync

# Run all three experiments
uv run ddsp_from_sratch.py
```

That's it. No model downloads, no external data, no configuration. The script generates its own target audio, trains the synthesizer, and saves output files.

## What It Does

The script runs three experiments, each training the same DDSP architecture on a different synthetic target. Audio snapshots are saved every 500 steps so you can hear the reconstruction improve over training.

| Experiment | Target | Description |
|-----------|--------|-------------|
| `a440` | 440 Hz, 3 harmonics | A simple instrument-like tone (fundamental + 2nd + 3rd harmonic at 1.0, 0.5, 0.25 amplitude). The easiest case — converges quickly. |
| `c261` | 261.63 Hz, 6 harmonics | Middle C with six harmonics of decreasing amplitude. Richer spectrum presents a harder optimization landscape. |
| `e329_odd` | 329.63 Hz, odd harmonics only | Even harmonics zeroed out, producing the hollow timbre of a closed-pipe resonator (clarinet-like). Tests whether the optimizer can learn to suppress even harmonics. |

## Output

All files are written to `../../static/audio/` (the site's static asset directory):

```
static/audio/a440_target.wav          — target waveform
static/audio/a440_step0000.wav        — reconstruction at step 0 (random init)
static/audio/a440_step0500.wav        — reconstruction at step 500
static/audio/a440_step1000.wav        — ...
static/audio/a440_step1500.wav
static/audio/a440_step2000.wav
static/audio/a440_step2500.wav
static/audio/a440_step3000.wav        — final reconstruction
static/audio/a440_loss.png            — loss curve plot

(same pattern for c261_* and e329_odd_*)
```

## Architecture

The synthesizer follows the DDSP paper's Harmonic plus Noise model:

```
Ground-truth f0 ──────────────────────┐
                                      v
                        ┌──────────────────────┐
Random init ──────────> │  Harmonic Amplitudes  │──> harmonic_synth() ──┐
(n_frames × 60)         │  (learnable)          │                      │
                        └──────────────────────┘                      │
                                                                       ├──> + ──> predicted audio
                        ┌──────────────────────┐                      │
Random init ──────────> │  Noise Filter         │──> filtered_noise()──┘
(n_frames × 65)         │  (learnable)          │
                        └──────────────────────┘

predicted audio ──> multi_scale_spectral_loss(predicted, target) ──> backward()
```

Key implementation details:
- **Phase accumulation** via `torch.cumsum` keeps oscillators phase-continuous when frequency changes (no clicks)
- **Filtered noise** applies the learned spectral envelope via pointwise multiplication in the frequency domain (`rfft` → multiply → `irfft`)
- **Multi-scale spectral loss** computes magnitude spectrograms at 6 FFT sizes (64, 128, 256, 512, 1024, 2048) with both linear and log terms
- **Separate learning rates**: harmonic amplitudes at 1e-2, noise filter at 1e-3

## Modifying the Experiments

### Change the target sound

Edit `main()` at the bottom of the script. Each experiment specifies a fundamental frequency and a list of harmonic amplitudes:

```python
run_experiment(
    name="my_experiment",
    f0_hz=392.0,                          # G4
    harmonics=[1.0, 0.8, 0.0, 0.4],      # strong 1st, 2nd, skip 3rd, some 4th
    output_dir=output_dir,
    n_steps=5000,                         # train longer
    snapshot_every=250,                   # save more frequently
)
```

### Change the sample rate or duration

Edit the constants at the top of the script:

```python
SAMPLE_RATE = 16000    # increase to 44100 for higher fidelity (slower training)
AUDIO_DURATION = 4     # seconds
```

### Change the model capacity

Adjust the synthesis parameters inside `run_experiment()`:

```python
n_frames = 250         # temporal resolution (more = finer control, slower)
n_harmonics = 60       # how many harmonics the model can use
n_filter_bands = 65    # frequency resolution of the noise filter
```

## Dependencies

Defined in `pyproject.toml`:

- `torch` — autograd, tensor operations, FFT
- `librosa` — audio loading (used internally by some utilities)
- `soundfile` — WAV file I/O
- `matplotlib` — loss curve plots
- `numpy` — array utilities

## References

- Engel, J., Hantrakul, L., Gu, C., & Roberts, A. (2020). DDSP: Differentiable Digital Signal Processing. *ICLR 2020*. [arXiv:2001.04643](https://arxiv.org/abs/2001.04643)
