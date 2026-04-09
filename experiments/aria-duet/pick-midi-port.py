#!/usr/bin/env python3
"""Interactive MIDI port picker for Aria-Duet run scripts.

Called by run-*.sh to select MIDI ports at runtime. Prints the chosen
port name to stdout (the shell script captures it). All prompts go to
stderr so they don't contaminate the captured output.

Usage:
    # Pick an output port
    PORT=$(python pick-midi-port.py output)

    # Pick an input port
    PORT=$(python pick-midi-port.py input)

    # Skip prompt if only one port matches
    PORT=$(python pick-midi-port.py output)

    # Pre-selected via config.sh (script prints it back, no prompt)
    PORT=$(python pick-midi-port.py output "IAC Driver Bus 1")
"""

import sys

try:
    import mido
except ImportError:
    print("Error: mido not installed. Run ./setup.sh first.", file=sys.stderr)
    sys.exit(1)


def pick_port(direction: str, preset: str | None = None) -> str:
    """Pick a MIDI port interactively. Returns the port name."""
    if direction == "input":
        ports = mido.get_input_names()
        label = "MIDI INPUT"
    else:
        ports = mido.get_output_names()
        label = "MIDI OUTPUT"

    # Deduplicate while preserving order
    seen = set()
    unique_ports = []
    for p in ports:
        if p not in seen:
            seen.add(p)
            unique_ports.append(p)
    ports = unique_ports

    if not ports:
        print(f"\nNo {label} ports found.", file=sys.stderr)
        print("  - On macOS: enable IAC Driver in Audio MIDI Setup.app", file=sys.stderr)
        print("  - On Linux: ensure ALSA or JACK is running", file=sys.stderr)
        print("  - On Windows: ensure a MIDI driver is installed", file=sys.stderr)
        sys.exit(1)

    # If a preset was given and it exists, use it silently
    if preset and preset in ports:
        return preset
    elif preset:
        print(f"\n  Warning: configured port \"{preset}\" not found.", file=sys.stderr)
        print(f"  Available ports:", file=sys.stderr)
        # Fall through to interactive selection

    # Auto-select if only one port
    if len(ports) == 1:
        print(f"  {label}: {ports[0]} (auto-selected, only port available)", file=sys.stderr)
        return ports[0]

    # Interactive selection
    print(f"\n  Select {label} port:", file=sys.stderr)
    for i, name in enumerate(ports, 1):
        print(f"    {i}) {name}", file=sys.stderr)

    while True:
        try:
            print(f"  Choice [1-{len(ports)}]: ", end="", file=sys.stderr, flush=True)
            raw = input()
            idx = int(raw) - 1
            if 0 <= idx < len(ports):
                return ports[idx]
        except (ValueError, EOFError):
            pass
        print(f"  Please enter a number between 1 and {len(ports)}.", file=sys.stderr)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("input", "output"):
        print("Usage: pick-midi-port.py <input|output> [preset-name]", file=sys.stderr)
        sys.exit(1)

    direction = sys.argv[1]
    preset = sys.argv[2] if len(sys.argv) > 2 else None

    port = pick_port(direction, preset)
    # Print to stdout for shell capture
    print(port)


if __name__ == "__main__":
    main()
