"""Global hotkey toggle (start/stop) — like the founder's Esc/End toggle.

Cross-platform via pynput (Windows/Linux/macOS). Runs a listener in a background
thread and bridges key presses into the asyncio loop with call_soon_threadsafe.

Graceful degradation: on a headless server or where pynput can't grab input
(no display, missing perms), we log a warning and rely on Ctrl+C instead — the
engine still runs. macOS additionally needs Accessibility permission for the
listener; that is a Phase 2 packaging concern.
"""
from __future__ import annotations

import asyncio
from typing import Callable, Optional

from .log import get_logger

log = get_logger("hotkey")

# Names accepted in a recipe's "hotkey" field -> pynput special key attribute.
# Single printable characters (e.g. "q") are also accepted directly.
_SPECIAL_KEYS = {
    "Escape": "esc", "Esc": "esc",
    "End": "end", "Home": "home",
    "F1": "f1", "F2": "f2", "F3": "f3", "F4": "f4", "F5": "f5", "F6": "f6",
    "F7": "f7", "F8": "f8", "F9": "f9", "F10": "f10", "F11": "f11", "F12": "f12",
    "Space": "space", "Tab": "tab", "Enter": "enter", "Pause": "pause",
    "Insert": "insert", "Delete": "delete",
}


class HotkeyToggle:
    """Listens for one key globally and invokes on_toggle() on the asyncio loop."""

    def __init__(self, key_name: str, loop: asyncio.AbstractEventLoop,
                 on_toggle: Callable[[], None]) -> None:
        self.key_name = key_name
        self.loop = loop
        self.on_toggle = on_toggle
        self._listener = None

    def start(self) -> bool:
        """Start the global listener. Returns True if active, False if degraded."""
        try:
            from pynput import keyboard
        except Exception as exc:  # import can fail without a display backend
            log.warning("Hotkey disabled (pynput unavailable: %s). Use Ctrl+C to stop.",
                        exc)
            return False

        match = self._resolve_key(keyboard)
        if match is None:
            log.warning("Unknown hotkey %r; hotkey disabled. Use Ctrl+C to stop.",
                        self.key_name)
            return False

        def on_press(key):
            if key == match:
                self.loop.call_soon_threadsafe(self.on_toggle)

        try:
            self._listener = keyboard.Listener(on_press=on_press)
            self._listener.start()
        except Exception as exc:
            log.warning("Could not start hotkey listener (%s). Use Ctrl+C to stop.",
                        exc)
            return False

        log.info("Hotkey '%s' armed — press it to start/stop.", self.key_name)
        return True

    def _resolve_key(self, keyboard):
        special = _SPECIAL_KEYS.get(self.key_name)
        if special:
            return getattr(keyboard.Key, special, None)
        if len(self.key_name) == 1:
            return keyboard.KeyCode.from_char(self.key_name)
        return None

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None
