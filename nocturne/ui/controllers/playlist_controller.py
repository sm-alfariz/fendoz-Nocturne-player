# coding:utf-8
"""
playlist_controller.py — Business logic for the Playlist views.
"""

from __future__ import annotations


from PySide6.QtCore import Signal

from nocturne.data.models import Track
from nocturne.data.playlist_manager import PlaylistManager
from nocturne.ui.controllers.base import Controller


class PlaylistController(Controller):
    """Handles playlist CRUD and data loading."""

    track_activated = Signal(object)  # Track

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pm = PlaylistManager()

    def list_all(self):
        return self._pm.list_all()

    def create(self, name: str) -> int:
        return self._pm.create(name)

    def delete(self, playlist_id: int) -> None:
        self._pm.delete(playlist_id)

    def get_name(self, playlist_id: int) -> str:
        playlists = self._pm.list_all()
        return next(
            (p.name for p in playlists if p.id == playlist_id), "Playlist"
        )

    def get_tracks(self, playlist_id: int) -> list[Track]:
        return self._pm.get_tracks(playlist_id)

    def import_m3u(self, path: str) -> dict:
        return self._pm.import_m3u(path)

    def export_m3u(self, playlist_id: int, output_path: str) -> None:
        self._pm.export_m3u(playlist_id, output_path)

    def remove_track(self, playlist_id: int, track_id: int) -> None:
        self._pm.remove_track(playlist_id, track_id)

    def reorder_tracks(self, playlist_id: int, track_ids: list[int]) -> None:
        self._pm.reorder(playlist_id, track_ids)
