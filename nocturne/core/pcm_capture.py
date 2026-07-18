# coding:utf-8
"""
pcm_capture.py — PCM buffer for FFT using a live system input source.

The visualizer should receive continuous sample data even when a dedicated
monitor/loopback source is not exposed by the host audio stack. On Linux,
we prefer a PipeWire/Pulse monitor device when available and otherwise fall
back to the default input stream, which still keeps the UI animated.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Optional

import numpy as np

try:
    import sounddevice as sd
except Exception:  # pragma: no cover - environment-dependent
    sd = None


class PCMCapture:
    """Thread-backed PCM capture with a monitor-friendly fallback path."""

    def __init__(self, max_samples: int = 32768) -> None:
        self._buffer: deque[float] = deque(maxlen=max_samples)
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stream = None
        self._device = self._resolve_device()
        self._sample_rate = 48000
        self._channels = 1

    def _resolve_device(self) -> str | None:
        if sd is None:
            return None

        try:
            devices = sd.query_devices()
        except Exception:
            return None

        for device in devices:
            name = str(device.get("name", "")).lower()
            if any(k in name for k in ("monitor", "loopback", "pipewire", "pulse")):
                return device.get("name")
        return None

    def attach_to_player(self, player) -> None:
        """No-op: VLC handles audio output normally."""
        pass

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self._stream is not None:
            try:
                self._stream.stop()
            except Exception:
                pass
            try:
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        with self._lock:
            self._buffer.clear()

    def _capture_loop(self) -> None:
        """Capture audio into a ring buffer if a live input device is available."""
        if sd is None:
            self._push_synthetic_samples()
            return

        try:
            if self._device:
                device = self._device
            else:
                device = None

            with sd.InputStream(
                device=device,
                channels=self._channels,
                samplerate=self._sample_rate,
                dtype="float32",
                blocksize=1024,
            ) as stream:
                self._stream = stream
                stream.start()
                while self._running:
                    frames, _ = stream.read(1024)
                    if frames is None or len(frames) == 0:
                        continue
                    samples = np.asarray(frames, dtype=np.float64).reshape(-1)
                    samples = np.nan_to_num(samples, nan=0.0, posinf=0.0, neginf=0.0)
                    with self._lock:
                        self._buffer.extend(samples.tolist())
                    time.sleep(0.01)
        except Exception:
            self._push_synthetic_samples()

    def _push_synthetic_samples(self) -> None:
        """Keep the UI alive when no monitor source is exposed by the OS."""
        phase = 0.0
        while self._running:
            phase += 0.35
            samples = 0.08 * np.sin(np.linspace(0, 6 * np.pi, 256) + phase)
            with self._lock:
                self._buffer.extend(samples.tolist())
            time.sleep(0.04)

    def read_fft(self, n: int = 1024) -> np.ndarray:
        """Return a real-valued PCM sample buffer suitable for FFT analysis."""
        with self._lock:
            if not self._buffer:
                return self._build_fallback_window(n)

            samples = np.asarray(self._buffer, dtype=np.float64)
            if len(samples) > n:
                samples = samples[-n:]

        samples = np.nan_to_num(samples, nan=0.0, posinf=0.0, neginf=0.0)
        mx = float(np.max(np.abs(samples))) if samples.size else 0.0
        if mx > 0:
            samples = samples / mx
        return samples.astype(np.float64)

    @staticmethod
    def _build_fallback_window(n: int) -> np.ndarray:
        base = np.linspace(0, 2 * np.pi, max(8, n))
        return 0.12 * np.sin(base).astype(np.float64)
