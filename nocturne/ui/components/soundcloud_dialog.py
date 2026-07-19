# coding:utf-8
"""
soundcloud_dialog.py — Dialog for adding SoundCloud tracks/playlists by URL.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)
from qfluentwidgets import InfoBar, PrimaryPushButton

from nocturne.integrations.soundcloud.resolver import resolve_url, resolve_playlist


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
            # Try as playlist
            playlist = resolve_playlist(self._url)
            if playlist:
                self.finished.emit(playlist)
                return
            self.error.emit("Could not resolve URL. Check it's a valid SoundCloud track or playlist.")
        except Exception as e:
            self.error.emit(f"Error: {e}")


class SoundCloudDialog(QDialog):
    """Modal dialog to add SoundCloud tracks by URL."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add from SoundCloud")
        self.setMinimumWidth(480)
        self._tracks: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # URL input
        layout.addWidget(QLabel("SoundCloud URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://soundcloud.com/artist/track")
        layout.addWidget(self.url_input)

        # Buttons
        btn_row = QHBoxLayout()
        self.resolve_btn = PrimaryPushButton("Resolve")
        self.resolve_btn.clicked.connect(self._resolve)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.resolve_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.status = QLabel("")
        layout.addWidget(self.status)

        self._worker: ResolveWorker | None = None

    def _resolve(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            return

        self.resolve_btn.setEnabled(False)
        self.status.setText("Resolving…")

        self._worker = ResolveWorker(url, self)
        self._worker.finished.connect(self._on_resolved)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_resolved(self, tracks: list[dict]) -> None:
        self._tracks = tracks
        self.status.setText(f"Found {len(tracks)} track(s). Click OK to add.")
        self.resolve_btn.setEnabled(True)
        self.accept()

    def _on_error(self, msg: str) -> None:
        self.status.setText(msg)
        InfoBar.error("Resolution failed", msg, parent=self)
        self.resolve_btn.setEnabled(True)

    @property
    def tracks(self) -> list[dict]:
        return self._tracks
