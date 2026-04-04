#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# FluidSynth: Fallback Audio Engine
# ============================================================================
# Starts FluidSynth as a MIDI-to-audio synthesizer, listening on CoreMIDI.
# This is the Tier 2/3 fallback for users without Ableton Live or another DAW.
#
# FluidSynth listens on all CoreMIDI sources by default, so it will
# automatically pick up MIDI from the IAC Driver (where the demo sends output).
#
# Prerequisites:
#   ./setup.sh --with-fluidsynth
#
# Usage:
#   ./run-fluidsynth.sh                   # Start FluidSynth
#   ./run-fluidsynth.sh /path/to/sf2      # Custom SoundFont
#
# Then in another terminal, run the demo:
#   ./run-demo-file.sh
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOUNDFONT="${1:-${SCRIPT_DIR}/soundfonts/FluidR3_GM.sf2}"

# --- Preflight checks -------------------------------------------------------

if ! command -v fluidsynth &> /dev/null; then
    echo "Error: FluidSynth not installed."
    echo "  Install with: brew install fluid-synth"
    echo "  Or run: ./setup.sh --with-fluidsynth"
    exit 1
fi

if [ ! -f "${SOUNDFONT}" ]; then
    echo "Error: SoundFont not found at ${SOUNDFONT}"
    echo "  Run: ./setup.sh --with-fluidsynth"
    echo "  Or download manually to: ${SCRIPT_DIR}/soundfonts/"
    exit 1
fi

# --- Run --------------------------------------------------------------------

echo ""
echo "============================================"
echo "  FluidSynth: MIDI Audio Engine"
echo "============================================"
echo ""
echo "  SoundFont: $(basename "${SOUNDFONT}")"
echo "  Audio:     CoreAudio (system output)"
echo "  MIDI:      CoreMIDI (all sources)"
echo ""
echo "  FluidSynth will play any MIDI sent to CoreMIDI ports."
echo "  Run the demo in another terminal."
echo "  Press Ctrl+C to stop."
echo ""

fluidsynth \
    -a coreaudio \
    -m coremidi \
    -g 1.0 \
    "${SOUNDFONT}"
