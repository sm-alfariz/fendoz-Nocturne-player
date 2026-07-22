# coding:utf-8
"""
equalizer.py — 10-band equalizer via libVLC native equalizer API.

FR-3.1–3.4: ±12dB per band, presets, real-time without audio pop.
"""

from __future__ import annotations

import json
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import vlc

from nocturne.data.db import get_connection


# ISO standard 10-band frequencies: 31, 62, 125, 250, 500, 1k, 2k, 4k, 8k, 16k Hz
BAND_COUNT = 10
BAND_LABELS = ["31", "62", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"]

# Built-in presets (values in dB)
BUILTIN_PRESETS = {
    "Flat": [0.0] * 10,
    "Bass Boost": [5.0, 4.0, 2.0, 0.0, -0.5, -1.0, -1.5, -2.0, -1.5, -1.0],
    "Treble Boost": [-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0],
    "Vocal": [-1.0, -0.5, 0.0, 1.0, 2.0, 2.5, 2.0, 1.0, 1.0, 0.5],
    "Rock": [4.0, 3.0, 2.0, 1.0, 0.0, -0.5, 1.0, 2.0, 3.0, 3.5],
    "Jazz": [3.0, 2.5, 2.0, 1.5, 1.0, 0.5, 1.0, 1.5, 2.0, 2.5],
}


class Equalizer:
    """Wraps libVLC equalizer API for 10-band control.

    When created without a VLC instance (player_instance=None), all methods
    become no-ops — useful when the Qt backend is active.
    """

    def __init__(self, player_instance: vlc.Instance | None = None) -> None:
        self._instance = player_instance
        self._active = player_instance is not None
        self._eq = None
        self._player = None  # stored by attach_to_player for re-attachment
        self._current_preset = "Flat"

    @property
    def current_preset(self) -> str:
        return self._current_preset

    def apply_preset(self, name: str, custom_values: Optional[list[float]] = None) -> None:
        """Apply a preset by name, or custom values."""
        if not self._active:
            return
        if name in BUILTIN_PRESETS:
            values = BUILTIN_PRESETS[name]
        elif name in self.all_presets():
            values = self.all_presets()[name]
        elif custom_values is not None and len(custom_values) == BAND_COUNT:
            values = custom_values
            name = "Custom"
        else:
            return

        import vlc
        self._eq = vlc.AudioEqualizer()

        for band_idx in range(BAND_COUNT):
            self._eq.set_amp_at_index(values[band_idx], band_idx)

        self._current_preset = name

        # Re-attach to player so the new EQ takes effect immediately
        if self._player is not None:
            self._player.set_equalizer(self._eq)

    def set_band(self, band_index: int, db_value: float) -> None:
        """Adjust a single band in real-time."""
        if not self._active or not self._eq:
            return
        self._eq.set_amp_at_index(max(-12.0, min(12.0, db_value)), band_index)
        # Re-attach so the change takes effect immediately
        if self._player is not None:
            self._player.set_equalizer(self._eq)

    def attach_to_player(self, player) -> None:
        """Attach equalizer to a libVLC media player."""
        self._player = player
        if not self._active or not self._eq:
            return
        player.set_equalizer(self._eq)

    # ── Preset persistence ────────────────────────────────────────────

    def save_custom_preset(self, name: str, values: list[float]) -> int:
        """Save a custom EQ preset to the database."""
        conn = get_connection()
        cursor = conn.execute(
            "INSERT INTO eq_presets (name, band_values_json, is_custom) VALUES (?, ?, 1)",
            (name, json.dumps(values)),
        )
        conn.commit()
        conn.close()
        return cursor.lastrowid

    def load_custom_presets(self) -> dict[str, list[float]]:
        """Load all custom EQ presets from DB."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT name, band_values_json FROM eq_presets WHERE is_custom = 1"
        ).fetchall()
        conn.close()
        presets = {}
        for r in rows:
            try:
                presets[r[0]] = json.loads(r[1])
            except (json.JSONDecodeError, TypeError):
                pass
        return presets

    @classmethod
    def all_presets(cls, include_custom: Optional[dict[str, list[float]]] = None) -> dict[str, list[float]]:
        """Return built-in presets merged with custom ones from DB."""
        presets = dict(BUILTIN_PRESETS)
        custom = include_custom if include_custom is not None else cls._load_custom_from_db()
        if custom:
            presets.update(custom)
        return presets

    @classmethod
    def _load_custom_from_db(cls) -> dict[str, list[float]]:
        """Load custom presets from DB (silent, no-op on failure)."""
        try:
            conn = get_connection()
            rows = conn.execute(
                "SELECT name, band_values_json FROM eq_presets WHERE is_custom = 1"
            ).fetchall()
            conn.close()
            result = {}
            for r in rows:
                try:
                    result[r[0]] = json.loads(r[1])
                except (json.JSONDecodeError, TypeError):
                    pass
            return result
        except Exception:
            return {}

    # ── Active preset persistence ─────────────────────────────────────

    def save_active_preset(self) -> None:
        """Persist the current active preset name to app_settings."""
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES ('eq_active_preset', ?)",
            (self._current_preset,),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def load_active_preset() -> str:
        """Load the persisted active preset name, defaulting to 'Flat'."""
        try:
            conn = get_connection()
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = 'eq_active_preset'"
            ).fetchone()
            conn.close()
            return row[0] if row else "Flat"
        except Exception:
            return "Flat"
