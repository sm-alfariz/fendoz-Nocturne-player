# coding:utf-8
"""
artists_view.py — Grid card view of artists, click to show tracks.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget, QGridLayout, QPushButton
from qfluentwidgets import CardWidget, FlowLayout

from nocturne.data.db import get_connection


class ArtistCard(CardWidget):
    def __init__(self, name: str, track_count: int, parent=None):
        super().__init__(parent)
        self.artist_name = name
        self.setFixedSize(200, 100)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        self.name_label = QLabel(name)
        self.name_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        self.count_label = QLabel(f"{track_count} tracks")
        self.count_label.setStyleSheet("color: #7C8AA5; font-size: 12px;")
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
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)

        self.grid = QWidget()
        self.grid_layout = FlowLayout(self.grid)
        layout.addWidget(self.grid)

    def _filter(self, text: str) -> None:
        self._filter_text = text
        self.load()

    def load(self) -> None:
        # Clear existing
        self._clear_layout()
        conn = get_connection()
        query = (
            "SELECT artist, COUNT(*) as cnt FROM tracks "
            "WHERE artist IS NOT NULL AND artist != '' "
        )
        params = []
        if self._filter_text:
            query += "AND artist LIKE ? "
            params.append(f"%{self._filter_text}%")
        query += "GROUP BY artist ORDER BY artist"
        rows = conn.execute(query, params).fetchall()
        if not rows:
            label = QLabel("Belum ada artis.\nScan folder musik di Settings.")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color:#7C8AA5;font-size:16px;padding:60px;")
            self.grid_layout.addWidget(label)
            return
        for row in rows:
            card = ArtistCard(row[0], row[1], self.grid)
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
