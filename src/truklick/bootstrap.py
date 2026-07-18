"""First-run bootstrap so a downloaded binary "just works".

A non-coder downloads one file and double-clicks it. They should not have to know
what Playwright or Chromium is. On first launch we check whether the browser is
present and, if not, download it once — with a clear message about what is
happening and roughly how big it is.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .log import get_logger

log = get_logger("bootstrap")


def browsers_dir() -> Path:
    """Where Playwright keeps downloaded browsers, per platform."""
    env = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env:
        return Path(env)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ms-playwright"
    return Path.home() / ".cache" / "ms-playwright"


def configure_frozen_env() -> None:
    """Point a frozen build at the user's real browser cache.

    Inside a PyInstaller bundle, Playwright resolves browsers relative to the
    driver package it unpacks into a temp dir (…/_MEIxxxx/playwright/driver/
    package/.local-browsers), which is empty and thrown away on exit — so it can
    never find the Chromium we downloaded. Pinning PLAYWRIGHT_BROWSERS_PATH to
    the standard per-user cache makes the binary and a normal pip install agree.
    """
    if not getattr(sys, "frozen", False):
        return
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        return
    if sys.platform == "darwin":
        d = Path.home() / "Library" / "Caches" / "ms-playwright"
    elif sys.platform == "win32":
        d = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ms-playwright"
    else:
        d = Path.home() / ".cache" / "ms-playwright"
    d.mkdir(parents=True, exist_ok=True)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(d)


def chromium_present() -> bool:
    """True if a Chromium download is already on disk.

    Deliberately a filesystem check, NOT playwright.sync_api: the sync API raises
    if called from inside a running asyncio loop, and that exception used to be
    swallowed here — making a perfectly working install report as missing and
    print a scary 'could not download' message.
    """
    d = browsers_dir()
    if not d.is_dir():
        return False
    return any(p.is_dir() and p.name.startswith("chromium") for p in d.iterdir())


def ensure_chromium(auto: bool = True) -> bool:
    """Make sure Chromium is installed. Returns True if usable.

    `auto=False` only reports, so a GUI can ask before downloading ~150MB.
    """
    if chromium_present():
        return True
    if not auto:
        return False

    print("=" * 62)
    print("  First run: downloading the browser Truklick drives (~150 MB).")
    print("  This happens once. Please leave this window open.")
    print("=" * 62, flush=True)

    # Works both from source and from a PyInstaller bundle.
    cmds = [[sys.executable, "-m", "playwright", "install", "chromium"]]
    if getattr(sys, "frozen", False):
        # inside a bundle sys.executable is the app itself; use the vendored driver
        try:
            from playwright._impl._driver import compute_driver_executable
            drv = compute_driver_executable()
            cmds.insert(0, [str(drv[0]), *drv[1:], "install", "chromium"]
                        if isinstance(drv, (list, tuple)) else [str(drv), "install", "chromium"])
        except Exception as exc:
            log.debug("could not locate bundled driver: %s", exc)

    for cmd in cmds:
        try:
            r = subprocess.run(cmd, check=False)
            if r.returncode == 0 and chromium_present():
                print("  Browser installed. Continuing...\n", flush=True)
                return True
        except Exception as exc:
            log.debug("install attempt failed (%s): %s", cmd, exc)

    print("\n  Could not download the browser automatically.")
    print("  Fix: install Python 3.12 and run:  playwright install chromium\n")
    return False
