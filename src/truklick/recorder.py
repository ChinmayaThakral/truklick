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
    const info = {
      text: label.slice(0, 80),
      role: roleOf(el),
      id: junkId(el.id) ? null : el.id,
      css: cssPath(el),
      tag: el.nodeName.toLowerCase(),
      url: location.href,
      t: Date.now(),
      vanished: null,
    };
    window.__truklickHit(info);
    // Observe the OUTCOME rather than assuming it: did this element actually go
    // away? Only then is 'expect absent' a true statement about the task.
    setTimeout(() => {
      const gone = !document.contains(el) || !el.getBoundingClientRect().width;
      window.__truklickOutcome({ t: info.t, vanished: gone });
    }, 900);
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

        async def on_outcome(_source, data):
            for h in reversed(self.hits):
                if h.get("t") == data.get("t"):
                    h["vanished"] = bool(data.get("vanished"))
                    break

        await self.page.expose_binding("__truklickHit", on_hit)
        await self.page.expose_binding("__truklickOutcome", on_outcome)
        await self.page.add_init_script(f"({_HOOK_JS})()")
        await self.page.evaluate(f"({_HOOK_JS})()")
        log.info("Recording. Do the task in the browser; press Ctrl+C here when done.")

    def build(self, name: str, url: str, loop: bool = True) -> dict:
        steps: list[dict] = []
        fragile: list[str] = []
        for hit in self.hits:
            target = _target_for(hit)
            # No blind sleeps: wait_for already waits for the real thing, and a fixed
            # sleep only makes the recipe slower and more brittle. The observed gap is
            # kept as metadata so it can be re-added in the Tune panel if wanted.
            wf = {"action": "wait_for", "target": target,
                  "timeout_ms": 30000, "poll_ms": 25}
            if hit.get("gap_ms"):
                wf["_recorded_gap_ms"] = hit["gap_ms"]
            if "selector" in target:
                # Fell back to a raw CSS path — on utility-class frameworks these
                # break on any restyle. Never let that be silent.
                fragile.append(target["selector"])
                wf["_FRAGILE"] = ("No text or ARIA name on this element, so only a CSS "
                                  "path was available. This WILL break if the page is "
                                  "restyled — give the element a stable label or "
                                  "replace this target by hand.")
            steps.append(wf)
            steps.append({"action": "click", "target": target})

        # Only assert an outcome we actually OBSERVED. Auto-asserting that the last
        # element disappears is wrong for navigation clicks and makes the recipe fail
        # on every run.
        if self.hits and self.hits[-1].get("vanished"):
            steps.append({"action": "expect", "target": _target_for(self.hits[-1]),
                          "present": False, "timeout_ms": 10000, "poll_ms": 100,
                          "name": "last action had an effect",
                          "_note": "Added because this element was OBSERVED to "
                                   "disappear after you clicked it during recording."})
        out = {
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
        if fragile:
            out["_WARNING_fragile_targets"] = (
                f"{len(fragile)} step(s) had to fall back to a raw CSS path because the "
                "element has no visible text or aria-label. Those are the first things "
                "that will break when the site is restyled — review them.")
        return out

    def save(self, path: Path, name: str, url: str, loop: bool = True) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.build(name, url, loop), indent=2,
                                   ensure_ascii=False) + "\n", encoding="utf-8")
        return path
