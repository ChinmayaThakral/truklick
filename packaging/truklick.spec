# PyInstaller spec — one self-contained Truklick executable per OS.
#
# Chromium is NOT bundled (it is ~150MB and licence-awkward to redistribute).
# Instead the app downloads it on first launch via `playwright install chromium`,
# which is the same thing the dev setup does. See truklick.bootstrap.
#
# Build:  pyinstaller packaging/truklick.spec --noconfirm
import sys

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
for pkg in ("playwright", "pynput"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# recipes ship with the binary so a new user has something to run immediately
datas += [("../recipes", "recipes"), ("../examples", "examples")]

a = Analysis(
    ["entry.py"],
    pathex=["../src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["truklick", "truklick.cli", "truklick.gui"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="truklick",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,          # keeps the log visible; the GUI opens in the browser
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
