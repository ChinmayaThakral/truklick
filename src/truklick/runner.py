"""Recipe runner — execute a recipe's steps against a live page.

Ties together the browser manager (Chromium + CDP), the raw input driver, and
resilient targeting. Use-case-agnostic (ADR-006): it only knows how to run the
generic step vocabulary. A global hotkey toggles start/stop; Ctrl+C shuts down.

Reliability (ARCHITECTURE §6): registers the browser watchdog so a crash triggers
a relaunch + re-navigation + CDP re-bind, and the loop keeps going.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from playwright.async_api import Page

from . import targeting
from .browser import BrowserManager
from .cdp_input import Input
from .log import get_logger
from .motion import MotionProfile
from .recipe import Recipe, Step

log = get_logger("runner")


@dataclass
class RunnerConfig:
    auto_start: bool = True        # begin running immediately (else wait for hotkey)
    human_motion: bool = False     # toggle easing+jitter motion profile
    status_overlay: bool = True    # show RUNNING/PAUSED toast in the page on toggle


# Injected on toggle so the user can see the state without looking at the terminal.
# pointer-events:none is REQUIRED — it keeps the toast out of elementFromPoint(), so
# it can never occlude a target or block a click (see targeting.find_click_point).
_TOAST_JS = """
(state) => {
  let el = document.getElementById('__truklick_toast');
  if (!el) {
    el = document.createElement('div');
    el.id = '__truklick_toast';
    el.style.cssText =
      'position:fixed;top:16px;right:16px;z-index:2147483647;padding:10px 16px;' +
      'border-radius:10px;font:600 14px system-ui,-apple-system,sans-serif;' +
      'color:#fff;pointer-events:none;box-shadow:0 6px 20px rgba(0,0,0,.35);' +
      'transition:opacity .25s;';
    document.documentElement.appendChild(el);
  }
  const running = state === 'running';
  el.textContent = running ? '\\u25CF  Truklick RUNNING' : '\\u23F8  Truklick PAUSED';
  el.style.background = running ? '#2ea043' : '#d29922';
  el.style.opacity = '1';
  clearTimeout(window.__truklickToastTimer);
  if (running) {
    window.__truklickToastTimer = setTimeout(() => { el.style.opacity = '0'; }, 2000);
  }
}
"""


class RecipeRunner:
    def __init__(self, browser: BrowserManager, recipe: Recipe,
                 config: Optional[RunnerConfig] = None) -> None:
        self.browser = browser
        self.recipe = recipe
        self.config = config or RunnerConfig()
        self.page: Optional[Page] = None
        self.input: Optional[Input] = None
        self._clicks_this_pass = 0          # for half-done-pass detection
        self._expect_pass = 0               # verified outcomes
        self._expect_fail = 0
        self._passes = 0
        self._active = asyncio.Event()      # set = executing steps
        self._shutdown = asyncio.Event()    # set = tear down and exit

    # -- setup / lifecycle -------------------------------------------------

    async def _attach(self) -> None:
        """(Re)acquire page, navigate if configured, open CDP, bind input."""
        from urllib.parse import urlparse
        hint = urlparse(self.recipe.url or "").netloc or None
        self.page = await self.browser.ensure_page(url_contains=hint)

        if self.browser.is_attached:
            # Never navigate someone's live session: a goto would reload the page and
            # destroy an open popup (the very thing we're waiting for).
            log.info("Attached mode — using the page as-is, NOT navigating.")
        elif self.recipe.url:
            log.info("Navigating to %s", self.recipe.url)
            await self.page.goto(self.recipe.url, wait_until="domcontentloaded")
        current = self.page.url
        if not self.recipe.matches(current):
            log.warning("Current URL %s does not match recipe match_url %r — "
                        "running anyway.", current, self.recipe.match_url)
        cdp = await self.browser.new_cdp_session(self.page)
        motion = MotionProfile(enabled=self.config.human_motion)
        if self.input is None:
            self.input = Input(cdp, motion=motion)
        else:
            self.input.bind(cdp)
        log.info("Attached to page: %s", current)

    async def _on_restart(self, _bm: BrowserManager) -> None:
        log.warning("Re-attaching after browser restart...")
        await self._attach()

    def toggle(self) -> None:
        """Hotkey callback: flip active/paused."""
        if self._active.is_set():
            self._active.clear()
            log.info("PAUSED (hotkey). Press again to resume.")
            self._flash_status("paused")
        else:
            self._active.set()
            log.info("RUNNING (hotkey).")
            self._flash_status("running")

    def _flash_status(self, state: str) -> None:
        """Show the state in the page itself, so the user doesn't need the terminal.
        Fire-and-forget: never let a UI nicety break or delay the run."""
        if not self.config.status_overlay or self.page is None:
            return
        async def _go():
            try:
                await self.page.evaluate(_TOAST_JS, state)
            except Exception as exc:
                log.debug("status overlay failed (ignored): %s", exc)
        try:
            asyncio.create_task(_go())
        except RuntimeError:
            pass  # no running loop (e.g. during teardown)

    def request_shutdown(self) -> None:
        self._shutdown.set()
        self._active.set()  # unblock any wait

    def _live(self) -> bool:
        """True while we should keep executing (not paused, not shutting down)."""
        return self._active.is_set() and not self._shutdown.is_set()

    # -- main loop ---------------------------------------------------------

    async def run(self) -> None:
        await self._attach()
        if not self.browser.is_attached:
            # In attach mode a "restart" would launch a NEW browser, which is wrong —
            # the user's session is the one that matters.
            self.browser.start_watchdog(self._on_restart)

        if self.config.auto_start:
            self._active.set()
            log.info("Runner started (auto-start). Recipe: %s", self.recipe.name)
            self._flash_status("running")
        else:
            log.info("Runner armed but paused — press '%s' to start.",
                     self.recipe.hotkey)
            self._flash_status("paused")

        try:
            while not self._shutdown.is_set():
                await self._wait_active()
                if self._shutdown.is_set():
                    break
                await self._run_pass()
                if self._shutdown.is_set():
                    break
                if self.recipe.loop:
                    await asyncio.sleep(self.recipe.loop_delay_ms / 1000)
                else:
                    # single-shot: one pass, then exit cleanly.
                    log.info("Recipe pass complete (loop=false). Done.")
                    break
        except asyncio.CancelledError:
            raise
        finally:
            log.info("Runner stopping. %s", self.outcome_summary())

    async def _wait_active(self) -> None:
        """Block until active or shutdown."""
        while not self._active.is_set() and not self._shutdown.is_set():
            await asyncio.sleep(0.05)

    async def _await_condition(self, target: dict, present: bool,
                               timeout_ms: int, poll_ms: int) -> bool:
        """Poll until the target is present (or absent). Responsive to pause/stop."""
        import time
        deadline = time.monotonic() + timeout_ms / 1000
        while True:
            if not self._live():
                return False
            hit = await targeting.find(self.page, target)
            if (hit is not None) == present:
                return True
            if time.monotonic() >= deadline:
                return False
            await asyncio.sleep(max(poll_ms, 25) / 1000)

    def outcome_summary(self) -> str:
        total = self._expect_pass + self._expect_fail
        if total == 0:
            return f"{self._passes} pass(es) run; no expect steps in this recipe."
        rate = 100.0 * self._expect_pass / total
        return (f"{self._passes} pass(es) run — outcomes verified: "
                f"{self._expect_pass}/{total} succeeded ({rate:.0f}%), "
                f"{self._expect_fail} failed.")

    async def _run_pass(self) -> None:
        """Execute the recipe's top-level steps once."""
        self._clicks_this_pass = 0
        self._passes += 1
        ok = await self._exec_steps(self.recipe.steps)
        if not ok and self._clicks_this_pass > 0 and not self._shutdown.is_set():
            # Half-done pass: we already changed the page, then a later step failed.
            # Seen live on lp.p2p.me: Close was clicked, then Accept never appeared —
            # the popup was dismissed and the order left unaccepted. Never let that
            # pass silently.
            log.warning(
                "PASS ABORTED AFTER %d CLICK(S) — the page was already changed but "
                "the recipe did not finish. Check this one manually.",
                self._clicks_this_pass)

    async def _exec_steps(self, steps: list[Step]) -> bool:
        """Run a list of steps. Returns False if interrupted (paused/shutdown)."""
        for step in steps:
            if not self._active.is_set() or self._shutdown.is_set():
                return False
            ok = await self._exec_step(step)
            if ok is False:
                # a wait_for/click that found nothing — abort this pass cleanly
                return False
        return True

    async def _exec_step(self, step: Step) -> Optional[bool]:
        action = step.action
        assert self.page is not None and self.input is not None
        try:
            if action == "wait":
                # chunked so a pause/shutdown mid-wait is responsive
                remaining = step.ms / 1000
                while remaining > 0 and self._live():
                    dt = min(0.1, remaining)
                    await asyncio.sleep(dt)
                    remaining -= dt
                return True

            if action == "expect":
                # "Did it actually work?" — verify an OUTCOME, not just that we
                # clicked. present=false is usually the useful one: the thing you
                # acted on should now be GONE.
                present = bool(step.raw.get("present", True))
                label = step.raw.get("name") or (
                    f"{step.target} {'present' if present else 'gone'}")
                ok = await self._await_condition(
                    step.target, present, step.timeout_ms, step.poll_ms)
                if ok:
                    self._expect_pass += 1
                    log.info("EXPECT OK — %s", label)
                    return True
                self._expect_fail += 1
                log.warning("EXPECT FAILED — %s (waited %dms). The clicks may have "
                            "landed but the outcome did not happen.",
                            label, step.timeout_ms)
                return False

            if action == "wait_for":
                hit = await targeting.wait_for(
                    self.page, step.target, step.timeout_ms,
                    poll_ms=step.poll_ms,
                    should_continue=self._live,
                )
                if hit is None:
                    if not self._live():
                        return False  # paused/shutting down, not a real timeout
                    log.info("wait_for timed out for %s", step.target)
                    return False
                log.info("wait_for satisfied (%s in %s)", hit.strategy, hit.where)
                return True

            if action == "click":
                # Verified click point: box must be stable AND elementFromPoint must
                # actually hit the target, so we never fire at a stale position.
                hit = await targeting.find_click_point(self.page, step.target)
                if hit is None:
                    log.warning("click target not found / never settled: %s",
                                step.target)
                    return False
                log.info("clicking %r via %s in %s", step.target, hit.strategy,
                         hit.where)
                await self.input.click(hit.cx, hit.cy)
                self._clicks_this_pass += 1
                return True

            if action == "type":
                if step.target:
                    hit = await targeting.find(self.page, step.target)
                    if hit:
                        await self.input.click(hit.cx, hit.cy)
                await self.input.type_text(step.text)
                if step.raw.get("enter"):
                    await self.input.press_key("Enter")
                return True

            if action == "swipe":
                return await self._exec_swipe(step)

            if action == "loop":
                count = int(step.raw.get("count", 1))
                for _ in range(count):
                    if not await self._exec_steps(step.steps):
                        return False
                return True

            if action == "condition":
                hit = await targeting.find(self.page, step.target)
                exists_expected = bool(step.raw.get("exists", True))
                if (hit is not None) == exists_expected:
                    return await self._exec_steps(step.steps)
                return True

            log.error("Unknown action at runtime: %s", action)
            return True
        except Exception as exc:
            log.error("Step '%s' failed: %s", action, exc)
            return True  # keep the loop alive; next pass may recover

    async def _exec_swipe(self, step: Step) -> bool:
        """Slide/drag. Either explicit from/to {x,y}, or across a target's box."""
        assert self.page is not None and self.input is not None
        frm, to = step.raw.get("from"), step.raw.get("to")
        steps_n = int(step.raw.get("steps", 20))
        if frm and to:
            await self.input.drag(frm["x"], frm["y"], to["x"], to["y"], steps=steps_n)
            return True
        # target-based: slide from left-center to right-center (slide-to-confirm)
        hit = await targeting.find(self.page, step.target)
        if hit is None:
            log.warning("swipe target not found: %s", step.target)
            return False
        pad = float(step.raw.get("edge_pad", 6))
        x1 = hit.x + pad
        x2 = hit.x + hit.width - pad
        y = hit.cy
        await self.input.drag(x1, y, x2, y, steps=steps_n)
        return True
