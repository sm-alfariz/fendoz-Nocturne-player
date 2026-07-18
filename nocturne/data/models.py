# coding:utf-8
"""
models.py — Dataclass / Pydantic models for domain entities.

Maps SQL rows to Python objects explicitly (no heavy ORM).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Track:
    id: int = 0
    path: Optional[str] = None
    title: str = ""
    artist: Optional[str] = None
    album_id: Optional[int] = None
    duration_ms: int = 0
    file_mtime: int = 0
    source_type: str = "local"  # 'local' | 'soundcloud'
    source_url: Optional[str] = None
    cached_path: Optional[str] = None
    added_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Track":
        keys = row.keys()
        vals = [row[k] for k in keys]
        return cls(**dict(zip(keys, vals)))


@dataclass
class Album:
    id: int = 0
    title: str = ""
    artist: Optional[str] = None
    artwork_blob: Optional[bytes] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Album":
        return cls(**dict(row))


@dataclass
class Playlist:
    id: int = 0
    name: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    tracks: list[Track] = field(default_factory=list)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Playlist":
        return cls(id=row["id"], name=row["name"],
                   created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"])


@dataclass
class EQPreset:
    id: int = 0
    name: str = ""
    band_values: list[float] = field(default_factory=lambda: [0.0] * 10)
    is_custom: bool = True

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "EQPreset":
        import json
        return cls(
            id=row["id"],
            name=row["name"],
            band_values=json.loads(row["band_values_json"]),
            is_custom=bool(row["is_custom"]),
        )
