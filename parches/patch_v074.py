#!/usr/bin/env python3
# Parche v0.74: Merc Coin en rosa, PANEL nitido en la HDMI y en la web, teclas del PC en la web,
# FPS de la pantalla grande (AUTO/3/5/10), fecha del juego junto a la hora y plataforma exacta (hora y profundidad).
import re, shutil, sys, time
P = sys.argv[1] if len(sys.argv) > 1 else "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def panel_hi" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.73' not in s:
    sys.exit("Este parche es para la v0.73")
shutil.copy(P, P + ".bak73")

def rep(old, new, all_=False):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new) if all_ else s.replace(old, new, 1)

# ---------- 1. Merc Coin en rosa ----------
rep('''        put(surf, F["small"], txt, (8, y), ORANGE)
    c_ = (O.get("crew") or {})''', '''        put(surf, F["small"], txt, (8, y), MERC)
    c_ = (O.get("crew") or {})''')
rep('''            l1 = f"{p[0]} derribos  ·  {p[4]} min" + (f"  ·  +{p[2]} Merc Coin" if p[2] not in ("", "0") else "")
            l2 = (f"+{p[3]} méritos  ·  " if p[3] not in ("", "0") else "") + "cobra al salir, en una estación"
            xa["a"] = dict(until=now + 12, col=GREEN, title="OPERACIÓN TERMINADA", big=f"{crx(float(p[1] or 0))} cr", lines=[l1, l2])''',
    '''            l1 = f"{p[0]} derribos  ·  {p[4]} min" + (f"  ·  +{p[3]} méritos" if p[3] not in ("", "0") else "")
            lm = (f"+{p[2]} MERC COIN", MERC) if p[2] not in ("", "0") else ""
            xa["a"] = dict(until=now + 12, col=GREEN, title="OPERACIÓN TERMINADA", big=f"{crx(float(p[1] or 0))} cr",
                           lines=[l1, lm, "cobra al salir, en una estación"])''')
rep('''    for ln_ in a["lines"]:
        if ln_:
            put(surf, F["btn"], ln_, (cx, y), col, box.w - 20, anchor="midtop")''', '''    for ln_ in a["lines"]:
        if ln_:
            t_, c2 = ln_ if isinstance(ln_, tuple) else (ln_, col)
            put(surf, F["btn"], t_, (cx, y), c2, box.w - 20, anchor="midtop")''')
rep('''def draw_xa(surf, now):''', '''MERC = (255, 80, 200)      # rosa de las Merc Coin, como en el juego

def draw_xa(surf, now):''')

# ---------- 2. PANEL nitido (HDMI en modo PANEL y pagina /panel) ----------
rep('''    if online:
        process_notes(d)
        track_update(d, now)
    if now - ui["start"] < 3:''', '''    if online and not HI_PASS[0]:
        process_notes(d)
        track_update(d, now)
    if now - ui["start"] < 3:''')
rep('''    xa_notes(d if online else None, now)
    draw_xa(surf, now)
    if cfg.get("voice") or cfg.get("stream"):
        voice_watch()''', '''    if not HI_PASS[0]:
        xa_notes(d if online else None, now)
    draw_xa(surf, now)
    if (cfg.get("voice") or cfg.get("stream")) and not HI_PASS[0]:
        voice_watch()''')
rep('''def render_big_panel(S):
    src = PANEL_SURF[0]''', '''def render_big_panel(S):
    hi = panel_hi() if cfg.get("sharp") else None
    if hi is not None:
        S.fill(BLACK)
        S.blit(hi, ((BIG["w"] - hi.get_width()) // 2, (BIG["h"] - hi.get_height()) // 2))
        return True
    src = PANEL_SURF[0]''')
rep('''        stream["small"] = small.copy()''', '''        hi = panel_hi() if cfg.get("sharp") else None
        stream["small"] = (hi if hi is not None else small).copy()''')

# ---------- 3. teclas del PC en la pagina web ----------
rep('''{cache:'no-store'});});})();
</script>"""''', '''{cache:'no-store'});});})();
document.addEventListener('keydown',ev=>{const k={Escape:'esc',Backspace:'esc',m:'m',M:'m',a:'a',A:'a',Tab:'tab'}[ev.key];
if(!k)return;ev.preventDefault();fetch('/key?k='+k,{cache:'no-store'});});
</script>"""''')
rep('''            if path == "/tap":''', '''            if path == "/key":
                k = self.path.split("k=", 1)[-1][:4]
                if k == "esc":
                    on_tap(*BACK.center)
                elif k == "m":
                    ui["view"] = 0
                elif k == "a":
                    ui["view"] = 12
                elif k == "tab":
                    hdmi_toggle()
                self.send_response(204)
                self.end_headers()
                return
            if path == "/tap":''')

# ---------- 4. FPS de la pantalla grande ----------
rep('''            if BIG["n"] % 3 == 0 or hdmi_panel():''', '''            if big_due() or hdmi_panel():''', all_=True)
rep('''def big_cell(S, cell, v, d, flags, now, r, font, how, extra=""):
''', '''def big_cell(S, cell, v, d, flags, now, r, font, how, extra=""):
    if v in (72, 150):
        BIG["fast"] = True          # mapa del sistema o plano a pie: se mueven
''')
rep('''def render_big():
    S, cell = BIG["surf"], BIG["cell"]
''', '''def render_big():
    S, cell = BIG["surf"], BIG["cell"]
    BIG["fast"] = False
''')

# ---------- 5. fecha del juego junto a la hora ----------
rep('''        bx = pygame.Rect(bw // 2 + 20, 12, 240, 18)''', '''        bx = pygame.Rect(bw // 2 + 20, 12, 160, 18)''')
rep('''    put(S, fbig, time.strftime("%H:%M"), (bw - 12, 9), ORANGE, anchor="topright")
''', '''    put(S, fbig, time.strftime("%H:%M"), (bw - 12, 9), ORANGE, anchor="topright")
    put(S, fsm, game_date().upper(), (bw - 28 - fbig.size(time.strftime("%H:%M"))[0], 16), BLUE, anchor="topright")
''')

# ---------- 6. plataforma exacta: hora y profundidad ----------
rep('''def pad_clock(pad):
    """Hora aproximada (1-12) de la plataforma, mirando desde la ranura de entrada."""
    sector = int((pad - 1) * 12 / 45)
    return (6 + sector - 1) % 12 + 1
''', '''# 45 plataformas en 3 bloques de 15; cada bloque ocupa 4 horas. (sector dentro del bloque, profundidad)
PAD_GRP = [(0, 0), (0, 0), (0, 2), (0, 2), (1, 0), (1, 0), (1, 1), (1, 2), (2, 0), (2, 2),
           (3, 0), (3, 0), (3, 1), (3, 2), (3, 2)]
PAD_DEPTH = ["ENTRADA", "MEDIO", "FONDO"]

def pad_pos(pad):
    """(hora 1-12, profundidad 0 entrada / 1 medio / 2 fondo), mirando desde la ranura de entrada."""
    p = (int(pad) - 1) % 45
    sct, dep = PAD_GRP[p % 15]
    sct += (p // 15) * 4
    return (6 + sct) % 12 or 12, dep

def pad_clock(pad):
    return pad_pos(pad)[0]
''')
rep('''        hour = pad_clock(pad)
        for h in range(12):
            a0, a1 = math.radians(h * 30 - 105), math.radians(h * 30 - 75)
            pts = [(cx, cy)] + [(cx + rad * math.cos(a0 + (a1 - a0) * t / 6), cy + rad * math.sin(a0 + (a1 - a0) * t / 6)) for t in range(7)]
            on = (h or 12) == hour
            pygame.draw.polygon(surf, ORANGE if on else BLACK, pts)
            pygame.draw.polygon(surf, DIM, pts, 1)''', '''        hour, dep = pad_pos(pad)
        RR = (rad, rad * 0.75, rad * 0.54, rad * 0.34)
        for h in range(12):
            a0, a1 = math.radians(h * 30 - 105), math.radians(h * 30 - 75)
            angs = [a0 + (a1 - a0) * t / 6 for t in range(7)]
            for k in range(3):
                ro, ri = RR[k], RR[k + 1]
                pts = [(cx + ro * math.cos(a), cy + ro * math.sin(a)) for a in angs] + \\
                      [(cx + ri * math.cos(a), cy + ri * math.sin(a)) for a in reversed(angs)]
                on = (h or 12) == hour and k == dep
                pygame.draw.polygon(surf, ORANGE if on else BLACK, pts)
                pygame.draw.polygon(surf, DIM, pts, 1)''')
rep('''            put(surf, F["small"], f"a las {pad_clock(pad)} (aprox.)", (x0, y), ORANGE); y += 18''',
    '''            h_, d_ = pad_pos(pad)
            put(surf, F["btn"], f"a las {h_}  ·  {PAD_DEPTH[d_]}", (x0, y), ORANGE); y += 22''')

CODE = r'''
# ---------- v0.74: PANEL nitido y FPS de la pantalla grande ----------
HI_PASS = [False]
PHI = {"surf": None, "n": -1, "fail": 0.0}
BIGFPS = ["AUTO", "3", "5", "10"]

def panel_hi():
    """El panel (pantalla pequena) dibujado a tamano grande: para la HDMI en modo PANEL y la web /panel."""
    if PHI["n"] == BIG["n"] and PHI["surf"] is not None:
        return PHI["surf"]
    if time.time() - PHI["fail"] < 60:
        return None
    bw, bh = BIG["w"] or 1024, BIG["h"] or 600
    sc = min(bw / W, bh / H)
    size = (int(W * sc), int(H * sc))
    real = PHI["surf"] if PHI["surf"] is not None and PHI["surf"].get_size() == size else pygame.Surface(size)
    keep = dict(F)
    HI_IDS.clear(); HI_KEEP.clear()
    F.update(hi_fonts(sc))
    HI_PASS[0] = True
    try:
        ss = ScaledSurf(real, sc, sc)
        if ui.get("bye"):
            draw_bye(ss)
        else:
            render(ss); decorate(ss); draw_borders(real); rhino_banner(ss)
        draw_pointer(ss)
    except Exception as e:
        log_exc("panel nitido", e)
        PHI["fail"] = time.time()
        return None
    finally:
        HI_PASS[0] = False
        F.clear(); F.update(keep)
        HI_IDS.clear(); HI_KEEP.clear()
    PHI.update(surf=real, n=BIG["n"])
    return real

def big_due():
    f = cfg.get("bigfps", "AUTO")
    if f == "AUTO":
        f = "10" if BIG.get("fast") else "3"
    step = {"3": 3, "5": 2, "10": 1}.get(f, 3)
    return BIG["n"] % step == 0

'''
rep("\ndef render(surf):", CODE + "\ndef render(surf):")

# AJUSTES > PANTALLA: MODO, NITIDEZ y FPS
i0 = s.index("# 12 AJUSTES > PANTALLA: MODO y NITIDEZ")
i1 = s.index("VIEWS[160] = view_pantalla")
s = s[:i0] + r'''# 12 AJUSTES > PANTALLA: MODO, NITIDEZ y FPS
def view_pantalla(surf, d, flags, now):
    f = cfg.get("bigfps", "AUTO")
    items = [("MODO", BIGMODES.get(cfg.get("bigmode", "4"), "4 CUADROS"), False),
             ("NITIDEZ", "ALTA" if cfg.get("sharp") else "NORMAL", bool(cfg.get("sharp"))),
             ("FPS", "AUTO (3/10)" if f == "AUTO" else f"{f} por seg.", False)]
    for i, (t, sub, fill) in enumerate(items):
        draw_button(surf, grid(i, 3, 1, TOP, H - 40), t, sub, F["big"], filled=fill, lit=flash.get((160, i), 0) > now)
    put(surf, F["small"], "Toca para cambiar. FPS AUTO: rápido solo con mapas.",
        (W // 2, H - 30), DIM, W - 16, anchor="midtop")

def tap_pantalla(x, y):
    for i in range(3):
        if not grid(i, 3, 1, TOP, H - 40).collidepoint(x, y):
            continue
        tap_flash((160, i))
        if i == 0:
            order = list(BIGMODES)
            cfg["bigmode"] = order[(order.index(cfg.get("bigmode", "4")) + 1) % len(order)]
        elif i == 1:
            cfg["sharp"] = not cfg.get("sharp", True)
        else:
            cfg["bigfps"] = BIGFPS[(BIGFPS.index(cfg.get("bigfps", "AUTO")) + 1) % len(BIGFPS)]
        save_cfg()
        return

''' + s[i1:]

# --- manual
rep('''- ESC = atrás  ·  M = menú  ·  A = ajustes.''',
    '''- ESC = atrás  ·  M = menú  ·  A = ajustes.
- En la página web del PC (EMITIR) también funcionan ESC, M, A y TAB.''')
rep('''- Pestañas: algunos menús tienen varias páginas''', '''- En la pantalla grande, a la izquierda de la hora, la fecha del juego.
- Pestañas: algunos menús tienen varias páginas''')

rep('    ("0.73", "ALERTAS y CAMBIO AUTO uno a uno (OPCIONES); NITIDEZ ALTA por defecto"),\n',
    '    ("0.73", "ALERTAS y CAMBIO AUTO uno a uno (OPCIONES); NITIDEZ ALTA por defecto"),\n'
    '    ("0.74", "Merc Coin rosa, PANEL nítido, teclas en la web, FPS, fecha del juego, plataforma exacta"),\n')
s = re.sub(r'PANEL_VER = "v0\.73[^"]*"', 'PANEL_VER = "v0.74 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.74  (copia en " + P + ".bak73)")
