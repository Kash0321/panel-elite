#!/usr/bin/env python3
# Sender v0.77: lee las teclas del juego (.binds) y se las manda al panel.
import shutil, sys
P = sys.argv[1] if len(sys.argv) > 1 else "elite_sender.py"
s = open(P, encoding="utf-8").read()
if "def binds_pkt" in s:
    sys.exit("Ya estaba aplicado")
shutil.copy(P, P + ".bak76")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

CODE = r'''
# ---------- v0.77: teclas del juego (ficheros .binds) ----------
BINDS_FILE = ""      # vacio = el que use el juego; o la ruta completa de un .binds
BINDS_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Frontier Developments", "Elite Dangerous",
                         "Options", "Bindings")
EK = {"Period": ".", "Comma": ",", "Minus": "-", "Equals": "=", "LeftBracket": "[", "RightBracket": "]",
      "BackSlash": "\\", "SemiColon": ";", "Apostrophe": "'", "Grave": "`", "Slash": "/", "Space": "Space",
      "Tab": "Tab", "Enter": "Enter", "Backspace": "Backspace", "Escape": "Esc", "Insert": "Insert",
      "Home": "Home", "PageUp": "PageUp", "Delete": "Delete", "End": "End", "PageDown": "PageDown",
      "UpArrow": "Up", "DownArrow": "Down", "LeftArrow": "Left", "RightArrow": "Right",
      "Numpad_Add": "KPAdd", "Numpad_Subtract": "KPSub", "Numpad_Multiply": "KPMul", "Numpad_Divide": "KPDiv",
      "Numpad_Decimal": "KPDec", "Numpad_Enter": "KPEnter"}
EMOD = {"LeftShift": "Shift", "RightShift": "Shift", "LeftControl": "Ctrl", "RightControl": "Ctrl",
        "LeftAlt": "Alt", "RightAlt": "AltGr"}
binds = {"path": None, "mtime": 0, "t": 0, "pkt": None}

def ek(name):
    n = (name or "").replace("Key_", "", 1)
    if len(n) == 1 and (n.isalpha() or n.isdigit()):
        return n.lower()
    if n[:1] == "F" and n[1:].isdigit():
        return n
    if n.startswith("Numpad_") and n[7:].isdigit():
        return "KP" + n[7:]
    return EK.get(n)

def binds_path():
    if BINDS_FILE:
        return BINDS_FILE
    preset = None
    for st in ("StartPreset.4.start", "StartPreset.start"):
        try:
            with open(os.path.join(BINDS_DIR, st), encoding="utf-8-sig") as f:
                preset = f.read().split()[0]
            break
        except (OSError, IndexError):
            pass
    files = glob.glob(os.path.join(BINDS_DIR, "*.binds"))
    if preset:
        mine = [f for f in files if os.path.basename(f).split(".")[0] == preset]
        if mine:
            return max(mine, key=os.path.getmtime)
    return max(files, key=os.path.getmtime) if files else None

def binds_read(path):
    import xml.etree.ElementTree as ET
    root = ET.parse(path).getroot()
    keys, bad, used = {}, {}, set()
    for e in root:
        for side in ("Primary", "Secondary"):
            b = e.find(side)
            if b is None or b.get("Device") != "Keyboard" or not b.get("Key"):
                continue
            mods = [m for m in b.findall("Modifier")]
            if any(m.get("Device") != "Keyboard" for m in mods):
                continue
            mk = [EMOD.get((m.get("Key") or "").replace("Key_", "", 1)) for m in mods]
            k = ek(b.get("Key"))
            if k is None or None in mk:
                bad.setdefault(e.tag, b.get("Key"))
                continue
            combo = "+".join(sorted(set(mk)) + [k])
            used.add(combo)
            keys.setdefault(e.tag, combo)            # la principal manda; si no hay, la secundaria
    cand = [f"F{i}" for i in range(5, 13)] + [f"Ctrl+F{i}" for i in range(1, 13)] + \
           [f"Shift+F{i}" for i in range(1, 13)] + [f"Ctrl+{c}" for c in "bhjkoptuvxz"]
    free = [c for c in cand if c not in used][:12]
    return {"file": os.path.basename(path), "keys": keys, "bad": bad, "free": free}

def binds_pkt():
    now = time.time()
    if now - binds["t"] < 30:
        return binds["pkt"]
    binds["t"] = now
    try:
        p = binds_path()
        if not p:
            return binds["pkt"]
        m = os.path.getmtime(p)
        if p != binds["path"] or m != binds["mtime"]:
            binds["pkt"] = binds_read(p)
            binds.update(path=p, mtime=m)
            print("Teclas del juego:", os.path.basename(p), len(binds["pkt"]["keys"]), "acciones con tecla", flush=True)
    except Exception as e:
        print("No leo las teclas del juego:", e, flush=True)
    return binds["pkt"]

'''
rep('print("Leyendo journals...")', CODE + 'print("Leyendo journals...")')
rep('''"exdiary", "ranks", "routeinfo", "ppme", "dest", "mycg", "friends")''',
    '''"exdiary", "ranks", "routeinfo", "ppme", "dest", "mycg", "friends", "binds")''')
rep('''"friends": friends_pkt(), "mycg": mycg_pkt(),''', '''"friends": friends_pkt(), "mycg": mycg_pkt(), "binds": binds_pkt(),''')
open(P, "w", encoding="utf-8").write(s)
print("OK sender v0.77 (teclas del juego)")
