#!/usr/bin/env python3
# Parche v0.64: la voz y los pitidos suenan en el PC (navegador / OBS) - pagina /voz sin imagen y voz en la de EMITIR
import re, shutil, sys, time
P = "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def feed_add" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.63' not in s:
    sys.exit("Este parche es para la v0.63")
shutil.copy(P, P + ".bak63")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

# ---------------- paginas web (la voz la pone el PC: la Pi solo manda el texto) ----------------
PAGES = r'''
VOICE_JS = r"""
<script>
const ST = (()=>{ try { return JSON.parse(localStorage.getItem('vozpanel') || '{}'); } catch(e) { return {}; } })();
function guardar(){ try { localStorage.setItem('vozpanel', JSON.stringify(ST)); } catch(e) {} }
let ctx = null;
function audio(){ if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)(); return ctx; }
function tono(f0, f1, dur, t0){
  const c = audio(), o = c.createOscillator(), g = c.createGain(), vol = 0.25 * (ST.vol ?? 1);
  o.frequency.setValueAtTime(f0, t0); o.frequency.linearRampToValueAtTime(f1 || f0, t0 + dur);
  g.gain.setValueAtTime(0, t0); g.gain.linearRampToValueAtTime(vol, t0 + .01);
  g.gain.setValueAtTime(vol, t0 + dur - .02); g.gain.linearRampToValueAtTime(0, t0 + dur);
  o.connect(g).connect(c.destination); o.start(t0); o.stop(t0 + dur);
}
function pitido(tipo){
  if (ST.pitidos === false) return 0;
  const c = audio(); c.resume(); let t = c.currentTime;
  if (tipo === 'alarm') { for (let k = 0; k < 2; k++) { tono(880, 880, .15, t); tono(660, 660, .15, t + .2); t += .4; } return .8; }
  if (tipo === 'jump')  { tono(200, 1200, 1.2, t); return 1.2; }
  tono(660, 990, .18, t); return .2;
}
function vocesEs(){ return speechSynthesis.getVoices().filter(v => v.lang.toLowerCase().startsWith('es')); }
const dicho = {};
function decir(a){
  const txt = ((a.titulo || '') + '. ' + (a.dato || '')).replace(/[¡!¿?>|·_]/g, ' ').replace(/\s+/g, ' ').trim();
  if (!txt || Date.now() - (dicho[txt] || 0) < 30000) return;
  dicho[txt] = Date.now();
  const espera = pitido(a.tipo);
  if (ST.voz === false) return;
  setTimeout(() => {
    const u = new SpeechSynthesisUtterance(txt);
    const v = vocesEs().find(x => x.name === ST.nombre) || vocesEs()[0];
    if (v) { u.voice = v; u.lang = v.lang; } else u.lang = 'es-ES';
    u.rate = ST.vel ?? 1.0; u.pitch = ST.tono ?? 0.9; u.volume = ST.vol ?? 1;
    speechSynthesis.speak(u);
    const e = document.getElementById('ultimo'); if (e) e.textContent = txt;
  }, espera * 1000 + 150);
}
let desde = -1;
async function sondeo(){
  const est = document.getElementById('estado');
  try {
    const j = await (await fetch('/avisos?desde=' + desde, {cache: 'no-store'})).json();
    if (desde < 0 || j.seq < desde) desde = j.seq;          // al abrir (o si la Pi reinicia) no lee lo antiguo
    else { j.items.forEach(decir); desde = j.seq; }
    if (est) { est.textContent = 'CONECTADO A LA PI'; est.style.color = '#3ad13a'; }
  } catch(e) { if (est) { est.textContent = 'SIN CONEXIÓN CON LA PI'; est.style.color = '#e03030'; } }
  setTimeout(sondeo, 1000);
}
function activar(){
  audio().resume();
  const ov = document.getElementById('activar'); if (ov) ov.style.display = 'none';
  const u = new SpeechSynthesisUtterance(' '); speechSynthesis.speak(u);
}
window.addEventListener('load', () => {
  sondeo();
  setTimeout(() => { if (audio().state === 'running') activar(); }, 300);   // OBS: ya puede sonar sin tocar
});
</script>
<div id="activar" onclick="activar()" style="position:fixed;inset:0;background:rgba(0,0,0,.85);color:#ff8c00;
 display:flex;align-items:center;justify-content:center;font:bold 28px Segoe UI,Arial;cursor:pointer;z-index:9">
 TOCA AQUÍ PARA ACTIVAR LA VOZ</div>
"""

STREAM_HTML = ("<!doctype html><html><head><meta charset='utf-8'><title>Panel Elite</title></head>"
               "<body style='margin:0;background:#000;overflow:hidden'>"
               "<img src='/hdmi' style='width:100vw;height:100vh;object-fit:contain'>" + VOICE_JS +
               "</body></html>").encode()

VOZ_HTML = ("""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Voz del panel Elite</title>
<style>body{margin:0;background:#000;color:#ff8c00;font-family:Segoe UI,Arial,sans-serif;padding:20px}
h1{margin:0}.d{color:#a05800}select,input{background:#111;color:#ff8c00;border:1px solid #a05800;font-size:16px;padding:5px;margin:4px}
button{background:#000;color:#ff8c00;border:2px solid #ff8c00;border-radius:6px;font-size:16px;padding:8px 14px;margin:4px;cursor:pointer}
label{display:block;margin:8px 0}#ultimo{color:#fff}</style></head><body>
<h1>VOZ DEL PANEL</h1><p class="d">Deja esta pestaña abierta (puede estar minimizada). La voz la pone este PC; la Pi solo manda el texto.</p>
<p id="estado" class="d">conectando...</p>
<label>Voz: <select id="nombre"></select></label>
<label>Velocidad <input id="vel" type="range" min="0.6" max="1.6" step="0.1"></label>
<label>Tono <input id="tono" type="range" min="0.5" max="1.5" step="0.1"></label>
<label>Volumen <input id="vol" type="range" min="0.1" max="1" step="0.1"></label>
<label><input id="vozon" type="checkbox"> Hablar</label>
<label><input id="pitidos" type="checkbox"> Pitidos</label>
<button onclick="decir({tipo:'ok',titulo:'Prueba de voz',dato:'Panel Elite '+Date.now()%1000})">PROBAR</button>
<p class="d">Último aviso: <span id="ultimo">-</span></p>
""" + VOICE_JS + """
<script>
function rellenar(){
  const sel = document.getElementById('nombre'); sel.innerHTML = '';
  vocesEs().forEach(v => { const o = document.createElement('option'); o.value = o.textContent = v.name; sel.appendChild(o); });
  if (ST.nombre) sel.value = ST.nombre;
}
speechSynthesis.onvoiceschanged = rellenar; rellenar();
const C = {vel: 1.0, tono: 0.9, vol: 1};
for (const k of ['vel', 'tono', 'vol']) { const e = document.getElementById(k); e.value = ST[k] ?? C[k]; e.oninput = () => { ST[k] = +e.value; guardar(); }; }
document.getElementById('nombre').onchange = e => { ST.nombre = e.target.value; guardar(); };
const vz = document.getElementById('vozon'), pt = document.getElementById('pitidos');
vz.checked = ST.voz !== false; pt.checked = ST.pitidos !== false;
vz.onchange = () => { ST.voz = vz.checked; guardar(); }; pt.onchange = () => { ST.pitidos = pt.checked; guardar(); };
</script></body></html>""").encode()

# avisos para el PC (solo texto)
feed = {"seq": 0, "items": []}

def feed_add(tipo, titulo, dato):
    with stream_lock:
        feed["seq"] += 1
        feed["items"].append({"n": feed["seq"], "tipo": tipo, "titulo": titulo or "", "dato": dato or ""})
        del feed["items"][:-20]
'''

# sustituir la pagina sencilla de la v0.63 por las nuevas
i0 = s.index("STREAM_HTML = (b\"<!doctype html>")
i1 = s.index("def stream_jpeg(which):")
s = s[:i0] + PAGES.lstrip("\n") + "\n" + s[i1:]

# nuevas direcciones: /voz y /avisos
rep('''            if path not in ("/hdmi", "/panel"):
                self.send_error(404); return''', '''            if path == "/voz":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(VOZ_HTML)
                return
            if path == "/avisos":
                try:
                    desde = int(self.path.split("desde=")[1].split("&")[0])
                except (IndexError, ValueError):
                    desde = -1
                with stream_lock:
                    data = json.dumps({"seq": feed["seq"], "items": [a for a in feed["items"] if a["n"] > desde]})
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(data.encode())
                return
            if path not in ("/hdmi", "/panel"):
                self.send_error(404); return''')

# cada aviso nuevo va a la voz de la Pi (si esta activada) y a la lista para el PC (si EMITIR esta activado)
rep('''def voice_watch():
    a, x = ui.get("alert"), xa.get("a")
    if a is not voice["alert"]:
        voice["alert"] = a
        if a:
            voice_say(f'{a.get("text", "")}. {a.get("sub", "")}')
    if x is not voice["xa"]:
        voice["xa"] = x
        if x:
            voice_say(f'{x.get("title", "")}. {x.get("big", "")}')''', '''def voice_watch():
    a, x = ui.get("alert"), xa.get("a")
    if a is not voice["alert"]:
        voice["alert"] = a
        if a:
            voice_say(f'{a.get("text", "")}. {a.get("sub", "")}')
            if cfg.get("stream"):
                k = a.get("kind")
                feed_add("jump" if k == "jump" else "ok" if k in ("ok", "galnet") else "alarm", a.get("text"), a.get("sub"))
    if x is not voice["xa"]:
        voice["xa"] = x
        if x:
            voice_say(f'{x.get("title", "")}. {x.get("big", "")}')
            if cfg.get("stream"):
                feed_add("alarm" if x.get("col") == RED else "ok", x.get("title"), x.get("big"))''')
rep("    if cfg.get(\"voice\"):\n        voice_watch()\n", "    if cfg.get(\"voice\") or cfg.get(\"stream\"):\n        voice_watch()\n")

rep('    ("0.63", "EMITIR pantallas por la red (PC, OBS, VR) y VOZ de la nave"),\n',
    '    ("0.63", "EMITIR pantallas por la red (PC, OBS, VR) y VOZ de la nave"),\n'
    '    ("0.64", "Voz y pitidos en el PC: página /voz y en EMITIR"),\n')
s = re.sub(r'PANEL_VER = "v0\.63[^"]*"', 'PANEL_VER = "v0.64 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.64 voz en el PC  (copia en panel.py.bak63)")
print("Abre en el PC:  http://IP-de-la-Pi:8080/voz   (activa EMITIR en 12 AJUSTES > OPCIONES)")
