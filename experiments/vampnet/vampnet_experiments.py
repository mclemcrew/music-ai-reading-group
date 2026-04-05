"""
VampNet Music Generation Experiments
=====================================

Demonstrates VampNet's masking strategies on a real audio clip:
  1. Vamping (periodic)  — keep every Nth token, regenerate the rest
  2. Inpainting          — mask a contiguous time region, fill it in
  3. Beat-driven masking — preserve tokens on the beat, regenerate off-beat

Outputs WAV files to static/audio/ with the vampnet_ prefix.
Also saves a trimmed 10-second excerpt as the target/reference.

Usage:
    uv run vampnet_experiments.py --input path/to/audio.wav
    uv run vampnet_experiments.py  # uses synthetic fallback
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "audio"

# Use a 10-second excerpt to keep files manageable and generation fast
EXCERPT_DURATION = 10.0


def ensure_wavebeat_symlink() -> None:
    """VampNet's Interface.default() doesn't pass the wavebeat checkpoint
    path, so it falls back to './models/vampnet/wavebeat.pth' relative to
    CWD. We symlink so the relative path resolves."""
    import vampnet

    src = vampnet.MODELS_DIR / "wavebeat.pth"
    dst = Path("models/vampnet/wavebeat.pth")
    if dst.exists() or not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.symlink_to(src)


def generate_fallback_audio(path: Path, sr: int = 44100) -> None:
    """Generate a synthetic sample if no input audio is provided."""
    t = np.linspace(0, EXCERPT_DURATION, int(sr * EXCERPT_DURATION), endpoint=False)
    freqs = [261.63, 329.63, 392.00, 523.25, 261.63]
    signal = np.zeros_like(t)
    seg_len = len(t) // len(freqs)
    for i, f0 in enumerate(freqs):
        start = i * seg_len
        end = start + seg_len if i < len(freqs) - 1 else len(t)
        seg_t = t[start:end] - t[start]
        envelope = np.exp(-0.3 * seg_t) * (1 - np.exp(-50 * seg_t))
        tone = sum(
            np.sin(2 * np.pi * k * f0 * seg_t) / (k ** 1.2)
            for k in range(1, 5)
        )
        signal[start:end] = tone * envelope
    signal = signal / (np.abs(signal).max() + 1e-8) * 0.8
    sf.write(str(path), signal.astype(np.float32), sr)
    print(f"  Generated fallback audio: {path}")


def prepare_excerpt(input_path: Path, output_path: Path) -> Path:
    """Trim or copy input to a 10-second mono excerpt."""
    import audiotools as at

    sig = at.AudioSignal(str(input_path))

    # Convert to mono if stereo
    if sig.num_channels > 1:
        sig = sig.to_mono()

    # Trim to excerpt duration
    if sig.duration > EXCERPT_DURATION:
        n_samples = int(EXCERPT_DURATION * sig.sample_rate)
        sig.audio_data = sig.audio_data[:, :, :n_samples]

    sig.write(str(output_path))
    print(f"  Prepared {sig.duration:.1f}s mono excerpt: {output_path}")
    return output_path


def run_vamping(
    interface, signal, name: str = "vampnet_vamp",
    periodic_prompt: int = 7, temperature: float = 1.0,
) -> None:
    """Periodic prompting — keep every Nth token as context."""
    print(f"\n--- Vamping (periodic_prompt={periodic_prompt}, temp={temperature}) ---")

    codes = interface.encode(signal)
    mask = interface.build_mask(
        codes, signal,
        periodic_prompt=periodic_prompt,
        periodic_prompt_width=1,
        upper_codebook_mask=3,
    )

    masked_pct = mask.float().mean().item() * 100
    print(f"  Codes: {codes.shape}, masked: {masked_pct:.0f}%")
    print("  Generating...")

    output_codes = interface.vamp(
        codes, mask, return_mask=False, temperature=temperature,
    )
    output_signal = interface.decode(output_codes)

    out_path = OUTPUT_DIR / f"{name}.wav"
    output_signal.write(str(out_path))
    print(f"  Saved: {out_path.name}")


def run_vamping_dense(
    interface, signal, name: str = "vampnet_vamp_dense",
    periodic_prompt: int = 4, temperature: float = 1.0,
) -> None:
    """Denser periodic prompting for more fidelity."""
    print(f"\n--- Vamping dense (periodic_prompt={periodic_prompt}, temp={temperature}) ---")

    codes = interface.encode(signal)
    mask = interface.build_mask(
        codes, signal,
        periodic_prompt=periodic_prompt,
        periodic_prompt_width=1,
        upper_codebook_mask=3,
    )

    masked_pct = mask.float().mean().item() * 100
    print(f"  Codes: {codes.shape}, masked: {masked_pct:.0f}%")
    print("  Generating...")

    output_codes = interface.vamp(
        codes, mask, return_mask=False, temperature=temperature,
    )
    output_signal = interface.decode(output_codes)

    out_path = OUTPUT_DIR / f"{name}.wav"
    output_signal.write(str(out_path))
    print(f"  Saved: {out_path.name}")


def run_inpainting(
    interface, signal, name: str = "vampnet_inpaint",
    temperature: float = 0.8,
) -> None:
    """Mask the middle 4 seconds, keep first and last as context."""
    print(f"\n--- Inpainting (middle 4s masked, temp={temperature}) ---")

    codes = interface.encode(signal)

    start_t = interface.s2t(3.0)
    end_t = interface.s2t(7.0)
    mask = torch.zeros_like(codes)
    mask[:, :, start_t:end_t] = 1

    masked_pct = mask.float().mean().item() * 100
    print(f"  Codes: {codes.shape}, masked: {masked_pct:.0f}% (tokens {start_t}-{end_t})")
    print("  Generating...")

    output_codes = interface.vamp(
        codes, mask, return_mask=False, temperature=temperature,
    )
    output_signal = interface.decode(output_codes)

    out_path = OUTPUT_DIR / f"{name}.wav"
    output_signal.write(str(out_path))
    print(f"  Saved: {out_path.name}")


def run_beat_mask(
    interface, signal, name: str = "vampnet_beat",
    temperature: float = 1.0, after_beat_s: float = 0.05,
) -> None:
    """Beat-driven masking — keep tokens on beats, regenerate off-beat."""
    print(f"\n--- Beat-driven masking (temp={temperature}, after_beat={after_beat_s}s) ---")

    codes = interface.encode(signal)

    beat_mask = interface.make_beat_mask(
        signal,
        after_beat_s=after_beat_s,
        mask_downbeats=True,
        mask_upbeats=True,
        invert=True,
    )

    if beat_mask.dim() == 1:
        beat_mask = beat_mask.unsqueeze(0).unsqueeze(0)
    beat_mask = beat_mask.expand_as(codes)

    masked_pct = beat_mask.float().mean().item() * 100
    print(f"  Codes: {codes.shape}, masked: {masked_pct:.0f}%")
    print("  Generating...")

    output_codes = interface.vamp(
        codes, beat_mask, return_mask=False, temperature=temperature,
    )
    output_signal = interface.decode(output_codes)

    out_path = OUTPUT_DIR / f"{name}.wav"
    output_signal.write(str(out_path))
    print(f"  Saved: {out_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="VampNet experiments")
    parser.add_argument(
        "--input", type=str, default=None,
        help="Path to input audio file.",
    )
    parser.add_argument(
        "--prefix", type=str, default="vampnet",
        help="Output filename prefix (default: vampnet).",
    )
    parser.add_argument(
        "--style", type=str, default="wild",
        choices=["wild", "faithful"],
        help="'wild' = high temp, sparse prompts (creative). "
             "'faithful' = low temp, dense prompts (polished).",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ensure_wavebeat_symlink()

    # Prepare input
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: {input_path} not found", file=sys.stderr)
            sys.exit(1)
    else:
        input_path = Path(__file__).parent / "sample.wav"
        print("No --input provided, generating synthetic fallback...")
        generate_fallback_audio(input_path)

    # Save trimmed excerpt as target
    excerpt_path = Path(__file__).parent / "excerpt.wav"
    prepare_excerpt(input_path, excerpt_path)

    pfx = args.prefix
    target_path = OUTPUT_DIR / f"{pfx}_target.wav"
    shutil.copy2(excerpt_path, target_path)
    print(f"  Target: {target_path}")

    # Load VampNet
    print("\nLoading VampNet...")
    import vampnet
    import audiotools as at

    interface = vampnet.interface.Interface.default()
    print(f"  Loaded on {interface.device}")

    # Load the excerpt
    signal = at.AudioSignal(str(excerpt_path))

    # Style presets
    if args.style == "wild":
        # Creative/exploratory: high temp, sparse prompts
        vamp_period, vamp_dense_period = 9, 5
        vamp_temp, dense_temp, inpaint_temp, beat_temp = 1.2, 1.0, 1.0, 1.1
        beat_after = 0.03
        print(f"  Style: wild (high temperature, sparse prompts)")
    else:
        # Faithful/polished: low temp, dense prompts
        vamp_period, vamp_dense_period = 5, 2
        vamp_temp, dense_temp, inpaint_temp, beat_temp = 0.7, 0.6, 0.6, 0.7
        beat_after = 0.08
        print(f"  Style: faithful (low temperature, dense prompts)")

    # Run all experiments
    run_vamping(interface, signal, name=f"{pfx}_vamp",
                periodic_prompt=vamp_period, temperature=vamp_temp)
    run_vamping_dense(interface, signal, name=f"{pfx}_vamp_dense",
                      periodic_prompt=vamp_dense_period, temperature=dense_temp)
    run_inpainting(interface, signal, name=f"{pfx}_inpaint",
                   temperature=inpaint_temp)

    try:
        run_beat_mask(interface, signal, name=f"{pfx}_beat",
                      temperature=beat_temp, after_beat_s=beat_after)
    except Exception as e:
        print(f"  Beat masking failed (beat tracker may need longer audio): {e}")

    print("\n--- All done! Files in static/audio/vampnet_*.wav ---")


if __name__ == "__main__":
    main()
