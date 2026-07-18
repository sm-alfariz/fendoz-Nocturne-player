# coding:utf-8
"""
lyrics_online.py — Online lyrics lookup via LrcLib API (FR-5.2).

Level 4 in lyrics hierarchy: when SYLT, .lrc sidecar, and DB cache all
fail, query LrcLib (https://lrclib.net) — free, no auth, returns LRC.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

LRCLIB_API = "https://lrclib.net/api/get"


def fetch_lyrics_online(artist: str | None, title: str) -> str | None:
    """Query LrcLib for synced lyrics by artist + track title.

    Returns LRC-formatted string, or None on failure.
    """
    if not title:
        return None

    import httpx

    try:
        resp = httpx.get(
            LRCLIB_API,
            params={"artist_name": artist or "", "track_name": title},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        synced = data.get("syncedLyrics") or data.get("plainLyrics")
        if synced:
            return synced
        logger.info("No lyrics found on LrcLib for %s - %s", artist, title)
        return None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.info("LrcLib returned 404 for %s - %s", artist, title)
        else:
            logger.warning("LrcLib error %s: %s", e.response.status_code, e)
        return None
    except Exception as e:
        logger.warning("LrcLib request failed: %s", e)
        return None
