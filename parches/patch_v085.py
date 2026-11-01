#!/usr/bin/env python3
# Parche v0.85: cierre de emergencia mas facil de acertar: zona mas grande (toda la barra de arriba
# entre MENU y el engranaje, sin las pestanas) y aviso 1/3, 2/3 en cada toque.
import re, shutil, sys, time
P = sys.argv[1] if len(sys.argv) > 1 else "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "KILL zona v085" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.84' not in s:
    sys.exit("Este parche es para la v0.84")
shutil.copy(P, P + ".bak84")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

rep('''def kill_title_rect():
    return pygame.Rect(BACK.right, 0, W - 182 - BACK.right, 32)''', '''def kill_title_rect():
    # KILL zona v085: toda la barra de arriba entre MENU y el engranaje; con pestanas, solo la franja del nombre
    v = ui.get("view")
    h = 30 if tab_group(v)[0] else TOP - 4
    return pygame.Rect(BACK.right, 0, GEAR.x - 8 - BACK.right, h)''')
rep('''    KILL["taps"] = [t for t in KILL["taps"] if now - t < 2.0] + [now]
    if len(KILL["taps"]) >= 3:
        KILL["taps"] = []
        KILL["t0"] = now
        play("alarm")
    return True''', '''    KILL["taps"] = [t for t in KILL["taps"] if now - t < 2.5] + [now]
    if len(KILL["taps"]) >= 3:
        KILL["taps"] = []
        KILL["t0"] = now
        play("alarm")
    else:
        ui["toast"] = (f"CERRAR JUEGO: toque {len(KILL['taps'])} de 3", now + 2)
    return True''')
rep('    ("0.84", "Cierre de emergencia del juego, ESCUADRÓN en AMIGOS, MENÚ PRINCIPAL en verde y arreglos"),\n',
    '    ("0.84", "Cierre de emergencia del juego, ESCUADRÓN en AMIGOS, MENÚ PRINCIPAL en verde y arreglos"),\n'
    '    ("0.85", "Cierre de emergencia: zona más grande en la barra de arriba y aviso de toques 1/3, 2/3"),\n')
rep('''- Tres toques seguidos sobre el nombre del sistema (arriba)''', '''- Tres toques seguidos sobre la barra de arriba, entre MENÚ y el engranaje (el nombre del sistema); abajo sale «toque 1 de 3», «2 de 3»''')
s = re.sub(r'PANEL_VER = "v0\.84[^"]*"', 'PANEL_VER = "v0.85 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)
open(P, "w", encoding="utf-8").write(s)
print("OK v0.85  (copia en " + P + ".bak84)")
