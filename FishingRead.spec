# -*- mode: python ; coding: utf-8 -*-

import sys
import os

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('read.ico', '.'),
    ],
    hiddenimports=[
        'PyQt5.QtSvg',
        'PyQt5.QtNetwork',
        'PyQt5.sip',
        'fishingread',
        'fishingread.core',
        'fishingread.ui',
        'fishingread.platform',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'PIL', 'pandas', 'numpy',
        'scipy', 'cv2', 'tensorflow', 'torch',
        'test', 'unittest', 'pdb',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='鱼阅',
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
    icon=['read.ico'],
)
