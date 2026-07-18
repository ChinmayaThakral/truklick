"""Recorder — demonstrate a task once, get a runnable recipe.

You click through the task by hand; we watch over CDP and write a recipe.

The important part is NOT "replay these clicks". A replayed click list is a macro,
and macros break. Because we see the page, every recorded click becomes a
declarative pair:

    wait_for <target>      <- wait until the thing is actually there
    click    <target>      <- then click it

That is what makes a recording survive slow loads, animations and redesigns — the
difference between a brittle macro and a recipe.

Targets are captured with the strategy ranking we learned empirically:
visible text and ARIA role first, CSS selector only as a last resort, and
framework-generated ids (React/Radix `«r3»`-style) are refused outright because
they change on every render.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Optional

from .log import get_logger

log = get_logger("recorder")

# Runs in the page. Reports a click plus every way we might re-find the element.
_HOOK_JS = r"""
() => {
  if (window.__truklickRec) return;
  window.__truklickRec = true;

  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  // React/Radix/Emotion generated ids change every render — never target them.
  const junkId = id => !id || /[«»]|^:r[0-9a-z]+:?$|^radix-|^headlessui-|^mui-\d/i.test(id);

  function cssPath(el) {
    const parts = [];
    while (el && el.nodeType === 1 && parts.length < 5) {
      let sel = el.nodeName.toLowerCase();
      if (!junkId(el.id)) { parts.unshift(sel + '#' + CSS.escape(el.id)); break; }
      const cls = (typeof el.className === 'string' ? el.className : '')
        .trim().split(/\s+/).filter(Boolean).slice(0, 2)
        .map(c => '.' + CSS.escape(c)).join('');
      sel += cls;
      const par = el.parentElement;
      if (par) {
        const sibs = [...par.children].filter(c => c.nodeName === el.nodeName);
        if (sibs.length > 1) sel += ':nth-of-type(' + (sibs.indexOf(el) + 1) + ')';
      }
      parts.unshift(sel);
      el = el.parentElement;
    }
    return parts.join(' > ');
  }

  function roleOf(el) {
    const explicit = el.getAttribute('role');
    if (explicit) return explicit;
    const tag = el.nodeName.toLowerCase();
    if (tag === 'button') return 'button';
    if (tag === 'a' && el.hasAttribute('href')) return 'link';
    if (tag === 'input') {
      const t = (el.type || '').toLowerCase();
      if (['button', 'submit', 'reset'].includes(t)) return 'button';
      if (t === 'checkbox') return 'checkbox';
    }
    return null;
  }

  // The element the user *meant*: nearest clickable ancestor, else the target.
  function meaningful(el) {
    let n = el;
    for (let i = 0; i < 4 && n; i++, n = n.parentElement) {
      if (roleOf(n)) return n;
      if (getComputedStyle(n).cursor === 'pointer') return n;
    }
    return el;
  }

  document.addEventListener('click', (e) => {
    if (!e.isTrusted) return;                  // ignore our own synthetic clicks
    const el = meaningful(e.target);
    if (!el || el.id === '__truklick_toast') return;
    const label = norm(el.getAttribute('aria-label') || el.innerText || el.value);
    window.__truklickHit({
      text: label.slice(0, 80),
      role: roleOf(el),
      id: junkId(el.id) ? null : el.id,
      css: cssPath(el),
      tag: el.nodeName.toLowerCase(),
      url: location.href,
      t: Date.now(),
    });
  }, true);
}
"""


def _target_for(hit: dict) -> dict:
    """Pick the most durable strategy available (text/role beat CSS here)."""
    text, role = hit.get("text"), hit.get("role")
    if role and text:
        return {"role": role, "name": text, "exact": True}
    if text:
        return {"text": text, "exact": True}
    if hit.get("id"):
        return {"selector": f"#{hit['id']}"}
    return {"selector": hit.get("css") or hit.get("tag") or "*"}


class Recorder:
    def __init__(self, page, keep_delays: bool = True) -> None:
        self.page = page
        self.keep_delays = keep_delays
        self.hits: list[dict] = []
        self._last_t: Optional[float] = None

    async def start(self) -> None:
        async def on_hit(_source, hit):
            now = time.time()
            gap = 0 if self._last_t is None else int((now - self._last_t) * 1000)
            self._last_t = now
            hit["gap_ms"] = gap
            self.hits.append(hit)
            log.info("recorded #%d: %s %r", len(self.hits), hit.get("tag"),
                     (hit.get("text") or "")[:40])

        await self.page.expose_binding("__truklickHit", on_hit)
        await self.page.add_init_script(f"({_HOOK_JS})()")
        await self.page.evaluate(f"({_HOOK_JS})()")
        log.info("Recording. Do the task in the browser; press Ctrl+C here when done.")

    def build(self, name: str, url: str, loop: bool = True) -> dict:
        steps: list[dict] = []
        for i, hit in enumerate(self.hits):
            target = _target_for(hit)
            # A pause the user took is meaningful (waiting for something) — but we
            # express it as a wait_for on the NEXT target, not a blind sleep, so it
            # self-adjusts. Tunable delays are kept separately for the editor.
            if self.keep_delays and i > 0 and hit["gap_ms"] > 1500:
                steps.append({"action": "wait", "ms": min(hit["gap_ms"], 5000),
                              "_note": "recorded pause — tune or delete"})
            steps.append({"action": "wait_for", "target": target,
                          "timeout_ms": 30000, "poll_ms": 25})
            steps.append({"action": "click", "target": target})
        if steps:
            last = steps[-1]["target"]
            steps.append({"action": "expect", "target": last, "present": False,
                          "timeout_ms": 10000,
                          "name": "last action had an effect",
                          "_note": "verifies the OUTCOME, not just the click. Change "
                                   "or delete if the element is meant to stay."})
        return {
            "_comment": f"Recorded by Truklick from {len(self.hits)} action(s). "
                        "Each click became wait_for + click so it survives slow "
                        "loads. Tune timings in the control panel.",
            "name": name,
            "match_url": (url.split("?")[0].rstrip("/") + "/*") if url else "*",
            "url": url,
            "hotkey": "Escape",
            "loop": loop,
            "loop_delay_ms": 100,
            "steps": steps,
        }

    def save(self, path: Path, name: str, url: str, loop: bool = True) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.build(name, url, loop), indent=2,
                                   ensure_ascii=False) + "\n", encoding="utf-8")
        return path
