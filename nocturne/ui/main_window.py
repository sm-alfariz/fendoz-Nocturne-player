# coding:utf-8
"""
main_window.py — 3-column layout with persistent sidebar navigation.

Layout follows 09-screens-and-navigation.md and 05-system-architecture.md.
Business logic is delegated to MainWindowController.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap, QRadialGradient
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMenu,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    FluentIcon as FIF,
    NavigationInterface,
    NavigationItemPosition,
)

from nocturne.config.config import ROOT, cfg
from nocturne.ui.components.player_bar import PlayerBar
from nocturne.ui.icon_utils import artwork_pixmap
from nocturne.ui.components.lyrics_panel import LyricsPanel
from nocturne.ui.components.miniplayer import MiniPlayer
from nocturne.ui.components.scan_progress_overlay import ScanProgressOverlay
from nocturne.ui.components.top_bar import TopBar
from nocturne.ui.components.stage_widget import StageWidget
from nocturne.ui.views.blank_widget import BlankWidget
from nocturne.ui.views.home_interface import HomeInterface
from nocturne.ui.views.setting_interface import SettingInterface
from nocturne.ui.views.songs_view import SongsView
from nocturne.ui.views.artists_view import ArtistsView
from nocturne.ui.views.albums_view import AlbumsView
from nocturne.ui.views.playlist_view import PlaylistView
from nocturne.ui.views.equalizer_view import EqualizerView
from nocturne.ui.theme.tokens import Color
from nocturne.common.signal_bus import signalBus
from nocturne.ui.controllers import MainWindowController
from nocturne.data.db import get_connection
from nocturne.data.models import Track

logger = logging.getLogger(__name__)


class MainWindow(QWidget):
    """Main application window — 3-column layout + player bar.

    Business logic is handled by MainWindowController.
    This class owns UI layout, styling, and signal wiring only.
    """

    NAV_ITEMS = [
        ("home", "Home", FIF.HOME.icon(color=Color.TEXT_DIM), "home"),
        ("songs", "Songs", FIF.MUSIC.icon(color=Color.TEXT_DIM), "songs"),
        ("artists", "Artists", FIF.PEOPLE.icon(color=Color.TEXT_DIM), "artists"),
        ("albums", "Albums", FIF.ALBUM.icon(color=Color.TEXT_DIM), "albums"),
        ("playlist", "Playlist", FIF.MUSIC_FOLDER.icon(color=Color.TEXT_DIM), "playlist"),
        ("equalizer", "Mixer", QIcon(os.path.join(ROOT, "resource", "img", "mixer.png")), "equalizer"),
        ("settings", "Settings", FIF.SETTING.icon(color=Color.TEXT_DIM), "settings"),
    ]

    def __init__(self) -> None:
        super().__init__()
        # self.setWindowIcon(QIcon(os.path.join(ROOT, "resource", "img", "icon.png")))
        self.setWindowTitle("Nocturne")
        self.setMinimumSize(1100, 720)
        self.resize(1280, 800)
        self.setStyleSheet("background:transparent;")

        # ── Controller ────────────────────────────────────────────────
        self.ctrl = MainWindowController(self)

        self._current_track: Optional[Track] = None

        # ── Views ─────────────────────────────────────────────────────
        self._views = QStackedWidget()
        self._views.setStyleSheet(f"background:{Color.BACKGROUND};")
        self._pages: dict[str, QWidget] = {}
        for key, label, _icon, _route in self.NAV_ITEMS:
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
                w = SettingInterface(self.ctrl.settings, self)
                w.scan_requested.connect(self._scan_library)
            elif key == "equalizer":
                w = EqualizerView(self.ctrl.equalizer, assign_callback=self.ctrl._assign_eq_to_track, parent=self)
            elif key == "playlist":
                w = PlaylistView(self)
                w.track_activated.connect(self._play_track)
                w.play_playlist_track.connect(self._play_playlist_track)
            else:
                w = BlankWidget(label, self)
            self._pages[key] = w
            self._views.addWidget(w)

        # ── UI components ─────────────────────────────────────────────
        self.player_bar = PlayerBar(eq_preset=self.ctrl.equalizer.current_preset, parent=self)
        self.player_bar.bind_engine(self.ctrl.player_engine)
        signalBus.play_toggled.connect(self._on_play_toggled)
        self.player_bar.next_requested.connect(self.ctrl.next_track)
        self.player_bar.prev_requested.connect(self.ctrl.prev_track)
        self.player_bar.shuffle_toggled.connect(self._on_shuffle)

        self.lyrics_panel = LyricsPanel(self)
        self.stage = StageWidget(self)
        self.top_bar = TopBar(self)

        # ── Scan progress overlay (on top of everything) ─────────────
        self.scan_overlay = ScanProgressOverlay(self)

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
        self.top_bar.miniplayer_btn.clicked.connect(self._show_miniplayer)

        # Search with debounce (150ms)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(self._on_search_debounced)

        # ── Signal bus connections ────────────────────────────────────
        signalBus.scan_started.connect(self._scan_library)
        signalBus.reduce_motion_changed.connect(self.stage.ring.set_reduce_motion)
        signalBus.playlist_changed.connect(self._rebuild_playlist_nav)
        signalBus.tags_edited.connect(self._refresh_after_tags_edit)
        signalBus.eq_preset_changed.connect(self.player_bar.set_eq_preset)

        # ── Controller connections ────────────────────────────────────
        self.ctrl.track_changed.connect(self._on_track_changed)
        self.ctrl.lyrics_loaded.connect(self._on_lyrics_loaded)
        self.ctrl.scan_complete.connect(self._on_scan_complete)
        self.ctrl.scan_progress.connect(self.scan_overlay.set_progress)
        self.ctrl.volume_restored.connect(self.player_bar.set_volume)

        # ── Audio worker → visualizer + spectrum ──────────────────────
        self.ctrl.audio_worker.spectrum_ready.connect(self._pages["home"].set_spectrum)

        # ── Miniplayer ─────────────────────────────────────────────────
        self.mini_player = MiniPlayer(self.ctrl.player_engine, None)
        self.ctrl.audio_worker.spectrum_ready.connect(self.mini_player.set_spectrum)
        self.mini_player.play_toggled.connect(self.player_bar._toggle_play)
        self.mini_player.next_requested.connect(self.ctrl.next_track)
        self.mini_player.prev_requested.connect(self.ctrl.prev_track)
        self.mini_player.closed.connect(self._restore_from_miniplayer)

        # ── System tray ────────────────────────────────────────────────
        self._setup_tray()
        QApplication.instance().setQuitOnLastWindowClosed(not cfg.closeToTray.value)
        if cfg.closeToTray.value:
            self.setAttribute(Qt.WA_QuitOnClose, False)
            self.tray_icon.show()
            QTimer.singleShot(0, self._remove_close_button)

        # ── Resume playback on startup ────────────────────────────────
        QTimer.singleShot(0, self.ctrl.resume_playback)

        # Initial view data load
        QTimer.singleShot(0, self._load_initial_views)

    def _build_layout(self) -> None:
        vroot = QVBoxLayout(self)
        vroot.setContentsMargins(0, 0, 0, 0)
        vroot.setSpacing(0)
        vroot.addWidget(self.top_bar)

        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(0)

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

        self.nav = NavigationInterface(self, True, True)
        self.nav.setMinimumExpandWidth(800)
        self.nav.setExpandWidth(220)
        self.nav.setStyleSheet(
            f"background:rgba(15,23,42,0.35);border-right:1px solid {Color.BORDER};"
        )
        self.nav.displayModeChanged.connect(self.top_bar.raise_)
        self._setup_navigation()
        middle.addWidget(self.nav)
        middle.addLayout(col, 1)
        vroot.addLayout(middle, 1)
        vroot.addWidget(self.player_bar)

    def _setup_navigation(self) -> None:
        nav = self.nav

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

        from nocturne.data.playlist_manager import PlaylistManager
        pm = PlaylistManager()
        nav.addItem(
            routeKey="playlist_section",
            icon=QIcon(os.path.join(ROOT, "resource", "img", "playlist.png")),
            text="My Playlist",
            position=NavigationItemPosition.SCROLL,
        )
        self._playlist_nav_keys: list[str] = []
        for pl in pm.list_all():
            key = f"playlist_{pl.id}"
            self._playlist_nav_keys.append(key)
            nav.addItem(
                routeKey=key,
                icon=FIF.MUSIC_FOLDER,
                text=pl.name,
                onClick=lambda pid=pl.id: self._nav_playlist_click(pid),
                position=NavigationItemPosition.SCROLL,
                parentRouteKey="playlist_section",
            )

        nav.addItem(
            routeKey="exit_app",
            icon=FIF.CLOSE,
            text="Exit",
            onClick=self._quit_app,
            position=NavigationItemPosition.BOTTOM,
        )

        nav.expand(useAni=False)
        nav.setCurrentItem("home")

    def _switch_to(self, key: str) -> None:
        if key in self._pages:
            self._views.setCurrentWidget(self._pages[key])
            if key == "artists":
                view = self._pages[key]
                if isinstance(view, ArtistsView) and view.grid_layout.count() == 0:
                    view.load(self.ctrl.artists.load_artists())
            elif key == "albums":
                view = self._pages[key]
                if isinstance(view, AlbumsView) and view.grid_layout.count() == 0:
                    view.load(self.ctrl.albums.load_albums())
            elif key == "equalizer" and self._current_track:
                conn = get_connection()
                row = conn.execute(
                    "SELECT eq_preset FROM tracks WHERE id = ?",
                    (self._current_track.id,),
                ).fetchone()
                if hasattr(self._pages[key], "load_for_track"):
                    self._pages[key].load_for_track(
                        row["eq_preset"] if row else None
                    )

    def _rebuild_playlist_nav(self) -> None:
        """Re-read playlists from DB and update the sidebar navigation."""
        for key in self._playlist_nav_keys:
            self.nav.removeWidget(key)
        self._playlist_nav_keys.clear()

        from nocturne.data.playlist_manager import PlaylistManager
        for pl in PlaylistManager().list_all():
            key = f"playlist_{pl.id}"
            self._playlist_nav_keys.append(key)
            self.nav.addItem(
                routeKey=key,
                icon=FIF.MUSIC_FOLDER,
                text=pl.name,
                onClick=lambda pid=pl.id: self._nav_playlist_click(pid),
                position=NavigationItemPosition.SCROLL,
                parentRouteKey="playlist_section",
            )

    def _nav_playlist_click(self, playlist_id: int) -> None:
        self.show_view("playlist")
        pl_view = self._pages.get("playlist")
        if hasattr(pl_view, "detail") and hasattr(pl_view.detail, "load"):
            pl_view.detail.load(playlist_id)

    def show_view(self, key: str) -> None:
        self._switch_to(key)
        self.nav.setCurrentItem(key)

    def _open_soundcloud_dialog(self) -> None:
        from PySide6.QtWidgets import QDialog
        from qfluentwidgets import InfoBar
        from nocturne.ui.components.soundcloud_dialog import SoundCloudDialog
        from nocturne.data.db import upsert_sc_track

        dialog = SoundCloudDialog(self, mode="play")
        if dialog.exec() != QDialog.Accepted:
            return

        tracks_meta = dialog.tracks
        if not tracks_meta:
            return

        for meta in tracks_meta:
            if not meta.get("stream_url"):
                InfoBar.warning(
                    "Skipped track",
                    f"Could not get stream for: {meta.get('title', '?')}",
                    parent=self,
                )
                continue
            track = upsert_sc_track(meta)
            self._play_track(track)
            break  # play first valid track

    # ── Playback ──────────────────────────────────────────────────────

    def _play_playlist_track(self, track: Track, queue: list) -> None:
        if self._current_track and hasattr(self.lyrics_panel, "_offset_ms"):
            self.ctrl.save_lyrics_offset(
                self._current_track, self.lyrics_panel._offset_ms
            )
        self._current_track = track
        self.ctrl.play_track(track, queue)

    def _play_track(self, track: Track) -> None:
        if self._current_track and hasattr(self.lyrics_panel, "_offset_ms"):
            self.ctrl.save_lyrics_offset(
                self._current_track, self.lyrics_panel._offset_ms
            )
        self._current_track = track
        self.ctrl.play_track(track)

    def _play_artist_tracks(self, artist: str) -> None:
        self.ctrl.play_artist_tracks(artist)

    def _play_album_tracks(self, album_id: int) -> None:
        self.ctrl.play_album_tracks(album_id)

    # ── Controller signal handlers ───────────────────────────────────

    def _on_track_changed(self, track: Track) -> None:
        self._current_track = track
        self.player_bar.set_playing(True)
        self._pages["home"].set_playing(True)
        self._lyrics_timer.start()

        self.player_bar.update_track_info(
            title=track.title,
            artist=track.artist or "",
        )

        self.stage.track_title.setText(track.title)
        self.stage.track_artist.setText(track.artist or "")
        home_view = self._pages.get("home")
        if hasattr(home_view, "set_track_info"):
            home_view.set_track_info(track.title, track.artist or "")

        songs = self._pages.get("songs")
        if hasattr(songs, "highlight_track"):
            songs.highlight_track(track.id)

        playlist = self._pages.get("playlist")
        if hasattr(playlist, "highlight_track"):
            playlist.highlight_track(track.id)

        pix = None
        if track.album_id:
            conn = get_connection()
            row = conn.execute(
                "SELECT artwork_blob FROM albums WHERE id = ?", (track.album_id,)
            ).fetchone()
            if row and row[0]:
                pix = artwork_pixmap(track.album_id, row[0], size=300)

        if not pix and track.path and track.source_type == "local":
            # fallback: read artwork directly from file
            try:
                from mutagen import File as MutagenFile
                mf = MutagenFile(track.path)
                if mf:
                    for key in mf:
                        if key.startswith("APIC"):
                            pic = mf[key]
                            if hasattr(pic, "data"):
                                p = QPixmap()
                                if p.loadFromData(pic.data):
                                    pix = p
                                    break
            except Exception:
                logger.warning("Failed to extract artwork from file: %s", track.path)

        if pix:
            self.stage.ring.set_artwork(pix)
            self.player_bar.update_track_info(track.title, track.artist or "", pix)
            self.mini_player.update_track_info(track.title, track.artist or "", pix)
        else:
            self.stage.ring.set_artwork(None)
            self.mini_player.update_track_info(track.title, track.artist or "")


        eq_name = "Flat"
        if track.id:
            conn = get_connection()
            row = conn.execute(
                "SELECT eq_preset FROM tracks WHERE id = ?", (track.id,)
            ).fetchone()
            eq_name = row["eq_preset"] if row and row["eq_preset"] else "Flat"
        self.player_bar.set_eq_preset(eq_name)

    def _on_lyrics_loaded(self, lines, offset_ms: int) -> None:
        self.lyrics_panel.load_lyrics(lines or [])
        self.lyrics_panel.set_offset(offset_ms)

    def _on_scan_complete(self) -> None:
        self.scan_overlay.hide()
        songs_view = self._pages.get("songs")
        if isinstance(songs_view, SongsView):
            tracks = self.ctrl.songs.load_tracks()
            songs_view.load(tracks)

        artists_view = self._pages.get("artists")
        if isinstance(artists_view, ArtistsView):
            rows = self.ctrl.artists.load_artists()
            artists_view.load(rows)

        albums_view = self._pages.get("albums")
        if isinstance(albums_view, AlbumsView):
            rows = self.ctrl.albums.load_albums()
            albums_view.load(rows)

        playlist_view = self._pages.get("playlist")
        if hasattr(playlist_view, "load"):
            playlist_view.load()

    def _refresh_after_tags_edit(self) -> None:
        songs = self._pages.get("songs")
        if isinstance(songs, SongsView):
            songs.load(self.ctrl.songs.load_tracks())

        artists = self._pages.get("artists")
        if isinstance(artists, ArtistsView):
            artists.load(self.ctrl.artists.load_artists())

        albums = self._pages.get("albums")
        if isinstance(albums, AlbumsView):
            albums.load(self.ctrl.albums.load_albums())

    # ── Playback lifecycle ────────────────────────────────────────────

    def _on_shuffle(self) -> None:
        enabled = self.ctrl.toggle_shuffle()
        self.player_bar.shuffle_btn.setChecked(enabled)

    def _on_play_toggled(self, playing: bool) -> None:
        self.player_bar.set_playing(playing)
        self._pages["home"].set_playing(playing)
        if playing:
            if not self.ctrl.audio_worker.isRunning():
                self.ctrl.audio_worker.start()
            self._lyrics_timer.start()
        else:
            self.ctrl.audio_worker.stop()
            self._lyrics_timer.stop()

    # ── Lyrics ────────────────────────────────────────────────────────

    def _load_initial_views(self) -> None:
        songs_view = self._pages.get("songs")
        if isinstance(songs_view, SongsView):
            tracks = self.ctrl.songs.load_tracks()
            songs_view.load(tracks)

        playlist_view = self._pages.get("playlist")
        if hasattr(playlist_view, "load"):
            playlist_view.load()

    def _tick_lyrics(self) -> None:
        if self.ctrl.is_playing:
            self.lyrics_panel.highlight_line(self.ctrl.position_ms)

    def _on_search_debounced(self) -> None:
        text = self.top_bar.search.text().strip()
        for key in ("songs", "artists", "albums"):
            view = self._pages.get(key)
            if hasattr(view, "_filter"):
                view._filter(text)
        if text and self._views.currentWidget() != self._pages.get("songs"):
            self._switch_to("songs")

    # ── Library scanning ──────────────────────────────────────────────

    def _scan_library(self) -> None:
        if not self.ctrl.music_folders:
            self.show_view("settings")
            return
        self.scan_overlay.progress_bar.setValue(0)
        self.scan_overlay.label.setText("Scanning library...")
        self.scan_overlay.show()
        self.scan_overlay.raise_()
        self.ctrl.scan_library()

    def add_music_folder(self, folder: str) -> None:
        self.ctrl.add_music_folder(folder)

    def _really_quit(self) -> None:
        """Clean shutdown without tray — called from Exit action or close when tray off."""
        self.ctrl.audio_worker.stop()
        self.ctrl.player_engine.save_state()
        self.ctrl.player_engine.stop()
        self.ctrl.player_engine.cleanup()
        self._lyrics_timer.stop()
        if self.mini_player:
            self.mini_player._timer.stop()


    def _remove_close_button(self) -> None:
        """Strip the OS close button from title bar."""
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self.show()

    def closeEvent(self, event) -> None:
        """On tray mode, ignore close — user must use Exit button or tray."""
        if cfg.closeToTray.value and self.tray_icon:
            self.hide()
            if self.mini_player and self.mini_player.isVisible():
                self.mini_player.hide()
            self.tray_icon.show()
            return
        event.accept()
        self._really_quit()

    def _make_miniplayer_icon(self) -> QIcon:
        """Generate a miniplayer-relevant tray icon programmatically."""
        size = 64
        px = QPixmap(size, size)
        px.fill(Qt.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.Antialiasing)

        # Miniplayer body (rounded rect)
        from nocturne.ui.theme.tokens import Color
        body_color = QColor(Color.ACCENT)
        path = QPainterPath()
        path.addRoundedRect(6, 10, 52, 44, 8, 8)
        p.fillPath(path, body_color)

        # Play triangle
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffffff"))
        tri = QPainterPath()
        tri.moveTo(28, 22)
        tri.lineTo(28, 42)
        tri.lineTo(44, 32)
        tri.closeSubpath()
        p.drawPath(tri)

        # Mini bar at bottom (progress indicator)
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(12, 46, 40, 3, 1, 1)

        p.end()
        return QIcon(px)

    def _setup_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(self._make_miniplayer_icon(), self)
        self.tray_icon.setToolTip("Nocturne - Miniplayer")

        menu = QMenu()

        self._tray_show_player = menu.addAction("Show Player")
        self._tray_show_player.triggered.connect(self._show_from_tray)

        self._tray_show_miniplayer = menu.addAction("Show Miniplayer")
        self._tray_show_miniplayer.triggered.connect(self._show_miniplayer)

        menu.addSeparator()

        self._tray_next = menu.addAction("Next Track")
        self._tray_next.triggered.connect(self.ctrl.next_track)

        self._tray_prev = menu.addAction("Previous Track")
        self._tray_prev.triggered.connect(self.ctrl.prev_track)

        self._tray_play = menu.addAction("Pause")
        self._tray_play.triggered.connect(self._tray_toggle_play)

        menu.addSeparator()

        exit_action = menu.addAction("Exit App")
        exit_action.triggered.connect(self._quit_app)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_from_tray()

    def _show_from_tray(self) -> None:
        if self.mini_player and self.mini_player.isVisible():
            self.mini_player.hide()
        self.showNormal()
        self.activateWindow()
        self.tray_icon.hide()

    def _show_miniplayer(self) -> None:
        if not self.mini_player:
            return
        self.hide()
        # Center on screen
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.center().x() - self.mini_player.width() // 2
            y = geo.bottom() - self.mini_player.height() - 60
            self.mini_player.move(x, y)
        self.mini_player.show()

    def _restore_from_miniplayer(self) -> None:
        self._show_from_tray()

    def _tray_toggle_play(self) -> None:
        if self.ctrl.player_engine.is_playing:
            self.ctrl.player_engine.pause()
            self._tray_play.setText("Play")
        else:
            self.ctrl.player_engine.play()
            self._tray_play.setText("Pause")

    def _quit_app(self) -> None:
        self.tray_icon.hide()
        self.mini_player._timer.stop()
        self.ctrl.audio_worker.stop()
        self.ctrl.player_engine.save_state()
        self.ctrl.player_engine.stop()
        self.ctrl.player_engine.cleanup()
        self._lyrics_timer.stop()
        QApplication.quit()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        g1 = QRadialGradient(0, 0, max(w, h) * 0.7)
        g1.setColorAt(0, QColor(30, 136, 229, 40))
        g1.setColorAt(1, QColor(10, 15, 30, 0))
        painter.fillRect(self.rect(), g1)

        g2 = QRadialGradient(w, h, max(w, h) * 0.7)
        g2.setColorAt(0, QColor(79, 195, 247, 25))
        g2.setColorAt(1, QColor(10, 15, 30, 0))
        painter.fillRect(self.rect(), g2)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    app.exec()
