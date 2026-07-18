# coding:utf-8
"""
artists_view.py — Grid card view of artists, click to show tracks.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
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


class ArtistsView(QWidget):
    """Artists page — grid of artist cards."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Artists")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)

        self.grid = QWidget()
        self.grid_layout = FlowLayout(self.grid)
        layout.addWidget(self.grid)

    def load(self) -> None:
        conn = get_connection()
        rows = conn.execute(
            "SELECT artist, COUNT(*) as cnt FROM tracks "
            "WHERE artist IS NOT NULL AND artist != '' "
            "GROUP BY artist ORDER BY artist"
        ).fetchall()
        for row in rows:
            card = ArtistCard(row[0], row[1], self.grid)
            self.grid_layout.addWidget(card)
