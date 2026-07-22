# coding:utf-8
"""
artists_view.py — Grid card view of artists, click to show tracks.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget
from qfluentwidgets import CardWidget, FlowLayout

from nocturne.data.db import get_connection
from nocturne.ui.common import clear_flow_layout, make_empty_label, TITLE_STYLE
from nocturne.ui.theme.tokens import Color


class ArtistCard(CardWidget):
    def __init__(self, name: str, track_count: int, parent=None):
        super().__init__(parent)
        self.artist_name = name
        self.setFixedSize(200, 100)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        self.name_label = QLabel(name)
        self.name_label.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {Color.TEXT_PRIMARY};")
        self.count_label = QLabel(f"{track_count} tracks")
        self.count_label.setStyleSheet(f"color: {Color.TEXT_DIM}; font-size: 12px;")
        layout.addWidget(self.name_label, 0, Qt.AlignCenter)
        layout.addWidget(self.count_label, 0, Qt.AlignCenter)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        parent = self.parent()
        while parent and not isinstance(parent, ArtistsView):
            parent = parent.parent()
        if parent:
            parent.artist_activated.emit(self.artist_name)


class ArtistsView(QWidget):
    """Artists page — grid of artist cards."""

    artist_activated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_text = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Artists")
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        # Loading placeholder
        self._loading_label = make_empty_label("Loading…")
        layout.addWidget(self._loading_label)

        # Scrollable grid
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self.grid = QWidget()
        self.grid.setStyleSheet("background:transparent;")
        self.grid_layout = FlowLayout(self.grid)
        self._scroll.setWidget(self.grid)
        self._scroll.hide()
        layout.addWidget(self._scroll, 1)

    def _filter(self, text: str) -> None:
        self._filter_text = text
        self.load()

    def load(self, rows: list[tuple[str, int]] | None = None) -> None:
        clear_flow_layout(self.grid_layout)
        self._loading_label.hide()
        self._scroll.show()
        if rows is None:
            conn = get_connection()
            query = (
                "SELECT artist, COUNT(*) as cnt FROM tracks "
                "WHERE artist IS NOT NULL AND artist != '' "
            )
            params: list[str] = []
            if self._filter_text:
                query += "AND artist LIKE ? "
                params.append(f"%{self._filter_text}%")
            query += "GROUP BY artist ORDER BY artist"
            rows = conn.execute(query, params).fetchall()
        if not rows:
            label = make_empty_label("Belum ada artis.\nScan folder musik di Settings.")
            self.grid_layout.addWidget(label)
            return
        for row in rows:
            card = ArtistCard(row[0], row[1], self.grid)
            self.grid_layout.addWidget(card)
