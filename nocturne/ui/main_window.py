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

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    FluentIcon as FIF,
    NavigationInterface,
    NavigationItemPosition,
    NavigationAvatarWidget,
    NavigationPushButton,
    SearchLineEdit,
)

import vlc

from nocturne.config.config import ROOT, cfg
from nocturne.ui.components.player_bar import PlayerBar
from nocturne.ui.components.lyrics_panel import LyricsPanel
from nocturne.ui.components.ring_visualizer import RingVisualizer
from nocturne.ui.views.blank_widget import BlankWidget
from nocturne.ui.views.home_interface import HomeInterface
from nocturne.ui.views.setting_interface import SettingInterface
from nocturne.ui.views.songs_view import SongsView
from nocturne.ui.views.artists_view import ArtistsView
from nocturne.ui.views.albums_view import AlbumsView
from nocturne.ui.views.equalizer_view import EqualizerView
from nocturne.ui.theme.theme_manager import apply_theme
from nocturne.core.player_engine import PlayerEngine
from nocturne.core.equalizer import Equalizer
from nocturne.core.audio_worker import AudioWorker
from nocturne.core.lyrics_sync import LyricsParser
from nocturne.data.db import get_connection
from nocturne.data.models import Track
from nocturne.data.library_scanner import LibraryScanner


class TopBar(QWidget):
    """Persistent top bar: logo, search, notification, settings, profile."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(48)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)

        self.logo = QLabel("Nocturne")
        self.logo.setObjectName("topBarLogo")
        layout.addWidget(self.logo)

        self.search = SearchLineEdit(self)
        self.search.setPlaceholderText(self.tr("Search music, artists, albums…"))
        self.search.setFixedWidth(320)
        layout.addSpacing(24)
        layout.addWidget(self.search)

        layout.addStretch()

        self.notif_btn = QPushButton()
        self.notif_btn.setIcon(FIF.RINGER.icon())
        self.notif_btn.setFixedSize(32, 32)
        self.notif_btn.setFlat(True)
        layout.addWidget(self.notif_btn)

        self.settings_btn = QPushButton()
        self.settings_btn.setIcon(FIF.SETTING.icon())
        self.settings_btn.setFixedSize(32, 32)
        self.settings_btn.setFlat(True)
        layout.addWidget(self.settings_btn)

        self.profile = NavigationAvatarWidget("User", os.path.join(ROOT, "resource", "img", "icon.png"))
        layout.addWidget(self.profile)


class StageWidget(QWidget):
    """Center column: album art + ring visualizer + track info."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(32, 16, 32, 16)

        # Ring visualizer wraps album art
        self.ring = RingVisualizer(self)
        self.ring.setFixedSize(280, 280)
        layout.addWidget(self.ring, 0, Qt.AlignCenter)

        # Track metadata
        self.track_title = QLabel("")
        self.track_title.setStyleSheet("font-size: 21px; font-weight: 700; font-family: 'Sora'; color: #E2E8F0;")
        self.track_title.setAlignment(Qt.AlignCenter)
        layout.addSpacing(16)
        layout.addWidget(self.track_title)

        self.track_artist = QLabel("")
        self.track_artist.setStyleSheet("font-size: 13px; color: #7C8AA5;")
        self.track_artist.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.track_artist)

        layout.addStretch()


class SidebarWidget(QWidget):
    """Fixed-width sidebar with NavigationInterface."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(220)
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
        ("equalizer", "Equalizer", FIF.SETTING, "equalizer"),
        ("settings", "Settings", FIF.SETTING, "settings"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.setWindowIcon(QIcon(os.path.join(ROOT, "resource", "img", "icon.png")))
        self.setWindowTitle("Nocturne")
        self.setMinimumSize(1100, 720)
        self.resize(1280, 800)

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
        self._pages: dict[str, QWidget] = {}
        for key, label, icon, route in self.NAV_ITEMS:
            if key == "home":
                w = HomeInterface(self)
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
                w = EqualizerView(self.equalizer, self)
            else:
                w = BlankWidget(label, self)
            self._pages[key] = w
            self._views.addWidget(w)

        # ── UI components ─────────────────────────────────────────────
        self.player_bar = PlayerBar(self)
        self.player_bar.bind_engine(self.player_engine)
        self.player_bar.play_toggled.connect(self._on_play_toggled)
        self.player_bar.next_requested.connect(self.player_engine.next)
        self.player_bar.prev_requested.connect(self.player_engine.previous)

        self.lyrics_panel = LyricsPanel(self)
        self.stage = StageWidget(self)
        self.top_bar = TopBar(self)

        # ── Build layout ──────────────────────────────────────────────
        self._build_layout()
        apply_theme(QApplication.instance() or QApplication([]))

        # ── Lyrics sync timer ─────────────────────────────────────────
        self._lyrics_timer = QTimer(self)
        self._lyrics_timer.setInterval(300)
        self._lyrics_timer.timeout.connect(self._tick_lyrics)

        # ── Audio worker → visualizer ─────────────────────────────────
        self.audio_worker.spectrum_ready.connect(self.stage.ring.set_spectrum)

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

        col = QHBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self._views, 1)
        self.lyrics_panel.setFixedWidth(300)
        col.addWidget(self.lyrics_panel)

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
                onClick=lambda k=key: self._switch_to(k),
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

    def show_view(self, key: str) -> None:
        self._switch_to(key)
        self.sidebar.nav.setCurrentItem(key)

    # ── Playback ──────────────────────────────────────────────────────

    def _play_track(self, track: Track) -> None:
        """Play a single track."""
        if not track.path or not Path(track.path).exists():
            return

        self._current_track = track
        self.player_engine.load_single(track.path)
        self.player_engine.play()
        self._on_track_changed(track)

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

    def _on_track_changed(self, track: Track) -> None:
        """Update all UI when track changes."""
        # Player bar
        self.player_bar.update_track_info(
            title=track.title,
            artist=track.artist or "",
        )

        # Stage
        self.stage.track_title.setText(track.title)
        self.stage.track_artist.setText(track.artist or "")

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

        # Lyrics
        self._load_lyrics(track)

        # Save state
        self.player_engine.save_state()

    def _on_play_toggled(self) -> None:
        self.player_engine.toggle_play()
        playing = self.player_engine.is_playing
        self.player_bar.set_playing(playing)
        if playing:
            self.audio_worker.start()
            self._lyrics_timer.start()
        else:
            self._lyrics_timer.stop()

    # ── Lyrics ────────────────────────────────────────────────────────

    def _load_lyrics(self, track: Track) -> None:
        """Fetch lyrics from DB cache or .lrc sidecar."""
        conn = get_connection()
        row = conn.execute(
            "SELECT lrc_content FROM lyrics WHERE track_id = ?", (track.id,)
        ).fetchone()
        lrc_content = row[0] if row else None

        lines = LyricsParser.resolve(track.path or "", lrc_content)
        self.lyrics_panel.load_lyrics(lines or [])

    def _tick_lyrics(self) -> None:
        """Called every 300ms to sync lyrics highlight."""
        if self.player_engine.is_playing:
            self.lyrics_panel.highlight_line(self.player_engine.position_ms)

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

    def add_music_folder(self, folder: str) -> None:
        """Add a folder to the scan list."""
        path = Path(folder)
        if path.is_dir() and path not in self._music_folders:
            self._music_folders.append(path)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    app.exec()
