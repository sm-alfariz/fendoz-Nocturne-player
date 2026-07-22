# coding:utf-8
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from nocturne.data.db import init_db  # noqa: E402
from nocturne.data.playlist_manager import PlaylistManager  # noqa: E402


@pytest.fixture
def tmp_db(tmp_path: Path) -> sqlite3.Connection:
    """Return a fresh in-memory or temp-file DB with migrated schema."""
    path = tmp_path / "test.db"
    conn = init_db(path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def db_with_track(tmp_db: sqlite3.Connection) -> tuple[sqlite3.Connection, int]:
    """Seed one album + one track, return (conn, track_id)."""
    cur = tmp_db.execute(
        "INSERT INTO albums (title, artist) VALUES (?, ?)",
        ("Test Album", "Test Artist"),
    )
    album_id = cur.lastrowid
    cur = tmp_db.execute(
        "INSERT INTO tracks (path, title, artist, album_id, duration_ms, file_mtime, source_type) "
        "VALUES (?, ?, ?, ?, ?, ?, 'local')",
        ("/music/song.mp3", "Test Song", "Test Artist", album_id, 200_000, 1000),
    )
    track_id = cur.lastrowid
    tmp_db.commit()
    return tmp_db, track_id


@pytest.fixture
def manager(tmp_db: sqlite3.Connection) -> PlaylistManager:
    """Return a PlaylistManager bound to the temp DB."""
    return PlaylistManager(conn=tmp_db)
