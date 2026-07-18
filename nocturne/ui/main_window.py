# coding:utf-8
"""
main_window.py — 3-column layout with persistent sidebar navigation.

┌──────────────────────────────────────────────────────────────┐
│ Top Bar: Logo | Search | Notifikasi | Settings | Profile     │
├───────────┬───────────────────────────────┬──────────────────┤
│ Sidebar   │  Stage: Album Art + Ring Viz   │  Panel Lirik     │
│           │  Judul/Artis + Spectrum Bar    │  (tersinkron)    │
├───────────┴───────────────────────────────┴──────────────────┤
│ Player Bar: Now Playing | Transport + Progress | Volume + EQ │
└──────────────────────────────────────────────────────────────┘

Layout follows 09-screens-and-navigation.md and 05-system-architecture.md.
"""

from __future__ import annotations

import os
import sys
import sqlite3
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    FluentIcon as FIF,
    NavigationInterface,
    NavigationItemPosition,
    NavigationAvatarWidget,
)

from nocturne.config.config import ROOT
from nocturne.ui.components.player_bar import PlayerBar
from nocturne.ui.components.lyrics_panel import LyricsPanel
from nocturne.ui.components.ring_visualizer import RingVisualizer, SpectrumBar
from nocturne.ui.views.blank_widget import BlankWidget
from nocturne.ui.views.home_interface import HomeInterface
from nocturne.ui.views.setting_interface import SettingInterface
from nocturne.ui.views.songs_view import SongsView
from nocturne.ui.views.artists_view import ArtistsView
from nocturne.ui.views.albums_view import AlbumsView
from nocturne.ui.views.playlist_view import PlaylistView
from nocturne.ui.views.equalizer_view import EqualizerView
from nocturne.ui.theme.tokens import Color, Fonts, FontWeights
from nocturne.common.signal_bus import signalBus
from nocturne.core.player_engine import PlayerEngine
from nocturne.core.equalizer import Equalizer
from nocturne.core.audio_worker import AudioWorker
from nocturne.core.lyrics_sync import LyricsParser
from nocturne.data.db import get_connection
from nocturne.data.models import Track
from nocturne.data.library_scanner import LibraryScanner


class LogoMark(QWidget):
    """Gradient square with centre dot — mockup logo mark."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(30, 30)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        grad = QLinearGradient(0, 0, 30, 30)
        grad.setColorAt(0, QColor(Color.PRIMARY))
        grad.setColorAt(1, QColor(Color.ACCENT))
        painter.setBrush(grad)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 9, 9)
        # Shadow glow
        shadow = QColor(79, 195, 247, 128)
        pen = QPen(shadow, 2)
        painter.setPen(pen)
        painter.drawRoundedRect(self.rect(), 9, 9)
        # Centre dot
        painter.setBrush(QColor(Color.BACKGROUND))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(10, 10, 10, 10)


class TopBar(QWidget):
    """Persistent top bar: logo + search + icons (mockup style)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setStyleSheet(
            f"background:rgba(15,23,42,0.6);"
            f"border-bottom:1px solid {Color.BORDER};"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 8, 24, 8)
        layout.setSpacing(24)

        # Logo
        logo_row = QHBoxLayout()
        logo_row.setSpacing(10)
        logo_row.addWidget(LogoMark(self))
        logo_text = QLabel("Nocturne")
        logo_text.setStyleSheet(
            f"font-family:'{Fonts.DISPLAY}';font-weight:{FontWeights.LOGO};"
            f"font-size:18px;letter-spacing:0.5px;color:{Color.TEXT_PRIMARY};background:transparent;"
        )
        logo_row.addWidget(logo_text)
        layout.addLayout(logo_row)

        # Search (mockup style)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Cari lagu, artis, atau album...")
        self.search.setFixedWidth(420)
        self.search.addAction(FIF.SEARCH.icon(), QLineEdit.LeadingPosition)
        self.search.setStyleSheet(
            f"background:{Color.CARD_SOFT};border:1px solid {Color.BORDER};"
            f"border-radius:12px;padding:9px 14px 9px 36px;"
            f"color:{Color.TEXT_PRIMARY};font-size:13px;outline:none;"
            f"selection-background-color:{Color.ACCENT};"
        )
        layout.addWidget(self.search)

        layout.addStretch()

        # Notification icon
        self.notif_btn = QPushButton()
        self.notif_btn.setIcon(FIF.RINGER.icon())
        self.notif_btn.setFixedSize(36, 36)
        self.notif_btn.setFlat(True)
        self.notif_btn.setStyleSheet(
            f"QPushButton{{background:{Color.CARD_SOFT};border:1px solid {Color.BORDER};"
            f"border-radius:11px;color:{Color.TEXT_DIM};}}"
            f"QPushButton:hover{{color:{Color.ACCENT};border-color:{Color.ACCENT};}}"
        )
        layout.addWidget(self.notif_btn)

        # Settings icon
        self.settings_btn = QPushButton()
        self.settings_btn.setIcon(FIF.SETTING.icon())
        self.settings_btn.setFixedSize(36, 36)
        self.settings_btn.setFlat(True)
        self.settings_btn.setStyleSheet(self.notif_btn.styleSheet())
        layout.addWidget(self.settings_btn)

        # SoundCloud button
        self.sc_btn = QPushButton()
        self.sc_btn.setIcon(FIF.CLOUD.icon())
        self.sc_btn.setFixedSize(36, 36)
        self.sc_btn.setFlat(True)
        self.sc_btn.setStyleSheet(self.notif_btn.styleSheet())
        self.sc_btn.setToolTip("Add from SoundCloud")
        layout.addWidget(self.sc_btn)

        # Avatar
        self.avatar = QLabel("EF")
        self.avatar.setFixedSize(36, 36)
        self.avatar.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 #3B4A6B,stop:1 #1E293B);"
            f"border:1px solid {Color.BORDER};border-radius:11px;"
            f"font-family:'{Fonts.DISPLAY}';font-weight:{FontWeights.DISPLAY_BOLD};"
            f"font-size:13px;color:{Color.ACCENT};"
        )
        self.avatar.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.avatar)


class StageWidget(QWidget):
    """Center column: album art + ring + track info + spectrum bar (mockup)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background:{Color.BACKGROUND};")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(32, 28, 32, 16)
        layout.setSpacing(0)

        # Art + Ring wrapper
        self.ring = RingVisualizer(self)
        self.ring.setFixedSize(280, 280)
        layout.addSpacing(6)
        layout.addWidget(self.ring, 0, Qt.AlignCenter)

        # Track meta
        self.track_title = QLabel("")
        self.track_title.setStyleSheet(
            f"font-family:'{Fonts.DISPLAY}';font-weight:{FontWeights.DISPLAY_BOLD};"
            f"font-size:21px;letter-spacing:.2px;color:{Color.TEXT_PRIMARY};"
        )
        self.track_title.setAlignment(Qt.AlignCenter)
        layout.addSpacing(24)
        layout.addWidget(self.track_title)

        self.track_artist = QLabel("")
        self.track_artist.setStyleSheet(f"font-size:13px;color:{Color.TEXT_DIM};margin-top:5px;")
        self.track_artist.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.track_artist)

        # Tags
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

        # Spectrum bar
        self.spectrum = SpectrumBar(self)
        self.spectrum.setFixedHeight(96)
        layout.addSpacing(30)
        layout.addWidget(self.spectrum, 0, Qt.AlignCenter)

        layout.addStretch()

    def update_tags(self, bitrate: str = "", bpm: str = "", genre: str = "") -> None:
        parts = [p for p in [bitrate, bpm, genre] if p]
        self.tag_label.setText(" · ".join(parts))


class SidebarWidget(QWidget):
    """Fixed-width sidebar with NavigationInterface."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(220)
        self.setStyleSheet(f"background:rgba(15,23,42,0.35);border-right:1px solid {Color.BORDER};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.nav = NavigationInterface(self, True, True)
        layout.addWidget(self.nav)


class MainWindow(QWidget):
    """Main application window — 3-column layout + player bar."""

    NAV_ITEMS = [
        ("home", "Home", FIF.HOME, "home"),
        ("songs", "Songs", FIF.MUSIC, "songs"),
        ("artists", "Artists", FIF.PEOPLE, "artists"),
        ("albums", "Albums", FIF.ALBUM, "albums"),
        ("playlist", "Playlist", FIF.MUSIC_FOLDER, "playlist"),
        ("equalizer", "Equalizer", FIF.MIX_VOLUMES, "equalizer"),
        ("settings", "Settings", FIF.SETTING, "settings"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.setWindowIcon(QIcon(os.path.join(ROOT, "resource", "img", "icon.png")))
        self.setWindowTitle("Nocturne")
        self.setMinimumSize(1100, 720)
        self.resize(1280, 800)
        self.setStyleSheet(f"background:transparent;")

        # ── Core engine ───────────────────────────────────────────────
        self.player_engine = PlayerEngine()
        self.equalizer = Equalizer(self.player_engine._instance)
        self.audio_worker = AudioWorker(
            pcm_source=self.player_engine.pcm_data, parent=self
        )
        self.equalizer.apply_preset("Flat")
        self.equalizer.attach_to_player(self.player_engine._player)

        self._music_folders: list[Path] = []
        self._current_track: Optional[Track] = None

        # ── Views ─────────────────────────────────────────────────────
        self._views = QStackedWidget()
        self._views.setStyleSheet(f"background:{Color.BACKGROUND};")
        self._pages: dict[str, QWidget] = {}
        for key, label, icon, route in self.NAV_ITEMS:
            if key == "home":
                w = HomeInterface(self)
                w.track_activated.connect(self._play_track)
            elif key == "songs":
                w = SongsView(self)
                w.track_activated.connect(self._play_track)
            elif key == "artists":
                w = ArtistsView(self)
                w.artist_activated.connect(self._play_artist_tracks)
            elif key == "albums":
                w = AlbumsView(self)
                w.album_activated.connect(self._play_album_tracks)
            elif key == "settings":
                w = SettingInterface(self)
                w.scan_requested.connect(self._scan_library)
            elif key == "equalizer":
                w = EqualizerView(self.equalizer, self, assign_callback=self._assign_eq_to_track)
            elif key == "playlist":
                w = PlaylistView(self)
                w.track_activated.connect(self._play_track)
            else:
                w = BlankWidget(label, self)
            self._pages[key] = w
            self._views.addWidget(w)

        # ── UI components ─────────────────────────────────────────────
        self.player_bar = PlayerBar(self)
        self.player_bar.bind_engine(self.player_engine)
        signalBus.play_toggled.connect(self._on_play_toggled)
        self.player_bar.next_requested.connect(self.player_engine.next)
        self.player_bar.prev_requested.connect(self.player_engine.previous)

        self.lyrics_panel = LyricsPanel(self)
        self.stage = StageWidget(self)
        self.top_bar = TopBar(self)

        # ── Build layout ──────────────────────────────────────────────
        self._build_layout()

        # Load base QSS
        from nocturne.ui.theme.theme_manager import apply_theme
        apply_theme(QApplication.instance() or QApplication([]))

        # ── Lyrics sync timer ─────────────────────────────────────────
        self._lyrics_timer = QTimer(self)
        self._lyrics_timer.setInterval(300)
        self._lyrics_timer.timeout.connect(self._tick_lyrics)

        # ── Top bar connections ────────────────────────────────────────
        self.top_bar.settings_btn.clicked.connect(lambda: self.show_view("settings"))
        self.top_bar.search.textChanged.connect(lambda: self._search_timer.start())
        self.top_bar.sc_btn.clicked.connect(self._open_soundcloud_dialog)

        # Search with debounce (150ms)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(self._on_search_debounced)

        # ── Signal bus connections ────────────────────────────────────
        signalBus.folder_added.connect(self._on_folder_added)
        signalBus.scan_started.connect(self._scan_library)
        signalBus.reduce_motion_changed.connect(self.stage.ring.set_reduce_motion)

        # ── Audio worker → visualizer + spectrum ──────────────────────
        self.audio_worker.spectrum_ready.connect(self.stage.ring.set_spectrum)
        self.audio_worker.spectrum_ready.connect(self.stage.spectrum.set_spectrum)
        self.audio_worker.spectrum_ready.connect(self._pages["home"].set_spectrum)

        # ── Resume playback on startup (deferred — Qt event loop must be running) ─
        QTimer.singleShot(0, self._resume_playback)

    def _build_layout(self) -> None:
        vroot = QVBoxLayout(self)
        vroot.setContentsMargins(0, 0, 0, 0)
        vroot.setSpacing(0)
        vroot.addWidget(self.top_bar)

        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(0)

        self.sidebar = SidebarWidget(self)
        self._setup_navigation()
        middle.addWidget(self.sidebar)

        # Lyrics column: header + panel
        lyrics_col = QVBoxLayout()
        lyrics_col.setContentsMargins(0, 0, 0, 0)
        lyrics_col.setSpacing(0)
        from nocturne.ui.components.lyrics_panel import _build_lyrics_header
        lyrics_col.addWidget(_build_lyrics_header())
        self.lyrics_panel.setFixedWidth(300)
        lyrics_col.addWidget(self.lyrics_panel, 1)

        col = QHBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self._views, 1)
        col.addLayout(lyrics_col)

        middle.addLayout(col, 1)
        vroot.addLayout(middle, 1)
        vroot.addWidget(self.player_bar)

    def _setup_navigation(self) -> None:
        nav = self.sidebar.nav

        for key, label, icon, route_key in self.NAV_ITEMS:
            kwargs = dict(
                routeKey=route_key,
                text=label,
                icon=icon,
                onClick=lambda k=key, _key=key: self._switch_to(_key),
            )
            if key in ("settings", "equalizer"):
                kwargs["position"] = NavigationItemPosition.BOTTOM
            nav.addItem(**kwargs)

        nav.addSeparator()
        nav.addWidget(
            routeKey="avatar",
            widget=NavigationAvatarWidget(
                "FenDoZ", os.path.join(ROOT, "resource", "img", "icon.png")
            ),
            onClick=lambda: None,
            position=NavigationItemPosition.BOTTOM,
        )

        nav.setMinimumExpandWidth(800)
        nav.setExpandWidth(220)
        nav.expand(useAni=False)
        nav.setCurrentItem("home")

    def _switch_to(self, key: str) -> None:
        if key in self._pages:
            self._views.setCurrentWidget(self._pages[key])
            if hasattr(self._pages[key], "load"):
                self._pages[key].load()
            if key == "equalizer" and self._current_track:
                conn = get_connection()
                row = conn.execute(
                    "SELECT eq_preset FROM tracks WHERE id = ?",
                    (self._current_track.id,),
                ).fetchone()
                if hasattr(self._pages[key], "load_for_track"):
                    self._pages[key].load_for_track(
                        row["eq_preset"] if row else None
                    )

    def show_view(self, key: str) -> None:
        self._switch_to(key)
        self.sidebar.nav.setCurrentItem(key)

    def _open_soundcloud_dialog(self) -> None:
        """Open SoundCloud URL dialog and play the resolved track."""
        from PySide6.QtWidgets import QDialog
        from qfluentwidgets import InfoBar
        from nocturne.ui.components.soundcloud_dialog import SoundCloudDialog
        from nocturne.integrations.soundcloud.resolver import get_stream
        from nocturne.data.db import upsert_sc_track

        dialog = SoundCloudDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return

        tracks_meta = dialog.tracks
        if not tracks_meta:
            return

        # Play first track
        first_meta = tracks_meta[0]
        if "stream_url" not in first_meta:
            first_meta["stream_url"] = get_stream(
                first_meta.get("source_url", "")
            )
        if not first_meta.get("stream_url"):
            InfoBar.error(
                "Playback failed",
                "Could not get stream URL",
                parent=self,
            )
            return

        track = upsert_sc_track(first_meta)
        self._play_track(track)

    # ── Playback ──────────────────────────────────────────────────────

    def _play_track(self, track: Track) -> None:
        """Play a single track."""
        if track.source_type == "local":
            if not track.path or not Path(track.path).exists():
                return
        # soundcloud tracks: path is a URL, skip file check

        # Save lyrics offset for previous track before switching
        if self._current_track:
            self._save_lyrics_offset(self._current_track)

        self._current_track = track
        self.player_engine.load_single(track.path)
        # load_single already calls player.play()
        self._on_track_changed(track)

    def _assign_eq_to_track(self, preset_name: str) -> None:
        """Assign an EQ preset to the currently playing track."""
        if not self._current_track or not self._current_track.id:
            return
        conn = get_connection()
        conn.execute(
            "UPDATE tracks SET eq_preset = ? WHERE id = ?",
            (preset_name, self._current_track.id),
        )
        conn.commit()
        self.player_bar.set_eq_preset(preset_name)

    def _play_artist_tracks(self, artist: str) -> None:
        """Queue all tracks by an artist."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM tracks WHERE artist = ? AND path IS NOT NULL ORDER BY album_id, title",
            (artist,),
        ).fetchall()
        tracks = [Track.from_row(r) for r in rows]
        if not tracks:
            return
        paths = [t.path for t in tracks if t.path and Path(t.path).exists()]
        if not paths:
            return
        self.player_engine.load_playlist(paths, 0)
        self.player_engine.play()
        self._current_track = tracks[0]
        self._on_track_changed(tracks[0])

    def _play_album_tracks(self, album_id: int) -> None:
        """Queue all tracks in an album."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM tracks WHERE album_id = ? AND path IS NOT NULL ORDER BY title",
            (album_id,),
        ).fetchall()
        tracks = [Track.from_row(r) for r in rows]
        if not tracks:
            return
        paths = [t.path for t in tracks if t.path and Path(t.path).exists()]
        if not paths:
            return
        self.player_engine.load_playlist(paths, 0)
        self.player_engine.play()
        self._current_track = tracks[0]
        self._on_track_changed(tracks[0])

    # ── Resume ───────────────────────────────────────────────────────

    def _resume_playback(self) -> None:
        """Restore last playback position on startup (FR-1.5)."""
        state = self.player_engine.load_state()
        if not state:
            return

        # Restore volume regardless of track path validity
        vol = state.get("volume")
        if vol is not None:
            self.player_bar.volume_slider.setValue(vol)  # triggers _on_volume → engine

        if not state.get("path"):
            return
        path = state["path"]
        if not Path(path).exists():
            return
        conn = get_connection()
        row = conn.execute("SELECT * FROM tracks WHERE path = ?", (path,)).fetchone()
        if not row:
            return
        track = Track.from_row(row)
        self._current_track = track
        self.player_engine.load_single(track.path)
        pos = state.get("position_ms", 0)
        if pos > 0:
            QTimer.singleShot(500, lambda: self.player_engine.seek(pos))
        self._on_track_changed(track)

    def _on_track_changed(self, track: Track) -> None:
        """Update all UI when track changes."""
        self.player_bar.set_playing(True)
        self._pages["home"].set_playing(True)
        if not self.audio_worker.isRunning():
            self.audio_worker.start()
        self._lyrics_timer.start()

        # Player bar
        self.player_bar.update_track_info(
            title=track.title,
            artist=track.artist or "",
        )

        # Stage
        self.stage.track_title.setText(track.title)
        self.stage.track_artist.setText(track.artist or "")
        home_view = self._pages.get("home")
        if hasattr(home_view, "set_track_info"):
            home_view.set_track_info(track.title, track.artist or "")

        # Highlight in songs view
        songs = self._pages.get("songs")
        if hasattr(songs, "highlight_track"):
            songs.highlight_track(track.id)

        # Album artwork
        if track.album_id:
            conn = get_connection()
            row = conn.execute(
                "SELECT artwork_blob FROM albums WHERE id = ?", (track.album_id,)
            ).fetchone()
            if row and row[0]:
                pix = QPixmap()
                if pix.loadFromData(row[0]):
                    self.stage.ring.set_artwork(pix)
                    self.player_bar.update_track_info(track.title, track.artist or "", pix)
                    return

        # Fallback: no artwork
        self.stage.ring.set_artwork(None)

        # Record play history
        if track.id:
            conn = get_connection()
            conn.execute(
                "INSERT INTO play_history (track_id, duration_played_ms) VALUES (?, ?)",
                (track.id, 0),
            )
            conn.commit()

        # Lyrics
        self._load_lyrics(track)

        # Apply track EQ preset (FR-3.3)
        conn = get_connection()
        row = conn.execute(
            "SELECT eq_preset FROM tracks WHERE id = ?", (track.id,)
        ).fetchone()
        eq_name = row["eq_preset"] if row and row["eq_preset"] else "Flat"
        self.equalizer.apply_preset(eq_name)
        self.player_bar.set_eq_preset(eq_name)

        # Save state
        self.player_engine.save_state()

    def _on_play_toggled(self, playing: bool) -> None:
        self.player_bar.set_playing(playing)
        self._pages["home"].set_playing(playing)
        if playing:
            if not self.audio_worker.isRunning():
                self.audio_worker.start()
            self._lyrics_timer.start()
        else:
            self.audio_worker.stop()
            self._lyrics_timer.stop()

    def _on_folder_added(self, folder: str) -> None:
        path = Path(folder)
        if path.is_dir() and path not in self._music_folders:
            self._music_folders.append(path)

    # ── Lyrics ────────────────────────────────────────────────────────

    def _load_lyrics(self, track: Track) -> None:
        """Fetch lyrics from DB cache or .lrc sidecar."""
        conn = get_connection()
        row = conn.execute(
            "SELECT lrc_content, offset_ms FROM lyrics WHERE track_id = ?",
            (track.id,),
        ).fetchone()
        if row:
            lrc_content = row["lrc_content"]
            self.lyrics_panel.set_offset(row["offset_ms"] or 0)
        else:
            lrc_content = None
            self.lyrics_panel.set_offset(0)

        lines = LyricsParser.resolve(track.path or "", lrc_content)
        self.lyrics_panel.load_lyrics(lines or [])

    def _save_lyrics_offset(self, track: Track) -> None:
        """Save current lyrics offset to the database for this track."""
        if not track or not track.id:
            return
        offset = self.lyrics_panel._offset_ms if hasattr(self.lyrics_panel, "_offset_ms") else 0
        if offset == 0:
            return
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO lyrics (track_id, lrc_content, offset_ms) "
            "VALUES (?, COALESCE((SELECT lrc_content FROM lyrics WHERE track_id = ?), ''), ?)",
            (track.id, track.id, offset),
        )
        conn.commit()

    def _tick_lyrics(self) -> None:
        """Called every 300ms to sync lyrics highlight."""
        if self.player_engine.is_playing:
            self.lyrics_panel.highlight_line(self.player_engine.position_ms)

    def _on_search_debounced(self) -> None:
        """Apply search filter after debounce delay."""
        text = self.top_bar.search.text()
        for key in ("songs", "artists", "albums"):
            view = self._pages.get(key)
            if hasattr(view, "_filter"):
                view._filter(text)

    # ── Library scanning ──────────────────────────────────────────────

    def _scan_library(self) -> None:
        """Run library scanner on configured folders."""
        if not self._music_folders:
            # Ask user to configure folders first
            self.show_view("settings")
            return

        conn = get_connection()
        conn.row_factory = sqlite3.Row
        scanner = LibraryScanner(conn)
        new, updated = scanner.scan(self._music_folders)

        # Reload views
        songs_view = self._pages.get("songs")
        if isinstance(songs_view, SongsView):
            songs_view.load()

        artists_view = self._pages.get("artists")
        if isinstance(artists_view, ArtistsView):
            artists_view.load()

        albums_view = self._pages.get("albums")
        if isinstance(albums_view, AlbumsView):
            albums_view.load()

        playlist_view = self._pages.get("playlist")
        if hasattr(playlist_view, "load"):
            playlist_view.load()

    def add_music_folder(self, folder: str) -> None:
        """Add a folder to the scan list."""
        path = Path(folder)
        if path.is_dir() and path not in self._music_folders:
            self._music_folders.append(path)

    def paintEvent(self, event) -> None:
        """Draw radial gradient glows matching mockup atmosphere."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Top-left cyan glow
        g1 = QRadialGradient(0, 0, max(w, h) * 0.7)
        g1.setColorAt(0, QColor(30, 136, 229, 40))
        g1.setColorAt(1, QColor(10, 15, 30, 0))
        painter.fillRect(self.rect(), g1)

        # Bottom-right blue glow
        g2 = QRadialGradient(w, h, max(w, h) * 0.7)
        g2.setColorAt(0, QColor(79, 195, 247, 25))
        g2.setColorAt(1, QColor(10, 15, 30, 0))
        painter.fillRect(self.rect(), g2)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    app.exec()
