# coding:utf-8
"""
qt_player_engine.py — QMediaPlayer-based audio engine (no VLC dependency).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from nocturne.data.db import get_db_path
from nocturne.core.pcm_capture import PCMCapture


class QtPlayerEngine:
    """Audio playback via QMediaPlayer + QAudioOutput (Qt built-in)."""

    _STATE_FILE = "playback_state.json"

    # Equalizer compatibility shims — not used by Qt backend
    _instance = None
    _player_vlc = None

    def __init__(self) -> None:
        self._media_player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._media_player.setAudioOutput(self._audio_output)
        self._pcm = PCMCapture()

        self._playlist_paths: list[str] = []
        self._current_index = -1
        self._repeat_mode = "off"
        self._shuffle = False
        self._original_indices: list[int] = []
        self._shuffled_indices: list[int] = []

    # ── Playback control ──────────────────────────────────────────────

    def play(self) -> None:
        self._pcm.start()
        self._media_player.play()

    def pause(self) -> None:
        self._pcm.stop()
        self._media_player.pause()

    def stop(self) -> None:
        self._pcm.stop()
        self._media_player.stop()

    def toggle_play(self) -> None:
        if self._media_player.playbackState() == QMediaPlayer.PlayingState:
            self.pause()
        else:
            self.play()

    def next(self) -> None:
        if self._current_index < len(self._playlist_paths) - 1:
            self._current_index += 1
            self._load_current()

    def previous(self) -> None:
        if self._current_index > 0:
            self._current_index -= 1
            self._load_current()

    def seek(self, ms: int) -> None:
        self._media_player.setPosition(ms)

    @property
    def is_playing(self) -> bool:
        return self._media_player.playbackState() == QMediaPlayer.PlayingState

    @property
    def position_ms(self) -> int:
        return self._media_player.position()

    @property
    def duration_ms(self) -> int:
        return self._media_player.duration()

    @property
    def volume(self) -> int:
        return int(self._audio_output.volume() * 100)

    @volume.setter
    def volume(self, val: int) -> None:
        self._audio_output.setVolume(max(0, min(100, val)) / 100)

    @property
    def current_media_path(self) -> str | None:
        src = self._media_player.source()
        if src.scheme() == "file":
            return src.toLocalFile()
        mrl = src.toString()
        return mrl if mrl else None

    # ── Repeat / shuffle ──────────────────────────────────────────────

    @property
    def repeat_mode(self) -> str:
        return self._repeat_mode

    def cycle_repeat(self) -> str:
        modes = ["off", "one", "all"]
        idx = (modes.index(self._repeat_mode) + 1) % len(modes)
        self._repeat_mode = modes[idx]
        return self._repeat_mode

    @property
    def shuffle(self) -> bool:
        return self._shuffle

    def toggle_shuffle(self) -> bool:
        self._shuffle = not self._shuffle
        if self._shuffle:
            import random
            self._shuffled_indices = list(range(len(self._playlist_paths)))
            random.shuffle(self._shuffled_indices)
        return self._shuffle

    # ── Playlist management ───────────────────────────────────────────

    def load_playlist(self, paths: list[str], start_index: int = 0) -> None:
        self._playlist_paths = list(paths)
        self._current_index = start_index
        self._load_current()
        self.play()

    def load_single(self, path: str) -> None:
        self.load_playlist([path], 0)

    def _load_current(self) -> None:
        if 0 <= self._current_index < len(self._playlist_paths):
            self._media_player.setSource(
                QUrl.fromLocalFile(self._playlist_paths[self._current_index])
            )

    # ── PCM / FFT bridge ──────────────────────────────────────────────

    def pcm_data(self, n_samples: int = 1024) -> np.ndarray | None:
        return self._pcm.read_fft(n_samples)

    # ── Playback state persistence ────────────────────────────────────

    def save_state(self) -> None:
        state = {
            "path": self.current_media_path,
            "position_ms": self.position_ms,
            "volume": self.volume,
            "timestamp": time.time(),
        }
        state_path = Path(get_db_path()).parent / self._STATE_FILE
        try:
            with open(state_path, "w") as f:
                json.dump(state, f)
        except OSError:
            pass

    def load_state(self) -> dict | None:
        state_path = Path(get_db_path()).parent / self._STATE_FILE
        if not state_path.exists():
            return None
        try:
            with open(state_path) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    def cleanup(self) -> None:
        self._pcm.stop()
        self._media_player.stop()
