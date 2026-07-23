# coding:utf-8
"""SoundCloud worker threads — search, stream resolution, URL resolve."""

from __future__ import annotations

import logging
import threading
from urllib.request import Request, urlopen

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QPixmap

from nocturne.integrations.soundcloud.resolver import (
    get_stream,
    resolve_playlist,
    resolve_url,
    search,
)

logger = logging.getLogger(__name__)

# Shared artwork cache: URL → QPixmap (populated on main thread from raw bytes).
# Workers use it to skip already-fetched artwork URLs.
_ARTWORK_CACHE: dict[str, QPixmap] = {}


class SearchWorker(QThread):
    """Background search via SoundCloud API.

    Emits ``finished(list)`` with track dicts, each carrying an optional
    ``_artwork_bytes`` key with raw image data for main-thread QPixmap creation.
    """

    finished = Signal(list)  # list[dict]
    error = Signal(str)

    def __init__(self, query: str, parent=None):
        super().__init__(parent)
        self._query = query
        self._stop = threading.Event()

    def request_stop(self) -> None:
        """Cooperative stop — checked before each network call."""
        self._stop.set()

    def _is_cancelled(self) -> bool:
        return self._stop.is_set()

    def run(self) -> None:
        try:
            results = search(self._query, limit=20)
            if self._is_cancelled():
                return
            # Pre-fetch artwork raw bytes (QPixmap created on main thread)
            for track in results:
                if self._is_cancelled():
                    return
                url = track.get("artwork_url", "")
                if url and url not in _ARTWORK_CACHE:
                    try:
                        url_lg = url.replace("-large", "-t300x300")
                        req = Request(url_lg, headers={"User-Agent": "Mozilla/5.0"})
                        with urlopen(req, timeout=8) as resp:
                            track["_artwork_bytes"] = resp.read()
                    except Exception:
                        logger.debug("Artwork fetch failed for %s", url)
            if not self._is_cancelled():
                self.finished.emit(results)
        except Exception as e:
            logger.warning("SearchWorker error: %s", e)
            self.error.emit(str(e))


class StreamWorker(QThread):
    """Background thread: resolve stream URLs for selected tracks."""

    finished = Signal(list)  # list[dict] with stream_url populated
    error = Signal(str)

    def __init__(self, tracks: list[dict], parent=None):
        super().__init__(parent)
        self._tracks = tracks

    def run(self) -> None:
        try:
            for track in self._tracks:
                if not track.get("stream_url") and track.get("source_url"):
                    try:
                        track["stream_url"] = get_stream(track["source_url"])
                    except Exception as e:
                        logger.warning("Stream resolve failed for %s: %s",
                                       track.get("title"), e)
            self.finished.emit(self._tracks)
        except Exception as e:
            self.error.emit(str(e))


class ResolveWorker(QThread):
    """Background thread for SoundCloud URL resolution."""

    finished = Signal(object)  # list of track dicts
    error = Signal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self) -> None:
        try:
            result = resolve_url(self._url)
            if result:
                self.finished.emit([result])
                return
            playlist = resolve_playlist(self._url)
            if playlist:
                self.finished.emit(playlist)
                return
            self.error.emit("Could not resolve URL.")
        except Exception as e:
            self.error.emit(f"Error: {e}")
