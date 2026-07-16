# ARCHITECTURE.md

> The technical design of the platform. Grounded entirely in `PROVEN_FACTS.md`.

---

## 1. WHAT THE PLATFORM IS

A local desktop application that:
1. Launches (or attaches to) a Chromium-family browser with anti-throttle flags.
2. Connects to it over the **Chrome DevTools Protocol (CDP)**.
3. Loads user-authored **recipes** (small scripts describing automation steps).
4. Executes recipes using **trusted CDP input** that works while the browser is
   **minimized/backgrounded**.
5. Provides a **hotkey toggle** (start/stop) and, later, a **GUI** and **visual
   element picker** so non-coders never touch code.

The platform is the product. Recipes (including the P2P.me one) are user content.

## 2. WHY THIS ARCHITECTURE (the decision)

| Approach | Trusted? | Works minimized? | Needs virtual display? | Non-coder friendly? |
|---|---|---|---|---|
| Browser extension JS click | ❌ | n/a | no | yes |
| OS pixel click (xdotool/RobotGo) | ✅ | ❌ | **yes** | no (libraries) |
| **CDP `Input.dispatchMouseEvent`** | ✅ | ✅ | **no** | (we make it so) |

CDP is the only path that is both **trusted** and **background-capable without a
virtual display**. This is the project's core technical bet, and it is PROVEN
(Facts 1–3). See `docs/INNOVATION.md` for the market gap this creates.

## 3. COMPONENT MAP

```
┌───────────────────────────────────────────────────────────────┐
│                        DESKTOP APP (GUI)                        │
│   - recipe list / editor / run-stop toggle / status            │
│   - visual element picker (later phase)                        │
│   - Tauri (Rust+web) or Wails (Go+web) shell  [phase 2+]       │
└───────────────┬───────────────────────────────────────────────┘
                │ calls
┌───────────────▼───────────────────────────────────────────────┐
│                        CORE ENGINE                              │
│   - browser manager: launch/attach Chromium w/ anti-throttle    │
│     flags; keep-alive supervisor (watchdog pattern)             │
│   - CDP client: raw Input.dispatchMouseEvent / dispatchKeyEvent │
│   - targeting: find element (text/selector) → bounding box →    │
│     center coords  (resilient, no fixed pixels)                 │
│   - motion: human-like move profiles (easing+jitter) [refine]   │
│   - recipe runner: parse recipe → execute steps → loop → toggle │
│   - hotkey listener: global start/stop (e.g. Esc/End)           │
└───────────────┬───────────────────────────────────────────────┘
                │ speaks CDP over WebSocket
┌───────────────▼───────────────────────────────────────────────┐
│              CHROMIUM (headful-minimized or headless)           │
│   launched with:                                                │
│     --disable-background-timer-throttling                       │
│     --disable-backgrounding-occluded-windows                    │
│     --disable-renderer-backgrounding                            │
│     --disable-ipc-flooding-protection                           │
│     --disable-features=CalculateNativeWinOcclusion              │
│   persistent profile dir (keeps logins between runs)            │
└───────────────────────────────────────────────────────────────┘
```

Optional **companion browser extension** (later phase): only if we need richer
in-page element scanning/highlighting for the visual picker. The extension does
NOT do the clicking (it can't produce trusted input) — it only helps *identify*
elements; the trusted click is always done by the core engine via CDP.

## 4. THE RECIPE FORMAT (draft — refine in Phase 1)

A recipe is a human-readable file (JSON or YAML; JSON to start). Example shape:

```json
{
  "name": "P2P.me accept & close",
  "match_url": "https://lp.p2p.me/*",
  "hotkey": "Escape",
  "loop": true,
  "steps": [
    { "action": "wait_for", "target": { "text": "Close" }, "timeout_ms": 30000 },
    { "action": "click",    "target": { "text": "Close" } },
    { "action": "wait",     "ms": 100 },
    { "action": "click",    "target": { "text": "Slide to Accept" } }
  ]
}
```

Design principles:
- **Targets are resilient** (by visible text, ARIA role, stable selector — NOT fixed
  pixels). Multiple fallback strategies per target.
- **Steps are explicit** (wait_for, click, swipe/drag, type, wait, loop, condition).
- **Human-readable & git-friendly** so recipes can be shared like Espanso configs.
- **No use-case baked into the engine.** The engine just runs steps.

> NOTE: the exact P2P.me recipe (button labels, order, iframe/DOM specifics) is to be
> captured from the live site and stored in `recipes/p2p-me/`. See SESSION_LOG for the
> captured DOM once available.

## 5. TECH STACK DECISION (Phase 1)

- **Language: Python first.** Rationale: the PoCs are Python + Playwright and are
  PROVEN working; fastest path to a running, debuggable tool. Playwright gives us the
  CDP session (`context.new_cdp_session`) plus browser lifecycle management for free.
- **Later (Phase 2+):** consider a Go (chromedp) or Rust core for single-binary
  distribution to non-coders, and Tauri/Wails for the GUI. Do NOT prematurely rewrite;
  ship a working Python slice first, then decide on distribution packaging.
- **Browser control:** raw CDP via Playwright's `CDPSession` for input; Playwright for
  launch/profile/lifecycle. (We use Playwright as a convenience wrapper but always do
  the actual input via raw `Input.dispatchMouseEvent`, per FACT 2's nuance.)

## 6. RELIABILITY / BACKGROUND OPERATION

- Launch with anti-throttle flags (FACT 2).
- Persistent profile dir → logins survive restarts.
- Supervisor/watchdog keeps the browser + CDP session alive and auto-restarts on
  crash (the human already built this pattern on their Linux server; port the idea).
- Because CDP doesn't need a visible window, no Xvfb/virtual display is required on
  desktop. (On a headless server it's even simpler.)

## 7. CROSS-PLATFORM

- Windows + Linux first (both PoC-validated on Windows; Linux is the human's server
  environment and CDP behaves the same).
- macOS phase 2 (Accessibility permissions, notarization, code-signing).
- Chromium-family only (CDP requirement).
