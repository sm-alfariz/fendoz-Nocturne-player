# coding:utf-8
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

# Ensure ROOT is on sys.path so `src` becomes importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def pytest_configure():
    """Prevent QApplication::arguments() warning in headless runs."""
    # Already set by pytest-qt's qapp fixture, but ensure OpenGL sharing
    # for headless CI environments
    pass
