#!/usr/bin/env python3
# Parche v0.62: pantalla grande con 3 modos (4 CUADROS / MIXTO / GRANDE) desde 12 AJUSTES -> PANTALLA
import re, shutil, sys, time
P = "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def big_cell" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.61' not in s:
    sys.exit("Este parche es para la v0.61")
shutil.copy(P, P + ".bak61")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

# dibujo de un cuadro en cualquier tamano + los tres repartos
rep('''    for i, v in enumerate(cells):
        r = pygame.Rect((i % 2) * cw, hh + (i // 2) * ch, cw, ch)
        cell.fill(BLACK)
        fn = view_navbig if v == 3 else VIEWS.get(v)
        try:
            if fn:
                fn(cell, d, flags, now)
        except Exception as e:
            put(cell, F["small"], f"error: {e}"[:60], (8, TOP + 8), RED)
        pygame.draw.rect(S, DIM, r.inflate(-4, -4), 1, border_radius=6)
        put(S, fsm, str(MENU.get(v, v)).upper(), (r.x + 10, r.y + 4), DIM, r.w - 20)
        big_fill(S, cell.subsurface((0, TOP, W, H - TOP)), pygame.Rect(r.x + 4, r.y + 22, r.w - 8, r.h - 25))
''', '''    bm = cfg.get("bigmode", "4")
    if bm == "GRANDE":
        # un cuadro a pantalla completa (letra al doble); van rotando cada BIG_ROT segundos
        k = int(now // BIG_ROT) % len(cells)
        r = pygame.Rect(0, hh, bw, bh - hh)
        big_cell(S, cell, cells[k], d, flags, now, r, fbig, "fit", f"  {k + 1}/{len(cells)}")
        pct = (now % BIG_ROT) / BIG_ROT
        pygame.draw.rect(S, DIM, (r.right - 130, r.y + 14, 110, 6), 1)
        pygame.draw.rect(S, ORANGE, (r.right - 129, r.y + 15, int(108 * pct), 4))
        return
    if bm == "MIXTO":
        # el cuadro principal grande a la izquierda; los demas pequenos a la derecha
        main = cells[1] if len(cells) > 1 else cells[0]
        rest = [c for c in cells if c != main][:3]
        bwl = bw * 2 // 3
        big_cell(S, cell, main, d, flags, now, pygame.Rect(0, hh, bwl, bh - hh), fbig, "top")
        if rest:
            h3 = (bh - hh) // len(rest)
            for k, v in enumerate(rest):
                big_cell(S, cell, v, d, flags, now, pygame.Rect(bwl, hh + k * h3, bw - bwl, h3), fsm, "fill")
        return
    for i, v in enumerate(cells):
        r = pygame.Rect((i % 2) * cw, hh + (i // 2) * ch, cw, ch)
        big_cell(S, cell, v, d, flags, now, r, fsm, "fill")
''')

rep('''def big_fill(dst, src, area):''', '''BIG_ROT = 10          # segundos por cuadro en modo GRANDE
BIGMODES = {"4": "4 CUADROS", "MIXTO": "MIXTO", "GRANDE": "GRANDE"}

def big_cell(S, cell, v, d, flags, now, r, font, how, extra=""):
    cell.fill(BLACK)
    fn = view_navbig if v == 3 else VIEWS.get(v)
    try:
        if fn:
            fn(cell, d, flags, now)
    except Exception as e:
        put(cell, F["small"], f"error: {e}"[:60], (8, TOP + 8), RED)
    pygame.draw.rect(S, DIM, r.inflate(-4, -4), 1, border_radius=6)
    lab = font.render(str(MENU.get(v, v)).upper() + extra, True, DIM)
    S.blit(lab, (r.x + 10, r.y + 4))
    top = r.y + lab.get_height() + 6
    src = cell.subsurface((0, TOP, W, H - TOP))
    area = pygame.Rect(r.x + 4, top, r.w - 8, r.bottom - 3 - top)
    if how == "fill":
        big_fill(S, src, area)
        return
    sc = min(area.w / src.get_width(), area.h / src.get_height())
    size = (int(src.get_width() * sc), int(src.get_height() * sc))
    try:
        img = pygame.transform.smoothscale(src, size)
    except ValueError:
        img = pygame.transform.scale(src, size)
    y = area.y if how == "top" else area.centery - size[1] // 2
    S.blit(img, (area.centerx - size[0] // 2, y))

def big_fill(dst, src, area):''')

# boton PANTALLA en 12 AJUSTES (hueco libre de la 2a fila)
rep('("VERSIONES", 1245), ("LOG", 121), ("STREAM", 122), None,',
    '("VERSIONES", 1245), ("LOG", 121), ("STREAM", 122), ("PANTALLA", "bigmode"),')
rep('''               "icons": "SÍ" if ICONS_ON[0] else "NO"}''',
    '''               "icons": "SÍ" if ICONS_ON[0] else "NO",
               "bigmode": BIGMODES.get(cfg.get("bigmode", "4"), "4 CUADROS")}''')
rep('''        elif act == "icons":
            icons_toggle()
''', '''        elif act == "icons":
            icons_toggle()
        elif act == "bigmode":
            order = list(BIGMODES)
            cfg["bigmode"] = order[(order.index(cfg.get("bigmode", "4")) + 1) % len(order)]
            save_cfg()
''')

rep('    ("0.61", "Pantalla grande: cuadros a todo lo ancho, texto más grande"),\n',
    '    ("0.61", "Pantalla grande: cuadros a todo lo ancho, texto más grande"),\n'
    '    ("0.62", "Pantalla grande: modos 4 CUADROS, MIXTO y GRANDE (AJUSTES)"),\n')
s = re.sub(r'PANEL_VER = "v0\.61[^"]*"', 'PANEL_VER = "v0.62 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.62 modos de la pantalla grande  (copia en panel.py.bak61)")
