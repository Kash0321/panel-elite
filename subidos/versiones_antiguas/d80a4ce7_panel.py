#!/usr/bin/env python3
# Panel tactil Elite Dangerous - Raspberry Pi 4 + pantalla 3.5" 480x320
import os, glob, json, socket, threading, time, queue, hashlib, base64, math, shutil, subprocess, wave, struct
from collections import deque
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
import numpy as np

UDP_PORT = 5005
W, H = 480, 320
SWAP_XY, INV_X, INV_Y = False, False, True   # ajustar si el tactil va cruzado
HOLD = 0.08                                     # segundos que se mantiene pulsada la tecla
CAL = os.environ.get("CAL") == "1"              # CAL=1 imprime coordenadas del tactil

# OBS (PC de streaming) - en OBS: Herramientas > Ajustes del servidor WebSocket
OBS_HOST = "192.168.0.XXX"   # <-- IP del PC de streaming
OBS_PORT = 4455
OBS_PASSWORD = ""            # <-- contrasena del servidor WebSocket de OBS
OBS_MIC = ""                 # nombre de la fuente del micro; vacio = el "Mic/Aux" de OBS

KEYS = {chr(c): 0x04 + i for i, c in enumerate(range(ord('a'), ord('z') + 1))}
KEYS.update({str(n): 0x1E + (n - 1) for n in range(1, 10)}); KEYS['0'] = 0x27
KEYS.update({'.': 0x37, 'Insert': 0x49, 'Home': 0x4A, 'PageUp': 0x4B, 'Delete': 0x4C, 'End': 0x4D,
             'PageDown': 0x4E, 'Tab': 0x2B, 'Space': 0x2C, 'Enter': 0x28, 'Esc': 0x29})
KEYS.update({f'F{i}': 0x3A + i - 1 for i in range(1, 13)})
KEYS.update({f'KP{n}': 0x59 + n - 1 for n in range(1, 10)}); KEYS['KP0'] = 0x62
MODS = {'Ctrl': 0x01, 'Shift': 0x02, 'Alt': 0x04}

# ---------- contenido de los menus ----------
MENU = {1: "MANDOS", 2: "PIPS", 3: "NAVEGACIÓN", 4: "CARGA/MISIÓN", 5: "SRV / A PIE", 6: "COMBATE", 7: "EXPLORACIÓN",
        8: "ESTACIÓN", 9: "CAZA", 10: "MINERÍA", 11: "SESIÓN", 12: "LOG / STREAM", 121: "LOG", 122: "STREAM",
        71: "EXPLORACIÓN", 72: "SISTEMA"}
MENU.update({123: "RANGOS", 124: "AJUSTES"})
PARENT = {71: 7, 72: 7, 121: 12, 122: 12, 123: 12, 124: 12}
CMDR_NAME = "ORTEM ED DER"

# Menu 1 - (texto, tecla, bit de Flags o None)
BUTTONS = [
    ("TREN", ".", 2), ("LUCES", "l", 8), ("VISIÓN NOC", "n", 28), ("RECOGEDOR", "c", 9),
    ("SUPERCRUC.", "m", 4), ("SILENCIO", "Shift+y", 10), ("DISIPADOR", "e", None), ("CHAFF", "Shift+r", None),
    ("SALTO FSD", "h", 17), ("ESCUDO", "Shift+e", None), ("MAPA GAL", "g", None), ("MAPA SIS", "s", None),
]
# Menu 2 - pips
PIP_COLS = [("SISTEMAS", "y"), ("MOTORES", "u"), ("ARMAS", "i")]
PIP_PRESETS = [("RESET", ["j"]), ("MAX SIS", ["j", "y", "y", "y", "y"]),
               ("MAX MOT", ["j", "u", "u", "u", "u"]), ("MAX ARM", ["j", "i", "i", "i", "i"])]
# Menu 5 - (texto, tecla, bit de Flags o None)
SRV_BTNS = [("FAROS", "l", 8), ("TORRETA", "t", 13), ("RECOGER", "c", 9),
            ("NAVE", "h", None), ("MAPA GAL", "g", None), ("MAPA SIS", "s", None)]
PIE_BTNS = [("LINTERNA", "l", None), ("VISIÓN NOC", "n", None), ("ESCUDO", "c", None),
            ("BOTIQUÍN", "F1", None), ("BATERÍA", "F2", None), ("RECARGAR", "r", None)]

# Menu 6 - combate (texto, tecla)
COMBAT_BTNS = [("OBJETIVO", "Shift+f"), ("SIGUIENTE", "Shift+q"), ("ANTERIOR", "Shift+w"), ("PELIGROSO", "Shift+p"),
               ("SU OBJ.", "0"), ("SUBSIST.", "Shift+a"), ("ALA 1", "7"), ("ALA 2", "8"),
               ("ALA 3", "9"), ("CHAFF", "Shift+r"), ("DISIPADOR", "e"), ("ESCUDO", "Shift+e")]
# Menu 9 - ordenes del caza (texto, tecla, grupo: los del mismo grupo se excluyen)
FIGHTER_BTNS = [("DEFENSIVO", "KP1", "b"), ("AGRESIVO", "KP2", "b"), ("ATACAR", "KP3", "a"), ("ALTO FUEGO", "KP4", "a"),
                ("POSICIÓN", "KP5", "m"), ("SEGUIRME", "KP6", "m"), ("VOLVER", "KP0", "m"), ("ÓRDENES", "KP7", None)]

ALERTS = [(20, "SOBRECALENTADO"), (23, "INTERDICCION"), (22, "PELIGRO"), (19, "COMBUSTIBLE BAJO"), (16, "MASS LOCK")]
SCOOPABLE = set("KGBFOAM")

ORANGE = (255, 140, 0); DIM = (120, 66, 0); BLACK = (0, 0, 0); RED = (230, 40, 30)
WHITE = (230, 230, 230); BLUE = (90, 170, 255); GREEN = (90, 220, 120)

state = {"data": None, "rx": 0.0, "log": deque(maxlen=300)}
ui = {"view": 0, "pause": False, "tab4": 0, "page4": 0, "orders": {}, "page7": 0, "confirm": (None, 0),
      "start": time.time(), "idle_skip": 0, "idle_on": False, "note_seq": None, "gui": 0, "alert": None}

# ---------- ajustes (se guardan en la Pi) ----------
SETTINGS_FILE = os.path.expanduser("~/panel_ajustes.json")
THEMES = [("NARANJA", (255, 140, 0)), ("AZUL", (80, 160, 255)), ("VERDE", (60, 220, 110)),
          ("MORADO", (190, 110, 255)), ("ROJO", (255, 80, 60)), ("BLANCO", (225, 225, 225))]
cfg = {"auto": True, "alerts": True, "sound": True, "theme": 0, "cmdr": CMDR_NAME}

def load_cfg():
    try:
        cfg.update(json.load(open(SETTINGS_FILE)))
    except Exception:
        pass
    apply_theme()

def save_cfg():
    try:
        json.dump(cfg, open(SETTINGS_FILE, "w"))
    except Exception as e:
        print("No guardo ajustes:", e)

def apply_theme():
    global ORANGE, DIM
    ORANGE = THEMES[cfg["theme"] % len(THEMES)][1]
    DIM = tuple(c * 47 // 100 for c in ORANGE)

# ---------- sonidos ----------
SOUNDS = {}

def make_sounds():
    def tone(path, parts):
        with wave.open(path, "w") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
            frames = b""
            for f0, f1, dur in parts:
                n = int(22050 * dur)
                for k in range(n):
                    f = f0 + (f1 - f0) * k / n
                    env = min(1, k / 300, (n - k) / 300)
                    frames += struct.pack("<h", int(9000 * env * math.sin(2 * math.pi * f * k / 22050)))
            w.writeframes(frames)
    try:
        SOUNDS["alarm"] = "/tmp/panel_alarma.wav"; tone(SOUNDS["alarm"], [(880, 880, .15), (0, 0, .05), (660, 660, .15)] * 2)
        SOUNDS["jump"] = "/tmp/panel_salto.wav"; tone(SOUNDS["jump"], [(200, 1200, 1.2)])
        SOUNDS["ok"] = "/tmp/panel_ok.wav"; tone(SOUNDS["ok"], [(660, 990, .18)])
    except Exception as e:
        print("Sin sonidos:", e)

def play(name):
    if cfg["sound"] and name in SOUNDS and shutil.which("aplay"):
        try:
            subprocess.Popen(["aplay", "-q", SOUNDS[name]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass

# ---------- avisos: alertas y cambio automatico de menu ----------
AUTO_VIEW = {"interdicted": 6, "underattack": 6, "docking": 8, "prospector": 10, "srv": 5, "foot": 5, "fighter": 9}

def set_alert(text, sub="", col=None, secs=3.0, kind="red"):
    ui["alert"] = {"text": text, "sub": sub, "col": col or RED, "until": time.time() + secs, "kind": kind}

def handle_note(kind, text):
    if cfg["auto"] and kind in AUTO_VIEW:
        ui["view"] = AUTO_VIEW[kind]
    if not cfg["alerts"]:
        return
    if kind == "jump":
        sysname, cls = (text.split("|") + [""])[:2]
        set_alert("SALTO AL HIPERESPACIO", f"> {sysname}" + (f"  (estrella {cls})" if cls else ""), BLUE, 45, "jump")
        play("jump")
    elif kind == "jumpend":
        if ui["alert"] and ui["alert"]["kind"] == "jump":
            ui["alert"] = None
    elif kind == "interdicted":
        set_alert("¡INTERDICCIÓN!", text, secs=4); play("alarm")
    elif kind == "underattack":
        set_alert("¡TE ATACAN!", "", secs=2); play("alarm")
    elif kind == "shields_down":
        set_alert("ESCUDOS CAÍDOS", "", secs=3); play("alarm")
    elif kind == "shields_up":
        set_alert("ESCUDOS ARRIBA", "", GREEN, 1.5, "ok"); play("ok")
    elif kind == "hull":
        set_alert(f"CASCO {text}%", "", secs=3); play("alarm")
    elif kind == "heat":
        set_alert("SOBRECALENTAMIENTO", "", secs=3); play("alarm")

def process_notes(d):
    notes = d.get("notes") or []
    top = max([n[0] for n in notes], default=0)
    if ui["note_seq"] is None or top < ui["note_seq"]:     # arranque o sender reiniciado
        ui["note_seq"] = top
    for seq, kind, text in notes:
        if seq > ui["note_seq"]:
            ui["note_seq"] = seq
            handle_note(kind, text)
    gui = d.get("gui", 0)
    if gui == 9 and ui["gui"] != 9 and cfg["auto"]:          # FSS abierto
        ui["view"] = 72
    ui["gui"] = gui
    cm = (d.get("ranks") or {}).get("cmdr")
    if cm and cm.upper() != cfg.get("cmdr"):
        cfg["cmdr"] = cm.upper(); save_cfg()
flash = {}
lock = threading.Lock()

# ---------- framebuffer ----------
ROT = False

def find_fb():
    global ROT
    cands = []
    for p in sorted(glob.glob('/sys/class/graphics/fb*')):
        try:
            name = open(p + '/name').read().strip()
            w, h = map(int, open(p + '/virtual_size').read().strip().split(','))
            bpp = int(open(p + '/bits_per_pixel').read())
            stride = int(open(p + '/stride').read())
        except Exception:
            continue
        print("Encontrado", p, name, w, h, bpp)
        cands.append((name, w, h, bpp, stride, '/dev/' + os.path.basename(p)))
    for name, w, h, bpp, stride, dev in cands:
        if 'vc4' not in name.lower() and (min(w, h) == min(W, H) or 'ili' in name.lower() or 'piscreen' in name.lower()):
            ROT = w == 320
            return dev, bpp, stride
    raise SystemExit('No encuentro el framebuffer de la pantalla')

def to_fb_bytes(surf, bpp, stride):
    if ROT:
        surf = pygame.transform.rotate(surf, 90)
    a = pygame.surfarray.array3d(surf).swapaxes(0, 1)
    hh, ww = a.shape[:2]
    if bpp == 16:
        r = (a[:, :, 0].astype(np.uint16) >> 3) << 11
        g = (a[:, :, 1].astype(np.uint16) >> 2) << 5
        b = a[:, :, 2].astype(np.uint16) >> 3
        px = np.ascontiguousarray(r | g | b).view(np.uint8).reshape(hh, ww * 2)
    else:
        alpha = np.full(a.shape[:2] + (1,), 255, np.uint8)
        px = np.concatenate([a[:, :, 2:3], a[:, :, 1:2], a[:, :, 0:1], alpha], axis=2).reshape(hh, ww * 4)
    if stride > px.shape[1]:
        px = np.pad(px, ((0, 0), (0, stride - px.shape[1])))
    return px.tobytes()

# ---------- teclado USB ----------
hid_lock = threading.Lock()

def _press(f, key):
    *mods, k = key.split('+')
    code, mod = KEYS[k], sum(MODS[m] for m in mods)
    f.write(bytes([mod, 0, 0, 0, 0, 0, 0, 0])); time.sleep(0.02)
    f.write(bytes([mod, 0, code, 0, 0, 0, 0, 0])); time.sleep(HOLD)
    f.write(bytes([mod, 0, 0, 0, 0, 0, 0, 0])); f.write(bytes(8))

def press_seq(keys):
    def run():
        with hid_lock:
            try:
                with open('/dev/hidg0', 'wb', buffering=0) as f:
                    for k in keys:
                        _press(f, k); time.sleep(0.12)
            except OSError as e:
                print("Error HID:", e)
    threading.Thread(target=run, daemon=True).start()

# ---------- UDP ----------
def udp_loop():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("0.0.0.0", UDP_PORT))
    while True:
        pkt, _ = s.recvfrom(65535)
        try:
            d = json.loads(pkt)
        except Exception:
            continue
        with lock:
            if "log" in d:
                if not ui["pause"]:
                    state["log"].append(d["log"])
            else:
                state["data"] = d
                state["rx"] = time.time()

# ---------- layout ----------
TOP = 56
BACK = pygame.Rect(0, 0, 96, TOP - 4)

def grid(i, cols=4, rows=3, top=TOP, bottom=H, left=0, right=W):
    cw, ch = (right - left) // cols, (bottom - top) // rows
    c, r = i % cols, i // cols
    return pygame.Rect(left + c * cw + 4, top + r * ch + 4, cw - 8, ch - 8)

PIP_BOTTOM = 238
SEC_TOP = TOP + 20   # menu 5: hueco para los titulos SRV / A PIE
TAB_H = 36           # menu 4: pestanas

def pip_rect(i):  return grid(i, 3, 1, TOP, PIP_BOTTOM)
def preset_rect(i): return grid(i, 4, 1, PIP_BOTTOM, H)
def tab_rect(i):  return grid(i, 2, 1, TOP, TOP + TAB_H)
def m5_rect(i):   return grid(i % 2 + (2 if i >= 6 else 0) + 4 * ((i % 6) // 2), 4, 3, SEC_TOP, H)

CARD6 = TOP + 112      # menu 6: alto de la ficha del objetivo
CARD9 = TOP + 76       # menu 9: alto de la ficha del caza
def c6_rect(i): return grid(i, 4, 3, CARD6, H)
def c9_rect(i): return grid(i, 4, 2, CARD9, H)

def tap_flash(key):
    flash[key] = time.time() + 0.25

def on_tap(x, y):
    if CAL:
        print("toque", x, y)
    if ui["alert"] and time.time() < ui["alert"]["until"]:
        ui["alert"] = None; return
    if ui["idle_on"]:
        ui["idle_skip"] = time.time() + 60; return
    v = ui["view"]
    if v and BACK.collidepoint(x, y):
        ui["view"] = PARENT.get(v, 0); ui["pause"] = False
        return
    if v == 0:
        for i in range(12):
            if grid(i).collidepoint(x, y):
                tap_flash((0, i)); ui["view"] = i + 1; ui["page4"] = 0
                return
    elif v == 1:
        for i, b in enumerate(BUTTONS):
            if grid(i).collidepoint(x, y):
                tap_flash((1, i)); press_seq([b[1]]); return
    elif v == 2:
        for i, (_, k) in enumerate(PIP_COLS):
            if pip_rect(i).collidepoint(x, y):
                tap_flash((2, i)); press_seq([k]); return
        for i, (_, ks) in enumerate(PIP_PRESETS):
            if preset_rect(i).collidepoint(x, y):
                tap_flash((2, 10 + i)); press_seq(ks); return
    elif v == 4:
        for i in range(2):
            if tab_rect(i).collidepoint(x, y):
                ui["tab4"] = i; ui["page4"] = 0; return
        if y > TOP + TAB_H:
            ui["page4"] += 1
    elif v == 5:
        for i, b in enumerate(SRV_BTNS + PIE_BTNS):
            if m5_rect(i).collidepoint(x, y):
                tap_flash((5, i)); press_seq([b[1]]); return
    elif v == 6:
        for i, b in enumerate(COMBAT_BTNS):
            if c6_rect(i).collidepoint(x, y):
                tap_flash((6, i)); press_seq([b[1]]); return
    elif v == 9:
        for i, (txt, key, grp) in enumerate(FIGHTER_BTNS):
            if c9_rect(i).collidepoint(x, y):
                tap_flash((9, i)); press_seq([key])
                if grp:
                    ui["orders"][grp] = i
                    if key == "KP0":
                        ui["orders"].pop("a", None)
                return
    elif v == 7:
        for i in range(2):
            if grid(i, 2, 1).collidepoint(x, y):
                tap_flash((7, i)); ui["view"] = 71 + i; return
    elif v == 72:
        tap_orrery(x, y)
    elif v == 12:
        for i in range(4):
            if grid(i, 2, 2).collidepoint(x, y):
                tap_flash((12, i)); ui["view"] = 121 + i; return
    elif v == 124:
        for i, k in enumerate(["auto", "alerts", "sound", "theme"]):
            if grid(i, 2, 2).collidepoint(x, y):
                tap_flash((124, i))
                if k == "theme":
                    cfg["theme"] = (cfg["theme"] + 1) % len(THEMES); apply_theme()
                else:
                    cfg[k] = not cfg[k]
                    if k == "sound" and cfg[k]: play("ok")
                save_cfg(); return
    elif v == 121:
        if y > TOP:
            ui["pause"] = not ui["pause"]
    elif v == 122:
        tap_stream(x, y)

# ---------- tactil ----------
def touch_loop():
    from evdev import InputDevice, list_devices, ecodes
    dev = None
    for p in list_devices():
        d = InputDevice(p)
        if 'ADS7846' in d.name or 'touch' in d.name.lower():
            dev = d; break
    if not dev:
        print("No encuentro el tactil"); return
    ax, ay = dev.absinfo(ecodes.ABS_X), dev.absinfo(ecodes.ABS_Y)
    rx = ry = 0; down = False; pending = False
    for ev in dev.read_loop():
        if ev.type == ecodes.EV_ABS:
            if ev.code == ecodes.ABS_X: rx = ev.value
            elif ev.code == ecodes.ABS_Y: ry = ev.value
        elif ev.type == ecodes.EV_KEY and ev.code == ecodes.BTN_TOUCH:
            down = ev.value == 1
            if down: pending = True
        elif ev.type == ecodes.EV_SYN and pending and down:
            pending = False
            x = (rx - ax.min) / max(1, ax.max - ax.min)
            y = (ry - ay.min) / max(1, ay.max - ay.min)
            if SWAP_XY: x, y = y, x
            if INV_X: x = 1 - x
            if INV_Y: y = 1 - y
            on_tap(int(x * W), int(y * H))

# ---------- utilidades de dibujo ----------
F = {}

def fit(font, text, width):
    text = str(text)
    if font.size(text)[0] <= width:
        return text
    while text and font.size(text + "...")[0] > width:
        text = text[:-1]
    return text + "..."

def put(surf, font, text, pos, col=None, width=None, anchor="topleft"):
    col = col or ORANGE
    if width:
        text = fit(font, text, width)
    t = font.render(str(text), True, col)
    surf.blit(t, t.get_rect(**{anchor: pos}))
    return t.get_width()

def draw_button(surf, r, txt, sub, f_txt, filled=False, lit=False, dim=False, compact=False):
    if filled or lit:
        pygame.draw.rect(surf, WHITE if lit else ORANGE, r, border_radius=6)
        col = BLACK
    else:
        pygame.draw.rect(surf, DIM if dim else ORANGE, r, 2, border_radius=6)
        col = DIM if dim else ORANGE
    up, down = (7, 12) if compact else (8, 18)
    put(surf, f_txt, txt, (r.centerx, r.centery - (up if sub else 0)), col, r.w - 8, "center")
    if sub:
        put(surf, F["small"], sub, (r.centerx, r.centery + down), col, r.w - 8, "center")

def fmt_time(sec):
    if sec <= 0: return "CADUCADA"
    d, h, m = int(sec // 86400), int(sec % 86400 // 3600), int(sec % 3600 // 60)
    return f"{d}d {h}h" if d else (f"{h}h {m:02d}m" if h else f"{m}m")

def star_ok(cls):
    return (cls or "").split("_")[0] in SCOOPABLE

# ---------- vistas ----------
def view_menu(surf, d, flags, now):
    for i in range(12):
        name = MENU.get(i + 1)
        draw_button(surf, grid(i), str(i + 1), name or "vacío", F["num"],
                    lit=flash.get((0, i), 0) > now, dim=name is None)

def view_mandos(surf, d, flags, now):
    for i, (txt, key, bit) in enumerate(BUTTONS):
        draw_button(surf, grid(i), txt, key.upper(), F["btn"],
                    filled=bit is not None and bool(flags & (1 << bit)), lit=flash.get((1, i), 0) > now)

def view_pips(surf, d, flags, now):
    pips = (d or {}).get("Pips") or [0, 0, 0]
    for i, (name, key) in enumerate(PIP_COLS):
        r = pip_rect(i)
        lit = flash.get((2, i), 0) > now
        pygame.draw.rect(surf, WHITE if lit else ORANGE, r, 2, border_radius=6)
        put(surf, F["btn"], name, (r.centerx, r.y + 14), ORANGE, anchor="center")
        val = pips[i] if i < len(pips) else 0
        bw, bh, gap = r.w - 40, 24, 6
        for p in range(4):                       # 4 pips, de abajo arriba
            br = pygame.Rect(r.x + 20, r.bottom - 30 - (p + 1) * (bh + gap), bw, bh)
            fill = max(0, min(2, val - p * 2))   # medios pips
            pygame.draw.rect(surf, DIM, br, 1)
            if fill:
                pygame.draw.rect(surf, BLUE, (br.x + 2, br.y + 2, (br.w - 4) * fill // 2, br.h - 4))
        put(surf, F["small"], f"{val / 2:g} / 4   [{key.upper()}]", (r.centerx, r.bottom - 14), ORANGE, anchor="center")
    for i, (name, ks) in enumerate(PIP_PRESETS):
        draw_button(surf, preset_rect(i), name, ks[0].upper() if len(ks) == 1 else None, F["btn"],
                    lit=flash.get((2, 10 + i), 0) > now)

def view_nav(surf, d, flags, now):
    nav = (d or {}).get("nav") or {}
    route = (d or {}).get("route") or []
    y = TOP + 6
    tgt = nav.get("target")
    if not tgt and not route:
        put(surf, F["big"], "Sin ruta trazada", (W // 2, (H + TOP) // 2), DIM, anchor="center")
        return
    put(surf, F["small"], "SIGUIENTE SALTO", (8, y), DIM); y += 16
    put(surf, F["big"], (tgt or route[0][0]).upper(), (8, y), ORANGE, W - 16); y += 30
    cls = nav.get("star") or (route[0][1] if route else "")
    ok = star_ok(cls)
    x = 8 + put(surf, F["btn"], f"Estrella {cls or '?'}   ", (8, y), ORANGE)
    put(surf, F["btn"], "RECOGIBLE" if ok else "NO RECOGIBLE", (x, y), GREEN if ok else RED); y += 26
    jumps = nav.get("jumps")
    last = nav.get("last")
    put(surf, F["btn"], f"Saltos restantes: {jumps if jumps is not None else len(route)}", (8, y))
    if last:
        put(surf, F["btn"], f"Último salto: {last:.1f} al", (W - 8, y), ORANGE, anchor="topright")
    y += 30
    pygame.draw.line(surf, DIM, (8, y - 4), (W - 8, y - 4))
    if route:
        put(surf, F["small"], f"RUTA  -  destino: {route[-1][0]}", (8, y), DIM, W - 16); y += 18
        for n, (name, c) in enumerate(route[:5]):
            col = ORANGE if star_ok(c) else RED
            put(surf, F["btn"], f"{n + 1}. {name}", (8, y), col, W - 90)
            put(surf, F["btn"], c or "?", (W - 8, y), col, anchor="topright")
            y += 22

def view_carga(surf, d, flags, now):
    cargo = (d or {}).get("cargo") or []
    miss = (d or {}).get("missions") or []
    used = sum(c for _, c in cargo)
    cap = (d or {}).get("cargocap")
    tabs = [f"BODEGA {used}/{cap if cap is not None else '?'} t", f"MISIONES ({len(miss)})"]
    for i, t in enumerate(tabs):
        draw_button(surf, tab_rect(i), t, None, F["btn"], filled=ui["tab4"] == i)
    top = TOP + TAB_H + 4
    if ui["tab4"] == 0:
        rows, rh = [(n, c) for n, c in cargo], 24
        if not rows:
            put(surf, F["btn"], "Bodega vacía", (W // 2, (H + top) // 2), DIM, anchor="center"); return
    else:
        rows, rh = miss, 42
        if not rows:
            put(surf, F["btn"], "Sin misiones activas", (W // 2, (H + top) // 2), DIM, anchor="center"); return
    per = max(1, (H - top - 18) // rh)
    pages = (len(rows) + per - 1) // per
    pg = ui["page4"] % pages
    y = top
    for row in rows[pg * per:(pg + 1) * per]:
        if ui["tab4"] == 0:
            name, cnt = row
            put(surf, F["btn"], name, (10, y), ORANGE, W - 90)
            put(surf, F["btn"], f"{cnt} t", (W - 10, y), ORANGE, anchor="topright")
        else:
            name, dest, exp = row
            put(surf, F["btn"], name, (10, y), ORANGE, W - 20)
            left = exp - time.time() if exp else 0
            put(surf, F["small"], f"-> {dest or '?'}", (10, y + 20), DIM, W - 110)
            put(surf, F["small"], fmt_time(left) if exp else "", (W - 10, y + 20),
                RED if exp and left < 3600 else DIM, anchor="topright")
        y += rh
    if pages > 1:
        put(surf, F["small"], f"pág {pg + 1}/{pages}  (toca para pasar)", (W // 2, H - 10), DIM, anchor="center")

def view_srv(surf, d, flags, now):
    flags2 = (d or {}).get("Flags2", 0)
    in_srv, on_foot = bool(flags & (1 << 26)), bool(flags2 & 1)
    for label, cx, act in (("SRV", W // 4, in_srv), ("A PIE", 3 * W // 4, on_foot)):
        put(surf, F["small"], label + ("  (ACTIVO)" if act else ""), (cx, TOP + 9), GREEN if act else DIM, anchor="center")
    pygame.draw.line(surf, DIM, (W // 2, TOP + 2), (W // 2, H - 4))
    for i, (txt, key, bit) in enumerate(SRV_BTNS + PIE_BTNS):
        dim = (i < 6 and on_foot) or (i >= 6 and in_srv)
        draw_button(surf, m5_rect(i), txt, key.upper(), F["btn"], dim=dim,
                    filled=bit is not None and in_srv and i < 6 and bool(flags & (1 << bit)),
                    lit=flash.get((5, i), 0) > now)

def bar(surf, x, y, w, label, pct, col):
    put(surf, F["small"], label, (x, y + 1), DIM)
    bx = pygame.Rect(x + 52, y, w - 52, 14)
    pygame.draw.rect(surf, DIM, bx, 1)
    if pct is not None:
        pygame.draw.rect(surf, col, (bx.x + 2, bx.y + 2, int((bx.w - 4) * max(0, min(100, pct)) / 100), bx.h - 4))
        put(surf, F["small"], f"{pct:.0f}%", (bx.right - 4, y + 1), WHITE, anchor="topright")

def view_combat(surf, d, flags, now):
    t = (d or {}).get("target")
    card = pygame.Rect(4, TOP + 2, W - 8, CARD6 - TOP - 4)
    pygame.draw.rect(surf, DIM, card, 1, border_radius=6)
    if not t:
        put(surf, F["big"], "SIN OBJETIVO", card.center, DIM, anchor="center")
    else:
        x, y = card.x + 8, card.y + 6
        cmdr = t.get("cmdr")
        put(surf, F["big"], (t.get("ship") or "?").upper(), (x, y), ORANGE, card.w - 140)
        put(surf, F["small"], f"ESCANEO {t.get('scan', 0)}/3", (card.right - 8, y + 4), DIM, anchor="topright")
        y += 28
        if t.get("pilot"):
            w_ = put(surf, F["btn"], t["pilot"], (x, y), BLUE if cmdr else ORANGE, card.w - 170)
            if cmdr:
                put(surf, F["small"], " COMANDANTE", (x + w_ + 4, y + 4), BLUE)
            put(surf, F["small"], t.get("rank") or "", (card.right - 8, y + 4), DIM, anchor="topright")
        y += 24
        half = (card.w - 24) // 2
        bar(surf, x, y, half, "ESCUDO", t.get("shield"), BLUE)
        bar(surf, x + half + 8, y, half, "CASCO", t.get("hull"), ORANGE)
        y += 20
        legal = t.get("legal") or ""
        wanted = legal.lower() == "wanted"
        put(surf, F["small"], ("BUSCADO" if wanted else legal.upper()) or "-", (x, y), RED if wanted else GREEN)
        if t.get("bounty"):
            put(surf, F["small"], f"RECOMPENSA {t['bounty']:,} cr".replace(",", "."), (x + 90, y), RED)
        if t.get("subsys"):
            sh = t.get("subhealth")
            put(surf, F["small"], f"{t['subsys']}" + (f"  {sh:.0f}%" if sh is not None else ""),
                (card.right - 8, y), ORANGE, card.w // 2 - 20, anchor="topright")
    for i, (txt, key) in enumerate(COMBAT_BTNS):
        draw_button(surf, c6_rect(i), txt, key.upper(), F["btn"], lit=flash.get((6, i), 0) > now, compact=True)

FIGHTER_STATE = {"hangar": ("EN EL HANGAR", DIM), "out": ("LANZADO", GREEN), "dead": ("DESTRUIDO - RECONSTRUYENDO", RED),
                 "ready": ("RECONSTRUIDO - LISTO", ORANGE)}

def view_fighter(surf, d, flags, now):
    f = (d or {}).get("fighter") or {}
    card = pygame.Rect(4, TOP + 2, W - 8, CARD9 - TOP - 4)
    pygame.draw.rect(surf, DIM, card, 1, border_radius=6)
    txt, col = FIGHTER_STATE.get(f.get("state"), ("SIN DATOS DEL CAZA", DIM))
    if flags & (1 << 25):
        txt, col = "PILOTANDO EL CAZA", BLUE
    put(surf, F["small"], "CAZA", (card.x + 8, card.y + 6), DIM)
    put(surf, F["big"], txt, (card.x + 8, card.y + 22), col, card.w - 16)
    who = f.get("pilot")
    if who and f.get("state") == "out":
        put(surf, F["small"], f"Piloto: {who}", (card.x + 8, card.y + 50), ORANGE)
    orders = ui["orders"]
    for i, (t_, key, grp) in enumerate(FIGHTER_BTNS):
        draw_button(surf, c9_rect(i), t_, key.replace("KP", "NUM "), F["btn"],
                    filled=grp is not None and orders.get(grp) == i, lit=flash.get((9, i), 0) > now)

def view_log(surf, d, flags, now):
    with lock:
        log = list(state["log"])
    f = F["mono"]
    cw, lh = f.size("M")[0], f.get_linesize()
    ncols, nrows = (W - 8) // cw, (H - TOP - 4) // lh
    rows = []
    for line in reversed(log):
        rows[:0] = [line[i:i + ncols] for i in range(0, len(line), ncols)] or [""]
        if len(rows) >= nrows:
            break
    for j, r in enumerate(rows[-nrows:]):
        surf.blit(f.render(r, True, ORANGE), (4, TOP + 2 + j * lh))
    if ui["pause"]:
        t = F["btn"].render(" PAUSA ", True, BLACK, WHITE)
        surf.blit(t, (W - t.get_width() - 6, TOP + 4))
    if not log:
        put(surf, F["btn"], "Esperando eventos del journal...", (8, TOP + 10), DIM)

# ---------- formatos ----------
def cr(v):
    v = v or 0
    a = abs(v)
    if a >= 1e9: return f"{v / 1e9:.2f} mil M".replace(".", ",")
    if a >= 1e6: return f"{v / 1e6:.1f} M".replace(".", ",")
    if a >= 1e3: return f"{v / 1e3:.0f} k"
    return f"{v:.0f}"

def dur(sec):
    sec = max(0, int(sec)); return f"{sec // 3600}h {sec % 3600 // 60:02d}m"

# ---------- 7 exploracion ----------
def view_explo(surf, d, flags, now):
    ex = (d or {}).get("explo") or {}
    y = TOP + 6
    total, scanned = ex.get("total"), ex.get("scanned", 0)
    put(surf, F["small"], "CUERPOS ESCANEADOS", (8, y), DIM)
    put(surf, F["small"], "MAPEADOS", (W - 8, y), DIM, anchor="topright")
    y += 14
    done = total is not None and scanned >= total
    put(surf, F["big"], f"{scanned} / {total if total is not None else '?'}", (8, y), GREEN if done else ORANGE)
    put(surf, F["big"], str(ex.get("mapped", 0)), (W - 8, y), ORANGE, anchor="topright")
    fss = ex.get("fss")
    bx = pygame.Rect(150, y + 6, 200, 14)
    pygame.draw.rect(surf, DIM, bx, 1)
    if fss is not None:
        pygame.draw.rect(surf, BLUE, (bx.x + 2, bx.y + 2, int((bx.w - 4) * fss), bx.h - 4))
        put(surf, F["small"], f"FSS {fss * 100:.0f}%", (bx.centerx, bx.y + 1), WHITE, anchor="midtop")
    else:
        put(surf, F["small"], "SIN ESCANEO FSS", (bx.centerx, bx.y + 1), DIM, anchor="midtop")
    y += 30
    pygame.draw.line(surf, DIM, (8, y), (W - 8, y)); y += 4
    top = ex.get("top") or []
    sysname = ex.get("system") or ""
    if not top:
        put(surf, F["btn"], "Nada destacable escaneado aún", (W // 2, y + 60), DIM, anchor="center")
    for name, cls, dist, first, mapped, val in top[:7]:
        short = name[len(sysname):].strip() if name.startswith(sysname) else name
        put(surf, F["btn"], short or name, (8, y), ORANGE, 70)
        put(surf, F["small"], cls, (80, y + 4), ORANGE, 150)
        put(surf, F["small"], f"{dist:,} ls".replace(",", "."), (300, y + 4), DIM, anchor="topright")
        put(surf, F["small"], "1º" if first else "", (318, y + 4), GREEN)
        put(surf, F["small"], "MAPEADO" if mapped else "SIN MAPEAR", (342, y + 4), BLUE if mapped else DIM)
        put(surf, F["small"], cr(val), (W - 8, y + 4), ORANGE, anchor="topright")
        y += 21
    pygame.draw.line(surf, DIM, (8, H - 24), (W - 8, H - 24))
    put(surf, F["btn"], f"DATOS SIN VENDER  ~ {cr(ex.get('unsold'))} cr", (8, H - 20), ORANGE)
    put(surf, F["small"], f"{ex.get('unsold_n', 0)} cuerpos", (W - 8, H - 16), DIM, anchor="topright")

# ---------- 8 estacion ----------
STARPORTS = {"Coriolis", "Orbis", "Ocellus", "Bernal", "AsteroidBase", "Dodec"}
ST_TYPE = {"Coriolis": "Estación Coriolis", "Orbis": "Estación Orbis", "Ocellus": "Estación Ocellus",
           "Bernal": "Estación Ocellus", "AsteroidBase": "Base asteroide", "Outpost": "Puesto avanzado",
           "FleetCarrier": "Portanaves", "CraterOutpost": "Puesto planetario", "CraterPort": "Puerto planetario",
           "OnFootSettlement": "Asentamiento", "Dodec": "Estación Dodec", "MegaShip": "Mega nave"}
SERVICES = [("refuel", "COMBUSTIBLE"), ("repair", "REPARAR"), ("rearm", "REARMAR"), ("commodities", "MERCADO"),
            ("shipyard", "ASTILLERO"), ("outfitting", "EQUIPAMIENTO"), ("blackmarket", "MERCADO NEGRO"),
            ("facilitator", "FACTORES INT."), ("materialtrader", "MATERIALES"), ("techBroker", "TECNOLOGÍA"),
            ("engineer", "INGENIERO"), ("vistagenomics", "VISTA GENOMICS"), ("searchrescue", "RESCATE"),
            ("missions", "MISIONES"), ("tuning", "PERSONALIZAR")]
STATUS_COL = {"CONCEDIDO": GREEN, "ATRACADO": BLUE, "DENEGADO": RED, "SOLICITADO": ORANGE}

def pad_clock(pad):
    """Hora aproximada (1-12) de la plataforma, mirando desde la ranura de entrada."""
    sector = int((pad - 1) * 12 / 45)
    return (6 + sector - 1) % 12 + 1

def view_station(surf, d, flags, now):
    st = (d or {}).get("station") or {}
    if not st.get("status"):
        put(surf, F["big"], "Sin solicitud de atraque", (W // 2, (H + TOP) // 2), DIM, anchor="center")
        return
    pad, stype = st.get("pad"), st.get("type")
    cx, cy, rad = 118, (H + TOP) // 2 + 4, 108
    x0 = 248
    if pad and stype in STARPORTS:
        import math
        hour = pad_clock(pad)
        for h in range(12):
            a0, a1 = math.radians(h * 30 - 105), math.radians(h * 30 - 75)
            pts = [(cx, cy)] + [(cx + rad * math.cos(a0 + (a1 - a0) * t / 6), cy + rad * math.sin(a0 + (a1 - a0) * t / 6)) for t in range(7)]
            on = (h or 12) == hour
            pygame.draw.polygon(surf, ORANGE if on else BLACK, pts)
            pygame.draw.polygon(surf, DIM, pts, 1)
        pygame.draw.rect(surf, BLACK, (cx - 30, cy - 9, 60, 18))
        pygame.draw.rect(surf, GREEN, (cx - 30, cy - 9, 60, 18), 2)
        put(surf, F["small"], "ENTRADA", (cx, cy), GREEN, anchor="center")
        put(surf, F["small"], "12", (cx, cy - rad - 1), DIM, anchor="midbottom")
        put(surf, F["small"], "6", (cx, cy + rad + 1), DIM, anchor="midtop")
    elif pad:
        put(surf, F["num"], str(pad), (cx, cy), ORANGE, anchor="center")
        put(surf, F["small"], "PLATAFORMA", (cx, cy - 34), DIM, anchor="center")
    else:
        x0 = 8
    y = TOP + 6
    put(surf, F["big"], (st.get("name") or "?").upper(), (x0, y), ORANGE, W - x0 - 8); y += 26
    put(surf, F["small"], ST_TYPE.get(stype, stype or ""), (x0, y), DIM, W - x0 - 8); y += 18
    status = st.get("status")
    put(surf, F["btn"], status, (x0, y), STATUS_COL.get(status, DIM)); y += 22
    if status == "DENEGADO" and st.get("reason"):
        put(surf, F["small"], st["reason"], (x0, y), RED, W - x0 - 8); y += 16
    if pad:
        put(surf, F["big"], f"PLATAFORMA {pad}", (x0, y), WHITE); y += 26
        if stype in STARPORTS:
            put(surf, F["small"], f"a las {pad_clock(pad)} (aprox.)", (x0, y), ORANGE); y += 18
    if st.get("dist"):
        put(surf, F["small"], f"{st['dist']:,.0f} ls de la estrella".replace(",", "."), (x0, y), DIM); y += 16
    if st.get("faction"):
        put(surf, F["small"], st["faction"], (x0, y), DIM, W - x0 - 8); y += 18
    srv = set(st.get("services") or [])
    tags = [t for k, t in SERVICES if k in srv]
    tx = x0
    for t in tags:
        w_ = F["small"].size(t)[0] + 10
        if tx + w_ > W - 4:
            tx = x0; y += 18
        if y > H - 16: break
        pygame.draw.rect(surf, DIM, (tx, y, w_ - 4, 16), 1, border_radius=3)
        put(surf, F["small"], t, (tx + 3, y + 2), ORANGE)
        tx += w_

# ---------- 10 mineria ----------
def view_mining(surf, d, flags, now):
    m = (d or {}).get("mining") or {}
    last = m.get("last")
    y = TOP + 6
    if last and last.get("motherlode"):
        blink = int(now * 2) % 2
        r = pygame.Rect(4, y - 2, W - 8, 30)
        pygame.draw.rect(surf, RED if blink else BLACK, r, border_radius=6)
        pygame.draw.rect(surf, RED, r, 2, border_radius=6)
        put(surf, F["big"], f"NÚCLEO: {last['motherlode'].upper()}", r.center, WHITE, anchor="center")
        y += 34
    put(surf, F["small"], "ÚLTIMO PROSPECTOR", (8, y), DIM)
    put(surf, F["small"], "REFINADO (SESIÓN)", (318, y), DIM); y += 14
    yy = y
    if not last:
        put(surf, F["btn"], "Lanza un prospector", (8, y + 4), DIM)
    else:
        put(surf, F["btn"], f"Contenido: {last.get('content') or '?'}", (8, y), ORANGE); y += 22
        if last.get("remaining") is not None:
            put(surf, F["small"], f"Restante {last['remaining']:.0f}%", (8, y), DIM); y += 16
        for name, pct in last.get("mats") or []:
            put(surf, F["small"], name, (8, y + 1), ORANGE, 120)
            bx = pygame.Rect(132, y, 140, 14)
            pygame.draw.rect(surf, DIM, bx, 1)
            pygame.draw.rect(surf, BLUE, (bx.x + 2, bx.y + 2, int((bx.w - 4) * min(pct, 100) / 100), bx.h - 4))
            put(surf, F["small"], f"{pct:.1f}%", (bx.right + 34, y + 1), WHITE, anchor="topright")
            y += 19
    pygame.draw.line(surf, DIM, (310, yy - 14), (310, H - 30))
    ref = sorted((m.get("refined") or {}).items(), key=lambda kv: -kv[1])
    if not ref:
        put(surf, F["small"], "nada aún", (318, yy + 4), DIM)
    for name, n in ref[:8]:
        put(surf, F["small"], name, (318, yy + 2), ORANGE, 110)
        put(surf, F["btn"], f"{n} t", (W - 8, yy), ORANGE, anchor="topright"); yy += 20
    pygame.draw.line(surf, DIM, (8, H - 26), (W - 8, H - 26))
    lim = m.get("limpets")
    put(surf, F["btn"], f"LIMPETS: {lim if lim is not None else '?'}", (8, H - 22), RED if lim == 0 else ORANGE)
    put(surf, F["small"], f"Prospectores {m.get('prospectors', 0)}   ·   Recolectores {m.get('collectors', 0)}",
        (W - 8, H - 18), DIM, anchor="topright")

# ---------- 11 sesion ----------
def view_session(surf, d, flags, now):
    s_ = (d or {}).get("sess") or {}
    if not s_:
        put(surf, F["btn"], "Sin sesión (carga la partida)", (W // 2, (H + TOP) // 2), DIM, anchor="center"); return
    e = s_.get("earn") or {}
    left = [("TIEMPO", dur(time.time() - (s_.get("start") or time.time()))), ("SALTOS", str(s_.get("jumps", 0))),
            ("AÑOS LUZ", f"{s_.get('ly', 0):,.0f}".replace(",", ".")), ("DERRIBOS", str(s_.get("kills", 0))),
            ("MUERTES", str(s_.get("deaths", 0)))]
    right = [("RECOMPENSAS", e.get("bounty")), ("COMERCIO", e.get("trade")), ("EXPLORACIÓN", e.get("explo")),
             ("MISIONES", e.get("missions")), ("EXOBIOLOGÍA", e.get("bio"))]
    y = TOP + 6
    for (l1, v1), (l2, v2) in zip(left, right):
        put(surf, F["small"], l1, (8, y + 4), DIM)
        put(surf, F["big"], v1, (226, y), RED if l1 == "MUERTES" and v1 != "0" else ORANGE, anchor="topright")
        put(surf, F["small"], l2, (246, y + 4), DIM)
        put(surf, F["big"], cr(v2), (W - 8, y), ORANGE, anchor="topright")
        y += 32
    pygame.draw.line(surf, DIM, (236, TOP + 4), (236, y - 4))
    pygame.draw.line(surf, DIM, (8, y), (W - 8, y)); y += 6
    bal, c0 = (d or {}).get("balance"), s_.get("credits0")
    if bal is not None:
        put(surf, F["small"], "SALDO", (8, y + 6), DIM)
        put(surf, F["big"], f"{bal:,.0f} cr".replace(",", "."), (60, y), ORANGE)
        if c0 is not None:
            diff = bal - c0
            put(surf, F["big"], ("+" if diff >= 0 else "") + cr(diff), (W - 8, y), GREEN if diff >= 0 else RED, anchor="topright")

# ---------- 12 submenu ----------
def view_sub7(surf, d, flags, now):
    for i, (n, name) in enumerate([("1", "EXPLORACIÓN"), ("2", "SISTEMA")]):
        draw_button(surf, grid(i, 2, 1), n, name, F["num"], lit=flash.get((7, i), 0) > now)

# ---------- 7.2 sistema en movimiento (planetario) ----------
SPEEDS = [(1, "TIEMPO REAL"), (60, "1 min / s"), (3600, "1 hora / s"), (86400, "1 día / s"),
          (864000, "10 días / s"), (8640000, "100 días / s"), (31536000, "1 año / s")]
orr = {"speed": 3, "paused": False, "t": None, "last": None, "focus": None, "sel": None, "sys": None,
       "scale": None, "hits": []}
OR_AREA = pygame.Rect(0, TOP, 332, H - TOP)
OR_X = 336                                   # columna derecha

def or_btn(name):
    w2 = (W - OR_X - 6) // 2
    return {"menos": pygame.Rect(OR_X, 176, w2, 32), "mas": pygame.Rect(OR_X + w2 + 4, 176, w2, 32),
            "pausa": pygame.Rect(OR_X, 226, W - OR_X - 4, 28), "zoom": pygame.Rect(OR_X, 258, W - OR_X - 4, 28),
            "ahora": pygame.Rect(OR_X, 290, W - OR_X - 4, 28)}[name]

STAR_COL = {"O": (150, 180, 255), "B": (170, 200, 255), "A": (230, 235, 255), "F": (255, 250, 215), "G": (255, 228, 110),
            "K": (255, 165, 70), "M": (255, 105, 70), "L": (220, 70, 60), "T": (170, 60, 90), "Y": (120, 50, 80),
            "N": (210, 225, 255), "H": (90, 90, 90), "D": (235, 240, 255)}
PLANET_COL = {"Earthlike body": (60, 190, 150), "Water world": (60, 120, 255), "Ammonia world": (190, 160, 90),
              "Icy body": (190, 220, 240), "Rocky body": (150, 130, 110), "Rocky ice body": (170, 170, 185),
              "Metal rich body": (205, 120, 60), "High metal content body": (180, 140, 100)}

def bcol(o):
    st = o.get("star")
    if st:
        return STAR_COL.get("H" if st.startswith("Super") else st[0], (240, 240, 240))
    pc = o.get("pc") or ""
    return (210, 170, 120) if "gas giant" in pc.lower() else PLANET_COL.get(pc, (160, 160, 160))

def bsize(o):
    if o.get("star"):
        return 4 if o["star"][0] in "DNH" else 8
    return 5 if "gas giant" in (o.get("pc") or "").lower() else (4 if o.get("r", 0) > 5000 else 3)

def kep(o, t=None, E=None):
    """Posicion (x, y) en metros respecto a su padre. Con E dibuja la orbita completa."""
    a, P = o.get("a"), o.get("P")
    if not a or not P:
        return 0.0, 0.0
    e = min(o.get("e", 0), 0.99)
    if E is None:
        M = math.radians(o.get("M", 0)) + 2 * math.pi * ((t - (o.get("t") or t)) / P)
        E = M
        for _ in range(8):
            E -= (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
    xv, yv = a * (math.cos(E) - e), a * math.sqrt(1 - e * e) * math.sin(E)
    w, i, W_ = math.radians(o.get("w", 0)), math.radians(o.get("i", 0)), math.radians(o.get("W", 0))
    xw, yw = xv * math.cos(w) - yv * math.sin(w), xv * math.sin(w) + yv * math.cos(w)
    return (xw * math.cos(W_) - yw * math.cos(i) * math.sin(W_), xw * math.sin(W_) + yw * math.cos(i) * math.cos(W_))

def build_tree(orbits):
    nodes, parent, ntype = {}, {}, {}
    for o in orbits:
        if o.get("id") is None:
            continue
        nodes[o["id"]] = o
        chain = o.get("par") or []
        if chain:
            parent[o["id"]] = chain[0][1]
            for (k1, v1), (k2, v2) in zip(chain, chain[1:]):
                parent.setdefault(v1, v2)
            for k, v in chain:
                ntype.setdefault(v, k)
        ntype[o["id"]] = "Star" if o.get("star") else "Planet" if o.get("pc") else ntype.get(o["id"], "Null")
    ids = set(nodes) | set(parent) | set(parent.values())
    roots = [i for i in ids if i not in parent]
    root = 0 if 0 in roots else (min(roots) if roots else None)
    return nodes, parent, ntype, root, ids

def classify(F, tree):
    nodes, parent, ntype, root, ids = tree
    local, moons = [], {}
    for n in ids:
        if n == F:
            continue
        chain, p, ok = [], parent.get(n), False
        while p is not None:
            if p == F:
                ok = True; break
            chain.append(p); p = parent.get(p)
        if not ok:
            continue
        planets = [c for c in chain if ntype.get(c) == "Planet"]
        if planets:
            moons.setdefault(planets[-1], []).append(n)
        else:
            local.append(n)
    return local, moons

def view_orrery(surf, d, flags, now):
    orbits = (d or {}).get("orbits") or []
    system = ((d or {}).get("explo") or {}).get("system")
    if system != orr["sys"]:
        orr.update(sys=system, focus=None, sel=None, scale=None)
    if orr["t"] is None:
        orr["t"] = now
    if orr["last"] is not None and not orr["paused"]:
        orr["t"] += (now - orr["last"]) * SPEEDS[orr["speed"]][0]
    orr["last"] = now
    t = orr["t"]
    pygame.draw.line(surf, DIM, (OR_AREA.right + 1, TOP + 2), (OR_AREA.right + 1, H - 4))
    draw_or_side(surf, d, orbits)
    tree = build_tree(orbits)
    nodes, parent, ntype, root, ids = tree
    if root is None or not nodes:
        put(surf, F["btn"], "Escanea el sistema (FSS)", (OR_AREA.centerx, OR_AREA.centery - 10), DIM, anchor="center")
        put(surf, F["small"], "para ver sus órbitas", (OR_AREA.centerx, OR_AREA.centery + 12), DIM, anchor="center")
        orr["hits"] = []
        return
    F_ = orr["focus"] if orr["focus"] in ids else root
    memo = {}
    def apos(i):
        if i in memo: return memo[i]
        p = parent.get(i)
        bx, by = apos(p) if p is not None else (0.0, 0.0)
        ox, oy = kep(nodes[i], t) if i in nodes else (0.0, 0.0)
        memo[i] = (bx + ox, by + oy)
        return memo[i]
    local, moons = classify(F_, tree)
    fx, fy = apos(F_)
    cx, cy = OR_AREA.center
    rmax = min(OR_AREA.w, OR_AREA.h) / 2 - 14
    # escala logaritmica (fija mientras no cambie el foco o los cuerpos)
    key = (F_, len(nodes))
    if not orr["scale"] or orr["scale"][0] != key:
        ds = [math.hypot(*[a - b for a, b in zip(apos(n), (fx, fy))]) for n in local]
        ds += [nodes[n].get("a", 0) * (1 + nodes[n].get("e", 0)) for n in local if n in nodes and parent.get(n) == F_]
        ds = [x for x in ds if x > 0]
        dmax = max(ds) if ds else 1.0
        d0 = max(min(ds) * 0.4, dmax * 1e-5) if ds else 1.0
        orr["scale"] = (key, dmax, d0)
    _, dmax, d0 = orr["scale"]
    norm = math.log1p(dmax / d0)
    def scr(px, py):
        dx, dy = px - fx, py - fy
        dd = math.hypot(dx, dy)
        if dd <= 0:
            return cx, cy
        r = rmax * min(1.05, math.log1p(dd / d0) / norm)
        return cx + dx / dd * r, cy - dy / dd * r
    surf.set_clip(OR_AREA)
    # orbitas
    for n in local:
        o = nodes.get(n)
        if not o or not o.get("a"):
            continue
        bx, by = apos(parent.get(n))
        pts = [scr(bx + x, by + y) for x, y in (kep(o, E=k * 2 * math.pi / 48) for k in range(49))]
        pygame.draw.lines(surf, (60, 40, 10) if ntype.get(n) == "Null" else DIM, False, pts, 1)
    # cuerpos
    hits = []
    me = (d or {}).get("body")
    def body(n, x, y, small=False):
        o = nodes.get(n)
        if not o or ntype.get(n) == "Null":
            return
        r = 2 if small else bsize(o)
        col = bcol(o)
        pygame.draw.circle(surf, col, (int(x), int(y)), r)
        if o.get("rings") and not small:
            pygame.draw.ellipse(surf, (200, 180, 140), (x - r - 4, y - 2, 2 * r + 8, 4), 1)
        if o.get("star") and o["star"][0] in "NH":
            pygame.draw.circle(surf, col, (int(x), int(y)), r + 3, 1)
        if n == orr["sel"]:
            pygame.draw.circle(surf, WHITE, (int(x), int(y)), r + 5, 1)
        if me and o.get("name") == me:
            pygame.draw.circle(surf, GREEN, (int(x), int(y)), r + 8, 1)
            put(surf, F["small"], "TÚ", (x + r + 8, y - 16), GREEN)
        if not small and len(local) < 30:
            nm = o.get("name", "")
            short = nm[len(system):].strip() if system and nm.startswith(system) else nm
            put(surf, F["small"], short or nm, (x + r + 3, y + 1), DIM, 60)
        hits.append((n, x, y))
    if ntype.get(F_) != "Null":
        body(F_, cx, cy)
    else:
        pygame.draw.line(surf, DIM, (cx - 4, cy), (cx + 4, cy)); pygame.draw.line(surf, DIM, (cx, cy - 4), (cx, cy + 4))
    for n in local:
        x, y = scr(*apos(n))
        body(n, x, y)
        ms = moons.get(n)
        if ms:
            ax, ay = apos(n)
            rel = [(m, apos(m)[0] - ax, apos(m)[1] - ay) for m in ms]
            dm = [math.hypot(dx, dy) for _, dx, dy in rel]
            mmax, mmin = max(dm + [1]), min([v for v in dm if v > 0] + [1])
            for (m, dx, dy), dd in zip(rel, dm):
                rr = 9 + 12 * math.log1p(dd / (mmin * 0.5)) / math.log1p(mmax / (mmin * 0.5)) if dd > 0 else 9
                pygame.draw.circle(surf, (50, 35, 10), (int(x), int(y)), int(rr), 1)
                body(m, x + dx / (dd or 1) * rr, y - dy / (dd or 1) * rr, small=True)
    surf.set_clip(None)
    orr["hits"] = hits
    # tiempo simulado
    off = (t - now) / 86400
    if abs(off) > 0.01 or orr["paused"]:
        put(surf, F["small"], ("PAUSA  " if orr["paused"] else "") + f"T{'+' if off >= 0 else ''}{off:,.1f} días".replace(",", "X").replace(".", ",").replace("X", "."),
            (6, H - 16), ORANGE)
    if F_ != root:
        put(surf, F["small"], "ZOOM", (6, TOP + 4), GREEN)

def draw_or_side(surf, d, orbits):
    o = next((x for x in orbits if x.get("id") == orr["sel"]), None)
    y = TOP + 4
    if not o or not o.get("name"):
        put(surf, F["small"], "Toca un cuerpo", (OR_X, y), DIM)
        put(surf, F["small"], "para ver sus datos", (OR_X, y + 14), DIM)
    else:
        system = ((d or {}).get("explo") or {}).get("system") or ""
        nm = o["name"]
        short = nm[len(system):].strip() if system and nm.startswith(system) else nm
        put(surf, F["btn"], short or nm, (OR_X, y), ORANGE, W - OR_X - 4); y += 20
        put(surf, F["small"], o.get("cls", ""), (OR_X, y), bcol(o), W - OR_X - 4); y += 15
        put(surf, F["small"], f"{o.get('dist', 0):,} ls".replace(",", "."), (OR_X, y), DIM); y += 14
        if o.get("P"):
            days = o["P"] / 86400
            put(surf, F["small"], f"Órbita: {days:,.1f} días".replace(",", "X").replace(".", ",").replace("X", "."), (OR_X, y), DIM); y += 14
        if o.get("r"):
            put(surf, F["small"], f"Radio: {o['r']:,} km".replace(",", "."), (OR_X, y), DIM); y += 14
        put(surf, F["small"], ("1º  " if o.get("first") else "") + ("MAPEADO" if o.get("mapped") else ""), (OR_X, y), GREEN); y += 14
        put(surf, F["small"], f"~ {cr(o.get('value'))} cr", (OR_X, y), ORANGE); y += 14
        if o.get("src") == "edsm":
            put(surf, F["small"], "Fuente: EDSM (pos. aprox.)", (OR_X, y), BLUE, W - OR_X - 4)
    now = time.time()
    for k, txt in (("menos", "-"), ("mas", "+")):
        draw_button(surf, or_btn(k), txt, None, F["big"], lit=flash.get((72, k), 0) > now)
    put(surf, F["small"], SPEEDS[orr["speed"]][1], (or_btn("menos").x + (W - OR_X) // 2 - 2, 214), ORANGE, anchor="midtop")
    draw_button(surf, or_btn("pausa"), "SEGUIR" if orr["paused"] else "PAUSA", None, F["btn"], filled=orr["paused"])
    zoomed = orr["focus"] is not None
    draw_button(surf, or_btn("zoom"), "SISTEMA" if zoomed else "ZOOM", None, F["btn"],
                dim=not zoomed and orr["sel"] is None, filled=zoomed)
    draw_button(surf, or_btn("ahora"), "AHORA", None, F["btn"], lit=flash.get((72, "ahora"), 0) > now)

def tap_orrery(x, y):
    if OR_AREA.collidepoint(x, y):
        best = min(orr["hits"], key=lambda h: (h[1] - x) ** 2 + (h[2] - y) ** 2, default=None)
        if best and (best[1] - x) ** 2 + (best[2] - y) ** 2 < 18 ** 2:
            orr["sel"] = best[0]
        return
    if or_btn("menos").collidepoint(x, y):
        tap_flash((72, "menos")); orr["speed"] = max(0, orr["speed"] - 1)
    elif or_btn("mas").collidepoint(x, y):
        tap_flash((72, "mas")); orr["speed"] = min(len(SPEEDS) - 1, orr["speed"] + 1)
    elif or_btn("pausa").collidepoint(x, y):
        orr["paused"] = not orr["paused"]
    elif or_btn("zoom").collidepoint(x, y):
        if orr["focus"] is not None:
            orr["focus"] = None
        elif orr["sel"] is not None:
            orr["focus"] = orr["sel"]
        orr["scale"] = None
    elif or_btn("ahora").collidepoint(x, y):
        tap_flash((72, "ahora")); orr["t"] = time.time()

def view_sub12(surf, d, flags, now):
    for i, (n, name) in enumerate([("1", "LOG"), ("2", "STREAM"), ("3", "RANGOS"), ("4", "AJUSTES")]):
        draw_button(surf, grid(i, 2, 2), n, name, F["num"], lit=flash.get((12, i), 0) > now)

# ---------- 12.3 rangos ----------
RANK_NAMES = {
    "Combat": ["Harmless", "Mostly Harmless", "Novice", "Competent", "Expert", "Master", "Dangerous", "Deadly", "Elite"],
    "Trade": ["Penniless", "Mostly Penniless", "Peddler", "Dealer", "Merchant", "Broker", "Entrepreneur", "Tycoon", "Elite"],
    "Explore": ["Aimless", "Mostly Aimless", "Scout", "Surveyor", "Trailblazer", "Pathfinder", "Ranger", "Pioneer", "Elite"],
    "Soldier": ["Defenceless", "Mostly Defenceless", "Rookie", "Soldier", "Gunslinger", "Warrior", "Gladiator", "Deadeye", "Elite"],
    "Exobiologist": ["Directionless", "Mostly Directionless", "Compiler", "Collector", "Cataloguer", "Taxonomist",
                     "Ecologist", "Geneticist", "Elite"],
    "Federation": ["None", "Recruit", "Cadet", "Midshipman", "Petty Officer", "Chief Petty Officer", "Warrant Officer",
                   "Ensign", "Lieutenant", "Lt. Commander", "Post Commander", "Post Captain", "Rear Admiral",
                   "Vice Admiral", "Admiral"],
    "Empire": ["None", "Outsider", "Serf", "Master", "Squire", "Knight", "Lord", "Baron", "Viscount", "Count", "Earl",
               "Marquis", "Duke", "Prince", "King"]}
RANK_ROWS = [("COMBATE", "Combat"), ("COMERCIO", "Trade"), ("EXPLORACIÓN", "Explore"), ("MERCENARIO", "Soldier"),
             ("EXOBIOLOGÍA", "Exobiologist"), ("FEDERACIÓN", "Federation"), ("IMPERIO", "Empire")]

def rank_name(key, n):
    names = RANK_NAMES[key]
    if n is None: return "?"
    if n < len(names): return names[n]
    return f"Elite {['I', 'II', 'III', 'IV', 'V'][min(4, n - len(names))]}"

def view_ranks(surf, d, flags, now):
    r = (d or {}).get("ranks") or {}
    rank, prog = r.get("rank") or {}, r.get("progress") or {}
    put(surf, F["small"], "CMDR " + ((r.get("cmdr") or cfg["cmdr"]).upper()), (W - 8, TOP + 4), DIM, anchor="topright")
    if not rank:
        put(surf, F["btn"], "Sin datos de rangos (carga la partida)", (W // 2, (H + TOP) // 2), DIM, anchor="center")
        return
    y = TOP + 18
    for label, key in RANK_ROWS:
        n, p_ = rank.get(key), prog.get(key, 0)
        put(surf, F["small"], label, (8, y + 4), DIM)
        put(surf, F["btn"], rank_name(key, n).upper(), (118, y), ORANGE, 210)
        bx = pygame.Rect(330, y + 3, 110, 12)
        pygame.draw.rect(surf, DIM, bx, 1)
        pygame.draw.rect(surf, BLUE, (bx.x + 2, bx.y + 2, int((bx.w - 4) * min(p_ or 0, 100) / 100), bx.h - 4))
        put(surf, F["small"], f"{p_ or 0}%", (W - 6, y + 3), WHITE, anchor="topright")
        y += 35

# ---------- 12.4 ajustes ----------
def view_settings(surf, d, flags, now):
    items = [("CAMBIO AUTO", cfg["auto"]), ("ALERTAS", cfg["alerts"]), ("SONIDO", cfg["sound"]), ("COLOR", None)]
    for i, (name, on) in enumerate(items):
        r = grid(i, 2, 2)
        if on is None:
            draw_button(surf, r, name, THEMES[cfg["theme"]][0], F["big"], filled=True, lit=flash.get((124, i), 0) > now)
        else:
            draw_button(surf, r, name, "ACTIVADO" if on else "DESACTIVADO", F["big"], filled=on,
                        lit=flash.get((124, i), 0) > now)

# ---------- reposo y pantalla de inicio ----------
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]

def draw_emblem(surf, cx, cy, r, t):
    for k in range(3):
        pygame.draw.circle(surf, DIM, (cx, cy), r - k * 9, 1)
    a = t * 0.8
    for k in range(3):
        ang = a + k * 2 * math.pi / 3
        pygame.draw.circle(surf, ORANGE, (int(cx + (r - 9) * math.cos(ang)), int(cy + (r - 9) * math.sin(ang))), 3)
    pts = [(cx, cy - r * 0.45), (cx + r * 0.38, cy + r * 0.3), (cx, cy + r * 0.12), (cx - r * 0.38, cy + r * 0.3)]
    pygame.draw.polygon(surf, ORANGE, pts, 2)

def draw_splash(surf, now):
    surf.fill(BLACK)
    k = min(1, (now - ui["start"]) / 2.5)
    draw_emblem(surf, W // 2, 110, 70, now)
    put(surf, F["small"], "CMDR", (W // 2, 200), DIM, anchor="center")
    put(surf, F["big"], cfg["cmdr"], (W // 2, 224), ORANGE, anchor="center")
    put(surf, F["small"], "PANEL DE MANDO  ·  ELITE DANGEROUS", (W // 2, 252), DIM, anchor="center")
    pygame.draw.rect(surf, DIM, (140, 280, 200, 8), 1)
    pygame.draw.rect(surf, ORANGE, (142, 282, int(196 * k), 4))

def draw_idle(surf, now):
    surf.fill(BLACK)
    lt = time.localtime(now)
    draw_emblem(surf, 70, 160, 50, now / 3)
    put(surf, F["clock"], time.strftime("%H:%M", lt), (290, 110), ORANGE, anchor="center")
    put(surf, F["btn"], f"{DIAS[lt.tm_wday]} {lt.tm_mday} de {MESES[lt.tm_mon - 1]}", (290, 170), DIM, anchor="center")
    put(surf, F["big"], "CMDR " + cfg["cmdr"], (290, 215), ORANGE, 300, anchor="center")
    if int(now) % 4 < 3:
        put(surf, F["small"], "Esperando a Elite Dangerous...", (290, 248), DIM, anchor="center")
    put(surf, F["small"], "toca la pantalla para abrir el menú", (W // 2, H - 14), DIM, anchor="center")

def draw_alert(surf, now):
    a = ui["alert"]
    col = a["col"]
    on = int(now * 3) % 2 == 0 or a["kind"] != "red"
    for k in range(4 if on else 2):
        pygame.draw.rect(surf, col, (k * 3, k * 3, W - k * 6, H - k * 6), 2)
    box = pygame.Rect(30, 105, W - 60, 110)
    pygame.draw.rect(surf, BLACK, box)
    pygame.draw.rect(surf, col, box, 3, border_radius=8)
    if a["kind"] == "jump":
        for j in range(14):                       # estela de salto
            yy = box.y + 8 + ((j * 23 + int(now * 160)) % (box.h - 16))
            pygame.draw.line(surf, (40, 70, 130), (box.x + 10, yy), (box.x + 10 + (j * 37) % 120, yy))
            pygame.draw.line(surf, (40, 70, 130), (box.right - 10 - (j * 53) % 120, yy), (box.right - 10, yy))
    put(surf, F["big"] if len(a["text"]) > 16 else F["num"], a["text"], (box.centerx, box.centery - (14 if a["sub"] else 0)),
        col if on else WHITE, box.w - 20, anchor="center")
    if a["sub"]:
        put(surf, F["btn"], a["sub"], (box.centerx, box.centery + 26), WHITE, box.w - 20, anchor="center")

# ---------- 12.2 stream (OBS websocket v5) ----------
obs = {"ok": False, "err": "sin conectar", "scenes": [], "scene": None, "stream": False, "stime": "",
       "rec": False, "mic": None}
obs_cmds = queue.Queue()

def obs_loop():
    while True:
        try:
            import websocket
        except ImportError:
            obs["err"] = "falta python3-websocket"; time.sleep(30); continue
        if "XXX" in OBS_HOST:
            obs["err"] = "pon OBS_HOST en panel.py"; time.sleep(30); continue
        try:
            ws = websocket.create_connection(f"ws://{OBS_HOST}:{OBS_PORT}", timeout=4)
            hello = json.loads(ws.recv())["d"]
            ident = {"rpcVersion": 1, "eventSubscriptions": 0}
            auth = hello.get("authentication")
            if auth:
                sec = base64.b64encode(hashlib.sha256((OBS_PASSWORD + auth["salt"]).encode()).digest()).decode()
                ident["authentication"] = base64.b64encode(hashlib.sha256((sec + auth["challenge"]).encode()).digest()).decode()
            ws.send(json.dumps({"op": 1, "d": ident}))
            if json.loads(ws.recv()).get("op") != 2:
                raise RuntimeError("contraseña incorrecta")
            n = [0]
            def req(t, data=None):
                n[0] += 1; rid = str(n[0])
                ws.send(json.dumps({"op": 6, "d": {"requestType": t, "requestId": rid, "requestData": data or {}}}))
                while True:
                    m = json.loads(ws.recv())
                    if m.get("op") == 7 and m["d"].get("requestId") == rid:
                        return m["d"].get("responseData") or {}
            mic = OBS_MIC or req("GetSpecialInputs").get("mic1")
            obs.update(ok=True, err="", micname=mic)
            last_list = 0
            while True:
                while not obs_cmds.empty():
                    t, data = obs_cmds.get()
                    if t == "ToggleInputMute":
                        data = {"inputName": mic}
                    req(t, data)
                if time.time() - last_list > 5:
                    sl = req("GetSceneList")
                    obs["scenes"] = [x["sceneName"] for x in reversed(sl.get("scenes", []))][:8]
                    last_list = time.time()
                obs["scene"] = req("GetCurrentProgramScene").get("currentProgramSceneName")
                st = req("GetStreamStatus")
                obs["stream"], obs["stime"] = st.get("outputActive", False), (st.get("outputTimecode") or "")[:8]
                obs["rec"] = req("GetRecordStatus").get("outputActive", False)
                obs["mic"] = req("GetInputMute", {"inputName": mic}).get("inputMuted") if mic else None
                time.sleep(0.5)
        except Exception as e:
            obs.update(ok=False, err=(str(e) or type(e).__name__)[:40])
            time.sleep(5)

ST_CARD = TOP + 46
def scene_rect(i): return grid(i, 4, 2, ST_CARD, 246)
def sbtn_rect(i):  return grid(i, 3, 1, 246, H)

def tap_stream(x, y):
    for i, name in enumerate(obs["scenes"]):
        if scene_rect(i).collidepoint(x, y):
            tap_flash((122, i)); obs_cmds.put(("SetCurrentProgramScene", {"sceneName": name})); return
    for i, cmd in enumerate(["ToggleInputMute", "ToggleStream", "ToggleRecord"]):
        if sbtn_rect(i).collidepoint(x, y):
            if i == 0:
                tap_flash((122, 20)); obs_cmds.put((cmd, None)); return
            c, until = ui["confirm"]
            if c == cmd and time.time() < until:       # segundo toque: confirmar
                ui["confirm"] = (None, 0); tap_flash((122, 20 + i)); obs_cmds.put((cmd, None))
            else:
                ui["confirm"] = (cmd, time.time() + 3)
            return

def view_stream(surf, d, flags, now):
    card = pygame.Rect(4, TOP + 2, W - 8, ST_CARD - TOP - 4)
    pygame.draw.rect(surf, DIM, card, 1, border_radius=6)
    if not obs["ok"]:
        put(surf, F["btn"], "OBS: " + obs["err"], card.center, RED, card.w - 16, anchor="center")
    else:
        live = obs["stream"]
        if live and int(now * 2) % 2:
            pygame.draw.circle(surf, RED, (card.x + 16, card.y + 18), 7)
        put(surf, F["big"], ("EN DIRECTO  " + obs["stime"]) if live else "SIN EMITIR", (card.x + 30, card.y + 8), RED if live else DIM)
        if obs["rec"]:
            pygame.draw.circle(surf, RED, (card.right - 138, card.y + 17), 6)
            put(surf, F["btn"], "GRABANDO", (card.right - 126, card.y + 10), RED)
        mic = obs["mic"]
        put(surf, F["small"], "MICRO " + ("SILENCIADO" if mic else "ACTIVO" if mic is False else "?"),
            (card.right - 8, card.y + 30), RED if mic else GREEN, anchor="topright")
    for i, name in enumerate(obs["scenes"]):
        draw_button(surf, scene_rect(i), name, None, F["btn"], filled=name == obs["scene"],
                    lit=flash.get((122, i), 0) > now)
    if obs["ok"] and not obs["scenes"]:
        put(surf, F["btn"], "Sin escenas", (W // 2, (ST_CARD + 246) // 2), DIM, anchor="center")
    c, until = ui["confirm"]
    conf = c if time.time() < until else None
    labels = [("MICRO", "SILENCIAR" if obs["mic"] is False else "ACTIVAR", obs["mic"] is True),
              ("DIRECTO", "¿SEGURO?" if conf == "ToggleStream" else ("PARAR" if obs["stream"] else "EMPEZAR"), obs["stream"]),
              ("GRABAR", "¿SEGURO?" if conf == "ToggleRecord" else ("PARAR" if obs["rec"] else "EMPEZAR"), obs["rec"])]
    for i, (t, sub, on) in enumerate(labels):
        draw_button(surf, sbtn_rect(i), t, sub, F["btn"], filled=on, lit=flash.get((122, 20 + i), 0) > now,
                    dim=not obs["ok"])

VIEWS = {0: view_menu, 1: view_mandos, 2: view_pips, 3: view_nav, 4: view_carga, 5: view_srv, 6: view_combat, 7: view_sub7, 71: view_explo, 72: view_orrery, 8: view_station,
         9: view_fighter, 10: view_mining, 11: view_session, 12: view_sub12, 121: view_log, 122: view_stream,
         123: view_ranks, 124: view_settings}

def render(surf):
    with lock:
        d, rx = state["data"], state["rx"]
    now = time.time()
    online = d is not None and now - rx < 5
    if online:
        process_notes(d)
    if now - ui["start"] < 3:
        draw_splash(surf, now); return
    ui["idle_on"] = not online and ui["view"] == 0 and now > ui["idle_skip"] and now - ui["start"] > 8
    if ui["idle_on"]:
        draw_idle(surf, now); return
    flags = (d or {}).get("Flags", 0) if online else 0
    v = ui["view"]
    surf.fill(BLACK)
    # barra superior
    x0 = 8
    if v:
        pygame.draw.rect(surf, ORANGE, BACK.inflate(-8, -8), 2, border_radius=6)
        put(surf, F["btn"], "< MENÚ", BACK.center, ORANGE, anchor="center")
        x0 = BACK.right + 4
    title = ((d or {}).get("system") or "---").upper() if online else "SIN DATOS"
    put(surf, F["big"], title, (x0, 6), ORANGE if online else DIM, W - 136 - x0)
    fuel = ((d or {}).get("Fuel") or {}).get("FuelMain")
    cap = (d or {}).get("fuelcap")
    if online and fuel is not None:
        pct = max(0.0, min(1.0, fuel / cap)) if cap else None
        bx = pygame.Rect(W - 128, 8, 120, 14)
        pygame.draw.rect(surf, DIM, bx, 1)
        if pct is not None:
            pygame.draw.rect(surf, RED if pct < 0.25 else ORANGE, (bx.x + 2, bx.y + 2, int((bx.w - 4) * pct), bx.h - 4))
        put(surf, F["small"], f"FUEL {fuel:.1f}t", (W - 128, 26))
    mode = (d or {}).get("mode") if online else None
    if mode:
        put(surf, F["small"], f"MODO: {mode}", (W - 128, 40), RED, 124)
    alert = next((t for b, t in ALERTS if flags & (1 << b)), None) if online else None
    if alert:
        put(surf, F["small"], alert, (x0, 34), RED)
    elif v:
        put(surf, F["small"], MENU.get(v, f"MENU {v}"), (x0, 34), DIM)
    pygame.draw.line(surf, DIM, (0, TOP - 2), (W, TOP - 2), 1)
    fn = VIEWS.get(v)
    if fn:
        fn(surf, d if online else None, flags, now)
    else:
        put(surf, F["btn"], f"Menú {v} vacío", (W // 2, (H + TOP) // 2), DIM, anchor="center")
    if ui["alert"]:
        if now < ui["alert"]["until"]:
            draw_alert(surf, now)
        else:
            ui["alert"] = None

def load_fonts():
    pygame.font.init()
    mono = pygame.font.match_font("dejavusansmono") or pygame.font.match_font("monospace")
    F.update(big=pygame.font.Font(None, 30), btn=pygame.font.Font(None, 24), small=pygame.font.Font(None, 18),
             num=pygame.font.Font(None, 48), mono=pygame.font.Font(mono, 11), clock=pygame.font.Font(None, 110))

def main():
    load_cfg()
    make_sounds()
    load_fonts()
    surf = pygame.Surface((W, H))
    dev, bpp, stride = find_fb()
    print("Framebuffer", dev, bpp, "bpp")
    threading.Thread(target=udp_loop, daemon=True).start()
    threading.Thread(target=touch_loop, daemon=True).start()
    threading.Thread(target=obs_loop, daemon=True).start()
    last = None
    with open(dev, 'r+b', buffering=0) as fb:
        while True:
            render(surf)
            data = to_fb_bytes(surf, bpp, stride)
            if data != last:
                fb.seek(0); fb.write(data); last = data
            time.sleep(0.1)

if __name__ == "__main__":
    main()
