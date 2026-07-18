# Truklick

**Real clicks. Any website. Even minimized.**

Truklick is an open-source automation platform for the browser. It fires **genuinely
trusted input** (`isTrusted === true`) at any Chromium-rendered page — the kind of
click a browser extension physically cannot produce — and it keeps working while the
window is **minimized or in the background**, with no virtual display.

You automate things by loading a **recipe**: a small, shareable file that says
"wait for this, click that." Recipes are plain text, git-friendly, and easy to pass
around. **You don't have to be a programmer.**

> Think *"Tampermonkey, but the clicks are real, it works in the background, and
> anyone can use it."*

---

## Why it exists

Three ways to click something on a web page, and until now you had to pick your poison:

| Approach | Real/trusted click? | Works minimized? | Needs a visible screen? | Usable by a non-coder? |
|---|---|---|---|---|
| Browser extension JS | ❌ never | — | no | yes |
| OS pixel clicker (xdotool, RobotGo, AutoHotkey) | ✅ | ❌ | **yes** | no |
| **Truklick** (CDP `Input.dispatchMouseEvent`) | ✅ | ✅ | **no** | **that's the point** |

Extensions can't produce trusted input — it's an unforgeable browser security
guarantee, so any site that checks gets to reject them. Pixel clickers *are* trusted
but click *screen coordinates*, so they need a live screen and break the moment
anything moves. Truklick drives the browser directly over the Chrome DevTools
Protocol: trusted like a real mouse, but aimed at **the element**, not a pixel — so it
survives layout changes and keeps running in the background.

This isn't a claim. It's measured — see [`docs/PROVEN_FACTS.md`](docs/PROVEN_FACTS.md)
and the reproducible proofs in [`poc/`](poc/).

## What you can build with it

Anything that is "watch a page, and when *X* appears, do *Y*" — dashboards that need
babysitting, queues, repetitive click-throughs, internal tools with no API. The engine
is completely **use-case agnostic**: it only knows how to find elements and click,
type, and drag them. What you automate is your recipe, and your business.

The repo ships example recipes (including one that operates a merchant payments
dashboard) to prove the platform generalises — **they're demonstrations, not the
product.**

## Install

**Just want it working?** Download a single file from
[**Releases**](https://github.com/ChinmayaThakral/truklick/releases) — Windows, macOS
and Linux. No Python, no terminal. Run it and a control panel opens in your browser.

**From source** (needs Python 3.12):

```bash
git clone https://github.com/ChinmayaThakral/truklick.git && cd truklick
python3.12 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e . && playwright install chromium
truklick            # opens the control panel
```

## Use it

```bash
truklick                                  # control panel (no terminal needed after this)
truklick run recipes/demo/selftest.json   # prove trusted clicking works, offline
truklick run <recipe.json>                # run any recipe
```

Start with **`recipes/demo/selftest.json`** — it's self-contained (no website, no
login) and turns a button green when Truklick lands a real trusted click on it. If
that works, your install works.

## Make a recipe without writing one

**Demonstrate it once:**

```bash
truklick record my-task.json --url https://example.com
```

A browser opens; you do the task by hand; press `Ctrl+C`. You get a runnable recipe.

It isn't a macro recorder. Because Truklick watches the page, every click you make
becomes a **`wait_for` + `click` pair** — so the recipe waits for things to appear
instead of replaying blind timings. Targets are captured by visible text and ARIA
role, and framework-generated ids (React/Radix `«r3»`-style) are refused outright
because they change on every render.

Then **tune it** in the control panel: press **Tune** to adjust every delay, timeout
and poll interval per step, or delete steps. Edits are validated before saving, so a
bad edit can never overwrite a working recipe.

## Know whether it actually worked

Every automation tool tells you it clicked. Truklick tells you whether the **outcome
happened**:

```json
{ "action": "expect", "target": { "role": "button", "name": "Accept" },
  "present": false, "name": "order went through" }
```

On exit you get a real success rate — `outcomes verified: 47/50 succeeded (94%)` —
instead of guessing from a log of clicks. Recorded recipes get an `expect` step
automatically.

## Staying current

```bash
truklick update          # is there a newer release?
```

It also tells you quietly at startup, and the control panel shows a banner. It
**checks** — it never silently replaces itself. Downloads are unsigned, and a tool
that drives your logged-in sessions should not auto-execute code fetched in the
background (see ADR-014). You decide when to download.

## Writing a recipe

A recipe is JSON. Targets are found by **visible text, ARIA role, or CSS selector** —
never by pixel coordinates — so they survive redesigns and any screen size.

```json
{
  "name": "Dismiss the popup when it appears",
  "match_url": "https://example.com/*",
  "url": "https://example.com",
  "hotkey": "Escape",
  "loop": true,
  "steps": [
    { "action": "wait_for", "target": { "text": "Close", "exact": true }, "timeout_ms": 60000 },
    { "action": "click",    "target": { "text": "Close", "exact": true } }
  ]
}
```

Actions: `wait_for`, `click`, `swipe`, `type`, `wait`, `loop`, `condition`.
Full format in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) §4 and ADR-007.

Press the recipe's **hotkey** (default `Escape`) to pause/resume — a badge in the page
shows whether it's running.

## How it works

```
 control panel / CLI
        │
   recipe runner ──── targeting (text / role / selector → element → live coordinates)
        │
   raw CDP Input.dispatchMouseEvent        ← trusted, background-capable
        │
   Chromium (anti-throttle flags, persistent profile)
```

Details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
Decisions and their evidence: [`docs/DECISIONS.md`](docs/DECISIONS.md).

## Status

- ✅ **Engine** — trusted clicking, resilient targeting, recipes, hotkey, control panel
- ✅ **Proven** — trusted input, background/minimized operation, and a full
  recipe driving a real production site end to end (`PROVEN_FACTS` 1–6)
- ✅ **Distribution** — one-file downloads for Windows, macOS and Linux, built in CI
- 🚧 **Now** — visual element picker, code signing / notarization
- ⏳ **Next** — recipe gallery, richer editor

See [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Honest about the limits

- **Chromium-family only.** CDP is required; Firefox/Safari can't do this.
- **Sophisticated bot-detection can still spot automation** by *motion physics*, even
  though the clicks are genuinely trusted. There's an optional human-like motion
  profile; for ordinary buttons it's unnecessary.
- **macOS needs Accessibility permission** for the global hotkey, and downloads are
  currently unsigned.
- Built in the open with heavy AI assistance — that's not hidden, and every
  load-bearing claim in `PROVEN_FACTS.md` has a runnable proof behind it.

## Contributing

Keep the engine use-case-agnostic — site-specific logic belongs in a recipe, never in
the core. Don't contradict `docs/PROVEN_FACTS.md` without a new, runnable proof.
`CLAUDE.md` and `docs/SESSION_LOG.md` carry the full context and history.

## License

MIT. What you automate, and whether you're permitted to, is your responsibility —
the same as any general-purpose automation tool.
