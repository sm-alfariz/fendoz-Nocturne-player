# coding:utf-8
"""
resolver.py — SoundCloud URL resolution, streaming, and search.

Public interface:
- resolve_url(url) -> Track metadata
- get_stream(url) -> stream URL
- search(query) -> list[Track]
"""

from __future__ import annotations


def resolve_url(url: str) -> dict | None:
    """Resolve a SoundCloud URL → track metadata dict (or None)."""
    ...


def get_stream(url: str) -> str | None:
    """Return direct audio stream URL for a resolved track."""
    ...


def search(query: str) -> list[dict]:
    """Search SoundCloud → list of track metadata dicts."""
    ...
