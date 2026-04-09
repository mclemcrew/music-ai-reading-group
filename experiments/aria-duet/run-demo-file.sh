#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Aria-Duet: MIDI File Input Demo
# ============================================================================
# Plays a MIDI file as simulated human input, then the AI generates a
# continuation when you press Enter. Works without any external hardware
# (Tier 3 / laptop-only mode).
#
# Usage:
#   ./run-demo-file.sh                           # defaults to waltz.mid
#   ./run-demo-file.sh /path/to/some-piece.mid   # custom MIDI file
#
# Controls:
#   Enter          -> AI takes over (generates continuation)
#   Enter again    -> Your turn (back to MIDI file playback)
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
MIDI_FILE="${1:-${ARIA_DIR}/example-prompts/waltz.mid}"
SAVE_DIR="${SCRIPT_DIR}/recordings"
SAVE_PATH="${SAVE_DIR}/file-demo-$(date +%Y%m%d-%H%M%S).mid"

# --- Preflight checks -------------------------------------------------------

if [ ! -f "${CHECKPOINT}" ]; then
    echo "Error: Model checkpoint not found at ${CHECKPOINT}"
    echo "  Run ./setup.sh first to download it."
    exit 1
fi

if [ ! -f "${MIDI_FILE}" ]; then
    echo "Error: MIDI file not found: ${MIDI_FILE}"
    echo "  Available example prompts:"
    ls "${ARIA_DIR}/example-prompts/"*.mid 2>/dev/null || echo "    (none found)"
    exit 1
fi

# --- Run --------------------------------------------------------------------

source "${SCRIPT_DIR}/.venv/bin/activate"

# --- Pick MIDI ports (interactive if not preset in config.sh) ----------------

PICK="${SCRIPT_DIR}/pick-midi-port.py"
MIDI_OUT=$(python "${PICK}" output "${MIDI_OUT:-}")
MIDI_THROUGH=$(python "${PICK}" output "${MIDI_THROUGH:-}")

echo ""
echo "============================================"
echo "  Aria-Duet: File Input Demo"
echo "============================================"
echo ""
echo "  Checkpoint:  $(basename "${CHECKPOINT}")"
echo "  MIDI Out:    ${MIDI_OUT}"
echo "  MIDI Through: ${MIDI_THROUGH}"
echo "  Prompt:      $(basename "${MIDI_FILE}")"
echo "  Recording:   $(basename "${SAVE_PATH}")"
echo ""
echo "  Controls:"
echo "    Enter        -> AI takes over"
echo "    Enter again  -> Back to file playback"
echo "    Type + Enter -> Reset context"
echo "    Ctrl+C       -> Quit"
echo ""
echo "  Loading model (first run compiles MLX kernels, ~30-60s)..."
echo ""

python "${ARIA_DIR}/demo/demo_mlx.py" \
    --checkpoint "${CHECKPOINT}" \
    --midi_path "${MIDI_FILE}" \
    --midi_through "${MIDI_THROUGH}" \
    --midi_out "${MIDI_OUT}" \
    --hardware "${HARDWARE}" \
    --back_and_forth \
    --temp 0.95 \
    --top_p 0.95 \
    --save_path "${SAVE_PATH}" \
    ${PENALTIES:+--penalties}
