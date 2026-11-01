#!/usr/bin/env python3
# Parche v0.54: pantalla del reloj con foto arriba y ventana de noticias GALNET que van subiendo
import re, shutil, sys, time
P = "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def idle_crawl" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.53' not in s:
    sys.exit("Este parche es para la v0.53")
shutil.copy(P, P + ".bak53")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

i0 = s.index("def draw_idle(surf, now):")
i1 = s.index("def draw_alert(surf, now):")
NEW = r'''IDLE_PHOTO = (66, 70)
IDLE_BOX = pygame.Rect(6, 150, W - 12, 152)
IDLE_SPEED = 14          # pixeles por segundo que suben las noticias

def idle_photo():
    img = cmdr_img()
    if not img:
        return None
    key = ("idlephoto", id(img))
    c = style["cache"]
    if key not in c:
        k = min(116 / img.get_width(), 120 / img.get_height(), 1.0)
        size = (int(img.get_width() * k), int(img.get_height() * k))
        c[key] = pygame.transform.smoothscale(img, size) if k < 1 else img
    return c[key]

def idle_crawl_lines():
    L = galnet["list"][:6]
    key = tuple(n["id"] for n in L)
    if galnet.get("crawl", (None,))[0] != key:
        out, w = [], IDLE_BOX.w - 16
        for n in L:
            for t in wrap_lines(F["btn"], n["title"], w):
                out.append((F["btn"], t, ORANGE, 21))
            out.append((F["small"], n["date"], BLUE, 17))
            body = [b for b in wrap_lines(F["small"], n["body"], w)]
            for t in body[:9]:
                out.append((F["small"], t, WHITE, 16))
            if len(body) > 9:
                out.append((F["small"], "...  (sigue en 12.9 GALNET)", DIM, 16))
            out.append((None, "", None, 22))
        galnet["crawl"] = (key, out, sum(h for *_, h in out))
    return galnet["crawl"][1], galnet["crawl"][2]

def idle_crawl(surf, now):
    box = IDLE_BOX
    pygame.draw.rect(surf, DIM, box, 1, border_radius=6)
    put(surf, F["small"], "NOTICIAS GALNET", (box.x + 8, box.y + 5), ORANGE)
    if int(now) % 4 < 3:
        put(surf, F["small"], "Esperando a Elite Dangerous...", (box.right - 8, box.y + 5), DIM, anchor="topright")
    pygame.draw.line(surf, DIM, (box.x + 6, box.y + 21), (box.right - 6, box.y + 21))
    area = pygame.Rect(box.x + 8, box.y + 24, box.w - 16, box.h - 28)
    lines, total = idle_crawl_lines()
    if not lines:
        put(surf, F["small"], galnet["err"] or "descargando noticias...", area.center, DIM, area.w, anchor="center")
        return
    off = (now * IDLE_SPEED) % total
    old = surf.get_clip()
    surf.set_clip(area)
    y = area.bottom - off
    while y < area.bottom:
        for f, t, col, h in lines:
            if area.y - h < y < area.bottom and f:
                put(surf, f, t, (area.x, int(y)), col, area.w)
            y += h
    surf.set_clip(old)
    fade = style["cache"].get("idlefade")
    if fade is None:
        fade = pygame.Surface((area.w, 12), pygame.SRCALPHA)
        for k in range(12):
            pygame.draw.line(fade, (0, 0, 0, 255 - k * 21), (0, k), (area.w, k))
        style["cache"]["idlefade"] = fade
    surf.blit(fade, (area.x, area.y))
    surf.blit(pygame.transform.flip(fade, False, True), (area.x, area.bottom - 12))

def draw_idle(surf, now):
    surf.fill(BLACK)
    lt = time.localtime(now)
    img = idle_photo()
    if img:
        r = img.get_rect(center=IDLE_PHOTO)
        surf.blit(img, r)
        pygame.draw.rect(surf, ORANGE, r.inflate(6, 6), 2, border_radius=4)
    else:
        draw_emblem(surf, IDLE_PHOTO[0], IDLE_PHOTO[1], 50, now / 3)
    cx = 310
    put(surf, F["clock"], time.strftime("%H:%M", lt), (cx, 44), ORANGE, anchor="center")
    put(surf, F["btn"], f"{DIAS[lt.tm_wday]} {lt.tm_mday} de {MESES[lt.tm_mon - 1]}", (cx, 90), DIM, anchor="center")
    put(surf, F["big"], "CMDR " + cfg["cmdr"], (cx, 114), ORANGE, 320, anchor="center")
    ip = my_ip()
    put(surf, F["small"], PANEL_VER.split(" · ")[0], (150, 132), GREEN)
    put(surf, F["small"], f"IP {ip}" if ip else "SIN RED", (W - 8, 132), DIM if ip else RED, anchor="topright")
    idle_crawl(surf, now)
    put(surf, F["small"], "toca la pantalla para abrir el menú", (W // 2, H - 9), DIM, anchor="center")

'''
s = s[:i0] + NEW + s[i1:]

# estilo CABINA: marco de la foto y estrellas fuera de la ventana de noticias
rep("r = pygame.Rect(0, 0, 112, 128); r.center = (70, 160)", "r = pygame.Rect(0, 0, 124, 128); r.center = IDLE_PHOTO")
rep("if 130 < x < 450 and 60 < y0 < 280:", "if y0 > 146:")

rep('    ("0.53", "12.9 GALNET: noticias oficiales y aviso de noticia nueva"),\n',
    '    ("0.53", "12.9 GALNET: noticias oficiales y aviso de noticia nueva"),\n'
    '    ("0.54", "Reloj: foto arriba y noticias GALNET subiendo"),\n')
s = re.sub(r'PANEL_VER = "v0\.53[^"]*"', 'PANEL_VER = "v0.54 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.54 reloj con GALNET  (copia en panel.py.bak53)")
