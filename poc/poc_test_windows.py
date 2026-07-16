"""
============================================================================
 PROOF OF CONCEPT — Trusted CDP Clicking on a Backgrounded Window
============================================================================

PURPOSE
  This is the single load-bearing test for the whole project. It answers ONE
  question with a yes/no on YOUR real machine:

    "Can we fire a TRUSTED (isTrusted=true) click at a DOM element while the
     browser window is minimized / occluded / not focused?"

  Everything about the tool's architecture depends on this answer. We do NOT
  write the project foundation until we know it.

WHAT IT DOES
  1. Launches Chromium with anti-throttling flags.
  2. Opens a local test page with a button that RECORDS whether the click it
     received was trusted (isTrusted) and logs the time.
  3. Waits for you to MINIMIZE the window (it counts down).
  4. Fires a raw CDP Input.dispatchMouseEvent at the button's real coordinates
     WHILE minimized.
  5. Restores the window and shows you the result: was the click received?
     Was it trusted? How long did it take (to detect throttling)?

  We test against a LOCAL page first (not P2P.me) so the result is clean and
  reproducible with no login/site-variance. Once this passes, the SECOND test
  points at the real target.

REQUIREMENTS (Windows)
  1. Install Python 3.10+ from python.org (check "Add to PATH" during install)
  2. Open PowerShell or CMD and run:
        pip install playwright
        playwright install chromium
  3. Then run this file:
        python poc_test_windows.py

  (Playwright bundles its own Chromium, so nothing else to install.)
============================================================================
"""

import asyncio
import time
from playwright.async_api import async_playwright

# A self-contained test page. The button records isTrusted + timestamp into
# window.__result when clicked. No network, no login, fully reproducible.
TEST_PAGE = """
<!DOCTYPE html>
<html>
<head><title>CDP Trusted Click PoC</title></head>
<body style="font-family: sans-serif; padding: 40px; background:#111; color:#eee;">
  <h1>CDP Background-Click Proof of Concept</h1>
  <p>The script will click the button below while this window is minimized.</p>
  <button id="target"
          style="font-size: 28px; padding: 30px 60px; margin-top: 30px;
                 background:#5b5bd6; color:white; border:none; border-radius:12px;
                 cursor:pointer;">
    TARGET BUTTON
  </button>
  <pre id="log" style="margin-top:30px; font-size:16px; color:#7fd67f;"></pre>
  <script>
    window.__result = null;
    const btn = document.getElementById('target');
    const log = document.getElementById('log');
    btn.addEventListener('click', (e) => {
      window.__result = {
        received: true,
        isTrusted: e.isTrusted,
        at: Date.now()
      };
      log.textContent = 'CLICK RECEIVED!\\n'
        + 'isTrusted = ' + e.isTrusted + '\\n'
        + 'time = ' + new Date().toLocaleTimeString();
      btn.style.background = e.isTrusted ? '#2ea043' : '#d29922';
      btn.textContent = e.isTrusted ? 'TRUSTED CLICK ✓' : 'UNTRUSTED CLICK ✗';
    });
  </script>
</body>
</html>
"""

# Anti-throttling flags — these keep a backgrounded/occluded window fully alive.
# Verified from Chrome-launcher docs + Puppeteer background-tab issues.
LAUNCH_ARGS = [
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-ipc-flooding-protection",
    "--disable-features=CalculateNativeWinOcclusion",
]


async def run_poc():
    async with async_playwright() as p:
        print("\n[1] Launching Chromium (headful, anti-throttle flags)...")
        browser = await p.chromium.launch(
            headless=False,
            args=LAUNCH_ARGS,
        )
        page = await browser.new_page()

        # Load the self-contained test page.
        await page.set_content(TEST_PAGE)
        await page.bring_to_front()

        # Find the button's real coordinates via the DOM (this is what the real
        # tool does — resilient targeting, not hardcoded pixels).
        box = await page.locator("#target").bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        print(f"[2] Target button center at page coords: ({cx:.0f}, {cy:.0f})")

        # Open a raw CDP session so we can send Input.dispatchMouseEvent directly.
        # This is the KEY: raw CDP, not page.click(). It skips scroll-into-view
        # (which breaks in background) and fires trusted input through Chrome's
        # real input pipeline.
        client = await page.context.new_cdp_session(page)

        print("\n" + "=" * 60)
        print("  ACTION NEEDED: MINIMIZE the Chromium window NOW.")
        print("  You have 8 seconds. Minimize it and DON'T touch it.")
        print("=" * 60)
        for i in range(8, 0, -1):
            print(f"  Firing click in {i}...", end="\r")
            await asyncio.sleep(1)
        print("\n[3] Firing RAW CDP trusted click while (hopefully) minimized...")

        t0 = time.time()
        # A trusted click = mousePressed + mouseReleased at the same point.
        await client.send("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": cx, "y": cy,
            "button": "left", "clickCount": 1,
        })
        await client.send("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": cx, "y": cy,
            "button": "left", "clickCount": 1,
        })
        dispatch_ms = (time.time() - t0) * 1000
        print(f"[4] CDP dispatch returned in {dispatch_ms:.0f} ms")

        # Give the page a moment, then read the result the button recorded.
        await asyncio.sleep(1)
        result = await page.evaluate("window.__result")

        print("\n[5] Restoring window to show you the result...")
        await page.bring_to_front()
        await asyncio.sleep(1)

        print("\n" + "=" * 60)
        print("  RESULT")
        print("=" * 60)
        if result and result.get("received"):
            print(f"  Click received:  YES")
            print(f"  isTrusted:       {result.get('isTrusted')}")
            if result.get("isTrusted"):
                print("\n  ✓✓✓  SUCCESS — trusted click landed while minimized.")
                print("       This validates the CDP-primary architecture.")
            else:
                print("\n  ⚠  Click landed but was UNTRUSTED. Investigate.")
        else:
            print("  Click received:  NO")
            print("\n  ✗  The click did NOT land while minimized.")
            print("     This means CDP-while-minimized is unreliable on this")
            print("     setup, and the tool needs the virtual-display fallback")
            print("     as its primary reliability layer (your VPS approach).")
        print("=" * 60)

        print("\n[6] Leaving the window open 15s so you can see it. ")
        await asyncio.sleep(15)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(run_poc())
