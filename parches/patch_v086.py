#!/usr/bin/env python3
# Parche v0.86: cuenta atras de 3 s en el cierre de emergencia, copiloto en azul oscuro,
# salud a pie por debajo del 30 %: pantalla roja parpadeando (las dos pantallas). Va con el sender v0.86.
import re, shutil, sys, time
P = sys.argv[1] if len(sys.argv) > 1 else "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def draw_hpcrit" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.85' not in s:
    sys.exit("Este parche es para la v0.85")
shutil.copy(P, P + ".bak85")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

# 1. cierre de emergencia: 3 segundos (3 - 2 - 1)
rep('''KILL_SECS = 1.5''', '''KILL_SECS = 3.0''')

# 2. copiloto en azul oscuro
rep('''        put(surf, F["small"], f"copiloto {c_.get('name', '')}: -{crx(c_['paid'])} cr", (W - 8, y), DIM, 240, anchor="topright")''',
    '''        put(surf, F["small"], f"copiloto {c_.get('name', '')}: -{crx(c_['paid'])} cr", (W - 8, y), (70, 120, 230), 240, anchor="topright")''')

rep('''bar(surf, 16 + half, y, half, "SALUD", hp, RED if hp is not None and hp < 25 else GREEN)''',
    '''bar(surf, 16 + half, y, half, "SALUD", hp, RED if hp is not None and hp < 30 else GREEN)''')

# 3. salud critica (< 30 %): pantalla roja parpadeando 3 s y luego borde rojo mientras siga baja
rep('''        lvl = 3 if hp_ < 0.25 else 2 if hp_ < 0.5 else 1 if hp_ < 0.75 else 0
        prev = xa.get("hplvl", 0)
        if lvl > prev:
            xa["a"] = dict(''', '''        lvl = 3 if hp_ < HP_CRIT else 2 if hp_ < 0.5 else 1 if hp_ < 0.75 else 0
        prev = xa.get("hplvl", 0)
        if lvl == 3 and prev < 3:
            if ev_on("hplow"):
                HPC["t0"] = now
                play("alarm")
        elif lvl > prev:
            xa["a"] = dict(''')
rep('''    draw_kill(surf, now)''', '''    draw_hpcrit(surf, now)
    draw_kill(surf, now)''')
rep('''        render_big()
''', '''        render_big()
        draw_hpcrit(BIG["surf"], time.time())
''')

CODE = r'''
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

'''
rep("\ndef render(surf):", CODE + "\ndef render(surf):")

rep('''# Enlace energético''', '''# Salud crítica
- A pie, si la salud baja del 30 %: las dos pantallas en rojo parpadeando deprisa 3 segundos con ¡SALUD XX %! ¡BOTIQUÍN YA!, y luego un borde rojo parpadeando hasta que te cures. Se apaga en ALERTAS > SALUD BAJA (A PIE).
# Enlace energético''')
rep('''- Tres toques seguidos sobre la barra de arriba''', '''- (cuenta atrás de 3 segundos) Tres toques seguidos sobre la barra de arriba''')
rep('    ("0.85", "Cierre de emergencia: zona más grande en la barra de arriba y aviso de toques 1/3, 2/3"),\n',
    '    ("0.85", "Cierre de emergencia: zona más grande en la barra de arriba y aviso de toques 1/3, 2/3"),\n'
    '    ("0.86", "Salud < 30 %: pantalla roja; cierre en 3 s; copiloto en azul; arreglo del falso MENÚ PRINCIPAL al morir"),\n')
s = re.sub(r'PANEL_VER = "v0\.85[^"]*"', 'PANEL_VER = "v0.86 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)
open(P, "w", encoding="utf-8").write(s)
print("OK v0.86  (copia en " + P + ".bak85)")
