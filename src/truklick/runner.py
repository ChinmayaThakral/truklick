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


class RecipeRunner:
    def __init__(self, browser: BrowserManager, recipe: Recipe,
                 config: Optional[RunnerConfig] = None) -> None:
        self.browser = browser
        self.recipe = recipe
        self.config = config or RunnerConfig()
        self.page: Optional[Page] = None
        self.input: Optional[Input] = None
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
        else:
            self._active.set()
            log.info("RUNNING (hotkey).")

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
        else:
            log.info("Runner armed but paused — press '%s' to start.",
                     self.recipe.hotkey)

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
            log.info("Runner stopping.")

    async def _wait_active(self) -> None:
        """Block until active or shutdown."""
        while not self._active.is_set() and not self._shutdown.is_set():
            await asyncio.sleep(0.05)

    async def _run_pass(self) -> None:
        """Execute the recipe's top-level steps once."""
        await self._exec_steps(self.recipe.steps)

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

            if action == "wait_for":
                hit = await targeting.wait_for(
                    self.page, step.target, step.timeout_ms,
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
