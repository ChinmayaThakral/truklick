"""Targeting tests that don't need a browser."""
import asyncio

import pytest

from truklick import targeting


def test_find_rejects_empty_target():
    async def go():
        # no usable strategy -> ValueError (guards against silent no-op targets)
        with pytest.raises(ValueError):
            await targeting.find(object(), {})
    asyncio.run(go())


def test_wait_for_aborts_immediately_when_cancelled():
    """should_continue() False must return None without ever touching the page,
    so a hotkey/Ctrl+C is responsive mid-wait (regression: wait_for used to block
    for the full timeout)."""
    async def go():
        # page=None would blow up if find() were called; it must not be.
        result = await targeting.wait_for(
            None, {"text": "x"}, timeout_ms=30000,
            should_continue=lambda: False,
        )
        assert result is None
    asyncio.run(go())
