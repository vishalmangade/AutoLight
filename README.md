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
| `--mode`          | `spectrum` | `spectrum` = bass/mid/treble -> RGB, reactive. `pulse` = single warm color that breathes with volume. |
| `--fps`           | `15`       | Max updates/sec sent to the bulb. Higher = snappier but can make the bulb lag; 10-20 is the sweet spot. |
| `--gain`          | `6.0`      | Sensitivity of the color bands. Raise if colors look dim/muted, lower if they clip to full brightness constantly. |
| `--volume-gain`   | `2.2`      | Sensitivity of the brightness response to volume. |
| `--device`        | system default | Capture a specific playback device by name instead of the default speaker. |
| `--no-restore`    |            | Don't restore the bulb's previous state when you stop the program. |

## Troubleshooting

- **No bulbs found on discover**: confirm the bulb and laptop are on the same
  SSID (not a guest network with client isolation enabled), and allow Python
  through the Windows Firewall if prompted on first run.
- **Audio capture fails / no loopback device**: this uses WASAPI loopback via
  the `soundcard` package, which works with the default Windows audio stack -
  no "Stereo Mix" or virtual cable needed. Make sure something is actually
  playing through the selected output device.
- **Light feels laggy or drops colors**: lower `--fps` (e.g. `--fps 10`) -
  WiZ bulbs can struggle to keep up with commands sent much faster than that
  over wifi.
