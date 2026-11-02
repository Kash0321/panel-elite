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
MODS = {'Ctrl': 0x01, 'Shift': 0x02, 'Alt': 0x04, 'AltGr': 0x40}
KEYS.update({'-': 0x2D, '=': 0x2E, '[': 0x2F, ']': 0x30, '\\': 0x31, ';': 0x33, "'": 0x34, '`': 0x35, ',': 0x36,
             '/': 0x38, 'Backspace': 0x2A, 'Right': 0x4F, 'Left': 0x50, 'Down': 0x51, 'Up': 0x52, 'KPDiv': 0x54,
             'KPMul': 0x55, 'KPSub': 0x56, 'KPAdd': 0x57, 'KPEnter': 0x58, 'KPDec': 0x63})

def key_ok(k):
    *mods, kk = (k or "").split('+')
    return kk in KEYS and all(m in MODS for m in mods)

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
cfg = {"sharp": True, "auto": True, "alerts": True, "sound": True, "theme": 0, "cmdr": CMDR_NAME}

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
        import os as _os
        if _os.path.exists(path) and _os.path.getsize(path) > 1000:
            return
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
    if XA_K[0] and (not ev_on(XA_K[0]) or not snd_on(XA_K[0])):
        return
    if cfg["sound"] and name in SOUNDS and shutil.which("aplay"):
        try:
            subprocess.Popen(["aplay", "-q", SOUNDS[name]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass

# ---------- avisos: alertas y cambio automatico de menu ----------
AUTO_VIEW = {"embark": 100, "market": 127, "interdicted": 6, "underattack": 6, "docking": 8, "prospector": 10, "srv": 5, "foot": 100, "fighter": 9}

# avisos uno a uno: cfg["ev"][clave] = False lo apaga (lo que no esta en la lista sale siempre)
EV_LIST = [("jump", "SALTO"), ("interdicted", "INTERDICCIÓN"), ("underattack", "TE ATACAN"),
           ("shields_down", "ESCUDOS CAÍDOS"), ("shields_up", "ESCUDOS ARRIBA"), ("hull", "CASCO DAÑADO"),
           ("heat", "SOBRECALENTAMIENTO"), ("rebuy", "CASCO CRÍTICO"), ("died", "HAS CAÍDO / DESTRUIDA"),
           ("hplow", "SALUD BAJA (A PIE)"), ("oxy", "POCO OXÍGENO"), ("temp", "FRÍO / CALOR"),
           ("srvfuel", "COMBUSTIBLE SRV"), ("gravity", "GRAVEDAD ALTA"), ("fuelroute", "RUTA COMBUSTIBLE"),
           ("jetcone", "FSD SOBREALIMENT."), ("jetdmg", "DAÑO EN EL FSD"), ("arrive", "LLEGADA / SEÑAL"),
           ("newsys", "SIN EXPLORAR"), ("honk", "ESCANEO SISTEMA"), ("find", "HALLAZGO VALIOSO"),
           ("codex", "CÓDICE"), ("risk", "DATOS EN RIESGO"), ("matfull", "MATERIAL AL MÁX."),
           ("alien", "SEÑALES ALIEN"), ("tgwar", "GUERRA THARGOIDE"), ("shutdown", "APAGÓN THARGOIDE"),
           ("wanted", "OBJETIVO BUSCADO"), ("cmdrtarget", "CMDR FIJADO"), ("kill", "BAJA / DERRIBO"),
           ("escaped", "ESCAPADO"), ("submitted", "SOMETIDO"), ("crime", "DELITO"),
           ("dropship", "TRANSPORTE ZONA"), ("deploy", "DESPLEGADO"), ("thrown", "GRANADA LANZADA"),
           ("pickup", "RECOGIDO"), ("usecons", "CONSUMIBLE USADO"), ("lowcons", "QUEDAN POCOS"),
           ("redeem", "COBRADO"), ("opstart", "OPERACIÓN INICIADA"), ("opend", "OPERACIÓN TERMINADA"),
           ("missionexp", "MISIÓN CADUCA"), ("missionhere", "ENTREGA AQUÍ"), ("taxi", "TAXI"),
           ("settle", "ASENTAMIENTO"), ("sessend", "FIN DE SESIÓN"), ("friend", "AMIGOS"),
           ("wing", "ALA"), ("cg", "OBJ. COMUNITARIO"), ("galnet", "NOTICIA GALNET"), ("power", "BAJA TENSIÓN"),
           ("keys", "TECLAS SIN ASIGNAR"), ("elink", "RECARGA CON ENLACE"),
           ("thargmusic", "MÚSICA THARGOIDE")]
# cambio automatico de menu uno a uno: cfg["autoev"][clave] = False
AUTO_LIST = [("docking", "ATRAQUE > ESTACIÓN"), ("market", "MERCADO"), ("interdicted", "INTERDICCIÓN > COMBATE"),
             ("underattack", "TE ATACAN > COMBATE"), ("arrsig", "SEÑAL PELIGROSA > COMBATE"),
             ("arrst", "LLEGADA > ESTACIÓN"), ("prospector", "PROSPECTOR > MINERÍA"), ("srv", "SRV"),
             ("fighter", "CAZA"), ("embark", "EMBARCAR > EN VIVO"), ("foot", "A PIE > EN VIVO"),
             ("fss", "FSS > SISTEMA"), ("combatmusic", "MÚSICA COMBATE > COMBATE"),
             ("ppmenu", "MENÚ POWERPLAY > POWERPLAY"), ("sqmenu", "MENÚ ESCUADRÓN > ESCUADRÓN")]
XA_K = [None]          # aviso que se esta procesando (para apagarlo y silenciarlo)

SND_DEF = {"kill": False}      # de entrada en silencio: bajas y derribos (con sus creditos)

def snd_on(k):
    return not k or (cfg.get("snd") or {}).get(k, SND_DEF.get(k, True))

def ev_on(k):
    return cfg.get("alerts", True) and (cfg.get("ev") or {}).get(k, True)

def auto_on(k):
    return cfg.get("auto", True) and (cfg.get("autoev") or {}).get(k, True)

def ev_migrate():
    # antes ALERTAS / CAMBIO AUTO eran un solo interruptor: si estaba apagado, se apagan todos
    for master, store, L in (("alerts", "ev", EV_LIST), ("auto", "autoev", AUTO_LIST), ("sound", "snd", EV_LIST)):
        if not cfg.get(master, True):
            cfg[store] = {k: False for k, _ in L}
            cfg[master] = True
            save_cfg()

class XaDict(dict):
    def __setitem__(self, k, v):
        if k == "a" and v is not None and XA_K[0] and not ev_on(XA_K[0]):
            return
        if k == "a" and isinstance(v, dict):
            v.setdefault("ev", XA_K[0])
        dict.__setitem__(self, k, v)

def set_alert(text, sub="", col=None, secs=3.0, kind="red"):
    ui["alert"] = {"text": text, "sub": sub, "col": col or RED, "until": time.time() + secs, "kind": kind,
                   "ev": XA_K[0] or (kind if kind in ("galnet",) else None)}

def handle_note(kind, text):
    if kind == "combatmusic" and auto_on("combatmusic"):
        foot = (state.get("data") or {}).get("Flags2", 0) & 1
        if ui["view"] not in ((100, 150) if foot else (6, 61)):
            ui["view"] = 100 if foot else 6
    elif kind == "ppmenu" and auto_on("ppmenu"):
        ui["view"] = 3; ui["navtab"] = 2
    elif kind == "sqmenu" and auto_on("sqmenu"):
        ui["view"] = 165; ui["sqpage"] = 0
    elif kind == "mainmenu":
        ui["view"] = 100; ui["idle_skip"] = 0
    elif kind == "loadgame":
        track.update(body=None, pts=[], kills=[], items=[], last=None, raw=None, fast=False)
    if kind in AUTO_VIEW and auto_on(kind):
        ui["view"] = AUTO_VIEW[kind]
        if kind in ("underattack", "interdicted") and ((state.get("data") or {}).get("Flags2", 0) & 1):
            ui["view"] = 100
    if not ev_on(kind):
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

FIGHT_SECS = 60
fight = {"t": 0.0}
FIGHT_KINDS = ("underattack", "shields_down", "kill", "deploy", "interdicted")

def in_fight(d, now=None):
    return bool(d) and bool(d.get("Flags2", 0) & 1) and (now or time.time()) - fight["t"] < FIGHT_SECS

def process_notes(d):
    notes = d.get("notes") or []
    top = max([n[0] for n in notes], default=0)
    if ui["note_seq"] is None or top < ui["note_seq"]:     # arranque o sender reiniciado
        ui["note_seq"] = top
    for seq, kind, text in notes:
        if seq > ui["note_seq"]:
            ui["note_seq"] = seq
            if kind in FIGHT_KINDS:
                fight["t"] = time.time()
            if kind == "kill":
                track_kill()
            if kind == "pickup":
                nm_ = (text.split("|") + [""])[0]
                track_item(ITEM_KIND.get(nm_, "gren"))
            if kind == "deploy":                       # el mapa empieza al bajar del transporte
                track.update(pts=[], kills=[], items=[], last=None)
            XA_K[0] = kind
            try:
                handle_note(kind, text)
            finally:
                XA_K[0] = None
    gui = d.get("gui", 0)
    if gui == 9 and ui["gui"] != 9 and auto_on("fss"):          # FSS abierto
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
    return '/dev/null', 16, W * 2   # sin pantalla pequena: solo la HDMI

_FB16 = {}

def to_fb_bytes(surf, bpp, stride):
    if ROT:
        surf = pygame.transform.rotate(surf, 90)
    if bpp == 16:
        w_, h_ = surf.get_size()
        t = _FB16.get((w_, h_))
        if t is None:
            t = _FB16[(w_, h_)] = pygame.Surface((w_, h_), 0, 16, (0xF800, 0x07E0, 0x001F, 0))
        t.blit(surf, (0, 0))
        raw, pitch = t.get_buffer().raw, t.get_pitch()
        if pitch != stride:
            n = min(pitch, stride)
            raw = b"".join(raw[y * pitch:y * pitch + n].ljust(stride, b"\0") for y in range(h_))
        return raw
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
    if not all(key_ok(k) for k in keys):
        set_alert("SIN TECLA EN EL JUEGO", "mira AJUSTES > OPCIONES > TECLAS", ORANGE, 3)
        return
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
        pkt, addr_ = s.recvfrom(65535)
        state["pc"] = addr_[0]
        try:
            if pkt[:1] == b"Z":
                import zlib
                pkt = zlib.decompress(pkt[1:])
            d = json.loads(pkt)
        except Exception:
            continue
        with lock:
            if "log" in d:
                if not ui["pause"]:
                    state["log"].append(d["log"])
            else:
                old = state["data"] or {}
                for k, v in old.items():          # lo que no ha cambiado no viene: se conserva
                    if k not in d:
                        d[k] = v
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
    if kill_tap(x, y):
        return
    if ui["alert"] and time.time() < ui["alert"]["until"]:
        ui["alert"] = None; return
    if ui["idle_on"]:
        ui["idle_skip"] = time.time() + 60; return
    v = ui["view"]
    if BACK.collidepoint(x, y):
        ui["view"] = 0 if v == 100 else PARENT.get(v, 0); ui["pause"] = False
        return
    if y < TOP and tap_topbar(x, y, v):
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
                    if txt == "VOLVER":
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
    elif v == 3:
        cur = ui.get('navtab') or (1 if time.time() < pol['until'] else 0); ui['navtab'] = (cur + 1) % 3; pol['until'] = 0; return
    elif v == 124:
        for i in range(7):
            if grid(i, 4, 2).collidepoint(x, y):
                power_tap(i); return
    elif v == 1245:
        ui['page1245'] = ui.get('page1245', 0) + 1; return
    elif (v == 100 and NAVE_BTN.collidepoint(x, y)) or (v == 73 and NAVE_BTN_BIO.collidepoint(x, y)):
        ship_here(); return
    elif v == 76:
        ui['alientab'] = 1 - ui.get('alientab', 0); return
    elif v == 11:
        if ui.get('sesstab') and SQ_BTN.collidepoint(x, y):
            tap_flash(("sqbtn",)); ui["view"] = 165; ui["sqpage"] = 0; return
        ui['sesstab'] = 1 - ui.get('sesstab', 0); return
    elif v == 150:
        tap_map(x, y); return
    elif v == 160:
        tap_pantalla(x, y); return
    elif v == 164:
        tap_keys(x, y); return
    elif v == 165:
        tap_squad(x, y); return
    elif v in (161, 162, 163):
        tap_evlist(x, y); return
    elif v in (140, 141):
        tap_manual(x, y); return
    elif v == 132:
        cgoals["page"] += 1; return
    elif v in (130, 131):
        tap_galnet(x, y); return
    elif v == 71:
        ui['page71'] = ui.get('page71', 0) + 1; return
    elif v == 72:
        tap_orrery(x, y)
    elif v == 12:
        tap_sub12(x, y); return
    elif v == 1244:
        for i, k in enumerate(["auto", "alerts", "sound", "theme", "voice", "stream", "keys", "killbtn"]):
            if grid(i, 4, 2).collidepoint(x, y):
                if k == "keys":
                    tap_flash((124, i)); ui["view"] = 164; return
                if k == "killbtn":
                    tap_flash((124, i)); cfg["killbtn"] = not cfg.get("killbtn", True); save_cfg(); return
                tap_flash((124, i))
                if k in ("alerts", "auto", "sound"):
                    ui["view"] = {"alerts": 161, "auto": 162, "sound": 163}[k]; return
                if k == "theme":
                    cfg["theme"] = (cfg["theme"] + 1) % len(THEMES); apply_theme()
                else:
                    cfg[k] = not cfg.get(k, False)
                    if k == "sound" and cfg[k]: play("ok")
                    if k == "voice" and cfg[k]: voice["last"].clear(); voice_say("Voz de la nave activada")
                    if k == "stream" and cfg[k]: stream_start()
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
    if type(surf).__name__ == "ScaledSurf":
        f_ = getattr(font, "f", 1)
        r_ = pygame.Rect(0, 0, int(t.get_width() / f_), int(t.get_height() / f_))
        setattr(r_, anchor, pos)
        surf.blit(t, r_.topleft)
        return r_.w
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
        surf.blit(f.render(r, True, RED if r.startswith("[PANEL]") else ORANGE), (4, TOP + 2 + j * lh))
    if ui["pause"]:
        t = F["btn"].render(" PAUSA ", True, BLACK, WHITE)
        surf.blit(t, (W - t.get_width() - 6, TOP + 4))
    if not log:
        put(surf, F["btn"], "Esperando eventos del journal...", (8, TOP + 10), DIM)

# ---------- formatos ----------
def crx(v):
    v = v or 0
    return fnum(v, 0) if abs(v) < 1e6 else cr(v)

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

# 45 plataformas en 3 bloques de 15; cada bloque ocupa 4 horas. (sector dentro del bloque, profundidad)
PAD_GRP = [(0, 0), (0, 0), (0, 2), (0, 2), (1, 0), (1, 0), (1, 1), (1, 2), (2, 0), (2, 2),
           (3, 0), (3, 0), (3, 1), (3, 2), (3, 2)]
PAD_DEPTH = ["ENTRADA", "MEDIO", "FONDO"]

def pad_pos(pad):
    """(hora 1-12, profundidad 0 entrada / 1 medio / 2 fondo), mirando desde la ranura de entrada."""
    p = (int(pad) - 1) % 45
    sct, dep = PAD_GRP[p % 15]
    sct += (p // 15) * 4
    return (6 + sct) % 12 or 12, dep

def pad_clock(pad):
    return pad_pos(pad)[0]

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
        hour, dep = pad_pos(pad)
        RR = (rad, rad * 0.75, rad * 0.54, rad * 0.34)
        for h in range(12):
            a0, a1 = math.radians(h * 30 - 105), math.radians(h * 30 - 75)
            angs = [a0 + (a1 - a0) * t / 6 for t in range(7)]
            for k in range(3):
                ro, ri = RR[k], RR[k + 1]
                pts = [(cx + ro * math.cos(a), cy + ro * math.sin(a)) for a in angs] + \
                      [(cx + ri * math.cos(a), cy + ri * math.sin(a)) for a in reversed(angs)]
                on = (h or 12) == hour and k == dep
                pygame.draw.polygon(surf, ORANGE if on else BLACK, pts)
                pygame.draw.polygon(surf, DIM, pts, 1)
        k_ = 0.6 + 0.4 * math.sin(now * 3)
        arc = pygame.Rect(cx - rad - 7, cy - rad - 7, 2 * rad + 14, 2 * rad + 14)
        pygame.draw.arc(surf, tuple(int(c * k_) for c in RED[:3]), arc, math.radians(145), math.radians(215), 7)
        pygame.draw.arc(surf, tuple(int(c * k_) for c in GREEN[:3]), arc, math.radians(-35), math.radians(35), 7)
        pygame.draw.rect(surf, BLACK, (cx - 30, cy - 9, 60, 18))
        pygame.draw.rect(surf, WHITE, (cx - 30, cy - 9, 60, 18), 2)
        put(surf, F["small"], "ENTRADA", (cx, cy), WHITE, anchor="center")
        pygame.draw.circle(surf, RED, (cx - 40, cy), 6)
        pygame.draw.circle(surf, GREEN, (cx + 40, cy), 6)
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
            h_, d_ = pad_pos(pad)
            put(surf, F["btn"], f"a las {h_}  ·  {PAD_DEPTH[d_]}", (x0, y), ORANGE); y += 22
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
        return cx + dx / dd * r * ORR_XS[0], cy - dy / dd * r
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
NAVE_BTN = pygame.Rect(196, H - 58, 124, 36)          # EN VIVO
NAVE_BTN_BIO = pygame.Rect(196, H - 64, 124, 34)      # XENOBIOLOGIA: por encima de MUESTRAS SIN VENDER

def ship_pos(b):
    s_ = b.get("ship")
    if s_ != SHIPOV["src"]:              # el juego da una posicion nueva: manda la del juego
        SHIPOV["src"], SHIPOV["pos"] = s_, None
    return SHIPOV["pos"] or s_

def ship_here():
    if SHIPOV["cur"]:
        SHIPOV["pos"] = list(SHIPOV["cur"])
        tap_flash(("nave", 0))

def draw_compass(surf, d, b, btn=None):
    btn = btn or NAVE_BTN
    ship, lat, lon, R = ship_pos(b), b.get("lat"), b.get("lon"), b.get("R")
    out = bool((d or {}).get("Flags", 0) & (1 << 26)) or bool((d or {}).get("Flags2", 0) & 1)
    SHIPOV["cur"] = (lat, lon) if (out and lat is not None) else None
    if out and lat is not None and R:
        draw_button(surf, btn, "NAVE AQUÍ", None, F["btn"], lit=flash.get(("nave", 0), 0) > time.time())
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
    draw_compass(surf, d, b, NAVE_BTN_BIO)
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
    if mode == "A PIE" and in_fight(d, now):
        return draw_fight_big(surf, d, now)
    put(surf, F["big"], mode, (8, y), GREEN)
    if mode == "A PIE" and in_fight(d, now):
        tw_ = F["big"].size(mode)[0]
        r_ = pygame.Rect(16 + tw_, y + 2, 112, 22)
        on_ = int(now * 2) % 2 == 0
        pygame.draw.rect(surf, RED, r_, 0 if on_ else 2, border_radius=4)
        put(surf, F["small"], "EN COMBATE", r_.center, BLACK if on_ else RED, anchor="center")
    if mode == "A PIE":
        s_ = L.get("suit") or {}
        put(surf, F["small"], " · ".join(x for x in (s_.get("name"), s_.get("loadout")) if x), (W - 8, y + 6), ORANGE, 300, anchor="topright")
        y += 30
        oxy, hp = pctv(L.get("oxy")), pctv(L.get("health"))
        half = (W - 24) // 2
        bar(surf, 8, y, half, "OXÍGENO", oxy, RED if oxy is not None and oxy < 25 else BLUE)
        bar(surf, 16 + half, y, half, "SALUD", hp, RED if hp is not None and hp < 30 else GREEN)
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
        act_ = [c_ for c_ in [("ESTACIÓN", f2 & (1 << 3), BLUE), ("PLANETA", f2 & (1 << 4), BLUE),
                              ("RESPIRABLE", f2 & (1 << 16), GREEN), ("POCO O2", f2 & (1 << 6), RED),
                              ("SALUD BAJA", f2 & (1 << 7), RED), ("FRÍO", f2 & ((1 << 8) | (1 << 10)), BLUE),
                              ("CALOR", f2 & ((1 << 9) | (1 << 11)), RED), ("PLANEO", f2 & (1 << 12), ORANGE)] if c_[1]]
        y = chips(surf, act_[:4], y) if act_ else y
        Z = d.get("footcz") or {}
        P = d.get("pack") or {}
        if Z.get("n"):
            led = Z.get("led") or {}
            zt = (Z.get("zone") or "ZONA DE COMBATE").upper() + (f"  ·  por {Z['side']}" if Z.get("side") else "")
            put(surf, F["small"], zt, (8, y + 2), BLUE, W - 16)
            put(surf, F["btn"], f"{Z['n']} BAJAS", (8, y + 18), GREEN)
            put(surf, F["btn"], f"{crx(led.get('cr', 0))} cr sin cobrar", (120, y + 18), ORANGE, 230)
            if Z.get("rate"):
                put(surf, F["small"], f"{str(Z['rate']).replace('.', ',')} / min", (W - 8, y + 22), DIM, anchor="topright")
        if Z.get("n"):
            y += 40
        draw_cons_row(surf, d, 8, y + 2, F["btn"], 12)
        y += 4
        if not Z.get("n") and (P.get("n_items") or P.get("n_comp") or P.get("n_data")):
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
    led = ((d or {}).get("footcz") or {}).get("led") or {}
    if led.get("cr"):
        b, rw = led.get("bonds") or [0, 0], led.get("bounties") or [0, 0]
        put(surf, F["small"], "SIN COBRAR (bonos + recompensas)", (8, H - 54), DIM)
        put(surf, F["big"], f"{crx(led['cr'])} cr", (8, H - 40), RED)
        put(surf, F["small"], f"{b[0]} bonos {crx(b[1])} cr  ·  {rw[0]} recompensas {crx(rw[1])} cr", (8, H - 16), DIM, 330)
    elif s_.get("pending"):
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
    ("0.53", "12.9 GALNET: noticias oficiales y aviso de noticia nueva"),
    ("0.54", "Reloj: foto arriba y noticias GALNET subiendo"),
    ("0.55", "Pantalla grande ATRACADO: GALNET y carga/misión; fecha del juego"),
    ("0.56", "12.10 Objetivos comunitarios (web y los tuyos)"),
    ("0.57", "SALIR: shell en la HDMI y aviso en la pequeña"),
    ("0.58", "12 AJUSTES a la vista, pestañas de información y engranaje"),
    ("0.59", "Optimización de pantallas y aviso de BAJA TENSIÓN"),
    ("0.60", "Datos comprimidos, registro de errores, arranque y aviso thargoide"),
    ("0.61", "Pantalla grande: cuadros a todo lo ancho, texto más grande"),
    ("0.62", "Pantalla grande: modos 4 CUADROS, MIXTO y GRANDE (AJUSTES)"),
    ("0.63", "EMITIR pantallas por la red (PC, OBS, VR) y VOZ de la nave"),
    ("0.64", "Voz y pitidos en el PC: página /voz y en EMITIR"),
    ("0.65", "MANUAL de uso en AJUSTES y en http://IP:8080/manual"),
    ("0.66", "Bajas a pie y derribos con contador, bonos sin cobrar, zona de combate y luces del atraque"),
    ("0.67", "EN COMBATE a pie (grande en 2 cuadros) y salud baja al 75/50/25 %"),
    ("0.68", "MAPA de recorrido a pie, SRV y Rhino"),
    ("0.69", "Botiquines y células en avisos y MAPA, MARCAR RECARGA, HAS CAÍDO y COBRADO"),
    ("0.70", "Ratón y teclado; la HDMI puede mostrar el PANEL (TAB o clic derecho)"),
    ("0.71", "Llegada y señales, OPERATIONS, Merc Coin, copiloto, SISTEMA grande y clic desde el PC"),
    ("0.72", "NITIDEZ ALTA: pantalla grande a 1024x600 real (AJUSTES > PANTALLA)"),
    ("0.73", "ALERTAS y CAMBIO AUTO uno a uno (OPCIONES); NITIDEZ ALTA por defecto"),
    ("0.74", "Merc Coin rosa, PANEL nítido, teclas en la web, FPS, fecha del juego, plataforma exacta"),
    ("0.75", "SONIDO Y VOZ uno a uno (bajas en silencio); te atacan a pie > EN VIVO; mapa ZONA"),
    ("0.76", "Mapa a pie sin el vuelo del transporte, leyenda de símbolos y más zoom en ZONA"),
    ("0.77", "Teclas del juego (.binds), indicador de CPU/temperatura/FPS y modo PANEL ligero"),
    ("0.78", "Arreglo: el mapa a pie vuelve a dibujar el recorrido"),
    ("0.79", "Enlace energético: parado 8 s = RECARGANDO y punto de recarga en el mapa"),
    ("0.80", "Menú principal, música de combate y thargoide, Powerplay y ficha ESCUADRÓN"),
    ("0.81", "Inara (solo lectura): nombre de tu rango de escuadrón y otros CMDR en ESCUADRÓN"),
    ("0.82", "ESCUADRÓN por páginas: hasta 30 comandantes, conectados primero"),
    ("0.83", "Botiquines, células y explosivos (máximo por traje) siempre a la vista; EN COMBATE en grande"),
    ("0.84", "Cierre de emergencia del juego, ESCUADRÓN en AMIGOS, MENÚ PRINCIPAL en verde y arreglos"),
    ("0.85", "Cierre de emergencia: zona más grande en la barra de arriba y aviso de toques 1/3, 2/3"),
    ("0.86", "Salud < 30 %: pantalla roja; cierre en 3 s; copiloto en azul; arreglo del falso MENÚ PRINCIPAL al morir"),
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
            ("MUESTRAS BIO", X.get("bio", 0), WHITE), ("SEÑALES VISITADAS", X.get("signals", 0), WHITE)]
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
    draw_button(surf, SQ_BTN, "ESCUADRÓN  >", None, F["btn"], lit=flash.get(("sqbtn",), 0) > now)
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
            if y > H - 40:
                break
            put(surf, F["small"], n, (8, y), WHITE, 300)
            put(surf, F["small"], f"hace {mins} min" if mins < 60 else f"hace {mins // 60} h", (W - 8, y), DIM, anchor="topright")
            y += 17

def view_session3(surf, d, flags, now):
    if ui.get("sesstab"):
        return view_friends(surf, d, flags, now)
    view_session2(surf, d, flags, now)
    n = len(((d or {}).get("friends") or {}).get("on") or [])
    paid_ = (((d or {}).get("ops") or {}).get("crew") or {}).get("paid")
    put(surf, F["small"], f"toca para ver AMIGOS ({n} conectados)" + (f"  ·  copiloto -{crx(paid_)} cr" if paid_ else ""),
        (8, 252), GREEN if n else DIM, W - 16)

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
    if i == 0:
        ui["bye"] = time.time()
        sh = ("sleep 1; systemctl stop elite-panel; con2fbmap 1 0; "
              "cat /dev/zero > /dev/fb0 2>/dev/null; chvt 2; chvt 1; setterm --blank 0 --cursor on > /dev/tty1")
        subprocess.Popen(["sudo", "-n", "systemd-run", "--no-block", "--collect", "sh", "-c", sh])
        return
    subprocess.Popen(["sudo", "-n"] + cmd)

def view_sub12(surf, d, flags, now):
    for i, (n, name) in enumerate([("1", "LOG"), ("2", "STREAM"), ("3", "RANGOS"), ("4", "AJUSTES"), ("5", "MATERIAL"), ("6", "PORTANAV."), ("7", "MERCADO"), ("8", "NOTAS"), ("9", "GALNET"), ("10", "OBJ. COM.")]):
        draw_button(surf, grid(i, 4, 3), n, name, F["big"], lit=flash.get((12, i), 0) > now)
    nn = len(galnet["new"])
    if nn:
        put(surf, F["small"], f"{nn} noticia{'s' if nn > 1 else ''} nueva{'s' if nn > 1 else ''} en GALNET", (W - 8, H - 18), GREEN, anchor="topright")

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
    items = [("CAMBIO AUTO", cfg["auto"]), ("ALERTAS", cfg["alerts"]), ("SONIDO", cfg["sound"]), ("COLOR", None),
             ("VOZ", cfg.get("voice", False)), ("EMITIR", cfg.get("stream", False)), ("TECLAS", None),
             ("CERRAR JUEGO", cfg.get("killbtn", True))]
    for i, (name, on) in enumerate(items):
        r = grid(i, 4, 2)
        if name == "TECLAS":
            miss = len(BINDS["missing"])
            draw_button(surf, r, name, (f"{miss} SIN TECLA  >" if miss else "TODAS  >") if BINDS["file"] else "DE FÁBRICA  >",
                        F["btn"], filled=bool(BINDS["file"]) and not miss, lit=flash.get((124, i), 0) > now)
            continue
        lit = flash.get((124, i), 0) > now
        if on is None:
            draw_button(surf, r, name, THEMES[cfg["theme"]][0], F["btn"], filled=True, lit=lit)
            continue
        sub = "ACTIVADO" if on else "DESACTIVADO"
        if name in ("ALERTAS", "CAMBIO AUTO", "SONIDO"):
            L, st, _, _, df = EVL[{"ALERTAS": 161, "CAMBIO AUTO": 162, "SONIDO": 163}[name]]
            n = sum(1 for k, _ in L if (cfg.get(st) or {}).get(k, df.get(k, True))) if on else 0
            on = n > 0
            sub = f"{n} de {len(L)}  >"
        if name == "VOZ" and not voice_ok():
            sub = "falta espeak-ng"
        if name == "CERRAR JUEGO":
            sub = "3 toques en el sistema" if on else "DESACTIVADO"
        if name == "EMITIR" and on:
            sub = stream["err"] or f"{my_ip()}:{STREAM_PORT}" + (f"  ({stream['clients']})" if stream["clients"] else "")
        draw_button(surf, r, name, sub, F["btn"] if F["btn"].size(name)[0] < r.w - 10 else F["small"], filled=on, lit=lit)

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

IDLE_PHOTO = (66, 70)
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

def idle_crawl(surf, now, box=None, waiting=True):
    box = box or IDLE_BOX
    pygame.draw.rect(surf, DIM, box, 1, border_radius=6)
    put(surf, F["small"], "NOTICIAS GALNET", (box.x + 8, box.y + 5), ORANGE)
    if power["now"] and int(now * 2) % 2 == 0:
        put(surf, F["small"], "BAJA TENSIÓN", (box.right - 8, box.y + 5), RED, anchor="topright")
        draw_bolt(surf, box.right - 108, box.y + 2, RED, 0.85)
    elif waiting and int(now) % 4 < 3 and not (state.get("data") or {}).get("menu"):
        t_ = "ESPERANDO A ELITE DANGEROUS"
        w_ = F["small"].size(t_)[0] + 14
        r_ = pygame.Rect(box.right - 6 - w_, box.y + 2, w_, 18)
        pygame.draw.rect(surf, RED, r_, border_radius=4)
        put(surf, F["small"], t_, r_.center, (255, 215, 0), anchor="center")
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
    put(surf, F["small"], game_date(), (cx + 4, 132), BLUE, anchor="midtop")
    put(surf, F["small"], f"IP {ip}" if ip else "SIN RED", (W - 8, 132), DIM if ip else RED, anchor="topright")
    idle_crawl(surf, now)
    put(surf, F["small"], "toca la pantalla para abrir el menú", (W // 2, H - 9), DIM, anchor="center")

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
xa = XaDict({"seq": None, "a": None})
NEON = (90, 200, 255)

def xa_notes(d, now):
    try:
        _xa_notes(d, now)
    finally:
        XA_K[0] = None

def _xa_notes(d, now):
    if not d:
        return
    XA_K[0] = "hplow"
    hp_ = (d.get("live") or {}).get("health")
    if d.get("Flags2", 0) & 1 and isinstance(hp_, (int, float)):
        lvl = 3 if hp_ < HP_CRIT else 2 if hp_ < 0.5 else 1 if hp_ < 0.75 else 0
        prev = xa.get("hplvl", 0)
        if lvl == 3 and prev < 3:
            if ev_on("hplow"):
                HPC["t0"] = now
                play("alarm")
        elif lvl > prev:
            xa["a"] = dict(until=now + (4 if lvl > 1 else 3), col=ORANGE if lvl == 1 else RED, title="SALUD BAJA",
                           big=f"{hp_ * 100:.0f} %", lines=["usa un botiquín" if lvl < 3 else "¡BOTIQUÍN YA!"])
            if lvl > 1:
                play("alarm")
        xa["hplvl"] = 0 if lvl == 0 else max(prev, lvl)
    else:
        xa["hplvl"] = 0
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
            XA_K[0] = {"hp": "hplow", "cold": "temp", "hot": "temp", "fuel": "srvfuel"}.get(k, k)
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
        XA_K[0] = kind
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
            veh = p[3] if len(p) > 3 else "N"
            num = p[4] if len(p) > 4 and p[4].isdigit() and p[4] != "0" else ""
            name = "BAJA" if veh == "F" else "DERRIBO (SRV)" if veh == "S" else "DERRIBO"
            col = RED if p[2] == "P" else BLUE if p[2] in ("B", "T") else GREEN
            lines = [p[0]]
            if len(p) > 6 and p[6] not in ("", "0"):
                lines.append(f"{p[5]} sin cobrar  ·  {crx(float(p[6]))} cr")
            xa["a"] = dict(until=now + 3, col=col, title=f"{name} nº {num}" if num else name,
                           big=f"+{crx(rew)} cr" if rew else "PvP", lines=lines)
        elif kind == "dropship":
            xa["a"] = dict(until=now + 6, col=ORANGE, title="TRANSPORTE A ZONA DE COMBATE",
                           big=(p[0] or "").upper(), lines=[p[1]] if len(p) > 1 and p[1] else [])
        elif kind == "deploy":
            st = {"War": "EN GUERRA", "CivilWar": "EN GUERRA CIVIL"}.get(p[2] if len(p) > 2 else "", p[2] if len(p) > 2 else "")
            sub = (f"Asentamiento de {p[1]}" if len(p) > 1 and p[1] else "") + (f"  ·  {st}" if st else "")
            xa["a"] = dict(until=now + 6, col=RED, title="¡DESPLEGADO!", big=(p[0] or "").upper(), lines=[sub] if sub else [])
        elif kind == "escaped" and len(p) >= 2:
            xa["a"] = dict(until=now + 5, col=GREEN, title="¡ESCAPADO!", big=p[0] or "INTERDICCIÓN",
                           lines=["era un comandante" if p[1] == "1" else "era un NPC"])
        elif kind == "submitted" and len(p) >= 2:
            xa["a"] = dict(until=now + 5, col=ORANGE, title="TE HAS SOMETIDO", big=p[0] or "INTERDICCIÓN",
                           lines=["COMANDANTE" if p[1] == "1" else "NPC", "carga el FSD y salta"])
        elif kind == "rebuy" and len(p) >= 2:
            xa["a"] = dict(until=now + 8, col=RED, title="CASCO CRÍTICO", big=f"{p[0]}%",
                           lines=[f"REBUY {cr(float(p[1] or 0))} cr", "considera huir"])
        elif kind == "arrive" and len(p) >= 5:
            nm, t_, body_, btype = p[0], int(p[1] or 0), p[2], p[3]
            if nm and (p[4] == "1" or btype == "Station"):
                xa["a"] = dict(until=now + 4, col=BLUE, title="LLEGADA A", big=nm.upper(), lines=[body_] if body_ and body_ != nm else [])
                if auto_on("arrst"):
                    ui["view"] = 8
            elif nm:
                conflict = "conflict" in nm.lower()
                xa["a"] = dict(until=now + 6, col=RED if conflict else threat_col(t_), title=f"SEÑAL  ·  AMENAZA {t_}",
                               big=nm.upper(), lines=["zona de conflicto" if conflict else "salida de supercrucero"])
                if t_ >= 3 or conflict:
                    play("alarm")
                    if auto_on("arrsig"):
                        ui["view"] = 6
            elif btype == "Station" and body_:
                xa["a"] = dict(until=now + 3, col=BLUE, title="LLEGADA A", big=body_.upper(), lines=[])
        elif kind == "thrown" and len(p) >= 3:
            mx_ = suit_max(d).get(cons_kind(p[0]) or "", None)
            xa["a"] = dict(until=now + 2, col=GREY, title=f"{p[1].upper()} LANZADO",
                           big=f"quedan {p[2]}" + (f" de {mx_}" if mx_ else ""), lines=[])
        elif kind == "opstart" and len(p) >= 2:
            xa["a"] = dict(until=now + 6, col=ORANGE, title="OPERACIÓN INICIADA", big=(p[0] or "").upper(),
                           lines=[f"escuadrón {p[1]}"] if p[1] else [])
            play("ok")
        elif kind == "opend" and len(p) >= 5:
            l1 = f"{p[0]} derribos  ·  {p[4]} min" + (f"  ·  +{p[3]} méritos" if p[3] not in ("", "0") else "")
            lm = (f"+{p[2]} MERC COIN", MERC) if p[2] not in ("", "0") else ""
            xa["a"] = dict(until=now + 12, col=GREEN, title="OPERACIÓN TERMINADA", big=f"{crx(float(p[1] or 0))} cr",
                           lines=[l1, lm, "cobra al salir, en una estación"])
            play("ok")
        elif kind == "pickup" and len(p) >= 3:
            xa["a"] = dict(until=now + 2.5, col=YELLOW if p[0] == "energycell" else GREEN if p[0] == "healthpack" else GREY,
                           title=f"+1 {p[1].upper()}", big=f"llevas {p[2]}", lines=[])
        elif kind == "usecons" and len(p) >= 3:
            left = int(p[2]) if p[2].isdigit() else -1
            xa["a"] = dict(until=now + (4 if left == 0 else 2.5), col=RED if left == 0 else ORANGE,
                           title=f"{p[1].upper()} USADO", big="¡NO TE QUEDAN!" if left == 0 else f"quedan {left}", lines=[])
            if left == 0:
                play("alarm")
        elif kind == "redeem" and len(p) >= 2:
            amt, tr = float(p[0] or 0), float(p[1] or 0)
            xa["a"] = dict(until=now + 7, col=GREEN, title="COBRADO", big=f"{crx(amt)} cr",
                           lines=[f"el panel llevaba sumados {crx(tr)} cr"] + ([f"diferencia {'+' if amt >= tr else ''}{crx(amt - tr)} cr"] if tr else []))
        elif kind == "died" and len(p) >= 4 and (((d or {}).get("footcz") or {}).get("onfoot") or (d or {}).get("Flags2", 0) & 1):
            xa["a"] = dict(until=now + 10, col=RED, title="HAS CAÍDO", big=p[0] or "",
                           lines=["al reaparecer en la zona conservas los bonos"])
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
        elif kind == "cg" and len(p) >= 2:
            xa["a"] = dict(until=now + 6, col=GREEN, title="OBJETIVO COMUNITARIO", big=p[1].upper(), lines=[p[0]])
        elif kind == "shutdown":
            xa["a"] = dict(until=now + 8, col=(120, 230, 120), title="¡SISTEMAS APAGADOS!", big="ENCUENTRO THARGOIDE",
                           lines=["la nave se reiniciará en unos segundos"])
            play("alarm")
        elif kind == "thargmusic":
            xa["a"] = dict(until=now + 6, col=(120, 230, 120), title="ENCUENTRO THARGOIDE",
                           big="MÚSICA DE ALERTA", lines=["el juego ha puesto la música thargoide"])
            play("alarm")
        elif kind == "gravity" and len(p) >= 2:
            g = float(p[0])
            xa["a"] = dict(until=now + 7, col=RED if g >= 2 else ORANGE, title="GRAVEDAD ALTA",
                           big=f"{p[0].replace('.', ',')} G", lines=[p[1], "aterriza despacio" if g >= 2 else ""])

MERC = (255, 80, 200)      # rosa de las Merc Coin, como en el juego

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
            t_, c2 = ln_ if isinstance(ln_, tuple) else (ln_, col)
            put(surf, F["btn"], t_, (cx, y), c2, box.w - 20, anchor="midtop")
        y += 26

PANEL_VER = "v0.86 · 01/11/2026 12:47"

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
    if False:
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
            if y0 > 146:
                continue
            surf.set_at((int(x), int(y0)), (b, b, b))
        r = pygame.Rect(0, 0, 124, 128); r.center = IDLE_PHOTO
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
BIG_SETS = {"COMBATE A PIE": [100, 5, 150], "VIAJE": [100, 3, 71, 72], "APROXIMACIÓN": [100, 72, 73, 74], "SUPERFICIE": [100, 73, 5, 150],
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

BIG_ROT = 10          # segundos por cuadro en modo GRANDE
BIGMODES = {"4": "4 CUADROS", "MIXTO": "MIXTO", "GRANDE": "GRANDE"}

def big_cell(S, cell, v, d, flags, now, r, font, how, extra=""):
    if v in (72, 150):
        BIG["fast"] = True          # mapa del sistema o plano a pie: se mueven
    if v == 150:
        pygame.draw.rect(S, DIM, r.inflate(-4, -4), 1, border_radius=6)
        lab = font.render("MAPA" + extra, True, DIM)
        S.blit(lab, (r.x + 10, r.y + 4))
        top = r.y + lab.get_height() + 6
        draw_map(S, pygame.Rect(r.x + 6, top, r.w - 12, r.bottom - 6 - top), d, now)
        return
    fn = view_navbig if v == 3 else view_orrery_big if v == 72 else VIEWS.get(v)
    sharp = bool(cfg.get("sharp")) and fn is not None
    if not sharp:
        big_cell_draw(cell, fn, d, flags, now)
    pygame.draw.rect(S, DIM, r.inflate(-4, -4), 1, border_radius=6)
    lab = font.render(str(MENU.get(v, v)).upper() + extra, True, DIM)
    S.blit(lab, (r.x + 10, r.y + 4))
    top = r.y + lab.get_height() + 6
    src = cell.subsurface((0, TOP, W, H - TOP))
    area = pygame.Rect(r.x + 4, top, r.w - 8, r.bottom - 3 - top)
    if sharp:
        if hi_cell(S, fn, d, flags, now, area, how):
            return
        big_cell_draw(cell, fn, d, flags, now)
    if how == "fill":
        big_fill(S, src, area)
        return
    sc = min(area.w / src.get_width(), area.h / src.get_height())
    size = (int(src.get_width() * sc), int(src.get_height() * sc))
    try:
        img = pygame.transform.smoothscale(src, size)
    except ValueError:
        img = pygame.transform.scale(src, size)
    y = area.y if how == "top" else area.centery - size[1] // 2
    S.blit(img, (area.centerx - size[0] // 2, y))

def big_fill(dst, src, area):
    """Escala el cuadro a todo el hueco (un poco mas ancho que alto) para no dejar bandas a los lados."""
    try:
        img = pygame.transform.smoothscale(src, area.size)
    except ValueError:
        img = pygame.transform.scale(src, area.size)
    dst.blit(img, area.topleft)

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
    if in_fight(d):
        return "COMBATE A PIE"
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
    BIG["fast"] = False
    if hdmi_panel() and not ui.get("bye") and render_big_panel(S):
        return
    if ui.get("bye"):
        S.fill(BLACK); return
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
    if d.get("menu"):
        draw_idle(cell, now); big_blit(S, cell, S.get_rect())
        put(S, fbig, "MENÚ PRINCIPAL", (bw // 2, bh - 40), GREEN, anchor="center")
        return
    mode = big_mode(d, flags)
    hh = 44
    tw = put(S, fbig, (d.get("system") or "---").upper(), (12, 9), ORANGE, 400)
    put(S, fsm, mode, (12 + tw + 14, 16), GREEN, max(40, bw // 2 + 10 - (12 + tw + 14)))
    fuel, cap = (d.get("Fuel") or {}).get("FuelMain"), d.get("fuelcap")
    if flags & (1 << 26):
        fuel, cap = (d.get("Fuel") or {}).get("FuelReservoir"), None
    if fuel is not None:
        bx = pygame.Rect(bw // 2 + 20, 8 if cfg.get("perf") else 12, 160, 14 if cfg.get("perf") else 18)
        pygame.draw.rect(S, DIM, bx, 1)
        if cap:
            pct = max(0.0, min(1.0, fuel / cap))
            pygame.draw.rect(S, RED if pct < 0.25 else ORANGE, (bx.x + 2, bx.y + 2, int((bx.w - 4) * pct), bx.h - 4))
        put(S, fsm, f"FUEL {fuel:.1f} t", (bx.right + 10, 6 if cfg.get("perf") else 14), ORANGE)
    put(S, fbig, time.strftime("%H:%M"), (bw - 12, 9), ORANGE, anchor="topright")
    if cfg.get("perf"):
        perf_draw(S, bw // 2 + 20, 27)
    put(S, fsm, game_date().upper(), (bw - 28 - fbig.size(time.strftime("%H:%M"))[0], 16), BLUE, anchor="topright")
    pygame.draw.line(S, DIM, (0, hh - 2), (bw, hh - 2), 1)
    cw, ch = bw // 2, (bh - hh) // 2
    cells = list(BIG_SETS[mode])
    if 74 in cells and not ((d.get("rings") or {}).get("rings") or (d.get("rings") or {}).get("signals")):
        cells[cells.index(74)] = 128
    if mode == "ATRACADO" and 4 in cells:
        cells[cells.index(4)] = atr_cell(d, now)
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
    bm = cfg.get("bigmode", "4")
    if bm == "GRANDE":
        # un cuadro a pantalla completa (letra al doble); van rotando cada BIG_ROT segundos
        k = int(now // BIG_ROT) % len(cells)
        r = pygame.Rect(0, hh, bw, bh - hh)
        big_cell(S, cell, cells[k], d, flags, now, r, fbig, "fit", f"  {k + 1}/{len(cells)}")
        pct = (now % BIG_ROT) / BIG_ROT
        pygame.draw.rect(S, DIM, (r.right - 130, r.y + 14, 110, 6), 1)
        pygame.draw.rect(S, ORANGE, (r.right - 129, r.y + 15, int(108 * pct), 4))
        return
    if bm == "MIXTO":
        # el cuadro principal grande a la izquierda; los demas pequenos a la derecha
        main = cells[1] if len(cells) > 1 else cells[0]
        rest = [c for c in cells if c != main][:3]
        bwl = bw * 2 // 3
        big_cell(S, cell, main, d, flags, now, pygame.Rect(0, hh, bwl, bh - hh), fbig, "top")
        if rest:
            h3 = (bh - hh) // len(rest)
            for k, v in enumerate(rest):
                big_cell(S, cell, v, d, flags, now, pygame.Rect(bwl, hh + k * h3, bw - bwl, h3), fsm, "fill")
        return
    if len(cells) == 3 and cells[2] == 150:
        # combate a pie: EN VIVO arriba a la izquierda, botones abajo a la izquierda y el MAPA a toda la altura
        big_cell(S, cell, cells[0], d, flags, now, pygame.Rect(0, hh, cw, ch), fsm, "fill")
        big_cell(S, cell, cells[1], d, flags, now, pygame.Rect(0, hh + ch, cw, ch), fsm, "fill")
        big_cell(S, cell, 150, d, flags, now, pygame.Rect(cw, hh, cw, bh - hh), fsm, "fill")
        return
    if len(cells) == 2:
        for i, v in enumerate(cells):
            big_cell(S, cell, v, d, flags, now, pygame.Rect(i * cw, hh, cw, bh - hh), fbig, "fit")
        return
    for i, v in enumerate(cells):
        r = pygame.Rect((i % 2) * cw, hh + (i // 2) * ch, cw, ch)
        big_cell(S, cell, v, d, flags, now, r, fsm, "fill")

def big_frame():
    if BIG["fb"] is None:
        if BIG["dev"] is None and not big_open():
            BIG["dev"] = False
        if BIG["fb"] is None:
            return
    try:
        PERF["frames"] += 1
        render_big()
        draw_hpcrit(BIG["surf"], time.time())
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
                    if ev_on("galnet"):
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


# ---------- fecha del juego y cuadro GALNET de la pantalla grande ----------
MES3 = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]

def game_date():
    g = time.gmtime()
    return f"{g.tm_mday} {MES3[g.tm_mon - 1]} {g.tm_year + 1286}"

def view_galnet_cell(surf, d, flags, now):
    idle_crawl(surf, now, pygame.Rect(4, TOP + 2, W - 8, H - TOP - 6), waiting=False)

ATR_ROT = [(133, 20), (4, 4), (132, 20)]     # GALNET 20 s, CARGA/MISIÓN 4 s, OBJ. COMUNITARIOS 20 s

def atr_cell(d, now):
    rot = [(133, 20)]
    if (d or {}).get("cargo") or (d or {}).get("missions"):
        rot.append((4, 4))
    if 132 in VIEWS and cg_all(d):
        rot.append((132, 20))
    if len(rot) == 1:
        return 133
    t = now % sum(s_ for _, s_ in rot)
    for v, s_ in rot:
        if t < s_:
            return v
        t -= s_
    return 133

VIEWS[133] = view_galnet_cell
MENU[133] = "GALNET"


# ---------- 12.10 objetivos comunitarios ----------
CG_URL = "https://api.orerve.net/2.0/website/initiatives/list?lang=es"
cgoals = {"list": [], "t": 0, "err": "", "page": 0, "d": None}

def _first(it, *keys):
    for k in keys:
        v = it.get(k)
        if v not in (None, "", []):
            return v
    return None

def _num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None

def cg_fetch():
    import urllib.request
    req = urllib.request.Request(CG_URL, headers={"User-Agent": "PanelElite/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    items = data.get("activeInitiatives") if isinstance(data, dict) else data
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        out.append({"title": str(_first(it, "title", "name") or "?"),
                    "sys": str(_first(it, "starsystem_name", "system_name", "systemName", "system") or ""),
                    "market": str(_first(it, "market_name", "marketName", "station_name", "station") or ""),
                    "expiry": str(_first(it, "expiry", "end_date", "endDate", "expires") or ""),
                    "qty": _num(_first(it, "qty", "current_qty", "progress", "current")),
                    "target": _num(_first(it, "target_qty", "targetQty", "target")),
                    "text": galnet_text(str(_first(it, "objective", "bulletin", "description") or ""))[:300]})
    return out

def cg_loop():
    while True:
        try:
            cgoals["list"], cgoals["t"], cgoals["err"] = cg_fetch(), time.time(), ""
            time.sleep(1800)
        except Exception as e:
            cgoals["err"] = str(e)[:60]
            print("objetivos:", e, flush=True)
            time.sleep(600)

threading.Thread(target=cg_loop, daemon=True).start()

def cg_all(d):
    mine = [dict(g, me=True) for g in ((d or {}).get("mycg") or [])]
    names = {g["title"].lower() for g in mine}
    return mine + [g for g in cgoals["list"] if g["title"].lower() not in names]

def cg_left(exp):
    import calendar
    e = (exp or "").replace("Z", "")
    for txt, fmt in ((e[:19], "%Y-%m-%dT%H:%M:%S"), (e[:19], "%Y-%m-%d %H:%M:%S"), (e[:10], "%Y-%m-%d")):
        try:
            sec = calendar.timegm(time.strptime(txt, fmt)) - time.time()
            break
        except ValueError:
            continue
    else:
        return exp[:16]
    if sec <= 0:
        return "terminado"
    dd, hh = int(sec // 86400), int(sec % 86400 // 3600)
    return f"quedan {dd}d {hh}h" if dd else f"quedan {hh}h {int(sec % 3600 // 60)}m"

def _tier(t):
    m = re.search(r"\d+", t or "")
    return int(m.group()) if m else None

CG_PER = 2
CG_PAGE = pygame.Rect(W - 118, TOP + 2, 110, 28)

def view_cgoals(surf, d, flags, now):
    cgoals["d"] = d
    L = cg_all(d)
    pages = max(1, (len(L) + CG_PER - 1) // CG_PER)
    pg = cgoals["page"] % pages
    if cgoals["err"] and not L:
        info, col = cgoals["err"], RED
    elif cgoals["t"]:
        info, col = f"{len(L)} activo{'s' if len(L) != 1 else ''} · actualizado " + time.strftime("%H:%M", time.localtime(cgoals["t"])), DIM
    else:
        info, col = "descargando...", DIM
    put(surf, F["small"], info, (8, TOP + 9), col, W - 140)
    if pages > 1:
        draw_button(surf, CG_PAGE, f"PÁG {pg + 1}/{pages} >", None, F["small"])
    if not L:
        put(surf, F["btn"], "No hay objetivos comunitarios activos", (W // 2, (H + TOP) // 2), DIM, anchor="center")
        return
    for i, g in enumerate(L[pg * CG_PER:(pg + 1) * CG_PER]):
        r = pygame.Rect(6, TOP + 34 + i * 116, W - 12, 110)
        me = g.get("me")
        pygame.draw.rect(surf, GREEN if me else DIM, r, 1, border_radius=5)
        put(surf, F["btn"], g["title"], (r.x + 8, r.y + 4), ORANGE, r.w - 16)
        where = " · ".join(x for x in (g.get("sys", "").upper(), g.get("market", "")) if x)
        put(surf, F["small"], where, (r.x + 8, r.y + 24), WHITE, r.w - 140)
        left = "COMPLETADO" if g.get("complete") else cg_left(g.get("expiry", ""))
        put(surf, F["small"], left, (r.right - 8, r.y + 24), GREEN if g.get("complete") else BLUE, anchor="topright")
        bar = pygame.Rect(r.x + 8, r.y + 44, r.w - 16, 14)
        pygame.draw.rect(surf, DIM, bar, 1)
        t, top = _tier(g.get("tier")), _tier(g.get("top"))
        if t is not None and top:
            pct, txt = min(1.0, t / top), f"NIVEL {t} de {top}"
        elif g.get("qty") is not None and g.get("target"):
            pct = min(1.0, g["qty"] / g["target"]); txt = f"{fnum(g['qty'], 0)} / {fnum(g['target'], 0)}"
        else:
            pct, txt = None, ""
        if pct is not None:
            pygame.draw.rect(surf, GREEN if me else ORANGE, (bar.x + 2, bar.y + 2, int((bar.w - 4) * pct), bar.h - 4))
        put(surf, F["small"], txt, (r.x + 8, r.y + 62), GREEN if me else ORANGE)
        if me:
            if g.get("contrib"):
                put(surf, F["small"], f"{fnum(g['contrib'], 0)} pilotos", (r.right - 8, r.y + 62), DIM, anchor="topright")
            mine = f"TU APORTACIÓN: {fnum(g.get('mine') or 0, 0)}"
            if g.get("band"):
                mine += f"   ·   estás en el {g['band']}% mejor"
            if g.get("toprank"):
                mine += "   ·   TOP"
            put(surf, F["small"], mine, (r.x + 8, r.y + 82), GREEN, r.w - 16)
        elif g.get("text"):
            put(surf, F["small"], g["text"].replace("\n", " "), (r.x + 8, r.y + 82), DIM, r.w - 16)

VIEWS[132] = view_cgoals
MENU[132] = "OBJETIVOS COMUNITARIOS"
PARENT[132] = 12


# ---------- pantalla de SALIR ----------
def draw_bye(surf):
    surf.fill(BLACK)
    _orig_rect(surf, ORANGE, (0, 0, W, H), 2)
    put(surf, F["num"], "PANEL PARADO", (W // 2, 70), ORANGE, W - 20, anchor="center")
    put(surf, F["btn"], "El shell está en la pantalla HDMI", (W // 2, 125), WHITE, W - 20, anchor="center")
    put(surf, F["small"], "Para volver a arrancar el panel:", (W // 2, 175), DIM, anchor="center")
    put(surf, F["btn"], "sudo systemctl start elite-panel", (W // 2, 200), GREEN, W - 20, anchor="center")
    put(surf, F["small"], "o reinicia la Pi", (W // 2, 235), DIM, anchor="center")
    put(surf, F["small"], PANEL_VER.split(" · ")[0], (W // 2, H - 20), DIM, anchor="center")


# ---------- v0.58: 12 AJUSTES, pestanas de informacion y engranaje ----------
TABS = [[(3, "NAVEGACIÓN"), (128, "NOTAS")],
        [(4, "CARGA/MISIÓN"), (125, "MATERIALES")],
        [(8, "ESTACIÓN"), (127, "MERCADO"), (126, "PORTANAVES")],
        [(11, "SESIÓN"), (130, "GALNET"), (132, "OBJ.COM"), (123, "RANGOS")]]
TAB_OF = {129: 128, 131: 130}          # pantallas de detalle -> su pestana
GEAR = pygame.Rect(W - 50, 2, 46, TOP - 8)      # engranaje a la derecha del todo
MENU.update({12: "AJUSTES", 11: "SESIÓN·GALNET"})
for _v in (123, 125, 126, 127, 128, 130, 132):
    PARENT[_v] = 0
PARENT.update({121: 12, 122: 12, 1244: 12, 1245: 12}); MENU[1244] = "OPCIONES"

def tab_group(v):
    v = TAB_OF.get(v, v)
    for g in TABS:
        if any(t == v for t, _ in g):
            return g, v
    return None, v

def tab_rects(v):
    g, cur = tab_group(v)
    if not g:
        return []
    out, x = [], BACK.right + 4
    for t, name in g:
        w = F["small"].size(name)[0] + 16
        out.append((t, name, pygame.Rect(x, 35, w, 19), t == cur))
        x += w + 3
    return out

def draw_tabs(surf, v):
    for t, name, r, on in tab_rects(v):
        new = t == 130 and galnet["new"]
        col = GREEN if new else ORANGE
        if on:
            pygame.draw.rect(surf, col, r, border_radius=4)
            put(surf, F["small"], name, r.center, BLACK, anchor="center")
        else:
            pygame.draw.rect(surf, col if new else DIM, r, 1, border_radius=4)
            put(surf, F["small"], name, r.center, col, anchor="center")

def draw_gear(surf, v, now):
    on = v in (12, 121, 122, 1244, 1245)
    col = WHITE if flash.get(("gear",), 0) > now else ORANGE
    if on:
        pygame.draw.rect(surf, ORANGE, GEAR, 2, border_radius=6)
    cx, cy = GEAR.center
    rot = now * 40                                   # gira despacio (40 grados por segundo)
    for a in range(8):
        r_ = math.radians(a * 45 + rot)
        pygame.draw.line(surf, col, (cx + 11 * math.cos(r_), cy + 11 * math.sin(r_)),
                         (cx + 17 * math.cos(r_), cy + 17 * math.sin(r_)), 6)
    pygame.draw.circle(surf, col, (cx, cy), 13)
    pygame.draw.circle(surf, BLACK, (cx, cy), 5)
    if power["now"] and int(now * 2) % 2 == 0:
        draw_bolt(surf, GEAR.x - 20, 28, RED)

def tap_topbar(x, y, v):
    if x >= GEAR.x - 4:
        tap_flash(("gear",)); ui["view"] = 12; return True
    for t, _, r, _ in tab_rects(v):
        if r.inflate(2, 10).collidepoint(x, y):
            ui["view"] = t; ui["page4"] = 0; return True
    return False

SET12 = [("OPCIONES", 1244), ("ESTILO", "style"), ("BORDES", "borders"), ("ICONOS", "icons"),
         ("VERSIONES", 1245), ("LOG", 121), ("STREAM", 122), ("PANTALLA", 160),
         ("SALIR", 0), ("REINICIAR", 1), ("APAGAR", 2), ("MANUAL", 140)]

def view_sub12(surf, d, flags, now):
    c, until = ui["confirm"]
    for i, it in enumerate(SET12):
        if not it:
            continue
        name, act = it
        r = grid(i, 4, 3)
        sub = {"style": "CABINA" if style["cab"] else "CLÁSICO",
               "borders": "SÍ" if style.get("borders", True) else "NO",
               "icons": "SÍ" if ICONS_ON[0] else "NO",
               "bigmode": BIGMODES.get(cfg.get("bigmode", "4"), "4 CUADROS")}.get(act) if isinstance(act, str) else (
                   f"{BIGMODES.get(cfg.get('bigmode', '4'), '4 CUADROS')} · {'ALTA' if cfg.get('sharp') else 'NORMAL'}" if act == 160 else None)
        if i in (8, 9, 10):
            sure = c == ("pw", act) and time.time() < until
            draw_button(surf, r, "¿SEGURO?" if sure else name, None if sure else "toca 2 veces", F["btn"],
                        filled=sure, lit=flash.get((1240, act), 0) > now)
        else:
            draw_button(surf, r, name, sub, F["btn"], filled=act == "style" and style["cab"],
                        lit=flash.get((12, i), 0) > now)

def tap_sub12(x, y):
    for i, it in enumerate(SET12):
        if not it or not grid(i, 4, 3).collidepoint(x, y):
            continue
        name, act = it
        if i in (8, 9, 10):
            power_tap(act); return
        tap_flash((12, i))
        if act == "style":
            style_toggle()
        elif act == "borders":
            borders_toggle()
        elif act == "icons":
            icons_toggle()
        elif act == "bigmode":
            order = list(BIGMODES)
            cfg["bigmode"] = order[(order.index(cfg.get("bigmode", "4")) + 1) % len(order)]
            save_cfg()
        else:
            ui["view"] = act
        return

VIEWS[12] = view_sub12


# ---------- alimentacion de la Pi (vcgencmd get_throttled) ----------
power = {"now": False, "past": False, "warned": 0, "ok": False}

def power_loop():
    while True:
        try:
            out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=5).stdout
            v = int(out.strip().split("=")[1], 16)
            power.update(now=bool(v & 1), past=bool(v & 0x10000), ok=True)
            if power["now"] and time.time() - power["warned"] > 600 and ev_on("power"):
                power["warned"] = time.time()
                set_alert("BAJA TENSIÓN", "a la Pi le falta corriente: revisa la alimentación", RED, 5)
        except Exception:
            pass
        time.sleep(10)

threading.Thread(target=power_loop, daemon=True).start()

def draw_bolt(surf, x, y, col, k=1.0):
    pts = [(6, 0), (0, 11), (5, 11), (2, 20), (11, 7), (6, 7), (9, 0)]
    pygame.draw.polygon(surf, col, [(x + px * k, y + py * k) for px, py in pts])

def power_box(surf, r):
    pygame.draw.rect(surf, DIM, r, 1, border_radius=6)
    put(surf, F["small"], "ALIMENTACIÓN", (r.centerx, r.y + 10), DIM, anchor="midtop")
    if not power["ok"]:
        txt, col = "sin datos", DIM
    elif power["now"]:
        txt, col = "¡BAJA!", RED
    elif power["past"]:
        txt, col = "AVISOS", ORANGE
    else:
        txt, col = "CORRECTA", GREEN
    put(surf, F["btn"], txt, (r.centerx, r.centery + 2), col, r.w - 8, anchor="center")
    sub = "ahora mismo" if power["now"] else "desde que arrancó" if power["past"] else ""
    if sub:
        put(surf, F["small"], sub, (r.centerx, r.bottom - 22), DIM, r.w - 8, anchor="midtop")


# ---------- registro de errores: /home/ortem/panel.log y pantalla LOG ----------
import builtins, traceback, os as _os
PANEL_LOG = "/home/ortem/panel.log"
_err_seen = {}

def plog(*a, **k):
    msg = " ".join(str(x) for x in a)
    builtins.print(msg, flush=True)
    try:
        if _os.path.exists(PANEL_LOG) and _os.path.getsize(PANEL_LOG) > 300000:
            _os.replace(PANEL_LOG, PANEL_LOG + ".1")
        with open(PANEL_LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%d/%m %H:%M:%S ") + msg + "\n")
    except OSError:
        pass
    if lock.acquire(timeout=0.2):
        try:
            state["log"].append("[PANEL] " + msg)
        finally:
            lock.release()

print = plog

def log_exc(where, e):
    key = (where, type(e).__name__, str(e)[:80])
    if time.time() - _err_seen.get(key, 0) > 300:          # el mismo error, como mucho cada 5 min
        _err_seen[key] = time.time()
        plog(f"ERROR en {where}: {e}\n" + "".join(traceback.format_exc().splitlines(True)[-4:]))

sys_excepthook = None
def _hook(t, e, tb):
    plog("ERROR GRAVE: " + "".join(traceback.format_exception(t, e, tb)))
import sys as _sys
_sys.excepthook = _hook
threading.excepthook = lambda a: plog(f"ERROR en hilo {a.thread.name if a.thread else '?'}: " +
                                       "".join(traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback)))


# ---------- EMITIR: las pantallas por la red (http://IP:8080) ----------
# Solo gasta CPU mientras alguien esta mirando: si no hay nadie conectado no se copia ni se comprime nada.
STREAM_PORT = 8080
stream = {"clients": 0, "big": None, "small": None, "seq": 0, "jpg": {}, "srv": None, "err": ""}
stream_lock = threading.Lock()
VOICE_JS = r"""
<script>
const ST = (()=>{ try { return JSON.parse(localStorage.getItem('vozpanel') || '{}'); } catch(e) { return {}; } })();
function guardar(){ try { localStorage.setItem('vozpanel', JSON.stringify(ST)); } catch(e) {} }
let ctx = null;
function audio(){ if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)(); return ctx; }
function tono(f0, f1, dur, t0){
  const c = audio(), o = c.createOscillator(), g = c.createGain(), vol = 0.25 * (ST.vol ?? 1);
  o.frequency.setValueAtTime(f0, t0); o.frequency.linearRampToValueAtTime(f1 || f0, t0 + dur);
  g.gain.setValueAtTime(0, t0); g.gain.linearRampToValueAtTime(vol, t0 + .01);
  g.gain.setValueAtTime(vol, t0 + dur - .02); g.gain.linearRampToValueAtTime(0, t0 + dur);
  o.connect(g).connect(c.destination); o.start(t0); o.stop(t0 + dur);
}
function pitido(tipo){
  if (ST.pitidos === false) return 0;
  const c = audio(); c.resume(); let t = c.currentTime;
  if (tipo === 'alarm') { for (let k = 0; k < 2; k++) { tono(880, 880, .15, t); tono(660, 660, .15, t + .2); t += .4; } return .8; }
  if (tipo === 'jump')  { tono(200, 1200, 1.2, t); return 1.2; }
  tono(660, 990, .18, t); return .2;
}
function vocesEs(){ return speechSynthesis.getVoices().filter(v => v.lang.toLowerCase().startsWith('es')); }
const dicho = {};
function decir(a){
  const txt = ((a.titulo || '') + '. ' + (a.dato || '')).replace(/[¡!¿?>|·_]/g, ' ').replace(/\s+/g, ' ').trim();
  if (!txt || Date.now() - (dicho[txt] || 0) < 30000) return;
  dicho[txt] = Date.now();
  const espera = pitido(a.tipo);
  if (ST.voz === false) return;
  setTimeout(() => {
    const u = new SpeechSynthesisUtterance(txt);
    const v = vocesEs().find(x => x.name === ST.nombre) || vocesEs()[0];
    if (v) { u.voice = v; u.lang = v.lang; } else u.lang = 'es-ES';
    u.rate = ST.vel ?? 1.0; u.pitch = ST.tono ?? 0.9; u.volume = ST.vol ?? 1;
    speechSynthesis.speak(u);
    const e = document.getElementById('ultimo'); if (e) e.textContent = txt;
  }, espera * 1000 + 150);
}
let desde = -1;
async function sondeo(){
  const est = document.getElementById('estado');
  try {
    const j = await (await fetch('/avisos?desde=' + desde, {cache: 'no-store'})).json();
    if (desde < 0 || j.seq < desde) desde = j.seq;          // al abrir (o si la Pi reinicia) no lee lo antiguo
    else { j.items.forEach(decir); desde = j.seq; }
    if (est) { est.textContent = 'CONECTADO A LA PI'; est.style.color = '#3ad13a'; }
  } catch(e) { if (est) { est.textContent = 'SIN CONEXIÓN CON LA PI'; est.style.color = '#e03030'; } }
  setTimeout(sondeo, 1000);
}
function activar(){
  audio().resume();
  const ov = document.getElementById('activar'); if (ov) ov.style.display = 'none';
  const u = new SpeechSynthesisUtterance(' '); speechSynthesis.speak(u);
}
window.addEventListener('load', () => {
  sondeo();
  setTimeout(() => { if (audio().state === 'running') activar(); }, 300);   // OBS: ya puede sonar sin tocar
});
</script>
<div id="activar" onclick="activar()" style="position:fixed;inset:0;background:rgba(0,0,0,.85);color:#ff8c00;
 display:flex;align-items:center;justify-content:center;font:bold 28px Segoe UI,Arial;cursor:pointer;z-index:9">
 TOCA AQUÍ PARA ACTIVAR LA VOZ</div>
"""

CLICK_JS = """<script>
(function(){const im=document.querySelector('img');if(!im)return;im.style.cursor='pointer';
im.addEventListener('click',ev=>{const r=im.getBoundingClientRect(),nw=im.naturalWidth,nh=im.naturalHeight;if(!nw)return;
const sc=Math.min(r.width/nw,r.height/nh),dx=(r.width-nw*sc)/2,dy=(r.height-nh*sc)/2;
const x=Math.round((ev.clientX-r.left-dx)/sc),y=Math.round((ev.clientY-r.top-dy)/sc);
if(x<0||y<0||x>=nw||y>=nh)return;
fetch('/tap?x='+x+'&y='+y+'&w='+nw+'&h='+nh+'&s='+(im.src.indexOf('/panel')>=0?'p':'h'),{cache:'no-store'});});})();
document.addEventListener('keydown',ev=>{const k={Escape:'esc',Backspace:'esc',m:'m',M:'m',a:'a',A:'a',Tab:'tab'}[ev.key];
if(!k)return;ev.preventDefault();fetch('/key?k='+k,{cache:'no-store'});});
</script>"""

STREAM_HTML = ("<!doctype html><html><head><meta charset='utf-8'><title>Panel Elite</title></head>"
               "<body style='margin:0;background:#000;overflow:hidden'>"
               "<img src='/hdmi' style='width:100vw;height:100vh;object-fit:contain'>" + CLICK_JS + VOICE_JS +
               "</body></html>").encode()

VOZ_HTML = ("""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Voz del panel Elite</title>
<style>body{margin:0;background:#000;color:#ff8c00;font-family:Segoe UI,Arial,sans-serif;padding:20px}
h1{margin:0}.d{color:#a05800}select,input{background:#111;color:#ff8c00;border:1px solid #a05800;font-size:16px;padding:5px;margin:4px}
button{background:#000;color:#ff8c00;border:2px solid #ff8c00;border-radius:6px;font-size:16px;padding:8px 14px;margin:4px;cursor:pointer}
label{display:block;margin:8px 0}#ultimo{color:#fff}</style></head><body>
<h1>VOZ DEL PANEL</h1><p class="d">Deja esta pestaña abierta (puede estar minimizada). La voz la pone este PC; la Pi solo manda el texto.</p>
<p id="estado" class="d">conectando...</p>
<label>Voz: <select id="nombre"></select></label>
<label>Velocidad <input id="vel" type="range" min="0.6" max="1.6" step="0.1"></label>
<label>Tono <input id="tono" type="range" min="0.5" max="1.5" step="0.1"></label>
<label>Volumen <input id="vol" type="range" min="0.1" max="1" step="0.1"></label>
<label><input id="vozon" type="checkbox"> Hablar</label>
<label><input id="pitidos" type="checkbox"> Pitidos</label>
<button onclick="decir({tipo:'ok',titulo:'Prueba de voz',dato:'Panel Elite '+Date.now()%1000})">PROBAR</button>
<p class="d">Último aviso: <span id="ultimo">-</span></p>
""" + VOICE_JS + """
<script>
function rellenar(){
  const sel = document.getElementById('nombre'); sel.innerHTML = '';
  vocesEs().forEach(v => { const o = document.createElement('option'); o.value = o.textContent = v.name; sel.appendChild(o); });
  if (ST.nombre) sel.value = ST.nombre;
}
speechSynthesis.onvoiceschanged = rellenar; rellenar();
const C = {vel: 1.0, tono: 0.9, vol: 1};
for (const k of ['vel', 'tono', 'vol']) { const e = document.getElementById(k); e.value = ST[k] ?? C[k]; e.oninput = () => { ST[k] = +e.value; guardar(); }; }
document.getElementById('nombre').onchange = e => { ST.nombre = e.target.value; guardar(); };
const vz = document.getElementById('vozon'), pt = document.getElementById('pitidos');
vz.checked = ST.voz !== false; pt.checked = ST.pitidos !== false;
vz.onchange = () => { ST.voz = vz.checked; guardar(); }; pt.onchange = () => { ST.pitidos = pt.checked; guardar(); };
</script></body></html>""").encode()

# avisos para el PC (solo texto)
feed = {"seq": 0, "items": []}

def feed_add(tipo, titulo, dato):
    with stream_lock:
        feed["seq"] += 1
        feed["items"].append({"n": feed["seq"], "tipo": tipo, "titulo": titulo or "", "dato": dato or ""})
        del feed["items"][:-20]

def stream_jpeg(which):
    import io
    with stream_lock:
        seq = stream["seq"]
        old = stream["jpg"].get(which)
        if old and old[0] == seq:
            return old[1]
        surf = stream["big"] if which == "big" and stream["big"] is not None else stream["small"]
        if surf is None:
            return None
        buf = io.BytesIO()
        pygame.image.save(surf, buf, "x.jpg")
        data = buf.getvalue()
        stream["jpg"][which] = (seq, data)
        return data

def stream_start():
    if stream["srv"]:
        return
    from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/ver"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(STREAM_HTML.replace(b"/hdmi", b"/panel") if "pequena" in self.path else STREAM_HTML)
                return
            if path == "/key":
                k = self.path.split("k=", 1)[-1][:4]
                if k == "esc":
                    on_tap(*BACK.center)
                elif k == "m":
                    ui["view"] = 0
                elif k == "a":
                    ui["view"] = 12
                elif k == "tab":
                    hdmi_toggle()
                self.send_response(204)
                self.end_headers()
                return
            if path == "/tap":
                try:
                    q = dict(kv.split("=", 1) for kv in self.path.split("?", 1)[1].split("&"))
                    remote_tap(int(q["x"]), int(q["y"]), int(q["w"]), int(q["h"]), q.get("s", "h"))
                except Exception:
                    pass
                self.send_response(204)
                self.end_headers()
                return
            if path == "/manual":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(manual_html())
                return
            if path == "/voz":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(VOZ_HTML)
                return
            if path == "/avisos":
                try:
                    desde = int(self.path.split("desde=")[1].split("&")[0])
                except (IndexError, ValueError):
                    desde = -1
                with stream_lock:
                    data = json.dumps({"seq": feed["seq"], "items": [a for a in feed["items"] if a["n"] > desde]})
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(data.encode())
                return
            if path not in ("/hdmi", "/panel"):
                self.send_error(404); return
            which = "big" if path == "/hdmi" else "small"
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            stream["clients"] += 1
            last = -1
            try:
                while cfg.get("stream"):
                    if stream["seq"] == last:
                        time.sleep(0.05); continue
                    last = stream["seq"]
                    jpg = stream_jpeg(which)
                    if jpg:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(jpg))
                        self.wfile.write(jpg + b"\r\n")
            except Exception:
                pass
            finally:
                stream["clients"] -= 1

    try:
        srv = ThreadingHTTPServer(("0.0.0.0", STREAM_PORT), H)
        srv.daemon_threads = True
        stream["srv"] = srv
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print(f"EMITIR: http://{my_ip()}:{STREAM_PORT}")
    except OSError as e:
        stream["err"] = str(e)[:40]
        print("EMITIR:", e)

def stream_snap(small):
    if not cfg.get("stream") or stream["clients"] <= 0:
        return
    with stream_lock:
        hi = panel_hi() if cfg.get("sharp") else None
        stream["small"] = (hi if hi is not None else small).copy()
        stream["big"] = BIG["surf"].copy() if BIG.get("fb") and BIG.get("surf") is not None else None
        stream["seq"] += 1

if cfg.get("stream"):
    pass   # se arranca en main() cuando ya estan los ajustes cargados

# ---------- VOZ de la nave (espeak-ng) ----------
voice = {"alert": None, "xa": None, "proc": None, "last": {}}

def voice_ok():
    return bool(shutil.which("espeak-ng"))

def voice_say(text):
    if not cfg.get("voice") or not voice_ok():
        return
    t = re.sub(r"[¡!¿?>|·_]", " ", text or "")
    t = re.sub(r"\s+", " ", t).strip(" .")
    if not t or time.time() - voice["last"].get(t, 0) < 30:      # no repetir lo mismo en 30 s
        return
    p_ = voice["proc"]
    if p_ and p_.poll() is None:                                  # ya esta hablando
        return
    voice["last"][t] = time.time()
    try:
        voice["proc"] = subprocess.Popen(["espeak-ng", "-v", "es", "-s", "150", "-a", "130", t],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass

def voice_watch():
    a, x = ui.get("alert"), xa.get("a")
    if a is not voice["alert"]:
        voice["alert"] = a
        if a and snd_on(a.get("ev")):
            voice_say(f'{a.get("text", "")}. {a.get("sub", "")}')
            if cfg.get("stream"):
                k = a.get("kind")
                feed_add("jump" if k == "jump" else "ok" if k in ("ok", "galnet") else "alarm", a.get("text"), a.get("sub"))
    if x is not voice["xa"]:
        voice["xa"] = x
        if x and snd_on(x.get("ev")):
            voice_say(f'{x.get("title", "")}. {x.get("big", "")}')
            if cfg.get("stream"):
                feed_add("alarm" if x.get("col") == RED else "ok", x.get("title"), x.get("big"))


# ---------- MANUAL (12 AJUSTES > MANUAL y http://IP:8080/manual) ----------
# Marcas: "# " titulo   "- " punto   "@r" rojo "@n" naranja "@v" verde "@a" azul "@m" marron "@g" gris
CREADOR = "CMDR ORTEM ED DER  ·  ortemedder@gmail.com"
MANUAL = [
("INICIO", "PRIMEROS PASOS", """
# Qué es
Panel táctil para Elite Dangerous: botones que pulsan teclas del juego y pantallas con los datos de tu nave en tiempo real.
# Cómo funciona
- En el PC de juego corre elite_sender.py: lee los ficheros del juego (Status.json y el journal) y los envía por la red a esta Pi.
- La Pi los muestra y, en la Pi 4, pulsa las teclas en el PC como si fuera un teclado USB.
- En el PC, control_sender.pyw tiene los botones INICIAR y PARAR del sender.
# Para empezar
- Enciende la Pi: arranca sola en la pantalla del reloj.
- En el PC pulsa INICIAR en el control del sender y abre Elite.
- Al entrar en el juego el panel pasa solo a EN VIVO.
- En elite_sender.py, PI_IP tiene que ser la IP de esta Pi: {ip}
# Tocar la pantalla
- Toque corto en los botones. En listas y textos, tocar pasa de página.
- < MENÚ (arriba a la izquierda) vuelve atrás.
# Ratón y teclado
- Con un ratón o un teclado con touchpad conectado a la Pi: clic izquierdo = tocar.
- Clic derecho o TAB: la pantalla HDMI cambia entre PANEL (los menús, para manejarlos con el ratón) y TABLERO (los cuadros de datos).
- ESC = atrás  ·  M = menú  ·  A = ajustes.
- En la página web del PC (EMITIR) también funcionan ESC, M, A y TAB.
# Teclas del juego
- Con el sender v0.77 el PC manda tus controles (el fichero .binds que usa el juego) y cada botón usa tu tecla.
- AJUSTES > OPCIONES > TECLAS: el fichero leído y los botones sin tecla de teclado, con una tecla libre que puedes asignar en el juego.
- Un botón sin tecla pone SIN TECLA y al tocarlo avisa.
# Menú principal y música del juego (con el sender v0.80)
- Al salir al menú principal: las dos pantallas pasan al reloj con EN EL MENÚ PRINCIPAL y sale el resumen de la sesión. Al volver a la partida el mapa empieza de cero.
- Música de combate: el panel pasa a COMBATE (a pie, a EN VIVO) antes del primer disparo. Se apaga en CAMBIO AUTO.
- Música thargoide: aviso ENCUENTRO THARGOIDE. Se apaga en ALERTAS y en SONIDO Y VOZ.
- Abrir el menú de Powerplay del juego lleva a NAVEGACIÓN > POWERPLAY; el de escuadrón, a la ficha ESCUADRÓN (nombre, tu rango, ala y amigos).
# Inara (solo lectura, con el sender v0.81)
- Pon tu clave de Inara (la misma de EDMC) en inara_clave.txt junto a elite_sender.py. La Pi no la ve.
- Opcional: inara_cmdrs.txt con otros comandantes, uno por línea (hasta 30: todo tu escuadrón). En ESCUADRÓN, tocando pasas las páginas: 6 por página, primero los conectados (en verde).
- La ficha ESCUADRÓN muestra el nombre real de tu rango y, de los otros CMDR, su nave, rango de combate y escuadrón. Se lee al arrancar y luego cada hora. Lo que sube a Inara lo sigue haciendo EDMC.
# Combate a pie
- EN VIVO a pie muestra siempre botiquines (+), células (rayo) y explosivos con barritas según el máximo de tu traje (Dominator 3/3/2, Maverick 2/1/1, Artemis 1/1/1). Rojo con 1 o ninguno.
- En combate (te atacan o hay bajas en el último minuto) la pantalla pasa a EN COMBATE en grande: salud, escudo, bajas, botiquines y células, créditos sin cobrar y explosivos.
- Al lanzar una granada: «quedan X de Y».
# Cierre de emergencia del juego
- (cuenta atrás de 3 segundos) Tres toques seguidos sobre la barra de arriba, entre MENÚ y el engranaje (el nombre del sistema); abajo sale «toque 1 de 3», «2 de 3»: pantalla roja con cuenta atrás rápida 3-2-1 y el sender del PC cierra Elite Dangerous (taskkill). Tocar en cualquier sitio cancela.
- Necesita el sender v0.84. La primera vez Windows puede preguntar por el cortafuegos: permite redes privadas.
- Se desactiva en AJUSTES > OPCIONES > CERRAR JUEGO.
# Salud crítica
- A pie, si la salud baja del 30 %: las dos pantallas en rojo parpadeando deprisa 3 segundos con ¡SALUD XX %! ¡BOTIQUÍN YA!, y luego un borde rojo parpadeando hasta que te cures. Se apaga en ALERTAS > SALUD BAJA (A PIE).
# Enlace energético
- Si llevas el enlace energético en la mano y estás parado 8 segundos (girar con el ratón no cuenta), el panel lo da por recarga: aviso pequeño RECARGANDO y punto de recarga (rayo amarillo) en el MAPA, si no hay otro a menos de 20 m.
- El juego no dice la batería del traje ni la munición: es una aproximación.
- Sin pantalla pequeña la HDMI arranca sola en modo PANEL.
# Según tu equipo
- @v Pi 4 con pantalla táctil y cable USB al PC: funciona todo.
- @n Pi 3: todo menos los botones que pulsan teclas (no puede hacer de teclado USB).
- @n Sin pantalla pequeña ni táctil: solo la pantalla grande de datos, sin menús.
"""),
("PANTALLAS", "LAS PANTALLAS", """
# Pantalla del reloj
Sale cuando el juego no envía datos: tu foto, hora, fecha real y del juego, CMDR, versión, IP y noticias GALNET subiendo. Tócala para abrir el menú.
# EN VIVO
Pantalla de inicio durante el juego. Cambia sola según estés en la nave, a pie o en el SRV. MENÚ (arriba a la izquierda) abre los 12 menús.
# Barra de arriba
- Nombre del sistema (o un aviso en rojo).
- Combustible con su barra.
- En la pantalla grande, a la izquierda de la hora, la fecha del juego.
- AJUSTES > PANTALLA > CONSUMO: CPU del panel, temperatura de la Pi y FPS de la pantalla grande (verde, naranja, rojo).
- Pestañas: algunos menús tienen varias páginas (por ejemplo ESTACIÓN | MERCADO | PORTANAVES). Toca una para cambiar.
- @n El engranaje que gira (a la derecha) lleva a AJUSTES desde cualquier pantalla.
- @r Un rayo rojo parpadeando: a la Pi le falta corriente.
# Cambio automático
Con CAMBIO AUTO (OPCIONES) el panel salta solo a la pantalla útil: al atracar, al lanzar el SRV, si te interdictan o te atacan...
- Toca CAMBIO AUTO para elegir uno a uno qué cambios quieres (verde = activo). TODOS ON / TODOS OFF arriba.
"""),
("MENÚS", "LOS 12 MENÚS", """
- 1 MANDOS: tren, luces, visión nocturna, recogedor, supercrucero, silencio, disipador, chaff, salto, escudo y mapas. Se iluminan si están activos.
- 2 PIPS: reparto de energía y combinaciones rápidas.
- 3 NAVEGACIÓN: destino, ruta, sistema (política) y powerplay; toca para cambiar de cara. Pestaña NOTAS: tus sitios guardados.
- 4 CARGA/MISIÓN: bodega y misiones. Pestaña MATERIALES.
- 5 SRV / RHINO / A PIE: botones del vehículo y a pie. Pestaña MAPA: tu recorrido sobre el planeta.
- 6 COMBATE: botones de combate.
- 7 EXPLORACIÓN: exploración (EDSM), sistema en movimiento, xenobiología, yacimientos, diario y alienígenas.
- 8 ESTACIÓN: atraque y ficha de la estación. Pestañas MERCADO y PORTANAVES.
- 9 CAZA: órdenes al caza.
- 10 MINERÍA: prospectores y refinado.
- 11 SESIÓN·GALNET: resumen de la sesión (toca para ver AMIGOS). Pestañas GALNET, OBJ.COM y RANGOS.
- 12 AJUSTES: opciones, estilo, bordes, iconos, versiones, LOG, STREAM, PANTALLA, MANUAL y salir / reiniciar / apagar.
@g Los botones de teclas usan las teclas de tu configuración del juego.
"""),
("PANT. GRANDE", "PANTALLA GRANDE (HDMI)", """
Muestra datos (no se toca) y elige sola el tablero según la situación:
- VIAJE: en vivo, navegación, exploración y sistema (en la grande, el SISTEMA sale a todo lo ancho, sin botones y con la ficha del cuerpo más interesante).
- APROXIMACIÓN (cerca de un planeta o anillo): sistema, xenobiología y yacimientos.
- SUPERFICIE (aterrizado, SRV o a pie): xenobiología, SRV y MAPA del recorrido. En el Rhino: yacimientos y minería.
- ATRACADO: en vivo, estación, mercado y GALNET. GALNET alterna con CARGA/MISIÓN si llevas carga o misiones, y con OBJETIVOS COMUNITARIOS si hay.
- ATRAQUE: la estación a pantalla completa al conceder el atraque. Luz roja a la izquierda y verde a la derecha, como en la entrada de la estación.
- COMBATE: combate, registro de combate y pips.
- COMBATE A PIE: EN VIVO y SRV / RHINO / A PIE a la izquierda y el MAPA a la derecha.
# Modos (AJUSTES > PANTALLA)
- 4 CUADROS: los cuatro a la vez.
- MIXTO: el cuadro principal grande a la izquierda y los demás pequeños.
- GRANDE: un cuadro a pantalla completa con letra al doble; van rotando cada 10 s.
# Nitidez (AJUSTES > PANTALLA)
- NORMAL: los cuadros se dibujan a 480x320 y se amplían (más ligero).
- ALTA: se dibujan a la resolución real de la HDMI (1024x600): letras y líneas nítidas en todos los modos. Gasta algo más de CPU. Si algún cuadro diera problemas, ese cuadro vuelve solo a NORMAL.
Los avisos salen en las dos pantallas.
"""),
("AVISOS", "AVISOS Y SONIDOS", """
Los avisos importantes ocupan la pantalla unos segundos. Toca para quitarlos.
- @r Rojo: peligro (interdicción, te atacan, escudos caídos, casco, sobrecalentamiento, baja tensión).
- @a Azul: información (salto al hiperespacio, códice, noticias).
- @v Verde: buenas noticias (escudos arriba, sistema sin explorar, amigo conectado, objetivo comunitario).
- @n Naranja: atención (recogida de combustible, misión a punto de caducar).
- BAJA (a pie), DERRIBO (nave) y DERRIBO (SRV): número, créditos y lo que llevas sin cobrar. Azul = bono de combate, verde = recompensa. Lo sin cobrar se guarda en el PC hasta que lo cobras (y se pierde si mueres, como en el juego). Total en 11 SESIÓN.
- @r EN COMBATE (a pie): si en el último minuto te han atacado, ha caído tu escudo o has hecho una baja.
- @n SALUD BAJA a pie: avisa al 75 %, y con alarma al 50 % y al 25 %.
- +1 BOTIQUÍN / CÉLULA / GRANADA al cogerlos (llevas N) y USADO al gastarlos; en rojo y con alarma si no te queda ninguno.
- COBRADO: lo que paga el juego y lo que llevaba sumado el panel (la diferencia suele ser de bonos anteriores o extras).
- @r HAS CAÍDO: al morir a pie (en la zona conservas los bonos).
- LLEGADA A (estación) al salir de supercrucero; en las SEÑALES su nivel de AMENAZA (verde 0-2, naranja 3-4, rojo 5 o más) y las zonas de conflicto.
- @n OPERACIÓN INICIADA / TERMINADA (modo Operations): nave, escuadrón y al terminar el resumen con créditos, derribos, Merc Coin y méritos. Las bajas a pie dentro de la nave de carga no las registra el juego.
- GRANADA / PROYECTOR LANZADO: lo que te queda.
- @r ¡DESPLEGADO!: al bajar del transporte en una zona de combate a pie; EN VIVO muestra bajas, ritmo y bonos.
Debajo del nombre del sistema salen los estados del juego: SOBRECALENTADO, INTERDICCION, PELIGRO, COMBUSTIBLE BAJO y MASS LOCK.
# Activar y desactivar (AJUSTES > OPCIONES)
- ALERTAS: los avisos a pantalla completa. Al tocarlo sale la lista de todos los avisos, por páginas: toca cada uno para activarlo o apagarlo (relleno = activo). Un aviso apagado tampoco suena ni lo dice la voz. TODOS ON / TODOS OFF arriba; PÁG pasa de página.
- SONIDO: los pitidos (alarma, salto y "ok"). Al tocarlo sale la lista SONIDO Y VOZ: elige uno a uno qué avisos pitan y hablan (relleno = suena). Uno apagado aquí se sigue viendo, pero en silencio. De entrada BAJA / DERRIBO va en silencio.
- VOZ: que la Pi lea los avisos (ver VOZ).
"""),
("COLORES", "COLORES Y ESTILO", """
- COLOR (OPCIONES): naranja, azul, verde, morado, rojo o blanco. Cambia el color principal del panel.
- ESTILO (AJUSTES): CLÁSICO (limpio) o CABINA: esquinas cortadas, líneas de escaneo, fondo de hexágonos en el espacio y de puntos en tierra, tinte rojo si hay peligro y azul atracado.
- ICONOS (AJUSTES): el menú principal con dibujos en vez de números.
# Qué significa cada color del texto
- @v Verde: bien, activo, completado.
- @r Rojo: peligro o error.
- @a Azul: información.
- @g Gris: sin datos o apagado.
"""),
("BORDES", "BORDES DE SITUACIÓN", """
Con BORDES activado (AJUSTES > BORDES), el marco de las dos pantallas avisa de tu situación. Puede haber hasta 3 a la vez, uno dentro de otro:
- @r Rojo: te buscan o eres hostil, o el casco está por debajo del 30 %.
- @n Naranja (color del tema): sistema anárquico, sin ley.
- @m Marrón: en tierra (a pie en un planeta o en el SRV).
- @a Azul: atracado.
"""),
("VOZ", "VOZ DE LA NAVE", """
Hay dos voces y se pueden usar a la vez. Ninguna repite el mismo aviso en 30 s.
# Voz de la Pi
- AJUSTES > OPCIONES > VOZ. Suena por el altavoz de la Pi (HDMI o jack).
- Usa espeak-ng: {voz}.
- Voz robótica. Solo gasta CPU mientras habla.
# Voz del PC
- Activa EMITIR y abre en el PC: http://{ip}:8080/voz
- Toca una vez para activarla y deja la pestaña abierta (puede estar minimizada).
- Usa las voces de Windows: elige voz, velocidad, tono y volumen y pulsa PROBAR.
- La Pi solo envía el texto: casi no gasta.
"""),
("EMITIR", "EMITIR: PC, OBS Y VR", """
Ver las pantallas del panel en el PC. AJUSTES > OPCIONES > EMITIR (ahora: {emitir}).
- Pantalla grande con voz: http://{ip}:8080
- Pantalla pequeña: http://{ip}:8080/?pequena
- Solo la voz: http://{ip}:8080/voz
- Este manual: http://{ip}:8080/manual
- VLC (solo imagen): http://{ip}:8080/hdmi
# OBS
Fuente Navegador con la dirección. Marca "Controlar audio mediante OBS" para la voz.
# Manejar el panel desde el PC
Con el ratón del PC: clic sobre la imagen = tocar el panel. Funciona con la pantalla pequeña (?pequena) y con la HDMI en modo PANEL.
# Gafas de VR
Abre la página en el PC de juego y colócala en la cabina con Desktop+ (SteamVR).
@g Solo gasta CPU mientras alguien mira la imagen.
"""),
("EXPLORACIÓN", "EXPLORACIÓN Y MÁS", """
- Xenobiología (7.3): especies, valor, distancia entre muestras y brújula para volver a la nave. NAVE AQUÍ corrige dónde está la nave.
- Exploración (7.1): cuerpos del sistema con datos de EDSM; toca para pasar páginas.
- Yacimientos (7.4): señales del planeta y anillos.
- Rhino: franja de altura para desplegarlo; en verde (entre 40 y 7 m) está listo.
- Alienígenas (7.6): thargoides y guardianes. Aviso de SISTEMAS APAGADOS.
- MAPA (5 > MAPA): tu recorrido a pie, en SRV o Rhino (rastro naranja), tu posición y rumbo (flecha verde), la nave, el asentamiento (azul), las bajas (cruces rojas) y las muestras (verde). Donde coges un botiquín sale una cruz verde, una célula de energía un rayo amarillo y las granadas un rombo gris. MARCAR RECARGA pone un rayo con aro donde estás (el juego no avisa al recargar el traje ni al coger munición). Norte arriba; la cuadrícula se ajusta sola. Toca para ver todo el recorrido o 100 m a tu alrededor.
- Notas de viaje (3 > NOTAS): GUARDAR AQUÍ guarda el sitio; toca uno para ver distancia y rumbo.
- GALNET (11 > GALNET): noticias oficiales en español cada 30 min. Las nuevas en verde.
- Objetivos comunitarios (11 > OBJ.COM): los tuyos en verde, con tu aportación.
"""),
("PROBLEMAS", "SI ALGO NO VA", """
- SIN DATOS: el sender no envía. En el PC, control del sender > INICIAR. Revisa PI_IP ({ip}) y que el PC y la Pi estén en la misma red.
- Los botones no pulsan teclas: en la Pi 4 el cable USB-C tiene que ir al PC. La Pi 3 no puede hacer de teclado.
- @r Rayo rojo / BAJA TENSIÓN: usa una fuente de 5,1 V y 3 A y alimenta la pantalla HDMI aparte. Ahora: {pot}.
- No suena: mira OPCIONES > SONIDO. Para el sonido por HDMI, en /etc/asound.conf pon la tarjeta de la HDMI (aplay -l).
- La pantalla grande no se ve: la Pi tiene que arrancar sin escritorio (sudo systemctl set-default multi-user.target).
- "Error en esta pantalla": queda apuntado en AJUSTES > LOG y en panel.log.
- Reiniciar el panel: sudo systemctl restart elite-panel
- Salir al shell: AJUSTES > SALIR (dos toques).
"""),
("ACERCA DE", "ACERCA DE", """
# PANEL ELITE
Panel táctil y tablero de datos para Elite Dangerous.
- Versión: {ver}
- Comandante: CMDR {cmdr}
- IP de esta Pi: {ip}
- Alimentación: {pot}
- Voz de la Pi: {voz}
# Creador
@v {creador}
# Desarrollado con
@a Claude (Anthropic)
# Gracias a
EDSM (datos de sistemas) y Frontier Developments (GALNET y objetivos comunitarios).
@g Proyecto no oficial, sin relación con Frontier Developments. Elite Dangerous es una marca de Frontier Developments.
@g La lista de cambios está en AJUSTES > VERSIONES.
"""),
]

def man_vars():
    pot = ("sin datos" if not power.get("ok") else "BAJA AHORA" if power.get("now")
           else "hubo bajadas desde que arrancó" if power.get("past") else "correcta")
    return {"ip": my_ip() or "IP-de-la-Pi", "ver": PANEL_VER, "cmdr": cfg.get("cmdr", ""), "pot": pot,
            "voz": "instalada" if voice_ok() else "NO instalada (sudo apt install espeak-ng)",
            "emitir": "activado" if cfg.get("stream") else "desactivado", "creador": CREADOR}

def man_text(k):
    t = MANUAL[k][2]
    for key, val in man_vars().items():
        t = t.replace("{" + key + "}", str(val))
    return t.strip("\n")

def man_parse(line):
    kind, col = "p", None
    if line.startswith("# "):
        return "h", None, line[2:]
    if line.startswith("- "):
        kind, line = "li", line[2:]
    if line.startswith("@") and len(line) > 1:
        col, line = line[1], line[2:].lstrip()
    return kind, col, line

def man_col(c):
    return {"r": RED, "n": ORANGE, "v": GREEN, "a": BLUE, "m": BROWN, "g": DIM}.get(c, WHITE)

man = {"topic": 0, "page": 0, "cache": None}

def man_pages(k):
    key = (k, man_text(k))
    if man["cache"] and man["cache"][0] == key:
        return man["cache"][1]
    rows = []
    for raw in key[1].split("\n"):
        if not raw.strip():
            rows.append((None, "", None, 0, 6)); continue
        kind, c, txt = man_parse(raw)
        if kind == "h":
            rows.append(("h", txt, ORANGE, 0, 24)); continue
        ind = 12 if kind == "li" else 0
        for j, t in enumerate(wrap_lines(F["small"], txt, W - 20 - ind)):
            rows.append(("li" if kind == "li" and j == 0 else "p", t, man_col(c), ind, 17))
    pages, cur, h = [], [], 0
    avail = H - TOP - 30
    for r in rows:
        if cur and (h + r[4] > avail or (r[0] == "h" and h + 60 > avail)):
            pages.append(cur); cur, h = [], 0
        if not cur and r[0] is None:
            continue
        cur.append(r); h += r[4]
    if cur:
        pages.append(cur)
    man["cache"] = (key, pages)
    return pages

def view_manual(surf, d, flags, now):
    for i, (short, title, _) in enumerate(MANUAL):
        draw_button(surf, grid(i, 4, 3), str(i + 1), short, F["num"], lit=flash.get((140, i), 0) > now)

def view_manual_page(surf, d, flags, now):
    k = man["topic"]
    pages = man_pages(k)
    pg = max(0, min(man["page"], len(pages) - 1))
    y = TOP + 4
    for kind, txt, col, ind, h in pages[pg]:
        if kind == "h":
            put(surf, F["btn"], txt, (8, y + 2), ORANGE, W - 16)
        elif kind:
            if kind == "li":
                pygame.draw.circle(surf, col if col != WHITE else ORANGE, (12, y + 7), 2)
            put(surf, F["small"], txt, (10 + ind, y), col, W - 20 - ind)
        y += h
    pygame.draw.line(surf, DIM, (8, H - 22), (W - 8, H - 22))
    put(surf, F["small"], "< atrás", (8, H - 18), DIM)
    put(surf, F["small"], f"{MANUAL[k][1]}   ·   pág {pg + 1}/{len(pages)}", (W // 2, H - 18), ORANGE, W - 160, anchor="midtop")
    put(surf, F["small"], "sigue >" if pg < len(pages) - 1 else "índice >", (W - 8, H - 18), DIM, anchor="topright")

def tap_manual(x, y):
    if ui["view"] == 140:
        for i in range(len(MANUAL)):
            if grid(i, 4, 3).collidepoint(x, y):
                tap_flash((140, i)); man.update(topic=i, page=0)
                MENU[141] = "MANUAL · " + MANUAL[i][1]; ui["view"] = 141; return
        return
    n = len(man_pages(man["topic"]))
    if x < W // 3:
        if man["page"] == 0:
            ui["view"] = 140
        else:
            man["page"] -= 1
    else:
        if man["page"] >= n - 1:
            ui["view"] = 140
        else:
            man["page"] += 1

def manual_html():
    import html as _h
    C = {"r": "#e03030", "n": "#ff8c00", "v": "#3ad13a", "a": "#50a0ff", "m": "#9a5a28", "g": "#888"}
    out = ["<!doctype html><html lang='es'><head><meta charset='utf-8'><title>Manual del Panel Elite</title>"
           "<style>body{background:#000;color:#ddd;font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:auto;padding:20px;line-height:1.5}"
           "h1,h2,h3{color:#ff8c00}h2{border-bottom:1px solid #a05800;padding-bottom:4px;margin-top:36px}a{color:#ff8c00}"
           "nav a{display:inline-block;margin:3px 10px 3px 0}code{color:#3ad13a}@media print{body{background:#fff;color:#000}}</style></head><body>",
           "<h1>MANUAL DEL PANEL ELITE</h1>",
           "<p>" + _h.escape(PANEL_VER) + " · CMDR " + _h.escape(cfg.get("cmdr", "")) + "</p><nav>"]
    out += [f"<a href='#t{i}'>{i + 1}. {_h.escape(t)}</a>" for i, (_, t, _) in enumerate(MANUAL)]
    out.append("</nav>")
    for i, (_, title, _) in enumerate(MANUAL):
        out.append(f"<h2 id='t{i}'>{i + 1}. {_h.escape(title)}</h2>")
        ul = False
        for raw in man_text(i).split("\n"):
            if not raw.strip():
                continue
            kind, c, txt = man_parse(raw)
            txt = _h.escape(txt)
            txt = re.sub(r"(https?://\S+)", r"<a href='\1'>\1</a>", txt)
            if c:
                txt = f"<span style='color:{C.get(c, '#ddd')}'>{txt}</span>"
            if kind == "li" and not ul:
                out.append("<ul>"); ul = True
            if kind != "li" and ul:
                out.append("</ul>"); ul = False
            out.append(f"<h3>{txt}</h3>" if kind == "h" else f"<li>{txt}</li>" if kind == "li" else f"<p>{txt}</p>")
        if ul:
            out.append("</ul>")
    out.append("</body></html>")
    return "\n".join(out).encode()

VIEWS.update({140: view_manual, 141: view_manual_page})
MENU.update({140: "MANUAL", 141: "MANUAL"})
PARENT.update({140: 12, 141: 140})


# ---------- MAPA de recorrido (a pie, SRV y Rhino sobre un planeta) ----------
track = {"body": None, "pts": [], "kills": [], "items": [], "last": None, "zoom": 0}
YELLOW = (255, 215, 0)
GREY = (150, 150, 150)
ITEM_KIND = {"healthpack": "med", "energycell": "cell"}
FOOT_MAX_V = 20.0                          # m/s: mas rapido que esto, a pie, es ir en el transporte
TRACK_MAX, TRACK_STEP = 2000, 3.0          # puntos guardados como mucho / metros entre puntos

def track_update(d, now):
    b = (d or {}).get("bio") or {}
    lat, lon, R = b.get("lat"), b.get("lon"), b.get("R")
    if lat is None or not R:
        return
    body = (d or {}).get("body") or b.get("body")
    if body != track["body"]:                          # otro planeta: mapa nuevo
        track.update(body=body, pts=[], kills=[], items=[], last=None)
    out = (d.get("Flags2", 0) & 1) or (d.get("Flags", 0) & (1 << 26))
    if not out or d.get("Flags2", 0) & 2:              # en taxi o en el transporte no se apunta
        return
    elink_check(d, now, lat, lon, R)
    raw = track.get("raw")
    if d.get("Flags2", 0) & 1 and not d.get("Flags", 0) & (1 << 26):
        # posicion nueva: la velocidad se mide sobre 1 s como minimo (el juego da la posicion a saltos)
        if raw is None or now - raw[2] >= 1.0:
            if raw is not None and now - raw[2] < 10:
                track["fast"] = hav(raw[:2], (lat, lon), R) / (now - raw[2]) > FOOT_MAX_V
            track["raw"] = (lat, lon, now)
        if track.get("fast"):
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
        track["pts"].append((lat, lon))
        track["last"] = (lat, lon)
        del track["pts"][:-TRACK_MAX]

ELINK_SECS, ELINK_STILL, ELINK_NEAR = 8.0, 1.0, 20.0    # segundos parado, margen (m), sin otro punto a (m)
ELINK = {"t0": None, "pos": None, "done": False}

def elink_check(d, now, lat, lon, R):
    """Enlace energetico en la mano y parado: recargando (el juego no dice la bateria del traje)."""
    w = str(((d or {}).get("live") or {}).get("weapon") or "").lower()
    holding = d.get("Flags2", 0) & 1 and any(k in w for k in ("rechargetool", "energylink", "enlace"))
    if not holding:
        ELINK.update(t0=None, pos=None, done=False)
        return
    if ELINK["pos"] is None or hav(ELINK["pos"], (lat, lon), R) > ELINK_STILL:
        ELINK.update(t0=now, pos=(lat, lon), done=False)
        return
    if ELINK["done"] or now - ELINK["t0"] < ELINK_SECS:
        return
    ELINK["done"] = True
    near = any(k_ == "recharge" and hav((la, lo), (lat, lon), R) < ELINK_NEAR for k_, la, lo in track["items"])
    if not near:
        track["items"].append(("recharge", lat, lon))
        del track["items"][:-300]
    if ev_on("elink"):
        ui["toast"] = ("RECARGANDO  ·  enlace energético" if near else "PUNTO DE RECARGA GRABADO", now + 4)
        if not near and snd_on("elink"):
            voice_say("Punto de recarga grabado")
            if cfg.get("stream"):
                feed_add("ok", "PUNTO DE RECARGA GRABADO", "")

def draw_toast(surf, now):
    t = ui.get("toast")
    if not t or now > t[1]:
        return
    f = F["small"]
    w_ = f.size(t[0])[0] + 20
    r = pygame.Rect((W - w_) // 2, H - 26, w_, 22)
    pygame.draw.rect(surf, BLACK, r, border_radius=6)
    pygame.draw.rect(surf, YELLOW, r, 1, border_radius=6)
    put(surf, f, t[0], r.center, YELLOW, anchor="center")

def track_item(kind):
    with lock:
        d = state["data"]
    b = (d or {}).get("bio") or {}
    if b.get("lat") is not None:
        track["items"].append((kind, b["lat"], b["lon"]))
        del track["items"][:-300]
        return True
    return False

def track_kill():
    with lock:
        d = state["data"]
    b = (d or {}).get("bio") or {}
    if b.get("lat") is not None:
        track["kills"].append((b["lat"], b["lon"]))
        del track["kills"][:-200]

MAP_STEPS = (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000)

def fmt_m(m):
    return f"{m / 1000:g} km".replace(".", ",") if m >= 1000 else f"{m:g} m"

def draw_map(surf, r, d, now):
    d = d or {}
    b = d.get("bio") or {}
    lat, lon, R = b.get("lat"), b.get("lon"), b.get("R")
    fs = F["small"]
    if lat is None or not R:
        put(surf, F["btn"], "Sin posición en un planeta", (r.centerx, r.centery - 10), DIM, r.w - 16, anchor="center")
        put(surf, fs, "El mapa funciona a pie, en SRV o en Rhino sobre un planeta", (r.centerx, r.centery + 12),
            DIM, r.w - 16, anchor="midtop")
        return
    k = math.cos(math.radians(lat))
    def xy(p):
        return (R * math.radians(p[1] - lon) * k, R * math.radians(p[0] - lat))
    trail_all = [xy(p) if p is not None else None for p in track["pts"]]
    trail = [p for p in trail_all if p is not None]
    marks = []
    ship = ship_pos(b)
    if ship:
        marks.append(("ship", xy(ship)))
    sp = (d.get("footcz") or {}).get("spos")
    if sp and (not sp[2] or sp[2] == d.get("body")):
        marks.append(("base", xy(sp)))
    marks += [("kill", xy(p)) for p in track["kills"]]
    marks += [("bio", xy(p)) for p in (b.get("pts") or []) if p]
    marks += [(k_, xy((la, lo))) for k_, la, lo in track["items"]]
    me = (0.0, 0.0)
    zm = track["zoom"] % 3
    if zm == 1:
        minx, maxx, miny, maxy = -100, 100, -100, 100
    elif zm == 0:
        # ZONA: centrado en ti, con lo ultimo que has recorrido y las ultimas bajas (sin puntos lejanos sueltos)
        rec = trail[-150:] + [m[1] for m in marks if m[0] == "kill"][-30:]
        far = [max(abs(p[0]), abs(p[1])) for p in rec]
        far = sorted(f_ for f_ in far if f_ < 1500)
        ext = far[int(len(far) * 0.8)] if far else 40
        ext = max(ext, 40)
        minx, maxx, miny, maxy = -ext, ext, -ext, ext
    else:
        allp = trail + [m[1] for m in marks] + [me]
        minx, maxx = min(p[0] for p in allp), max(p[0] for p in allp)
        miny, maxy = min(p[1] for p in allp), max(p[1] for p in allp)
    w_, h_ = max(maxx - minx, 40), max(maxy - miny, 40)
    cx_, cy_ = (minx + maxx) / 2, (miny + maxy) / 2
    mg = 1.08 if zm == 0 else 1.25
    sc = min(r.w / (w_ * mg), r.h / (h_ * mg))
    def scr(p):
        return (int(r.centerx + (p[0] - cx_) * sc), int(r.centery - (p[1] - cy_) * sc))
    span = max(r.w, r.h) / sc
    step = next((s_ for s_ in MAP_STEPS if span / s_ <= 8), MAP_STEPS[-1])
    old = surf.get_clip()
    surf.set_clip(r)
    gc = tuple(max(18, c // 3) for c in DIM[:3])
    gx = math.floor((cx_ - r.w / 2 / sc) / step) * step
    while scr((gx, 0))[0] <= r.right:
        x = scr((gx, 0))[0]
        pygame.draw.line(surf, gc, (x, r.y), (x, r.bottom))
        gx += step
    gy = math.floor((cy_ - r.h / 2 / sc) / step) * step
    while scr((0, gy))[1] >= r.y:
        y = scr((0, gy))[1]
        pygame.draw.line(surf, gc, (r.x, y), (r.right, y))
        gy += step
    pts = [scr(p) if p is not None else None for p in trail_all] + [scr(me)]
    n = len(pts)
    for i in range(1, n):
        if pts[i - 1] is None or pts[i] is None:
            continue
        f_ = 0.25 + 0.75 * i / n                        # lo antiguo se va apagando
        pygame.draw.line(surf, tuple(int(c * f_) for c in ORANGE[:3]), pts[i - 1], pts[i], 2)
    for kind, p in marks:
        x, y = scr(p)
        if kind == "ship":
            pygame.draw.polygon(surf, ORANGE, [(x, y - 8), (x + 7, y), (x, y + 8), (x - 7, y)])
            put(surf, fs, "NAVE", (x + 10, y - 7), ORANGE)
        elif kind == "base":
            pygame.draw.rect(surf, BLUE, (x - 6, y - 6, 12, 12), 2)
            put(surf, fs, (sp[3] if sp and len(sp) > 3 else "ASENTAMIENTO")[:22], (x + 10, y - 7), BLUE)
        elif kind == "kill":
            pygame.draw.line(surf, RED, (x - 4, y - 4), (x + 4, y + 4), 2)
            pygame.draw.line(surf, RED, (x - 4, y + 4), (x + 4, y - 4), 2)
        elif kind == "med":
            pygame.draw.line(surf, GREEN, (x - 6, y), (x + 6, y), 4)
            pygame.draw.line(surf, GREEN, (x, y - 6), (x, y + 6), 4)
        elif kind == "cell":
            draw_bolt(surf, x - 4, y - 8, YELLOW, 0.75)
        elif kind == "recharge":
            pygame.draw.circle(surf, YELLOW, (x, y), 10, 2)
            draw_bolt(surf, x - 4, y - 8, YELLOW, 0.75)
        elif kind == "gren":
            pygame.draw.polygon(surf, GREY, [(x, y - 4), (x + 4, y), (x, y + 4), (x - 4, y)])
        else:
            pygame.draw.circle(surf, GREEN, (x, y), 4, 2)
    x, y = scr(me)
    a = math.radians(b.get("hdg") or 0)
    tip = (x + 11 * math.sin(a), y - 11 * math.cos(a))
    lft = (x + 7 * math.sin(a - 2.5), y - 7 * math.cos(a - 2.5))
    rgt = (x + 7 * math.sin(a + 2.5), y - 7 * math.cos(a + 2.5))
    pygame.draw.polygon(surf, GREEN, [tip, lft, (x, y), rgt])
    surf.set_clip(old)
    pygame.draw.rect(surf, DIM, r, 1)
    put(surf, fs, ("ZONA", "CERCA (100 m)", "TODO EL RECORRIDO")[track["zoom"] % 3] + "  ·  toca para cambiar",
        (r.x + 6, r.y + 4), DIM, r.w - 120)
    nx = r.right - 12
    pygame.draw.line(surf, WHITE, (nx, r.y + 22), (nx, r.y + 9), 2)
    pygame.draw.polygon(surf, WHITE, [(nx, r.y + 4), (nx - 4, r.y + 11), (nx + 4, r.y + 11)])
    put(surf, fs, "N", (nx - 7, r.y + 6), WHITE, anchor="topright")
    put(surf, fs, f"cuadro = {fmt_m(step)}", (r.x + 6, r.bottom - 18), DIM)
    map_legend(surf, r.x + 8, r.bottom - 29, fs)
    nk = len(track["kills"])
    info = []
    if ship:
        info.append(f"nave a {fmt_m(round(hav((lat, lon), ship, R)))}")
    if nk:
        info.append(f"{nk} bajas")
    if info:
        put(surf, fs, "  ·  ".join(info), (r.right - 6, r.bottom - 18), ORANGE, r.w // 2, anchor="topright")

def map_legend(surf, x, y, fs):
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

MARK_BTN = pygame.Rect(W - 172, H - 38, 166, 34)

def view_map(surf, d, flags, now):
    draw_map(surf, pygame.Rect(4, TOP + 2, W - 8, H - TOP - 46), d, now)
    draw_button(surf, MARK_BTN, "      MARCAR RECARGA", None, F["small"], lit=flash.get(("mark",), 0) > now)
    draw_bolt(surf, MARK_BTN.x + 8, MARK_BTN.y + 7, YELLOW, 0.95)
    nm = sum(1 for k_, *_ in track["items"] if k_ == "med")
    nc = sum(1 for k_, *_ in track["items"] if k_ in ("cell", "recharge"))
    put(surf, F["small"], f"+ botiquines {nm}   ·   rayos {nc}", (8, H - 28), DIM, W - 190)

def tap_map(x=0, y=0):
    if MARK_BTN.collidepoint(x, y):
        if track_item("recharge"):
            tap_flash(("mark",))
            set_alert("PUNTO DE RECARGA MARCADO", "", YELLOW, 1.5, "ok")
        else:
            set_alert("SIN POSICIÓN", "solo en un planeta", secs=2)
        return
    track["zoom"] = (track["zoom"] + 1) % 3

VIEWS[150] = view_map
MENU[150] = "MAPA"
PARENT[150] = 0
TABS.append([(5, "SRV / A PIE"), (150, "MAPA")])


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
    hi = panel_hi() if cfg.get("sharp") else None
    if hi is not None:
        S.fill(BLACK)
        S.blit(hi, ((BIG["w"] - hi.get_width()) // 2, (BIG["h"] - hi.get_height()) // 2))
        if cfg.get("perf"):
            perf_side(S)
        return True
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


# ---------- v0.71 ----------
TYPE_ES = {"Station": "estación", "Planet": "planeta", "Star": "estrella", "PlanetaryRing": "anillo"}

def threat_col(t):
    return GREEN if t <= 2 else ORANGE if t <= 4 else RED

# EN VIVO en la nave: operacion en curso y Merc Coin
def view_live_v071(surf, d, flags, now):
    view_live(surf, d, flags, now)
    d = d or {}
    if d.get("Flags2", 0) & 1 or flags & (1 << 26):
        return
    O = d.get("ops") or {}
    y = H - 20
    if O.get("merc") is not None:
        txt = f"MERC COIN {fnum(O['merc'], 0)}" + (f"  (+{O['lastgain']})" if O.get("lastgain") else "")
        put(surf, F["small"], txt, (8, y), MERC)
    c_ = (O.get("crew") or {})
    if c_.get("paid"):
        put(surf, F["small"], f"copiloto {c_.get('name', '')}: -{crx(c_['paid'])} cr", (W - 8, y), (70, 120, 230), 240, anchor="topright")
    if O.get("on"):
        mins = int((now - (O.get("t0") or now)) // 60)
        put(surf, F["small"], f"OPERACIÓN · {O.get('target') or O.get('mission') or ''} · {O.get('kills', 0)} derribos · "
                              f"{crx(O.get('cr', 0))} cr · {mins} min", (8, y - 18), RED, W - 16)

# SISTEMA en la pantalla grande: sin botones, mapa a todo lo ancho y ficha automatica
ORR_XS = [1.0]

def or_side_big(surf, d, orbits):
    d = d or {}
    want = [((d.get("dest") or {}).get("name")), d.get("body")]
    o = next((x for w_ in want if w_ for x in orbits if x.get("name") == w_), None)
    if o is None:
        cand = [x for x in orbits if x.get("name") and not x.get("mapped")]
        o = max(cand, key=lambda x: x.get("value") or 0, default=None)
    put(surf, F["small"], SPEEDS[orr["speed"]][1] + ("  ·  PAUSA" if orr["paused"] else ""), (W - 6, H - 16), DIM, anchor="topright")
    if not o:
        return
    system = (d.get("explo") or {}).get("system") or ""
    nm = o["name"]
    short = nm[len(system):].strip() if system and nm.startswith(system) else nm
    box = pygame.Rect(W - 168, TOP + 4, 162, 74)
    pygame.draw.rect(surf, BLACK, box)
    pygame.draw.rect(surf, DIM, box, 1, border_radius=4)
    put(surf, F["btn"], short or nm, (box.x + 6, box.y + 3), ORANGE, box.w - 12)
    put(surf, F["small"], o.get("cls", ""), (box.x + 6, box.y + 22), bcol(o), box.w - 12)
    put(surf, F["small"], f"{o.get('dist', 0):,} ls".replace(",", "."), (box.x + 6, box.y + 38), DIM)
    put(surf, F["small"], ("1º " if o.get("first") else "") + ("MAPEADO" if o.get("mapped") else ""), (box.right - 6, box.y + 38), GREEN, anchor="topright")
    put(surf, F["small"], f"~ {cr(o.get('value'))} cr", (box.x + 6, box.y + 54), ORANGE)

def view_orrery_big(surf, d, flags, now):
    global OR_AREA, draw_or_side
    keep = (OR_AREA, draw_or_side, orr.get("hits"), orr.get("scale"))
    OR_AREA = pygame.Rect(0, TOP, W, H - TOP)
    draw_or_side = or_side_big
    ORR_XS[0] = (W / 2 - 14) / max(1, (H - TOP) / 2 - 14)
    orr["scale"] = None
    try:
        view_orrery(surf, d, flags, now)
    finally:
        OR_AREA, draw_or_side, orr["hits"], orr["scale"] = keep
        ORR_XS[0] = 1.0

# clic del raton del PC sobre la pagina de EMITIR
def remote_tap(x, y, w, h, which):
    if (w, h) == (W, H) or which == "p":
        px, py = x * W / max(1, w), y * H / max(1, h)
    else:
        if not hdmi_panel():
            return
        sc = min(w / W, h / H)
        px, py = (x - (w - W * sc) / 2) / sc, (y - (h - H * sc) / 2) / sc
    if 0 <= px < W and 0 <= py < H:
        mouse.update(x=px, y=py, t=time.time())
        on_tap(int(px), int(py))

VIEWS[100] = view_live_v071


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

# 12 AJUSTES > PANTALLA: MODO, NITIDEZ y FPS
def view_pantalla(surf, d, flags, now):
    f = cfg.get("bigfps", "AUTO")
    items = [("MODO", BIGMODES.get(cfg.get("bigmode", "4"), "4 CUADROS"), False),
             ("NITIDEZ", "ALTA" if cfg.get("sharp") else "NORMAL", bool(cfg.get("sharp"))),
             ("FPS", "AUTO (3/10)" if f == "AUTO" else f"{f} por seg.", False),
             ("CONSUMO", "SÍ" if cfg.get("perf") else "NO", bool(cfg.get("perf")))]
    for i, (t, sub, fill) in enumerate(items):
        draw_button(surf, grid(i, 2, 2, TOP, H - 40), t, sub, F["big"], filled=fill, lit=flash.get((160, i), 0) > now)
    perf_update()
    x = 8
    for j, (t, col) in enumerate(perf_parts()):
        x += put(surf, F["btn"], t, (x, H - 32), col) + 14
    put(surf, F["small"], "pantalla grande", (W - 8, H - 26), DIM, anchor="topright")

def tap_pantalla(x, y):
    for i in range(4):
        if not grid(i, 2, 2, TOP, H - 40).collidepoint(x, y):
            continue
        tap_flash((160, i))
        if i == 0:
            order = list(BIGMODES)
            cfg["bigmode"] = order[(order.index(cfg.get("bigmode", "4")) + 1) % len(order)]
        elif i == 1:
            cfg["sharp"] = not cfg.get("sharp", True)
        elif i == 2:
            cfg["bigfps"] = BIGFPS[(BIGFPS.index(cfg.get("bigfps", "AUTO")) + 1) % len(BIGFPS)]
        else:
            cfg["perf"] = not cfg.get("perf", False)
        save_cfg()
        return

VIEWS[160] = view_pantalla
MENU[160] = "PANTALLA"
PARENT[160] = 12


# ---------- AJUSTES > OPCIONES > ALERTAS (161) y CAMBIO AUTO (162): uno a uno ----------
EVPP = 12

EVL = {161: (EV_LIST, "ev", "evpage", "alerts", {}), 162: (AUTO_LIST, "autoev", "autopage", "auto", {}),
       163: (EV_LIST, "snd", "sndpage", "sound", SND_DEF)}

def _evl(v):
    return EVL[v][:3]

def view_evlist(surf, d, flags, now):
    v = ui["view"]
    L, st, pk = _evl(v)
    pages = (len(L) + EVPP - 1) // EVPP
    pg = ui.get(pk, 0) % pages
    on = cfg.get(st) or {}
    df = EVL[v][4]
    n = sum(1 for k, _ in L if on.get(k, df.get(k, True)))
    top = [("TODOS ON", None), ("TODOS OFF", None), (f"PÁG {pg + 1}/{pages}" if pages > 1 else f"{n} de {len(L)}", None)]
    for i, (t, _) in enumerate(top):
        draw_button(surf, grid(i, 3, 1, TOP, TOP + 40), t, None, F["btn"], lit=flash.get((v, 100 + i), 0) > now)
    for i, (k, name) in enumerate(L[pg * EVPP:(pg + 1) * EVPP]):
        r = grid(i, 2, 6, TOP + 38, H)
        draw_button(surf, r, name, None, F["small"] if len(name) > 17 else F["btn"], filled=on.get(k, df.get(k, True)),
                    lit=flash.get((v, i), 0) > now)

def tap_evlist(x, y):
    v = ui["view"]
    L, st, pk = _evl(v)
    pages = (len(L) + EVPP - 1) // EVPP
    pg = ui.get(pk, 0) % pages
    on = cfg.setdefault(st, {})
    for i in range(3):
        if grid(i, 3, 1, TOP, TOP + 40).collidepoint(x, y):
            tap_flash((v, 100 + i))
            if i < 2:
                for k, _ in L:
                    on[k] = i == 0
                cfg[EVL[v][3]] = True
                save_cfg()
            else:
                ui[pk] = pg + 1
            return
    for i, (k, _) in enumerate(L[pg * EVPP:(pg + 1) * EVPP]):
        if grid(i, 2, 6, TOP + 38, H).collidepoint(x, y):
            tap_flash((v, i))
            on[k] = not on.get(k, EVL[v][4].get(k, True))
            cfg[EVL[v][3]] = True
            save_cfg()
            return

VIEWS[161] = view_evlist
VIEWS[162] = view_evlist
VIEWS[163] = view_evlist
MENU[163] = "SONIDO Y VOZ"
PARENT[163] = 1244
MENU[161] = "ALERTAS"
MENU[162] = "CAMBIO AUTO"
PARENT[161] = 1244
PARENT[162] = 1244


# ---------- v0.74: PANEL nitido y FPS de la pantalla grande ----------
HI_PASS = [False]
PHI = {"surf": None, "n": -1, "fail": 0.0}
BIGFPS = ["AUTO", "3", "5", "10"]

def panel_hi():
    """El panel (pantalla pequena) dibujado a tamano grande: para la HDMI en modo PANEL y la web /panel."""
    if PHI["n"] == BIG["n"] and PHI["surf"] is not None:
        return PHI["surf"]
    if time.time() - PHI["fail"] < 60:
        return None
    bw, bh = BIG["w"] or 1024, BIG["h"] or 600
    sc = min(bw / W, bh / H)
    size = (int(W * sc), int(H * sc))
    real = PHI["surf"] if PHI["surf"] is not None and PHI["surf"].get_size() == size else pygame.Surface(size)
    keep = dict(F)
    HI_IDS.clear(); HI_KEEP.clear()
    F.update(hi_fonts(sc))
    HI_PASS[0] = True
    try:
        ss = ScaledSurf(real, sc, sc)
        if ui.get("bye"):
            draw_bye(ss)
        else:
            render(ss); decorate(ss); draw_borders(real); rhino_banner(ss)
        draw_pointer(ss)
    except Exception as e:
        log_exc("panel nitido", e)
        PHI["fail"] = time.time()
        return None
    finally:
        HI_PASS[0] = False
        F.clear(); F.update(keep)
        HI_IDS.clear(); HI_KEEP.clear()
    PHI.update(surf=real, n=BIG["n"])
    return real

def big_due():
    f = cfg.get("bigfps", "AUTO")
    if f == "AUTO":
        f = "10" if BIG.get("fast") else "3"
    step = {"3": 3, "5": 2, "10": 1}.get(f, 3)
    return BIG["n"] % step == 0


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


# ---------- v0.80: ficha ESCUADRON (al abrir el menu de escuadron del juego) ----------
INARA_RK = {"combat": "Combat", "trade": "Trade", "exploration": "Explore", "soldier": "Soldier",
            "mercenary": "Soldier", "exobiologist": "Exobiologist", "federation": "Federation", "empire": "Empire"}

def inara_rank(o, which="combat"):
    for n, v, _ in (o or {}).get("ranks") or []:
        if str(n).lower() == which and INARA_RK.get(which) in RANK_NAMES and isinstance(v, int):
            return rank_name(INARA_RK[which], v)
    return ""

SQ_PER = 6

def squad_pages(d):
    oth = (((d or {}).get("inara") or {}).get("others")) or []
    return 1 + (len(oth) + SQ_PER - 1) // SQ_PER

def view_squad_page(surf, d, pg):
    """Pagina pg (1..): miembros con nave, rango de combate, escuadron y si estan conectados."""
    ina = d.get("inara") or {}
    on = set((d.get("friends") or {}).get("on") or [])
    oth = sorted(ina.get("others") or [], key=lambda o: (o.get("name") not in on, (o.get("name") or "").lower()))
    y = TOP + 6
    put(surf, F["small"], "COMANDANTE", (8, y), DIM)
    put(surf, F["small"], "NAVE  ·  COMBATE  ·  ESCUADRÓN", (170, y), DIM); y += 18
    for o in oth[(pg - 1) * SQ_PER:pg * SQ_PER]:
        live = o.get("name") in on
        pygame.draw.circle(surf, GREEN if live else DIM, (14, y + 10), 5, 0 if live else 1)
        put(surf, F["btn"], o.get("name", "?"), (26, y + 2), GREEN if live else ORANGE, 140)
        bits = [o.get("ship"), inara_rank(o), o.get("squad")]
        put(surf, F["small"], "  ·  ".join(b for b in bits if b) or "sin datos públicos", (170, y + 6), DIM, W - 178)
        y += 36
    put(surf, F["small"], f"pág {pg + 1}/{squad_pages(d)}  ·  verde = conectado  ·  toca", (W - 8, H - 16), DIM,
        W - 16, anchor="topright")

def tap_squad(x, y):
    with lock:
        d = state["data"]
    ui["sqpage"] = (ui.get("sqpage", 0) + 1) % squad_pages(d)

def view_squad(surf, d, flags, now):
    d = d or {}
    pg = ui.get("sqpage", 0) % squad_pages(d)
    if pg:
        return view_squad_page(surf, d, pg)
    sq = d.get("squad") or {}
    fr = d.get("friends") or {}
    ina = d.get("inara") or {}
    me = ina.get("me") or {}
    y = TOP + 6
    name = sq.get("name") or me.get("squad")
    if name:
        put(surf, F["big"], name.upper(), (8, y), ORANGE, W - 16); y += 30
        rk = me.get("sqrank") or (f"rango {sq['rank']}" if sq.get("rank") is not None else "")
        if rk:
            n_ = f"  ·  {me['sqn']} miembros" if me.get("sqn") else ""
            put(surf, F["btn"], f"tu rango: {rk}{n_}", (8, y), BLUE, W - 16); y += 24
    else:
        put(surf, F["btn"], "Sin escuadrón (o aún no hay datos)", (8, y), DIM, W - 16); y += 26
    pygame.draw.line(surf, DIM, (8, y), (W - 8, y)); y += 6
    wing = fr.get("wing") or []
    if wing:
        put(surf, F["small"], "ALA", (8, y), DIM)
        put(surf, F["btn"], ", ".join(str(w) for w in wing)[:50], (60, y - 3), GREEN, W - 68); y += 22
    on = fr.get("on") or []
    put(surf, F["small"], f"AMIGOS CONECTADOS ({len(on)})", (8, y), DIM); y += 16
    put(surf, F["btn"], ", ".join(on[:5]) if on else "ninguno ahora mismo", (8, y), GREEN if on else DIM, W - 16); y += 26
    oth = ina.get("others") or []
    if oth:
        n_on = sum(1 for o in oth if o.get("name") in on)
        put(surf, F["small"], "INARA", (8, y), DIM); y += 16
        put(surf, F["btn"], f"{len(oth)} comandantes  ·  {n_on} conectados  ·  toca para verlos", (8, y), ORANGE, W - 16)
    if ina.get("ok"):
        mins = int((time.time() - (ina.get("t") or time.time())) // 60)
        st = f"Inara: hace {mins} min" if mins else "Inara: al día"
    else:
        st = "Inara: sin datos" + (f" ({ina['err']})" if ina.get("err") else "")
    put(surf, F["small"], st, (W - 8, H - 16), DIM, W - 16, anchor="topright")

VIEWS[165] = view_squad
MENU[165] = "ESCUADRÓN"
PARENT[165] = 0


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


# ---------- v0.84: boton ESCUADRON y cierre de emergencia del juego ----------
SQ_BTN = pygame.Rect(W - 160, H - 36, 152, 32)
KILL_PORT, KILL_MSG = 5006, b"ELITEPANEL-KILL"
KILL = {"taps": [], "t0": None, "sent": 0.0, "seq": None}
KILL_SECS = 3.0
KILL_CANCEL = pygame.Rect(W // 2 - 110, H - 90, 220, 60)

def kill_title_rect():
    # KILL zona v085: toda la barra de arriba entre MENU y el engranaje; con pestanas, solo la franja del nombre
    v = ui.get("view")
    h = 30 if tab_group(v)[0] else TOP - 4
    return pygame.Rect(BACK.right, 0, GEAR.x - 8 - BACK.right, h)

def kill_tap(x, y):
    """3 toques en el nombre del sistema: cuenta atras y el sender cierra el juego. Cualquier toque cancela."""
    now = time.time()
    if KILL["t0"]:
        KILL["t0"] = None
        set_alert("CIERRE CANCELADO", "", GREEN, 1.5, "ok")
        return True
    if not cfg.get("killbtn", True) or not kill_title_rect().collidepoint(x, y):
        return False
    KILL["taps"] = [t for t in KILL["taps"] if now - t < 2.5] + [now]
    if len(KILL["taps"]) >= 3:
        KILL["taps"] = []
        KILL["t0"] = now
        play("alarm")
    else:
        ui["toast"] = (f"CERRAR JUEGO: toque {len(KILL['taps'])} de 3", now + 2)
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


# ---------- v0.86: salud critica a pie ----------
HP_CRIT = 0.30
HPC = {"t0": None}
_HPF = {}

def draw_hpcrit(surf, now):
    """Salud < 30 % a pie: 3 s de pantalla roja parpadeando deprisa y luego borde rojo hasta que te cures."""
    if HPC["t0"] is None:
        return
    with lock:
        d = state["data"] or {}
    hp = (d.get("live") or {}).get("health")
    if not (d.get("Flags2", 0) & 1) or hp is None or hp >= HP_CRIT:
        HPC["t0"] = None
        return
    w, h = surf.get_size()
    on = int(now * 10) % 2 == 0                      # 5 parpadeos por segundo
    if now - HPC["t0"] < 3:
        surf.fill(RED if on else BLACK)
        k = h / 320
        key = round(k, 2)
        if key not in _HPF:
            _HPF[key] = (pygame.font.Font(None, int(96 * k)), pygame.font.Font(None, int(44 * k)))
        f1, f2 = _HPF[key] if type(surf).__name__ != "ScaledSurf" else (F["num"], F["big"])
        col = (255, 215, 0) if on else RED
        put(surf, f1, f"¡SALUD {hp * 100:.0f} %!", (w // 2, int(h * 0.38)), col, anchor="center")
        put(surf, f2, "¡BOTIQUÍN YA!", (w // 2, int(h * 0.66)), col, anchor="center")
    elif on:
        t = max(4, h // 50)
        pygame.draw.rect(surf, RED, (0, 0, w, h), t)


def render(surf):
    with lock:
        d, rx = state["data"], state["rx"]
    now = time.time()
    online = d is not None and now - rx < 5
    if online and not HI_PASS[0]:
        binds_check(d)
        process_notes(d)
        track_update(d, now)
    if now - ui["start"] < 3:
        draw_splash(surf, now); return
    menu_ = online and (d or {}).get("menu")
    ui["idle_on"] = (not online or menu_) and ui["view"] in (0, 100) and now > ui["idle_skip"] and now - ui["start"] > 8
    if ui["idle_on"]:
        if menu_ and not HI_PASS[0]:
            xa_notes(d, now)
        draw_idle(surf, now)
        if menu_:
            draw_xa(surf, now)
            put(surf, F["big"], "MENÚ PRINCIPAL", (W // 2, H - 44), GREEN, anchor="center")
        return
    if False:
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
    title = ("MENÚ PRINCIPAL" if (d or {}).get("menu") else ((d or {}).get("system") or "---").upper()) if online else "SIN DATOS"
    alert0 = next((t for b, t in ALERTS if flags & (1 << b)), None) if online else None
    if alert0 and tab_group(v)[0]:
        put(surf, F["big"], alert0, (x0, 6), RED, W - 182 - x0)
    else:
        put(surf, F["big"], title, (x0, 6), (GREEN if (d or {}).get("menu") else ORANGE) if online else DIM, W - 182 - x0)
    draw_gear(surf, v, now)
    fuel = ((d or {}).get("Fuel") or {}).get("FuelMain")
    cap = (d or {}).get("fuelcap")
    if online and fuel is not None:
        pct = max(0.0, min(1.0, fuel / cap)) if cap else None
        bx = pygame.Rect(W - 176, 6, 120, 14)
        pygame.draw.rect(surf, DIM, bx, 1)
        if pct is not None:
            pygame.draw.rect(surf, RED if pct < 0.25 else ORANGE, (bx.x + 2, bx.y + 2, int((bx.w - 4) * pct), bx.h - 4))
        put(surf, F["small"], f"FUEL {fuel:.1f}t", (W - 176, 21))
    mode = (d or {}).get("mode") if online else None
    if mode and not tab_group(v)[0]:
        put(surf, F["small"], f"MODO: {mode}", (W - 176, 37), RED, 120)
    alert = next((t for b, t in ALERTS if flags & (1 << b)), None) if online else None
    if tab_group(v)[0]:
        draw_tabs(surf, v)
    elif alert:
        put(surf, F["small"], alert, (x0, 34), RED)
    elif v:
        put(surf, F["small"], MENU.get(v, f"MENU {v}"), (x0, 34), DIM)
    pygame.draw.line(surf, DIM, (0, TOP - 2), (W, TOP - 2), 1)
    fn = VIEWS.get(v)
    if fn:
        try:
            fn(surf, d if online else None, flags, now)
        except Exception as e:
            log_exc(f"pantalla {v}", e)
            put(surf, F["btn"], "Error en esta pantalla", (W // 2, (H + TOP) // 2 - 10), RED, anchor="center")
            put(surf, F["small"], "está apuntado en 12 AJUSTES > LOG", (W // 2, (H + TOP) // 2 + 14), DIM, anchor="center")
    else:
        put(surf, F["btn"], f"Menú {v} vacío", (W // 2, (H + TOP) // 2), DIM, anchor="center")
    draw_scoop(surf, d if online else None, flags, now)
    if not HI_PASS[0]:
        xa_notes(d if online else None, now)
    draw_xa(surf, now)
    draw_toast(surf, now)
    draw_hpcrit(surf, now)
    draw_kill(surf, now)
    if (cfg.get("voice") or cfg.get("stream")) and not HI_PASS[0]:
        voice_watch()
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
    T0 = time.time()
    load_cfg()
    ev_migrate()
    make_sounds()
    load_fonts()
    surf = pygame.Surface((W, H))
    dev, bpp, stride = find_fb()
    SMALL["null"] = dev == "/dev/null"
    print("Framebuffer", dev, bpp, "bpp")
    print(f"Panel {PANEL_VER.split(' · ')[0]} listo en {time.time() - T0:.1f} s")
    if cfg.get("stream"):
        stream_start()
    threading.Thread(target=udp_loop, daemon=True).start()
    threading.Thread(target=touch_loop, daemon=True).start()
    threading.Thread(target=mouse_loop, daemon=True).start()
    threading.Thread(target=obs_loop, daemon=True).start()
    last = None
    with open(dev, 'r+b', buffering=0) as fb:
        while True:
            if ui.get("bye"):
                draw_bye(surf)
            else:
                render(surf)
                decorate(surf)
                draw_borders(surf)
                rhino_banner(surf)
            draw_pointer(surf)
            PANEL_SURF[0] = surf
            BIG["n"] += 1
            if big_go(surf):
                big_frame()
                stream_snap(surf)
            data = to_fb_bytes(surf, bpp, stride)
            if data != last:
                fb.seek(0); fb.write(data); last = data
            time.sleep(0.1)

if __name__ == "__main__":
    main()
