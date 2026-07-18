# coding:utf-8
"""
pcm_capture.py — PCM buffer for FFT via PulseAudio monitor source.

Keeps VLC native audio output intact. Uses a separate thread to capture
audio from PulseAudio's monitor (loopback) source for FFT processing.

Fallback: returns None (visualizer shows empty bars).
"""

from __future__ import annotations

import struct
import threading
import time
from collections import deque
from typing import Optional

import numpy as np


class PCMCapture:
    """Captures PCM from the running audio output for FFT analysis.

    Currently a stub — real capture requires PulseAudio / PipeWire monitor
    source integration. Returns None from read_fft, so the visualizer shows
    flat bars.
    """

    def __init__(self, max_samples: int = 32768) -> None:
        self._buffer: deque[float] = deque(maxlen=max_samples)
        self._lock = threading.Lock()
        self._running = False

    def attach_to_player(self, player) -> None:
        """No-op: VLC handles audio output normally."""
        pass

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False
        with self._lock:
            self._buffer.clear()

    def read_fft(self, n: int = 1024) -> np.ndarray | None:
        """Return None — capture not yet implemented.

        ponytail: Implement via ``pw-stream`` or ``pulseaudio`` monitor source
        in a background thread. Add when real visualizer data is needed.
        """
        return None
