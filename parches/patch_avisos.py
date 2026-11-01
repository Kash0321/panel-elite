#!/usr/bin/env python3
# Parche v0.73: AVISOS uno a uno y CAMBIO AUTO uno a uno (AJUSTES > OPCIONES). NITIDEZ ALTA por defecto.
import re, shutil, sys, time
P = sys.argv[1] if len(sys.argv) > 1 else "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def view_evlist" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.72' not in s:
    sys.exit("Este parche es para la v0.72")
shutil.copy(P, P + ".bak72")

def rep(old, new, all_=False):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new) if all_ else s.replace(old, new, 1)

# --- NITIDEZ ALTA por defecto
rep('cfg = {"auto": True, "alerts": True,', 'cfg = {"sharp": True, "auto": True, "alerts": True,')

# --- funciones (antes de set_alert, para que existan pronto)
rep('''def set_alert(text, sub="", col=None, secs=3.0, kind="red"):''', r'''# avisos uno a uno: cfg["ev"][clave] = False lo apaga (lo que no esta en la lista sale siempre)
EV_LIST = [("jump", "SALTO"), ("interdicted", "INTERDICCIÓN"), ("underattack", "TE ATACAN"),
           ("shields_down", "ESCUDOS CAÍDOS"), ("shields_up", "ESCUDOS ARRIBA"), ("hull", "CASCO DAÑADO"),
           ("heat", "SOBRECALENTAMIENTO"), ("rebuy", "CASCO CRÍTICO"), ("died", "HAS CAÍDO / DESTRUIDA"),
           ("hplow", "SALUD BAJA (A PIE)"), ("oxy", "POCO OXÍGENO"), ("temp", "FRÍO / CALOR"),
           ("srvfuel", "COMBUSTIBLE SRV"), ("gravity", "GRAVEDAD ALTA"), ("fuelroute", "RUTA COMBUSTIBLE"),
           ("jetcone", "FSD SOBREALIMENT."), ("jetdmg", "DAÑO EN EL FSD"), ("arrive", "LLEGADA / SEÑAL"),
           ("newsys", "SIN EXPLORAR"), ("honk", "ESCANEO SISTEMA"), ("find", "HALLAZGO VALIOSO"),
           ("codex", "CÓDICE"), ("risk", "DATOS EN RIESGO"), ("matfull", "MATERIAL AL MÁX."),
           ("alien", "SEÑALES ALIEN"), ("tgwar", "GUERRA THARGOIDE"), ("shutdown", "APAGÓN THARGOIDE"),
           ("wanted", "OBJETIVO BUSCADO"), ("cmdrtarget", "CMDR FIJADO"), ("kill", "BAJA / DERRIBO"),
           ("escaped", "ESCAPADO"), ("submitted", "SOMETIDO"), ("crime", "DELITO"),
           ("dropship", "TRANSPORTE ZONA"), ("deploy", "DESPLEGADO"), ("thrown", "GRANADA LANZADA"),
           ("pickup", "RECOGIDO"), ("usecons", "CONSUMIBLE USADO"), ("lowcons", "QUEDAN POCOS"),
           ("redeem", "COBRADO"), ("opstart", "OPERACIÓN INICIADA"), ("opend", "OPERACIÓN TERMINADA"),
           ("missionexp", "MISIÓN CADUCA"), ("missionhere", "ENTREGA AQUÍ"), ("taxi", "TAXI"),
           ("settle", "ASENTAMIENTO"), ("sessend", "FIN DE SESIÓN"), ("friend", "AMIGOS"),
           ("wing", "ALA"), ("cg", "OBJ. COMUNITARIO"), ("galnet", "NOTICIA GALNET"), ("power", "BAJA TENSIÓN")]
# cambio automatico de menu uno a uno: cfg["autoev"][clave] = False
AUTO_LIST = [("docking", "ATRAQUE > ESTACIÓN"), ("market", "MERCADO"), ("interdicted", "INTERDICCIÓN > COMBATE"),
             ("underattack", "TE ATACAN > COMBATE"), ("arrsig", "SEÑAL PELIGROSA > COMBATE"),
             ("arrst", "LLEGADA > ESTACIÓN"), ("prospector", "PROSPECTOR > MINERÍA"), ("srv", "SRV"),
             ("fighter", "CAZA"), ("embark", "EMBARCAR > EN VIVO"), ("foot", "A PIE > EN VIVO"),
             ("fss", "FSS > SISTEMA")]
XA_K = [None]          # aviso que se esta procesando (para apagarlo y silenciarlo)

def ev_on(k):
    return cfg.get("alerts", True) and (cfg.get("ev") or {}).get(k, True)

def auto_on(k):
    return cfg.get("auto", True) and (cfg.get("autoev") or {}).get(k, True)

def ev_migrate():
    # antes ALERTAS / CAMBIO AUTO eran un solo interruptor: si estaba apagado, se apagan todos
    for master, store, L in (("alerts", "ev", EV_LIST), ("auto", "autoev", AUTO_LIST)):
        if not cfg.get(master, True):
            cfg[store] = {k: False for k, _ in L}
            cfg[master] = True
            save_cfg()

class XaDict(dict):
    def __setitem__(self, k, v):
        if k == "a" and v is not None and XA_K[0] and not ev_on(XA_K[0]):
            return
        dict.__setitem__(self, k, v)

def set_alert(text, sub="", col=None, secs=3.0, kind="red"):''')

rep('''def play(name):
''', '''def play(name):
    if XA_K[0] and not ev_on(XA_K[0]):
        return
''')

# --- avisos de handle_note y cambio automatico
rep('''    if cfg["auto"] and kind in AUTO_VIEW:
        ui["view"] = AUTO_VIEW[kind]
    if not cfg["alerts"]:
        return''', '''    if kind in AUTO_VIEW and auto_on(kind):
        ui["view"] = AUTO_VIEW[kind]
    if not ev_on(kind):
        return''')
rep('''    if gui == 9 and ui["gui"] != 9 and cfg["auto"]:''', '''    if gui == 9 and ui["gui"] != 9 and auto_on("fss"):''')
rep('''                if cfg["auto"]:
                    ui["view"] = 8''', '''                if auto_on("arrst"):
                    ui["view"] = 8''')
rep('''                    if cfg["auto"]:
                        ui["view"] = 6''', '''                    if auto_on("arrsig"):
                        ui["view"] = 6''')

# --- avisos superpuestos (xa_notes)
rep('xa = {"seq": None, "a": None}', 'xa = XaDict({"seq": None, "a": None})')
rep('''def xa_notes(d, now):
    if not d:
        return
''', '''def xa_notes(d, now):
    try:
        _xa_notes(d, now)
    finally:
        XA_K[0] = None

def _xa_notes(d, now):
    if not d:
        return
    XA_K[0] = "hplow"
''')
rep('''        if lvl > prev and cfg["alerts"]:''', '''        if lvl > prev:''')
rep('''    for k, on in conds.items():
        if on and not dg.get(k):
''', '''    for k, on in conds.items():
        if on and not dg.get(k):
            XA_K[0] = {"hp": "hplow", "cold": "temp", "hot": "temp", "fuel": "srvfuel"}.get(k, k)
''')
rep('''        xa["seq"] = seq
        p = (text or "").split("|")''', '''        xa["seq"] = seq
        XA_K[0] = kind
        p = (text or "").split("|")''')

# --- GALNET y baja tension
rep('''                    if cfg["alerts"]:
                        set_alert("NUEVA NOTICIA GALNET"''', '''                    if ev_on("galnet"):
                        set_alert("NUEVA NOTICIA GALNET"''')
rep('''time.time() - power["warned"] > 600 and cfg["alerts"]:''', '''time.time() - power["warned"] > 600 and ev_on("power"):''')

# --- arranque
rep('''    load_cfg()
''', '''    load_cfg()
    ev_migrate()
''', all_=True)

# --- OPCIONES: ALERTAS y CAMBIO AUTO abren sus listas
rep('''        sub = "ACTIVADO" if on else "DESACTIVADO"
''', '''        sub = "ACTIVADO" if on else "DESACTIVADO"
        if name in ("ALERTAS", "CAMBIO AUTO"):
            L, st = (EV_LIST, "ev") if name == "ALERTAS" else (AUTO_LIST, "autoev")
            n = sum(1 for k, _ in L if (cfg.get(st) or {}).get(k, True)) if on else 0
            on = n > 0
            sub = f"{n} de {len(L)}  >"
''')
rep('''                if k == "theme":
                    cfg["theme"] = (cfg["theme"] + 1) % len(THEMES); apply_theme()''', '''                if k in ("alerts", "auto"):
                    ui["view"] = 161 if k == "alerts" else 162; return
                if k == "theme":
                    cfg["theme"] = (cfg["theme"] + 1) % len(THEMES); apply_theme()''')

CODE = r'''
# ---------- AJUSTES > OPCIONES > ALERTAS (161) y CAMBIO AUTO (162): uno a uno ----------
EVPP = 12

def _evl(v):
    return (EV_LIST, "ev", "evpage") if v == 161 else (AUTO_LIST, "autoev", "autopage")

def view_evlist(surf, d, flags, now):
    v = ui["view"]
    L, st, pk = _evl(v)
    pages = (len(L) + EVPP - 1) // EVPP
    pg = ui.get(pk, 0) % pages
    on = cfg.get(st) or {}
    n = sum(1 for k, _ in L if on.get(k, True))
    top = [("TODOS ON", None), ("TODOS OFF", None), (f"PÁG {pg + 1}/{pages}" if pages > 1 else f"{n} de {len(L)}", None)]
    for i, (t, _) in enumerate(top):
        draw_button(surf, grid(i, 3, 1, TOP, TOP + 40), t, None, F["btn"], lit=flash.get((v, 100 + i), 0) > now)
    for i, (k, name) in enumerate(L[pg * EVPP:(pg + 1) * EVPP]):
        r = grid(i, 2, 6, TOP + 38, H)
        draw_button(surf, r, name, None, F["small"] if len(name) > 17 else F["btn"], filled=on.get(k, True),
                    lit=flash.get((v, i), 0) > now)

def tap_evlist(x, y):
    v = ui["view"]
    L, st, pk = _evl(v)
    pages = (len(L) + EVPP - 1) // EVPP
    pg = ui.get(pk, 0) % pages
    on = cfg.setdefault(st, {})
    for i in range(3):
        if grid(i, 3, 1, TOP, TOP + 40).collidepoint(x, y):
            tap_flash((v, 100 + i))
            if i < 2:
                for k, _ in L:
                    on[k] = i == 0
                cfg["alerts" if v == 161 else "auto"] = True
                save_cfg()
            else:
                ui[pk] = pg + 1
            return
    for i, (k, _) in enumerate(L[pg * EVPP:(pg + 1) * EVPP]):
        if grid(i, 2, 6, TOP + 38, H).collidepoint(x, y):
            tap_flash((v, i))
            on[k] = not on.get(k, True)
            cfg["alerts" if v == 161 else "auto"] = True
            save_cfg()
            return

VIEWS[161] = view_evlist
VIEWS[162] = view_evlist
MENU[161] = "ALERTAS"
MENU[162] = "CAMBIO AUTO"
PARENT[161] = 1244
PARENT[162] = 1244

'''
rep("\ndef render(surf):", CODE + "\ndef render(surf):")
rep('''    elif v == 160:
        tap_pantalla(x, y); return''', '''    elif v == 160:
        tap_pantalla(x, y); return
    elif v in (161, 162):
        tap_evlist(x, y); return''')

# --- manual
rep('''Con CAMBIO AUTO (OPCIONES) el panel salta solo a la pantalla útil: al atracar, al lanzar el SRV, si te interdictan o te atacan...''',
    '''Con CAMBIO AUTO (OPCIONES) el panel salta solo a la pantalla útil: al atracar, al lanzar el SRV, si te interdictan o te atacan...
- Toca CAMBIO AUTO para elegir uno a uno qué cambios quieres (verde = activo). TODOS ON / TODOS OFF arriba.''')
rep('''- ALERTAS: los avisos a pantalla completa.''',
    '''- ALERTAS: los avisos a pantalla completa. Al tocarlo sale la lista de todos los avisos, por páginas: toca cada uno para activarlo o apagarlo (relleno = activo). Un aviso apagado tampoco suena ni lo dice la voz. TODOS ON / TODOS OFF arriba; PÁG pasa de página.''')

rep('    ("0.72", "NITIDEZ ALTA: pantalla grande a 1024x600 real (AJUSTES > PANTALLA)"),\n',
    '    ("0.72", "NITIDEZ ALTA: pantalla grande a 1024x600 real (AJUSTES > PANTALLA)"),\n'
    '    ("0.73", "ALERTAS y CAMBIO AUTO uno a uno (OPCIONES); NITIDEZ ALTA por defecto"),\n')
s = re.sub(r'PANEL_VER = "v0\.72[^"]*"', 'PANEL_VER = "v0.73 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.73 avisos uno a uno  (copia en " + P + ".bak72)")
