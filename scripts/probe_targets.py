"""
READ-ONLY target probe. Clicks NOTHING.

Attaches to the running browser and reports, for each recipe target, what every
targeting strategy resolves to right now — including what document.elementFromPoint()
says is actually at the computed coordinate. Use this the instant an order popup /
the home Accept is on screen, BEFORE letting the engine click anything.

Exists because of the 2026-07-19 live run: the Accept click landed on the wrong
element and we could not diagnose it after the fact (the button was gone).

RUN:
    python scripts/probe_targets.py
"""

import asyncio

from playwright.async_api import async_playwright

CDP_URL = "http://localhost:9222"

TARGETS = {
    "Close": {"text": "Close", "exact": True},
    "Accept (role only — what the recipe uses)": {
        "role": "button", "name": "Accept", "exact": True},
    "Accept (loose text — the thing that mis-clicked)": {"text": "Accept"},
    "Accept (exact text)": {"text": "Accept", "exact": True},
}


async def probe(page, label, target):
    from truklick import targeting
    print(f"\n--- {label}  {target}")
    hit = await targeting.find(page, target)
    if hit is None:
        print("    find()            -> not present")
    else:
        got = await page.evaluate(
            """([x, y]) => {
                const el = document.elementFromPoint(x, y);
                if (!el) return null;
                const b = el.closest('button');
                return {tag: el.tagName.toLowerCase(),
                        isButton: !!b,
                        text: ((b || el).innerText || '').trim().slice(0, 40)};
            }""",
            [hit.cx, hit.cy],
        )
        print(f"    find()            -> via {hit.strategy} in {hit.where} "
              f"center=({hit.cx:.0f},{hit.cy:.0f})")
        print(f"    elementAtPoint    -> {got}")
    safe = await targeting.find_click_point(page, target)
    print(f"    find_click_point() -> "
          + (f"SAFE ({safe.strategy}) ({safe.cx:.0f},{safe.cy:.0f})" if safe
             else "refused (not present / not settled / occluded)"))


async def main():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(CDP_URL)
        page = next((pg for c in b.contexts for pg in c.pages
                     if "p2p.me" in (pg.url or "")), None)
        if page is None:
            print("No lp.p2p.me page found. Is open_dashboard.py running?")
            return
        print(f"page: {page.url}")
        n = await page.evaluate("document.querySelectorAll('*').length")
        print(f"DOM nodes: {n}")
        for label, target in TARGETS.items():
            await probe(page, label, target)


if __name__ == "__main__":
    asyncio.run(main())
