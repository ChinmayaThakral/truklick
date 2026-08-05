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
                min_w = target.get("min_width")
                if min_w and box["width"] < float(min_w):
                    continue  # narrow inner label, not the wide track we want
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


# ---------------------------------------------------------------------------
# FAST PATH
# ---------------------------------------------------------------------------
# The general path below costs several CDP round-trips per strategy per frame
# (count -> is_visible -> bounding_box), plus a wall-clock settle between two box
# reads. That is fine for correctness but it is pure device-side latency.
#
# This resolver does the whole job in ONE round-trip, inside the page: find the
# element, confirm it is not still animating (two animation frames), confirm
# elementFromPoint actually hits it, and return the click point. Typical cost is
# one evaluate (~2-5ms) instead of ~10 round-trips + a 120ms settle.
#
# It deliberately supports only the unambiguous target shapes (exact text,
# role=button/link + exact name, css selector). Anything else falls back to the
# general path, so we never trade correctness for speed.
_FAST_JS = r"""
async ([spec]) => {
  const raf = () => new Promise(r => requestAnimationFrame(() => r()));
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();

  function visible(el) {
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return false;
    const s = getComputedStyle(el);
    return s.display !== 'none' && s.visibility !== 'hidden' && parseFloat(s.opacity) !== 0;
  }
  function pick() {
    if (spec.selector) {
      const el = document.querySelector(spec.selector);
      return el && visible(el) ? el : null;
    }
    if (spec.role) {
      const minW = spec.minWidth || 0;
      const sel = spec.role === 'button' ? 'button,[role="button"]'
                : spec.role === 'link'   ? 'a,[role="link"]'
                : '[role="' + spec.role + '"]';
      for (const el of document.querySelectorAll(sel)) {
        if (!visible(el)) continue;
        if (minW && el.getBoundingClientRect().width < minW) continue;
        const name = norm(el.getAttribute('aria-label') || el.innerText || el.textContent);
        if (spec.name == null) return el;
        if (spec.exact ? name === spec.name : name.includes(spec.name)) return el;
      }
      return null;
    }
    if (spec.text != null) {
      // deepest element whose own text matches, so we land on the label not a
      // wrapper. minWidth flips that for slide/drag tracks: the matching text
      // also appears on a narrow inner label (e.g. a 105px <p> inside a 400px
      // slide track); minWidth keeps only elements at least that wide, so we
      // land on the track we must drag, not its label leaf.
      const minW = spec.minWidth || 0;
      let best = null;
      for (const el of document.querySelectorAll('*')) {
        if (!visible(el)) continue;
        const t = norm(el.innerText || el.textContent);
        const hit = spec.exact ? t === spec.text : t.includes(spec.text);
        if (!hit) continue;
        if (minW && el.getBoundingClientRect().width < minW) continue;
        if (!best || best.contains(el)) best = el;
      }
      return best;
    }
    return null;
  }

  let el = pick();
  if (!el) return null;

  if (spec.detectOnly) {              // polling for presence: no stability/hit checks
    const r = el.getBoundingClientRect();
    return {x: r.x, y: r.y, width: r.width, height: r.height,
            cx: r.x + r.width / 2, cy: r.y + r.height / 2, detect: true};
  }

  // Is anything actually animating this element (or an ancestor that carries it)?
  // Asking the browser beats sampling: a frame wait is only needed when something
  // is genuinely in motion. Conservative on error — if we cannot tell, we wait.
  let inMotion = true;
  try {
    inMotion = document.getAnimations().some(a =>
      a.playState === 'running' && a.effect && a.effect.target &&
      (a.effect.target === el || a.effect.target.contains(el)));
  } catch (e) { inMotion = true; }

  let b = el.getBoundingClientRect();
  if (inMotion) {
    // Something IS animating this element. Sample across real elapsed time, not
    // requestAnimationFrame: rAF resolves near-instantly in headless Chromium, so
    // both samples land at the same moment and movement goes undetected. A real
    // delay is only paid when the browser says something is actually moving.
    const a0 = b;
    await new Promise(r => setTimeout(r, 20));
    el = pick();
    if (!el) return null;
    b = el.getBoundingClientRect();
    const moved = Math.abs(a0.x - b.x) > 0.5 || Math.abs(a0.y - b.y) > 0.5 ||
                  Math.abs(a0.width - b.width) > 0.5 || Math.abs(a0.height - b.height) > 0.5;
    if (moved) return {moving: true};
  }

  const cx = b.x + b.width / 2, cy = b.y + b.height / 2;
  const at = document.elementFromPoint(cx, cy);
  if (!at || !(at === el || el.contains(at) || at.contains(el))) return {occluded: true};

  return {x: b.x, y: b.y, width: b.width, height: b.height, cx, cy};
}
"""


def _fast_spec(target: dict) -> Optional[dict]:
    """Return a JS spec if this target shape is safe to resolve on the fast path."""
    if target.get("fallback_selector"):
        return None  # multi-strategy fallbacks stay on the general path
    if target.get("selector"):
        return {"selector": target["selector"]}
    mw = target.get("min_width")
    if target.get("role"):
        return {"role": target["role"], "name": target.get("name"),
                "exact": bool(target.get("exact")), "minWidth": mw}
    if target.get("text") is not None:
        return {"text": target["text"], "exact": bool(target.get("exact")),
                "minWidth": mw}
    return None


async def fast_click_point(page: Page, target: dict) -> Optional[Hit]:
    """One-round-trip resolve + stability + occlusion check. None if unsupported,
    absent, still moving, or occluded — caller falls back to the general path."""
    spec = _fast_spec(target)
    if spec is None:
        return None
    try:
        res = await page.evaluate(_FAST_JS, [spec])
    except Exception as exc:
        log.debug("fast path failed (%s), falling back", exc)
        return None
    if not res or res.get("moving") or res.get("occluded"):
        return None
    return Hit(cx=res["cx"], cy=res["cy"], x=res["x"], y=res["y"],
               width=res["width"], height=res["height"],
               strategy="fast", where="main frame")


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

    # Fast path first: one round-trip, in-page stability + occlusion check.
    fast = await fast_click_point(page, target)
    if fast is not None:
        return fast

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
    spec = _fast_spec(target)
    while True:
        if should_continue is not None and not should_continue():
            return None
        # one round-trip probe when the target shape allows it
        if spec is not None:
            try:
                res = await page.evaluate(_FAST_JS, [{**spec, "detectOnly": True}])
            except Exception:
                res = None
                spec = None  # fall back permanently for this wait
            if res:
                if res.get("moving") or res.get("occluded"):
                    await asyncio.sleep(poll_ms / 1000)
                    continue
                return Hit(cx=res["cx"], cy=res["cy"], x=res["x"], y=res["y"],
                           width=res["width"], height=res["height"],
                           strategy="fast", where="main frame")
            if spec is not None:
                # not found on the fast path; only pay for the slow search
                # occasionally, in case the target is inside an iframe
                if attempt % 10 != 0:
                    if time.monotonic() >= deadline:
                        return None
                    attempt += 1
                    await asyncio.sleep(poll_ms / 1000)
                    continue
        hit = await find(page, target)
        if hit:
            return hit
        if time.monotonic() >= deadline:
            return None
        attempt += 1
        if attempt % 8 == 0:
            log.info("still waiting for target %s ...", target)
        await asyncio.sleep(poll_ms / 1000)
