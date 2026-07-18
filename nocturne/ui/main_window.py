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

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
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

from nocturne.config.config import ROOT, cfg
from nocturne.ui.components.player_bar import PlayerBar
from nocturne.ui.components.lyrics_panel import LyricsPanel
from nocturne.ui.views.blank_widget import BlankWidget
from nocturne.ui.views.home_interface import HomeInterface
from nocturne.ui.views.setting_interface import SettingInterface
from nocturne.ui.views.songs_view import SongsView
from nocturne.ui.views.artists_view import ArtistsView
from nocturne.ui.views.albums_view import AlbumsView
from nocturne.ui.theme.theme_manager import apply_theme


class TopBar(QWidget):
    """Persistent top bar: logo, search, notification, settings, profile."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(48)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)

        # Logo / title
        self.logo = QLabel("Nocturne")
        self.logo.setObjectName("topBarLogo")
        layout.addWidget(self.logo)

        # Search
        self.search = SearchLineEdit(self)
        self.search.setPlaceholderText(self.tr("Search music, artists, albums…"))
        self.search.setFixedWidth(320)
        layout.addSpacing(24)
        layout.addWidget(self.search)

        layout.addStretch()

        # Notifications
        self.notif_btn = QPushButton()
        self.notif_btn.setIcon(FIF.RINGER.icon())
        self.notif_btn.setFixedSize(32, 32)
        self.notif_btn.setFlat(True)
        layout.addWidget(self.notif_btn)

        # Settings shortcut
        self.settings_btn = QPushButton()
        self.settings_btn.setIcon(FIF.SETTING.icon())
        self.settings_btn.setFixedSize(32, 32)
        self.settings_btn.setFlat(True)
        layout.addWidget(self.settings_btn)

        # Profile
        self.profile = NavigationAvatarWidget("User", os.path.join(ROOT, "resource", "img", "icon.png"))
        layout.addWidget(self.profile)


class StageWidget(QWidget):
    """Center column: album art + ring visualizer + track info."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        # Placeholder — will hold AlbumArt + RingVisualizer
        self.placeholder = QLabel("Stage — Album Art + Ring Visualizer")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("color: #7C8AA5; font-size: 14px;")
        layout.addWidget(self.placeholder)


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

        # --- Views (stacked) ---
        self._views = QStackedWidget()
        self._pages = {}
        for key, label, icon, route in self.NAV_ITEMS:
            if key == "home":
                w = HomeInterface(self)
            elif key == "songs":
                w = SongsView(self)
            elif key == "artists":
                w = ArtistsView(self)
            elif key == "albums":
                w = AlbumsView(self)
            elif key == "settings":
                w = SettingInterface(self)
            elif key in ("playlist", "equalizer"):
                w = BlankWidget(label, self)
            else:
                w = BlankWidget(label, self)
            self._pages[key] = w
            self._views.addWidget(w)

        # --- Player bar (bottom) ---
        self.player_bar = PlayerBar(self)

        # --- Lyrics panel (right) ---
        self.lyrics_panel = LyricsPanel(self)

        # --- Stage (center) ---
        self.stage = StageWidget(self)

        # --- Top bar ---
        self.top_bar = TopBar(self)

        # Build layout
        self._build_layout()

        # Apply theme
        apply_theme(QApplication.instance() or QApplication([]))

    def _build_layout(self) -> None:
        """Build the 3-column + top bar + player bar layout."""
        vroot = QVBoxLayout(self)
        vroot.setContentsMargins(0, 0, 0, 0)
        vroot.setSpacing(0)

        # Top bar
        vroot.addWidget(self.top_bar)

        # Middle: sidebar + (stage + lyrics)
        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(0)

        # Sidebar
        self.sidebar = SidebarWidget(self)
        self._setup_navigation()
        middle.addWidget(self.sidebar)

        # Column: stage (stretch) + lyrics panel (fixed 300px)
        col = QHBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self._views, 1)  # stacked views fill the center
        self.lyrics_panel.setFixedWidth(300)
        col.addWidget(self.lyrics_panel)

        middle.addLayout(col, 1)
        vroot.addLayout(middle, 1)

        # Player bar (bottom)
        vroot.addWidget(self.player_bar)

    def _setup_navigation(self) -> None:
        """Populate NavigationInterface with PRD 7-item sidebar."""
        nav = self.sidebar.nav

        route_keys = {}
        for key, label, icon, route_key in self.NAV_ITEMS:
            route_keys[key] = route_key
            kwargs = dict(
                routeKey=route_key,
                text=label,
                icon=icon,
                onClick=lambda k=key: self._switch_to(k),
            )
            if key == "settings":
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

        # Default to home
        nav.setCurrentItem("home")

    def _switch_to(self, key: str) -> None:
        """Switch the stacked widget to the given page key."""
        if key in self._pages:
            self._views.setCurrentWidget(self._pages[key])

    # ── Expose for sub-interfaces ─────────────────────────────────────

    @property
    def current_view(self) -> QWidget | None:
        return self._views.currentWidget()

    def show_view(self, key: str) -> None:
        """Programmatic navigation (e.g. from settings 'open folder')."""
        self._switch_to(key)
        self.sidebar.nav.setCurrentItem(key)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    app.exec()
