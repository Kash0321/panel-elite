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
MENU = {1: "MANDOS", 2: "PIPS", 3: "NAVEGACIÓN", 4: "CARGA/MISIÓN", 5: "SRV / RHINO / A PIE", 6: "COMBATE", 7: "EXPLORACIÓN",
        8: "ESTACIÓN", 9: "CAZA", 10: "MINERÍA", 11: "SESIÓN", 12: "LOG / STREAM", 121: "LOG", 122: "STREAM",
        71: "EXPLORACIÓN", 72: "SISTEMA", 73: "XENOBIOLOGÍA", 74: "YACIMIENTOS", 75: "DIARIO DE EXPLORACIÓN", 76: "ALIENÍGENAS", 100: "EN VIVO", 61: "REGISTRO DE COMBATE", 125: "MATERIALES", 126: "PORTANAVES", 127: "MERCADO", 1244: "PREFERENCIAS", 1245: "VERSIONES", 128: "NOTAS DE VIAJE", 129: "NOTA"}
MENU.update({123: "RANGOS", 124: "AJUSTES"})
PARENT = {0: 100, 71: 7, 72: 7, 73: 7, 74: 7, 75: 7, 76: 7, 121: 12, 122: 12, 123: 12, 124: 12, 1244: 124, 1245: 124, 125: 12, 126: 12, 127: 12, 128: 12, 129: 128}
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
ui = {"view": 100, "pause": False, "tab4": 0, "page4": 0, "orders": {}, "page7": 0, "confirm": (None, 0),
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
AUTO_VIEW = {"embark": 100, "market": 127, "interdicted": 6, "underattack": 6, "docking": 8, "prospector": 10, "srv": 5, "foot": 100, "fighter": 9}

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
SEC_TOP = TOP + 20   # menu 5: hueco para los titulos SRV / RHINO / A PIE
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
    if BACK.collidepoint(x, y):
        ui["view"] = 0 if v == 100 else PARENT.get(v, 0); ui["pause"] = False
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
        for i in range(6):
            if grid(i, 3, 2).collidepoint(x, y):
                tap_flash((7, i)); ui["view"] = 71 + i; return
    elif v in (125, 127):
        ui[f'page{v}'] = ui.get(f'page{v}', 0) + 1; return
    elif v in (128, 129):
        tap_trip(x, y); return
    elif v == 11 and STYLE_BTN.collidepoint(x, y):
        style_toggle(); return
    elif v == 3:
        cur = ui.get('navtab') or (1 if time.time() < pol['until'] else 0); ui['navtab'] = (cur + 1) % 3; pol['until'] = 0; return
    elif v == 124:
        for i in range(7):
            if grid(i, 4, 2).collidepoint(x, y):
                power_tap(i); return
    elif v == 1245:
        ui['page1245'] = ui.get('page1245', 0) + 1; return
    elif v in (100, 73) and NAVE_BTN.collidepoint(x, y):
        ship_here(); return
    elif v == 76:
        ui['alientab'] = 1 - ui.get('alientab', 0); return
    elif v == 11:
        ui['sesstab'] = 1 - ui.get('sesstab', 0); return
    elif v == 71:
        ui['page71'] = ui.get('page71', 0) + 1; return
    elif v == 72:
        tap_orrery(x, y)
    elif v == 12:
        for i in range(8):
            if grid(i, 4, 2).collidepoint(x, y):
                tap_flash((12, i)); ui["view"] = 121 + i; return
    elif v == 1244:
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
        put(surf, F["small"], f"RUTA  -  destino: {route[-1][0]}", (8, y), DIM, W - 210)
        RI = (d or {}).get("routeinfo") or {}
        bits = []
        if RI.get("eta"):
            bits.append(f"ETA {RI['eta'] // 3600}h {RI['eta'] % 3600 // 60:02d}m" if RI["eta"] >= 3600 else f"ETA {RI['eta'] // 60} min")
        if RI.get("neutron"):
            bits.append(f"neutrón a {RI['neutron']}")
        if bits:
            put(surf, F["small"], "  ·  ".join(bits), (W - 8, y), BLUE, anchor="topright")
        y += 18
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
    for label, cx, act in ((("RHINO" if "rhino" in ((d or {}).get("srvtype") or "").lower() else "SRV"), W // 4, in_srv), ("A PIE", 3 * W // 4, on_foot)):
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
    if ex.get("edsm_n"):
        put(surf, F["small"], f"EDSM: {ex['edsm_n']} cuerpos", (150, y), BLUE)
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
        msg = "Consultando EDSM..." if ex.get("edsm_st") == "consultando" else "Nada destacable escaneado aún"
        put(surf, F["btn"], msg, (W // 2, y + 60), DIM, anchor="center")
    per = 7
    pages = max(1, (len(top) + per - 1) // per)
    pg = ui.get("page71", 0) % pages
    if pages > 1:
        put(surf, F["small"], f"pág {pg + 1}/{pages}  (toca para pasar)", (W // 2, H - 34), DIM, anchor="center")
    for row in top[pg * per:(pg + 1) * per]:
        name, cls, dist, first, mapped, val = row[:6]
        src = row[6] if len(row) > 6 else None
        short = name[len(sysname):].strip() if name.startswith(sysname) else name
        put(surf, F["btn"], short or name, (8, y), ORANGE, 70)
        put(surf, F["small"], cls, (80, y + 4), ORANGE, 150)
        put(surf, F["small"], f"{dist:,} ls".replace(",", "."), (300, y + 4), DIM, anchor="topright")
        if src == "edsm":
            put(surf, F["small"], "EDSM", (342, y + 4), BLUE)
        else:
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
    if "rhino" in ((d or {}).get("srvtype") or "").lower():
        put(surf, F["small"], "BODEGA DEL RHINO", (8, y), DIM)
        put(surf, F["small"], "REFINADO (SESIÓN)", (318, y), DIM); y += 14
        yy = y
        inv, tot = (d or {}).get("srvinv") or [], (d or {}).get("srvcargo")
        put(surf, F["big"], f"{tot if tot is not None else '?'} t", (8, y), ORANGE); y += 30
        for name, n in inv[:8]:
            put(surf, F["small"], name, (8, y + 2), ORANGE, 220)
            put(surf, F["btn"], f"{n} t", (300, y), WHITE, anchor="topright"); y += 20
        if not inv:
            put(surf, F["small"], "vacía", (8, y), DIM)
        pygame.draw.line(surf, DIM, (310, yy - 14), (310, H - 30))
        ref = sorted((m.get("refined") or {}).items(), key=lambda kv: -kv[1])
        if not ref:
            put(surf, F["small"], "nada aún", (318, yy + 4), DIM)
        for name, n in ref[:8]:
            put(surf, F["small"], name, (318, yy + 2), ORANGE, 110)
            put(surf, F["btn"], f"{n}", (W - 8, yy), ORANGE, anchor="topright"); yy += 20
        pygame.draw.line(surf, DIM, (8, H - 26), (W - 8, H - 26))
        sf = ((d or {}).get("Fuel") or {}).get("FuelReservoir")
        put(surf, F["btn"], f"COMBUSTIBLE: {sf:.2f} t".replace(".", ",") if sf is not None else "COMBUSTIBLE: ?",
            (8, H - 22), RED if sf is not None and sf < 0.1 else ORANGE)
        zonas = sum(c for n, c in (((d or {}).get("rings") or {}).get("signals") or []) if "miner" in n.lower() or "mining" in n.lower())
        put(surf, F["small"], f"Zonas de minería en el planeta: {zonas}", (W - 8, H - 18), DIM, anchor="topright")
        return
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
    for i, (n, name) in enumerate([("1", "EXPLORACIÓN"), ("2", "SISTEMA"), ("3", "XENOBIO"), ("4", "YACIM."), ("5", "DIARIO"), ("6", "ALIEN")]):
        draw_button(surf, grid(i, 3, 2), n, name, F["num"], lit=flash.get((7, i), 0) > now)

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

# ---------- 7.3 xenobiologia ----------
def hav(a, b, R):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(min(1, h)))

SHIPOV = {"pos": None, "src": None, "cur": None}
NAVE_BTN = pygame.Rect(196, H - 60, 124, 40)

def ship_pos(b):
    s_ = b.get("ship")
    if s_ != SHIPOV["src"]:              # el juego da una posicion nueva: manda la del juego
        SHIPOV["src"], SHIPOV["pos"] = s_, None
    return SHIPOV["pos"] or s_

def ship_here():
    if SHIPOV["cur"]:
        SHIPOV["pos"] = list(SHIPOV["cur"])
        tap_flash(("nave", 0))

def draw_compass(surf, d, b):
    ship, lat, lon, R = ship_pos(b), b.get("lat"), b.get("lon"), b.get("R")
    out = bool((d or {}).get("Flags", 0) & (1 << 26)) or bool((d or {}).get("Flags2", 0) & 1)
    SHIPOV["cur"] = (lat, lon) if (out and lat is not None) else None
    if out and lat is not None and R:
        draw_button(surf, NAVE_BTN, "NAVE AQUÍ", None, F["btn"], lit=flash.get(("nave", 0), 0) > time.time())
    if not ship or lat is None or not R or not out:
        return
    y0 = H - 62
    pygame.draw.line(surf, DIM, (8, y0 - 4), (W - 8, y0 - 4))
    dist = hav(ship, (lat, lon), R)
    p1, p2, dl = math.radians(lat), math.radians(ship[0]), math.radians(ship[1] - lon)
    brg = math.degrees(math.atan2(math.sin(dl) * math.cos(p2),
                                  math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl))) % 360
    hdg = b.get("hdg")
    cx, cy, r = 32, y0 + 17, 17
    pygame.draw.circle(surf, DIM, (cx, cy), r, 1)
    if hdg is not None:
        a = math.radians(brg - hdg)
        pt = lambda k, da: (cx + r * k * math.sin(a + da), cy - r * k * math.cos(a + da))
        pygame.draw.polygon(surf, GREEN, [pt(0.95, 0), pt(0.6, 2.5), (cx, cy), pt(0.6, -2.5)])
    txt = f"{dist / 1000:.1f} km".replace(".", ",") if dist >= 1000 else f"{dist:.0f} m"
    put(surf, F["small"], "NAVE", (60, y0 + 2), DIM)
    put(surf, F["big"], txt, (60, y0 + 14), GREEN)
    put(surf, F["btn"], f"rumbo {brg:.0f}°", (W - 8, y0 + 4), ORANGE, anchor="topright")
    if hdg is not None:
        put(surf, F["small"], f"vas a {hdg:.0f}°", (W - 8, y0 + 24), DIM, anchor="topright")

def view_bio(surf, d, flags, now):
    b = (d or {}).get("bio") or {}
    y = TOP + 6
    put(surf, F["small"], "CUERPO", (8, y), DIM)
    sig = b.get("signals")
    put(surf, F["small"], f"SEÑALES BIO: {sig if sig is not None else '?'}", (W - 8, y), DIM, anchor="topright"); y += 14
    put(surf, F["btn"], b.get("body") or "No estás en un planeta", (8, y), ORANGE if b.get("body") else DIM, W - 16); y += 22
    done = set(b.get("done") or [])
    gx = 8
    for g in b.get("genuses") or []:
        t = ("OK " if g in done else "") + g
        w_ = F["small"].size(t)[0] + 10
        if gx + w_ > W - 4: break
        pygame.draw.rect(surf, GREEN if g in done else DIM, (gx, y, w_ - 4, 16), 1, border_radius=3)
        put(surf, F["small"], t, (gx + 3, y + 2), GREEN if g in done else ORANGE)
        gx += w_
    y += 22
    pygame.draw.line(surf, DIM, (8, y), (W - 8, y)); y += 6
    if not b.get("species"):
        put(surf, F["btn"], "Sin muestreo en curso", (W // 2, y + 50), DIM, anchor="center")
    else:
        step = b.get("step", 0)
        put(surf, F["big"], b["species"].upper(), (8, y), GREEN if step >= 3 else ORANGE, W - 90)
        for k in range(3):
            pygame.draw.circle(surf, ORANGE, (W - 70 + k * 22, y + 12), 8, 0 if k < step else 1)
        y += 26
        put(surf, F["small"], b.get("variant") or "", (8, y), DIM, W - 220)
        val = b.get("value")
        if val:
            txt = ("" if b.get("exact") else "~") + cr(val) + " cr"
            if b.get("bonus"):
                txt += f"  x5 = {cr(val * 5)}"
            put(surf, F["btn"], txt, (W - 8, y - 3), GREEN if b.get("bonus") else ORANGE, 210, anchor="topright")
        y += 20
        pts, R = b.get("pts") or [], b.get("R")
        lat, lon, rng = b.get("lat"), b.get("lon"), b.get("range", 100)
        if step >= 3:
            put(surf, F["big"], "MUESTRA COMPLETA", (W // 2, y + 22), GREEN, anchor="center")
        elif pts and R and lat is not None:
            dist = min(hav(p, (lat, lon), R) for p in pts)
            ok = dist >= rng
            put(surf, F["num"], f"{dist:,.0f} m".replace(",", "."), (8, y), GREEN if ok else RED)
            put(surf, F["btn"], f"mín. {rng} m", (W - 8, y + 4), DIM, anchor="topright")
            put(surf, F["small"], "PUEDES MUESTREAR" if ok else "ALÉJATE", (W - 8, y + 26), GREEN if ok else RED, anchor="topright")
            bx = pygame.Rect(8, y + 44, W - 16, 12)
            pygame.draw.rect(surf, DIM, bx, 1)
            pygame.draw.rect(surf, GREEN if ok else RED, (bx.x + 2, bx.y + 2, int((bx.w - 4) * min(1, dist / rng)), bx.h - 4))
        else:
            put(surf, F["btn"], f"Distancia mínima del género: {rng} m", (8, y + 10), DIM)
    draw_compass(surf, d, b)
    pygame.draw.line(surf, DIM, (8, H - 24), (W - 8, H - 24))
    put(surf, F["btn"], f"MUESTRAS SIN VENDER: {b.get('unsold', 0)}", (8, H - 20), ORANGE)
    if b.get("unsold_cr"):
        put(surf, F["btn"], f"~ {cr(b['unsold_cr'])} cr", (W - 8, H - 20), ORANGE, anchor="topright")

# ---------- 11 submenu / 11.2 en vivo ----------
def view_sub11(surf, d, flags, now):
    for i, (n, name) in enumerate([("1", "SESIÓN"), ("2", "EN VIVO")]):
        draw_button(surf, grid(i, 2, 1), n, name, F["num"], lit=flash.get((11, i), 0) > now)

def chips(surf, items, y, cols=4):
    cw = (W - 16) // cols
    for k, (txt, on, col) in enumerate(items):
        r = pygame.Rect(8 + (k % cols) * cw, y + (k // cols) * 24, cw - 4, 20)
        if on:
            pygame.draw.rect(surf, col, r, border_radius=4)
            put(surf, F["small"], txt, r.center, BLACK, cw - 8, anchor="center")
        else:
            pygame.draw.rect(surf, DIM, r, 1, border_radius=4)
            put(surf, F["small"], txt, r.center, DIM, cw - 8, anchor="center")
    return y + ((len(items) + cols - 1) // cols) * 24

LEGAL = {"Clean": ("LIMPIO", None), "IllegalCargo": ("CARGA ILEGAL", "r"), "Speeding": ("EXCESO VELOCIDAD", "r"),
         "Wanted": ("BUSCADO", "r"), "Hostile": ("HOSTIL", "r"), "PassengerWanted": ("PASAJERO BUSCADO", "r"),
         "Warrant": ("ORDEN DE ARRESTO", "r"), "Allied": ("ALIADO", None), "Thargoid": ("THARGOIDE", "r")}

def pctv(v):
    return None if v is None else v * 100

def view_live(surf, d, flags, now):
    d = d or {}
    L, f2 = d.get("live") or {}, d.get("Flags2", 0)
    if f2 & 1:
        mode = "A PIE"
    elif flags & (1 << 26):
        mode = (d.get("srvtype") or "SRV").upper()
    elif flags & (1 << 25):
        mode = "CAZA"
    else:
        mode = "NAVE"
    y = TOP + 4
    put(surf, F["big"], mode, (8, y), GREEN)
    if mode == "A PIE":
        s_ = L.get("suit") or {}
        put(surf, F["small"], " · ".join(x for x in (s_.get("name"), s_.get("loadout")) if x), (W - 8, y + 6), ORANGE, 300, anchor="topright")
        y += 30
        oxy, hp = pctv(L.get("oxy")), pctv(L.get("health"))
        half = (W - 24) // 2
        bar(surf, 8, y, half, "OXÍGENO", oxy, RED if oxy is not None and oxy < 25 else BLUE)
        bar(surf, 16 + half, y, half, "SALUD", hp, RED if hp is not None and hp < 25 else GREEN)
        y += 22
        t = L.get("temp")
        tcol = RED if f2 & ((1 << 9) | (1 << 11)) else BLUE if f2 & ((1 << 8) | (1 << 10)) else ORANGE
        put(surf, F["small"], "TEMPERATURA", (8, y + 4), DIM)
        put(surf, F["big"], f"{t - 273.15:.0f} °C" if t is not None else "?", (100, y), tcol)
        g = L.get("grav")
        put(surf, F["small"], "GRAVEDAD", (250, y + 4), DIM)
        put(surf, F["big"], f"{g:.2f} G".replace(".", ",") if g is not None else "-", (W - 8, y),
            RED if g and g > 2 else ORANGE, anchor="topright")
        y += 26
        put(surf, F["small"], "ARMA", (8, y + 4), DIM)
        put(surf, F["btn"], L.get("weapon") or "-", (60, y + 1), ORANGE, W - 70); y += 24
        y = chips(surf, [("ESTACIÓN", f2 & (1 << 3), BLUE), ("PLANETA", f2 & (1 << 4), BLUE),
                         ("RESPIRABLE", f2 & (1 << 16), GREEN), ("POCO O2", f2 & (1 << 6), RED),
                         ("SALUD BAJA", f2 & (1 << 7), RED), ("FRÍO", f2 & ((1 << 8) | (1 << 10)), BLUE),
                         ("CALOR", f2 & ((1 << 9) | (1 << 11)), RED), ("PLANEO", f2 & (1 << 12), ORANGE)], y)
        P = d.get("pack") or {}
        cons = P.get("cons") or []
        if cons:
            put(surf, F["small"], "  ·  ".join(f"{n} {c}" for n, c in cons[:5]), (8, y + 4), ORANGE, W - 16)
        if P.get("n_items") or P.get("n_comp") or P.get("n_data"):
            put(surf, F["small"], f"Mochila: {P.get('n_items', 0)} objetos · {P.get('n_comp', 0)} componentes · {P.get('n_data', 0)} datos",
                (8, y + 22), DIM, W - 16)
        draw_compass(surf, d, d.get("bio") or {})
    elif flags & (1 << 26):
        put(surf, F["small"], d.get("body") or "", (W - 8, y + 6), ORANGE, 300, anchor="topright")
        y += 34
        y = chips(surf, [("FRENO MANO", flags & (1 << 12), RED), ("TORRETA", flags & (1 << 13), ORANGE),
                         ("TORR. RECOGIDA", flags & (1 << 14), DIM), ("ASIST. CONDUC.", flags & (1 << 15), GREEN),
                         ("LUCES", flags & (1 << 8), ORANGE), ("LUCES LARGAS", flags & (1 << 31), ORANGE),
                         ("CARGA", flags & (1 << 9), ORANGE), ("SOBRECALENT.", flags & (1 << 20), RED)], y)
        if d.get("srvcargo") is not None:
            put(surf, F["small"], "BODEGA DEL VEHÍCULO", (8, y + 8), DIM)
            put(surf, F["big"], f"{d['srvcargo']} t", (170, y + 2), ORANGE)
            inv = ", ".join(f"{n} {c}" for n, c in (d.get("srvinv") or [])[:4])
            if inv:
                put(surf, F["small"], inv, (240, y + 8), WHITE, W - 248)
        sf = (d.get("Fuel") or {}).get("FuelReservoir")
        put(surf, F["small"], "COMBUSTIBLE", (8, y + 40), DIM)
        put(surf, F["big"], f"{sf:.2f} t".replace(".", ",") if sf is not None else "?", (110, y + 34),
            RED if sf is not None and sf < 0.1 else ORANGE)
        sh = flags & 8
        put(surf, F["btn"], "ESCUDOS ACTIVOS" if sh else "SIN ESCUDOS", (W - 8, y + 36), BLUE if sh else RED, anchor="topright")
        sm = d.get("srvmats") or []
        if sm:
            put(surf, F["small"], "RECOGIDO: " + ", ".join(f"{n} {c}" + (" (MÁX)" if full else "") for n, c, full in sm[:5]),
                (8, y + 64), RED if any(x[2] for x in sm) else ORANGE, W - 16)
        draw_compass(surf, d, d.get("bio") or {})
    else:
        sh = L.get("ship") or {}
        nm = " · ".join(x for x in (sh.get("name"), sh.get("ident")) if x)
        put(surf, F["small"], (sh.get("ship") or "").upper(), (W - 8, y + 2), ORANGE, 300, anchor="topright")
        put(surf, F["small"], nm, (W - 8, y + 16), DIM, 300, anchor="topright")
        y += 32
        hull = pctv(sh.get("hull"))
        half = (W - 24) // 2
        bar(surf, 8, y, half, "CASCO", hull, RED if hull is not None and hull < 30 else ORANGE)
        cg, cap = L.get("cargo"), d.get("cargocap")
        put(surf, F["small"], "CARGA", (16 + half, y + 1), DIM)
        put(surf, F["btn"], f"{cg:.0f} / {cap if cap is not None else '?'} t" if cg is not None else "-",
            (W - 8, y - 2), ORANGE, anchor="topright")
        y += 22
        lg, kind = LEGAL.get(L.get("legal"), (L.get("legal") or "-", None))
        put(surf, F["small"], "ESTADO", (8, y + 4), DIM)
        put(surf, F["btn"], lg, (64, y + 1), RED if kind else GREEN)
        alt = L.get("alt")
        if alt is not None and flags & (1 << 21):
            real = not flags & (1 << 29)
            lab, acol = "ALTITUD", ORANGE
            if real and 7 <= alt <= 40:
                lab, acol = "RHINO OK", GREEN
            elif real and alt < 7:
                lab, acol = "SUBE A 7 m", ORANGE
            elif real and alt <= 80:
                lab, acol = "BAJA A 40 m", ORANGE
            put(surf, F["small"], lab, (250, y + 4), acol if lab != "ALTITUD" else DIM)
            put(surf, F["btn"], f"{alt / 1000:.1f} km".replace(".", ",") if alt >= 1000 else f"{alt:.0f} m",
                (W - 8, y + 1), acol, anchor="topright")
        y += 26
        rh = sh.get("rhino")
        rcol = GREEN if rh == "A BORDO" else RED if rh == "SIN RHINO" else ORANGE
        chips(surf, ([(f"RHINO {rh}" if rh != "SIN RHINO" else rh, rh in ("A BORDO", "SIN RHINO", "FUERA"), rcol)] if rh else []) + [("ATRACADO", flags & 1, BLUE), ("ATERRIZADO", flags & 2, BLUE), ("TREN", flags & 4, ORANGE),
                     ("ESCUDOS", flags & 8, BLUE), ("SUPERCRUCERO", flags & 16, BLUE), ("FA OFF", flags & 32, RED),
                     ("ARMAS", flags & 64, RED), ("LUCES", flags & 256, ORANGE), ("RECOGEDOR", flags & 512, ORANGE),
                     ("SILENCIOSO", flags & 1024, BLUE), ("RECOG. COMB.", flags & 2048, ORANGE),
                     ("MASA BLOQ.", flags & (1 << 16), RED), ("FSD CARGANDO", flags & (1 << 17), BLUE),
                     ("FSD ENFRIANDO", flags & (1 << 18), DIM), ("SOBRECALENT.", flags & (1 << 20), RED),
                     ("VISIÓN NOCT.", flags & (1 << 28), GREEN)], y)

# ---------- 12.5 materiales / 12.6 portanaves / 12.7 mercado ----------
def pager(key, n, per):
    pages = max(1, (n + per - 1) // per)
    pg = ui.get(key, 0) % pages
    if pages > 1:
        put(surf_ref[0], F["small"], f"pág {pg + 1}/{pages}  (toca para pasar)", (W // 2, H - 9), DIM, anchor="center")
    return pg
surf_ref = [None]

def view_mats(surf, d, flags, now):
    surf_ref[0] = surf
    M = (d or {}).get("mats") or {}
    rows = M.get("list") or []
    y = TOP + 4
    put(surf, F["small"], f"{M.get('n', 0)} materiales", (8, y), DIM)
    put(surf, F["small"], f"AL MÁXIMO: {M.get('full', 0)}", (W - 8, y), RED if M.get("full") else DIM, anchor="topright")
    y += 16
    if not rows:
        put(surf, F["btn"], "Sin datos (carga la partida)", (W // 2, (H + TOP) // 2), DIM, anchor="center"); return
    per = 10
    pg = pager("page125", len(rows), per)
    for name, c, mx in rows[pg * per:(pg + 1) * per]:
        pct = c / mx
        col = RED if c >= mx else ORANGE if pct >= 0.9 else DIM
        put(surf, F["small"], name, (8, y + 3), ORANGE, 200)
        bx = pygame.Rect(214, y + 3, 186, 12)
        pygame.draw.rect(surf, DIM, bx, 1)
        pygame.draw.rect(surf, RED if c >= mx else BLUE, (bx.x + 2, bx.y + 2, int((bx.w - 4) * min(1, pct)), bx.h - 4))
        put(surf, F["small"], f"{c}/{mx}", (W - 8, y + 3), col if c >= 0.9 * mx else WHITE, anchor="topright")
        y += 22

def view_carrier(surf, d, flags, now):
    c = (d or {}).get("carrier") or {}
    if not (c.get("name") or c.get("callsign")):
        put(surf, F["btn"], "Sin datos del portanaves", (W // 2, (H + TOP) // 2 - 10), DIM, anchor="center")
        put(surf, F["small"], "abre su gestión en el juego una vez", (W // 2, (H + TOP) // 2 + 12), DIM, anchor="center")
        return
    y = TOP + 6
    put(surf, F["big"], (c.get("name") or "").upper(), (8, y), ORANGE, W - 140)
    put(surf, F["btn"], c.get("callsign") or "", (W - 8, y + 2), DIM, anchor="topright"); y += 30
    put(surf, F["small"], "SISTEMA", (8, y + 4), DIM)
    put(surf, F["btn"], c.get("system") or "?", (80, y + 1), ORANGE, W - 90); y += 28
    fuel = c.get("fuel")
    put(surf, F["small"], "TRITIO", (8, y + 1), DIM)
    bx = pygame.Rect(80, y, W - 170, 16)
    pygame.draw.rect(surf, DIM, bx, 1)
    if fuel is not None:
        pygame.draw.rect(surf, RED if fuel < 135 else GREEN, (bx.x + 2, bx.y + 2, int((bx.w - 4) * min(1, fuel / 1000)), bx.h - 4))
    put(surf, F["btn"], f"{fuel} t" if fuel is not None else "?", (W - 8, y - 2), RED if fuel is not None and fuel < 135 else ORANGE, anchor="topright")
    y += 28
    put(surf, F["small"], "SALDO", (8, y + 4), DIM)
    put(surf, F["big"], f"{cr(c.get('balance'))} cr", (80, y), ORANGE); y += 34
    pygame.draw.line(surf, DIM, (8, y), (W - 8, y)); y += 8
    dest, dep = c.get("dest"), c.get("depart")
    if dest and dep:
        left = dep - time.time()
        put(surf, F["small"], "SALTO PROGRAMADO A", (8, y), DIM)
        put(surf, F["big"], dest.upper(), (8, y + 14), BLUE, W - 16); y += 46
        if left > 0:
            put(surf, F["num"], f"{int(left) // 60:02d}:{int(left) % 60:02d}", (W // 2, y), ORANGE if left > 60 else RED, anchor="midtop")
        else:
            put(surf, F["big"], "SALTANDO...", (W // 2, y + 8), BLUE if int(now * 2) % 2 else WHITE, anchor="midtop")
    else:
        put(surf, F["btn"], "Sin salto programado", (W // 2, y + 30), DIM, anchor="center")

def view_market(surf, d, flags, now):
    surf_ref[0] = surf
    m = (d or {}).get("market") or {}
    if not m.get("station"):
        put(surf, F["btn"], "Abre el mercado en una estación", (W // 2, (H + TOP) // 2), DIM, anchor="center"); return
    y = TOP + 4
    age = int((time.time() - (m.get("t") or time.time())) / 60)
    put(surf, F["btn"], m["station"].upper(), (8, y), ORANGE, W - 120)
    put(surf, F["small"], f"hace {age} min" if age else "ahora", (W - 8, y + 4), DIM, anchor="topright"); y += 22
    sell = m.get("sell") or []
    rows = sell if sell else m.get("best") or []
    put(surf, F["small"], "TU BODEGA AQUÍ" if sell else "BODEGA VACÍA · LO MEJOR PAGADO AQUÍ (vs media)", (8, y), DIM)
    if sell:
        put(surf, F["small"], "TOTAL", (W - 8, y), DIM, anchor="topright")
    y += 16
    per = 7 if sell else 9
    pg = pager("page127", len(rows), per)
    for r in rows[pg * per:(pg + 1) * per]:
        if sell:
            name, n, price, mean, dem = r
        else:
            name, price, mean = r; n = None
        diff = (price - mean) / mean * 100 if mean else 0
        put(surf, F["small"], name, (8, y + 3), ORANGE, 170)
        if n is not None:
            put(surf, F["small"], f"{n} t", (200, y + 3), WHITE, anchor="topright")
        put(surf, F["small"], f"{price:,} cr".replace(",", "."), (300, y + 3), WHITE, anchor="topright")
        put(surf, F["small"], f"{diff:+.0f}%", (350, y + 3), GREEN if diff >= 0 else RED, anchor="topright")
        if n is not None:
            put(surf, F["btn"], cr(n * price), (W - 8, y), GREEN if diff >= 0 else ORANGE, anchor="topright")
        y += 22
    if sell:
        tot = sum(r[1] * r[2] for r in sell)
        pygame.draw.line(surf, DIM, (8, H - 40), (W - 8, H - 40))
        put(surf, F["btn"], f"VENDIENDO TODO: {cr(tot)} cr", (8, H - 36), GREEN)

# ---------- 12.8 notas de viaje ----------
NOTES_FILE = "/home/ortem/notas.json"

def trip_load():
    try:
        with open(NOTES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []

trip = {"list": trip_load(), "sel": None, "page": 0, "d": None}

def trip_save():
    import os
    try:
        with open(NOTES_FILE + ".tmp", "w", encoding="utf-8") as f:
            json.dump(trip["list"], f, ensure_ascii=False, indent=1)
        os.replace(NOTES_FILE + ".tmp", NOTES_FILE)
    except OSError as e:
        print("notas:", e)

def trip_here(d):
    d = d or {}
    flags, f2 = d.get("Flags", 0), d.get("Flags2", 0)
    b = d.get("bio") or {}
    st = d.get("station") or {}
    if b.get("species") and 0 < b.get("step", 0) < 3: tag = "XENOBIO"
    elif flags & 1: tag = "ESTACIÓN"
    elif f2 & 1: tag = "A PIE"
    elif flags & (1 << 26): tag = "SRV"
    elif flags & 2: tag = "ATERRIZADO"
    elif d.get("body"): tag = "PLANETA"
    else: tag = "ESPACIO"
    return {"sys": d.get("system"), "body": d.get("body"), "st": st.get("name") if flags & 1 else None,
            "lat": b.get("lat"), "lon": b.get("lon"), "R": b.get("R"), "pos": d.get("starpos"),
            "tag": tag, "t": time.time()}

def trip_label(n):
    sysname, body = n.get("sys") or "?", n.get("body") or ""
    if n.get("st"):
        return n["st"]
    if body and body != sysname:
        return body
    return sysname

def trip_dist(n, d):
    a, b = n.get("pos"), (d or {}).get("starpos")
    if not a or not b:
        return ""
    ly = math.dist(a, b)
    return "aquí" if ly < 0.01 else f"{ly:,.1f} al".replace(",", "X").replace(".", ",").replace("X", ".")

TRIP_SAVE = pygame.Rect(8, TOP + 2, 210, 34)
TRIP_PAGE = pygame.Rect(W - 118, TOP + 2, 110, 34)
TRIP_DEL = pygame.Rect(W - 130, H - 42, 122, 36)
TRIP_PER = 6
TAG_COL = {"XENOBIO": GREEN, "ESTACIÓN": BLUE, "A PIE": GREEN, "SRV": ORANGE, "ATERRIZADO": ORANGE,
           "PLANETA": ORANGE, "ESPACIO": DIM}

def trip_row(i):
    return pygame.Rect(8, TOP + 42 + i * 32, W - 16, 30)

def view_trip(surf, d, flags, now):
    trip["d"] = d
    L = trip["list"]
    draw_button(surf, TRIP_SAVE, "GUARDAR AQUÍ", None, F["btn"], filled=True, dim=not (d or {}).get("system"),
                lit=flash.get((128, "save"), 0) > now)
    pages = max(1, (len(L) + TRIP_PER - 1) // TRIP_PER)
    pg = trip["page"] % pages
    if pages > 1:
        draw_button(surf, TRIP_PAGE, f"PÁG {pg + 1}/{pages} >", None, F["small"])
    else:
        put(surf, F["small"], f"{len(L)} sitios", (W - 8, TOP + 12), DIM, anchor="topright")
    if not L:
        put(surf, F["btn"], "Aún no has guardado ningún sitio", (W // 2, (H + TOP) // 2 + 16), DIM, anchor="center")
        return
    for i, n in enumerate(L[pg * TRIP_PER:(pg + 1) * TRIP_PER]):
        r = trip_row(i)
        pygame.draw.rect(surf, DIM, r, 1, border_radius=4)
        put(surf, F["btn"], trip_label(n), (r.x + 6, r.y + 2), ORANGE, 290)
        tag = n.get("tag", "")
        put(surf, F["small"], tag, (r.right - 6, r.y + 3), TAG_COL.get(tag, DIM), anchor="topright")
        sub = f"{n.get('sys') or '?'}  ·  {time.strftime('%d/%m %H:%M', time.localtime(n.get('t', 0)))}"
        put(surf, F["small"], sub, (r.x + 6, r.y + 17), DIM, 330)
        put(surf, F["small"], trip_dist(n, d), (r.right - 6, r.y + 17), BLUE, anchor="topright")

def view_trip_detail(surf, d, flags, now):
    trip["d"] = d
    L, i = trip["list"], trip["sel"]
    if i is None or i >= len(L):
        ui["view"] = 128; return
    n = L[i]
    y = TOP + 4
    put(surf, F["big"], (n.get("sys") or "?").upper(), (8, y), ORANGE, W - 16); y += 28
    if n.get("st") or (n.get("body") and n.get("body") != n.get("sys")):
        put(surf, F["btn"], trip_label(n), (8, y), WHITE, W - 16); y += 22
    tag = n.get("tag", "")
    put(surf, F["small"], tag, (8, y), TAG_COL.get(tag, DIM))
    put(surf, F["small"], time.strftime("%d/%m/%Y %H:%M", time.localtime(n.get("t", 0))), (W - 8, y), DIM, anchor="topright"); y += 18
    if n.get("lat") is not None:
        put(surf, F["small"], f"lat {n['lat']:.4f}   lon {n['lon']:.4f}", (8, y), DIM); y += 18
    dist = trip_dist(n, d)
    if dist:
        put(surf, F["small"], "DISTANCIA", (8, y + 6), DIM)
        put(surf, F["big"], dist, (90, y), BLUE); y += 30
    b = (d or {}).get("bio") or {}
    here = (d or {}).get("body") and (d or {}).get("body") == n.get("body")
    if here and n.get("lat") is not None and b.get("lat") is not None and b.get("R"):
        p1, p2 = math.radians(b["lat"]), math.radians(n["lat"])
        dl = math.radians(n["lon"] - b["lon"])
        brg = math.degrees(math.atan2(math.sin(dl) * math.cos(p2),
                                      math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl))) % 360
        m = hav((b["lat"], b["lon"]), (n["lat"], n["lon"]), b["R"])
        cx, cy, r = 40, H - 40, 26
        pygame.draw.circle(surf, DIM, (cx, cy), r, 1)
        hdg = b.get("hdg")
        if hdg is not None:
            a = math.radians(brg - hdg)
            pt = lambda k, da: (cx + r * k * math.sin(a + da), cy - r * k * math.cos(a + da))
            pygame.draw.polygon(surf, GREEN, [pt(0.95, 0), pt(0.6, 2.5), (cx, cy), pt(0.6, -2.5)])
        txt = f"{m / 1000:.1f} km".replace(".", ",") if m >= 1000 else f"{m:.0f} m"
        put(surf, F["small"], "DESTINO", (76, H - 64), DIM)
        put(surf, F["big"], txt, (76, H - 50), GREEN)
        put(surf, F["small"], f"rumbo {brg:.0f}°", (76, H - 22), ORANGE)
    c, until = ui["confirm"]
    sure = c == "trip_del" and time.time() < until
    draw_button(surf, TRIP_DEL, "¿SEGURO?" if sure else "BORRAR", None, F["btn"], filled=sure)

def tap_trip(x, y):
    v, d = ui["view"], trip["d"]
    L = trip["list"]
    if v == 128:
        if TRIP_SAVE.collidepoint(x, y):
            n = trip_here(d)
            if not n["sys"]:
                set_alert("SIN DATOS DEL JUEGO", secs=2); return
            L.insert(0, n); trip_save(); trip["page"] = 0
            tap_flash((128, "save"))
            set_alert("SITIO GUARDADO", trip_label(n), col=GREEN, secs=2, kind="ok")
            return
        pages = max(1, (len(L) + TRIP_PER - 1) // TRIP_PER)
        if pages > 1 and TRIP_PAGE.collidepoint(x, y):
            trip["page"] += 1; return
        pg = trip["page"] % pages
        for i in range(TRIP_PER):
            idx = pg * TRIP_PER + i
            if idx < len(L) and trip_row(i).collidepoint(x, y):
                trip["sel"] = idx; ui["view"] = 129; return
    elif v == 129 and TRIP_DEL.collidepoint(x, y):
        c, until = ui["confirm"]
        if c == "trip_del" and time.time() < until:
            ui["confirm"] = (None, 0)
            if trip["sel"] is not None and trip["sel"] < len(L):
                L.pop(trip["sel"]); trip_save()
            ui["view"] = 128
        else:
            ui["confirm"] = ("trip_del", time.time() + 3)

# ---------- 7.4 yacimientos: zonas de mineria del planeta (Rhino) y anillos ----------
RES_COL = {"PRÍSTINAS": GREEN, "MAYORES": GREEN, "COMUNES": ORANGE, "BAJAS": RED, "AGOTADAS": RED}

def view_rings(surf, d, flags, now):
    R = (d or {}).get("rings") or {}
    if not R.get("planet"):
        put(surf, F["btn"], "Acércate a un planeta", (W // 2, (H + TOP) // 2), DIM, anchor="center"); return
    y = TOP + 4
    put(surf, F["big"], R["planet"].upper(), (8, y), ORANGE, W - 150)
    if R.get("reserve"):
        put(surf, F["small"], "RESERVAS", (W - 8, y), DIM, anchor="topright")
        put(surf, F["btn"], R["reserve"], (W - 8, y + 12), RES_COL.get(R["reserve"], ORANGE), anchor="topright")
    y += 34
    sig = R.get("signals") or []
    put(surf, F["small"], "SEÑALES DEL PLANETA", (8, y), DIM); y += 15
    if not sig:
        put(surf, F["small"], "sin datos: escanea el planeta (FSS) o mapéalo con la sonda (DSS)", (8, y), DIM, W - 16); y += 20
    else:
        x = 8
        for name, c in sig:
            low = name.lower()
            col = GREEN if ("bio" in low) else BLUE if ("geo" in low) else ORANGE
            txt = f"{name} x{c}"
            w_ = F["btn"].size(txt)[0] + 14
            if x + w_ > W - 6:
                x = 8; y += 24
            pygame.draw.rect(surf, col, (x, y, w_ - 4, 21), 1, border_radius=4)
            put(surf, F["btn"], txt, (x + 5, y + 2), col)
            x += w_
        y += 28
    rings = R.get("rings") or []
    if not rings:
        return
    pygame.draw.line(surf, DIM, (8, y), (W - 8, y)); y += 4
    here = R.get("here") or ""
    for name, cls, hs in rings:
        if y > H - 40:
            break
        inside = bool(here) and here.endswith(name)
        r = pygame.Rect(6, y, W - 12, 26 + 20 * max(1, (len(hs or []) + 1) // 2))
        pygame.draw.rect(surf, GREEN if inside else DIM, r, 1, border_radius=5)
        put(surf, F["btn"], name.upper(), (r.x + 8, r.y + 4), ORANGE, 110)
        put(surf, F["small"], cls, (r.x + 120, r.y + 8), BLUE, 160)
        if inside:
            put(surf, F["small"], "ESTÁS AQUÍ", (r.right - 8, r.y + 8), GREEN, anchor="topright")
        yy = r.y + 26
        if not hs:
            put(surf, F["small"], "sin sondear: usa la sonda de superficie en el anillo", (r.x + 8, yy + 2), DIM, r.w - 16)
        else:
            for k, (m, c) in enumerate(hs):
                put(surf, F["btn"], f"{m}  x{c}", (r.x + 8 + (k % 2) * (r.w // 2), yy + (k // 2) * 20),
                    GREEN if c >= 2 else WHITE, r.w // 2 - 12)
        y = r.bottom + 6

# ---------- 3 navegacion: ficha del destino dentro del sistema ----------
# ---------- 3 navegacion: cara SISTEMA (politica) ----------
pol = {"sys": None, "until": 0}

def nav_show_pol(d, now):
    sysn = (d or {}).get("system")
    if sysn and sysn != pol["sys"]:
        if pol["sys"] is not None:
            pol["until"] = now + 20
            pol["t0"] = now
        pol["sys"] = sysn
    if NAVBIG[0]:
        return False
    return bool(ui.get("navtab")) or now < pol["until"]

def view_pol(surf, d, flags, now):
    S = (d or {}).get("sysinfo") or {}
    if not S.get("faction") and not S.get("gov"):
        put(surf, F["btn"], "Sin datos del sistema", (W // 2, (H + TOP) // 2), DIM, anchor="center"); return
    y = TOP + 4
    sec = (S.get("sec") or "").lower()
    seccol = GREEN if "alta" in sec or "high" in sec else ORANGE if "media" in sec or "medium" in sec else RED
    pop = S.get("pop")
    popt = (f"{pop / 1e9:.1f} mil M hab." if pop >= 1e9 else f"{pop / 1e6:.1f} M hab." if pop >= 1e6 else f"{pop:,} hab.").replace(".", ",") if pop else ""
    tags = [(S.get("gov"), ORANGE), (S.get("alleg"), BLUE), (S.get("sec"), seccol), (S.get("econ"), WHITE), (popt, DIM)]
    x = 6
    for t, col in tags:
        if not t:
            continue
        w_ = F["small"].size(t)[0] + 12
        if x + w_ > W - 4:
            x = 6; y += 20
        pygame.draw.rect(surf, col, (x, y, w_ - 4, 17), 1, border_radius=3)
        put(surf, F["small"], t, (x + 4, y + 2), col)
        x += w_
    y += 24
    put(surf, F["small"], "CONTROLA", (6, y + 5), DIM)
    put(surf, F["btn"], S.get("faction") or "?", (96, y + 1), ORANGE, 280)
    if S.get("fstate"):
        put(surf, F["small"], S["fstate"], (W - 6, y + 5), RED if S["fstate"] in ("GUERRA", "GUERRA CIVIL", "BLOQUEO", "DISTURBIOS", "ATAQUE PIRATA") else GREEN, anchor="topright")
    y += 24
    put(surf, F["small"], "POWERPLAY", (6, y + 4), DIM)
    if S.get("pp"):
        put(surf, F["btn"], S["pp"], (96, y), BLUE, 230)
        put(surf, F["small"], S.get("ppstate") or "", (W - 6, y + 4), BLUE, anchor="topright")
    else:
        rivals = [p for p in S.get("powers") or []]
        put(surf, F["small"], ("en disputa: " + ", ".join(rivals)) if rivals else "sin potencia", (96, y + 4), DIM, W - 106)
    y += 22
    pygame.draw.line(surf, DIM, (6, y), (W - 6, y)); y += 3
    for name, infl, st_, rep in (S.get("facs") or [])[:6]:
        if y > H - 40:
            break
        put(surf, F["small"], name, (6, y + 3), ORANGE if name == S.get("faction") else WHITE, 190)
        bx = pygame.Rect(200, y + 4, 110, 11)
        pygame.draw.rect(surf, DIM, bx, 1)
        pygame.draw.rect(surf, BLUE, (bx.x + 2, bx.y + 2, int((bx.w - 4) * min(100, infl) / 100), bx.h - 4))
        put(surf, F["small"], f"{infl:.0f}%", (342, y + 3), WHITE, anchor="topright")
        put(surf, F["small"], st_ or "", (348, y + 3), RED if st_ in ("GUERRA", "GUERRA CIVIL", "BLOQUEO") else DIM, 80)
        if rep is not None:
            put(surf, F["small"], f"{rep:+.0f}", (W - 6, y + 3), GREEN if rep >= 35 else RED if rep <= -35 else ORANGE, anchor="topright")
        y += 19
    if S.get("st_name"):
        pygame.draw.line(surf, DIM, (6, H - 22), (W - 6, H - 22))
        t = f"{S['st_name']} · {S.get('st_faction') or '?'} · {S.get('st_gov') or ''}"
        put(surf, F["small"], t, (6, H - 18), ORANGE, W - 12)

def nav_strip(surf, d):
    S = (d or {}).get("sysinfo") or {}
    parts = [S.get("gov"), S.get("alleg"), S.get("sec"), S.get("fstate")]
    t = " · ".join(p for p in parts if p)
    if t:
        sec = (S.get("sec") or "").lower()
        col = GREEN if "alta" in sec or "high" in sec else ORANGE if "media" in sec or "medium" in sec else RED
        pygame.draw.line(surf, DIM, (8, H - 22), (W - 8, H - 22))
        put(surf, F["small"], t, (8, H - 18), col, W - 16)

# ---------- 3 navegacion: cara POWERPLAY ----------
def view_pp(surf, d, flags, now):
    S = (d or {}).get("sysinfo") or {}
    me = (d or {}).get("ppme") or {}
    y = TOP + 4
    put(surf, F["small"], "POWERPLAY DEL SISTEMA", (8, y), DIM)
    if S.get("ppstate"):
        put(surf, F["small"], S["ppstate"], (W - 8, y), BLUE, anchor="topright")
    y += 16
    pp, mine = S.get("pp"), me.get("power")
    if pp:
        put(surf, F["big"], pp.upper(), (8, y), BLUE, W - 130)
        if mine:
            put(surf, F["btn"], "TU POTENCIA" if pp == mine else "RIVAL", (W - 8, y + 4), GREEN if pp == mine else RED, anchor="topright")
        y += 30
        prog = S.get("pp_prog")
        if prog is not None:
            put(surf, F["small"], "CONTROL", (8, y + 2), DIM)
            bx = pygame.Rect(80, y, 300, 16)
            pygame.draw.rect(surf, DIM, bx, 1)
            pygame.draw.rect(surf, BLUE, (bx.x + 2, bx.y + 2, int((bx.w - 4) * max(0, min(1, prog))), bx.h - 4))
            put(surf, F["btn"], f"{prog * 100:.0f}%", (W - 8, y - 2), WHITE, anchor="topright")
            y += 24
        ri, un = S.get("pp_reinf"), S.get("pp_under")
        if ri is not None or un is not None:
            ri, un = ri or 0, un or 0
            tot = max(1, ri + un)
            put(surf, F["small"], "REFUERZO", (8, y + 2), DIM)
            put(surf, F["btn"], f"{ri:,}".replace(",", "."), (150, y - 1), GREEN, anchor="topright")
            put(surf, F["small"], "SABOTAJE", (250, y + 2), DIM)
            put(surf, F["btn"], f"{un:,}".replace(",", "."), (W - 8, y - 1), RED, anchor="topright")
            y += 20
            bx = pygame.Rect(8, y, W - 16, 10)
            pygame.draw.rect(surf, RED, bx)
            pygame.draw.rect(surf, GREEN, (bx.x, bx.y, int(bx.w * ri / tot), bx.h))
            y += 18
    else:
        put(surf, F["big"], "SIN POTENCIA", (8, y), DIM); y += 30
    conf = S.get("pp_conf") or []
    if conf:
        put(surf, F["small"], "CONQUISTA EN CURSO (100% = toma el control)", (8, y), DIM); y += 16
        for power, cp in conf[:4]:
            col = GREEN if power == mine else ORANGE
            put(surf, F["small"], power, (8, y + 1), col, 170)
            bx = pygame.Rect(184, y + 2, 220, 12)
            pygame.draw.rect(surf, DIM, bx, 1)
            pygame.draw.rect(surf, col, (bx.x + 2, bx.y + 2, int((bx.w - 4) * max(0, min(1, cp))), bx.h - 4))
            put(surf, F["small"], f"{cp * 100:.0f}%", (W - 8, y + 1), WHITE, anchor="topright")
            y += 18
    elif S.get("powers") and not pp:
        put(surf, F["small"], "presentes: " + ", ".join(S["powers"]), (8, y), DIM, W - 16); y += 18
    pygame.draw.line(surf, DIM, (8, H - 44), (W - 8, H - 44))
    if mine:
        put(surf, F["small"], "TU POTENCIA", (8, H - 40), DIM)
        put(surf, F["btn"], mine, (100, H - 43), GREEN if pp == mine else ORANGE, 200)
        put(surf, F["small"], f"RANGO {me.get('rank', '?')}", (W - 8, H - 40), WHITE, anchor="topright")
        m = me.get("merits")
        put(surf, F["small"], f"Méritos: {m:,}".replace(",", ".") if m is not None else "Méritos: ?", (8, H - 20), ORANGE)
        if me.get("session"):
            put(surf, F["small"], f"+{me['session']:,} en esta sesión".replace(",", "."), (W - 8, H - 20), GREEN, anchor="topright")
    else:
        put(surf, F["small"], "No estás alineado con ninguna potencia", (8, H - 30), DIM)

NAVBIG = [False]

def view_navbig(surf, d, flags, now):
    """Pantalla grande: 10 s sistema, 5 s powerplay (si hay), luego ruta/destino."""
    nav_show_pol(d, now)
    S = (d or {}).get("sysinfo") or {}
    el = now - pol.get("t0", 0)
    if el < 10:
        return view_pol(surf, d, flags, now)
    if el < 15 and (S.get("pp") or S.get("pp_conf") or S.get("powers")):
        return view_pp(surf, d, flags, now)
    NAVBIG[0] = True
    try:
        view_navx(surf, d, flags, now)
    finally:
        NAVBIG[0] = False

def view_navx(surf, d, flags, now):
    if ui.get("navtab") == 2 and not NAVBIG[0]:
        return view_pp(surf, d, flags, now)
    if nav_show_pol(d, now):
        return view_pol(surf, d, flags, now)
    D = (d or {}).get("dest")
    if not D or not D.get("name"):
        nav = (d or {}).get("nav") or {}
        if not nav.get("target") and not (d or {}).get("route"):
            return view_pol(surf, d, flags, now)
        view_nav(surf, d, flags, now)
        nav_strip(surf, d)
        return
    y = TOP + 4
    arrived = (d or {}).get("body") == D["name"]
    put(surf, F["small"], "DESTINO EN EL SISTEMA", (8, y), DIM)
    if arrived:
        put(surf, F["btn"], "HAS LLEGADO", (W - 8, y - 2), GREEN, anchor="topright")
    elif flags & 16:
        put(surf, F["btn"], "EN RUTA", (W - 8, y - 2), BLUE if int(now * 2) % 2 else WHITE, anchor="topright")
    y += 16
    put(surf, F["big"], D["name"].upper(), (8, y), ORANGE, W - 16); y += 30
    if D.get("cls"):
        put(surf, F["btn"], D["cls"], (8, y), BLUE, 280)
    if D.get("dist") is not None:
        put(surf, F["btn"], f"{D['dist']:,} ls".replace(",", "."), (W - 8, y), WHITE, anchor="topright")
    if D.get("cls") or D.get("dist") is not None:
        y += 26
    tags = []
    if D.get("land") is not None:
        tags.append(("ATERRIZABLE", GREEN) if D["land"] else ("NO ATERRIZABLE", DIM))
    g = D.get("g")
    if g is not None:
        tags.append((f"{g:.2f} G".replace(".", ","), RED if g >= 2 else ORANGE if g >= 1.5 else WHITE))
    if D.get("rings"):
        tags.append(("ANILLOS", BLUE))
    if D.get("tf"):
        tags.append(("TERRAFORMABLE", GREEN))
    if D.get("first"):
        tags.append(("1º DESCUBRIMIENTO", GREEN))
    if D.get("mapped"):
        tags.append(("MAPEADO", BLUE))
    for name, c in D.get("signals") or []:
        low = name.lower()
        tags.append((f"{name} x{c}", GREEN if "bio" in low else BLUE if "geo" in low else ORANGE))
    x = 8
    for t, col in tags:
        w_ = F["btn"].size(t)[0] + 14
        if x + w_ > W - 6:
            x = 8; y += 26
        pygame.draw.rect(surf, col, (x, y, w_ - 4, 22), 1, border_radius=4)
        put(surf, F["btn"], t, (x + 5, y + 2), col)
        x += w_
    if tags:
        y += 30
    if D.get("value"):
        put(surf, F["small"], "VALOR DE DATOS", (8, y + 4), DIM)
        put(surf, F["big"], f"~ {cr(D['value'])} cr", (130, y), ORANGE)
    b = (d or {}).get("bio") or {}
    if D.get("lat") is not None and b.get("lat") is not None and b.get("R") and (d or {}).get("body") == D.get("sbody"):
        p1, p2 = math.radians(b["lat"]), math.radians(D["lat"])
        dl = math.radians(D["lon"] - b["lon"])
        brg = math.degrees(math.atan2(math.sin(dl) * math.cos(p2),
                                      math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl))) % 360
        m = hav((b["lat"], b["lon"]), (D["lat"], D["lon"]), b["R"])
        cx, cy, rr = 34, H - 48, 22
        pygame.draw.circle(surf, DIM, (cx, cy), rr, 1)
        hdg = b.get("hdg")
        if hdg is not None:
            a = math.radians(brg - hdg)
            pt = lambda k, da: (cx + rr * k * math.sin(a + da), cy - rr * k * math.cos(a + da))
            pygame.draw.polygon(surf, GREEN, [pt(0.95, 0), pt(0.6, 2.5), (cx, cy), pt(0.6, -2.5)])
        txt = f"{m / 1000:.1f} km".replace(".", ",") if m >= 1000 else f"{m:.0f} m"
        put(surf, F["small"], "DISTANCIA AL DESTINO", (66, H - 70), DIM)
        put(surf, F["big"], txt, (66, H - 56), GREEN)
        put(surf, F["btn"], f"rumbo {brg:.0f}°", (W - 8, H - 52), ORANGE, anchor="topright")
    src = D.get("src")
    put(surf, F["small"], f"datos: {src}" if src else "sin datos: no escaneado (o es una estación/señal)",
        (8, H - 16), DIM if src else ORANGE)

# ---------- 8 estacion: a los 15 s de atracar, ficha de la estacion y facciones ----------
stdock = {"key": None, "t": 0}

def view_stationx(surf, d, flags, now):
    st = (d or {}).get("station") or {}
    key = (st.get("name"), st.get("status"))
    if st.get("status") == "ATRACADO":
        if stdock["key"] != key:
            stdock.update(key=key, t=now)
        if now - stdock["t"] >= 15:
            S = (d or {}).get("sysinfo") or {}
            stpp = S.get("pp") or S.get("pp_conf") or S.get("powers")
            if stpp and (now - stdock["t"] - 15) % 15 >= 10:
                return view_pp(surf, d, flags, now)
            return view_station_info(surf, d, st)
    else:
        stdock["key"] = None
    return view_station(surf, d, flags, now)

def view_station_info(surf, d, st):
    S = (d or {}).get("sysinfo") or {}
    y = TOP + 4
    put(surf, F["big"], (st.get("name") or "?").upper(), (8, y), ORANGE, W - 16); y += 27
    put(surf, F["small"], ST_TYPE.get(st.get("type"), st.get("type") or ""), (8, y), DIM, 200)
    put(surf, F["small"], "ATRACADO", (220, y), BLUE)
    if st.get("dist"):
        put(surf, F["small"], f"{st['dist']:,.0f} ls de la estrella".replace(",", "."), (W - 8, y), DIM, anchor="topright")
    y += 18
    fac = st.get("faction") or S.get("st_faction")
    put(surf, F["small"], "FACCIÓN", (8, y + 4), DIM)
    put(surf, F["btn"], fac or "?", (80, y), ORANGE, 290)
    fst = S.get("st_fstate")
    if fst:
        put(surf, F["small"], fst, (W - 8, y + 4), RED if fst in ("GUERRA", "GUERRA CIVIL", "BLOQUEO", "DISTURBIOS") else GREEN, anchor="topright")
    y += 22
    gv = " · ".join(x for x in (S.get("st_gov"), S.get("st_alleg"), st.get("economy")) if x)
    if gv:
        put(surf, F["small"], gv, (80, y), WHITE, W - 88); y += 18
    srv = set(st.get("services") or [])
    tags = [t for k, t in SERVICES if k in srv]
    tx = 8
    for t in tags:
        w_ = F["small"].size(t)[0] + 10
        if tx + w_ > W - 4:
            tx = 8; y += 18
        pygame.draw.rect(surf, DIM, (tx, y, w_ - 4, 16), 1, border_radius=3)
        put(surf, F["small"], t, (tx + 3, y + 2), ORANGE)
        tx += w_
    if tags:
        y += 22
    facs = S.get("facs") or []
    if facs and y < H - 36:
        pygame.draw.line(surf, DIM, (8, y), (W - 8, y)); y += 3
        put(surf, F["small"], "FACCIONES DEL SISTEMA", (8, y), DIM); y += 15
        for name, infl, st_, rep in facs:
            if y > H - 18:
                break
            put(surf, F["small"], name, (8, y), ORANGE if name == fac else WHITE, 200)
            bx = pygame.Rect(212, y + 1, 100, 10)
            pygame.draw.rect(surf, DIM, bx, 1)
            pygame.draw.rect(surf, BLUE, (bx.x + 2, bx.y + 2, int((bx.w - 4) * min(100, infl) / 100), bx.h - 4))
            put(surf, F["small"], f"{infl:.0f}%", (346, y), WHITE, anchor="topright")
            put(surf, F["small"], st_ or "", (352, y), RED if st_ in ("GUERRA", "GUERRA CIVIL", "BLOQUEO") else DIM, 80)
            if rep is not None:
                put(surf, F["small"], f"{rep:+.0f}", (W - 8, y), GREEN if rep >= 35 else RED if rep <= -35 else ORANGE, anchor="topright")
            y += 17

# ---------- 12.4 ajustes: salir, reiniciar, apagar, preferencias ----------
POWER = [("1", "SALIR"), ("2", "REINICIAR"), ("3", "APAGAR"), ("4", "PREFERENCIAS"), ("5", "VERSIONES"), ("6", "BORDES"), ("7", "ICONOS")]

# ---------- 11 sesion: recompensas pendientes de cobrar ----------
def view_session2(surf, d, flags, now):
    view_session(surf, d, flags, now)
    s_ = (d or {}).get("sess") or {}
    if s_.get("pending"):
        put(surf, F["small"], "RECOMPENSAS SIN COBRAR", (8, H - 54), DIM)
        put(surf, F["big"], f"{cr(s_['pending'])} cr", (8, H - 40), RED)
        put(surf, F["small"], f"{s_.get('pending_n', 0)} derribos · cóbralas en una estación", (8, H - 16), DIM, 300)

# ---------- registro de combate (pantalla grande, tablero COMBATE) y escudos caidos ----------
def view_combatlog(surf, d, flags, now):
    C = (d or {}).get("combat") or {}
    y = TOP + 4
    sd = C.get("sd")
    put(surf, F["small"], "ESCUDOS", (8, y + 6), DIM)
    if sd:
        el = int(now - sd)
        put(surf, F["big"], f"CAÍDOS  {el // 60:02d}:{el % 60:02d}", (80, y), RED if int(now * 2) % 2 else WHITE)
    else:
        put(surf, F["big"], "ACTIVOS" if flags & 8 else "SIN ESCUDOS", (80, y), BLUE if flags & 8 else DIM)
    y += 32
    pygame.draw.line(surf, DIM, (8, y), (W - 8, y)); y += 4
    kills = C.get("kills") or []
    put(surf, F["small"], "ÚLTIMOS DERRIBOS", (8, y), DIM); y += 16
    if not kills:
        put(surf, F["small"], "ninguno en esta sesión", (8, y), DIM); y += 18
    for tgt, rew, kind in kills[:6]:
        tag, col = {"R": ("RECOMPENSA", ORANGE), "B": ("BONO", BLUE), "P": ("PvP", RED)}.get(kind, ("", DIM))
        put(surf, F["btn"], tgt, (8, y), WHITE, 230)
        put(surf, F["small"], tag, (250, y + 4), col)
        if rew:
            put(surf, F["btn"], f"+{cr(rew)}", (W - 8, y), GREEN, anchor="topright")
        y += 22
    bonds = C.get("bonds") or []
    if bonds and y < H - 60:
        pygame.draw.line(surf, DIM, (8, y + 2), (W - 8, y + 2)); y += 6
        put(surf, F["small"], "BONOS DE GUERRA POR FACCIÓN", (8, y), DIM); y += 16
        for fac, v in bonds:
            if y > H - 38:
                break
            put(surf, F["small"], fac, (8, y), BLUE, 300)
            put(surf, F["btn"], f"{cr(v)} cr", (W - 8, y - 3), BLUE, anchor="topright"); y += 18
    s_ = (d or {}).get("sess") or {}
    if s_.get("pending"):
        put(surf, F["small"], f"RECOMPENSAS SIN COBRAR: {cr(s_['pending'])} cr ({s_.get('pending_n', 0)})", (8, H - 16), RED, W - 16)

def view_combatx(surf, d, flags, now):
    view_combat(surf, d, flags, now)
    sd = ((d or {}).get("combat") or {}).get("sd")
    if sd:
        el = int(now - sd)
        r = pygame.Rect(W - 190, TOP + 34, 182, 22)
        pygame.draw.rect(surf, BLACK, r)
        pygame.draw.rect(surf, RED, r, 2, border_radius=4)
        put(surf, F["btn"], f"ESCUDOS  {el // 60:02d}:{el % 60:02d}", r.center, RED if int(now * 2) % 2 else WHITE, anchor="center")

# ---------- 12.4.5 versiones: resumen de cambios ----------
CHANGES = [
    ("base", "Panel de 12 botones, teclado USB y estado del juego por red"),
    ("base", "7.3 Xenobiología: muestras, distancia, valor de especies y x5"),
    ("base", "Recogida de combustible en naranja y sobrecalentamiento"),
    ("base", "Brújula para volver a la nave"),
    ("base", "EN VIVO como inicio (nave/a pie/SRV) con botón MENÚ"),
    ("base", "7.1 Exploración con EDSM y páginas"),
    ("base", "Avisos: combustible en ruta, neutrones y gravedad"),
    ("base", "12.5 Materiales, 12.6 Portanaves y 12.7 Mercado"),
    ("0.10", "Versión en la pantalla del reloj"),
    ("0.11", "12.8 Notas de viaje con brújula al destino"),
    ("0.12", "Foto del CMDR en reloj y arranque"),
    ("0.13", "Estilo CABINA (botón ESTILO en Sesión)"),
    ("0.14", "Botón ESTILO más grande"),
    ("0.15", "Pantalla grande HDMI: tablero de 4 cuadros"),
    ("0.16", "Viaje con SISTEMA y Combate con PIPS"),
    ("0.17", "Aproximación/Superficie y 7.4 Yacimientos"),
    ("0.18", "Tablero especial con el Rhino"),
    ("0.19", "Bodega del vehículo"),
    ("0.20", "Ficha del destino en Navegación"),
    ("0.21", "Altitud para desplegar el Rhino"),
    ("0.22", "RHINO en la pantalla 5"),
    ("0.23", "Pantalla 5: SRV / RHINO / A PIE"),
    ("0.24", "Lista de minerales de la bodega del Rhino"),
    ("0.25", "Combustible y escudos del Rhino"),
    ("0.26", "Superficie con Materiales y Minería"),
    ("0.27", "Minería en modo Rhino"),
    ("0.28", "Avisos de nave (el juego no los registra)"),
    ("0.29", "RHINO A BORDO"),
    ("0.30", "Franja RHINO PREPARADO"),
    ("0.31", "Franja de altura: 100-41 / 40-7 / <7 m"),
    ("0.32", "Brújula a puertos planetarios"),
    ("0.33", "Tablero ATRAQUE con la plataforma"),
    ("0.34", "Navegación: cara SISTEMA (política)"),
    ("0.35", "Estación: ficha y facciones a los 15 s"),
    ("0.36", "12.4 Salir, reiniciar y apagar"),
    ("0.37", "Navegación: cara POWERPLAY"),
    ("0.38", "Grande: 10 s sistema y 5 s Powerplay"),
    ("0.39", "Estación alterna ficha y Powerplay"),
    ("0.40", "Hallazgos, Códice, buscados, misiones, fin de sesión"),
    ("0.41", "A pie: peligros, mochila, asentamientos, delitos, taxi"),
    ("0.42", "Combate: escudos, derribos, bonos, rebuy, PvP"),
    ("0.43", "Ficha de llegada y sistema sin explorar"),
    ("0.44", "Esta lista de versiones"),
    ("0.45", "Estilo CABINA también en la pantalla grande"),
    ("0.46", "Bordes de situación por riesgo y botón BORDES"),
    ("0.47", "IP de la Pi en la pantalla del reloj"),
    ("0.48", "Brújula NAVE: corrección automática y botón NAVE AQUÍ"),
    ("0.49", "Menú principal con iconos (botón ICONOS)"),
    ("0.50", "Exploración: escaneo, ruta, diario 7.5, riesgo y distancias"),
    ("0.51", "7.6 Alienígenas: thargoides y guardianes, señales y guerra"),
    ("0.52", "Amigos y ala: avisos y cara AMIGOS en Sesión"),
]

def view_changelog(surf, d, flags, now):
    per = 11
    rows = list(reversed(CHANGES))
    pages = max(1, (len(rows) + per - 1) // per)
    pg = ui.get("page1245", 0) % pages
    y = TOP + 4
    put(surf, F["small"], f"{len(CHANGES)} cambios  ·  lo más nuevo primero", (8, y), DIM)
    put(surf, F["small"], f"pág {pg + 1}/{pages}  (toca)", (W - 8, y), DIM, anchor="topright")
    y += 18
    for ver, txt in rows[pg * per:(pg + 1) * per]:
        put(surf, F["small"], "v" + ver if ver != "base" else "base", (8, y + 2), GREEN if ver != "base" else DIM)
        put(surf, F["btn"], txt, (62, y), ORANGE, W - 70)
        y += 22

# ---------- menu principal con iconos (12.4 -> 7 ICONOS) ----------
ICONS_FILE = "/home/ortem/iconos.txt"
try:
    ICONS_ON = [open(ICONS_FILE).read().strip() == "si"]
except OSError:
    ICONS_ON = [False]

def icons_toggle():
    ICONS_ON[0] = not ICONS_ON[0]
    try:
        with open(ICONS_FILE, "w") as f:
            f.write("si" if ICONS_ON[0] else "no")
    except OSError:
        pass

def menu_icon(s, i, c, cx, cy):
    L = lambda a, b, w=2: pygame.draw.line(s, c, a, b, w)
    C = lambda p_, r, w=2: pygame.draw.circle(s, c, p_, r, w)
    R = lambda x, y, w, h, wd=2: pygame.draw.rect(s, c, (cx + x, cy + y, w, h), wd)
    if i == 0:
        R(-12, 6, 24, 6); L((cx, cy + 6), (cx, cy - 8), 3); C((cx, cy - 11), 5, 0)
    elif i == 1:
        for j, h in enumerate((10, 16, 8)):
            R(-13 + j * 10, 10 - h, 7, h, 0)
    elif i == 2:
        C((cx, cy), 13); pygame.draw.polygon(s, c, [(cx, cy - 11), (cx + 4, cy), (cx, cy + 11), (cx - 4, cy)], 0)
    elif i == 3:
        R(-12, -9, 24, 18); L((cx - 12, cy - 3), (cx + 12, cy - 3)); L((cx, cy - 9), (cx, cy - 3))
    elif i == 4:
        R(-14, -6, 28, 9); C((cx - 8, cy + 7), 4); C((cx + 8, cy + 7), 4)
    elif i == 5:
        C((cx, cy), 11); L((cx - 15, cy), (cx - 5, cy)); L((cx + 5, cy), (cx + 15, cy))
        L((cx, cy - 15), (cx, cy - 5)); L((cx, cy + 5), (cx, cy + 15))
    elif i == 6:
        C((cx, cy), 8, 0); pygame.draw.ellipse(s, c, (cx - 16, cy - 4, 32, 8), 2)
    elif i == 7:
        pygame.draw.polygon(s, c, [(cx, cy - 13), (cx + 13, cy), (cx, cy + 13), (cx - 13, cy)], 2); R(-5, -2, 10, 4, 0)
    elif i == 8:
        pygame.draw.polygon(s, c, [(cx, cy - 12), (cx + 11, cy + 10), (cx, cy + 5), (cx - 11, cy + 10)], 2)
    elif i == 9:
        pygame.draw.polygon(s, c, [(cx - 12, cy + 2), (cx - 5, cy - 9), (cx + 6, cy - 7), (cx + 12, cy + 3),
                                   (cx + 3, cy + 11), (cx - 8, cy + 9)], 2); L((cx - 3, cy - 1), (cx + 4, cy + 4))
    elif i == 10:
        C((cx, cy), 12); L((cx, cy), (cx, cy - 8)); L((cx, cy), (cx + 6, cy + 3))
    elif i == 11:
        C((cx, cy), 6)
        for a in range(8):
            r = math.radians(a * 45)
            L((cx + 9 * math.cos(r), cy + 9 * math.sin(r)), (cx + 13 * math.cos(r), cy + 13 * math.sin(r)), 3)

def view_menux(surf, d, flags, now):
    if not ICONS_ON[0]:
        return view_menu(surf, d, flags, now)
    for i in range(12):
        name = MENU.get(i + 1)
        r = grid(i)
        draw_button(surf, r, "", None, F["small"], lit=flash.get((0, i), 0) > now, dim=name is None)
        col = DIM if name is None else ORANGE
        menu_icon(surf, i, col, r.centerx, r.y + int(r.h * 0.38))
        put(surf, F["small"], f"{i + 1} {name or 'vacío'}", (r.centerx, r.bottom - 18), col, r.w - 8, anchor="midtop")

# ---------- 7.5 diario de exploracion ----------
def view_diary(surf, d, flags, now):
    X = (d or {}).get("exdiary") or {}
    y = TOP + 6
    secs = int(now - (X.get("start") or now))
    put(surf, F["small"], f"SESIÓN DE EXPLORACIÓN · {secs // 3600}h {secs % 3600 // 60:02d}m", (8, y), DIM); y += 18
    rows = [("SISTEMAS VISITADOS", X.get("systems", 0), WHITE), ("AÑOS LUZ", X.get("ly", 0), WHITE),
            ("CUERPOS ESCANEADOS", X.get("scanned", 0), WHITE), ("1º DESCUBRIMIENTOS", X.get("first", 0), GREEN),
            ("CUERPOS MAPEADOS", X.get("mapped", 0), WHITE), ("1º MAPEADOS", X.get("first_mapped", 0), GREEN),
            ("MUESTRAS BIO", X.get("bio", 0), WHITE)]
    for k, (lab, val, col) in enumerate(rows):
        x0 = 8 if k % 2 == 0 else W // 2 + 4
        put(surf, F["small"], lab, (x0, y + 5), DIM)
        put(surf, F["big"], f"{val:,}".replace(",", "."), (x0 + W // 2 - 20, y), col, anchor="topright")
        if k % 2 == 1:
            y += 28
    y += 30
    pygame.draw.line(surf, DIM, (8, y), (W - 8, y)); y += 6
    tot = (X.get("unsold") or 0) + (X.get("unsold_bio") or 0)
    put(surf, F["small"], "SIN VENDER (exploración + bio)", (8, y + 6), DIM)
    put(surf, F["big"], f"{cr(tot)} cr", (W - 8, y), RED if tot >= 50e6 else ORANGE, anchor="topright"); y += 32
    if X.get("dsol") is not None:
        put(surf, F["small"], "DISTANCIA A SOL", (8, y + 4), DIM)
        put(surf, F["btn"], f"{X['dsol']:,.0f} al".replace(",", "."), (W - 8, y), BLUE, anchor="topright"); y += 22
    if X.get("dst") is not None:
        put(surf, F["small"], f"A LA ÚLTIMA ESTACIÓN ({X.get('stname') or '?'})", (8, y + 4), DIM, 330)
        put(surf, F["btn"], f"{X['dst']:,.0f} al".replace(",", "."), (W - 8, y), BLUE, anchor="topright")

# ---------- 7.6 alienigenas: thargoides y guardianes (toca para cambiar) ----------
TGCOL = (120, 230, 120)

def view_alien(surf, d, flags, now):
    A = (d or {}).get("alien") or {}
    tab = ui.get("alientab", 0)
    for i, t in enumerate(("THARGOIDES", "GUARDIANES")):
        r = pygame.Rect(4 + i * (W // 2), TOP + 2, W // 2 - 8, 26)
        on = tab == i
        pygame.draw.rect(surf, (TGCOL if i == 0 else BLUE) if on else DIM, r, 0 if on else 1, border_radius=4)
        put(surf, F["btn"], t, r.center, BLACK if on else DIM, anchor="center")
    y = TOP + 36
    if tab == 0:
        w = A.get("tgwar")
        if w:
            put(surf, F["small"], "GUERRA EN EL SISTEMA", (8, y + 4), DIM)
            put(surf, F["big"], w["state"], (180, y), RED if w["state"] in ("INVASIÓN", "CONTROLADO", "BASTIÓN") else ORANGE)
            y += 28
            pr = w.get("progress")
            if pr is not None:
                bx = pygame.Rect(8, y, W - 90, 14)
                pygame.draw.rect(surf, DIM, bx, 1)
                pygame.draw.rect(surf, TGCOL, (bx.x + 2, bx.y + 2, int((bx.w - 4) * max(0, min(1, pr))), bx.h - 4))
                put(surf, F["btn"], f"{pr * 100:.0f}%", (W - 8, y - 4), WHITE, anchor="topright"); y += 20
            extra = " · ".join(x for x in (f"puertos restantes {w['ports']}" if w.get("ports") else "", str(w.get("time") or "")) if x)
            if extra:
                put(surf, F["small"], extra, (8, y), DIM, W - 16); y += 18
        else:
            put(surf, F["btn"], "Sistema sin guerra thargoide", (8, y), GREEN); y += 26
        put(surf, F["small"], "DERRIBOS THARGOIDES (sesión)", (8, y + 4), DIM)
        put(surf, F["btn"], f"{A.get('tgk', 0)}  ·  {cr(A.get('tgb', 0))} cr", (W - 8, y), TGCOL, anchor="topright"); y += 26
        rows = A.get("tg") or []
        title, col = "MATERIALES THARGOIDES", TGCOL
    else:
        bp = A.get("bp") or {}
        put(surf, F["small"], "PLANOS GUARDIANES", (8, y), DIM); y += 16
        for k, (lab, key) in enumerate((("MÓDULO", "module"), ("ARMA", "weapon"), ("NAVE", "vessel"))):
            x0 = 8 + k * (W // 3)
            put(surf, F["small"], lab, (x0, y + 6), DIM)
            put(surf, F["big"], str(bp.get(key, 0)), (x0 + W // 3 - 30, y), BLUE, anchor="topright")
        y += 32
        rows = A.get("gd") or []
        title, col = "MATERIALES Y DATOS GUARDIANES", BLUE
    pygame.draw.line(surf, DIM, (8, y), (W - 8, y)); y += 4
    put(surf, F["small"], title, (8, y), DIM); y += 16
    if not rows:
        put(surf, F["small"], "ninguno", (8, y), DIM)
    for k, (n, c) in enumerate(rows):
        cx, cy = (8 if k % 2 == 0 else W // 2 + 4), y + (k // 2) * 18
        if cy > H - 18:
            break
        put(surf, F["small"], n, (cx, cy), WHITE, W // 2 - 50)
        put(surf, F["small"], str(c), (cx + W // 2 - 14, cy), col, anchor="topright")

# ---------- 11 sesion: cara AMIGOS (toca para cambiar) ----------
def view_friends(surf, d, flags, now):
    Fr = (d or {}).get("friends") or {}
    on, off, wg = Fr.get("on") or [], Fr.get("off") or [], Fr.get("wing") or []
    y = TOP + 4
    put(surf, F["small"], f"AMIGOS CONECTADOS ({len(on)})", (8, y), DIM)
    put(surf, F["small"], "toca para volver a SESIÓN", (W - 8, y), DIM, anchor="topright"); y += 16
    if not on:
        put(surf, F["btn"], "ninguno", (8, y), DIM); y += 24
    for k, n in enumerate(on[:10]):
        cx, cy = (8 if k % 2 == 0 else W // 2 + 4), y + (k // 2) * 22
        pygame.draw.circle(surf, GREEN, (cx + 5, cy + 8), 4)
        put(surf, F["btn"], n, (cx + 14, cy), GREEN, W // 2 - 26)
    y += ((min(len(on), 10) + 1) // 2) * 22 + 6
    if wg:
        pygame.draw.line(surf, DIM, (8, y), (W - 8, y)); y += 4
        put(surf, F["small"], "TU ALA", (8, y), DIM); y += 16
        put(surf, F["btn"], "  ·  ".join(wg), (8, y), BLUE, W - 16); y += 26
    if off and y < H - 40:
        pygame.draw.line(surf, DIM, (8, y), (W - 8, y)); y += 4
        put(surf, F["small"], "DESCONECTADOS HACE POCO", (8, y), DIM); y += 16
        for n, mins in off:
            if y > H - 18:
                break
            put(surf, F["small"], n, (8, y), WHITE, 300)
            put(surf, F["small"], f"hace {mins} min" if mins < 60 else f"hace {mins // 60} h", (W - 8, y), DIM, anchor="topright")
            y += 17

def view_session3(surf, d, flags, now):
    if ui.get("sesstab"):
        return view_friends(surf, d, flags, now)
    view_session2(surf, d, flags, now)
    n = len(((d or {}).get("friends") or {}).get("on") or [])
    put(surf, F["small"], f"toca para ver AMIGOS ({n} conectados)", (8, 252), GREEN if n else DIM)

def view_sub124(surf, d, flags, now):
    c, until = ui["confirm"]
    for i, (n, name) in enumerate(POWER):
        sure = c == ("pw", i) and time.time() < until
        draw_button(surf, grid(i, 4, 2), n, "¿SEGURO?" if sure else (f"BORDES {'SÍ' if style.get('borders', True) else 'NO'}" if i == 5 else f"ICONOS {'SÍ' if ICONS_ON[0] else 'NO'}" if i == 6 else name), F["num"], filled=sure,
                    lit=flash.get((1240, i), 0) > now)

def power_tap(i):
    import subprocess
    if i == 3:
        ui["view"] = 1244; return
    if i == 4:
        ui["view"] = 1245; return
    if i == 5:
        borders_toggle(); return
    if i == 6:
        icons_toggle(); return
    c, until = ui["confirm"]
    if c != ("pw", i) or time.time() > until:
        ui["confirm"] = (("pw", i), time.time() + 3); return
    ui["confirm"] = (None, 0)
    tap_flash((1240, i))
    cmd = [["systemctl", "stop", "elite-panel"], ["systemctl", "reboot"], ["systemctl", "poweroff"]][i]
    subprocess.Popen(["sudo", "-n"] + cmd)

def view_sub12(surf, d, flags, now):
    for i, (n, name) in enumerate([("1", "LOG"), ("2", "STREAM"), ("3", "RANGOS"), ("4", "AJUSTES"), ("5", "MATERIAL"), ("6", "PORTANAV."), ("7", "MERCADO"), ("8", "NOTAS")]):
        draw_button(surf, grid(i, 4, 2), n, name, F["num"], lit=flash.get((12, i), 0) > now)

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
    img = cmdr_img()
    if img:
        r = img.get_rect(center=(W // 2, 105))
        surf.blit(img, r)
        pygame.draw.rect(surf, ORANGE, r.inflate(6, 6), 2, border_radius=4)
    else:
        draw_emblem(surf, W // 2, 110, 70, now)
    put(surf, F["small"], "CMDR", (W // 2, 200), DIM, anchor="center")
    put(surf, F["big"], cfg["cmdr"], (W // 2, 224), ORANGE, anchor="center")
    put(surf, F["small"], "PANEL DE MANDO  ·  ELITE DANGEROUS", (W // 2, 252), DIM, anchor="center")
    pygame.draw.rect(surf, DIM, (140, 280, 200, 8), 1)
    pygame.draw.rect(surf, ORANGE, (142, 282, int(196 * k), 4))

CMDR_IMG = [None]

def cmdr_img():
    if CMDR_IMG[0] is None:
        try:
            CMDR_IMG[0] = pygame.image.load("/home/ortem/cmdr.jpg")
        except Exception as e:
            print("foto:", e); CMDR_IMG[0] = False
    return CMDR_IMG[0]

IPC = {"ip": None, "t": 0}

def my_ip():
    import socket
    if time.time() - IPC["t"] > 30:
        IPC["t"] = time.time()
        try:
            sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sk.connect(("192.168.0.1", 9))
            IPC["ip"] = sk.getsockname()[0]
            sk.close()
        except OSError:
            IPC["ip"] = None
    return IPC["ip"]

def draw_idle(surf, now):
    surf.fill(BLACK)
    lt = time.localtime(now)
    img = cmdr_img()
    if img:
        r = img.get_rect(center=(70, 160))
        surf.blit(img, r)
        pygame.draw.rect(surf, ORANGE, r.inflate(6, 6), 2, border_radius=4)
    else:
        draw_emblem(surf, 70, 160, 50, now / 3)
    put(surf, F["clock"], time.strftime("%H:%M", lt), (290, 110), ORANGE, anchor="center")
    put(surf, F["btn"], f"{DIAS[lt.tm_wday]} {lt.tm_mday} de {MESES[lt.tm_mon - 1]}", (290, 170), DIM, anchor="center")
    put(surf, F["big"], "CMDR " + cfg["cmdr"], (290, 215), ORANGE, 300, anchor="center")
    put(surf, F["small"], PANEL_VER, (290, 270), GREEN, anchor="center")
    ip = my_ip()
    put(surf, F["small"], f"IP {ip}" if ip else "SIN RED", (290, 286), DIM if ip else RED, anchor="center")
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

VIEWS = {0: view_menux, 1: view_mandos, 2: view_pips, 3: view_navx, 4: view_carga, 5: view_srv, 6: view_combatx, 61: view_combatlog, 7: view_sub7, 71: view_explo, 72: view_orrery, 73: view_bio, 74: view_rings, 75: view_diary, 76: view_alien, 8: view_stationx,
         9: view_fighter, 10: view_mining, 11: view_session3, 100: view_live, 12: view_sub12, 121: view_log, 122: view_stream,
         123: view_ranks, 124: view_sub124, 1244: view_settings, 1245: view_changelog, 125: view_mats, 126: view_carrier, 127: view_market, 128: view_trip, 129: view_trip_detail}

# ---------- recogida de combustible ----------
scoop = {"hist": [], "was": False, "full_until": 0}

def fnum(v, nd=1):
    return f"{v:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def dur_s(sec):
    sec = max(0, int(sec))
    return f"{sec // 60}m {sec % 60:02d}s" if sec >= 60 else f"{sec} s"

def draw_scoop(surf, d, flags, now):
    fuel = ((d or {}).get("Fuel") or {}).get("FuelMain")
    cap = (d or {}).get("fuelcap")
    if (d or {}).get("Flags", 0) & (1 << 26):
        fuel, cap = ((d or {}).get("Fuel") or {}).get("FuelReservoir"), None
    on, hot = bool(flags & (1 << 11)), bool(flags & (1 << 20))
    if on and fuel is not None:
        h = scoop["hist"]; h.append((now, fuel))
        while now - h[0][0] > 6: h.pop(0)
    else:
        if scoop["was"] and fuel is not None and cap and fuel >= cap - 0.05:
            scoop["full_until"] = now + 4
        scoop["hist"] = []
    scoop["was"] = on
    full = now < scoop["full_until"]
    if not on and not full:
        return
    blink = int(now * 3) % 2 == 0
    col = GREEN if full and not on else (RED if hot and blink else ORANGE)
    for k in range(4):
        pygame.draw.rect(surf, col, (k * 3, k * 3, W - k * 6, H - k * 6), 2)
    box = pygame.Rect(24, 58, W - 48, 214)
    pygame.draw.rect(surf, BLACK, box)
    for j in range(12):
        yy = box.y + 10 + (j * 19) % (box.h - 20)
        ln = (j * 41 + int(now * 120)) % 90
        pygame.draw.line(surf, (90, 45, 0), (box.x + 8, yy), (box.x + 8 + ln, yy))
        pygame.draw.line(surf, (90, 45, 0), (box.right - 8 - ln, yy), (box.right - 8, yy))
    pygame.draw.rect(surf, col, box, 3, border_radius=8)
    cx, y = box.centerx, box.y + 14
    if full and not on:
        put(surf, F["num"], "DEPÓSITO LLENO", (cx, box.centery - 14), GREEN, box.w - 20, anchor="center")
        if fuel is not None:
            put(surf, F["btn"], f"{fnum(fuel)} t", (cx, box.centery + 26), WHITE, anchor="center")
        return
    put(surf, F["big"], "RECOGIENDO COMBUSTIBLE", (cx, y), ORANGE, box.w - 20, anchor="midtop"); y += 34
    if fuel is not None:
        put(surf, F["num"], f"{fnum(fuel)} / {fnum(cap) if cap else '?'} t", (cx, y), WHITE, box.w - 20, anchor="midtop"); y += 46
        bx = pygame.Rect(box.x + 20, y, box.w - 40, 18)
        pygame.draw.rect(surf, DIM, bx, 1)
        if cap:
            pct = max(0.0, min(1.0, fuel / cap))
            pygame.draw.rect(surf, ORANGE, (bx.x + 2, bx.y + 2, int((bx.w - 4) * pct), bx.h - 4))
            put(surf, F["small"], f"{pct * 100:.0f}%", (bx.centerx, bx.y + 3), WHITE, anchor="midtop")
        y += 28
    h = scoop["hist"]
    if len(h) >= 2 and h[-1][0] - h[0][0] > 1:
        rate = (h[-1][1] - h[0][1]) / (h[-1][0] - h[0][0])
        put(surf, F["btn"], f"{fnum(rate, 2)} t/s", (box.x + 20, y), ORANGE)
        if rate > 0.001 and cap and fuel is not None:
            put(surf, F["btn"], f"lleno en {dur_s((cap - fuel) / rate)}", (box.right - 20, y), ORANGE, anchor="topright")
    y += 26
    if hot:
        put(surf, F["big"], "¡SOBRECALENTAMIENTO!", (cx, y), RED if blink else WHITE, box.w - 20, anchor="midtop")
    else:
        put(surf, F["small"], "temperatura OK", (cx, y + 6), GREEN, anchor="midtop")

# ---------- avisos extra: combustible en ruta, neutrones, gravedad ----------
xa = {"seq": None, "a": None}
NEON = (90, 200, 255)

def xa_notes(d, now):
    if not d:
        return
    # avisos de peligro a pie y combustible del vehiculo (al empezar cada situacion)
    dg = xa.setdefault("dg", {})
    f2, fl = d.get("Flags2", 0), d.get("Flags", 0)
    L = d.get("live") or {}
    sf = (d.get("Fuel") or {}).get("FuelReservoir")
    foot = f2 & 1
    conds = {"oxy": foot and f2 & (1 << 6), "hp": foot and f2 & (1 << 7),
             "cold": foot and f2 & (1 << 10), "hot": foot and f2 & (1 << 11),
             "fuel": bool(fl & (1 << 26)) and sf is not None and sf < 0.1}
    for k, on in conds.items():
        if on and not dg.get(k):
            t = L.get("temp")
            tc = f"{t - 273.15:.0f} °C" if t is not None else ""
            msg = {"oxy": ("POCO OXÍGENO", f"{(L.get('oxy') or 0) * 100:.0f}%", "vuelve a la nave o recarga"),
                   "hp": ("SALUD BAJA", f"{(L.get('health') or 0) * 100:.0f}%", "usa un botiquín"),
                   "cold": ("FRÍO EXTREMO", tc, "busca refugio"),
                   "hot": ("CALOR EXTREMO", tc, "busca sombra o refugio"),
                   "fuel": ("COMBUSTIBLE DEL VEHÍCULO", f"{sf or 0:.2f} t".replace(".", ","), "vuelve a la nave a repostar")}[k]
            xa["a"] = dict(until=now + 6, col=RED if k != "cold" else (90, 200, 255), title=msg[0], big=msg[1], lines=[msg[2]])
        dg[k] = bool(on)
    notes = d.get("notes") or []
    if xa["seq"] is None:
        xa["seq"] = max([n[0] for n in notes], default=0); return
    for seq, kind, text in notes:
        if seq <= xa["seq"]:
            continue
        xa["seq"] = seq
        p = (text or "").split("|")
        if kind == "fuelroute" and len(p) >= 5:
            here = p[0] == "here"
            dest = f"{p[3]} saltos hasta {p[4]}" if p[4] else f"{p[3]} saltos y no hay estrellas recogibles"
            xa["a"] = dict(until=now + 8, col=ORANGE if here else RED,
                           title="RECOGE COMBUSTIBLE AQUÍ" if here else "¡NO LLEGAS A REPOSTAR!",
                           big=f"{p[1].replace('.', ',')} t / ~{p[2].replace('.', ',')} t",
                           lines=["tienes / necesitas", dest])
        elif kind == "jetcone":
            xa["a"] = dict(until=now + 6, col=NEON, title="FSD SOBREALIMENTADO",
                           big=f"ALCANCE x{p[0].replace('.', ',')}", lines=["el próximo salto llega mucho más lejos"])
        elif kind == "jetdmg":
            xa["a"] = dict(until=now + 6, col=RED, title="¡DAÑO EN EL FSD!", big="CHORRO DE NEUTRONES",
                           lines=[p[0] or "FSD", "revisa la salud del módulo"])
        elif kind == "matfull" and len(p) >= 2:
            xa["a"] = dict(until=now + 5, col=ORANGE, title="MATERIAL AL MÁXIMO", big=p[0],
                           lines=[f"{p[1]} / {p[1]}", "lo que recojas de más se pierde"])
        elif kind == "find" and len(p) >= 5:
            first = p[3] == "1"
            xa["a"] = dict(until=now + 7, col=GREEN if first else ORANGE,
                           title="¡1º DESCUBRIMIENTO!" if first else "HALLAZGO VALIOSO", big=p[0].upper(),
                           lines=[p[1], f"~{cr(float(p[2]))} cr  ·  mapeado ~{cr(float(p[4]))} cr"])
        elif kind == "codex" and len(p) >= 3:
            xa["a"] = dict(until=now + 6, col=(90, 200, 255), title="NUEVO EN EL CÓDICE", big=p[0],
                           lines=[p[1], p[2]])
        elif kind == "wanted" and len(p) >= 3:
            xa["a"] = dict(until=now + 6, col=RED, title="OBJETIVO BUSCADO", big=f"{cr(float(p[2] or 0))} cr",
                           lines=[p[0], p[1]])
        elif kind == "missionexp" and len(p) >= 2:
            xa["a"] = dict(until=now + 7, col=ORANGE, title="MISIÓN A PUNTO DE CADUCAR", big=f"{p[1]} min",
                           lines=[p[0], f"destino: {p[2]}" if len(p) > 2 and p[2] else ""])
        elif kind == "missionhere" and len(p) >= 2:
            n = int(p[0])
            xa["a"] = dict(until=now + 7, col=GREEN, title="ENTREGA AQUÍ", big=f"{n} MISIÓN" + ("ES" if n > 1 else ""),
                           lines=[p[1], "busca la estación de destino"])
        elif kind == "sessend" and len(p) >= 9:
            v = [float(x) for x in p]
            secs = int(v[1])
            xa["a"] = dict(until=now + 90, col=(90, 200, 255), title="SESIÓN TERMINADA", big=f"+{cr(v[0])} cr",
                           lines=[f"{secs // 3600}h {secs % 3600 // 60:02d}m  ·  {int(v[2])} saltos  ·  {int(v[3])} al",
                                  f"Expl. {cr(v[4])} · Bio {cr(v[5])} · Comercio {cr(v[6])} · Recomp. {cr(v[7])}",
                                  f"Refinado: {int(v[8])} t" if v[8] else ""])
        elif kind == "lowcons" and len(p) >= 2:
            xa["a"] = dict(until=now + 6, col=ORANGE, title="QUEDAN POCOS", big=p[0].upper(),
                           lines=[f"te quedan {p[1]}", "repón en un asentamiento o estación"])
        elif kind == "crime" and len(p) >= 4:
            fine, bounty = float(p[1] or 0), float(p[2] or 0)
            xa["a"] = dict(until=now + 7, col=RED, title="DELITO COMETIDO", big=p[0].upper(),
                           lines=[(f"multa {cr(fine)} cr" if fine else "") + (f"  recompensa {cr(bounty)} cr" if bounty else ""), p[3]])
        elif kind == "taxi" and len(p) >= 4:
            xa["a"] = dict(until=now + 7, col=(90, 200, 255), title=p[0], big=p[2] or p[1],
                           lines=[p[1], f"coste {cr(float(p[3] or 0))} cr"])
        elif kind == "settle" and len(p) >= 5:
            rep = float(p[4]) if p[4] not in ("", "None") else None
            hostil = rep is not None and rep <= -35
            xa["a"] = dict(until=now + 7, col=RED if hostil else GREEN, title="ASENTAMIENTO", big=p[0],
                           lines=[f"{p[1]} · {p[2]}", ("HOSTIL HACIA TI" if hostil else (f"reputación {rep:+.0f}" if rep is not None else "")) + (f" · {p[3]}" if p[3] else "")])
        elif kind == "kill" and len(p) >= 3:
            rew = float(p[1] or 0)
            xa["a"] = dict(until=now + 2.5, col=GREEN if p[2] != "P" else RED, title="DERRIBO",
                           big=f"+{cr(rew)} cr" if rew else "PvP", lines=[p[0]])
        elif kind == "escaped" and len(p) >= 2:
            xa["a"] = dict(until=now + 5, col=GREEN, title="¡ESCAPADO!", big=p[0] or "INTERDICCIÓN",
                           lines=["era un comandante" if p[1] == "1" else "era un NPC"])
        elif kind == "submitted" and len(p) >= 2:
            xa["a"] = dict(until=now + 5, col=ORANGE, title="TE HAS SOMETIDO", big=p[0] or "INTERDICCIÓN",
                           lines=["COMANDANTE" if p[1] == "1" else "NPC", "carga el FSD y salta"])
        elif kind == "rebuy" and len(p) >= 2:
            xa["a"] = dict(until=now + 8, col=RED, title="CASCO CRÍTICO", big=f"{p[0]}%",
                           lines=[f"REBUY {cr(float(p[1] or 0))} cr", "considera huir"])
        elif kind == "died" and len(p) >= 4:
            xa["a"] = dict(until=now + 15, col=RED, title="NAVE DESTRUIDA", big=p[0] or "?",
                           lines=[" · ".join(x for x in (p[1].replace("_", " ").title(), p[2]) if x), f"rebuy {cr(float(p[3] or 0))} cr"])
        elif kind == "cmdrtarget" and len(p) >= 3:
            xa["a"] = dict(until=now + 5, col=ORANGE, title="COMANDANTE FIJADO", big=p[0],
                           lines=[" · ".join(x for x in (p[1], p[2]) if x), "posible PvP"])
        elif kind == "arrive" and len(p) >= 4:
            cur = xa.get("a")
            if not (cur and cur.get("title") == "SISTEMA SIN EXPLORAR" and now < cur["until"]):
                ui["alert"] = None
                scoop = p[2] == "1"
                xa["a"] = dict(until=now + 3, col=GREEN if scoop else ORANGE, title="LLEGADA", big=p[0].upper(),
                               lines=[f"{p[1]}  ·  {'RECOGIBLE' if scoop else 'NO RECOGIBLE'}",
                                      f"EDSM: {p[3]} cuerpos conocidos" if p[3] not in ("", "0") else "SIN DATOS EN EDSM"])
        elif kind == "newsys" and len(p) >= 1:
            ui["alert"] = None
            xa["a"] = dict(until=now + 6, col=GREEN, title="SISTEMA SIN EXPLORAR", big=p[0].upper(),
                           lines=["nadie ha descubierto esta estrella", "escanea todo con el FSS"])
        elif kind == "honk" and len(p) >= 3:
            n = int(p[0] or 0)
            known = int(p[2]) if p[2] not in ("", "None") else None
            info_ = "SIN DATOS EN EDSM: todo por descubrir" if not known else (
                f"EDSM conoce {known} · {max(0, n - known)} nuevos" if n > known else f"EDSM los conoce todos ({known})")
            xa["a"] = dict(until=now + 4, col=(90, 200, 255), title="ESCANEO DE DESCUBRIMIENTO", big=f"{n} CUERPOS",
                           lines=[f"{p[1]} señales", info_])
        elif kind == "risk" and len(p) >= 1:
            xa["a"] = dict(until=now + 6, col=ORANGE, title="DATOS EN RIESGO", big=f"{cr(float(p[0]))} cr",
                           lines=["llevas esto sin vender", "si te destruyen, se pierde"])
        elif kind == "alien" and len(p) >= 3:
            tgk = p[0] == "THARGOIDES"
            xa["a"] = dict(until=now + 6, col=(120, 230, 120) if tgk else (90, 200, 255), title=f"SEÑALES {p[0]}",
                           big=f"{p[1]} EN EL PLANETA", lines=[p[2], "míralas en 7.6 ALIENÍGENAS" if not tgk else "cuidado: posible actividad thargoide"])
        elif kind == "tgwar" and len(p) >= 4:
            pr = float(p[1] or 0)
            xa["a"] = dict(until=now + 6, col=RED if p[0] in ("INVASIÓN", "CONTROLADO", "BASTIÓN") else ORANGE,
                           title="GUERRA THARGOIDE", big=p[0], lines=[f"progreso {pr * 100:.0f}%" + (f" · puertos {p[2]}" if p[2] else ""), p[3]])
        elif kind == "friend" and len(p) >= 2:
            t = {"on": ("AMIGO CONECTADO", GREEN), "off": ("AMIGO DESCONECTADO", DIM), "req": ("SOLICITUD DE AMISTAD", BLUE)}.get(p[1])
            if t:
                xa["a"] = dict(until=now + 4, col=t[1], title=t[0], big=p[0], lines=[])
        elif kind == "wing" and len(p) >= 2:
            t = {"invite": "INVITACIÓN A ALA", "join": "TE HAS UNIDO A UN ALA", "add": "NUEVO EN TU ALA", "leave": "HAS SALIDO DEL ALA"}.get(p[1])
            if t:
                xa["a"] = dict(until=now + 4, col=BLUE, title=t, big=p[0] if p[0] != "-" else "", lines=[])
        elif kind == "gravity" and len(p) >= 2:
            g = float(p[0])
            xa["a"] = dict(until=now + 7, col=RED if g >= 2 else ORANGE, title="GRAVEDAD ALTA",
                           big=f"{p[0].replace('.', ',')} G", lines=[p[1], "aterriza despacio" if g >= 2 else ""])

def draw_xa(surf, now):
    a = xa["a"]
    if not a:
        return
    if now > a["until"]:
        xa["a"] = None; return
    col = a["col"]
    on = int(now * 3) % 2 == 0 or col != RED
    for k in range(4 if on else 2):
        pygame.draw.rect(surf, col, (k * 3, k * 3, W - k * 6, H - k * 6), 2)
    box = pygame.Rect(24, 64, W - 48, 196)
    pygame.draw.rect(surf, BLACK, box)
    dim = tuple(int(c) // 3 for c in col[:3])
    for j in range(12):
        yy = box.y + 10 + (j * 17) % (box.h - 20)
        ln = (j * 41 + int(now * 160)) % 100
        pygame.draw.line(surf, dim, (box.x + 8, yy), (box.x + 8 + ln, yy))
        pygame.draw.line(surf, dim, (box.right - 8 - ln, yy), (box.right - 8, yy))
    pygame.draw.rect(surf, col, box, 3, border_radius=8)
    cx, y = box.centerx, box.y + 16
    put(surf, F["big"], a["title"], (cx, y), col if on else WHITE, box.w - 20, anchor="midtop"); y += 36
    put(surf, F["num"], a["big"], (cx, y), WHITE, box.w - 20, anchor="midtop"); y += 52
    for ln_ in a["lines"]:
        if ln_:
            put(surf, F["btn"], ln_, (cx, y), col, box.w - 20, anchor="midtop")
        y += 26

PANEL_VER = "v0.52 · 29/10/2026 15:30"

# ---------- estilo CABINA (decoracion, se cambia en SESION) ----------
STYLE_FILE = "/home/ortem/estilo.txt"

def style_load():
    try:
        return open(STYLE_FILE).read().strip() == "cabina"
    except OSError:
        return False

style = {"cab": style_load(), "view": None, "vt": 0.0, "cache": {}}
STYLE_BTN = pygame.Rect(W - 160, H - 58, 152, 52)
HOLO = (90, 200, 255)

def style_toggle():
    style["cab"] = not style["cab"]
    try:
        with open(STYLE_FILE, "w") as f:
            f.write("cabina" if style["cab"] else "clasico")
    except OSError:
        pass

_orig_rect = pygame.draw.rect

def _cab_rect(surf, col, rect, width=0, border_radius=0, *a, **k):
    """En modo CABINA los rectangulos redondeados pasan a esquinas cortadas."""
    if style["cab"] and border_radius and border_radius > 0:
        r = pygame.Rect(rect)
        c = max(3, min(10, r.h // 3, r.w // 3))
        pts = [(r.x + c, r.y), (r.right - 1, r.y), (r.right - 1, r.bottom - 1 - c),
               (r.right - 1 - c, r.bottom - 1), (r.x, r.bottom - 1), (r.x, r.y + c)]
        return pygame.draw.polygon(surf, col, pts, width)
    return _orig_rect(surf, col, rect, width, border_radius, *a, **k)

pygame.draw.rect = _cab_rect

def _cached(key, make):
    c = style["cache"]
    if key not in c:
        c[key] = make()
    return c[key]

def _scan():
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for y in range(0, H, 3):
        pygame.draw.line(s, (0, 0, 0, 55), (0, y), (W, y))
    return s

def _hexes():
    s = pygame.Surface((W, H - TOP), pygame.SRCALPHA)
    r = 16
    dx, dy = r * 1.732, r * 1.5
    for row in range(int((H - TOP) / dy) + 2):
        for col in range(int(W / dx) + 2):
            cx = col * dx + (dx / 2 if row % 2 else 0)
            cy = row * dy
            pts = [(cx + r * math.cos(math.radians(60 * k + 30)), cy + r * math.sin(math.radians(60 * k + 30))) for k in range(6)]
            pygame.draw.polygon(s, (255, 140, 0, 16), pts, 1)
    return s

def _dots():
    s = pygame.Surface((W, H - TOP), pygame.SRCALPHA)
    for y in range(8, H - TOP, 16):
        for x in range(8, W, 16):
            s.set_at((x, y), (255, 140, 0, 60))
    return s

def _tint(col):
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    s.fill((col[0], col[1], col[2], 22))
    return s

def _stars():
    import random
    rnd = random.Random(7)
    return [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(4, 25), rnd.randint(60, 200)) for _ in range(45)]

def decorate(surf):
    now = time.time()
    v = ui["view"]
    splash = now - ui["start"] < 3
    if v == 11 and not splash and not ui["idle_on"]:
        draw_button(surf, STYLE_BTN, "ESTILO", "CABINA" if style["cab"] else "CLÁSICO", F["small"], filled=style["cab"])
    if not style["cab"]:
        return
    with lock:
        d, rx = state["data"], state["rx"]
    online = d is not None and now - rx < 5
    if v != style["view"]:
        style["view"], style["vt"] = v, now
    if ui["idle_on"]:
        # 8: estrellas y marco holografico de la foto
        for x0, y0, sp, b in _cached("stars", _stars):
            x = (x0 + now * sp) % W
            if 130 < x < 450 and 60 < y0 < 280:
                continue
            surf.set_at((int(x), int(y0)), (b, b, b))
        r = pygame.Rect(0, 0, 112, 128); r.center = (70, 160)
        k = 0.5 + 0.5 * math.sin(now * 2)
        col = tuple(int(c * (0.4 + 0.6 * k)) for c in HOLO)
        for (x, y), (sx, sy) in (((r.left, r.top), (1, 1)), ((r.right, r.top), (-1, 1)),
                                 ((r.left, r.bottom), (1, -1)), ((r.right, r.bottom), (-1, -1))):
            pygame.draw.line(surf, col, (x, y), (x + 16 * sx, y), 2)
            pygame.draw.line(surf, col, (x, y), (x, y + 16 * sy), 2)
        yy = r.top + int((now * 40) % r.h)
        pygame.draw.line(surf, col, (r.left + 4, yy), (r.right - 4, yy), 1)
    elif not splash:
        if online:
            flags, f2 = d.get("Flags", 0), d.get("Flags2", 0)
            # 6: fondo tenue segun el modo
            ground = f2 & 1 or flags & (1 << 26)
            surf.blit(_cached("dots" if ground else "hex", _dots if ground else _hexes), (0, TOP))
            # 7: tinte segun la situacion
            L = d.get("live") or {}
            hull = (L.get("ship") or {}).get("hull")
            danger = L.get("legal") in ("Wanted", "Hostile", "Warrant") or (hull is not None and hull < 0.3)
            cols = border_cols(d)
            if cols:
                surf.blit(_cached(("tint", tuple(cols[0][:3])), lambda: _tint(cols[0])), (0, 0))
        # 3: barra superior con barrido y piloto de datos
        p = (now * 160) % (W + 200) - 100
        for x in range(0, W, 3):
            b = max(0.25, 1 - abs(x - p) / 90)
            pygame.draw.line(surf, tuple(int(c * b) for c in ORANGE[:3]), (x, TOP - 2), (x + 2, TOP - 2))
        fresh = online and now - rx < 0.6
        pygame.draw.circle(surf, GREEN if fresh else DIM, (W - 5, TOP - 8), 3)
        # 5: barrido al cambiar de pantalla
        dt = now - style["vt"]
        if dt < 0.35:
            x = int(W * dt / 0.35)
            _orig_rect(surf, BLACK, (x, TOP, W - x, H - TOP))
            pygame.draw.line(surf, ORANGE, (x, TOP), (x, H), 2)
    # 2: lineas de escaneo y franja que baja
    surf.blit(_cached("scan", _scan), (0, 0))
    yy = int((now * 35) % H)
    band = _cached("band", lambda: pygame.Surface((W, 3), pygame.SRCALPHA))
    band.fill((255, 170, 60, 28))
    surf.blit(band, (0, yy))

# ---------- pantalla grande HDMI: tablero de 4 cuadros segun la situacion ----------
BIG = {"dev": None, "fb": None, "w": 0, "h": 0, "bpp": 16, "stride": 0, "surf": None, "s16": None,
       "last": None, "n": 0, "fonts": None, "cell": None}
BIG_SETS = {"VIAJE": [100, 3, 71, 72], "APROXIMACIÓN": [100, 72, 73, 74], "SUPERFICIE": [100, 73, 5, 125],
            "ATRACADO": [100, 8, 127, 4], "ATRAQUE": [8], "COMBATE": [100, 6, 61, 2]}

def big_open():
    import glob, os, fcntl
    for p in sorted(glob.glob('/sys/class/graphics/fb*')):
        try:
            name = open(p + '/name').read().strip()
            if 'vc4' not in name.lower():
                continue
            w, h = map(int, open(p + '/virtual_size').read().strip().split(','))
            bpp = int(open(p + '/bits_per_pixel').read())
            stride = int(open(p + '/stride').read())
            dev = '/dev/' + os.path.basename(p)
            fb = open(dev, 'r+b', buffering=0)
        except Exception as e:
            print("HDMI:", e, flush=True); continue
        try:
            buf = bytearray(160)
            fcntl.ioctl(fb, 0x4600, buf)        # FBIOGET_VSCREENINFO
            fcntl.ioctl(fb, 0x4601, buf)        # FBIOPUT_VSCREENINFO (enciende la salida)
            fcntl.ioctl(fb, 0x4611, 0)          # FBIOBLANK: desbloquear
        except OSError:
            pass
        masks = (0xF800, 0x07E0, 0x001F, 0) if bpp == 16 else (0xFF0000, 0xFF00, 0xFF, 0)
        BIG.update(dev=dev, fb=fb, w=w, h=h, bpp=bpp, stride=stride, surf=pygame.Surface((w, h), 0, 32),
                   s16=pygame.Surface((w, h), 0, bpp, masks), cell=pygame.Surface((W, H), 0, 32))
        print("Pantalla grande", dev, w, h, bpp, flush=True)
        return True
    return False

def big_blit(dst, src, area):
    s = min(area.w / src.get_width(), area.h / src.get_height())
    size = (max(1, int(src.get_width() * s)), max(1, int(src.get_height() * s)))
    try:
        img = pygame.transform.smoothscale(src, size)
    except ValueError:
        img = pygame.transform.scale(src, size)
    dst.blit(img, img.get_rect(center=area.center))

def big_mode(d, flags):
    f2 = d.get("Flags2", 0)
    if flags & 1:
        return "ATRACADO"
    if (d.get("station") or {}).get("status") == "CONCEDIDO":
        return "ATRAQUE"
    if f2 & 1 or flags & ((1 << 26) | 2):
        return "SUPERFICIE"
    if (d.get("body") or "").endswith(" Ring"):
        return "APROXIMACIÓN"
    if d.get("target") or flags & 64:
        return "COMBATE"
    if flags & (1 << 21):
        return "APROXIMACIÓN"
    return "VIAJE"

def render_big():
    S, cell = BIG["surf"], BIG["cell"]
    bw, bh = BIG["w"], BIG["h"]
    with lock:
        d, rx = state["data"], state["rx"]
    now = time.time()
    online = d is not None and now - rx < 5
    if BIG["fonts"] is None:
        BIG["fonts"] = (pygame.font.Font(None, 40), pygame.font.Font(None, 26))
    fbig, fsm = BIG["fonts"]
    S.fill(BLACK)
    flags = (d or {}).get("Flags", 0) if online else 0
    full = None
    if ui.get("alert") and now < ui["alert"]["until"]:
        full = "alert"
    elif xa.get("a") and now < xa["a"]["until"]:
        full = "xa"
    elif online and (flags & (1 << 11) or now < scoop["full_until"]):
        full = "scoop"
    if now - ui["start"] < 3:
        draw_splash(cell, now); big_blit(S, cell, S.get_rect()); return
    if not online:
        draw_idle(cell, now); big_blit(S, cell, S.get_rect()); return
    if full:
        cell.fill(BLACK)
        if full == "alert":
            draw_alert(cell, now)
        elif full == "xa":
            draw_xa(cell, now)
        else:
            draw_scoop(cell, d, flags, now)
        big_blit(S, cell, S.get_rect()); return
    mode = big_mode(d, flags)
    hh = 44
    put(S, fbig, (d.get("system") or "---").upper(), (12, 9), ORANGE, 400)
    put(S, fsm, mode, (bw // 2 - 80, 14), GREEN, 190, anchor="midtop")
    fuel, cap = (d.get("Fuel") or {}).get("FuelMain"), d.get("fuelcap")
    if flags & (1 << 26):
        fuel, cap = (d.get("Fuel") or {}).get("FuelReservoir"), None
    if fuel is not None:
        bx = pygame.Rect(bw // 2 + 20, 12, 240, 18)
        pygame.draw.rect(S, DIM, bx, 1)
        if cap:
            pct = max(0.0, min(1.0, fuel / cap))
            pygame.draw.rect(S, RED if pct < 0.25 else ORANGE, (bx.x + 2, bx.y + 2, int((bx.w - 4) * pct), bx.h - 4))
        put(S, fsm, f"FUEL {fuel:.1f} t", (bx.right + 10, 14), ORANGE)
    put(S, fbig, time.strftime("%H:%M"), (bw - 12, 9), ORANGE, anchor="topright")
    pygame.draw.line(S, DIM, (0, hh - 2), (bw, hh - 2), 1)
    cw, ch = bw // 2, (bh - hh) // 2
    cells = list(BIG_SETS[mode])
    if 74 in cells and not ((d.get("rings") or {}).get("rings") or (d.get("rings") or {}).get("signals")):
        cells[cells.index(74)] = 128
    if mode == "SUPERFICIE" and flags & (1 << 26) and "rhino" in (d.get("srvtype") or "").lower():
        cells = [100, 74, 5, 10]
    if len(cells) == 1:
        cell.fill(BLACK)
        try:
            VIEWS[cells[0]](cell, d, flags, now)
        except Exception as e:
            put(cell, F["small"], f"error: {e}"[:60], (8, TOP + 8), RED)
        big_blit(S, cell.subsurface((0, TOP, W, H - TOP)), pygame.Rect(4, hh + 4, bw - 8, bh - hh - 8))
        return
    for i, v in enumerate(cells):
        r = pygame.Rect((i % 2) * cw, hh + (i // 2) * ch, cw, ch)
        cell.fill(BLACK)
        fn = view_navbig if v == 3 else VIEWS.get(v)
        try:
            if fn:
                fn(cell, d, flags, now)
        except Exception as e:
            put(cell, F["small"], f"error: {e}"[:60], (8, TOP + 8), RED)
        pygame.draw.rect(S, DIM, r.inflate(-6, -6), 1, border_radius=6)
        put(S, fsm, str(MENU.get(v, v)).upper(), (r.x + 12, r.y + 6), DIM, r.w - 24)
        big_blit(S, cell.subsurface((0, TOP, W, H - TOP)), pygame.Rect(r.x + 6, r.y + 26, r.w - 12, r.h - 32))

def big_frame():
    if BIG["fb"] is None:
        if BIG["dev"] is None and not big_open():
            BIG["dev"] = False
        if BIG["fb"] is None:
            return
    try:
        render_big()
        decorate_big(BIG["surf"])
        draw_borders(BIG["surf"])
        rhino_banner(BIG["surf"])
        s16 = BIG["s16"]
        s16.blit(BIG["surf"], (0, 0))
        raw = s16.get_buffer().raw
        pitch, stride = s16.get_pitch(), BIG["stride"]
        if pitch != stride:
            n = min(pitch, stride)
            raw = b"".join(raw[y * pitch:y * pitch + n].ljust(stride, b"\0") for y in range(BIG["h"]))
        if raw != BIG["last"]:
            BIG["fb"].seek(0); BIG["fb"].write(raw); BIG["last"] = raw
    except Exception as e:
        print("HDMI:", e, flush=True)

# ---------- aviso RHINO PREPARADO (7-40 m) en las dos pantallas ----------
RB_FONTS = {}

def rhino_ready():
    with lock:
        d, rx = state["data"], state["rx"]
    if not d or time.time() - rx > 5:
        return None
    flags, f2 = d.get("Flags", 0), d.get("Flags2", 0)
    if flags & ((1 << 26) | 1 | 2) or f2 & 1:            # en SRV, atracado, aterrizado o a pie
        return None
    if not flags & (1 << 21) or flags & (1 << 29):       # sin altitud real sobre el terreno
        return None
    L = d.get("live") or {}
    alt, rh = L.get("alt"), (L.get("ship") or {}).get("rhino")
    if alt is not None and alt <= 100 and rh in ("A BORDO", "HANGAR"):
        return alt
    return None

def rhino_banner(surf):
    alt = rhino_ready()
    if alt is None:
        return
    now = time.time()
    if alt > 40:
        col, txt = (255, 80, 0), "BAJA PARA EL RHINO"
    elif alt >= 7:
        col, txt = (0, 170, 60), "RHINO PREPARADO"
    else:
        col = (255, 0, 0) if int(now * 4) % 2 == 0 else (60, 0, 0)
        txt = "DEMASIADO BAJO"
    w, h = surf.get_size()
    bh = max(58, h // 7)
    r = pygame.Rect(0, h - bh, w, bh)
    pygame.draw.rect(surf, col, r)
    pygame.draw.rect(surf, WHITE, r, 3)
    size = int(bh * 0.8)
    if size not in RB_FONTS:
        RB_FONTS[size] = (pygame.font.Font(None, size), pygame.font.Font(None, max(18, size // 2)))
    fb, fs = RB_FONTS[size]
    img = fb.render(txt, True, WHITE)
    surf.blit(img, img.get_rect(center=(r.centerx - w // 14, r.centery)))
    a = fs.render(f"{alt:.0f} m", True, WHITE)
    surf.blit(a, a.get_rect(midright=(r.right - 12, r.centery)))

# ---------- estilo CABINA tambien en la pantalla grande ----------
def _bpat(w, h, ground):
    sf = pygame.Surface((w, h), pygame.SRCALPHA)
    if ground:
        for y in range(8, h, 20):
            for x in range(8, w, 20):
                sf.set_at((x, y), (255, 140, 0, 60))
    else:
        r = 22
        dx, dy = r * 1.732, r * 1.5
        for row in range(int(h / dy) + 2):
            for col in range(int(w / dx) + 2):
                cx = col * dx + (dx / 2 if row % 2 else 0)
                cy = row * dy
                pts = [(cx + r * math.cos(math.radians(60 * k + 30)), cy + r * math.sin(math.radians(60 * k + 30))) for k in range(6)]
                pygame.draw.polygon(sf, (255, 140, 0, 16), pts, 1)
    return sf

def _bscan(w, h):
    sf = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(0, h, 3):
        pygame.draw.line(sf, (0, 0, 0, 55), (0, y), (w, y))
    return sf

def _btint(w, h, col):
    sf = pygame.Surface((w, h), pygame.SRCALPHA)
    sf.fill((col[0], col[1], col[2], 22))
    return sf

def decorate_big(S):
    if not style["cab"]:
        return
    now = time.time()
    w, h = S.get_size()
    hh = 44
    with lock:
        d, rx = state["data"], state["rx"]
    online = d is not None and now - rx < 5
    if online and now - ui["start"] >= 3:
        flags, f2 = d.get("Flags", 0), d.get("Flags2", 0)
        ground = bool(f2 & 1 or flags & (1 << 26))
        S.blit(_cached(("bpat", ground, w, h), lambda: _bpat(w, h - hh, ground)), (0, hh))
        L = d.get("live") or {}
        hull = (L.get("ship") or {}).get("hull")
        danger = L.get("legal") in ("Wanted", "Hostile", "Warrant") or (hull is not None and hull < 0.3)
        cols = border_cols(d)
        if cols:
            S.blit(_cached(("btint", tuple(cols[0][:3]), w, h), lambda: _btint(w, h, cols[0])), (0, 0))
        p_ = (now * 300) % (w + 300) - 150
        for x in range(0, w, 4):
            b = max(0.25, 1 - abs(x - p_) / 150)
            pygame.draw.line(S, tuple(int(c * b) for c in ORANGE[:3]), (x, hh - 2), (x + 3, hh - 2))
        pygame.draw.circle(S, GREEN if now - rx < 0.6 else DIM, (w - 6, 6), 4)
    S.blit(_cached(("bscan", w, h), lambda: _bscan(w, h)), (0, 0))
    band = _cached(("bband", w), lambda: pygame.Surface((w, 4), pygame.SRCALPHA))
    band.fill((255, 170, 60, 28))
    S.blit(band, (0, int((now * 60) % h)))

# ---------- bordes de situacion (rojo, naranja, marron, azul) ----------
BROWN = (150, 90, 40)
BORDERS_FILE = "/home/ortem/bordes.txt"
try:
    style["borders"] = open(BORDERS_FILE).read().strip() != "no"
except OSError:
    style["borders"] = True

def borders_toggle():
    style["borders"] = not style["borders"]
    try:
        with open(BORDERS_FILE, "w") as f:
            f.write("si" if style["borders"] else "no")
    except OSError:
        pass

def border_cols(d):
    flags, f2 = d.get("Flags", 0), d.get("Flags2", 0)
    L = d.get("live") or {}
    hull = (L.get("ship") or {}).get("hull")
    sec = ((d.get("sysinfo") or {}).get("sec") or "").lower()
    out = []
    if L.get("legal") in ("Wanted", "Hostile", "Warrant") or (hull is not None and hull < 0.3 and not f2 & 1):
        out.append(RED)
    if "anarqu" in sec or "lawless" in sec or "sin ley" in sec:
        out.append(ORANGE)
    if f2 & (1 << 4) or flags & (1 << 26):
        out.append(BROWN)
    if flags & 1:
        out.append(BLUE)
    return out[:3]

def draw_borders(surf):
    if not style.get("borders", True):
        return
    now = time.time()
    with lock:
        d, rx = state["data"], state["rx"]
    if not d or now - rx > 5 or now - ui["start"] < 3 or ui.get("idle_on"):
        return
    w, h = surf.get_size()
    th = 2 if w < 600 else 3
    for k, col in enumerate(border_cols(d)):
        o = k * (th + 1)
        _orig_rect(surf, col, (o, o, w - 2 * o, h - 2 * o), th)

def render(surf):
    with lock:
        d, rx = state["data"], state["rx"]
    now = time.time()
    online = d is not None and now - rx < 5
    if online:
        process_notes(d)
    if now - ui["start"] < 3:
        draw_splash(surf, now); return
    ui["idle_on"] = not online and ui["view"] in (0, 100) and now > ui["idle_skip"] and now - ui["start"] > 8
    if ui["idle_on"]:
        draw_idle(surf, now); return
    flags = (d or {}).get("Flags", 0) if online else 0
    v = ui["view"]
    surf.fill(BLACK)
    # barra superior
    x0 = 8
    if True:
        pygame.draw.rect(surf, ORANGE, BACK.inflate(-8, -8), 2, border_radius=6)
        put(surf, F["btn"], "MENÚ" if v == 100 else "< INICIO" if v == 0 else "< MENÚ", BACK.center, ORANGE, anchor="center")
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
    draw_scoop(surf, d if online else None, flags, now)
    xa_notes(d if online else None, now)
    draw_xa(surf, now)
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
            decorate(surf)
            draw_borders(surf)
            rhino_banner(surf)
            BIG["n"] += 1
            if BIG["n"] % 2 == 0:
                big_frame()
            data = to_fb_bytes(surf, bpp, stride)
            if data != last:
                fb.seek(0); fb.write(data); last = data
            time.sleep(0.1)

if __name__ == "__main__":
    main()
