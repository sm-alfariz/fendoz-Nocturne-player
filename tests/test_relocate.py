# coding:utf-8
"""Test relocate.py — batch path update."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from nocturne.data.relocate import relocate_folder


class TestRelocateFolder:
    def test_updates_paths(self, tmp_path: Path) -> None:
        """Create actual files at new location, verify paths are rewritten."""
        old = tmp_path / "old_music"
        new = tmp_path / "new_music"
        old.mkdir()
        new.mkdir()

        # Create a real file at new location
        (new / "song.mp3").write_text("dummy")
        (new / "sub").mkdir()
        (new / "sub" / "track.mp3").write_text("dummy")

        conn = sqlite3.connect(str(tmp_path / "test.db"))
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY,
                path TEXT,
                source_type TEXT DEFAULT 'local'
            );
        """)
        conn.execute("INSERT INTO tracks (path, source_type) VALUES (?, 'local')",
                     (str(old / "song.mp3"),))
        conn.execute("INSERT INTO tracks (path, source_type) VALUES (?, 'local')",
                     (str(old / "sub" / "track.mp3"),))
        conn.commit()

        result = relocate_folder(str(old), str(new), conn=conn)
        assert result["total"] == 2
        assert result["updated"] == 2
        assert result["not_found"] == 0

        rows = conn.execute("SELECT path FROM tracks ORDER BY id").fetchall()
        assert rows[0][0] == str(new / "song.mp3")
        assert rows[1][0] == str(new / "sub" / "track.mp3")

    def test_skips_non_local_tracks(self, tmp_path: Path) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE tracks (id INTEGER PRIMARY KEY, path TEXT, source_type TEXT)")
        conn.execute("INSERT INTO tracks (path, source_type) VALUES (?, 'soundcloud')",
                     ("/old/sc.mp3",))
        conn.commit()

        result = relocate_folder("/old", "/new", conn=conn)
        # Total is 0 because query filters to source_type='local'
        assert result["total"] == 0
        assert result["updated"] == 0

    def test_reports_not_found(self, tmp_path: Path) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE tracks (id INTEGER PRIMARY KEY, path TEXT, source_type TEXT)")
        conn.execute("INSERT INTO tracks (path, source_type) VALUES (?, 'local')",
                     ("/nonexistent/song.mp3",))
        conn.commit()

        result = relocate_folder("/nonexistent", "/also_missing", conn=conn)
        assert result["not_found"] == 1
        assert result["updated"] == 0
        assert len(result["errors"]) == 1
