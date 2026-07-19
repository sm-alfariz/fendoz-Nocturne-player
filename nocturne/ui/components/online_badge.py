# coding:utf-8
"""
online_badge.py — Small "Online" badge widget for SoundCloud tracks.

Design: border tipis accent, teks mono kecil.  (08-design-system.md)
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from nocturne.ui.theme.tokens import Color


class OnlineBadge(QLabel):
    """Badge indicating a track is from an online source."""

    def __init__(self, parent=None) -> None:
        super().__init__("Online", parent)
        self.setStyleSheet(
            f"border: 1px solid {Color.ACCENT}; "
            f"color: {Color.ACCENT}; "
            "font-family: 'JetBrains Mono'; font-size: 10px; "
            "padding: 1px 6px; border-radius: 8px;"
        )
        self.setFixedHeight(18)
