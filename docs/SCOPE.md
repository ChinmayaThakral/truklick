# SCOPE.md — What This Platform Is and Isn't

> Keeps the project aimed at the platform vision. Recipes are user content.

---

## WHAT IT IS
- A **general-purpose, local, open-source automation platform** for the browser.
- It runs **user-authored recipes** that fire **trusted, DOM-targeted input** at any
  Chromium-rendered website, reliably, including while minimized/backgrounded.
- Aimed first at **non-coders**, with power-user and server use supported.
- Neutral infrastructure, in the same family as **AutoHotkey, Tampermonkey, Espanso,
  Playwright** — a tool that runs scripts the user chooses.

## WHAT IT IS NOT
- **Not** a single-purpose P2P.me bot. P2P.me is the *first example recipe* that proves
  the platform generalizes; it lives in `recipes/p2p-me/`, not in the engine.
- **Not** a browser extension for the clicking itself (extensions can't do trusted
  input). A companion extension may later assist *element scanning* only.
- **Not** a cloud/SaaS product. It's a local tool; recipes are shareable files.
- **Not** an AI agent (for now). AI-assisted recipe creation is explicitly deferred to
  a later phase; the core is deterministic recipes.
- **Not** Firefox/Safari-capable for trusted input (CDP is Chromium-only).

## THE RECIPE MODEL (like every automation tool)
The platform executes recipes. **What a user automates, and whether they have the right
to automate it, is the user's responsibility** — the same neutral stance every
general automation tool takes (AutoHotkey scripts, Tampermonkey userscripts, Playwright
scripts, n8n workflows). The project ships an example recipe (P2P.me) to demonstrate
capability; it does not endorse or restrict what recipes users write. Contributors
should keep the engine use-case-agnostic and avoid baking any specific site's logic
into the core.

## DESIGN BOUNDARIES (to stay focused)
- Core engine: use-case-agnostic; knows only "run these steps against this page."
- Recipes: all site-specific logic lives here, as data/config, not engine code.
- Targeting: resilient (text/role/selector), never fixed pixels in the engine.
- Reliability: background-capable, restart-surviving, hotkey-toggle — first-class.
- Cross-platform: Windows, macOS and Linux all ship as single-file binaries (v0.1.x).
  Chromium-family only. (Early docs said 'Windows+Linux first, macOS later' — in
  practice macOS was the primary development and validation platform.)
