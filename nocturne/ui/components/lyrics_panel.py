# coding:utf-8
"""
lyrics_panel.py — Right-side lyrics panel matching mockup-nocturne.html.

Header with SYNCED badge (pulsing dot), body with gradient mask,
active line in gradient accent→primary text.
"""

from __future__ import annotations

import math
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from nocturne.ui.theme.tokens import Color, Fonts

from nocturne.core.lyrics_sync import LyricLine


class _SyncBadge(QLabel):
    """'SYNCED' badge with pulsing dot animation."""

    def __init__(self, parent=None):
        super().__init__("SYNCED", parent)
        self._pulse = 1.0
        self.setStyleSheet(
            f"color:{Color.ACCENT};font-size:10px;font-family:'{Fonts.MONO}';"
            f"background:rgba(79,195,247,0.1);border:1px solid {Color.BORDER};"
            f"padding:4px 8px;border-radius:8px;"
        )
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick_pulse)
        self._timer.start()

    def _tick_pulse(self):
        import time
        self._pulse = 0.5 + 0.5 * math.sin(time.time() * 4.5)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        alpha = int(self._pulse * 255)
        c = QColor(Color.ACCENT)
        c.setAlpha(max(60, alpha))
        painter.setBrush(c)
        glow = QColor(Color.ACCENT)
        glow.setAlpha(max(30, alpha // 3))
        painter.setBrush(glow)
        painter.drawEllipse(7, self.height() // 2 - 4, 8, 8)
        painter.setBrush(c)
        painter.drawEllipse(8, self.height() // 2 - 3, 6, 6)


def _build_lyrics_header() -> QWidget:
    """Build the lyrics panel header with 'Lirik' title and SYNCED badge."""
    h = QWidget()
    h.setStyleSheet(f"border-bottom:1px solid {Color.BORDER};")
    hl = QHBoxLayout(h)
    hl.setContentsMargins(22, 20, 22, 14)
    title = QLabel("Lirik")
    title.setStyleSheet(
        f"font-family:'{Fonts.DISPLAY}';font-size:14px;font-weight:700;color:{Color.TEXT_PRIMARY};"
    )
    hl.addWidget(title)
    hl.addStretch()
    hl.addWidget(_SyncBadge())
    return h


class LyricsPanel(QScrollArea):
    """Right-side panel showing synchronised lyrics with auto-scroll."""

    LINE_HEIGHT = 40

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(300)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet(
            f"background:rgba(15,23,42,0.35);border-left:1px solid {Color.BORDER};"
        )

        # Container
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setSpacing(4)
        self._layout.setContentsMargins(22, 24, 22, 40)
        self._layout.setAlignment(Qt.AlignTop)
        self.setWidget(self._container)

        self._lines: list[LyricLine] = []
        self._labels: list[QLabel] = []
        self._offset_ms = 0

        # Header
        self._header = QWidget()
        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(22, 20, 22, 14)
        title = QLabel("Lirik")
        title.setStyleSheet(
            f"font-family:'{Fonts.DISPLAY}';font-size:14px;font-weight:700;color:{Color.TEXT_PRIMARY};"
        )
        hl.addWidget(title)
        hl.addStretch()

        self._offset_label = QLabel("0ms")
        self._offset_label.setStyleSheet(
            f"color:{Color.TEXT_DIM};font-size:9px;font-family:'{Fonts.MONO}';"
            "padding:0 4px;"
        )
        self._offset_minus = QPushButton("-100")
        self._offset_plus = QPushButton("+100")
        for btn in (self._offset_minus, self._offset_plus):
            btn.setFixedHeight(20)
            btn.setStyleSheet(
                f"color:{Color.ACCENT};font-size:10px;font-family:'{Fonts.MONO}';"
                f"background:rgba(79,195,247,0.08);border:1px solid {Color.BORDER};"
                "border-radius:5px;padding:0 6px;"
            )
        self._offset_minus.clicked.connect(lambda: self.adjust_offset(-100))
        self._offset_plus.clicked.connect(lambda: self.adjust_offset(+100))
        hl.addWidget(self._offset_minus)
        hl.addWidget(self._offset_label)
        hl.addWidget(self._offset_plus)
        hl.addSpacing(4)
        hl.addWidget(_SyncBadge())

        # Header goes outside scroll area — handle via parent layout
        self._show_placeholder()

    def paintEvent(self, event):
        """Draw gradient fade at top and bottom of the lyrics viewport."""
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        fade_height = 40
        w = self.viewport().width()

        # Top fade: bg (hides content) → transparent (reveals content)
        top_grad = QLinearGradient(0, 0, 0, fade_height)
        bg = QColor(Color.BACKGROUND)
        bg_transparent = QColor(bg)
        bg_transparent.setAlpha(0)
        top_grad.setColorAt(0, bg)
        top_grad.setColorAt(1, bg_transparent)
        painter.fillRect(0, 0, w, fade_height, top_grad)

        # Bottom fade: bg → transparent
        vh = self.viewport().height()
        bot_grad = QLinearGradient(0, vh - fade_height, 0, vh)
        bot_grad.setColorAt(0, bg_transparent)
        bot_grad.setColorAt(1, bg)
        painter.fillRect(0, vh - fade_height, w, fade_height, bot_grad)

    def _show_placeholder(self, msg: str = "Lirik tidak ditemukan\nuntuk lagu ini") -> None:
        self._clear_labels()
        label = QLabel(msg)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(f"color: {Color.TEXT_DIM}; font-size: 14px; padding: 40px;")
        self._layout.addWidget(label)
        self._labels.append(label)

    def _clear_labels(self) -> None:
        for label in self._labels:
            self._layout.removeWidget(label)
            label.deleteLater()
        self._labels.clear()
        self._lines.clear()

    def load_lyrics(self, lines: list[LyricLine]) -> None:
        self._clear_labels()
        if not lines:
            self._show_placeholder()
            return

        self._lines = lines
        for ll in lines:
            label = QLabel(ll.text)
            label.setWordWrap(True)
            label.setFixedHeight(self.LINE_HEIGHT)
            label.setStyleSheet(
                f"color: {Color.TEXT_DIM}; font-size: 15px; font-weight: 500; "
                "padding: 5px 0; background: transparent;"
            )
            self._layout.addWidget(label)
            self._labels.append(label)

        self.verticalScrollBar().setValue(0)

    def highlight_line(self, timestamp_ms: int) -> None:
        if not self._lines:
            return

        ts = max(0, timestamp_ms + self._offset_ms)
        active_idx = -1
        for i, ll in enumerate(self._lines):
            if ll.timestamp_ms <= ts:
                active_idx = i
            else:
                break

        for i, label in enumerate(self._labels):
            if i == active_idx:
                label.setStyleSheet(
                    "font-size: 17px; font-weight: 700; padding: 5px 0; color: #FFFFFF;"
                    "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                    "stop:0 rgba(79,195,247,0.10),stop:1 rgba(30,136,229,0.03));"
                )
                target_y = i * self.LINE_HEIGHT - self.height() // 3
                self.verticalScrollBar().setValue(max(0, target_y))
            else:
                label.setStyleSheet(
                    f"color: {Color.TEXT_DIM}; font-size: 15px; font-weight: 500; "
                    "padding: 5px 0;"
                )

    def set_offset(self, offset_ms: int) -> None:
        self._offset_ms = offset_ms

    def adjust_offset(self, delta_ms: int) -> None:
        self._offset_ms += delta_ms
        self._offset_label.setText(f"{self._offset_ms:+d}ms")
