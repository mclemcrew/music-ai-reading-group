"""
DAC Codec Quality Experiments
==============================

Demonstrates how the Descript Audio Codec (DAC) reconstructs audio at
different numbers of codebook levels, making the RVQ hierarchy audible.

For each level count (1, 2, 4, 6, 9), encodes audio with DAC and
reconstructs using only the first N codebook levels. Saves WAVs so you
can hear how each level adds finer spectral detail.

Usage:
    uv run dac_experiments.py
    uv run dac_experiments.py --input path/to/audio.wav
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "audio"

# Codebook level counts to reconstruct at
LEVEL_STEPS = [1, 2, 3, 4, 5, 6, 7, 8, 9]


def generate_sample_audio(path: Path, sr: int = 44100, duration: float = 4.0) -> None:
    """Generate a musically rich test signal (C major arpeggio with harmonics)."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)

    # Build a chord progression: C major -> F major -> G major -> C major
    chords = [
        [261.63, 329.63, 392.00],  # C E G
        [349.23, 440.00, 523.25],  # F A C5
        [392.00, 493.88, 587.33],  # G B D5
        [261.63, 329.63, 392.00],  # C E G
    ]
    segment_len = len(t) // len(chords)
    signal = np.zeros_like(t)

    for i, chord_freqs in enumerate(chords):
        start = i * segment_len
        end = start + segment_len if i < len(chords) - 1 else len(t)
        seg_t = t[start:end] - t[start]
        envelope = np.exp(-0.3 * seg_t) * (1 - np.exp(-50 * seg_t))  # attack + decay

        chord_signal = np.zeros(end - start)
        for f0 in chord_freqs:
            # Fundamental + 4 harmonics for a richer timbre
            for k in range(1, 5):
                amp = 1.0 / (k ** 1.2)
                chord_signal += amp * np.sin(2 * np.pi * k * f0 * seg_t)

        signal[start:end] = chord_signal * envelope

    # Normalize
    signal = signal / (np.abs(signal).max() + 1e-8) * 0.8
    sf.write(str(path), signal.astype(np.float32), sr)
    print(f"  Generated sample audio: {path}")


def reconstruct_at_n_levels(model, codes: torch.Tensor, n_levels: int) -> torch.Tensor:
    """Reconstruct audio using only the first n_levels codebook levels.

    Each VQ level has codebook_dim=8 with an out_proj (8 → 1024) that maps
    into the decoder's latent space. We sum the projected embeddings from the
    first N levels and decode.
    """
    # Get the decoder latent dimension from the first quantizer's out_proj
    out_dim = model.quantizer.quantizers[0].out_proj.out_channels
    z_partial = torch.zeros(
        codes.shape[0], out_dim, codes.shape[-1],
        device=codes.device,
    )

    for i in range(n_levels):
        qi = model.quantizer.quantizers[i]
        z_i = qi.out_proj(qi.decode_code(codes[:, i, :]))
        z_partial = z_partial + z_i

    return model.decode(z_partial)


def main() -> None:
    parser = argparse.ArgumentParser(description="DAC codec quality experiments")
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Path to input audio. If not provided, generates a synthetic sample.",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Prepare input audio
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: {input_path} not found", file=sys.stderr)
            sys.exit(1)
    else:
        input_path = Path(__file__).parent / "sample_dac.wav"
        print("No input audio — generating synthetic sample...")
        generate_sample_audio(input_path)

    # Save target
    import shutil

    target_path = OUTPUT_DIR / "dac_codec_target.wav"
    shutil.copy2(input_path, target_path)
    print(f"  Target saved: {target_path}")

    # Load DAC model
    print("\nLoading DAC model (downloads on first run)...")
    import dac

    model_path = dac.utils.download(model_type="44khz")
    model = dac.DAC.load(model_path)

    device = "cpu"
    if torch.cuda.is_available():
        device = "cuda"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = "mps"
    model = model.to(device)
    model.eval()
    print(f"  Model loaded on {device}")

    # Load and encode audio
    from audiotools import AudioSignal

    signal = AudioSignal(str(input_path))
    signal = signal.to(device)
    x = model.preprocess(signal.audio_data, signal.sample_rate)

    print(f"  Input shape: {x.shape}")

    with torch.no_grad():
        z, codes, latents, _, _ = model.encode(x)

    n_codebooks = codes.shape[1]
    print(f"  Encoded: {codes.shape} ({n_codebooks} codebook levels)")

    # Reconstruct at each level count
    print("\nReconstructing at different codebook levels...")
    for n in LEVEL_STEPS:
        if n > n_codebooks:
            continue

        print(f"  {n}/{n_codebooks} codebooks...", end=" ")

        with torch.no_grad():
            y = reconstruct_at_n_levels(model, codes, n)

        # Convert to numpy and save
        audio_np = y.squeeze().cpu().numpy()
        if audio_np.ndim > 1:
            audio_np = audio_np[0]  # Take first channel if multi-channel

        # Normalize to prevent clipping
        peak = np.abs(audio_np).max()
        if peak > 0:
            audio_np = audio_np / peak * 0.9

        out_path = OUTPUT_DIR / f"dac_codec_{n:02d}.wav"
        sf.write(str(out_path), audio_np, signal.sample_rate)
        print(f"saved {out_path.name}")

    # Also save full reconstruction for comparison
    print(f"  Full reconstruction (all {n_codebooks})...", end=" ")
    with torch.no_grad():
        y_full = model.decode(z)
    audio_full = y_full.squeeze().cpu().numpy()
    if audio_full.ndim > 1:
        audio_full = audio_full[0]
    peak = np.abs(audio_full).max()
    if peak > 0:
        audio_full = audio_full / peak * 0.9
    sf.write(str(OUTPUT_DIR / "dac_codec_full.wav"), audio_full, signal.sample_rate)
    print("saved dac_codec_full.wav")

    print(f"\n--- Done! Audio files saved to {OUTPUT_DIR}/dac_codec_*.wav ---")
    print("Files:")
    print("  dac_codec_target.wav  — original input")
    for n in LEVEL_STEPS:
        if n <= n_codebooks:
            print(f"  dac_codec_{n:02d}.wav      — {n} codebook level{'s' if n > 1 else ''}")
    print("  dac_codec_full.wav    — full reconstruction (all levels)")


if __name__ == "__main__":
    main()
