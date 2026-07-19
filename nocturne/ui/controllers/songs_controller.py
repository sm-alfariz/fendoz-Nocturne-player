# coding:utf-8
"""
songs_controller.py — Business logic for the Songs list view.
"""

from __future__ import annotations

from PySide6.QtCore import Signal

from nocturne.data.db import get_connection
from nocturne.data.models import Track
from nocturne.ui.controllers.base import Controller


class SongsController(Controller):
    """Handles track querying for SongsView."""

    track_activated = Signal(object)  # Track

    def load_tracks(self) -> list[Track]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT t.*, a.title AS album_title FROM tracks t "
            "LEFT JOIN albums a ON t.album_id = a.id "
            "ORDER BY t.added_at DESC"
        ).fetchall()
        return [Track.from_row(r) for r in rows]
