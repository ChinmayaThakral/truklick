"""find_click_point(): only return a coordinate that is actually safe to click.

HONEST SCOPE — read before trusting this file:
The live Accept failure (2026-07-19, lp.p2p.me) is NOT reproduced here. I first
assumed it was a stale-coordinate race (box read while the dialog was dismissing),
but a direct comparison showed the OLD code also clicks correctly on both a smoothly
animating element and a hard reflow/jump. So that hypothesis is DISPROVEN and the
real cause of the Accept miss is still unknown (see docs/SESSION_LOG.md).

What IS proven here: the occlusion guard. With an overlay covering the target, the
old find() returned a coordinate that clicked the OVERLAY; find_click_point refuses.
That is a genuine correctness improvement — just not (necessarily) the live bug fix.
"""
import asyncio
from pathlib import Path

import pytest

pytest.importorskip("playwright")

from truklick import targeting  # noqa: E402
from truklick.browser import BrowserConfig, BrowserManager  # noqa: E402

# Button animates from far away into its final spot over ~600ms, like a dialog settling.
MOVING = """
<style>
  @keyframes slidein { from { transform: translateY(-300px); } to { transform: none; } }
  #b { position:absolute; top:400px; left:100px; animation: slidein .6s ease-out forwards; }
</style>
<button id="b" onclick="window.__clicked=true">Accept</button>
"""

# An overlay covers the button: the centre point does NOT hit it.
OCCLUDED = """
<button id="b" style="position:absolute;top:100px;left:100px;width:120px;height:40px"
        onclick="window.__clicked=true">Accept</button>
<div style="position:absolute;top:0;left:0;width:100%;height:400px;background:rgba(0,0,0,.5)"></div>
"""

STATIC = """<button id="b" style="position:absolute;top:100px;left:100px"
             onclick="window.__clicked=true">Accept</button>"""


async def _click_and_report(html, target):
    bm = BrowserManager(BrowserConfig(profile_dir=Path("/tmp/tk_stab_profile"), headless=True))
    await bm.start()
    try:
        page = await bm.ensure_page()
        await page.set_content(html)
        hit = await targeting.find_click_point(page, target)
        if hit is None:
            return {"hit": False, "clicked": False}
        cdp = await bm.new_cdp_session(page)
        from truklick.cdp_input import Input
        await Input(cdp).click(hit.cx, hit.cy)
        await asyncio.sleep(0.2)
        clicked = await page.evaluate("window.__clicked === true")
        return {"hit": True, "clicked": bool(clicked)}
    finally:
        await bm.stop()


def _run(html, target={"text": "Accept", "exact": True}):
    try:
        return asyncio.run(_click_and_report(html, target))
    except Exception as exc:
        if "Executable doesn't exist" in str(exc):
            pytest.skip("Chromium not installed")
        raise


def test_click_lands_on_a_moving_element():
    """An animating element must still be clicked correctly (not a bug repro — the
    old code also passed this; kept so the stability wait can't regress)."""
    res = _run(MOVING)
    assert res["hit"], "never resolved a click point for the animating element"
    assert res["clicked"], "click missed on an animating element"


def test_static_element_still_works():
    res = _run(STATIC)
    assert res["hit"] and res["clicked"]


def test_occluded_element_is_refused_not_misclicked():
    """If something covers the target, we must NOT return a coordinate that would
    click the overlay instead."""
    res = _run(OCCLUDED)
    assert res["hit"] is False, "returned a click point that would hit the overlay"


# Slow drift: ~0.8px/frame, near the 0.5px movement threshold. This is the case that
# decides whether ONE animation frame of stability checking is enough (it is — the
# resolver refuses rather than clicking a stale position). Guards the speed change
# that took appear->click from ~74ms to ~24ms.
SLOW_DRIFT = """<style>@keyframes d{from{top:120px}to{top:320px}}
#b{position:fixed;left:100px;top:120px;width:90px;height:34px;animation:d 4s linear forwards}</style>
<button id="b" onclick="window.__clicked=true">Accept</button>"""


async def _resolve_mid_animation(html, delay=0.4):
    """Resolve while the element is genuinely MID-animation.

    Resolving immediately after set_content is not a valid test: a CSS animation has
    not started moving yet, so two samples legitimately match and the element really
    is momentarily stationary. The delay is what makes this reproduce the hazard.
    """
    bm = BrowserManager(BrowserConfig(profile_dir=Path("/tmp/tk_slowdrift"),
                                      headless=True))
    await bm.start()
    try:
        page = await bm.ensure_page()
        await page.set_content(html)
        await asyncio.sleep(delay)
        return await targeting.find_click_point(page, {"text": "Accept", "exact": True})
    finally:
        await bm.stop()


def test_slow_drift_is_refused_not_misclicked():
    """A slowly-moving target must never be clicked at a stale position."""
    try:
        hit = asyncio.run(_resolve_mid_animation(SLOW_DRIFT))
    except Exception as exc:
        if "Executable doesn't exist" in str(exc):
            pytest.skip("Chromium not installed")
        raise
    assert hit is None, (
        "returned a click point for a still-moving element — the click would land "
        "where the element used to be")
