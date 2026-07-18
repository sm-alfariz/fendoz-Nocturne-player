# coding:utf-8
"""
player_bar.py — Bottom control bar: Now Playing, Transport, Volume + EQ.

Matches mockup-nocturne.html: 3-column grid, EQ toggle badge, volume slider,
shuffle/prev/play/next/repeat with play button gradient.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPoint, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPixmap, QPolygon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import FluentIcon as FIF

from nocturne.core.player_engine import PlayerEngine
from nocturne.ui.theme.tokens import Color, Fonts


class _IconButton(QPushButton):
    """Flat icon button with hover effect."""

    def __init__(self, icon, size=36, parent=None):
        super().__init__(parent)
        self._normal_icon = icon
        self.setFixedSize(size, size)
        self.setFlat(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;color:{Color.TEXT_DIM};}}"
            f"QPushButton:hover{{color:{Color.ACCENT};}}"
        )
        self.setIcon(icon)


class _PlayButton(QPushButton):
    """Play button with gradient circle (mockup style)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(42, 42)
        self.setCursor(Qt.PointingHandCursor)
        self._playing = False

    def set_playing(self, playing: bool) -> None:
        self._playing = playing
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        r = self.rect()

        # Gradient circle
        grad = QLinearGradient(0, 0, r.width(), r.height())
        grad.setColorAt(0, QColor(Color.PRIMARY))
        grad.setColorAt(1, QColor(Color.ACCENT))
        painter.setBrush(grad)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(r.adjusted(1, 1, -1, -1))

        # Shadow
        shadow = QColor(79, 195, 247, 140)
        painter.setBrush(Qt.NoBrush)
        pen = QPen(shadow, 4)
        painter.setPen(pen)
        painter.drawEllipse(r.adjusted(2, 2, -2, -2))

        # Icon (play / pause triangle)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#0B1220"))
        cx, cy = r.center().x(), r.center().y()
        if self._playing:
            # Pause bars
            painter.drawRect(cx - 7, cy - 8, 4, 16)
            painter.drawRect(cx + 3, cy - 8, 4, 16)
        else:
            # Play triangle
            poly = QPolygon()
            poly << QPoint(cx - 5, cy - 8)
            poly << QPoint(cx - 5, cy + 8)
            poly << QPoint(cx + 7, cy)
            painter.drawPolygon(poly)


class PlayerBar(QWidget):
    """Bottom dock — 3-column grid: now-playing | transport | right-controls."""

    play_toggled = Signal()
    next_requested = Signal()
    prev_requested = Signal()
    seek_requested = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(72)
        self.setStyleSheet(
            f"background:rgba(10,15,30,0.85);"
            f"border-top:1px solid {Color.BORDER};"
        )
        self._engine: PlayerEngine | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(0)

        # ── Left: Now Playing ─────────────────────────────────────────
        now = QHBoxLayout()
        now.setSpacing(12)
        self.artwork_mini = QLabel()
        self.artwork_mini.setFixedSize(44, 44)
        self.artwork_mini.setStyleSheet(
            f"background:radial-gradient(circle at 35% 30%, #2E4A7D, #101B33 70%);"
            f"border:1px solid {Color.BORDER}; border-radius:11px;"
        )
        now.addWidget(self.artwork_mini)

        txt = QVBoxLayout()
        txt.setSpacing(2)
        self.track_title = QLabel("No track")
        self.track_title.setStyleSheet(
            f"color:{Color.TEXT_PRIMARY};font-weight:600;font-size:12.5px;"
        )
        self.track_artist = QLabel("")
        self.track_artist.setStyleSheet(f"color:{Color.TEXT_DIM};font-size:11px;")
        txt.addWidget(self.track_title)
        txt.addWidget(self.track_artist)
        now.addLayout(txt)
        layout.addLayout(now, 1)

        # ── Center: Transport + Progress ──────────────────────────────
        ctr = QVBoxLayout()
        ctr.setSpacing(6)
        ctr.setAlignment(Qt.AlignCenter)

        # Buttons row
        btns = QHBoxLayout()
        btns.setSpacing(20)
        btns.setAlignment(Qt.AlignCenter)

        self.shuffle_btn = _IconButton(FIF.ARROW_DOWN.icon(), 28)
        self.shuffle_btn.setCheckable(True)
        self.shuffle_btn.clicked.connect(self._on_shuffle)
        btns.addWidget(self.shuffle_btn)

        self.prev_btn = _IconButton(FIF.SKIP_BACK.icon())
        self.prev_btn.clicked.connect(self.prev_requested.emit)
        btns.addWidget(self.prev_btn)

        self.play_btn = _PlayButton()
        self.play_btn.clicked.connect(self._on_play)
        btns.addWidget(self.play_btn)

        self.next_btn = _IconButton(FIF.SKIP_FORWARD.icon())
        self.next_btn.clicked.connect(self.next_requested.emit)
        btns.addWidget(self.next_btn)

        self.repeat_btn = _IconButton(FIF.SYNC.icon(), 28)
        self.repeat_btn.clicked.connect(self._on_repeat)
        btns.addWidget(self.repeat_btn)
        ctr.addLayout(btns)

        # Progress row
        prog = QHBoxLayout()
        prog.setSpacing(10)
        self.time_current = QLabel("0:00")
        self.time_current.setStyleSheet(
            f"color:{Color.TEXT_DIM};font-size:10.5px;font-family:'{Fonts.MONO}';"
        )
        self.time_current.setFixedWidth(34)
        self.time_total = QLabel("0:00")
        self.time_total.setStyleSheet(
            f"color:{Color.TEXT_DIM};font-size:10.5px;font-family:'{Fonts.MONO}';"
        )
        self.time_total.setFixedWidth(34)
        self.time_total.setAlignment(Qt.AlignRight)

        self.progress_bar = QSlider(Qt.Horizontal)
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.sliderMoved.connect(self._on_seek)
        self.progress_bar.setStyleSheet(
            f"QSlider::groove:horizontal{{height:4px;border-radius:4px;background:{Color.CARD};}}"
            f"QSlider::handle:horizontal{{width:11px;height:11px;margin:-4px 0;border-radius:6px;"
            f"background:#fff;box-shadow:0 0 8px {Color.ACCENT};}}"
            f"QSlider::sub-page:horizontal{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {Color.PRIMARY},stop:1 {Color.ACCENT});border-radius:4px;}}"
        )

        prog.addWidget(self.time_current)
        prog.addWidget(self.progress_bar, 1)
        prog.addWidget(self.time_total)
        ctr.addLayout(prog)
        layout.addLayout(ctr, 2)

        # ── Right: EQ Toggle + Volume ─────────────────────────────────
        right = QHBoxLayout()
        right.setSpacing(16)
        right.setAlignment(Qt.AlignRight)

        # EQ badge
        self.eq_label = QLabel("EQ: Flat")
        self.eq_label.setStyleSheet(
            f"color:{Color.ACCENT};font-size:11px;font-family:'{Fonts.MONO}';"
            f"background:rgba(79,195,247,0.08);border:1px solid {Color.BORDER};"
            f"padding:6px 10px;border-radius:9px;"
        )
        right.addWidget(self.eq_label)

        # Volume icon
        self.vol_icon = QLabel()
        self.vol_icon.setPixmap(FIF.VOLUME.icon().pixmap(15, 15))
        right.addWidget(self.vol_icon)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 200)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self._on_volume)
        self.volume_slider.setStyleSheet(
            f"QSlider::groove:horizontal{{height:4px;border-radius:4px;background:{Color.CARD};}}"
            f"QSlider::handle:horizontal{{width:0px;}}"
            f"QSlider::sub-page:horizontal{{background:{Color.ACCENT};border-radius:4px;}}"
        )
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
            self.artwork_mini.setPixmap(
                artwork.scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            self.artwork_mini.clear()

    def set_playing(self, playing: bool) -> None:
        self.play_btn.set_playing(playing)

    def set_progress(self, ms: int) -> None:
        if not self._engine:
            
            return
        total = self._engine.duration_ms
        if total > 0:
            self.progress_bar.setValue(int(ms / total * 1000))
        self.time_current.setText(self._fmt_time(ms))
        self.time_total.setText(self._fmt_time(total))

    def set_eq_preset(self, name: str) -> None:
        self.eq_label.setText(f"EQ: {name}")

    # ── Internals ─────────────────────────────────────────────────────

    def _on_play(self) -> None:
        if self._engine:
            self._engine.toggle_play()
            playing = self._engine.is_playing
            self.set_playing(playing)
            # MainWindow handles AudioWorker start/stop via this signal
            from nocturne.common.signal_bus import signalBus
            signalBus.play_toggled.emit(playing)

    def _on_seek(self, value: int) -> None:
        if self._engine and self._engine.duration_ms > 0:
            ms = int(value / 1000 * self._engine.duration_ms)
            self._engine.seek(ms)
            self.seek_requested.emit(ms)

    def _on_volume(self, val: int) -> None:
        if self._engine:
            self._engine.volume = val

    def _on_shuffle(self) -> None:
        if self._engine:
            enabled = self._engine.toggle_shuffle()
            self.shuffle_btn.setChecked(enabled)

    def _on_repeat(self) -> None:
        if self._engine:
            mode = self._engine.cycle_repeat()
            icons = {"off": FIF.SYNC.icon(), "one": FIF.SYNC.icon(), "all": FIF.SYNC.icon()}
            self.repeat_btn.setIcon(icons.get(mode, FIF.SYNC.icon()))
            # Visual indicator: accent when active
            accent = "#4FC3F7" if mode != "off" else "inherit"
            self.repeat_btn.setStyleSheet(
                f"QPushButton{{background:transparent;border:none;color:{accent};}}"
                f"QPushButton:hover{{color:#4FC3F7;}}"
            )

    def _poll_position(self) -> None:
        if self._engine and self._engine.is_playing:
            self.set_progress(self._engine.position_ms)

    @staticmethod
    def _fmt_time(ms: int) -> str:
        if ms <= 0:
            return "0:00"
        m, s = divmod(ms // 1000, 60)
        return f"{m}:{s:02d}"
