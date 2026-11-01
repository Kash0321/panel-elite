#!/usr/bin/env python3
# Parche v0.82: ficha ESCUADRON por paginas con todos los comandantes de inara_cmdrs.txt (hasta 30).
import re, shutil, sys, time
P = sys.argv[1] if len(sys.argv) > 1 else "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def view_squad_page" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.81' not in s:
    sys.exit("Este parche es para la v0.81")
shutil.copy(P, P + ".bak81")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

rep('''    oth = ina.get("others") or []
    if oth:
        put(surf, F["small"], "INARA", (8, y), DIM); y += 16
        for o in oth:
            if y > H - 36:
                break
            bits = [o.get("ship"), inara_rank(o), o.get("squad")]
            put(surf, F["btn"], o.get("name", "?"), (8, y), ORANGE, 130)
            put(surf, F["small"], "  ·  ".join(b for b in bits if b), (140, y + 4), DIM, W - 148); y += 22''',
    '''    oth = ina.get("others") or []
    if oth:
        n_on = sum(1 for o in oth if o.get("name") in on)
        put(surf, F["small"], "INARA", (8, y), DIM); y += 16
        put(surf, F["btn"], f"{len(oth)} comandantes  ·  {n_on} conectados  ·  toca para verlos", (8, y), ORANGE, W - 16)''')
rep('''def view_squad(surf, d, flags, now):
    d = d or {}''', '''SQ_PER = 6

def squad_pages(d):
    oth = (((d or {}).get("inara") or {}).get("others")) or []
    return 1 + (len(oth) + SQ_PER - 1) // SQ_PER

def view_squad_page(surf, d, pg):
    """Pagina pg (1..): miembros con nave, rango de combate, escuadron y si estan conectados."""
    ina = d.get("inara") or {}
    on = set((d.get("friends") or {}).get("on") or [])
    oth = sorted(ina.get("others") or [], key=lambda o: (o.get("name") not in on, (o.get("name") or "").lower()))
    y = TOP + 6
    put(surf, F["small"], "COMANDANTE", (8, y), DIM)
    put(surf, F["small"], "NAVE  ·  COMBATE  ·  ESCUADRÓN", (170, y), DIM); y += 18
    for o in oth[(pg - 1) * SQ_PER:pg * SQ_PER]:
        live = o.get("name") in on
        pygame.draw.circle(surf, GREEN if live else DIM, (14, y + 10), 5, 0 if live else 1)
        put(surf, F["btn"], o.get("name", "?"), (26, y + 2), GREEN if live else ORANGE, 140)
        bits = [o.get("ship"), inara_rank(o), o.get("squad")]
        put(surf, F["small"], "  ·  ".join(b for b in bits if b) or "sin datos públicos", (170, y + 6), DIM, W - 178)
        y += 36
    put(surf, F["small"], f"pág {pg + 1}/{squad_pages(d)}  ·  verde = conectado  ·  toca", (W - 8, H - 16), DIM,
        W - 16, anchor="topright")

def tap_squad(x, y):
    with lock:
        d = state["data"]
    ui["sqpage"] = (ui.get("sqpage", 0) + 1) % squad_pages(d)

def view_squad(surf, d, flags, now):
    d = d or {}
    pg = ui.get("sqpage", 0) % squad_pages(d)
    if pg:
        return view_squad_page(surf, d, pg)''')
rep('''    elif v == 164:
        tap_keys(x, y); return''', '''    elif v == 164:
        tap_keys(x, y); return
    elif v == 165:
        tap_squad(x, y); return''')
rep('''    elif kind == "sqmenu" and auto_on("sqmenu"):
        ui["view"] = 165''', '''    elif kind == "sqmenu" and auto_on("sqmenu"):
        ui["view"] = 165; ui["sqpage"] = 0''')
rep('''- Opcional: inara_cmdrs.txt con otros comandantes, uno por línea (por ejemplo KORZO).''',
    '''- Opcional: inara_cmdrs.txt con otros comandantes, uno por línea (hasta 30: todo tu escuadrón). En ESCUADRÓN, tocando pasas las páginas: 6 por página, primero los conectados (en verde).''')
rep('    ("0.81", "Inara (solo lectura): nombre de tu rango de escuadrón y otros CMDR en ESCUADRÓN"),\n',
    '    ("0.81", "Inara (solo lectura): nombre de tu rango de escuadrón y otros CMDR en ESCUADRÓN"),\n'
    '    ("0.82", "ESCUADRÓN por páginas: hasta 30 comandantes, conectados primero"),\n')
s = re.sub(r'PANEL_VER = "v0\.81[^"]*"', 'PANEL_VER = "v0.82 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)
open(P, "w", encoding="utf-8").write(s)
print("OK v0.82  (copia en " + P + ".bak81)")
