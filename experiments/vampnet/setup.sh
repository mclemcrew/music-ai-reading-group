#!/usr/bin/env bash
#
# VampNet Experiment Setup
# ========================
# Installs dependencies, downloads pre-trained models (~1.5 GB),
# and patches the VampNet package for local use.
#
# Usage:
#   ./setup.sh
#
# Prerequisites:
#   - macOS or Linux
#   - Python 3.9–3.11
#   - uv (https://docs.astral.sh/uv/)

set -euo pipefail
cd "$(dirname "$0")"

echo "=== VampNet Experiment Setup ==="
echo ""

# 1. Install Python dependencies
echo "[1/4] Installing dependencies (torch, vampnet, audiotools)..."
uv sync
echo "  Done."
echo ""

# 2. Create the HuggingFace model repo config
# VampNet reads this file at import time to know where to download models from.
SITE_PACKAGES=".venv/lib/python3.*/site-packages"
HF_REPO_FILE=$(echo $SITE_PACKAGES)/DEFAULT_HF_MODEL_REPO

if [ ! -f $HF_REPO_FILE ]; then
    echo "[2/4] Creating HuggingFace model repo config..."
    echo "hugggof/vampnet" > $HF_REPO_FILE
    echo "  Written: $HF_REPO_FILE"
else
    echo "[2/4] HuggingFace config already exists, skipping."
fi
echo ""

# 3. Download models (codec, coarse, c2f, wavebeat)
echo "[3/4] Downloading pre-trained models (~1.5 GB on first run)..."
uv run python -c "
import vampnet
interface = vampnet.interface.Interface.default()
print('  Models downloaded and loaded successfully.')
print('  Device:', interface.device)
"
echo ""

# 4. Symlink wavebeat model to the path VampNet expects at runtime
echo "[4/4] Linking wavebeat model..."
VAMPNET_MODELS=$(echo $SITE_PACKAGES)/models/vampnet
if [ -f "$VAMPNET_MODELS/wavebeat.pth" ]; then
    mkdir -p models/vampnet
    if [ ! -e models/vampnet/wavebeat.pth ]; then
        ln -sf "$(cd "$VAMPNET_MODELS" && pwd)/wavebeat.pth" models/vampnet/wavebeat.pth
        echo "  Linked: models/vampnet/wavebeat.pth"
    else
        echo "  Already linked."
    fi
else
    echo "  Warning: wavebeat.pth not found in $VAMPNET_MODELS"
    echo "  Beat-driven masking may not work."
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Run the experiments:"
echo "  uv run vampnet_experiments.py --input path/to/audio.wav"
echo "  uv run dac_experiments.py --input path/to/audio.wav"
echo ""
echo "Or with no audio file (uses a synthetic sample):"
echo "  uv run vampnet_experiments.py"
echo "  uv run dac_experiments.py"
