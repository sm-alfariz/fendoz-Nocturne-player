# coding:utf-8
"""
pcm_capture.py — Thread-safe PCM ring buffer from libVLC audio callbacks.

Captures decoded audio samples for FFT processing (FR-4.1) while routing
audio to the system output via sounddevice.

Because VLC audio callbacks (CFUNCTYPE) cannot wrap bound methods, this
module uses module-level callback functions that dispatch through a
module-level singleton reference.
"""

from __future__ import annotations

import ctypes
import struct
import threading
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

# Module-level singleton: set by PCMCapture, used by C callbacks
_capture_instance: Optional["PCMCapture"] = None
_capture_lock = threading.Lock()


def _play_cb(data_ptr, samples_ptr, count, pts):
    inst = _get_inst()
    if inst:
        inst._play_cb(samples_ptr, count, pts)


def _pause_cb(data_ptr, pts):
    inst = _get_inst()
    if inst:
        inst._pause_cb(pts)


def _resume_cb(data_ptr, pts):
    inst = _get_inst()
    if inst:
        inst._resume_cb(pts)


def _flush_cb(data_ptr, pts):
    inst = _get_inst()
    if inst:
        inst._flush_cb(pts)


def _drain_cb(data_ptr):
    inst = _get_inst()
    if inst:
        inst._drain_cb()


def _get_inst():
    with _capture_lock:
        return _capture_instance


# Pre-created ctypes function pointers (using vlc's CFUNCTYPE types)
_CB_PLAY = vlc.AudioPlayCb(_play_cb)
_CB_PAUSE = vlc.AudioPauseCb(_pause_cb)
_CB_RESUME = vlc.AudioResumeCb(_resume_cb)
_CB_FLUSH = vlc.AudioFlushCb(_flush_cb)
_CB_DRAIN = vlc.AudioDrainCb(_drain_cb)


class PCMCapture:
    """Wraps VLC audio callbacks → ring buffer (+ optional sounddevice out)."""

    def __init__(self, max_samples: int = 32768) -> None:
        self._buffer: deque[float] = deque(maxlen=max_samples)
        self._lock = threading.Lock()
        self._running = False
        self._format_set = False
        self._sd_stream: sd.OutputStream | None = None if sd is None else None

    # ── Public API ────────────────────────────────────────────────────

    def attach_to_player(self, player) -> None:
        global _capture_instance
        with _capture_lock:
            _capture_instance = self

        player.audio_set_format(FORMAT, SAMPLE_RATE, CHANNELS)
        player.audio_set_callbacks(
            _CB_PLAY, _CB_PAUSE, _CB_RESUME, _CB_FLUSH, _CB_DRAIN,
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
        with self._lock:
            self._buffer.clear()

    def read_fft(self, n: int = 1024) -> np.ndarray | None:
        with self._lock:
            if len(self._buffer) < n:
                return None
            chunk = np.array([self._buffer.popleft() for _ in range(n)],
                             dtype=np.float64)
        return chunk

    # ── VLC callbacks ─────────────────────────────────────────────────

    def _play_cb(self, samples_ptr, count: int, pts: int) -> None:
        if not self._running or count <= 0:
            return
        try:
            raw = ctypes.string_at(samples_ptr, count * CHANNELS * SAMPLE_WIDTH)
            frame_count = count
            fmt = "<" if struct.pack("=h", 1)[0] == 1 else ">"
            fmt += f"{frame_count * CHANNELS}h"
            ints = struct.unpack(fmt, raw)
        except Exception:
            return

        mono = [(ints[i] + ints[i + 1]) / 65536.0
                for i in range(0, len(ints), CHANNELS)]

        with self._lock:
            self._buffer.extend(mono)

        if self._sd_stream and sd is not None:
            try:
                s = self._sd_stream
                if s is not None:
                    arr = np.frombuffer(raw, dtype=np.int16).reshape(-1, CHANNELS)
                    s.write(arr)
            except Exception:
                pass

    def _pause_cb(self, pts: int) -> None:
        if self._sd_stream and sd is not None:
            self._sd_stream.stop()

    def _resume_cb(self, pts: int) -> None:
        if self._sd_stream and sd is not None and not self._sd_stream.active:
            self._sd_stream.start()

    def _flush_cb(self, pts: int) -> None:
        with self._lock:
            self._buffer.clear()

    def _drain_cb(self) -> None:
        pass
