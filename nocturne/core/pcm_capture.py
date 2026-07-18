# coding:utf-8
"""
pcm_capture.py — Thread-safe PCM ring buffer from libVLC audio callbacks.

Captures decoded audio samples for FFT processing (FR-4.1) while routing
audio to the system output.  Depends on `sounddevice` for playback.

Usage:
    capture = PCMCapture()
    capture.attach_to_player(player)   # replaces VLC's aout
    capture.start()
    # ... later ...
    samples = capture.read_fft(1024)   # for AudioWorker / numpy FFT
    capture.stop()
"""

from __future__ import annotations

import ctypes
import struct
import threading
import time
from collections import deque
from typing import Optional

import numpy as np
import vlc

try:
    import sounddevice as sd
except ImportError:
    sd = None  # playback disabled; FFT capture works via callback alone


SAMPLE_RATE = 44100
CHANNELS = 2
FORMAT = "S16N"          # signed 16-bit native endian
SAMPLE_WIDTH = 2         # 16-bit = 2 bytes


class PCMCapture:
    """Wraps VLC audio callbacks → ring buffer (+ optional sounddevice out)."""

    def __init__(self, max_samples: int = 32768) -> None:
        self._buffer: deque[float] = deque(maxlen=max_samples)  # mono mixdown
        self._lock = threading.Lock()
        self._running = False
        self._format_set = False
        self._sd_stream: sd.OutputStream | None = None if sd is None else None

    # ── Public API ────────────────────────────────────────────────────

    def attach_to_player(self, player) -> None:
        """Replace VLC's audio output with our callbacks (playback + capture)."""
        player.audio_set_format(FORMAT, SAMPLE_RATE, CHANNELS)
        player.audio_set_callbacks(
            self._play_cb,
            self._pause_cb,
            self._resume_cb,
            self._flush_cb,
            self._drain_cb,
            ctypes.c_void_p(0),
        )
        self._format_set = True

    def start(self) -> None:
        self._running = True
        if sd is not None:
            self._sd_stream = sd.OutputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=1024,
            )
            self._sd_stream.start()

    def stop(self) -> None:
        self._running = False
        if self._sd_stream:
            self._sd_stream.stop()
            self._sd_stream.close()
            self._sd_stream = None
        self._buffer.clear()

    def read_fft(self, n: int = 1024) -> np.ndarray | None:
        """Return up to *n* mono float samples (0..1) for FFT, or None."""
        with self._lock:
            if len(self._buffer) < n:
                return None
            chunk = np.array([self._buffer.popleft() for _ in range(n)],
                             dtype=np.float64)
        return chunk

    # ── VLC callbacks ─────────────────────────────────────────────────

    def _play_cb(self, data: ctypes.c_void_p, samples_ptr, count: int, pts) -> None:
        """Called by libVLC with decoded PCM data."""
        if not self._running or count <= 0:
            return
        try:
            raw = ctypes.string_at(samples_ptr, count * CHANNELS * SAMPLE_WIDTH)
            frame_count = count  # per-channel
            fmt = f"<{frame_count * CHANNELS}h" if struct.pack("=h", 1)[0] == 1 else f">{frame_count * CHANNELS}h"
            ints = struct.unpack(fmt, raw)
        except Exception:
            return

        # Mix down to mono + normalise
        mono = [(ints[i] + ints[i + 1]) / 65536.0
                for i in range(0, len(ints), CHANNELS)]

        with self._lock:
            self._buffer.extend(mono)

        # Forward to sounddevice for audio output
        if self._sd_stream and sd is not None:
            try:
                # Blocking write keeps callback under control
                sd_stream = self._sd_stream
                if sd_stream is not None:
                    arr = np.frombuffer(raw, dtype=np.int16).reshape(-1, CHANNELS)
                    sd_stream.write(arr)
            except Exception:
                pass

    def _pause_cb(self, data, pts) -> None:
        """Pause notification — passthrough to sounddevice."""
        if self._sd_stream and sd is not None:
            self._sd_stream.stop()

    def _resume_cb(self, data, pts) -> None:
        """Resume notification."""
        if self._sd_stream and sd is not None and not self._sd_stream.active:
            self._sd_stream.start()

    def _flush_cb(self, data, pts) -> None:
        """Discard pending buffers."""
        with self._lock:
            self._buffer.clear()

    def _drain_cb(self, data) -> None:
        """Drain remaining — no-op (buffer auto-drains)."""
        pass
