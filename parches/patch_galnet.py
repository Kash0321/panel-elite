#!/usr/bin/env python3
# Parche v0.53: 12.9 GALNET (noticias oficiales en espanol, cada 30 min, aviso de noticia nueva)
import re, shutil, sys
P = "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def view_galnet" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.52' not in s:
    sys.exit("Este parche es para la v0.52")
shutil.copy(P, P + ".bak52")

def rep(old, new, n=1):
    global s
    if s.count(old) < 1:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, n)

CODE = r'''
# ---------- 12.9 GALNET: noticias oficiales (la Pi las baja sola) ----------
import re
GALNET_URL = ("https://cms.zaonce.net/es-ES/jsonapi/node/galnet_article"
              "?sort=-published_at&page%5Blimit%5D=20")
GALNET_FILE = "/home/ortem/galnet.json"
GALNET_EVERY = 1800
galnet = {"list": [], "t": 0, "err": "", "page": 0, "sel": None, "apage": 0, "new": set(), "lines": None}

def galnet_text(html_):
    import html as _h
    t = re.sub(r"(?i)<br\s*/?>|</p>", "\n", html_ or "")
    t = re.sub(r"<[^>]+>", "", t)
    t = _h.unescape(t).replace("\r", "")
    return re.sub(r"\n{3,}", "\n\n", t).strip()

def galnet_fetch():
    import urllib.request
    req = urllib.request.Request(GALNET_URL, headers={"User-Agent": "PanelElite/1.0",
                                                      "Accept": "application/vnd.api+json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    out = []
    for a in data.get("data", []):
        t = a.get("attributes") or {}
        out.append({"id": a.get("id"), "title": (t.get("title") or "").strip(),
                    "date": t.get("field_galnet_date") or "",
                    "body": galnet_text((t.get("body") or {}).get("value", ""))})
    return out

def galnet_loop():
    try:
        with open(GALNET_FILE, encoding="utf-8") as f:
            galnet["list"] = json.load(f)
    except (OSError, ValueError):
        pass
    first = not galnet["list"]
    while True:
        try:
            L = galnet_fetch()
            if L:
                old = {n["id"] for n in galnet["list"]}
                nuevas = [n for n in L if n["id"] not in old]
                galnet["list"], galnet["t"], galnet["err"] = L, time.time(), ""
                if nuevas and not first:
                    galnet["new"].update(n["id"] for n in nuevas)
                    if cfg["alerts"]:
                        set_alert("NUEVA NOTICIA GALNET", nuevas[0]["title"], BLUE, 6, "galnet")
                first = False
                with open(GALNET_FILE + ".tmp", "w", encoding="utf-8") as f:
                    json.dump(L, f, ensure_ascii=False)
                import os as _os
                _os.replace(GALNET_FILE + ".tmp", GALNET_FILE)
            time.sleep(GALNET_EVERY)
        except Exception as e:
            galnet["err"] = str(e)[:60]
            print("galnet:", e, flush=True)
            time.sleep(300)

threading.Thread(target=galnet_loop, daemon=True).start()

def wrap_lines(font, text, width):
    out = []
    for par in text.split("\n"):
        if not par.strip():
            out.append(""); continue
        line = ""
        for w in par.split():
            test = (line + " " + w).strip()
            if font.size(test)[0] <= width:
                line = test
            else:
                if line:
                    out.append(line)
                line = w
        out.append(line)
    return out

GAL_PER = 6
GAL_PAGE = pygame.Rect(W - 118, TOP + 2, 110, 30)

def gal_row(i):
    return pygame.Rect(8, TOP + 38 + i * 37, W - 16, 34)

def view_galnet(surf, d, flags, now):
    L = galnet["list"]
    pages = max(1, (len(L) + GAL_PER - 1) // GAL_PER)
    pg = galnet["page"] % pages
    if galnet["t"]:
        info = "actualizado " + time.strftime("%H:%M", time.localtime(galnet["t"]))
    else:
        info = galnet["err"] or "descargando..."
    put(surf, F["small"], info, (8, TOP + 10), RED if galnet["err"] else DIM, W - 140)
    if pages > 1:
        draw_button(surf, GAL_PAGE, f"PÁG {pg + 1}/{pages} >", None, F["small"])
    if not L:
        put(surf, F["btn"], "Sin noticias todavía", (W // 2, (H + TOP) // 2), DIM, anchor="center"); return
    for i, n in enumerate(L[pg * GAL_PER:(pg + 1) * GAL_PER]):
        r = gal_row(i)
        nueva = n["id"] in galnet["new"]
        pygame.draw.rect(surf, GREEN if nueva else DIM, r, 1, border_radius=4)
        put(surf, F["btn"], n["title"], (r.x + 6, r.y + 2), GREEN if nueva else ORANGE, r.w - 12)
        put(surf, F["small"], n["date"] + ("   · NUEVA" if nueva else ""), (r.x + 6, r.y + 19), BLUE if not nueva else GREEN)

def view_galnet_art(surf, d, flags, now):
    L, i = galnet["list"], galnet["sel"]
    if i is None or i >= len(L):
        ui["view"] = 130; return
    n = L[i]
    if galnet["lines"] is None or galnet["lines"][0] != n["id"]:
        galnet["lines"] = (n["id"], wrap_lines(F["big"], n["title"], W - 16)[:2],
                           wrap_lines(F["small"], n["body"], W - 16))
    _, tl, body = galnet["lines"]
    y = TOP + 2
    for t in tl:
        put(surf, F["big"], t, (8, y), ORANGE); y += 24
    put(surf, F["small"], "GALNET · " + n["date"], (8, y), BLUE); y += 18
    per = max(1, (H - y - 4) // 16)
    pages = max(1, (len(body) + per - 1) // per)
    pg = galnet["apage"] % pages
    put(surf, F["small"], f"pág {pg + 1}/{pages}  (toca)", (W - 8, y - 18), DIM, anchor="topright")
    for line in body[pg * per:(pg + 1) * per]:
        put(surf, F["small"], line, (8, y), WHITE); y += 16

def tap_galnet(x, y):
    v, L = ui["view"], galnet["list"]
    if v == 130:
        pages = max(1, (len(L) + GAL_PER - 1) // GAL_PER)
        if pages > 1 and GAL_PAGE.collidepoint(x, y):
            galnet["page"] += 1; return
        pg = galnet["page"] % pages
        for i in range(GAL_PER):
            idx = pg * GAL_PER + i
            if idx < len(L) and gal_row(i).collidepoint(x, y):
                galnet["sel"], galnet["apage"] = idx, 0
                galnet["new"].discard(L[idx]["id"])
                ui["view"] = 131; return
    elif v == 131:
        galnet["apage"] += 1

VIEWS.update({130: view_galnet, 131: view_galnet_art})
MENU.update({130: "GALNET", 131: "NOTICIA"})
PARENT.update({130: 12, 131: 130})

'''

# codigo nuevo antes de render()
rep("\ndef render(surf):", CODE + "\ndef render(surf):")
# menu 12: noveno boton GALNET (rejilla 4x3)
rep('''    for i, (n, name) in enumerate([("1", "LOG"), ("2", "STREAM"), ("3", "RANGOS"), ("4", "AJUSTES"), ("5", "MATERIAL"), ("6", "PORTANAV."), ("7", "MERCADO"), ("8", "NOTAS")]):
        draw_button(surf, grid(i, 4, 2), n, name, F["num"], lit=flash.get((12, i), 0) > now)''',
    '''    for i, (n, name) in enumerate([("1", "LOG"), ("2", "STREAM"), ("3", "RANGOS"), ("4", "AJUSTES"), ("5", "MATERIAL"), ("6", "PORTANAV."), ("7", "MERCADO"), ("8", "NOTAS"), ("9", "GALNET")]):
        draw_button(surf, grid(i, 4, 3), n, name, F["big"], lit=flash.get((12, i), 0) > now)
    nn = len(galnet["new"])
    if nn:
        put(surf, F["small"], f"{nn} noticia{'s' if nn > 1 else ''} nueva{'s' if nn > 1 else ''} en GALNET", (W - 8, H - 18), GREEN, anchor="topright")''')
rep('''        for i in range(8):
            if grid(i, 4, 2).collidepoint(x, y):
                tap_flash((12, i)); ui["view"] = 121 + i; return''',
    '''        for i in range(9):
            if grid(i, 4, 3).collidepoint(x, y):
                tap_flash((12, i)); ui["view"] = 121 + i if i < 8 else 130; return''')
# toques en GALNET
rep("    elif v == 71:\n", "    elif v in (130, 131):\n        tap_galnet(x, y); return\n    elif v == 71:\n")
# version y lista de cambios
rep('    ("0.52", "Amigos y ala: avisos y cara AMIGOS en Sesión"),\n',
    '    ("0.52", "Amigos y ala: avisos y cara AMIGOS en Sesión"),\n    ("0.53", "12.9 GALNET: noticias oficiales y aviso de noticia nueva"),\n')
s = re.sub(r'PANEL_VER = "v0\.52[^"]*"', 'PANEL_VER = "v0.53 · ' + __import__("time").strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.53 GALNET  (copia en panel.py.bak52)")
