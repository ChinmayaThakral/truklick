# FEATURE SPEC — Objective DOM Scanner / Capture ("Capture Mode")

> Drop this in `docs/` (e.g. `docs/FEATURE_SCANNER.md`) and hand it to Claude Code.
> This is a Phase-2 feature (visual picker family in ROADMAP). It must obey every
> rule in CLAUDE.md and must not contradict docs/PROVEN_FACTS.md.

---

## GOAL (in the human's words, kept objective)

Let a **non-coder** capture, with **no code**, the elements on any page — especially
when a target UI (e.g. an order popup) appears — so those captures can **later** be
turned into accurate recipes. The scanner is **deliberately unopinionated**: it does
NOT decide what is "noise." It captures **everything visible**, because what's noise on
one site is the target on another. Filtering/selection is a later, per-recipe concern —
NOT the scanner's job.

## NON-GOALS (do not build these here)
- No filtering/ranking of "important" elements. Capture all; let recipe-authoring pick.
- No clicking / no automation actions. This feature only *observes and records*.
- No recipe generation yet. Output is a raw, complete **capture artifact**; converting
  captures → recipes is a separate later step.
- No opinion about P2P.me. The scanner is 100% use-case-agnostic (ADR-006).

---

## ARCHITECTURE DECISION TO MAKE FIRST (justify against PROVEN_FACTS)

**Default/expected approach: CDP-injected capture, NOT a separate browser extension.**

Reasoning Claude Code must weigh and record as an ADR:
- The engine already controls Chromium over CDP (FACT 1–3). It can inject a scanning
  script into the page via CDP (`Runtime.evaluate` / `Page.addScriptToEvaluateOnNewDocument`)
  and read the entire DOM — no separate install, no Web Store review, no cross-browser
  extension versioning, no second maintenance surface.
- An extension would add a parallel way into the page and ongoing publishing/versioning
  burden, for capability the CDP rail already provides. Extensions also can't do trusted
  input anyway (FACT 1), so there's no input reason to introduce one.
- **Only** choose an extension if there is a concrete capability CDP-injection cannot
  provide for *capture* (there very likely isn't). If Claude Code believes an extension
  is warranted, it must justify it explicitly against PROVEN_FACTS and get human sign-off
  before building it. Do not silently default to "build a Chrome extension."

Record the choice as a new ADR (e.g. ADR-009) in docs/DECISIONS.md.

---

## WHAT TO CAPTURE (objective + complete)

Trigger: a hotkey (configurable; distinct from the run/toggle hotkey) puts the current
page into **Capture Mode** and writes a **capture artifact** (a JSON file) describing
the page state at that moment.

For **every visible element** on the page (across the **main frame, all iframes, and
open shadow DOM**), record ALL of the following so the capture is objective AND directly
convertible into accurate recipes later:

- `tag` — element tag name.
- `visible_text` — trimmed visible text content (and `aria-label` / `title` / `alt`
  / `placeholder` / `value` if present).
- `role` — ARIA role (explicit or implicit) + accessible name.
- `id`, `classes` — raw id and class list.
- `css_selector` — a robust, reasonably-unique CSS selector for re-finding it.
- `xpath` — an absolute XPath as a fallback strategy.
- `attributes` — the full attribute map (so nothing is lost).
- `bounding_box` — {x, y, width, height} in page/CSS pixels (center is derivable).
- `frame_path` — where it lives: "main", or the iframe chain (indexes/urls), or a
  shadow-DOM host path. This is REQUIRED — a target is useless if we don't know which
  frame/shadow root to look in.
- `visible` — boolean (in viewport / not display:none / not visibility:hidden).
- `clickable_hint` — best-effort boolean (has click handler / is button/link/role).
  This is a *hint only*, never a filter.

Also capture page-level context: `url`, `title`, `timestamp`, `viewport` size, and a
`frames[]` inventory (main + each iframe's url + a shadow-DOM presence flag).

> RATIONALE (do not skip): capturing visible_text ALONE is useless for building recipes,
> because text is not a reliable way to re-find an element. Capturing the FULL strategy
> set (text + role + id + classes + css_selector + xpath + frame_path + bbox) is what
> makes captures convertible into ACCURATE recipes. Objective completeness = capture
> everything, every strategy, no filtering — not "text only."

## OUTPUT FORMAT

Write a `capture-<timestamp>.json` artifact (a directory like `captures/` — gitignore
it; captures may contain page content the user doesn't want committed). Shape:

```json
{
  "url": "...",
  "title": "...",
  "timestamp": "...",
  "viewport": { "width": 0, "height": 0 },
  "frames": [ { "path": "main", "url": "..." }, { "path": "iframe[0]", "url": "..." } ],
  "elements": [
    {
      "tag": "button",
      "visible_text": "Close",
      "role": "button",
      "accessible_name": "Close",
      "id": "",
      "classes": ["btn","btn-secondary"],
      "css_selector": "div.modal > button.btn-secondary",
      "xpath": "/html/body/div[3]/button[2]",
      "attributes": { "type": "button", "data-x": "..." },
      "bounding_box": { "x": 0, "y": 0, "width": 0, "height": 0 },
      "frame_path": "main",
      "visible": true,
      "clickable_hint": true
    }
  ]
}
```

The `elements[]` entries map 1:1 onto the engine's existing `target` strategies
(selector / role+name / text / fallback_selector) so a later step can turn any captured
element straight into a recipe target with high accuracy.

## HOW IT SHOULD FEEL (non-coder UX, minimal for now)

- Run the browser via the existing engine, log in / get the target UI on screen.
- Press the capture hotkey → Truklick injects the scan via CDP, writes the artifact,
  logs "Captured N elements across M frames → captures/capture-<ts>.json".
- (Optional, nice-to-have, not required for v1) briefly highlight/outline captured
  elements on the page so the user sees it worked. Keep it non-destructive.
- That's it. No selection, no code. Selection happens later when authoring a recipe
  from the artifact.

## CONSTRAINTS (from CLAUDE.md / PROVEN_FACTS — restate, don't violate)
- CDP rail only unless an extension is explicitly justified + signed off (see above).
- Use-case-agnostic: no P2P.me specifics in the scanner (ADR-006).
- Search main frame + iframes + shadow DOM. Missing a frame path = broken capture.
- Python 3.12; Playwright for lifecycle + raw CDP for the injection.
- Never contradict PROVEN_FACTS; if a browser behavior is uncertain (e.g. reading
  closed shadow roots, cross-origin iframe access limits), write a tiny PoC in /poc,
  run it (or ask the human), and record the result before relying on it.
- Gitignore `captures/` (page content / possible sensitive data).

## HONEST LIMITATIONS TO SURFACE (Claude Code must note these)
- **Cross-origin iframes**: CDP can often reach them, but same-origin-policy and site
  headers can block script injection into some frames. Capture what's reachable; record
  which frames were unreachable rather than silently dropping them.
- **Closed shadow DOM**: cannot be read by design. Record its presence; don't pretend.
- **Dynamic pages**: the capture is a snapshot at hotkey time. If the popup mutates,
  the user re-captures. That's fine and expected.

## DEFINITION OF DONE (v1)
- A capture hotkey produces a complete `capture-<ts>.json` for the current page,
  covering main frame + iframes + open shadow DOM, with the full strategy set per
  element and correct frame paths.
- Proven on the bundled `examples/selftest.html` (add a couple of nested/iframe cases),
  and — when the human has a live order — on the real lp.p2p.me popup, confirming the
  Close/Accept controls appear in the artifact with usable selectors + frame paths.
- New ADR recorded (CDP-injection vs extension decision). SESSION_LOG updated.
- No filtering of elements. Completeness verified (count matches a manual DOM count on
  the test page).

---

## REVIEWER NOTES — technical corrections before implementation

> Added by Claude Code (2026-07-16) reviewing the spec above. The spec is sound; these
> are three places where a naive implementation would "quietly lie," plus a reuse note.
> Fold them into the body when this feature is actually built. Trim freely if you disagree.

**1. The cross-origin iframe limitation is overstated for OUR rail.**
The "Honest Limitations" note frames cross-origin iframes through the *in-page-JS*
same-origin model. But we don't inject from page JS — we drive Playwright/CDP, which
operates at the protocol level and is **not** bound by same-origin policy. Playwright
already enumerates cross-origin frames (`page.frames`) and can `frame.evaluate()` in
them. The real boundaries are narrower: (a) out-of-process iframes (OOPIFs) not attached
to the CDP session/target we hold, and (b) frames the browser refuses to expose. So the
rule should be: *attempt every frame Playwright lists; record the specific frames where
evaluation raised* — don't pre-assume "cross-origin = unreachable." Getting this wrong
makes the scanner under-report reachable targets.

**2. Bounding-box coordinate space is a real correctness trap (this is the one that
bites).** A raw `getBoundingClientRect()` executed *inside* an iframe returns coordinates
relative to **that iframe's** viewport. But the engine's trusted click (`cdp_input.py`)
dispatches in **main-frame** viewport CSS pixels. If the capture stores bare in-iframe
rects and labels them "page/CSS pixels," every captured iframe element's bbox will be
wrong at click time — a silent lie of exactly the kind this doc exists to prevent.
Fix: **reuse Playwright's `locator.bounding_box()`**, which already returns
main-frame-relative coords — it's what `targeting.py` uses today and what the Session-1
e2e trusted-click proof relied on. (Alternative: store the frame-relative rect *plus*
the frame's offset so it's translatable, but reusing `bounding_box()` is simpler and
already proven.)

**3. Whole-page traversal must recurse open shadow roots explicitly.**
`document.querySelectorAll('*')` does **not** descend into shadow DOM. The walk has to
recurse `element.shadowRoot` (open only) at each node. The spec intends this
("across … open shadow DOM") — just don't let it get lost in implementation, because a
missed shadow root silently drops real targets.

**4. Reuse the engine's targeting vocabulary, don't reinvent it.**
Build each element's strategy set to map 1:1 onto the existing `target` dict
(`selector` / `role`+`name` / `text` / `fallback_selector` in `targeting.py`) so a
capture converts straight into a recipe target with no lossy translation. This keeps the
capture↔recipe accuracy honest and avoids a second, divergent selector model.

**5. PoC-first, per CLAUDE.md.** Before relying on cross-origin reach and shadow reads on
the real target, write one `/poc` that scans a page with: a nested same-origin iframe, a
cross-origin iframe, an open shadow root, and a closed shadow root — and record in
PROVEN_FACTS what actually reads. The lp.p2p.me popup's rendering (main frame? iframe?
shadow DOM?) is the load-bearing unknown; capture that during the Phase-1 real-site run
so this feature is designed against reality, not a guess.
