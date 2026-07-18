# coding:utf-8
"""
Nocturne — premium offline-first desktop music player.
Entry point: ``python main.py`` or ``python -m nocturne``
"""

import sys
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QLoggingCategory, qInstallMessageHandler

# filter noisy Qt warnings from third-party widgets
QLoggingCategory.setFilterRules("""
    qt.gui.pixmap.warning=false
    qt.qpa.window.warning=false
    qt.qpa.xcb.warning=false
""")

# fallback: silence Qt warnings that bypass categories
_old_handler = None
def _qt_msg_handler(msg_type, context, msg):
    msg_lower = msg.lower()
    if 'null pixmap' in msg_lower or 'window opacity' in msg_lower or 'propagatesizehints' in msg_lower:
        return
    if _old_handler:
        _old_handler(msg_type, context, msg)

qInstallMessageHandler(_qt_msg_handler)

# enable dpi scale
from nocturne.config.config import cfg

if cfg.get(cfg.dpiScale) != "Auto":
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
    os.environ["QT_SCALE_FACTOR"] = str(cfg.get(cfg.dpiScale))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)

    from qfluentwidgets import setTheme, Theme
    setTheme(Theme.DARK)

    from nocturne.ui.main_window import MainWindow
    w = MainWindow()
    w.show()
    app.exec()
