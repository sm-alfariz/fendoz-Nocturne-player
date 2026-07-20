# coding:utf-8
"""
player_bar.py — Custom bottom bar matching mockup-nocturne design.

Self-contained: no qfluentwidgets MediaPlayBarBase dependency.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QStyle, QVBoxLayout, QWidget

from nocturne.core.player_engine import PlayerEngine
from nocturne.ui.common import fmt_ms
from nocturne.ui.theme.tokens import Color, FontWeights


class ClickableSlider(QSlider):
    """Horizontal slider that seeks on click, with gradient track paint."""

    def __init__(self, parent=None) -> None:
        super().__init__(Qt.Horizontal, parent)
        self.setRange(0, 0)
        self.setFixedHeight(22)

        self._accent = QColor(Color.ACCENT)
        self._primary = QColor(Color.PRIMARY)
        self._track_bg = QColor(30, 41, 59)
        self._handle_color = QColor(Color.ACCENT)

        self.setStyleSheet(self._make_qss())

    def _make_qss(self) -> str:
        return f"""
        QSlider {{
            background: transparent;
        }}
        QSlider::groove:horizontal {{
            height: 6px;
            border-radius: 3px;
            background: {self._track_bg.name()};
        }}
        QSlider::handle:horizontal {{
            width: 14px;
            height: 14px;
            margin: -4px 0;
            border-radius: 7px;
            background: {self._handle_color.name()};
        }}
        QSlider::handle:horizontal:hover {{
            background: {Color.ACCENT};
        }}
        """

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        r = self.rect()
        groove_h = 6
        groove_rect = r.adjusted(7, (r.height() - groove_h) // 2, -7, -(r.height() - groove_h) // 2)

        # Track background
        painter.setBrush(self._track_bg)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(groove_rect, 3, 3)

        # Filled portion — gradient
        val = self.value()
        max_v = max(self.maximum(), 1)
        ratio = val / max_v
        filled_w = int(groove_rect.width() * ratio)
        if filled_w > 0:
            filled = groove_rect.adjusted(0, 0, -(groove_rect.width() - filled_w), 0)
            grad = QLinearGradient(filled.topLeft(), filled.topRight())
            grad.setColorAt(0.0, self._primary)
            grad.setColorAt(1.0, self._accent)
            painter.setBrush(grad)
            painter.drawRoundedRect(filled, 3, 3)

        # Handle
        handle_x = groove_rect.x() + filled_w
        handle_y = r.center().y()
        painter.setBrush(self._handle_color)
        painter.drawEllipse(handle_x - 7, handle_y - 7, 14, 14)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._set_pos_from_event(event)
        super().mousePressEvent(event)

    def _set_pos_from_event(self, event) -> None:
        r = self.rect().adjusted(7, 0, -7, 0)
        val = QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), event.position().x(), r.width()
        )
        self.setValue(val)


class PlayerBar(QWidget):
    """Bottom dock — now-playing | transport + progress | extras."""

    play_toggled = Signal()
    next_requested = Signal()
    prev_requested = Signal()
    seek_requested = Signal(int)
    shuffle_toggled = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(72)
        self.setStyleSheet(
            f"background:rgba(10,15,30,0.75);"
            f"border-top:1px solid {Color.BORDER};"
        )

        # ── Engine reference ────────────────────────────────────────────
        self._engine: PlayerEngine | None = None

        # ── Layout ──────────────────────────────────────────────────────
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 8, 24, 8)
        layout.setSpacing(0)

        # ── Left: Now Playing ───────────────────────────────────────────
        left = QHBoxLayout()
        left.setSpacing(12)

        self.artwork_mini = QLabel("🎵")
        self.artwork_mini.setFixedSize(44, 44)
        self.artwork_mini.setAlignment(Qt.AlignCenter)
        self.artwork_mini.setStyleSheet(
            "background:radial-gradient(circle at 35% 30%, #2E4A7D, #101B33 70%);"
            "border-radius:10px;font-size:20px;"
        )
        left.addWidget(self.artwork_mini)

        txt = QVBoxLayout()
        txt.setSpacing(2)
        self.track_title = QLabel("No track")
        self.track_title.setStyleSheet(
            f"color:{Color.TEXT_PRIMARY};font-weight:{FontWeights.BODY_SEMIBOLD};"
            f"font-size:13px;background:transparent;"
        )
        self.track_artist = QLabel("-")
        self.track_artist.setStyleSheet(
            f"color:{Color.TEXT_DIM};font-size:11px;background:transparent;"
        )
        txt.addWidget(self.track_title)
        txt.addWidget(self.track_artist)
        left.addLayout(txt)
        layout.addLayout(left, 1)

        # ── Center: Transport + Progress ────────────────────────────────
        center = QVBoxLayout()
        center.setSpacing(6)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)
        btn_row.setSpacing(8)

        self.shuffle_btn = QPushButton("🔀")
        self.shuffle_btn.setCheckable(True)
        self.shuffle_btn.setFixedSize(32, 32)
        self.shuffle_btn.setStyleSheet(self._btn_qss())
        self.shuffle_btn.clicked.connect(self._on_shuffle)
        btn_row.addWidget(self.shuffle_btn)

        self.prev_btn = QPushButton("⏮")
        self.prev_btn.setFixedSize(32, 32)
        self.prev_btn.setStyleSheet(self._btn_qss())
        self.prev_btn.clicked.connect(self.prev_requested.emit)
        btn_row.addWidget(self.prev_btn)

        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(36, 36)
        self.play_btn.setStyleSheet(
            self._btn_qss() +
            f"QPushButton{{font-size:18px;background:{Color.ACCENT};"
            f"border-radius:18px;color:#fff;}}"
            f"QPushButton:hover{{background:{Color.PRIMARY};}}"
        )
        self.play_btn.clicked.connect(self._toggle_play)
        btn_row.addWidget(self.play_btn)

        self.next_btn = QPushButton("⏭")
        self.next_btn.setFixedSize(32, 32)
        self.next_btn.setStyleSheet(self._btn_qss())
        self.next_btn.clicked.connect(self.next_requested.emit)
        btn_row.addWidget(self.next_btn)

        self.repeat_btn = QPushButton("🔁")
        self.repeat_btn.setCheckable(True)
        self.repeat_btn.setFixedSize(32, 32)
        self.repeat_btn.setStyleSheet(self._btn_qss())
        self.repeat_btn.clicked.connect(self._on_repeat)
        btn_row.addWidget(self.repeat_btn)

        center.addLayout(btn_row)

        # Progress row
        prog_row = QHBoxLayout()
        prog_row.setSpacing(8)

        self.time_label = QLabel("0:00")
        self.time_label.setStyleSheet(
            f"color:{Color.TEXT_DIM};font-size:11px;background:transparent;"
        )
        self.time_label.setFixedWidth(36)
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        prog_row.addWidget(self.time_label)

        self.progress_slider = ClickableSlider(self)
        self.progress_slider.sliderMoved.connect(self._on_seek)
        prog_row.addWidget(self.progress_slider, 1)

        self.duration_label = QLabel("0:00")
        self.duration_label.setStyleSheet(
            f"color:{Color.TEXT_DIM};font-size:11px;background:transparent;"
        )
        self.duration_label.setFixedWidth(36)
        self.duration_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        prog_row.addWidget(self.duration_label)

        center.addLayout(prog_row)
        layout.addLayout(center, 2)

        # ── Right: Extras ──────────────────────────────────────────────
        right = QHBoxLayout()
        right.setAlignment(Qt.AlignRight)
        right.setSpacing(12)

        self.like_btn = QPushButton("♡")
        self.like_btn.setFixedSize(32, 32)
        self.like_btn.setStyleSheet(
            self._btn_qss() +
            f"QPushButton{{font-size:16px;}}"
            f"QPushButton:checked{{color:{Color.ACCENT_SECONDARY};}}"
        )
        self.like_btn.setCheckable(True)
        right.addWidget(self.like_btn)

        self.vol_btn = QPushButton("🔊")
        self.vol_btn.setFixedSize(32, 32)
        self.vol_btn.setStyleSheet(self._btn_qss())
        self.vol_btn.clicked.connect(self._toggle_mute)
        right.addWidget(self.vol_btn)

        self.eq_label = QLabel("EQ: Flat")
        self.eq_label.setStyleSheet(
            f"color:{Color.ACCENT};font-size:11px;"
            f"background:rgba(79,195,247,0.08);border:1px solid {Color.BORDER};"
            f"padding:6px 10px;border-radius:9px;"
        )
        right.addWidget(self.eq_label)

        layout.addLayout(right, 1)

        # ── Poll timer ──────────────────────────────────────────────────
        self._timer = QTimer(self)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

        self._is_playing = False
        self._muted = False
        self._last_vol = 70

    # ── Button QSS factory ──────────────────────────────────────────

    def _btn_qss(self) -> str:
        return (
            f"QPushButton{{background:transparent;border:none;"
            f"color:{Color.TEXT_DIM};font-size:14px;}}"
            f"QPushButton:hover{{color:{Color.ACCENT};}}"
            f"QPushButton:checked{{color:{Color.ACCENT};}}"
        )

    # ── Engine binding ──────────────────────────────────────────────

    def bind_engine(self, engine: PlayerEngine) -> None:
        self._engine = engine

    # ── Public updates ──────────────────────────────────────────────

    def update_track_info(
        self, title: str, artist: str, artwork: QPixmap | None = None
    ) -> None:
        self.track_title.setText(title or "No track")
        self.track_artist.setText(artist or "-")
        if artwork:
            self.artwork_mini.setText("")
            self.artwork_mini.setPixmap(
                artwork.scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            self.artwork_mini.clear()
            self.artwork_mini.setText("🎵")

    def set_playing(self, playing: bool) -> None:
        self._is_playing = playing
        self.play_btn.setText("⏸" if playing else "▶")
        self.play_btn.setStyleSheet(
            self._btn_qss() +
            f"QPushButton{{font-size:18px;background:{Color.ACCENT};"
            f"border-radius:18px;color:#fff;}}"
            f"QPushButton:hover{{background:{Color.PRIMARY};}}"
        )

    def set_volume(self, volume: int) -> None:
        self._last_vol = volume
        self._muted = volume == 0
        self.vol_btn.setText("🔇" if self._muted else "🔊")

    def set_eq_preset(self, name: str) -> None:
        self.eq_label.setText(f"EQ: {name}")

    # ── Internals ──────────────────────────────────────────────────

    def _toggle_play(self) -> None:
        self.play_toggled.emit()
        # Engine might be null if called before bind — no-op
        if self._engine:
            self._engine.toggle_play()

    def _toggle_mute(self) -> None:
        if not self._engine:
            return
        self._muted = not self._muted
        self._engine.volume = 0 if self._muted else self._last_vol
        self.vol_btn.setText("🔇" if self._muted else "🔊")

    def _on_seek(self, position: int) -> None:
        if self._engine:
            self._engine.seek(position)

    def _on_shuffle(self) -> None:
        self.shuffle_toggled.emit()

    def _on_repeat(self) -> None:
        if not self._engine:
            return
        mode = self._engine.cycle_repeat()
        icons = {"off": "🔁", "one": "🔂", "all": "🔁"}
        self.repeat_btn.setText(icons.get(mode, "🔁"))
        accent = Color.ACCENT if mode != "off" else Color.TEXT_DIM
        self.repeat_btn.setStyleSheet(self._btn_qss().replace(Color.TEXT_DIM, accent))
        self.repeat_btn.setChecked(mode != "off")

    def _poll(self) -> None:
        if not self._engine:
            return
        pos = self._engine.position_ms
        dur = self._engine.duration_ms

        self.progress_slider.setRange(0, dur)
        self.progress_slider.blockSignals(True)
        self.progress_slider.setValue(pos)
        self.progress_slider.blockSignals(False)

        self.time_label.setText(fmt_ms(pos))
        self.duration_label.setText(fmt_ms(dur))

        # Sync play state button with engine
        playing = self._engine.is_playing
        if playing != self._is_playing:
            self._is_playing = playing
            self.play_btn.setText("⏸" if playing else "▶")
