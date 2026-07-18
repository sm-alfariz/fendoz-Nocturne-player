# coding:utf-8
import os

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPixmap, QPainter, QColor, QBrush, QPainterPath, QLinearGradient
from PySide6.QtTest import QTest

from qfluentwidgets import isDarkTheme

from src.views.home_window import BannerWidget, HomeInterface
from src.components.link_card import LinkCardView


class TestBannerWidget:
    def test_construction(self, qtbot):
        banner = BannerWidget()
        qtbot.addWidget(banner)

        assert banner.height() == 336
        assert banner.galleryLabel.text() == "FdZ PySide6 + qfluentwidgets "
        assert isinstance(banner.linkCardView, LinkCardView)

    def test_has_four_link_cards(self, qtbot):
        banner = BannerWidget()
        qtbot.addWidget(banner)

        # 4 cards added in __init__
        assert banner.linkCardView.hBoxLayout.count() == 4

    def _simulate_paint(self, banner):
        """Call paintEvent directly so coverage tracks it."""
        from PySide6.QtWidgets import QStyleOption

        # Create a fake paint event
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QPaintEvent, QRegion

        pe = QPaintEvent(QRectF(0, 0, banner.width(), banner.height()).toRect())
        banner.paintEvent(pe)

    def test_paint_event_runs(self, qtbot):
        """paintEvent executes without error (covers QPainter path + gradient + pixmap)."""
        banner = BannerWidget()
        qtbot.addWidget(banner)
        banner.resize(800, 336)

        self._simulate_paint(banner)

        assert banner.banner is not None
        assert not banner.banner.isNull()

    def test_paint_event_dark_theme(self, qtbot):
        """covers the dark-theme branch inside paintEvent."""
        from qfluentwidgets import qconfig, Theme

        banner = BannerWidget()
        qtbot.addWidget(banner)
        banner.resize(800, 336)

        old_theme = qconfig.theme
        qconfig.theme = Theme.DARK

        try:
            self._simulate_paint(banner)
        finally:
            qconfig.theme = old_theme

    def test_paint_event_light_theme(self, qtbot):
        """covers the light-theme branch inside paintEvent (lines 84-85)."""
        from qfluentwidgets import qconfig, Theme

        banner = BannerWidget()
        qtbot.addWidget(banner)
        banner.resize(800, 336)

        old_theme = qconfig.theme
        qconfig.theme = Theme.LIGHT

        try:
            self._simulate_paint(banner)
        finally:
            qconfig.theme = old_theme


class TestHomeInterface:
    def test_construction(self, qtbot):
        home = HomeInterface()
        qtbot.addWidget(home)

        assert home.objectName() == "homeInterface"
        assert home.widget() is home.view
        assert home.horizontalScrollBarPolicy().name == "ScrollBarAlwaysOff"

    def test_contains_banner(self, qtbot):
        home = HomeInterface()
        qtbot.addWidget(home)

        assert isinstance(home.banner, BannerWidget)
