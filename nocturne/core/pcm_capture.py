# coding:utf-8
"""
pcm_capture.py — PCM ring buffer from libVLC audio callbacks + playback thread.

Because VLC audio callbacks run on a non-Python thread, we never call
sounddevice from inside the callback. Instead we queue PCM data to a
playback worker thread via a lock-free pipe.
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
    sd = None


SAMPLE_RATE = 44100
CHANNELS = 2
FORMAT = "S16N"
SAMPLE_WIDTH = 2


# ── Module-level C callbacks ────────────────────────────────────────
# CFUNCTYPE can't wrap bound methods, so we use a module singleton.

_capture: Optional["PCMCapture"] = None
_cap_lock = threading.Lock()


def _get_cap():
    with _cap_lock:
        return _capture


def _play_cb(data_ptr, samples_ptr, count, pts):
    cap = _get_cap()
    if cap:
        cap._on_play(samples_ptr, count, pts)


def _pause_cb(data_ptr, pts):
    cap = _get_cap()
    if cap:
        cap._on_pause()


def _resume_cb(data_ptr, pts):
    cap = _get_cap()
    if cap:
        cap._on_resume()


def _flush_cb(data_ptr, pts):
    cap = _get_cap()
    if cap:
        cap._on_flush()


def _drain_cb(data_ptr):
    cap = _get_cap()
    if cap:
        cap._on_drain()


_PLAY_CB_T = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_int64)
_PAUSE_CB_T = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int64)
_RESUME_CB_T = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int64)
_FLUSH_CB_T = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int64)
_DRAIN_CB_T = ctypes.CFUNCTYPE(None, ctypes.c_void_p)

_CB_PLAY = _PLAY_CB_T(_play_cb)
_CB_PAUSE = _PAUSE_CB_T(_pause_cb)
_CB_RESUME = _RESUME_CB_T(_resume_cb)
_CB_FLUSH = _FLUSH_CB_T(_flush_cb)
_CB_DRAIN = _DRAIN_CB_T(_drain_cb)


# ── Playback thread ─────────────────────────────────────────────────

class _PlaybackThread(threading.Thread):
    """Consumes PCM from a deque and writes to sounddevice."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.queue: deque[bytes] = deque()
        self._ev = threading.Event()
        self._running = True

    def run(self) -> None:
        if sd is None:
            return
        stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=1024,
        )
        stream.start()
        while self._running:
            try:
                data = self.queue.popleft()
                arr = np.frombuffer(data, dtype=np.int16).reshape(-1, CHANNELS)
                stream.write(arr)
            except IndexError:
                self._ev.wait(0.010)
        stream.stop()
        stream.close()

    def feed(self, raw: bytes) -> None:
        self.queue.append(raw)

    def shutdown(self) -> None:
        self._running = False
        self._ev.set()


class PCMCapture:
    """Wraps VLC audio callbacks → ring buffer (+ playback thread)."""

    def __init__(self, max_samples: int = 32768) -> None:
        self._buffer: deque[float] = deque(maxlen=max_samples)
        self._buf_lock = threading.Lock()
        self._running = False
        self._format_set = False
        self._playback: _PlaybackThread | None = None
        self._paused = False

    # ── Public API ────────────────────────────────────────────────────

    def attach_to_player(self, player) -> None:
        global _capture
        with _cap_lock:
            _capture = self
        player.audio_set_format(FORMAT, SAMPLE_RATE, CHANNELS)
        player.audio_set_callbacks(
            _CB_PLAY, _CB_PAUSE, _CB_RESUME, _CB_FLUSH, _CB_DRAIN,
            ctypes.c_void_p(0),
        )
        self._format_set = True

    def start(self) -> None:
        self._running = True
        self._paused = False
        if sd is not None and self._playback is None:
            self._playback = _PlaybackThread()
            self._playback.start()

    def stop(self) -> None:
        self._running = False
        if self._playback:
            self._playback.shutdown()
            self._playback = None
        with self._buf_lock:
            self._buffer.clear()

    def read_fft(self, n: int = 1024) -> np.ndarray | None:
        with self._buf_lock:
            if len(self._buffer) < n:
                return None
            chunk = np.array([self._buffer.popleft() for _ in range(n)],
                             dtype=np.float64)
        return chunk

    # ── VLC callbacks (called from VLC thread — keep minimal) ─────────

    def _on_play(self, samples_ptr, count: int, pts: int) -> None:
        """VLC audio thread — do NOT call Python blocking I/O."""
        if not self._running or count <= 0:
            return
        try:
            raw = ctypes.string_at(samples_ptr, count * CHANNELS * SAMPLE_WIDTH)
            F = "<" if struct.pack("=h", 1)[0] == 1 else ">"
            F += f"{count * CHANNELS}h"
            ints = struct.unpack(F, raw)
        except Exception:
            return
        # Mono mixdown → FFT buffer (fast, no I/O)
        mono = [(ints[i] + ints[i + 1]) / 65536.0
                for i in range(0, len(ints), CHANNELS)]
        with self._buf_lock:
            self._buffer.extend(mono)
        # Delegate audio output to playback thread
        if self._playback and not self._paused:
            self._playback.feed(raw)

    def _on_pause(self) -> None:
        self._paused = True

    def _on_resume(self) -> None:
        self._paused = False

    def _on_flush(self) -> None:
        with self._buf_lock:
            self._buffer.clear()

    def _on_drain(self) -> None:
        pass
