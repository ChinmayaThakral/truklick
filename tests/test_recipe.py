"""Recipe loader/validator tests (pure, no browser)."""
import json

import pytest

from truklick.recipe import RecipeError, load_recipe


def _write(tmp_path, data):
    p = tmp_path / "r.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_loads_and_strips_comments(tmp_path):
    p = _write(tmp_path, {
        "_comment": "docs only",
        "name": "R",
        "match_url": "https://x/*",
        "loop": True,
        "loop_delay_ms": 150,
        "steps": [
            {"action": "wait_for", "target": {"text": "Go"}, "_note": "x"},
            {"action": "click", "target": {"text": "Go"}},
            {"action": "wait", "ms": 100},
        ],
    })
    r = load_recipe(p)
    assert r.name == "R"
    assert r.loop is True and r.loop_delay_ms == 150
    assert len(r.steps) == 3
    # comment key stripped from step raw
    assert "_note" not in r.steps[0].raw


def test_glob_match():
    p_url = "https://lp.p2p.me/orders/123"
    from truklick.recipe import Recipe, Step
    r = Recipe(name="x", match_url="https://lp.p2p.me/*", steps=[])
    assert r.matches(p_url)
    assert not r.matches("https://evil.example/lp.p2p.me")


def test_rejects_unknown_action(tmp_path):
    p = _write(tmp_path, {"name": "R", "steps": [{"action": "explode"}]})
    with pytest.raises(RecipeError):
        load_recipe(p)


def test_requires_target_for_click(tmp_path):
    p = _write(tmp_path, {"name": "R", "steps": [{"action": "click"}]})
    with pytest.raises(RecipeError):
        load_recipe(p)


def test_missing_steps(tmp_path):
    p = _write(tmp_path, {"name": "R"})
    with pytest.raises(RecipeError):
        load_recipe(p)
