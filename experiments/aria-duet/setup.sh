#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Aria-Duet Demo Setup
# ============================================================================
# One-click setup for the Ghost in the Keys / Aria-Duet real-time demo.
# Creates a Python 3.11 venv, installs Aria + dependencies, and downloads
# the demo-specific model checkpoint (~1.4 GB).
#
# Usage:
#   cd ARIA-DUET
#   ./setup.sh
#
# Optional flags:
#   --with-fluidsynth   Also install FluidSynth + GM SoundFont (for Tier 2/3)
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARIA_DIR="/Users/mclemens/Development/aria"
CHECKPOINT_DIR="${SCRIPT_DIR}/checkpoints"
CHECKPOINT_FILE="${CHECKPOINT_DIR}/model-demo.safetensors"
CHECKPOINT_URL="https://huggingface.co/loubb/aria-medium-base/resolve/main/model-demo.safetensors?download=true"
SOUNDFONT_DIR="${SCRIPT_DIR}/soundfonts"
SOUNDFONT_FILE="${SOUNDFONT_DIR}/FluidR3_GM.sf2"
SOUNDFONT_URL="https://keymusician01.s3.amazonaws.com/FluidR3_GM.sf2"

WITH_FLUIDSYNTH=false
for arg in "$@"; do
    case "$arg" in
        --with-fluidsynth) WITH_FLUIDSYNTH=true ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

# --- Check prerequisites ---------------------------------------------------

echo ""
echo "============================================"
echo "  Aria-Duet Demo Setup"
echo "============================================"
echo ""

# Check that uv is installed
if ! command -v uv &> /dev/null; then
    echo "Error: 'uv' is not installed."
    echo "  Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi
echo "[ok] uv found: $(uv --version)"

# Check that Aria repo exists
if [ ! -f "${ARIA_DIR}/pyproject.toml" ]; then
    echo "Error: Aria repo not found at ${ARIA_DIR}"
    echo "  Clone it: git clone https://github.com/eleutherai/aria ${ARIA_DIR}"
    exit 1
fi
echo "[ok] Aria repo found at ${ARIA_DIR}"

# --- Python environment ----------------------------------------------------

echo ""
echo "--- Setting up Python environment ---"

cd "${SCRIPT_DIR}"

if [ ! -d ".venv" ]; then
    echo "Creating venv with Python 3.11..."
    uv venv --python 3.11
else
    echo "Venv already exists, skipping creation."
fi

echo "Installing Aria with all dependencies..."
echo "  (This includes: mlx, python-rtmidi, safetensors, mido, torch, etc.)"
uv pip install -e "${ARIA_DIR}[all]"

echo "[ok] Python environment ready"

# --- Verify installation ----------------------------------------------------

echo ""
echo "--- Verifying installation ---"

"${SCRIPT_DIR}/.venv/bin/python" -c "
import mlx.core as mx
import mido
from ariautils.tokenizer import AbsTokenizer
from aria.model import ModelConfig
print(f'  MLX backend: {mx.default_device()}')
print(f'  Tokenizer vocab size: {AbsTokenizer().vocab_size}')
print(f'  mido MIDI backends available')
print('  All imports OK')
"

echo "[ok] Installation verified"

# --- Download model checkpoint ----------------------------------------------

echo ""
echo "--- Downloading model checkpoint ---"

if [ -f "${CHECKPOINT_FILE}" ]; then
    echo "Checkpoint already exists at ${CHECKPOINT_FILE}"
    echo "  (Delete it and re-run setup.sh to re-download)"
else
    echo "Downloading model-demo.safetensors (~1.4 GB)..."
    echo "  Source: huggingface.co/loubb/aria-medium-base"
    echo "  This is the demo-specific checkpoint with sustain pedal support."
    echo ""
    curl -L --progress-bar \
        -o "${CHECKPOINT_FILE}" \
        "${CHECKPOINT_URL}"
    echo ""
    echo "[ok] Checkpoint downloaded"
fi

# Verify checkpoint
FILESIZE=$(stat -f%z "${CHECKPOINT_FILE}" 2>/dev/null || stat -c%s "${CHECKPOINT_FILE}" 2>/dev/null)
if [ "${FILESIZE}" -lt 1000000000 ]; then
    echo "WARNING: Checkpoint file seems too small (${FILESIZE} bytes)."
    echo "  Expected ~1.4 GB. The download may have failed."
    echo "  Delete ${CHECKPOINT_FILE} and re-run setup.sh"
fi

# --- FluidSynth (optional) --------------------------------------------------

if [ "${WITH_FLUIDSYNTH}" = true ]; then
    echo ""
    echo "--- Setting up FluidSynth (fallback audio) ---"

    if ! command -v brew &> /dev/null; then
        echo "Error: Homebrew not found. Install FluidSynth manually."
    else
        if ! command -v fluidsynth &> /dev/null; then
            echo "Installing FluidSynth via Homebrew..."
            brew install fluid-synth
        else
            echo "[ok] FluidSynth already installed"
        fi
    fi

    if [ ! -f "${SOUNDFONT_FILE}" ]; then
        echo "Downloading General MIDI SoundFont (~148 MB)..."
        curl -L --progress-bar \
            -o "${SOUNDFONT_FILE}" \
            "${SOUNDFONT_URL}"
        echo "[ok] SoundFont downloaded"
    else
        echo "[ok] SoundFont already exists"
    fi
fi

# --- Done -------------------------------------------------------------------

echo ""
echo "============================================"
echo "  Setup complete!"
echo "============================================"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Enable IAC Driver (one-time macOS setup):"
echo "     - Open Audio MIDI Setup.app"
echo "     - Window > Show MIDI Studio"
echo "     - Double-click 'IAC Driver'"
echo "     - Check 'Device is online'"
echo ""
echo "  2. Discover your MIDI port names:"
echo "     source .venv/bin/activate"
echo "     python list-midi-ports.py"
echo ""
echo "  3. Update port names in the run scripts if needed:"
echo "     Edit MIDI_OUT and MIDI_IN at the top of:"
echo "       run-demo-file.sh"
echo "       run-demo-live.sh"
echo "       run-playback-only.sh"
echo ""
echo "  4. Start your audio engine:"
echo "     - Ableton Live: Create MIDI track, set input to IAC Driver Bus 1"
if [ "${WITH_FLUIDSYNTH}" = true ]; then
echo "     - FluidSynth:   ./run-fluidsynth.sh"
fi
echo ""
echo "  5. Test audio routing:"
echo "     ./run-playback-only.sh"
echo ""
echo "  6. Run the demo:"
echo "     ./run-demo-file.sh          # MIDI file input (laptop only)"
echo "     ./run-demo-live.sh          # USB MIDI keyboard input"
echo ""
