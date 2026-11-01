#!/usr/bin/env python3
# Parche v0.68: MAPA de recorrido a pie / SRV / Rhino (pestana MAPA en el menu 5, SUPERFICIE y COMBATE A PIE)
import re, shutil, sys, time
P = "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def draw_map" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.67' not in s:
    sys.exit("Este parche es para la v0.67")
shutil.copy(P, P + ".bak67")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

CODE = r'''
# ---------- MAPA de recorrido (a pie, SRV y Rhino sobre un planeta) ----------
track = {"body": None, "pts": [], "kills": [], "last": None, "zoom": 0}
TRACK_MAX, TRACK_STEP = 2000, 3.0          # puntos guardados como mucho / metros entre puntos

def track_update(d, now):
    b = (d or {}).get("bio") or {}
    lat, lon, R = b.get("lat"), b.get("lon"), b.get("R")
    if lat is None or not R:
        return
    body = (d or {}).get("body") or b.get("body")
    if body != track["body"]:                          # otro planeta: mapa nuevo
        track.update(body=body, pts=[], kills=[], last=None)
    out = (d.get("Flags2", 0) & 1) or (d.get("Flags", 0) & (1 << 26))
    if not out:
        return
    if track["last"] is None or hav(track["last"], (lat, lon), R) >= TRACK_STEP:
        track["pts"].append((lat, lon))
        track["last"] = (lat, lon)
        del track["pts"][:-TRACK_MAX]

def track_kill():
    with lock:
        d = state["data"]
    b = (d or {}).get("bio") or {}
    if b.get("lat") is not None:
        track["kills"].append((b["lat"], b["lon"]))
        del track["kills"][:-200]

MAP_STEPS = (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000)

def fmt_m(m):
    return f"{m / 1000:g} km".replace(".", ",") if m >= 1000 else f"{m:g} m"

def draw_map(surf, r, d, now):
    d = d or {}
    b = d.get("bio") or {}
    lat, lon, R = b.get("lat"), b.get("lon"), b.get("R")
    fs = F["small"]
    if lat is None or not R:
        put(surf, F["btn"], "Sin posición en un planeta", (r.centerx, r.centery - 10), DIM, r.w - 16, anchor="center")
        put(surf, fs, "El mapa funciona a pie, en SRV o en Rhino sobre un planeta", (r.centerx, r.centery + 12),
            DIM, r.w - 16, anchor="midtop")
        return
    k = math.cos(math.radians(lat))
    def xy(p):
        return (R * math.radians(p[1] - lon) * k, R * math.radians(p[0] - lat))
    trail = [xy(p) for p in track["pts"]]
    marks = []
    ship = ship_pos(b)
    if ship:
        marks.append(("ship", xy(ship)))
    sp = (d.get("footcz") or {}).get("spos")
    if sp and (not sp[2] or sp[2] == d.get("body")):
        marks.append(("base", xy(sp)))
    marks += [("kill", xy(p)) for p in track["kills"]]
    marks += [("bio", xy(p)) for p in (b.get("pts") or []) if p]
    me = (0.0, 0.0)
    if track["zoom"]:
        minx, maxx, miny, maxy = -100, 100, -100, 100
    else:
        allp = trail + [m[1] for m in marks] + [me]
        minx, maxx = min(p[0] for p in allp), max(p[0] for p in allp)
        miny, maxy = min(p[1] for p in allp), max(p[1] for p in allp)
    w_, h_ = max(maxx - minx, 40), max(maxy - miny, 40)
    cx_, cy_ = (minx + maxx) / 2, (miny + maxy) / 2
    sc = min(r.w / (w_ * 1.25), r.h / (h_ * 1.25))
    def scr(p):
        return (int(r.centerx + (p[0] - cx_) * sc), int(r.centery - (p[1] - cy_) * sc))
    span = max(r.w, r.h) / sc
    step = next((s_ for s_ in MAP_STEPS if span / s_ <= 8), MAP_STEPS[-1])
    old = surf.get_clip()
    surf.set_clip(r)
    gc = tuple(max(18, c // 3) for c in DIM[:3])
    gx = math.floor((cx_ - r.w / 2 / sc) / step) * step
    while scr((gx, 0))[0] <= r.right:
        x = scr((gx, 0))[0]
        pygame.draw.line(surf, gc, (x, r.y), (x, r.bottom))
        gx += step
    gy = math.floor((cy_ - r.h / 2 / sc) / step) * step
    while scr((0, gy))[1] >= r.y:
        y = scr((0, gy))[1]
        pygame.draw.line(surf, gc, (r.x, y), (r.right, y))
        gy += step
    pts = [scr(p) for p in trail] + [scr(me)]
    n = len(pts)
    for i in range(1, n):
        f_ = 0.25 + 0.75 * i / n                        # lo antiguo se va apagando
        pygame.draw.line(surf, tuple(int(c * f_) for c in ORANGE[:3]), pts[i - 1], pts[i], 2)
    for kind, p in marks:
        x, y = scr(p)
        if kind == "ship":
            pygame.draw.polygon(surf, ORANGE, [(x, y - 8), (x + 7, y), (x, y + 8), (x - 7, y)])
            put(surf, fs, "NAVE", (x + 10, y - 7), ORANGE)
        elif kind == "base":
            pygame.draw.rect(surf, BLUE, (x - 6, y - 6, 12, 12), 2)
            put(surf, fs, (sp[3] if sp and len(sp) > 3 else "ASENTAMIENTO")[:22], (x + 10, y - 7), BLUE)
        elif kind == "kill":
            pygame.draw.line(surf, RED, (x - 4, y - 4), (x + 4, y + 4), 2)
            pygame.draw.line(surf, RED, (x - 4, y + 4), (x + 4, y - 4), 2)
        else:
            pygame.draw.circle(surf, GREEN, (x, y), 4, 2)
    x, y = scr(me)
    a = math.radians(b.get("hdg") or 0)
    tip = (x + 11 * math.sin(a), y - 11 * math.cos(a))
    lft = (x + 7 * math.sin(a - 2.5), y - 7 * math.cos(a - 2.5))
    rgt = (x + 7 * math.sin(a + 2.5), y - 7 * math.cos(a + 2.5))
    pygame.draw.polygon(surf, GREEN, [tip, lft, (x, y), rgt])
    surf.set_clip(old)
    pygame.draw.rect(surf, DIM, r, 1)
    put(surf, fs, ("CERCA (100 m)" if track["zoom"] else "TODO EL RECORRIDO") + "  ·  toca para cambiar",
        (r.x + 6, r.y + 4), DIM, r.w - 120)
    nx = r.right - 12
    pygame.draw.line(surf, WHITE, (nx, r.y + 22), (nx, r.y + 9), 2)
    pygame.draw.polygon(surf, WHITE, [(nx, r.y + 4), (nx - 4, r.y + 11), (nx + 4, r.y + 11)])
    put(surf, fs, "N", (nx - 7, r.y + 6), WHITE, anchor="topright")
    put(surf, fs, f"cuadro = {fmt_m(step)}", (r.x + 6, r.bottom - 18), DIM)
    nk = len(track["kills"])
    info = []
    if ship:
        info.append(f"nave a {fmt_m(round(hav((lat, lon), ship, R)))}")
    if nk:
        info.append(f"{nk} bajas")
    if info:
        put(surf, fs, "  ·  ".join(info), (r.right - 6, r.bottom - 18), ORANGE, r.w // 2, anchor="topright")

def view_map(surf, d, flags, now):
    draw_map(surf, pygame.Rect(4, TOP + 2, W - 8, H - TOP - 6), d, now)

def tap_map():
    track["zoom"] = 1 - track["zoom"]

VIEWS[150] = view_map
MENU[150] = "MAPA"
PARENT[150] = 0
TABS.append([(5, "SRV / A PIE"), (150, "MAPA")])

'''
rep("\ndef render(surf):", CODE + "\ndef render(surf):")

# recoger puntos del recorrido y marcar las bajas
rep('''    if online:
        process_notes(d)''', '''    if online:
        process_notes(d)
        track_update(d, now)''')
rep('''            if kind in FIGHT_KINDS:
                fight["t"] = time.time()''', '''            if kind in FIGHT_KINDS:
                fight["t"] = time.time()
            if kind == "kill":
                track_kill()''')

# pantalla grande: el mapa en SUPERFICIE (en lugar de MATERIALES) y en COMBATE A PIE
rep('''BIG_SETS = {"COMBATE A PIE": [100, 5], ''', '''BIG_SETS = {"COMBATE A PIE": [100, 5, 150], ''')
rep('''"SUPERFICIE": [100, 73, 5, 125]''', '''"SUPERFICIE": [100, 73, 5, 150]''')
rep('''    if len(cells) == 2:
        # dos cuadros, uno al lado del otro y a toda la altura
        for i, v in enumerate(cells):
            big_cell(S, cell, v, d, flags, now, pygame.Rect(i * cw, hh, cw, bh - hh), fbig, "fit")
        return''', '''    if len(cells) == 3 and cells[2] == 150:
        # combate a pie: EN VIVO arriba a la izquierda, botones abajo a la izquierda y el MAPA a toda la altura
        big_cell(S, cell, cells[0], d, flags, now, pygame.Rect(0, hh, cw, ch), fsm, "fill")
        big_cell(S, cell, cells[1], d, flags, now, pygame.Rect(0, hh + ch, cw, ch), fsm, "fill")
        big_cell(S, cell, 150, d, flags, now, pygame.Rect(cw, hh, cw, bh - hh), fsm, "fill")
        return
    if len(cells) == 2:
        for i, v in enumerate(cells):
            big_cell(S, cell, v, d, flags, now, pygame.Rect(i * cw, hh, cw, bh - hh), fbig, "fit")
        return''')
# el mapa se dibuja directamente al tamano del cuadro (sin escalar: nitido)
rep('''def big_cell(S, cell, v, d, flags, now, r, font, how, extra=""):
''', '''def big_cell(S, cell, v, d, flags, now, r, font, how, extra=""):
    if v == 150:
        pygame.draw.rect(S, DIM, r.inflate(-4, -4), 1, border_radius=6)
        lab = font.render("MAPA" + extra, True, DIM)
        S.blit(lab, (r.x + 10, r.y + 4))
        top = r.y + lab.get_height() + 6
        draw_map(S, pygame.Rect(r.x + 6, top, r.w - 12, r.bottom - 6 - top), d, now)
        return
''')

# toque en el mapa: todo el recorrido / cerca
rep("    elif v in (140, 141):\n", "    elif v == 150:\n        tap_map(); return\n    elif v in (140, 141):\n")

# manual
rep('''- 5 SRV / RHINO / A PIE: botones del vehículo y a pie.''',
    '''- 5 SRV / RHINO / A PIE: botones del vehículo y a pie. Pestaña MAPA: tu recorrido sobre el planeta.''')
rep('''- SUPERFICIE (aterrizado, SRV o a pie): xenobiología, SRV y materiales.''',
    '''- SUPERFICIE (aterrizado, SRV o a pie): xenobiología, SRV y MAPA del recorrido.''')
rep('''- COMBATE A PIE: EN VIVO y SRV / RHINO / A PIE, uno al lado del otro.''',
    '''- COMBATE A PIE: EN VIVO y SRV / RHINO / A PIE a la izquierda y el MAPA a la derecha.''')
rep('''- Notas de viaje (3 > NOTAS):''', '''- MAPA (5 > MAPA): tu recorrido a pie, en SRV o Rhino (rastro naranja), tu posición y rumbo (flecha verde), la nave, el asentamiento (azul), las bajas (cruces rojas) y las muestras (verde). Norte arriba; la cuadrícula se ajusta sola. Toca para ver todo el recorrido o 100 m a tu alrededor.
- Notas de viaje (3 > NOTAS):''')

rep('    ("0.67", "EN COMBATE a pie (grande en 2 cuadros) y salud baja al 75/50/25 %"),\n',
    '    ("0.67", "EN COMBATE a pie (grande en 2 cuadros) y salud baja al 75/50/25 %"),\n'
    '    ("0.68", "MAPA de recorrido a pie, SRV y Rhino"),\n')
s = re.sub(r'PANEL_VER = "v0\.67[^"]*"', 'PANEL_VER = "v0.68 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.68 MAPA  (copia en panel.py.bak67)")
