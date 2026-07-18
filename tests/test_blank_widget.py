# coding:utf-8
from PySide6.QtCore import Qt
from qfluentwidgets import SubtitleLabel

from src.views.blank_widget import BlankWidget


class TestBlankWidget:
    def test_construction(self, qtbot):
        widget = BlankWidget("Hello World")
        qtbot.addWidget(widget)

        assert widget.label.text() == "Hello World"
        assert isinstance(widget.label, SubtitleLabel)

    def test_object_name(self, qtbot):
        widget = BlankWidget("My Tasks")
        qtbot.addWidget(widget)

        assert widget.objectName() == "My-Tasks"

    def test_label_alignment(self, qtbot):
        widget = BlankWidget("Test")
        qtbot.addWidget(widget)

        assert widget.label.alignment() == Qt.AlignCenter
