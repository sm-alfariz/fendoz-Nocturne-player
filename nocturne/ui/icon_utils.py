# coding:utf-8
"""
icon_utils.py — Load PNG icons from resource/img/ as QPixmap/QIcon.

Icons are lazily loaded on first access (QPixmap requires QApplication).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap

ICON_DIR = Path(__file__).resolve().parent.parent.parent / "resource" / "img"

_cache: dict[str, QPixmap] = {}
_icon_cache: dict[str, QIcon] = {}
_artwork_cache: dict[tuple[int, int], QPixmap] = {}  # (album_id, size) → scaled artwork


def pixmap(name: str) -> QPixmap:
    """Load a PNG from resource/img/ and return a QPixmap (cached)."""
    if name not in _cache:
        _cache[name] = QPixmap(str(ICON_DIR / name))
    return _cache[name]


def icon(name: str) -> QIcon:
    """Load a PNG from resource/img/ and return a QIcon (cached)."""
    if name not in _icon_cache:
        _icon_cache[name] = QIcon(str(ICON_DIR / name))
    return _icon_cache[name]


def pixmap_scaled(name: str, w: int, h: int) -> QPixmap:
    """Load and scale a PNG icon."""
    return pixmap(name).scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def artwork_pixmap(album_id: int, blob: bytes, size: int = 140) -> QPixmap | None:
    """Decode artwork blob into a scaled QPixmap, keyed by (album_id, size) (cached)."""
    key = (album_id, size)
    if key in _artwork_cache:
        return _artwork_cache[key]
    px = QPixmap()
    if not px.loadFromData(blob):
        return None
    scaled = px.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    _artwork_cache[key] = scaled
    return scaled


def invalidate_artwork_cache(album_id: int) -> None:
    """Remove all scaled variants for album_id (call after artwork update)."""
    keys = [k for k in _artwork_cache if k[0] == album_id]
    for k in keys:
        del _artwork_cache[k]
