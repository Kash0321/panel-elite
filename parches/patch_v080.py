#!/usr/bin/env python3
# Parche v0.80: menu principal (reloj, resumen, mapa nuevo al volver), musica de combate y thargoide,
# menu de Powerplay -> POWERPLAY y menu de escuadron -> ficha ESCUADRON. Necesita el sender v0.80.
import re, shutil, sys, time
P = sys.argv[1] if len(sys.argv) > 1 else "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def view_squad" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.79' not in s:
    sys.exit("Este parche es para la v0.79")
shutil.copy(P, P + ".bak79")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

# --- listas de ALERTAS y CAMBIO AUTO
rep('''("elink", "RECARGA CON ENLACE")]''', '''("elink", "RECARGA CON ENLACE"),
           ("thargmusic", "MÚSICA THARGOIDE")]''')
rep('''             ("fss", "FSS > SISTEMA")]''', '''             ("fss", "FSS > SISTEMA"), ("combatmusic", "MÚSICA COMBATE > COMBATE"),
             ("ppmenu", "MENÚ POWERPLAY > POWERPLAY"), ("sqmenu", "MENÚ ESCUADRÓN > ESCUADRÓN")]''')

# --- notas nuevas: cambios de pantalla y mapa nuevo al volver a la partida
rep('''def handle_note(kind, text):
''', '''def handle_note(kind, text):
    if kind == "combatmusic" and auto_on("combatmusic"):
        foot = (state.get("data") or {}).get("Flags2", 0) & 1
        if ui["view"] not in ((100, 150) if foot else (6, 61)):
            ui["view"] = 100 if foot else 6
    elif kind == "ppmenu" and auto_on("ppmenu"):
        ui["view"] = 3; ui["navtab"] = 2
    elif kind == "sqmenu" and auto_on("sqmenu"):
        ui["view"] = 165
    elif kind == "mainmenu":
        ui["view"] = 100; ui["idle_skip"] = 0
    elif kind == "loadgame":
        track.update(body=None, pts=[], kills=[], items=[], last=None, raw=None, fast=False)
''')

# --- aviso thargoide por la musica
rep('''        elif kind == "gravity" and len(p) >= 2:''', '''        elif kind == "thargmusic":
            xa["a"] = dict(until=now + 6, col=(120, 230, 120), title="ENCUENTRO THARGOIDE",
                           big="MÚSICA DE ALERTA", lines=["el juego ha puesto la música thargoide"])
            play("alarm")
        elif kind == "gravity" and len(p) >= 2:''')

# --- menu principal: reloj en las dos pantallas (con el resumen de la sesion encima)
rep('''    ui["idle_on"] = not online and ui["view"] in (0, 100) and now > ui["idle_skip"] and now - ui["start"] > 8
    if ui["idle_on"]:''', '''    menu_ = online and (d or {}).get("menu")
    ui["idle_on"] = (not online or menu_) and ui["view"] in (0, 100) and now > ui["idle_skip"] and now - ui["start"] > 8
    if ui["idle_on"]:
        if menu_ and not HI_PASS[0]:
            xa_notes(d, now)
        draw_idle(surf, now)
        if menu_:
            draw_xa(surf, now)
            put(surf, F["btn"], "EN EL MENÚ PRINCIPAL", (W // 2, H - 44), ORANGE, anchor="center")
        return
    if False:''')
rep('''    title = ((d or {}).get("system") or "---").upper() if online else "SIN DATOS"''',
    '''    title = ("EN EL MENÚ PRINCIPAL" if (d or {}).get("menu") else ((d or {}).get("system") or "---").upper()) if online else "SIN DATOS"''')
rep('''    mode = big_mode(d, flags)
    hh = 44''', '''    if d.get("menu"):
        draw_idle(cell, now); big_blit(S, cell, S.get_rect())
        put(S, fbig, "EN EL MENÚ PRINCIPAL", (bw // 2, bh - 40), DIM, anchor="center")
        return
    mode = big_mode(d, flags)
    hh = 44''')

# --- ficha ESCUADRON
CODE = r'''
# ---------- v0.80: ficha ESCUADRON (al abrir el menu de escuadron del juego) ----------
def view_squad(surf, d, flags, now):
    d = d or {}
    sq = d.get("squad") or {}
    fr = d.get("friends") or {}
    y = TOP + 6
    if sq.get("name"):
        put(surf, F["big"], sq["name"].upper(), (8, y), ORANGE, W - 16); y += 30
        if sq.get("rank") is not None:
            put(surf, F["btn"], f"tu rango en el escuadrón: {sq['rank']}", (8, y), BLUE, W - 16); y += 24
    else:
        put(surf, F["btn"], "Sin escuadrón (o aún no hay datos)", (8, y), DIM, W - 16); y += 26
    pygame.draw.line(surf, DIM, (8, y), (W - 8, y)); y += 6
    wing = fr.get("wing") or []
    if wing:
        put(surf, F["small"], "ALA", (8, y), DIM); y += 16
        put(surf, F["btn"], ", ".join(str(w) for w in wing)[:60], (8, y), GREEN, W - 16); y += 26
    on = fr.get("on") or []
    put(surf, F["small"], f"AMIGOS CONECTADOS ({len(on)})", (8, y), DIM); y += 16
    for n in on[:6]:
        put(surf, F["btn"], n, (8, y), GREEN, W - 16); y += 22
    if not on:
        put(surf, F["small"], "ninguno ahora mismo", (8, y), DIM); y += 18
    off = fr.get("off") or []
    if off and y < H - 40:
        put(surf, F["small"], "DESCONECTADOS HACE POCO", (8, y + 4), DIM); y += 20
        for n, mins in off[:3]:
            if y > H - 20:
                break
            put(surf, F["small"], f"{n}  ·  hace {mins} min", (8, y), DIM, W - 16); y += 16

VIEWS[165] = view_squad
MENU[165] = "ESCUADRÓN"
PARENT[165] = 0

'''
rep("\ndef render(surf):", CODE + "\ndef render(surf):")

rep('''# Enlace energético''', '''# Menú principal y música del juego (con el sender v0.80)
- Al salir al menú principal: las dos pantallas pasan al reloj con EN EL MENÚ PRINCIPAL y sale el resumen de la sesión. Al volver a la partida el mapa empieza de cero.
- Música de combate: el panel pasa a COMBATE (a pie, a EN VIVO) antes del primer disparo. Se apaga en CAMBIO AUTO.
- Música thargoide: aviso ENCUENTRO THARGOIDE. Se apaga en ALERTAS y en SONIDO Y VOZ.
- Abrir el menú de Powerplay del juego lleva a NAVEGACIÓN > POWERPLAY; el de escuadrón, a la ficha ESCUADRÓN (nombre, tu rango, ala y amigos).
# Enlace energético''')
rep('    ("0.79", "Enlace energético: parado 8 s = RECARGANDO y punto de recarga en el mapa"),\n',
    '    ("0.79", "Enlace energético: parado 8 s = RECARGANDO y punto de recarga en el mapa"),\n'
    '    ("0.80", "Menú principal, música de combate y thargoide, Powerplay y ficha ESCUADRÓN"),\n')
s = re.sub(r'PANEL_VER = "v0\.79[^"]*"', 'PANEL_VER = "v0.80 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)
open(P, "w", encoding="utf-8").write(s)
print("OK v0.80  (copia en " + P + ".bak79)")
