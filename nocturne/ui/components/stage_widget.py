# coding:utf-8
"""Center column stage widget — ring visualizer, track info, spectrum bar."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from nocturne.ui.components.ring_visualizer import RingVisualizer, SpectrumBar
from nocturne.ui.theme.tokens import Color, Fonts, FontWeights


class StageWidget(QWidget):
    """Center column: album art + ring + track info + spectrum bar (mockup)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background:{Color.BACKGROUND};")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(32, 28, 32, 16)
        layout.setSpacing(0)

        self.ring = RingVisualizer(self)
        self.ring.setFixedSize(280, 280)
        layout.addSpacing(6)
        layout.addWidget(self.ring, 0, Qt.AlignCenter)

        self.track_title = QLabel("")
        self.track_title.setStyleSheet(
            f"font-family:'{Fonts.DISPLAY}';font-weight:{FontWeights.DISPLAY_BOLD};"
            f"font-size:21px;letter-spacing:.2px;color:{Color.TEXT_PRIMARY};"
        )
        self.track_title.setAlignment(Qt.AlignCenter)
        layout.addSpacing(24)
        layout.addWidget(self.track_title)

        self.track_artist = QLabel("")
        self.track_artist.setStyleSheet(
            f"font-size:13px;color:{Color.TEXT_DIM};margin-top:5px;"
        )
        self.track_artist.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.track_artist)

        self.tags = QWidget()
        tl = QHBoxLayout(self.tags)
        tl.setSpacing(8)
        tl.setAlignment(Qt.AlignCenter)
        self.tag_label = QLabel("")
        self.tag_label.setStyleSheet(
            f"font-family:'{Fonts.MONO}';font-size:10.5px;"
            f"color:{Color.ACCENT};background:{Color.CARD_SOFT};"
            f"border:1px solid {Color.BORDER};border-radius:20px;padding:4px 10px;"
        )
        tl.addWidget(self.tag_label)
        layout.addSpacing(12)
        layout.addWidget(self.tags)

        self.spectrum = SpectrumBar(self)
        self.spectrum.setFixedHeight(96)
        layout.addSpacing(30)
        layout.addWidget(self.spectrum)

        layout.addStretch()

    def update_tags(self, bitrate: str = "", bpm: str = "", genre: str = "") -> None:
        parts = [p for p in [bitrate, bpm, genre] if p]
        self.tag_label.setText(" · ".join(parts))
