#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Aria-Duet: Parameter Sweep
# ============================================================================
# Runs headless generation across a grid of temperature / min_p values
# using the shipped example prompts. Outputs are saved to recordings/sweep/
# for side-by-side comparison.
#
# Usage:
#   ./sweep.sh              # full sweep (54 runs, ~30-50 min)
#   ./sweep.sh --quick      # quick sweep (6 runs, ~5 min)
# ============================================================================

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
SWEEP_DIR="${SCRIPT_DIR}/recordings/sweep"
GENERATOR="${SCRIPT_DIR}/sweep_generate.py"

# --- Preflight checks -------------------------------------------------------

if [ ! -f "${CHECKPOINT}" ]; then
    echo "Error: Checkpoint not found at ${CHECKPOINT}"
    echo "  Run ./setup.sh first."
    exit 1
fi

source "${SCRIPT_DIR}/.venv/bin/activate"

mkdir -p "${SWEEP_DIR}"

# --- Parameter grid ----------------------------------------------------------

## NOTE: Uses top_p (not min_p) — min_p kills note tokens. See CHANGES.md §12.
if [ "${1:-}" = "--quick" ]; then
    TEMPS=(0.85 0.95 1.00)
    TOP_PS=(0.95)
    PROMPTS=("waltz.mid" "nocturne.mid")
    echo "Quick sweep: 3 temps x 1 top_p x 2 prompts = 6 runs"
else
    TEMPS=(0.85 0.90 0.95 0.97 1.00)
    TOP_PS=(0.90 0.95 0.99)
    PROMPTS=("waltz.mid" "classical.mid" "nocturne.mid")
    echo "Full sweep: 5 temps x 3 top_p x 3 prompts = 45 runs"
fi

echo ""
echo "Output directory: ${SWEEP_DIR}"
echo ""

# --- CSV index header --------------------------------------------------------

INDEX="${SWEEP_DIR}/index.csv"
echo "file,prompt,temp,top_p,tokens" > "${INDEX}"

# --- Run sweep ---------------------------------------------------------------

TOTAL=$(( ${#TEMPS[@]} * ${#TOP_PS[@]} * ${#PROMPTS[@]} ))
COUNT=0

for PROMPT in "${PROMPTS[@]}"; do
    PROMPT_PATH="${ARIA_DIR}/example-prompts/${PROMPT}"
    PROMPT_NAME="${PROMPT%.mid}"

    if [ ! -f "${PROMPT_PATH}" ]; then
        echo "Warning: ${PROMPT_PATH} not found, skipping."
        continue
    fi

    for TEMP in "${TEMPS[@]}"; do
        for TOP_P in "${TOP_PS[@]}"; do
            COUNT=$((COUNT + 1))
            FILENAME="${PROMPT_NAME}__temp${TEMP}__topp${TOP_P}.mid"
            SAVE_PATH="${SWEEP_DIR}/${FILENAME}"

            echo "[${COUNT}/${TOTAL}] ${FILENAME}"

            if [ -f "${SAVE_PATH}" ]; then
                echo "  -> Already exists, skipping."
                echo "${FILENAME},${PROMPT_NAME},${TEMP},${TOP_P},cached" >> "${INDEX}"
                continue
            fi

            python "${GENERATOR}" \
                --checkpoint "${CHECKPOINT}" \
                --aria_dir "${ARIA_DIR}" \
                --prompt_midi "${PROMPT_PATH}" \
                --prompt_duration 15 \
                --temp "${TEMP}" \
                --top_p "${TOP_P}" \
                --length 2048 \
                --save_path "${SAVE_PATH}" \
                2>&1 | tail -1

            echo "${FILENAME},${PROMPT_NAME},${TEMP},${TOP_P},2048" >> "${INDEX}"
            echo ""
        done
    done
done

echo "============================================"
echo "  Sweep complete: ${COUNT} runs"
echo "  Output: ${SWEEP_DIR}/"
echo "  Index:  ${INDEX}"
echo "============================================"
