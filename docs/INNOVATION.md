# INNOVATION.md — What Makes This Different

> The positioning and innovation thesis. Keep the project aimed at THIS.

---

## THE ONE-LINER

**"Tampermonkey for trusted, background-capable automation — usable by anyone,
not just coders."**

## THE THESIS

Every existing tool sits in exactly one of these boxes, and none covers the whole
thing:

- Browser extensions: easy for anyone, but **cannot produce trusted input** and can't
  run true background reliably.
- OS macro tools (AutoHotkey/xdotool/RobotGo): trusted input, but **coding required**,
  **pixel-based**, and **break when minimized** (need a visible/virtual display).
- Dev/AI web-automation frameworks (Playwright, Skyvern, Browser-Use): powerful and
  DOM-aware, but built **for developers or AI agents**, often cloud/LLM, not for a
  layperson automating a site for a personal recurring task.
- Workflow platforms (n8n, Zapier, ActivePieces): **API/integration orchestration**,
  not local trusted input on arbitrary websites.

**The gap:** a **local, cross-platform, open-source desktop platform** where a
**non-coder** loads a **shareable recipe** that fires **trusted, DOM-targeted,
background-capable input** at **any website**, reliably, and toggles it with a hotkey.

We fill that gap. The enabling technical insight — trusted CDP input that works
minimized without a virtual display — is PROVEN (see `PROVEN_FACTS.md`).

## WHAT IS *NOT* THE INNOVATION (be honest)

- Self-healing/resilient selectors — already table stakes in the dev tools.
- CDP trusted input itself — known to developers.
- Auto-clicking — a saturated extension category.

## WHAT *IS* THE INNOVATION

1. **The packaging:** trusted + background + DOM-targeted + **non-coder-friendly** +
   **recipe-shareable**, in one local open-source tool. That exact combination is
   unoccupied.
2. **Reliability posture:** "works minimized, survives restarts, hotkey toggle" as a
   first-class promise, borrowed from the founder's hard-won production experience.
3. **The recipe ecosystem:** an Espanso-style community library of shareable
   automations, where P2P.me is simply the first published recipe — proving the
   platform generalizes.
4. **The origin story:** built by someone who felt the exact pain and validated every
   load-bearing assumption with real proofs before writing the tool. That credibility
   is a differentiator in an AI-slop-saturated open-source landscape.

## POSITIONING GUARDRAIL

The **platform** is the product. **Recipes are user content.** Do not let any single
use case (including P2P.me) redefine the project as a single-purpose tool. The P2P.me
recipe is the *first demo that proves generality*, nothing more. Keep the core engine
use-case-agnostic.

## TARGET USER (priority order)

1. **Non-coders** who need simple, reliable web automation and can't/won't script.
2. Power users / server operators who want a cleaner, trusted, background-capable
   engine than xdotool/RobotGo.
3. The founder + friends/family with specific recurring tasks (recipes).

## THE NARRATIVE FOR LAUNCH

> "Every automation tool I tried either couldn't send a real click (extensions) or
> needed me to be a programmer and keep a screen alive (xdotool/RobotGo). I spent
> hours hand-building a virtual-display VPS contraption just to click two buttons
> reliably in the background. Then I learned the browser can do trusted input directly
> over CDP — no virtual display, works minimized — and I built the tool I wish I'd
> had. It runs little shareable recipes. Here's mine; make your own."
