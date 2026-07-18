# coding:utf-8
"""
player_bar.py — Bottom control bar: Now Playing, Transport, Volume + EQ.

Central hub connecting PlayerEngine to UI.  All other modules read state
via Qt signals, not polling.  (09-screens-and-navigation.md)
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import CardWidget, ProgressBar, Slider

from nocturne.core.player_engine import PlayerEngine
from nocturne.ui.theme.tokens import Color


class PlayerBar(QWidget):
    """Bottom dock containing transport controls, progress, and volume."""

    play_toggled = Signal()
    next_requested = Signal()
    prev_requested = Signal()
    seek_requested = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(80)

        self._engine: PlayerEngine | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(16)

        # ── Left: Now Playing ─────────────────────────────────────────
        now_playing = QHBoxLayout()
        now_playing.setSpacing(12)

        self.artwork_mini = QLabel()
        self.artwork_mini.setFixedSize(48, 48)
        self.artwork_mini.setStyleSheet("background: #1E293B; border-radius: 8px;")
        now_playing.addWidget(self.artwork_mini)

        track_info = QVBoxLayout()
        track_info.setSpacing(2)
        self.track_title = QLabel("No track")
        self.track_title.setStyleSheet(f"color: {Color.TEXT_PRIMARY}; font-weight: 600; font-size: 13px;")
        self.track_artist = QLabel("")
        self.track_artist.setStyleSheet(f"color: {Color.TEXT_DIM}; font-size: 11px;")
        track_info.addWidget(self.track_title)
        track_info.addWidget(self.track_artist)
        now_playing.addLayout(track_info)

        layout.addLayout(now_playing, 1)

        # ── Center: Transport ─────────────────────────────────────────
        transport = QHBoxLayout()
        transport.setSpacing(8)
        transport.setAlignment(Qt.AlignCenter)

        self.prev_btn = QPushButton()
        self.prev_btn.setIcon(FIF.SKIP_BACK.icon())
        self.prev_btn.setFixedSize(32, 32)
        self.prev_btn.setFlat(True)
        self.prev_btn.clicked.connect(self.prev_requested.emit)
        transport.addWidget(self.prev_btn)

        self.play_btn = QPushButton()
        self.play_btn.setIcon(FIF.PLAY_SOLID.icon())
        self.play_btn.setFixedSize(40, 40)
        self.play_btn.setFlat(True)
        self.play_btn.clicked.connect(self._on_play)
        transport.addWidget(self.play_btn)

        self.next_btn = QPushButton()
        self.next_btn.setIcon(FIF.SKIP_FORWARD.icon())
        self.next_btn.setFixedSize(32, 32)
        self.next_btn.setFlat(True)
        self.next_btn.clicked.connect(self.next_requested.emit)
        transport.addWidget(self.next_btn)

        layout.addLayout(transport, 2)

        # ── Progress ──────────────────────────────────────────────────
        progress = QVBoxLayout()
        progress.setSpacing(2)

        progress_row = QHBoxLayout()
        self.time_current = QLabel("0:00")
        self.time_current.setStyleSheet(f"color: {Color.TEXT_DIM}; font-size: 11px; font-family: 'JetBrains Mono';")
        self.time_total = QLabel("0:00")
        self.time_total.setStyleSheet(f"color: {Color.TEXT_DIM}; font-size: 11px; font-family: 'JetBrains Mono';")

        self.progress_bar = QSlider(Qt.Horizontal)
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.sliderMoved.connect(self._on_seek)
        progress_row.addWidget(self.time_current)
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.time_total)
        progress.addLayout(progress_row)
        layout.addLayout(progress, 3)

        # ── Right: Volume with Shuffle/Repeat ────────────────────────
        right = QHBoxLayout()
        right.setSpacing(8)
        right.setAlignment(Qt.AlignRight)

        self.shuffle_btn = QPushButton()
        self.shuffle_btn.setIcon(FIF.ARROW_DOWN.icon())
        self.shuffle_btn.setFixedSize(28, 28)
        self.shuffle_btn.setFlat(True)
        self.shuffle_btn.setCheckable(True)
        transport.addWidget(self.shuffle_btn)

        self.repeat_btn = QPushButton()
        self.repeat_btn.setIcon(FIF.SYNC.icon())
        self.repeat_btn.setFixedSize(28, 28)
        self.repeat_btn.setFlat(True)
        transport.addWidget(self.repeat_btn)

        self.volume_icon = QLabel()
        self.volume_icon.setPixmap(FIF.VOLUME.icon().pixmap(16, 16))
        right.addWidget(self.volume_icon)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self._on_volume)
        right.addWidget(self.volume_slider)

        layout.addLayout(right, 1)

        # Progress update timer
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._poll_position)

    # ── Engine binding ────────────────────────────────────────────────

    def bind_engine(self, engine: PlayerEngine) -> None:
        self._engine = engine
        self.volume_slider.setValue(engine.volume)
        self._timer.start()

    # ── Public updates ────────────────────────────────────────────────

    def update_track_info(self, title: str, artist: str, artwork: QPixmap | None = None) -> None:
        self.track_title.setText(title or "No track")
        self.track_artist.setText(artist or "")
        if artwork:
            self.artwork_mini.setPixmap(artwork.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.artwork_mini.clear()
            self.artwork_mini.setStyleSheet("background: #1E293B; border-radius: 8px;")

    def set_playing(self, playing: bool) -> None:
        icon = FIF.PAUSE_BOLD.icon() if playing else FIF.PLAY_SOLID.icon()
        self.play_btn.setIcon(icon)

    def set_progress(self, ms: int) -> None:
        if not self._engine:
            return
        total = self._engine.duration_ms
        if total > 0:
            self.progress_bar.setValue(int(ms / total * 1000))
        self.time_current.setText(self._fmt_time(ms))
        self.time_total.setText(self._fmt_time(total))

    # ── Internals ─────────────────────────────────────────────────────

    def _on_play(self) -> None:
        if self._engine:
            self._engine.toggle_play()
            self.set_playing(self._engine.is_playing)

    def _on_seek(self, value: int) -> None:
        if self._engine and self._engine.duration_ms > 0:
            ms = int(value / 1000 * self._engine.duration_ms)
            self._engine.seek(ms)
            self.seek_requested.emit(ms)

    def _on_volume(self, val: int) -> None:
        if self._engine:
            self._engine.volume = val

    def _poll_position(self) -> None:
        if self._engine and self._engine.is_playing:
            self.set_progress(self._engine.position_ms)

    @staticmethod
    def _fmt_time(ms: int) -> str:
        if ms <= 0:
            return "0:00"
        total_s = ms // 1000
        m, s = divmod(total_s, 60)
        return f"{m}:{s:02d}"
