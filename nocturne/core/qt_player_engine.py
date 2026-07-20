# coding:utf-8
"""
qt_player_engine.py — QMediaPlayer-based audio engine (no VLC dependency).
"""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from nocturne.core.base_player_engine import BasePlayerEngine


class QtPlayerEngine(BasePlayerEngine):
    """Audio playback via QMediaPlayer + QAudioOutput (Qt built-in)."""

    # Equalizer compatibility shims — not used by Qt backend
    _instance = None
    _player_vlc = None

    def __init__(self) -> None:
        super().__init__()
        self._media_player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._media_player.setAudioOutput(self._audio_output)
        self._current_index = -1

        self._media_player.mediaStatusChanged.connect(self._on_media_status)

    def _on_media_status(self, status) -> None:
        if status == QMediaPlayer.EndOfMedia and self._on_end:
            self._on_end()

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

    def cleanup(self) -> None:
        self._pcm.stop()
        self._media_player.stop()
