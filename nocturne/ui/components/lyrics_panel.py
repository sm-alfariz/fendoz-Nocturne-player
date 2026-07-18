# coding:utf-8
"""
lyrics_panel.py — Right-side lyrics panel matching mockup-nocturne.html.

Header with SYNCED badge (pulsing dot), body with gradient mask,
active line in gradient accent→primary text.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from nocturne.ui.theme.tokens import Color, Fonts

from nocturne.core.lyrics_sync import LyricLine
from nocturne.ui.theme.tokens import Color, Fonts


class _SyncBadge(QLabel):
    """'SYNCED' badge with pulsing dot animation."""

    def __init__(self, parent=None):
        super().__init__("SYNCED", parent)
        self._dot_visible = True
        self.setStyleSheet(
            f"color:{Color.ACCENT};font-size:10px;font-family:'{Fonts.MONO}';"
            f"background:rgba(79,195,247,0.1);border:1px solid {Color.BORDER};"
            f"padding:4px 8px;border-radius:8px;"
        )
        self._timer = QTimer(self)
        self._timer.setInterval(1400)
        self._timer.timeout.connect(self._toggle_dot)
        self._timer.start()

    def _toggle_dot(self):
        self._dot_visible = not self._dot_visible
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        if self._dot_visible:
            painter.setBrush(QColor(Color.ACCENT))
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
        hl.addWidget(_SyncBadge())

        # Header goes outside scroll area — handle via parent layout
        self._show_placeholder()

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
                # Gradient text via QSS (rich-text fallback)
                label.setStyleSheet(
                    f"font-size: 17px; font-weight: 700; padding: 5px 0; color: {Color.TEXT_PRIMARY};"
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
