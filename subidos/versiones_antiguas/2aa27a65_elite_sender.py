# Envia el estado de Elite Dangerous a la Raspberry Pi por UDP
# (Status.json, Journal, NavRoute.json y Cargo.json)
# Ejecutar en el PC de juego (Windows):  python elite_sender.py
import json, socket, time, glob, os, calendar, traceback, threading, urllib.request, urllib.parse

PI_IP = "192.168.0.94"   # IP de la Raspberry Pi (PI4ELITE)
PORT = 5005
DIR = os.path.expanduser(r"~\Saved Games\Frontier Developments\Elite Dangerous")
MISSION_DAYS = 30          # dias de journal que se leen al arrancar para recuperar misiones

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
info = {"system": "", "fuelcap": None, "cargocap": None, "mode": None,
        "nav": {"target": None, "star": None, "jumps": None, "last": None}}
route = []          # [(sistema, clase)]
missions = {}       # id -> [nombre, destino, expira_epoch]
cargo = []          # [(nombre, cantidad)]
cargo_mtime = 0
target = None       # ficha del objetivo fijado
fighter = {"state": None, "pilot": None}
jfile, jpos = None, 0

# ---- exploracion / estacion / mineria / sesion ----
explo = {"system": None, "total": None, "fss": None, "bodies": {}, "bary": {}}   # cuerpos del sistema actual
unsold = {}         # BodyName -> valor aprox. de datos sin vender
station = {}
mining = {"last": None, "refined": {}, "prospectors": 0, "collectors": 0, "limpets": None}
sess = {}

def new_session(e=None):
    sess.clear()
    sess.update(start=iso2epoch((e or {}).get("timestamp")) or time.time(), credits0=(e or {}).get("Credits"),
                jumps=0, ly=0.0, kills=0, deaths=0,
                earn={"bounty": 0, "trade": 0, "explo": 0, "missions": 0, "bio": 0})
    mining.update(last=None, refined={}, prospectors=0, collectors=0)

WHITE_DWARFS = {"D", "DA", "DAB", "DAO", "DAZ", "DAV", "DB", "DBZ", "DBV", "DO", "DOV", "DQ", "DC", "DCV", "DX"}

def body_value(e, mapped=False):
    """Valor aproximado de los datos de un cuerpo (formula de la comunidad, 3.3+)."""
    first = e.get("WasDiscovered") is False
    if "StarType" in e:
        st = e["StarType"]
        k = 14057 if st in WHITE_DWARFS else 22628 if st in ("N", "H", "SupermassiveBlackHole") else 1200
        return (k + e.get("StellarMass", 1) * k / 66.25) * (2.6 if first else 1)
    pc, tf = e.get("PlanetClass", ""), e.get("TerraformState") == "Terraformable"
    if pc == "Metal rich body": k = 21790 + (65631 if tf else 0)
    elif pc == "Ammonia world": k = 96932
    elif pc in ("Earthlike body", "Water world"): k = 64831 + (116295 if tf else 0)
    elif pc == "High metal content body": k = 9654 + (100677 if tf else 0)
    elif pc == "Sudarsky class I gas giant": k = 1656
    elif pc == "Sudarsky class II gas giant": k = 9654
    else: k = 300 + (93328 if tf else 0)
    v = max(500, k + k * 0.56591828 * e.get("MassEM", 1) ** 0.2)
    if mapped:
        v *= 3.699622554 if e.get("WasMapped") is False else 3.3333333
        v += max(v * 0.3, 555)          # bonificacion de Odyssey
    return v * (2.6 if first else 1)

def body_label(e):
    st = e.get("StarType")
    if st:
        return ("ESTRELLA NEUTRONES" if st == "N" else "AGUJERO NEGRO" if st in ("H", "SupermassiveBlackHole")
                else "ENANA BLANCA" if st in WHITE_DWARFS else f"ESTRELLA {st}")
    pc = e.get("PlanetClass", "")
    lab = {"Earthlike body": "TIPO TIERRA", "Water world": "MUNDO DE AGUA", "Ammonia world": "AMONÍACO",
           "Metal rich body": "RICO EN METAL", "High metal content body": "ALTO METAL", "Icy body": "HIELO",
           "Rocky body": "ROCOSO", "Rocky ice body": "ROCA/HIELO"}.get(pc, "GIGANTE GAS" if "gas giant" in pc.lower() else pc.upper())
    return lab + (" TERRAF." if e.get("TerraformState") == "Terraformable" else "")

def interesting(b):
    return b["cls"] in ("TIPO TIERRA", "MUNDO DE AGUA", "AMONÍACO") or "TERRAF." in b["cls"] or b["value"] > 400000

def handle_extra(e):
    ev = e.get("event")
    if ev in ("Location", "FSDJump", "CarrierJump") and e.get("StarSystem"):
        if e["StarSystem"] != explo["system"]:
            explo.update(system=e["StarSystem"], total=None, fss=None, bodies={}, bary={})
        if ev == "FSDJump":
            station.clear()
            if sess:
                sess["jumps"] += 1; sess["ly"] += e.get("JumpDist", 0)
        if e.get("Docked"):
            station.update(status="ATRACADO", name=e.get("StationName"), type=e.get("StationType"))
    elif ev == "FSSDiscoveryScan":
        explo["total"], explo["fss"] = e.get("BodyCount"), e.get("Progress")
    elif ev == "FSSAllBodiesFound":
        explo["fss"] = 1.0; explo["total"] = e.get("Count", explo["total"])
    elif ev == "ScanBaryCentre" and e.get("StarSystem") == explo["system"]:
        explo["bary"][e.get("BodyID")] = e
    elif ev == "Scan" and ("StarType" in e or "PlanetClass" in e):
        name = e.get("BodyName", "?")
        old = explo["bodies"].get(name, {})
        b = {"name": name, "cls": body_label(e), "dist": e.get("DistanceFromArrivalLS", 0),
             "first": e.get("WasDiscovered") is False, "mapped": old.get("mapped", False), "raw": e}
        b["value"] = body_value(e, b["mapped"])
        explo["bodies"][name] = b; unsold[name] = b["value"]
    elif ev == "SAAScanComplete":
        b = explo["bodies"].get(e.get("BodyName"))
        if b:
            b["mapped"] = True; b["value"] = body_value(b["raw"], True); unsold[b["name"]] = b["value"]
    elif ev in ("SellExplorationData", "MultiSellExplorationData"):
        systems = e.get("Systems") or [d.get("SystemName", "") for d in e.get("Discovered") or []]
        for sysname in systems:
            for k in [k for k in unsold if k.startswith(sysname)]:
                unsold.pop(k)
        if sess:
            sess["earn"]["explo"] += e.get("TotalEarnings", 0)
    elif ev == "Died":
        unsold.clear()
        if sess: sess["deaths"] += 1
    # estacion
    elif ev == "DockingRequested":
        station.clear(); station.update(status="SOLICITADO", name=e.get("StationName"), type=e.get("StationType"))
    elif ev == "DockingGranted":
        station.update(status="CONCEDIDO", pad=e.get("LandingPad"), name=e.get("StationName"), type=e.get("StationType"))
    elif ev == "DockingDenied":
        station.update(status="DENEGADO", reason=e.get("Reason"), name=e.get("StationName"), type=e.get("StationType"))
    elif ev in ("DockingTimeout", "DockingCancelled"):
        station.update(status="CADUCADO" if ev == "DockingTimeout" else "CANCELADO", pad=None)
    elif ev == "Docked":
        station.update(status="ATRACADO", name=e.get("StationName"), type=e.get("StationType"),
                       services=e.get("StationServices") or [], dist=e.get("DistFromStarLS"),
                       economy=e.get("StationEconomy_Localised"), faction=(e.get("StationFaction") or {}).get("Name"))
    elif ev == "Undocked":
        station.update(status="DESPEGADO", pad=None)
    # mineria
    elif ev == "ProspectedAsteroid":
        mining["last"] = {"content": e.get("Content_Localised") or e.get("Content"),
                          "motherlode": e.get("MotherlodeMaterial_Localised") or e.get("MotherlodeMaterial"),
                          "remaining": e.get("Remaining"),
                          "mats": [[m.get("Name_Localised") or m.get("Name", "?").capitalize(), m.get("Proportion", 0)]
                                   for m in sorted(e.get("Materials") or [], key=lambda m: -m.get("Proportion", 0))][:5]}
    elif ev == "MiningRefined":
        t = e.get("Type_Localised") or e.get("Type", "?")
        mining["refined"][t] = mining["refined"].get(t, 0) + 1
    elif ev == "LaunchDrone":
        if e.get("Type") == "Prospector": mining["prospectors"] += 1
        elif e.get("Type") == "Collection": mining["collectors"] += 1
    # sesion
    elif ev == "LoadGame":
        new_session(e)
    elif sess and ev in ("Bounty", "FactionKillBond"):
        sess["kills"] += 1
    elif sess and ev == "RedeemVoucher":
        sess["earn"]["bounty"] += e.get("Amount", 0)
    elif sess and ev == "MarketSell":
        sess["earn"]["trade"] += e.get("TotalSale", 0) - e.get("AvgPricePaid", 0) * e.get("Count", 0)
    elif sess and ev == "MissionCompleted":
        sess["earn"]["missions"] += e.get("Reward", 0)
    elif sess and ev == "SellOrganicData":
        sess["earn"]["bio"] += sum(b.get("Value", 0) + b.get("Bonus", 0) for b in e.get("BioData") or [])

def orbit_of(e):
    o = {"id": e.get("BodyID"), "t": iso2epoch(e.get("timestamp"))}
    for k, src, nd in (("a", "SemiMajorAxis", 0), ("e", "Eccentricity", 4), ("i", "OrbitalInclination", 2),
                       ("w", "Periapsis", 2), ("W", "AscendingNode", 2), ("P", "OrbitalPeriod", 0), ("M", "MeanAnomaly", 2)):
        if src in e:
            o[k] = round(e[src], nd) if nd else round(e[src])
    return o

def orbits_pkt():
    out = []
    for b in explo["bodies"].values():
        e = b["raw"]
        o = orbit_of(e)
        o.update(name=b["name"], cls=b["cls"], dist=round(b["dist"]), first=b["first"], mapped=b["mapped"],
                 value=round(b["value"]), r=round(e.get("Radius", 0) / 1000),
                 star=e.get("StarType"), pc=e.get("PlanetClass"), rings=bool(e.get("Rings")),
                 par=[[k, v] for p in e.get("Parents") or [] for k, v in p.items()])
        out.append(o)
    for e in explo["bary"].values():
        out.append(orbit_of(e))
    if edsm["system"] == explo["system"]:
        own = {o["id"] for o in out}
        out += [o for o in edsm["orbits"] if o["id"] not in own]
    return out

def explo_pkt():
    bodies = list(explo["bodies"].values())
    top = sorted([b for b in bodies if interesting(b)], key=lambda b: -b["value"])[:7]
    return {"system": explo["system"], "total": explo["total"], "fss": explo["fss"], "scanned": len(bodies),
            "mapped": sum(b["mapped"] for b in bodies),
            "top": [[b["name"], b["cls"], round(b["dist"]), b["first"], b["mapped"], round(b["value"])] for b in top],
            "unsold": round(sum(unsold.values())), "unsold_n": len(unsold)}

def send(obj):
    data = json.dumps(obj).encode()
    if len(data) < 60000:
        sock.sendto(data, (PI_IP, PORT))

def iso2epoch(s):
    try:
        return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return None

def load_route():
    global route
    try:
        with open(os.path.join(DIR, "NavRoute.json"), encoding="utf-8") as f:
            r = json.load(f).get("Route") or []
        route = [(x.get("StarSystem", "?"), x.get("StarClass", "")) for x in r]
    except (OSError, ValueError):
        pass

def load_cargo():
    global cargo, cargo_mtime
    p = os.path.join(DIR, "Cargo.json")
    try:
        m = os.path.getmtime(p)
        if m == cargo_mtime:
            return
        with open(p, encoding="utf-8") as f:
            c = json.load(f)
        if c.get("Vessel", "Ship") != "Ship":
            return
        cargo = [(x.get("Name_Localised") or x.get("Name", "?").capitalize(), x.get("Count", 0))
                 for x in c.get("Inventory") or []]
        mining["limpets"] = sum(x.get("Count", 0) for x in c.get("Inventory") or [] if x.get("Name") == "drones")
        cargo_mtime = m
    except (OSError, ValueError):
        pass

def handle(e):
    global target
    ev = e.get("event")
    nav = info["nav"]
    if ev in ("Location", "FSDJump", "CarrierJump") and "StarSystem" in e:
        info["system"] = e["StarSystem"]
        target = None
        if ev == "FSDJump":
            nav["last"] = e.get("JumpDist")
            nav["target"] = nav["star"] = None
    elif ev == "LoadGame":
        gm = e.get("GameMode")
        info["mode"] = {"Open": "ABIERTO", "Solo": "SÓLO", "Group": "PRIVADO"}.get(gm, gm.upper() if gm else None)
    elif ev == "Loadout":
        info["fuelcap"] = (e.get("FuelCapacity") or {}).get("Main")
        info["cargocap"] = e.get("CargoCapacity")
    elif ev == "FSDTarget":
        nav["target"], nav["star"] = e.get("Name"), e.get("StarClass")
        nav["jumps"] = e.get("RemainingJumpsInRoute")
    elif ev == "NavRoute":
        load_route()
    elif ev == "NavRouteClear":
        route.clear(); nav["jumps"] = 0
    elif ev == "MissionAccepted":
        missions[e["MissionID"]] = [e.get("LocalisedName") or e.get("Name", "?"),
                                    e.get("DestinationSystem", ""), iso2epoch(e.get("Expiry"))]
    elif ev == "MissionRedirected" and e.get("MissionID") in missions:
        missions[e["MissionID"]][1] = e.get("NewDestinationSystem", "")
    elif ev in ("MissionCompleted", "MissionAbandoned", "MissionFailed"):
        missions.pop(e.get("MissionID"), None)
    elif ev == "ShipTargeted":
        if not e.get("TargetLocked"):
            target = None
        else:
            pilot = e.get("PilotName_Localised") or ""
            target = {"ship": e.get("Ship_Localised") or (e.get("Ship") or "").capitalize(),
                      "scan": e.get("ScanStage", 0), "pilot": pilot,
                      "cmdr": (e.get("PilotName") or "").startswith("$cmdr"),
                      "rank": e.get("PilotRank"), "shield": e.get("ShieldHealth"), "hull": e.get("HullHealth"),
                      "legal": e.get("LegalStatus"), "bounty": e.get("Bounty"),
                      "subsys": e.get("Subsystem_Localised"), "subhealth": e.get("SubsystemHealth")}
    elif ev in ("FSDJump", "SupercruiseEntry", "Docked", "Died"):
        target = None
    elif ev in ("LaunchFighter", "CrewLaunchFighter"):
        fighter["state"] = "out"
        fighter["pilot"] = "Tu" if e.get("PlayerControlled") else (e.get("Crew") or "Tripulante")
    elif ev == "DockFighter":
        fighter["state"] = "hangar"
    elif ev == "FighterDestroyed":
        fighter["state"] = "dead"
    elif ev == "FighterRebuilt":
        fighter["state"] = "ready"
    elif ev == "Missions":
        now = time.time()
        active = {}
        for m in e.get("Active") or []:
            mid = m.get("MissionID")
            active[mid] = missions.get(mid) or [m.get("Name", "?"), "", now + m.get("Expires", 0)]
        missions.clear(); missions.update(active)

# ---- rangos, avisos al panel y EDSM ----
ranks = {"rank": {}, "progress": {}, "cmdr": None}
notes = []           # [seq, tipo, texto] - avisos para el panel (alertas y cambio de menu)
note_seq = [0]
LIVE = [False]       # False mientras se leen los journals antiguos al arrancar

def note(kind, text=""):
    if not LIVE[0]:
        return
    note_seq[0] += 1
    notes.append([note_seq[0], kind, text])
    del notes[:-8]

def handle_more(e):
    ev = e.get("event")
    if ev == "Rank":
        ranks["rank"] = {k: v for k, v in e.items() if k not in ("timestamp", "event")}
    elif ev == "Progress":
        ranks["progress"] = {k: v for k, v in e.items() if k not in ("timestamp", "event")}
    elif ev in ("Promotion",):
        ranks["rank"].update({k: v for k, v in e.items() if k not in ("timestamp", "event")})
    elif ev in ("LoadGame", "Commander"):
        ranks["cmdr"] = e.get("Commander") or e.get("Name") or ranks["cmdr"]
    # avisos
    if ev == "StartJump" and e.get("JumpType") == "Hyperspace":
        note("jump", f"{e.get('StarSystem', '')}|{e.get('StarClass', '')}")
    elif ev == "FSDJump":
        note("jumpend", e.get("StarSystem", ""))
        if LIVE[0]:
            threading.Thread(target=fetch_edsm, args=(e.get("StarSystem"),), daemon=True).start()
    elif ev == "Interdicted":
        note("interdicted", e.get("Interdictor_Localised") or e.get("Interdictor") or "")
    elif ev == "UnderAttack" and e.get("Target", "You") == "You":
        note("underattack")
    elif ev == "ShieldState":
        note("shields_up" if e.get("ShieldsUp") else "shields_down")
    elif ev == "HullDamage" and e.get("PlayerPilot") and not e.get("Fighter") and e.get("Health", 1) < 0.25:
        note("hull", f"{e.get('Health', 0) * 100:.0f}")
    elif ev == "HeatWarning":
        note("heat")
    elif ev == "DockingGranted":
        note("docking", str(e.get("LandingPad", "")))
    elif ev == "LaunchDrone" and e.get("Type") == "Prospector":
        note("prospector")
    elif ev == "LaunchSRV":
        note("srv")
    elif ev == "Disembark":
        note("foot")
    elif ev == "LaunchFighter" and not e.get("PlayerControlled"):
        note("fighter")
    elif ev == "Location" and LIVE[0]:
        threading.Thread(target=fetch_edsm, args=(e.get("StarSystem"),), daemon=True).start()

# EDSM: cuerpos de sistemas ya explorados por otros (para el menu 7.2)
edsm = {"system": None, "orbits": [], "status": ""}
EDSM_STAR = {"Neutron Star": "N", "Black Hole": "H", "Supermassive Black Hole": "SupermassiveBlackHole",
             "T Tauri Star": "TTS", "Herbig Ae/Be Star": "AeBe"}
EDSM_PLANET = {"Earth-like world": "Earthlike body", "Water world": "Water world", "Ammonia world": "Ammonia world",
               "High metal content world": "High metal content body", "Metal-rich body": "Metal rich body",
               "Icy body": "Icy body", "Rocky body": "Rocky body", "Rocky Ice world": "Rocky ice body",
               "Class I gas giant": "Sudarsky class I gas giant", "Class II gas giant": "Sudarsky class II gas giant"}

def edsm_epoch(s):
    try:
        return calendar.timegm(time.strptime(s, "%Y-%m-%d %H:%M:%S"))
    except (TypeError, ValueError):
        return None

def fetch_edsm(system):
    if not system or system == edsm["system"]:
        return
    edsm.update(system=system, orbits=[], status="consultando")
    try:
        url = "https://www.edsm.net/api-system-v1/bodies?systemName=" + urllib.parse.quote(system)
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ElitePanel"}), timeout=15) as r:
            data = json.loads(r.read().decode("utf-8") or "{}")
    except Exception as ex:
        edsm["status"] = "error"; print("EDSM:", ex, flush=True); return
    out = []
    for b in (data.get("bodies") if isinstance(data, dict) else None) or []:
        sub = b.get("subType") or ""
        fake = {"BodyName": b.get("name"), "WasDiscovered": True, "WasMapped": True}
        if b.get("type") == "Star":
            st = EDSM_STAR.get(sub)
            if not st:
                if sub.startswith("White Dwarf"):
                    st = sub[sub.find("(") + 1:sub.find(")")] if "(" in sub else "D"
                else:
                    st = sub.split(" ")[0] if sub else "?"
            fake.update(StarType=st, StellarMass=b.get("solarMasses", 1))
            radius = (b.get("solarRadius") or 0) * 696340
        else:
            pc = EDSM_PLANET.get(sub) or (sub.replace("Class", "Sudarsky class") if "gas giant" in sub else sub)
            fake.update(PlanetClass=pc, MassEM=b.get("earthMasses", 1),
                        TerraformState="Terraformable" if (b.get("terraformingState") or "").startswith("Candidate") else "")
            radius = b.get("radius") or 0
        o = {"id": b.get("bodyId"), "t": edsm_epoch(b.get("updateTime")), "src": "edsm",
             "name": b.get("name"), "cls": body_label(fake), "dist": round(b.get("distanceToArrival") or 0),
             "first": False, "mapped": False, "value": round(body_value(fake)), "r": round(radius),
             "star": fake.get("StarType"), "pc": fake.get("PlanetClass"), "rings": bool(b.get("rings")),
             "par": [[k, v] for p in b.get("parents") or [] for k, v in p.items()]}
        for k, src, mult in (("a", "semiMajorAxis", 1.495978707e11), ("e", "orbitalEccentricity", 1),
                             ("i", "orbitalInclination", 1), ("w", "argOfPeriapsis", 1), ("W", "ascendingNode", 1),
                             ("P", "orbitalPeriod", 86400), ("M", "meanAnomaly", 1)):
            if b.get(src) is not None:
                o[k] = b[src] * mult
        out.append(o)
    if edsm["system"] == system:
        edsm.update(orbits=out[:150], status=f"{len(out)} cuerpos")
        print(time.strftime("%H:%M:%S"), f"EDSM: {system}: {len(out)} cuerpos", flush=True)

def parse_lines(lines):
    for line in lines:
        try:
            e = json.loads(line)
            handle(e)
            handle_extra(e)
            handle_more(e)
        except Exception:
            continue

def startup_scan():
    """Lee los journals de los ultimos dias para recuperar misiones activas."""
    global jfile, jpos
    files = sorted(glob.glob(os.path.join(DIR, "Journal.*.log")), key=os.path.getmtime)
    limit = time.time() - MISSION_DAYS * 86400
    for p in [f for f in files if os.path.getmtime(f) > limit]:
        with open(p, "rb") as f:
            data = f.read()
        cut = data.rfind(b"\n") + 1
        lines = data[:cut].decode("utf-8", "ignore").splitlines()
        parse_lines(lines)
        jfile, jpos = p, cut
    if jfile:
        for line in lines[-15:]:
            send({"log": line})
    load_route(); load_cargo()

def tail_journal():
    global jfile, jpos
    files = sorted(glob.glob(os.path.join(DIR, "Journal.*.log")), key=os.path.getmtime)
    if not files:
        return
    if files[-1] != jfile:
        jfile, jpos = files[-1], 0
    with open(jfile, "rb") as f:
        f.seek(jpos)
        data = f.read()
    cut = data.rfind(b"\n") + 1
    jpos += cut
    lines = data[:cut].decode("utf-8", "ignore").splitlines()
    for line in lines:
        send({"log": line})
    parse_lines(lines)

def route_ahead():
    names = [n for n, _ in route]
    if info["system"] in names:
        return route[names.index(info["system"]) + 1:]
    return route

print("Leyendo journals...")
startup_scan()
LIVE[0] = True
threading.Thread(target=fetch_edsm, args=(explo["system"],), daemon=True).start()
print("Enviando a", PI_IP, PORT)
last_info = None
while True:
    try:
        tail_journal()
        load_cargo()
        with open(os.path.join(DIR, "Status.json"), encoding="utf-8") as f:
            st = json.load(f)
        now = time.time()
        pkt = {"Flags": st.get("Flags", 0), "Flags2": st.get("Flags2", 0), "Fuel": st.get("Fuel"),
               "Pips": st.get("Pips"), **info, "target": target, "fighter": fighter,
               "route": route_ahead()[:8], "balance": st.get("Balance"),
               "explo": explo_pkt(), "orbits": orbits_pkt(), "body": st.get("BodyName"),
               "gui": st.get("GuiFocus", 0), "notes": notes, "ranks": ranks, "edsm": edsm["status"], "station": station, "mining": mining, "sess": sess,
               "cargo": cargo[:40],
               "missions": sorted(([n[:60], d, x] for n, d, x in missions.values() if not x or x > now),
                                  key=lambda m: m[2] or 9e12)[:20]}
        send(pkt)
        summary = (explo["system"], len(explo["bodies"]), len(pkt["orbits"]))
        if summary != last_info:          # solo escribe cuando cambia algo
            last_info = summary
            size = len(json.dumps(pkt).encode())
            print(time.strftime("%H:%M:%S"), f"sistema: {explo['system']}  cuerpos escaneados: {len(explo['bodies'])}"
                  f"  orbitas: {len(pkt['orbits'])}  paquete: {size} bytes" + ("  <-- DEMASIADO GRANDE" if size >= 60000 else ""),
                  flush=True)
    except (OSError, ValueError):
        pass
    except Exception:
        traceback.print_exc()
    time.sleep(0.25)
