# coding:utf-8
"""
relocate.py — Batch-update track paths when the music folder is moved.

FR-8.1: Batch UPDATE tracks.path via REPLACE, validate files exist first,
preserve playlist_items references.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from nocturne.data.db import get_connection


def relocate_folder(
    old_prefix: str,
    new_prefix: str,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """Update all track paths from old_prefix to new_prefix.

    Returns dict with keys:
      - total: number of tracks affected
      - updated: number successfully updated
      - not_found: number of files that don't exist at the new path
      - errors: list[str] of per-track error messages

    Validates each file exists at the new path before committing.
    Skips non-local tracks (source_type != 'local').
    """
    if conn is None:
        conn = get_connection()

    old_prefix_norm = Path(old_prefix).as_posix() + "/"
    new_prefix_norm = Path(new_prefix).as_posix() + "/"

    rows = conn.execute(
        "SELECT id, path FROM tracks WHERE source_type = 'local' AND path IS NOT NULL"
    ).fetchall()

    result: dict = {"total": len(rows), "updated": 0, "not_found": 0, "errors": []}
    updates: list[tuple[str, int]] = []

    for row in rows:
        track_id = row[0]
        old_path = row[1]

        if not old_path.startswith(old_prefix_norm):
            continue

        new_path = old_path.replace(old_prefix_norm, new_prefix_norm, 1)

        if not Path(new_path).exists():
            result["not_found"] += 1
            result["errors"].append(f"Not found: {new_path}")
            continue

        updates.append((new_path, track_id))

    if updates:
        conn.executemany(
            "UPDATE tracks SET path = ? WHERE id = ?", updates
        )
        conn.commit()

    result["updated"] = len(updates)
    return result
