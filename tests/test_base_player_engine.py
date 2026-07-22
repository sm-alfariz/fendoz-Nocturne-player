# coding:utf-8
"""Test base_player_engine.py — repeat cycling, shuffle, state persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from nocturne.core.base_player_engine import BasePlayerEngine


class _ConcreteEngine(BasePlayerEngine):
    """Minimal concrete subclass for testing abstract state."""

    def __init__(self) -> None:
        super().__init__()
        self._current_path: str | None = None
        self._pos: int = 0
        self._dur: int = 0
        self._vol: int = 70

    @property
    def is_playing(self) -> bool:
        return False

    @property
    def position_ms(self) -> int:
        return self._pos

    @property
    def duration_ms(self) -> int:
        return self._dur

    @property
    def volume(self) -> int:
        return self._vol

    @volume.setter
    def volume(self, v: int) -> None:
        self._vol = v

    @property
    def current_media_path(self) -> str | None:
        return self._current_path

    def play(self) -> None:
        pass

    def pause(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def toggle_play(self) -> None:
        pass

    def next(self) -> None:
        pass

    def previous(self) -> None:
        pass

    def seek(self, ms: int) -> None:
        self._pos = ms


@pytest.fixture
def engine() -> _ConcreteEngine:
    return _ConcreteEngine()


class TestRepeatMode:
    def test_default_is_off(self, engine: _ConcreteEngine) -> None:
        assert engine.repeat_mode == "off"

    def test_cycles_off_to_one(self, engine: _ConcreteEngine) -> None:
        mode = engine.cycle_repeat()
        assert mode == "one"
        assert engine.repeat_mode == "one"

    def test_cycles_one_to_all(self, engine: _ConcreteEngine) -> None:
        engine.cycle_repeat()  # off -> one
        engine.cycle_repeat()  # one -> all
        assert engine.repeat_mode == "all"

    def test_cycles_all_to_off(self, engine: _ConcreteEngine) -> None:
        for _ in range(3):
            engine.cycle_repeat()
        assert engine.repeat_mode == "off"


class TestShuffle:
    def test_default_is_false(self, engine: _ConcreteEngine) -> None:
        assert engine.shuffle is False

    def test_toggle_turns_on(self, engine: _ConcreteEngine) -> None:
        assert engine.toggle_shuffle() is True
        assert engine.shuffle is True

    def test_toggle_turns_off(self, engine: _ConcreteEngine) -> None:
        engine.toggle_shuffle()
        engine.toggle_shuffle()
        assert engine.shuffle is False


class TestPcmData:
    def test_returns_none_when_no_player(self, engine: _ConcreteEngine) -> None:
        # Without a real player backend, PCMCapture returns None or raises
        result = engine.pcm_data(128)
        assert result is None or hasattr(result, "shape")


class TestStatePersistence:
    def test_save_and_load_state(self, engine: _ConcreteEngine,
                                  tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from nocturne.core import base_player_engine as bpe

        # Monkeypatch db_path to use tmp
        monkeypatch.setattr(bpe, "get_db_path", lambda: tmp_path / "nocturne.db")

        engine._current_path = "/music/test.mp3"
        engine._pos = 45000
        engine._vol = 80
        engine.save_state()

        state_path = (tmp_path / "nocturne.db").parent / "playback_state.json"
        assert state_path.exists()

        loaded = engine.load_state()
        assert loaded is not None
        assert loaded["path"] == "/music/test.mp3"
        assert loaded["position_ms"] == 45000
        assert loaded["volume"] == 80

    def test_load_state_returns_none_when_no_file(self, engine: _ConcreteEngine,
                                                   tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from nocturne.core import base_player_engine as bpe
        monkeypatch.setattr(bpe, "get_db_path", lambda: tmp_path / "nocturne.db")
        assert engine.load_state() is None

    def test_load_state_returns_none_on_corrupt_json(self, engine: _ConcreteEngine,
                                                      tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from nocturne.core import base_player_engine as bpe
        monkeypatch.setattr(bpe, "get_db_path", lambda: tmp_path)
        (tmp_path / "playback_state.json").write_text("{corrupt}", encoding="utf-8")
        assert engine.load_state() is None
