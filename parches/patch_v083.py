#!/usr/bin/env python3
# Parche v0.83: consumibles siempre a la vista a pie (botiquines, celulas y explosivos con el maximo del traje)
# y pantalla EN COMBATE a pie en grande.
import re, shutil, sys, time
P = sys.argv[1] if len(sys.argv) > 1 else "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def draw_fight_big" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.82' not in s:
    sys.exit("Este parche es para la v0.82")
shutil.copy(P, P + ".bak82")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

# --- EN VIVO a pie: en combate, la pantalla grande de combate; si no, consumibles siempre visibles
rep('''    y = TOP + 4
    put(surf, F["big"], mode, (8, y), GREEN)
    if mode == "A PIE" and in_fight(d, now):''', '''    y = TOP + 4
    if mode == "A PIE" and in_fight(d, now):
        return draw_fight_big(surf, d, now)
    put(surf, F["big"], mode, (8, y), GREEN)
    if mode == "A PIE" and in_fight(d, now):''')
rep('''        Z = d.get("footcz") or {}
        P = {} if Z.get("n") else (d.get("pack") or {})
        if Z.get("n"):''', '''        Z = d.get("footcz") or {}
        P = d.get("pack") or {}
        if Z.get("n"):''')
rep('''        cons = P.get("cons") or []
        if cons:
            put(surf, F["small"], "  ·  ".join(f"{n} {c}" for n, c in cons[:5]), (8, y + 4), ORANGE, W - 16)
        if P.get("n_items") or P.get("n_comp") or P.get("n_data"):''', '''        if Z.get("n"):
            y += 40
        draw_cons_row(surf, d, 8, y + 2, F["btn"], 12)
        y += 4
        if P.get("n_items") or P.get("n_comp") or P.get("n_data"):''')

# --- aviso al lanzar: "quedan X de Y"
rep('''            xa["a"] = dict(until=now + 2, col=GREY, title=f"{p[1].upper()} LANZADO", big=f"quedan {p[2]}", lines=[])''',
    '''            mx_ = suit_max(d).get(cons_kind(p[0]) or "", None)
            xa["a"] = dict(until=now + 2, col=GREY, title=f"{p[1].upper()} LANZADO",
                           big=f"quedan {p[2]}" + (f" de {mx_}" if mx_ else ""), lines=[])''')

CODE = r'''
# ---------- v0.83: consumibles a la vista y EN COMBATE a pie en grande ----------
# maximo de explosivos por traje (comprobado por el CMDR): fragmentacion, disruptor (EMP), proyector de escudo
SUIT_EXPL = {"dominator": (3, 3, 2), "maverick": (2, 1, 1), "artemis": (1, 1, 1), "vuelo": (0, 0, 0), "flight": (0, 0, 0)}
EXPL = [("frag", "FRAG."), ("emp", "DISRUPT."), ("shield", "PROYECT.")]

def cons_kind(name):
    n = (name or "").lower()
    if "frag" in n:
        return "frag"
    if "emp" in n or "disrup" in n:
        return "emp"
    if "proyect" in n or "project" in n or "grenade_shield" in n:
        return "shield"
    if "botiqu" in n or "health" in n or "medkit" in n:
        return "med"
    if "lula" in n or "energycell" in n or "energy cell" in n or "cell" in n:
        return "cell"
    return None

def cons_count(d):
    out = {}
    for it in (((d or {}).get("pack") or {}).get("cons") or []):
        k = cons_kind(it[0])
        if k:
            out[k] = out.get(k, 0) + (it[1] or 0)
    return out

def suit_name_of(d):
    d = d or {}
    return str(((d.get("live") or {}).get("suit") or {}).get("name") or (d.get("footcz") or {}).get("suit") or "")

def suit_max(d):
    sn = suit_name_of(d).lower()
    t = next((v for k, v in SUIT_EXPL.items() if k in sn), None)
    return dict(zip(("frag", "emp", "shield"), t)) if t else {}

def cons_col(n, mx=None):
    if n <= 1:
        return RED
    if mx and n < mx:
        return ORANGE
    return GREEN

def draw_med(surf, x, y, k, col):
    a, b = int(5 * k), int(2 * k)
    pygame.draw.rect(surf, col, (x - b, y - a, 2 * b, 2 * a))
    pygame.draw.rect(surf, col, (x - a, y - b, 2 * a, 2 * b))

def draw_pips(surf, x, y, n, mx, w, h):
    for i in range(max(mx, n)):
        r = pygame.Rect(x + i * (w + 4), y, w, h)
        if i < n:
            pygame.draw.rect(surf, cons_col(n, mx), r)
        else:
            pygame.draw.rect(surf, DIM, r, 1)
    return max(mx, n) * (w + 4)

def draw_cons_row(surf, d, x, y, font, ph):
    """Una fila: + botiquines, rayo celulas, y los explosivos con barritas segun el traje."""
    c, mx = cons_count(d), suit_max(d)
    h_ = font.get_height()
    draw_med(surf, x + 7, y + h_ // 2, h_ / 18, cons_col(c.get("med", 0)))
    x += 16 + put(surf, font, str(c.get("med", 0)), (x + 18, y), cons_col(c.get("med", 0))) + 8
    draw_bolt(surf, x, y + 1, cons_col(c.get("cell", 0)), h_ / 22)
    x += 14 + put(surf, font, str(c.get("cell", 0)), (x + 14, y), cons_col(c.get("cell", 0))) + 10
    for k, lab in EXPL:
        if not mx.get(k) and not c.get(k):
            continue
        x += put(surf, F["small"], lab, (x, y + h_ // 2 - 6), DIM) + 4
        x += draw_pips(surf, x, y + h_ // 2 - ph // 2, c.get(k, 0), mx.get(k, 0), ph, ph) + 8
    return y + h_

def draw_fight_big(surf, d, now):
    """EN COMBATE a pie: lo importante en grande para mirarlo de reojo."""
    L, Z = d.get("live") or {}, d.get("footcz") or {}
    led = Z.get("led") or {}
    y = TOP + 2
    on_ = int(now * 2) % 2 == 0
    r_ = pygame.Rect(8, y, 200, 30)
    pygame.draw.rect(surf, RED, r_, 0 if on_ else 3, border_radius=6)
    put(surf, F["big"], "EN COMBATE", r_.center, BLACK if on_ else RED, anchor="center")
    put(surf, F["small"], suit_name_of(d), (W - 8, y + 8), ORANGE, 250, anchor="topright")
    y += 36
    hp = pctv(L.get("health"))
    sd = (d.get("combat") or {}).get("sd")
    hb = pygame.Rect(8, y, W - 160, 22)
    pygame.draw.rect(surf, DIM, hb, 1)
    if hp is not None:
        pygame.draw.rect(surf, RED if hp < 25 else ORANGE if hp < 50 else GREEN,
                         (hb.x + 2, hb.y + 2, int((hb.w - 4) * max(0, min(100, hp)) / 100), hb.h - 4))
    put(surf, F["btn"], f"SALUD {hp:.0f} %" if hp is not None else "SALUD ?", hb.center, WHITE, anchor="center")
    sr = pygame.Rect(W - 146, y, 138, 22)
    if sd:
        el = int(now - sd)
        pygame.draw.rect(surf, RED, sr, 0 if on_ else 2, border_radius=4)
        put(surf, F["btn"], f"ESCUDO {el // 60:02d}:{el % 60:02d}", sr.center, BLACK if on_ else RED, anchor="center")
    else:
        pygame.draw.rect(surf, BLUE, sr, 2, border_radius=4)
        put(surf, F["btn"], "ESCUDO OK", sr.center, BLUE, anchor="center")
    y += 28
    # bajas y consumibles en grande
    put(surf, F["num"], str(Z.get("n") or 0), (8, y), GREEN)
    put(surf, F["small"], "BAJAS", (12 + F["num"].size(str(Z.get("n") or 0))[0], y + 26), GREEN)
    c = cons_count(d)
    x = W - 8
    for k in ("cell", "med"):
        n = c.get(k, 0)
        tw = F["num"].size(str(n))[0]
        put(surf, F["num"], str(n), (x, y), cons_col(n), anchor="topright")
        x -= tw + 6
        if k == "med":
            draw_med(surf, x - 14, y + 20, 2.4, cons_col(n)); x -= 36
        else:
            draw_bolt(surf, x - 22, y + 2, cons_col(n), 1.9); x -= 40
    y += 48
    put(surf, F["big"], f"{crx(led.get('cr', 0))} cr", (8, y), ORANGE)
    put(surf, F["small"], "sin cobrar", (12 + F["big"].size(f"{crx(led.get('cr', 0))} cr")[0], y + 10), DIM)
    if Z.get("rate"):
        put(surf, F["btn"], f"{str(Z['rate']).replace('.', ',')} / min", (W - 8, y + 4), DIM, anchor="topright")
    y += 34
    # explosivos con barritas gruesas
    mx = suit_max(d)
    x = 8
    for k, lab in EXPL:
        if not mx.get(k) and not c.get(k):
            continue
        x += put(surf, F["btn"], lab, (x, y + 2), DIM) + 6
        x += draw_pips(surf, x, y, c.get(k, 0), mx.get(k, 0), 18, 22) + 14
    y += 30
    zt = (Z.get("zone") or "").upper() + (f"  ·  por {Z['side']}" if Z.get("side") else "")
    put(surf, F["small"], "  ·  ".join(t for t in (zt, L.get("weapon")) if t), (8, H - 18), DIM, W - 16)

'''
rep("\ndef render(surf):", CODE + "\ndef render(surf):")

rep('''# Enlace energético''', '''# Combate a pie
- EN VIVO a pie muestra siempre botiquines (+), células (rayo) y explosivos con barritas según el máximo de tu traje (Dominator 3/3/2, Maverick 2/1/1, Artemis 1/1/1). Rojo con 1 o ninguno.
- En combate (te atacan o hay bajas en el último minuto) la pantalla pasa a EN COMBATE en grande: salud, escudo, bajas, botiquines y células, créditos sin cobrar y explosivos.
- Al lanzar una granada: «quedan X de Y».
# Enlace energético''')
rep('    ("0.82", "ESCUADRÓN por páginas: hasta 30 comandantes, conectados primero"),\n',
    '    ("0.82", "ESCUADRÓN por páginas: hasta 30 comandantes, conectados primero"),\n'
    '    ("0.83", "Botiquines, células y explosivos (máximo por traje) siempre a la vista; EN COMBATE en grande"),\n')
s = re.sub(r'PANEL_VER = "v0\.82[^"]*"', 'PANEL_VER = "v0.83 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)
open(P, "w", encoding="utf-8").write(s)
print("OK v0.83  (copia en " + P + ".bak82)")
