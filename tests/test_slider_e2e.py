"""End-to-end proof of the slide-to-accept path (P2P.me flow change, 2026-08-05).

Two things this guards, both through the real engine (not a PoC):

1. min_width picks the WIDE track, not the narrow inner label. The matching text
   "Slide to Accept" appears on both a ~400px track and a ~105px <p> inside it;
   without min_width the resolver lands on the label and the drag spans ~105px and
   never accepts. This is the exact trap the field record calls out.

2. The safety gate: a trusted drag across "Slide to Accept" fires accept (isTrusted)
   and leaves "Slide to Complete" — the money step — completely untouched. This is
   the gate the field record says must pass before going live.

Skipped automatically if Playwright's Chromium isn't installed.
"""
import asyncio
from pathlib import Path

import pytest

pytest.importorskip("playwright")

from truklick import targeting  # noqa: E402
from truklick.browser import BrowserConfig, BrowserManager  # noqa: E402
from truklick.cdp_input import Input  # noqa: E402

SLIDER = (Path(__file__).resolve().parent.parent / "examples" / "slider.html")

ACCEPT = {"text": "Slide to Accept", "exact": True, "min_width": 300}
ACCEPT_NO_WIDTH = {"text": "Slide to Accept", "exact": True}


async def _run(tmp_path) -> dict:
    bm = BrowserManager(BrowserConfig(profile_dir=tmp_path / "profile", headless=True))
    await bm.start()
    try:
        page = await bm.ensure_page()
        await page.goto(SLIDER.as_uri(), wait_until="domcontentloaded")

        # (1) min_width selects the wide track; without it we get the narrow label.
        track = await targeting.find_click_point(page, ACCEPT)
        assert track is not None, "min_width target did not resolve"
        label = await targeting.find_click_point(page, ACCEPT_NO_WIDTH)
        assert label is not None, "no-width target did not resolve"

        # (2) trusted drag across the track, with an end-hold, like the recipe.
        cdp = await bm.new_cdp_session(page)
        inp = Input(cdp)
        x1 = track.x + 24
        x2 = track.x + track.width - 4
        await inp.drag(x1, track.cy, x2, track.cy, steps=30,
                       step_delay_s=0.006, hold_ms=120)
        await asyncio.sleep(0.2)

        return {
            "track_w": track.width,
            "label_w": label.width,
            "accept": await page.evaluate("window.__accept || null"),
            "complete": await page.evaluate("window.__complete || null"),
        }
    finally:
        await bm.stop()


def test_slide_to_accept(tmp_path):
    try:
        r = asyncio.run(_run(tmp_path))
    except Exception as exc:
        if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc):
            pytest.skip("Chromium not installed (run: playwright install chromium)")
        raise

    # min_width grabbed the 400px track; the bare target grabbed the 105px label.
    assert r["track_w"] >= 300, f"min_width did not select the track (w={r['track_w']})"
    assert r["label_w"] < 300, f"expected the narrow label without min_width (w={r['label_w']})"

    # Accept fired as trusted input.
    assert r["accept"] and r["accept"].get("done") is True, "slide-to-accept did not fire"
    assert r["accept"].get("isTrusted") is True, "slide was not trusted input!"

    # Safety gate: the money slider was never touched.
    assert r["complete"] is None, "SAFETY VIOLATION: 'Slide to Complete' was activated"
