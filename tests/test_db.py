# coding:utf-8
"""Test db.py — schema init, migrations, upsert_sc_track."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from nocturne.data.db import get_db_path, init_db, migrate, upsert_sc_track


class TestInitDb:
    def test_creates_tables(self, tmp_path: Path) -> None:
        path = tmp_path / "nocturne.db"
        conn = init_db(path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = {r[0] for r in tables}
        assert "tracks" in names
        assert "albums" in names
        assert "playlists" in names
        assert "playlist_items" in names
        assert "eq_presets" in names
        assert "lyrics" in names
        assert "play_history" in names
        conn.close()

    def test_wal_mode(self, tmp_path: Path) -> None:
        conn = init_db(tmp_path / "n.db")
        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert journal == "wal"
        conn.close()

    def test_foreign_keys_on(self, tmp_path: Path) -> None:
        conn = init_db(tmp_path / "n.db")
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        conn.close()

    def test_user_version(self, tmp_path: Path) -> None:
        conn = init_db(tmp_path / "n.db")
        ver = conn.execute("PRAGMA user_version").fetchone()[0]
        assert ver >= 2
        conn.close()

    def test_migrate_from_v0(self, tmp_path: Path) -> None:
        """Fresh DB already runs migrations; test migrate() independently."""
        path = tmp_path / "n.db"
        conn = sqlite3.connect(str(path))
        conn.execute("PRAGMA user_version = 0")
        migrate(conn, 0)
        ver = conn.execute("PRAGMA user_version").fetchone()[0]
        assert ver == 2
        conn.close()

    def test_get_db_path(self) -> None:
        p = get_db_path()
        assert isinstance(p, Path)
        assert p.name == "nocturne.db"


class TestUpsertScTrack:
    def test_inserts_new_track(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Patch get_connection to use our temp DB."""
        import sqlite3
        from nocturne.data import db as db_module
        test_conn = init_db(tmp_path / "sc.db")
        test_conn.row_factory = sqlite3.Row
        monkeypatch.setattr(db_module, "get_connection", lambda: test_conn)

        data = {
            "stream_url": "https://stream.url/1",
            "title": "SC Track",
            "artist": "SC Artist",
            "duration_ms": 180_000,
            "source_url": "https://sc.com/t/1",
        }
        track = upsert_sc_track(data)
        assert track.title == "SC Track"
        assert track.source_type == "soundcloud"
        assert track.id > 0
        test_conn.close()

    def test_updates_existing_track(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from nocturne.data import db as db_module
        test_conn = init_db(tmp_path / "sc2.db")
        test_conn.row_factory = sqlite3.Row
        monkeypatch.setattr(db_module, "get_connection", lambda: test_conn)

        data = {
            "stream_url": "https://stream.url/old",
            "title": "Original",
            "artist": "A",
            "duration_ms": 100_000,
            "source_url": "https://sc.com/t/2",
        }
        track_a = upsert_sc_track(data)
        assert track_a.title == "Original"

        # Same source_url, new stream_url
        data["stream_url"] = "https://stream.url/new"
        data["title"] = "Updated"
        track_b = upsert_sc_track(data)
        assert track_b.title == "Original"  # title NOT updated by upsert
        assert track_b.path == "https://stream.url/new"  # path (stream_url) IS updated
        test_conn.close()
