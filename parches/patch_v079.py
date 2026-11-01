#!/usr/bin/env python3
# Parche v0.79: enlace energetico. Si lo llevas en la mano y estas parado 8 s (1 m de margen),
# el panel lo da por recarga: aviso pequeno "RECARGANDO" y punto de recarga en el mapa (si no hay otro a menos de 20 m).
import re, shutil, sys, time
P = sys.argv[1] if len(sys.argv) > 1 else "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def elink_check" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.78' not in s:
    sys.exit("Este parche es para la v0.78")
shutil.copy(P, P + ".bak78")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

rep('''    if not out or d.get("Flags2", 0) & 2:              # en taxi o en el transporte no se apunta
        return''', '''    if not out or d.get("Flags2", 0) & 2:              # en taxi o en el transporte no se apunta
        return
    elink_check(d, now, lat, lon, R)''')

rep('''def track_item(kind):''', '''ELINK_SECS, ELINK_STILL, ELINK_NEAR = 8.0, 1.0, 20.0    # segundos parado, margen (m), sin otro punto a (m)
ELINK = {"t0": None, "pos": None, "done": False}

def elink_check(d, now, lat, lon, R):
    """Enlace energetico en la mano y parado: recargando (el juego no dice la bateria del traje)."""
    w = str(((d or {}).get("live") or {}).get("weapon") or "").lower()
    holding = d.get("Flags2", 0) & 1 and any(k in w for k in ("rechargetool", "energylink", "enlace"))
    if not holding:
        ELINK.update(t0=None, pos=None, done=False)
        return
    if ELINK["pos"] is None or hav(ELINK["pos"], (lat, lon), R) > ELINK_STILL:
        ELINK.update(t0=now, pos=(lat, lon), done=False)
        return
    if ELINK["done"] or now - ELINK["t0"] < ELINK_SECS:
        return
    ELINK["done"] = True
    near = any(k_ == "recharge" and hav((la, lo), (lat, lon), R) < ELINK_NEAR for k_, la, lo in track["items"])
    if not near:
        track["items"].append(("recharge", lat, lon))
        del track["items"][:-300]
    if ev_on("elink"):
        ui["toast"] = ("RECARGANDO  ·  enlace energético" + ("" if near else "  ·  punto marcado"), now + 4)

def draw_toast(surf, now):
    t = ui.get("toast")
    if not t or now > t[1]:
        return
    f = F["small"]
    w_ = f.size(t[0])[0] + 20
    r = pygame.Rect((W - w_) // 2, H - 26, w_, 22)
    pygame.draw.rect(surf, BLACK, r, border_radius=6)
    pygame.draw.rect(surf, YELLOW, r, 1, border_radius=6)
    put(surf, f, t[0], r.center, YELLOW, anchor="center")

def track_item(kind):''')

rep('''    draw_xa(surf, now)
    if (cfg.get("voice")''', '''    draw_xa(surf, now)
    draw_toast(surf, now)
    if (cfg.get("voice")''')
rep('''           ("keys", "TECLAS SIN ASIGNAR")]''', '''           ("keys", "TECLAS SIN ASIGNAR"), ("elink", "RECARGA CON ENLACE")]''')

rep('''- Un botón sin tecla pone SIN TECLA y al tocarlo avisa.''', '''- Un botón sin tecla pone SIN TECLA y al tocarlo avisa.
# Enlace energético
- Si llevas el enlace energético en la mano y estás parado 8 segundos (girar con el ratón no cuenta), el panel lo da por recarga: aviso pequeño RECARGANDO y punto de recarga (rayo amarillo) en el MAPA, si no hay otro a menos de 20 m.
- El juego no dice la batería del traje ni la munición: es una aproximación.''')

rep('    ("0.78", "Arreglo: el mapa a pie vuelve a dibujar el recorrido"),\n',
    '    ("0.78", "Arreglo: el mapa a pie vuelve a dibujar el recorrido"),\n'
    '    ("0.79", "Enlace energético: parado 8 s = RECARGANDO y punto de recarga en el mapa"),\n')
s = re.sub(r'PANEL_VER = "v0\.78[^"]*"', 'PANEL_VER = "v0.79 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)
open(P, "w", encoding="utf-8").write(s)
print("OK v0.79  (copia en " + P + ".bak78)")
