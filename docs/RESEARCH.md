# RESEARCH.md — Market & Technical Research

> Consolidated research that justifies the project. Fact-checked across multiple
> passes. Sources listed at the end. This exists so future sessions don't re-derive
> the landscape from scratch or hallucinate competitors.

---

## 1. THE PROBLEM (lived, not theoretical)

The founder needed reliable, trusted automation of a web app (a merchant dashboard,
P2P.me) that:
- requires **trusted input** (browser-extension clicks are rejected),
- must run **24/7 in the background** (even minimized),
- must be **reliable** and survive restarts.

No existing tool made this easy. The founder ended up hand-building an elaborate stack
on an Ubuntu VPS: a virtual display (Xvfb), a window manager (Openbox), a VNC server,
self-hosted RustDesk for phone access, and an `xdotool` bash script clicking screen
coordinates — plus systemd services and a watchdog to keep it alive. It worked, but it
took many hours of trial-and-error and is not something a non-coder could reproduce.

**Insight:** the pain existed because that approach clicks **screen pixels**, which is
the ONLY method that needs a visible/virtual display and exact coordinates. There is a
better way (CDP — see below) that the founder didn't know existed. The tool we're
building packages that better way for everyone.

## 2. THE TRUSTED-INPUT LANDSCAPE (technical)

Three ways to click a web element, and their properties:

1. **Extension / page JavaScript** (`element.click()`, dispatched events):
   `isTrusted = false`, unforgeable. Rejected by trusted-input-gated sites.
   Confirmed unforgeable by Chromium dev group + Mozilla (bug 637248).
2. **OS-level pixel input** (xdotool, RobotGo, nut.js, PyAutoGUI): `isTrusted = true`,
   but clicks **screen coordinates**, so it needs a visible or virtual display and
   **breaks when minimized** (RobotGo issue #125, unresolved for years).
3. **CDP `Input.dispatchMouseEvent`**: `isTrusted = true` AND targets the page
   directly over a WebSocket, so it works **backgrounded/minimized/headless with no
   virtual display.** This is the sweet spot. Confirmed by: cypress-real-events (exists
   precisely to fire real system-level events via CDP), Puppeteer's native click path,
   and our own PoCs.

**Key nuance we verified:** high-level `page.click()` breaks in background because it
scrolls-into-view first via IntersectionObserver (which doesn't fire in background
tabs). RAW `Input.dispatchMouseEvent` at coordinates does not have this problem. So the
engine must use raw CDP dispatch, not high-level element clicks. (Puppeteer issues
#5201, #3339, #3318.)

**Background throttling** is a separate, solvable concern: launch flags
`--disable-background-timer-throttling`, `--disable-backgrounding-occluded-windows`,
`--disable-renderer-backgrounding`, `--disable-features=CalculateNativeWinOcclusion`
keep a backgrounded window fully alive. (Chrome-launcher docs; testcafe/karma issues.)

## 3. THE COMPETITIVE LANDSCAPE (market)

Researched across several passes. The space is dense but splits into layers that are
each occupied by *different* players — and the founder's specific combination is not
served by any of them.

- **Native input libraries** (RobotGo, nut.js, PyAutoGUI): trusted-ish but pixel-based,
  break minimized, are developer libraries not non-coder tools.
- **Macro/scripting tools** (AutoHotkey, AutoIt, Hammerspoon, xdotool, **Espanso**):
  require writing scripts in a language; not visual; not trusted-web-element aware.
  Espanso is the closest *distribution/community* model (cross-platform, community-
  shared config recipes) — but for text expansion, not clicking. **Study Espanso's
  community/recipe-gallery mechanics.**
- **Element-aware web automation** (Skyvern, Browser-Use, Taiko, Loopi, OpenChrome):
  DOM-aware, self-healing selectors (so "survive page changes" is table stakes, NOT our
  innovation) — but built for **developers or AI agents**, often cloud/LLM-driven, and
  most click via CDP/JS in ways aimed at automation engineers, not laypeople doing
  simple recurring personal tasks.
- **Browser extension auto-clickers** (dozens on Chrome Web Store): easy UX but
  `isTrusted=false` — cannot do the trusted-input use cases at all.
- **Workflow/automation platforms** (n8n, ActivePieces, Windmill, Zapier-likes):
  API/integration orchestration and business workflows — a different category
  entirely; not local trusted browser input.
- **Test-automation frameworks** (Playwright, Cypress, Selenium, Robot Framework):
  for QA engineers writing tests, not non-coders automating live sites for personal use.

**The unoccupied gap:** a **local, cross-platform desktop platform for non-coders**
that runs **shareable recipes** which fire **trusted, background-capable input** at
**any website**. "Tampermonkey for trusted native clicks, usable by anyone." Nobody
packages exactly this.

## 4. HONEST CAVEATS (so we don't fool ourselves)

- **Not unprecedented in the universe** — CDP trusted input is known to developers.
  The novelty is **packaging it for non-coders as a recipe platform**, the same way
  Espanso didn't invent text expansion but made it pleasant and shareable. That framing
  is achievable and defensible; "never done before by anyone" is the wrong bar.
- **The niche has a shadow side:** trusted-input demand overlaps with things sites try
  to prevent. The platform must be neutral infrastructure (recipes are user content),
  like every general automation tool. This protects the project and lets it grow a
  community.
- **Behavioral anti-bot detection** can flag CDP via motion physics even though
  `isTrusted` is true. Mitigate with human-like motion. Not a blocker for simple
  dashboard buttons.
- **Chromium-only.** CDP requires it.

## 5. WHY THE FOUNDER'S EXPERIENCE IS THE REAL ASSET

The strongest thing here isn't a novel algorithm — it's the lived pain: "I needed
reliable trusted background automation, every existing tool either couldn't do trusted
input or required a CS degree, so I hand-built an absurd VPS stack over many hours.
Then I found a clean way (CDP) and built the tool I wish I'd had." That narrative is
what earns community trust and contributors.

---

## SOURCES (key)
- Trusted CDP input: cypress-real-events (github.com/joshwooding/cypress-real-events);
  Puppeteer CDP native-click behavior; MDN `Event.isTrusted`.
- `isTrusted` unforgeable: Chromium dev group thread; MDN; Mozilla bug 637248.
- Background click breakage via IntersectionObserver: Puppeteer issues #5201, #3339, #3318.
- Anti-throttle flags: GoogleChrome/chrome-launcher chrome-flags docs; testcafe #217;
  karma-chrome-launcher #280.
- Pixel-clicker minimized limitation: go-vgo/robotgo #125.
- Element-aware layer: Skyvern, Browser-Use, Taiko, Loopi, OpenChrome.
- Distribution/community model: Espanso.
- Broader automation market (for positioning): n8n, ActivePieces, Windmill, Robot
  Framework, Playwright, Cypress, Selenium (2026 landscape roundups).
- 2026 anti-bot behavioral detection: headless-browser-detection writeups.
