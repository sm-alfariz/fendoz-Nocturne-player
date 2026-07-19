# coding:utf-8
"""
base.py — Abstract base for all controllers.
"""

from __future__ import annotations

from PySide6.QtCore import QObject


class Controller(QObject):
    """Base class for all page/view controllers.

    Subclasses own data access and business logic,
    emitting typed signals for the UI layer to consume.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
