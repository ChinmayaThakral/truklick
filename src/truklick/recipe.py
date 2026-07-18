"""Recipe model + loader.

A recipe is user content (ADR-006) — a human-readable JSON file describing steps.
The engine parses it into typed objects and knows nothing site-specific. Keys
beginning with '_' (e.g. "_comment", "_note") are treated as documentation and
ignored, so authors can annotate recipes freely.

Recipe format v1 (ARCHITECTURE §4):
{
  "name": "...",
  "match_url": "https://site/*",   # guard: only run on matching URLs
  "url": "https://site/",          # optional: navigate here on start
  "hotkey": "Escape",              # start/stop toggle key
  "loop": true,
  "loop_delay_ms": 200,
  "steps": [ {action, ...}, ... ]
}

Step actions: wait_for, click, swipe, type, wait, loop, condition.
"""
from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

VALID_ACTIONS = {"wait_for", "click", "swipe", "type", "wait", "loop", "condition",
                 "expect"}


def _strip_comments(obj: Any) -> Any:
    """Recursively drop dict keys starting with '_' (author annotations)."""
    if isinstance(obj, dict):
        return {k: _strip_comments(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [_strip_comments(v) for v in obj]
    return obj


@dataclass
class Step:
    action: str
    raw: dict = field(default_factory=dict)  # the full (comment-stripped) step dict

    # convenience accessors
    @property
    def target(self) -> Optional[dict]:
        return self.raw.get("target")

    @property
    def timeout_ms(self) -> int:
        return int(self.raw.get("timeout_ms", 30000))

    @property
    def ms(self) -> int:
        return int(self.raw.get("ms", 0))

    @property
    def poll_ms(self) -> int:
        """How often wait_for re-checks the DOM. Lower = faster reaction, more CPU."""
        return int(self.raw.get("poll_ms", 250))

    @property
    def text(self) -> str:
        return str(self.raw.get("text", ""))

    @property
    def steps(self) -> list["Step"]:
        return [Step(s["action"], s) for s in self.raw.get("steps", [])]


@dataclass
class Recipe:
    name: str
    match_url: str
    steps: list[Step]
    url: Optional[str] = None
    hotkey: str = "Escape"
    loop: bool = False
    loop_delay_ms: int = 200
    source_path: Optional[Path] = None

    def matches(self, current_url: str) -> bool:
        """True if the current URL matches match_url (glob)."""
        if not self.match_url:
            return True
        return fnmatch.fnmatch(current_url, self.match_url)


class RecipeError(ValueError):
    pass


def _validate_step(idx: int, step: dict) -> None:
    action = step.get("action")
    if action not in VALID_ACTIONS:
        raise RecipeError(
            f"step[{idx}]: unknown action {action!r}. Valid: {sorted(VALID_ACTIONS)}"
        )
    if action in {"wait_for", "click", "expect"} and not step.get("target"):
        raise RecipeError(f"step[{idx}]: '{action}' requires a 'target'")
    if action == "wait" and "ms" not in step:
        raise RecipeError(f"step[{idx}]: 'wait' requires 'ms'")
    if action == "type" and "text" not in step:
        raise RecipeError(f"step[{idx}]: 'type' requires 'text'")
    if action == "swipe" and not (step.get("from") and step.get("to")):
        # allow a single target-based slider too; require at least a target or from/to
        if not step.get("target"):
            raise RecipeError(
                f"step[{idx}]: 'swipe' requires 'target' or both 'from' and 'to'"
            )
    for j, nested in enumerate(step.get("steps", [])):
        _validate_step(f"{idx}.{j}", nested)


def load_recipe(path: str | Path) -> Recipe:
    """Load, comment-strip, validate, and parse a recipe JSON file."""
    p = Path(path)
    if not p.exists():
        raise RecipeError(f"Recipe not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RecipeError(f"Invalid JSON in {p}: {exc}") from exc

    data = _strip_comments(data)

    if "name" not in data:
        raise RecipeError("Recipe missing 'name'")
    if "steps" not in data or not isinstance(data["steps"], list):
        raise RecipeError("Recipe missing 'steps' list")
    for i, step in enumerate(data["steps"]):
        _validate_step(i, step)

    return Recipe(
        name=data["name"],
        match_url=data.get("match_url", ""),
        url=data.get("url"),
        hotkey=data.get("hotkey", "Escape"),
        loop=bool(data.get("loop", False)),
        loop_delay_ms=int(data.get("loop_delay_ms", 200)),
        steps=[Step(s["action"], s) for s in data["steps"]],
        source_path=p,
    )
