# coding:utf-8
"""
miniplayer.py - Collapsible frameless miniplayer matching mockup design.
Compact bar + expandable body with animated visualizer, full controls, volume.
"""

from __future__ import annotations

import math
import random

import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget, QSlider,
)

from nocturne.core.player_engine import PlayerEngine
from nocturne.ui.theme.tokens import Color, FontWeights


def _fmt_ms(ms: int) -> str:
    if ms < 0:
        ms = 0
    total_s = ms // 1000
    m, s = divmod(total_s, 60)
    return f"{m}:{s:02d}"


COMPACT_H = 76
EXPANDED_H = 440
W = 360
RADIUS = 16


class _MarqueeLabel(QWidget):
    """Scrolling marquee when text overflows."""

    def __init__(self, text="", parent=None) -> None:
        super().__init__(parent)
        self._text = text
        self._offset = 0
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)

    def setText(self, text: str) -> None:
        self._text = text
        self._offset = 0
        self._timer.stop()
        self.update()
        fm = QFontMetrics(self.font())
        if fm.horizontalAdvance(text) > self.width():
            self._timer.start()

    def text(self) -> str:
        return self._text

    def _tick(self) -> None:
        fm = QFontMetrics(self.font())
        tw = fm.horizontalAdvance(self._text)
        if tw <= self.width():
            self._timer.stop()
            return
        self._offset -= 1
        gap_px = int(fm.horizontalAdvance(" ") * 3)
        if self._offset < -(tw + gap_px):
            self._offset = 0
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        fm = QFontMetrics(self.font())
        tw = fm.horizontalAdvance(self._text)
        if tw <= self.width():
            p.drawText(self.rect(), Qt.AlignVCenter | Qt.AlignLeft, self._text)
            return
        p.setClipRect(self.rect())
        y = self.rect().center().y() + fm.ascent() // 2
        gap_px = int(fm.horizontalAdvance(" ") * 3)
        p.drawText(self._offset, y, self._text)
        p.drawText(self._offset + tw + gap_px, y, self._text)
        p.end()


class _VisualizerBars(QWidget):
    """Animated visualizer bars driven by real PCM spectrum data."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._bar_heights = [random.uniform(0.15, 0.85) for _ in range(24)]
        self._spectrum: np.ndarray = np.zeros(0)
        self._smooth: np.ndarray = np.zeros(24)
        self._has_signal = False
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30fps like SpectrumBar
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_spectrum(self, data: np.ndarray) -> None:
        """Receive FFT magnitudes from AudioWorker."""
        self._spectrum = data
        self._has_signal = bool(np.any(data > 0.01))

    def _tick(self) -> None:
        n = len(self._bar_heights)
        if self._has_signal and len(self._spectrum) > 0:
            # Downsample spectrum to bar count
            step = len(self._spectrum) / n
            for i in range(n):
                idx = min(int(i * step), len(self._spectrum) - 1)
                target = max(0.06, min(0.95, abs(float(self._spectrum[idx]))))
                self._smooth[i] = self._smooth[i] * 0.75 + target * 0.25
                self._bar_heights[i] = self._smooth[i]
        else:
            # Idle animation when no signal
            for i in range(n):
                base = 0.3 + 0.25 * math.sin(self._phase + i * 0.4)
                noise = random.uniform(-0.08, 0.08)
                self._bar_heights[i] = max(0.06, min(0.95, base + noise))
            self._phase += 0.12
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Background rounded rect (mockup: bg-card-alt #16223b)
        bg = QColor("#16223b")
        p.setBrush(bg)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(self.rect(), 10, 10)

        # Bars area with padding
        r = self.rect().adjusted(14, 16, -14, -14)
        bar_w = 4
        gap = 4
        total_w = len(self._bar_heights) * (bar_w + gap) - gap
        ox = r.x() + (r.width() - total_w) // 2
        accent = QColor(Color.ACCENT)
        pink = QColor(Color.ACCENT_SECONDARY)
        for i, h in enumerate(self._bar_heights):
            bh = int(r.height() * h)
            x = ox + i * (bar_w + gap)
            y = r.bottom() - bh
            grad = QLinearGradient(x, y, x, r.bottom())
            grad.setColorAt(0.0, accent)
            grad.setColorAt(1.0, pink)
            p.setBrush(grad)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(x, y, bar_w, bh, 2, 2)
        p.end()


class _RoundedWidget(QWidget):
    """Base widget that paints its own background + border with per-state corner rounding."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._expanded = False
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def _rounded_path(self) -> QPainterPath:
        w, h = self.width(), self.height()
        r = RADIUS
        path = QPainterPath()
        if self._expanded:
            path.addRoundedRect(0, 0, w, h, r, r)
        else:
            path.moveTo(0, r)
            path.arcTo(0, 0, r * 2, r * 2, 180, -90)
            path.lineTo(w - r, 0)
            path.arcTo(w - r * 2, 0, r * 2, r * 2, 90, -90)
            path.lineTo(w, h)
            path.lineTo(0, h)
            path.closeSubpath()
        return path

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = self._rounded_path()
        p.fillPath(path, QColor(Color.CARD))
        p.setPen(QColor(Color.BORDER))
        p.drawPath(path)


class MiniPlayer(_RoundedWidget):
    """Collapsible always-on-top miniplayer. Compact bar + expandable body."""

    play_toggled = Signal()
    next_requested = Signal()
    prev_requested = Signal()
    closed = Signal()

    def __init__(self, engine: PlayerEngine, parent=None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._is_playing = False
        self._drag_pos = None

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setFixedWidth(W)

        # Root layout
        root = QVBoxLayout(self)
        root.setContentsMargins(1, 1, 1, 1)
        root.setSpacing(0)

        # Compact bar (always visible)
        self.bar = QWidget()
        self.bar.setFixedHeight(74)
        self.bar.setStyleSheet("background:transparent;")
        bar_layout = QHBoxLayout(self.bar)
        bar_layout.setContentsMargins(14, 0, 8, 0)
        bar_layout.setSpacing(10)

        # Artwork
        self.artwork = QLabel("\U0001f3b5")
        self.artwork.setFixedSize(44, 44)
        self.artwork.setAlignment(Qt.AlignCenter)
        self.artwork.setStyleSheet(
            "background:radial-gradient(circle at 35% 30%, #2E4A7D, #101B33 70%);"
            "border-radius:10px;font-size:20px;"
        )
        bar_layout.addWidget(self.artwork)

        # Meta column
        meta = QVBoxLayout()
        meta.setSpacing(1)
        self.title_label = _MarqueeLabel("No track")
        self.title_label.setStyleSheet(
            f"color:{Color.TEXT_PRIMARY};font-weight:{FontWeights.BODY_SEMIBOLD};"
            f"font-size:13px;background:transparent;"
        )
        self.artist_label = QLabel("-")
        self.artist_label.setStyleSheet(
            f"color:{Color.TEXT_DIM};font-size:11px;background:transparent;"
        )
        meta.addWidget(self.title_label)
        meta.addWidget(self.artist_label)

        # Progress bar in compact mode
        self.compact_progress = QWidget()
        self.compact_progress.setFixedHeight(3)
        self.compact_progress.setStyleSheet(
            f"background:{Color.BORDER};border-radius:2px;"
        )
        self.compact_fill = QWidget(self.compact_progress)
        self.compact_fill.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {Color.PRIMARY},stop:1 {Color.ACCENT});"
            f"border-radius:2px;"
        )
        meta.addWidget(self.compact_progress)

        # Time row
        time_row = QHBoxLayout()
        time_row.setSpacing(0)
        self.compact_time = QLabel("0:00")
        self.compact_time.setStyleSheet(
            f"color:{Color.TEXT_DIM};font-size:9px;background:transparent;"
        )
        self.compact_duration = QLabel("0:00")
        self.compact_duration.setStyleSheet(
            f"color:{Color.TEXT_DIM};font-size:9px;background:transparent;"
        )
        time_row.addWidget(self.compact_time)
        time_row.addStretch()
        time_row.addWidget(self.compact_duration)
        meta.addLayout(time_row)

        bar_layout.addLayout(meta, 1)

        # Controls in bar
        self.prev_btn = self._icon_btn("⏮", 28, 28)
        self.prev_btn.clicked.connect(self.prev_requested.emit)
        bar_layout.addWidget(self.prev_btn)

        self.play_btn = self._play_btn()
        self.play_btn.clicked.connect(self._toggle_play)
        bar_layout.addWidget(self.play_btn)

        self.next_btn = self._icon_btn("⏭", 28, 28)
        self.next_btn.clicked.connect(self.next_requested.emit)
        bar_layout.addWidget(self.next_btn)

        # Expand toggle
        self.expand_btn = QPushButton("▾")
        self.expand_btn.setFixedSize(26, 26)
        self.expand_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;"
            f"color:{Color.TEXT_DIM};font-size:12px;}}"
            f"QPushButton:hover{{color:{Color.ACCENT};}}"
        )
        bar_layout.addWidget(self.expand_btn)

        root.addWidget(self.bar)

        # Expanded body
        self.body = QWidget()
        self.body.setStyleSheet("background:transparent;")
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(20, 18, 20, 20)
        body_layout.setSpacing(0)

        # Visualizer with animated bars
        self.visualizer = _VisualizerBars()
        self.visualizer.setFixedHeight(120)
        body_layout.addWidget(self.visualizer)

        # Expanded title/artist
        self.exp_title = QLabel("No track")
        self.exp_title.setStyleSheet(
            f"color:{Color.TEXT_PRIMARY};font-weight:{FontWeights.BODY_SEMIBOLD};"
            f"font-size:16px;background:transparent;margin-top:16px;"
        )
        body_layout.addWidget(self.exp_title)

        self.exp_artist = QLabel("-")
        self.exp_artist.setStyleSheet(
            f"color:{Color.TEXT_DIM};font-size:12px;background:transparent;margin-bottom:14px;"
        )
        body_layout.addWidget(self.exp_artist)

        # Scrubber
        scrub = QHBoxLayout()
        scrub.setSpacing(10)
        self.exp_time = QLabel("0:00")
        self.exp_time.setStyleSheet(
            f"color:{Color.TEXT_DIM};font-size:10px;background:transparent;"
        )
        self.exp_time.setFixedWidth(30)
        scrub.addWidget(self.exp_time)

        self.scrub_track = QWidget()
        self.scrub_track.setFixedHeight(4)
        self.scrub_track.setStyleSheet(
            f"background:{Color.BORDER};border-radius:2px;"
        )
        self.scrub_fill = QWidget(self.scrub_track)
        self.scrub_fill.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {Color.PRIMARY},stop:1 {Color.ACCENT});"
            f"border-radius:2px;"
        )
        scrub.addWidget(self.scrub_track, 1)

        self.exp_duration = QLabel("0:00")
        self.exp_duration.setStyleSheet(
            f"color:{Color.TEXT_DIM};font-size:10px;background:transparent;"
        )
        self.exp_duration.setFixedWidth(30)
        self.exp_duration.setAlignment(Qt.AlignRight)
        scrub.addWidget(self.exp_duration)
        body_layout.addLayout(scrub)

        # Main controls
        ctrl_row = QHBoxLayout()
        ctrl_row.setAlignment(Qt.AlignCenter)
        ctrl_row.setSpacing(22)
        ctrl_row.setContentsMargins(0, 18, 0, 4)

        self.shuffle_btn = self._side_btn("\U0001f500")
        ctrl_row.addWidget(self.shuffle_btn)

        self.exp_prev = self._side_btn("⏮")
        ctrl_row.addWidget(self.exp_prev)

        self.exp_play = QPushButton("▶")
        self.exp_play.setFixedSize(46, 46)
        self.exp_play.setStyleSheet(
            f"QPushButton{{font-size:18px;background:{Color.ACCENT};"
            f"border-radius:23px;color:#fff;border:none;}}"
            f"QPushButton:hover{{background:{Color.PRIMARY};}}"
        )
        self.exp_play.clicked.connect(self._toggle_play)
        ctrl_row.addWidget(self.exp_play)

        self.exp_next = self._side_btn("⏭")
        ctrl_row.addWidget(self.exp_next)

        self.repeat_btn = self._side_btn("\U0001f501")
        ctrl_row.addWidget(self.repeat_btn)

        body_layout.addLayout(ctrl_row)

        # Volume
        vol_row = QHBoxLayout()
        vol_row.setContentsMargins(0, 18, 0, 0)
        vol_row.setSpacing(10)
        self.vol_icon = QLabel("\U0001f50a")
        self.vol_icon.setFixedSize(20, 20)
        self.vol_icon.setStyleSheet(
            f"color:{Color.TEXT_DIM};font-size:14px;background:transparent;"
        )
        vol_row.addWidget(self.vol_icon)

        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(70)
        self.vol_slider.setFixedHeight(4)
        self.vol_slider.setStyleSheet(
            f"QSlider::groove:horizontal{{height:4px;border-radius:2px;"
            f"background:{Color.BORDER};}}"
            f"QSlider::handle:horizontal{{width:10px;height:10px;margin:-3px 0;"
            f"border-radius:5px;background:{Color.ACCENT};}}"
            f"QSlider::sub-page:horizontal{{background:{Color.ACCENT};"
            f"border-radius:2px;}}"
        )
        vol_row.addWidget(self.vol_slider, 1)
        body_layout.addLayout(vol_row)

        # Footer buttons
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 14, 0, 0)
        self.like_btn = QPushButton("♡ Suka")
        self.like_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;"
            f"color:{Color.TEXT_DIM};font-size:11px;}}"
            f"QPushButton:hover{{color:{Color.ACCENT};}}"
            f"QPushButton:checked{{color:{Color.ACCENT_SECONDARY};}}"
        )
        self.like_btn.setCheckable(True)
        footer.addWidget(self.like_btn)

        footer.addStretch()

        self.queue_btn = QPushButton("☰ Antrean")
        self.queue_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;"
            f"color:{Color.TEXT_DIM};font-size:11px;}}"
            f"QPushButton:hover{{color:{Color.ACCENT};}}"
        )
        footer.addWidget(self.queue_btn)
        body_layout.addLayout(footer)

        root.addWidget(self.body)

        # Close button (overlay, top-right)
        self.close_btn = QPushButton("✕", self)
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setStyleSheet(
            f"QPushButton{{background:{Color.CARD};border:1px solid {Color.BORDER};"
            f"border-radius:12px;color:{Color.TEXT_DIM};font-size:11px;}}"
            f"QPushButton:hover{{color:{Color.ACCENT_SECONDARY};"
            f"background:{Color.CARD_SOFT};}}"
        )
        self.close_btn.clicked.connect(self._do_close)

        # Start collapsed
        self.body.setVisible(False)
        self.setFixedHeight(COMPACT_H)

        # Signals
        self.expand_btn.clicked.connect(self._toggle_expand)
        self.exp_prev.clicked.connect(self.prev_requested.emit)
        self.exp_next.clicked.connect(self.next_requested.emit)

        # Poll timer
        self._timer = QTimer(self)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    # Helpers

    def _icon_btn(self, text: str, w: int, h: int) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(w, h)
        btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;"
            f"color:{Color.TEXT_DIM};font-size:14px;}}"
            f"QPushButton:hover{{color:{Color.ACCENT};}}"
        )
        return btn

    def _play_btn(self) -> QPushButton:
        btn = QPushButton("▶")
        btn.setFixedSize(34, 34)
        btn.setStyleSheet(
            f"QPushButton{{font-size:16px;background:{Color.ACCENT};"
            f"border-radius:17px;color:#fff;border:none;}}"
            f"QPushButton:hover{{background:{Color.PRIMARY};}}"
        )
        return btn

    def _side_btn(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(30, 30)
        btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;"
            f"color:{Color.TEXT_DIM};font-size:14px;}}"
            f"QPushButton:hover{{color:{Color.ACCENT};}}"
        )
        return btn

    # Public API

    def update_track_info(
        self, title: str, artist: str, artwork: QPixmap | None = None
    ) -> None:
        self.title_label.setText(title or "No track")
        self.artist_label.setText(artist or "-")
        self.exp_title.setText(title or "No track")
        self.exp_artist.setText(artist or "-")
        if artwork:
            self.artwork.setText("")
            self.artwork.setPixmap(
                artwork.scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            self.artwork.clear()
            self.artwork.setText("\U0001f3b5")

    def set_playing(self, playing: bool) -> None:
        self._is_playing = playing
        txt = "⏸" if playing else "▶"
        self.play_btn.setText(txt)
        self.exp_play.setText(txt)

    def set_spectrum(self, data: np.ndarray) -> None:
        self.visualizer.set_spectrum(data)

    # Internals

    def _toggle_play(self) -> None:
        self.play_toggled.emit()
        if self._engine:
            self._engine.toggle_play()

    def _do_close(self) -> None:
        self._timer.stop()
        self.hide()
        self.closed.emit()

    def _poll(self) -> None:
        if not self._engine:
            return
        pos = self._engine.position_ms
        dur = self._engine.duration_ms

        ratio = pos / max(dur, 1)
        cw = self.compact_progress.width()
        self.compact_fill.setFixedWidth(int(cw * ratio))

        self.compact_time.setText(_fmt_ms(pos))
        self.compact_duration.setText(_fmt_ms(dur))

        self.exp_time.setText(_fmt_ms(pos))
        self.exp_duration.setText(_fmt_ms(dur))

        sw = self.scrub_track.width()
        self.scrub_fill.setFixedWidth(int(sw * ratio))

        playing = self._engine.is_playing
        if playing != self._is_playing:
            self._is_playing = playing
            txt = "⏸" if playing else "▶"
            self.play_btn.setText(txt)
            self.exp_play.setText(txt)

    def _toggle_expand(self, event=None) -> None:
        self._expanded = not self._expanded
        self.body.setVisible(self._expanded)
        h = EXPANDED_H if self._expanded else COMPACT_H
        self.setFixedHeight(h)
        self.update()
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.center().x() - self.width() // 2
            y = geo.bottom() - h - 60
            self.move(x, y)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.close_btn.move(self.width() - self.close_btn.width() - 6, 6)
        cw = self.compact_progress.width()
        if self._engine:
            ratio = self._engine.position_ms / max(self._engine.duration_ms, 1)
            self.compact_fill.setFixedWidth(int(cw * ratio))
        sw = self.scrub_track.width()
        if self._engine:
            ratio = self._engine.position_ms / max(self._engine.duration_ms, 1)
            self.scrub_fill.setFixedWidth(int(sw * ratio))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        event.accept()
