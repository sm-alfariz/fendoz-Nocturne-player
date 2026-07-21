# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Nocturne Music Player.

Build:  pyinstaller nocturne.spec
"""

import sys
from pathlib import Path

block_cipher = None

# ── VLC native libraries ──────────────────────────────────────────
VLC_LIBS_SRC = '/usr/lib'
vlc_binaries = [
    (f'{VLC_LIBS_SRC}/libvlc.so.5', '.'),
    (f'{VLC_LIBS_SRC}/libvlccore.so.9', '.'),
]

# VLC plugins — collect recursively
import os
_vlc_plugins = []
for _root, _dirs, _files in os.walk('/usr/lib/vlc'):
    for _f in _files:
        _src = os.path.join(_root, _f)
        _dst = os.path.join('vlc_plugins', os.path.relpath(_root, '/usr/lib/vlc'), _f)
        _vlc_plugins.append((_src, _dst))

a = Analysis(
    ['nocturne/__main__.py'],
    pathex=[],
    binaries=vlc_binaries,
    datas=[
        ('resource/img/*', 'resource/img'),
        ('resource/styles/*', 'resource/styles'),
        ('config/config.json', 'config'),
    ] + _vlc_plugins,
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'qfluentwidgets',
        'vlc',
        'mutagen',
        'numpy',
        'httpx',
        'sqlite3',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='nocturne',
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

# macOS .app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='Nocturne.app',
        icon='resource/img/icon.png',
        bundle_identifier='com.fendoz.nocturne',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'CFBundleShortVersionString': '0.1.0',
        },
    )
