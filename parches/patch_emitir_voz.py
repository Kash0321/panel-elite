#!/usr/bin/env python3
# Parche v0.63: EMITIR (ver las pantallas en el PC/OBS/VR por la red) y VOZ de la nave; los dos se activan en OPCIONES
import re, shutil, sys, time
P = "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def stream_start" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.62' not in s:
    sys.exit("Este parche es para la v0.62")
shutil.copy(P, P + ".bak62")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

CODE = r'''
# ---------- EMITIR: las pantallas por la red (http://IP:8080) ----------
# Solo gasta CPU mientras alguien esta mirando: si no hay nadie conectado no se copia ni se comprime nada.
STREAM_PORT = 8080
stream = {"clients": 0, "big": None, "small": None, "seq": 0, "jpg": {}, "srv": None, "err": ""}
stream_lock = threading.Lock()
STREAM_HTML = (b"<!doctype html><html><head><meta charset='utf-8'><title>Panel Elite</title></head>"
               b"<body style='margin:0;background:#000;overflow:hidden'>"
               b"<img src='/hdmi' style='width:100vw;height:100vh;object-fit:contain'></body></html>")

def stream_jpeg(which):
    import io
    with stream_lock:
        seq = stream["seq"]
        old = stream["jpg"].get(which)
        if old and old[0] == seq:
            return old[1]
        surf = stream["big"] if which == "big" and stream["big"] is not None else stream["small"]
        if surf is None:
            return None
        buf = io.BytesIO()
        pygame.image.save(surf, buf, "x.jpg")
        data = buf.getvalue()
        stream["jpg"][which] = (seq, data)
        return data

def stream_start():
    if stream["srv"]:
        return
    from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/ver"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(STREAM_HTML.replace(b"/hdmi", b"/panel") if "pequena" in self.path else STREAM_HTML)
                return
            if path not in ("/hdmi", "/panel"):
                self.send_error(404); return
            which = "big" if path == "/hdmi" else "small"
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            stream["clients"] += 1
            last = -1
            try:
                while cfg.get("stream"):
                    if stream["seq"] == last:
                        time.sleep(0.05); continue
                    last = stream["seq"]
                    jpg = stream_jpeg(which)
                    if jpg:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(jpg))
                        self.wfile.write(jpg + b"\r\n")
            except Exception:
                pass
            finally:
                stream["clients"] -= 1

    try:
        srv = ThreadingHTTPServer(("0.0.0.0", STREAM_PORT), H)
        srv.daemon_threads = True
        stream["srv"] = srv
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print(f"EMITIR: http://{my_ip()}:{STREAM_PORT}")
    except OSError as e:
        stream["err"] = str(e)[:40]
        print("EMITIR:", e)

def stream_snap(small):
    if not cfg.get("stream") or stream["clients"] <= 0:
        return
    with stream_lock:
        stream["small"] = small.copy()
        stream["big"] = BIG["surf"].copy() if BIG.get("fb") and BIG.get("surf") is not None else None
        stream["seq"] += 1

if cfg.get("stream"):
    pass   # se arranca en main() cuando ya estan los ajustes cargados

# ---------- VOZ de la nave (espeak-ng) ----------
voice = {"alert": None, "xa": None, "proc": None, "last": {}}

def voice_ok():
    return bool(shutil.which("espeak-ng"))

def voice_say(text):
    if not cfg.get("voice") or not voice_ok():
        return
    t = re.sub(r"[¡!¿?>|·_]", " ", text or "")
    t = re.sub(r"\s+", " ", t).strip(" .")
    if not t or time.time() - voice["last"].get(t, 0) < 30:      # no repetir lo mismo en 30 s
        return
    p_ = voice["proc"]
    if p_ and p_.poll() is None:                                  # ya esta hablando
        return
    voice["last"][t] = time.time()
    try:
        voice["proc"] = subprocess.Popen(["espeak-ng", "-v", "es", "-s", "150", "-a", "130", t],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass

def voice_watch():
    a, x = ui.get("alert"), xa.get("a")
    if a is not voice["alert"]:
        voice["alert"] = a
        if a:
            voice_say(f'{a.get("text", "")}. {a.get("sub", "")}')
    if x is not voice["xa"]:
        voice["xa"] = x
        if x:
            voice_say(f'{x.get("title", "")}. {x.get("big", "")}')

'''
rep("\ndef render(surf):", CODE + "\ndef render(surf):")

# la voz mira los avisos nuevos (muy barato: solo compara)
rep("    draw_xa(surf, now)\n", "    draw_xa(surf, now)\n    if cfg.get(\"voice\"):\n        voice_watch()\n")

# instantaneas para EMITIR, al mismo ritmo que la pantalla grande y solo si hay alguien mirando
rep('''            if BIG["n"] % 3 == 0:
                big_frame()
''', '''            if BIG["n"] % 3 == 0:
                big_frame()
                stream_snap(surf)
''')
rep('''    threading.Thread(target=udp_loop, daemon=True).start()''', '''    if cfg.get("stream"):
        stream_start()
    threading.Thread(target=udp_loop, daemon=True).start()''')

# OPCIONES: 6 botones (se anaden VOZ y EMITIR)
rep('''    items = [("CAMBIO AUTO", cfg["auto"]), ("ALERTAS", cfg["alerts"]), ("SONIDO", cfg["sound"]), ("COLOR", None)]
    for i, (name, on) in enumerate(items):
        r = grid(i, 2, 2)
        if on is None:
            draw_button(surf, r, name, THEMES[cfg["theme"]][0], F["big"], filled=True, lit=flash.get((124, i), 0) > now)
        else:
            draw_button(surf, r, name, "ACTIVADO" if on else "DESACTIVADO", F["big"], filled=on,
                        lit=flash.get((124, i), 0) > now)''',
'''    items = [("CAMBIO AUTO", cfg["auto"]), ("ALERTAS", cfg["alerts"]), ("SONIDO", cfg["sound"]), ("COLOR", None),
             ("VOZ", cfg.get("voice", False)), ("EMITIR", cfg.get("stream", False))]
    for i, (name, on) in enumerate(items):
        r = grid(i, 3, 2)
        lit = flash.get((124, i), 0) > now
        if on is None:
            draw_button(surf, r, name, THEMES[cfg["theme"]][0], F["btn"], filled=True, lit=lit)
            continue
        sub = "ACTIVADO" if on else "DESACTIVADO"
        if name == "VOZ" and not voice_ok():
            sub = "falta espeak-ng"
        if name == "EMITIR" and on:
            sub = stream["err"] or f"{my_ip()}:{STREAM_PORT}" + (f"  ({stream['clients']})" if stream["clients"] else "")
        draw_button(surf, r, name, sub, F["btn"], filled=on, lit=lit)''')
rep('''        for i, k in enumerate(["auto", "alerts", "sound", "theme"]):
            if grid(i, 2, 2).collidepoint(x, y):
                tap_flash((124, i))
                if k == "theme":
                    cfg["theme"] = (cfg["theme"] + 1) % len(THEMES); apply_theme()
                else:
                    cfg[k] = not cfg[k]
                    if k == "sound" and cfg[k]: play("ok")''',
'''        for i, k in enumerate(["auto", "alerts", "sound", "theme", "voice", "stream"]):
            if grid(i, 3, 2).collidepoint(x, y):
                tap_flash((124, i))
                if k == "theme":
                    cfg["theme"] = (cfg["theme"] + 1) % len(THEMES); apply_theme()
                else:
                    cfg[k] = not cfg.get(k, False)
                    if k == "sound" and cfg[k]: play("ok")
                    if k == "voice" and cfg[k]: voice["last"].clear(); voice_say("Voz de la nave activada")
                    if k == "stream" and cfg[k]: stream_start()''')

rep('    ("0.62", "Pantalla grande: modos 4 CUADROS, MIXTO y GRANDE (AJUSTES)"),\n',
    '    ("0.62", "Pantalla grande: modos 4 CUADROS, MIXTO y GRANDE (AJUSTES)"),\n'
    '    ("0.63", "EMITIR pantallas por la red (PC, OBS, VR) y VOZ de la nave"),\n')
s = re.sub(r'PANEL_VER = "v0\.62[^"]*"', 'PANEL_VER = "v0.63 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.63 EMITIR y VOZ  (copia en panel.py.bak62)")
