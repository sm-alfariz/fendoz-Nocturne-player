# coding:utf-8
"""
blank_widget.py
Last updated: 2026-07-08

Generic placeholder widget with a centered subtitle label. Used as a stub
for nav items that lack a real implementation.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import SubtitleLabel, setFont


class BlankWidget(QWidget):
    """
    just example in real change this with your widget

    Args:
        QWidget (): _description_
    """

    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.label = SubtitleLabel(text, self)
        self.hBoxLayout = QHBoxLayout(self)

        setFont(self.label, 24)
        self.label.setAlignment(Qt.AlignCenter)
        self.hBoxLayout.addWidget(self.label, 1, Qt.AlignCenter)
        self.setObjectName(text.replace(" ", "-"))
