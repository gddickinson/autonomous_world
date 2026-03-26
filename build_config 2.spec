# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Autonomous World.

This spec file provides fine-grained control over the build.
Usage:
    pyinstaller build_config.spec

For most builds, use build.py instead — it generates an equivalent spec
automatically and handles platform detection.
"""

import os
import sys

block_cipher = None

ROOT = os.path.dirname(os.path.abspath(SPEC))
SEP = ';' if sys.platform == 'win32' else ':'

# Collect data directories
datas = []
for name in ('game', 'data'):
    src = os.path.join(ROOT, name)
    if os.path.isdir(src):
        datas.append((src, name))

a = Analysis(
    [os.path.join(ROOT, 'play.py')],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'pygame',
        'numpy',
        'json',
        'threading',
        'socket',
        'game.main',
        'game.settings',
        'game.network.server',
        'game.network.client',
        'game.network.protocol',
        'game.network.coop_quests',
        'game.network.pvp_arena',
        'game.network.player_trade',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'email',
        'xml',
        'pydoc',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AutonomousWorld',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, 'icon.ico') if os.path.isfile(
        os.path.join(ROOT, 'icon.ico')) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AutonomousWorld',
)

# macOS .app bundle (only built on macOS)
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='AutonomousWorld.app',
        icon=os.path.join(ROOT, 'icon.icns') if os.path.isfile(
            os.path.join(ROOT, 'icon.icns')) else None,
        bundle_identifier='com.autonomousworld.game',
        info_plist={
            'CFBundleName': 'Autonomous World',
            'CFBundleDisplayName': 'Autonomous World',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0.0',
            'NSHighResolutionCapable': True,
        },
    )
