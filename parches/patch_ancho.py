#!/usr/bin/env python3
# Parche v0.61: pantalla grande - cada cuadro ocupa todo su hueco (sin bandas a los lados), texto mas grande
import re, shutil, sys, time
P = "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def big_fill" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.60' not in s:
    sys.exit("Este parche es para la v0.60")
shutil.copy(P, P + ".bak60")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

rep('''def big_blit(dst, src, area):''', '''def big_fill(dst, src, area):
    """Escala el cuadro a todo el hueco (un poco mas ancho que alto) para no dejar bandas a los lados."""
    try:
        img = pygame.transform.smoothscale(src, area.size)
    except ValueError:
        img = pygame.transform.scale(src, area.size)
    dst.blit(img, area.topleft)

def big_blit(dst, src, area):''')

rep('''        pygame.draw.rect(S, DIM, r.inflate(-6, -6), 1, border_radius=6)
        put(S, fsm, str(MENU.get(v, v)).upper(), (r.x + 12, r.y + 6), DIM, r.w - 24)
        big_blit(S, cell.subsurface((0, TOP, W, H - TOP)), pygame.Rect(r.x + 6, r.y + 26, r.w - 12, r.h - 32))''',
'''        pygame.draw.rect(S, DIM, r.inflate(-4, -4), 1, border_radius=6)
        put(S, fsm, str(MENU.get(v, v)).upper(), (r.x + 10, r.y + 4), DIM, r.w - 20)
        big_fill(S, cell.subsurface((0, TOP, W, H - TOP)), pygame.Rect(r.x + 4, r.y + 22, r.w - 8, r.h - 25))''')

# cabecera: el modo (ATRACADO...) justo detras del nombre del sistema, sin pisarlo
rep('''    put(S, fbig, (d.get("system") or "---").upper(), (12, 9), ORANGE, 400)
    put(S, fsm, mode, (bw // 2 - 80, 14), GREEN, 190, anchor="midtop")''',
    '''    tw = put(S, fbig, (d.get("system") or "---").upper(), (12, 9), ORANGE, 400)
    put(S, fsm, mode, (12 + tw + 14, 16), GREEN, max(40, bw // 2 + 10 - (12 + tw + 14)))''')

rep('    ("0.60", "Datos comprimidos, registro de errores, arranque y aviso thargoide"),\n',
    '    ("0.60", "Datos comprimidos, registro de errores, arranque y aviso thargoide"),\n'
    '    ("0.61", "Pantalla grande: cuadros a todo lo ancho, texto más grande"),\n')
s = re.sub(r'PANEL_VER = "v0\.60[^"]*"', 'PANEL_VER = "v0.61 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.61  (copia en panel.py.bak60)")
