#!/usr/bin/env python3
# Parche v0.66: BAJAS a pie / DERRIBOS con contador y bonos sin cobrar, zona de combate y luces de la entrada del atraque
import re, shutil, sys, time
P = "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if 'kind == "deploy"' in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.65' not in s:
    sys.exit("Este parche es para la v0.65")
shutil.copy(P, P + ".bak65")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

# creditos exactos por debajo del millon (120.523 en vez de 121 k)
rep("def cr(v):", "def crx(v):\n    v = v or 0\n    return fnum(v, 0) if abs(v) < 1e6 else cr(v)\n\ndef cr(v):")

# 1) aviso de baja / derribo con numero y lo que llevas sin cobrar
rep('''        elif kind == "kill" and len(p) >= 3:
            rew = float(p[1] or 0)
            xa["a"] = dict(until=now + 2.5, col=GREEN if p[2] != "P" else RED, title="DERRIBO",
                           big=f"+{cr(rew)} cr" if rew else "PvP", lines=[p[0]])''',
'''        elif kind == "kill" and len(p) >= 3:
            rew = float(p[1] or 0)
            veh = p[3] if len(p) > 3 else "N"
            num = p[4] if len(p) > 4 and p[4].isdigit() and p[4] != "0" else ""
            name = "BAJA" if veh == "F" else "DERRIBO (SRV)" if veh == "S" else "DERRIBO"
            col = RED if p[2] == "P" else BLUE if p[2] in ("B", "T") else GREEN
            lines = [p[0]]
            if len(p) > 6 and p[6] not in ("", "0"):
                lines.append(f"{p[5]} sin cobrar  ·  {crx(float(p[6]))} cr")
            xa["a"] = dict(until=now + 3, col=col, title=f"{name} nº {num}" if num else name,
                           big=f"+{crx(rew)} cr" if rew else "PvP", lines=lines)
        elif kind == "dropship":
            xa["a"] = dict(until=now + 6, col=ORANGE, title="TRANSPORTE A ZONA DE COMBATE",
                           big=(p[0] or "").upper(), lines=[p[1]] if len(p) > 1 and p[1] else [])
        elif kind == "deploy":
            st = {"War": "EN GUERRA", "CivilWar": "EN GUERRA CIVIL"}.get(p[2] if len(p) > 2 else "", p[2] if len(p) > 2 else "")
            sub = (f"Asentamiento de {p[1]}" if len(p) > 1 and p[1] else "") + (f"  ·  {st}" if st else "")
            xa["a"] = dict(until=now + 6, col=RED, title="¡DESPLEGADO!", big=(p[0] or "").upper(), lines=[sub] if sub else [])''')

# 2) EN VIVO a pie: zona de combate, bajas, ritmo y bonos sin cobrar (en lugar de la mochila mientras combates)
rep('''        P = d.get("pack") or {}
        cons = P.get("cons") or []
        if cons:''', '''        Z = d.get("footcz") or {}
        P = {} if Z.get("n") else (d.get("pack") or {})
        if Z.get("n"):
            led = Z.get("led") or {}
            zt = (Z.get("zone") or "ZONA DE COMBATE").upper() + (f"  ·  por {Z['side']}" if Z.get("side") else "")
            put(surf, F["small"], zt, (8, y + 2), BLUE, W - 16)
            put(surf, F["btn"], f"{Z['n']} BAJAS", (8, y + 18), GREEN)
            put(surf, F["btn"], f"{crx(led.get('cr', 0))} cr sin cobrar", (120, y + 18), ORANGE, 230)
            if Z.get("rate"):
                put(surf, F["small"], f"{str(Z['rate']).replace('.', ',')} / min", (W - 8, y + 22), DIM, anchor="topright")
        cons = P.get("cons") or []
        if cons:''')

# 3) SESION: lo que llevas sin cobrar (bonos de combate + recompensas, en nave, SRV o a pie)
rep('''    s_ = (d or {}).get("sess") or {}
    if s_.get("pending"):''', '''    s_ = (d or {}).get("sess") or {}
    led = ((d or {}).get("footcz") or {}).get("led") or {}
    if led.get("cr"):
        b, rw = led.get("bonds") or [0, 0], led.get("bounties") or [0, 0]
        put(surf, F["small"], "SIN COBRAR (bonos + recompensas)", (8, H - 54), DIM)
        put(surf, F["big"], f"{crx(led['cr'])} cr", (8, H - 40), RED)
        put(surf, F["small"], f"{b[0]} bonos {crx(b[1])} cr  ·  {rw[0]} recompensas {crx(rw[1])} cr", (8, H - 16), DIM, 330)
    elif s_.get("pending"):''')

# 4) ATRAQUE: luz roja a la izquierda y verde a la derecha, como la entrada de la estacion
rep('''        pygame.draw.rect(surf, BLACK, (cx - 30, cy - 9, 60, 18))
        pygame.draw.rect(surf, GREEN, (cx - 30, cy - 9, 60, 18), 2)
        put(surf, F["small"], "ENTRADA", (cx, cy), GREEN, anchor="center")''',
'''        k_ = 0.6 + 0.4 * math.sin(now * 3)
        arc = pygame.Rect(cx - rad - 7, cy - rad - 7, 2 * rad + 14, 2 * rad + 14)
        pygame.draw.arc(surf, tuple(int(c * k_) for c in RED[:3]), arc, math.radians(145), math.radians(215), 7)
        pygame.draw.arc(surf, tuple(int(c * k_) for c in GREEN[:3]), arc, math.radians(-35), math.radians(35), 7)
        pygame.draw.rect(surf, BLACK, (cx - 30, cy - 9, 60, 18))
        pygame.draw.rect(surf, WHITE, (cx - 30, cy - 9, 60, 18), 2)
        put(surf, F["small"], "ENTRADA", (cx, cy), WHITE, anchor="center")
        pygame.draw.circle(surf, RED, (cx - 40, cy), 6)
        pygame.draw.circle(surf, GREEN, (cx + 40, cy), 6)''')

# 5) manual
rep('''- @n Naranja: atención (recogida de combustible, misión a punto de caducar).
''', '''- @n Naranja: atención (recogida de combustible, misión a punto de caducar).
- BAJA (a pie), DERRIBO (nave) y DERRIBO (SRV): número, créditos y lo que llevas sin cobrar. Azul = bono de combate, verde = recompensa. Lo sin cobrar se guarda en el PC hasta que lo cobras (y se pierde si mueres, como en el juego). Total en 11 SESIÓN.
- @r ¡DESPLEGADO!: al bajar del transporte en una zona de combate a pie; EN VIVO muestra bajas, ritmo y bonos.
''')
rep('''- ATRAQUE: la estación a pantalla completa al conceder el atraque.''',
    '''- ATRAQUE: la estación a pantalla completa al conceder el atraque. Luz roja a la izquierda y verde a la derecha, como en la entrada de la estación.''')

rep('    ("0.65", "MANUAL de uso en AJUSTES y en http://IP:8080/manual"),\n',
    '    ("0.65", "MANUAL de uso en AJUSTES y en http://IP:8080/manual"),\n'
    '    ("0.66", "Bajas a pie y derribos con contador, bonos sin cobrar, zona de combate y luces del atraque"),\n')
s = re.sub(r'PANEL_VER = "v0\.65[^"]*"', 'PANEL_VER = "v0.66 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.66  (copia en panel.py.bak65)")
