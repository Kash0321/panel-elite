#!/usr/bin/env python3
# Parche v0.59: optimizacion (pantalla pequena 8 veces mas rapida, grande a 3,3 imagenes/s) y aviso de BAJA TENSION
import re, shutil, sys, time
P = "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def power_loop" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.58' not in s:
    sys.exit("Este parche es para la v0.58")
shutil.copy(P, P + ".bak58")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

# 1) pantalla pequena: conversion a 16 bits con pygame en vez de numpy (mismo resultado, ~8 veces mas rapido)
rep('''def to_fb_bytes(surf, bpp, stride):
    if ROT:
        surf = pygame.transform.rotate(surf, 90)
''', '''_FB16 = {}

def to_fb_bytes(surf, bpp, stride):
    if ROT:
        surf = pygame.transform.rotate(surf, 90)
    if bpp == 16:
        w_, h_ = surf.get_size()
        t = _FB16.get((w_, h_))
        if t is None:
            t = _FB16[(w_, h_)] = pygame.Surface((w_, h_), 0, 16, (0xF800, 0x07E0, 0x001F, 0))
        t.blit(surf, (0, 0))
        raw, pitch = t.get_buffer().raw, t.get_pitch()
        if pitch != stride:
            n = min(pitch, stride)
            raw = b"".join(raw[y * pitch:y * pitch + n].ljust(stride, b"\\0") for y in range(h_))
        return raw
''')

# 2) pantalla grande: una de cada 3 vueltas (unas 3,3 imagenes por segundo)
rep('            if BIG["n"] % 2 == 0:', '            if BIG["n"] % 3 == 0:')

CODE = r'''
# ---------- alimentacion de la Pi (vcgencmd get_throttled) ----------
power = {"now": False, "past": False, "warned": 0, "ok": False}

def power_loop():
    while True:
        try:
            out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=5).stdout
            v = int(out.strip().split("=")[1], 16)
            power.update(now=bool(v & 1), past=bool(v & 0x10000), ok=True)
            if power["now"] and time.time() - power["warned"] > 600 and cfg["alerts"]:
                power["warned"] = time.time()
                set_alert("BAJA TENSIÓN", "a la Pi le falta corriente: revisa la alimentación", RED, 5)
        except Exception:
            pass
        time.sleep(10)

threading.Thread(target=power_loop, daemon=True).start()

def draw_bolt(surf, x, y, col, k=1.0):
    pts = [(6, 0), (0, 11), (5, 11), (2, 20), (11, 7), (6, 7), (9, 0)]
    pygame.draw.polygon(surf, col, [(x + px * k, y + py * k) for px, py in pts])

def power_box(surf, r):
    pygame.draw.rect(surf, DIM, r, 1, border_radius=6)
    put(surf, F["small"], "ALIMENTACIÓN", (r.centerx, r.y + 10), DIM, anchor="midtop")
    if not power["ok"]:
        txt, col = "sin datos", DIM
    elif power["now"]:
        txt, col = "¡BAJA!", RED
    elif power["past"]:
        txt, col = "AVISOS", ORANGE
    else:
        txt, col = "CORRECTA", GREEN
    put(surf, F["btn"], txt, (r.centerx, r.centery + 2), col, r.w - 8, anchor="center")
    sub = "ahora mismo" if power["now"] else "desde que arrancó" if power["past"] else ""
    if sub:
        put(surf, F["small"], sub, (r.centerx, r.bottom - 22), DIM, r.w - 8, anchor="midtop")

'''
rep("\ndef render(surf):", CODE + "\ndef render(surf):")

# rayo rojo parpadeando en la barra de arriba si falta corriente ahora
rep("    pygame.draw.circle(surf, BLACK, (cx, cy), 5)\n",
    "    pygame.draw.circle(surf, BLACK, (cx, cy), 5)\n"
    "    if power[\"now\"] and int(now * 2) % 2 == 0:\n"
    "        draw_bolt(surf, GEAR.x - 20, 28, RED)\n")

# estado de la alimentacion en AJUSTES (hueco de abajo a la derecha)
rep('''            draw_button(surf, r, name, sub, F["btn"], filled=act == "style" and style["cab"],
                        lit=flash.get((12, i), 0) > now)
''', '''            draw_button(surf, r, name, sub, F["btn"], filled=act == "style" and style["cab"],
                        lit=flash.get((12, i), 0) > now)
    power_box(surf, grid(11, 4, 3))
''')

# aviso en la pantalla del reloj (cabecera de la ventana de noticias)
rep('''    if waiting and int(now) % 4 < 3:
        put(surf, F["small"], "Esperando a Elite Dangerous...", (box.right''',
    '''    if power["now"] and int(now * 2) % 2 == 0:
        put(surf, F["small"], "BAJA TENSIÓN", (box.right - 8, box.y + 5), RED, anchor="topright")
        draw_bolt(surf, box.right - 108, box.y + 2, RED, 0.85)
    elif waiting and int(now) % 4 < 3:
        put(surf, F["small"], "Esperando a Elite Dangerous...", (box.right''')

rep('    ("0.58", "12 AJUSTES a la vista, pestañas de información y engranaje"),\n',
    '    ("0.58", "12 AJUSTES a la vista, pestañas de información y engranaje"),\n'
    '    ("0.59", "Optimización de pantallas y aviso de BAJA TENSIÓN"),\n')
s = re.sub(r'PANEL_VER = "v0\.58[^"]*"', 'PANEL_VER = "v0.59 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.59 optimizada  (copia en panel.py.bak58)")
