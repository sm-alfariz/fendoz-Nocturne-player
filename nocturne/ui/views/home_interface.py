# coding:utf-8
"""
home_interface.py — Nocturne home dashboard aligned to the PRD and mockup.
"""

from __future__ import annotations


from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

import numpy as np

from nocturne.common.style_sheet import StyleSheet
from nocturne.data.models import Track
from nocturne.ui.components.ring_visualizer import RingVisualizer, SpectrumBar
from qfluentwidgets import ScrollArea

from nocturne.ui.theme.tokens import Color


class _Card(QPushButton):
    """Small clickable card for history/playlist items."""

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setFixedSize(160, 90)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            f"QPushButton{{background:{Color.CARD};border:1px solid {Color.BORDER};"
            f"border-radius:11px;text-align:left;padding:12px;}}"
            f"QPushButton:hover{{border-color:{Color.ACCENT};}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)
        t = QLabel(title)
        t.setWordWrap(True)
        t.setStyleSheet(
            f"font-size:13px;font-weight:600;color:{Color.TEXT_PRIMARY};background:transparent;"
        )
        layout.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setStyleSheet(f"font-size:11px;color:{Color.TEXT_DIM};background:transparent;")
            layout.addWidget(s)
        layout.addStretch()


class _Section(QWidget):
    """A labelled horizontal row of cards."""

    def __init__(self, heading: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 4, 24, 4)
        layout.setSpacing(12)

        header = QLabel(heading)
        header.setStyleSheet(
            f"font-size:18px;font-weight:700;color:{Color.TEXT_PRIMARY};background:transparent;"
        )
        layout.addWidget(header)

        self.card_row = QHBoxLayout()
        self.card_row.setSpacing(12)
        self.card_row.setAlignment(Qt.AlignLeft)
        layout.addLayout(self.card_row)

    def add_card(self, title: str, subtitle: str = "") -> _Card:
        card = _Card(title, subtitle)
        self.card_row.addWidget(card)
        return card

    def clear(self) -> None:
        while self.card_row.count():
            item = self.card_row.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()


class BannerWidget(QWidget):
    """Mockup-aligned Home stage using the full ring visualizer composition."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFixedHeight(640)

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(24, 12, 24, 18)
        self.vBoxLayout.setSpacing(10)
        self.vBoxLayout.setAlignment(Qt.AlignCenter)

        self.galleryLabel = QLabel("Continue Listening", self)
        self.galleryLabel.setObjectName("galleryLabel")
        self.galleryLabel.setAlignment(Qt.AlignCenter)
        self.vBoxLayout.addWidget(self.galleryLabel)

        self.subtitle = QLabel(
            "Resume the current flow and keep the visualizer alive while playback is running.",
            self,
        )
        self.subtitle.setObjectName("bannerSubtitle")
        self.subtitle.setWordWrap(True)
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.vBoxLayout.addWidget(self.subtitle)

        self.visualizer = RingVisualizer(self)
        self.visualizer.setObjectName("homeRingVisualizer")
        self.visualizer.setFixedSize(360, 360)
        self.visualizer.setVisible(False)
        self.vBoxLayout.addWidget(self.visualizer, 0, Qt.AlignCenter)

        self.spectrum = SpectrumBar(self)
        self.spectrum.setFixedHeight(96)
        self.vBoxLayout.addSpacing(20)
        self.vBoxLayout.addWidget(self.spectrum, 0, Qt.AlignCenter)
        self.vBoxLayout.addStretch()

    def set_track_info(self, title: str, artist: str = "") -> None:
        if title:
            self.galleryLabel.setText(title)
            self.subtitle.setText(artist or "Now playing")
        else:
            self.galleryLabel.setText("Continue Listening")
            self.subtitle.setText(
                "Resume the current flow and keep the visualizer alive while playback is running."
            )

    def set_spectrum(self, data: np.ndarray) -> None:
        self.visualizer.set_spectrum(data)
        self.spectrum.set_spectrum(data)

    def set_playing(self, playing: bool) -> None:
        self.visualizer.setVisible(playing)


class HomeInterface(ScrollArea):
    """Home dashboard interface."""

    track_activated = Signal(object)  # Track

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.banner = BannerWidget(self)
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)

        self.__initWidget()

    def __initWidget(self):
        self.view.setObjectName("view")
        self.setObjectName("homeInterface")
        StyleSheet.HOME_WIDGET_STYLE.apply(self)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.vBoxLayout.setContentsMargins(0, 0, 0, 36)
        self.vBoxLayout.setSpacing(40)
        self.vBoxLayout.addWidget(self.banner)
        self.vBoxLayout.setAlignment(Qt.AlignTop)

    def load(
        self,
        history: list[tuple[int, str, str]] | None = None,
        playlists: list[tuple[int, str]] | None = None,
    ) -> None:
        self._clear_sections()

        if history:
            sec = _Section("Continue Listening", self.view)
            for track_id, title, artist in history:
                card = sec.add_card(title or "?", artist or "")
                card.clicked.connect(
                    lambda checked=False, tid=track_id: self._play_history_track(tid)
                )
            self.vBoxLayout.insertWidget(1, sec)

        if playlists:
            sec = _Section("Playlists", self.view)
            for pl_id, name in playlists:
                card = sec.add_card(name)
                card.clicked.connect(
                    lambda checked=False, pid=pl_id: self._open_playlist(pid)
                )
            insert_at = 2 if history else 1
            self.vBoxLayout.insertWidget(insert_at, sec)

    def _clear_sections(self) -> None:
        while self.vBoxLayout.count() > 1:
            item = self.vBoxLayout.takeAt(self.vBoxLayout.count() - 1)
            if item and item.widget():
                item.widget().deleteLater()

    def _play_history_track(self, track_id: int) -> None:
        from nocturne.data.db import get_connection
        import sqlite3
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
        if row:
            track = Track.from_row(row)
            self.track_activated.emit(track)

    def _open_playlist(self, playlist_id: int) -> None:
        parent = self.parent()
        if hasattr(parent, "show_view"):
            parent.show_view("playlist")

    def set_track_info(self, title: str, artist: str = "") -> None:
        self.banner.set_track_info(title, artist)

    def set_spectrum(self, data: np.ndarray) -> None:
        self.banner.set_spectrum(data)

    def set_playing(self, playing: bool) -> None:
        self.banner.set_playing(playing)
