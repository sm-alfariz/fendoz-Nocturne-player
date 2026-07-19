# coding:utf-8
"""
theme_manager.py — Load QSS + fonts into QApplication.

Single source of truth for applying the design system (08-design-system.md).
"""

from __future__ import annotations

import os

from PySide6.QtCore import QDir
from PySide6.QtGui import QFontDatabase

from nocturne.config.config import ROOT


def apply_theme(app) -> None:
    """Load base QSS and register font families on ``app``."""
    # Load base QSS
    base_qss = os.path.join(ROOT, "resource", "styles", "base.qss")
    if os.path.isfile(base_qss):
        with open(base_qss, encoding="utf-8") as f:
            qss = f.read()
        app.setStyleSheet(app.styleSheet() + qss)

    # Register font directories (app may bundle fonts in resource/fonts/)
    fonts_dir = os.path.join(ROOT, "resource", "fonts")
    if os.path.isdir(fonts_dir):
        QDir.addSearchPath("fonts", fonts_dir)
        for f in os.listdir(fonts_dir):
            QFontDatabase.addApplicationFont(os.path.join(fonts_dir, f))
