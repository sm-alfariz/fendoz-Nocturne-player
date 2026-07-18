# coding:utf-8
from unittest.mock import patch

from PySide6.QtCore import Qt, QUrl
from PySide6.QtTest import QTest
from qfluentwidgets import FluentIcon

from src.components.link_card import LinkCard, LinkCardView


class TestLinkCard:
    def test_construction(self, qtbot):
        card = LinkCard(FluentIcon.GITHUB, "GitHub", "My repo", "https://github.com")
        qtbot.addWidget(card)

        assert card.width() == 198
        assert card.height() == 220
        assert card.titleLabel.text() == "GitHub"
        assert card.contentLabel.text() == "My repo"
        assert card.url == QUrl("https://github.com")
        assert card.cursor().shape() == Qt.PointingHandCursor

    def test_object_names(self, qtbot):
        card = LinkCard(FluentIcon.CODE, "Code", "Samples", "https://example.com")
        qtbot.addWidget(card)

        assert card.titleLabel.objectName() == "titleLabel"
        assert card.contentLabel.objectName() == "contentLabel"

    @patch("src.components.link_card.QDesktopServices.openUrl")
    def test_mouse_release_opens_url(self, mock_openUrl, qtbot):
        card = LinkCard(FluentIcon.GITHUB, "GitHub", "My repo", "https://github.com")
        qtbot.addWidget(card)

        QTest.mouseRelease(card, Qt.LeftButton)

        mock_openUrl.assert_called_once_with(QUrl("https://github.com"))


class TestLinkCardView:
    def test_construction(self, qtbot):
        view = LinkCardView()
        qtbot.addWidget(view)

        assert view.widget() is view.view

    def test_add_card(self, qtbot):
        view = LinkCardView()
        qtbot.addWidget(view)

        view.addCard(FluentIcon.GITHUB, "GitHub", "Desc", "https://github.com")
        assert view.hBoxLayout.count() >= 1

    def test_add_multiple_cards(self, qtbot):
        view = LinkCardView()
        qtbot.addWidget(view)

        view.addCard(FluentIcon.GITHUB, "A", "a", "https://a.com")
        view.addCard(FluentIcon.CODE, "B", "b", "https://b.com")
        assert view.hBoxLayout.count() == 2
