#!/usr/bin/env python3
# Parche v0.76: mapa a pie sin el vuelo del transporte (filtro de velocidad), leyenda de simbolos y mas zoom en ZONA.
import re, shutil, sys, time
P = sys.argv[1] if len(sys.argv) > 1 else "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "FOOT_MAX_V" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.75' not in s:
    sys.exit("Este parche es para la v0.75")
shutil.copy(P, P + ".bak75")

def rep(old, new, all_=False):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new) if all_ else s.replace(old, new, 1)

# --- filtro de velocidad: a pie nadie va a mas de 20 m/s; lo mas rapido es el transporte
rep('''    if track["last"] is None or hav(track["last"], (lat, lon), R) >= TRACK_STEP:
        track["pts"].append((lat, lon))''', '''    raw = track.get("raw")
    track["raw"] = (lat, lon, now)
    if raw and d.get("Flags2", 0) & 1 and not d.get("Flags", 0) & (1 << 26):
        dt = now - raw[2]
        if 0 < dt < 10 and hav(raw[:2], (lat, lon), R) / dt > FOOT_MAX_V:
            pts_ = track["pts"]
            if pts_ and pts_[-1] is not None:
                k_ = len(pts_)
                while k_ > 0 and pts_[k_ - 1] is not None:
                    k_ -= 1
                if len(pts_) - k_ < 5:
                    del pts_[k_:]                      # trozo suelto de 1-4 puntos: fuera
                if pts_ and pts_[-1] is not None:
                    pts_.append(None)                  # corte: no se une con una raya
            track["last"] = None
            return
    if track["last"] is None or hav(track["last"], (lat, lon), R) >= TRACK_STEP:
        track["pts"].append((lat, lon))''')
rep('''TRACK_MAX, TRACK_STEP = 2000, 3.0''', '''FOOT_MAX_V = 20.0                          # m/s: mas rapido que esto, a pie, es ir en el transporte
TRACK_MAX, TRACK_STEP = 2000, 3.0''')

# --- dibujo: los cortes (None) y mas zoom en ZONA
rep('''    trail = [xy(p) for p in track["pts"]]''', '''    trail_all = [xy(p) if p is not None else None for p in track["pts"]]
    trail = [p for p in trail_all if p is not None]''')
rep('''        ext = far[int(len(far) * 0.95)] if far else 50
        ext = max(ext, 50)''', '''        ext = far[int(len(far) * 0.8)] if far else 40
        ext = max(ext, 40)''')
rep('''    sc = min(r.w / (w_ * 1.25), r.h / (h_ * 1.25))
    def scr(p):''', '''    mg = 1.08 if zm == 0 else 1.25
    sc = min(r.w / (w_ * mg), r.h / (h_ * mg))
    def scr(p):''')
rep('''    pts = [scr(p) for p in trail] + [scr(me)]
    n = len(pts)
    for i in range(1, n):
        f_ = 0.25 + 0.75 * i / n                        # lo antiguo se va apagando
        pygame.draw.line(surf, tuple(int(c * f_) for c in ORANGE[:3]), pts[i - 1], pts[i], 2)''',
    '''    pts = [scr(p) if p is not None else None for p in trail_all] + [scr(me)]
    n = len(pts)
    for i in range(1, n):
        if pts[i - 1] is None or pts[i] is None:
            continue
        f_ = 0.25 + 0.75 * i / n                        # lo antiguo se va apagando
        pygame.draw.line(surf, tuple(int(c * f_) for c in ORANGE[:3]), pts[i - 1], pts[i], 2)''')

# --- leyenda de simbolos en pequeno, junto a "cuadro = ..."
rep('''    put(surf, fs, f"cuadro = {fmt_m(step)}", (r.x + 6, r.bottom - 18), DIM)
''', '''    put(surf, fs, f"cuadro = {fmt_m(step)}", (r.x + 6, r.bottom - 18), DIM)
    map_legend(surf, r.x + 8, r.bottom - 29, fs)
''')
rep('''MARK_BTN = pygame.Rect(W - 172, H - 38, 166, 34)''', '''def map_legend(surf, x, y, fs):
    """Simbolos en pequeno: X baja, + botiquin, rayo celula, rombo nave, cuadro asentamiento."""
    def lab(t, x):
        put(surf, fs, t, (x, y - 7), DIM)
        return x + fs.size(t)[0] + 8
    pygame.draw.line(surf, RED, (x, y - 3), (x + 6, y + 3), 2); pygame.draw.line(surf, RED, (x, y + 3), (x + 6, y - 3), 2)
    x = lab("baja", x + 9)
    pygame.draw.line(surf, GREEN, (x, y), (x + 8, y), 3); pygame.draw.line(surf, GREEN, (x + 4, y - 4), (x + 4, y + 4), 3)
    x = lab("botiquín", x + 11)
    draw_bolt(surf, x, y - 6, YELLOW, 0.55)
    x = lab("célula", x + 9)
    pygame.draw.polygon(surf, ORANGE, [(x + 4, y - 5), (x + 8, y), (x + 4, y + 5), (x, y)])
    x = lab("nave", x + 11)
    pygame.draw.rect(surf, BLUE, (x, y - 4, 8, 8), 2)
    lab("base", x + 11)

MARK_BTN = pygame.Rect(W - 172, H - 38, 166, 34)''')

rep('    ("0.75", "SONIDO Y VOZ uno a uno (bajas en silencio); te atacan a pie > EN VIVO; mapa ZONA"),\n',
    '    ("0.75", "SONIDO Y VOZ uno a uno (bajas en silencio); te atacan a pie > EN VIVO; mapa ZONA"),\n'
    '    ("0.76", "Mapa a pie sin el vuelo del transporte, leyenda de símbolos y más zoom en ZONA"),\n')
s = re.sub(r'PANEL_VER = "v0\.75[^"]*"', 'PANEL_VER = "v0.76 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.76  (copia en " + P + ".bak75)")
