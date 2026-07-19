# coding:utf-8
"""
equalizer_controller.py — Business logic for the Equalizer view.
"""

from __future__ import annotations

from typing import Callable, Optional


from nocturne.core.equalizer import Equalizer
from nocturne.ui.controllers.base import Controller


class EqualizerController(Controller):
    """Handles equalizer preset management and band control."""

    def __init__(self, equalizer: Equalizer, assign_callback: Optional[Callable] = None, parent=None) -> None:
        super().__init__(parent)
        self._eq = equalizer
        self._assign_callback = assign_callback

    @property
    def eq(self) -> Equalizer:
        return self._eq

    def all_presets(self) -> dict:
        return Equalizer.all_presets()

    def apply_preset(self, name: str) -> None:
        self._eq.apply_preset(name)

    def set_band(self, index: int, db: float) -> None:
        self._eq.set_band(index, db)

    def save_custom_preset(self, name: str, values: list[float]) -> None:
        self._eq.save_custom_preset(name, values)

    def assign_to_track(self, preset_name: str) -> None:
        if self._assign_callback:
            self._assign_callback(preset_name)
