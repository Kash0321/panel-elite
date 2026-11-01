#!/usr/bin/env python3
# Parche v0.57: SALIR deja el shell en la pantalla HDMI y un aviso fijo en la pequena
import re, shutil, sys, time
P = "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def draw_bye" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.56' not in s:
    sys.exit("Este parche es para la v0.56")
shutil.copy(P, P + ".bak56")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

# SALIR: aviso en pantalla, y un proceso aparte para el panel y pasa la consola a la HDMI
rep('    subprocess.Popen(["sudo", "-n"] + cmd)',
    '''    if i == 0:
        ui["bye"] = time.time()
        sh = ("sleep 1; systemctl stop elite-panel; con2fbmap 1 0; "
              "cat /dev/zero > /dev/fb0 2>/dev/null; chvt 2; chvt 1; setterm --blank 0 --cursor on > /dev/tty1")
        subprocess.Popen(["sudo", "-n", "systemd-run", "--no-block", "--collect", "sh", "-c", sh])
        return
    subprocess.Popen(["sudo", "-n"] + cmd)''')

CODE = r'''
# ---------- pantalla de SALIR ----------
def draw_bye(surf):
    surf.fill(BLACK)
    _orig_rect(surf, ORANGE, (0, 0, W, H), 2)
    put(surf, F["num"], "PANEL PARADO", (W // 2, 70), ORANGE, W - 20, anchor="center")
    put(surf, F["btn"], "El shell está en la pantalla HDMI", (W // 2, 125), WHITE, W - 20, anchor="center")
    put(surf, F["small"], "Para volver a arrancar el panel:", (W // 2, 175), DIM, anchor="center")
    put(surf, F["btn"], "sudo systemctl start elite-panel", (W // 2, 200), GREEN, W - 20, anchor="center")
    put(surf, F["small"], "o reinicia la Pi", (W // 2, 235), DIM, anchor="center")
    put(surf, F["small"], PANEL_VER.split(" · ")[0], (W // 2, H - 20), DIM, anchor="center")

'''
rep("\ndef render(surf):", CODE + "\ndef render(surf):")

# bucle principal: si se esta saliendo, solo el aviso
rep('''            render(surf)
            decorate(surf)
            draw_borders(surf)
            rhino_banner(surf)
''', '''            if ui.get("bye"):
                draw_bye(surf)
            else:
                render(surf)
                decorate(surf)
                draw_borders(surf)
                rhino_banner(surf)
''')
# pantalla grande en negro al salir
rep('''def render_big():
    S, cell = BIG["surf"], BIG["cell"]
''', '''def render_big():
    S, cell = BIG["surf"], BIG["cell"]
    if ui.get("bye"):
        S.fill(BLACK); return
''')

rep('    ("0.56", "12.10 Objetivos comunitarios (web y los tuyos)"),\n',
    '    ("0.56", "12.10 Objetivos comunitarios (web y los tuyos)"),\n'
    '    ("0.57", "SALIR: shell en la HDMI y aviso en la pequeña"),\n')
s = re.sub(r'PANEL_VER = "v0\.56[^"]*"', 'PANEL_VER = "v0.57 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.57 SALIR  (copia en panel.py.bak56)")
