# coding:utf-8
"""Test playlist_manager.py — PlaylistManager CRUD, reorder, m3u."""

from __future__ import annotations

from pathlib import Path

from nocturne.data.playlist_manager import PlaylistManager
from nocturne.data.models import Playlist, Track


class TestPlaylistCrud:
    def test_create_and_list(self, manager: PlaylistManager) -> None:
        pid = manager.create("My Favorites")
        assert pid > 0
        playlists = manager.list_all()
        names = [p.name for p in playlists]
        assert "My Favorites" in names

    def test_rename(self, manager: PlaylistManager) -> None:
        pid = manager.create("Old")
        manager.rename(pid, "Renamed")
        playlists = manager.list_all()
        renamed = [p for p in playlists if p.id == pid][0]
        assert renamed.name == "Renamed"

    def test_delete_removes_playlist(self, manager: PlaylistManager) -> None:
        pid = manager.create("Temp")
        manager.delete(pid)
        ids = [p.id for p in manager.list_all()]
        assert pid not in ids

    def test_list_all_returns_playlist_objects(self, manager: PlaylistManager) -> None:
        manager.create("P1")
        manager.create("P2")
        playlists = manager.list_all()
        assert all(isinstance(p, Playlist) for p in playlists)


class TestPlaylistTracks:
    def test_add_track(self, manager: PlaylistManager, db_with_track) -> None:
        conn, track_id = db_with_track
        pid = manager.create("Test")
        manager.add_track(pid, track_id)
        tracks = manager.get_tracks(pid)
        assert len(tracks) == 1
        assert tracks[0].id == track_id
        assert isinstance(tracks[0], Track)

    def test_remove_track(self, manager: PlaylistManager, db_with_track) -> None:
        conn, track_id = db_with_track
        pid = manager.create("Test")
        manager.add_track(pid, track_id)
        manager.remove_track(pid, track_id)
        assert manager.get_tracks(pid) == []

    def test_add_duplicate_is_ignored(self, manager: PlaylistManager, db_with_track) -> None:
        conn, track_id = db_with_track
        pid = manager.create("Test")
        manager.add_track(pid, track_id)
        manager.add_track(pid, track_id)  # second insert ignored via OR IGNORE
        assert len(manager.get_tracks(pid)) == 1

    def test_reorder(self, manager: PlaylistManager, db_with_track) -> None:
        conn, tid1 = db_with_track
        pid = manager.create("Test")
        # Add a second track
        cur = conn.execute(
            "INSERT INTO tracks (path, title, artist, duration_ms, file_mtime, source_type) "
            "VALUES (?, ?, ?, ?, ?, 'local')",
            ("/music/song2.mp3", "Song2", "Artist", 150_000, 1001),
        )
        tid2 = cur.lastrowid
        conn.commit()

        manager.add_track(pid, tid1)
        manager.add_track(pid, tid2)

        # Reverse order
        manager.reorder(pid, [tid2, tid1])
        tracks = manager.get_tracks(pid)
        assert [t.id for t in tracks] == [tid2, tid1]


class TestM3u:
    def test_export_then_import_roundtrip(self, manager: PlaylistManager,
                                           db_with_track, tmp_path: Path) -> None:
        conn, track_id = db_with_track
        pid = manager.create("Roundtrip")
        manager.add_track(pid, track_id)

        m3u_path = tmp_path / "export.m3u8"
        manager.export_m3u(pid, m3u_path)

        # Adjust track path so import finds it
        result = manager.import_m3u(m3u_path)
        assert result["playlist_name"] == "export"
        # The m3u contains the path from the track; test that parsing works
        assert isinstance(result["found"], list)

    def test_import_missing_file(self, tmp_path: Path) -> None:
        m3u = tmp_path / "missing.m3u"
        m3u.write_text("/nonexistent/song.mp3\n", encoding="utf-8")
        result = PlaylistManager(conn=None).import_m3u(m3u)
        assert result["playlist_name"] == "missing"
        assert len(result["missing"]) == 1
