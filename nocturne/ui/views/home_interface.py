# coding:utf-8
"""
home_interface.py — Nocturne home dashboard aligned to the PRD and mockup.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

import numpy as np

from nocturne.common.style_sheet import StyleSheet
from nocturne.ui.components.ring_visualizer import RingVisualizer
from qfluentwidgets import ScrollArea


class BannerWidget(QWidget):
    """Mockup-aligned Home stage using the full ring visualizer composition."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFixedHeight(520)

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

    def set_playing(self, playing: bool) -> None:
        self.visualizer.setVisible(playing)


class HomeInterface(ScrollArea):
    """Home dashboard interface."""

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

    def set_track_info(self, title: str, artist: str = "") -> None:
        self.banner.set_track_info(title, artist)

    def set_spectrum(self, data: np.ndarray) -> None:
        self.banner.set_spectrum(data)

    def set_playing(self, playing: bool) -> None:
        self.banner.set_playing(playing)
