"""
Open the P2P dashboard in a persistent Chromium with CDP exposed, and keep it alive.

Why: you log in and use the site normally, and captures can ATTACH to this same
browser later (scripts/capture_now.py) — no terminal interaction needed at the
moment an order pops. Leave this running.

RUN:
    python scripts/open_dashboard.py
"""

import asyncio

from playwright.async_api import async_playwright

CDP_PORT = 9222
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
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            args=LAUNCH_ARGS,
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
