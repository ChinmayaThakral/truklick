"""
============================================================================
 PROOF OF CONCEPT #2 — Trusted CDP Click on the REAL lp.p2p.me site
============================================================================

PURPOSE
  PoC #1 proved trusted-CDP-while-minimized works on a clean LOCAL page.
  This proves the SAME thing on the REAL site, in YOUR logged-in session,
  against the REAL DOM (which may have iframes / dynamic rendering / overlays).

  It targets an element BY ITS VISIBLE TEXT so you don't need coordinates.
  Use a SAFE, non-committing element to validate:
     - the "Close" button on an order popup (dismisses, commits nothing), OR
     - any always-present dashboard element (e.g. a bank name, "My Orders",
       "Home") if no order is showing yet.

  This does NOT loop and does NOT click accept/confirm. It fires ONE trusted
  click at the element you name, while minimized, and reports the result.
  That single result validates the architecture for the real site.

HOW IT WORKS
  1. Launches anti-throttle Chromium with a PERSISTENT profile (so your login
     is remembered between runs — log in once, reuse forever).
  2. Opens lp.p2p.me and waits for you to log in and press Enter.
  3. You type the visible text of the element to test-click (e.g. "Close").
  4. It finds that element in the DOM, reports its box, you minimize, it fires
     a trusted CDP click while minimized, and reports whether it landed.

REQUIREMENTS (already installed from PoC #1):
    python -m pip install playwright
    python -m playwright install chromium

RUN:
    python poc_test_p2p.py
============================================================================
"""

import asyncio
import time
from playwright.async_api import async_playwright

LAUNCH_ARGS = [
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-ipc-flooding-protection",
    "--disable-features=CalculateNativeWinOcclusion",
]

# Persistent profile dir — keeps you logged in between runs.
PROFILE_DIR = "./p2p_profile"
TARGET_URL = "https://lp.p2p.me"


async def find_element_box(page, text):
    """
    Find the FIRST visible element whose trimmed text equals or contains the
    given text (case-insensitive), searching the main frame and all iframes.
    Returns (box, frame_description) or (None, None).
    Uses getBoundingClientRect via the DOM — the resilient-targeting approach.
    """
    # Try main frame first, then any iframes (P2P popups sometimes render nested)
    frames = [page.main_frame] + [f for f in page.frames if f != page.main_frame]
    for frame in frames:
        try:
            # Build a locator that matches visible text
            locator = frame.get_by_text(text, exact=False).first
            count = await locator.count()
            if count > 0:
                box = await locator.bounding_box()
                if box:
                    where = "main frame" if frame == page.main_frame else f"iframe ({frame.url[:40]})"
                    return box, where
        except Exception:
            continue
    return None, None


async def run_poc():
    async with async_playwright() as p:
        print("\n[1] Launching Chromium with a persistent profile...")
        print("    (Your login will be saved in ./p2p_profile for next runs)")
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            args=LAUNCH_ARGS,
        )
        page = context.pages[0] if context.pages else await context.new_page()

        print(f"[2] Opening {TARGET_URL} ...")
        await page.goto(TARGET_URL, wait_until="domcontentloaded")

        print("\n" + "=" * 64)
        print("  LOG IN NOW if you aren't already.")
        print("  If you want to test the real Close button, get an order")
        print("  popup showing. Otherwise you can test any visible element.")
        print("=" * 64)
        input("  Press ENTER here when you're ready...")

        while True:
            print("\n" + "-" * 64)
            target_text = input(
                "  Type the VISIBLE TEXT of the element to test-click\n"
                "  (e.g. 'Close', 'My Orders', a bank name) — or 'q' to quit: "
            ).strip()
            if target_text.lower() == "q":
                break
            if not target_text:
                continue

            box, where = await find_element_box(page, target_text)
            if not box:
                print(f"  ✗ Could not find a visible element with text '{target_text}'.")
                print("    Try the exact text as shown on the page.")
                continue

            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2
            print(f"  ✓ Found '{target_text}' in {where}")
            print(f"    Box center (page coords): ({cx:.0f}, {cy:.0f})")

            client = await context.new_cdp_session(page)

            print("\n  MINIMIZE the Chromium window now. Firing in 6 seconds...")
            for i in range(6, 0, -1):
                print(f"    {i}...", end="\r")
                await asyncio.sleep(1)
            print("  Firing raw trusted CDP click while minimized...       ")

            # Record isTrusted on the very next click, anywhere, so we can prove
            # trust even on elements we don't control.
            await page.evaluate("""
                window.__pocTrusted = null;
                document.addEventListener('click', function handler(e){
                    window.__pocTrusted = e.isTrusted;
                    document.removeEventListener('click', handler, true);
                }, true);
            """)

            t0 = time.time()
            await client.send("Input.dispatchMouseEvent", {
                "type": "mousePressed", "x": cx, "y": cy,
                "button": "left", "clickCount": 1,
            })
            await client.send("Input.dispatchMouseEvent", {
                "type": "mouseReleased", "x": cx, "y": cy,
                "button": "left", "clickCount": 1,
            })
            dispatch_ms = (time.time() - t0) * 1000
            await asyncio.sleep(1)

            trusted = await page.evaluate("window.__pocTrusted")

            await page.bring_to_front()
            print("\n  " + "=" * 60)
            print("  RESULT")
            print("  " + "=" * 60)
            print(f"    CDP dispatch time:  {dispatch_ms:.0f} ms")
            if trusted is True:
                print(f"    Click registered:   YES")
                print(f"    isTrusted:          True")
                print("\n    ✓✓✓  TRUSTED CLICK LANDED on the real site while minimized.")
                print("         Architecture confirmed on lp.p2p.me.")
            elif trusted is False:
                print(f"    Click registered:   YES, but isTrusted=False (investigate)")
            else:
                print(f"    Click registered:   NOT detected on the element.")
                print("         Possible: element in nested iframe / overlay intercepts /")
                print("         coordinates shifted after minimize. We'll diagnose.")
            print("  " + "=" * 60)
            print("  Did the page react as expected? (e.g. popup closed)")

        print("\n[done] Closing.")
        await context.close()


if __name__ == "__main__":
    asyncio.run(run_poc())
