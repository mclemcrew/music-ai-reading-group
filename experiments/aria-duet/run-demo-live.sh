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
ENV_ARIA_DIR="${ARIA_DIR:-}"
ENV_MIDI_OUT="${MIDI_OUT:-}"
ENV_MIDI_THROUGH="${MIDI_THROUGH:-}"
ENV_MIDI_IN="${MIDI_IN:-}"
ENV_CHECKPOINT="${CHECKPOINT:-}"

# --- Load config -------------------------------------------------------------

if [ ! -f "${SCRIPT_DIR}/config.sh" ]; then
    echo "Error: config.sh not found."
    echo "  cp config.example.sh config.sh   # then edit ARIA_DIR"
    exit 1
fi
source "${SCRIPT_DIR}/config.sh"

ARIA_DIR="${ENV_ARIA_DIR:-${ARIA_DIR:?Set ARIA_DIR in config.sh}}"
MIDI_OUT="${ENV_MIDI_OUT:-${MIDI_OUT:-}}"
MIDI_THROUGH="${ENV_MIDI_THROUGH:-${MIDI_THROUGH:-}}"
MIDI_IN="${ENV_MIDI_IN:-${MIDI_IN:-}}"
CHECKPOINT="${ENV_CHECKPOINT:-}"
HARDWARE="${SCRIPT_DIR}/hardware/software-routing.json"
SAVE_DIR="${SCRIPT_DIR}/recordings"
SAVE_PATH="${SAVE_DIR}/live-demo-$(date +%Y%m%d-%H%M%S).mid"
COMPAT_TOKENIZER_CONFIG="${SCRIPT_DIR}/compat/demo-tokenizer-config.json"
TARGET_TOKENIZER_CONFIG="${ARIA_DIR}/demo/demo-tokenizer-config.json"

if [ -z "${CHECKPOINT}" ]; then
    if [ -f "${ARIA_DIR}/model-demo.safetensors" ]; then
        CHECKPOINT="${ARIA_DIR}/model-demo.safetensors"
    else
        CHECKPOINT="${SCRIPT_DIR}/checkpoints/model-demo.safetensors"
    fi
fi

# --- Preflight checks -------------------------------------------------------

if [ ! -f "${CHECKPOINT}" ]; then
    echo "Error: Model checkpoint not found at ${CHECKPOINT}"
    echo "  Run ./setup.sh first to download it."
    exit 1
fi

if [ ! -x "${ARIA_DIR}/.venv/bin/python3" ] && [ ! -x "${SCRIPT_DIR}/.venv/bin/python3" ]; then
    echo "Error: no usable Python environment found."
    echo "  Expected either ${ARIA_DIR}/.venv/bin/python3 or ${SCRIPT_DIR}/.venv/bin/python3"
    exit 1
fi

if [ -x "${ARIA_DIR}/.venv/bin/python3" ]; then
    PYTHON_BIN="${ARIA_DIR}/.venv/bin/python3"
else
    PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python3"
fi

if [ ! -f "${TARGET_TOKENIZER_CONFIG}" ]; then
    echo "Installing compatibility tokenizer config into ${TARGET_TOKENIZER_CONFIG}"
    cp "${COMPAT_TOKENIZER_CONFIG}" "${TARGET_TOKENIZER_CONFIG}"
fi

# --- Run --------------------------------------------------------------------

# --- Pick MIDI ports (interactive if not preset in config.sh) ----------------

PICK="${SCRIPT_DIR}/pick-midi-port.py"
MIDI_OUT=$("${PYTHON_BIN}" "${PICK}" output "${MIDI_OUT:-}")
MIDI_THROUGH=$("${PYTHON_BIN}" "${PICK}" output "${MIDI_THROUGH:-}")
MIDI_IN=$("${PYTHON_BIN}" "${PICK}" input "${MIDI_IN:-}")

if [ "${ALLOW_SHARED_MIDI_PORTS:-0}" != "1" ] && {
    [ "${MIDI_IN}" = "${MIDI_OUT}" ] || [ "${MIDI_IN}" = "${MIDI_THROUGH}" ];
}; then
    echo "Error: live demo input port matches an output port."
    echo "  MIDI In:      ${MIDI_IN}"
    echo "  MIDI Out:     ${MIDI_OUT}"
    echo "  MIDI Through: ${MIDI_THROUGH}"
    echo "  Connect a real MIDI keyboard or set ALLOW_SHARED_MIDI_PORTS=1 to bypass."
    exit 1
fi

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

"${PYTHON_BIN}" "${ARIA_DIR}/demo/demo_mlx.py" \
    --checkpoint "${CHECKPOINT}" \
    --midi_in "${MIDI_IN}" \
    --midi_out "${MIDI_OUT}" \
    --midi_through "${MIDI_THROUGH}" \
    --hardware "${HARDWARE}" \
    --back_and_forth \
    --temp 0.95 \
    --save_path "${SAVE_PATH}"
