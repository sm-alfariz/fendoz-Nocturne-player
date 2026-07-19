# coding:utf-8
"""
player_bar.py — Bottom control bar using SimpleMediaPlayBar (QFluentWidgets).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets.multimedia.media_play_bar import (
    MediaPlayBarBase,
    MediaPlayBarButton,
    MediaPlayerBase,
)

from nocturne.core.player_engine import PlayerEngine
from nocturne.ui.theme.tokens import Color


class _PlayerEngineAdapter(MediaPlayerBase):
    """Wraps PlayerEngine (VLC) as MediaPlayerBase for SimpleMediaPlayBar.
    Signals are inherited from MediaPlayerBase.
    """

    def __init__(self, engine: PlayerEngine, parent=None) -> None:
        super().__init__(parent)
        self._engine = engine

        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def isPlaying(self) -> bool:
        return self._engine.is_playing

    def play(self) -> None:
        self._engine.play()

    def pause(self) -> None:
        self._engine.pause()

    def stop(self) -> None:
        self._engine.stop()

    def setPosition(self, position: int) -> None:
        self._engine.seek(position)

    def setVolume(self, volume: int) -> None:
        self._engine.volume = volume

    def volume(self) -> int:
        return self._engine.volume

    def position(self) -> int:
        return self._engine.position_ms

    def duration(self) -> int:
        return self._engine.duration_ms

    def setSource(self, media: QUrl) -> None:
        pass

    def source(self) -> QUrl:
        return QUrl()

    def mediaStatus(self) -> QMediaPlayer.MediaStatus:
        return (
            QMediaPlayer.LoadedMedia
            if self._engine.is_playing
            else QMediaPlayer.NoMedia
        )

    def playbackState(self) -> QMediaPlayer.PlaybackState:
        return (
            QMediaPlayer.PlayingState
            if self._engine.is_playing
            else QMediaPlayer.StoppedState
        )

    def setMuted(self, isMuted: bool) -> None:
        self._engine.volume = 0 if isMuted else 100

    def playbackRate(self) -> float:
        return 1.0

    def setPlaybackRate(self, rate: float) -> None:
        pass

    def videoOutput(self) -> QObject:
        return None

    def _poll(self) -> None:
        engine = self._engine
        if not engine:
            return
        self.positionChanged.emit(engine.position_ms)
        self.durationChanged.emit(engine.duration_ms)
        status = QMediaPlayer.LoadedMedia if engine.is_playing else QMediaPlayer.NoMedia
        self.mediaStatusChanged.emit(status)


class _CustomPlayBar(MediaPlayBarBase):
    """SimpleMediaPlayBar without internal MediaPlayer — we wire our engine manually."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.setContentsMargins(10, 4, 10, 4)
        self.hBoxLayout.setSpacing(6)
        self.hBoxLayout.addWidget(self.playButton, 0, Qt.AlignLeft)
        self.hBoxLayout.addWidget(self.progressSlider, 1)
        self.hBoxLayout.addWidget(self.volumeButton, 0)

        self.progressSlider.setFixedHeight(22)
        self.setFixedHeight(48)

        self.progressSlider.setThemeColor(Color.ACCENT, Color.ACCENT)
        self.playButton.setStyleSheet(
            f"TransparentToolButton{{background:transparent;border:none;color:{Color.TEXT_PRIMARY};}}"
            f"TransparentToolButton:hover{{color:{Color.ACCENT};}}"
        )
        self.volumeButton.setStyleSheet(
            f"TransparentToolButton{{background:transparent;border:none;color:{Color.TEXT_DIM};}}"
            f"TransparentToolButton:hover{{color:{Color.ACCENT};}}"
        )

    def paintEvent(self, e) -> None:
        """No background fill — PlayerBar handles the backdrop."""


class PlayerBar(QWidget):
    """Bottom dock — now-playing | SimpleMediaPlayBar | EQ badge."""

    play_toggled = Signal()
    next_requested = Signal()
    prev_requested = Signal()
    seek_requested = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(72)
        # self.setStyleSheet(
        #     f"background:rgba(10,15,30,0.75);border-top:1px solid {Color.BORDER};"
        # )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(0)

        # ── Left: Now Playing ─────────────────────────────────────────
        left = QHBoxLayout()
        left.setSpacing(10)

        self.artwork_mini = QLabel("🎵")
        self.artwork_mini.setFixedSize(44, 44)
        self.artwork_mini.setAlignment(Qt.AlignCenter)
        self.artwork_mini.setStyleSheet(
            f"background:radial-gradient(circle at 35% 30%, #2E4A7D, #101B33 70%);"
            f"border-radius:11px;font-size:20px;"
        )
        left.addWidget(self.artwork_mini)

        txt = QVBoxLayout()
        txt.setSpacing(4)
        self.track_title = QLabel("No track")
        self.track_title.setStyleSheet("color:#fff;font-weight:500;font-size:12px;bacgkground:transparent;")
        self.track_artist = QLabel("-")
        self.track_artist.setStyleSheet("color:rgba(148,163,184,0.8);font-size:11px;background:transparent;")
        txt.addWidget(self.track_title)
        txt.addWidget(self.track_artist)
        left.addLayout(txt)
        layout.addLayout(left, 1)

        # ── Center: SimpleMediaPlayBar ─────────────────────────────────
        self.bar = _CustomPlayBar(self)
        self._adapter: _PlayerEngineAdapter | None = None

        self._add_nav_buttons()

        layout.addWidget(self.bar, 2)

        # ── Right: EQ badge ────────────────────────────────────────────
        right = QHBoxLayout()
        right.setAlignment(Qt.AlignRight)
        right.setSpacing(12)

        self.eq_label = QLabel("EQ: Flat")
        self.eq_label.setStyleSheet(
            f"color:{Color.ACCENT};font-size:11px;"
            f"background:rgba(79,195,247,0.08);border:1px solid {Color.BORDER};"
            f"padding:6px 10px;border-radius:9px;"
        )
        right.addWidget(self.eq_label)
        layout.addLayout(right, 1)

    def _add_nav_buttons(self) -> None:
        qss = (
            f"MediaPlayBarButton{{background:transparent;border:none;color:{Color.TEXT_DIM};}}"
            f"MediaPlayBarButton:hover{{color:{Color.ACCENT};}}"
            f"MediaPlayBarButton:checked{{color:{Color.ACCENT};}}"
        )

        self.shuffle_btn = MediaPlayBarButton(self)
        self.shuffle_btn.setIcon(FIF.ARROW_DOWN.icon())
        self.shuffle_btn.setCheckable(True)
        self.shuffle_btn.clicked.connect(self._on_shuffle)
        self.shuffle_btn.setStyleSheet(qss)

        self.prev_btn = _NavButton(FIF.SKIP_BACK.icon())
        self.prev_btn.clicked.connect(self.prev_requested.emit)
        self.prev_btn.setStyleSheet(qss)

        self.next_btn = _NavButton(FIF.SKIP_FORWARD.icon())
        self.next_btn.clicked.connect(self.next_requested.emit)
        self.next_btn.setStyleSheet(qss)

        self.repeat_btn = MediaPlayBarButton(self)
        self.repeat_btn.setIcon(FIF.SYNC.icon())
        self.repeat_btn.clicked.connect(self._on_repeat)
        self.repeat_btn.setStyleSheet(qss)

        bar = self.bar
        idx = bar.hBoxLayout.indexOf(bar.progressSlider)
        for btn in (self.shuffle_btn, self.prev_btn, self.next_btn, self.repeat_btn):
            bar.hBoxLayout.insertWidget(idx, btn, 0, Qt.AlignLeft)

    # ── Engine binding ────────────────────────────────────────────────

    def bind_engine(self, engine: PlayerEngine) -> None:
        self._adapter = _PlayerEngineAdapter(engine, self)
        self.bar.setMediaPlayer(self._adapter)
        self._adapter.setVolume(engine.volume)

    # ── Public updates ────────────────────────────────────────────────

    def update_track_info(
        self, title: str, artist: str, artwork: QPixmap | None = None
    ) -> None:
        self.track_title.setText(title or "No track")
        self.track_artist.setText(artist or "-")
        if artwork:
            self.artwork_mini.setText("")
            self.artwork_mini.setPixmap(
                artwork.scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            self.artwork_mini.clear()
            self.artwork_mini.setText("🎵")

    def set_playing(self, playing: bool) -> None:
        self.bar.playButton.setPlay(playing)

    def set_volume(self, volume: int) -> None:
        if self._adapter:
            self._adapter.setVolume(volume)

    def set_eq_preset(self, name: str) -> None:
        self.eq_label.setText(f"EQ: {name}")

    # ── Internals ─────────────────────────────────────────────────────

    def _on_shuffle(self) -> None:
        if self._adapter:
            enabled = self._adapter._engine.toggle_shuffle()
            self.shuffle_btn.setChecked(enabled)

    def _on_repeat(self) -> None:
        if self._adapter:
            engine = self._adapter._engine
            mode = engine.cycle_repeat()
            icons = {
                "off": FIF.SYNC.icon(),
                "one": FIF.SYNC.icon(),
                "all": FIF.SYNC.icon(),
            }
            self.repeat_btn.setIcon(icons.get(mode, FIF.SYNC.icon()))
            accent = "#4FC3F7" if mode != "off" else "inherit"
            self.repeat_btn.setStyleSheet(
                f"MediaPlayBarButton{{background:transparent;border:none;color:{accent};}}"
                f"MediaPlayBarButton:hover{{color:#4FC3F7;}}"
            )


class _NavButton(MediaPlayBarButton):
    """Slightly larger nav button for prev/next."""

    def __init__(self, icon, parent=None) -> None:
        super().__init__(parent)
        self.setIcon(icon)
