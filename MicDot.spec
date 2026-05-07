# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

webview_datas, webview_binaries, webview_hiddenimports = collect_all("webview")

a = Analysis(
    ["micdot/main.py"],
    pathex=[],
    binaries=webview_binaries,
    datas=webview_datas,
    hiddenimports=[
        *webview_hiddenimports,
        "pystray._darwin",
        "pynput.keyboard._darwin",
        "pynput.mouse._darwin",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MicDot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="MicDot",
)
app = BUNDLE(
    coll,
    name="MicDot.app",
    icon=None,
    bundle_identifier="com.micdot.app",
    info_plist={
        "CFBundleName": "MicDot",
        "CFBundleDisplayName": "MicDot",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "LSUIElement": True,
        "NSAccessibilityUsageDescription": (
            "MicDot listens for the global mute hotkey."
        ),
    },
)
