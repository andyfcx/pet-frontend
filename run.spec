# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules


ROOT = Path.cwd()
SRC = ROOT / "src"
TARGET_ARCH = os.environ.get("TARGET_ARCH", "arm64")
APP_VERSION = os.environ.get("APP_VERSION", "0.1.1")

datas = collect_data_files("customtkinter")
datas += collect_data_files("tkinterdnd2")
binaries = collect_dynamic_libs("tkinterdnd2")

a = Analysis(
    [str(SRC / "biometeo_frontend" / "main.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "tkinterdnd2",
        "customtkinter",
        "pandas",
        "biometeo",
        *collect_submodules("biometeo"),
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Biometeo Frontend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=TARGET_ARCH,
    codesign_identity=None,
    entitlements_file=None,
)
app = BUNDLE(
    exe,
    name="Biometeo Frontend.app",
    icon=None,
    bundle_identifier="org.biometeo.frontend",
    info_plist={
        "CFBundleName": "Biometeo Frontend",
        "CFBundleDisplayName": "Biometeo Frontend",
        "CFBundleIdentifier": "org.biometeo.frontend",
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleVersion": APP_VERSION,
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
    },
)
