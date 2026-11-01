#!/usr/bin/env python3
# Parche v0.71: llegada al salir de supercrucero y senales con amenaza, modo OPERATIONS (inicio, resumen, Merc Coin,
# meritos), granadas lanzadas, sueldo del copiloto, SISTEMA grande sin botones en la pantalla grande,
# senales en el diario y clic del raton del PC sobre la pagina de EMITIR.
import re, shutil, sys, time
P = sys.argv[1] if len(sys.argv) > 1 else "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def view_orrery_big" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.70' not in s:
    sys.exit("Este parche es para la v0.70")
shutil.copy(P, P + ".bak70")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

CODE = r'''
# ---------- v0.71 ----------
TYPE_ES = {"Station": "estación", "Planet": "planeta", "Star": "estrella", "PlanetaryRing": "anillo"}

def threat_col(t):
    return GREEN if t <= 2 else ORANGE if t <= 4 else RED

# EN VIVO en la nave: operacion en curso y Merc Coin
def view_live_v071(surf, d, flags, now):
    view_live(surf, d, flags, now)
    d = d or {}
    if d.get("Flags2", 0) & 1 or flags & (1 << 26):
        return
    O = d.get("ops") or {}
    y = H - 20
    if O.get("merc") is not None:
        txt = f"MERC COIN {fnum(O['merc'], 0)}" + (f"  (+{O['lastgain']})" if O.get("lastgain") else "")
        put(surf, F["small"], txt, (8, y), ORANGE)
    c_ = (O.get("crew") or {})
    if c_.get("paid"):
        put(surf, F["small"], f"copiloto {c_.get('name', '')}: -{crx(c_['paid'])} cr", (W - 8, y), DIM, 240, anchor="topright")
    if O.get("on"):
        mins = int((now - (O.get("t0") or now)) // 60)
        put(surf, F["small"], f"OPERACIÓN · {O.get('target') or O.get('mission') or ''} · {O.get('kills', 0)} derribos · "
                              f"{crx(O.get('cr', 0))} cr · {mins} min", (8, y - 18), RED, W - 16)

# SISTEMA en la pantalla grande: sin botones, mapa a todo lo ancho y ficha automatica
ORR_XS = [1.0]

def or_side_big(surf, d, orbits):
    d = d or {}
    want = [((d.get("dest") or {}).get("name")), d.get("body")]
    o = next((x for w_ in want if w_ for x in orbits if x.get("name") == w_), None)
    if o is None:
        cand = [x for x in orbits if x.get("name") and not x.get("mapped")]
        o = max(cand, key=lambda x: x.get("value") or 0, default=None)
    put(surf, F["small"], SPEEDS[orr["speed"]][1] + ("  ·  PAUSA" if orr["paused"] else ""), (W - 6, H - 16), DIM, anchor="topright")
    if not o:
        return
    system = (d.get("explo") or {}).get("system") or ""
    nm = o["name"]
    short = nm[len(system):].strip() if system and nm.startswith(system) else nm
    box = pygame.Rect(W - 168, TOP + 4, 162, 74)
    pygame.draw.rect(surf, BLACK, box)
    pygame.draw.rect(surf, DIM, box, 1, border_radius=4)
    put(surf, F["btn"], short or nm, (box.x + 6, box.y + 3), ORANGE, box.w - 12)
    put(surf, F["small"], o.get("cls", ""), (box.x + 6, box.y + 22), bcol(o), box.w - 12)
    put(surf, F["small"], f"{o.get('dist', 0):,} ls".replace(",", "."), (box.x + 6, box.y + 38), DIM)
    put(surf, F["small"], ("1º " if o.get("first") else "") + ("MAPEADO" if o.get("mapped") else ""), (box.right - 6, box.y + 38), GREEN, anchor="topright")
    put(surf, F["small"], f"~ {cr(o.get('value'))} cr", (box.x + 6, box.y + 54), ORANGE)

def view_orrery_big(surf, d, flags, now):
    global OR_AREA, draw_or_side
    keep = (OR_AREA, draw_or_side, orr.get("hits"), orr.get("scale"))
    OR_AREA = pygame.Rect(0, TOP, W, H - TOP)
    draw_or_side = or_side_big
    ORR_XS[0] = (W / 2 - 14) / max(1, (H - TOP) / 2 - 14)
    orr["scale"] = None
    try:
        view_orrery(surf, d, flags, now)
    finally:
        OR_AREA, draw_or_side, orr["hits"], orr["scale"] = keep
        ORR_XS[0] = 1.0

# clic del raton del PC sobre la pagina de EMITIR
def remote_tap(x, y, w, h, which):
    if (w, h) == (W, H) or which == "p":
        px, py = x * W / max(1, w), y * H / max(1, h)
    else:
        if not hdmi_panel():
            return
        sc = min(w / W, h / H)
        px, py = (x - (w - W * sc) / 2) / sc, (y - (h - H * sc) / 2) / sc
    if 0 <= px < W and 0 <= py < H:
        mouse.update(x=px, y=py, t=time.time())
        on_tap(int(px), int(py))

VIEWS[100] = view_live_v071

'''
rep("\ndef render(surf):", CODE + "\ndef render(surf):")

# el mapa del sistema puede estirarse a lo ancho (solo en la pantalla grande)
rep("        return cx + dx / dd * r, cy - dy / dd * r", "        return cx + dx / dd * r * ORR_XS[0], cy - dy / dd * r")
rep("    fn = view_navbig if v == 3 else VIEWS.get(v)", "    fn = view_navbig if v == 3 else view_orrery_big if v == 72 else VIEWS.get(v)")

# diario: senales visitadas
rep('''            ("MUESTRAS BIO", X.get("bio", 0), WHITE)]''', '''            ("MUESTRAS BIO", X.get("bio", 0), WHITE), ("SEÑALES VISITADAS", X.get("signals", 0), WHITE)]''')

# sesion: sueldo del copiloto
rep('''    put(surf, F["small"], f"toca para ver AMIGOS ({n} conectados)", (8, 252), GREEN if n else DIM)''',
    '''    paid_ = (((d or {}).get("ops") or {}).get("crew") or {}).get("paid")
    put(surf, F["small"], f"toca para ver AMIGOS ({n} conectados)" + (f"  ·  copiloto -{crx(paid_)} cr" if paid_ else ""),
        (8, 252), GREEN if n else DIM, W - 16)''')

# avisos nuevos
rep('''        elif kind == "pickup" and len(p) >= 3:''', '''        elif kind == "arrive" and len(p) >= 5:
            nm, t_, body_, btype = p[0], int(p[1] or 0), p[2], p[3]
            if nm and (p[4] == "1" or btype == "Station"):
                xa["a"] = dict(until=now + 4, col=BLUE, title="LLEGADA A", big=nm.upper(), lines=[body_] if body_ and body_ != nm else [])
                if cfg["auto"]:
                    ui["view"] = 8
            elif nm:
                conflict = "conflict" in nm.lower()
                xa["a"] = dict(until=now + 6, col=RED if conflict else threat_col(t_), title=f"SEÑAL  ·  AMENAZA {t_}",
                               big=nm.upper(), lines=["zona de conflicto" if conflict else "salida de supercrucero"])
                if t_ >= 3 or conflict:
                    play("alarm")
                    if cfg["auto"]:
                        ui["view"] = 6
            elif btype == "Station" and body_:
                xa["a"] = dict(until=now + 3, col=BLUE, title="LLEGADA A", big=body_.upper(), lines=[])
        elif kind == "thrown" and len(p) >= 3:
            xa["a"] = dict(until=now + 2, col=GREY, title=f"{p[1].upper()} LANZADO", big=f"quedan {p[2]}", lines=[])
        elif kind == "opstart" and len(p) >= 2:
            xa["a"] = dict(until=now + 6, col=ORANGE, title="OPERACIÓN INICIADA", big=(p[0] or "").upper(),
                           lines=[f"escuadrón {p[1]}"] if p[1] else [])
            play("ok")
        elif kind == "opend" and len(p) >= 5:
            l1 = f"{p[0]} derribos  ·  {p[4]} min" + (f"  ·  +{p[2]} Merc Coin" if p[2] not in ("", "0") else "")
            l2 = (f"+{p[3]} méritos  ·  " if p[3] not in ("", "0") else "") + "cobra al salir, en una estación"
            xa["a"] = dict(until=now + 12, col=GREEN, title="OPERACIÓN TERMINADA", big=f"{crx(float(p[1] or 0))} cr", lines=[l1, l2])
            play("ok")
        elif kind == "pickup" and len(p) >= 3:''')

# EMITIR: el clic en la imagen es un toque en el panel
rep('''STREAM_HTML = ("<!doctype html>''', '''CLICK_JS = """<script>
(function(){const im=document.querySelector('img');if(!im)return;im.style.cursor='pointer';
im.addEventListener('click',ev=>{const r=im.getBoundingClientRect(),nw=im.naturalWidth,nh=im.naturalHeight;if(!nw)return;
const sc=Math.min(r.width/nw,r.height/nh),dx=(r.width-nw*sc)/2,dy=(r.height-nh*sc)/2;
const x=Math.round((ev.clientX-r.left-dx)/sc),y=Math.round((ev.clientY-r.top-dy)/sc);
if(x<0||y<0||x>=nw||y>=nh)return;
fetch('/tap?x='+x+'&y='+y+'&w='+nw+'&h='+nh+'&s='+(im.src.indexOf('/panel')>=0?'p':'h'),{cache:'no-store'});});})();
</script>"""

STREAM_HTML = ("<!doctype html>''')
rep('''"<img src='/hdmi' style='width:100vw;height:100vh;object-fit:contain'>" + VOICE_JS +''',
    '''"<img src='/hdmi' style='width:100vw;height:100vh;object-fit:contain'>" + CLICK_JS + VOICE_JS +''')
rep('''            if path == "/manual":''', '''            if path == "/tap":
                try:
                    q = dict(kv.split("=", 1) for kv in self.path.split("?", 1)[1].split("&"))
                    remote_tap(int(q["x"]), int(q["y"]), int(q["w"]), int(q["h"]), q.get("s", "h"))
                except Exception:
                    pass
                self.send_response(204)
                self.end_headers()
                return
            if path == "/manual":''')

# manual
rep('''# Gafas de VR''', '''# Manejar el panel desde el PC
Con el ratón del PC: clic sobre la imagen = tocar el panel. Funciona con la pantalla pequeña (?pequena) y con la HDMI en modo PANEL.
# Gafas de VR''')
rep('''- @r ¡DESPLEGADO!:''', '''- LLEGADA A (estación) al salir de supercrucero; en las SEÑALES su nivel de AMENAZA (verde 0-2, naranja 3-4, rojo 5 o más) y las zonas de conflicto.
- @n OPERACIÓN INICIADA / TERMINADA (modo Operations): nave, escuadrón y al terminar el resumen con créditos, derribos, Merc Coin y méritos. Las bajas a pie dentro de la nave de carga no las registra el juego.
- GRANADA / PROYECTOR LANZADO: lo que te queda.
- @r ¡DESPLEGADO!:''')
rep('''- VIAJE: en vivo, navegación, exploración y sistema.''', '''- VIAJE: en vivo, navegación, exploración y sistema (en la grande, el SISTEMA sale a todo lo ancho, sin botones y con la ficha del cuerpo más interesante).''')

rep('    ("0.70", "Ratón y teclado; la HDMI puede mostrar el PANEL (TAB o clic derecho)"),\n',
    '    ("0.70", "Ratón y teclado; la HDMI puede mostrar el PANEL (TAB o clic derecho)"),\n'
    '    ("0.71", "Llegada y señales, OPERATIONS, Merc Coin, copiloto, SISTEMA grande y clic desde el PC"),\n')
s = re.sub(r'PANEL_VER = "v0\.70[^"]*"', 'PANEL_VER = "v0.71 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.71  (copia en " + P + ".bak70)")
