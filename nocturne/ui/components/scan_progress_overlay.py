# coding:utf-8
"""
scan_progress_overlay.py — Semi-transparent overlay with progress bar during library scan.

Cover the main window so user cannot interact until scan finishes.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from qfluentwidgets import ProgressBar

from nocturne.ui.theme.tokens import Color


class ScanProgressOverlay(QWidget):
    """Semi-transparent overlay covering the window during library scan."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(15, 23, 42, 180);")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        self.label = QLabel("Scanning library...")
        self.label.setStyleSheet(
            f"color: {Color.TEXT_PRIMARY}; font-size: 16px; background: transparent;"
        )
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        self.progress_bar = ProgressBar(self)
        self.progress_bar.setFixedWidth(320)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar, 0, Qt.AlignCenter)

        self.hide()

    def set_progress(self, current: int, total: int) -> None:
        """Update progress bar from (current, total) scan counts."""
        if total > 0:
            pct = int(current / total * 100)
            self.progress_bar.setValue(pct)
            self.label.setText(f"Scanning library... ({current}/{total})")

    def paintEvent(self, event) -> None:
        """Fill the overlay with a translucent background."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(15, 23, 42, 180))

    def showEvent(self, event) -> None:
        """Recentre when shown (parent may have resized)."""
        if self.parent():
            self.resize(self.parent().size())
        super().showEvent(event)
