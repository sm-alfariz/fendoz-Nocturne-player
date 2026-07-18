# coding:utf-8
"""
playlist_manager.py — CRUD, drag-reorder, and .m3u/.m3u8 import/export.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional

from nocturne.data.db import get_connection
from nocturne.data.models import Playlist, Track


class PlaylistManager:
    """Playlist CRUD + reorder + .m3u import/export."""

    def __init__(self, conn: Optional[sqlite3.Connection] = None) -> None:
        self._conn = conn or get_connection()
        self._conn.row_factory = sqlite3.Row

    # ── CRUD ──────────────────────────────────────────────────────────

    def create(self, name: str) -> int:
        cursor = self._conn.execute(
            "INSERT INTO playlists (name) VALUES (?)", (name,)
        )
        self._conn.commit()
        return cursor.lastrowid

    def rename(self, playlist_id: int, new_name: str) -> None:
        self._conn.execute(
            "UPDATE playlists SET name = ? WHERE id = ?",
            (new_name, playlist_id),
        )
        self._conn.commit()

    def delete(self, playlist_id: int) -> None:
        self._conn.execute(
            "DELETE FROM playlist_items WHERE playlist_id = ?", (playlist_id,)
        )
        self._conn.execute(
            "DELETE FROM playlists WHERE id = ?", (playlist_id,)
        )
        self._conn.commit()

    def list_all(self) -> list[Playlist]:
        rows = self._conn.execute(
            "SELECT * FROM playlists ORDER BY created_at DESC"
        ).fetchall()
        return [Playlist.from_row(r) for r in rows]

    def get_tracks(self, playlist_id: int) -> list[Track]:
        rows = self._conn.execute(
            """SELECT t.* FROM tracks t
               JOIN playlist_items pi ON t.id = pi.track_id
               WHERE pi.playlist_id = ?
               ORDER BY pi.position""",
            (playlist_id,),
        ).fetchall()
        return [Track.from_row(r) for r in rows]

    # ── Track operations ──────────────────────────────────────────────

    def add_track(self, playlist_id: int, track_id: int) -> None:
        max_pos = self._conn.execute(
            "SELECT COALESCE(MAX(position), -1) FROM playlist_items WHERE playlist_id = ?",
            (playlist_id,),
        ).fetchone()[0]
        self._conn.execute(
            "INSERT OR IGNORE INTO playlist_items (playlist_id, track_id, position) VALUES (?, ?, ?)",
            (playlist_id, track_id, max_pos + 1),
        )
        self._conn.commit()

    def remove_track(self, playlist_id: int, track_id: int) -> None:
        self._conn.execute(
            "DELETE FROM playlist_items WHERE playlist_id = ? AND track_id = ?",
            (playlist_id, track_id),
        )
        self._conn.commit()

    def reorder(self, playlist_id: int, track_ids: list[int]) -> None:
        """Update positions to match the given track_id order."""
        self._conn.executemany(
            "UPDATE playlist_items SET position = ? WHERE playlist_id = ? AND track_id = ?",
            [(pos, playlist_id, tid) for pos, tid in enumerate(track_ids)],
        )
        self._conn.commit()

    # ── .m3u import / export ──────────────────────────────────────────

    def import_m3u(self, path: str | Path) -> dict:
        """Import an .m3u/.m3u8 file.

        Returns dict with keys:
          - playlist_name: str
          - found: list[Track]
          - missing: list[str]  (paths in the .m3u that couldn't be resolved)
        """
        path = Path(path)
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        base = path.parent

        entries: list[str] = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            entries.append(line)

        found: list[Track] = []
        missing: list[str] = []

        conn = get_connection()
        conn.row_factory = sqlite3.Row

        for entry in entries:
            # Try absolute first, then relative to .m3u location
            candidates = [Path(entry)]
            if not candidates[0].is_absolute():
                candidates.append(base / entry)
            resolved = None
            for c in candidates:
                if c.exists():
                    resolved = str(c.resolve())
                    break
            if resolved:
                row = conn.execute(
                    "SELECT * FROM tracks WHERE path = ?", (resolved,)
                ).fetchone()
                if row:
                    found.append(Track.from_row(row))
                    continue
            missing.append(entry)

        return {"playlist_name": path.stem, "found": found, "missing": missing}

    def export_m3u(self, playlist_id: int, output_path: str | Path) -> None:
        """Export a playlist to .m3u8 format."""
        tracks = self.get_tracks(playlist_id)
        lines = ["#EXTM3U"]
        for t in tracks:
            lines.append(f"#EXTINF:{t.duration_ms},{t.artist or ''} - {t.title}")
            lines.append(t.path or "")
        Path(output_path).write_text("\n".join(lines), encoding="utf-8")
