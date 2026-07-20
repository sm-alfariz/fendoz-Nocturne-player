# coding:utf-8
"""
controllers — Business logic layer for UI views.

Each view has a corresponding controller that owns data access,
business logic, and emits model objects via signals.
Views remain pure QWidget classes with no SQL or business logic.
"""

from __future__ import annotations

from nocturne.ui.controllers.base import Controller
from nocturne.ui.controllers.home_controller import HomeController
from nocturne.ui.controllers.songs_controller import SongsController
from nocturne.ui.controllers.artists_controller import ArtistsController
from nocturne.ui.controllers.albums_controller import AlbumsController
from nocturne.ui.controllers.settings_controller import SettingsController
from nocturne.ui.controllers.main_window_controller import MainWindowController

__all__ = [
    "Controller",
    "HomeController",
    "SongsController",
    "ArtistsController",
    "AlbumsController",
    "SettingsController",
    "MainWindowController",
]
