# CAPTURE_GUIDE.md — grabbing the P2P.me buttons (no DevTools)

> A dead-simple playbook for capturing the Close (popup) and Accept (home) controls
> with `scripts/capture_helper.py`, so the real recipe can be built accurately.
> Written to be usable by a non-coder (future-you, or a friend). Orders arrive
> ~1/hour and popups can expire — so the goal is: be fast and calm, not fumbling.

---

## THE 30-SECOND VERSION

1. `git pull` (get the latest), then from the repo root:
   ```
   python scripts/capture_helper.py
   ```
   (Windows: `py -3.12 scripts\capture_helper.py`. Reuses `./p2p_profile`, so log in once.)
2. **Order popup on screen** (Slide to Accept + Close) → click the terminal → press **ENTER**.
3. **Click Close yourself** → home shows the clean **Accept** button → press **ENTER** again.
4. Press **q** to quit.
5. Send me the two `captures/capture_*.json` files (or paste the two terminal lists and
   say which number is Close and which is Accept).

That's it. No right-clicking, no copying selectors.

---

## PRACTICE FIRST (do this before a real order — 2 minutes)

The one risk is that the *first* time you use this is during a time-sensitive order.
Kill that risk now: point it at ANY site with a popup and rehearse the two-press rhythm.

- Run the helper, but when it opens, browse to any site with a modal — a cookie-consent
  banner, a login modal, a newsletter popup, anything with a **Close/X** button.
- Popup on screen → **ENTER**. Read the printed list — find your button by its text and
  note its `frame=` tag.
- Dismiss it → **ENTER** again.
- Open `captures/` and glance at a JSON file so you know what you're sending me.

After this you'll have the muscle memory. When the real order comes, hit ENTER the
instant the popup appears — the scan is sub-second, faster than a popup can expire.

---

## WHAT THE TERMINAL SHOWS YOU

Each ENTER prints something like:
```
  Found 42 elements (7 look clickable). Showing up to 15 likely buttons:
    [0] 'Close'  <button>  frame=main
    [1] 'Slide to Accept'  <div>  frame=main
    ...
  ✓ Saved full capture -> captures/capture_20260716_141530.json
```
- The `frame=` tag tells us **where the popup renders** (main frame vs an iframe) — this
  is the exact fact that decides how the recipe (and the future scanner) must target it.
- Type `l` instead of ENTER for a longer list if your button isn't in the first 15.

---

## THE MAC MINIMIZED SELF-TEST (closes the last Phase-1 box — do this from the Mac)

Session 1 proved the engine fires a **trusted** click end-to-end on the Mac, but only
*headless* (no window to minimize). "Works while minimized" is PROVEN on Windows
(PROVEN_FACTS FACT 2) but **unproven on macOS**. This test settles it on real Mac
hardware, and needs no live order:

```
truklick run recipes/demo/minimized_selftest.json \
  --url "file://$(pwd)/examples/selftest.html"
```

Then:
1. A Chromium window opens on the self-test page. **You have ~10 seconds to MINIMIZE it.**
2. While minimized, the engine fires the trusted click (you won't see it happen).
3. The window stays open ~20s more — **restore it** and look at the button:
   - **green "TRUSTED ✓"** → the click landed while minimized. macOS confirmed. ✅
   - still blue/unchanged → it did NOT land minimized on macOS; tell me and we dig in
     (this is exactly the kind of Mac-specific window/focus quirk worth flushing out now).

> Honest note: this is a genuine open question, not a formality — I don't yet know if the
> anti-throttle flags behave the same on macOS as on Windows. That's why the test exists.
> If pynput/Accessibility is granted you can instead run with `--wait` and press Escape
> after minimizing; the fixed-wait version above needs no permissions.

---

## SENDING CAPTURES BACK

Either is fine:
- **Paste the two terminal lists** and say "Close is [0], Accept is [2]", or
- **Paste / attach the two `captures/capture_*.json` files.**

The `captures/` folder is gitignored (it can contain page content), so it won't be
committed — you send the files to me directly.
