# coding:utf-8
"""
songs_view.py — Sortable / filterable list of all scanned tracks.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QSortFilterProxyModel, QAbstractTableModel, Signal
from PySide6.QtWidgets import QHeaderView, QTableView, QVBoxLayout, QWidget
from qfluentwidgets import SearchLineEdit, TableView

from nocturne.data.db import get_connection
from nocturne.data.models import Track


class SongTableModel(QAbstractTableModel):
    COLUMNS = ["#", "Title", "Artist", "Album", "Duration", "Added"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracks: list[Track] = []

    def load(self) -> None:
        self.beginResetModel()
        conn = get_connection()
        rows = conn.execute(
            "SELECT t.*, a.title AS album_title FROM tracks t "
            "LEFT JOIN albums a ON t.album_id = a.id "
            "ORDER BY t.added_at DESC"
        ).fetchall()
        self._tracks = [Track.from_row(r) for r in rows]
        self.endResetModel()

    def rowCount(self, parent=None) -> int:
        return len(self._tracks)

    def columnCount(self, parent=None) -> int:
        return len(self.COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        t = self._tracks[index.row()]
        col = index.column()
        if col == 0: return str(t.id)
        if col == 1: return t.title
        if col == 2: return t.artist or ""
        if col == 3: return t.album_title if hasattr(t, "album_title") else ""
        if col == 4:
            m, s = divmod(t.duration_ms // 1000, 60)
            return f"{m}:{s:02d}"
        if col == 5: return str(t.added_at)[:10] if t.added_at else ""
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
        self.proxy.setFilterKeyColumn(-1)  # all columns

        self.table = TableView(self)
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table)

    def load(self) -> None:
        self.model.load()

    def _filter(self, text: str) -> None:
        self.proxy.setFilterFixedString(text)

    def _on_double_click(self, index) -> None:
        source_index = self.proxy.mapToSource(index)
        track = self.model.track_at(source_index.row())
        self.track_activated.emit(track)
