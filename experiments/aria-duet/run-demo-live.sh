#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Aria-Duet: Live MIDI Keyboard Demo
# ============================================================================
# Play on your USB MIDI keyboard, then press Enter (or a MIDI control
# signal) to hand off to the AI. The AI generates a piano continuation
# in the style of what you just played.
#
# Usage:
#   ./run-demo-live.sh
#
# Controls:
#   Enter          -> AI takes over (generates continuation)
#   Enter again    -> Your turn (play on keyboard)
#   Type + Enter   -> Reset session context
#   Ctrl+C         -> Quit
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
HARDWARE="${SCRIPT_DIR}/hardware/software-routing.json"
SAVE_DIR="${SCRIPT_DIR}/recordings"
SAVE_PATH="${SAVE_DIR}/live-demo-$(date +%Y%m%d-%H%M%S).mid"

# --- Preflight checks -------------------------------------------------------

if [ ! -f "${CHECKPOINT}" ]; then
    echo "Error: Model checkpoint not found at ${CHECKPOINT}"
    echo "  Run ./setup.sh first to download it."
    exit 1
fi

# --- Run --------------------------------------------------------------------

source "${SCRIPT_DIR}/.venv/bin/activate"

# --- Pick MIDI ports (interactive if not preset in config.sh) ----------------

PICK="${SCRIPT_DIR}/pick-midi-port.py"
MIDI_OUT=$(python "${PICK}" output "${MIDI_OUT:-}")
MIDI_THROUGH=$(python "${PICK}" output "${MIDI_THROUGH:-}")
MIDI_IN=$(python "${PICK}" input "${MIDI_IN:-}")

echo ""
echo "============================================"
echo "  Aria-Duet: Live MIDI Keyboard Demo"
echo "============================================"
echo ""
echo "  Checkpoint:  $(basename "${CHECKPOINT}")"
echo "  MIDI In:     ${MIDI_IN}"
echo "  MIDI Out:    ${MIDI_OUT}"
echo "  MIDI Through: ${MIDI_THROUGH}"
echo "  Recording:   $(basename "${SAVE_PATH}")"
echo ""
echo "  Controls:"
echo "    Play something on your keyboard, then..."
echo "    Enter        -> AI takes over"
echo "    Enter again  -> Your turn to play"
echo "    Type + Enter -> Reset context"
echo "    Ctrl+C       -> Quit"
echo ""
echo "  Loading model (first run compiles MLX kernels, ~30-60s)..."
echo ""

python "${ARIA_DIR}/demo/demo_mlx.py" \
    --checkpoint "${CHECKPOINT}" \
    --midi_in "${MIDI_IN}" \
    --midi_out "${MIDI_OUT}" \
    --midi_through "${MIDI_THROUGH}" \
    --hardware "${HARDWARE}" \
    --back_and_forth \
    --temp 0.95 \
    --top_p 0.95 \
    --save_path "${SAVE_PATH}" \
    ${PENALTIES:+--penalties}
