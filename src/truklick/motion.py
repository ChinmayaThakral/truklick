"""Human-like motion profiles — easing + jitter for CDP mouse moves.

PROVEN_FACTS caveat: CDP input can be flagged by behavioral anti-bot systems via
motion physics (trajectory entropy, acceleration curves, timing) even though
isTrusted is genuinely true. This module generates eased, slightly jittered
paths to blunt the "too perfect" signature. It is a REFINEMENT, off by default,
and toggleable (Phase 2 territory) — simple dashboard buttons don't need it.

Pure and deterministic-ish (seedable) so it is unit-testable without a browser.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass
class MotionProfile:
    """Tunable parameters for a human-like move."""

    enabled: bool = False
    steps: int = 20            # number of intermediate mouseMoved events
    jitter_px: float = 1.2     # max perpendicular wobble
    min_step_delay_s: float = 0.004
    max_step_delay_s: float = 0.016
    press_delay_s: float = 0.06  # dwell between mousePressed and mouseReleased


def _ease_in_out_quad(t: float) -> float:
    """Ease-in-out: slow start, fast middle, slow end (0..1 -> 0..1)."""
    if t < 0.5:
        return 2 * t * t
    return 1 - pow(-2 * t + 2, 2) / 2


def path(
    start: tuple[float, float],
    end: tuple[float, float],
    profile: MotionProfile,
    rng: random.Random | None = None,
) -> list[tuple[float, float]]:
    """Return an eased, jittered list of points from start to end (inclusive of end).

    The wobble is applied perpendicular to the travel direction and tapers to
    zero at the endpoints so we always land exactly on target.
    """
    r = rng or random
    x0, y0 = start
    x1, y1 = end
    dx, dy = x1 - x0, y1 - y0
    dist = math.hypot(dx, dy)
    steps = max(1, profile.steps)
    if dist == 0:
        return [end]

    # unit perpendicular vector for lateral wobble
    px, py = -dy / dist, dx / dist

    points: list[tuple[float, float]] = []
    for i in range(1, steps + 1):
        t = i / steps
        e = _ease_in_out_quad(t)
        # taper wobble to 0 at both ends (sin envelope)
        envelope = math.sin(math.pi * t)
        wob = r.uniform(-profile.jitter_px, profile.jitter_px) * envelope
        x = x0 + dx * e + px * wob
        y = y0 + dy * e + py * wob
        points.append((x, y))
    points[-1] = (x1, y1)  # guarantee exact landing
    return points


def step_delay(profile: MotionProfile, rng: random.Random | None = None) -> float:
    r = rng or random
    return r.uniform(profile.min_step_delay_s, profile.max_step_delay_s)
