# coding: utf-8
"""
signal_bus.py
Last updated: 2026-07-08

Singleton QObject providing application-wide Qt signals for cross-component
communication: navigation, theme toggles, support actions.
"""

from PySide6.QtCore import QObject, Signal


class SignalBus(QObject):
    """Signal bus"""

    switchToSampleCard = Signal(str, int)
    micaEnableChanged = Signal(bool)
    supportSignal = Signal()


signalBus = SignalBus()
