# DECISIONS.md — Decision Log (Architecture Decision Records)

> Append-only. Every significant technical decision gets a dated entry with the
> context, the decision, and the evidence. The first entries are the PoC proofs the
> whole project rests on. Never silently reverse a decision — add a new entry that
> supersedes it, with reasoning.

---

## ADR-001 — Use CDP trusted input as the core clicking mechanism
- **Date:** 2026-06-27
- **Context:** Need trusted input (extensions can't) that works in the background
  (pixel clickers can't without a virtual display).
- **Decision:** Use CDP `Input.dispatchMouseEvent` (raw, coordinate-based) as the core
  input mechanism.
- **Evidence:** PoC #1 (`poc/poc_test_windows.py`) — trusted click landed while
  minimized on a local page (`isTrusted: True`, ~16ms). See PROVEN_FACTS FACT 1 & 2.
- **Status:** ADOPTED.

## ADR-002 — Use RAW CDP dispatch, never high-level element.click(), for background
- **Date:** 2026-06-27
- **Context:** High-level `page.click()` scrolls-into-view via IntersectionObserver,
  which doesn't fire in background tabs → breaks minimized.
- **Decision:** Always use raw `Input.dispatchMouseEvent` at computed coordinates.
- **Evidence:** Puppeteer issues #5201/#3339/#3318; confirmed by our PoCs working with
  raw dispatch. See PROVEN_FACTS FACT 2 nuance.
- **Status:** ADOPTED.

## ADR-003 — Launch Chromium with anti-throttle flags + persistent profile
- **Date:** 2026-06-27
- **Decision:** Always launch with the five anti-throttle flags (see PROVEN_FACTS
  FACT 2) and a persistent user-data-dir (keeps logins between runs).
- **Evidence:** PoC #2 (`poc/poc_test_p2p.py`) — persistent profile kept login;
  trusted click worked minimized on the real site.
- **Status:** ADOPTED.

## ADR-004 — Validate on the real target before building the platform
- **Date:** 2026-06-27
- **Context:** Local success doesn't guarantee real-site success (iframes, dynamic DOM).
- **Decision:** Prove trusted-CDP-while-minimized on the real logged-in target
  (lp.p2p.me) before writing the platform scaffold.
- **Evidence:** PoC #2 — user confirmed "works flawlessly." See PROVEN_FACTS FACT 3.
- **Status:** DONE. Foundation validated.

## ADR-005 — Python + Playwright(CDP) for Phase 1
- **Date:** 2026-06-27
- **Context:** Need fastest path to a running, debuggable tool; PoCs are Python.
- **Decision:** Build Phase 1 in Python using Playwright for browser lifecycle +
  `CDPSession` for raw input. Defer Go/Rust + Tauri/Wails GUI to Phase 2 (distribution).
- **Rationale:** Ship a working slice fast; don't prematurely optimize for distribution
  before the engine is proven end-to-end. Revisit for single-binary packaging later.
- **Status:** ADOPTED (revisit at Phase 2).

## ADR-006 — Platform is neutral; recipes are user content
- **Date:** 2026-06-27
- **Context:** The product is the automation *platform*, not any single use case.
- **Decision:** Keep the core engine use-case-agnostic. Ship P2P.me only as an example
  recipe under `recipes/p2p-me/`, cleanly separated from the engine. The platform's
  stance mirrors AutoHotkey/Tampermonkey/Playwright: neutral tool, user-authored
  scripts, user responsibility.
- **Status:** ADOPTED.

## ADR-007 — Recipe format v1 (finalized in Phase 1)
- **Date:** 2026-07-16
- **Context:** ROADMAP Phase 1 calls for finalizing recipe format v1. The draft in
  ARCHITECTURE §4 needed concrete rules for navigation, comments, and the step set.
- **Decision:** Recipes are JSON with: `name`, `match_url` (glob guard),
  optional `url` (navigate on start), `hotkey`, `loop`, `loop_delay_ms`, and
  `steps[]`. Step actions: `wait_for`, `click`, `swipe`, `type`, `wait`, `loop`,
  `condition`. Targets are dicts with any of `selector` / `role`+`name` / `text`
  (+`exact`) / `fallback_selector`, tried most-specific first, across main frame +
  iframes. Any key beginning with `_` (e.g. `_comment`, `_note`) is documentation
  and is stripped at load, so authors can annotate freely.
- **Rationale:** Keeps recipes human-readable, git-friendly, and use-case-agnostic
  (ADR-006). The `url` field was added because `match_url` is a glob and can't be
  navigated to directly; `match_url` stays as the run guard.
- **Status:** ADOPTED (v1). Extend (not break) in later phases.

## ADR-008 — Dev toolchain provisions Python 3.12 via `uv`
- **Date:** 2026-07-16
- **Context:** The dev mac only had Python 3.14 (Homebrew), and `brew install
  python@3.12` stalled on Homebrew's API index. ADR-005 pins 3.12.
- **Decision:** Use `uv` to provision CPython 3.12 and manage the venv
  (`uv python install 3.12`, `uv venv --python 3.12`). This honors the 3.12 pin
  without depending on a system/Homebrew 3.12. pyproject still pins
  `>=3.12,<3.13`; `uv` is a convenience, not a hard requirement (plain
  `python3.12 -m venv` works too).
- **Status:** ADOPTED (dev environment only).

## ADR-009 — Attach to a running browser (`--attach`) as a first-class mode
- **Date:** 2026-07-19
- **Context:** The CLI always launched its own browser, so it could not drive a
  session the user was already logged into — fatal for validating against a real
  site where login and a live popup already exist.
- **Decision:** `--attach CDP_URL` connects over CDP to an existing browser. In this
  mode we NEVER navigate (a goto would reload the page and destroy the popup we are
  waiting for), never close the user's browser on exit, and disable the restart
  watchdog (a "restart" would launch a new browser, defeating the point).
- **Evidence:** Used for every live lp.p2p.me run (FACT 6).
- **Status:** ADOPTED.

## ADR-010 — Local web control panel instead of Tauri/Wails
- **Date:** 2026-07-19
- **Context:** ARCHITECTURE originally planned a Tauri (Rust) or Wails (Go) desktop
  shell for the non-coder GUI.
- **Decision:** Ship a local control panel served by Python's stdlib `http.server`
  and opened in the user's browser. Recipes run as a SUBPROCESS so a crashing run
  cannot take down the panel and Stop is a real kill.
- **Rationale:** Zero new dependencies, identical on all three OSes, survives being
  frozen into a single binary, and avoids a second language/toolchain. A native
  shell buys polish we do not need yet. Supersedes the GUI half of ADR-005.
- **Status:** ADOPTED (revisit only if the panel becomes limiting).

## ADR-011 — Distribute as PyInstaller single-file binaries, not a Go/Rust rewrite
- **Date:** 2026-07-19
- **Context:** ADR-005 deferred distribution and floated rewriting the core in Go or
  Rust for a single downloadable binary.
- **Decision:** Keep the Python core; build one self-contained executable per OS with
  PyInstaller in GitHub Actions and publish to Releases. Chromium is NOT bundled —
  it is downloaded on first run (~150MB), keeping the binary ~50-70MB and avoiding
  redistribution questions.
- **Evidence:** v0.1.0/v0.1.1 built and smoke-tested on all three OSes in CI; the
  published macOS asset was downloaded and run end to end.
- **Consequence:** No rewrite needed. macOS/Windows binaries are unsigned for now.
- **Status:** ADOPTED. Supersedes the "consider Go/Rust core" part of ADR-005.

## ADR-012 — Record by demonstration is the primary recipe-authoring path
- **Date:** 2026-07-19
- **Context:** Non-coders will not hand-write JSON. The roadmap assumed a visual
  element picker would be the answer.
- **Decision:** Ship a recorder first: the user performs the task once and we emit a
  recipe. Crucially each click becomes `wait_for` + `click` — declarative, not a
  replayed macro — and targets are chosen text/role-first, with framework-generated
  ids (React/Radix `«r3»`) refused outright.
- **Evidence:** Tested against live lp.p2p.me; it independently produced the exact
  `role=button name="Close" exact` target we had reverse-engineered by hand.
- **Status:** ADOPTED. The visual picker remains open as a complement, not a
  prerequisite.

## ADR-013 — Assert only OBSERVED outcomes (`expect`)
- **Date:** 2026-07-19
- **Context:** Automation tools report that they clicked, not whether the task
  worked. The live P2P runs made this concrete: clicks fired and nobody could say
  whether the order was accepted.
- **Decision:** Add an `expect` step asserting an outcome (element present/absent),
  and report a success rate on exit. The recorder emits `expect` ONLY when it
  actually observed the element vanish after the click — never by assumption.
- **Rationale:** An auto-added assumption failed on every navigation click during
  live testing. An assertion that is not grounded in an observation is worse than no
  assertion, because it trains users to ignore failures.
- **Status:** ADOPTED.

---

## TEMPLATE FOR NEW ADRs
```
## ADR-NNN — <short title>
- Date:
- Context:
- Decision:
- Evidence / Rationale:
- Status: PROPOSED | ADOPTED | SUPERSEDED-BY-ADR-XXX
```
