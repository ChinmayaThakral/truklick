"""End-to-end engine proof: targeting + raw CDP trusted click, through the real
engine modules (not the PoC). Mirrors PoC #1's isTrusted check.

Runs headless so it works in CI / on a dev box. NOTE: 'works while minimized'
(PROVEN_FACTS FACT 2) is a headful/real-hardware property already proven on
Windows in the PoCs; headless has no window to minimize. This test proves the
engine's trusted-click + resilient-targeting path end to end.

Skipped automatically if Playwright's Chromium isn't installed.
"""
import asyncio
from pathlib import Path

import pytest

pytest.importorskip("playwright")

from truklick import targeting  # noqa: E402
from truklick.browser import BrowserConfig, BrowserManager  # noqa: E402
from truklick.cdp_input import Input  # noqa: E402

SELFTEST = (Path(__file__).resolve().parent.parent / "examples" / "selftest.html")


async def _run(tmp_path) -> dict:
    bm = BrowserManager(BrowserConfig(profile_dir=tmp_path / "profile", headless=True))
    await bm.start()
    try:
        page = await bm.ensure_page()
        await page.goto(SELFTEST.as_uri(), wait_until="domcontentloaded")

        hit = await targeting.find(page, {"text": "Self-Test Target"})
        assert hit is not None, "targeting failed to locate the button"

        cdp = await bm.new_cdp_session(page)
        inp = Input(cdp)
        await inp.click(hit.cx, hit.cy)

        await asyncio.sleep(0.3)
        return await page.evaluate("window.__result")
    finally:
        await bm.stop()


def test_engine_fires_trusted_click(tmp_path):
    try:
        result = asyncio.run(_run(tmp_path))
    except Exception as exc:
        if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc):
            pytest.skip("Chromium not installed (run: playwright install chromium)")
        raise
    assert result and result.get("received") is True
    assert result.get("isTrusted") is True, "click was not trusted!"
