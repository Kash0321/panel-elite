#!/usr/bin/env python3
# Parche v0.72: NITIDEZ ALTA en la pantalla grande (los cuadros se dibujan a la resolucion real de la HDMI).
# 12 AJUSTES > PANTALLA: MODO (4 CUADROS / MIXTO / GRANDE) y NITIDEZ (NORMAL / ALTA). NORMAL = como la v0.71.
import re, shutil, sys, time
P = sys.argv[1] if len(sys.argv) > 1 else "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "class ScaledSurf" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.71' not in s:
    sys.exit("Este parche es para la v0.71")
shutil.copy(P, P + ".bak71")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

CODE = r'''
# ---------- v0.72: NITIDEZ ALTA (dibujar los cuadros de la pantalla grande a su tamano real) ----------
# Las pantallas siguen pensando en 480x320; ScaledSurf traduce posiciones, tamanos y letras al tamano real.
HI_IDS, HI_KEEP, _HIF, _HISURF = set(), [], {}, {}

class FontProxy:
    def __init__(self, real, f):
        self.real, self.f = real, f
    def size(self, text):
        w, h = self.real.size(text)
        return (int(w / self.f + 0.5), int(h / self.f + 0.5))
    def render(self, *a, **k):
        t = self.real.render(*a, **k)
        HI_IDS.add(id(t)); HI_KEEP.append(t)
        return t
    def get_linesize(self):
        return int(self.real.get_linesize() / self.f + 0.5)
    def get_height(self):
        return int(self.real.get_height() / self.f + 0.5)
    def __getattr__(self, n):
        return getattr(self.real, n)

def hi_fonts(f):
    mono = pygame.font.match_font("dejavusansmono") or pygame.font.match_font("monospace")
    out = {}
    for k, base in (("big", 30), ("btn", 24), ("small", 18), ("num", 48), ("clock", 110), ("mono", 11)):
        size = max(6, int(round(base * f)))
        if (k, size) not in _HIF:
            _HIF[(k, size)] = pygame.font.Font(mono if k == "mono" else None, size)
        out[k] = FontProxy(_HIF[(k, size)], size / base)
    return out

class ScaledSurf:
    def __init__(self, real, sx, sy):
        self.real, self.sx, self.sy, self.clip = real, sx, sy, None
    def _r(self, r):
        r = pygame.Rect(r)
        return pygame.Rect(int(r.x * self.sx), int(r.y * self.sy), max(0, int(round(r.w * self.sx))), max(0, int(round(r.h * self.sy))))
    def get_size(self):
        return (W, H)
    def get_width(self):
        return W
    def get_height(self):
        return H
    def get_rect(self, **k):
        r = pygame.Rect(0, 0, W, H)
        for a, v in k.items():
            setattr(r, a, v)
        return r
    def fill(self, color, rect=None, special_flags=0):
        return self.real.fill(color, None if rect is None else self._r(rect), special_flags)
    def blit(self, src, dest, area=None, special_flags=0):
        x, y = dest[0], dest[1]
        pos = (int(x * self.sx), int(y * self.sy))
        if id(src) in HI_IDS:                      # texto ya dibujado a tamano real
            return self.real.blit(src, pos, area, special_flags)
        w, h = src.get_size()
        size = (max(1, int(w * self.sx)), max(1, int(h * self.sy)))
        try:
            sc = pygame.transform.smoothscale(src, size)
        except ValueError:
            sc = pygame.transform.scale(src, size)
        return self.real.blit(sc, pos, None if area is None else self._r(area), special_flags)
    def set_clip(self, r=None):
        self.clip = None if r is None else pygame.Rect(r)
        self.real.set_clip(None if r is None else self._r(r))
    def get_clip(self):
        return self.clip or pygame.Rect(0, 0, W, H)
    def set_at(self, pos, c):
        self.real.fill(c, self._r((pos[0], pos[1], 1, 1)))
    def get_at(self, pos):
        return self.real.get_at((int(pos[0] * self.sx), int(pos[1] * self.sy)))
    def __getattr__(self, n):
        return getattr(self.real, n)

def _hw(s_, w):
    return w if not w or w <= 0 else max(1, int(round(w * min(s_.sx, s_.sy))))

def _hp(s_, p):
    return (p[0] * s_.sx, p[1] * s_.sy)

def _wrap_draw():
    D = pygame.draw
    def mk(name, fn):
        def w(surf, *a, **k):
            if not isinstance(surf, ScaledSurf):
                return fn(surf, *a, **k)
            s_, a = surf, list(a)
            m = min(s_.sx, s_.sy)
            if name in ("rect", "ellipse", "arc"):
                a[1] = s_._r(a[1])
                wi = 4 if name == "arc" else 2
                if len(a) > wi:
                    a[wi] = _hw(s_, a[wi])
                if name == "rect" and len(a) > 3:
                    a[3] = int(a[3] * m)
            elif name in ("line", "aaline"):
                a[1], a[2] = _hp(s_, a[1]), _hp(s_, a[2])
                if name == "line" and len(a) > 3:
                    a[3] = _hw(s_, a[3])
            elif name in ("lines", "aalines"):
                a[2] = [_hp(s_, p_) for p_ in a[2]]
                if name == "lines" and len(a) > 3:
                    a[3] = _hw(s_, a[3])
            elif name == "polygon":
                a[1] = [_hp(s_, p_) for p_ in a[1]]
                if len(a) > 2:
                    a[2] = _hw(s_, a[2])
            elif name == "circle":
                a[1] = _hp(s_, a[1])
                a[2] = max(1, a[2] * m)
                if len(a) > 3:
                    a[3] = _hw(s_, a[3])
            if "width" in k:
                k["width"] = _hw(s_, k["width"])
            if "border_radius" in k:
                k["border_radius"] = int(k["border_radius"] * m)
            return fn(s_.real, *a, **k)
        return w
    for n in ("rect", "ellipse", "arc", "line", "aaline", "lines", "aalines", "polygon", "circle"):
        setattr(D, n, mk(n, getattr(D, n)))

_wrap_draw()

def big_cell_draw(cell, fn, d, flags, now):
    cell.fill(BLACK)
    try:
        if fn:
            fn(cell, d, flags, now)
    except Exception as e:
        put(cell, F["small"], f"error: {e}"[:60], (8, TOP + 8), RED)

def hi_cell(S, fn, d, flags, now, area, how):
    sx, sy = area.w / W, area.h / (H - TOP)
    if how != "fill":
        sx = sy = min(sx, sy)
    size = (int(W * sx) + 2, int(H * sy) + 2)
    real = _HISURF.get(size)
    if real is None:
        real = _HISURF[size] = pygame.Surface(size)
    real.fill(BLACK)
    keep = dict(F)
    HI_IDS.clear(); HI_KEEP.clear()
    F.update(hi_fonts(min(sx, sy)))
    try:
        fn(ScaledSurf(real, sx, sy), d, flags, now)
    except Exception as e:
        log_exc("nitidez alta", e)
        return False
    finally:
        F.clear(); F.update(keep)
        HI_IDS.clear(); HI_KEEP.clear()
    cw, ch = int(W * sx), int((H - TOP) * sy)
    top_ = int(TOP * sy)
    sub = real.subsurface((0, top_, min(cw, real.get_width()), min(ch, real.get_height() - top_)))
    if how == "fill":
        S.blit(sub, area.topleft)
    else:
        y = area.y if how == "top" else area.centery - ch // 2
        S.blit(sub, (area.centerx - cw // 2, y))
    return True

# 12 AJUSTES > PANTALLA: MODO y NITIDEZ
def view_pantalla(surf, d, flags, now):
    draw_button(surf, grid(0, 2, 1, TOP, H - 40), "MODO", BIGMODES.get(cfg.get("bigmode", "4"), "4 CUADROS"), F["big"],
                lit=flash.get((160, 0), 0) > now)
    draw_button(surf, grid(1, 2, 1, TOP, H - 40), "NITIDEZ", "ALTA" if cfg.get("sharp") else "NORMAL", F["big"],
                filled=bool(cfg.get("sharp")), lit=flash.get((160, 1), 0) > now)
    put(surf, F["small"], "Toca para cambiar. Se ve en la pantalla grande (HDMI).", (W // 2, H - 30), DIM, W - 16, anchor="midtop")

def tap_pantalla(x, y):
    if grid(0, 2, 1, TOP, H - 40).collidepoint(x, y):
        tap_flash((160, 0))
        order = list(BIGMODES)
        cfg["bigmode"] = order[(order.index(cfg.get("bigmode", "4")) + 1) % len(order)]
        save_cfg()
    elif grid(1, 2, 1, TOP, H - 40).collidepoint(x, y):
        tap_flash((160, 1))
        cfg["sharp"] = not cfg.get("sharp", False)
        save_cfg()

VIEWS[160] = view_pantalla
MENU[160] = "PANTALLA"
PARENT[160] = 12

'''
rep("\ndef render(surf):", CODE + "\ndef render(surf):")

# put(): con la superficie escalada, el texto se coloca en coordenadas logicas
rep('''    t = font.render(str(text), True, col)
    surf.blit(t, t.get_rect(**{anchor: pos}))
    return t.get_width()''', '''    t = font.render(str(text), True, col)
    if type(surf).__name__ == "ScaledSurf":
        f_ = getattr(font, "f", 1)
        r_ = pygame.Rect(0, 0, int(t.get_width() / f_), int(t.get_height() / f_))
        setattr(r_, anchor, pos)
        surf.blit(t, r_.topleft)
        return r_.w
    surf.blit(t, t.get_rect(**{anchor: pos}))
    return t.get_width()''')

# big_cell: en NITIDEZ ALTA se dibuja a tamano real (si algo falla, vuelve al modo normal en ese cuadro)
rep('''    cell.fill(BLACK)
    fn = view_navbig if v == 3 else view_orrery_big if v == 72 else VIEWS.get(v)
    try:
        if fn:
            fn(cell, d, flags, now)
    except Exception as e:
        put(cell, F["small"], f"error: {e}"[:60], (8, TOP + 8), RED)
''', '''    fn = view_navbig if v == 3 else view_orrery_big if v == 72 else VIEWS.get(v)
    sharp = bool(cfg.get("sharp")) and fn is not None
    if not sharp:
        big_cell_draw(cell, fn, d, flags, now)
''')
rep('''    area = pygame.Rect(r.x + 4, top, r.w - 8, r.bottom - 3 - top)
    if how == "fill":
        big_fill(S, src, area)
        return''', '''    area = pygame.Rect(r.x + 4, top, r.w - 8, r.bottom - 3 - top)
    if sharp:
        if hi_cell(S, fn, d, flags, now, area, how):
            return
        big_cell_draw(cell, fn, d, flags, now)
    if how == "fill":
        big_fill(S, src, area)
        return''')

# AJUSTES: el boton PANTALLA abre la pantalla con MODO y NITIDEZ
rep('("PANTALLA", "bigmode"),', '("PANTALLA", 160),')
rep('''               "bigmode": BIGMODES.get(cfg.get("bigmode", "4"), "4 CUADROS")}.get(act) if isinstance(act, str) else None''',
    '''               "bigmode": BIGMODES.get(cfg.get("bigmode", "4"), "4 CUADROS")}.get(act) if isinstance(act, str) else (
                   f"{BIGMODES.get(cfg.get('bigmode', '4'), '4 CUADROS')} · {'ALTA' if cfg.get('sharp') else 'NORMAL'}" if act == 160 else None)''')
rep("    elif v in (140, 141):\n", "    elif v == 160:\n        tap_pantalla(x, y); return\n    elif v in (140, 141):\n")

# manual
rep('''- GRANDE: un cuadro a pantalla completa con letra al doble; van rotando cada 10 s.''',
    '''- GRANDE: un cuadro a pantalla completa con letra al doble; van rotando cada 10 s.
# Nitidez (AJUSTES > PANTALLA)
- NORMAL: los cuadros se dibujan a 480x320 y se amplían (más ligero).
- ALTA: se dibujan a la resolución real de la HDMI (1024x600): letras y líneas nítidas en todos los modos. Gasta algo más de CPU. Si algún cuadro diera problemas, ese cuadro vuelve solo a NORMAL.''')

rep('    ("0.71", "Llegada y señales, OPERATIONS, Merc Coin, copiloto, SISTEMA grande y clic desde el PC"),\n',
    '    ("0.71", "Llegada y señales, OPERATIONS, Merc Coin, copiloto, SISTEMA grande y clic desde el PC"),\n'
    '    ("0.72", "NITIDEZ ALTA: pantalla grande a 1024x600 real (AJUSTES > PANTALLA)"),\n')
s = re.sub(r'PANEL_VER = "v0\.71[^"]*"', 'PANEL_VER = "v0.72 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.72 NITIDEZ  (copia en " + P + ".bak71)")
