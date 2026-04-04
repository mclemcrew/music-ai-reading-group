#!/usr/bin/env python3
"""Discover available MIDI ports on this system.

Run this after setting up the environment to find the exact port names
needed for the demo scripts (--midi_in, --midi_out, --midi_through).

Usage:
    source .venv/bin/activate
    python list-midi-ports.py
"""

import sys

try:
    import mido
except ImportError:
    print("Error: mido not installed. Run setup.sh first.")
    print("  ./setup.sh")
    sys.exit(1)


def main():
    inputs = mido.get_input_names()
    outputs = mido.get_output_names()

    print("=" * 60)
    print("  MIDI Port Discovery")
    print("=" * 60)

    print("\n  INPUT PORTS (--midi_in)")
    print("  " + "-" * 40)
    if inputs:
        for name in inputs:
            print(f"    {name}")
    else:
        print("    (none found)")

    print("\n  OUTPUT PORTS (--midi_out, --midi_through)")
    print("  " + "-" * 40)
    if outputs:
        for name in outputs:
            print(f"    {name}")
    else:
        print("    (none found)")

    # Check for IAC Driver
    iac_found = any("IAC" in name for name in inputs + outputs)
    usb_found = any(
        kw in name.lower()
        for name in inputs
        for kw in ["usb", "keyboard", "controller", "mpk", "akai", "arturia", "novation", "korg", "roland"]
    )

    print("\n  STATUS")
    print("  " + "-" * 40)
    if iac_found:
        print("    IAC Driver: FOUND")
    else:
        print("    IAC Driver: NOT FOUND")
        print("      -> Open Audio MIDI Setup.app")
        print("      -> Window > Show MIDI Studio")
        print("      -> Double-click 'IAC Driver'")
        print("      -> Check 'Device is online'")

    if usb_found:
        print("    USB MIDI keyboard: FOUND")
    else:
        print("    USB MIDI keyboard: not detected")
        print("      -> Connect your MIDI controller via USB")
        print("      -> Or use --midi_path mode (no keyboard needed)")

    print()

    # Suggest script configuration
    if iac_found:
        iac_output = next((name for name in outputs if "IAC" in name), None)
        if iac_output:
            print("  SUGGESTED CONFIGURATION")
            print("  " + "-" * 40)
            print(f"    MIDI_OUT=\"{iac_output}\"")
            print(f"    MIDI_THROUGH=\"{iac_output}\"")
            if usb_found:
                usb_input = next(
                    (name for name in inputs if any(
                        kw in name.lower()
                        for kw in ["usb", "keyboard", "controller", "mpk", "akai", "arturia", "novation", "korg", "roland"]
                    )),
                    None,
                )
                if usb_input:
                    print(f"    MIDI_IN=\"{usb_input}\"")
            print()

    print("=" * 60)


if __name__ == "__main__":
    main()
