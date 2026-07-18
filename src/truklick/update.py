"""Update checking.

Tells the user when a newer release exists and where to get it.

DELIBERATELY NOT A SILENT SELF-UPDATER — read this before "improving" it:
Truklick drives logged-in sessions, sometimes on financial dashboards. A background
process that downloads an executable and replaces itself turns any compromise of the
release channel (stolen token, hijacked CI, MITM) into arbitrary code execution on
every user's machine, with no human in the loop. Our builds are also unsigned, so
there is nothing to verify a download against. Until releases are signed AND the
signature is checked before install, the honest design is: detect, inform, let the
human choose. See docs/DECISIONS.md ADR-014.

Network behaviour: one short-timeout request, cached on disk, failures ignored
silently. An update check must never delay startup or break a run.
"""
from __future__ import annotations

import json
import os
import sys
import time
import ssl
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import __version__
from .log import get_logger

log = get_logger("update")

RELEASES_API = "https://api.github.com/repos/ChinmayaThakral/truklick/releases/latest"
RELEASES_PAGE = "https://github.com/ChinmayaThakral/truklick/releases/latest"
CHECK_INTERVAL_S = 6 * 3600      # don't hammer the API
_LAST_ERROR: str = ""            # why the last check failed, for reporting
TIMEOUT_S = 4


def _ssl_context() -> Optional[ssl.SSLContext]:
    """A context with CA certs that works inside a frozen binary.

    PyInstaller bundles do not carry the system trust store, so a plain
    urlopen() fails with CERTIFICATE_VERIFY_FAILED for every user of a downloaded
    build — silently, if you are not looking. certifi ships the CA bundle with us.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        try:
            return ssl.create_default_context()
        except Exception:
            return None


@dataclass
class UpdateInfo:
    current: str
    latest: str
    url: str
    available: bool


def _cache_path() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    if base:
        d = Path(base) / "truklick"
    elif sys.platform == "darwin":
        d = Path.home() / "Library" / "Caches" / "truklick"
    elif sys.platform == "win32":
        d = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "truklick"
    else:
        d = Path.home() / ".cache" / "truklick"
    d.mkdir(parents=True, exist_ok=True)
    return d / "update-check.json"


def parse_version(v: str) -> tuple:
    """'v0.1.10' -> (0, 1, 10). Unparsable parts sort low, so junk never looks newer."""
    v = (v or "").strip().lstrip("vV").split("+")[0].split("-")[0]
    out = []
    for part in v.split("."):
        try:
            out.append(int(part))
        except ValueError:
            out.append(-1)
    while len(out) < 3:
        out.append(0)
    return tuple(out[:3])


def is_newer(latest: str, current: str) -> bool:
    return parse_version(latest) > parse_version(current)


def _read_cache() -> Optional[dict]:
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
        if time.time() - float(data.get("checked_at", 0)) < CHECK_INTERVAL_S:
            return data
    except Exception:
        pass
    return None


def _write_cache(tag: str) -> None:
    try:
        _cache_path().write_text(
            json.dumps({"checked_at": time.time(), "latest": tag}), encoding="utf-8")
    except Exception as exc:
        log.debug("could not cache update check: %s", exc)


def check(force: bool = False) -> Optional[UpdateInfo]:
    """Return UpdateInfo, or None if we could not check. Never raises."""
    if not force:
        cached = _read_cache()
        if cached:
            tag = cached.get("latest", "")
            return UpdateInfo(__version__, tag.lstrip("v"), RELEASES_PAGE,
                              is_newer(tag, __version__))
    try:
        req = urllib.request.Request(
            RELEASES_API, headers={"Accept": "application/vnd.github+json",
                                   "User-Agent": f"truklick/{__version__}"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_S,
                                    context=_ssl_context()) as r:
            tag = json.loads(r.read().decode("utf-8")).get("tag_name", "")
    except Exception as exc:
        log.debug("update check failed (ignored): %s", exc)
        globals()["_LAST_ERROR"] = str(exc)
        return None
    if not tag:
        return None
    _write_cache(tag)
    return UpdateInfo(__version__, tag.lstrip("v"), RELEASES_PAGE,
                      is_newer(tag, __version__))


def notify_if_available() -> None:
    """One quiet line at startup when a newer release exists. Never blocks a run."""
    info = check()
    if info and info.available:
        print(f"\n  ── Update available: v{info.latest} "
              f"(you have v{info.current})\n     {info.url}\n", flush=True)
