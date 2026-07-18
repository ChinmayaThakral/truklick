"""Local control panel — the no-terminal way to use Truklick.

Serves a small page on 127.0.0.1 and opens it in the default browser. You pick a
recipe, hit Start, and watch the live log. The recipe runs as a SUBPROCESS, so a
crash in a run can never take down the panel, and Stop is a real kill.

Deliberately stdlib-only (http.server + threads): no extra dependency, works
identically on Windows / macOS / Linux, and survives being frozen into a binary.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from .log import get_logger

log = get_logger("gui")

_LOG_LINES: deque[str] = deque(maxlen=500)
_PROC: Optional[subprocess.Popen] = None
_LOCK = threading.Lock()
_CURRENT: Optional[str] = None


def _base_dir() -> Path:
    """Where recipes live — next to the binary when frozen, else the repo."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent.parent


def list_recipes() -> list[str]:
    root = _base_dir() / "recipes"
    out = []
    if root.is_dir():
        out = sorted(str(p.relative_to(_base_dir())) for p in root.rglob("*.json"))
    cwd = Path.cwd() / "recipes"
    if cwd.is_dir() and cwd != root:
        out += sorted(str(p) for p in cwd.rglob("*.json"))
    return out


def _self_cmd(recipe: str) -> list[str]:
    """Command to run a recipe using this same install (frozen binary or module)."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "run", recipe]
    return [sys.executable, "-m", "truklick", "run", recipe]


def _pump(proc: subprocess.Popen) -> None:
    for raw in iter(proc.stdout.readline, b""):
        line = raw.decode("utf-8", "replace").rstrip()
        if line:
            _LOG_LINES.append(line)
    _LOG_LINES.append("--- run ended ---")


def start(recipe: str, extra: list[str] | None = None) -> tuple[bool, str]:
    global _PROC, _CURRENT
    with _LOCK:
        if _PROC and _PROC.poll() is None:
            return False, "already running"
        if not Path(recipe).exists() and not (_base_dir() / recipe).exists():
            return False, f"recipe not found: {recipe}"
        path = recipe if Path(recipe).exists() else str(_base_dir() / recipe)
        cmd = _self_cmd(path) + (extra or [])
        _LOG_LINES.clear()
        _LOG_LINES.append(f"$ {' '.join(cmd)}")
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        _PROC = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, env=env)
        _CURRENT = recipe
        threading.Thread(target=_pump, args=(_PROC,), daemon=True).start()
        return True, "started"


def stop() -> tuple[bool, str]:
    global _PROC
    with _LOCK:
        if not _PROC or _PROC.poll() is not None:
            return False, "not running"
        _PROC.terminate()
        try:
            _PROC.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _PROC.kill()
        return True, "stopped"


def status() -> dict:
    running = bool(_PROC and _PROC.poll() is None)
    return {"running": running, "recipe": _CURRENT if running else None,
            "log": list(_LOG_LINES)[-200:]}


PAGE = """<!doctype html><html><head><meta charset=utf-8>
<title>Truklick</title><style>
:root{color-scheme:dark}
body{margin:0;font:15px/1.5 system-ui,-apple-system,sans-serif;background:#0d1117;color:#e6edf3}
header{padding:18px 24px;border-bottom:1px solid #21262d;display:flex;align-items:center;gap:12px}
h1{font-size:18px;margin:0;font-weight:650;letter-spacing:.2px}
.tag{font-size:12px;color:#8b949e}
main{padding:24px;max-width:900px;margin:0 auto}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:18px}
select{flex:1;min-width:260px;padding:10px;border-radius:8px;background:#161b22;
 color:#e6edf3;border:1px solid #30363d;font-size:14px}
button{padding:10px 20px;border:0;border-radius:8px;font-weight:600;cursor:pointer;font-size:14px}
#go{background:#238636;color:#fff}#halt{background:#da3633;color:#fff}
button:disabled{opacity:.4;cursor:not-allowed}
#dot{width:10px;height:10px;border-radius:50%;background:#6e7681;display:inline-block}
#dot.on{background:#3fb950;box-shadow:0 0 10px #3fb950}
.step{display:flex;gap:10px;align-items:center;background:#161b22;border:1px solid #30363d;
 border-radius:8px;padding:9px 12px;margin-bottom:7px;flex-wrap:wrap}
.step b{font-size:13px;color:#79c0ff;min-width:74px}
.step .t{flex:1;min-width:150px;color:#8b949e;font-size:12.5px;
 overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.step label{font-size:11.5px;color:#8b949e}
.step input{width:74px;padding:5px 7px;border-radius:6px;background:#0d1117;
 color:#e6edf3;border:1px solid #30363d;font-size:12.5px}
.step .del{background:#30363d;color:#e6edf3;padding:5px 10px;font-size:12px}
pre{background:#010409;border:1px solid #21262d;border-radius:10px;padding:14px;
 height:52vh;overflow:auto;font:12.5px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace;
 white-space:pre-wrap;word-break:break-word}
.hint{color:#8b949e;font-size:13px;margin-top:10px}
</style></head><body>
<header><span id=dot></span><h1>Truklick</h1>
<span class=tag>trusted browser automation &middot; runs recipes</span></header>
<main>
 <div id=upd style="display:none;margin-bottom:16px;padding:11px 14px;border-radius:8px;
   background:#1f2a37;border:1px solid #2f4562;font-size:13.5px"></div>
 <div class=row>
   <select id=recipe></select>
   <button id=go>Start</button>
   <button id=halt disabled>Stop</button>
   <button id=edit style="background:#30363d;color:#e6edf3">Tune</button>
 </div>
 <div id=editor style="display:none;margin-bottom:18px">
   <div id=steps></div>
   <button id=save style="background:#1f6feb;color:#fff;margin-top:10px">Save</button>
   <span id=saved class=hint></span>
 </div>
 <pre id=log>Pick a recipe and press Start.</pre>
 <div class=hint>A browser window will open. Log in once if the site needs it —
 the login is remembered. Press Stop here (or the recipe's hotkey) to halt.</div>
</main>
<script>
const $=s=>document.querySelector(s);
async function refresh(){
  const r=await fetch('/api/status').then(r=>r.json());
  $('#dot').className=r.running?'on':'';
  $('#go').disabled=r.running; $('#halt').disabled=!r.running;
  if(r.log.length){const el=$('#log');const bottom=el.scrollTop+el.clientHeight>=el.scrollHeight-40;
    el.textContent=r.log.join('\\n'); if(bottom)el.scrollTop=el.scrollHeight;}
}
let RECIPE=null, RPATH=null;
const FIELDS=[['ms','delay ms'],['timeout_ms','timeout ms'],['poll_ms','poll ms']];
function drawSteps(){
  $('#steps').innerHTML = RECIPE.steps.map((s,i)=>{
    const t=s.target?JSON.stringify(s.target):(s.text||'');
    const inputs=FIELDS.filter(([k])=>s[k]!==undefined).map(([k,lab])=>
      `<label>${lab}</label><input data-i="${i}" data-k="${k}" value="${s[k]}">`).join(' ');
    return `<div class=step><b>${s.action}</b><span class=t title='${t}'>${t}</span>
      ${inputs}<button class=del data-del="${i}">remove</button></div>`;}).join('')
    || '<div class=hint>no steps</div>';
  $('#steps').querySelectorAll('input').forEach(el=>el.onchange=e=>{
    const v=parseInt(e.target.value,10);
    if(!isNaN(v)) RECIPE.steps[e.target.dataset.i][e.target.dataset.k]=v;});
  $('#steps').querySelectorAll('[data-del]').forEach(el=>el.onclick=e=>{
    RECIPE.steps.splice(+e.target.dataset.del,1); drawSteps();});
}
$('#edit').onclick=async()=>{
  const box=$('#editor');
  if(box.style.display==='block'){box.style.display='none';return;}
  RPATH=$('#recipe').value;
  RECIPE=await fetch('/api/recipe?path='+encodeURIComponent(RPATH)).then(r=>r.json());
  drawSteps(); box.style.display='block';
};
$('#save').onclick=async()=>{
  const r=await fetch('/api/save',{method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify({path:RPATH,recipe:RECIPE})}).then(r=>r.json());
  $('#saved').textContent = r.ok ? 'saved' : ('not saved: '+r.msg);
  setTimeout(()=>$('#saved').textContent='',4000);
};
$('#go').onclick=async()=>{await fetch('/api/start',{method:'POST',
  headers:{'content-type':'application/json'},body:JSON.stringify({recipe:$('#recipe').value})});refresh();};
$('#halt').onclick=async()=>{await fetch('/api/stop',{method:'POST'});refresh();};
fetch('/api/update').then(r=>r.json()).then(u=>{
  if(u.available){ $('#upd').style.display='block';
    $('#upd').innerHTML = `A newer version is available: <b>v${u.latest}</b> `
      + `(you have v${u.current}) &nbsp;<a href="${u.url}" target="_blank" `
      + `style="color:#79c0ff">Download</a>`; }
}).catch(()=>{});
(async()=>{
  const rs=await fetch('/api/recipes').then(r=>r.json());
  $('#recipe').innerHTML=rs.map(r=>`<option value="${r}">${r}</option>`).join('')
    || '<option>no recipes found</option>';
  setInterval(refresh,600); refresh();
})();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _resolve(self, rel):
        from urllib.parse import unquote
        rel = unquote(rel)
        p = Path(rel)
        return p if p.exists() else (_base_dir() / rel)

    def do_GET(self):
        if self.path.startswith("/api/recipe?"):
            rel = self.path.split("?path=", 1)[1]
            try:
                return self._send(200, self._resolve(rel).read_text(encoding="utf-8"))
            except Exception as exc:
                return self._send(400, json.dumps({"error": str(exc)}))
        if self.path == "/":
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if self.path == "/api/update":
            try:
                from .update import check
                i = check()
                return self._send(200, json.dumps(
                    {"available": bool(i and i.available),
                     "latest": i.latest if i else None,
                     "current": i.current if i else None,
                     "url": i.url if i else None}))
            except Exception:
                return self._send(200, json.dumps({"available": False}))
        if self.path == "/api/status":
            return self._send(200, json.dumps(status()))
        if self.path == "/api/recipes":
            return self._send(200, json.dumps(list_recipes()))
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if self.path == "/api/start":
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            ok, msg = start(body.get("recipe", ""))
            return self._send(200 if ok else 400, json.dumps({"ok": ok, "msg": msg}))
        if self.path == "/api/save":
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            tmp = None
            try:
                # validate before overwriting — never save a recipe that won't load
                from .recipe import load_recipe
                target = self._resolve(body["path"])
                tmp = target.with_suffix(".tmp.json")
                tmp.write_text(json.dumps(body["recipe"], indent=2,
                                          ensure_ascii=False) + "\n", encoding="utf-8")
                load_recipe(tmp)          # raises if invalid
                tmp.replace(target)
                return self._send(200, json.dumps({"ok": True}))
            except Exception as exc:
                if tmp is not None:
                    try:
                        tmp.unlink(missing_ok=True)
                    except Exception:
                        pass
                return self._send(400, json.dumps({"ok": False, "msg": str(exc)}))
        if self.path == "/api/stop":
            ok, msg = stop()
            return self._send(200, json.dumps({"ok": ok, "msg": msg}))
        self._send(404, b"not found", "text/plain")

    def log_message(self, *a):  # keep the console clean
        pass


def serve(port: int = 8765, open_browser: bool = True) -> int:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print("=" * 58)
    print(f"  Truklick control panel:  {url}")
    print("  Close this window to quit.")
    print("=" * 58, flush=True)
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop()
        httpd.server_close()
    return 0
