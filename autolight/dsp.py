"""Turns raw audio blocks into smoothed bass/mid/treble energy, loudness, and pitch."""
from __future__ import annotations

import numpy as np

BASS_RANGE = (20, 250)
MID_RANGE = (250, 4000)
TREBLE_RANGE = (4000, 16000)
PITCH_RANGE = (80, 2000)  # typical melody/vocal/bass-guitar fundamental range
PITCH_REFERENCE_HZ = 220.0  # A3; just an anchor for the octave-folding math below


class BandAnalyzer:
    def __init__(
        self,
        samplerate: int,
        blocksize: int,
        gain: float = 6.0,
        attack: float = 0.6,
        decay: float = 0.15,
        noise_gate: float = 0.02,
        pitch_prominence: float = 2.0,
        hue_smoothing: float = 0.3,
    ):
        self.gain = gain
        self.attack = attack
        self.decay = decay
        self.noise_gate = noise_gate
        self.pitch_prominence = pitch_prominence
        self.hue_smoothing = hue_smoothing
        self._window = np.hanning(blocksize)
        self._freqs = np.fft.rfftfreq(blocksize, d=1 / samplerate)
        self._bass_mask = (self._freqs >= BASS_RANGE[0]) & (self._freqs < BASS_RANGE[1])
        self._mid_mask = (self._freqs >= MID_RANGE[0]) & (self._freqs < MID_RANGE[1])
        self._treble_mask = (self._freqs >= TREBLE_RANGE[0]) & (self._freqs < TREBLE_RANGE[1])
        self._pitch_mask = (self._freqs >= PITCH_RANGE[0]) & (self._freqs < PITCH_RANGE[1])
        self._pitch_freqs = self._freqs[self._pitch_mask]
        self._smoothed = np.zeros(3)  # bass, mid, treble
        self._volume = 0.0
        self._hue_vec = complex(1.0, 0.0)  # circular EMA state for smoothing hue across the 0/1 wrap

    def analyze(self, samples: np.ndarray) -> tuple[float, float, float, float, float | None]:
        """Returns (bass, mid, treble, volume, hue); bands/volume smoothed to roughly 0-1.

        hue is a smoothed 0-1 chroma value (same musical note -> same hue,
        regardless of octave), or None when no clear tonal pitch is present
        (silence, pure percussion/noise) - callers should hold their last
        color in that case rather than snapping to black/red.
        """
        volume = float(np.sqrt(np.mean(samples**2)))
        if volume < self.noise_gate:
            samples = samples * 0.0
            volume = 0.0

        spectrum = np.abs(np.fft.rfft(samples * self._window))
        raw = np.array(
            [
                spectrum[self._bass_mask].mean() if self._bass_mask.any() else 0.0,
                spectrum[self._mid_mask].mean() if self._mid_mask.any() else 0.0,
                spectrum[self._treble_mask].mean() if self._treble_mask.any() else 0.0,
            ]
        )
        raw = np.clip(np.log1p(raw * self.gain), 0.0, 1.0)

        for i in range(3):
            coeff = self.attack if raw[i] > self._smoothed[i] else self.decay
            self._smoothed[i] += (raw[i] - self._smoothed[i]) * coeff

        vol_coeff = self.attack if volume > self._volume else self.decay
        self._volume += (volume - self._volume) * vol_coeff

        hue = self._detect_pitch_hue(spectrum, volume)

        return (*self._smoothed.tolist(), self._volume, hue)

    def _detect_pitch_hue(self, spectrum: np.ndarray, volume: float) -> float | None:
        if volume <= 0 or not self._pitch_mask.any():
            return None

        band = spectrum[self._pitch_mask]
        peak_idx = int(np.argmax(band))
        peak_mag = band[peak_idx]
        if peak_mag <= band.mean() * self.pitch_prominence:
            return None  # no standout tone this frame - likely percussion/noise

        freq = self._pitch_freqs[peak_idx]
        semitones = 12.0 * np.log2(freq / PITCH_REFERENCE_HZ)
        chroma = (semitones % 12.0) / 12.0  # fold to one octave: note name, ignoring which octave

        target = complex(np.cos(chroma * 2 * np.pi), np.sin(chroma * 2 * np.pi))
        self._hue_vec += (target - self._hue_vec) * self.hue_smoothing
        return float((np.angle(self._hue_vec) / (2 * np.pi)) % 1.0)
