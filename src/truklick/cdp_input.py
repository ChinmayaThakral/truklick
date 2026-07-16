"""Raw CDP input — the trusted-click pipeline.

ADR-001/002 + PROVEN_FACTS FACT 1 & 2: ALWAYS use raw Input.dispatchMouseEvent
(and Input.dispatchKeyEvent) at computed coordinates. NEVER use high-level
element.click(), which scrolls-into-view via IntersectionObserver and breaks in
a backgrounded/minimized window. Everything here talks to a CDPSession directly.

Coordinates are CSS pixels in the main-frame viewport (what Playwright's
bounding_box() returns), which is exactly what Input.dispatchMouseEvent expects.
"""
from __future__ import annotations

import asyncio
import random
from typing import Optional

from playwright.async_api import CDPSession

from .log import get_logger
from .motion import MotionProfile, path, step_delay

log = get_logger("input")

# Minimal key map for named/special keys. Printable text goes via Input.insertText.
# windowsVirtualKeyCode values are the standard VKs (used across platforms by CDP).
_KEY_MAP: dict[str, dict] = {
    "Enter": {"key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "text": "\r"},
    "Tab": {"key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9},
    "Escape": {"key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27},
    "Backspace": {"key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8},
    "Delete": {"key": "Delete", "code": "Delete", "windowsVirtualKeyCode": 46},
    "ArrowLeft": {"key": "ArrowLeft", "code": "ArrowLeft", "windowsVirtualKeyCode": 37},
    "ArrowUp": {"key": "ArrowUp", "code": "ArrowUp", "windowsVirtualKeyCode": 38},
    "ArrowRight": {"key": "ArrowRight", "code": "ArrowRight", "windowsVirtualKeyCode": 39},
    "ArrowDown": {"key": "ArrowDown", "code": "ArrowDown", "windowsVirtualKeyCode": 40},
    "Home": {"key": "Home", "code": "Home", "windowsVirtualKeyCode": 36},
    "End": {"key": "End", "code": "End", "windowsVirtualKeyCode": 35},
    "Space": {"key": " ", "code": "Space", "windowsVirtualKeyCode": 32, "text": " "},
}


class Input:
    """Raw CDP input driver bound to one CDP session.

    All motion is optional and controlled by `motion` (MotionProfile). With
    motion disabled (default), clicks are a bare mousePressed+mouseReleased at the
    target — the exact pattern proven in the PoCs.
    """

    def __init__(
        self,
        cdp: CDPSession,
        motion: Optional[MotionProfile] = None,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.cdp = cdp
        self.motion = motion or MotionProfile(enabled=False)
        self._rng = rng or random.Random()
        # track last known cursor position for realistic move origins
        self._x = 0.0
        self._y = 0.0

    def bind(self, cdp: CDPSession) -> None:
        """Rebind to a new CDP session (e.g. after a browser restart)."""
        self.cdp = cdp

    # -- primitives --------------------------------------------------------

    async def _mouse(self, event_type: str, x: float, y: float,
                     button: str = "none", click_count: int = 0,
                     buttons: int = 0) -> None:
        await self.cdp.send("Input.dispatchMouseEvent", {
            "type": event_type,
            "x": x,
            "y": y,
            "button": button,
            "buttons": buttons,
            "clickCount": click_count,
        })
        self._x, self._y = x, y

    async def move(self, x: float, y: float, buttons: int = 0) -> None:
        """Move the cursor to (x, y). Uses the motion profile if enabled."""
        if self.motion.enabled:
            for (px, py) in path((self._x, self._y), (x, y), self.motion, self._rng):
                await self._mouse("mouseMoved", px, py, buttons=buttons)
                await asyncio.sleep(step_delay(self.motion, self._rng))
        else:
            await self._mouse("mouseMoved", x, y, buttons=buttons)

    # -- gestures ----------------------------------------------------------

    async def click(self, x: float, y: float, button: str = "left",
                    click_count: int = 1) -> None:
        """Trusted click: (optional move ->) mousePressed -> mouseReleased.

        This is the load-bearing operation. Raw dispatch only (ADR-002)."""
        log.info("click (%.0f, %.0f) button=%s", x, y, button)
        if self.motion.enabled:
            await self.move(x, y)
        await self._mouse("mousePressed", x, y, button=button,
                          click_count=click_count, buttons=1)
        if self.motion.enabled and self.motion.press_delay_s:
            await asyncio.sleep(self.motion.press_delay_s)
        await self._mouse("mouseReleased", x, y, button=button,
                          click_count=click_count, buttons=0)

    async def drag(self, x1: float, y1: float, x2: float, y2: float,
                   steps: int = 20, button: str = "left") -> None:
        """Swipe/drag: mousePressed at start -> stepped mouseMoved -> mouseReleased.

        Used for slide-to-confirm style controls. Steps are eased when motion is
        enabled, otherwise linear. Raw CDP throughout (ADR-002)."""
        log.info("drag (%.0f, %.0f) -> (%.0f, %.0f) steps=%d", x1, y1, x2, y2, steps)
        await self._mouse("mousePressed", x1, y1, button=button,
                          click_count=1, buttons=1)
        if self.motion.enabled:
            prof = MotionProfile(enabled=True, steps=steps,
                                 jitter_px=self.motion.jitter_px,
                                 min_step_delay_s=self.motion.min_step_delay_s,
                                 max_step_delay_s=self.motion.max_step_delay_s)
            pts = path((x1, y1), (x2, y2), prof, self._rng)
        else:
            pts = [
                (x1 + (x2 - x1) * (i / steps), y1 + (y2 - y1) * (i / steps))
                for i in range(1, steps + 1)
            ]
        for (px, py) in pts:
            await self._mouse("mouseMoved", px, py, buttons=1)
            await asyncio.sleep(step_delay(self.motion, self._rng)
                                if self.motion.enabled else 0.008)
        await self._mouse("mouseReleased", x2, y2, button=button,
                          click_count=1, buttons=0)

    # -- keyboard ----------------------------------------------------------

    async def type_text(self, text: str, per_char_delay_s: float = 0.0) -> None:
        """Type printable text via Input.insertText (simple, reliable, trusted)."""
        log.info("type %r (%d chars)", text[:40], len(text))
        for ch in text:
            await self.cdp.send("Input.insertText", {"text": ch})
            if per_char_delay_s:
                await asyncio.sleep(per_char_delay_s)

    async def press_key(self, key: str) -> None:
        """Press a named key (Enter, Tab, Escape, arrows, ...) via keyDown/keyUp."""
        spec = _KEY_MAP.get(key)
        if spec is None:
            raise ValueError(f"Unknown key {key!r}. Known: {sorted(_KEY_MAP)}")
        log.info("press_key %s", key)
        down = {"type": "keyDown", **spec}
        await self.cdp.send("Input.dispatchKeyEvent", down)
        up = {"type": "keyUp", **{k: v for k, v in spec.items() if k != "text"}}
        await self.cdp.send("Input.dispatchKeyEvent", up)
