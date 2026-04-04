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
#   ./run-demo-live.sh "Your MIDI Port Name"   # override MIDI input port
#
# Controls:
#   Enter          -> AI takes over (generates continuation)
#   Enter again    -> Your turn (play on keyboard)
#   Type + Enter   -> Reset session context
#   Ctrl+C         -> Quit
# ============================================================================

# --- Configuration (edit these after running list-midi-ports.py) ------------

MIDI_IN="${1:-USB MIDI Keyboard}"     # Your USB MIDI controller port name
MIDI_OUT="IAC Driver Bus 1"          # Where AI output goes (-> Ableton / FluidSynth)
MIDI_THROUGH="IAC Driver Bus 1"      # Echo your playing through audio engine too

# --- Paths ------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARIA_DIR="/Users/mclemens/Development/aria"
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

echo ""
echo "============================================"
echo "  Aria-Duet: Live MIDI Keyboard Demo"
echo "============================================"
echo ""
echo "  Checkpoint:  $(basename "${CHECKPOINT}")"
echo "  MIDI In:     ${MIDI_IN}"
echo "  MIDI Out:    ${MIDI_OUT}"
echo "  Recording:   $(basename "${SAVE_PATH}")"
echo ""
echo "  Controls:"
echo "    Play something on your keyboard, then..."
echo "    Enter        -> AI takes over"
echo "    Enter again  -> Your turn to play"
echo "    Type + Enter -> Reset context"
echo "    Ctrl+C       -> Quit"
echo ""
echo "  Tip: Run 'python list-midi-ports.py' to find your exact port name."
echo "  Loading model (first run compiles MLX kernels, ~30-60s)..."
echo ""

python "${ARIA_DIR}/demo/demo_mlx.py" \
    --checkpoint "${CHECKPOINT}" \
    --midi_in "${MIDI_IN}" \
    --midi_out "${MIDI_OUT}" \
    --midi_through "${MIDI_THROUGH}" \
    --hardware "${HARDWARE}" \
    --back_and_forth \
    --temp 0.85 \
    --min_p 0.05 \
    --save_path "${SAVE_PATH}"
