#!/usr/bin/env python3
# Parche v0.81: ficha ESCUADRON con datos de Inara (nombre real de tu rango, otros CMDR). Necesita el sender v0.81.
import re, shutil, sys, time
P = sys.argv[1] if len(sys.argv) > 1 else "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def inara_rank" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.80' not in s:
    sys.exit("Este parche es para la v0.80")
shutil.copy(P, P + ".bak80")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

i0 = s.index("def view_squad(surf, d, flags, now):")
i1 = s.index("VIEWS[165] = view_squad")
s = s[:i0] + r'''INARA_RK = {"combat": "Combat", "trade": "Trade", "exploration": "Explore", "soldier": "Soldier",
            "mercenary": "Soldier", "exobiologist": "Exobiologist", "federation": "Federation", "empire": "Empire"}

def inara_rank(o, which="combat"):
    for n, v, _ in (o or {}).get("ranks") or []:
        if str(n).lower() == which and INARA_RK.get(which) in RANK_NAMES and isinstance(v, int):
            return rank_name(INARA_RK[which], v)
    return ""

def view_squad(surf, d, flags, now):
    d = d or {}
    sq = d.get("squad") or {}
    fr = d.get("friends") or {}
    ina = d.get("inara") or {}
    me = ina.get("me") or {}
    y = TOP + 6
    name = sq.get("name") or me.get("squad")
    if name:
        put(surf, F["big"], name.upper(), (8, y), ORANGE, W - 16); y += 30
        rk = me.get("sqrank") or (f"rango {sq['rank']}" if sq.get("rank") is not None else "")
        if rk:
            n_ = f"  ·  {me['sqn']} miembros" if me.get("sqn") else ""
            put(surf, F["btn"], f"tu rango: {rk}{n_}", (8, y), BLUE, W - 16); y += 24
    else:
        put(surf, F["btn"], "Sin escuadrón (o aún no hay datos)", (8, y), DIM, W - 16); y += 26
    pygame.draw.line(surf, DIM, (8, y), (W - 8, y)); y += 6
    wing = fr.get("wing") or []
    if wing:
        put(surf, F["small"], "ALA", (8, y), DIM)
        put(surf, F["btn"], ", ".join(str(w) for w in wing)[:50], (60, y - 3), GREEN, W - 68); y += 22
    on = fr.get("on") or []
    put(surf, F["small"], f"AMIGOS CONECTADOS ({len(on)})", (8, y), DIM); y += 16
    put(surf, F["btn"], ", ".join(on[:5]) if on else "ninguno ahora mismo", (8, y), GREEN if on else DIM, W - 16); y += 26
    oth = ina.get("others") or []
    if oth:
        put(surf, F["small"], "INARA", (8, y), DIM); y += 16
        for o in oth:
            if y > H - 36:
                break
            bits = [o.get("ship"), inara_rank(o), o.get("squad")]
            put(surf, F["btn"], o.get("name", "?"), (8, y), ORANGE, 130)
            put(surf, F["small"], "  ·  ".join(b for b in bits if b), (140, y + 4), DIM, W - 148); y += 22
    if ina.get("ok"):
        mins = int((time.time() - (ina.get("t") or time.time())) // 60)
        st = f"Inara: hace {mins} min" if mins else "Inara: al día"
    else:
        st = "Inara: sin datos" + (f" ({ina['err']})" if ina.get("err") else "")
    put(surf, F["small"], st, (W - 8, H - 16), DIM, W - 16, anchor="topright")

''' + s[i1:]

rep('''- Abrir el menú de Powerplay del juego lleva a NAVEGACIÓN > POWERPLAY; el de escuadrón, a la ficha ESCUADRÓN (nombre, tu rango, ala y amigos).''',
    '''- Abrir el menú de Powerplay del juego lleva a NAVEGACIÓN > POWERPLAY; el de escuadrón, a la ficha ESCUADRÓN (nombre, tu rango, ala y amigos).
# Inara (solo lectura, con el sender v0.81)
- Pon tu clave de Inara (la misma de EDMC) en inara_clave.txt junto a elite_sender.py. La Pi no la ve.
- Opcional: inara_cmdrs.txt con otros comandantes, uno por línea (por ejemplo KORZO).
- La ficha ESCUADRÓN muestra el nombre real de tu rango y, de los otros CMDR, su nave, rango de combate y escuadrón. Se lee al arrancar y luego cada hora. Lo que sube a Inara lo sigue haciendo EDMC.''')
rep('    ("0.80", "Menú principal, música de combate y thargoide, Powerplay y ficha ESCUADRÓN"),\n',
    '    ("0.80", "Menú principal, música de combate y thargoide, Powerplay y ficha ESCUADRÓN"),\n'
    '    ("0.81", "Inara (solo lectura): nombre de tu rango de escuadrón y otros CMDR en ESCUADRÓN"),\n')
s = re.sub(r'PANEL_VER = "v0\.80[^"]*"', 'PANEL_VER = "v0.81 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)
open(P, "w", encoding="utf-8").write(s)
print("OK v0.81  (copia en " + P + ".bak80)")
