import math
import os
from pathlib import Path
from typing import NamedTuple

import librosa
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
import torch
import torch.nn as nn
import torch.nn.functional as F

# Same idea as the DDSP script but for transcription instead of synthesis.
# We build the core NMP/Basic Pitch architecture (Bittner et al. 2022) and
# train it on synthetic audio to see if it can actually learn to detect notes.

SAMPLE_RATE = 22050           # librosa default
HOP_LENGTH = 256              # CQT hop, about 11.6 ms per frame
N_BINS = 264                  # 88 semitones * 3 bins per semitone
N_HARMONICS = 8               # sub-harmonic + 7 overtones
N_SEMITONES = 88              # piano range A0 to C8
BINS_PER_SEMITONE = 3
MIDI_OFFSET = 21              # A0 = MIDI 21
ANNOTATIONS_FPS = SAMPLE_RATE / HOP_LENGTH  # ~86 frames/sec

# sub-harmonic (f/2) + fundamental + overtones 2f through 7f
HARMONIC_MULTIPLIERS = [0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]

device = None
if torch.backends.mps.is_available():
    device = torch.device("mps")
elif torch.cuda.is_available():
    device = torch.device("cuda")
else:
    device = torch.device("cpu")

print(f"Using device: {device}")


class NoteEvent(NamedTuple):
    pitch_midi: int
    start_s: float
    end_s: float
    amplitude: float = 1.0


def make_audio(notes, duration):
    # Additive synthesis: sum sinusoids for each note so we know exactly
    # what pitches are active. 6 harmonics per note gives the CQT something
    # realistic to work with (the same peaks harmonic stacking is designed to find).
    n_samples = int(duration * SAMPLE_RATE)
    audio = np.zeros(n_samples, dtype=np.float32)
    t = np.arange(n_samples) / SAMPLE_RATE

    for note in notes:
        f0 = librosa.midi_to_hz(note.pitch_midi)
        start_idx = int(note.start_s * SAMPLE_RATE)
        end_idx = min(int(note.end_s * SAMPLE_RATE), n_samples)
        length = end_idx - start_idx
        if length <= 0:
            continue

        # tiny ADSR envelope so we don't get clicks at the edges
        env = np.ones(length, dtype=np.float32)
        atk = int(0.005 * SAMPLE_RATE)
        rel = int(0.005 * SAMPLE_RATE)
        if atk < length:
            env[:atk] = np.linspace(0.0, 1.0, atk)
        if rel < length:
            env[-rel:] = np.linspace(1.0, 0.0, rel)

        # 1/k amplitude rolloff (sawtooth-ish)
        note_audio = np.zeros(length, dtype=np.float32)
        for harm in range(1, 7):
            freq = f0 * harm
            if freq >= SAMPLE_RATE / 2:
                break
            note_audio += (1.0 / harm) * np.sin(2 * np.pi * freq * t[start_idx:end_idx])

        audio[start_idx:end_idx] += note.amplitude * env * note_audio

    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio * (0.9 / peak)
    return audio


def compute_cqt(audio):
    # CQT instead of mel because it has log-frequency spacing: the distance
    # between f and 2f is always 36 bins no matter what f is. That's the
    # property that makes harmonic stacking possible.
    C = librosa.cqt(
        audio,
        sr=SAMPLE_RATE,
        hop_length=HOP_LENGTH,
        fmin=librosa.midi_to_hz(MIDI_OFFSET),    # A0 = 27.5 Hz
        n_bins=N_BINS,
        bins_per_octave=BINS_PER_SEMITONE * 12,  # 36 bins/octave
    )
    mag = np.abs(C)
    mag_db = librosa.amplitude_to_db(mag, ref=np.max(mag) + 1e-8)
    mag_norm = np.clip((mag_db + 80.0) / 80.0, 0.0, 1.0)
    return mag_norm.astype(np.float32)


def harmonic_stack(cqt):
    # This is the key NMP trick and honestly it's kind of elegant.
    # For each harmonic k: shift = round(log2(k) * 36) bins.
    # Roll the CQT by that much, and now harmonic k sits right on top of f.
    # A tiny 3x3 conv can see the whole harmonic series without needing
    # a huge receptive field. That's how 6K params can work.
    channels = []
    for k in HARMONIC_MULTIPLIERS:
        shift = round(math.log2(k) * BINS_PER_SEMITONE * 12) if k > 0 else 0
        ch = np.roll(cqt, -shift, axis=0)
        # np.roll wraps around, but we don't want that, so zero out the wrapped part
        if shift > 0:
            ch[-shift:] = 0.0
        elif shift < 0:
            ch[:-shift] = 0.0
        channels.append(ch)  # [N_BINS, n_frames]

    stacked = np.stack(channels, axis=0)    # [8, N_BINS, n_frames]
    stacked = stacked.transpose(0, 2, 1)    # [8, n_frames, N_BINS]
    return stacked.astype(np.float32)


def make_targets(notes, n_frames):
    # Three separate ground truth matrices at different resolutions.
    # Training all three heads at once acts as a regularizer, which is
    # pretty important when your model only has 6K params.
    contour_gt = np.zeros((n_frames, N_BINS), dtype=np.float32)       # 3 bins/semitone
    note_gt = np.zeros((n_frames, N_SEMITONES), dtype=np.float32)     # 1 bin/semitone
    onset_gt = np.zeros((n_frames, N_SEMITONES), dtype=np.float32)    # attack frames only

    for note in notes:
        idx = note.pitch_midi - MIDI_OFFSET
        if not (0 <= idx < N_SEMITONES):
            continue
        t0 = int(note.start_s * ANNOTATIONS_FPS)
        t1 = min(int(note.end_s * ANNOTATIONS_FPS) + 1, n_frames)

        # contour: center 3 bins for this semitone
        bc = idx * BINS_PER_SEMITONE + 1
        for b in range(max(0, bc - 1), min(N_BINS, bc + 2)):
            contour_gt[t0:t1, b] = 1.0

        # note: just the semitone bin
        note_gt[t0:t1, idx] = 1.0

        # onset: +/-1 frame around the attack with soft weighting.
        # a single frame is too narrow of a target, the optimizer struggles.
        # +/-1 frame is ~11.6 ms which is within perceptual onset tolerance.
        for df in range(-1, 3):
            f = t0 + df
            if 0 <= f < n_frames:
                w = 1.0 if df in (0, 1) else 0.5
                onset_gt[f, idx] = max(onset_gt[f, idx], w)

    return contour_gt, note_gt, onset_gt


class NMPModel(nn.Module):
    # 3-head CNN, roughly following Basic Pitch (Bittner et al. 2022).
    # Input is the 8-channel harmonic-stacked CQT.
    # Outputs: contour (fine pitch), note (semitone), onset (attacks).
    #
    # The whole thing is ~6K params. That works because harmonic stacking
    # already did the hard part (aligning overtones), so the conv layers
    # just need to spot local patterns in the stacked channels.

    def __init__(self, n_harmonics=N_HARMONICS):
        super().__init__()

        # shared front-end: 8 harmonic channels in, 16 feature maps out
        # kernel (3, 13) = 3 frames (~35 ms) by 13 freq bins (~4 semitones)
        self.front_end = nn.Sequential(
            nn.Conv2d(n_harmonics, 16, kernel_size=(3, 13), padding=(1, 6)),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.Dropout(0.25),
        )

        # contour head: stays at 264 bins (fine-grained pitch)
        self.contour_head = nn.Sequential(
            nn.Conv2d(16, 1, kernel_size=(5, 5), padding=(2, 2)),
            nn.Sigmoid(),
        )

        # note head: stride=(1,3) collapses 264 bins down to 88 (one per semitone).
        # learned stride rather than just averaging, so it picks the strongest
        # bin within each 3-bin group
        self.note_head = nn.Sequential(
            nn.Conv2d(16, 1, kernel_size=(1, 3), stride=(1, 3)),
            nn.Sigmoid(),
        )

        # onset head: takes [contour_downsampled, note] concatenated = 2 channels.
        # the idea is that onsets are the one moment where contour and note
        # sharply agree, so concatenating makes that coincidence easy to detect
        self.onset_head = nn.Sequential(
            nn.Conv2d(2, 8, kernel_size=(5, 5), padding=(2, 2)),
            nn.ReLU(),
            nn.Conv2d(8, 1, kernel_size=(3, 3), padding=(1, 1)),
            nn.Sigmoid(),
        )

    def forward(self, x):
        # x: [B, 8, T, 264]
        features = self.front_end(x)              # [B, 16, T, 264]
        contour = self.contour_head(features)     # [B, 1, T, 264]
        note = self.note_head(features)           # [B, 1, T, 88]
        # downsample contour 264->88 to match note resolution
        contour_down = F.avg_pool2d(contour, kernel_size=(1, 3), stride=(1, 3))
        onset = self.onset_head(torch.cat([contour_down, note], dim=1))
        return contour, note, onset


def compute_loss(contour, note, onset, contour_gt, note_gt, onset_gt, onset_weight=5.0):
    # BCE on all three heads. Onset gets weighted 5x because onset frames are
    # so sparse (maybe 3 out of 7,568 labels in a 1-sec clip). Without the
    # weight, predicting all-zeros gets near-zero loss and the onset head
    # never learns anything. Same trick as Onsets & Frames section 3.3.
    L_contour = F.binary_cross_entropy(contour, contour_gt)
    L_note = F.binary_cross_entropy(note, note_gt)
    L_onset = F.binary_cross_entropy(
        onset, onset_gt,
        weight=(onset_gt * (onset_weight - 1.0) + 1.0),
    )
    return L_contour + L_note + L_onset


def create_notes_from_posteriors(onset, note, threshold_onset=0.35,
                                 threshold_note=0.20, min_note_frames=5):
    # Simplified version of Basic Pitch's output_to_notes_polyphonic.
    # For each pitch: find onset peaks above threshold, then trace forward
    # through the note posterior until energy drops for 11+ frames.
    # Onset = precision (few false positives), note = recall (catches sustain).
    events = []
    n_frames, n_pitches = onset.shape

    for pitch_idx in range(n_pitches):
        o = onset[:, pitch_idx]
        n = note[:, pitch_idx]

        for t in range(1, n_frames - 1):
            if o[t] > threshold_onset and o[t] >= o[t - 1] and o[t] >= o[t + 1]:
                end_t, gap = t, 0
                for t2 in range(t, n_frames):
                    if n[t2] >= threshold_note:
                        end_t, gap = t2, 0
                    else:
                        gap += 1
                        if gap > 11:
                            break
                if end_t - t >= min_note_frames:
                    events.append(NoteEvent(
                        pitch_midi=pitch_idx + MIDI_OFFSET,
                        start_s=t / ANNOTATIONS_FPS,
                        end_s=end_t / ANNOTATIONS_FPS,
                    ))
    return events


def _fallback_resynth(note_np, threshold=0.15):
    # For early training steps where the onset head hasn't learned anything yet,
    # just threshold the note posterior directly. Sounds messy but at least
    # it's not silence.
    events = []
    n_frames, n_pitches = note_np.shape
    for p in range(n_pitches):
        col = note_np[:, p]
        active = False
        start_t = 0
        for t in range(n_frames):
            if col[t] >= threshold and not active:
                active = True
                start_t = t
            elif col[t] < threshold and active:
                active = False
                if t - start_t >= 3:
                    events.append(NoteEvent(
                        pitch_midi=p + MIDI_OFFSET,
                        start_s=start_t / ANNOTATIONS_FPS,
                        end_s=t / ANNOTATIONS_FPS,
                    ))
        if active and n_frames - start_t >= 3:
            events.append(NoteEvent(
                pitch_midi=p + MIDI_OFFSET,
                start_s=start_t / ANNOTATIONS_FPS,
                end_s=n_frames / ANNOTATIONS_FPS,
            ))
    return events


def run_experiment(name, note_events, duration, n_steps=2000,
                   snapshot_steps=None, out_dir=None):
    # Same structure as the DDSP script: fixed ground truth, learned params,
    # snapshots at regular intervals so you can hear it converge.
    if snapshot_steps is None:
        snapshot_steps = [0, 200, 500, 1000, 2000]
    snapshot_set = set(snapshot_steps)

    os.makedirs(str(out_dir), exist_ok=True)
    prefix = f"nmp_{name}"

    # ground truth audio (fixed, we're not optimizing it like DDSP does)
    audio = make_audio(note_events, duration)
    sf.write(str(out_dir / f"{prefix}_target.wav"), audio, SAMPLE_RATE)

    # CQT + harmonic stack (also fixed)
    cqt = compute_cqt(audio)
    stacked = harmonic_stack(cqt)    # [8, n_frames, N_BINS]
    n_frames = stacked.shape[1]

    contour_gt, note_gt, onset_gt = make_targets(note_events, n_frames)

    # add batch dim
    x = torch.tensor(stacked[np.newaxis]).to(device)
    cgt = torch.tensor(contour_gt[np.newaxis, np.newaxis]).to(device)
    ngt = torch.tensor(note_gt[np.newaxis, np.newaxis]).to(device)
    ogt = torch.tensor(onset_gt[np.newaxis, np.newaxis]).to(device)

    model = NMPModel().to(device)
    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\n[{name}] {n_params:,} trainable parameters | {n_frames} frames")

    optimizer = torch.optim.Adam(model.parameters(), lr=3e-3)
    losses = []

    for step in range(n_steps + 1):
        model.train()
        optimizer.zero_grad()
        contour, note_pred, onset_pred = model(x)
        loss = compute_loss(contour, note_pred, onset_pred, cgt, ngt, ogt)
        loss.backward()
        # BCE gradients blow up when predictions are confidently wrong
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        losses.append(loss.item())

        if step % 200 == 0:
            print(f"  step {step:4d} | loss {loss.item():.4f}")

        if step in snapshot_set:
            _save_snapshot(model, x, prefix, step, duration,
                           note_gt, onset_gt, out_dir)

    return losses


def _save_snapshot(model, x, prefix, step, duration, note_gt, onset_gt, out_dir):
    model.eval()
    with torch.inference_mode():
        _, note_pred, onset_pred = model(x)

    note_np = note_pred[0, 0].cpu().numpy()
    onset_np = onset_pred[0, 0].cpu().numpy()

    # 4-panel piano roll comparison
    fig, axes = plt.subplots(2, 2, figsize=(12, 5))
    fig.suptitle(f"{prefix} — step {step}", fontsize=10)
    for ax, data, title, cmap in [
        (axes[0, 0], note_gt.T,    "Note GT",        "Greens"),
        (axes[0, 1], note_np.T,    "Note predicted", "Blues"),
        (axes[1, 0], onset_gt.T,   "Onset GT",       "Oranges"),
        (axes[1, 1], onset_np.T,   "Onset predicted","Reds"),
    ]:
        ax.imshow(data, origin="lower", aspect="auto", cmap=cmap, vmin=0, vmax=1)
        ax.set_title(title, fontsize=8)
    axes[0, 0].set_ylabel("Semitone")
    axes[1, 0].set_ylabel("Semitone")
    axes[1, 0].set_xlabel("Frame")
    axes[1, 1].set_xlabel("Frame")
    plt.tight_layout()
    plt.savefig(str(out_dir / f"{prefix}_step{step:04d}_pianoroll.png"), dpi=80)
    plt.close()

    # try onset-then-trace first, fall back to simple threshold if the
    # onset head hasn't converged yet (early steps)
    detected = create_notes_from_posteriors(onset_np, note_np)
    if not detected:
        detected = _fallback_resynth(note_np)
    resynth = make_audio(detected, duration) if detected else np.zeros(
        int(duration * SAMPLE_RATE), dtype=np.float32
    )
    sf.write(str(out_dir / f"{prefix}_step{step:04d}.wav"), resynth, SAMPLE_RATE)


def save_loss_curve(all_losses, out_dir):
    colors = {
        "single_note": "#e07020",
        "scale":       "#1a9e8f",
        "chord":       "#2979ff",
    }
    fig, ax = plt.subplots(figsize=(8, 4))
    for name, losses in all_losses.items():
        ax.plot(losses, label=name.replace("_", " "),
                color=colors.get(name, "#9ca3af"), linewidth=1.5)
    ax.set_xlabel("Training step")
    ax.set_ylabel("Loss (3-head BCE)")
    ax.set_title("NMP Training Convergence")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(str(out_dir / "nmp_loss.png"), dpi=80)
    plt.close()
    print(f"\nLoss curve saved to {out_dir}/nmp_loss.png")


def main():
    out_dir = Path(__file__).resolve().parent.parent.parent / "static" / "audio"
    all_losses = {}

    # Experiment 1: single note C4
    # Simplest case, one pitch, one second. If this doesn't converge
    # something is wrong with the harmonic stacking.
    print("\n=== Experiment 1: Single note C4 ===")
    losses_1 = run_experiment(
        name="single_note",
        note_events=[NoteEvent(pitch_midi=60, start_s=0.1, end_s=0.9)],
        duration=1.0,
        n_steps=2000,
        snapshot_steps=[0, 200, 500, 1000, 2000],
        out_dir=out_dir,
    )
    all_losses["single_note"] = losses_1

    # Experiment 2: C major scale
    # Eight sequential notes. The model can't just memorize one frequency
    # region, it has to generalize across pitch.
    print("\n=== Experiment 2: C major scale ===")
    scale = [60, 62, 64, 65, 67, 69, 71, 72]  # C4 D4 E4 F4 G4 A4 B4 C5
    losses_2 = run_experiment(
        name="scale",
        note_events=[
            NoteEvent(p, i * 0.25 + 0.05, i * 0.25 + 0.22)
            for i, p in enumerate(scale)
        ],
        duration=2.2,
        n_steps=3000,
        snapshot_steps=[0, 200, 500, 1000, 2000, 3000],
        out_dir=out_dir,
    )
    all_losses["scale"] = losses_2

    # Experiment 3: C major chord (the hard one)
    # Three simultaneous notes. G4's 2nd harmonic is near C5's fundamental
    # so their spectra overlap. Harmonic stacking is what separates them.
    print("\n=== Experiment 3: C major chord (C4-E4-G4) ===")
    losses_3 = run_experiment(
        name="chord",
        note_events=[
            NoteEvent(pitch_midi=60, start_s=0.1, end_s=0.9),  # C4
            NoteEvent(pitch_midi=64, start_s=0.1, end_s=0.9),  # E4
            NoteEvent(pitch_midi=67, start_s=0.1, end_s=0.9),  # G4
        ],
        duration=1.0,
        n_steps=3000,
        snapshot_steps=[0, 200, 500, 1000, 2000, 3000],
        out_dir=out_dir,
    )
    all_losses["chord"] = losses_3

    save_loss_curve(all_losses, out_dir)
    print(f"\nAll done! Outputs in {out_dir}/  (prefix: nmp_*)")


if __name__ == "__main__":
    main()
