#!/usr/bin/env python3
"""Send a short piano phrase on a virtual MIDI output port for live-demo smoke tests."""

from __future__ import annotations

import argparse
import time

import mido


DEFAULT_PORT = "Codex Live Input"

# (start_s, duration_s, pitch, velocity)
PHRASE = [
    (0.00, 0.45, 60, 76),
    (0.00, 0.45, 64, 70),
    (0.00, 0.45, 67, 74),
    (0.55, 0.40, 62, 72),
    (0.55, 0.40, 65, 68),
    (0.55, 0.40, 69, 72),
    (1.05, 0.35, 64, 78),
    (1.05, 0.35, 67, 73),
    (1.05, 0.35, 71, 77),
    (1.50, 0.70, 72, 84),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port-name", default=DEFAULT_PORT)
    parser.add_argument(
        "--start-delay",
        type=float,
        default=2.0,
        help="Seconds to wait before sending the first note.",
    )
    parser.add_argument(
        "--linger-seconds",
        type=float,
        default=20.0,
        help="How long to keep the virtual port open after sending the phrase.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    deadline = time.monotonic() + args.start_delay

    with mido.open_output(args.port_name, virtual=True, autoreset=True) as port:
        print(f"Opened virtual MIDI output: {args.port_name}", flush=True)
        while time.monotonic() < deadline:
            time.sleep(0.01)

        phrase_start = time.monotonic()
        scheduled = []

        for idx, note in enumerate(PHRASE):
            start_s, duration_s, pitch, velocity = note
            scheduled.append((phrase_start + start_s, True, idx, pitch, velocity))
            scheduled.append(
                (phrase_start + start_s + duration_s, False, idx, pitch, 0)
            )

        scheduled.sort()

        for send_at, is_note_on, _, pitch, velocity in scheduled:
            while True:
                now = time.monotonic()
                if now >= send_at:
                    break
                time.sleep(min(0.01, send_at - now))

            port.send(
                mido.Message(
                    "note_on" if is_note_on else "note_off",
                    note=pitch,
                    velocity=velocity,
                    channel=0,
                )
            )

        time.sleep(args.linger_seconds)


if __name__ == "__main__":
    main()
