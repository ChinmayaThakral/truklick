# Truklick

**Trusted, background-capable browser automation for everyone — not just coders.**

Truklick is an open-source, cross-platform desktop tool that runs small,
shareable **recipes** to automate any website. Unlike browser-extension auto-clickers,
its clicks are **real, OS-trusted input** (they pass `isTrusted` checks that reject
extension clicks). Unlike screen-pixel macro tools, it keeps working **while the
window is minimized** — with **no virtual display required**.

Think **"Tampermonkey, but the clicks are real and it works in the background,
and you don't have to be a programmer."**

> ⚠️ Early-stage project, built in the open. Yes, it's being built with the help of
> Claude — that's not hidden; see `/docs`. The foundation is validated with real,
> reproducible proofs (see `docs/PROVEN_FACTS.md` and `/poc`).

---

## Why this exists

The author needed to reliably automate a couple of buttons on a web dashboard, in the
background, 24/7. Every tool fell short: **browser extensions can't send trusted
input**, and **OS macro tools (xdotool/RobotGo) need a visible screen and break when
minimized.** After hand-building an elaborate virtual-display VPS contraption to make
it work, the author found a cleaner way — **trusted input over the Chrome DevTools
Protocol (CDP), which works minimized without any virtual display** — and built the
tool they wished existed. (Full story: `docs/RESEARCH.md`, `docs/INNOVATION.md`.)

## How it works (the core idea)

| Approach | Trusted click? | Works minimized? | Needs a visible/virtual display? |
|---|---|---|---|
| Browser extension JS | ❌ | — | no |
| OS pixel click (xdotool/RobotGo) | ✅ | ❌ | **yes** |
| **Truklick (CDP `Input.dispatchMouseEvent`)** | ✅ | ✅ | **no** |

This is proven, not claimed — see `/poc` for the two proof scripts and
`docs/PROVEN_FACTS.md` for results.

## Status

- ✅ **Phase 0 — Foundation:** trusted + background + real-site + DOM-targeting proven.
- 🚧 **Phase 1 — Engine + first recipe:** in progress (Windows + Linux).
- ⏳ Phase 2 — visual picker + GUI for non-coders.
- ⏳ Phase 3 — distribution + recipe gallery.

See `docs/ROADMAP.md`.

## Recipes

A recipe is a small, human-readable file describing steps (find element → trusted
click → wait → loop, etc.). Recipes are **user content** — the platform is neutral
infrastructure, like AutoHotkey or Tampermonkey. The first example recipe automates a
merchant dashboard; it lives in `recipes/` to demonstrate that the platform generalizes.

## Repo layout

```
CLAUDE.md            # master context + guardrails (read first, esp. for Claude Code)
README.md
LICENSE              # MIT
docs/
  PROVEN_FACTS.md    # experimentally verified truths (anti-hallucination anchor)
  ARCHITECTURE.md    # the technical design
  RESEARCH.md        # market + technical research
  INNOVATION.md      # positioning / what's different
  DECISIONS.md       # architecture decision records (ADRs)
  ROADMAP.md         # phased build plan
  SCOPE.md           # what it is / isn't
  SESSION_LOG.md     # running session log (continuity / anti-drift)
poc/
  poc_test_windows.py  # PROOF: trusted CDP click while minimized (local page)
  poc_test_p2p.py      # PROOF: same, on the real logged-in site
recipes/
  p2p-me/            # first example recipe (user content)
```

## Quick start (dev, Phase 1)

Requires **Python 3.12** (not 3.14 — see SESSION_LOG for why).

```bash
python -m pip install playwright
python -m playwright install chromium
# run a PoC to see the foundation for yourself:
python poc/poc_test_windows.py
```

## License

MIT — see `LICENSE`. Use responsibly; recipes you write are your responsibility.
