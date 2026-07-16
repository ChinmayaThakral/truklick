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
