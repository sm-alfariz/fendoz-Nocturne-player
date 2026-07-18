# coding:utf-8
"""
albums_view.py — Grid card view of albums, click to show tracks.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget, QGridLayout
from qfluentwidgets import CardWidget, FlowLayout

from nocturne.data.db import get_connection


class AlbumCard(CardWidget):
    def __init__(self, album_id: int, title: str, artist: str | None,
                 artwork_blob: bytes | None, track_count: int, parent=None):
        super().__init__(parent)
        self.album_id = album_id
        self.setFixedSize(180, 220)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)

        # Artwork placeholder
        self.artwork = QLabel()
        self.artwork.setFixedSize(140, 140)
        self.artwork.setAlignment(Qt.AlignCenter)
        self.artwork.setStyleSheet("background: #1E293B; border-radius: 8px;")
        if artwork_blob:
            pixmap = QPixmap()
            if pixmap.loadFromData(artwork_blob):
                self.artwork.setPixmap(pixmap.scaled(140, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(self.artwork, 0, Qt.AlignCenter)

        self.title_label = QLabel(title if len(title) < 30 else title[:27] + "...")
        self.title_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        self.subtitle = QLabel(f"{artist or 'Unknown'} · {track_count}")
        self.subtitle.setStyleSheet("color: #7C8AA5; font-size: 11px;")
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
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)

        self.grid = QWidget()
        self.grid_layout = FlowLayout(self.grid)
        layout.addWidget(self.grid)

    def _filter(self, text: str) -> None:
        self._filter_text = text
        self.load()

    def load(self) -> None:
        self._clear_layout()
        conn = get_connection()
        query = (
            "SELECT a.id, a.title, a.artist, a.artwork_blob, COUNT(t.id) as cnt "
            "FROM albums a LEFT JOIN tracks t ON t.album_id = a.id "
        )
        params = []
        if self._filter_text:
            query += "WHERE a.title LIKE ? "
            params.append(f"%{self._filter_text}%")
        query += "GROUP BY a.id ORDER BY a.title"
        rows = conn.execute(query, params).fetchall()
        if not rows:
            label = QLabel("Belum ada album.\nScan folder musik di Settings.")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color:#7C8AA5;font-size:16px;padding:60px;")
            self.grid_layout.addWidget(label)
            return
        for r in rows:
            card = AlbumCard(r[0], r[1], r[2], r[3], r[4], self.grid)
            self.grid_layout.addWidget(card)

    def _clear_layout(self) -> None:
        from PySide6.QtWidgets import QLayoutItem, QWidget
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if isinstance(item, QWidget):
                item.deleteLater()
            elif isinstance(item, QLayoutItem):
                w = item.widget()
                if w:
                    w.deleteLater()
