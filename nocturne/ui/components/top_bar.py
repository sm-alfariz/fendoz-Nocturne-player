# coding:utf-8
"""Top bar widget — logo, search, miniplayer/settings/SC buttons."""

from __future__ import annotations

import os

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget
from qfluentwidgets import FluentIcon as FIF

from nocturne.config.config import ROOT, cfg
from nocturne.ui.theme.tokens import Color, Fonts, FontWeights


class TopBar(QWidget):
    """Persistent top bar: logo + search + icons (mockup style)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 12, 0)
        layout.setSpacing(12)

        logo_row = QHBoxLayout()
        logo_row.setSpacing(5)
        logo_icon = QLabel()
        logo_icon.setFixedSize(32, 32)
        logo_icon.setPixmap(
            QIcon(os.path.join(ROOT, "resource", "img", "icon.png")).pixmap(32, 32)
        )
        logo_row.addWidget(logo_icon)
        logo_text = QLabel("Nocturne")
        logo_text.setStyleSheet(
            f"font-family:'{Fonts.DISPLAY}';font-weight:{FontWeights.LOGO};"
            f"font-size:18px;letter-spacing:0.5px;color:{Color.TEXT_PRIMARY};background:transparent;"
        )
        logo_row.addWidget(logo_text)
        layout.addLayout(logo_row)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Cari lagu, artis, atau album...")
        self.search.setFixedWidth(420)
        self.search.addAction(FIF.SEARCH.icon(), QLineEdit.LeadingPosition)
        self.search.setStyleSheet(
            f"background:{Color.CARD_SOFT};border:1px solid {Color.BORDER};"
            f"border-radius:12px;padding:7px 14px 7px 7px;"
            f"color:{Color.TEXT_PRIMARY};font-size:13px;outline:none;"
            f"selection-background-color:{Color.ACCENT};"
        )
        layout.addWidget(self.search)

        layout.addStretch()

        self.miniplayer_btn = QPushButton()
        self.miniplayer_btn.setIcon(FIF.MINIMIZE.icon(color=Color.TEXT_DIM))
        self.miniplayer_btn.setFixedSize(32, 32)
        self.miniplayer_btn.setFlat(True)
        self.miniplayer_btn.setToolTip("Switch to Miniplayer")
        self._style_icon_btn(self.miniplayer_btn)
        layout.addWidget(self.miniplayer_btn)

        self.settings_btn = QPushButton()
        self.settings_btn.setIcon(FIF.SETTING.icon(color=Color.TEXT_DIM))
        self.settings_btn.setFixedSize(32, 32)
        self.settings_btn.setFlat(True)
        self.settings_btn.setStyleSheet(self.miniplayer_btn.styleSheet())
        layout.addWidget(self.settings_btn)

        self.sc_btn = QPushButton()
        self.sc_btn.setIcon(FIF.CLOUD.icon())
        self.sc_btn.setFixedSize(32, 32)
        self.sc_btn.setFlat(True)
        self.sc_btn.setStyleSheet(self.miniplayer_btn.styleSheet())
        self.sc_btn.setToolTip("Search SoundCloud")
        self.sc_btn.setVisible(cfg.onlineEnabled.value)
        cfg.onlineEnabled.valueChanged.connect(self.sc_btn.setVisible)
        layout.addWidget(self.sc_btn)

    def _style_icon_btn(self, btn: QPushButton) -> None:
        btn.setStyleSheet(
            f"QPushButton{{background:{Color.CARD_SOFT};border:1px solid {Color.BORDER};"
            f"border-radius:11px;color:{Color.TEXT_DIM};}}"
            f"QPushButton:hover{{color:{Color.ACCENT};border-color:{Color.ACCENT};"
            f"box-shadow:0 0 14px rgba(79,195,247,0.25);}}"
        )
