import warnings

# This is a warning that I kept getting and just wanted to ignore for right now
warnings.filterwarnings(
    "ignore", message=".*output with one or more elements was resized.*"
)

import librosa
import matplotlib.pyplot as plt
import soundfile
import torch
import torch.nn as nn
import torch.nn.functional as F

# We gotta define some constants
SAMPLE_RATE = (
    16000  # could be larger, but we start with this because it's faster to process
)
AUDIO_DURATION = 4  # second
NUM_SAMPLES = SAMPLE_RATE * AUDIO_DURATION

device = None
if torch.backends.mps.is_available():
    device = torch.device("mps")
elif torch.cuda.is_available():
    device = torch.device("cuda")
else:
    device = torch.device("cpu")

print(f"Using device: {device}")


def harmonic_synth(f0, amplitudes, sample_rate):
    # f0 shape: [n_frames]
    # amplitudes shape: [n_frames, n_harmonics]
    n_harmonics = amplitudes.shape[-1]

    # compute frequency of each harmonic
    # harmonic_numbers should be [1, 2, 3, ..., n_harmonics]
    # freqs should be [n_frames, n_harmonics]
    harmonic_numbers = torch.arange(1, n_harmonics + 1, device=f0.device)
    freqs = f0[:, None] * harmonic_numbers[None, :]

    # compute phase of each harmonic
    # phases should be [n_frames, n_harmonics])
    step_size = torch.tensor(2 * torch.pi / sample_rate)
    phases = torch.cumsum(freqs * step_size, dim=0)

    # compute waveform
    # waveform should be [n_frames, n_harmonics]
    waveform = amplitudes * torch.sin(phases)

    # sum over harmonics to get final waveform
    # final_waveform should be [n_frames]
    final_waveform = waveform.sum(dim=-1)

    return final_waveform


def filtered_noise_synth(filter_magnitudes, n_samples):
    # filter_magnitudes shape: [n_frames, n_filter_bands]
    # This is the "EQ curve" the neural network predicts per frame

    # noise should be shape [n_samples], just random numbers like gaussian noise
    noise = torch.randn(n_samples, device=filter_magnitudes.device)

    n_frames = filter_magnitudes.shape[0]
    frame_size = n_samples // n_frames
    noise = noise.view(n_frames, frame_size)

    noise = torch.fft.rfft(noise, dim=-1)

    n_freq_bins = frame_size // 2 + 1
    filter_stretched = F.interpolate(
        filter_magnitudes.unsqueeze(1),
        size=n_freq_bins,
        mode="linear",
        align_corners=False,
    ).squeeze(1)

    noise = noise * filter_stretched

    noise = torch.fft.irfft(noise, n=frame_size, dim=-1).reshape(-1)

    return noise


def spectral_loss(predicted, target, fft_size):
    # Compute magnitude spectrograms
    window = torch.hann_window(fft_size, device=predicted.device)
    pred_mag = torch.stft(
        predicted,
        n_fft=fft_size,
        hop_length=fft_size // 4,
        window=window,
        return_complex=True,
    ).abs()
    target_mag = torch.stft(
        target,
        n_fft=fft_size,
        hop_length=fft_size // 4,
        window=window,
        return_complex=True,
    ).abs()

    # Linear term — catches loud/obvious errors
    linear_loss = torch.mean(torch.abs(pred_mag - target_mag))

    # Log term — catches quiet/subtle errors (the +1e-7 prevents log(0) = -inf) so we can still differentiate this
    log_loss = torch.mean(
        torch.abs(torch.log(pred_mag + 1e-7) - torch.log(target_mag + 1e-7))
    )

    return linear_loss + log_loss


def multi_scale_spectral_loss(predicted, target):
    # "Check the mix on six different speaker systems" but like a frequency domain loss
    fft_sizes = [2048, 1024, 512, 256, 128, 64]
    total_loss = 0
    for fft_size in fft_sizes:
        total_loss = total_loss + spectral_loss(predicted, target, fft_size)
    return total_loss


def make_target(f0_hz, harmonics, t):
    # Create a target signal with specified f0 and harmonic amplitudes
    signal = torch.zeros_like(t)
    for k, amp in enumerate(harmonics, start=1):
        signal = signal + amp * torch.sin(2 * torch.pi * f0_hz * k * t)
    return signal


# Run one DDSP optimization experiment, saving audio snapshots along the way
def run_experiment(
    name, f0_hz, harmonics, output_dir, n_steps=3000, snapshot_every=500
):
    import os

    os.makedirs(output_dir, exist_ok=True)

    # Just some pretty printing to separate experiments
    print(f"\n{'=' * 60}")
    print(f"Experiment: {name} (f0={f0_hz} Hz, {len(harmonics)} harmonics)")
    print(f"{'=' * 60}")

    # TARGET SIGNAL -> this is what we're trying to reconstruct
    t = torch.arange(NUM_SAMPLES, dtype=torch.float32) / SAMPLE_RATE
    target = make_target(f0_hz, harmonics, t).to(device)

    # Save the target audio for comparison
    soundfile.write(
        os.path.join(output_dir, f"{name}_target.wav"),
        target.cpu().numpy(),
        SAMPLE_RATE,
    )

    # SYNTH PARAMETERS -------------------------------
    # f0 is PROVIDED as ground truth (like CREPE would give us in the real pipeline).
    # Why? Optimizing f0 through sin(cumsum(...)) creates a wildly non-convex loss
    # landscape — we tried it and the optimizer got stuck. The real DDSP paper uses
    # a pre-trained pitch tracker (CREPE) for the same reason....so we did the same (kinda).
    n_frames = 250
    n_harmonics = 60
    n_filter_bands = 65

    f0 = f0_hz * torch.ones(n_frames, device=device)
    harmonic_amps = (
        0.01 * torch.randn(n_frames, n_harmonics, device=device)
    ).requires_grad_(True)
    noise_filter = (
        0.01 * torch.randn(n_frames, n_filter_bands, device=device)
    ).requires_grad_(True)

    # OPTIMIZER SETUP -------------------------------
    # Adam optimizer with different learning rates for harmonic amps and noise filter
    # harmonic amps get a higher learning rate (1e-2) to speed up convergence,
    # while noise filter parameters get a lower learning rate (1e-3) to stabilize.
    optimizer = torch.optim.Adam(
        [
            {"params": [harmonic_amps], "lr": 1e-2},
            {"params": [noise_filter], "lr": 1e-3},
        ]
    )

    # TRAINING LOOP -------------------------------
    # Iterate through steps, computing loss and updating parameters.
    # At each step, compute the output waveform, loss, and take a gradient step.
    # Snapshots are saved at regular intervals.
    losses = []
    for step in range(n_steps + 1):
        optimizer.zero_grad()

        # Upsample f0 and harmonic amps to match the number of samples.
        # This is necessary because the model outputs per-frame values,
        # but we need to synthesize a full waveform...this line tripped me up
        # for a long while...to be fair, didn't know that F.interpolate was a thing :)
        f0_upsampled = F.interpolate(
            f0[None, None, :], size=NUM_SAMPLES, mode="linear", align_corners=False
        ).squeeze()

        amps_upsampled = (
            F.interpolate(
                harmonic_amps.T[None, :, :],
                size=NUM_SAMPLES,
                mode="linear",
                align_corners=False,
            )
            .squeeze()
            .T
        )

        # Compute positive amplitudes and noise filter values
        amps_positive = F.softplus(amps_upsampled)  # didn't know about softplus before
        noise_filter_positive = torch.sigmoid(noise_filter) * 0.1

        # Synthesize harmonic and noise audio, then compute loss
        harmonic_audio = harmonic_synth(f0_upsampled, amps_positive, SAMPLE_RATE)
        noise_audio = filtered_noise_synth(noise_filter_positive, NUM_SAMPLES)
        predicted = harmonic_audio + noise_audio

        loss = multi_scale_spectral_loss(predicted, target)
        losses.append(loss.item())

        if step < n_steps:
            loss.backward()
            optimizer.step()

        # Save audio snapshots at regular intervals
        if step % snapshot_every == 0:
            snapshot_path = os.path.join(output_dir, f"{name}_step{step:04d}.wav")
            soundfile.write(
                snapshot_path, predicted.detach().cpu().numpy(), SAMPLE_RATE
            )
            print(f"  Step {step:4d} | Loss: {loss.item():.4f} | Saved {snapshot_path}")

    # Save loss curve plot
    plt.figure(figsize=(8, 4))
    plt.plot(losses, color="#e07020", linewidth=1.5)
    plt.xlabel("Step")
    plt.ylabel("Multi-Scale Spectral Loss")
    plt.title(f"{name} — Loss Curve")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"{name}_loss.png"), dpi=150)
    plt.close()
    print(f"  Final loss: {losses[-1]:.4f}")

    return losses


def main():
    output_dir = "../docs/audio"

    # Experiment 1: A440 with 3 harmonics (simple instrument-like tone)
    run_experiment(
        name="a440",
        f0_hz=440.0,
        harmonics=[1.0, 0.5, 0.25],
        output_dir=output_dir,
    )

    # Experiment 2: C261 with richer harmonic content (more overtones)
    run_experiment(
        name="c261",
        f0_hz=261.63,
        harmonics=[1.0, 0.7, 0.5, 0.3, 0.15, 0.08],
        output_dir=output_dir,
    )

    # Experiment 3: E329 with odd harmonics only (clarinet-like)
    run_experiment(
        name="e329_odd",
        f0_hz=329.63,
        harmonics=[1.0, 0.0, 0.6, 0.0, 0.3, 0.0, 0.15],
        output_dir=output_dir,
    )

    print("\nAll experiments are complete.....yay!")


if __name__ == "__main__":
    main()
