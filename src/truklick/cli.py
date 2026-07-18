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
    run.add_argument("--human-motion", action="store_true",
                     help="Enable human-like motion (easing+jitter). Refinement.")
    run.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    return p


async def _run(args: argparse.Namespace) -> int:
    try:
        recipe = load_recipe(args.recipe)
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(logging.DEBUG if getattr(args, "verbose", False) else logging.INFO)
    if args.command == "run":
        try:
            return asyncio.run(_run(args))
        except KeyboardInterrupt:
            return 130
    return 1


if __name__ == "__main__":
    sys.exit(main())
