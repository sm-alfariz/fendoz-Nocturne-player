# coding:utf-8
"""
miniplayer.py — Frameless always-on-top miniplayer window with transport controls.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from nocturne.core.player_engine import PlayerEngine
from nocturne.ui.theme.tokens import Color, FontWeights


class MiniPlayer(QWidget):
    """Compact always-on-top window for basic playback control."""

    play_toggled = Signal()
    next_requested = Signal()
    prev_requested = Signal()
    closed = Signal()

    def __init__(self, engine: PlayerEngine, parent=None) -> None:
        super().__init__(parent)
        self._engine = engine

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setFixedSize(400, 90)
        self.setStyleSheet(
            f"background:rgba(15,23,42,0.95);"
            f"border:1px solid {Color.BORDER};"
            f"border-radius:10px;"
        )

        # ── Layout ──────────────────────────────────────────────────────
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Artwork
        self.artwork = QLabel("🎵")
        self.artwork.setFixedSize(56, 56)
        self.artwork.setAlignment(Qt.AlignCenter)
        self.artwork.setStyleSheet(
            "background:radial-gradient(circle at 35% 30%, #2E4A7D, #101B33 70%);"
            "border-radius:12px;font-size:24px;"
        )
        layout.addWidget(self.artwork)

        # Track info
        txt = QVBoxLayout()
        txt.setSpacing(2)
        self.title_label = QLabel("No track")
        self.title_label.setStyleSheet(
            f"color:{Color.TEXT_PRIMARY};font-weight:{FontWeights.BODY_SEMIBOLD};"
            f"font-size:13px;background:transparent;"
        )
        self.artist_label = QLabel("-")
        self.artist_label.setStyleSheet(
            f"color:{Color.TEXT_DIM};font-size:11px;background:transparent;"
        )
        txt.addWidget(self.title_label)
        txt.addWidget(self.artist_label)
        layout.addLayout(txt, 1)

        # Prev
        self.prev_btn = QPushButton("⏮")
        self.prev_btn.setFixedSize(32, 32)
        self.prev_btn.setStyleSheet(self._btn_qss())
        self.prev_btn.clicked.connect(self.prev_requested.emit)
        layout.addWidget(self.prev_btn)

        # Play/Pause
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(36, 36)
        self.play_btn.setStyleSheet(
            self._btn_qss() +
            f"QPushButton{{font-size:18px;background:{Color.ACCENT};"
            f"border-radius:18px;color:#fff;}}"
            f"QPushButton:hover{{background:{Color.PRIMARY};}}"
        )
        self.play_btn.clicked.connect(self._toggle_play)
        layout.addWidget(self.play_btn)

        # Next
        self.next_btn = QPushButton("⏭")
        self.next_btn.setFixedSize(32, 32)
        self.next_btn.setStyleSheet(self._btn_qss())
        self.next_btn.clicked.connect(self.next_requested.emit)
        layout.addWidget(self.next_btn)

        # Close
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;"
            f"color:{Color.TEXT_DIM};font-size:14px;}}"
            f"QPushButton:hover{{color:{Color.ACCENT_SECONDARY};}}"
        )
        self.close_btn.clicked.connect(self._do_close)
        layout.addWidget(self.close_btn)

        # Poll timer
        self._timer = QTimer(self)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

        self._is_playing = False

    # ── Button QSS ──────────────────────────────────────────────────

    def _btn_qss(self) -> str:
        return (
            f"QPushButton{{background:transparent;border:none;"
            f"color:{Color.TEXT_DIM};font-size:14px;}}"
            f"QPushButton:hover{{color:{Color.ACCENT};}}"
        )

    # ── Public API ──────────────────────────────────────────────────

    def update_track_info(
        self, title: str, artist: str, artwork: QPixmap | None = None
    ) -> None:
        self.title_label.setText(title or "No track")
        self.artist_label.setText(artist or "-")
        if artwork:
            self.artwork.setText("")
            self.artwork.setPixmap(
                artwork.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            self.artwork.clear()
            self.artwork.setText("🎵")

    def set_playing(self, playing: bool) -> None:
        self._is_playing = playing
        self.play_btn.setText("⏸" if playing else "▶")

    # ── Internals ───────────────────────────────────────────────────

    def _toggle_play(self) -> None:
        self.play_toggled.emit()
        if self._engine:
            self._engine.toggle_play()

    def _do_close(self) -> None:
        self._timer.stop()
        self.hide()
        self.closed.emit()

    def _poll(self) -> None:
        if not self._engine:
            return
        playing = self._engine.is_playing
        if playing != self._is_playing:
            self._is_playing = playing
            self.play_btn.setText("⏸" if playing else "▶")
