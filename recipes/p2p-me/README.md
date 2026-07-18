# Example recipe — P2P.me auto Close + Accept

> **This is an example recipe, not the product.** Truklick is a general automation
> platform (see the [main README](../../README.md)); this file documents one recipe
> that happens to drive a merchant payments dashboard. It ships because it proves the
> platform works on a real, hostile production site — not because Truklick is a
> "P2P tool". Use it as a template for your own recipes.

For someone who just wants this particular recipe running. No coding needed.

**What it does:** opens a browser, you log in once, then it runs forever — the moment
an order popup appears it clicks **Close**, then clicks the **Accept** button on the
home screen. Then it waits for the next order. That's all it does. It never touches
payments: sending money / verifying money received stays manual on your phone.

---

## 1. Install (one time)

You need **Python 3.12** (not 3.13/3.14 — the project is pinned to 3.12).

```bash
git clone https://github.com/ChinmayaThakral/truklick.git
cd truklick

# create the environment
python3.12 -m venv .venv          # Windows: py -3.12 -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate

pip install -e .
playwright install chromium
```

> No Python 3.12? Easiest way: install [uv](https://docs.astral.sh/uv/), then
> `uv python install 3.12 && uv venv --python 3.12 .venv`

## 2. Run it

```bash
truklick run recipes/p2p-me/recipe.json
```

A Chromium window opens on lp.p2p.me.

- **Log in** (first run only — the login is remembered in `truklick_profile/`)
- That's it. It's already looping and will click Close → Accept on every order.
- While it waits you'll see `still waiting for target {'text': 'Close'...}` — normal.

**To stop:** press `Ctrl+C` in the terminal.

## 3. What you'll see when an order comes

```
clicking {'text': 'Close', 'exact': True} via text in main frame
input | click (640, 652) button=left
clicking {'role': 'button', 'name': 'Accept', 'exact': True} via role in main frame
input | click (668, 597) button=left
```

That's one order closed and accepted.

---

## Things worth knowing

**You can see the state on the browser itself.** A small badge appears top-right of
the page: green **● Truklick RUNNING** (fades after 2s) or amber **⏸ Truklick PAUSED**
(stays until you resume). So you can tell at a glance whether it's live without
switching to the terminal. Turn it off with `--no-overlay` if you'd rather not have it.

**It accepts every order it sees.** While it's running it will keep accepting orders,
including several in a row. If you can only work one order at a time, stop it
(`Ctrl+C`) while you handle one, then start it again.

**The pause hotkey (`Escape`) needs permission on macOS.** Go to *System Settings →
Privacy & Security → Accessibility*, add your terminal app, and restart the terminal.
Without it you'll see a warning that the hotkey won't work, and `Ctrl+C` is your only
stop. On Windows/Linux it generally works out of the box.

**If you ever see `PASS ABORTED AFTER N CLICK(S)`** — that means the popup was closed
but Accept never showed up, so that order was *not* accepted. Check it manually. This
happened once in live testing and the cause isn't fully understood yet, so watch the
first few orders before leaving it unattended.

**To make it close-only** (dismiss popups but let you tap Accept yourself): open
`recipes/p2p-me/recipe.json` and delete the last step (the one that clicks `Accept`).

**Speed:** it re-checks the page every 10ms and reacts in roughly 45ms. Making that
number smaller won't help — the limit is browser round-trip time, not the setting.

**Your login and any captures stay on your machine.** `truklick_profile/`,
`p2p_profile/` and `captures/` are gitignored and never uploaded.

---

## Useful extras

```bash
truklick run recipes/p2p-me/recipe.json --once     # handle a single order, then exit
truklick run recipes/p2p-me/recipe.json -v         # verbose logging
truklick run <recipe> --attach http://localhost:9222   # drive a browser you already have open
```

Full details: `README.md`, `docs/ARCHITECTURE.md`, and `docs/PROVEN_FACTS.md`.
