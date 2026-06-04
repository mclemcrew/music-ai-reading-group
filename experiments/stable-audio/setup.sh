#!/usr/bin/env bash
#
# Stable Audio 3 Experiment Setup
# ===============================
# Installs dependencies for local inference with the open-weight SA3 tiers
# (small-music, medium) plus the Stability API demo script.
#
# Usage:
#   ./setup.sh
#
# Prerequisites:
#   - macOS (Apple Silicon) or Linux
#   - uv (https://docs.astral.sh/uv/)
#   - A HuggingFace token with access to the (gated) SA3 weights, exported as
#     HF_TOKEN before running generate.py.
#   - For the API demos: STABILITY_API_KEY in the environment
#     (e.g. `source ../../../uapkg/ua-assistant/.env`).

set -euo pipefail
cd "$(dirname "$0")"

echo "=== Stable Audio 3 Experiment Setup ==="
echo ""

# 1. Pin Python 3.11 — torch / stable-audio-tools don't support 3.12+ yet.
echo "[1/4] Pinning Python 3.11 ..."
uv python pin 3.11 >/dev/null
echo "  Done."

# 2. Resolve the main dependency tree (torch, stable-audio-tools, transformers, ...).
echo "[2/4] Installing dependencies (uv sync) — this is large on first run ..."
uv sync
echo "  Done."

# 3. ABI fix: stable-audio-tools pulls pywavelets, and the resolved wheel can be
#    built against a different numpy ABI than the runtime numpy, which crashes at
#    import with "numpy.dtype size changed". Pin a matched pair of prebuilt wheels.
echo "[3/4] Pinning matched numpy + pywavelets wheels (ABI fix) ..."
uv pip install "numpy==2.4.6" "pywavelets==1.9.0" >/dev/null
echo "  Done."

# 4. stable-audio-tools imports pytorch_lightning at model-build time but does not
#    always pull it as a hard dependency.
echo "[4/4] Ensuring pytorch_lightning is present ..."
uv pip install pytorch_lightning >/dev/null
echo "  Done."

echo ""
echo "Verifying imports ..."
uv run --no-sync python -c "import numpy, pywt, pytorch_lightning, torch; \
print('  numpy', numpy.__version__, '| pywt', pywt.__version__, \
'| torch', torch.__version__, '| mps', torch.backends.mps.is_available())"

cat <<'NOTE'

Setup complete. Next steps:

  # Local open-weight tiers (needs HF_TOKEN with SA3 access):
  export HF_TOKEN=hf_...
  uv run --no-sync generate.py --model small  --duration 12
  uv run --no-sync generate.py --model medium --duration 12

  # Large tier + capability demos via the Stability API (needs STABILITY_API_KEY):
  source ../../../uapkg/ua-assistant/.env       # or export STABILITY_API_KEY=...
  uv run --no-sync api_demos.py --what all

IMPORTANT: always use `uv run --no-sync` — a bare `uv run` re-syncs and would
revert the numpy/pywavelets pins from step 3.
NOTE
