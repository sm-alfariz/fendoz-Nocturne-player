# coding:utf-8
"""
ring_visualizer.py — Custom QWidget rendering FFT spectrum as a ring around
album art, drawn with QPainter at ~30 fps.  (FR-4.1–4.3)

Matches mockup-nocturne.html: circular album art with glow shadow, ring segments
around it, and horizontal spectrum bar with gradient below track info.
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
    """Animated ring visualizer around album art matching mockup style."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._spectrum: np.ndarray = np.zeros(64)
        self._smooth: np.ndarray = np.zeros(64)
        self._artwork: Optional[QPixmap] = None
        self._reduce_motion = False
        self._frame = 0

        # 30 fps timer — always running for idle animation
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self.update)
        self._timer.start()

    def set_spectrum(self, data: np.ndarray) -> None:
        """Receive FFT magnitudes from AudioWorker."""
        self._spectrum = data

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
        base_r = 108
        segments = 90
        has_signal = bool(np.any(self._spectrum > 0.01))

        # Smooth spectrum for ring
        for i in range(len(self._spectrum)):
            val = max(0.0, min(1.0, abs(float(self._spectrum[i]))))
            self._smooth[i] = self._smooth[i] * 0.82 + val * 0.18

        for i in range(segments):
            angle = (i / segments) * math.pi * 2 + math.pi * 2 * self._frame * 0.045

            if has_signal:
                idx = int(i / segments * len(self._spectrum))
                n = self._smooth[idx]
            else:
                n = math.sin(self._frame * 0.045 + i * 0.28) * 0.5 + math.sin(self._frame * 0.045 * 1.7 + i * 0.12) * 0.3

            length = 6 + abs(n) * 16
            x1 = cx + math.cos(angle) * base_r
            y1 = cy + math.sin(angle) * base_r
            x2 = cx + math.cos(angle) * (base_r + length)
            y2 = cy + math.sin(angle) * (base_r + length)

            painter.setPen(QPen(
                QColor(Color.ACCENT_SECONDARY) if i % 11 == 0 else QColor(79, 195, 247, int((0.35 + abs(n) * 0.5) * 255)),
                2.4,
            ))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        # ── Album art (circular with glow shadow) ─────────────────────
        art_size = 186
        art_rect = QRectF(cx - art_size // 2, cy - art_size // 2, art_size, art_size)

        # Outer drop-shadow glow (mockup: 0 20px 50px -12px rgba(30,136,229,0.45))
        shadow_glow = QRadialGradient(cx, cy + 20, art_size * 0.7)
        shadow_glow.setColorAt(0, QColor(30, 136, 229, 80))
        shadow_glow.setColorAt(1, QColor(30, 136, 229, 0))
        painter.setBrush(shadow_glow)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(cx - art_size * 0.5, cy - art_size * 0.3, art_size, art_size * 0.8))

        # Border ring (mockup: box-shadow 0 0 0 1px var(--border))
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

            # Center dot (mockup: ::before pseudo-element)
            painter.setBrush(QBrush(QColor(Color.BACKGROUND_DEEP)))
            painter.setPen(QPen(QColor(79, 195, 247, 36), 1))
            painter.drawEllipse(QRectF(cx - 28, cy - 28, 56, 56))
        else:
            # Gradient fallback when no artwork
            grad = QConicalGradient(cx, cy, 0)
            grad.setColorAt(0, QColor("#2E4A7D"))
            grad.setColorAt(1, QColor("#101B33"))
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(art_rect)

            painter.setBrush(QBrush(QColor(Color.BACKGROUND_DEEP)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(cx - 28, cy - 28, 56, 56))

        painter.end()
        self._frame += 1


class SpectrumBar(QWidget):
    """Horizontal spectrum visualizer bar with peak hold + smooth decay."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._spectrum: np.ndarray = np.zeros(64)
        self._smooth: np.ndarray = np.zeros(64)
        self._peak: np.ndarray = np.zeros(64)
        self._has_signal = False
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self.update)
        self._timer.start()

    def set_spectrum(self, data: np.ndarray) -> None:
        self._spectrum = data
        self._has_signal = bool(np.any(data > 0.01))

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        n = len(self._spectrum)
        if n == 0:
            return

        spacing = 3
        bar_w = max(2, (w - (n - 1) * spacing) / n)

        # Update smoothed values and peaks
        for i in range(n):
            if self._has_signal:
                target = max(0.0, min(1.0, abs(float(self._spectrum[i]))))
            else:
                base = math.sin(self._phase + i * 0.35) * 0.5 + 0.5
                noise = __import__('random').random() * 0.35
                target = min(1.0, base * 0.7 + noise)

            # Smooth decay toward target
            self._smooth[i] = self._smooth[i] * 0.82 + target * 0.18
            # Peak hold — stays until new peak or slow decay
            if target >= self._peak[i]:
                self._peak[i] = target
            else:
                self._peak[i] *= 0.94

        painter.setPen(Qt.NoPen)
        for i in range(n):
            bh = max(4, self._smooth[i] * h * 0.94)
            peak_h = max(4, self._peak[i] * h * 0.94)
            x = i * (bar_w + spacing)

            # Bar gradient (mockup: accent → primary 65% → rgba(30,136,229,0.25))
            gradient = QLinearGradient(0, h, 0, 0)
            gradient.setColorAt(0, QColor(Color.PRIMARY))
            gradient.setColorAt(0.65, QColor(Color.ACCENT))
            gradient.setColorAt(1, QColor(30, 136, 229, 64))
            painter.setBrush(QBrush(gradient))
            opacity = 0.55 + (bh / h) * 0.45
            painter.setOpacity(opacity)
            painter.drawRoundedRect(
                int(x), int(h - bh), int(bar_w), int(bh), 4, 4
            )

            # Peak dot
            painter.setOpacity(0.9)
            painter.setBrush(QBrush(QColor(Color.ACCENT_SECONDARY)))
            painter.drawRoundedRect(
                int(x), int(h - peak_h - 2), int(bar_w), 3, 2, 2
            )

        painter.setOpacity(1.0)
        self._phase += 0.09
        painter.end()
