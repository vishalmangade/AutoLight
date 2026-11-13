"""Maps analyzed audio energy to WiZ RGB + brightness values."""
from __future__ import annotations

import colorsys
import time

PULSE_BASE_RGB = (255, 120, 20)  # warm amber; change to taste


def _loudness(volume: float, volume_gain: float) -> float:
    """Perceptual-ish 0-1 loudness: sqrt curve gives quiet passages more range
    than a straight linear scale would (real listening volumes are often a
    small fraction of full-scale RMS)."""
    if volume <= 0:
        return 0.0
    return min((volume * volume_gain) ** 0.5, 1.0)


def spectrum_color(
    bass: float, mid: float, treble: float, volume: float, volume_gain: float = 2.2, floor: int = 15, ceiling: int = 100, **_
) -> tuple[int, int, int, int]:
    """Bass -> red, mid -> green, treble -> blue; overall loudness -> brightness."""
    peak = max(bass, mid, treble, 1e-6)
    r, g, b = bass / peak, mid / peak, treble / peak
    dimming = floor + (ceiling - floor) * _loudness(volume, volume_gain)
    return int(r * 255), int(g * 255), int(b * 255), int(dimming)


def pulse_color(
    bass: float, mid: float, treble: float, volume: float, volume_gain: float = 2.2, floor: int = 10, ceiling: int = 100, **_
) -> tuple[int, int, int, int]:
    """A single warm color that breathes with volume; treble adds a sparkle toward white."""
    dimming = floor + (ceiling - floor) * _loudness(volume, volume_gain)
    sparkle = min(treble * 1.5, 1.0)
    r0, g0, b0 = PULSE_BASE_RGB
    r = r0 + sparkle * (255 - r0)
    g = g0 + sparkle * (255 - g0)
    b = b0 + sparkle * (255 - b0)
    return int(r), int(g), int(b), int(dimming)


class PartyMode:
    """Hue follows the song's dominant pitch (chroma, so the same musical
    note always lands on the same color regardless of octave); brightness
    flashes on detected beats.

    Full-mix music doesn't have one true "pitch" (it's chords + drums +
    vocals at once) - this tracks the loudest clearly-tonal component per
    instant, which is the standard approximation used by simple audio
    visualizers. It tracks a lead vocal/melody/bassline well and gets
    noisier on dense, percussion-heavy mixes (where pitch is often None
    anyway, so the color just holds steady instead of jumping).
    """

    def __init__(self, beat_sensitivity: float = 1.5, flash: float = 0.3):
        self.hue = 0.0
        self.beat_sensitivity = beat_sensitivity
        self.flash = flash
        self._volume_avg = 0.0
        self._last_beat = 0.0

    def __call__(
        self,
        bass: float,
        mid: float,
        treble: float,
        volume: float,
        hue: float | None = None,
        volume_gain: float = 2.2,
        floor: int = 12,
        ceiling: int = 100,
        **_,
    ) -> tuple[int, int, int, int]:
        now = time.monotonic()
        if hue is not None:
            self.hue = hue  # else hold the last color - e.g. during a drum-only passage

        # beat = volume spiking well above its own slow-moving baseline
        self._volume_avg += (volume - self._volume_avg) * 0.04
        is_beat = volume > self._volume_avg * self.beat_sensitivity + 0.01 and (now - self._last_beat) > 0.12
        if is_beat:
            self._last_beat = now

        loud = _loudness(volume, volume_gain)
        flash_boost = self.flash if is_beat else 0.0
        value = min(1.0, floor / 100 + (ceiling / 100 - floor / 100) * loud + flash_boost)
        saturation = 1.0 - min(treble * 0.4, 0.3)  # a little treble = slight white sparkle

        r, g, b = colorsys.hsv_to_rgb(self.hue, saturation, value)
        dimming = max(floor, min(ceiling, int(value * 100)))
        return int(r * 255), int(g * 255), int(b * 255), dimming


MODE_FACTORIES = {
    "spectrum": lambda: spectrum_color,
    "pulse": lambda: pulse_color,
    "party": lambda: PartyMode(),
}
