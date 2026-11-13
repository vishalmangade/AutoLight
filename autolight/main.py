"""AutoLight: sync a Philips WiZ smart bulb to your laptop's audio output.

Usage:
    python -m autolight.main --discover
    python -m autolight.main --ip 192.168.1.42
    python -m autolight.main --ip 192.168.1.42 --mode pulse --fps 10
"""
from __future__ import annotations

import argparse
import sys
import time

from autolight.audio import LoopbackCapture
from autolight.color import MODE_FACTORIES
from autolight.dsp import BandAnalyzer
from autolight.wiz import WizBulb, discover

SAMPLERATE = 48000
BLOCKSIZE = 1024


def run(args: argparse.Namespace) -> None:
    bulb = WizBulb(args.ip, min_interval=1 / args.fps)
    previous_state = bulb.get_pilot()
    if previous_state is None:
        print(f"Warning: could not reach bulb at {args.ip} (no reply to getPilot). Continuing anyway.")

    analyzer = BandAnalyzer(SAMPLERATE, BLOCKSIZE, gain=args.gain)
    color_fn = MODE_FACTORIES[args.mode]()

    print(f"AutoLight running -> bulb {args.ip} | mode={args.mode} | fps<={args.fps}")
    print("Ctrl+C to stop.")

    last_debug = 0.0
    try:
        with LoopbackCapture(samplerate=SAMPLERATE, blocksize=BLOCKSIZE, device_name=args.device) as cap:
            print(f"Capturing system audio from: {cap.device_name}")
            while True:
                samples = cap.read()
                bass, mid, treble, volume, hue = analyzer.analyze(samples)
                r, g, b, dimming = color_fn(
                    bass, mid, treble, volume, hue=hue, volume_gain=args.volume_gain, floor=args.floor, ceiling=args.ceiling
                )
                bulb.set_color(r, g, b, dimming)
                if args.debug and time.monotonic() - last_debug > 0.5:
                    hue_str = f"{hue:.2f}" if hue is not None else "None"
                    print(
                        f"volume={volume:.3f} bass={bass:.2f} mid={mid:.2f} treble={treble:.2f} hue={hue_str} "
                        f"-> rgb=({r},{g},{b}) dimming={dimming}"
                    )
                    last_debug = time.monotonic()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        if args.restore and previous_state:
            _restore(bulb, previous_state)
        bulb.close()


def _restore(bulb: WizBulb, state: dict) -> None:
    if {"r", "g", "b"} <= state.keys():
        bulb.set_color(state["r"], state["g"], state["b"], state.get("dimming", 100))
    elif "state" in state:
        bulb.set_state(state["state"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync a Philips WiZ bulb to your PC's audio output.")
    parser.add_argument("--ip", help="Bulb IP address (omit to auto-discover on the LAN)")
    parser.add_argument("--discover", action="store_true", help="List WiZ bulbs found on the LAN and exit")
    parser.add_argument("--device", help="Playback device name to capture (default: system default output)")
    parser.add_argument("--mode", choices=list(MODE_FACTORIES), default="spectrum")
    parser.add_argument("--fps", type=float, default=15, help="Max updates/sec sent to the bulb")
    parser.add_argument("--gain", type=float, default=6.0, help="Audio sensitivity for color bands")
    parser.add_argument("--volume-gain", type=float, default=2.2, help="Sensitivity for brightness response")
    parser.add_argument("--floor", type=int, default=20, help="Minimum brightness (10-100) sent to the bulb, even during quiet passages")
    parser.add_argument("--ceiling", type=int, default=100, help="Maximum brightness (10-100) sent to the bulb")
    parser.add_argument("--no-restore", dest="restore", action="store_false", help="Don't restore the bulb's previous state on exit")
    parser.add_argument("--debug", action="store_true", help="Print live audio levels and the color being sent, twice a second")
    args = parser.parse_args()

    if args.discover:
        bulbs = discover()
        if not bulbs:
            print("No WiZ bulbs found. Make sure your laptop is on the same wifi network as the bulb.")
        for b in bulbs:
            print(f"{b['ip']}  {b['info']}")
        return

    if not args.ip:
        print("No --ip given, searching for WiZ bulbs on your network...")
        bulbs = discover()
        if not bulbs:
            print("No bulbs found. Pass --ip <bulb-ip> explicitly (check your router's DHCP client list).")
            sys.exit(1)
        if len(bulbs) == 1:
            args.ip = bulbs[0]["ip"]
            print(f"Using {args.ip}")
        else:
            print("Multiple bulbs found:")
            for i, b in enumerate(bulbs):
                print(f"  [{i}] {b['ip']}")
            idx = int(input("Pick one: "))
            args.ip = bulbs[idx]["ip"]

    run(args)


if __name__ == "__main__":
    main()
