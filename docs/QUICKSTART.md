# QUICKSTART

## The fastest path

1. Download the file for your computer from
   [**Releases**](https://github.com/ChinmayaThakral/truklick/releases):
   `truklick-windows-x64.exe`, `truklick-macos-arm64`, or `truklick-linux-x64`.
2. Run it. (macOS/Linux: `chmod +x ./truklick-*` once first. macOS may warn it's
   unsigned — right-click → **Open** → **Open**.)
3. The **control panel** opens in your browser.
4. Pick **`recipes/demo/selftest.json`** and press **Start**.

A browser window opens and a button turns green **TRUSTED ✓**. That's Truklick firing
a real, trusted click. Your install works.

On first run it downloads the browser it drives (~150 MB, once).

## From source instead

Needs **Python 3.12**.

```bash
git clone https://github.com/ChinmayaThakral/truklick.git && cd truklick
python3.12 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e . && playwright install chromium
truklick
```

## Running your own automation

Point it at any recipe:

```bash
truklick run path/to/recipe.json      # or just pick it in the control panel
```

- **Pause/resume** with the recipe's hotkey (default `Escape`). A badge in the page
  shows green **RUNNING** or amber **PAUSED**.
- **Stop** with `Ctrl+C`, or the Stop button in the panel.
- Logins persist — the browser profile is saved next to the app and is never uploaded.

Writing your own recipe: see the format in the [README](../README.md#writing-a-recipe)
and the worked example in [`recipes/p2p-me/`](../recipes/p2p-me/).

## If something goes wrong

| Symptom | Fix |
|---|---|
| Hotkey doesn't pause it (macOS) | System Settings → Privacy & Security → Accessibility → add your terminal/the app, then restart it |
| `PASS ABORTED AFTER N CLICK(S)` | A recipe clicked something, then a later step didn't find its target. The page was left part-way — check it |
| Nothing happens, log says `still waiting` | The recipe's target isn't on screen yet. That's normal while it waits |
| macOS "cannot be opened" | Right-click the file → **Open** → **Open** (downloads aren't signed yet) |
