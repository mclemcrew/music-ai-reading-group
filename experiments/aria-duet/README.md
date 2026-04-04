# Aria-Duet: Real-Time Human-AI Piano Demo

Live demo of **Ghost in the Keys** (Bradshaw et al., NeurIPS Creative AI 2025) — a real-time turn-taking piano duet between a human and the [Aria](https://github.com/eleutherai/aria) model running on Apple Silicon.

**Paper:** [The Ghost in the Keys: A Disklavier Demo for Human-AI Musical Co-Creativity](https://arxiv.org/abs/2511.01663v1)

## How It Works

You play piano (via MIDI keyboard or simulated from a file). When you're ready, press **Enter** — the AI takes over and generates a musical continuation in the style of what you just played. Press Enter again to take back control. Back and forth, human and AI.

Under the hood: Aria is a 0.7B-parameter autoregressive transformer (LLaMA 3.2 1B architecture) trained on 100k+ hours of piano MIDI transcriptions, running inference via MLX on Apple Silicon.

## Prerequisites

- **macOS** with Apple Silicon (M1/M2/M3/M4)
- **Python 3.11** (installed automatically via `uv`)
- **[uv](https://docs.astral.sh/uv/)** — Python package manager
- **Aria repo** cloned at `/Users/mclemens/Development/aria`

## Quick Start

```bash
cd ARIA-DUET

# 1. One-time setup (creates venv, installs deps, downloads 1.4GB model)
./setup.sh

# 2. Discover your MIDI port names
source .venv/bin/activate
python list-midi-ports.py

# 3. Update port names in the run scripts if needed (see Configuration below)

# 4. Start your audio engine (see Audio Setup below)

# 5. Test audio routing
./run-playback-only.sh

# 6. Run the demo!
./run-demo-file.sh          # MIDI file input (laptop only, no hardware needed)
./run-demo-live.sh          # Live MIDI keyboard input
```

## Audio Setup — Pick Your Tier

### Tier 1: Ableton Live + UA Plugins (best sound)

1. Open Ableton Live
2. Create a new MIDI track
3. Load a piano instrument (UA piano plugin, or any software piano)
4. Set the track's MIDI input to **IAC Driver Bus 1** (or whichever port you configure)
5. Set **Monitor** to **In**
6. Arm the track for recording

### Tier 2: FluidSynth (free, no DAW needed)

```bash
# Install FluidSynth + download SoundFont
./setup.sh --with-fluidsynth

# Start FluidSynth in one terminal
./run-fluidsynth.sh

# Run the demo in another terminal
./run-demo-file.sh
```

### Tier 3: Laptop Only (no MIDI keyboard, no DAW)

Same as Tier 2, but use `run-demo-file.sh` instead of `run-demo-live.sh`. A MIDI file simulates human input — you press **Enter** on the laptop keyboard to trigger AI takeover.

## MIDI Routing Setup (Required for All Tiers)

### Enable IAC Driver (one-time)

1. Open **Audio MIDI Setup.app** (`/Applications/Utilities/`)
2. Menu: **Window > Show MIDI Studio**
3. Double-click **IAC Driver**
4. Check **Device is online**
5. Ensure at least one port exists (e.g., "Bus 1")

### Discover Port Names

```bash
source .venv/bin/activate
python list-midi-ports.py
```

This shows all available MIDI input/output ports and suggests configuration values.

### Configuration

Each `run-*.sh` script has port name variables at the top:

```bash
MIDI_OUT="IAC Driver Bus 1"       # AI output → audio engine
MIDI_THROUGH="IAC Driver Bus 1"   # Human input echo → audio engine
MIDI_IN="USB MIDI Keyboard"       # Your controller (run-demo-live.sh only)
```

Update these to match the exact port names from `list-midi-ports.py`.

## Available Scripts

| Script | Purpose | Hardware needed |
|--------|---------|----------------|
| `setup.sh` | Install everything | — |
| `list-midi-ports.py` | Show available MIDI ports | — |
| `run-playback-only.sh` | Test audio routing (no model) | Audio engine |
| `run-demo-file.sh` | Demo with MIDI file input | Audio engine |
| `run-demo-live.sh` | Demo with USB MIDI keyboard | Audio engine + MIDI keyboard |
| `run-fluidsynth.sh` | Start FluidSynth fallback audio | — |

## Example MIDI Prompts

The Aria repo includes several example MIDI files you can use:

```bash
./run-demo-file.sh /Users/mclemens/Development/aria/example-prompts/waltz.mid
./run-demo-file.sh /Users/mclemens/Development/aria/example-prompts/nocturne.mid
./run-demo-file.sh /Users/mclemens/Development/aria/example-prompts/classical.mid
./run-demo-file.sh /Users/mclemens/Development/aria/example-prompts/smooth_jazz.mid
./run-demo-file.sh /Users/mclemens/Development/aria/example-prompts/pokey_jazz.mid
./run-demo-file.sh /Users/mclemens/Development/aria/example-prompts/yesterday.mid
```

## Demo Day Checklist (Wednesday)

- [ ] Start Ableton Live with UA piano on IAC Driver Bus 1
- [ ] Verify audio: `./run-playback-only.sh` — hear piano?
- [ ] Connect USB MIDI keyboard (if using live mode)
- [ ] Pre-warm the model: run `./run-demo-file.sh`, let it load, do one takeover, Ctrl+C
- [ ] For the actual demo: `./run-demo-live.sh` (or `run-demo-file.sh`)
- [ ] If sharing over Zoom: use "Share Computer Audio" or route through virtual audio

## Troubleshooting

### "No MIDI output ports found"
Enable IAC Driver in Audio MIDI Setup.app (see above).

### "MIDI port not found: IAC Driver Bus 1"
The exact port name may differ. Run `python list-midi-ports.py` and update the scripts.

### No sound from Ableton
- Check the MIDI track's input is set to the correct IAC port
- Set Monitor to **In** and arm the track
- Check Ableton's audio output settings

### Model takes a long time to load
The first run compiles MLX kernels (~30-60 seconds on M4 Pro). Subsequent runs are faster. Pre-warm before your demo.

### "Embedding shape mismatch" error
You're using the wrong checkpoint. The demo requires `model-demo.safetensors` (with sustain pedal support), not the base `model.safetensors`. Re-run `./setup.sh`.

### Generation sounds choppy or has glitches
- Close other GPU-intensive applications
- Try `--quantize` flag for lower memory usage (edit the run script)
- Ensure your Mac has sufficient GPU memory bandwidth (M1 Pro or better recommended)

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ MIDI Input   │────>│  demo_mlx.py     │────>│ MIDI Output      │
│ (keyboard or │     │                  │     │ (IAC Driver)     │
│  MIDI file)  │     │  Aria 0.7B model │     │       │          │
└─────────────┘     │  MLX on Apple    │     └───────┼──────────┘
                     │  Silicon         │             │
                     └──────────────────┘             v
                                              ┌─────────────────┐
                                              │ Audio Engine     │
                                              │ (Ableton Live /  │
                                              │  FluidSynth)    │
                                              └────────┬────────┘
                                                       │
                                                       v
                                                   Speakers
```
