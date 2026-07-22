# coding:utf-8
from __future__ import annotations

"""
db.py — SQLite initialisation, migrations, and connection management.

Schema follows 06-database-schema.md (normalised: albums separate from tracks).
Migration versioning via PRAGMA user_version.
"""

import sqlite3  # noqa: E402
from pathlib import Path  # noqa: E402


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

    if current_version < 1:
        # v1: initial schema
        conn.executescript(SCHEMA_SQL)
        for idx in INDEXES_SQL:
            conn.execute(idx)
        conn.execute("PRAGMA user_version = 1")
        conn.commit()

    if current_version < 2:
        # v2: eq_preset column per track (FR-3.3)
        conn.execute("ALTER TABLE tracks ADD COLUMN eq_preset TEXT DEFAULT NULL")
        conn.execute("PRAGMA user_version = 2")
        conn.commit()

    if current_version < 3:
        # v3: app_settings key-value table for global preferences
        conn.executescript(
            "CREATE TABLE IF NOT EXISTS app_settings ("
            "  key TEXT PRIMARY KEY,"
            "  value TEXT NOT NULL"
            ");"
        )
        conn.execute("PRAGMA user_version = 3")
        conn.commit()


def get_connection() -> sqlite3.Connection:
    """Return a connection with Row factory (call from main thread only).

    For worker threads, create a separate connection with ``check_same_thread=False``.
    """
    conn = init_db(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def upsert_sc_track(data: dict):
    """Insert or update a SoundCloud track in the database.

    Deduplicates by source_url (SoundCloud permalink is stable).
    Returns a Track model.
    """
    from nocturne.data.models import Track

    conn = get_connection()
    existing = conn.execute(
        "SELECT * FROM tracks WHERE source_url = ?", (data.get("source_url"),)
    ).fetchone()

    if existing:
        stream_url = data.get("stream_url")
        if stream_url:
            conn.execute(
                "UPDATE tracks SET path = ? WHERE source_url = ?",
                (stream_url, data.get("source_url")),
            )
            conn.commit()
        track = Track.from_row(
            conn.execute(
                "SELECT * FROM tracks WHERE source_url = ?", (data.get("source_url"),)
            ).fetchone()
        )
    else:
        cursor = conn.execute(
            """INSERT INTO tracks (path, title, artist, duration_ms, source_type, source_url)
               VALUES (?, ?, ?, ?, 'soundcloud', ?)""",
            (
                data.get("stream_url"),
                data.get("title", ""),
                data.get("artist"),
                data.get("duration_ms", 0),
                data.get("source_url"),
            ),
        )
        conn.commit()
        track_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
        track = Track.from_row(row)

    return track
