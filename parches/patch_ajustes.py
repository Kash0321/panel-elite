#!/usr/bin/env python3
# Parche v0.58: menu 12 = AJUSTES (todo a la vista), informacion en pestanas dentro de su menu, engranaje arriba
import re, shutil, sys, time
P = "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def tap_sub12" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.57' not in s:
    sys.exit("Este parche es para la v0.57")
shutil.copy(P, P + ".bak57")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

CODE = r'''
# ---------- v0.58: 12 AJUSTES, pestanas de informacion y engranaje ----------
TABS = [[(3, "NAVEGACIÓN"), (128, "NOTAS")],
        [(4, "CARGA/MISIÓN"), (125, "MATERIALES")],
        [(8, "ESTACIÓN"), (127, "MERCADO"), (126, "PORTANAVES")],
        [(11, "SESIÓN"), (130, "GALNET"), (132, "OBJ.COM"), (123, "RANGOS")]]
TAB_OF = {129: 128, 131: 130}          # pantallas de detalle -> su pestana
GEAR = pygame.Rect(W - 50, 2, 46, TOP - 8)      # engranaje a la derecha del todo
MENU.update({12: "AJUSTES", 11: "SESIÓN·GALNET"})
for _v in (123, 125, 126, 127, 128, 130, 132):
    PARENT[_v] = 0
PARENT.update({121: 12, 122: 12, 1244: 12, 1245: 12}); MENU[1244] = "OPCIONES"

def tab_group(v):
    v = TAB_OF.get(v, v)
    for g in TABS:
        if any(t == v for t, _ in g):
            return g, v
    return None, v

def tab_rects(v):
    g, cur = tab_group(v)
    if not g:
        return []
    out, x = [], BACK.right + 4
    for t, name in g:
        w = F["small"].size(name)[0] + 16
        out.append((t, name, pygame.Rect(x, 35, w, 19), t == cur))
        x += w + 3
    return out

def draw_tabs(surf, v):
    for t, name, r, on in tab_rects(v):
        new = t == 130 and galnet["new"]
        col = GREEN if new else ORANGE
        if on:
            pygame.draw.rect(surf, col, r, border_radius=4)
            put(surf, F["small"], name, r.center, BLACK, anchor="center")
        else:
            pygame.draw.rect(surf, col if new else DIM, r, 1, border_radius=4)
            put(surf, F["small"], name, r.center, col, anchor="center")

def draw_gear(surf, v, now):
    on = v in (12, 121, 122, 1244, 1245)
    col = WHITE if flash.get(("gear",), 0) > now else ORANGE
    if on:
        pygame.draw.rect(surf, ORANGE, GEAR, 2, border_radius=6)
    cx, cy = GEAR.center
    rot = now * 40                                   # gira despacio (40 grados por segundo)
    for a in range(8):
        r_ = math.radians(a * 45 + rot)
        pygame.draw.line(surf, col, (cx + 11 * math.cos(r_), cy + 11 * math.sin(r_)),
                         (cx + 17 * math.cos(r_), cy + 17 * math.sin(r_)), 6)
    pygame.draw.circle(surf, col, (cx, cy), 13)
    pygame.draw.circle(surf, BLACK, (cx, cy), 5)

def tap_topbar(x, y, v):
    if x >= GEAR.x - 4:
        tap_flash(("gear",)); ui["view"] = 12; return True
    for t, _, r, _ in tab_rects(v):
        if r.inflate(2, 10).collidepoint(x, y):
            ui["view"] = t; ui["page4"] = 0; return True
    return False

SET12 = [("OPCIONES", 1244), ("ESTILO", "style"), ("BORDES", "borders"), ("ICONOS", "icons"),
         ("VERSIONES", 1245), ("LOG", 121), ("STREAM", 122), None,
         ("SALIR", 0), ("REINICIAR", 1), ("APAGAR", 2), None]

def view_sub12(surf, d, flags, now):
    c, until = ui["confirm"]
    for i, it in enumerate(SET12):
        if not it:
            continue
        name, act = it
        r = grid(i, 4, 3)
        sub = {"style": "CABINA" if style["cab"] else "CLÁSICO",
               "borders": "SÍ" if style.get("borders", True) else "NO",
               "icons": "SÍ" if ICONS_ON[0] else "NO"}.get(act) if isinstance(act, str) else None
        if i >= 8:
            sure = c == ("pw", act) and time.time() < until
            draw_button(surf, r, "¿SEGURO?" if sure else name, None if sure else "toca 2 veces", F["btn"],
                        filled=sure, lit=flash.get((1240, act), 0) > now)
        else:
            draw_button(surf, r, name, sub, F["btn"], filled=act == "style" and style["cab"],
                        lit=flash.get((12, i), 0) > now)

def tap_sub12(x, y):
    for i, it in enumerate(SET12):
        if not it or not grid(i, 4, 3).collidepoint(x, y):
            continue
        name, act = it
        if i >= 8:
            power_tap(act); return
        tap_flash((12, i))
        if act == "style":
            style_toggle()
        elif act == "borders":
            borders_toggle()
        elif act == "icons":
            icons_toggle()
        else:
            ui["view"] = act
        return

VIEWS[12] = view_sub12

'''
rep("\ndef render(surf):", CODE + "\ndef render(surf):")

# quitar el menu 12 antiguo (los nuevos view_sub12/tap van arriba)
rep('''    elif v == 12:
        for i in range(10):
            if grid(i, 4, 3).collidepoint(x, y):
                tap_flash((12, i)); ui["view"] = 121 + i if i < 8 else (130 if i == 8 else 132); return
''', '''    elif v == 12:
        tap_sub12(x, y); return
''')

# toques en la barra de arriba: engranaje y pestanas
rep('''        ui["view"] = 0 if v == 100 else PARENT.get(v, 0); ui["pause"] = False
        return
''', '''        ui["view"] = 0 if v == 100 else PARENT.get(v, 0); ui["pause"] = False
        return
    if y < TOP and tap_topbar(x, y, v):
        return
''')

# barra de arriba: engranaje y pestanas (el aviso sustituye al nombre del sistema si hay pestanas)
rep('''    title = ((d or {}).get("system") or "---").upper() if online else "SIN DATOS"
    put(surf, F["big"], title, (x0, 6), ORANGE if online else DIM, W - 136 - x0)
''', '''    title = ((d or {}).get("system") or "---").upper() if online else "SIN DATOS"
    alert0 = next((t for b, t in ALERTS if flags & (1 << b)), None) if online else None
    if alert0 and tab_group(v)[0]:
        put(surf, F["big"], alert0, (x0, 6), RED, W - 182 - x0)
    else:
        put(surf, F["big"], title, (x0, 6), ORANGE if online else DIM, W - 182 - x0)
    draw_gear(surf, v, now)
''')
rep('        bx = pygame.Rect(W - 128, 8, 120, 14)', '        bx = pygame.Rect(W - 176, 6, 120, 14)')
rep('        put(surf, F["small"], f"FUEL {fuel:.1f}t", (W - 128, 26))', '        put(surf, F["small"], f"FUEL {fuel:.1f}t", (W - 176, 21))')
rep('''    if mode:
        put(surf, F["small"], f"MODO: {mode}", (W - 128, 40), RED, 124)''', '''    if mode and not tab_group(v)[0]:
        put(surf, F["small"], f"MODO: {mode}", (W - 176, 37), RED, 120)''')

rep('''    if alert:
        put(surf, F["small"], alert, (x0, 34), RED)
    elif v:''', '''    if tab_group(v)[0]:
        draw_tabs(surf, v)
    elif alert:
        put(surf, F["small"], alert, (x0, 34), RED)
    elif v:''')

# el boton ESTILO sale de SESION (ahora esta en AJUSTES)
rep('    if v == 11 and not splash and not ui["idle_on"]:', '    if False:')
rep('    elif v == 11 and STYLE_BTN.collidepoint(x, y):\n        style_toggle(); return\n', '')

rep('    ("0.57", "SALIR: shell en la HDMI y aviso en la pequeña"),\n',
    '    ("0.57", "SALIR: shell en la HDMI y aviso en la pequeña"),\n'
    '    ("0.58", "12 AJUSTES a la vista, pestañas de información y engranaje"),\n')
s = re.sub(r'PANEL_VER = "v0\.57[^"]*"', 'PANEL_VER = "v0.58 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.58 AJUSTES  (copia en panel.py.bak57)")
