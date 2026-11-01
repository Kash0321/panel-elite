#!/usr/bin/env python3
# Parche v0.77: teclas del juego (.binds, las manda el sender), indicador CPU/temperatura/FPS y modo PANEL ligero.
import re, shutil, sys, time
P = sys.argv[1] if len(sys.argv) > 1 else "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def apply_binds" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.76' not in s:
    sys.exit("Este parche es para la v0.76")
shutil.copy(P, P + ".bak76")

def rep(old, new, all_=False):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new) if all_ else s.replace(old, new, 1)

# ---------- teclas nuevas que puede usar el juego ----------
rep('''MODS = {'Ctrl': 0x01, 'Shift': 0x02, 'Alt': 0x04}''', '''MODS = {'Ctrl': 0x01, 'Shift': 0x02, 'Alt': 0x04, 'AltGr': 0x40}
KEYS.update({'-': 0x2D, '=': 0x2E, '[': 0x2F, ']': 0x30, '\\\\': 0x31, ';': 0x33, "'": 0x34, '`': 0x35, ',': 0x36,
             '/': 0x38, 'Backspace': 0x2A, 'Right': 0x4F, 'Left': 0x50, 'Down': 0x51, 'Up': 0x52, 'KPDiv': 0x54,
             'KPMul': 0x55, 'KPSub': 0x56, 'KPAdd': 0x57, 'KPEnter': 0x58, 'KPDec': 0x63})

def key_ok(k):
    *mods, kk = (k or "").split('+')
    return kk in KEYS and all(m in MODS for m in mods)''')

# una accion sin tecla no se manda: aviso
rep('''def press_seq(keys):
''', '''def press_seq(keys):
    if not all(key_ok(k) for k in keys):
        set_alert("SIN TECLA EN EL JUEGO", "mira AJUSTES > OPCIONES > TECLAS", ORANGE, 3)
        return
''')
rep('''                    if key == "KP0":''', '''                    if txt == "VOLVER":''')

# ---------- OPCIONES: 4 x 2 con TECLAS ----------
rep('''             ("VOZ", cfg.get("voice", False)), ("EMITIR", cfg.get("stream", False))]
    for i, (name, on) in enumerate(items):
        r = grid(i, 3, 2)''', '''             ("VOZ", cfg.get("voice", False)), ("EMITIR", cfg.get("stream", False)), ("TECLAS", None)]
    for i, (name, on) in enumerate(items):
        r = grid(i, 4, 2)
        if name == "TECLAS":
            miss = len(BINDS["missing"])
            draw_button(surf, r, name, (f"{miss} SIN TECLA  >" if miss else "TODAS  >") if BINDS["file"] else "DE FÁBRICA  >",
                        F["btn"], filled=bool(BINDS["file"]) and not miss, lit=flash.get((124, i), 0) > now)
            continue''')
rep('''        for i, k in enumerate(["auto", "alerts", "sound", "theme", "voice", "stream"]):
            if grid(i, 3, 2).collidepoint(x, y):''', '''        for i, k in enumerate(["auto", "alerts", "sound", "theme", "voice", "stream", "keys"]):
            if grid(i, 4, 2).collidepoint(x, y):
                if k == "keys":
                    tap_flash((124, i)); ui["view"] = 164; return''')

rep('''        draw_button(surf, r, name, sub, F["btn"], filled=on, lit=lit)

# ---------- reposo''', '''        draw_button(surf, r, name, sub, F["btn"] if F["btn"].size(name)[0] < r.w - 10 else F["small"], filled=on, lit=lit)

# ---------- reposo''')

# ---------- PANEL ligero: la HDMI en modo PANEL solo se redibuja si el panel cambia ----------
rep('''            BIG["n"] += 1
            if big_due() or hdmi_panel():
                big_frame()
                stream_snap(surf)
            data = to_fb_bytes(surf, bpp, stride)''', '''            BIG["n"] += 1
            if big_go(surf):
                big_frame()
                stream_snap(surf)
            data = to_fb_bytes(surf, bpp, stride)''', all_=True)
rep('''def big_frame():
    if BIG["fb"] is None:
        if BIG["dev"] is None and not big_open():
            BIG["dev"] = False
        if BIG["fb"] is None:
            return
    try:
        render_big()''', '''def big_frame():
    if BIG["fb"] is None:
        if BIG["dev"] is None and not big_open():
            BIG["dev"] = False
        if BIG["fb"] is None:
            return
    try:
        PERF["frames"] += 1
        render_big()''')

# ---------- indicador en la barra de la pantalla grande ----------
rep('''        bx = pygame.Rect(bw // 2 + 20, 12, 160, 18)''', '''        bx = pygame.Rect(bw // 2 + 20, 8 if cfg.get("perf") else 12, 160, 14 if cfg.get("perf") else 18)''')
rep('''        put(S, fsm, f"FUEL {fuel:.1f} t", (bx.right + 10, 14), ORANGE)''',
    '''        put(S, fsm, f"FUEL {fuel:.1f} t", (bx.right + 10, 6 if cfg.get("perf") else 14), ORANGE)''')
rep('''    put(S, fbig, time.strftime("%H:%M"), (bw - 12, 9), ORANGE, anchor="topright")
''', '''    put(S, fbig, time.strftime("%H:%M"), (bw - 12, 9), ORANGE, anchor="topright")
    if cfg.get("perf"):
        perf_draw(S, bw // 2 + 20, 27)
''')
rep('''def render_big_panel(S):
    hi = panel_hi() if cfg.get("sharp") else None
    if hi is not None:
        S.fill(BLACK)
        S.blit(hi, ((BIG["w"] - hi.get_width()) // 2, (BIG["h"] - hi.get_height()) // 2))
        return True''', '''def render_big_panel(S):
    hi = panel_hi() if cfg.get("sharp") else None
    if hi is not None:
        S.fill(BLACK)
        S.blit(hi, ((BIG["w"] - hi.get_width()) // 2, (BIG["h"] - hi.get_height()) // 2))
        if cfg.get("perf"):
            perf_side(S)
        return True''')

CODE = r'''
# ---------- v0.77: teclas del juego, indicador de CPU y PANEL ligero ----------
# Que accion del juego hace cada boton (nombres del fichero .binds). Varias = la primera que tenga tecla.
BIND_MAP = {
    "BUTTONS": {"TREN": "LandingGearToggle", "LUCES": "ShipSpotLightToggle", "VISIÓN NOC": "NightVisionToggle",
                "RECOGEDOR": "ToggleCargoScoop", "SUPERCRUC.": "Supercruise|HyperSuperCombination",
                "SILENCIO": "ToggleButtonUpInput", "DISIPADOR": "DeployHeatSink", "CHAFF": "FireChaffLauncher",
                "SALTO FSD": "Hyperspace|HyperSuperCombination", "ESCUDO": "UseShieldCell",
                "MAPA GAL": "GalaxyMapOpen", "MAPA SIS": "SystemMapOpen"},
    "PIP_COLS": {"SISTEMAS": "IncreaseSystemsPower", "MOTORES": "IncreaseEnginesPower", "ARMAS": "IncreaseWeaponsPower"},
    "SRV_BTNS": {"FAROS": "HeadlightsBuggyButton", "TORRETA": "ToggleBuggyTurretButton",
                 "RECOGER": "ToggleCargoScoop_Buggy", "NAVE": "RecallDismissShip",
                 "MAPA GAL": "GalaxyMapOpen_Buggy|GalaxyMapOpen", "MAPA SIS": "SystemMapOpen_Buggy|SystemMapOpen"},
    "PIE_BTNS": {"LINTERNA": "HumanoidToggleFlashlightButton", "VISIÓN NOC": "HumanoidToggleNightVisionButton",
                 "ESCUDO": "HumanoidToggleShieldsButton", "BOTIQUÍN": "HumanoidHealthPack",
                 "BATERÍA": "HumanoidBattery", "RECARGAR": "HumanoidReloadButton"},
    "COMBAT_BTNS": {"OBJETIVO": "SelectTarget", "SIGUIENTE": "CycleNextTarget", "ANTERIOR": "CyclePreviousTarget",
                    "PELIGROSO": "SelectHighestThreat", "SU OBJ.": "SelectTargetsTarget",
                    "SUBSIST.": "CycleNextSubsystem|CyclePreviousSubsystem", "ALA 1": "TargetWingman0",
                    "ALA 2": "TargetWingman1", "ALA 3": "TargetWingman2", "CHAFF": "FireChaffLauncher",
                    "DISIPADOR": "DeployHeatSink", "ESCUDO": "UseShieldCell"},
    "FIGHTER_BTNS": {"DEFENSIVO": "OrderDefensiveBehaviour", "AGRESIVO": "OrderAggressiveBehaviour",
                     "ATACAR": "OrderFocusTarget", "ALTO FUEGO": "OrderHoldFire", "POSICIÓN": "OrderHoldPosition",
                     "SEGUIRME": "OrderFollow", "VOLVER": "OrderRequestDock", "ÓRDENES": "OpenOrders"},
}
PIP_RESET_ACT = "ResetPowerDistribution"
SIN = "SIN TECLA"
BINDS = {"sig": None, "file": None, "missing": [], "free": [], "page": 0}
_BDEF = {}

def apply_binds(B):
    """Pone en los botones las teclas del juego (las manda el sender). Sin datos: las de fabrica."""
    g = globals()
    if not _BDEF:
        for name in BIND_MAP:
            _BDEF[name] = list(g[name])
        _BDEF["PIP_PRESETS"] = list(PIP_PRESETS)
    keys = (B or {}).get("keys") if B else None
    missing = []
    for name, amap in BIND_MAP.items():
        new = []
        for it in _BDEF[name]:
            it = list(it)
            if keys is not None and it[0] in amap:
                acts = amap[it[0]].split("|")
                k = next((keys[a] for a in acts if a in keys and key_ok(keys[a])), None)
                if k is None:
                    missing.append((it[0], acts[0], (B.get("bad") or {}).get(acts[0])))
                it[1] = k or SIN
            new.append(tuple(it))
        g[name][:] = new
    if keys is not None:
        r = keys.get(PIP_RESET_ACT) if key_ok(keys.get(PIP_RESET_ACT)) else None
        if r is None:
            missing.append(("RESET PIPS", PIP_RESET_ACT, (B.get("bad") or {}).get(PIP_RESET_ACT)))
        sy, mo, ar = [k for _, k in PIP_COLS]
        PIP_PRESETS[:] = [("RESET", [r or SIN]), ("MAX SIS", [r or SIN] + [sy] * 4),
                          ("MAX MOT", [r or SIN] + [mo] * 4), ("MAX ARM", [r or SIN] + [ar] * 4)]
    else:
        PIP_PRESETS[:] = _BDEF["PIP_PRESETS"]
    seen, uniq = set(), []
    for m in missing:
        if (m[0], m[1]) not in seen:
            seen.add((m[0], m[1])); uniq.append(m)
    BINDS.update(file=(B or {}).get("file") if keys is not None else None, missing=uniq,
                 free=list((B or {}).get("free") or []))

def binds_check(d):
    B = (d or {}).get("binds")
    sig = (B or {}).get("file"), len((B or {}).get("keys") or {}), str(sorted(((B or {}).get("keys") or {}).items()))[:4000]
    if B and sig != BINDS["sig"]:
        BINDS["sig"] = sig
        apply_binds(B)
        if BINDS["missing"] and ev_on("keys"):
            set_alert("TECLAS DEL JUEGO", f"{len(BINDS['missing'])} botones sin tecla: AJUSTES > OPCIONES > TECLAS", ORANGE, 5)

def view_keys(surf, d, flags, now):
    y = TOP + 4
    if not BINDS["file"]:
        put(surf, F["btn"], "Teclas de fábrica del panel", (8, y), ORANGE); y += 24
        for t in ["El sender del PC no ha mandado tus controles.",
                  "Actualiza elite_sender.py (v0.77) en el PC de juego:",
                  "lee el fichero .binds que usa el juego y el panel",
                  "pone en cada botón tu tecla."]:
            put(surf, F["small"], t, (8, y), DIM, W - 16); y += 18
        return
    miss = BINDS["missing"]
    put(surf, F["btn"], BINDS["file"], (8, y), ORANGE, W - 16); y += 22
    if not miss:
        put(surf, F["btn"], "Todos los botones tienen tecla", (8, y + 6), GREEN); y += 34
        put(surf, F["small"], "El panel usa las teclas de tus controles del juego.", (8, y), DIM, W - 16)
        return
    put(surf, F["small"], f"{len(miss)} botones sin tecla de teclado. Asígnales en el juego (OPCIONES > CONTROLES)",
        (8, y), DIM, W - 16); y += 16
    put(surf, F["small"], "una de estas teclas, que no usas:", (8, y), DIM, W - 16); y += 20
    free = BINDS["free"]
    per = 6
    pages = max(1, (len(miss) + per - 1) // per)
    pg = BINDS["page"] % pages
    for i, (lab, act, bad) in enumerate(miss[pg * per:(pg + 1) * per]):
        j = pg * per + i
        put(surf, F["btn"], lab, (8, y), WHITE, 120)
        put(surf, F["small"], act, (132, y + 4), DIM, 210)
        sug = f"tecla {bad.replace('Key_', '')} no válida" if bad else (free[j] if j < len(free) else "")
        put(surf, F["btn"], sug, (W - 8, y), RED if bad else GREEN, 130, anchor="topright")
        y += 26
    if pages > 1:
        put(surf, F["small"], f"pág {pg + 1}/{pages}  (toca)", (W - 8, H - 18), DIM, anchor="topright")

def tap_keys(x, y):
    BINDS["page"] += 1

VIEWS[164] = view_keys
MENU[164] = "TECLAS DEL JUEGO"
PARENT[164] = 1244

# --- consumo: CPU del panel (como top), temperatura de la Pi y FPS de la pantalla grande
PERF = {"t": 0.0, "cpu": None, "temp": None, "fps": 0.0, "frames": 0, "f0": 0, "c0": None, "w0": None}

def perf_update():
    now = time.time()
    if now - PERF["t"] < 2:
        return
    try:
        with open("/proc/self/stat") as f:
            st = f.read().rsplit(")", 1)[1].split()
        c = (int(st[11]) + int(st[12])) / os.sysconf("SC_CLK_TCK")
        if PERF["c0"] is not None:
            PERF["cpu"] = 100.0 * (c - PERF["c0"]) / max(0.1, now - PERF["w0"])
        PERF["c0"], PERF["w0"] = c, now
    except (OSError, ValueError, IndexError):
        pass
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            PERF["temp"] = int(f.read()) / 1000
    except (OSError, ValueError):
        PERF["temp"] = None
    if PERF["t"]:
        PERF["fps"] = (PERF["frames"] - PERF["f0"]) / (now - PERF["t"])
    PERF["f0"], PERF["t"] = PERF["frames"], now

def perf_parts():
    c, t = PERF["cpu"], PERF["temp"]
    out = []
    if c is not None:
        out.append((f"CPU {c:.0f} %", GREEN if c < 30 else ORANGE if c < 60 else RED))
    if t is not None:
        out.append((f"{t:.0f} °C", GREEN if t < 70 else ORANGE if t < 80 else RED))
    out.append((f"{PERF['fps']:.0f} FPS", DIM))
    return out

def perf_draw(S, x, y):
    f = BIG.get("pfont") or BIG.setdefault("pfont", pygame.font.Font(None, 20))
    for i, (t, col) in enumerate(perf_parts()):
        if i:
            x += put(S, f, "·", (x + 6, y), DIM) + 12
        x += put(S, f, t, (x, y), col)

def perf_side(S):
    f = BIG.get("pfont") or BIG.setdefault("pfont", pygame.font.Font(None, 20))
    y = 8
    for t, col in perf_parts():
        put(S, f, t, (BIG["w"] - 6, y), col, anchor="topright"); y += 16

def big_go(surf):
    """Si toca redibujar la pantalla grande en este ciclo."""
    perf_update()
    if not hdmi_panel():
        return big_due()
    # modo PANEL: solo si el panel ha cambiado (sin contar el engranaje que gira)
    sig = pygame.image.tostring(surf.subsurface((0, 0, GEAR.x, H)), "RGB") + \
          pygame.image.tostring(surf.subsurface((GEAR.x, GEAR.bottom, W - GEAR.x, H - GEAR.bottom)), "RGB")
    changed = sig != BIG.get("psig")
    if changed:
        BIG["psig"] = sig
    if cfg.get("bigfps", "AUTO") != "AUTO" and not big_due():
        if changed:
            BIG["psig"] = None                 # que se dibuje en el siguiente ciclo permitido
        return False
    if changed or time.time() - BIG.get("plast", 0) > 5:
        BIG["plast"] = time.time()
        return True
    return False

'''
rep("\ndef render(surf):", CODE + "\ndef render(surf):")

# aplicar las teclas al llegar datos
rep('''    if online and not HI_PASS[0]:
        process_notes(d)''', '''    if online and not HI_PASS[0]:
        binds_check(d)
        process_notes(d)''')
rep('''    elif v in (161, 162, 163):''', '''    elif v == 164:
        tap_keys(x, y); return
    elif v in (161, 162, 163):''')
# aviso de teclas en la lista de ALERTAS
rep('''("galnet", "NOTICIA GALNET"), ("power", "BAJA TENSIÓN")]''', '''("galnet", "NOTICIA GALNET"), ("power", "BAJA TENSIÓN"),
           ("keys", "TECLAS SIN ASIGNAR")]''')

# ---------- PANTALLA: 4 botones con INDICADOR ----------
rep('''             ("FPS", "AUTO (3/10)" if f == "AUTO" else f"{f} por seg.", False)]
    for i, (t, sub, fill) in enumerate(items):
        draw_button(surf, grid(i, 3, 1, TOP, H - 40), t, sub, F["big"], filled=fill, lit=flash.get((160, i), 0) > now)
    put(surf, F["small"], "Toca para cambiar. FPS AUTO: rápido solo con mapas.",
        (W // 2, H - 30), DIM, W - 16, anchor="midtop")''', '''             ("FPS", "AUTO (3/10)" if f == "AUTO" else f"{f} por seg.", False),
             ("CONSUMO", "SÍ" if cfg.get("perf") else "NO", bool(cfg.get("perf")))]
    for i, (t, sub, fill) in enumerate(items):
        draw_button(surf, grid(i, 2, 2, TOP, H - 40), t, sub, F["big"], filled=fill, lit=flash.get((160, i), 0) > now)
    perf_update()
    x = 8
    for j, (t, col) in enumerate(perf_parts()):
        x += put(surf, F["btn"], t, (x, H - 32), col) + 14
    put(surf, F["small"], "pantalla grande", (W - 8, H - 26), DIM, anchor="topright")''')
rep('''    for i in range(3):
        if not grid(i, 3, 1, TOP, H - 40).collidepoint(x, y):
            continue''', '''    for i in range(4):
        if not grid(i, 2, 2, TOP, H - 40).collidepoint(x, y):
            continue''')
rep('''        else:
            cfg["bigfps"] = BIGFPS[(BIGFPS.index(cfg.get("bigfps", "AUTO")) + 1) % len(BIGFPS)]''', '''        elif i == 2:
            cfg["bigfps"] = BIGFPS[(BIGFPS.index(cfg.get("bigfps", "AUTO")) + 1) % len(BIGFPS)]
        else:
            cfg["perf"] = not cfg.get("perf", False)''')

# --- manual
rep('''- En la página web del PC (EMITIR) también funcionan ESC, M, A y TAB.''',
    '''- En la página web del PC (EMITIR) también funcionan ESC, M, A y TAB.
# Teclas del juego
- Con el sender v0.77 el PC manda tus controles (el fichero .binds que usa el juego) y cada botón usa tu tecla.
- AJUSTES > OPCIONES > TECLAS: el fichero leído y los botones sin tecla de teclado, con una tecla libre que puedes asignar en el juego.
- Un botón sin tecla pone SIN TECLA y al tocarlo avisa.''')
rep('''- En la pantalla grande, a la izquierda de la hora, la fecha del juego.''',
    '''- En la pantalla grande, a la izquierda de la hora, la fecha del juego.
- AJUSTES > PANTALLA > CONSUMO: CPU del panel, temperatura de la Pi y FPS de la pantalla grande (verde, naranja, rojo).''')

rep('    ("0.76", "Mapa a pie sin el vuelo del transporte, leyenda de símbolos y más zoom en ZONA"),\n',
    '    ("0.76", "Mapa a pie sin el vuelo del transporte, leyenda de símbolos y más zoom en ZONA"),\n'
    '    ("0.77", "Teclas del juego (.binds), indicador de CPU/temperatura/FPS y modo PANEL ligero"),\n')
s = re.sub(r'PANEL_VER = "v0\.76[^"]*"', 'PANEL_VER = "v0.77 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.77  (copia en " + P + ".bak76)")
