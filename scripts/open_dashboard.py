"""
Open the P2P dashboard in a persistent Chromium with CDP exposed, and keep it alive.

Why: you log in and use the site normally, and captures can ATTACH to this same
browser later (scripts/capture_now.py) — no terminal interaction needed at the
moment an order pops. Leave this running.

RUN:
    python scripts/open_dashboard.py
"""

import asyncio
import sys

from playwright.async_api import async_playwright

CDP_PORT = 9222
WINDOW_W, WINDOW_H = 1440, 900   # sensible desktop size; override with --size WxH

LAUNCH_ARGS = [
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-ipc-flooding-protection",
    "--disable-features=CalculateNativeWinOcclusion",
    f"--remote-debugging-port={CDP_PORT}",
]

PROFILE_DIR = "./p2p_profile"   # persistent: log in once (gitignored)
TARGET_URL = "https://lp.p2p.me"


async def main():
    w, h = WINDOW_W, WINDOW_H
    if "--size" in sys.argv:
        try:
            w, h = (int(v) for v in sys.argv[sys.argv.index("--size") + 1].split("x"))
        except Exception:
            print("--size expects WxH, e.g. --size 1920x1080")
            return

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            args=LAUNCH_ARGS + [f"--window-size={w},{h}"],
            # no_viewport: don't emulate a fixed 1280x720 viewport — let the page use
            # the real OS window size. (Targeting is resolution-independent either way;
            # this is purely so the window looks/behaves normally.)
            no_viewport=True,
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(TARGET_URL, wait_until="domcontentloaded")

        print("=" * 58)
        print("  Dashboard open. Log in and use it normally.")
        print(f"  CDP exposed on http://localhost:{CDP_PORT}")
        print("  Capture anytime with:  python scripts/capture_now.py")
        print("  Leave this running. Close the window (or Ctrl+C) to stop.")
        print("=" * 58, flush=True)

        closed = asyncio.Event()
        ctx.on("close", lambda _: closed.set())
        await closed.wait()
        print("[done] Browser closed.")


if __name__ == "__main__":
    asyncio.run(main())
