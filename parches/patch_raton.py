#!/usr/bin/env python3
# Parche v0.70: RATON y TECLADO. La pantalla HDMI puede mostrar el panel (menus y botones) y manejarse con el raton.
# Sin pantalla pequena (como la Pi 3 de KORZO) la HDMI pasa sola a modo PANEL.
import re, shutil, sys, time
P = sys.argv[1] if len(sys.argv) > 1 else "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def mouse_loop" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.69' not in s:
    sys.exit("Este parche es para la v0.69")
shutil.copy(P, P + ".bak69")

def rep(old, new, all_=False):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new) if all_ else s.replace(old, new, 1)

# sin pantalla pequena el panel sigue funcionando con la HDMI
if "raise SystemExit('No encuentro el framebuffer de la pantalla')" in s:
    rep("    raise SystemExit('No encuentro el framebuffer de la pantalla')",
        "    return '/dev/null', 16, W * 2   # sin pantalla pequena: solo la HDMI")

CODE = r'''
# ---------- RATON Y TECLADO (y HDMI en modo PANEL) ----------
# Clic izquierdo = tocar   ·   clic derecho o TAB = HDMI: PANEL <-> TABLERO   ·   ESC = atras   ·   M = menu   ·   A = ajustes
SMALL = {"null": False}
mouse = {"x": W // 2, "y": H // 2, "t": 0.0}
PANEL_SURF = [None]
MOUSE_SPEED = 0.6

def hdmi_panel():
    return cfg.get("hdmi", "panel" if SMALL["null"] else "tablero") == "panel"

def hdmi_toggle():
    cfg["hdmi"] = "tablero" if hdmi_panel() else "panel"
    save_cfg()

def handle_input(ev, ec):
    now = time.time()
    if ev.type == ec.EV_REL:
        if ev.code == ec.REL_X:
            mouse["x"] = max(0, min(W - 1, mouse["x"] + ev.value * MOUSE_SPEED)); mouse["t"] = now
        elif ev.code == ec.REL_Y:
            mouse["y"] = max(0, min(H - 1, mouse["y"] + ev.value * MOUSE_SPEED)); mouse["t"] = now
    elif ev.type == ec.EV_KEY and ev.value == 1:
        if ev.code == ec.BTN_LEFT:
            mouse["t"] = now
            on_tap(int(mouse["x"]), int(mouse["y"]))
        elif ev.code in (ec.BTN_RIGHT, ec.KEY_TAB):
            hdmi_toggle()
        elif ev.code in (ec.KEY_ESC, ec.KEY_BACKSPACE):
            on_tap(*BACK.center)
        elif ev.code in (ec.KEY_M, ec.KEY_HOME):
            ui["view"] = 0
        elif ev.code == ec.KEY_A:
            ui["view"] = 12

def mouse_loop():
    try:
        from evdev import InputDevice, list_devices, ecodes as ec
    except ImportError:
        return
    import select
    devs = {}
    while True:
        for p in list_devices():
            if p in devs:
                continue
            try:
                d = InputDevice(p)
                caps = d.capabilities()
            except Exception:
                continue
            if "ADS7846" in d.name or "touch" in d.name.lower():
                continue                                   # el tactil lo lleva touch_loop
            if ec.EV_REL in caps or ec.KEY_ESC in caps.get(ec.EV_KEY, []):
                devs[p] = d
                print("Raton/teclado:", d.name)
        if not devs:
            time.sleep(5); continue
        try:
            r, _, _ = select.select(list(devs.values()), [], [], 5)
        except (OSError, ValueError):
            devs = {}; continue
        for d in r:
            try:
                for ev in d.read():
                    handle_input(ev, ec)
            except OSError:
                devs = {k: v for k, v in devs.items() if v is not d}

def draw_pointer(surf):
    if time.time() - mouse["t"] > 10:
        return
    x, y = int(mouse["x"]), int(mouse["y"])
    pts = [(x, y), (x, y + 16), (x + 4, y + 12), (x + 8, y + 19), (x + 11, y + 17), (x + 7, y + 11), (x + 12, y + 11)]
    pygame.draw.polygon(surf, WHITE, pts)
    pygame.draw.polygon(surf, BLACK, pts, 1)

def render_big_panel(S):
    src = PANEL_SURF[0]
    if src is None:
        return False
    bw, bh = BIG["w"], BIG["h"]
    sc = min(bw / W, bh / H)
    size = (int(W * sc), int(H * sc))
    S.fill(BLACK)
    try:
        img = pygame.transform.smoothscale(src, size)
    except ValueError:
        img = pygame.transform.scale(src, size)
    S.blit(img, ((bw - size[0]) // 2, (bh - size[1]) // 2))
    return True

'''
rep("\ndef render(surf):", CODE + "\ndef render(surf):")

# arrancar el hilo del raton y saber si hay pantalla pequena (en las dos definiciones de main)
rep('''    threading.Thread(target=touch_loop, daemon=True).start()''',
    '''    threading.Thread(target=touch_loop, daemon=True).start()
    threading.Thread(target=mouse_loop, daemon=True).start()''', all_=True)
rep('''    dev, bpp, stride = find_fb()
''', '''    dev, bpp, stride = find_fb()
    SMALL["null"] = dev == "/dev/null"
''', all_=True)

# puntero sobre el panel, y la HDMI en modo PANEL a 10 imagenes por segundo
rep('''            BIG["n"] += 1
            if BIG["n"] % 3 == 0:''', '''            draw_pointer(surf)
            PANEL_SURF[0] = surf
            BIG["n"] += 1
            if BIG["n"] % 3 == 0 or hdmi_panel():''')
rep('''def render_big():
    S, cell = BIG["surf"], BIG["cell"]
''', '''def render_big():
    S, cell = BIG["surf"], BIG["cell"]
    if hdmi_panel() and not ui.get("bye") and render_big_panel(S):
        return
''')

# manual
rep('''- < MENÚ (arriba a la izquierda) vuelve atrás.''',
    '''- < MENÚ (arriba a la izquierda) vuelve atrás.
# Ratón y teclado
- Con un ratón o un teclado con touchpad conectado a la Pi: clic izquierdo = tocar.
- Clic derecho o TAB: la pantalla HDMI cambia entre PANEL (los menús, para manejarlos con el ratón) y TABLERO (los cuadros de datos).
- ESC = atrás  ·  M = menú  ·  A = ajustes.
- Sin pantalla pequeña la HDMI arranca sola en modo PANEL.''')

rep('    ("0.69", "Botiquines y células en avisos y MAPA, MARCAR RECARGA, HAS CAÍDO y COBRADO"),\n',
    '    ("0.69", "Botiquines y células en avisos y MAPA, MARCAR RECARGA, HAS CAÍDO y COBRADO"),\n'
    '    ("0.70", "Ratón y teclado; la HDMI puede mostrar el PANEL (TAB o clic derecho)"),\n')
s = re.sub(r'PANEL_VER = "v0\.69[^"]*"', 'PANEL_VER = "v0.70 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.70 raton y teclado  (copia en " + P + ".bak69)")
