"""Recorder behaviour, locked in after testing against the real lp.p2p.me site.

That live test found three things this file guards against:
  1. it auto-asserted the last-clicked element disappears — wrong for navigation
     clicks, so the recipe failed on every run;
  2. an icon button with no text fell back to a raw Tailwind CSS path silently;
  3. it emitted blind `wait` sleeps that only slowed the recipe down.
"""
import asyncio
from pathlib import Path

import pytest

pytest.importorskip("playwright")

from truklick import targeting  # noqa: E402
from truklick.browser import BrowserConfig, BrowserManager  # noqa: E402
from truklick.cdp_input import Input  # noqa: E402
from truklick.recorder import Recorder, _target_for  # noqa: E402

PAGE = """<body style="font:16px system-ui;padding:30px">
<button id="dismiss">Dismiss</button>
<button id="nav">Home</button>
<button id="icon" class="inline-flex cursor-pointer" style="padding:8px"><svg width=12 height=12></svg></button>
<script>dismiss.onclick=()=>dismiss.remove();</script></body>"""


async def _record(order):
    bm = BrowserManager(BrowserConfig(profile_dir=Path("/tmp/tk_rec_t"), headless=True))
    await bm.start()
    try:
        page = await bm.ensure_page()
        await page.set_content(PAGE)
        r = Recorder(page)
        await r.start()
        cdp = await bm.new_cdp_session(page)
        inp = Input(cdp)
        for t in order:
            hit = await targeting.find_click_point(page, t)
            assert hit, f"fixture target not found: {t}"
            await inp.click(hit.cx, hit.cy)
            await asyncio.sleep(1.3)          # let the outcome observer report
        return r.build("t", "about:blank", loop=False)
    finally:
        await bm.stop()


def _run(order):
    try:
        return asyncio.run(_record(order))
    except Exception as exc:
        if "Executable doesn't exist" in str(exc):
            pytest.skip("Chromium not installed")
        raise


def test_expect_added_only_when_element_actually_vanished():
    r = _run([{"text": "Home", "exact": True}, {"text": "Dismiss", "exact": True}])
    assert any(s["action"] == "expect" for s in r["steps"]), \
        "element vanished but no outcome check was recorded"


def test_no_expect_for_navigation_click():
    """Regression: auto-asserting 'last element disappears' made recorded recipes
    fail on every run when the last click was navigation."""
    r = _run([{"text": "Dismiss", "exact": True}, {"text": "Home", "exact": True}])
    assert not any(s["action"] == "expect" for s in r["steps"]), \
        "asserted an outcome that was never observed"


def test_fragile_css_fallback_is_flagged_not_silent():
    r = _run([{"selector": "#icon"}])
    assert "_WARNING_fragile_targets" in r, "raw CSS fallback was not surfaced"


def test_no_blind_sleeps():
    r = _run([{"text": "Home", "exact": True}, {"text": "Dismiss", "exact": True}])
    assert not any(s["action"] == "wait" for s in r["steps"]), \
        "blind sleeps make recipes slower and more brittle; wait_for handles it"


def test_generated_ids_are_never_targeted():
    """React/Radix ids change per render — targeting them guarantees breakage."""
    for junk in ("radix-«rj»", ":r7:", "headlessui-menu-1"):
        t = _target_for({"text": "", "role": None, "id": None, "css": "button.x"})
        assert junk not in str(t)
