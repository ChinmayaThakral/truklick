"""Browser manager — launch/attach Chromium with anti-throttle flags + a
persistent profile, expose a raw CDP session, and keep it alive.

Grounded in PROVEN_FACTS FACT 2 (anti-throttle flags keep a minimized window
alive) and ADR-003 (always launch with the five flags + persistent user-data-dir).
The persistent profile keeps logins between runs and MUST NOT be committed
(it is gitignored via *_profile/).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable, Optional

from playwright.async_api import (
    BrowserContext,
    CDPSession,
    Page,
    Playwright,
    async_playwright,
)

from .log import get_logger

log = get_logger("browser")

# The five anti-throttle flags. PROVEN_FACTS FACT 2 / ADR-003. These keep a
# backgrounded/occluded/minimized Chromium window fully alive so raw CDP input
# still lands — the key advantage over pixel clickers that need a live display.
ANTI_THROTTLE_FLAGS: list[str] = [
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-ipc-flooding-protection",
    "--disable-features=CalculateNativeWinOcclusion",
]


@dataclass
class BrowserConfig:
    """How to launch Chromium. OS-agnostic — no hardcoded platform assumptions."""

    profile_dir: Path
    headless: bool = False
    # Optional Chromium channel (e.g. "chrome", "msedge"). Default: Playwright's
    # bundled Chromium. Chromium-family only — CDP requires it (PROVEN_FACTS caveat).
    channel: Optional[str] = None
    extra_args: list[str] = field(default_factory=list)
    # Watchdog poll interval; the supervisor restarts the browser if it dies.
    keepalive_interval_s: float = 3.0
    # If set (e.g. "http://localhost:9222"), ATTACH to an already-running browser
    # over CDP instead of launching one. Used to drive a session the user is already
    # logged into. In this mode we never close their browser on stop().
    cdp_url: Optional[str] = None


class BrowserManager:
    """Owns the Chromium lifecycle and the CDP session.

    Usage:
        async with BrowserManager(config) as bm:
            page = bm.page
            cdp = await bm.new_cdp_session()
            ...

    A keep-alive supervisor (opt-in via start_watchdog) restarts the browser if
    it crashes/closes and invokes an on_restart callback so the caller can
    re-navigate and re-acquire its CDP session (ARCHITECTURE §6).
    """

    def __init__(self, config: BrowserConfig) -> None:
        self.config = config
        self._pw: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._browser = None          # set only when attached over CDP
        self._attached = False
        self._closed = asyncio.Event()
        self._watchdog_task: Optional[asyncio.Task] = None
        self._on_restart: Optional[Callable[["BrowserManager"], Awaitable[None]]] = None
        self._stopping = False

    # -- lifecycle ---------------------------------------------------------

    async def start(self) -> None:
        """Launch a persistent Chromium context, or ATTACH to a running one."""
        if self.config.cdp_url:
            await self._attach_existing()
            return

        self.config.profile_dir.mkdir(parents=True, exist_ok=True)
        args = ANTI_THROTTLE_FLAGS + list(self.config.extra_args)
        log.info("Launching Chromium (headless=%s, profile=%s)",
                 self.config.headless, self.config.profile_dir)
        log.debug("Anti-throttle flags: %s", " ".join(args))

        self._pw = await async_playwright().start()
        launch_kwargs = dict(
            user_data_dir=str(self.config.profile_dir),
            headless=self.config.headless,
            args=args,
        )
        if self.config.channel:
            launch_kwargs["channel"] = self.config.channel
        self._context = await self._pw.chromium.launch_persistent_context(**launch_kwargs)

        self._closed.clear()
        self._context.on("close", lambda _: self._closed.set())
        log.info("Chromium up. %d page(s) open.", len(self._context.pages))

    async def _attach_existing(self) -> None:
        """Connect to a browser the user already has open (they stay logged in).

        We deliberately do NOT create/close pages or contexts here — this is someone's
        live session."""
        url = self.config.cdp_url
        log.info("Attaching to existing browser at %s", url)
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.connect_over_cdp(url)
        if not self._browser.contexts:
            raise RuntimeError(f"Attached to {url} but it has no browser contexts")
        self._context = self._browser.contexts[0]
        self._attached = True
        self._closed.clear()
        log.info("Attached. %d page(s) open. (Your browser will be left open.)",
                 len(self._context.pages))

    @property
    def is_attached(self) -> bool:
        return self._attached

    async def stop(self) -> None:
        """Tear down the browser and Playwright cleanly.

        When attached to a user's existing browser we only DISCONNECT — closing it
        would kill their logged-in session."""
        self._stopping = True
        if self._watchdog_task:
            self._watchdog_task.cancel()
            self._watchdog_task = None
        if self._attached:
            log.info("Detaching — leaving your browser open.")
            self._context = None
            self._browser = None
            if self._pw:
                await self._pw.stop()
                self._pw = None
            return
        if self._context:
            try:
                await self._context.close()
            except Exception as exc:  # pragma: no cover - best-effort teardown
                log.debug("context close error (ignored): %s", exc)
            self._context = None
        if self._pw:
            await self._pw.stop()
            self._pw = None
        log.info("Chromium stopped.")

    async def restart(self) -> None:
        """Relaunch the browser (loses page/CDP references — caller must re-acquire)."""
        log.warning("Restarting Chromium...")
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None
        if self._pw:
            await self._pw.stop()
            self._pw = None
        await self.start()

    # -- accessors ---------------------------------------------------------

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("BrowserManager not started")
        return self._context

    @property
    def page(self) -> Page:
        """The active page (first open page, or a fresh one if none)."""
        ctx = self.context
        if not ctx.pages:
            raise RuntimeError("No open pages")
        return ctx.pages[0]

    async def ensure_page(self, url_contains: Optional[str] = None) -> Page:
        """Return an existing page, creating one if the context has none.

        url_contains: prefer a page whose URL contains this (used when attached, so we
        drive the tab the user is actually on rather than an unrelated one)."""
        ctx = self.context
        if url_contains:
            for pg in ctx.pages:
                if url_contains in (pg.url or ""):
                    return pg
        if ctx.pages:
            return ctx.pages[0]
        return await ctx.new_page()

    async def new_cdp_session(self, page: Optional[Page] = None) -> CDPSession:
        """Open a raw CDP session on a page — the input pipeline (ADR-001/002)."""
        target = page or await self.ensure_page()
        return await self.context.new_cdp_session(target)

    def is_alive(self) -> bool:
        return self._context is not None and not self._closed.is_set()

    # -- supervisor --------------------------------------------------------

    def start_watchdog(
        self, on_restart: Callable[["BrowserManager"], Awaitable[None]]
    ) -> None:
        """Begin keep-alive supervision. on_restart runs after each auto-restart
        so the caller can re-navigate and re-acquire its CDP session."""
        self._on_restart = on_restart
        self._watchdog_task = asyncio.create_task(self._watchdog())

    async def _watchdog(self) -> None:
        while not self._stopping:
            try:
                await asyncio.wait_for(
                    self._closed.wait(), timeout=self.config.keepalive_interval_s
                )
            except asyncio.TimeoutError:
                continue  # still alive
            if self._stopping:
                return
            log.warning("Browser closed unexpectedly — supervisor relaunching.")
            try:
                await self.restart()
                if self._on_restart:
                    await self._on_restart(self)
            except Exception as exc:  # pragma: no cover
                log.error("Watchdog restart failed: %s", exc)
                await asyncio.sleep(self.config.keepalive_interval_s)

    # -- async context manager --------------------------------------------

    async def __aenter__(self) -> "BrowserManager":
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.stop()
