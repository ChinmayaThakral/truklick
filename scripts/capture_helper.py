"""
============================================================================
 TRUKLICK CAPTURE HELPER — the easy way to grab button info
============================================================================

WHAT THIS DOES (no DevTools, no right-clicking, no copying selectors):
  1. Opens Chromium (with a persistent profile, so you log in once).
  2. You use lp.p2p.me normally.
  3. Whenever the thing you care about is ON SCREEN, you switch to this
     terminal and press ENTER. It snapshots EVERY clickable element on the
     current screen into a file in ./captures/.
  4. You do this twice for your flow:
        - when the ORDER POPUP is showing  -> captures the "Close" button
        - after you click Close, when the HOME screen shows the clean
          "Accept" button -> press ENTER again to capture that.
  5. Send me (or keep) the saved files. Each button's full targeting info
     (text, selector, xpath, role, frame, box) is in there — everything
     needed to build an accurate recipe.

  It also prints, right in the terminal, a short list of the clickable
  things it found each time (with their text), so you can SEE it worked and
  tell me which line is "Close" and which is "Accept" if the text isn't
  obvious.

REQUIREMENTS (same as before, already installed):
    python -m pip install playwright
    python -m playwright install chromium

RUN (from the repo root, so ./p2p_profile is reused / created here):
    python scripts/capture_helper.py

CONTROLS (type in the terminal, then press ENTER):
    (just ENTER) = capture whatever is on screen right now
    l            = capture + show a longer list (more elements)
    q            = quit
============================================================================
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

LAUNCH_ARGS = [
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-ipc-flooding-protection",
    "--disable-features=CalculateNativeWinOcclusion",
]

PROFILE_DIR = "./p2p_profile"      # same profile as the PoC — login is remembered
CAPTURE_DIR = Path("./captures")
TARGET_URL = "https://lp.p2p.me"

# This JS runs INSIDE the page and each iframe. It collects every element that
# is plausibly clickable (button/link/role=button/onclick/pointer cursor) OR has
# visible text, and records the full strategy set for each. Bounding boxes here
# are in-frame; we DO NOT trust them for clicking — for the real recipe we re-find
# by selector/text (which targeting.py resolves to correct main-frame coords).
COLLECT_JS = r"""
() => {
  function cssPath(el) {
    if (!(el instanceof Element)) return '';
    const parts = [];
    while (el && el.nodeType === 1 && parts.length < 6) {
      let sel = el.nodeName.toLowerCase();
      if (el.id) { sel += '#' + CSS.escape(el.id); parts.unshift(sel); break; }
      const cls = (el.className && typeof el.className === 'string')
        ? el.className.trim().split(/\s+/).filter(Boolean).slice(0,3).map(c => '.'+CSS.escape(c)).join('')
        : '';
      sel += cls;
      const parent = el.parentNode;
      if (parent && parent.children) {
        const sibs = Array.from(parent.children).filter(c => c.nodeName === el.nodeName);
        if (sibs.length > 1) sel += ':nth-of-type(' + (sibs.indexOf(el)+1) + ')';
      }
      parts.unshift(sel);
      el = el.parentElement;
    }
    return parts.join(' > ');
  }
  function xPath(el) {
    if (el && el.id) return '//*[@id="' + el.id + '"]';
    const parts = [];
    while (el && el.nodeType === 1) {
      let i = 1, sib = el.previousElementSibling;
      while (sib) { if (sib.nodeName === el.nodeName) i++; sib = sib.previousElementSibling; }
      parts.unshift(el.nodeName.toLowerCase() + '[' + i + ']');
      el = el.parentElement;
    }
    return '/' + parts.join('/');
  }
  function visibleText(el) {
    const t = (el.innerText || el.textContent || '').trim().replace(/\s+/g,' ');
    return t.slice(0, 120);
  }
  function isVisible(el) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return false;
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity) === 0) return false;
    return true;
  }
  function clickableHint(el) {
    const tag = el.nodeName.toLowerCase();
    if (['button','a','input','select','textarea','label'].includes(tag)) return true;
    const role = el.getAttribute('role');
    if (role && ['button','link','tab','menuitem','checkbox','switch'].includes(role)) return true;
    if (el.onclick) return true;
    if (getComputedStyle(el).cursor === 'pointer') return true;
    return false;
  }

  const out = [];
  const all = Array.from(document.querySelectorAll('*'));
  for (const el of all) {
    if (!isVisible(el)) continue;
    const text = visibleText(el);
    const hint = clickableHint(el);
    // keep it objective but useful: capture clickable things, or elements with short
    // button-like text. (We are not filtering hard — just avoiding whole-page text blobs.)
    if (!hint && !(text && text.length > 0 && text.length <= 40)) continue;
    const r = el.getBoundingClientRect();
    out.push({
      tag: el.nodeName.toLowerCase(),
      visible_text: text,
      aria_label: el.getAttribute('aria-label') || '',
      title: el.getAttribute('title') || '',
      value: (el.value !== undefined ? String(el.value) : '') || '',
      placeholder: el.getAttribute('placeholder') || '',
      role: el.getAttribute('role') || '',
      id: el.id || '',
      classes: (el.className && typeof el.className === 'string') ? el.className : '',
      css_selector: cssPath(el),
      xpath: xPath(el),
      clickable_hint: hint,
      in_frame_rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }
    });
  }
  return out;
}
"""


async def collect_from_all_frames(page):
    """Run COLLECT_JS in the main frame and every child frame. Tag each element
    with which frame it came from."""
    results = []
    frames = [page.main_frame] + [f for f in page.frames if f != page.main_frame]
    for idx, frame in enumerate(frames):
        where = "main" if frame == page.main_frame else f"iframe[{idx}] {frame.url[:60]}"
        try:
            els = await frame.evaluate(COLLECT_JS)
            for e in els:
                e["frame_path"] = where
            results.extend(els)
        except Exception as ex:
            results.append({"frame_error": where, "error": str(ex)})
    return results


def summarize(elements, limit):
    """Print a short, human-readable list so the user can see it worked and
    identify Close / Accept by their text."""
    clickables = [e for e in elements if e.get("clickable_hint")]
    print(f"\n  Found {len(elements)} elements ({len(clickables)} look clickable). "
          f"Showing up to {limit} likely buttons:")
    shown = 0
    for e in clickables:
        label = e.get("visible_text") or e.get("aria_label") or e.get("value") or "(no text)"
        if not label.strip():
            continue
        print(f"    [{shown}] '{label}'  <{e['tag']}>  frame={e['frame_path']}")
        shown += 1
        if shown >= limit:
            break
    if shown == 0:
        print("    (no obvious labelled buttons — the full data is still saved to the file)")


async def main():
    CAPTURE_DIR.mkdir(exist_ok=True)
    async with async_playwright() as p:
        print("\n[1] Opening Chromium (persistent profile — log in once)...")
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            args=LAUNCH_ARGS,
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(TARGET_URL, wait_until="domcontentloaded")

        print("""
============================================================
  READY.

  Use lp.p2p.me normally. When the thing you want is on
  screen, come back HERE and press ENTER to capture it.

  YOUR FLOW:
    1) When an ORDER POPUP shows (Slide to Accept + Close),
       press ENTER  -> captures the Close button.
    2) Click Close yourself. The HOME screen now shows the
       clean Accept button. Press ENTER again
       -> captures the Accept button.

  Commands:  ENTER = capture   |   l = capture + longer list   |   q = quit
============================================================
""")
        loop = asyncio.get_running_loop()
        while True:
            cmd = await loop.run_in_executor(None, input, "  >> press ENTER to capture (or 'q' to quit): ")
            cmd = cmd.strip().lower()
            if cmd == "q":
                break
            limit = 40 if cmd == "l" else 15

            elements = await collect_from_all_frames(page)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = CAPTURE_DIR / f"capture_{ts}.json"
            artifact = {
                "url": page.url,
                "title": await page.title(),
                "timestamp": ts,
                "element_count": len(elements),
                "elements": elements,
            }
            fname.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
            summarize(elements, limit)
            print(f"\n  ✓ Saved full capture -> {fname}")
            print("    (Tell me which [number] is Close / Accept, or just send me this file.)\n")

        print("\n[done] Closing. Your captures are in ./captures/")
        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
