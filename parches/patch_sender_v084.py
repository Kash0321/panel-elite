#!/usr/bin/env python3
# Sender v0.84: cierre de emergencia. Escucha en UDP 5006 la orden del panel (solo desde la IP de la Pi)
# y cierra el juego con: taskkill /IM EliteDangerous64.exe /F
import shutil, sys
P = sys.argv[1] if len(sys.argv) > 1 else "elite_sender.py"
s = open(P, encoding="utf-8").read()
if "def kill_loop" in s:
    sys.exit("Ya estaba aplicado")
shutil.copy(P, P + ".bak81")

CODE = r'''
# ---------- v0.84: cierre de emergencia del juego (orden del panel) ----------
KILL_PORT, KILL_MSG = 5006, b"ELITEPANEL-KILL"
killres = {"seq": 0, "ok": False, "msg": ""}

def kill_game():
    import subprocess
    try:
        r = subprocess.run(["taskkill", "/IM", "EliteDangerous64.exe", "/F"], capture_output=True, text=True,
                           timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        ok = r.returncode == 0
        msg = "Elite Dangerous cerrado" if ok else (r.stderr or r.stdout or "no estaba abierto").strip()[:60]
    except Exception as e:
        ok, msg = False, str(e)[:60]
    killres.update(seq=killres["seq"] + 1, ok=ok, msg=msg)
    print(time.strftime("%H:%M:%S"), "CIERRE DE EMERGENCIA:", msg, flush=True)
    send({"killres": dict(killres)})

def kill_loop():
    try:
        so = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        so.bind(("0.0.0.0", KILL_PORT))
    except OSError as e:
        print("Cierre de emergencia no disponible:", e, flush=True)
        return
    while True:
        try:
            data, addr = so.recvfrom(256)
        except OSError:
            continue
        if addr[0] == PI_IP and data.strip() == KILL_MSG:
            kill_game()

threading.Thread(target=kill_loop, daemon=True).start()

'''
key = 'print("Leyendo journals...")'
if key not in s:
    sys.exit("No encuentro el arranque del sender")
s = s.replace(key, CODE + key, 1)
open(P, "w", encoding="utf-8").write(s)
print("OK sender v0.84 (cierre de emergencia)")
