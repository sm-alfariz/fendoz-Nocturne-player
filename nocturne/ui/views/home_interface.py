# coding:utf-8
"""
home_interface.py — Home page: BannerWidget (gradient + link cards) in ScrollArea.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, ScrollArea, isDarkTheme

from nocturne.common.style_sheet import StyleSheet
from nocturne.ui.components.link_card import LinkCardView
from nocturne.config.config import EXAMPLE_URL, FEEDBACK_URL, HELP_URL, REPO_URL, ROOT


class BannerWidget(QWidget):
    """Banner widget"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFixedHeight(336)

        self.vBoxLayout = QVBoxLayout(self)
        self.galleryLabel = QLabel("FdZ PySide6 + qfluentwidgets ", self)
        self.banner = QPixmap(os.path.join(ROOT, "resource/img/header1.png"))
        self.linkCardView = LinkCardView(self)

        self.galleryLabel.setObjectName("galleryLabel")

        self.vBoxLayout.setSpacing(0)
        self.vBoxLayout.setContentsMargins(0, 20, 0, 0)
        self.vBoxLayout.addWidget(self.galleryLabel)
        self.vBoxLayout.addWidget(self.linkCardView, 1, Qt.AlignBottom)
        self.vBoxLayout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.linkCardView.addCard(
            os.path.join(ROOT, "resource/img/icon.png"),
            self.tr("Getting started"),
            self.tr("An overview of app development options and samples."),
            HELP_URL,
        )

        self.linkCardView.addCard(
            FluentIcon.GITHUB,
            self.tr("GitHub repo"),
            self.tr("The latest fluent design controls and styles for your applications."),
            REPO_URL,
        )

        self.linkCardView.addCard(
            FluentIcon.CODE,
            self.tr("Code samples"),
            self.tr("Find samples that demonstrate specific tasks, features and APIs."),
            EXAMPLE_URL,
        )

        self.linkCardView.addCard(
            FluentIcon.FEEDBACK,
            self.tr("Send feedback"),
            self.tr("Help us improve PyQt-Fluent-Widgets by providing feedback."),
            FEEDBACK_URL,
        )

    def paintEvent(self, e):
        super().paintEvent(e)
        painter = QPainter(self)
        painter.setRenderHints(QPainter.SmoothPixmapTransform | QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)
        w, h = self.width(), self.height()
        path.addRoundedRect(QRectF(0, 0, w, h), 10, 10)
        path.addRect(QRectF(0, h - 50, 50, 50))
        path.addRect(QRectF(w - 50, 0, 50, 50))
        path.addRect(QRectF(w - 50, h - 50, 50, 50))
        path = path.simplified()

        gradient = QLinearGradient(0, 0, 0, h)

        if not isDarkTheme():
            gradient.setColorAt(0, QColor(207, 216, 228, 255))
            gradient.setColorAt(1, QColor(207, 216, 228, 0))
        else:
            gradient.setColorAt(0, QColor(0, 0, 0, 255))
            gradient.setColorAt(1, QColor(0, 0, 0, 0))

        painter.fillPath(path, QBrush(gradient))

        pixmap = self.banner.scaled(
            self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation
        )
        painter.fillPath(path, QBrush(pixmap))


class HomeInterface(ScrollArea):
    """Home interface"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.banner = BannerWidget(self)
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)

        self.__initWidget()

    def __initWidget(self):
        self.view.setObjectName("view")
        self.setObjectName("homeInterface")
        StyleSheet.HOME_WIDGET_STYLE.apply(self)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.vBoxLayout.setContentsMargins(0, 0, 0, 36)
        self.vBoxLayout.setSpacing(40)
        self.vBoxLayout.addWidget(self.banner)
        self.vBoxLayout.setAlignment(Qt.AlignTop)
