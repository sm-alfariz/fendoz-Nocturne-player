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
        self._segments = 90

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

        # Soft outer glow to emulate the PRD mockup's glassy dark atmosphere.
        glow = QRadialGradient(cx, cy, 110)
        glow.setColorAt(0, QColor(30, 136, 229, 44))
        glow.setColorAt(0.55, QColor(79, 195, 247, 12))
        glow.setColorAt(1, QColor(10, 15, 30, 0))
        painter.setBrush(glow)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(cx - 128, cy - 128, 256, 256))

        # ── Ring segments around album art ────────────────────────────
        inner_radius = 108
        outer_radius = 130
        segments = self._segments
        has_signal = bool(np.any(self._spectrum > 0.01))
        t_ring = self._frame * 0.045
        pen = QPen()
        pen.setWidthF(2.4)

        for i in range(segments):
            angle = math.radians(i / segments * 360 - 90 + math.sin(t_ring + i * 0.22) * 8)
            if has_signal:
                idx = int(i / segments * len(self._spectrum))
                magnitude = max(0.0, min(1.0, abs(float(self._spectrum[idx]))))
                pulse = 0.78 + 0.22 * math.sin(t_ring * 2.1 + i * 0.16)
                bar_len = 6 + magnitude * 18 * pulse
            else:
                n = math.sin(t_ring + i * 0.28) * 0.5 + math.sin(t_ring * 1.7 + i * 0.12) * 0.3
                bar_len = 6 + abs(n) * 16

            x1 = cx + inner_radius * math.cos(angle)
            y1 = cy + inner_radius * math.sin(angle)
            x2 = cx + (inner_radius + bar_len) * math.cos(angle)
            y2 = cy + (inner_radius + bar_len) * math.sin(angle)

            if i % 11 == 0:
                pen.setColor(QColor(Color.ACCENT_SECONDARY))
                pen.setWidthF(2.8)
            else:
                if has_signal:
                    alpha = int(60 + magnitude * 165)
                else:
                    alpha = 90 + int(abs(n) * 120)
                pen.setColor(QColor(79, 195, 247, min(alpha, 255)))
                pen.setWidthF(2.4)

            painter.setPen(pen)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        outer_ring = QPen(QColor(79, 195, 247, 72), 1.3)
        painter.setPen(outer_ring)
        painter.drawEllipse(QRectF(cx - outer_radius, cy - outer_radius, outer_radius * 2, outer_radius * 2))

        # ── Album art (circular with glow shadow) ─────────────────────
        art_size = 188
        art_rect = QRectF(cx - art_size // 2, cy - art_size // 2, art_size, art_size)

        # Outer drop-shadow glow (mockup: 0 20px 50px -12px rgba(30,136,229,0.45))
        shadow_glow = QRadialGradient(cx, cy + 20, art_size * 0.7)
        shadow_glow.setColorAt(0, QColor(30, 136, 229, 80))
        shadow_glow.setColorAt(1, QColor(30, 136, 229, 0))
        painter.setBrush(shadow_glow)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(cx - art_size * 0.5, cy - art_size * 0.3, art_size, art_size * 0.8))

        # Border ring
        border_pen = QPen(QColor(79, 195, 247, 36), 1)
        painter.setPen(border_pen)
        painter.setBrush(QBrush(QColor("#101B33")))
        painter.drawEllipse(art_rect)

        if self._artwork:
            # Rotate album art continuously (22s revolution at 30fps)
            rotation = (self._frame * 0.545) % 360
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(rotation)
            painter.translate(-cx, -cy)
            pix = self._artwork.scaled(
                art_size, art_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            clip_path = painter.clipPath()
            painter.setClipRect(art_rect.toRect())
            painter.drawPixmap(int(art_rect.x()), int(art_rect.y()), pix)
            painter.setClipPath(clip_path)
            painter.restore()
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
        self._has_signal = False
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self.update)

    def set_spectrum(self, data: np.ndarray) -> None:
        self._spectrum = data
        self._has_signal = bool(np.any(data > 0.01))
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

        for i in range(n):
            if self._has_signal:
                mag = max(0.0, min(1.0, abs(float(self._spectrum[i]))))
            else:
                base = math.sin(self._phase + i * 0.35) * 0.5 + 0.5
                import random as _random
                noise = _random.random() * 0.35
                mag = min(1.0, base * 0.7 + noise)
            bh = max(8, mag * h * 0.94)
            x = i * (bar_w + spacing)
            painter.setBrush(QBrush(gradient))
            painter.drawRoundedRect(
                int(x), int(h - bh), int(bar_w), int(bh), 4, 4
            )
            painter.setBrush(QColor(30, 136, 229, 40))
            painter.drawRect(
                int(x), int(h - 2), int(bar_w), 2
            )

        self._phase += 0.09
        painter.end()
