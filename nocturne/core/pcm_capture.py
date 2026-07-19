# coding:utf-8
"""
pcm_capture.py — PCM ring buffer capturing live audio output via PulseAudio monitor.

Uses `parec` subprocess from the default monitor source so the FFT visualizer
reacts to whatever audio is playing — VLC, browser, system sounds.
Falls back to synthetic data when no monitor source is available.
"""

from __future__ import annotations

import logging
import math
import subprocess
import threading
import time
from collections import deque
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class PCMCapture:
    """Thread-backed PCM capture from PulseAudio monitor source."""

    def __init__(self, max_samples: int = 32768) -> None:
        self._buffer: deque[float] = deque(maxlen=max_samples)
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._proc: Optional[subprocess.Popen] = None
        self._monitor_source: Optional[str] = None
        self._rate = 48000

    def _resolve_monitor(self) -> Optional[str]:
        """Find the PulseAudio monitor source for the default sink."""
        try:
            r = subprocess.run(
                ["pactl", "info"],
                capture_output=True, text=True, timeout=3,
            )
            if r.returncode != 0:
                return None
            sink = None
            for line in r.stdout.splitlines():
                if "Default Sink:" in line:
                    sink = line.split(":", 1)[1].strip()
                    break
            if not sink:
                return None
            mon = f"{sink}.monitor"
            # verify it exists
            r2 = subprocess.run(
                ["pactl", "list", "short", "sources"],
                capture_output=True, text=True, timeout=3,
            )
            if mon in r2.stdout:
                logger.info("PulseAudio monitor: %s", mon)
                return mon
        except Exception as e:
            logger.warning("pactl failed: %s", e)
        return None

    def attach_to_player(self, player) -> None:
        pass

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        with self._lock:
            self._buffer.clear()

    def _run(self) -> None:
        src = self._resolve_monitor()
        if src:
            self._capture_parec(src)
        else:
            self._push_synthetic()

    def _capture_parec(self, source: str) -> None:
        """Read raw PCM s16le from parec connected to the monitor source."""
        try:
            self._proc = subprocess.Popen(
                ["parec",
                 f"--device={source}",
                 "--format=s16le",
                 "--channels=1",
                 f"--rate={self._rate}",
                 "--raw"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=4096,
            )
        except FileNotFoundError:
            logger.warning("parec not found, falling back to synthetic")
            self._push_synthetic()
            return

        t = 0
        read_size = 2048  # 1024 samples * 2 bytes
        while self._running and self._proc and self._proc.stdout:
            t += 1
            try:
                raw = self._proc.stdout.read(read_size)
                if not raw:
                    break
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
                samples = np.clip(samples, -1.0, 1.0)

                # Always mix in synthetic variation so bars never freeze on silence
                synth = _synthetic_frame(t)
                mixed = samples * 0.7 + synth * 0.3

                with self._lock:
                    self._buffer.extend(mixed.tolist())
            except Exception:
                break
        self._push_synthetic()

    def _push_synthetic(self) -> None:
        """Idle animation — IFFT-based so spectrum varies per frame."""
        t = 0
        while self._running:
            t += 1
            samples = _synthetic_frame(t)
            with self._lock:
                self._buffer.extend(samples.tolist())
            time.sleep(0.032)


def _synthetic_frame(t: int) -> np.ndarray:
    """Generate one frame of synthetic PCM data with varying spectrum."""
    n_fft = 512
    spec = np.zeros(n_fft + 1, dtype=np.complex128)
    peaks = [
        (2 + int(10 * (math.sin(t * 0.05) * 0.5 + 0.5)), 1.0),
        (15 + int(15 * (math.sin(t * 0.09 + 1.3) * 0.5 + 0.5)), 0.8),
        (35 + int(15 * (math.sin(t * 0.14 + 2.7) * 0.5 + 0.5)), 0.6),
        (55 + int(8 * (math.sin(t * 0.20 + 4.0) * 0.5 + 0.5)), 0.4),
    ]
    for visible_band, amp in peaks:
        bin_idx = min(int(visible_band * n_fft / 64 + 4), n_fft)
        for spread in (-2, -1, 0, 1, 2):
            idx = bin_idx + spread
            if 0 <= idx <= n_fft:
                spec[idx] = complex(amp * max(0, 1 - abs(spread) * 0.3), 0)

    phases = np.exp(1j * np.random.uniform(0, 2 * np.pi, n_fft + 1))
    spec = spec * phases
    samples = np.fft.irfft(spec)
    mx = float(np.max(np.abs(samples))) or 1.0
    return (samples / mx) * 0.15

    def read_fft(self, n: int = 1024) -> np.ndarray:
        """Return a real-valued PCM sample buffer suitable for FFT.
        Consumes the samples so each call returns fresh data.
        """
        with self._lock:
            if not self._buffer:
                return self._build_fallback_window(n)

            # Take up to n samples and remove them from the buffer
            count = min(len(self._buffer), n)
            samples = np.asarray([self._buffer.popleft() for _ in range(count)], dtype=np.float64)

        samples = np.nan_to_num(samples, nan=0.0, posinf=0.0, neginf=0.0)
        if len(samples) < n:
            samples = np.pad(samples, (0, n - len(samples)))
        mx = float(np.max(np.abs(samples))) if samples.size else 0.0
        if mx > 0:
            samples = np.clip(samples / mx, -1.0, 1.0)
        return samples.astype(np.float64)

    @staticmethod
    def _build_fallback_window(n: int) -> np.ndarray:
        base = np.linspace(0, 2 * np.pi, max(8, n))
        return 0.12 * np.sin(base).astype(np.float64)
