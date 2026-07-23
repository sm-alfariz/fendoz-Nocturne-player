# coding:utf-8
"""
nocturne.__main__ — Entry point for ``python -m nocturne``.
"""

from __future__ import annotations

import sys
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QLoggingCategory, qInstallMessageHandler
from PySide6.QtGui import QColor, QIcon, QPalette

from nocturne.utils.crash_handler import install_crash_handler
install_crash_handler()

# PyInstaller frozen build: point VLC to bundled native libs
if getattr(sys, 'frozen', False):
    _meipass = sys._MEIPASS
    os.environ.setdefault('VLC_PLUGIN_PATH', os.path.join(_meipass, 'vlc_plugins'))
    os.environ.setdefault('PYTHON_VLC_LIB_PATH', os.path.join(_meipass, 'libvlc.so.5'))

QLoggingCategory.setFilterRules("""
    qt.gui.pixmap.warning=false
    qt.qpa.window.warning=false
    qt.qpa.xcb.warning=false
""")

_old_handler = None

def _qt_msg_handler(msg_type, context, msg):
    msg_lower = msg.lower()
    if 'null pixmap' in msg_lower or 'window opacity' in msg_lower or 'propagatesizehints' in msg_lower:
        return
    if _old_handler:
        _old_handler(msg_type, context, msg)

qInstallMessageHandler(_qt_msg_handler)

from nocturne.config.config import cfg, ROOT  # noqa: E402

if cfg.get(cfg.dpiScale) != "Auto":
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
    os.environ["QT_SCALE_FACTOR"] = str(cfg.get(cfg.dpiScale))

app = QApplication(sys.argv)
app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)
app.setQuitOnLastWindowClosed(False)
app.aboutToQuit.connect(lambda: sys.stderr.write("aboutToQuit fired\n"))
app.setWindowIcon(QIcon(os.path.join(ROOT, "resource", "img", "icon.png")))

# Force dark theme before any widgets are created
from qfluentwidgets import setTheme, Theme  # noqa: E402
from qfluentwidgets import qconfig  # noqa: E402
qconfig.set(qconfig.themeMode, Theme.DARK)
setTheme(Theme.DARK)

# Dark palette so native QFileDialog etc render with dark text/background
_qp = QPalette()
_qp.setColor(QPalette.Window, QColor("#0F172A"))
_qp.setColor(QPalette.WindowText, QColor("#E2E8F0"))
_qp.setColor(QPalette.Base, QColor("#1E293B"))
_qp.setColor(QPalette.AlternateBase, QColor("#0F172A"))
_qp.setColor(QPalette.ToolTipBase, QColor("#1E293B"))
_qp.setColor(QPalette.ToolTipText, QColor("#E2E8F0"))
_qp.setColor(QPalette.Text, QColor("#E2E8F0"))
_qp.setColor(QPalette.Button, QColor("#1E293B"))
_qp.setColor(QPalette.ButtonText, QColor("#E2E8F0"))
_qp.setColor(QPalette.BrightText, QColor("#4FC3F7"))
_qp.setColor(QPalette.Link, QColor("#4FC3F7"))
_qp.setColor(QPalette.Highlight, QColor("#1E88E5"))
_qp.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
_qp.setColor(QPalette.PlaceholderText, QColor("#7C8AA5"))
app.setPalette(_qp)

from nocturne.ui.main_window import MainWindow  # noqa: E402
w = MainWindow()
w.show()
app.exec()
