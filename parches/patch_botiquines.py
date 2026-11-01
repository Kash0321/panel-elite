#!/usr/bin/env python3
# Parche v0.69: botiquines / celulas / granadas (avisos y marcas en el MAPA), boton MARCAR RECARGA,
# "HAS CAIDO" a pie y lo que paga el juego al cobrar
import re, shutil, sys, time
P = "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def track_item" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.68' not in s:
    sys.exit("Este parche es para la v0.68")
shutil.copy(P, P + ".bak68")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

# 1) marcas en el mapa: botiquin (cruz verde), celula (rayo amarillo), granadas (rombo gris), recarga (rayo con aro)
rep('''track = {"body": None, "pts": [], "kills": [], "last": None, "zoom": 0}''',
    '''track = {"body": None, "pts": [], "kills": [], "items": [], "last": None, "zoom": 0}
YELLOW = (255, 215, 0)
GREY = (150, 150, 150)
ITEM_KIND = {"healthpack": "med", "energycell": "cell"}''')
rep('''        track.update(body=body, pts=[], kills=[], last=None)''',
    '''        track.update(body=body, pts=[], kills=[], items=[], last=None)''')
rep('''def track_kill():''', '''def track_item(kind):
    with lock:
        d = state["data"]
    b = (d or {}).get("bio") or {}
    if b.get("lat") is not None:
        track["items"].append((kind, b["lat"], b["lon"]))
        del track["items"][:-300]
        return True
    return False

def track_kill():''')
rep('''    marks += [("bio", xy(p)) for p in (b.get("pts") or []) if p]''',
    '''    marks += [("bio", xy(p)) for p in (b.get("pts") or []) if p]
    marks += [(k_, xy((la, lo))) for k_, la, lo in track["items"]]''')
rep('''        else:
            pygame.draw.circle(surf, GREEN, (x, y), 4, 2)
    x, y = scr(me)''', '''        elif kind == "med":
            pygame.draw.line(surf, GREEN, (x - 6, y), (x + 6, y), 4)
            pygame.draw.line(surf, GREEN, (x, y - 6), (x, y + 6), 4)
        elif kind == "cell":
            draw_bolt(surf, x - 4, y - 8, YELLOW, 0.75)
        elif kind == "recharge":
            pygame.draw.circle(surf, YELLOW, (x, y), 10, 2)
            draw_bolt(surf, x - 4, y - 8, YELLOW, 0.75)
        elif kind == "gren":
            pygame.draw.polygon(surf, GREY, [(x, y - 4), (x + 4, y), (x, y + 4), (x - 4, y)])
        else:
            pygame.draw.circle(surf, GREEN, (x, y), 4, 2)
    x, y = scr(me)''')

# 2) pantalla MAPA de la pequena: boton MARCAR RECARGA
rep('''def view_map(surf, d, flags, now):
    draw_map(surf, pygame.Rect(4, TOP + 2, W - 8, H - TOP - 6), d, now)

def tap_map():
    track["zoom"] = 1 - track["zoom"]''', '''MARK_BTN = pygame.Rect(W - 172, H - 38, 166, 34)

def view_map(surf, d, flags, now):
    draw_map(surf, pygame.Rect(4, TOP + 2, W - 8, H - TOP - 46), d, now)
    draw_button(surf, MARK_BTN, "      MARCAR RECARGA", None, F["small"], lit=flash.get(("mark",), 0) > now)
    draw_bolt(surf, MARK_BTN.x + 8, MARK_BTN.y + 7, YELLOW, 0.95)
    nm = sum(1 for k_, *_ in track["items"] if k_ == "med")
    nc = sum(1 for k_, *_ in track["items"] if k_ in ("cell", "recharge"))
    put(surf, F["small"], f"+ botiquines {nm}   ·   rayos {nc}", (8, H - 28), DIM, W - 190)

def tap_map(x=0, y=0):
    if MARK_BTN.collidepoint(x, y):
        if track_item("recharge"):
            tap_flash(("mark",))
            set_alert("PUNTO DE RECARGA MARCADO", "", YELLOW, 1.5, "ok")
        else:
            set_alert("SIN POSICIÓN", "solo en un planeta", secs=2)
        return
    track["zoom"] = 1 - track["zoom"]''')
rep("    elif v == 150:\n        tap_map(); return\n", "    elif v == 150:\n        tap_map(x, y); return\n")

# 3) al recibir los avisos: marcar en el mapa lo que coges
rep('''            if kind == "kill":
                track_kill()''', '''            if kind == "kill":
                track_kill()
            if kind == "pickup":
                nm_ = (text.split("|") + [""])[0]
                track_item(ITEM_KIND.get(nm_, "gren"))''')

# 4) avisos: coger / usar consumibles, cobro y HAS CAIDO a pie
rep('''        elif kind == "died" and len(p) >= 4:
            xa["a"] = dict(until=now + 15, col=RED, title="NAVE DESTRUIDA", big=p[0] or "?",''',
    '''        elif kind == "pickup" and len(p) >= 3:
            xa["a"] = dict(until=now + 2.5, col=YELLOW if p[0] == "energycell" else GREEN if p[0] == "healthpack" else GREY,
                           title=f"+1 {p[1].upper()}", big=f"llevas {p[2]}", lines=[])
        elif kind == "usecons" and len(p) >= 3:
            left = int(p[2]) if p[2].isdigit() else -1
            xa["a"] = dict(until=now + (4 if left == 0 else 2.5), col=RED if left == 0 else ORANGE,
                           title=f"{p[1].upper()} USADO", big="¡NO TE QUEDAN!" if left == 0 else f"quedan {left}", lines=[])
            if left == 0:
                play("alarm")
        elif kind == "redeem" and len(p) >= 2:
            amt, tr = float(p[0] or 0), float(p[1] or 0)
            xa["a"] = dict(until=now + 7, col=GREEN, title="COBRADO", big=f"{crx(amt)} cr",
                           lines=[f"el panel llevaba sumados {crx(tr)} cr"] + ([f"diferencia {'+' if amt >= tr else ''}{crx(amt - tr)} cr"] if tr else []))
        elif kind == "died" and len(p) >= 4 and (((d or {}).get("footcz") or {}).get("onfoot") or (d or {}).get("Flags2", 0) & 1):
            xa["a"] = dict(until=now + 10, col=RED, title="HAS CAÍDO", big=p[0] or "",
                           lines=["al reaparecer en la zona conservas los bonos"])
        elif kind == "died" and len(p) >= 4:
            xa["a"] = dict(until=now + 15, col=RED, title="NAVE DESTRUIDA", big=p[0] or "?",''')

# 5) manual
rep('''- MAPA (5 > MAPA): tu recorrido a pie, en SRV o Rhino (rastro naranja), tu posición y rumbo (flecha verde), la nave, el asentamiento (azul), las bajas (cruces rojas) y las muestras (verde).''',
    '''- MAPA (5 > MAPA): tu recorrido a pie, en SRV o Rhino (rastro naranja), tu posición y rumbo (flecha verde), la nave, el asentamiento (azul), las bajas (cruces rojas) y las muestras (verde). Donde coges un botiquín sale una cruz verde, una célula de energía un rayo amarillo y las granadas un rombo gris. MARCAR RECARGA pone un rayo con aro donde estás (el juego no avisa al recargar el traje ni al coger munición).''')
rep('''- @r ¡DESPLEGADO!:''', '''- +1 BOTIQUÍN / CÉLULA / GRANADA al cogerlos (llevas N) y USADO al gastarlos; en rojo y con alarma si no te queda ninguno.
- COBRADO: lo que paga el juego y lo que llevaba sumado el panel (la diferencia suele ser de bonos anteriores o extras).
- @r HAS CAÍDO: al morir a pie (en la zona conservas los bonos).
- @r ¡DESPLEGADO!:''')

rep('    ("0.68", "MAPA de recorrido a pie, SRV y Rhino"),\n',
    '    ("0.68", "MAPA de recorrido a pie, SRV y Rhino"),\n'
    '    ("0.69", "Botiquines y células en avisos y MAPA, MARCAR RECARGA, HAS CAÍDO y COBRADO"),\n')
s = re.sub(r'PANEL_VER = "v0\.68[^"]*"', 'PANEL_VER = "v0.69 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.69  (copia en panel.py.bak68)")
