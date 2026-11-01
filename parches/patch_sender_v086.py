#!/usr/bin/env python3
# Sender v0.86: al morir el juego pone la musica del menu en la pantalla de carga; ya no se toma por MENU PRINCIPAL.
import shutil, sys
P = sys.argv[1] if len(sys.argv) > 1 else "elite_sender.py"
s = open(P, encoding="utf-8").read()
if "MENU_EXIT_EVENTS" in s:
    sys.exit("Ya estaba aplicado")
if "def handle_v080" not in s:
    sys.exit("Antes hay que poner el sender v0.80")
shutil.copy(P, P + ".bak85")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

rep('''music = {"track": None, "sent": False, "tg": 0.0}''', '''music = {"track": None, "sent": False, "tg": 0.0, "died": 0.0}
MENU_EXIT_EVENTS = ("Resurrect", "Location", "Docked", "Undocked", "Embark", "Disembark", "Touchdown", "Liftoff",
                    "SupercruiseEntry", "SupercruiseExit", "FSDJump", "ApproachBody")''')
rep('''def handle_v080(e):
    ev = e.get("event")
    if ev == "Music":
        tr, old = e.get("MusicTrack") or "", music["track"]
        music["track"] = tr
        if tr == "MainMenu" and old != "MainMenu":''', '''def handle_v080(e):
    ev = e.get("event")
    ts = iso2epoch(e.get("timestamp")) or time.time()
    if ev == "Died":
        music["died"] = ts
    if ev in MENU_EXIT_EVENTS and info.get("menu"):
        info["menu"] = False                      # de vuelta en la partida (p. ej. tras morir y reaparecer)
    if ev == "Music":
        tr, old = e.get("MusicTrack") or "", music["track"]
        music["track"] = tr
        if tr not in ("MainMenu", "NoTrack", "") and info.get("menu"):
            info["menu"] = False
        if tr == "MainMenu" and ts - music["died"] < 120:
            pass                                  # pantalla de carga tras morir: no es el menu principal
        elif tr == "MainMenu" and old != "MainMenu":''')
open(P, "w", encoding="utf-8").write(s)
print("OK sender v0.86 (menu principal tras morir)")
