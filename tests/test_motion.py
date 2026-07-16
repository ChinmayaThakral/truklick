"""Motion profile tests (pure, deterministic with a seeded RNG)."""
import math
import random

from truklick.motion import MotionProfile, path, _ease_in_out_quad


def test_easing_bounds():
    assert _ease_in_out_quad(0) == 0
    assert _ease_in_out_quad(1) == 1
    assert 0 < _ease_in_out_quad(0.5) < 1


def test_path_lands_exactly_on_target():
    prof = MotionProfile(enabled=True, steps=15, jitter_px=3.0)
    pts = path((0, 0), (100, 40), prof, random.Random(1))
    assert pts[-1] == (100, 40)
    assert len(pts) == 15


def test_path_stays_near_the_line():
    # jitter tapers at the ends; midpoints wobble but stay within jitter bound
    prof = MotionProfile(enabled=True, steps=50, jitter_px=2.0)
    pts = path((0, 0), (100, 0), prof, random.Random(7))
    # perpendicular is the y axis here; |y| must never exceed jitter bound
    assert all(abs(y) <= 2.0 + 1e-9 for _, y in pts)


def test_zero_distance():
    prof = MotionProfile(enabled=True, steps=10)
    assert path((5, 5), (5, 5), prof) == [(5, 5)]
