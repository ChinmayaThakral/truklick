"""Targeting — resilient element location, no hardcoded pixels.

PROVEN_FACTS FACT 4: find an element by visible text / role / selector, read its
bounding box, click its center. Survives layout shifts. We search the MAIN FRAME
and ALL IFRAMES (P2P popups can render nested). Multiple fallback strategies per
target, tried in order.

A `target` is a plain dict from the recipe (kept engine-agnostic, ADR-006), e.g.:
    { "selector": "#accept" }
    { "text": "Close" }
    { "role": "button", "name": "Close" }
    { "text": "Close", "fallback_selector": "button.close" }
Any combination is allowed; strategies are tried most-specific first.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from playwright.async_api import Frame, Locator, Page

from .log import get_logger

log = get_logger("targeting")


@dataclass
class Hit:
    """A located element's center + box, in main-frame viewport CSS pixels."""

    cx: float
    cy: float
    x: float
    y: float
    width: float
    height: float
    strategy: str
    where: str  # "main frame" or "iframe(<url>)"


def _locators_for(frame: Frame, target: dict) -> list[tuple[str, Locator]]:
    """Build (strategy_name, locator) pairs for a target, most-specific first."""
    out: list[tuple[str, Locator]] = []
    if target.get("selector"):
        out.append(("selector", frame.locator(target["selector"]).first))
    if target.get("role"):
        kwargs = {}
        if target.get("name"):
            kwargs["name"] = target["name"]
            # Playwright matches accessible name as a case-insensitive SUBSTRING by
            # default, so name="Accept" would also match "Slide to Accept". Honour an
            # explicit exact flag to keep targets unambiguous.
            if target.get("exact"):
                kwargs["exact"] = True
        out.append(("role", frame.get_by_role(target["role"], **kwargs).first))
    if target.get("text"):
        exact = bool(target.get("exact", False))
        out.append(("text", frame.get_by_text(target["text"], exact=exact).first))
    if target.get("fallback_selector"):
        out.append(("fallback_selector",
                    frame.locator(target["fallback_selector"]).first))
    return out


def _frames(page: Page) -> list[Frame]:
    """Main frame first, then all iframes."""
    return [page.main_frame] + [f for f in page.frames if f != page.main_frame]


async def find(page: Page, target: dict, require_visible: bool = True) -> Optional[Hit]:
    """Locate a target across main frame + iframes. Returns a Hit or None.

    Tries each strategy in each frame; returns the first that resolves to a
    visible element with a real bounding box.
    """
    if not any(target.get(k) for k in ("selector", "role", "text", "fallback_selector")):
        raise ValueError(f"Target has no usable strategy: {target!r}")

    for frame in _frames(page):
        where = "main frame" if frame == page.main_frame else f"iframe({frame.url[:48]})"
        for strategy, locator in _locators_for(frame, target):
            try:
                if await locator.count() == 0:
                    continue
                if require_visible and not await locator.is_visible():
                    continue
                box = await locator.bounding_box()
                if not box or box["width"] <= 0 or box["height"] <= 0:
                    continue
                hit = Hit(
                    cx=box["x"] + box["width"] / 2,
                    cy=box["y"] + box["height"] / 2,
                    x=box["x"], y=box["y"],
                    width=box["width"], height=box["height"],
                    strategy=strategy, where=where,
                )
                log.debug("found via %s in %s @ (%.0f, %.0f)",
                          strategy, where, hit.cx, hit.cy)
                return hit
            except Exception as exc:  # locator can throw on detached/odd frames
                log.debug("strategy %s in %s errored: %s", strategy, where, exc)
                continue
    return None


async def _iter_candidates(page: Page, target: dict):
    """Yield (strategy, where, locator) for each strategy in each frame."""
    for frame in _frames(page):
        where = "main frame" if frame == page.main_frame else f"iframe({frame.url[:48]})"
        for strategy, locator in _locators_for(frame, target):
            yield strategy, where, locator


async def find_click_point(page: Page, target: dict, settle_ms: int = 120,
                           attempts: int = 6) -> Optional[Hit]:
    """Resolve a target to a point that is SAFE to click.

    Raw CDP dispatches at coordinates, so a box read during a layout animation can
    be stale by the time the click fires — the click then lands where the element
    WAS. (Seen live: clicking Close then immediately resolving the next target while
    the dialog was still dismissing.) So we:
      1. wait until the bounding box is STABLE across two reads settle_ms apart, and
      2. verify document.elementFromPoint() at the centre actually hits that element
         (catches overlays and mid-transition reflow).
    Returns None if it can't be made safe within `attempts`.
    """
    import asyncio

    for _ in range(attempts):
        found = None
        async for strategy, where, locator in _iter_candidates(page, target):
            try:
                if await locator.count() == 0 or not await locator.is_visible():
                    continue
                box1 = await locator.bounding_box()
                if not box1 or box1["width"] <= 0 or box1["height"] <= 0:
                    continue
                await asyncio.sleep(settle_ms / 1000)
                box2 = await locator.bounding_box()
                if not box2:
                    continue
                if any(abs(box1[k] - box2[k]) > 0.5 for k in ("x", "y", "width", "height")):
                    log.debug("target still moving (%s), retrying", strategy)
                    found = "moving"
                    break  # layout animating — restart the whole resolve
                cx = box2["x"] + box2["width"] / 2
                cy = box2["y"] + box2["height"] / 2
                handle = await locator.element_handle()
                if handle is not None:
                    hits = await page.evaluate(
                        """([el, x, y]) => {
                            const t = document.elementFromPoint(x, y);
                            if (!t) return false;
                            return el === t || el.contains(t) || t.contains(el);
                        }""",
                        [handle, cx, cy],
                    )
                    if not hits:
                        log.debug("point (%.0f,%.0f) does not hit target via %s "
                                  "(overlay/reflow?)", cx, cy, strategy)
                        found = "occluded"
                        break
                log.debug("click point verified via %s in %s @ (%.0f, %.0f)",
                          strategy, where, cx, cy)
                return Hit(cx=cx, cy=cy, x=box2["x"], y=box2["y"],
                           width=box2["width"], height=box2["height"],
                           strategy=strategy, where=where)
            except Exception as exc:
                log.debug("strategy %s errored: %s", strategy, exc)
                continue
        if found is None:
            return None  # target genuinely not present
        await asyncio.sleep(settle_ms / 1000)
    log.warning("target never settled into a safely clickable point: %s", target)
    return None


async def wait_for(page: Page, target: dict, timeout_ms: int = 30000,
                   poll_ms: int = 250,
                   should_continue=None) -> Optional[Hit]:
    """Poll find() until the target appears or timeout. Raw CDP has no auto-wait
    (PROVEN_FACTS caveat), so the runner waits explicitly here.

    should_continue: optional callable -> bool. Checked each poll; when it
    returns False (e.g. the runner was paused or is shutting down) we abort and
    return None immediately, so a hotkey/Ctrl+C is responsive even mid-wait.
    """
    import asyncio
    import time

    deadline = time.monotonic() + timeout_ms / 1000
    attempt = 0
    while True:
        if should_continue is not None and not should_continue():
            return None
        hit = await find(page, target)
        if hit:
            return hit
        if time.monotonic() >= deadline:
            return None
        attempt += 1
        if attempt % 8 == 0:
            log.info("still waiting for target %s ...", target)
        await asyncio.sleep(poll_ms / 1000)
