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


signalBus = SignalBus()
