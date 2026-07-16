"""
============================================================================
 PROOF OF CONCEPT #3 — Trusted CDP click while MINIMIZED on macOS
============================================================================

PoC #1/#2 proved trusted-CDP-while-minimized on Windows. FACT 2 is Windows-only.
This settles whether the SAME holds on macOS — the last Phase-1 gate reachable
without a live order.

Difference from the Windows PoCs: instead of asking a human to minimize the
window, we minimize it programmatically over CDP via
`Browser.setWindowBounds({windowState:"minimized"})` — no Accessibility
permission, fully unattended, and it minimizes the real OS window. We then fire a
raw trusted click and read back `isTrusted`.

RUN:
    python poc/poc_test_mac.py
============================================================================
"""

import asyncio
import time
from pathlib import Path

from playwright.async_api import async_playwright

ANTI_THROTTLE_FLAGS = [
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-ipc-flooding-protection",
    "--disable-features=CalculateNativeWinOcclusion",
]

SELFTEST = Path(__file__).resolve().parent.parent / "examples" / "selftest.html"


async def run():
    async with async_playwright() as p:
        print("[1] Launching headful Chromium with anti-throttle flags...")
        browser = await p.chromium.launch(headless=False, args=ANTI_THROTTLE_FLAGS)
        page = await browser.new_page()
        await page.goto(SELFTEST.as_uri(), wait_until="domcontentloaded")

        # coords BEFORE minimizing (resilient targeting, not fixed pixels)
        box = await page.locator("#target").bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        print(f"[2] Target center @ ({cx:.0f}, {cy:.0f})")

        cdp = await page.context.new_cdp_session(page)

        # minimize the real OS window over CDP
        tinfo = await cdp.send("Target.getTargetInfo")
        target_id = tinfo["targetInfo"]["targetId"]
        win = await cdp.send("Browser.getWindowForTarget", {"targetId": target_id})
        window_id = win["windowId"]
        await cdp.send("Browser.setWindowBounds",
                       {"windowId": window_id, "bounds": {"windowState": "minimized"}})
        await asyncio.sleep(0.5)
        state = (await cdp.send("Browser.getWindowBounds",
                                {"windowId": window_id}))["bounds"]["windowState"]
        print(f"[3] Window state via CDP: {state!r}")
        if state != "minimized":
            print("    ⚠ Window did NOT report minimized — result below is not a valid "
                  "minimized test.")

        print("[4] Firing raw trusted CDP click while minimized...")
        t0 = time.time()
        await cdp.send("Input.dispatchMouseEvent",
                       {"type": "mousePressed", "x": cx, "y": cy,
                        "button": "left", "clickCount": 1})
        await cdp.send("Input.dispatchMouseEvent",
                       {"type": "mouseReleased", "x": cx, "y": cy,
                        "button": "left", "clickCount": 1})
        dispatch_ms = (time.time() - t0) * 1000
        await asyncio.sleep(0.5)
        result = await page.evaluate("window.__result")

        # restore so the run ends cleanly
        await cdp.send("Browser.setWindowBounds",
                       {"windowId": window_id, "bounds": {"windowState": "normal"}})

        print("\n" + "=" * 56)
        print("  RESULT (macOS minimized trusted-click)")
        print("=" * 56)
        print(f"  window state at click : {state}")
        print(f"  dispatch time         : {dispatch_ms:.0f} ms")
        if result and result.get("received"):
            print(f"  click received        : YES")
            print(f"  isTrusted             : {result.get('isTrusted')}")
            if state == "minimized" and result.get("isTrusted") is True:
                print("\n  ✓✓✓  PASS — trusted click landed while MINIMIZED on macOS.")
            else:
                print("\n  ⚠  See flags above — not a clean minimized+trusted pass.")
        else:
            print("  click received        : NO")
            print("\n  ✗  Click did NOT land while minimized on macOS. Worth digging in.")
        print("=" * 56)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
