#!/usr/bin/env python3
# Sender v0.81: lee de Inara (solo lectura) tu perfil y el de otros CMDR.
#   inara_clave.txt   -> tu clave personal de Inara (la misma de EDMC), junto a elite_sender.py
#   inara_cmdrs.txt   -> (opcional) otros comandantes, uno por linea, p. ej. KORZO
import shutil, sys
P = sys.argv[1] if len(sys.argv) > 1 else "elite_sender.py"
s = open(P, encoding="utf-8").read()
if "def inara_pkt" in s:
    sys.exit("Ya estaba aplicado")
if "def handle_v080" not in s:
    sys.exit("Antes hay que poner el sender v0.80")
shutil.copy(P, P + ".bak80")

def rep(old, new):
    global s
    if old not in s:
        sys.exit("No encuentro: " + old[:70])
    s = s.replace(old, new, 1)

CODE = r'''
# ---------- v0.81: Inara (solo lectura; lo que sube a Inara lo hace EDMC) ----------
INARA_URL = "https://inara.cz/inapi/v1/"
INARA_APP = "PanelEliteRPi"
INARA_EVERY = 3600                     # como mucho una vez por hora (Inara pide no saturarla)
HERE = os.path.dirname(os.path.abspath(__file__))
inara = {"ok": False, "err": "", "t": 0, "me": None, "others": [], "next": 0}

def _inara_txt(name):
    try:
        with open(os.path.join(HERE, name), encoding="utf-8-sig") as f:
            return [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]
    except OSError:
        return []

def _inara_trim(p):
    sq = p.get("commanderSquadron") or {}
    ship = p.get("commanderMainShip") or {}
    return {"name": p.get("commanderName") or p.get("userName") or "",
            "ranks": [[r.get("rankName"), r.get("rankValue"), r.get("rankProgress")] for r in p.get("commanderRanksPilot") or []],
            "power": p.get("preferredPowerName") or "", "alleg": p.get("preferredAllegianceName") or "",
            "role": p.get("preferredGameRole") or "",
            "ship": ship.get("shipType") or "", "shipname": ship.get("shipName") or "",
            "squad": sq.get("squadronName") or sq.get("SquadronName") or "",
            "sqrank": sq.get("squadronMemberRank") or sq.get("SquadronMemberRank") or "",
            "sqn": sq.get("squadronMembersCount") or sq.get("SquadronMembersCount"),
            "url": p.get("inaraURL") or ""}

def inara_fetch():
    key = (_inara_txt("inara_clave.txt") or [""])[0]
    if not key:
        inara.update(ok=False, err="sin clave (inara_clave.txt)")
        return
    others = _inara_txt("inara_cmdrs.txt")[:30]
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    evs = [{"eventName": "getCommanderProfile", "eventTimestamp": ts, "eventData": {}}]
    evs += [{"eventName": "getCommanderProfile", "eventTimestamp": ts, "eventData": {"searchName": n}} for n in others]
    hdr = {"appName": INARA_APP, "appVersion": "0.81", "isBeingDeveloped": True, "APIkey": key}
    if ranks.get("cmdr"):
        hdr["commanderName"] = ranks["cmdr"]
    req = urllib.request.Request(INARA_URL, data=json.dumps({"header": hdr, "events": evs}).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "PanelEliteRPi/0.81"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            res = json.load(r)
    except Exception as e:
        inara.update(ok=False, err=str(e)[:60])
        return
    h = res.get("header") or {}
    if h.get("eventStatus") not in (200, 202):
        inara.update(ok=False, err=str(h.get("eventStatusText") or h.get("eventStatus"))[:60])
        return
    out = []
    for ev in res.get("events") or []:
        out.append(_inara_trim(ev.get("eventData") or {}) if ev.get("eventStatus") in (200, 202) else None)
    me = out[0] if out else None
    inara.update(ok=me is not None, err="" if me else "perfil no encontrado", t=time.time(), me=me,
                 others=[o for o in out[1:] if o])
    print("Inara:", "perfil leído" if me else inara["err"], f"(+{len(inara['others'])} CMDR)", flush=True)

def inara_loop():
    time.sleep(20)                        # primero que el journal diga quien eres
    while True:
        try:
            inara_fetch()
        except Exception as e:
            inara.update(ok=False, err=str(e)[:60])
        time.sleep(INARA_EVERY if inara["ok"] else 600)

def inara_pkt():
    return {k: inara[k] for k in ("ok", "err", "t", "me", "others")}

threading.Thread(target=inara_loop, daemon=True).start()

'''
rep('print("Leyendo journals...")', CODE + 'print("Leyendo journals...")')
rep('''"mycg", "friends", "binds")''', '''"mycg", "friends", "binds", "inara")''')
rep('''"binds": binds_pkt(), "squad": squad,''', '''"binds": binds_pkt(), "squad": squad, "inara": inara_pkt(),''')
open(P, "w", encoding="utf-8").write(s)
print("OK sender v0.81 (Inara, solo lectura)")
