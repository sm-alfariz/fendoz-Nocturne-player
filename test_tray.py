"""Test tray icon and close-to-tray behavior."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMainWindow
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

# Check tray availability
print(f"QSystemTrayIcon.isSystemTrayAvailable(): {QSystemTrayIcon.isSystemTrayAvailable()}")
print(f"QSystemTrayIcon.supportsMessages(): {QSystemTrayIcon.supportsMessages()}")

# Create window
w = QMainWindow()
w.setWindowTitle("Tray Test")
w.resize(400, 300)

# Tray icon
icon = QIcon(os.path.join(os.path.dirname(__file__), "../resource/img/icon.png"))
tray = QSystemTrayIcon(icon, w)
tray.setToolTip("Test App")

# Override close
original_close = w.closeEvent
def close_event(event):
    print("closeEvent called — hiding to tray")
    event.ignore()
    w.hide()
    tray.show()
    tray.showMessage("Test", "Hidden to tray", QSystemTrayIcon.Information, 2000)
w.closeEvent = close_event

tray.activated.connect(lambda reason: print(f"Tray activated: {reason}"))

w.show()
print("App started — close the window to test tray")
app.exec()
print("App exited")
