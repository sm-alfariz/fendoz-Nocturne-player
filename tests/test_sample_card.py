# coding:utf-8
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from qfluentwidgets import FluentIcon

from src.components.sample_card import SampleCard, SampleCardView
from src.common.signal_bus import signalBus


class TestSampleCard:
    def test_construction(self, qtbot):
        card = SampleCard(FluentIcon.ALBUM, "Title", "Content text", "routeKey", 0)
        qtbot.addWidget(card)

        assert card.width() == 360
        assert card.height() == 90
        assert card.titleLabel.text() == "Title"
        assert card.contentLabel.text() == "Content text"
        assert card.routekey == "routeKey"
        assert card.index == 0

    def test_object_names(self, qtbot):
        card = SampleCard(FluentIcon.ALBUM, "T", "C", "rk", 1)
        qtbot.addWidget(card)

        assert card.titleLabel.objectName() == "titleLabel"
        assert card.contentLabel.objectName() == "contentLabel"

    def test_mouse_release_emits_signal(self, qtbot):
        card = SampleCard(FluentIcon.ALBUM, "T", "C", "myRoute", 42)
        qtbot.addWidget(card)

        with qtbot.waitSignal(signalBus.switchToSampleCard, timeout=1000) as blocker:
            QTest.mouseRelease(card, Qt.LeftButton)

        assert blocker.args == ["myRoute", 42]


class TestSampleCardView:
    def test_construction(self, qtbot):
        view = SampleCardView("My Section")
        qtbot.addWidget(view)

        assert view.titleLabel.text() == "My Section"
        assert view.titleLabel.objectName() == "viewTitleLabel"

    def test_add_sample_card(self, qtbot):
        view = SampleCardView("Section")
        qtbot.addWidget(view)

        view.addSampleCard(FluentIcon.ALBUM, "T", "C", "rk", 0)
        assert view.flowLayout.count() >= 1

    def test_add_multiple_cards(self, qtbot):
        view = SampleCardView("Section")
        qtbot.addWidget(view)

        view.addSampleCard(FluentIcon.ALBUM, "A", "a", "rk1", 0)
        view.addSampleCard(FluentIcon.GITHUB, "B", "b", "rk2", 1)
        assert view.flowLayout.count() == 2
