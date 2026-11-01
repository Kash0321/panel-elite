#!/usr/bin/env python3
# Parche v0.75: SONIDO Y VOZ uno a uno (bajas en silencio de entrada), "te atacan" a pie -> EN VIVO,
# mapa: el recorrido empieza al desplegar y modo ZONA (centrado en ti).
import re, shutil, sys, time
P = sys.argv[1] if len(sys.argv) > 1 else "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def snd_on" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.74' not in s:
    sys.exit("Este parche es para la v0.74")
shutil.copy(P, P + ".bak74")

def rep(old, new, all_=False):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new) if all_ else s.replace(old, new, 1)

# ---------- 1. SONIDO Y VOZ uno a uno ----------
rep('''def ev_on(k):''', '''SND_DEF = {"kill": False}      # de entrada en silencio: bajas y derribos (con sus creditos)

def snd_on(k):
    return not k or (cfg.get("snd") or {}).get(k, SND_DEF.get(k, True))

def ev_on(k):''')
rep('''    for master, store, L in (("alerts", "ev", EV_LIST), ("auto", "autoev", AUTO_LIST)):''',
    '''    for master, store, L in (("alerts", "ev", EV_LIST), ("auto", "autoev", AUTO_LIST), ("sound", "snd", EV_LIST)):''')
rep('''        if k == "a" and v is not None and XA_K[0] and not ev_on(XA_K[0]):
            return''', '''        if k == "a" and v is not None and XA_K[0] and not ev_on(XA_K[0]):
            return
        if k == "a" and isinstance(v, dict):
            v.setdefault("ev", XA_K[0])''')
rep('''def set_alert(text, sub="", col=None, secs=3.0, kind="red"):
    ui["alert"] = {"text": text, "sub": sub, "col": col or RED, "until": time.time() + secs, "kind": kind}''',
    '''def set_alert(text, sub="", col=None, secs=3.0, kind="red"):
    ui["alert"] = {"text": text, "sub": sub, "col": col or RED, "until": time.time() + secs, "kind": kind,
                   "ev": XA_K[0] or (kind if kind in ("galnet",) else None)}''')
rep('''def play(name):
    if XA_K[0] and not ev_on(XA_K[0]):
        return''', '''def play(name):
    if XA_K[0] and (not ev_on(XA_K[0]) or not snd_on(XA_K[0])):
        return''')
rep('''            handle_note(kind, text)
    gui = d.get("gui", 0)''', '''            if kind == "deploy":                       # el mapa empieza al bajar del transporte
                track.update(pts=[], kills=[], items=[], last=None)
            XA_K[0] = kind
            try:
                handle_note(kind, text)
            finally:
                XA_K[0] = None
    gui = d.get("gui", 0)''')
rep('''    a, x = ui.get("alert"), xa.get("a")
    if a is not voice["alert"]:
        voice["alert"] = a
        if a:''', '''    a, x = ui.get("alert"), xa.get("a")
    if a is not voice["alert"]:
        voice["alert"] = a
        if a and snd_on(a.get("ev")):''')
rep('''    if x is not voice["xa"]:
        voice["xa"] = x
        if x:''', '''    if x is not voice["xa"]:
        voice["xa"] = x
        if x and snd_on(x.get("ev")):''')

# listas: 161 ALERTAS, 162 CAMBIO AUTO, 163 SONIDO Y VOZ
rep('''def _evl(v):
    return (EV_LIST, "ev", "evpage") if v == 161 else (AUTO_LIST, "autoev", "autopage")''',
    '''EVL = {161: (EV_LIST, "ev", "evpage", "alerts", {}), 162: (AUTO_LIST, "autoev", "autopage", "auto", {}),
       163: (EV_LIST, "snd", "sndpage", "sound", SND_DEF)}

def _evl(v):
    return EVL[v][:3]''')
rep('''    n = sum(1 for k, _ in L if on.get(k, True))''', '''    df = EVL[v][4]
    n = sum(1 for k, _ in L if on.get(k, df.get(k, True)))''')
rep('''filled=on.get(k, True),''', '''filled=on.get(k, df.get(k, True)),''')
rep('''                cfg["alerts" if v == 161 else "auto"] = True
                save_cfg()''', '''                cfg[EVL[v][3]] = True
                save_cfg()''')
rep('''            on[k] = not on.get(k, True)
            cfg["alerts" if v == 161 else "auto"] = True''', '''            on[k] = not on.get(k, EVL[v][4].get(k, True))
            cfg[EVL[v][3]] = True''')
rep('''VIEWS[162] = view_evlist''', '''VIEWS[162] = view_evlist
VIEWS[163] = view_evlist
MENU[163] = "SONIDO Y VOZ"
PARENT[163] = 1244''')
rep('''    elif v in (161, 162):''', '''    elif v in (161, 162, 163):''')
# OPCIONES
rep('''        if name in ("ALERTAS", "CAMBIO AUTO"):
            L, st = (EV_LIST, "ev") if name == "ALERTAS" else (AUTO_LIST, "autoev")
            n = sum(1 for k, _ in L if (cfg.get(st) or {}).get(k, True)) if on else 0''',
    '''        if name in ("ALERTAS", "CAMBIO AUTO", "SONIDO"):
            L, st, _, _, df = EVL[{"ALERTAS": 161, "CAMBIO AUTO": 162, "SONIDO": 163}[name]]
            n = sum(1 for k, _ in L if (cfg.get(st) or {}).get(k, df.get(k, True))) if on else 0''')
rep('''                if k in ("alerts", "auto"):
                    ui["view"] = 161 if k == "alerts" else 162; return''', '''                if k in ("alerts", "auto", "sound"):
                    ui["view"] = {"alerts": 161, "auto": 162, "sound": 163}[k]; return''')

# ---------- 2. "te atacan" a pie -> EN VIVO (combate a pie) ----------
rep('''    if kind in AUTO_VIEW and auto_on(kind):
        ui["view"] = AUTO_VIEW[kind]''', '''    if kind in AUTO_VIEW and auto_on(kind):
        ui["view"] = AUTO_VIEW[kind]
        if kind in ("underattack", "interdicted") and ((state.get("data") or {}).get("Flags2", 0) & 1):
            ui["view"] = 100''')

# ---------- 3. mapa: sin el vuelo del transporte y modo ZONA ----------
rep('''    out = (d.get("Flags2", 0) & 1) or (d.get("Flags", 0) & (1 << 26))
    if not out:''', '''    out = (d.get("Flags2", 0) & 1) or (d.get("Flags", 0) & (1 << 26))
    if not out or d.get("Flags2", 0) & 2:              # en taxi o en el transporte no se apunta''')
rep('''    if track["zoom"]:
        minx, maxx, miny, maxy = -100, 100, -100, 100
    else:''', '''    zm = track["zoom"] % 3
    if zm == 1:
        minx, maxx, miny, maxy = -100, 100, -100, 100
    elif zm == 0:
        # ZONA: centrado en ti, con lo ultimo que has recorrido y las ultimas bajas (sin puntos lejanos sueltos)
        rec = trail[-150:] + [m[1] for m in marks if m[0] == "kill"][-30:]
        far = [max(abs(p[0]), abs(p[1])) for p in rec]
        far = sorted(f_ for f_ in far if f_ < 1500)
        ext = far[int(len(far) * 0.95)] if far else 50
        ext = max(ext, 50)
        minx, maxx, miny, maxy = -ext, ext, -ext, ext
    else:''')
rep('''    put(surf, fs, ("CERCA (100 m)" if track["zoom"] else "TODO EL RECORRIDO") + "  ·  toca para cambiar",''',
    '''    put(surf, fs, ("ZONA", "CERCA (100 m)", "TODO EL RECORRIDO")[track["zoom"] % 3] + "  ·  toca para cambiar",''')
rep('''    track["zoom"] = 1 - track["zoom"]''', '''    track["zoom"] = (track["zoom"] + 1) % 3''')

# --- manual
rep('''- SONIDO: los pitidos (alarma, salto y "ok").''',
    '''- SONIDO: los pitidos (alarma, salto y "ok"). Al tocarlo sale la lista SONIDO Y VOZ: elige uno a uno qué avisos pitan y hablan (relleno = suena). Uno apagado aquí se sigue viendo, pero en silencio. De entrada BAJA / DERRIBO va en silencio.''')

rep('    ("0.74", "Merc Coin rosa, PANEL nítido, teclas en la web, FPS, fecha del juego, plataforma exacta"),\n',
    '    ("0.74", "Merc Coin rosa, PANEL nítido, teclas en la web, FPS, fecha del juego, plataforma exacta"),\n'
    '    ("0.75", "SONIDO Y VOZ uno a uno (bajas en silencio); te atacan a pie > EN VIVO; mapa ZONA"),\n')
s = re.sub(r'PANEL_VER = "v0\.74[^"]*"', 'PANEL_VER = "v0.75 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.75  (copia en " + P + ".bak74)")
