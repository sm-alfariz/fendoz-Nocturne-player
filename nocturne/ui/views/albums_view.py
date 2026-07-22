# coding:utf-8
"""
albums_view.py — Grid card view of albums, click to show tracks.
"""

from __future__ import annotations


from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from qfluentwidgets import CardWidget, FlowLayout

from nocturne.data.db import get_connection
from nocturne.ui.common import clear_flow_layout, make_empty_label, TITLE_STYLE
from nocturne.ui.icon_utils import artwork_pixmap
from nocturne.ui.theme.tokens import Color


class AlbumCard(CardWidget):
    def __init__(self, album_id: int, title: str, artist: str | None,
                 artwork_blob: bytes | None, track_count: int, parent=None):
        super().__init__(parent)
        self.album_id = album_id
        self.setFixedSize(180, 220)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)

        self.artwork = QLabel()
        self.artwork.setFixedSize(140, 140)
        self.artwork.setAlignment(Qt.AlignCenter)
        self.artwork.setStyleSheet(f"background: {Color.CARD}; border-radius: 8px;")
        if artwork_blob:
            px = artwork_pixmap(album_id, artwork_blob)
            if px:
                self.artwork.setPixmap(px)
        layout.addWidget(self.artwork, 0, Qt.AlignCenter)

        self.title_label = QLabel(title if len(title) < 30 else title[:27] + "...")
        self.title_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        self.subtitle = QLabel(f"{artist or 'Unknown'} · {track_count}")
        self.subtitle.setStyleSheet(f"color: {Color.TEXT_DIM}; font-size: 11px;")
        self.subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.subtitle)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        parent = self.parent()
        while parent and not isinstance(parent, AlbumsView):
            parent = parent.parent()
        if parent:
            parent.album_activated.emit(self.album_id)


class AlbumsView(QWidget):
    """Albums page — grid of album cards."""

    album_activated = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_text = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Albums")
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        self.grid = QWidget()
        self.grid_layout = FlowLayout(self.grid)
        layout.addWidget(self.grid)

    def _filter(self, text: str) -> None:
        self._filter_text = text
        self.load()

    def load(self, rows: list[tuple] | None = None) -> None:
        clear_flow_layout(self.grid_layout)
        if rows is None:
            conn = get_connection()
            query = (
                "SELECT a.id, a.title, a.artist, a.artwork_blob, COUNT(t.id) as cnt "
                "FROM albums a LEFT JOIN tracks t ON t.album_id = a.id "
            )
            params: list[str] = []
            if self._filter_text:
                query += "WHERE a.title LIKE ? "
                params.append(f"%{self._filter_text}%")
            query += "GROUP BY a.id ORDER BY a.title"
            rows = conn.execute(query, params).fetchall()
        if not rows:
            label = make_empty_label("Belum ada album.\nScan folder musik di Settings.")
            self.grid_layout.addWidget(label)
            return
        for r in rows:
            card = AlbumCard(r[0], r[1], r[2], r[3], r[4], self.grid)
            self.grid_layout.addWidget(card)
