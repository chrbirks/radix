# PyInstaller spec for Radix.
#
# Deliberate choices (see plan):
# - onedir, NOT onefile: onefile self-extracts to temp on every launch (slow
#   starts) and trips AV heuristics on Windows.
# - no UPX: corrupts Qt DLLs and trips AV heuristics.
# - Qt modules we don't import are excluded to keep the bundle lean; PySide6
#   Essentials only (enforced in pyproject.toml, not here).

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis

EXCLUDED_QT = [
    "PySide6.QtNetwork",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtConcurrent",
    "PySide6.QtHelp",
    "PySide6.QtUiTools",
    "PySide6.QtDesigner",
    "PySide6.QtPrintSupport",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtXml",
]

a = Analysis(
    ["entry.py"],
    pathex=["../src"],
    binaries=[],
    datas=[
        ("../src/radix/ui_qt/fonts", "radix/ui_qt/fonts"),
        ("../src/radix/ui_qt/icons", "radix/ui_qt/icons"),
        # Linux desktop integration (unused on Windows, harmless to include):
        # copy these into ~/.local/share/{applications,icons/hicolor} so
        # Wayland compositors resolve the app's icon by desktop-file id
        # instead of showing the generic executable icon. See README.
        ("radix.desktop", "."),
        ("icons/hicolor", "icons/hicolor"),
    ],
    hiddenimports=[],
    excludes=["tkinter", "test", "unittest", "pydoc_data", *EXCLUDED_QT],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="radix",
    debug=False,
    strip=False,
    upx=False,
    console=False,  # GUI app; -e still works because stdout is inherited when present
    icon="icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="radix",
)
