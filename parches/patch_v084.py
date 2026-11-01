#!/usr/bin/env python3
# Parche v0.84: NAVE AQUI recolocado, MENU PRINCIPAL en verde, "Esperando a Elite Dangerous" en rojo y amarillo,
# boton ESCUADRON en AMIGOS, "PUNTO DE RECARGA GRABADO" y cierre de emergencia del juego (3 toques en el sistema).
import re, shutil, sys, time
P = sys.argv[1] if len(sys.argv) > 1 else "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def kill_tap" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.83' not in s:
    sys.exit("Este parche es para la v0.83")
shutil.copy(P, P + ".bak83")

def rep(old, new, all_=False):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new) if all_ else s.replace(old, new, 1)

# ---------- 1. NAVE AQUI: un sitio en EN VIVO y otro en XENOBIOLOGIA ----------
rep('''NAVE_BTN = pygame.Rect(196, H - 60, 124, 40)''', '''NAVE_BTN = pygame.Rect(196, H - 58, 124, 36)          # EN VIVO
NAVE_BTN_BIO = pygame.Rect(196, H - 64, 124, 34)      # XENOBIOLOGIA: por encima de MUESTRAS SIN VENDER''')
rep('''def draw_compass(surf, d, b):''', '''def draw_compass(surf, d, b, btn=None):
    btn = btn or NAVE_BTN''')
rep('''        draw_button(surf, NAVE_BTN, "NAVE AQUÍ", None, F["btn"], lit=flash.get(("nave", 0), 0) > time.time())''',
    '''        draw_button(surf, btn, "NAVE AQUÍ", None, F["btn"], lit=flash.get(("nave", 0), 0) > time.time())''')
rep('''    draw_compass(surf, d, b)
''', '''    draw_compass(surf, d, b, NAVE_BTN_BIO)
''')
rep('''    elif v in (100, 73) and NAVE_BTN.collidepoint(x, y):''', '''    elif (v == 100 and NAVE_BTN.collidepoint(x, y)) or (v == 73 and NAVE_BTN_BIO.collidepoint(x, y)):''')
# EN VIVO a pie: los estados solo los activos, en una fila (deja sitio a consumibles y NAVE AQUI)
rep('''        y = chips(surf, [("ESTACIÓN", f2 & (1 << 3), BLUE), ("PLANETA", f2 & (1 << 4), BLUE),
                         ("RESPIRABLE", f2 & (1 << 16), GREEN), ("POCO O2", f2 & (1 << 6), RED),
                         ("SALUD BAJA", f2 & (1 << 7), RED), ("FRÍO", f2 & ((1 << 8) | (1 << 10)), BLUE),
                         ("CALOR", f2 & ((1 << 9) | (1 << 11)), RED), ("PLANEO", f2 & (1 << 12), ORANGE)], y)''',
    '''        act_ = [c_ for c_ in [("ESTACIÓN", f2 & (1 << 3), BLUE), ("PLANETA", f2 & (1 << 4), BLUE),
                              ("RESPIRABLE", f2 & (1 << 16), GREEN), ("POCO O2", f2 & (1 << 6), RED),
                              ("SALUD BAJA", f2 & (1 << 7), RED), ("FRÍO", f2 & ((1 << 8) | (1 << 10)), BLUE),
                              ("CALOR", f2 & ((1 << 9) | (1 << 11)), RED), ("PLANEO", f2 & (1 << 12), ORANGE)] if c_[1]]
        y = chips(surf, act_[:4], y) if act_ else y''')
rep('''        if P.get("n_items") or P.get("n_comp") or P.get("n_data"):
            put(surf, F["small"], f"Mochila''', '''        if not Z.get("n") and (P.get("n_items") or P.get("n_comp") or P.get("n_data")):
            put(surf, F["small"], f"Mochila''')

# ---------- 2. MENU PRINCIPAL en verde ----------
rep('''    title = ("EN EL MENÚ PRINCIPAL" if (d or {}).get("menu")''', '''    title = ("MENÚ PRINCIPAL" if (d or {}).get("menu")''')
rep('''        put(surf, F["big"], title, (x0, 6), ORANGE if online else DIM, W - 182 - x0)''',
    '''        put(surf, F["big"], title, (x0, 6), (GREEN if (d or {}).get("menu") else ORANGE) if online else DIM, W - 182 - x0)''')
rep('''            put(surf, F["btn"], "EN EL MENÚ PRINCIPAL", (W // 2, H - 44), ORANGE, anchor="center")''',
    '''            put(surf, F["big"], "MENÚ PRINCIPAL", (W // 2, H - 44), GREEN, anchor="center")''')
rep('''        put(S, fbig, "EN EL MENÚ PRINCIPAL", (bw // 2, bh - 40), DIM, anchor="center")''',
    '''        put(S, fbig, "MENÚ PRINCIPAL", (bw // 2, bh - 40), GREEN, anchor="center")''')

# ---------- 3. Esperando a Elite Dangerous: rojo y amarillo ----------
rep('''    elif waiting and int(now) % 4 < 3:
        put(surf, F["small"], "Esperando a Elite Dangerous...", (box.right - 8, box.y + 5), DIM, anchor="topright")''',
    '''    elif waiting and int(now) % 4 < 3 and not (state.get("data") or {}).get("menu"):
        t_ = "ESPERANDO A ELITE DANGEROUS"
        w_ = F["small"].size(t_)[0] + 14
        r_ = pygame.Rect(box.right - 6 - w_, box.y + 2, w_, 18)
        pygame.draw.rect(surf, RED, r_, border_radius=4)
        put(surf, F["small"], t_, r_.center, (255, 215, 0), anchor="center")''')

# ---------- 4. boton ESCUADRON en 11 SESION > AMIGOS ----------
rep('''    put(surf, F["small"], "toca para volver a SESIÓN", (W - 8, y), DIM, anchor="topright"); y += 16''',
    '''    put(surf, F["small"], "toca para volver a SESIÓN", (W - 8, y), DIM, anchor="topright"); y += 16
    draw_button(surf, SQ_BTN, "ESCUADRÓN  >", None, F["btn"], lit=flash.get(("sqbtn",), 0) > now)''')
rep('''            if y > H - 18:
                break
            put(surf, F["small"], n, (8, y), WHITE, 300)''', '''            if y > H - 40:
                break
            put(surf, F["small"], n, (8, y), WHITE, 300)''')
rep('''    elif v == 11:
        ui['sesstab'] = 1 - ui.get('sesstab', 0); return''', '''    elif v == 11:
        if ui.get('sesstab') and SQ_BTN.collidepoint(x, y):
            tap_flash(("sqbtn",)); ui["view"] = 165; ui["sqpage"] = 0; return
        ui['sesstab'] = 1 - ui.get('sesstab', 0); return''')

# ---------- 5. PUNTO DE RECARGA GRABADO ----------
rep('''    if ev_on("elink"):
        ui["toast"] = ("RECARGANDO  ·  enlace energético" + ("" if near else "  ·  punto marcado"), now + 4)''',
    '''    if ev_on("elink"):
        ui["toast"] = ("RECARGANDO  ·  enlace energético" if near else "PUNTO DE RECARGA GRABADO", now + 4)
        if not near and snd_on("elink"):
            voice_say("Punto de recarga grabado")
            if cfg.get("stream"):
                feed_add("ok", "PUNTO DE RECARGA GRABADO", "")''')

# ---------- 6. cierre de emergencia del juego ----------
rep('''        pkt, _ = s.recvfrom(65535)''', '''        pkt, addr_ = s.recvfrom(65535)
        state["pc"] = addr_[0]''')
rep('''def on_tap(x, y):
    if CAL:
        print("toque", x, y)''', '''def on_tap(x, y):
    if CAL:
        print("toque", x, y)
    if kill_tap(x, y):
        return''')
rep('''    draw_toast(surf, now)''', '''    draw_toast(surf, now)
    draw_kill(surf, now)''')
rep('''("VOZ", cfg.get("voice", False)), ("EMITIR", cfg.get("stream", False)), ("TECLAS", None)]''',
    '''("VOZ", cfg.get("voice", False)), ("EMITIR", cfg.get("stream", False)), ("TECLAS", None),
             ("CERRAR JUEGO", cfg.get("killbtn", True))]''')
rep('''        for i, k in enumerate(["auto", "alerts", "sound", "theme", "voice", "stream", "keys"]):''',
    '''        for i, k in enumerate(["auto", "alerts", "sound", "theme", "voice", "stream", "keys", "killbtn"]):''')
rep('''                if k == "keys":
                    tap_flash((124, i)); ui["view"] = 164; return''', '''                if k == "keys":
                    tap_flash((124, i)); ui["view"] = 164; return
                if k == "killbtn":
                    tap_flash((124, i)); cfg["killbtn"] = not cfg.get("killbtn", True); save_cfg(); return''')
rep('''        if name == "EMITIR" and on:''', '''        if name == "CERRAR JUEGO":
            sub = "3 toques en el sistema" if on else "DESACTIVADO"
        if name == "EMITIR" and on:''')

CODE = r'''
# ---------- v0.84: boton ESCUADRON y cierre de emergencia del juego ----------
SQ_BTN = pygame.Rect(W - 160, H - 36, 152, 32)
KILL_PORT, KILL_MSG = 5006, b"ELITEPANEL-KILL"
KILL = {"taps": [], "t0": None, "sent": 0.0, "seq": None}
KILL_SECS = 1.5
KILL_CANCEL = pygame.Rect(W // 2 - 110, H - 90, 220, 60)

def kill_title_rect():
    return pygame.Rect(BACK.right, 0, W - 182 - BACK.right, 32)

def kill_tap(x, y):
    """3 toques en el nombre del sistema: cuenta atras y el sender cierra el juego. Cualquier toque cancela."""
    now = time.time()
    if KILL["t0"]:
        KILL["t0"] = None
        set_alert("CIERRE CANCELADO", "", GREEN, 1.5, "ok")
        return True
    if not cfg.get("killbtn", True) or not kill_title_rect().collidepoint(x, y):
        return False
    KILL["taps"] = [t for t in KILL["taps"] if now - t < 2.0] + [now]
    if len(KILL["taps"]) >= 3:
        KILL["taps"] = []
        KILL["t0"] = now
        play("alarm")
    return True

def kill_send():
    pc = state.get("pc")
    if not pc:
        set_alert("NO SÉ LA IP DEL PC", "el sender no está enviando", RED, 3)
        return
    try:
        so = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        so.sendto(KILL_MSG, (pc, KILL_PORT))
        so.close()
        KILL["sent"] = time.time()
        set_alert("CERRANDO ELITE...", f"orden enviada al PC {pc}", ORANGE, 4)
    except OSError as e:
        set_alert("NO SE PUDO ENVIAR", str(e)[:40], RED, 3)

def draw_kill(surf, now):
    with lock:
        d = state["data"] or {}
    kr = d.get("killres") or {}
    if kr.get("seq") is not None and kr.get("seq") != KILL["seq"]:
        first = KILL["seq"] is None and now - KILL["sent"] > 30
        KILL["seq"] = kr.get("seq")
        if not first:
            set_alert("JUEGO CERRADO" if kr.get("ok") else "NO SE PUDO CERRAR", kr.get("msg", ""),
                      GREEN if kr.get("ok") else RED, 4)
    if not KILL["t0"]:
        return
    el = now - KILL["t0"]
    if el >= KILL_SECS:
        KILL["t0"] = None
        kill_send()
        return
    n = 3 - int(el / (KILL_SECS / 3))
    surf.fill(RED)
    put(surf, F["big"], "CERRANDO ELITE DANGEROUS", (W // 2, 40), (255, 215, 0), W - 16, anchor="center")
    put(surf, F["clock"], str(n), (W // 2, 130), (255, 215, 0), anchor="center")
    pygame.draw.rect(surf, BLACK, KILL_CANCEL, border_radius=10)
    pygame.draw.rect(surf, (255, 215, 0), KILL_CANCEL, 3, border_radius=10)
    put(surf, F["big"], "CANCELAR", KILL_CANCEL.center, (255, 215, 0), anchor="center")
    put(surf, F["small"], "toca en cualquier sitio para cancelar", (W // 2, H - 18), BLACK, anchor="center")

'''
rep("\ndef render(surf):", CODE + "\ndef render(surf):")

rep('''# Enlace energético''', '''# Cierre de emergencia del juego
- Tres toques seguidos sobre el nombre del sistema (arriba): pantalla roja con cuenta atrás rápida 3-2-1 y el sender del PC cierra Elite Dangerous (taskkill). Tocar en cualquier sitio cancela.
- Necesita el sender v0.84. La primera vez Windows puede preguntar por el cortafuegos: permite redes privadas.
- Se desactiva en AJUSTES > OPCIONES > CERRAR JUEGO.
# Enlace energético''')
rep('    ("0.83", "Botiquines, células y explosivos (máximo por traje) siempre a la vista; EN COMBATE en grande"),\n',
    '    ("0.83", "Botiquines, células y explosivos (máximo por traje) siempre a la vista; EN COMBATE en grande"),\n'
    '    ("0.84", "Cierre de emergencia del juego, ESCUADRÓN en AMIGOS, MENÚ PRINCIPAL en verde y arreglos"),\n')
s = re.sub(r'PANEL_VER = "v0\.83[^"]*"', 'PANEL_VER = "v0.84 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)
open(P, "w", encoding="utf-8").write(s)
print("OK v0.84  (copia en " + P + ".bak83)")
