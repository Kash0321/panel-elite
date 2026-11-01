# Envia el estado de Elite Dangerous a la Raspberry Pi por UDP
# (Status.json, Journal, NavRoute.json y Cargo.json)
# Ejecutar en el PC de juego (Windows):  python elite_sender.py
import json, socket, time, glob, os, calendar, traceback, threading, urllib.request, urllib.parse, math, zlib

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
                jumps=0, ly=0.0, kills=0, deaths=0, pending=0, pending_n=0,
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

# ---- xenobiologia (menu 7.3) ----
BIO_RANGE = {"Aleoids": 150, "Bacterial": 500, "Cactoid": 300, "Clypeus": 150, "Conchas": 150,
             "Electricae": 1000, "Fonticulus": 500, "Shrubs": 150, "Fumerolas": 100, "Fungoids": 300,
             "Osseus": 800, "Recepta": 150, "Stratum": 500, "Tubus": 800, "Tussocks": 200}
BIO_VALUES = {  # valores base aproximados (comunidad); se corrigen solos con tus ventas reales
    "Aleoida Arcus": 7252500, "Aleoida Coronamus": 6284600, "Aleoida Gravis": 12934900, "Aleoida Laminiae": 3385200,
    "Aleoida Spica": 3385200, "Bacterium Acies": 1000000, "Bacterium Alcyoneum": 1658500, "Bacterium Aurasus": 1000000,
    "Bacterium Bullaris": 1152500, "Bacterium Cerbrus": 1689800, "Bacterium Informem": 8418000,
    "Bacterium Nebulus": 5289900, "Bacterium Omentum": 4638900, "Bacterium Scopulum": 4934500, "Bacterium Tela": 1949000,
    "Bacterium Verrata": 3897000, "Bacterium Vesicula": 1000000, "Bacterium Volu": 7774700,
    "Cactoida Cortexum": 3667600, "Cactoida Lapis": 2483600, "Cactoida Peperatis": 2483600,
    "Cactoida Pullulanta": 3667600, "Cactoida Vermis": 16202800, "Clypeus Lacrimam": 8418000,
    "Clypeus Margaritus": 11873200, "Clypeus Speculumi": 16202800, "Concha Aureolas": 7774700,
    "Concha Biconcavis": 16777100, "Concha Labiata": 2352400, "Concha Renibus": 4572400, "Electricae Pluma": 6284600,
    "Electricae Radialem": 6284600, "Fonticulua Campestris": 1000000, "Fonticulua Digitos": 1804100,
    "Fonticulua Fluctus": 20000000, "Fonticulua Lapida": 3111000, "Fonticulua Segmentatus": 19010800,
    "Fonticulua Upupam": 5727600, "Frutexa Acus": 7774700, "Frutexa Collum": 1639800, "Frutexa Fera": 1632500,
    "Frutexa Flabellum": 1808900, "Frutexa Flammasis": 10326000, "Frutexa Metallicum": 1632500,
    "Frutexa Sponsae": 5988000, "Fumerola Aquatis": 6284600, "Fumerola Carbosis": 6284600,
    "Fumerola Extremus": 16202800, "Fumerola Nitris": 7500900, "Fungoida Bullarum": 3703200,
    "Fungoida Gelata": 3330300, "Fungoida Setisis": 1670100, "Fungoida Stabitis": 2680300, "Osseus Cornibus": 1483000,
    "Osseus Discus": 12934900, "Osseus Fractus": 4027800, "Osseus Pellebantus": 9739000, "Osseus Pumice": 3156300,
    "Osseus Spiralis": 2404700, "Recepta Conditivus": 14313700, "Recepta Deltahedronix": 16202800,
    "Recepta Umbrux": 12934900, "Stratum Araneamus": 2448900, "Stratum Cucumisis": 16202800,
    "Stratum Excutitus": 2448900, "Stratum Frigus": 2637500, "Stratum Laminamus": 2788300, "Stratum Limaxus": 1362000,
    "Stratum Paleas": 1362000, "Stratum Tectonicas": 19010800, "Tubus Cavas": 11873200, "Tubus Compagibus": 7774700,
    "Tubus Conducta": 7774700, "Tubus Rosarium": 2637500, "Tubus Sororibus": 5727600, "Tussock Albata": 3252500,
    "Tussock Capillum": 7025800, "Tussock Caputus": 3472400, "Tussock Catena": 1766600, "Tussock Cultro": 1766600,
    "Tussock Divisa": 1766600, "Tussock Ignis": 1849000, "Tussock Pennata": 5853800, "Tussock Pennatis": 1000000,
    "Tussock Propagito": 1000000, "Tussock Serrati": 4447100, "Tussock Stigmasis": 19010800,
    "Tussock Triticum": 7774700, "Tussock Ventusa": 3277700, "Tussock Virgam": 14313700}
_BV_LAST = {}
for _k, _v in BIO_VALUES.items():
    _BV_LAST.setdefault(_k.split()[-1].lower(), _v)
bio_learned = {}     # valores reales aprendidos de tus ventas (SellOrganicData)

def bio_value(name):
    """(valor, exacto?) de una especie."""
    if not name:
        return None, False
    if name.lower() in bio_learned:
        return bio_learned[name.lower()], True
    v = BIO_VALUES.get(name) or _BV_LAST.get(name.split()[-1].lower())
    return v, False

bio = {"species": None, "genus": None, "variant": None, "range": 100, "step": 0, "pts": [],
       "signals": {}, "genuses": {}, "done": {}, "unsold": 0, "unsold_cr": 0, "body": None, "ship": None, "footfall": {}}
cur_st = {}          # ultimo Status.json leido (posicion en el planeta)

def bio_reset_sample():
    bio.update(species=None, genus=None, variant=None, step=0, pts=[])

def handle_bio(e):
    ev = e.get("event")
    if ev in ("ApproachBody", "Touchdown", "Liftoff", "Location") and e.get("Body"):
        if e.get("BodyType", "Planet") == "Planet" or ev != "Location":
            bio["body"] = e["Body"]
    if ev == "Touchdown" and e.get("Latitude") is not None:
        bio["ship"] = [e["Latitude"], e["Longitude"]]        # tambien cuando la nave aterriza sola (llamada)
    elif LIVE[0] and cur_st.get("Latitude") is not None and (
            (ev == "Disembark" and not e.get("SRV") and not e.get("Taxi") and e.get("OnPlanet")) or ev == "DockSRV"):
        bio["ship"] = [cur_st["Latitude"], cur_st["Longitude"]]   # estas junto a la nave
    elif ev == "Liftoff" and not e.get("PlayerControlled", True):
        bio["ship"] = None                                     # nave despedida: se va
    elif ev == "Liftoff":
        bio["ship"] = None
    if ev in ("LeaveBody", "FSDJump", "CarrierJump"):
        bio["body"] = bio["ship"] = None; bio_reset_sample()
    elif ev == "ScanOrganic":
        key = (e.get("Genus") or "").replace("$Codex_Ent_", "").replace("_Genus_Name;", "")
        sp = e.get("Species_Localised") or e.get("Species")
        if e.get("ScanType") == "Log" or sp != bio["species"]:
            bio.update(species=sp, step=0, pts=[])
        bio.update(genus=e.get("Genus_Localised") or key, variant=e.get("Variant_Localised"),
                   range=BIO_RANGE.get(key, 100))
        if e.get("ScanType") == "Analyse":
            bio.update(step=3, pts=[]); bio["unsold"] += 1
            v, _ = bio_value(sp)
            if v:
                bio["unsold_cr"] += v * (5 if bio["footfall"].get(bio["body"]) is False else 1)
            bio["done"].setdefault(bio["body"], set()).add(bio["genus"])
        else:
            bio["step"] = min(2, bio["step"] + 1)
            if LIVE[0] and cur_st.get("Latitude") is not None:
                bio["pts"].append([cur_st["Latitude"], cur_st["Longitude"]])
    elif ev in ("FSSBodySignals", "SAASignalsFound"):
        name = e.get("BodyName")
        for sg in e.get("Signals") or []:
            if "Biological" in (sg.get("Type") or ""):
                bio["signals"][name] = sg.get("Count")
        if e.get("Genuses"):
            bio["genuses"][name] = [g.get("Genus_Localised") or g.get("Genus") for g in e["Genuses"]]
    elif ev == "Scan" and "WasFootfalled" in e:
        bio["footfall"][e.get("BodyName")] = e["WasFootfalled"]
    elif ev in ("SellOrganicData", "Died"):
        bio["unsold"] = bio["unsold_cr"] = 0
        for s_ in e.get("BioData") or []:
            nm = s_.get("Species_Localised") or s_.get("Species")
            if nm and s_.get("Value"):
                bio_learned[nm.lower()] = s_["Value"]

# ---- estado en vivo (menu 11.2) ----
shipinfo = {"ship": None, "name": None, "ident": None, "hull": None}
suit = {"name": None, "loadout": None}

rhino_state = {}     # ShipID -> "A BORDO" / "FUERA" / "SIN RHINO"

def is_rhino(e):
    return "rhino" in ((e.get("SRVType") or "") + (e.get("Type") or "") + (info.get("srvtype") or "")).lower()

def rhino_label():
    if not shipinfo.get("rhino_bay"):
        return None
    return rhino_state.get(shipinfo.get("id"), "HANGAR")

def handle_live(e):
    ev = e.get("event")
    # estado del Rhino de la nave actual (antes de borrar srvtype)
    if ev in ("LaunchSRV", "DockSRV", "SRVDestroyed", "RestockVehicle", "BuyVehicle") and is_rhino(e):
        rhino_state[shipinfo.get("id")] = {"LaunchSRV": "FUERA", "SRVDestroyed": "SIN RHINO"}.get(ev, "A BORDO")
    if ev == "Loadout":
        items = [m.get("Item", "") for m in e.get("Modules") or []]
        shipinfo.update(ship=e.get("Ship_Localised") or (e.get("Ship") or "").replace("_", " ").title(),
                        name=e.get("ShipName"), ident=e.get("ShipIdent"), hull=e.get("HullHealth"),
                        id=e.get("ShipID"), rhino_bay=any("largebuggybay" in i for i in items))
    elif ev == "HullDamage" and e.get("PlayerPilot") and not e.get("Fighter"):
        shipinfo["hull"] = e.get("Health")
    elif ev == "RepairAll" or (ev == "Repair" and "hull" in str(e.get("Item", e.get("Items", ""))).lower()):
        shipinfo["hull"] = 1.0
    elif ev == "LaunchSRV":
        info["srvtype"] = e.get("SRVType_Localised") or e.get("SRVType")
    elif ev in ("DockSRV", "SRVDestroyed"):
        info["srvtype"] = info["srvcargo"] = info["srvinv"] = None
    elif ev == "Cargo" and e.get("Vessel") == "SRV":
        info["srvcargo"] = e.get("Count")
    elif ev == "SuitLoadout":
        suit.update(name=suit_name(e), loadout=e.get("LoadoutName"))

def live_pkt(st):
    return {"oxy": st.get("Oxygen"), "health": st.get("Health"), "temp": st.get("Temperature"),
            "weapon": st.get("SelectedWeapon_Localised") or st.get("SelectedWeapon"), "grav": st.get("Gravity"),
            "legal": st.get("LegalState"), "cargo": st.get("Cargo"), "alt": st.get("Altitude"),
            "ship": dict(shipinfo, rhino=rhino_label()), "suit": suit}

def bio_pkt(st):
    body = st.get("BodyName") or bio["body"]
    return {"body": body, "signals": bio["signals"].get(body), "genuses": bio["genuses"].get(body, []),
            "done": sorted(bio["done"].get(body, [])), "species": bio["species"], "genus": bio["genus"],
            "variant": bio["variant"], "step": bio["step"], "range": bio["range"], "pts": bio["pts"][-3:],
            "unsold": bio["unsold"], "lat": st.get("Latitude"), "lon": st.get("Longitude"), "R": st.get("PlanetRadius"),
            "ship": bio["ship"], "hdg": st.get("Heading"),
            "value": bio_value(bio["species"])[0], "exact": bio_value(bio["species"])[1],
            "bonus": bio["footfall"].get(body) is False, "unsold_cr": bio["unsold_cr"]}

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
    ed = [o for o in edsm["orbits"] if o.get("name")] if edsm["system"] == explo["system"] else []
    own = {b["name"] for b in bodies}
    extra = [dict(o, src="edsm") for o in ed if o["name"] not in own]
    allb = bodies + extra
    # primero los destacables, luego el resto por valor (el panel lo pagina de 7 en 7)
    top = sorted(allb, key=lambda b: (not interesting(b), -b["value"]))[:42]
    return {"system": explo["system"], "total": explo["total"], "fss": explo["fss"], "scanned": len(bodies),
            "mapped": sum(b["mapped"] for b in bodies),
            "top": [[b["name"], b["cls"], round(b["dist"]), b["first"], b["mapped"], round(b["value"]), b.get("src")]
                    for b in top],
            "edsm_n": len(ed), "edsm_st": edsm["status"] if edsm["system"] == explo["system"] else "",
            "unsold": round(sum(unsold.values())), "unsold_n": len(unsold)}

# datos pesados que casi no cambian: solo se envian si cambian (y todos cada 5 s por si se pierde alguno)
HEAVY = ("orbits", "explo", "sysinfo", "market", "rings", "mats", "carrier", "pack", "srvmats", "alien",
         "exdiary", "ranks", "routeinfo", "ppme", "dest", "mycg", "friends")
_heavy, _full, last_size = {}, [0.0], [0]

def send(obj):
    out = obj
    if "Flags" in obj:
        now = time.time()
        full = now - _full[0] > 5
        if full:
            _full[0] = now
        out = dict(obj)
        for k in HEAVY:
            if k in out:
                js = json.dumps(out[k], sort_keys=True)
                if not full and _heavy.get(k) == js:
                    del out[k]
                else:
                    _heavy[k] = js
    data = b"Z" + zlib.compress(json.dumps(out).encode(), 6)
    if "Flags" in obj:
        last_size[0] = len(data)
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
        if c.get("Vessel", "Ship") == "SRV":            # bodega del Rhino / SRV
            info["srvcargo"] = c.get("Count", 0)
            info["srvinv"] = [[x.get("Name_Localised") or x.get("Name", "?").capitalize(), x.get("Count", 0)]
                              for x in c.get("Inventory") or []]
            cargo_mtime = m
            return
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
        info["starpos"] = e.get("StarPos")
        info["sysaddr"] = e.get("SystemAddress")
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
    elif ev in ("Embark", "DockSRV"):
        note("embark")
    elif ev == "LaunchFighter" and not e.get("PlayerControlled"):
        note("fighter")
    elif ev == "Location" and LIVE[0]:
        threading.Thread(target=fetch_edsm, args=(e.get("StarSystem"),), daemon=True).start()

# ---- avisos extra: combustible en ruta, neutrones, gravedad ----
fuel_used = []       # combustible gastado en los ultimos saltos
cur_star = [None]    # clase de la estrella del sistema actual

def scoopable(c):
    return bool(c) and c.split("_")[0] in ("K", "G", "B", "F", "O", "A", "M")

def body_gravity(name):
    b = explo["bodies"].get(name)
    if b and b["raw"].get("SurfaceGravity"):
        return b["raw"]["SurfaceGravity"] / 9.80665
    if edsm["system"] == explo["system"]:
        for o in edsm["orbits"]:
            if o.get("name") == name and o.get("g"):
                return o["g"]
    return None

alerted = {"bodies": set(), "wanted": {}, "missions": set()}

def handle_alerts2(e):
    """Hallazgos, Codice, buscados, misiones en destino, recompensas pendientes y fin de sesion."""
    ev = e.get("event")
    if ev == "Scan" and e.get("BodyName") and ("PlanetClass" in e or "StarType" in e):
        b = explo["bodies"].get(e["BodyName"])
        if LIVE[0] and b and interesting(b) and b["name"] not in alerted["bodies"]:
            alerted["bodies"].add(b["name"])
            sysname = explo.get("system") or ""
            short = b["name"][len(sysname):].strip() if b["name"].startswith(sysname) else b["name"]
            note("find", f"{b['name']}|{b['cls']}|{round(b['value'])}|{int(b['first'])}|{round(body_value(e, True))}")
    elif ev == "CodexEntry" and e.get("IsNewEntry"):
        note("codex", f"{e.get('Name_Localised') or e.get('Name', '?')}|{e.get('SubCategory_Localised') or e.get('Category_Localised') or ''}|{e.get('Region_Localised') or ''}")
    elif ev == "ShipTargeted" and e.get("ScanStage") == 3 and (e.get("LegalStatus") or "").lower() == "wanted":
        key = (e.get("PilotName_Localised"), e.get("Ship"))
        if time.time() - alerted["wanted"].get(key, 0) > 120:
            alerted["wanted"][key] = time.time()
            note("wanted", f"{e.get('Ship_Localised') or (e.get('Ship') or '').capitalize()}|{e.get('PilotName_Localised') or ''}|{e.get('Bounty') or 0}")
    elif ev == "Bounty" and sess:
        sess["pending"] = sess.get("pending", 0) + (e.get("TotalReward") or e.get("Reward") or 0)
        sess["pending_n"] = sess.get("pending_n", 0) + 1
    elif ev == "RedeemVoucher" and e.get("Type") == "bounty" and sess:
        sess["pending"], sess["pending_n"] = 0, 0
    elif ev in ("FSDJump", "Location") and e.get("StarSystem"):
        here = [m[0] for m in missions.values() if m[1] == e["StarSystem"]]
        if here:
            note("missionhere", f"{len(here)}|{here[0][:40]}")
    elif ev == "Shutdown" and sess:
        ea = sess.get("earn") or {}
        tot = sum(ea.values())
        note("sessend", "|".join(str(x) for x in (round(tot), round(time.time() - (sess.get("start") or time.time())),
             sess.get("jumps", 0), round(sess.get("ly", 0)), round(ea.get("explo", 0)), round(ea.get("bio", 0)),
             round(ea.get("trade", 0)), round(ea.get("bounty", 0)), sum((mining.get("refined") or {}).values()))))

# ---- a pie y en vehiculo: mochila, crimenes, taxi, asentamientos, materiales del terreno ----
pack = {"cons": [], "n_items": 0, "n_comp": 0, "n_data": 0}
pack_mtime = [0]
srvmats = {}         # materiales recogidos desde que sacaste el vehiculo
CONS_ORDER = ["healthpack", "energycell", "amm_grenade_frag", "amm_grenade_emp", "amm_grenade_shield", "bypass"]
CRIME_ES = {"assault": "agresión", "murder": "asesinato", "piracy": "piratería", "fireInNoFireZone": "disparar en zona prohibida",
            "collidedAtSpeedInNoFireZone": "choque en zona prohibida", "dockingMajorTresspass": "allanamiento de plataforma",
            "dockingMinorTresspass": "invadir plataforma", "illegalCargo": "carga ilegal", "recklessWeaponsDischarge": "disparo imprudente",
            "onFoot_trespass": "allanamiento", "onFoot_theft": "robo", "onFoot_murder": "asesinato", "onFoot_assault": "agresión",
            "onFoot_identityTheft": "suplantación", "onFoot_breakingAndEntering": "entrada forzada",
            "onFoot_damagingDefences": "dañar defensas", "onFoot_overchargedPort": "sobrecargar puerto",
            "onFoot_carryingIllegalGoods": "objetos ilegales", "onFoot_arcCutterUse": "uso de cortador",
            "onFoot_recklessWeaponsDischarge": "disparo imprudente", "onFoot_propertyTheft": "robo"}

def load_backpack():
    p = os.path.join(DIR, "Backpack.json")
    try:
        m = os.path.getmtime(p)
        if m == pack_mtime[0]:
            return
        with open(p, encoding="utf-8") as f:
            b = json.load(f)
        pack_mtime[0] = m
    except (OSError, ValueError):
        return
    old = {k: c for k, _, c in pack.get("raw", [])}
    cons = [(x.get("Name", "").lower(), x.get("Name_Localised") or x.get("Name", "?"), x.get("Count", 0)) for x in b.get("Consumables") or []]
    cons.sort(key=lambda c: CONS_ORDER.index(c[0]) if c[0] in CONS_ORDER else 99)
    pack.update(raw=cons, cons=[[n, c] for _, n, c in cons],
                n_items=sum(x.get("Count", 0) for x in b.get("Items") or []),
                n_comp=sum(x.get("Count", 0) for x in b.get("Components") or []),
                n_data=sum(x.get("Count", 0) for x in b.get("Data") or []))
    if cur_st.get("Flags2", 0) & 1:
        for k, n, c in cons:
            if k in ("healthpack", "energycell") and c <= 1 and old.get(k, 99) > c:
                note("lowcons", f"{n}|{c}")

def handle_foot(e):
    ev = e.get("event")
    if ev == "CommitCrime":
        ct = e.get("CrimeType", "")
        name = CRIME_ES.get(ct) or ct.replace("onFoot_", "").replace("_", " ")
        note("crime", f"{name}|{e.get('Fine') or 0}|{e.get('Bounty') or 0}|{e.get('Faction', '')}")
    elif ev in ("BookTaxi", "BookDropship"):
        note("taxi", f"{'LANZADERA APEX' if ev == 'BookTaxi' else 'TRANSPORTE MILITAR'}|{e.get('DestinationSystem', '')}|"
                     f"{e.get('DestinationLocation', '')}|{e.get('Cost', 0)}")
    elif ev == "ApproachSettlement":
        fac = (e.get("StationFaction") or {}).get("Name") or ""
        rep = next((f[3] for f in sysinfo.get("facs") or [] if f[0] == fac[:30]), None)
        econ = ", ".join((x.get("Name_Localised") or "") for x in e.get("StationEconomies") or [])[:40]
        note("settle", f"{e.get('Name_Localised') or e.get('Name', '?')}|{fac}|{e.get('StationGovernment_Localised') or ''}|"
                       f"{econ}|{'' if rep is None else round(rep)}")
    elif ev == "LaunchSRV":
        srvmats.clear()
    elif ev == "MaterialCollected" and info.get("srvtype"):
        k = (e.get("Name") or "").lower()
        n = e.get("Name_Localised") or k.capitalize()
        srvmats[k] = [n, srvmats.get(k, [n, 0])[1] + (e.get("Count") or 1)]

def srvmats_pkt():
    out = []
    for k, (n, c) in sorted(srvmats.items(), key=lambda kv: -kv[1][1]):
        mx = MAT_MAX.get(MAT_GRADE.get(k))
        out.append([n, c, bool(mx and (mats.get(k) or [0, 0])[1] >= mx)])
    return out[:8]

# ---- combate con nave ----
combat = {"kills": [], "bonds": {}, "sd": None}
cmdr_seen = {}
hull_warned = [False]

def handle_combat(e):
    ev = e.get("event")
    handle_foot2(e)
    if ev == "LoadGame":
        combat.update(kills=[], bonds={}, sd=None, n=0)
    elif ev == "ShieldState":
        combat["sd"] = None if e.get("ShieldsUp") or not LIVE[0] else time.time()
    elif ev in ("Bounty", "FactionKillBond", "PVPKill"):
        if ev == "Bounty":
            tgt, rew, kind = e.get("Target_Localised") or (e.get("Target") or "?").capitalize(), e.get("TotalReward") or e.get("Reward") or 0, "R"
        elif ev == "FactionKillBond":
            tgt, rew, kind = e.get("VictimFaction_Localised") or e.get("VictimFaction") or "?", e.get("Reward") or 0, "B"
            if "thargoid" in (e.get("VictimFaction") or "").lower():
                tgt, kind = "THARGOIDE", "T"
            fac = e.get("AwardingFaction_Localised") or e.get("AwardingFaction") or "?"
            combat["bonds"][fac] = combat["bonds"].get(fac, 0) + rew
        else:
            tgt, rew, kind = e.get("Victim") or "?", 0, "P"
        combat["kills"].insert(0, [tgt[:28], rew, kind])
        del combat["kills"][8:]
        if LIVE[0]:
            veh = "F" if cur_st.get("Flags2", 0) & 1 else "S" if cur_st.get("Flags", 0) & (1 << 26) else "N"
        else:
            veh = "F" if footcz["onfoot"] else "N"
        combat["n"] = combat.get("n", 0) + 1
        ln, lc = ledger_tot()
        note("kill", f"{tgt[:28]}|{rew}|{kind}|{veh}|{footcz['n'] if veh == 'F' else combat['n']}|{ln}|{lc}")
    elif ev == "Interdicted" and e.get("Submitted"):
        note("submitted", f"{e.get('Interdictor_Localised') or e.get('Interdictor') or ''}|{int(bool(e.get('IsPlayer')))}")
    elif ev == "EscapeInterdiction":
        note("escaped", f"{e.get('Interdictor_Localised') or e.get('Interdictor') or ''}|{int(bool(e.get('IsPlayer')))}")
    elif ev == "HullDamage" and e.get("PlayerPilot") and not e.get("Fighter"):
        h = e.get("Health", 1)
        if h < 0.25 and not hull_warned[0]:
            hull_warned[0] = True
            note("rebuy", f"{h * 100:.0f}|{shipinfo.get('rebuy') or 0}")
        elif h > 0.5:
            hull_warned[0] = False
    elif ev in ("RepairAll", "Repair"):
        hull_warned[0] = False
    elif ev == "Died":
        k = (e.get("Killers") or [{}])[0] if e.get("Killers") else e
        note("died", f"{k.get('Name') or k.get('KillerName') or '?'}|{k.get('Ship') or k.get('KillerShip') or ''}|"
                     f"{k.get('Rank') or k.get('KillerRank') or ''}|{shipinfo.get('rebuy') or 0}")
        combat["sd"] = None
    elif ev == "ShipTargeted" and e.get("TargetLocked") and (e.get("PilotName") or "").startswith("$cmdr"):
        key = e.get("PilotName_Localised")
        if time.time() - cmdr_seen.get(key, 0) > 120:
            cmdr_seen[key] = time.time()
            note("cmdrtarget", f"{key or '?'}|{e.get('Ship_Localised') or (e.get('Ship') or '').capitalize()}|{e.get('PilotRank') or ''}")
    elif ev == "Loadout":
        shipinfo["rebuy"] = e.get("Rebuy")

# ---------- combate a pie: bajas, zona de conflicto y bonos sin cobrar (se guardan hasta cobrarlos) ----------
LEDGER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bonos_sin_cobrar.json")

def ledger_load():
    try:
        with open(LEDGER_FILE, encoding="utf-8") as f:
            L = json.load(f)
        L.setdefault("ts", ""); L.setdefault("bonds", {}); L.setdefault("bounties", {})
        return L
    except (OSError, ValueError):
        return {"ts": "", "bonds": {}, "bounties": {}}

ledger = ledger_load()

def ledger_save():
    try:
        with open(LEDGER_FILE + ".tmp", "w", encoding="utf-8") as f:
            json.dump(ledger, f, ensure_ascii=False)
        os.replace(LEDGER_FILE + ".tmp", LEDGER_FILE)
    except OSError:
        pass

def ledger_tot():
    n = sum(v[0] for k in ("bonds", "bounties") for v in ledger[k].values())
    c = sum(v[1] for k in ("bonds", "bounties") for v in ledger[k].values())
    return n, c

footcz = {"onfoot": False, "zone": "", "state": "", "side": "", "enemy": "", "n": 0, "t0": None, "t1": None,
          "suit": "", "weapons": [], "appr": None}
SUITS = {"tacticalsuit": "Dominator", "utilitysuit": "Maverick", "explorationsuit": "Artemis", "flightsuit": "Traje de vuelo"}

_seen_ts = {}

def ledger_new(ts):
    """Cada evento cuenta una sola vez aunque se relea el journal (tambien si hay varios en el mismo segundo)."""
    c = _seen_ts[ts] = _seen_ts.get(ts, 0) + 1
    if ts > ledger.get("ts", "") or (ts == ledger.get("ts") and c > ledger.get("k", 0)):
        ledger["ts"], ledger["k"] = ts, c
        return True
    return False

def is_foot():
    """A pie: en directo lo dice Status.json; al releer el journal, los eventos de bajar/subir."""
    if LIVE[0] and cur_st:
        return bool(cur_st.get("Flags2", 0) & 1)
    return footcz["onfoot"]

def suit_name(e):
    loc = e.get("SuitName_Localised") or ""
    if loc and not loc.startswith("$"):
        return loc
    base, _, cl = (e.get("SuitName") or "").lower().partition("_class")
    return SUITS.get(base, base.capitalize()) + (f" G{cl}" if cl.isdigit() else "")

def handle_foot2(e):
    ev, ts = e.get("event"), e.get("timestamp", "")
    new = ev in ("FactionKillBond", "Bounty", "RedeemVoucher", "Resurrect") and ledger_new(ts)
    if ev in ("FactionKillBond", "Bounty") and new:
        if ev == "FactionKillBond":
            key, facs = "bonds", [(e.get("AwardingFaction") or "?", e.get("Reward") or 0)]
        else:
            key = "bounties"
            facs = [(x.get("Faction") or "?", x.get("Reward") or 0) for x in (e.get("Rewards") or [])] \
                or [(e.get("VictimFaction") or "?", e.get("TotalReward") or 0)]
        for k, (f, v) in enumerate(facs):
            a = ledger[key].setdefault(f[:40], [0, 0])
            a[0] += 1 if k == 0 else 0
            a[1] += v
        ledger_save()
    elif ev == "RedeemVoucher" and new:
        typ = (e.get("Type") or "").lower()
        key = "bonds" if typ == "combatbond" else "bounties" if typ == "bounty" else None
        if key:
            facs = [x.get("Faction") for x in (e.get("Factions") or []) if x.get("Faction")]
            if e.get("Faction"):
                facs.append(e["Faction"])
            sel = [k for k in ledger[key] if not facs or any(k == f[:40] or k.startswith(f[:20]) for f in facs)]
            note("redeem", f"{e.get('Amount') or 0}|{sum(ledger[key][k][1] for k in sel)}|{key}")
            if facs:
                for f in facs:
                    for k in [k for k in ledger[key] if k == f[:40] or k.startswith(f[:20])]:
                        ledger[key].pop(k, None)
            else:
                ledger[key].clear()
        ledger_save()
    elif ev == "Resurrect" and new and (e.get("Option") or "").lower() == "rebuy":
        # solo se pierden al reaparecer pagando el seguro de la nave; a pie ("rejoin") se conservan
        ledger["bonds"].clear(); ledger["bounties"].clear(); ledger_save()
    if ev in ("CollectItems", "UseConsumable") and (e.get("Type") or "") == "Consumable":
        n = (e.get("Name") or "").lower()
        loc = e.get("Name_Localised") or n
        have = {k: c for k, _, c in pack.get("raw", [])}.get(n, 0)
        if ev == "CollectItems":
            footcz["lastpick"] = (n, ts)
            note("pickup", f"{n}|{loc}|{have + (e.get('Count') or 1)}")
        else:
            left = have if footcz.get("lastpick") == (n, ts) else max(0, have - 1)
            note("usecons", f"{n}|{loc}|{left}")
    if ev == "RedeemVoucher" and (e.get("Type") or "").lower() in ("combatbond", "bounty"):
        footcz.update(n=0, t0=None, t1=None)          # al cobrar el contador de bajas vuelve a cero
        combat["n"] = 0
    if ev in ("Disembark", "DropshipDeploy"):
        footcz["onfoot"] = True
    elif ev == "Embark":
        footcz["onfoot"] = False
    elif ev == "LoadGame":                          # si cargas la partida a pie, "Ship" es el traje
        footcz["onfoot"] = "suit" in (e.get("Ship") or "").lower()
    if ev == "BookDropship":
        footcz["zone"] = e.get("DestinationLocation") or ""
        note("dropship", f"{footcz['zone']}|{e.get('DestinationSystem') or ''}")
    elif ev == "ApproachSettlement":
        sf = e.get("StationFaction") or {}
        footcz["appr"] = (e.get("Name_Localised") or e.get("Name") or "", sf.get("Name") or "", sf.get("FactionState") or "")
        if e.get("Latitude") is not None:
            footcz["spos"] = [e["Latitude"], e["Longitude"], e.get("BodyName") or "", footcz["appr"][0]]
    elif ev == "DropshipDeploy":
        a = footcz.get("appr") or (footcz["zone"], "", "")
        footcz.update(zone=a[0] or footcz["zone"], state=a[2])
        note("deploy", f"{footcz['zone']}|{a[1]}|{a[2]}")
    elif ev == "SuitLoadout":
        sn = (e.get("SuitName") or "").lower()
        base, _, cl = sn.partition("_class")
        footcz["suit"] = SUITS.get(base, base.capitalize()) + (f" G{cl}" if cl.isdigit() else "")
        footcz["weapons"] = [m.get("ModuleName_Localised") or m.get("ModuleName") or "" for m in (e.get("Modules") or [])]
    elif ev == "FactionKillBond" and is_foot():
        t = iso2epoch(ts) or time.time()
        a = footcz.get("appr")
        if a and a[0] and a[0] != footcz["zone"]:          # otro asentamiento (el contador sigue hasta que cobres)
            footcz.update(zone=a[0], state=a[2])
        footcz["n"] += 1
        footcz["t0"] = footcz["t0"] or t
        footcz["t1"] = t
        footcz["side"] = e.get("AwardingFaction_Localised") or e.get("AwardingFaction") or ""
        footcz["enemy"] = e.get("VictimFaction_Localised") or e.get("VictimFaction") or ""

def footcz_pkt():
    if LIVE[0] and cur_st:
        footcz["onfoot"] = bool(cur_st.get("Flags2", 0) & 1)
    n, c = ledger_tot()
    mins = ((footcz["t1"] or 0) - (footcz["t0"] or 0)) / 60
    return {"onfoot": footcz["onfoot"], "zone": footcz["zone"], "state": footcz["state"], "side": footcz["side"],
            "enemy": footcz["enemy"], "n": footcz["n"], "rate": round(footcz["n"] / mins, 1) if mins >= 1 else None,
            "suit": footcz["suit"], "weapons": footcz["weapons"], "spos": footcz.get("spos"),
            "led": {"n": n, "cr": c,
                    "bonds": [sum(v[0] for v in ledger["bonds"].values()), sum(v[1] for v in ledger["bonds"].values())],
                    "bounties": [sum(v[0] for v in ledger["bounties"].values()), sum(v[1] for v in ledger["bounties"].values())]}}

# ---------- v0.71: llegada al salir de supercrucero, senales, lanzamientos, copiloto y modo OPERATIONS ----------
ops = {"on": False, "t0": None, "ship": "", "kills": 0, "cr": 0, "merits": 0, "mission": "", "target": "",
       "merc": None, "merc0": None, "lastgain": None, "pending": None}
crew = {"name": "", "paid": 0, "n": 0}
drop = {"name": "", "threat": 0, "t": 0}
GRENADES = ("amm_grenade_frag", "amm_grenade_emp", "amm_grenade_shield")

def handle_v071(e):
    ev = e.get("event")
    if ev == "SupercruiseDestinationDrop":
        drop.update(name=e.get("Type_Localised") or e.get("Type") or "", threat=e.get("Threat") or 0, t=time.time(),
                    market=bool(e.get("MarketID")))
        exd["signals"] = exd.get("signals", 0) + (0 if e.get("MarketID") else 1)
        if ops["on"]:
            ops["target"] = drop["name"]
    elif ev == "SupercruiseExit":
        recent = time.time() - drop["t"] < 30 if LIVE[0] else False
        nm = drop["name"] if recent else ""
        note("arrive", f"{nm}|{drop['threat'] if recent else 0}|{e.get('Body') or ''}|{e.get('BodyType') or ''}|"
                       f"{int(bool(recent and drop.get('market')))}")
        drop["t"] = 0
    elif ev == "BackpackChange":
        have = {k: c for k, _, c in pack.get("raw", [])}
        for x in e.get("Removed") or []:
            n = (x.get("Name") or "").lower()
            if n in GRENADES:
                note("thrown", f"{n}|{x.get('Name_Localised') or n}|{max(0, have.get(n, 0) - (x.get('Count') or 1))}")
    elif ev == "NpcCrewPaidWage":
        crew["paid"] += e.get("Amount") or 0
        crew["n"] += 1
        crew["name"] = e.get("NpcCrewName") or crew["name"]
    elif ev == "Statistics":
        mc = (e.get("Bank_Account") or {}).get("MercCoins_Current")
        if mc is not None:
            if ops["merc"] is not None and mc > ops["merc"]:
                ops["lastgain"] = mc - ops["merc"]
            ops["merc"] = mc
        if ops["pending"]:
            ops_summary()
    elif ev == "GameModeChange":
        gm = (e.get("GameMode") or "")
        if gm.lower().startswith("operation") and not ops["on"]:
            ops.update(on=True, t0=iso2epoch(e.get("timestamp")) or time.time(), kills=0, cr=0, merits=0,
                       target="", merc0=ops["merc"], pending=None)
            info["mode"] = "OPERACIÓN"
            note("opstart", f"{ops['ship']}|{squad.get('name', '')}")
        elif gm.lower() == "maingame" and ops["on"]:
            ops["on"] = False
            if info.get("mode") == "OPERACIÓN":
                info["mode"] = None
            ops["pending"] = time.time()               # el resumen sale al llegar las estadisticas (Merc Coin)
            ops["t1"] = iso2epoch(e.get("timestamp")) or time.time()
    elif ev == "LoadGame":
        ops["ship"] = e.get("Ship_Localised") or (e.get("Ship") or "").replace("_", " ")
    elif ev == "SquadronStartup":
        squad["name"] = e.get("SquadronName") or ""
    elif ev == "Missions" and ops["on"]:
        act = e.get("Active") or []
        ops["mission"] = act[0].get("Name", "") if act else ""
    elif ev == "Bounty" and ops["on"]:
        ops["kills"] += 1
        ops["cr"] += e.get("TotalReward") or sum(x.get("Reward", 0) for x in e.get("Rewards") or [])
    elif ev == "FactionKillBond" and ops["on"]:
        ops["kills"] += 1
        ops["cr"] += e.get("Reward") or 0
    elif ev == "PowerplayMerits" and ops["on"]:
        ops["merits"] += e.get("MeritsGained") or 0

squad = {"name": ""}

def ops_summary():
    if not ops["pending"]:
        return
    gain = (ops["merc"] - ops["merc0"]) if ops["merc"] is not None and ops["merc0"] is not None else ""
    mins = round(((ops.get("t1") or time.time()) - (ops["t0"] or time.time())) / 60)
    note("opend", f"{ops['kills']}|{ops['cr']}|{gain}|{ops['merits']}|{mins}")
    ops["pending"] = None

def check_ops():
    if ops["pending"] and time.time() - ops["pending"] > 30:     # si no llegan estadisticas
        ops_summary()

def ops_pkt():
    return {"on": ops["on"], "ship": ops["ship"], "kills": ops["kills"], "cr": ops["cr"], "merits": ops["merits"],
            "mission": ops["mission"], "target": ops["target"], "merc": ops["merc"], "lastgain": ops["lastgain"],
            "t0": ops["t0"], "crew": crew}

def combat_pkt():
    return {"kills": combat["kills"], "sd": combat["sd"],
            "bonds": sorted([[f[:30], v] for f, v in combat["bonds"].items()], key=lambda x: -x[1])[:4]}

def check_missions():
    if not LIVE[0]:
        return
    now = time.time()
    for mid, (name, dest, exp) in list(missions.items()):
        if exp and 0 < exp - now < 3600 and mid not in alerted["missions"]:
            alerted["missions"].add(mid)
            note("missionexp", f"{name[:40]}|{int((exp - now) // 60)}|{dest or ''}")

def handle_alerts(e):
    ev = e.get("event")
    handle_alerts2(e)
    handle_foot(e)
    handle_combat(e)
    handle_explo_alerts(e)
    handle_exdiary(e)
    handle_alien(e)
    handle_friends(e)
    handle_cg(e)
    handle_v071(e)
    if ev == "SystemsShutdown":
        note("shutdown", "")
    if ev == "StartJump" and e.get("JumpType") == "Hyperspace":
        cur_star[0] = e.get("StarClass")
    elif ev == "Location":
        cur_star[0] = None
    elif ev == "FSDJump":
        if e.get("FuelUsed"):
            fuel_used.append(e["FuelUsed"]); del fuel_used[:-5]
        ahead = route_ahead()
        if not LIVE[0] or not ahead or not fuel_used:
            return
        avg = sum(fuel_used) / len(fuel_used)
        n = next((i + 1 for i, (_, c) in enumerate(ahead) if scoopable(c)), None)
        name = ahead[n - 1][0] if n else ""
        jumps = n or len(ahead)
        need, have = jumps * avg, e.get("FuelLevel", 0)
        if have < need * 1.1:                          # 10% de margen
            kind = "here" if scoopable(cur_star[0]) else "no"
            note("fuelroute", f"{kind}|{have:.1f}|{need:.1f}|{jumps}|{name}")
    elif ev == "Liftoff" and e.get("PlayerControlled") is False:
        note("shipgone")
    elif ev == "Touchdown" and e.get("PlayerControlled") is False:
        note("shipland", f"{e.get('Latitude', '')}|{e.get('Longitude', '')}")
    elif ev == "JetConeBoost":
        note("jetcone", f"{e.get('BoostValue', 4):g}")
    elif ev == "JetConeDamage":
        note("jetdmg", e.get("Module_Localised") or e.get("Module") or "")
    elif ev == "ApproachBody":
        g = body_gravity(e.get("Body"))
        if g and g >= 1.5:
            note("gravity", f"{g:.2f}|{e.get('Body', '')}")

# ---- anillos y puntos calientes de mineria (menu 7.4) ----
RING_CLS = {"eRingClass_Metalic": "METÁLICO", "eRingClass_MetalRich": "RICO EN METAL",
            "eRingClass_Rocky": "ROCOSO", "eRingClass_Icy": "HELADO"}
RESERVE = {"PristineResources": "PRÍSTINAS", "MajorResources": "MAYORES", "CommonResources": "COMUNES",
           "LowResources": "BAJAS", "DepletedResources": "AGOTADAS"}
rings = {}           # planeta -> {"reserve": .., "rings": {nombre: clase}}
hotspots = {}        # anillo -> [[mineral, cantidad]]

def handle_rings(e):
    ev = e.get("event")
    if ev == "Scan" and e.get("Rings") and e.get("BodyName"):
        rings[e["BodyName"]] = {"reserve": RESERVE.get(e.get("ReserveLevel"), ""),
                                "rings": {r.get("Name"): RING_CLS.get(r.get("RingClass"), "")
                                          for r in e["Rings"] if "Belt" not in (r.get("Name") or "")}}
    elif ev == "SAASignalsFound" and (e.get("BodyName") or "").endswith(" Ring"):
        hotspots[e["BodyName"]] = [[s.get("Type_Localised") or s.get("Type", "?"), s.get("Count", 0)]
                                   for s in e.get("Signals") or []]
    elif ev in ("SAASignalsFound", "FSSBodySignals") and e.get("BodyName"):
        # señales del planeta, incluidas las zonas de mineria de superficie (Rhino), sea cual sea su nombre
        sig = [[s.get("Type_Localised") or s.get("Type", "?"), s.get("Count", 0), s.get("Type", "")]
               for s in e.get("Signals") or []]
        if sig and (ev == "SAASignalsFound" or e["BodyName"] not in planet_sig):
            planet_sig[e["BodyName"]] = sig
    if ev and ev not in LOGGED_EV and any(k in ev for k in ("Mining", "Deposit", "Rhino")):
        LOGGED_EV.add(ev)
        print("EVENTO NUEVO DE MINERIA:", json.dumps(e)[:400], flush=True)

planet_sig = {}      # planeta -> [[señal, cantidad, tipo interno]]
LOGGED_EV = set()

def rings_pkt(st):
    body = st.get("BodyName") or ""
    planet = body.rsplit(" ", 2)[0] if body.endswith(" Ring") else body
    if not planet:
        return {}
    info_ = rings.get(planet) or {}
    names = dict(info_.get("rings") or {})
    for k in hotspots:
        if k.startswith(planet + " ") and k.endswith(" Ring"):
            names.setdefault(k, "")
    sig = [s[:2] for s in planet_sig.get(planet, [])]
    out = [[n[len(planet):].strip(), c, hotspots.get(n)] for n, c in sorted(names.items())]
    return {"planet": planet, "reserve": info_.get("reserve", ""), "rings": out, "signals": sig,
            "here": body if body != planet else ""}

# ---- politica del sistema y de la estacion (menu 3) ----
sysinfo = {}
STATE_ES = {"None": "", "Boom": "AUGE", "Bust": "QUIEBRA", "CivilUnrest": "DISTURBIOS", "CivilWar": "GUERRA CIVIL",
            "Election": "ELECCIONES", "Expansion": "EXPANSIÓN", "Famine": "HAMBRUNA", "Investment": "INVERSIÓN",
            "Lockdown": "BLOQUEO", "Outbreak": "BROTE", "Retreat": "RETIRADA", "War": "GUERRA",
            "CivilLiberty": "LIBERTAD CIVIL", "PirateAttack": "ATAQUE PIRATA", "Blight": "PLAGA",
            "Drought": "SEQUÍA", "InfrastructureFailure": "FALLO INFRAESTR.", "NaturalDisaster": "DESASTRE",
            "PublicHoliday": "FIESTA", "Terrorism": "TERRORISMO", "ColdWar": "GUERRA FRÍA"}
PP_ES = {"Stronghold": "BASTIÓN", "Fortified": "FORTIFICADO", "Exploited": "EXPLOTADO",
         "Unoccupied": "SIN OCUPAR", "Contested": "EN DISPUTA", "InPrepareRadius": "PREPARACIÓN",
         "Controlled": "CONTROLADO", "Prepared": "PREPARADO", "HomeSystem": "SEDE"}

ALLEG_ES = {"Federation": "Federación", "Empire": "Imperio", "Alliance": "Alianza", "Independent": "Independiente",
            "Thargoid": "Thargoide", "Guardian": "Guardianes", "PilotsFederation": "Pilots Federation"}

ppme = {}            # tu Powerplay: potencia, rango, meritos, meritos de la sesion

def handle_ppme(e):
    ev = e.get("event")
    if ev == "Powerplay":
        ppme.update(power=e.get("Power"), rank=e.get("Rank"), merits=e.get("Merits"))
    elif ev == "PowerplayMerits":
        ppme.update(power=e.get("Power", ppme.get("power")), merits=e.get("TotalMerits", ppme.get("merits")))
        ppme["session"] = ppme.get("session", 0) + (e.get("MeritsGained") or 0)
    elif ev == "PowerplayRank":
        ppme["rank"] = e.get("Rank", ppme.get("rank"))
    elif ev in ("PowerplayJoin", "PowerplayDefect"):
        ppme.update(power=e.get("Power") or e.get("ToPower"), rank=1, merits=0)
    elif ev == "PowerplayLeave":
        ppme.clear()
    elif ev == "LoadGame":
        ppme["session"] = 0

def handle_sysinfo(e):
    ev = e.get("event")
    handle_ppme(e)
    if ev in ("FSDJump", "Location", "CarrierJump") and e.get("StarSystem"):
        sf = e.get("SystemFaction") or {}
        facs = sorted(e.get("Factions") or [], key=lambda f: -f.get("Influence", 0))
        sysinfo.clear()
        sysinfo.update(
            faction=sf.get("Name"), fstate=STATE_ES.get(sf.get("FactionState"), sf.get("FactionState") or ""),
            gov=e.get("SystemGovernment_Localised") or "", alleg=ALLEG_ES.get(e.get("SystemAllegiance"), e.get("SystemAllegiance") or "Independiente"),
            sec=e.get("SystemSecurity_Localised") or "", econ=e.get("SystemEconomy_Localised") or "",
            pop=e.get("Population"),
            pp=e.get("ControllingPower"), ppstate=PP_ES.get(e.get("PowerplayState"), e.get("PowerplayState") or ""),
            powers=e.get("Powers") or [],
            pp_prog=e.get("PowerplayStateControlProgress"),
            pp_reinf=e.get("PowerplayStateReinforcement"), pp_under=e.get("PowerplayStateUndermining"),
            pp_conf=sorted([[c.get("Power", "?"), c.get("ConflictProgress", 0)] for c in e.get("PowerplayConflictProgress") or []],
                           key=lambda c: -c[1]),
            facs=[[f.get("Name", "?")[:30], round(f.get("Influence", 0) * 100, 1),
                   STATE_ES.get(f.get("FactionState"), f.get("FactionState") or ""), f.get("MyReputation")]
                  for f in facs[:6]])
    if ev in ("Docked", "Location") and e.get("StationName"):
        stf = e.get("StationFaction") or {}
        sysinfo.update(st_name=e.get("StationName"), st_faction=stf.get("Name"),
                       st_fstate=STATE_ES.get(stf.get("FactionState"), stf.get("FactionState") or ""),
                       st_gov=e.get("StationGovernment_Localised") or "", st_alleg=ALLEG_ES.get(e.get("StationAllegiance"), e.get("StationAllegiance") or ""))
    elif ev == "Undocked":
        for k in ("st_name", "st_faction", "st_fstate", "st_gov", "st_alleg"):
            sysinfo.pop(k, None)

# ---- destino dentro del sistema (menu 3) ----
settlements = {}     # nombre -> {"lat", "lon", "body"} (puertos y asentamientos planetarios)

def handle_settlements(e):
    ev = e.get("event")
    if ev == "ApproachSettlement" and e.get("Latitude") is not None:
        for k in {e.get("Name_Localised"), e.get("Name")} - {None}:
            settlements[k] = {"lat": e["Latitude"], "lon": e["Longitude"], "body": e.get("BodyName")}
    elif ev in ("FSDJump", "CarrierJump"):
        settlements.clear()

def dest_pkt(st):
    D = st.get("Destination") or {}
    if not D or (info.get("sysaddr") and D.get("System") != info.get("sysaddr")):
        return None
    name = D.get("Name_Localised") or D.get("Name") or ""
    bid = D.get("Body")
    out = {"name": name, "src": ""}
    b = explo["bodies"].get(name)
    if b:
        e = b["raw"]
        out.update(name=b["name"], cls=b["cls"], dist=round(b["dist"]), land=e.get("Landable"),
                   g=round(e["SurfaceGravity"] / 9.80665, 2) if e.get("SurfaceGravity") else None,
                   rings=bool(e.get("Rings")), tf=e.get("TerraformState") == "Terraformable",
                   first=b["first"], mapped=b["mapped"], value=round(b["value"]), src="escaneo")
    else:
        o = None
        if edsm["system"] == explo["system"]:
            o = next((x for x in edsm["orbits"] if x.get("name") == name), None)
        if o:
            out.update(cls=o.get("cls"), dist=o.get("dist"), land=o.get("land"), g=o.get("g"),
                       rings=o.get("rings"), tf=o.get("tf"), value=o.get("value"), src="EDSM")
    sig = planet_sig.get(out["name"])
    if sig:
        out["signals"] = [s[:2] for s in sig]
    stl = settlements.get(name) or settlements.get(D.get("Name"))
    if stl:
        out.update(lat=stl["lat"], lon=stl["lon"], sbody=stl["body"])
    return out

# ---- materiales de ingenieria (menu 12.5) ----
MAT_MAX = {1: 300, 2: 250, 3: 200, 4: 150, 5: 100}
_G = {
    1: "carbon iron lead nickel phosphorus rhenium sulphur salvagedalloys temperedalloys heatconductionwiring "
       "basicconductors mechanicalscrap gridresistors wornshieldemitters compactcomposites crystalshards "
       "chemicalstorageunits scrambledemissiondata disruptedwakeechoes shieldcyclerecordings encryptedfiles "
       "bulkscandata legacyfirmware",
    2: "arsenic chromium germanium manganese vanadium zinc zirconium galvanisingalloys heatresistantceramics "
       "heatdispersionplate conductivecomponents mechanicalequipment hybridcapacitors shieldemitters "
       "filamentcomposites uncutfocuscrystals chemicalprocessors archivedemissiondata fsdtelemetry "
       "shieldsoakanalysis encryptioncodes scanarchives consumerfirmware",
    3: "boron cadmium mercury molybdenum niobium tin tungsten phasealloys precipitatedalloys heatexchangers "
       "conductiveceramics mechanicalcomponents electrochemicalarrays shieldingsensors highdensitycomposites "
       "focuscrystals chemicaldistillery emissiondata wakesolutions shielddensityreports symmetrickeys "
       "scandatabanks industrialfirmware",
    4: "antimony polonium ruthenium selenium technetium tellurium yttrium protolightalloys thermicalloys heatvanes "
       "conductivepolymers configurablecomponents polymercapacitors compoundshielding fedproprietarycomposites "
       "refinedfocuscrystals chemicalmanipulators decodedemissiondata hyperspacetrajectories shieldpatternanalysis "
       "encryptionarchives encodedscandata securityfirmware",
    5: "protoradiolicalloys militarygradealloys protoheatradiators biotechconductors improvisedcomponents "
       "militarysupercapacitors imperialshielding fedcorecomposites exquisitefocuscrystals pharmaceuticalisolators "
       "compactemissionsdata dataminedwake shieldfrequencydata adaptiveencryptors classifiedscandata embeddedfirmware"}
MAT_GRADE = {n: g for g, names in _G.items() for n in names.split()}
mats = {}            # id -> [nombre, cantidad]

def mat_add(name, count, local=None):
    if not name:
        return
    k = name.lower()
    m = mats.setdefault(k, [local or name.capitalize(), 0])
    if local:
        m[0] = local
    old = m[1]
    mx = MAT_MAX.get(MAT_GRADE.get(k))
    m[1] = max(0, min(mx or 10 ** 6, old + count))
    if mx and count > 0 and old < mx <= m[1]:
        note("matfull", f"{m[0]}|{mx}")

def handle_mats(e):
    ev = e.get("event")
    if ev == "Materials":
        mats.clear()
        for cat in ("Raw", "Manufactured", "Encoded"):
            for x in e.get(cat) or []:
                mats[x["Name"].lower()] = [x.get("Name_Localised") or x["Name"].capitalize(), x.get("Count", 0)]
    elif ev == "MaterialCollected":
        mat_add(e.get("Name"), e.get("Count", 1), e.get("Name_Localised"))
    elif ev == "MaterialDiscarded":
        mat_add(e.get("Name"), -e.get("Count", 1))
    elif ev == "MaterialTrade":
        p, r = e.get("Paid") or {}, e.get("Received") or {}
        mat_add(p.get("Material"), -p.get("Quantity", 0), p.get("Material_Localised"))
        mat_add(r.get("Material"), r.get("Quantity", 0), r.get("Material_Localised"))
    elif ev == "EngineerCraft":
        for x in e.get("Ingredients") or []:
            mat_add(x.get("Name"), -x.get("Count", 0))
    elif ev in ("Synthesis", "TechnologyBroker"):
        for x in e.get("Materials") or []:
            mat_add(x.get("Name"), -x.get("Count", 0))
    elif ev == "MissionCompleted":
        for x in e.get("MaterialsReward") or []:
            mat_add(x.get("Name"), x.get("Count", 0), x.get("Name_Localised"))
    elif ev == "EngineerContribution" and e.get("Type") == "Materials":
        mat_add(e.get("Material"), -e.get("Quantity", 0))

def mats_pkt():
    rows = []
    for k, (n, c) in mats.items():
        mx = MAT_MAX.get(MAT_GRADE.get(k))
        if mx:
            rows.append([n[:28], c, mx])
    rows.sort(key=lambda r: (-r[1] / r[2], r[0]))
    return {"n": len(mats), "full": sum(r[1] >= r[2] for r in rows), "list": rows[:60]}

# ---- portanaves (menu 12.6) ----
carrier = {}

def handle_carrier(e):
    ev = e.get("event")
    if ev == "CarrierStats":
        carrier.update(name=e.get("Name"), callsign=e.get("Callsign"), fuel=e.get("FuelLevel"),
                       balance=(e.get("Finance") or {}).get("CarrierBalance"))
    elif ev == "CarrierJumpRequest":
        carrier.update(dest=e.get("SystemName"), dest_body=e.get("Body"),
                       depart=iso2epoch(e.get("DepartureTime")) or (iso2epoch(e.get("timestamp")) or time.time()) + 15 * 60)
    elif ev == "CarrierJumpCancelled":
        carrier.update(dest=None, depart=None)
    elif ev in ("CarrierJump", "CarrierLocation"):
        carrier.update(system=e.get("StarSystem"), dest=None, depart=None)
    elif ev == "CarrierDepositFuel":
        carrier["fuel"] = e.get("Total", carrier.get("fuel"))
    elif ev in ("CarrierFinance", "CarrierBankTransfer"):
        carrier["balance"] = e.get("CarrierBalance", carrier.get("balance"))

def carrier_pkt():
    if carrier.get("dest") and carrier.get("depart") and time.time() > carrier["depart"] + 120:
        carrier.update(system=carrier["dest"], dest=None, depart=None)      # ya ha llegado
    return carrier

# ---- mercado (menu 12.7) ----
market = {}

def load_market():
    try:
        with open(os.path.join(DIR, "Market.json"), encoding="utf-8") as f:
            m = json.load(f)
        with open(os.path.join(DIR, "Cargo.json"), encoding="utf-8") as f:
            inv = {x.get("Name", "").lower(): x.get("Count", 0) for x in json.load(f).get("Inventory") or []
                   if not x.get("Stolen")}
    except (OSError, ValueError):
        return
    rows, best = [], []
    for it in m.get("Items") or []:
        key = (it.get("Name") or "").lower().strip("$").replace("_name;", "")
        name = (it.get("Name_Localised") or key)[:26]
        sell, mean = it.get("SellPrice", 0), it.get("MeanPrice", 0)
        if key in inv and sell:
            rows.append([name, inv[key], sell, mean, it.get("Demand", 0)])
        if sell and mean and it.get("Demand", 0) > 0:
            best.append([name, sell, mean])
    rows.sort(key=lambda r: -r[1] * r[2])
    best.sort(key=lambda r: -(r[1] - r[2]) / r[2])
    market.clear()
    market.update(station=m.get("StationName"), t=iso2epoch(m.get("timestamp")) or time.time(),
                  sell=rows[:20], best=best[:8])

def handle_market(e):
    if e.get("event") == "Market":
        load_market()
        note("market")

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

arrival = {"t": 0, "sys": None}
newsys_done = set()
STAR_ES = {"N": "NEUTRONES", "H": "AGUJERO NEGRO", "SupermassiveBlackHole": "AGUJERO NEGRO", "TTS": "T TAURI", "AeBe": "HERBIG AE/BE"}

def arrival_note(system, nbodies):
    """Ficha de llegada: solo justo despues de un salto (no al arrancar)."""
    if not LIVE[0] or arrival["sys"] != system or time.time() - arrival["t"] > 20:
        return
    arrival["sys"] = None
    c = cur_star[0] or ""
    cls = STAR_ES.get(c) or ("ENANA BLANCA" if c.startswith("D") else f"CLASE {c}" if c else "?")
    note("arrive", f"{system}|{cls}|{int(scoopable(c))}|{'' if nbodies is None else nbodies}")

def handle_explo_alerts(e):
    ev = e.get("event")
    if ev == "FSDJump" and LIVE[0]:
        arrival.update(t=time.time(), sys=e.get("StarSystem"))
    elif ev == "Scan" and "StarType" in e and e.get("DistanceFromArrivalLS", 1) == 0 and e.get("WasDiscovered") is False:
        sysn = explo.get("system")
        if sysn and sysn not in newsys_done:
            newsys_done.add(sysn)
            note("newsys", f"{sysn}|{e.get('StarType', '')}")

# ---- amigos y ala (menu 11, cara AMIGOS) ----
friends = {}         # nombre -> [estado, epoch]
wing = []

def handle_friends(e):
    ev = e.get("event")
    if ev == "Friends" and e.get("Name"):
        n, st = e["Name"], e.get("Status", "")
        prev = (friends.get(n) or [None])[0]
        friends[n] = [st, time.time()]
        if st == "Online" and prev != "Online":
            note("friend", f"{n}|on")
        elif st == "Offline" and prev == "Online":
            note("friend", f"{n}|off")
        elif st == "Requested":
            note("friend", f"{n}|req")
    elif ev == "WingInvite":
        note("wing", f"{e.get('Name', '?')}|invite")
    elif ev == "WingJoin":
        wing[:] = list(e.get("Others") or [])
        note("wing", f"{', '.join(wing) or '-'}|join")
    elif ev == "WingAdd" and e.get("Name"):
        if e["Name"] not in wing:
            wing.append(e["Name"])
        note("wing", f"{e['Name']}|add")
    elif ev == "WingLeave":
        wing.clear()
        note("wing", "-|leave")
    elif ev == "LoadGame":
        wing.clear(); friends.clear()

# ---------- objetivos comunitarios en los que participas (evento CommunityGoal) ----------
mycg = {}            # CGID -> datos

def handle_cg(e):
    if e.get("event") != "CommunityGoal":
        return
    seen = set()
    for g in e.get("CurrentGoals") or []:
        gid = g.get("CGID")
        seen.add(gid)
        tier = g.get("TierReached") or ""
        prev = (mycg.get(gid) or {}).get("tier")
        mycg[gid] = {"title": g.get("Title", "?"), "sys": g.get("SystemName", ""), "market": g.get("MarketName", ""),
                     "expiry": g.get("Expiry", ""), "complete": bool(g.get("IsComplete")),
                     "total": g.get("CurrentTotal"), "mine": g.get("PlayerContribution"),
                     "contrib": g.get("NumContributors"), "tier": tier,
                     "top": (g.get("TopTier") or {}).get("Name", ""), "band": g.get("PlayerPercentileBand"),
                     "toprank": bool(g.get("PlayerInTopRank"))}
        num = lambda t: "".join(c for c in (t or "") if c.isdigit())   # el juego alterna "Tier 5" / "Nivel 5"
        if prev and tier and num(tier) != num(prev) and not g.get("IsComplete"):
            note("cg", f"{mycg[gid]['title']}|{tier}")
    for gid in list(mycg):
        if gid not in seen:
            del mycg[gid]

def mycg_pkt():
    return list(mycg.values())

def friends_pkt():
    now = time.time()
    on = sorted(n for n, (s, t) in friends.items() if s == "Online")
    off = sorted(((n, int((now - t) // 60)) for n, (s, t) in friends.items() if s == "Offline" and now - t < 6 * 3600),
                 key=lambda x: x[1])[:6]
    return {"on": on, "off": [list(x) for x in off], "wing": wing}

# ---- thargoides y guardianes (menu 7.6) ----
TG_STATE = {"Thargoid_Probing": "ALERTA", "Thargoid_Harvest": "INVASIÓN", "Thargoid_Controlled": "CONTROLADO",
            "Thargoid_Stronghold": "BASTIÓN", "Thargoid_Recovery": "RECUPERACIÓN"}
alien = {"tgwar": None, "tgk": 0, "tgb": 0}
alien_seen = set()
alien_log = set()

def handle_alien(e):
    ev = e.get("event") or ""
    if ev == "LoadGame":
        alien.update(tgk=0, tgb=0)
    elif ev in ("FSDJump", "Location", "CarrierJump"):
        w = e.get("ThargoidWar") or {}
        st = TG_STATE.get(w.get("CurrentState"), "")
        alien["tgwar"] = {"state": st, "progress": w.get("WarProgress"), "ports": w.get("RemainingPorts"),
                          "time": w.get("EstimatedRemainingTime"), "won": w.get("SuccessStateReached")} if st else None
        if st and ev == "FSDJump":
            note("tgwar", f"{st}|{w.get('WarProgress') or 0}|{w.get('RemainingPorts') or ''}|{w.get('EstimatedRemainingTime') or ''}")
    elif ev in ("SAASignalsFound", "FSSBodySignals") and e.get("BodyName"):
        for sg in e.get("Signals") or []:
            t = sg.get("Type") or ""
            kind = "THARGOIDES" if "Thargoid" in t else "GUARDIANES" if "Guardian" in t else None
            if kind and (e["BodyName"], kind) not in alien_seen:
                alien_seen.add((e["BodyName"], kind))
                note("alien", f"{kind}|{sg.get('Count', 0)}|{e['BodyName']}")
    elif ev == "FactionKillBond" and "thargoid" in (e.get("VictimFaction") or "").lower():
        alien["tgk"] += 1
        alien["tgb"] += e.get("Reward") or 0
    if ev not in alien_log and any(k in ev for k in ("Thargoid", "Hyperdict", "Guardian")):
        alien_log.add(ev)
        print("EVENTO NUEVO ALIEN:", json.dumps(e)[:400], flush=True)

def alien_pkt():
    tg, gd = [], []
    for k, (n, c) in mats.items():
        if not c:
            continue
        if k.startswith("tg_") or k.startswith("unknown"):
            tg.append([n[:26], c])
        elif k.startswith("guardian_") or k.startswith("ancient"):
            gd.append([n[:26], c, k])
    bp = {k: next((c for n, c, kk in gd if kk == f"guardian_{k}blueprint"), 0) for k in ("module", "weapon", "vessel")}
    return {"tgwar": alien["tgwar"], "tgk": alien["tgk"], "tgb": alien["tgb"],
            "tg": sorted(tg, key=lambda x: -x[1])[:12], "gd": sorted([g[:2] for g in gd], key=lambda x: -x[1])[:12], "bp": bp}

# ---- diario de exploracion, ruta inteligente, datos en riesgo, distancia a casa ----
exd = {}
jump_ts = []
risk_step = [0]
last_station_pos = [None]

def exd_reset():
    exd.clear()
    exd.update(systems=set(), first=0, scanned=0, mapped=0, first_mapped=0, bio=0, signals=0, start=time.time())

exd_reset()

def handle_exdiary(e):
    ev = e.get("event")
    if ev == "LoadGame":
        exd_reset(); risk_step[0] = 0
    elif ev == "FSDJump":
        exd["systems"].add(e.get("StarSystem"))
        t = iso2epoch(e.get("timestamp"))
        if t:
            jump_ts.append(t); del jump_ts[:-12]
    elif ev == "Scan" and ("PlanetClass" in e or "StarType" in e) and e.get("ScanType") != "NavBeaconDetail":
        exd["scanned"] += 1
        if e.get("WasDiscovered") is False:
            exd["first"] += 1
    elif ev == "SAAScanComplete":
        exd["mapped"] += 1
        b = explo["bodies"].get(e.get("BodyName"))
        if b and b["raw"].get("WasMapped") is False:
            exd["first_mapped"] += 1
    elif ev == "ScanOrganic" and e.get("ScanType") == "Analyse":
        exd["bio"] += 1
    elif ev == "Docked":
        last_station_pos[0] = (info.get("starpos"), e.get("StationName"))
    elif ev == "FSSDiscoveryScan" and LIVE[0]:
        known = len([o for o in edsm["orbits"] if o.get("name")]) if edsm["system"] == explo["system"] else None
        note("honk", f"{e.get('BodyCount', 0)}|{e.get('NonBodyCount', 0)}|{'' if known is None else known}")

def routeinfo_pkt():
    ahead = route_ahead()
    if not ahead:
        return None
    gaps = [b - a for a, b in zip(jump_ts, jump_ts[1:]) if 0 < b - a < 600]
    avg = sum(gaps) / len(gaps) if gaps else None
    neu = next((i + 1 for i, (_, c) in enumerate(ahead) if c == "N"), None)
    return {"eta": round(avg * len(ahead)) if avg else None, "neutron": neu,
            "nonscoop": sum(1 for _, c in ahead if not scoopable(c))}

def exdiary_pkt():
    pos = info.get("starpos")
    dsol = math.dist(pos, (0, 0, 0)) if pos else None
    lsp, lsn = last_station_pos[0] or (None, None)
    dst = math.dist(pos, lsp) if pos and lsp else None
    return {"systems": len(exd["systems"]), "first": exd["first"], "scanned": exd["scanned"], "mapped": exd["mapped"],
            "first_mapped": exd["first_mapped"], "bio": exd["bio"], "ly": round(sess.get("ly", 0)) if sess else 0,
            "unsold": round(sum(unsold.values())), "unsold_bio": round(bio.get("unsold_cr", 0)), "dsol": dsol, "dst": dst, "stname": lsn,
            "start": exd["start"], "signals": exd.get("signals", 0)}

def check_risk():
    if not LIVE[0]:
        return
    tot = sum(unsold.values()) + bio.get("unsold_cr", 0)
    step = int(tot // 50_000_000)
    if step > risk_step[0]:
        risk_step[0] = step
        note("risk", f"{round(tot)}")
    elif step < risk_step[0]:
        risk_step[0] = step

def fetch_edsm(system):
    if not system or system == edsm["system"]:
        return
    edsm.update(system=system, orbits=[], status="consultando")
    try:
        url = "https://www.edsm.net/api-system-v1/bodies?systemName=" + urllib.parse.quote(system)
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ElitePanel"}), timeout=15) as r:
            data = json.loads(r.read().decode("utf-8") or "{}")
    except Exception as ex:
        edsm["status"] = "error"; print("EDSM:", ex, flush=True)
        arrival_note(system, None); return
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
        o = {"id": b.get("bodyId"), "t": edsm_epoch(b.get("updateTime")), "src": "edsm", "g": b.get("gravity"),
             "name": b.get("name"), "cls": body_label(fake), "dist": round(b.get("distanceToArrival") or 0),
             "first": False, "mapped": False, "value": round(body_value(fake)), "r": round(radius),
             "land": b.get("isLandable"), "tf": bool(fake.get("TerraformState")),
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
        arrival_note(system, len(out))

def parse_lines(lines):
    for line in lines:
        try:
            e = json.loads(line)
            handle(e)
            handle_extra(e)
            handle_more(e)
            handle_bio(e)
            handle_live(e)
            handle_alerts(e)
            handle_mats(e)
            handle_carrier(e)
            handle_market(e)
            handle_rings(e)
            handle_settlements(e)
            handle_sysinfo(e)
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
        with open(os.path.join(DIR, "Status.json"), encoding="utf-8") as f:
            st = json.load(f)
        cur_st.clear(); cur_st.update(st)     # antes del journal: posicion fresca para ScanOrganic
        tail_journal()
        load_cargo()
        load_backpack()
        check_missions()
        check_ops()
        check_risk()
        now = time.time()
        pkt = {"Flags": st.get("Flags", 0), "Flags2": st.get("Flags2", 0), "Fuel": st.get("Fuel"),
               "Pips": st.get("Pips"), **info, "target": target, "fighter": fighter,
               "route": route_ahead()[:8], "balance": st.get("Balance"),
               "explo": explo_pkt(), "orbits": orbits_pkt(), "body": st.get("BodyName"),
               "gui": st.get("GuiFocus", 0), "notes": notes, "ranks": ranks, "edsm": edsm["status"], "station": station, "mining": mining, "sess": sess,
               "bio": bio_pkt(st), "live": live_pkt(st),
               "mats": mats_pkt(), "carrier": carrier_pkt(), "market": market, "rings": rings_pkt(st), "dest": dest_pkt(st), "sysinfo": sysinfo, "ppme": ppme,
               "pack": {k: v for k, v in pack.items() if k != "raw"}, "srvmats": srvmats_pkt(), "combat": combat_pkt(), "footcz": footcz_pkt(), "ops": ops_pkt(), "exdiary": exdiary_pkt(), "routeinfo": routeinfo_pkt(), "alien": alien_pkt(), "friends": friends_pkt(), "mycg": mycg_pkt(),
               "cargo": cargo[:40],
               "missions": sorted(([n[:60], d, x] for n, d, x in missions.values() if not x or x > now),
                                  key=lambda m: m[2] or 9e12)[:20]}
        send(pkt)
        summary = (explo["system"], len(explo["bodies"]), len(pkt["orbits"]))
        if summary != last_info:          # solo escribe cuando cambia algo
            last_info = summary
            size = len(json.dumps(pkt).encode())
            comp = len(zlib.compress(json.dumps(pkt).encode(), 6))
            print(time.strftime("%H:%M:%S"), f"sistema: {explo['system']}  cuerpos escaneados: {len(explo['bodies'])}"
                  f"  orbitas: {len(pkt['orbits'])}  paquete: {size} bytes (comprimido {comp})" + ("  <-- DEMASIADO GRANDE" if comp >= 60000 else ""),
                  flush=True)
    except (OSError, ValueError):
        pass
    except Exception:
        traceback.print_exc()
    time.sleep(0.25)
