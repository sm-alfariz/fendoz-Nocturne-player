# coding:utf-8
"""
artists_controller.py — Business logic for the Artists view.
"""

from __future__ import annotations


from nocturne.data.db import get_connection
from nocturne.ui.controllers.base import Controller


class ArtistsController(Controller):
    """Handles artist data loading for ArtistsView."""

    def load_artists(self, filter_text: str = "") -> list[tuple[str, int]]:
        conn = get_connection()
        query = (
            "SELECT artist, COUNT(*) as cnt FROM tracks "
            "WHERE artist IS NOT NULL AND artist != '' "
        )
        params: list[str] = []
        if filter_text:
            query += "AND artist LIKE ? "
            params.append(f"%{filter_text}%")
        query += "GROUP BY artist ORDER BY artist"
        return conn.execute(query, params).fetchall()
