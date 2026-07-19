# coding:utf-8
"""
albums_controller.py — Business logic for the Albums view.
"""

from __future__ import annotations


from nocturne.data.db import get_connection
from nocturne.ui.controllers.base import Controller


class AlbumsController(Controller):
    """Handles album data loading for AlbumsView."""

    def load_albums(self, filter_text: str = "") -> list[tuple]:
        conn = get_connection()
        query = (
            "SELECT a.id, a.title, a.artist, a.artwork_blob, COUNT(t.id) as cnt "
            "FROM albums a LEFT JOIN tracks t ON t.album_id = a.id "
        )
        params: list[str] = []
        if filter_text:
            query += "WHERE a.title LIKE ? "
            params.append(f"%{filter_text}%")
        query += "GROUP BY a.id ORDER BY a.title"
        return conn.execute(query, params).fetchall()
