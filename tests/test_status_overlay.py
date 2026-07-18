"""The RUNNING/PAUSED toast must never interfere with clicking.

An overlay drawn into the page is a real hazard: find_click_point() refuses to click
when elementFromPoint() doesn't hit the target, so a badly-built toast would silently
stop the recipe from clicking Accept. pointer-events:none keeps it out of
elementFromPoint entirely — this test locks that in.
"""
import asyncio
from pathlib import Path

import pytest

pytest.importorskip("playwright")

from truklick import targeting  # noqa: E402
from truklick.browser import BrowserConfig, BrowserManager  # noqa: E402
from truklick.cdp_input import Input  # noqa: E402
from truklick.runner import _TOAST_JS  # noqa: E402

# A button in the top-right, exactly where the toast is drawn — worst case overlap.
PAGE = """
<body style="margin:0">
  <button style="position:fixed;top:18px;right:18px;padding:10px 20px"
          onclick="window.__clicked=true">Accept</button>
</body>
"""


async def _go(state):
    bm = BrowserManager(BrowserConfig(profile_dir=Path("/tmp/tk_overlay"),
                                      headless=True))
    await bm.start()
    try:
        page = await bm.ensure_page()
        await page.set_content(PAGE)
        await page.evaluate(_TOAST_JS, state)          # draw the toast
        assert await page.evaluate(
            "!!document.getElementById('__truklick_toast')"), "toast not drawn"
        hit = await targeting.find_click_point(
            page, {"role": "button", "name": "Accept", "exact": True})
        if hit is None:
            return {"resolved": False, "clicked": False}
        cdp = await bm.new_cdp_session(page)
        await Input(cdp).click(hit.cx, hit.cy)
        await asyncio.sleep(0.2)
        return {"resolved": True,
                "clicked": bool(await page.evaluate("window.__clicked === true"))}
    finally:
        await bm.stop()


def _run(state):
    try:
        return asyncio.run(_go(state))
    except Exception as exc:
        if "Executable doesn't exist" in str(exc):
            pytest.skip("Chromium not installed")
        raise


@pytest.mark.parametrize("state", ["running", "paused"])
def test_toast_does_not_block_clicks(state):
    res = _run(state)
    assert res["resolved"], "toast made the target unresolvable (occlusion guard hit)"
    assert res["clicked"], "toast swallowed the click"
