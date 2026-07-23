# coding:utf-8
"""
scan_worker.py — Library scan worker for background QThread execution.

Runs LibraryScanner.scan() in a worker thread, emitting Qt signals
so the UI stays responsive during large scans.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from nocturne.data.library_scanner import LibraryScanner


class ScanWorker(QObject):
    """Run LibraryScanner.scan() in a background thread via QThread.

    Emit Qt signals so UI stays responsive during large scans.
    Creates its own SQLite connection (check_same_thread=False) in run().
    """

    progress = Signal(int, int)  # current, total
    finished = Signal(int, int)  # new_tracks, updated_tracks

    def __init__(self, folders: list[Path], db_path: str | Path, parent=None):
        super().__init__(parent)
        self._folders = folders
        self._db_path = db_path

    def run(self) -> None:
        """Call this from QThread.started — wraps scanner with signal forwarding."""
        import sqlite3

        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")

        scanner = LibraryScanner(conn)
        scanner._signals.progress = lambda c, t: self.progress.emit(c, t)
        scanner._signals.finished = lambda n, u: self.finished.emit(n, u)
        scanner.scan(self._folders)
        conn.close()
