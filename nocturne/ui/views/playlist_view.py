# coding:utf-8
"""
playlist_view.py — Playlist list and detail view (FR-2.x).

Replaces BlankWidget in NAV_ITEMS. Shows all playlists, click to view
tracks, create/rename/delete dialogs.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import FluentIcon as FIF, InfoBar

from nocturne.data.db import get_connection
from nocturne.data.models import Track
from nocturne.data.playlist_manager import PlaylistManager


class PlaylistDetail(QWidget):
    """Right-side: tracks in a single playlist."""

    track_activated = Signal(object)  # Track

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        top = QHBoxLayout()
        self.title_label = QLabel("Select a playlist")
        self.title_label.setStyleSheet("font-size: 20px; font-weight: 700;")
        top.addWidget(self.title_label)
        top.addStretch()

        self.add_btn = QPushButton("Add Track")
        self.add_btn.setFixedHeight(30)
        self.del_btn = QPushButton("Delete Playlist")
        self.del_btn.setStyleSheet("color: #F472B6;")
        self.del_btn.setFixedHeight(30)
        top.addWidget(self.add_btn)
        top.addWidget(self.del_btn)
        layout.addLayout(top)

        self.track_list = QListWidget()
        self.track_list.setAlternatingRowColors(True)
        self.track_list.setStyleSheet(
            "QListWidget{background:#1E293B;border:1px solid rgba(79,195,247,0.14);border-radius:8px;}"
            "QListWidget::item{padding:8px 12px;color:#E2E8F0;border-bottom:1px solid rgba(79,195,247,0.06);}"
            "QListWidget::item:selected{background:rgba(30,136,229,0.2);}"
        )
        self.track_list.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.track_list)

        self._pm = PlaylistManager()
        self._playlist_id: int | None = None
        self._tracks: list[Track] = []

    def load(self, playlist_id: int) -> None:
        self._playlist_id = playlist_id
        pm = PlaylistManager()
        playlists = pm.list_all()
        name = next((p.name for p in playlists if p.id == playlist_id), "Playlist")
        self.title_label.setText(name)
        self._tracks = pm.get_tracks(playlist_id)
        self.track_list.clear()
        for t in self._tracks:
            item = QListWidgetItem(f"{t.title or '?'}  —  {t.artist or '?'}")
            item.setData(Qt.UserRole, t.id)
            self.track_list.addItem(item)

    def _on_double_click(self, index) -> None:
        row = index.row()
        if 0 <= row < len(self._tracks):
            self.track_activated.emit(self._tracks[row])


class PlaylistView(QWidget):
    """Playlist page: left list of playlists, right detail."""

    track_activated = Signal(object)  # Track

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header
        header = QHBoxLayout()
        title = QLabel("Playlists")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()

        self.create_btn = QPushButton("New Playlist")
        self.create_btn.setStyleSheet(
            "background:#1E88E5;color:#fff;border:none;border-radius:8px;padding:8px 18px;"
        )
        self.create_btn.clicked.connect(self._create)
        header.addWidget(self.create_btn)

        self.import_btn = QPushButton("Import .m3u")
        self.import_btn.clicked.connect(self._import_m3u)
        self.import_btn.setStyleSheet(
            "background:#1E293B;color:#E2E8F0;border:1px solid rgba(79,195,247,0.14);"
            "border-radius:8px;padding:8px 18px;"
        )
        header.addWidget(self.import_btn)
        layout.addLayout(header)

        # Splitter: left list, right detail
        splitter = QSplitter(Qt.Horizontal)

        self.playlist_list = QListWidget()
        self.playlist_list.setFixedWidth(260)
        self.playlist_list.setStyleSheet(
            "QListWidget{background:#1E293B;border:1px solid rgba(79,195,247,0.14);border-radius:8px;}"
            "QListWidget::item{padding:12px;color:#E2E8F0;border-bottom:1px solid rgba(79,195,247,0.06);}"
            "QListWidget::item:selected{background:rgba(30,136,229,0.2);border-left:3px solid #4FC3F7;}"
        )
        self.playlist_list.currentRowChanged.connect(self._on_select)
        splitter.addWidget(self.playlist_list)

        self.detail = PlaylistDetail(self)
        self.detail.track_activated.connect(self.track_activated.emit)
        self.detail.del_btn.clicked.connect(self._delete_current)
        splitter.addWidget(self.detail)

        splitter.setSizes([260, 400])
        layout.addWidget(splitter)

    def load(self) -> None:
        self._reload_list()
        self.detail.title_label.setText("Select a playlist")
        self.detail.track_list.clear()

    def _reload_list(self) -> None:
        self.playlist_list.blockSignals(True)
        self.playlist_list.clear()
        pm = PlaylistManager()
        for p in pm.list_all():
            item = QListWidgetItem(p.name)
            item.setData(Qt.UserRole, p.id)
            self.playlist_list.addItem(item)
        self.playlist_list.blockSignals(False)

    def _on_select(self, row: int) -> None:
        item = self.playlist_list.item(row)
        if item:
            pid = item.data(Qt.UserRole)
            self.detail.load(pid)

    def _create(self) -> None:
        name, ok = QInputDialog.getText(self, "New Playlist", "Playlist name:")
        if ok and name.strip():
            pm = PlaylistManager()
            pm.create(name.strip())
            self._reload_list()

    def _delete_current(self) -> None:
        pid = self.detail._playlist_id
        if pid is None:
            return
        ret = QMessageBox.question(
            self, "Delete", "Delete this playlist permanently?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            pm = PlaylistManager()
            pm.delete(pid)
            self._reload_list()
            self.detail.title_label.setText("Select a playlist")
            self.detail.track_list.clear()

    def _import_m3u(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Import .m3u", "", "Playlist files (*.m3u *.m3u8)"
        )
        if not path:
            return
        pm = PlaylistManager()
        result = pm.import_m3u(path)
        if result["missing"]:
            InfoBar.warning(
                parent=self,
                title="Import",
                content=f"{len(result['missing'])} tracks not found in library",
                duration=3000,
            )
        if result["found"]:
            pid = pm.create(result["playlist_name"])
            for t in result["found"]:
                pm.add_track(pid, t.id)
            self._reload_list()
            InfoBar.success(
                parent=self,
                title="Import",
                content=f"{len(result['found'])} tracks imported",
                duration=2000,
            )
