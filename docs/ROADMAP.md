# ROADMAP.md — Phased Build Plan

> Respect the phase order. Don't build Phase 3 things before Phase 1 works on the real
> target. Each phase ends with a working, demonstrable result.

---

## PHASE 0 — FOUNDATION ✅ DONE
- [x] Prove trusted CDP input works (PoC #1).
- [x] Prove it works minimized (PoC #1).
- [x] Prove it works on the real target site logged in (PoC #2).
- [x] Prove DOM-based resilient targeting.
- [x] Write foundation docs (this repo).

## PHASE 1 — THE ENGINE + FIRST RECIPE (current milestone)
Goal: a runnable tool that executes a recipe against the real site, reliably,
minimized, on **Windows and Linux**.

- [ ] **Core engine (Python + Playwright/CDP):**
  - [ ] Browser manager: launch/attach Chromium with anti-throttle flags +
        persistent profile (ADR-003).
  - [ ] CDP input module: raw `Input.dispatchMouseEvent` click + drag/swipe +
        key dispatch (ADR-001/002).
  - [ ] Targeting module: find element by visible text / selector (multi-strategy
        fallback) → bounding box → center coords (FACT 4). Search main frame + iframes.
  - [ ] Recipe loader + runner: parse JSON recipe → execute steps (wait_for, click,
        swipe, type, wait, loop, condition).
  - [ ] Global hotkey toggle (start/stop), configurable (e.g. Escape).
  - [ ] Keep-alive supervisor (auto-restart browser/session on crash).
- [ ] **Recipe format v1** finalized (see ARCHITECTURE §4). JSON, human-readable.
- [ ] **First recipe:** `recipes/p2p-me/` — authored from the live DOM once captured
      (see SESSION_LOG for captured button labels/HTML). Kept SEPARATE from engine.
- [ ] **End-to-end debug** on the real site until it works minimized.
- [ ] CLI to run a recipe: `python -m <tool> run recipes/p2p-me/recipe.json`

Exit criteria: run a recipe, minimize the window, watch it work on the real site,
toggle with hotkey.

## PHASE 2 — USABILITY FOR NON-CODERS
Goal: someone who can't code can create and run a recipe.

- [ ] **Visual element picker:** click "pick", hover-highlight elements, capture a
      resilient multi-strategy selector on click. (Companion extension OR injected
      content script for scanning/highlighting — but the trusted click stays in the
      engine via CDP.)
- [ ] **GUI shell:** Tauri (Rust+web) or Wails (Go+web). Recipe list, editor,
      run/stop toggle, live status/log. No code visible unless the user wants it.
- [ ] **Recipe builder UX:** pick targets → set order & delays → save → run.
- [ ] **Human-like motion profiles** (easing + jitter) to reduce "too perfect" CDP
      signature (see PROVEN_FACTS caveat).

## PHASE 3 — DISTRIBUTION & COMMUNITY
- [ ] Decide/execute distribution packaging: consider Go(chromedp)/Rust core for a
      single downloadable binary (revisit ADR-005). Bundle/auto-download Chromium.
- [ ] Windows + Linux installers; macOS support (permissions, notarization, signing).
- [ ] **Recipe gallery** (Espanso-style): shareable recipe files + a simple index.
- [ ] Docs site, contribution guide, examples beyond P2P.me to prove generality.
- [ ] Launch narrative (see INNOVATION.md).

## PHASE 4 — REFINEMENT
- [ ] Conditional logic, screenshots-on-event, notifications (Telegram/Discord hooks).
- [ ] Optional AI-assisted recipe creation (explicitly deferred; not Phase 1–3).
- [ ] Robustness: anti-bot motion tuning, retry/error handling, logging.

---

## GUARDRAILS FOR EVERY PHASE
- Keep the engine use-case-agnostic (ADR-006). P2P.me stays a recipe.
- Don't contradict PROVEN_FACTS without a new proof.
- Update SESSION_LOG at the end of each session.
