#!/usr/bin/env python3
# Parche v0.67: EN COMBATE a pie (pantalla grande en 2 cuadros: EN VIVO + SRV/RHINO/A PIE) y avisos de salud al 75/50/25 %
import re, shutil, sys, time
P = "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def in_fight" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.66' not in s:
    sys.exit("Este parche es para la v0.66")
shutil.copy(P, P + ".bak66")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

# 1) estado EN COMBATE: te atacan, escudo caido, baja o despliegue en los ultimos 60 s
rep('''def process_notes(d):''', '''FIGHT_SECS = 60
fight = {"t": 0.0}
FIGHT_KINDS = ("underattack", "shields_down", "kill", "deploy", "interdicted")

def in_fight(d, now=None):
    return bool(d) and bool(d.get("Flags2", 0) & 1) and (now or time.time()) - fight["t"] < FIGHT_SECS

def process_notes(d):''')
rep('''        if seq > ui["note_seq"]:
            ui["note_seq"] = seq
            handle_note(kind, text)''', '''        if seq > ui["note_seq"]:
            ui["note_seq"] = seq
            if kind in FIGHT_KINDS:
                fight["t"] = time.time()
            handle_note(kind, text)''')

# 2) pantalla grande: a pie y en combate, 2 cuadros (EN VIVO y SRV / RHINO / A PIE)
rep('''def big_mode(d, flags):
    f2 = d.get("Flags2", 0)
''', '''def big_mode(d, flags):
    f2 = d.get("Flags2", 0)
    if in_fight(d):
        return "COMBATE A PIE"
''')
rep('''BIG_SETS = {''', '''BIG_SETS = {"COMBATE A PIE": [100, 5], ''')
rep('''    for i, v in enumerate(cells):
        r = pygame.Rect((i % 2) * cw, hh + (i // 2) * ch, cw, ch)
        big_cell(S, cell, v, d, flags, now, r, fsm, "fill")''', '''    if len(cells) == 2:
        # dos cuadros, uno al lado del otro y a toda la altura
        for i, v in enumerate(cells):
            big_cell(S, cell, v, d, flags, now, pygame.Rect(i * cw, hh, cw, bh - hh), fbig, "fit")
        return
    for i, v in enumerate(cells):
        r = pygame.Rect((i % 2) * cw, hh + (i // 2) * ch, cw, ch)
        big_cell(S, cell, v, d, flags, now, r, fsm, "fill")''')

# 3) EN VIVO a pie: indicador EN COMBATE
rep('''    y = TOP + 4
    put(surf, F["big"], mode, (8, y), GREEN)''', '''    y = TOP + 4
    put(surf, F["big"], mode, (8, y), GREEN)
    if mode == "A PIE" and in_fight(d, now):
        tw_ = F["big"].size(mode)[0]
        r_ = pygame.Rect(16 + tw_, y + 2, 112, 22)
        on_ = int(now * 2) % 2 == 0
        pygame.draw.rect(surf, RED, r_, 0 if on_ else 2, border_radius=4)
        put(surf, F["small"], "EN COMBATE", r_.center, BLACK if on_ else RED, anchor="center")''')

# 4) salud a pie: avisos al 75 %, 50 % y 25 % (una vez por bajada; se rearma al curarte por encima del 75 %)
rep('''    # avisos de peligro a pie y combustible del vehiculo (al empezar cada situacion)''', '''    hp_ = (d.get("live") or {}).get("health")
    if d.get("Flags2", 0) & 1 and isinstance(hp_, (int, float)):
        lvl = 3 if hp_ < 0.25 else 2 if hp_ < 0.5 else 1 if hp_ < 0.75 else 0
        prev = xa.get("hplvl", 0)
        if lvl > prev and cfg["alerts"]:
            xa["a"] = dict(until=now + (4 if lvl > 1 else 3), col=ORANGE if lvl == 1 else RED, title="SALUD BAJA",
                           big=f"{hp_ * 100:.0f} %", lines=["usa un botiquín" if lvl < 3 else "¡BOTIQUÍN YA!"])
            if lvl > 1:
                play("alarm")
        xa["hplvl"] = 0 if lvl == 0 else max(prev, lvl)
    else:
        xa["hplvl"] = 0
    # avisos de peligro a pie y combustible del vehiculo (al empezar cada situacion)''')

# 5) manual
rep('''- COMBATE: combate, registro de combate y pips.''', '''- COMBATE: combate, registro de combate y pips.
- COMBATE A PIE: EN VIVO y SRV / RHINO / A PIE, uno al lado del otro.''')
rep('''- @r ¡DESPLEGADO!:''', '''- @r EN COMBATE (a pie): si en el último minuto te han atacado, ha caído tu escudo o has hecho una baja.
- @n SALUD BAJA a pie: avisa al 75 %, y con alarma al 50 % y al 25 %.
- @r ¡DESPLEGADO!:''')

rep('    ("0.66", "Bajas a pie y derribos con contador, bonos sin cobrar, zona de combate y luces del atraque"),\n',
    '    ("0.66", "Bajas a pie y derribos con contador, bonos sin cobrar, zona de combate y luces del atraque"),\n'
    '    ("0.67", "EN COMBATE a pie (grande en 2 cuadros) y salud baja al 75/50/25 %"),\n')
s = re.sub(r'PANEL_VER = "v0\.66[^"]*"', 'PANEL_VER = "v0.67 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.67  (copia en panel.py.bak66)")
