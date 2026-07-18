# coding:utf-8
"""
player_engine.py — libVLC wrapper for audio playback & PCM extraction.

Single audio engine — no fallback to QMediaPlayer (05-system-architecture.md).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import vlc

from nocturne.data.db import get_db_path
from nocturne.core.pcm_capture import PCMCapture


class PlayerEngine:
    """Manages libVLC instance, media playback, and PCM extraction for FFT."""

    _STATE_FILE = "playback_state.json"

    def __init__(self) -> None:
        import platform
        vlc_args = []
        if platform.system() == "Linux":
            vlc_args = ["--no-xlib", "--aout=auto", "--quiet"]
        self._instance = vlc.Instance(*vlc_args)
        self._player = self._instance.media_player_new()
        self._list_player = self._instance.media_list_player_new()
        self._list = self._instance.media_list_new()

        self._list_player.set_media_player(self._player)
        self._list_player.set_media_list(self._list)

        # Callbacks
        self._on_track_change = None

        # PCM capture for FFT visualizer
        self._pcm = PCMCapture()

        # Repeat / shuffle state
        self._repeat_mode = "off"  # "off" | "one" | "all"
        self._shuffle = False
        self._original_indices: list[int] = []
        self._shuffled_indices: list[int] = []
        self._playlist: list[str] = []

    # ── Playback control ──────────────────────────────────────────────

    def play(self) -> None:
        self._pcm.start()
        self._list_player.play()

    def pause(self) -> None:
        self._pcm.stop()
        self._list_player.pause()

    def stop(self) -> None:
        self._pcm.stop()
        self._list_player.stop()

    def toggle_play(self) -> None:
        if self._player.is_playing():
            self.pause()
        else:
            self.play()

    def next(self) -> None:
        self._list_player.next()

    def previous(self) -> None:
        self._list_player.previous()

    def seek(self, ms: int) -> None:
        self._player.set_time(ms)

    @property
    def is_playing(self) -> bool:
        return self._player.is_playing()

    @property
    def position_ms(self) -> int:
        return self._player.get_time()

    @property
    def duration_ms(self) -> int:
        return self._player.get_length()

    @property
    def volume(self) -> int:
        return self._player.audio_get_volume()

    @volume.setter
    def volume(self, val: int) -> None:
        self._player.audio_set_volume(max(0, min(200, val)))

    # ── Repeat / shuffle ──────────────────────────────────────────────

    @property
    def repeat_mode(self) -> str:
        return self._repeat_mode

    def cycle_repeat(self) -> str:
        modes = ["off", "one", "all"]
        idx = (modes.index(self._repeat_mode) + 1) % len(modes)
        self._repeat_mode = modes[idx]
        self._apply_repeat()
        return self._repeat_mode

    def _apply_repeat(self) -> None:
        if self._repeat_mode == "one":
            self._list_player.set_playback_mode(vlc.PlaybackMode.loop)
        elif self._repeat_mode == "all":
            self._list_player.set_playback_mode(vlc.PlaybackMode.loop)
        else:
            self._list_player.set_playback_mode(vlc.PlaybackMode.default)

    @property
    def shuffle(self) -> bool:
        return self._shuffle

    def toggle_shuffle(self) -> bool:
        self._shuffle = not self._shuffle
        if self._shuffle:
            import random
            self._shuffled_indices = list(range(len(self._playlist)))
            random.shuffle(self._shuffled_indices)
        return self._shuffle

    # ── Playlist management ───────────────────────────────────────────

    def load_playlist(self, paths: list[str], start_index: int = 0) -> None:
        """Load a list of file paths into the media list and start playback."""
        self._list = self._instance.media_list_new()
        for p in paths:
            self._list.add_media(self._instance.media_new(p))
        self._playlist = paths
        self._list_player.set_media_list(self._list)
        self._pcm.start()
        self._list_player.play_item_at_index(start_index)

    def load_single(self, path: str) -> None:
        """Load and play a single file via list player (so play/pause/stop route correctly)."""
        self.load_playlist([path], start_index=0)

    # ── PCM / FFT bridge ──────────────────────────────────────────────

    def pcm_data(self, n_samples: int = 1024) -> np.ndarray | None:
        """Return PCM samples for FFT processing. Called from AudioWorker.

        ponytail: Real PCM capture via PulseAudio monitor source — currently
        returns None so visualizer shows flat bars. Add in next iteration.
        """
        return self._pcm.read_fft(n_samples)

    # ── Track info ────────────────────────────────────────────────────

    @property
    def current_media_path(self) -> str | None:
        from urllib.parse import unquote
        media = self._player.get_media()
        if media:
            mrl = media.get_mrl()
            if mrl and mrl.startswith("file://"):
                return unquote(mrl[len("file://"):])
            return mrl
        return None

    # ── Playback state persistence ────────────────────────────────────

    def save_state(self) -> None:
        """Save current playback position for resume (FR-1.5)."""
        state = {
            "path": self.current_media_path,
            "position_ms": self.position_ms,
            "volume": self.volume,
            "timestamp": time.time(),
        }
        state_path = Path(get_db_path()).parent / self._STATE_FILE
        try:
            for p in [state_path]:
                with open(p, "w") as f:
                    json.dump(state, f)
        except OSError:
            pass

    def load_state(self) -> dict | None:
        """Load saved playback state (returns None if no saved state)."""
        state_path = Path(get_db_path()).parent / self._STATE_FILE
        if not state_path.exists():
            return None
        try:
            with open(state_path) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    def cleanup(self) -> None:
        """Release VLC resources."""
        self._player.stop()
        self._instance.release()
