#!/usr/bin/env python3
# Parche v0.60: paquetes comprimidos del sender, registro de errores (panel.log y LOG), arranque mas rapido,
# aviso de SISTEMAS APAGADOS (encuentro thargoide)
import re, shutil, sys, time
P = "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def plog" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.59' not in s:
    sys.exit("Este parche es para la v0.59")
shutil.copy(P, P + ".bak59")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

# 1) paquetes comprimidos ("Z" + zlib) y datos pesados que solo llegan cuando cambian
rep('''        pkt, _ = s.recvfrom(65535)
        try:
            d = json.loads(pkt)
        except Exception:
            continue
''', '''        pkt, _ = s.recvfrom(65535)
        try:
            if pkt[:1] == b"Z":
                import zlib
                pkt = zlib.decompress(pkt[1:])
            d = json.loads(pkt)
        except Exception:
            continue
''')
rep('''            else:
                state["data"] = d
                state["rx"] = time.time()
''', '''            else:
                old = state["data"] or {}
                for k, v in old.items():          # lo que no ha cambiado no viene: se conserva
                    if k not in d:
                        d[k] = v
                state["data"] = d
                state["rx"] = time.time()
''')

# 2) arranque: los sonidos se generan solo la primera vez
rep('''    def tone(path, parts):
        with wave.open(path, "w") as w:''', '''    def tone(path, parts):
        import os as _os
        if _os.path.exists(path) and _os.path.getsize(path) > 1000:
            return
        with wave.open(path, "w") as w:''')
rep('''def main():
    load_cfg()
''', '''def main():
    T0 = time.time()
    load_cfg()
''')
rep('''    print("Framebuffer", dev, bpp, "bpp")
    threading.Thread(target=udp_loop, daemon=True).start()''', '''    print("Framebuffer", dev, bpp, "bpp")
    print(f"Panel {PANEL_VER.split(' · ')[0]} listo en {time.time() - T0:.1f} s")
    threading.Thread(target=udp_loop, daemon=True).start()''')

CODE = r'''
# ---------- registro de errores: /home/ortem/panel.log y pantalla LOG ----------
import builtins, traceback, os as _os
PANEL_LOG = "/home/ortem/panel.log"
_err_seen = {}

def plog(*a, **k):
    msg = " ".join(str(x) for x in a)
    builtins.print(msg, flush=True)
    try:
        if _os.path.exists(PANEL_LOG) and _os.path.getsize(PANEL_LOG) > 300000:
            _os.replace(PANEL_LOG, PANEL_LOG + ".1")
        with open(PANEL_LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%d/%m %H:%M:%S ") + msg + "\n")
    except OSError:
        pass
    if lock.acquire(timeout=0.2):
        try:
            state["log"].append("[PANEL] " + msg)
        finally:
            lock.release()

print = plog

def log_exc(where, e):
    key = (where, type(e).__name__, str(e)[:80])
    if time.time() - _err_seen.get(key, 0) > 300:          # el mismo error, como mucho cada 5 min
        _err_seen[key] = time.time()
        plog(f"ERROR en {where}: {e}\n" + "".join(traceback.format_exc().splitlines(True)[-4:]))

sys_excepthook = None
def _hook(t, e, tb):
    plog("ERROR GRAVE: " + "".join(traceback.format_exception(t, e, tb)))
import sys as _sys
_sys.excepthook = _hook
threading.excepthook = lambda a: plog(f"ERROR en hilo {a.thread.name if a.thread else '?'}: " +
                                       "".join(traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback)))

'''
rep("\ndef render(surf):", CODE + "\ndef render(surf):")

# una pantalla con fallo ya no tumba el panel: se muestra el aviso y se apunta
rep('''    fn = VIEWS.get(v)
    if fn:
        fn(surf, d if online else None, flags, now)
    else:''', '''    fn = VIEWS.get(v)
    if fn:
        try:
            fn(surf, d if online else None, flags, now)
        except Exception as e:
            log_exc(f"pantalla {v}", e)
            put(surf, F["btn"], "Error en esta pantalla", (W // 2, (H + TOP) // 2 - 10), RED, anchor="center")
            put(surf, F["small"], "está apuntado en 12 AJUSTES > LOG", (W // 2, (H + TOP) // 2 + 14), DIM, anchor="center")
    else:''')

# los mensajes del panel en rojo en la pantalla LOG
rep("        surf.blit(f.render(r, True, ORANGE), (4, TOP + 2 + j * lh))",
    "        surf.blit(f.render(r, True, RED if r.startswith(\"[PANEL]\") else ORANGE), (4, TOP + 2 + j * lh))")

# 4) aviso de sistemas apagados (encuentro thargoide)
rep('        elif kind == "gravity" and len(p) >= 2:\n',
    '        elif kind == "shutdown":\n'
    '            xa["a"] = dict(until=now + 8, col=(120, 230, 120), title="¡SISTEMAS APAGADOS!", big="ENCUENTRO THARGOIDE",\n'
    '                           lines=["la nave se reiniciará en unos segundos"])\n'
    '            play("alarm")\n'
    '        elif kind == "gravity" and len(p) >= 2:\n')

rep('    ("0.59", "Optimización de pantallas y aviso de BAJA TENSIÓN"),\n',
    '    ("0.59", "Optimización de pantallas y aviso de BAJA TENSIÓN"),\n'
    '    ("0.60", "Datos comprimidos, registro de errores, arranque y aviso thargoide"),\n')
s = re.sub(r'PANEL_VER = "v0\.59[^"]*"', 'PANEL_VER = "v0.60 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.60  (copia en panel.py.bak59)")
