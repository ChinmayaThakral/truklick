"""CLI entry point.

    truklick run <recipe.json> [options]

Wires together the browser manager, runner, and hotkey toggle. Cross-platform;
no OS assumptions baked in (Windows + Linux first, per SCOPE).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from .browser import BrowserConfig, BrowserManager
from .hotkey import HotkeyToggle
from .log import get_logger, setup_logging
from .recipe import RecipeError, load_recipe
from .runner import RecipeRunner, RunnerConfig

log = get_logger("cli")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="truklick",
        description="Trusted, background-capable web automation via CDP. "
                    "Load a recipe; fire real clicks even while minimized.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run a recipe file")
    run.add_argument("recipe", type=Path, help="Path to a recipe .json file")
    run.add_argument("--profile-dir", type=Path, default=Path("./truklick_profile"),
                     help="Persistent Chromium profile dir (keeps logins). "
                          "Gitignored. Default: ./truklick_profile")
    run.add_argument("--attach", metavar="CDP_URL", default=None,
                     help="Attach to an ALREADY-RUNNING browser over CDP "
                          "(e.g. http://localhost:9222) instead of launching one. "
                          "Drives the session you're already logged into; never "
                          "navigates, and leaves your browser open on exit.")
    run.add_argument("--headless", action="store_true",
                     help="Run Chromium headless (default: headful/minimizable)")
    run.add_argument("--channel", default=None,
                     help="Chromium channel, e.g. 'chrome' (default: bundled Chromium)")
    run.add_argument("--url", default=None,
                     help="Override the recipe's start URL")
    run.add_argument("--once", action="store_true",
                     help="Run a single pass even if the recipe says loop=true")
    run.add_argument("--wait", action="store_true",
                     help="Start paused; press the hotkey to begin")
    run.add_argument("--no-hotkey", action="store_true",
                     help="Disable the global hotkey (use Ctrl+C to stop)")
    run.add_argument("--no-overlay", action="store_true",
                     help="Don't show the RUNNING/PAUSED status toast in the page")
    run.add_argument("--human-motion", action="store_true",
                     help="Enable human-like motion (easing+jitter). Refinement.")
    run.add_argument("-v", "--verbose", action="store_true", help="Debug logging")

    rec = sub.add_parser("record", help="Demonstrate a task once; get a recipe")
    rec.add_argument("output", type=Path, help="Where to write the recipe .json")
    rec.add_argument("--url", required=True, help="Page to start recording on")
    rec.add_argument("--name", default=None, help="Recipe name")
    rec.add_argument("--profile-dir", type=Path, default=Path("./truklick_profile"))
    rec.add_argument("--attach", metavar="CDP_URL", default=None,
                     help="Record in a browser you already have open")
    rec.add_argument("--no-loop", action="store_true",
                     help="Recipe runs once instead of looping")
    rec.add_argument("-v", "--verbose", action="store_true")

    up = sub.add_parser("update", help="Check whether a newer release exists")
    up.add_argument("-v", "--verbose", action="store_true")

    g = sub.add_parser("gui", help="Open the control panel (no terminal needed)")
    g.add_argument("--port", type=int, default=8765)
    g.add_argument("--no-open", action="store_true", help="Don't open a browser")
    return p


async def _run(args: argparse.Namespace) -> int:
    recipe_path = args.recipe
    if not Path(recipe_path).exists():
        from .gui import _base_dir
        bundled = _base_dir() / recipe_path
        if bundled.exists():
            recipe_path = bundled
    try:
        recipe = load_recipe(recipe_path)
    except RecipeError as exc:
        log.error("%s", exc)
        return 2

    if args.url:
        recipe.url = args.url
    if args.once:
        recipe.loop = False

    log.info("Loaded recipe '%s' (%d steps, loop=%s, hotkey=%s)",
             recipe.name, len(recipe.steps), recipe.loop, recipe.hotkey)

    bm = BrowserManager(BrowserConfig(
        profile_dir=args.profile_dir,
        headless=args.headless,
        channel=args.channel,
        cdp_url=args.attach,
    ))
    await bm.start()

    runner = RecipeRunner(bm, recipe, RunnerConfig(
        auto_start=not args.wait,
        human_motion=args.human_motion,
        status_overlay=not args.no_overlay,
    ))

    loop = asyncio.get_running_loop()

    # Ctrl+C / SIGTERM -> graceful shutdown
    def _sig() -> None:
        log.info("Shutdown signal received.")
        runner.request_shutdown()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _sig)
        except (NotImplementedError, RuntimeError):
            pass  # e.g. Windows may not support SIGTERM handler

    hotkey = None
    if not args.no_hotkey:
        hotkey = HotkeyToggle(recipe.hotkey, loop, runner.toggle)
        hotkey.start()

    try:
        await runner.run()
    finally:
        if hotkey:
            hotkey.stop()
        await bm.stop()
    return 0


async def _record(args: argparse.Namespace) -> int:
    from .recorder import Recorder

    bm = BrowserManager(BrowserConfig(profile_dir=args.profile_dir,
                                      cdp_url=args.attach))
    await bm.start()
    try:
        page = await bm.ensure_page()
        if not bm.is_attached:
            await page.goto(args.url, wait_until="domcontentloaded")
        rec = Recorder(page)
        await rec.start()
        print("\n" + "=" * 60)
        print("  RECORDING — do the task in the browser window.")
        print("  Every click is captured. Press Ctrl+C here when you're done.")
        print("=" * 60 + "\n", flush=True)
        # Install real signal handlers: relying on KeyboardInterrupt propagating out
        # of asyncio.run risks losing the whole recording before it is written.
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except (NotImplementedError, RuntimeError):
                pass
        try:
            await stop.wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        return _finish_record(rec, args, page.url)
    finally:
        await bm.stop()


def _finish_record(rec, args: argparse.Namespace, page_url: str) -> int:
    if not rec.hits:
        log.warning("Nothing recorded — no clicks were captured.")
        return 1
    name = args.name or f"Recorded on {page_url.split('//')[-1].split('/')[0]}"
    out = rec.save(args.output, name, args.url, loop=not args.no_loop)
    log.info("Saved %d action(s) -> %s", len(rec.hits), out)
    print(f"\n  Recipe written to {out}")
    print("  Run it:   truklick run " + str(out))
    print("  Tune it:  truklick   (control panel -> Edit)\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    from .bootstrap import configure_frozen_env
    configure_frozen_env()   # must run before Playwright resolves browsers
    argv = list(sys.argv[1:] if argv is None else argv)
    # Double-clicked binary (no args) -> open the control panel, not a usage error.
    if not argv:
        argv = ["gui"]
    args = build_parser().parse_args(argv)
    setup_logging(logging.DEBUG if getattr(args, "verbose", False) else logging.INFO)
    if args.command == "update":
        from .update import check
        info = check(force=True)
        if info is None:
            from .update import _LAST_ERROR
            reason = _LAST_ERROR or "no response"
            print(f"  Could not check for updates: {reason}")
            return 1
        if info.available:
            print(f"  Update available: v{info.latest}  (you have v{info.current})")
            print(f"  Download: {info.url}")
        else:
            print(f"  You are on the latest version (v{info.current}).")
        return 0

    if args.command == "gui":
        from .update import notify_if_available
        notify_if_available()
        from .bootstrap import ensure_chromium
        ensure_chromium()
        from .gui import serve
        return serve(port=args.port, open_browser=not args.no_open)
    if args.command == "record":
        if not args.attach:
            from .bootstrap import ensure_chromium
            ensure_chromium()
        try:
            return asyncio.run(_record(args))
        except KeyboardInterrupt:
            return 0

    if args.command == "run":
        from .update import notify_if_available
        notify_if_available()
        if not args.attach:
            from .bootstrap import ensure_chromium
            ensure_chromium()   # before the loop starts
        try:
            return asyncio.run(_run(args))
        except KeyboardInterrupt:
            return 130
    return 1


if __name__ == "__main__":
    sys.exit(main())
