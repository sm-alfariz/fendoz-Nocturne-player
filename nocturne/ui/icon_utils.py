# coding:utf-8
"""
icon_utils.py — Load PNG icons from resource/img/ as QPixmap/QIcon.

Icons are lazily loaded on first access (QPixmap requires QApplication).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon, QPixmap

ICON_DIR = Path(__file__).resolve().parent.parent.parent / "resource" / "img"

_cache: dict[str, QPixmap] = {}


def pixmap(name: str) -> QPixmap:
    """Load a PNG from resource/img/ and return a QPixmap (cached)."""
    if name not in _cache:
        _cache[name] = QPixmap(str(ICON_DIR / name))
    return _cache[name]


def icon(name: str) -> QIcon:
    """Load a PNG from resource/img/ and return a QIcon."""
    return QIcon(str(ICON_DIR / name))


def pixmap_scaled(name: str, w: int, h: int) -> QPixmap:
    """Load and scale a PNG icon."""
    from PySide6.QtCore import Qt
    return pixmap(name).scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
