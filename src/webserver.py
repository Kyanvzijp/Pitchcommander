"""
Webinterface voor de telefoon (zelfde netwerk als de Pi).

Open op je telefoon:  http://<ip-van-de-pi>:8080
Tik in de slagzone om een doelwit te plaatsen. De beamer projecteert daar
een bullseye. Elke worp wordt beoordeeld: binnen de doelcirkel = RAAK.

Draait in een daemon-thread naast de detectielus (gestart vanuit main.py).
"""
import random
import threading
from flask import Flask, jsonify, request

import config
from shared import STATE

app = Flask(__name__)

PAGE = """<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<title>Pitch Trainer</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, system-ui, sans-serif;
         background: #0d1117; color: #e6edf3; padding: 16px;
         display: flex; flex-direction: column; align-items: center; gap: 14px; }
  h1 { font-size: 1.2rem; }
  #zone { position: relative; width: min(92vw, 440px);
          aspect-ratio: __ASPECT__; background: #161b22;
          border: 3px solid #2ea043; border-radius: 6px;
          touch-action: manipulation; }
  .gridline { position: absolute; background: #21452b; }
  #target { position: absolute; width: 46px; height: 46px;
            margin: -23px 0 0 -23px; border-radius: 50%;
            border: 3px solid #f0b429;
            background: radial-gradient(circle, #f0b429 18%, transparent 19%,
                        transparent 45%, rgba(240,180,41,.5) 46%, transparent 60%);
            display: none; pointer-events: none; }
  .impact { position: absolute; width: 16px; height: 16px;
            margin: -8px 0 0 -8px; border-radius: 50%;
            border: 2px solid #fff; pointer-events: none; }
  .raak { background: #2ea043; } .mis { background: #d29922; }
  .bal  { background: #f85149; }
  #stats { font-size: 1.05rem; }
  #laatste { min-height: 1.4em; font-weight: 600; }
  .knoppen { display: flex; gap: 10px; }
  button { background: #21262d; color: #e6edf3; border: 1px solid #30363d;
           border-radius: 8px; padding: 10px 16px; font-size: .95rem; }
  button:active { background: #30363d; }
  small { color: #8b949e; }
</style>
</head>
<body>
  <h1>Pitch Trainer</h1>
  <small>Tik in de zone om een doelwit te plaatsen</small>
  <div id="zone">
    <div class="gridline" style="left:33.3%;top:0;width:1px;height:100%"></div>
    <div class="gridline" style="left:66.6%;top:0;width:1px;height:100%"></div>
    <div class="gridline" style="top:33.3%;left:0;height:1px;width:100%"></div>
    <div class="gridline" style="top:66.6%;left:0;height:1px;width:100%"></div>
    <div id="target"></div>
  </div>
  <div id="laatste"></div>
  <div id="stats">Raak: <b id="h">0</b> &nbsp; Mis: <b id="m">0</b></div>
  <div class="knoppen">
    <button onclick="randomTarget()">Random spot</button>
    <button onclick="clearTarget()">Doel weg</button>
    <button onclick="resetAll()">Reset score</button>
  </div>
<script>
const zone = document.getElementById('zone');
const targetEl = document.getElementById('target');
let lastResultT = 0;

zone.addEventListener('click', e => {
  const r = zone.getBoundingClientRect();
  const nx = (e.clientX - r.left) / r.width;
  const ny = (e.clientY - r.top) / r.height;
  setTarget(nx, ny);
});

function setTarget(nx, ny) {
  fetch('/api/target', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({nx, ny})});
  showTarget(nx, ny);
}
function showTarget(nx, ny) {
  targetEl.style.left = (nx*100)+'%';
  targetEl.style.top  = (ny*100)+'%';
  targetEl.style.display = 'block';
}
function randomTarget() {
  setTarget(0.12 + Math.random()*0.76, 0.12 + Math.random()*0.76);
}
function clearTarget() {
  fetch('/api/target/clear', {method:'POST'});
  targetEl.style.display = 'none';
}
function resetAll() {
  fetch('/api/reset', {method:'POST'});
  document.querySelectorAll('.impact').forEach(el => el.remove());
  document.getElementById('laatste').textContent = '';
}

async function poll() {
  try {
    const s = await (await fetch('/api/status')).json();
    document.getElementById('h').textContent = s.hits;
    document.getElementById('m').textContent = s.misses;
    if (s.target) showTarget(s.target.nx, s.target.ny);
    else targetEl.style.display = 'none';

    document.querySelectorAll('.impact').forEach(el => el.remove());
    for (const r of s.results) {
      const d = document.createElement('div');
      d.className = 'impact ' + (r.hit === true ? 'raak'
                   : (r.hit === false ? 'mis' : (r.strike ? 'mis' : 'bal')));
      // Worpen buiten de zone net binnen de rand tonen, anders zweven de
      // stippen over de knoppen heen.
      const cx = Math.min(Math.max(r.nx, -0.04), 1.04);
      const cy = Math.min(Math.max(r.ny, -0.04), 1.04);
      d.style.left = (cx*100)+'%';
      d.style.top  = (cy*100)+'%';
      zone.appendChild(d);
    }
    const last = s.results[s.results.length-1];
    if (last && last.t > lastResultT) {
      lastResultT = last.t;
      const el = document.getElementById('laatste');
      if (last.hit === true)  el.textContent = 'RAAK!';
      else if (last.hit === false)
        el.textContent = 'Mis, ' + last.dist_pct + '% ernaast';
      else el.textContent = last.strike ? 'Strike' : 'Ball';
      el.style.color = last.hit === true ? '#2ea043' : '#d29922';
    }
  } catch (e) { /* server even weg, stil opnieuw proberen */ }
  setTimeout(poll, 700);
}
poll();
</script>
</body>
</html>"""


@app.route("/")
def index():
    aspect = f"{config.ZONE_W} / {config.ZONE_H}"
    return PAGE.replace("__ASPECT__", aspect)


@app.route("/api/target", methods=["POST"])
def set_target():
    data = request.get_json(force=True, silent=True) or {}
    try:
        nx = float(data["nx"])
        ny = float(data["ny"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"ok": False, "error": "nx/ny vereist"}), 400
    STATE.set_target_normalized(nx, ny)
    return jsonify({"ok": True})


@app.route("/api/target/clear", methods=["POST"])
def clear_target():
    STATE.clear_target()
    return jsonify({"ok": True})


@app.route("/api/reset", methods=["POST"])
def reset():
    STATE.reset_results()
    return jsonify({"ok": True})


@app.route("/api/status")
def status():
    return jsonify(STATE.snapshot())


def start_in_background():
    """Start Flask in een daemon-thread. Aanroepen vanuit main.py."""
    t = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=config.WEB_PORT,
                               debug=False, use_reloader=False,
                               threaded=True),
        daemon=True)
    t.start()
    return t
