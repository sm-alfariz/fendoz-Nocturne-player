# coding:utf-8
"""
style_sheet.py — StyleSheet enum resolving theme-aware QSS file paths.
"""

from __future__ import annotations

import os
from enum import Enum

from qfluentwidgets import StyleSheetBase, Theme, qconfig

from nocturne.config.config import ROOT


class StyleSheet(StyleSheetBase, Enum):
    """Style sheet"""

    LINK_CARD = "link_card"
    SAMPLE_CARD = "sample_card"
    HOME_WIDGET_STYLE = "home_interface"
    SETTING_INTRFACE_STYLE = "setting_interface"

    def path(self, theme=Theme.AUTO):
        theme = qconfig.theme if theme == Theme.AUTO else theme
        return os.path.join(
            ROOT, f"resource/styles/{theme.value.lower()}/{self.value}.qss"
        )
