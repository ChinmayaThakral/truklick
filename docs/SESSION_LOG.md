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

**Addendum (2026-07-16):** Added `docs/FEATURE_SCANNER.md` — a Phase-2 spec for an
objective DOM "Capture Mode" (CDP-injected, captures every visible element with the
full strategy set + frame path; no noise filtering). Spec only, NOT implemented. It
carries reviewer corrections (iframe reach is wider than in-page-JS assumes; iframe
bbox must use main-frame coords via `bounding_box()`, else clicks lie; recurse open
shadow roots; reuse targeting vocabulary; PoC-first). Gitignored `captures/`.
**Phase 1's real-site *minimized* run on Windows is still the open gate — do that (and
capture how the lp.p2p.me popup renders: main frame / iframe / shadow) BEFORE building
the scanner, so it's designed against reality.** No ADR yet — the CDP-vs-extension
decision (ADR-009) gets recorded when the feature is actually built.

---

## SESSION 2 — Capture tooling + corrected P2P flow + Phase-1 prep (2026-07-16)

**Context:** Prep work doable from the Mac while away from the Windows box / a live
order. No engine changes; tooling, docs, and the real recipe skeleton.

**Corrected P2P flow (from the author):** order popup shows **Close** (+ a "Slide to
Accept" that we do NOT use); you click **Close**; the order then maps to the **home
screen** as a clean **Accept button** (no slider). So the two targets live on TWO
screens/moments — one static snapshot can't catch both.

**Built / added (committed + pushed):**
- `scripts/capture_helper.py` — press-ENTER DOM capture (main frame + iframes), prints a
  labelled list with `frame=` per element, saves full strategy set to `captures/`.
  Smoke-tested across a nested iframe (Accept in main, Close in iframe, both with
  selector+xpath). In-frame rects recorded but NOT trusted for clicking (recipes
  re-find by selector/text). `captures/` gitignored.
- `docs/CAPTURE_GUIDE.md` — non-coder playbook: two-press capture flow, **practice-first**
  on any modal site, the **Mac minimized self-test** command, what to send back.
- `recipes/demo/minimized_selftest.json` — closes the last Phase-1 box on real Mac
  hardware (minimize within 10s → restore → button turns green "TRUSTED" if the click
  landed minimized). macOS minimized behavior is UNPROVEN (only Windows is, FACT 2), so
  this is a genuine test, not a formality.
- `poc/poc_test_mac.py` — macOS minimized trusted-click PoC (minimizes via CDP
  `Browser.setWindowBounds`, no human/permission needed).
- `recipes/p2p-me/recipe.json` — finalized to the CONFIRMED logic: **only** Close +
  Accept, ultrafast (no inter-click waits; wait_for still guards each click), loop
  100ms. Old "Slide to Accept" draft removed. `_workflow` documents the author's
  toggle loop (see decision below).

**PROVEN this session — FACT 5: trusted click works minimized on macOS too.**
Ran `poc/poc_test_mac.py`: window state `minimized` (via CDP), click received,
`isTrusted: True`, ~54ms. Recorded as PROVEN_FACTS FACT 5. This closes the last
Phase-1 box reachable without a live order (the engine/OS minimized property on a 2nd
OS). The real lp.p2p.me minimized run on Windows is still the product-level gate.

**Author's confirmed workflow (locked):** phone rings 3x/order (assigned / accepted /
action-needed). Script auto-Closes + auto-Accepts fast, non-stop. On the 3rd ring the
author TOGGLES OFF (hotkey), handles that one order on the phone (~6-7 min: verify a buy
where money arrived, or send for a sell), then TOGGLES BACK ON. The toggle-pause is what
prevents accepting more orders than can be worked one at a time. Script does ONLY
Close+Accept; all payment/verify is manual on the phone.

**Decision (author):** **AUTO-ACCEPT** mode — recipe auto-clicks the home Accept, fully
hands-off (Close+Accept only). Chosen deliberately knowing it removes the prior
phone-verify-before-accept step. Revert to close-only = delete the final "click Accept"
step (documented in the recipe's `_mode`).

**Not done / open (needs the author + real hardware):**
1. On the next live order: run `scripts/capture_helper.py`, capture **Close** (popup) then
   **Accept** (home), send the two JSONs. Then fill the recipe placeholders with real
   selectors + frame paths.
3. Real-site minimized run of the filled recipe on Windows = Phase 1 exit criteria met.
4. Author to answer the `_open_questions_for_the_author` in the recipe (post-Accept
   behavior, animation delay, whether Close appears without an order).

**No PROVEN_FACTS changed. Reminders unchanged (raw CDP, P2P stays a recipe, pin 3.12).**

---

## SESSION 3 — Live DOM captured; real recipe written (2026-07-19)

**Done on the Mac** (macOS turned out to be fully viable — the "Windows box" framing in
earlier sessions was inherited assumption, not a technical requirement; FACT 5 covers
minimized on macOS).

**New tooling:** `scripts/open_dashboard.py` (persistent Chromium with CDP on :9222,
stays alive) + `scripts/capture_now.py` (attaches over CDP and captures the current
screen with zero interaction). This meant captures could be taken the instant an order
popup appeared, with no terminal juggling.

**CAPTURED FROM THE LIVE SITE (order 625945, a SELL order):**
- **Close** — in a Radix dialog. `<div>` (400x48 @ 440,640) wrapping a `<p>Close</p>`.
  With the popup open, exactly 2 elements contain "Close" and both are that control.
- **Accept** — on the HOME screen after Close, a REAL `<button>` (311x36 @ 726,819).
  Exactly 1 element contains "Accept" on the home screen. Confirmed absent on a clean
  home screen (76 elements) and present after closing an order — i.e. it only exists
  while an order is pending.

**KEY STRUCTURAL FINDINGS (these drove the targeting decisions):**
1. **No iframes anywhere** — every element is `frame=main`. (Also answers the open
   question the Phase-2 scanner spec was designed around.)
2. **React + Tailwind, no ids.** Every button has `id=''`; classes are utility classes;
   CSS paths are deep `nth-of-type` chains.
3. **The popup is a Radix dialog with a per-render generated id** (`div#radix-«rj»`).
   EVERY captured CSS selector inside the popup is anchored to it and WILL break on the
   next popup. → CSS fallbacks were deliberately OMITTED from the recipe: a stale
   selector matching the wrong control on a financial dashboard is worse than none.
4. **Text/role is the most stable strategy on this site** — the inverse of the usual
   advice (and of the guidance in docs/FEATURE_SCANNER.md's reviewer notes, which is
   correct in general but not here). Captured evidence beat the assumption.
5. **Ambiguity trap:** while the popup is open, the substring "Accept" also appears in
   "Slide to Accept" and "Accept to view UPI ID" (both non-buttons). Loose text
   targeting could hit the slider. → Accept uses `role=button` + exact name.

**Engine change:** `targeting.py` now honours an `exact` flag for role/name matching
(Playwright matches accessible name as a case-insensitive substring by default).

**Recipe:** `recipes/p2p-me/recipe.json` filled with the real targets —
wait_for Close(exact) → click Close → wait_for Accept(role=button, exact) → click
Accept → loop. Rationale documented inline so nobody "improves" it back to CSS.

**Tests:** 15 green, incl. new `tests/test_targeting_disambiguation.py` using a fixture
that reproduces the real popup/home structure and asserts Accept resolves to the real
`<button>` and NOT the slider.

**HONEST GAP — the recipe is NOT yet verified end to end:**
- The Accept target was verified against the captured DOM and a fixture, but **never
  against the live Accept button** — it disappeared (order handled) before a live
  resolve could be run. Live-resolve of both targets currently returns "not present"
  simply because no order is pending.
- No trusted click has yet been fired by the ENGINE at the real site. The Close click
  in this session was done by the human, by hand.

**NEXT SESSION (on the next live order):**
1. While the popup is open, run a live `targeting.find` for both targets and confirm
   they resolve (read-only, no clicks).
2. Then let the ENGINE fire the trusted click at **Close only** (non-committing) —
   deferred this session deliberately rather than experimenting on a live order under
   time pressure. Confirm it works, including MINIMIZED.
3. Only after that, run the full recipe (Close + Accept) end to end = Phase 1 exit.
4. Grant macOS Accessibility permission first, or the Escape toggle is dead (the engine
   now warns honestly instead of claiming "armed").

---

## SESSION 4 — First real end-to-end run on the live site (2026-07-19)

**MILESTONE: FACT 6.** The engine ran `recipes/p2p-me/recipe.json` unattended against
the live logged-in lp.p2p.me session (via `--attach`) and performed the full sequence:
detect popup → trusted click **Close** → wait for home **Accept** → trusted click
**Accept**. Author confirmed visually. This is the platform doing the real job from a
recipe, not a PoC script.

**How the earlier mis-click was diagnosed and fixed:**
- First live run (--once): Close landed, Accept did not. Evidence: `role` found 0
  matches (the real home button did not exist yet) and the Accept target ALSO carried
  a loose `text` fallback, which matched something in the still-dismissing popup and
  clicked it. The "safety" fallback caused the bug.
- Fix: Accept target requires `role=button` + exact name, **no text fallback** — so
  wait_for keeps polling for a genuine button instead of clicking a wrong element.
  Confirmed live: `clicking {'role':'button','name':'Accept'} via role`.

**A hypothesis I got WRONG (recorded so nobody repeats it):** I first assumed the
mis-click was a stale-coordinate race (box read while the dialog animated). A direct
old-vs-new comparison disproved it — the old code clicks correctly on both a smooth
animation and a hard reflow. The test docstring was corrected rather than left
implying a repro it does not have. The occlusion guard that came out of that work IS
a proven improvement (old `find()` returned a point that clicked an overlay;
`find_click_point()` refuses).

**RELIABILITY — 1 of 2 cycles FAILED. This is the top open issue:**
- Cycle 1 (00:30:49): Close clicked → Accept never appeared in 15s → order dismissed
  and left UNACCEPTED.
- Cycle 2 (00:33:37): Close → Accept 1s later, both correct. ✅
- Root cause of cycle 1 unknown. Mitigations: Accept timeout 15s → 40s; runner now
  logs `PASS ABORTED AFTER N CLICK(S)` when a pass dies after clicking, so a
  half-done order is never silent.

**Engine/tooling added this session:** `--attach CDP_URL` (drive an already-open
logged-in browser; never navigates, never closes the user's browser, watchdog
disabled), `scripts/open_dashboard.py`, `scripts/capture_now.py`,
`scripts/probe_targets.py` (read-only diagnosis), `targeting.find_click_point()`.

**PHASE 1 EXIT CRITERIA — still NOT fully met:**
- [x] Run a recipe against the real site end to end
- [ ] **MINIMIZED on the real site** — never tested (FACT 2/5 cover the engine/OS
      property only)
- [ ] **Hotkey toggle** — dead on this Mac; macOS Accessibility permission never
      granted, so the author has no manual brake and the operator (assistant) is the
      only stop button

**NEXT SESSION SHOULD:**
1. Grant macOS Accessibility permission → verify `Hotkey 'Escape' armed` → test
   pause/resume mid-loop. Without this the toggle workflow does not exist.
2. Run the recipe minimized on the real site → that is the last Phase-1 checkbox.
3. Investigate cycle-1 failure: when an order is closed but Accept never appears,
   determine whether the order is lost, and consider not clicking Close until Accept
   is confidently reachable.
4. Gather reliability data across more orders before trusting it unattended.

---

## SESSION 5 — v1: recorder, verification, GUI, packaging (2026-07-19)

**Reframing (author's correction, and it was right):** the repo had drifted into
reading like a P2P.me clicker. Truklick is a general trusted-automation platform;
P2P.me is ONE example recipe. README rewritten platform-first; the P2P guide moved to
`recipes/p2p-me/README.md` and explicitly labelled an example.

**P2P "failures" explained — not a bug.** The author clarified that P2P.me offers each
order to 3-4 merchants, first to accept wins. So cycles where Close fired but Accept
never appeared are lost races, not defects. This retires the open question from
Session 4. The new `expect` step now distinguishes the two cases explicitly.

**Shipped:**
- **`expect` step + outcome stats.** Verifies an OUTCOME (element present/absent)
  rather than just "we clicked". Runner reports `outcomes verified: N/M (X%)` on exit.
  Added to the P2P recipe (Accept button must be GONE = we won the order).
- **Recorder** (`truklick record`). Demonstrate a task once -> runnable recipe. Each
  click becomes `wait_for` + `click` (declarative, not a blind macro). Targets use
  text/ARIA role; framework-generated ids (React/Radix `«r3»`) are refused because
  they change per render — the lesson learned live in Session 3. VERIFIED: recorded a
  task whose 2nd button only appears 300ms later, replayed it, task completed,
  outcomes 1/1.
- **Control panel GUI** (`truklick` with no args). Recipe picker, Start/Stop, live
  log, status dot, and a **Tune** editor for per-step delay/timeout/poll (G Hub style).
  Saves are validated by `load_recipe()` and written via a temp file, so an invalid
  edit cannot corrupt a working recipe (verified).
- **On-page RUNNING/PAUSED badge** on hotkey toggle (`pointer-events:none` so it can
  never occlude a target — tested with the badge directly over a button).
- **Packaging**: PyInstaller spec + GitHub Actions release workflow -> one file per OS.
  First-run bootstrap downloads Chromium so users never hear "Playwright".
- **Speed**: single-round-trip in-page resolver (find + 2-frame stability + hit test in
  one evaluate). Measured **146.5ms -> 33.4ms per click resolve (4x)**. The remaining
  ~33ms is two display frames — the floor for proving an element isn't mid-animation.

**Bugs found and fixed (all would have shipped broken):**
- Frozen builds resolved browsers inside their own throwaway temp bundle and could
  never find Chromium -> pin `PLAYWRIGHT_BROWSERS_PATH` to the user cache.
- `chromium_present()` called `sync_playwright()` from inside the asyncio loop, where
  it always raises; the swallowed error made a *working* install print "could not
  download the browser".
- `--once` recipes hung instead of exiting (Session 1); `wait_for` ignored
  pause/shutdown (Session 1); hotkey claimed "armed" on macOS without Accessibility
  permission (Session 4).

**Hypotheses I got WRONG this project (recorded so nobody repeats them):**
1. Accept mis-click was a stale-coordinate race — DISPROVEN by direct old-vs-new
   comparison; the real cause was a loose `text` fallback matching inside the popup.
2. The ~50% Accept failure was our timing — DISPROVEN; the mechanics were byte-identical
   between a success and a failure. It was multi-merchant competition.

**Phase 1 exit criteria: MET.** Recipe runs against the real site ✅, hotkey toggle
pause/resume ✅ (verified live), trusted+minimized proven on Windows and macOS
(FACTS 2/5) ✅. The only untested variant is minimized *on the live site specifically*.

**NEXT:**
1. Verify the Windows and Linux binaries from CI — only macOS has been built and run.
2. Test the recorder against a real messy site (only synthetic pages so far).
3. Visual element picker (CDP-injected, per FEATURE_SCANNER.md — not an extension).
4. Recipe gallery once recipes are easy to make.

**Recorder tested against the LIVE lp.p2p.me site (post-v0.1.0).** Recorded 5 real
clicks. What held: no Radix/generated ids leaked, no nth-of-type paths, and the Close
button was captured as `role=button name="Close" exact` — *identical to the target we
reverse-engineered by hand in Session 3*. Three real defects found and fixed:
1. **Auto-`expect` was wrong.** It asserted the last-clicked element disappears — true
   for a dismiss, false for a nav click, so recorded recipes failed every run. Now the
   recorder OBSERVES (900ms after each click) whether the element actually vanished and
   only emits `expect` when it did.
2. **Silent fragile fallback.** An icon button with no text/aria-label fell back to a
   raw Tailwind CSS path with no warning. Now flagged per-step (`_FRAGILE`) and at the
   top of the recipe (`_WARNING_fragile_targets`).
3. **Blind `wait` sleeps** from recorded pauses — removed; `wait_for` already waits on
   the real condition. Observed gaps kept as `_recorded_gap_ms` metadata for tuning.
Locked in by `tests/test_recorder.py` (25 tests green).

**Doc-sync audit (end of Session 5).** Checked the repo against the project's own
rules. Found and fixed:
- **ROADMAP contradicted PROVEN_FACTS.** It marked "end-to-end debug on the real site
  until it works minimized" as DONE. We never ran minimized on the live site — the
  live runs were all with the window visible. Split into "end-to-end on the real site"
  (done, FACT 6) and "MINIMIZED on the real site" (still open). Do not tick the second
  until someone actually minimizes during a real order.
- **ARCHITECTURE was pre-v1**: no `expect`, no recorder, GUI still described as
  Tauri/Wails, platform section said Windows+Linux-first. Updated to describe the tool
  that actually exists.
- **Five undocumented decisions** — added ADR-009 (attach mode), ADR-010 (web control
  panel over Tauri/Wails), ADR-011 (PyInstaller over a Go/Rust rewrite), ADR-012
  (record-by-demonstration as the primary authoring path), ADR-013 (assert only
  observed outcomes).
- **CLAUDE.md / SCOPE.md** claimed Windows-first with macOS deferred; in reality macOS
  was the primary dev and validation platform and all three OSes ship.
- **FEATURE_SCANNER.md** marked NOT IMPLEMENTED / partly superseded by the recorder,
  with the live findings folded in (no iframes on lp.p2p.me; Radix per-render ids make
  CSS paths worthless there).
All internal doc links resolve. 25 tests green.

---

## SESSION 6 — Phase 1 closed: FACT 7, minimized on the live site (2026-07-19)

**PHASE 1 EXIT CRITERIA NOW FULLY MET.** Ran the recipe attached to the live logged-in
session with a window-state watcher recording evidence.

**FACT 7 proven:** window verified in the macOS Dock at 02:12:17 (`AXMinimized=true`),
order popup appeared, engine detected it and fired a trusted click at 02:12:34 — no
restore in between. Trusted input, at a real element, on a live production site, with
the window backgrounded.

**The measurement lesson (this is the reusable part):** `document.visibilityState`,
`document.hidden` and CDP `Browser.getWindowBounds` ALL report the page as
visible/maximized while the window sits in the Dock. That is not a bug — it is
precisely what `--disable-backgrounding-occluded-windows` /
`--disable-renderer-backgrounding` do, and it is *why* the clicks keep landing. We
spent several attempts trusting instruments our own architecture is designed to
defeat, and told the author three times (wrongly) that his window wasn't minimized.
The authoritative signal is the OS: `osascript … AXMinimized of window 1`. Also
learned: CDP `Browser.setWindowBounds` silently no-ops once a window is `maximized`.

**Three near-misses on this single checkbox, worth remembering:**
1. The ROADMAP had it ticked before it was ever done (caught in the doc audit).
2. It was measured with detectors that cannot see it (caught by AXMinimized).
3. A cycle was nearly credited where the window had been restored 2s before the
   clicks (caught by comparing timestamps rather than eyeballing the log).
Each was caught by checking rather than assuming. That discipline is the only reason
FACT 7 is trustworthy.

**Live tally for the session:** 4 orders seen — **2 won** (both verified by
`EXPECT OK — order accepted`), **2 lost to competition** (Accept never appeared;
`PASS ABORTED AFTER 1 CLICK(S)` fired correctly both times). Orders go to 3-4
merchants, first to accept wins, so ~50% losses are market behaviour, not defects —
and the `expect` step is what makes that distinction visible instead of a mystery.

**State:** v0.1.1 released (binaries for all 3 OSes). 25 tests green. FACTS 1-7,
ADRs 1-13. Phase 1 complete; Phase 2 largely delivered (recorder, control panel,
tuning editor). Remaining: visual element picker, recipe gallery, code signing,
recorder tested on more than one real site.

**Speed pass (end of Session 6): appear->click 73.9ms -> ~24ms (3.1x), no reliability
traded away.** Two changes, both measured:
1. `wait_for` was running the FULL click-safety check (stability + hit test) on every
   poll. Detection does not need those — only the click does. Added a `detectOnly`
   mode for polling. 73.9 -> 40.8ms.
2. Click-path stability reduced from two animation frames to one. 40.8 -> 23.8ms.
   Validated rather than assumed: a slow 0.8px/frame drift (near the 0.5px threshold)
   is still correctly REFUSED, so the guarantee held is "never click a stale or
   occluded position" — the resolver waits instead of guessing. Locked in by
   `test_slow_drift_is_refused_not_misclicked`.
The remaining ~24ms is one display frame plus CDP round-trips; below that we would be
clicking positions we have not confirmed are still valid.
Two self-inflicted detours worth noting: the first slow-drift test resolved before the
CSS animation had started moving (so the element genuinely WAS stationary — invalid
test), and the second failed on a `NameError` I misread as a logic failure for two
rounds. Read the actual error before theorising.

**End-of-session live results (2026-07-19, ~02:00-02:35).** Ran the recipe against the
live site with the window minimized in the Dock the whole time (2 restores, both by
the author checking on it — timestamps excluded from the FACT 7 evidence window).

- **7 order popups detected, all while minimized.** FACT 7 is proven several times
  over, not once.
- **1 order won and verified** (`EXPECT OK — order accepted`), **5 lost** to other
  merchants (`PASS ABORTED AFTER 1 CLICK(S)` each time, firing correctly).
- Orders arrived in bursts (~3 in 4 minutes at one point), not the ~1/hour baseline.

**Honest read of the 1-in-6 win rate:** too small a sample to conclude anything, and
two explanations remain open — normal variance in a 3-4 merchant race, or our
Close->Accept latency genuinely losing races. The speed pass (73.9ms -> 23.8ms) landed
near the end and the loop only ran on the fast code for ~1 minute, so it has NOT been
evaluated. Next session: run on the fast code across a meaningful number of orders and
compare the win rate. `expect` makes that measurable rather than a guess.

**Shutdown:** loop stopped, window watcher stopped, dashboard browser closed (CDP
:9222 freed), `captures/` deleted (contained balance, bank names, account fragment and
order IDs in plaintext), build artifacts and temp files removed. Browser profiles kept
(they hold logins). Repo clean and pushed.

**Sub-10ms pass.** Asked whether we could get under 10ms. Two changes, both measured:
1. **Animation-aware stability.** The frame wait was a heuristic — sample twice and
   guess whether the element is moving. The browser can just be asked:
   `document.getAnimations()` reports what is actually running on the element or an
   ancestor. If nothing is animating, no frame wait is needed at all. Conservative on
   error (if we cannot tell, we wait). 23.8ms -> 11.7ms median, min 5.5ms, and it is
   *more* correct than sampling, not less — a CSS animation is still detected and the
   slow-drift case still refuses.
2. **Poll interval.** Measured the real tradeoff on this machine:

   | poll_ms | appear->click | probes/sec | CPU |
   |---|---|---|---|
   | 10 | 15.0 ms | 74 | 9.7% |
   | 5  | 10.9 ms | 128 | 15.0% |
   | 2  | 6.2 ms | 254 | 23.9% |
   | 0  | 3.0 ms | 1314 | 49.7% |

   Set the P2P recipe to `poll_ms=2` (~6ms, sub-10ms as asked).

**Important context, recorded so nobody optimises this further by reflex:** local
latency is now far below the network round-trip to the site. Going 15ms -> 3ms costs
5x the CPU for a gain that is almost certainly invisible against server RTT. **The
bottleneck has moved off this machine.** If order win-rate is the goal, the next
useful measurement is win-rate at poll=2 vs poll=10 over many orders — not more
micro-optimisation.

**Update checking added (ADR-014).** `truklick update`, a quiet startup line, and a
banner in the control panel. Deliberately NOT a silent self-updater — see ADR-014: a
background self-replacing unsigned binary turns a release-channel compromise into RCE
on every user's machine, and we have nothing to verify a download against.

**Two real bugs this work surfaced:**
1. **Version drift.** v0.1.3 shipped while the code still reported `0.1.0`, so the
   update checker told everyone on the LATEST build that an update was available —
   permanently. Fixed, and `test_code_version_matches_packaging` now fails the build
   if `__version__` and pyproject ever disagree again.
2. **rAF is not a clock in headless.** The animation-aware stability change used
   `requestAnimationFrame` to sample twice; in headless Chromium rAF resolves
   near-instantly, so both samples land at the same moment and a genuinely moving
   element passed as stable. The slow-drift safety test caught it. Now, when
   `getAnimations()` reports motion, we sample across **real elapsed time** (20ms)
   instead — a delay paid only when the browser says something is actually moving,
   so the fast path is unaffected.
45 tests green.

**v0.1.4 shipped with a broken update checker — caught by testing the published
binary, not the source.** From a downloaded build every HTTPS call failed with
`CERTIFICATE_VERIFY_FAILED`: PyInstaller bundles do not carry the system trust store.
It worked perfectly from source, so source-only testing would never have found it.
Fixed by bundling `certifi` and building an SSL context from it. Also fixed the error
message, which blamed "offline?" for what was actually a certificate failure —
misdiagnosing the cause in the one message the user would ever see.
Lesson, repeated for the third time tonight: **test the artifact you ship, not the
code you wrote.** The same discipline caught the frozen-Chromium-path bug earlier.
