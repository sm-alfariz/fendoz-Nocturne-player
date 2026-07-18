# coding:utf-8
"""
ring_visualizer.py — Custom QWidget rendering FFT spectrum as a ring around
album art, drawn with QPainter at ~30 fps.  (FR-4.1–4.3)

Matches mockup: circular album art with glow shadow, ring segments around it,
horizontal spectrum bar below track info.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QLinearGradient,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QRgba64,
)
from PySide6.QtWidgets import QWidget

from nocturne.ui.theme.tokens import Color


class RingVisualizer(QWidget):
    """Animated ring visualizer around album art + horizontal spectrum bar."""

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
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2

        # ── Ring segments around album art ────────────────────────────
        radius = 108
        n_bars = len(self._spectrum)
        pen = QPen()
        pen.setWidthF(2.4)

        for i, magnitude in enumerate(self._spectrum):
            angle = math.radians(i / max(n_bars, 1) * 360 - 90)
            bar_len = 6 + abs(magnitude) * 16

            x1 = cx + radius * math.cos(angle)
            y1 = cy + radius * math.sin(angle)
            x2 = cx + (radius + bar_len) * math.cos(angle)
            y2 = cy + (radius + bar_len) * math.sin(angle)

            # Pink peak bar every 11th
            if i % 11 == 0:
                pen.setColor(QColor(Color.ACCENT_SECONDARY))
            else:
                alpha = int(0.35 + abs(magnitude) * 0.5 * 255)
                pen.setColor(QColor(79, 195, 247, min(alpha, 255)))
            painter.setPen(pen)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        # ── Album art (circular with glow shadow) ─────────────────────
        art_size = 186
        art_rect = QRectF(cx - art_size // 2, cy - art_size // 2, art_size, art_size)

        # Shadow
        shadow_pen = QPen(QColor(Color.BORDER), 1)
        painter.setPen(shadow_pen)
        painter.setBrush(QBrush(QColor("#101B33")))
        painter.drawEllipse(art_rect)

        if self._artwork:
            pix = self._artwork.scaled(
                art_size, art_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            # Clip to circle
            path = painter.clipPath()
            painter.setClipRect(art_rect.toRect())
            painter.drawPixmap(int(art_rect.x()), int(art_rect.y()), pix)
            painter.setClipPath(path)
        else:
            # Fallback: gradient circle with centre dot
            grad = QConicalGradient(cx, cy, 0)
            grad.setColorAt(0, QColor("#2E4A7D"))
            grad.setColorAt(1, QColor("#101B33"))
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(art_rect)

            # Centre dot
            painter.setBrush(QBrush(QColor(Color.BACKGROUND_DEEP)))
            painter.drawEllipse(QRectF(cx - 28, cy - 28, 56, 56))

        painter.end()


class SpectrumBar(QWidget):
    """Horizontal spectrum visualizer bar (below track info in mockup)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._spectrum: np.ndarray = np.zeros(64)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self.update)

    def set_spectrum(self, data: np.ndarray) -> None:
        self._spectrum = data
        if not self._timer.isActive():
            self._timer.start()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        n = len(self._spectrum)
        if n == 0:
            return

        bar_w = max(2, (w - (n - 1) * 3) / n)
        gradient = QLinearGradient(0, h, 0, 0)
        gradient.setColorAt(0, QColor(Color.PRIMARY))
        gradient.setColorAt(0.65, QColor(Color.ACCENT))
        gradient.setColorAt(1, QColor(30, 136, 229, 64))

        for i, mag in enumerate(self._spectrum):
            bh = max(4, mag * h * 0.9)
            x = i * (bar_w + 3)
            painter.fillRect(
                int(x), int(h - bh), int(bar_w), int(bh), QBrush(gradient)
            )

        painter.end()
