#!/usr/bin/env python3
# Parche v0.55: pantalla grande ATRACADO con GALNET (rota con CARGA/MISIÓN) y fecha del juego en el reloj
import re, shutil, sys, time
P = "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def atr_cell" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.54' not in s:
    sys.exit("Este parche es para la v0.54")
shutil.copy(P, P + ".bak54")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

# la ventana de noticias sirve tambien para un cuadro de la pantalla grande
rep("def idle_crawl(surf, now):\n    box = IDLE_BOX",
    "def idle_crawl(surf, now, box=None, waiting=True):\n    box = box or IDLE_BOX")
rep('    if int(now) % 4 < 3:\n        put(surf, F["small"], "Esperando a Elite Dangerous...", (box.right',
    '    if waiting and int(now) % 4 < 3:\n        put(surf, F["small"], "Esperando a Elite Dangerous...", (box.right')

# fecha del juego en la pantalla del reloj
rep('    put(surf, F["small"], PANEL_VER.split(" · ")[0], (150, 132), GREEN)\n',
    '    put(surf, F["small"], PANEL_VER.split(" · ")[0], (150, 132), GREEN)\n'
    '    put(surf, F["small"], game_date(), (cx + 4, 132), BLUE, anchor="midtop")\n')

CODE = r'''
# ---------- fecha del juego y cuadro GALNET de la pantalla grande ----------
MES3 = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]

def game_date():
    g = time.gmtime()
    return f"{g.tm_mday} {MES3[g.tm_mon - 1]} {g.tm_year + 1286}"

def view_galnet_cell(surf, d, flags, now):
    idle_crawl(surf, now, pygame.Rect(4, TOP + 2, W - 8, H - TOP - 6), waiting=False)

ATR_ROT = [(133, 20), (4, 4), (132, 20)]     # GALNET 20 s, CARGA/MISIÓN 4 s, OBJ. COMUNITARIOS 20 s

def atr_cell(d, now):
    rot = [(133, 20)]
    if (d or {}).get("cargo") or (d or {}).get("missions"):
        rot.append((4, 4))
    if 132 in VIEWS and (globals().get("cgoals") or {}).get("list"):
        rot.append((132, 20))
    if len(rot) == 1:
        return 133
    t = now % sum(s_ for _, s_ in rot)
    for v, s_ in rot:
        if t < s_:
            return v
        t -= s_
    return 133

VIEWS[133] = view_galnet_cell
MENU[133] = "GALNET"

'''
rep("\ndef render(surf):", CODE + "\ndef render(surf):")

rep("        cells[cells.index(74)] = 128\n",
    "        cells[cells.index(74)] = 128\n"
    "    if mode == \"ATRACADO\" and 4 in cells:\n"
    "        cells[cells.index(4)] = atr_cell(d, now)\n")

rep('    ("0.54", "Reloj: foto arriba y noticias GALNET subiendo"),\n',
    '    ("0.54", "Reloj: foto arriba y noticias GALNET subiendo"),\n'
    '    ("0.55", "Pantalla grande ATRACADO: GALNET y carga/misión; fecha del juego"),\n')
s = re.sub(r'PANEL_VER = "v0\.54[^"]*"', 'PANEL_VER = "v0.55 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.55  (copia en panel.py.bak54)")
