#!/usr/bin/env python3
# Sender v0.80: musica del juego (menu principal, combate, thargoides, Powerplay, escuadron) y datos del escuadron.
import shutil, sys
P = sys.argv[1] if len(sys.argv) > 1 else "elite_sender.py"
s = open(P, encoding="utf-8").read()
if "def handle_v080" in s:
    sys.exit("Ya estaba aplicado")
if "def binds_pkt" not in s:
    sys.exit("Antes hay que poner el sender v0.77")
shutil.copy(P, P + ".bak77")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

# resumen de sesion como funcion (al salir al menu y al cerrar el juego, una sola vez)
rep('''    elif ev == "Shutdown" and sess:
        ea = sess.get("earn") or {}''', '''    elif ev == "Shutdown" and sess and not music.get("sent"):
        music["sent"] = True
        ea = sess.get("earn") or {}''')

CODE = r'''
# ---------- v0.80: musica del juego y escuadron ----------
music = {"track": None, "sent": False, "tg": 0.0}
COMBAT_MUSIC = ("Combat_Dogfight", "Combat_LargeDogFight", "Combat_Unknown", "Combat_SRV")
TG_MUSIC = ("Unknown_Encounter", "Unknown_Exploration", "Unknown_Settlement")

def sess_summary():
    ea = sess.get("earn") or {}
    tot = sum(ea.values())
    note("sessend", "|".join(str(x) for x in (round(tot), round(time.time() - (sess.get("start") or time.time())),
         sess.get("jumps", 0), round(sess.get("ly", 0)), round(ea.get("explo", 0)), round(ea.get("bio", 0)),
         round(ea.get("trade", 0)), round(ea.get("bounty", 0)), sum((mining.get("refined") or {}).values()))))

def handle_v080(e):
    ev = e.get("event")
    if ev == "Music":
        tr, old = e.get("MusicTrack") or "", music["track"]
        music["track"] = tr
        if tr == "MainMenu" and old != "MainMenu":
            info["menu"] = True
            note("mainmenu", "")
            if sess and not music["sent"]:
                music["sent"] = True
                sess_summary()
        elif tr in COMBAT_MUSIC and old not in COMBAT_MUSIC:
            note("combatmusic", tr)
        elif tr in TG_MUSIC and time.time() - music["tg"] > 120:
            music["tg"] = time.time()
            note("thargmusic", tr)
        elif tr == "GalacticPowers" and old != tr:
            note("ppmenu", "")
        elif tr == "Squadrons" and old != tr:
            note("sqmenu", "")
    elif ev == "LoadGame":
        info["menu"] = False
        music["sent"] = False
        note("loadgame", "")
    elif ev == "SquadronStartup":
        squad["name"] = e.get("SquadronName") or ""
        squad["rank"] = e.get("CurrentRank")
    elif ev in ("SquadronPromotion", "SquadronDemotion"):
        squad["rank"] = e.get("NewRank")
    elif ev in ("LeftSquadron", "KickedFromSquadron", "DisbandedSquadron"):
        squad.update(name="", rank=None)

'''
rep("def handle_v071(e):", CODE + "def handle_v071(e):")
rep('''    handle_v071(e)
''', '''    handle_v071(e)
    handle_v080(e)
''')
rep('''"binds": binds_pkt(),''', '''"binds": binds_pkt(), "squad": squad,''')
open(P, "w", encoding="utf-8").write(s)
print("OK sender v0.80 (menu principal, musica, escuadron)")
