# PROVEN_FACTS.md — Experimentally Verified Truths

> These are facts we have **proven with running code on real hardware**, not
> assumptions. Every architectural decision rests on them. **Do not contradict
> a fact here without designing a new proof, running it, getting a green result,
> and updating this file.** This is the anti-hallucination anchor for the project.

---

## FACT 1 — CDP produces genuinely trusted input
- **Claim:** The Chrome DevTools Protocol command `Input.dispatchMouseEvent`
  produces DOM events with `isTrusted === true`, indistinguishable from a real
  mouse at the event-integrity level.
- **Why it matters:** Browser-extension JavaScript can NEVER produce trusted input
  (`isTrusted` is unforgeable from extension/page JS — a browser security guarantee).
  Sites that gate on trusted input (payments, "slide to confirm", some anti-bot)
  reject synthetic extension clicks but accept CDP input.
- **Proof:** `poc/poc_test_windows.py` — a local page recorded `e.isTrusted` on the
  received click. Result: `isTrusted: True`.
- **Status:** ✅ PROVEN on Windows (real hardware), [date: 2026-06-27].

## FACT 2 — Trusted CDP clicks work while the window is minimized/occluded
- **Claim:** With the correct launch flags, `Input.dispatchMouseEvent` lands on the
  target even when the Chromium window is minimized, occluded, or unfocused.
- **Required launch flags:**
  - `--disable-background-timer-throttling`
  - `--disable-backgrounding-occluded-windows`
  - `--disable-renderer-backgrounding`
  - `--disable-ipc-flooding-protection`
  - `--disable-features=CalculateNativeWinOcclusion`
- **Why it matters:** This eliminates the need for a virtual display (Xvfb) or
  OS-level pixel clicking. It is the key advantage over xdotool/RobotGo, which
  require a visible/virtual display and break when minimized.
- **Important nuance (verified):** This works with **raw** `Input.dispatchMouseEvent`
  at coordinates. It does NOT rely on Puppeteer/Playwright's high-level `page.click()`,
  which first tries to scroll the element into view using IntersectionObserver — and
  IntersectionObserver does NOT fire in background tabs (Puppeteer issues #5201,
  #3339, #3318). So: **always use raw CDP coordinate dispatch, never high-level
  element.click(), for background reliability.**
- **Proof:** `poc/poc_test_windows.py` — clicked a button while the window was
  minimized; click landed, `isTrusted: True`, dispatched in ~16ms.
- **Status:** ✅ PROVEN on Windows (real hardware), [date: 2026-06-27].

## FACT 3 — It works on the REAL target site, logged in, real DOM
- **Claim:** The same trusted-CDP-while-minimized behavior works on a real,
  logged-in production web app (lp.p2p.me), not just clean local pages — including
  finding elements in the real DOM (and iframes if present).
- **Proof:** `poc/poc_test_p2p.py` — persistent-profile Chromium, real login, found a
  real element by visible text, fired trusted CDP click while minimized. User
  confirmed: "works flawlessly."
- **Status:** ✅ PROVEN on Windows against lp.p2p.me (real hardware), [date: 2026-06-27].

## FACT 4 — DOM-based resilient targeting works (no hardcoded pixels)
- **Claim:** We can locate an element by visible text or selector, read its
  `getBoundingClientRect()` / bounding box, and click its center via CDP. This
  survives layout shifts (unlike fixed screen coordinates) and is how the picker
  will work.
- **Proof:** Both PoCs locate the target via the DOM and compute center coordinates
  at runtime, rather than using fixed pixels.
- **Status:** ✅ PROVEN, [date: 2026-06-27].

## FACT 5 — Trusted CDP click works while minimized on macOS too
- **Claim:** The trusted-CDP-while-minimized behavior (FACT 2) holds on macOS, not
  just Windows. The anti-throttle flags + raw `Input.dispatchMouseEvent` land a
  trusted click on a minimized window on Apple Silicon.
- **Method note (honest):** The window was minimized programmatically over CDP
  (`Browser.setWindowBounds` → `windowState:"minimized"`, verified by reading the
  state back as `"minimized"`), not by a human clicking minimize — but the OS window
  is in the minimized state either way, which is the property that matters.
- **Proof:** `poc/poc_test_mac.py` — window state `minimized`, click received on the
  self-test page, `isTrusted: True`, dispatch ~54ms.
- **Status:** ✅ PROVEN on macOS (Apple Silicon, real hardware), [date: 2026-07-16].
- **Still open:** the real *lp.p2p.me* minimized run (on the author's Windows box) is
  the product-level Phase-1 gate; this fact covers the engine/OS property only.

## FACT 6 — The ENGINE drives the real target end-to-end from a recipe
- **Claim:** Truklick's engine, running a recipe unattended, performs the full
  real-world sequence on the live logged-in site: detect the order popup → trusted
  click **Close** → wait for the home-screen **Accept** → trusted click **Accept**.
  Not a PoC script — the actual engine + recipe + CLI.
- **Proof:** 2026-07-19, `truklick run recipes/p2p-me/recipe.json --attach ...`
  against the live lp.p2p.me session. Log:
  `00:33:37 clicking {'text':'Close'} via text` → `00:33:38 clicking
  {'role':'button','name':'Accept','exact':True} via role`. The author watched it
  happen and confirmed: *"yes i saw it clicking accept on the second one."*
- **Why it matters:** closes the loop from PROVEN_FACTS 1–4 (trusted input works) to
  "the platform actually automates a real task from a shareable recipe."
- **Status:** ✅ PROVEN on macOS against live lp.p2p.me, [date: 2026-07-19].
- **IMPORTANT RELIABILITY CAVEAT — do not read this as "it works reliably":**
  In the same run, **1 of 2 order cycles FAILED**. On the first cycle Close was
  clicked and the Accept button then never appeared for 15s of continuous polling,
  so the popup was dismissed and the order left **unaccepted**. Root cause unknown
  (either that order's Accept genuinely never rendered, or it rendered in a form
  `role=button` could not see). Mitigations added: Accept timeout raised to 40s, and
  the runner now logs `PASS ABORTED AFTER N CLICK(S)` whenever a pass dies after
  already clicking, so a half-done order is never silent. **Not yet proven:
  reliability across many orders, and the real-site MINIMIZED run.**

---

## KNOWN CAVEATS (verified, not yet blockers)
- **Behavioral anti-bot detection:** Advanced 2026-era bot-defense systems can
  sometimes distinguish CDP-driven input from human input NOT via `isTrusted`
  (which is genuinely true) but via **motion physics** — trajectory entropy,
  sub-pixel coords, acceleration curves, timing jitter. CDP input can be "too
  perfect." Mitigation: generate human-like motion profiles (easing + jitter).
  For simple merchant-dashboard buttons this almost certainly doesn't matter; for
  hardened targets it might. This is a refinement, not a blocker. (Source:
  research, `docs/RESEARCH.md`.)
- **CDP is Chromium-only:** Firefox/Safari are out of scope for the trusted-input
  path. Scope the platform to Chromium-family browsers.
- **No CDP auto-wait:** raw CDP has no built-in waiting; the element must exist
  before dispatch. The recipe runner must handle "wait for element" explicitly.

---

## HOW TO ADD A NEW FACT
1. Write a minimal PoC in `/poc` that isolates the single claim.
2. Run it on real hardware (or have the human run it).
3. Only if green: add a numbered FACT here with the claim, why it matters, the proof
   file, and the date. Cross-reference it in `docs/DECISIONS.md`.
