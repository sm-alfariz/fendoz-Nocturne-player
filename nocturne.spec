# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Nocturne Player — standalone Linux binary."""

import sys
from pathlib import Path

block_cipher = None

ROOT = Path(".").resolve()

a = Analysis(
    ["nocturne/__main__.py"],
    pathex=[],
    binaries=[],
    datas=[
        (str(ROOT / "resource"), "resource"),
        (str(ROOT / "config"), "config"),
    ],
    hiddenimports=[
        "vlc",
        "numpy",
        "scipy._lib",
        "scipy",
        "mutagen",
        "mutagen.id3",
        "mutagen.mp3",
        "mutagen.flac",
        "mutagen.oggvorbis",
        "mutagen.wave",
        "mutagen.mp4",
        "mutagen.asf",
        "mutagen.trueaudio",
        "mutagen.wavpack",
        "mutagen.dsf",
        "sounddevice",
        "darkdetect",
        "colorthief",
        "httpx",
        "h2",
        "hpack",
        "hyperframe",
        "qfluentwidgets",
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtMultimedia",
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="nocturne",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
