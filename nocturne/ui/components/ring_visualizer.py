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
    QRadialGradient,
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
        self._frame = 0

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
        t = self._frame * 0.12

        # Soft outer glow to emulate the PRD mockup's glassy dark atmosphere.
        glow = QRadialGradient(cx, cy, 110)
        glow.setColorAt(0, QColor(30, 136, 229, 44))
        glow.setColorAt(0.55, QColor(79, 195, 247, 12))
        glow.setColorAt(1, QColor(10, 15, 30, 0))
        painter.setBrush(glow)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(cx - 128, cy - 128, 256, 256))

        # ── Ring segments around album art ────────────────────────────
        inner_radius = 104
        outer_radius = 130
        n_bars = max(1, len(self._spectrum))
        pen = QPen()
        pen.setWidthF(2.2)

        for i, magnitude in enumerate(self._spectrum):
            angle = math.radians(i / n_bars * 360 - 90 + math.sin(t + i * 0.22) * 8)
            magnitude = max(0.0, min(1.0, abs(float(magnitude))))
            pulse = 0.78 + 0.22 * math.sin(t * 2.1 + i * 0.16)
            bar_len = 6 + magnitude * 18 * pulse

            x1 = cx + inner_radius * math.cos(angle)
            y1 = cy + inner_radius * math.sin(angle)
            x2 = cx + (inner_radius + bar_len) * math.cos(angle)
            y2 = cy + (inner_radius + bar_len) * math.sin(angle)

            if i % 11 == 0:
                pen.setColor(QColor(Color.ACCENT_SECONDARY))
                pen.setWidthF(2.6)
            else:
                alpha = int(60 + magnitude * 165)
                pen.setColor(QColor(79, 195, 247, min(alpha, 255)))
                pen.setWidthF(2.0)

            painter.setPen(pen)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        outer_ring = QPen(QColor(79, 195, 247, 72), 1.3)
        painter.setPen(outer_ring)
        painter.drawEllipse(QRectF(cx - outer_radius, cy - outer_radius, outer_radius * 2, outer_radius * 2))

        # ── Album art (circular with glow shadow) ─────────────────────
        art_size = 188
        art_rect = QRectF(cx - art_size // 2, cy - art_size // 2, art_size, art_size)

        shadow_pen = QPen(QColor(79, 195, 247, 110), 1)
        painter.setPen(shadow_pen)
        painter.setBrush(QBrush(QColor("#101B33")))
        painter.drawEllipse(art_rect)

        if self._artwork:
            pix = self._artwork.scaled(
                art_size, art_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            clip_path = painter.clipPath()
            painter.setClipRect(art_rect.toRect())
            painter.drawPixmap(int(art_rect.x()), int(art_rect.y()), pix)
            painter.setClipPath(clip_path)
        else:
            grad = QConicalGradient(cx, cy, 0)
            grad.setColorAt(0, QColor("#2E4A7D"))
            grad.setColorAt(1, QColor("#101B33"))
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(art_rect)

            painter.setBrush(QBrush(QColor(Color.BACKGROUND_DEEP)))
            painter.drawEllipse(QRectF(cx - 26, cy - 26, 52, 52))

        painter.end()
        self._frame += 1


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

        painter.setPen(Qt.NoPen)
        spacing = 3
        bar_w = max(2, (w - (n - 1) * spacing) / n)
        gradient = QLinearGradient(0, h, 0, 0)
        gradient.setColorAt(0, QColor(Color.PRIMARY))
        gradient.setColorAt(0.7, QColor(Color.ACCENT))
        gradient.setColorAt(1, QColor(79, 195, 247, 70))

        for i, mag in enumerate(self._spectrum):
            mag = max(0.0, min(1.0, abs(float(mag))))
            bh = max(8, mag * h * 0.94)
            x = i * (bar_w + spacing)
            radius = 2
            painter.fillRect(
                int(x), int(h - bh), int(bar_w), int(bh), QBrush(gradient)
            )
            painter.setBrush(QColor(30, 136, 229, 70))
            painter.drawRoundedRect(int(x), int(h - bh), int(bar_w), int(bh), radius, radius)

        painter.end()
