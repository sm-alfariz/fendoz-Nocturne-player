# coding:utf-8
"""
blank_widget.py — Generic placeholder widget with centered subtitle label.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import SubtitleLabel, setFont


class BlankWidget(QWidget):
    """Placeholder stub for unimplemented nav items."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.label = SubtitleLabel(text, self)
        self.hBoxLayout = QHBoxLayout(self)

        setFont(self.label, 24)
        self.label.setAlignment(Qt.AlignCenter)
        self.hBoxLayout.addWidget(self.label, 1, Qt.AlignCenter)
        self.setObjectName(text.replace(" ", "-"))
