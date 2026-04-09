#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Aria-Duet: Playback-Only Test
# ============================================================================
# Streams a MIDI file through the output port without loading the model.
# Use this to verify your audio routing works (Ableton / FluidSynth can
# hear MIDI on the IAC Driver port) before running the full demo.
#
# Usage:
#   ./run-playback-only.sh                           # defaults to waltz.mid
#   ./run-playback-only.sh /path/to/some-piece.mid   # custom MIDI file
#
# If you hear piano sound, your routing works. If not, check:
#   1. IAC Driver is enabled (Audio MIDI Setup.app)
#   2. Ableton/FluidSynth is listening on the correct port
#   3. Port name below matches (run: python list-midi-ports.py)
# ============================================================================

# --- Paths ------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- Load config -------------------------------------------------------------

if [ ! -f "${SCRIPT_DIR}/config.sh" ]; then
    echo "Error: config.sh not found."
    echo "  cp config.example.sh config.sh   # then edit ARIA_DIR"
    exit 1
fi
source "${SCRIPT_DIR}/config.sh"

ARIA_DIR="${ARIA_DIR:?Set ARIA_DIR in config.sh}"
CHECKPOINT="${SCRIPT_DIR}/checkpoints/model-demo.safetensors"
MIDI_FILE="${1:-${ARIA_DIR}/example-prompts/waltz.mid}"

# --- Preflight checks -------------------------------------------------------

if [ ! -f "${CHECKPOINT}" ]; then
    echo "Error: Model checkpoint not found at ${CHECKPOINT}"
    echo "  Run ./setup.sh first to download it."
    exit 1
fi

if [ ! -f "${MIDI_FILE}" ]; then
    echo "Error: MIDI file not found: ${MIDI_FILE}"
    exit 1
fi

# --- Run --------------------------------------------------------------------

source "${SCRIPT_DIR}/.venv/bin/activate"

# --- Pick MIDI port (interactive if not preset in config.sh) -----------------

PICK="${SCRIPT_DIR}/pick-midi-port.py"
MIDI_OUT=$(python "${PICK}" output "${MIDI_OUT:-}")

echo ""
echo "============================================"
echo "  Aria-Duet: Playback Test"
echo "============================================"
echo ""
echo "  MIDI Out:  ${MIDI_OUT}"
echo "  File:      $(basename "${MIDI_FILE}")"
echo ""
echo "  Playing MIDI through output port..."
echo "  You should hear piano if your routing is correct."
echo "  Press Ctrl+C to stop."
echo ""

python "${ARIA_DIR}/demo/demo_mlx.py" \
    --checkpoint "${CHECKPOINT}" \
    --midi_out "${MIDI_OUT}" \
    --midi_path "${MIDI_FILE}" \
    --playback
