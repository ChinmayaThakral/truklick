# SESSION_LOG.md — Running Session Log

> Append a dated entry at the END of every working session. This is how the project
> keeps continuity and never drifts. Newest entries at the bottom. Each entry:
> what was attempted, what worked, what failed, decisions made, and the exact
> next step for the following session.

---

## SESSION 0 — Origin & Foundation (pre-repo, 2026-06-27)

**Context / how we got here:**
The founder was running a hand-built automation on an Ubuntu VPS to operate a merchant
dashboard (P2P.me): a virtual display (Xvfb) + Openbox + x11vnc + self-hosted RustDesk
(for phone access) + an `xdotool` bash script clicking fixed screen coordinates in a
loop, kept alive by systemd services and a watchdog. It worked but was fragile,
coordinate-dependent, and impossible for a non-coder to reproduce. Key recurring pains:
keeping the browser/session alive, "works while minimized," and RustDesk dropping when
the SSH terminal closed.

**The pivot:**
The founder wanted to generalize this into a real open-source **platform** — a
Tampermonkey-style tool where anyone drops in a **recipe/script** for their own use
case (P2P.me being the FIRST recipe, not the product). Goal: reliable, trusted,
background-capable web automation that non-coders can use, cross-platform (Windows +
Linux first).

**Research done (multi-pass, fact-checked):**
- Confirmed browser extensions CANNOT produce trusted input (`isTrusted` unforgeable).
- Confirmed OS pixel clickers (xdotool/RobotGo) are trusted but need a visible/virtual
  display and break minimized.
- **Discovered CDP `Input.dispatchMouseEvent` produces trusted input AND works
  backgrounded without a virtual display** — the key enabling insight.
- Verified the nuance that high-level `page.click()` breaks in background (Intersection
  Observer) but RAW CDP dispatch does not.
- Surveyed the market: the specific combination (local, non-coder, trusted,
  background, recipe-shareable, any-site) is unoccupied. See RESEARCH.md / INNOVATION.md.

**Proofs run (on real Windows hardware):**
- PoC #1 (`poc/poc_test_windows.py`): trusted click landed while minimized on a local
  page. `isTrusted: True`, ~16ms. GREEN.
- PoC #2 (`poc/poc_test_p2p.py`): trusted click worked on the REAL logged-in lp.p2p.me
  site while minimized, via persistent profile. Founder: "works flawlessly." GREEN.
- (Note: an early attempt failed because Python 3.14 was corrupted — `VCRUNTIME140.dll
  / python314.dll` Bad Image 0xc000012f. Fixed by installing Python 3.12. Lesson:
  pin Python 3.12 for now; 3.14 lacks some prebuilt wheels and caused a broken install.)

**Decisions made:** ADR-001 through ADR-006 (see DECISIONS.md).

**State at end of session:** Foundation proven. Full docs scaffold written (this repo).
Ready to build Phase 1 (the engine + first recipe).

**NEXT SESSION SHOULD:**
1. Read CLAUDE.md → PROVEN_FACTS.md → ARCHITECTURE.md → ROADMAP.md → this log.
2. Scaffold the Python project structure for the core engine (Phase 1, ROADMAP).
3. Implement the browser manager (launch w/ anti-throttle flags + persistent profile).
4. Implement the raw-CDP input module (click; then drag/swipe; then key).
5. Implement the targeting module (find by text/selector → box → center; main frame +
   iframes).
6. Implement the recipe loader/runner + a global hotkey toggle.
7. **Capture the real P2P.me DOM** for the Close (and Accept) buttons from the live
   site — the founder gets ~1 order/hour, so grab the button HTML when an order
   appears and paste it in; store the recipe in `recipes/p2p-me/`. Until then, the
   runner can be tested against any always-present dashboard element.
8. Set up the GitHub repo (init, license MIT, push scaffold).
9. Update this log at the end.

**IMPORTANT REMINDERS FOR NEXT SESSION:**
- Use RAW `Input.dispatchMouseEvent`, never high-level element.click(), for background
  reliability (ADR-002).
- Keep P2P.me OUT of the engine core (ADR-006). It's a recipe.
- Pin Python 3.12 (not 3.14).
- Don't contradict PROVEN_FACTS without a new green proof.

---

<!-- Add new sessions below this line -->

## SESSION 1 — Phase 1: the engine + first recipe scaffolding (2026-07-16)

**Goal:** Build Phase 1 per ROADMAP — the use-case-agnostic engine + CLI, prove it
end-to-end, keep P2P.me as a recipe. Repo was git-init'd and pushed first.

**Built (all committed + pushed to github.com/ChinmayaThakral/truklick):**
- Packaging: `pyproject.toml` (console script `truklick`, requires-python
  `>=3.12,<3.13` per ADR-005), `requirements.txt`.
- Engine (`src/truklick/`, use-case-agnostic, ADR-006):
  - `browser.py` — persistent Chromium + the five anti-throttle flags + CDP
    session + keep-alive watchdog (ADR-003, FACT 2).
  - `cdp_input.py` — raw `Input.dispatchMouseEvent` click / drag-swipe / type /
    keys. Never high-level `element.click()` (ADR-002).
  - `targeting.py` — multi-strategy (selector/role/text) across main frame +
    iframes → bounding-box center; no hardcoded pixels (FACT 4).
  - `motion.py` — optional easing+jitter motion profile, off by default (the
    anti-bot "too perfect" refinement from PROVEN_FACTS caveat).
  - `recipe.py` — recipe format v1 loader/validator (ADR-007); strips
    `_comment`/`_note`.
  - `runner.py` — executes wait_for/click/swipe/type/wait/loop/condition; loop
    mode, pause/resume, single-shot exit, restart-survive.
  - `hotkey.py` — global start/stop toggle (default Escape); degrades to Ctrl+C.
  - `cli.py` / `__main__.py` — `truklick run <recipe.json>` with
    --url/--headless/--once/--wait/--no-hotkey/--human-motion/--profile-dir.
- Validation assets: `examples/selftest.html` + `recipes/demo/selftest.json`
  (offline end-to-end proof, no login/network).
- Tests (12, all green): recipe/motion/targeting unit tests + an **end-to-end
  test that asserts the engine fires a genuinely trusted click (isTrusted ===
  true)** through the real modules — the PoC #1 property, now via the engine.

**What worked:**
- `pytest`: 12/12 green on Python 3.12.13.
- CLI single-shot run against the self-test page: launch (anti-throttle flags) →
  navigate → wait_for (found by text) → raw CDP click at computed center → clean
  exit 0.
- Loop mode + watchdog: first iteration clicked; when the browser was killed the
  watchdog auto-relaunched + re-attached (ARCHITECTURE §6, as intended).
- Graceful shutdown: Ctrl+C/SIGINT during a 30s `wait_for` now exits in ~0.19s.

**What failed / was fixed mid-session:**
- BUG (fixed): `--once`/non-loop recipes ran their pass then looped back to wait
  forever instead of exiting. Fixed: single-shot now breaks and exits cleanly.
- BUG (fixed): `wait_for` blocked for its full timeout ignoring pause/shutdown, so
  a hotkey/Ctrl+C mid-wait was unresponsive (bad for the toggle exit criterion).
  Fixed: `wait_for` takes a `should_continue` check and `wait` is chunked;
  regression test added.
- ENV: dev mac only had Python 3.14; `brew install python@3.12` stalled on the
  Homebrew API. Provisioned 3.12.13 via `uv` in ~16s instead (ADR-008). The 3.12
  pin was honored, NOT relaxed to 3.14.

**Decisions made:** ADR-007 (recipe format v1), ADR-008 (uv-provisioned 3.12 for dev).

**Honest limitation:** "works while minimized" (FACT 2) is a headful/real-hardware
property already proven on Windows in the PoCs; the mac validation here was
headless (no window to minimize) and proves the trusted-click + targeting + run-loop
path end-to-end. The real-site minimized run is the founder's Windows validation.

**NEXT SESSION SHOULD:**
1. **Capture the real lp.p2p.me DOM** for the Close (and Accept) controls from a
   live order (founder gets ~1/hour): right-click → Inspect → paste the button
   HTML/text. Update `recipes/p2p-me/recipe.json` placeholders with real
   text/selectors. Confirm whether Accept is a click or a slide (swipe) — the
   recipe note says a drag may no longer be needed; VERIFY against live DOM.
2. Run `truklick run recipes/p2p-me/recipe.json` headful on the real site with a
   persistent profile; log in once; test the **Close** button (non-committing)
   first, minimized, before anything else. Do NOT wire an unattended
   payment-committing loop — the founder drives accept-step validation.
3. Once real-site Close works minimized end-to-end via a recipe → Phase 1 exit
   criteria met. Then start Phase 2 (visual element picker + GUI).
4. Consider: retry/backoff polish, a non-mutating loop target for a clean loop
   smoke, and packaging the profile-dir default per-recipe.

**REMINDERS (unchanged):** raw CDP only (ADR-002); P2P.me stays a recipe (ADR-006);
pin 3.12 (ADR-005/008); never contradict PROVEN_FACTS without a new green proof.
