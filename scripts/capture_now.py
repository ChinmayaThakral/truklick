"""
Capture the CURRENT screen of an already-open dashboard (scripts/open_dashboard.py).

Attaches over CDP to the running browser, scans the main frame + every iframe, prints
a labelled list, and saves the full targeting data to ./captures/. Nothing interactive
— so it can be triggered the instant an order popup appears.

RUN:
    python scripts/capture_now.py          # normal list
    python scripts/capture_now.py -l       # longer list
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture_helper import CAPTURE_DIR, collect_from_all_frames, summarize  # noqa: E402

CDP_URL = "http://localhost:9222"


def _pick_page(contexts):
    """Prefer a page that looks like the dashboard; else the first page."""
    pages = [pg for c in contexts for pg in c.pages]
    if not pages:
        return None
    for pg in pages:
        if "p2p.me" in (pg.url or ""):
            return pg
    return pages[0]


async def main():
    limit = 40 if "-l" in sys.argv else 20
    CAPTURE_DIR.mkdir(exist_ok=True)
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(CDP_URL)
        except Exception as exc:
            print(f"✗ Could not attach to {CDP_URL}: {exc}")
            print("  Is scripts/open_dashboard.py still running?")
            return 1

        page = _pick_page(browser.contexts)
        if page is None:
            print("✗ Attached, but found no open pages.")
            return 1

        elements = await collect_from_all_frames(page)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = CAPTURE_DIR / f"capture_{ts}.json"
        artifact = {
            "url": page.url,
            "title": await page.title(),
            "timestamp": ts,
            "element_count": len(elements),
            "elements": elements,
        }
        fname.write_text(json.dumps(artifact, indent=2, ensure_ascii=False),
                         encoding="utf-8")
        print(f"  page: {page.url}")
        summarize(elements, limit)
        print(f"\n  ✓ Saved -> {fname}")
        # NOTE: deliberately not calling browser.close() — that would close the
        # user's live session. Exiting the context manager just disconnects.
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
