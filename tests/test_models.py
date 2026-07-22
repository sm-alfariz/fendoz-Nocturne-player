# coding:utf-8
"""Test models.py — Track, Album, Playlist, EQPreset dataclass factories."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from nocturne.data.models import Album, EQPreset, Playlist, Track


def make_row(d: dict) -> sqlite3.Row:
    """Build a sqlite3.Row mock from a dict with proper types.

    Uses INTEGER for int values and TEXT for str/None values so that
    Track.from_row() receives correct Python types.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cols = []
    typed_vals = []
    for k, v in d.items():
        if isinstance(v, int):
            cols.append(f"{k} INTEGER")
        elif isinstance(v, str):
            cols.append(f"{k} TEXT")
        else:
            cols.append(k)
        typed_vals.append(v)
    conn.execute(f"CREATE TABLE _x ({', '.join(cols)})")
    conn.execute(f"INSERT INTO _x VALUES ({', '.join('?' for _ in typed_vals)})", typed_vals)
    return conn.execute("SELECT * FROM _x").fetchone()


class TestTrack:
    def test_from_row_known_fields(self) -> None:
        row = make_row({"id": 1, "title": "Song", "artist": "A", "duration_ms": 180_000, "source_type": "local"})
        track = Track.from_row(row)
        assert track.id == 1
        assert track.title == "Song"
        assert track.artist == "A"
        assert track.duration_ms == 180_000
        assert track.source_type == "local"

    def test_from_row_ignores_unknown_columns(self) -> None:
        row = make_row({"id": 1, "title": "Song", "bogus_col": "x", "another": "y"})
        track = Track.from_row(row)
        assert track.id == 1
        assert track.title == "Song"
        assert not hasattr(track, "bogus_col")

    def test_from_sc_dict(self) -> None:
        data = {"title": "SC Song", "artist": "SC Artist", "duration_ms": 240_000, "stream_url": "https://...", "source_url": "https://sc.com/t/1"}
        track = Track.from_sc_dict(data)
        assert track.title == "SC Song"
        assert track.artist == "SC Artist"
        assert track.duration_ms == 240_000
        assert track.source_type == "soundcloud"
        assert track.source_url == "https://sc.com/t/1"
        assert track.path == "https://..."

    def test_default_source_type_is_local(self) -> None:
        t = Track()
        assert t.source_type == "local"

    def test_from_sc_dict_defaults(self) -> None:
        track = Track.from_sc_dict({})
        assert track.title == ""
        assert track.artist is None
        assert track.duration_ms == 0
        assert track.source_type == "soundcloud"


class TestAlbum:
    def test_from_row(self) -> None:
        row = make_row({"id": 10, "title": "Album", "artist": "A"})
        album = Album.from_row(row)
        assert album.id == 10
        assert album.title == "Album"
        assert album.artist == "A"


class TestPlaylist:
    def test_from_row(self) -> None:
        row = make_row({"id": 5, "name": "My Playlist", "created_at": "2025-01-15 10:00:00"})
        pl = Playlist.from_row(row)
        assert pl.id == 5
        assert pl.name == "My Playlist"
        assert isinstance(pl.created_at, datetime)

    def test_from_row_parses_iso_datetime(self) -> None:
        row = make_row({"id": 1, "name": "P", "created_at": "2025-06-01T12:00:00"})
        pl = Playlist.from_row(row)
        assert pl.created_at.year == 2025


class TestEQPreset:
    def test_from_row(self) -> None:
        row = make_row({"id": 1, "name": "Custom", "band_values_json": "[1.0,2.0,3.0,0,0,0,0,0,0,0]", "is_custom": 1})
        preset = EQPreset.from_row(row)
        assert preset.id == 1
        assert preset.name == "Custom"
        assert preset.band_values == [1.0, 2.0, 3.0, 0, 0, 0, 0, 0, 0, 0]
        assert preset.is_custom is True
