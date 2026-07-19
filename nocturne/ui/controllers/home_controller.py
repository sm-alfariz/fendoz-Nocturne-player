# coding:utf-8
"""
home_controller.py — Business logic for the Home dashboard.
"""

from __future__ import annotations

import sqlite3
from typing import Optional


from nocturne.data.db import get_connection
from nocturne.data.models import Track
from nocturne.ui.controllers.base import Controller


class HomeController(Controller):
    """Handles data loading for HomeInterface."""

    def get_continue_listening(self, limit: int = 5) -> list[tuple[int, str, str]]:
        conn = get_connection()
        return conn.execute(
            "SELECT DISTINCT t.id, t.title, t.artist "
            "FROM play_history ph "
            "JOIN tracks t ON t.id = ph.track_id "
            "ORDER BY ph.played_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def get_playlists_preview(self, limit: int = 6) -> list[tuple[int, str]]:
        conn = get_connection()
        return conn.execute(
            "SELECT id, name FROM playlists ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def get_track_by_id(self, track_id: int) -> Optional[Track]:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM tracks WHERE id = ?", (track_id,)
        ).fetchone()
        return Track.from_row(row) if row else None
