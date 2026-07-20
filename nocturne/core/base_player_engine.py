# coding:utf-8
"""
base_player_engine.py — Shared state/persistence for PlayerEngine variants.

 ponytail: Could evolve to ABC with abstract methods if third backend added.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from nocturne.data.db import get_db_path
from nocturne.core.pcm_capture import PCMCapture


class BasePlayerEngine:
    """Shared state, repeat/shuffle logic, persistence, and PCM bridge."""

    _STATE_FILE = "playback_state.json"

    def __init__(self) -> None:
        self._pcm = PCMCapture()
        self._repeat_mode = "off"
        self._shuffle = False
        self._shuffled_indices: list[int] = []
        self._playlist_paths: list[str] = []
        self._on_end = None

    # ── End callback ────────────────────────────────────────────────

    def set_on_end(self, callback) -> None:
        self._on_end = callback

    # ── Repeat / shuffle ────────────────────────────────────────────

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
        """Override in subclass to apply repeat to backend."""
        pass

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

    # ── PCM / FFT bridge ────────────────────────────────────────────

    def pcm_data(self, n_samples: int = 1024) -> np.ndarray | None:
        return self._pcm.read_fft(n_samples)

    # ── Playback state persistence ──────────────────────────────────

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
