# coding:utf-8
"""
playlist_view.py — Playlist list and detail view (FR-2.x).
"""

from __future__ import annotations


from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import InfoBar, MessageBox

from nocturne.common.signal_bus import signalBus
from nocturne.data.models import Track
from nocturne.data.playlist_manager import PlaylistManager
from nocturne.ui.controllers.playlist_controller import PlaylistController


class PlaylistDetail(QWidget):
    """Right-side: tracks in a single playlist."""

    track_activated = Signal(object)  # Track
    play_playlist_track = Signal(object, list)  # Track, queue

    def __init__(self, controller: PlaylistController, parent=None):
        super().__init__(parent)
        self._controller = controller
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        top = QHBoxLayout()
        self.title_label = QLabel("Select a playlist")
        self.title_label.setStyleSheet("font-size: 20px; font-weight: 700;")
        top.addWidget(self.title_label)
        top.addStretch()

        self.add_sc_btn = QPushButton("Add from URL")
        self.add_sc_btn.setFixedHeight(30)
        self.add_sc_btn.clicked.connect(self._add_soundcloud)
        self.add_btn = QPushButton("Add Track")
        self.add_btn.setFixedHeight(30)
        self.add_btn.clicked.connect(self._add_track)
        self.export_btn = QPushButton("Export .m3u")
        self.export_btn.setFixedHeight(30)
        self.export_btn.clicked.connect(self._export_m3u)
        self.del_btn = QPushButton("Delete Playlist")
        self.del_btn.setStyleSheet("color: #F472B6;")
        self.del_btn.setFixedHeight(30)
        top.addWidget(self.add_sc_btn)
        top.addWidget(self.add_btn)
        top.addWidget(self.export_btn)
        top.addWidget(self.del_btn)
        layout.addLayout(top)

        self.track_list = QListWidget()
        self.track_list.setStyleSheet(
            "QListWidget{background:#1E293B;border:1px solid rgba(79,195,247,0.14);border-radius:8px;}"
            "QListWidget::item{padding:8px 12px;color:#E2E8F0;}"
            "QListWidget::item:selected{background:rgba(30,136,229,0.2);}"
        )
        self.track_list.doubleClicked.connect(self._on_double_click)
        self.track_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.track_list.customContextMenuRequested.connect(self._on_context_menu)
        # Drag-drop reorder
        self.track_list.setDragDropMode(QListWidget.InternalMove)
        self.track_list.setDefaultDropAction(Qt.MoveAction)
        self.track_list.model().rowsInserted.connect(self._on_rows_inserted)
        layout.addWidget(self.track_list)

        self._playlist_id: int | None = None
        self._tracks: list[Track] = []
        self._suppress_reorder = False

    def load(self, playlist_id: int) -> None:
        self._playlist_id = playlist_id
        name = self._controller.get_name(playlist_id)
        self.title_label.setText(name)
        self._tracks = self._controller.get_tracks(playlist_id)
        self._suppress_reorder = True
        self.track_list.clear()
        for t in self._tracks:
            prefix = "🌐 " if t.source_type == "soundcloud" else ""
            item = QListWidgetItem(f"{prefix}{t.title or '?'}  —  {t.artist or '?'}")
            item.setData(Qt.UserRole, t.id)
            self.track_list.addItem(item)
        self._suppress_reorder = False

    def _on_context_menu(self, pos) -> None:
        item = self.track_list.itemAt(pos)
        if not item or self._playlist_id is None:
            return
        track_id = item.data(Qt.UserRole)
        menu = QMenu(self)
        remove_action = menu.addAction("Remove from playlist")
        action = menu.exec(self.track_list.viewport().mapToGlobal(pos))
        if action == remove_action:
            self._controller.remove_track(self._playlist_id, track_id)
            self.load(self._playlist_id)

    def _on_rows_inserted(self, parent, first, last) -> None:
        """Save new track order after drag-drop reorder."""
        if self._suppress_reorder or self._playlist_id is None:
            return
        ids: list[int] = []
        for i in range(self.track_list.count()):
            ids.append(self.track_list.item(i).data(Qt.UserRole))
        self._controller.reorder_tracks(self._playlist_id, ids)

    def _export_m3u(self) -> None:
        if self._playlist_id is None:
            return
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Export .m3u", f"{self.title_label.text()}.m3u",
            "Playlist files (*.m3u *.m3u8)"
        )
        if not path:
            return
        self._controller.export_m3u(self._playlist_id, path)
        InfoBar.success(title="Export", content=f"Exported {len(self._tracks)} tracks",
                        parent=self, duration=2000)

    def _add_soundcloud(self) -> None:
        if self._playlist_id is None:
            return
        from PySide6.QtWidgets import QDialog
        from nocturne.ui.components.soundcloud_dialog import SoundCloudDialog
        from nocturne.data.db import upsert_sc_track
        from nocturne.integrations.soundcloud.resolver import get_stream

        dialog = SoundCloudDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        pm = PlaylistManager()
        for meta in dialog.tracks:
            if "stream_url" not in meta:
                meta["stream_url"] = get_stream(meta.get("source_url", ""))
            track = upsert_sc_track(meta)
            pm.add_track(self._playlist_id, track.id)
        self.load(self._playlist_id)

    def _add_track(self) -> None:
        if self._playlist_id is None:
            return
        from PySide6.QtWidgets import QFileDialog
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Tracks", "", "Audio files (*.mp3 *.flac *.wav *.ogg *.m4a)"
        )
        if not paths:
            return
        from nocturne.data.db import get_connection
        conn = get_connection()
        pm = PlaylistManager()
        added = 0
        for p in paths:
            row = conn.execute(
                "SELECT id FROM tracks WHERE path = ?", (p,)
            ).fetchone()
            if row:
                pm.add_track(self._playlist_id, row[0])
                added += 1
        if added:
            InfoBar.success(title="Add Track", content=f"{added} track{'s' if added > 1 else ''} added",
                            parent=self, duration=2000)
        else:
            InfoBar.warning(title="Add Track", content="No tracks found in library. Scan your music first.",
                            parent=self, duration=3000)
        self.load(self._playlist_id)

    def _on_double_click(self, index) -> None:
        row = index.row()
        if 0 <= row < len(self._tracks):
            self.play_playlist_track.emit(self._tracks[row], list(self._tracks))


class PlaylistView(QWidget):
    """Playlist page: left list of playlists, right detail."""

    track_activated = Signal(object)  # Track
    play_playlist_track = Signal(object, list)  # Track, queue

    def __init__(self, parent=None):
        super().__init__(parent)
        self._controller = PlaylistController(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

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

        self.detail = PlaylistDetail(self._controller, self)
        self.detail.track_activated.connect(self.track_activated.emit)
        self.detail.play_playlist_track.connect(self.play_playlist_track.emit)
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
        for p in self._controller.list_all():
            item = QListWidgetItem(p.name)
            item.setData(Qt.UserRole, p.id)
            self.playlist_list.addItem(item)
        self.playlist_list.blockSignals(False)
        signalBus.playlist_changed.emit()

    def _on_select(self, row: int) -> None:
        item = self.playlist_list.item(row)
        if item:
            pid = item.data(Qt.UserRole)
            self.detail.load(pid)

    def _create(self) -> None:
        name, ok = QInputDialog.getText(self, "New Playlist", "Playlist name:")
        if ok and name.strip():
            self._controller.create(name.strip())
            self._reload_list()

    def _delete_current(self) -> None:
        pid = self.detail._playlist_id
        if pid is None:
            return
        dialog = MessageBox("Delete Playlist", "Delete this playlist permanently?", self)
        if dialog.exec():
            self._controller.delete(pid)
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
        result = self._controller.import_m3u(path)
        if result["missing"]:
            InfoBar.warning(
                parent=self,
                title="Import",
                content=f"{len(result['missing'])} tracks not found in library",
                duration=3000,
            )
        if result["found"]:
            pid = self._controller.create(result["playlist_name"])
            for t in result["found"]:
                from nocturne.data.playlist_manager import PlaylistManager
                PlaylistManager().add_track(pid, t.id)
            self._reload_list()
            InfoBar.success(
                parent=self,
                title="Import",
                content=f"{len(result['found'])} tracks imported",
                duration=2000,
            )
