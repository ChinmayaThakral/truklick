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
