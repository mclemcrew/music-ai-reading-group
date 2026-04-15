#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -f "${SCRIPT_DIR}/config.sh" ]; then
    echo "Error: config.sh not found."
    echo "  cp config.example.sh config.sh   # then edit ARIA_DIR"
    exit 1
fi
source "${SCRIPT_DIR}/config.sh"

ARIA_DIR="${ARIA_DIR:?Set ARIA_DIR in config.sh}"
PROMPT_MIDI="${1:-${ARIA_DIR}/example-prompts/waltz.mid}"
TAKEOVER_MS="${TAKEOVER_MS:-10000}"

source "${SCRIPT_DIR}/.venv/bin/activate"

ARGS=(
    "${SCRIPT_DIR}/faithful_headless_demo.py"
    "${PROMPT_MIDI}"
    "--takeover-ms" "${TAKEOVER_MS}"
)

if [ -n "${MIDI_OUT:-}" ]; then
    ARGS+=("--midi-out" "${MIDI_OUT}")
fi

if [ -n "${MIDI_THROUGH:-}" ]; then
    ARGS+=("--midi-through" "${MIDI_THROUGH}")
fi

echo ""
echo "============================================"
echo "  Aria-Duet: Faithful Headless Replay"
echo "============================================"
echo ""
echo "  Prompt:      $(basename "${PROMPT_MIDI}")"
echo "  Takeover:    ${TAKEOVER_MS}ms after first note"
echo "  MIDI Out:    ${MIDI_OUT:-<archive only>}"
echo "  MIDI Through:${MIDI_THROUGH:-<none>}"
echo ""

python "${ARGS[@]}"
