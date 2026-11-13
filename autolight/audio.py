"""System audio loopback capture - captures what you hear, not the microphone.

Uses WASAPI loopback via the `soundcard` library, so no virtual audio cable
or legacy "Stereo Mix" device needs to be enabled on Windows.
"""
from __future__ import annotations

import numpy as np
import soundcard as sc


class LoopbackCapture:
    def __init__(self, samplerate: int = 48000, blocksize: int = 1024, device_name: str | None = None):
        self.samplerate = samplerate
        self.blocksize = blocksize
        speaker = sc.get_speaker(device_name) if device_name else sc.default_speaker()
        self.device_name = speaker.name
        self._mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
        self._recorder = None

    def __enter__(self) -> "LoopbackCapture":
        self._recorder = self._mic.recorder(samplerate=self.samplerate, blocksize=self.blocksize)
        self._recorder.__enter__()
        return self

    def __exit__(self, *exc) -> None:
        if self._recorder:
            self._recorder.__exit__(*exc)

    def read(self) -> np.ndarray:
        """Return the latest audio block as mono float32 samples in [-1, 1]."""
        data = self._recorder.record(numframes=self.blocksize)
        return data.mean(axis=1) if data.ndim > 1 else data
