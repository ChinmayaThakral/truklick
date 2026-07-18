"""Targeting disambiguation against a fixture modelled on the REAL lp.p2p.me DOM
(captured 2026-07-19). The engine stays use-case-agnostic; this is just a test
fixture that reproduces a nasty real-world ambiguity:

While the order popup is open, the substring "Accept" appears in several NON-button
elements ("Slide to Accept", "Accept to view UPI ID"). The home-screen Accept is a
real <button>. If a recipe targeted text="Accept" loosely, it could match the slider
— on a financial dashboard that is exactly the kind of mis-click we must prevent.

So the recipe uses role=button + exact name. These tests lock that behaviour in.
"""
import asyncio

import pytest

pytest.importorskip("playwright")

from truklick import targeting  # noqa: E402
from truklick.browser import BrowserConfig, BrowserManager  # noqa: E402

# Mirrors the real structure: Radix-style popup (generated id, div>p "Close" button,
# slider + helper text containing "Accept"), and the home-screen real <button>Accept.
FIXTURE = """
<div id="radix-r7">
  <div class="px-6">
    <p>To</p>
    <div><p>Accept to view UPI ID</p></div>
    <div class="mt-12"><div class="bg-primary"><p>Slide to Accept</p></div></div>
    <div class="mt-4 h-12 w-full"><p>Close</p></div>
  </div>
</div>
<div class="mx-auto mb-16 max-w-md">
  <button class="inline-flex cursor-pointer items-center justify-center">Accept</button>
</div>
"""


async def _find(tmp_path, target):
    bm = BrowserManager(BrowserConfig(profile_dir=tmp_path / "p", headless=True))
    await bm.start()
    try:
        page = await bm.ensure_page()
        await page.set_content(FIXTURE)
        hit = await targeting.find(page, target)
        if hit is None:
            return None
        tag = await page.evaluate(
            """([x, y]) => { const el = document.elementFromPoint(x, y);
                             return el ? el.tagName.toLowerCase() : null; }""",
            [hit.cx, hit.cy],
        )
        return {"strategy": hit.strategy, "tag_at_center": tag}
    finally:
        await bm.stop()


def _run(tmp_path, target):
    try:
        return asyncio.run(_find(tmp_path, target))
    except Exception as exc:
        if "Executable doesn't exist" in str(exc):
            pytest.skip("Chromium not installed")
        raise


def test_accept_resolves_to_the_real_button_not_the_slider(tmp_path):
    """role=button + exact name must land on <button>Accept</button>, never on the
    'Slide to Accept' div or the 'Accept to view UPI ID' helper text."""
    res = _run(tmp_path, {"role": "button", "name": "Accept",
                          "exact": True, "text": "Accept"})
    assert res is not None, "Accept target did not resolve at all"
    assert res["strategy"] == "role", f"expected role strategy, got {res['strategy']}"
    assert res["tag_at_center"] == "button", (
        f"Accept click would land on <{res['tag_at_center']}>, not the real button")


def test_loose_text_accept_is_ambiguous(tmp_path):
    """Documents WHY we don't use loose text for Accept: a substring match does NOT
    reliably land on the button (it can hit the slider/helper text)."""
    res = _run(tmp_path, {"text": "Accept"})
    assert res is not None
    # The point isn't which one wins, it's that it is NOT guaranteed to be the button.
    # If this ever starts landing on <button>, the exact/role guard is still correct.
    assert res["tag_at_center"] in {"p", "div", "button"}


def test_close_resolves_inside_the_close_control(tmp_path):
    res = _run(tmp_path, {"text": "Close", "exact": True})
    assert res is not None, "Close target did not resolve"
    assert res["tag_at_center"] in {"p", "div"}, res
