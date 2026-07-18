# CLAUDE.md — Master Context & Guardrails (READ THIS FIRST, EVERY SESSION)

> **You are working on this project via Claude Code. Before doing anything,
> read this file completely, then read `docs/PROVEN_FACTS.md`,
> `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, and the latest entries in
> `docs/SESSION_LOG.md`. Do not propose or write code that contradicts
> `docs/PROVEN_FACTS.md` without re-proving the fact first.**

---

## 0. THE ONE-PARAGRAPH SUMMARY

We are building an **open-source, cross-platform desktop automation platform**
that lets *anyone* — especially non-coders — run **reliable, trusted, background-capable
automation on any website**, by loading small shareable **recipes** (scripts).
Think **"Tampermonkey, but the clicks are real OS-trusted input, it keeps working
when the window is minimized, and you don't need to be a programmer."** The first
recipe that ships on the platform automates a merchant dashboard (P2P.me) — but the
**product is the platform, not the recipe.** Recipes are user content.

---

## 1. NON-NEGOTIABLE GROUND RULES FOR EVERY SESSION

1. **Never contradict `docs/PROVEN_FACTS.md`.** Those are experimentally verified
   truths. If you think one is wrong, you must design and run a new proof (like the
   PoCs in `/poc`) and get a green result BEFORE changing direction. Write the new
   result into `docs/PROVEN_FACTS.md` and `docs/DECISIONS.md`.
2. **Foundation over speed.** The human running this project explicitly values a
   correct foundation over fast output. When unsure, verify with a tiny test
   rather than assuming. The PoC-first discipline (prove, then build) is how this
   project got here — keep it.
3. **Log every session.** At the END of every working session, append a dated entry
   to `docs/SESSION_LOG.md`: what was attempted, what worked, what failed, what the
   next session should pick up. This is how we never lose context or drift.
4. **The platform is neutral; recipes are user content.** The tool is general-purpose
   automation infrastructure (like AutoHotkey, Tampermonkey, Playwright). What a user
   automates is their responsibility, exactly as with any automation tool. Do NOT
   bake any single use case (including P2P.me) into the core engine — it ships as an
   *example recipe*, cleanly separated.
5. **Cross-platform, all three shipping.** As of v0.1.x we build single-file binaries
   for Windows, macOS and Linux in CI. Note the early docs assumed Windows-first —
   in practice the engine was built and live-validated on **macOS** (FACT 5/6). Don't
   hardcode OS assumptions. Outstanding OS-specific gaps: macOS needs Accessibility
   permission for the global hotkey, and no build is code-signed/notarized yet.
6. **Keep it honest and inspectable.** This is an open-source community project. Clean
   code, clear docs, MIT license. The human is openly using Claude to build it and is
   fine with that being visible in the repo.
7. **Don't over-engineer before validation.** Ship a working thin slice, prove it on
   the real target, then expand. Match the PoC discipline.

---

## 2. WHAT WE HAVE ALREADY PROVEN (see PROVEN_FACTS.md for detail)

- ✅ **Trusted input is achievable without a browser extension** via the Chrome
  DevTools Protocol command `Input.dispatchMouseEvent` (`isTrusted = true`).
- ✅ **It works while the window is minimized / occluded / unfocused**, when Chromium
  is launched with anti-throttle flags. Proven on real Windows hardware.
- ✅ **It works on the real target site** (a logged-in live web app with real DOM),
  not just clean local pages. Proven.
- ✅ **DOM-based targeting** (find element → get bounding box → click its center via
  CDP) works and is resilient to layout changes — no hardcoded pixel coordinates.

These four facts are the entire technical foundation. They are why this project is
viable where browser-extension auto-clickers are not.

## 3. THE CORE INSIGHT (why this is different)

Browser extensions **cannot** produce trusted input (`isTrusted` is unforgeable from
extension JS — security guarantee, confirmed by Chromium/Mozilla). OS-level pixel
clickers (xdotool/RobotGo) CAN, but they require a visible/virtual display and break
when minimized. **CDP `Input.dispatchMouseEvent` is the sweet spot: trusted like a
real mouse, but targets the page directly so it works backgrounded/headless and needs
no virtual display.** Packaging this for non-coders, as a recipe platform, is the
unoccupied gap this project fills. (See `docs/RESEARCH.md` and `docs/INNOVATION.md`.)

## 4. WHERE THE PROJECT ACTUALLY IS (updated 2026-07-19, v0.1.1)

Phase 1 is **done** and Phase 2 is largely delivered. Shipped: the engine (trusted
CDP input, resilient targeting, recipes, hotkey), a local **control panel GUI**, a
**recorder** (demonstrate a task once → recipe, ADR-012), **`expect`** outcome
verification (ADR-013), `--attach` (ADR-009), and one-file downloads for all three
OSes (ADR-011). 25 tests green. FACTS 1-6 proven.

**Still open:** minimized run on the *live* site specifically; a visual element
picker; recipe gallery; code signing. See ROADMAP.

The original milestone text is kept below for historical context.

## 4b. ORIGINAL FIRST SHORT-TERM GOAL (historical)

Build the **infrastructure tool (the platform)** + the **first recipe (P2P.me)**, get
it running reliably on **Windows and Linux**, and debug it against the real target
until it works end-to-end. Concretely:

1. Core engine: launch/attach Chromium with anti-throttle flags, connect via CDP.
2. Recipe format: a simple file describing steps (find element by text/selector →
   trusted click → wait → loop → hotkey toggle).
3. Recipe runner + global hotkey toggle (start/stop), like the user's existing
   Escape/End toggle on their Linux server.
4. The P2P.me recipe as the first example recipe (author-provided; see SESSION_LOG
   for the exact button labels/DOM once captured from the live site).
5. Prove it works, minimized, on the real site.

THEN expand toward: visual element picker, GUI, recipe gallery, companion extension
for scanning/targeting if needed, cross-platform packaging. See `docs/ROADMAP.md`.

## 5. HOW TO WORK IN THIS REPO

- Start by reading the docs listed at the top of this file.
- Pick the next task from `docs/ROADMAP.md` (respect the phase order).
- Before building on any assumption about browser behavior, check `PROVEN_FACTS.md`.
  If it's not proven there, write a tiny PoC in `/poc`, run it (or ask the human to
  run it), and record the result before proceeding.
- Keep the P2P.me specifics OUT of the core; they live in `recipes/p2p-me/`.
- End every session by updating `docs/SESSION_LOG.md`.

## 6. TONE / COLLABORATION

The human is technical enough to run scripts and debug for hours, but wants the
platform itself to be usable by non-coders. They want honesty over agreement — if a
plan is flawed, say so and propose better. They corrected an earlier drift where the
assistant over-focused on one use case's risk instead of the platform vision; stay on
the platform vision. Recipes are user content; the platform is the product.
