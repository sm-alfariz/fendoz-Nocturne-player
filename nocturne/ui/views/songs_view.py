# coding:utf-8
"""
songs_view.py — Sortable / filterable list of all scanned tracks.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QSortFilterProxyModel, QAbstractTableModel, Signal
from PySide6.QtWidgets import QDialog, QLabel, QMenu, QTableView, QVBoxLayout, QWidget
from qfluentwidgets import SearchLineEdit

from nocturne.data.models import Track
from nocturne.ui.theme.tokens import Color
from nocturne.common.signal_bus import signalBus

from nocturne.ui.components.tag_editor import TagEditorDialog


class SongTableModel(QAbstractTableModel):
    COLUMNS = ["#", "Title", "Artist", "Album", "Duration", "Src", "Added"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracks: list[Track] = []

    def set_tracks(self, tracks: list[Track]) -> None:
        self.beginResetModel()
        self._tracks = tracks
        self.endResetModel()

    def rowCount(self, parent=None) -> int:
        return len(self._tracks)

    def columnCount(self, parent=None) -> int:
        return len(self.COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        t = self._tracks[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return str(t.id)
            if col == 1:
                return t.title
            if col == 2:
                return t.artist or ""
            if col == 3:
                return getattr(t, "album_title", "")
            if col == 4:
                if t.duration_ms is None:
                    return "--:--"
                m, s = divmod(int(t.duration_ms) // 1000, 60)
                return f"{m}:{s:02d}"
            if col == 5:
                if t.source_type == "soundcloud":
                    return "Online"
                return "Local" if t.source_type == "local" else ""
            if col == 6:
                return str(t.added_at)[:10] if t.added_at else ""

        if role == Qt.TextAlignmentRole:
            if col in (0, 4, 5):
                return Qt.AlignCenter

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section]
        return None

    def track_at(self, row: int) -> Track:
        return self._tracks[row]


class SongsView(QWidget):
    """Songs list page with search filter."""

    track_activated = Signal(object)  # Track

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        self.search = SearchLineEdit(self)
        self.search.setPlaceholderText(self.tr("Filter songs…"))
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)

        self.model = SongTableModel(self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)

        self._empty_label = QLabel("Belum ada lagu.\nPilih folder musik di Settings untuk memulai.")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet(f"color:{Color.TEXT_DIM};font-size:16px;padding:60px;")
        self._empty_label.setVisible(False)
        layout.addWidget(self._empty_label)

        self.table = QTableView(self)
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.doubleClicked.connect(self._on_double_click)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        self.table.setStyleSheet(
            f"QTableView{{background:{Color.CARD};border:1px solid {Color.BORDER};"
            f"border-radius:8px;color:{Color.TEXT_PRIMARY};gridline-color:transparent;}}"
            f"QTableView::item{{padding:4px 8px;}}"
            f"QTableView::item:selected{{background:rgba(30,136,229,0.2);}}"
            f"QHeaderView::section{{background:{Color.CARD_SOFT};color:{Color.TEXT_DIM};"
            f"border:none;padding:6px 8px;font-weight:600;}}"
        )
        layout.addWidget(self.table)

    def load(self, tracks: list[Track] | None = None) -> int:
        if tracks is not None:
            self.model.set_tracks(tracks)
        rows = self.model.rowCount()
        self._empty_label.setVisible(rows == 0)
        self.table.setVisible(rows > 0)
        return rows

    def _filter(self, text: str) -> None:
        self.proxy.setFilterFixedString(text)

    def highlight_track(self, track_id: int) -> None:
        for row in range(self.model.rowCount()):
            t = self.model.track_at(row)
            if t and t.id == track_id:
                src_idx = self.model.index(row, 0)
                proxy_idx = self.proxy.mapFromSource(src_idx)
                self.table.selectRow(proxy_idx.row())
                return

    def _on_double_click(self, index) -> None:
        source_index = self.proxy.mapToSource(index)
        track = self.model.track_at(source_index.row())
        self.track_activated.emit(track)

    def _on_context_menu(self, pos) -> None:
        index = self.table.indexAt(pos)
        if not index or not index.isValid():
            return
        source_index = self.proxy.mapToSource(index)
        track = self.model.track_at(source_index.row())

        menu = QMenu(self.table)
        menu.setStyleSheet(
            f"QMenu{{background:{Color.CARD};border:1px solid {Color.BORDER};"
            f"border-radius:8px;padding:6px;color:{Color.TEXT_PRIMARY};}}"
            f"QMenu::item{{padding:6px 24px;border-radius:4px;}}"
            f"QMenu::item:selected{{background:{Color.ACCENT};color:#fff;}}"
        )
        action = menu.addAction("✎ Edit MP3 Tag")
        action.triggered.connect(lambda: self._edit_tags(track))

        # Add to Playlist submenu
        from nocturne.data.playlist_manager import PlaylistManager
        pm = PlaylistManager()
        playlists = pm.list_all()
        if playlists:
            sub = menu.addMenu("♪ Add to Playlist")
            for pl in playlists:
                pl_action = sub.addAction(pl.name)
                pl_action.triggered.connect(
                    lambda checked=False, pid=pl.id, t=track: self._add_to_playlist(t, pid)
                )
        else:
            pl_action = menu.addAction("♪ Add to Playlist")
            pl_action.triggered.connect(lambda: self._create_and_add(track))

        remove_action = menu.addAction("✕ Remove from library")
        remove_action.triggered.connect(lambda: self._remove_track(track))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _remove_track(self, track: Track) -> None:
        from qfluentwidgets import MessageBox
        box = MessageBox(
            "Remove from library",
            f"Remove \"{track.title}\" from the library?\n"
            "The file will NOT be deleted.",
            self,
        )
        if box.exec() != MessageBox.Accepted:
            return
        from nocturne.data.db import get_connection
        conn = get_connection()
        conn.execute("DELETE FROM tracks WHERE id = ?", (track.id,))
        conn.commit()
        # Refresh view
        from nocturne.ui.controllers.songs_controller import SongsController
        refreshed = SongsController().load_tracks()
        self.load(refreshed)
        signalBus.tags_edited.emit()

    def _add_to_playlist(self, track: Track, playlist_id: int) -> None:
        from nocturne.data.playlist_manager import PlaylistManager
        from qfluentwidgets import InfoBar
        pm = PlaylistManager()
        pm.add_track(playlist_id, track.id)
        pl = next((p for p in pm.list_all() if p.id == playlist_id), None)
        name = pl.name if pl else "playlist"
        InfoBar.success("Added", f"\"{track.title}\" added to {name}", parent=self, duration=2000)

    def _create_and_add(self, track: Track) -> None:
        from nocturne.data.playlist_manager import PlaylistManager
        from nocturne.ui.views.playlist_view import _styled_input_dialog
        from qfluentwidgets import InfoBar
        name, ok = _styled_input_dialog(self, "New Playlist", "Playlist name:")
        if not ok or not name.strip():
            return
        pm = PlaylistManager()
        pid = pm.create(name.strip())
        pm.add_track(pid, track.id)
        InfoBar.success("Created", f"Playlist \"{name.strip()}\" created with track", parent=self, duration=2000)
        signalBus.playlist_changed.emit()

    def _edit_tags(self, track: Track) -> None:
        if not track.path or not os.path.isfile(track.path):
            return
        dialog = TagEditorDialog(track.path, self.window())
        if dialog.exec() != QDialog.Accepted:
            return

        # Update DB row so app reflects changes immediately
        from nocturne.data.db import get_connection
        conn = get_connection()
        conn.execute(
            "UPDATE tracks SET title=?, artist=? WHERE path=?",
            (dialog.edited_title, dialog.edited_artist, track.path),
        )
        conn.commit()

        # Refresh view
        from nocturne.ui.controllers.songs_controller import SongsController
        refreshed = SongsController().load_tracks()
        self.load(refreshed)

        # Notify MainWindow so album/artist views can refresh too
        signalBus.tags_edited.emit()
