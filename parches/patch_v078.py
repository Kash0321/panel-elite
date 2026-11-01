#!/usr/bin/env python3
# Parche v0.78: el mapa vuelve a dibujar el recorrido (el filtro de velocidad media mal el tiempo).
import re, shutil, sys, time
P = sys.argv[1] if len(sys.argv) > 1 else "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "posicion nueva: la velocidad" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.77' not in s:
    sys.exit("Este parche es para la v0.77")
shutil.copy(P, P + ".bak77")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

rep('''    raw = track.get("raw")
    track["raw"] = (lat, lon, now)
    if raw and d.get("Flags2", 0) & 1 and not d.get("Flags", 0) & (1 << 26):
        dt = now - raw[2]
        if 0 < dt < 10 and hav(raw[:2], (lat, lon), R) / dt > FOOT_MAX_V:''', '''    raw = track.get("raw")
    if d.get("Flags2", 0) & 1 and not d.get("Flags", 0) & (1 << 26):
        # posicion nueva: la velocidad se mide sobre 1 s como minimo (el juego da la posicion a saltos)
        if raw is None or now - raw[2] >= 1.0:
            if raw is not None and now - raw[2] < 10:
                track["fast"] = hav(raw[:2], (lat, lon), R) / (now - raw[2]) > FOOT_MAX_V
            track["raw"] = (lat, lon, now)
        if track.get("fast"):''')

rep('    ("0.77", "Teclas del juego (.binds), indicador de CPU/temperatura/FPS y modo PANEL ligero"),\n',
    '    ("0.77", "Teclas del juego (.binds), indicador de CPU/temperatura/FPS y modo PANEL ligero"),\n'
    '    ("0.78", "Arreglo: el mapa a pie vuelve a dibujar el recorrido"),\n')
s = re.sub(r'PANEL_VER = "v0\.77[^"]*"', 'PANEL_VER = "v0.78 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)
open(P, "w", encoding="utf-8").write(s)
print("OK v0.78  (copia en " + P + ".bak77)")
