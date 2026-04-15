# Aria-Duet: Real-Time Human-AI Piano Demo

This directory contains wrappers and notes for running the released ARIA duet demo from the NeurIPS Creative AI paper.

The important operational detail is that the best results now come from a **fresh upstream Aria clone and fresh upstream virtual environment**, not from the older local editable-install flow we were using earlier.

## Current Status

- The author-updated `model-demo.safetensors` is much better than the earlier broken behavior we were seeing.
- `run-demo-file.sh` is the fastest way to confirm the updated demo works on your machine.
- `run-demo-live.sh` is ready, but it requires a **real MIDI input device**. If macOS only exposes `IAC Driver Bus 1`, the script will now fail fast instead of pretending the live setup is valid.
- The fresh upstream repo currently omits `demo/demo-tokenizer-config.json`. The wrappers in this directory automatically copy a compatible version into place when needed.

## Recommended Setup

Use a fresh clone exactly as the author suggested:

```bash
git clone https://github.com/EleutherAI/aria /path/to/fresh/aria
cd /path/to/fresh/aria
uv venv --python 3.12
source .venv/bin/activate
uv sync --extra demo
```

Then download the updated demo checkpoint from Hugging Face:

- `model-demo.safetensors`
- source: <https://huggingface.co/loubb/aria-medium-base/tree/main>

Place it at:

```bash
/path/to/fresh/aria/model-demo.safetensors
```

## Project Configuration

Set [config.sh](/Users/mclemens/Development/music-ai-reading-group/experiments/aria-duet/config.sh) to point at your fresh clone:

```bash
ARIA_DIR="/path/to/fresh/aria"
MIDI_OUT="IAC Driver Bus 1"
MIDI_THROUGH="IAC Driver Bus 1"
MIDI_IN="Your USB MIDI Keyboard"
```

You can also override these at runtime:

```bash
ARIA_DIR=/path/to/fresh/aria ./run-demo-file.sh
ARIA_DIR=/path/to/fresh/aria ./run-demo-live.sh
```

The wrappers prefer:

1. `${ARIA_DIR}/.venv/bin/python3`
2. `${ARIA_DIR}/model-demo.safetensors`

If the fresh clone is missing `demo/demo-tokenizer-config.json`, the wrapper installs the compatibility file from:

- [compat/demo-tokenizer-config.json](/Users/mclemens/Development/music-ai-reading-group/experiments/aria-duet/compat/demo-tokenizer-config.json)

## MIDI Setup

### Output Routing

Enable IAC Driver in macOS Audio MIDI Setup:

1. Open `Audio MIDI Setup.app`
2. Open `Window > Show MIDI Studio`
3. Double-click `IAC Driver`
4. Check `Device is online`
5. Ensure at least one port exists, usually `Bus 1`

Your audio engine should listen on `IAC Driver Bus 1`.

Examples:

- Ableton Live: MIDI track input = `IAC Driver Bus 1`, monitor = `In`
- FluidSynth: route demo output to the IAC bus you are monitoring

### Input Routing

For the live demo, you need a real MIDI input device such as:

- `CASIO USB-MIDI`
- another USB controller exposed in CoreMIDI

If `python list-midi-ports.py` only shows `IAC Driver Bus 1`, the live demo is **not ready yet**. The wrapper will stop with an error if input and output resolve to the same port.

Check ports with:

```bash
cd /Users/mclemens/Development/music-ai-reading-group/experiments/aria-duet
source .venv/bin/activate
python list-midi-ports.py
```

## Quick Start

From this directory:

```bash
cd /Users/mclemens/Development/music-ai-reading-group/experiments/aria-duet
```

### 1. Verify audio routing

```bash
ARIA_DIR=/path/to/fresh/aria ./run-playback-only.sh
```

If you hear piano, output routing is correct.

### 2. Verify the updated demo checkpoint

```bash
ARIA_DIR=/path/to/fresh/aria ./run-demo-file.sh
ARIA_DIR=/path/to/fresh/aria ./run-demo-file.sh /path/to/fresh/aria/example-prompts/nocturne.mid
ARIA_DIR=/path/to/fresh/aria ./run-demo-file.sh /path/to/fresh/aria/example-prompts/classical.mid
```

This is the current baseline sanity check. It uses the real upstream demo path with MIDI-file playback as the human side.

### 3. Run the live demo

```bash
ARIA_DIR=/path/to/fresh/aria ./run-demo-live.sh
```

Controls:

- `Play on keyboard` -> human context capture
- `Enter` -> AI takeover
- `Enter` again -> return to human
- `Type text + Enter` -> reset context
- `Ctrl+C` -> quit

The live wrapper now refuses to run if:

- `MIDI_IN == MIDI_OUT`
- `MIDI_IN == MIDI_THROUGH`

That protects you from accidentally testing a feedback loop instead of a real keyboard path.

## Example MIDI Prompts

Useful shipped prompts from the upstream repo:

```bash
ARIA_DIR=/path/to/fresh/aria ./run-demo-file.sh /path/to/fresh/aria/example-prompts/waltz.mid
ARIA_DIR=/path/to/fresh/aria ./run-demo-file.sh /path/to/fresh/aria/example-prompts/nocturne.mid
ARIA_DIR=/path/to/fresh/aria ./run-demo-file.sh /path/to/fresh/aria/example-prompts/classical.mid
ARIA_DIR=/path/to/fresh/aria ./run-demo-file.sh /path/to/fresh/aria/example-prompts/smooth_jazz.mid
ARIA_DIR=/path/to/fresh/aria ./run-demo-file.sh /path/to/fresh/aria/example-prompts/pokey_jazz.mid
ARIA_DIR=/path/to/fresh/aria ./run-demo-file.sh /path/to/fresh/aria/example-prompts/yesterday.mid
```

`waltz.mid`, `nocturne.mid`, and `classical.mid` were the best first-pass checks in our recent testing.

## Output Files

Wrappers save recordings into:

- [recordings](/Users/mclemens/Development/music-ai-reading-group/experiments/aria-duet/recordings)

Typical outputs:

- `file-demo-YYYYMMDD-HHMMSS.mid`
- `live-demo-YYYYMMDD-HHMMSS.mid`

Fresh upstream smoke-test outputs we generated live under `/tmp` were:

- [out-waltz.mid](/tmp/aria-refresh.BizqOS/aria/out-waltz.mid)
- [out-nocturne.mid](/tmp/aria-refresh.BizqOS/aria/out-nocturne.mid)
- [out-classical.mid](/tmp/aria-refresh.BizqOS/aria/out-classical.mid)

## Additional Scripts

- [run-playback-only.sh](/Users/mclemens/Development/music-ai-reading-group/experiments/aria-duet/run-playback-only.sh): sends a MIDI file to the output port without loading the model
- [run-demo-file.sh](/Users/mclemens/Development/music-ai-reading-group/experiments/aria-duet/run-demo-file.sh): uses MIDI-file playback as the human side of the duet
- [run-demo-live.sh](/Users/mclemens/Development/music-ai-reading-group/experiments/aria-duet/run-demo-live.sh): live keyboard duet
- [run-demo-faithful-headless.sh](/Users/mclemens/Development/music-ai-reading-group/experiments/aria-duet/run-demo-faithful-headless.sh): offline replay harness for debugging the takeover path
- [list-midi-ports.py](/Users/mclemens/Development/music-ai-reading-group/experiments/aria-duet/list-midi-ports.py): inspect visible MIDI ports

## Troubleshooting

### The live demo says the input port matches the output port

That means macOS is not exposing a real MIDI keyboard to the process. Fix the hardware/CoreMIDI setup first, then rerun:

```bash
python list-midi-ports.py
```

Do not bypass this unless you are intentionally testing loopback behavior.

### `CASIO USB-MIDI` does not appear

Check:

1. The keyboard is powered on
2. The USB cable is connected directly or through a working hub
3. The device appears in `Audio MIDI Setup.app`
4. The device appears in `python list-midi-ports.py`

### The fresh repo crashes with missing tokenizer config

The wrappers now copy a compatibility config automatically. If you are running `demo_mlx.py` directly, make sure this file exists:

- `demo/demo-tokenizer-config.json`

### File mode works but live mode does not

That usually means:

- output routing is correct
- the updated checkpoint is good
- but your live MIDI input device is still not available to CoreMIDI

That is a hardware or OS routing problem, not a decoding-quality problem.

## Notes

- The earlier sparse, pedal-heavy outputs were not representative of the current updated checkpoint.
- For quality checks, use the fresh upstream file-demo path first.
- Once that sounds good, move to the live keyboard path.
