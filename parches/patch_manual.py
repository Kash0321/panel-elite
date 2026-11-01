#!/usr/bin/env python3
# Parche v0.65: MANUAL de uso dentro del panel (12 AJUSTES > MANUAL) y en el PC (http://IP:8080/manual)
import re, shutil, sys, time
P = "/home/ortem/panel.py"
s = open(P, encoding="utf-8").read()
if "def view_manual" in s:
    sys.exit("Ya estaba aplicado")
if 'PANEL_VER = "v0.64' not in s:
    sys.exit("Este parche es para la v0.64")
shutil.copy(P, P + ".bak64")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

CODE = r'''
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
- Pestañas: algunos menús tienen varias páginas (por ejemplo ESTACIÓN | MERCADO | PORTANAVES). Toca una para cambiar.
- @n El engranaje que gira (a la derecha) lleva a AJUSTES desde cualquier pantalla.
- @r Un rayo rojo parpadeando: a la Pi le falta corriente.
# Cambio automático
Con CAMBIO AUTO (OPCIONES) el panel salta solo a la pantalla útil: al atracar, al lanzar el SRV, si te interdictan o te atacan...
"""),
("MENÚS", "LOS 12 MENÚS", """
- 1 MANDOS: tren, luces, visión nocturna, recogedor, supercrucero, silencio, disipador, chaff, salto, escudo y mapas. Se iluminan si están activos.
- 2 PIPS: reparto de energía y combinaciones rápidas.
- 3 NAVEGACIÓN: destino, ruta, sistema (política) y powerplay; toca para cambiar de cara. Pestaña NOTAS: tus sitios guardados.
- 4 CARGA/MISIÓN: bodega y misiones. Pestaña MATERIALES.
- 5 SRV / RHINO / A PIE: botones del vehículo y a pie.
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
- VIAJE: en vivo, navegación, exploración y sistema.
- APROXIMACIÓN (cerca de un planeta o anillo): sistema, xenobiología y yacimientos.
- SUPERFICIE (aterrizado, SRV o a pie): xenobiología, SRV y materiales. En el Rhino: yacimientos y minería.
- ATRACADO: en vivo, estación, mercado y GALNET. GALNET alterna con CARGA/MISIÓN si llevas carga o misiones, y con OBJETIVOS COMUNITARIOS si hay.
- ATRAQUE: la estación a pantalla completa al conceder el atraque.
- COMBATE: combate, registro de combate y pips.
# Modos (AJUSTES > PANTALLA)
- 4 CUADROS: los cuatro a la vez.
- MIXTO: el cuadro principal grande a la izquierda y los demás pequeños.
- GRANDE: un cuadro a pantalla completa con letra al doble; van rotando cada 10 s.
Los avisos salen en las dos pantallas.
"""),
("AVISOS", "AVISOS Y SONIDOS", """
Los avisos importantes ocupan la pantalla unos segundos. Toca para quitarlos.
- @r Rojo: peligro (interdicción, te atacan, escudos caídos, casco, sobrecalentamiento, baja tensión).
- @a Azul: información (salto al hiperespacio, códice, noticias).
- @v Verde: buenas noticias (escudos arriba, sistema sin explorar, amigo conectado, objetivo comunitario).
- @n Naranja: atención (recogida de combustible, misión a punto de caducar).
Debajo del nombre del sistema salen los estados del juego: SOBRECALENTADO, INTERDICCION, PELIGRO, COMBUSTIBLE BAJO y MASS LOCK.
# Activar y desactivar (AJUSTES > OPCIONES)
- ALERTAS: los avisos a pantalla completa.
- SONIDO: los pitidos (alarma, salto y "ok").
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

'''
rep("\ndef render(surf):", CODE + "\ndef render(surf):")

# boton MANUAL en AJUSTES (abajo a la derecha); la alimentacion pasa a MANUAL > ACERCA DE y PROBLEMAS
rep('         ("SALIR", 0), ("REINICIAR", 1), ("APAGAR", 2), None]',
    '         ("SALIR", 0), ("REINICIAR", 1), ("APAGAR", 2), ("MANUAL", 140)]')
rep('''        if i >= 8:
            sure = c == ("pw", act) and time.time() < until''', '''        if i in (8, 9, 10):
            sure = c == ("pw", act) and time.time() < until''')
rep('''        if i >= 8:
            power_tap(act); return''', '''        if i in (8, 9, 10):
            power_tap(act); return''')
rep("    power_box(surf, grid(11, 4, 3))\n", "")

# toques del manual
rep("    elif v == 132:\n", "    elif v in (140, 141):\n        tap_manual(x, y); return\n    elif v == 132:\n")

# manual en la web
rep('''            if path == "/voz":''', '''            if path == "/manual":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(manual_html())
                return
            if path == "/voz":''')

rep('    ("0.64", "Voz y pitidos en el PC: página /voz y en EMITIR"),\n',
    '    ("0.64", "Voz y pitidos en el PC: página /voz y en EMITIR"),\n'
    '    ("0.65", "MANUAL de uso en AJUSTES y en http://IP:8080/manual"),\n')
s = re.sub(r'PANEL_VER = "v0\.64[^"]*"', 'PANEL_VER = "v0.65 · ' + time.strftime("%d/%m/%Y %H:%M") + '"', s)

open(P, "w", encoding="utf-8").write(s)
print("OK v0.65 MANUAL  (copia en panel.py.bak64)")
