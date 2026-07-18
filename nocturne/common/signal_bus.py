# coding:utf-8
"""
signal_bus.py — Singleton QObject providing application-wide Qt signals.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class SignalBus(QObject):
    """Signal bus"""

    switchToSampleCard = Signal(str, int)
    micaEnableChanged = Signal(bool)
    supportSignal = Signal()
    folder_added = Signal(str)
    scan_started = Signal()
    play_toggled = Signal(bool)


signalBus = SignalBus()
