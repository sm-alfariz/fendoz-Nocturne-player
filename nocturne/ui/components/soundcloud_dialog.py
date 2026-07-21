# coding:utf-8
"""
soundcloud_dialog.py — SoundCloud search + URL resolve dialog.

Single input auto-detects URL vs search query.
"""

from __future__ import annotations

import re
from urllib.request import Request, urlopen

from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import InfoBar, PrimaryPushButton

from nocturne.integrations.soundcloud.resolver import (
    get_stream,
    resolve_playlist,
    resolve_url,
    search,
)
from nocturne.ui.common import fmt_ms
from nocturne.ui.icon_utils import pixmap_scaled
from nocturne.ui.theme.tokens import Color

_URL_RE = re.compile(r"https?://.*soundcloud\.com/")
_ARTWORK_CACHE: dict[str, QPixmap] = {}


# ── Worker threads ────────────────────────────────────────────────────


class SearchWorker(QThread):
    """Background search via SoundCloud API."""

    finished = Signal(list)  # list[dict]
    error = Signal(str)

    def __init__(self, query: str, parent=None):
        super().__init__(parent)
        self._query = query

    def run(self) -> None:
        try:
            results = search(self._query, limit=20)
            # Pre-fetch artwork thumbnails in background
            for track in results:
                url = track.get("artwork_url", "")
                if url and url not in _ARTWORK_CACHE:
                    try:
                        url_lg = url.replace("-large", "-t300x300")
                        req = Request(url_lg, headers={"User-Agent": "Mozilla/5.0"})
                        with urlopen(req, timeout=8) as resp:
                            data = resp.read()
                            px = QPixmap()
                            if px.loadFromData(data):
                                _ARTWORK_CACHE[url] = px.scaled(
                                    40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation
                                )
                    except Exception:
                        pass
            self.finished.emit(results)
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


# ── Result item widget ────────────────────────────────────────────────


class _TrackItemWidget(QWidget):
    """Custom widget for a single search result row."""

    def __init__(self, track: dict, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        self.artwork = QLabel()
        self.artwork.setFixedSize(40, 40)
        self.artwork.setStyleSheet(
            "background:rgba(79,195,247,0.12);border-radius:6px;"
        )
        artwork_url = track.get("artwork_url", "")
        if artwork_url and artwork_url in _ARTWORK_CACHE:
            self.artwork.setPixmap(_ARTWORK_CACHE[artwork_url])
        else:
            self.artwork.setPixmap(
                pixmap_scaled("soundcloud.png", 24, 24)
            )
            self.artwork.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.artwork)

        txt = QVBoxLayout()
        txt.setSpacing(1)
        title = QLabel(track.get("title", "Unknown"))
        title.setStyleSheet(
            f"color:{Color.TEXT_PRIMARY};font-size:13px;background:transparent;"
        )
        title.setWordWrap(False)
        txt.addWidget(title)

        meta_parts = [p for p in [track.get("artist", ""), track.get("genre", "")] if p]
        meta = QLabel(" — ".join(meta_parts) if meta_parts else "")
        meta.setStyleSheet(
            f"color:{Color.TEXT_DIM};font-size:11px;background:transparent;"
        )
        txt.addWidget(meta)
        layout.addLayout(txt, 1)

        duration = track.get("duration_ms", 0)
        if duration:
            dur_label = QLabel(fmt_ms(duration))
            dur_label.setStyleSheet(
                f"color:{Color.TEXT_DIM};font-size:11px;background:transparent;"
            )
            dur_label.setFixedWidth(40)
            dur_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            layout.addWidget(dur_label)


# ── Main dialog ───────────────────────────────────────────────────────


class SoundCloudDialog(QDialog):
    """Search SoundCloud or paste a URL to resolve tracks."""

    def __init__(self, parent=None, *, mode: str = "play"):
        super().__init__(parent)
        self.setWindowTitle("SoundCloud")
        self.setMinimumSize(500, 420)
        self._tracks: list[dict] = []
        self._mode = mode

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # Dark theme
        self.setStyleSheet(f"""
            QDialog{{background:{Color.BACKGROUND};}}
            QLabel{{color:{Color.TEXT_PRIMARY};background:transparent;}}
            QLineEdit{{
                background:{Color.CARD};color:{Color.TEXT_PRIMARY};
                border:1px solid {Color.BORDER};border-radius:8px;
                padding:8px 12px;font-size:13px;
            }}
            QLineEdit:focus{{border-color:{Color.ACCENT};}}
            QListWidget{{
                background:{Color.CARD};color:{Color.TEXT_PRIMARY};
                border:1px solid {Color.BORDER};border-radius:8px;
            }}
            QListWidget::item{{padding:4px 8px;}}
            QListWidget::item:selected{{background:rgba(79,195,247,0.15);}}
            QPushButton{{
                background:transparent;color:{Color.TEXT_PRIMARY};
                border:1px solid {Color.BORDER};border-radius:6px;
                padding:6px 14px;
            }}
            QPushButton:hover{{border-color:{Color.ACCENT};color:{Color.ACCENT};}}
        """)

        # Input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search SoundCloud or paste URL…")
        self.search_input.returnPressed.connect(self._on_submit)
        layout.addWidget(self.search_input)

        # Status
        self.status = QLabel("")
        self.status.setStyleSheet(f"color:{Color.TEXT_DIM};font-size:11px;")
        layout.addWidget(self.status)

        # Results list
        self.results_list = QListWidget()
        layout.addWidget(self.results_list, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        if self._mode == "add":
            self.action_btn = PrimaryPushButton("Add to Playlist")
        else:
            self.action_btn = PrimaryPushButton("Play")
        self.action_btn.setEnabled(False)
        self.action_btn.clicked.connect(self._on_action)
        btn_row.addWidget(self.action_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()

        layout.addLayout(btn_row)

        # State
        self._workers: list[QThread] = []
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._do_search)

    # ── Input handling ─────────────────────────────────────────────

    def _on_submit(self) -> None:
        text = self.search_input.text().strip()
        if not text:
            return
        if _URL_RE.match(text):
            self._resolve_url(text)
        else:
            self._debounce.start()  # debounce rapid typing

    def _do_search(self) -> None:
        text = self.search_input.text().strip()
        if not text:
            return
        self.status.setText("Searching…")
        self.action_btn.setEnabled(False)
        self.results_list.clear()
        self._start_worker(SearchWorker(text, self))

    def _resolve_url(self, url: str) -> None:
        self.status.setText("Resolving…")
        self.action_btn.setEnabled(False)
        self.results_list.clear()
        self._start_worker(ResolveWorker(url, self))

    def _start_worker(self, worker: QThread) -> None:
        if isinstance(worker, SearchWorker):
            worker.finished.connect(self._on_search_results)
        else:
            worker.finished.connect(self._on_resolved)
        worker.error.connect(self._on_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        worker.error.connect(lambda: self._cleanup_worker(worker))
        self._workers.append(worker)
        worker.start()

    def _cleanup_worker(self, worker: QThread) -> None:
        if worker in self._workers:
            self._workers.remove(worker)

    # ── Results ────────────────────────────────────────────────────

    def _on_search_results(self, tracks: list[dict]) -> None:
        self._show_tracks(tracks, "No results found.")

    def _on_resolved(self, tracks: list[dict]) -> None:
        self._show_tracks(tracks, "Could not resolve URL.")

    def _show_tracks(self, tracks: list[dict], empty_msg: str) -> None:
        self.results_list.clear()
        if not tracks:
            self.status.setText(empty_msg)
            return
        self._tracks = tracks
        for track in tracks:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, track)
            widget = _TrackItemWidget(track)
            item.setSizeHint(widget.sizeHint())
            self.results_list.addItem(item)
            self.results_list.setItemWidget(item, widget)
        self.status.setText(f"{len(tracks)} track(s) found.")
        self.action_btn.setEnabled(True)

    def _on_error(self, msg: str) -> None:
        self.status.setText(msg)
        InfoBar.error("Error", msg, parent=self)

    # ── Action ─────────────────────────────────────────────────────

    def _on_action(self) -> None:
        selected = self.results_list.selectedItems()
        if not selected:
            # If nothing selected, use all tracks
            selected = [
                self.results_list.item(i)
                for i in range(self.results_list.count())
            ]
        tracks = [item.data(Qt.UserRole) for item in selected if item.data(Qt.UserRole)]
        if not tracks:
            return
        # Ensure stream_url is populated
        for track in tracks:
            if not track.get("stream_url") and track.get("source_url"):
                try:
                    track["stream_url"] = get_stream(track["source_url"])
                except Exception:
                    pass
        self._tracks = tracks
        self.accept()

    # ── Cleanup ────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        for w in self._workers:
            w.quit()
            w.wait(2000)
        super().closeEvent(event)

    @property
    def tracks(self) -> list[dict]:
        return self._tracks
