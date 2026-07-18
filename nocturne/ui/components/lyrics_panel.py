# coding:utf-8
"""
lyrics_panel.py — Scrollable lyrics panel with real-time line highlight
and auto-scroll.  (FR-5.1–5.5)
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from nocturne.core.lyrics_sync import LyricLine
from nocturne.ui.theme.tokens import Color


class LyricsPanel(QScrollArea):
    """Right-side panel showing synchronised lyrics with auto-scroll."""

    LINE_HEIGHT = 48

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(300)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setSpacing(4)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setAlignment(Qt.AlignTop)
        self.setWidget(self._container)

        self._lines: list[LyricLine] = []
        self._labels: list[QLabel] = []
        self._offset_ms = 0

        # Scroll smoothness timer
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setInterval(200)
        self._scroll_timer.setSingleShot(True)

        # Placeholder state
        self._show_placeholder()

    def _show_placeholder(self, msg: str = "Lirik tidak ditemukan\nuntuk lagu ini") -> None:
        """Show a centered placeholder when no lyrics are loaded."""
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
        """Set new lyrics and reset scroll position."""
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
                f"color: {Color.TEXT_DIM}; font-size: 14px; "
                "padding: 4px 0;"
            )
            self._layout.addWidget(label)
            self._labels.append(label)

        # Scroll to top
        self.verticalScrollBar().setValue(0)

    def highlight_line(self, timestamp_ms: int) -> None:
        """Highlight the line whose timestamp <= current position.

        Auto-scrolls smoothly to keep the active line visible.
        """
        if not self._lines:
            return

        timestamp_ms = max(0, timestamp_ms + self._offset_ms)

        # Find the current line (last line with timestamp <= current)
        active_idx = -1
        for i, ll in enumerate(self._lines):
            if ll.timestamp_ms <= timestamp_ms:
                active_idx = i
            else:
                break

        # Reset all labels
        for i, label in enumerate(self._labels):
            if i == active_idx:
                label.setStyleSheet(
                    f"color: {Color.ACCENT}; font-size: 16px; font-weight: 600; "
                    "padding: 4px 0;"
                )
                # Auto-scroll to centre the active line
                target_y = i * self.LINE_HEIGHT - self.height() // 3
                self.verticalScrollBar().setValue(max(0, target_y))
            else:
                label.setStyleSheet(
                    f"color: {Color.TEXT_DIM}; font-size: 14px; "
                    "padding: 4px 0;"
                )

    def set_offset(self, offset_ms: int) -> None:
        """Adjust sync offset in milliseconds (FR-5.4)."""
        self._offset_ms = offset_ms

    def adjust_offset(self, delta_ms: int) -> None:
        """Fine-tune offset by ±delta."""
        self._offset_ms += delta_ms
