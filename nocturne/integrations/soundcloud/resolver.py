# coding:utf-8
"""
resolver.py — SoundCloud URL resolution, streaming, and search.

Modul terisolasi — tidak boleh diimpor langsung oleh core/player_engine.py.
Komunikasi lewat interface/event agar perubahan API pihak ketiga tidak
berdampak ke fitur offline.  (07-integrations-online-sources.md)

Interface publik:
  resolve_url(url: str) -> dict | None   — metadata track
  get_stream(url: str) -> str | None     — direct audio stream URL
  search(query: str) -> list[dict]       — cari track
  resolve_playlist(url: str) -> list[dict] — resolve playlist URL
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
SC_BASE = "https://api-v2.soundcloud.com"
SC_WEB = "https://soundcloud.com"
OEMBED_URL = "https://soundcloud.com/oembed"

# Will be populated by _fetch_client_id()
_CLIENT_ID: Optional[str] = None


# ── Client ID management ───────────────────────────────────────────────

def _fetch_client_id() -> Optional[str]:
    """Extract client_id from SoundCloud web player JavaScript.

    Walks the main JS bundle for `client_id:"..."` — more resilient than
    scraping SSR hydration data.
    Falls back to a known recent client_id if extraction fails.
    """
    global _CLIENT_ID
    if _CLIENT_ID:
        return _CLIENT_ID

    try:
        resp = httpx.get(SC_WEB, headers={"User-Agent": USER_AGENT}, timeout=10)
        resp.raise_for_status()

        # Strategy 1: find JS bundle URL, fetch it, extract client_id
        # Look for the main entry JS path in <script> tags
        for js_match in re.finditer(
            r'<script[^>]*src="([^"]*assets/[^"]*?\.js)"',
            resp.text,
        ):
            js_url = js_match.group(1)
            if js_url.startswith("//"):
                js_url = "https:" + js_url
            elif js_url.startswith("/"):
                js_url = SC_WEB + js_url
            if not js_url.startswith("http"):
                continue
            try:
                js_resp = httpx.get(
                    js_url,
                    headers={"User-Agent": USER_AGENT},
                    timeout=10,
                )
                if js_resp.status_code != 200:
                    continue
                # client_id in bundle: `client_id:"abc123"`
                match = re.search(r'client_id[=:]["\']([a-zA-Z0-9]+)["\']', js_resp.text)
                if match:
                    _CLIENT_ID = match.group(1)
                    logger.info("Extracted client_id from JS bundle")
                    return _CLIENT_ID
            except Exception:
                continue

        # Strategy 2: look for client_id in __sc_hydration apiClient data (SSR)
        m = re.search(r'__sc_hydration\s*=\s*(\[.*?\]);', resp.text, re.DOTALL)
        if m:
            import json as _json
            hydration = _json.loads(m.group(1))
            for item in hydration:
                if isinstance(item, dict) and item.get("hydratable") == "apiClient":
                    cid = item.get("data", {}).get("id")
                    if cid:
                        _CLIENT_ID = cid
                        logger.info("Extracted client_id from hydration apiClient")
                        return _CLIENT_ID

        # Strategy 3: direct regex on HTML
        match = re.search(r'client_id[=:]["\']([a-zA-Z0-9]+)["\']', resp.text)
        if match:
            _CLIENT_ID = match.group(1)
            logger.info("Extracted client_id from script")
            return _CLIENT_ID

        # Strategy 4: JSON-LD or embedded app state
        match = re.search(r'"clientId"\s*:\s*"([a-zA-Z0-9]+)"', resp.text)
        if match:
            _CLIENT_ID = match.group(1)
            logger.info("Extracted client_id from JSON state")
            return _CLIENT_ID
    except Exception as e:
        logger.warning("Failed to fetch client_id: %s", e)

    # Last-resort fallback (may expire) — regularly updated via community sources
    _CLIENT_ID = "emAJdGEj1mm9yjoCD2jkixmgqrGIyfpi"
    logger.warning("Using fallback client_id (may expire)")
    return _CLIENT_ID


def _get_headers() -> dict:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Origin": SC_WEB,
        "Referer": f"{SC_WEB}/",
    }


# ── oEmbed (no auth needed) ────────────────────────────────────────────

def _resolve_oembed(url: str) -> Optional[dict]:
    """Resolve track metadata via oEmbed endpoint (no auth)."""
    try:
        resp = httpx.get(
            OEMBED_URL,
            params={"format": "json", "url": url},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "title": data.get("title", ""),
            "artist": data.get("author_name", ""),
            "artwork_url": data.get("thumbnail_url", ""),
            "duration_ms": 0,  # oEmbed doesn't provide duration
            "source_url": url,
            "source_type": "soundcloud",
        }
    except Exception as e:
        logger.warning("oEmbed resolve failed: %s", e)
        return None


# ── API v2 (unofficial, needs client_id) ───────────────────────────────

def _api_get(path: str, params: dict = None) -> Optional[dict]:
    """Make authenticated GET request to SoundCloud API v2."""
    cid = _fetch_client_id()
    if not cid:
        return None

    p = {"client_id": cid, "app_version": "1709017986"}
    if params:
        p.update(params)

    try:
        resp = httpx.get(
            f"{SC_BASE}{path}",
            params=p,
            headers=_get_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            # client_id expired — reset and retry once
            global _CLIENT_ID
            _CLIENT_ID = None
            cid = _fetch_client_id()
            if cid:
                p["client_id"] = cid
                try:
                    resp = httpx.get(
                        f"{SC_BASE}{path}",
                        params=p,
                        headers=_get_headers(),
                        timeout=15,
                    )
                    resp.raise_for_status()
                    return resp.json()
                except Exception:
                    pass
        logger.warning("API request failed: %s", e)
        return None
    except Exception as e:
        logger.warning("API request failed: %s", e)
        return None


def _parse_track(data: dict) -> dict:
    """Normalise SoundCloud API track dict → our metadata format."""
    return {
        "id": data.get("id"),
        "title": data.get("title", ""),
        "artist": (
            data.get("user", {}).get("username", "")
            if isinstance(data.get("user"), dict)
            else ""
        ),
        "artwork_url": data.get("artwork_url", ""),
        "duration_ms": data.get("duration", 0),
        "genre": data.get("genre", ""),
        "source_url": data.get("permalink_url", data.get("uri", "")),
        "source_type": "soundcloud",
        "waveform_url": data.get("waveform_url", ""),
    }


# ── Public API ─────────────────────────────────────────────────────────

def _normalize_url(url: str) -> str:
    """Follow redirects on short SoundCloud URLs to get the canonical URL."""
    if not re.search(r"soundcloud\.com/(on\.soundcloud|s/)\b", url):
        return url
    try:
        resp = httpx.head(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=10,
            follow_redirects=True,
        )
        return str(resp.url)
    except Exception as e:
        logger.warning("URL normalization failed: %s", e)
        return url


def resolve_url(url: str) -> Optional[dict]:
    """Resolve a SoundCloud URL → track metadata dict.

    Tries API v2 first, falls back to oEmbed.
    Returns dict with keys: title, artist, artwork_url, duration_ms,
    source_url, source_type, and stream_url (API v2 only, oEmbed excludes it).
    """
    # Normalize short URLs first
    resolved_url = _normalize_url(url)
    # Extract track ID from URL via resolve endpoint
    result = _api_get("/resolve", {"url": resolved_url})
    if result and result.get("kind") == "track":
        meta = _parse_track(result)
        stream = _extract_stream_url(result)
        if stream:
            meta["stream_url"] = stream
        return meta

    # Fallback: oEmbed (less metadata but no auth)
    return _resolve_oembed(resolved_url)


def get_stream(url: str) -> Optional[str]:
    """Return direct audio stream URL for a resolved track.

    The stream URL requires the client_id and is time-limited.
    """
    resolved_url = _normalize_url(url)
    result = _api_get("/resolve", {"url": resolved_url})
    if result:
        return _extract_stream_url(result)
    return None


def _resolve_transcoding(transcoding_url: str) -> Optional[str]:
    """Resolve a transcoding URL to a playable stream URL."""
    cid = _fetch_client_id()
    try:
        resp = httpx.get(
            transcoding_url,
            params={"client_id": cid},
            headers=_get_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("url")
    except Exception as e:
        logger.warning("Transcoding resolution failed: %s", e)
        return None


def _extract_stream_url(data: dict) -> Optional[str]:
    """Extract a direct playable stream URL from an API track response."""
    media = data.get("media", {})
    if not isinstance(media, dict):
        return None
    transcodings = media.get("transcodings", [])
    preferred = None
    fallback = None
    for t in transcodings:
        fmt = t.get("format", {})
        protocol = fmt.get("protocol", "")
        t_url = t.get("url", "")
        if protocol == "progressive":
            preferred = t
            break
        elif protocol == "hls" and not fallback:
            fallback = t
    target = preferred or fallback
    if target:
        return _resolve_transcoding(target["url"])
    return None


def search(query: str, limit: int = 10) -> list[dict]:
    """Search SoundCloud → list of track metadata dicts."""
    result = _api_get("/search/tracks", {"q": query, "limit": limit})
    if result and "collection" in result:
        return [_parse_track(item) for item in result["collection"]]
    return []


def resolve_playlist(url: str) -> list[dict]:
    """Resolve a SoundCloud playlist/set URL → list of track dicts."""
    result = _api_get("/resolve", {"url": url})
    if result and result.get("kind") in ("playlist", "set"):
        tracks = result.get("tracks", [])
        return [_parse_track(t) for t in tracks]
    return []
