# coding:utf-8
"""
crash_handler.py — Global exception hook that logs uncaught exceptions
to a local file (no telemetry).  (FR-8.2)
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path


def get_log_dir() -> Path:
    """Return platform-appropriate directory for crash logs."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Logs"
    else:
        base = Path.home() / ".local" / "share"
    log_dir = base / "nocturne"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_log_path() -> Path:
    return get_log_dir() / "nocturne_crash.log"


def _exception_hook(exc_type, exc_value, exc_tb) -> None:
    """Custom excepthook that writes to nocturne_crash.log."""
    # Don't intercept keyboard interrupt
    if exc_type is KeyboardInterrupt:
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

    log_entry = (
        f"--- {timestamp} ---\n"
        f"Type: {exc_type.__name__}\n"
        f"Value: {exc_value}\n"
        f"Traceback:\n{tb_text}\n"
    )

    try:
        log_path = get_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception:
        pass  # Fail silently — don't crash the crash handler

    # Still print to stderr so user sees it in terminal
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def install_crash_handler() -> None:
    """Override sys.excepthook with the custom handler."""
    sys.excepthook = _exception_hook
