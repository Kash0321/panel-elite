#!/usr/bin/env python3
# Parche v0.56: 12.10 OBJETIVOS COMUNITARIOS (web oficial + los tuyos del journal) y en la pantalla grande ATRACADO
import re, shutil, sys, time
P = "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def view_cgoals" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.55' not in s:
    sys.exit("Este parche es para la v0.55")
shutil.copy(P, P + ".bak55")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

CODE = r'''
# ---------- 12.10 objetivos comunitarios ----------
CG_URL = "https://api.orerve.net/2.0/website/initiatives/list?lang=es"
cgoals = {"list": [], "t": 0, "err": "", "page": 0, "d": None}

def _first(it, *keys):
    for k in keys:
        v = it.get(k)
        if v not in (None, "", []):
            return v
    return None

def _num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None

def cg_fetch():
    import urllib.request
    req = urllib.request.Request(CG_URL, headers={"User-Agent": "PanelElite/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    items = data.get("activeInitiatives") if isinstance(data, dict) else data
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        out.append({"title": str(_first(it, "title", "name") or "?"),
                    "sys": str(_first(it, "starsystem_name", "system_name", "systemName", "system") or ""),
                    "market": str(_first(it, "market_name", "marketName", "station_name", "station") or ""),
                    "expiry": str(_first(it, "expiry", "end_date", "endDate", "expires") or ""),
                    "qty": _num(_first(it, "qty", "current_qty", "progress", "current")),
                    "target": _num(_first(it, "target_qty", "targetQty", "target")),
                    "text": galnet_text(str(_first(it, "objective", "bulletin", "description") or ""))[:300]})
    return out

def cg_loop():
    while True:
        try:
            cgoals["list"], cgoals["t"], cgoals["err"] = cg_fetch(), time.time(), ""
            time.sleep(1800)
        except Exception as e:
            cgoals["err"] = str(e)[:60]
            print("objetivos:", e, flush=True)
            time.sleep(600)

threading.Thread(target=cg_loop, daemon=True).start()

def cg_all(d):
    mine = [dict(g, me=True) for g in ((d or {}).get("mycg") or [])]
    names = {g["title"].lower() for g in mine}
    return mine + [g for g in cgoals["list"] if g["title"].lower() not in names]

def cg_left(exp):
    import calendar
    e = (exp or "").replace("Z", "")
    for txt, fmt in ((e[:19], "%Y-%m-%dT%H:%M:%S"), (e[:19], "%Y-%m-%d %H:%M:%S"), (e[:10], "%Y-%m-%d")):
        try:
            sec = calendar.timegm(time.strptime(txt, fmt)) - time.time()
            break
        except ValueError:
            continue
    else:
        return exp[:16]
    if sec <= 0:
        return "terminado"
    dd, hh = int(sec // 86400), int(sec % 86400 // 3600)
    return f"quedan {dd}d {hh}h" if dd else f"quedan {hh}h {int(sec % 3600 // 60)}m"

def _tier(t):
    m = re.search(r"\d+", t or "")
    return int(m.group()) if m else None

CG_PER = 2
CG_PAGE = pygame.Rect(W - 118, TOP + 2, 110, 28)

def view_cgoals(surf, d, flags, now):
    cgoals["d"] = d
    L = cg_all(d)
    pages = max(1, (len(L) + CG_PER - 1) // CG_PER)
    pg = cgoals["page"] % pages
    if cgoals["err"] and not L:
        info, col = cgoals["err"], RED
    elif cgoals["t"]:
        info, col = f"{len(L)} activo{'s' if len(L) != 1 else ''} · actualizado " + time.strftime("%H:%M", time.localtime(cgoals["t"])), DIM
    else:
        info, col = "descargando...", DIM
    put(surf, F["small"], info, (8, TOP + 9), col, W - 140)
    if pages > 1:
        draw_button(surf, CG_PAGE, f"PÁG {pg + 1}/{pages} >", None, F["small"])
    if not L:
        put(surf, F["btn"], "No hay objetivos comunitarios activos", (W // 2, (H + TOP) // 2), DIM, anchor="center")
        return
    for i, g in enumerate(L[pg * CG_PER:(pg + 1) * CG_PER]):
        r = pygame.Rect(6, TOP + 34 + i * 116, W - 12, 110)
        me = g.get("me")
        pygame.draw.rect(surf, GREEN if me else DIM, r, 1, border_radius=5)
        put(surf, F["btn"], g["title"], (r.x + 8, r.y + 4), ORANGE, r.w - 16)
        where = " · ".join(x for x in (g.get("sys", "").upper(), g.get("market", "")) if x)
        put(surf, F["small"], where, (r.x + 8, r.y + 24), WHITE, r.w - 140)
        left = "COMPLETADO" if g.get("complete") else cg_left(g.get("expiry", ""))
        put(surf, F["small"], left, (r.right - 8, r.y + 24), GREEN if g.get("complete") else BLUE, anchor="topright")
        bar = pygame.Rect(r.x + 8, r.y + 44, r.w - 16, 14)
        pygame.draw.rect(surf, DIM, bar, 1)
        t, top = _tier(g.get("tier")), _tier(g.get("top"))
        if t is not None and top:
            pct, txt = min(1.0, t / top), f"NIVEL {t} de {top}"
        elif g.get("qty") is not None and g.get("target"):
            pct = min(1.0, g["qty"] / g["target"]); txt = f"{fnum(g['qty'], 0)} / {fnum(g['target'], 0)}"
        else:
            pct, txt = None, ""
        if pct is not None:
            pygame.draw.rect(surf, GREEN if me else ORANGE, (bar.x + 2, bar.y + 2, int((bar.w - 4) * pct), bar.h - 4))
        put(surf, F["small"], txt, (r.x + 8, r.y + 62), GREEN if me else ORANGE)
        if me:
            if g.get("contrib"):
                put(surf, F["small"], f"{fnum(g['contrib'], 0)} pilotos", (r.right - 8, r.y + 62), DIM, anchor="topright")
            mine = f"TU APORTACIÓN: {fnum(g.get('mine') or 0, 0)}"
            if g.get("band"):
                mine += f"   ·   estás en el {g['band']}% mejor"
            if g.get("toprank"):
                mine += "   ·   TOP"
            put(surf, F["small"], mine, (r.x + 8, r.y + 82), GREEN, r.w - 16)
        elif g.get("text"):
            put(surf, F["small"], g["text"].replace("\n", " "), (r.x + 8, r.y + 82), DIM, r.w - 16)

VIEWS[132] = view_cgoals
MENU[132] = "OBJETIVOS COMUNITARIOS"
PARENT[132] = 12

'''
rep("\ndef render(surf):", CODE + "\ndef render(surf):")

# menu 12: boton 10
rep('("8", "NOTAS"), ("9", "GALNET")]):', '("8", "NOTAS"), ("9", "GALNET"), ("10", "OBJ. COM.")]):')
rep('''        for i in range(9):
            if grid(i, 4, 3).collidepoint(x, y):
                tap_flash((12, i)); ui["view"] = 121 + i if i < 8 else 130; return''',
    '''        for i in range(10):
            if grid(i, 4, 3).collidepoint(x, y):
                tap_flash((12, i)); ui["view"] = 121 + i if i < 8 else (130 if i == 8 else 132); return''')
rep("    elif v in (130, 131):\n", "    elif v == 132:\n        cgoals[\"page\"] += 1; return\n    elif v in (130, 131):\n")

# pantalla grande: objetivos en la rotacion del cuadro GALNET
rep('    if 132 in VIEWS and (globals().get("cgoals") or {}).get("list"):', '    if 132 in VIEWS and cg_all(d):')

# aviso al subir de nivel un objetivo en el que participas
rep('        elif kind == "gravity" and len(p) >= 2:\n',
    '        elif kind == "cg" and len(p) >= 2:\n'
    '            xa["a"] = dict(until=now + 6, col=GREEN, title="OBJETIVO COMUNITARIO", big=p[1].upper(), lines=[p[0]])\n'
    '        elif kind == "gravity" and len(p) >= 2:\n')

rep('    ("0.55", "Pantalla grande ATRACADO: GALNET y carga/misión; fecha del juego"),\n',
    '    ("0.55", "Pantalla grande ATRACADO: GALNET y carga/misión; fecha del juego"),\n'
    '    ("0.56", "12.10 Objetivos comunitarios (web y los tuyos)"),\n')
s = re.sub(r'PANEL_VER = "v0\.55[^"]*"', 'PANEL_VER = "v0.56 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.56 objetivos comunitarios  (copia en panel.py.bak55)")
