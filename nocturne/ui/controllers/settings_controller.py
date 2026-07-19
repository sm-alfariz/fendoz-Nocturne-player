# coding:utf-8
"""
settings_controller.py — Business logic for the Settings view.
"""

from __future__ import annotations


from nocturne.common.signal_bus import signalBus
from nocturne.data.db import get_db_path
from nocturne.ui.controllers.base import Controller


class SettingsController(Controller):
    """Handles settings actions that involve data or system access."""

    @property
    def crash_log_dir(self) -> str:
        return str(get_db_path().parent)

    def add_folder(self, folder: str) -> None:
        signalBus.folder_added.emit(folder)
