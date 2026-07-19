# coding:utf-8
"""
audio_worker.py — QThread that runs numpy FFT asynchronously.

Emits processed spectrum data via Qt signals.  Never touches the main thread.
"""

from __future__ import annotations


import logging

import numpy as np
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class AudioWorker(QThread):
    """Worker thread for FFT spectrum analysis.

    Pulls PCM data from PlayerEngine, applies numpy FFT, and emits
    frequency magnitudes to the UI visualizer at ~30 fps.
    """

    spectrum_ready = Signal(object)  # numpy.ndarray of magnitudes

    def __init__(self, pcm_source=None, parent=None) -> None:
        """
        Args:
            pcm_source: callable that returns list[float] or None (from PlayerEngine).
        """
        super().__init__(parent)
        self._pcm_source = pcm_source
        self._running = False
        self._band_count = 64  # configurable

    @property
    def band_count(self) -> int:
        return self._band_count

    @band_count.setter
    def band_count(self, n: int) -> None:
        self._band_count = max(8, min(128, n))

    def run(self) -> None:
        """Main loop: pull PCM -> FFT -> emit spectrum_ready every ~33ms."""
        self._running = True
        n_fft = 1024

        while self._running and self._pcm_source:
            data = self._pcm_source(n_fft)
            if data is None or len(data) < 2:
                self.msleep(33)
                continue

            try:
                arr = np.array(data, dtype=np.float64)
                spectrum = np.abs(np.fft.rfft(arr))[:n_fft // 2]

                # Band grouping: map FFT bins to uniform band count
                if len(spectrum) > 0:
                    band_size = max(1, len(spectrum) // self._band_count)
                    grouped = np.array([
                        np.mean(spectrum[i:i + band_size])
                        for i in range(0, len(spectrum), band_size)
                    ][:self._band_count])

                    # Normalise to 0-1 range
                    mx = np.max(grouped)
                    if mx > 0:
                        grouped = grouped / mx
                else:
                    grouped = np.zeros(self._band_count)

                self.spectrum_ready.emit(grouped)
            except Exception:
                logger.exception("FFT processing failed")

            self.msleep(33)  # ~30 fps

    def stop(self) -> None:
        """Gracefully stop the worker loop."""
        self._running = False
        self.wait(500)
