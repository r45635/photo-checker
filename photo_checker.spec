# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Photo Checker — macOS self-contained .app bundle."""

from pathlib import Path

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "api" / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Pre-built Next.js static frontend
        (str(ROOT / "web" / "out"), "web/out"),
        # photo_checker.py imported at runtime by _do_scan
        (str(ROOT / "photo_checker.py"), "."),
    ],
    hiddenimports=[
        # uvicorn internals
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        # fastapi / starlette
        "fastapi",
        "fastapi.staticfiles",
        "starlette.staticfiles",
        "starlette.middleware.cors",
        # image / video
        "PIL",
        "PIL.Image",
        "PIL.JpegImagePlugin",
        "pillow_heif",
        # Apple Photos
        "osxphotos",
        "osxphotos.photosdb",
        # misc
        "send2trash",
        "multipart",
        "python_multipart",
        "email",
        "email.mime",
        "email.mime.text",
        "distutils",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="photo-checker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,        # No terminal window in .app
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
    name="photo-checker",
)

app_bundle = BUNDLE(
    coll,
    name="Photo Checker.app",
    icon=None,
    bundle_identifier="com.vcruvellier.photo-checker",
    info_plist={
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleDisplayName": "Photo Checker",
        "NSHighResolutionCapable": True,
        "NSAppleEventsUsageDescription": "Photo Checker uses Apple Events to control Photos.app.",
        "NSAppleScriptEnabled": True,
        # Full Disk Access is required for osxphotos — prompt the user if needed
        "NSDesktopFolderUsageDescription": "Photo Checker needs access to read your photo library.",
        "NSDocumentsFolderUsageDescription": "Photo Checker needs access to read your photos.",
        "NSRemovableVolumesUsageDescription": "Photo Checker needs access to read photos on external drives.",
    },
)
