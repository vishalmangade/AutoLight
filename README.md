# AutoLight

Sync a Philips WiZ smart bulb to your laptop's audio output - no phone app,
no microphone, no cloud. Talks directly to the bulb over your wifi using the
same local UDP protocol the WiZ app uses (port 38899).

## Setup

```
pip install -r requirements.txt
```

Make sure your laptop is connected to the **same wifi network** as the bulb.

## Find your bulb

```
python -m autolight.main --discover
```

This broadcasts on the LAN and lists any WiZ bulbs that reply with their IP.
If it finds nothing, check your router's DHCP client list for a device named
like `wiz_...`.

## Run

```
python -m autolight.main --ip 192.168.1.42
```

Or skip `--ip` and it will auto-discover (and ask you to pick, if there's more
than one bulb):

```
python -m autolight.main
```

Press `Ctrl+C` to stop - the bulb is restored to whatever state it was in
before you started.

## Options

| Flag            | Default    | Meaning                                              |
|------------------|------------|-------------------------------------------------------|
| `--mode`          | `spectrum` | `spectrum` = bass/mid/treble -> RGB. `pulse` = single warm color that breathes with volume. `party` = hue follows the song's pitch, brightness flashes on beats. |
| `--fps`           | `15`       | Max updates/sec sent to the bulb. Higher = snappier but can make the bulb lag; 10-20 is the sweet spot. |
| `--gain`          | `6.0`      | Sensitivity of the color bands. Raise if colors look dim/muted, lower if they clip to full brightness constantly. |
| `--volume-gain`   | `2.2`      | Sensitivity of the brightness response to volume. Raise this if `dimming` stays low during normal listening volume. |
| `--floor`         | `20`       | Minimum brightness (10-100) sent to the bulb, even during quiet passages. |
| `--ceiling`       | `100`      | Maximum brightness (10-100) sent to the bulb. |
| `--device`        | system default | Capture a specific playback device by name instead of the default speaker. |
| `--no-restore`    |            | Don't restore the bulb's previous state when you stop the program. |
| `--debug`         |            | Print live audio levels and the color being sent, twice a second - useful for tuning the flags above. |

## Troubleshooting

- **No bulbs found on discover**: confirm the bulb and laptop are on the same
  SSID (not a guest network with client isolation enabled), and allow Python
  through the Windows Firewall if prompted on first run.
- **Laptop on 5GHz, bulb on 2.4GHz (same router, still not found/reachable)**:
  smart bulbs are 2.4GHz-only. Many routers put 2.4GHz and 5GHz on separate
  SSIDs with client/AP isolation enabled by default, which silently drops
  *both* broadcast discovery and direct unicast control between the two bands
  - nothing to do with this tool or your firewall. To check and fix:
  1. Get the bulb's IP from the WiZ app (tap the bulb -> device/Wi-Fi info)
     and test direct control, bypassing discovery entirely:
     ```
     python -m autolight.main --ip <bulb-ip> --debug
     ```
     If this prints `Warning: could not reach bulb` / nothing happens, the
     bands are isolated from each other at the router.
  2. Fix it in your router's admin page: enable **Smart Connect** / **Band
     Steering** to merge 2.4GHz + 5GHz into one SSID/broadcast domain (the
     standard recommendation for smart-home devices), or just connect your
     laptop to the bulb's 2.4GHz SSID while running this tool.
- **Audio capture fails / no loopback device**: this uses WASAPI loopback via
  the `soundcard` package, which works with the default Windows audio stack -
  no "Stereo Mix" or virtual cable needed. Make sure something is actually
  playing through the selected output device.
- **Light feels laggy or drops colors**: lower `--fps` (e.g. `--fps 10`) -
  WiZ bulbs can struggle to keep up with commands sent much faster than that
  over wifi.
- **Colors look dim or stuck in a narrow brightness range**: raise
  `--volume-gain` and/or `--floor`, and use `--debug` to watch the live
  `volume`/`dimming` values while tuning.
