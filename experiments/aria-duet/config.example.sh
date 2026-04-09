#!/usr/bin/env bash
# ============================================================================
# Aria-Duet Configuration
# ============================================================================
# Copy this file to config.sh and edit for your machine:
#   cp config.example.sh config.sh
#
# config.sh is gitignored — your local settings won't be committed.
# ============================================================================

# --- Required ----------------------------------------------------------------

# Path to your local clone of the Aria repo (https://github.com/eleutherai/aria)
ARIA_DIR="${HOME}/Development/aria"

# --- Optional overrides ------------------------------------------------------
# By default, MIDI ports are auto-discovered at runtime and you'll be prompted
# to choose. Uncomment these to skip the prompt and use fixed port names.

# MIDI_OUT="IAC Driver Bus 1"        # AI output → audio engine
# MIDI_THROUGH="IAC Driver Bus 1"    # Human input echo → audio engine
# MIDI_IN="Oxygen 49"                # Your controller (live mode only)

# --- Generation tuning -------------------------------------------------------
# Uncomment to enable custom pedal/time logit penalties (experimental).
# Default: upstream-minimal mode (no custom penalties, PED_OFF +3 boost only).
# PENALTIES=1
