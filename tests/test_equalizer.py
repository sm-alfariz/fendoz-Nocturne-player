# coding:utf-8
"""Test equalizer.py — preset management, band setting, persistence."""

from __future__ import annotations

from nocturne.core.equalizer import (
    BUILTIN_PRESETS,
    Equalizer,
)


class TestEqualizer:
    def test_noop_when_no_instance(self) -> None:
        """Equalizer with player_instance=None is a no-op."""
        eq = Equalizer(player_instance=None)
        eq.apply_preset("Bass Boost")
        assert eq.current_preset == "Flat"  # never changed because _active=False

    def test_current_preset_default(self) -> None:
        eq = Equalizer(None)
        assert eq.current_preset == "Flat"

    def test_all_presets_returns_builtins(self) -> None:
        presets = Equalizer.all_presets()
        assert "Flat" in presets
        assert "Bass Boost" in presets
        assert "Rock" in presets
        assert len(presets) == len(BUILTIN_PRESETS)

    def test_all_presets_with_custom(self) -> None:
        custom = {"My Custom": [1.0] * 10}
        presets = Equalizer.all_presets(include_custom=custom)
        assert "My Custom" in presets
        assert "Flat" in presets

    def test_all_presets_does_not_mutate_builtins(self) -> None:
        custom = {"Flat": [5.0] * 10}
        presets = Equalizer.all_presets(include_custom=custom)
        assert presets["Flat"] == [5.0] * 10
        # original BUILTIN_PRESETS unchanged
        assert BUILTIN_PRESETS["Flat"] == [0.0] * 10

    def test_save_and_load_custom_preset(self, tmp_path, monkeypatch) -> None:
        """Use a temp DB for EQ persistence."""
        import sqlite3
        from nocturne.data.db import init_db

        db_path = tmp_path / "eq.db"

        def _get_conn():
            c = init_db(db_path)
            c.row_factory = sqlite3.Row
            return c

        monkeypatch.setattr("nocturne.core.equalizer.get_connection", _get_conn)

        eq = Equalizer(None)
        eq.save_custom_preset("My Preset", [1.0, 2.0, 3.0, 0, 0, 0, 0, 0, 0, 0])
        loaded = eq.load_custom_presets()
        assert "My Preset" in loaded
        assert loaded["My Preset"] == [1.0, 2.0, 3.0, 0, 0, 0, 0, 0, 0, 0]

    def test_load_custom_presets_empty_when_none(self, tmp_path, monkeypatch) -> None:
        import sqlite3
        from nocturne.data.db import init_db

        db_path = tmp_path / "eq_empty.db"

        def _get_conn():
            c = init_db(db_path)
            c.row_factory = sqlite3.Row
            return c

        monkeypatch.setattr("nocturne.core.equalizer.get_connection", _get_conn)

        eq = Equalizer(None)
        assert eq.load_custom_presets() == {}
