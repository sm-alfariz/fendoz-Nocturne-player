# coding:utf-8
"""
db.py — SQLite initialisation, migrations, and connection management.

Schema follows 06-database-schema.md (normalised: albums separate from tracks).
Migration versioning via PRAGMA user_version.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS albums (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    artist TEXT,
    artwork_blob BLOB
);

CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY,
    path TEXT,
    title TEXT NOT NULL,
    artist TEXT,
    album_id INTEGER REFERENCES albums(id),
    duration_ms INTEGER,
    file_mtime INTEGER,
    source_type TEXT CHECK(source_type IN ('local','soundcloud')) DEFAULT 'local',
    source_url TEXT,
    cached_path TEXT,
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS playlist_items (
    playlist_id INTEGER REFERENCES playlists(id) ON DELETE CASCADE,
    track_id INTEGER REFERENCES tracks(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    PRIMARY KEY (playlist_id, track_id)
);

CREATE TABLE IF NOT EXISTS eq_presets (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    band_values_json TEXT NOT NULL,
    is_custom BOOLEAN DEFAULT 1
);

CREATE TABLE IF NOT EXISTS lyrics (
    track_id INTEGER PRIMARY KEY REFERENCES tracks(id) ON DELETE CASCADE,
    lrc_content TEXT,
    offset_ms INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS play_history (
    id INTEGER PRIMARY KEY,
    track_id INTEGER REFERENCES tracks(id) ON DELETE CASCADE,
    played_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    duration_played_ms INTEGER
);
"""

INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_tracks_artist_album ON tracks(artist, album_id);",
    "CREATE INDEX IF NOT EXISTS idx_tracks_file_mtime ON tracks(file_mtime);",
    "CREATE INDEX IF NOT EXISTS idx_playlist_items_order ON playlist_items(playlist_id, position);",
]


def get_db_path() -> Path:
    """Return platform-appropriate path for the local database file."""
    import platform
    home = Path.home()
    if platform.system() == "Windows":
        base = Path.home() / "AppData" / "Local" / "Nocturne"
    elif platform.system() == "Darwin":
        base = home / "Library" / "Application Support" / "Nocturne"
    else:
        base = home / ".local" / "share" / "nocturne"
    base.mkdir(parents=True, exist_ok=True)
    return base / "nocturne.db"


def init_db(db_path: str | Path) -> sqlite3.Connection:
    """Create / migrate schema and return a connection with WAL mode."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")

    current_version = conn.execute("PRAGMA user_version").fetchone()[0]
    migrate(conn, current_version)
    return conn


def migrate(conn: sqlite3.Connection, current_version: int) -> None:
    """Run incremental migrations keyed by PRAGMA user_version."""
    target = 1  # bump each time schema changes

    if current_version < 1:
        # v1: initial schema
        conn.executescript(SCHEMA_SQL)
        for idx in INDEXES_SQL:
            conn.execute(idx)
        conn.execute(f"PRAGMA user_version = {target}")
        conn.commit()

    # future: elif current_version < 2: ...


def get_connection() -> sqlite3.Connection:
    """Return a connection with Row factory (call from main thread only).

    For worker threads, create a separate connection with ``check_same_thread=False``.
    """
    conn = init_db(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn
