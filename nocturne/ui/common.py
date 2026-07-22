# coding:utf-8
"""
common.py — Shared UI helpers to avoid duplication across views/components.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLayoutItem, QWidget

from nocturne.ui.theme.tokens import Color


def fmt_ms(ms: int) -> str:
    """Format milliseconds to m:ss."""
    if ms < 0:
        ms = 0
    total_s = ms // 1000
    m, s = divmod(total_s, 60)
    return f"{m}:{s:02d}"


def clear_flow_layout(layout) -> None:
    """Remove all widgets from a FlowLayout."""
    while layout.count():
        item = layout.takeAt(0)
        if isinstance(item, QWidget):
            item.deleteLater()
        elif isinstance(item, QLayoutItem):
            w = item.widget()
            if w:
                w.deleteLater()


def make_empty_label(text: str, parent: QWidget | None = None) -> QWidget:
    """Create a centered empty-state label with standard styling."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel
    label = QLabel(text, parent)
    label.setAlignment(Qt.AlignCenter)
    label.setStyleSheet(f"color:{Color.TEXT_DIM};font-size:16px;padding:60px;")
    return label


TITLE_STYLE = f"font-family:'Sora';font-size:24px;font-weight:700;color:{Color.TEXT_PRIMARY};"
