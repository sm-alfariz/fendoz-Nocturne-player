# coding:utf-8
"""
ring_visualizer.py — Custom QWidget rendering FFT spectrum as a ring around
album art, drawn with QPainter at ~30 fps.  (FR-4.1–4.3)
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from nocturne.ui.theme.tokens import Color


class RingVisualizer(QWidget):
    """Animated ring visualizer around album art."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._spectrum: np.ndarray = np.zeros(64)
        self._artwork: Optional[QPixmap] = None
        self._reduce_motion = False

        # 30 fps timer
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self.update)

    def set_spectrum(self, data: np.ndarray) -> None:
        """Receive FFT magnitudes from AudioWorker."""
        self._spectrum = data
        if not self._timer.isActive() and not self._reduce_motion:
            self._timer.start()

    def set_artwork(self, pixmap: Optional[QPixmap]) -> None:
        self._artwork = pixmap

    def set_reduce_motion(self, enabled: bool) -> None:
        self._reduce_motion = enabled
        if enabled:
            self._timer.stop()
        else:
            self._timer.start()

    def paintEvent(self, event: QPaintEvent) -> None:
        """QPainter path — draw ring bars proportional to spectrum."""
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        radius = min(w, h) // 2 - 20

        # --- Album art (center) ---
        art_size = int(radius * 1.1)
        if self._artwork:
            pix = self._artwork.scaled(
                art_size, art_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            painter.drawPixmap(cx - pix.width() // 2, cy - pix.height() // 2, pix)
        else:
            # Fallback: draw dark circle with "N" letter
            painter.setBrush(QBrush(QColor(Color.CARD)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(cx - art_size // 2, cy - art_size // 2, art_size, art_size)
            painter.setPen(QColor(Color.TEXT_DIM))
            painter.setFont(self.font())
            painter.drawText(cx - 20, cy - 20, 40, 40, Qt.AlignCenter, "N")

        # --- Ring bars ---
        n_bars = len(self._spectrum)
        if n_bars == 0:
            return

        bar_width = 360.0 / n_bars
        pen = QPen()
        pen.setWidthF(max(1.5, bar_width * 0.6))

        for i, magnitude in enumerate(self._spectrum):
            angle = math.radians(i * bar_width - 90)
            bar_height = 4 + magnitude * (radius * 0.35)

            x1 = cx + (radius + 4) * math.cos(angle)
            y1 = cy + (radius + 4) * math.sin(angle)
            x2 = cx + (radius + 4 + bar_height) * math.cos(angle)
            y2 = cy + (radius + 4 + bar_height) * math.sin(angle)

            # Gradient from accent to primary
            t = magnitude
            r = int(79 + (30 - 79) * t)  # 4FC3F7 -> 1E88E5
            g = int(195 + (136 - 195) * t)
            b = int(247 + (229 - 247) * t)
            pen.setColor(QColor(r, g, b))
            painter.setPen(pen)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        painter.end()
