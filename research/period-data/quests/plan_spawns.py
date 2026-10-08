"""Generator stage 2: a spawn plan for every quest NPC/monster the server lacks (from resolved.json).
Position: CapnBry's classic-zone sighting (New Frontiers copies, region 163, are post-1.65 and skipped), else the
walkthrough's zone loc; snapped to the navmesh. Look and stats: the NPC template of that name when the database
has one, else a donor named in the spec. Event monsters (appear on a quest step) go to the ClassicQuests config,
the rest become DB spawns. Read-only; writes spawn_plan.json.   python plan_spawns.py"""
import json, os, re, sys, math, sqlite3, statistics, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:/OfflineDAoC"
DB = r"C:/OfflineDAoC/scratch/dbcopy.db"  # lock-free copy of the live DB (cp it first)
NAV = os.path.join(ROOT, r"runtime\server\navmesh")
sys.path.insert(0, os.path.join(ROOT, r"development-source\server\tools\navmesh_splice"))
from navcomp import NavAreas, _inside  # noqa: E402

c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
ZONES = {z[0]: z for z in c.execute("select ZoneID,RegionID,Name,OffsetX,OffsetY,Width,Height from Zones")}
resolved = json.load(open(os.path.join(HERE, "resolved.json"), encoding="utf-8"))
sight = json.load(open(os.path.join(HERE, "npc_sightings.json"), encoding="utf-8"))
sight_by = {v["name"].lower(): v["seen"] for v in sight.values()}
# The full CapnBry radar archive (every mob id; ../archive/capnbry/index_sightings.py): names the quest list did not fetch.
_full = os.path.join(HERE, "..", "archive", "capnbry", "sightings_index.json")
if os.path.exists(_full):
    for v in json.load(open(_full, encoding="utf-8")).values():
        if v["seen"]: sight_by.setdefault(v["name"].lower(), []).extend(s for s in v["seen"] if s not in sight_by.get(v["name"].lower(), []))

EVENT_WORDS = ("spawn_on_death_of", "spawn_on_kills_of", "spawn_on_talk")
def is_event(step):
    st = step["spec"]
    if st.get("do") == "event": return True
    if any(k in st for k in EVENT_WORDS): return True
    sp = st.get("spawn")
    if isinstance(sp, dict) and (sp.get("on_death_of") or sp.get("on_talk")): return True
    note = (st.get("loc_note") or "") + " " + (st.get("text") or "")
    return bool(re.search(r"\b(appears?|pops?|summon|spawns? when|will pop)\b", note, re.I))

meshes = {}
def reachable(m, i):
    """The polygon belongs to one of the zone's main walkable areas (a fifth of the largest connected area or more),
    so bots route to the spawn (owner 2026-10-07: new spawns must be reachable bot grind goals)."""
    if not hasattr(m, "_main"):
        biggest = max(m.area.values()) if m.area else 0
        m._main = {root for root, a in m.area.items() if a >= 0.2 * biggest}
    return m.root[i] in m._main

def floor(zid, x, y, z_hint):
    path = os.path.join(NAV, f"zone{zid:03d}.nav")
    if not os.path.exists(path): return None
    m = meshes.get(zid) or NavAreas(path); meshes[zid] = m
    best = None
    for r in (0, 80, 160, 300, 500):
        for a in range(0, 360, 45 if r else 360):
            px, py = x + r * math.cos(math.radians(a)), y + r * math.sin(math.radians(a))
            for i in m._grid().get((int(px // m.CELL), int(py // m.CELL)), ()):
                p = m.polys[i]
                if p[4] or not _inside(p[1], px, py) or not reachable(m, i): continue
                h = m.height(i, px, py)
                if h is None: continue
                d = abs(h - z_hint) if z_hint is not None else 0
                if z_hint is not None and d > 400: continue
                if best is None or d < best[3]: best = (px, py, h, d)
        if best: return best[:3]
    return None

def classic_sighting(name):
    seen = [s for s in sight_by.get(name.lower(), []) if s[0] in ZONES and ZONES[s[0]][1] != 163]
    if not seen: return None
    zid = collections.Counter(s[0] for s in seen).most_common(1)[0][0]
    pts = [s for s in seen if s[0] == zid]
    x, y, zz = (int(statistics.median(p[i] for p in pts)) for i in (1, 2, 3))
    lv = sorted({p[4] for p in pts if p[4] > 0})
    z = ZONES[zid]
    return dict(zone_id=zid, region=z[1], x=z[3] * 8192 + x, y=z[4] * 8192 + y, z=zz, levels=lv, source="CapnBry")

# Uthgard 2.0 map dots (../archive/uthgard/uthgard_locations.py): a later freeshard, used only when the period sources
# (CapnBry radar, walkthrough locs) have nothing.
_uth_path = os.path.join(HERE, "..", "archive", "uthgard", "locations.json")
UTH = {k.lower(): v for k, v in (json.load(open(_uth_path, encoding="utf-8")).items() if os.path.exists(_uth_path) else [])}
def _zkey(n): return re.sub(r"[^a-z]", "", (n or "").lower().replace("mountains", "mtns").replace("mts", "mtns"))
def uthgard_sighting(name, zone_hint=None):
    best = None
    for e in UTH.get(name.lower(), []):
        if not e["locs"]: continue
        zs = [z for z in ZONES.values() if _zkey(z[2]) == _zkey(e["zone"]) and z[1] != 163]
        if not zs: continue
        score = (0 if zone_hint and _zkey(zone_hint) == _zkey(e["zone"]) else 1, -len(e["locs"]))
        if best is None or score < best[0]: best = (score, zs[0], e)
    if not best: return None
    _, z, e = best
    x = int(statistics.median(p[0] for p in e["locs"])); y = int(statistics.median(p[1] for p in e["locs"]))
    # the dot nearest the median (a real seen spot, not the average of two camps)
    x, y = min(e["locs"], key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)
    return dict(zone_id=z[0], region=z[1], x=z[3] * 8192 + x, y=z[4] * 8192 + y, z=None, levels=[], source="Uthgard map")

def template(name):
    t = c.execute("select TemplateId,Name,Model,Size,Level,ClassType from NpcTemplate where lower(Name)=lower(?) limit 1", (name,)).fetchone()
    return dict(id=t[0], model=t[2], size=t[3], level=t[4], classtype=t[5]) if t else None

plan = {}
for q in resolved:
    for s in q["steps"]:
        ns = s.get("needs_spawn")
        if not ns: continue
        name = ns["name"]
        entry = plan.setdefault(name.lower(), dict(name=name, realm=q["realm"], quests=[], event=False, place=None,
                                                   template=template(name), spec_spawn=None, zone=ns.get("zone"),
                                                   loc_note=ns.get("loc_note"), role=ns.get("role") or s["do"]))
        entry["quests"].append(f'{q["name"]} step {s["index"]}')
        entry["qlevel"] = max(entry.get("qlevel") or 0, int(q.get("level") or 0))
        entry["event"] = entry["event"] or is_event(s)
        if isinstance(ns.get("spawn"), dict): entry["spec_spawn"] = ns["spawn"]
        # look_only: borrow the NPC template's looks but not the template itself (it would replace the peace flag and
        # aggression on load: the world's "Lucan" ghost template is aggressive)
        if isinstance(ns.get("spawn"), dict) and ns["spawn"].get("look_only"): entry["template"] = None
        if entry["place"] is None:
            place = classic_sighting(name)
            if not place and ns.get("at"):
                at = ns["at"]
                zid = next((zid for zid, z in ZONES.items() if z[1] == at["region"] and z[2] == at["zone"]), None)
                place = dict(zone_id=zid, region=at["region"], x=at["x"], y=at["y"], z=None, levels=[], source="walkthrough")
            if place and place.get("zone_id") is not None:
                f = floor(place["zone_id"], place["x"], place["y"], place["z"])
                if f: place.update(x=int(f[0]), y=int(f[1]), z=int(f[2]), on_mesh=True)
                else: place["on_mesh"] = False
            entry["place"] = place

# Quest givers missing from the shipped world (goal 10): a peaceful NPC of the quest's realm.
for q in resolved:
    ns = q.get("giver_needs")
    if not ns or (q.get("spec") or {}).get("type") == "otd": continue
    name = ns["name"]
    entry = plan.setdefault(name.lower(), dict(name=name, realm=q["realm"], quests=[], event=False, place=None,
                                               template=template(name), spec_spawn=None, zone=ns.get("zone"),
                                               loc_note=ns.get("loc_note"), role="talk"))
    entry["role"] = "talk"  # gives a quest: always peaceful, whatever else the quest does with it
    entry["quests"].append(f'{q["name"]} (gives the quest)')
    if entry["place"] is None:
        place = classic_sighting(name)
        if not place and ns.get("at"):
            at = ns["at"]
            zid = next((zid for zid, z in ZONES.items() if z[1] == at["region"] and z[2] == at["zone"]), None)
            place = dict(zone_id=zid, region=at["region"], x=at["x"], y=at["y"], z=None, levels=[], source="walkthrough")
        if place and place.get("zone_id") is not None:
            f = floor(place["zone_id"], place["x"], place["y"], place["z"])
            if f: place.update(x=int(f[0]), y=int(f[1]), z=int(f[2]), on_mesh=True)
            else: place["on_mesh"] = False
        entry["place"] = place

# One-time drops (goal 10): the named monster must be in the world. Only those with no spawn of that name.
spawned = {r[0].lower() for r in c.execute("select distinct Name from Mob where (PackageID is null or PackageID <> 'ClassicQuest')")}
for q in resolved:
    sp = q.get("spec") or q
    if sp.get("type") != "otd" or not sp.get("npc") or sp["npc"].lower() in spawned: continue
    name = sp["npc"]
    entry = plan.setdefault(name.lower(), dict(name=name, realm=sp["realm"], quests=[], event=False, place=None,
                                               template=template(name), spec_spawn=None, zone=sp.get("zone"),
                                               loc_note=sp.get("notes"), role="otd", night_only=bool(sp.get("night_only"))))
    entry["quests"].append(f'{sp["name"]} (one-time drop)')
    if entry["place"] is None:
        place = classic_sighting(name)
        if not place and sp.get("zone") and sp.get("loc"):
            zs = [z for z in ZONES.values() if z[2] == sp["zone"] and z[1] != 163]
            if zs:
                z = zs[0]
                place = dict(zone_id=z[0], region=z[1], x=z[3] * 8192 + sp["loc"][0], y=z[4] * 8192 + sp["loc"][1], z=None,
                             levels=[], source="walkthrough loc")
        if place and place.get("zone_id") is not None:
            f = floor(place["zone_id"], place["x"], place["y"], place["z"])
            if f: place.update(x=int(f[0]), y=int(f[1]), z=int(f[2]), on_mesh=True)
            else: place["on_mesh"] = False
        entry["place"] = place

# Kill-task drop sources (goal 10): the monsters a trade step's item drops from must be in the world.
for q in resolved:
    for s in q["steps"]:
        st = s["spec"]
        if st.get("do") != "trade": continue
        for name in st.get("from") or []:
            if name.lower() in spawned: continue
            entry = plan.setdefault(name.lower(), dict(name=name, realm=q["realm"], quests=[], event=False, place=None,
                                                       template=template(name), spec_spawn=None,
                                                       zone=st.get("zone") or (q["spec"].get("zone")), loc_note=q["spec"].get("notes"),
                                                       role="drop source"))
            entry["quests"].append(f'{q["name"]} (drops {", ".join(st.get("trades") or {})})')
            if entry["place"] is None:
                place = classic_sighting(name)
                if place and place.get("zone_id") is not None:
                    f = floor(place["zone_id"], place["x"], place["y"], place["z"])
                    if f: place.update(x=int(f[0]), y=int(f[1]), z=int(f[2]), on_mesh=True)
                    else: place["on_mesh"] = False
                entry["place"] = place

# Last resort for a place: the Uthgard map dots.
for e in plan.values():
    if (e.get("place") or {}).get("on_mesh"): continue
    place = uthgard_sighting(e["name"], e.get("zone"))
    if place:
        f = floor(place["zone_id"], place["x"], place["y"], place["z"])
        if f:
            place.update(x=int(f[0]), y=int(f[1]), z=int(f[2]), on_mesh=True)
            e["place"] = place

anchors = json.load(open(os.path.join(HERE, "anchors.json"), encoding="utf-8"))
def zone_rows(zone_name):
    return [z for z in ZONES.values() if z[2] == zone_name and z[1] != 163]
def in_zone(z, x, y): return z[3] * 8192 <= x < (z[3] + z[5]) * 8192 and z[4] * 8192 <= y < (z[4] + z[6]) * 8192
for e in plan.values():
    a = anchors.get(e["name"])
    if not a or "TODO" in a or (e["place"] and e["place"].get("on_mesh")): 
        if a and "TODO" in a: e["todo"] = a["TODO"]
        continue
    zs = zone_rows(a.get("zone"))
    if not zs: continue
    z = zs[0]
    if a.get("loc"):
        lx, ly = a["loc"]
        x, y = z[3] * 8192 + lx, z[4] * 8192 + ly
        place = dict(zone_id=z[0], region=z[1], x=x, y=y, z=None, levels=[], source="walkthrough loc (anchors)")
        f = floor(z[0], x, y, None)
        if f: place.update(x=int(f[0]), y=int(f[1]), z=int(f[2]), on_mesh=True)
        else: place["on_mesh"] = False
        e["place"] = place
        if a.get("event"): e["event"] = True
        continue
    key = a.get("near") or a.get("camp")
    rows = [r for r in c.execute("select X,Y,Z from Mob where Region=? and lower(Name)=lower(?)", (z[1], key)) if in_zone(z, r[0], r[1])]
    if not rows:
        rows = list(c.execute("select X,Y,Z from Mob where Region=? and lower(Name)=lower(?)", (z[1], key)))
        if rows: e["anchor_note"] = f"{key} is not in {a['zone']} on the server; used its spawns elsewhere in the region"
    if not rows: e["todo"] = f"anchor {key} not found in {a['zone']}"; continue
    if a.get("near"): x, y, zz = rows[0]
    else: x, y, zz = (int(statistics.median(r[i] for r in rows)) for i in range(3))
    x += a.get("offset", [0, 0])[0]; y += a.get("offset", [0, 0])[1]
    real = next((zz2 for zz2 in ZONES.values() if zz2[1] == z[1] and zz2[1] != 163 and in_zone(zz2, x, y)), z)
    place = dict(zone_id=real[0], region=z[1], x=x, y=y, z=zz, levels=list(a.get("levels") or []), source=f"anchor {key}")
    if a.get("like"):  # the creature it looks like (same species), at the anchor's levels
        lv = sorted(a.get("levels") or [])
        e["spec_spawn"] = dict(e.get("spec_spawn") or {}, like=a["like"], **({"level": lv[len(lv) // 2]} if lv else {}))
    # an offset onto a hillside leaves the anchor's height behind: then the ground at that point, whatever its height
    f = floor(real[0], x, y, zz) or floor(real[0], x, y, None)
    if f: place.update(x=int(f[0]), y=int(f[1]), z=int(f[2]), on_mesh=True)
    else: place["on_mesh"] = False
    e["place"] = place
    if a.get("event"): e["event"] = True
# Kill-task monsters live in camps, not as one spawn (owner 2026-10-07): every distinct period sighting in the camp's
# zone (300+ units apart, up to 8), else a ring around the placed spawn so the camp holds CAMP_MIN monsters.
CAMP_MIN, CAMP_MAX = 6, 8
def camp_points(e):
    p = e["place"]
    pts = []
    zid = p.get("zone_id")
    for s in sight_by.get(e["name"].lower(), []):
        if s[0] != zid or zid not in ZONES: continue
        z = ZONES[zid]
        x, y = z[3] * 8192 + s[1], z[4] * 8192 + s[2]
        if any((x - a) ** 2 + (y - b) ** 2 < 300 ** 2 for a, b, _ in pts + [(p["x"], p["y"], 0)]): continue
        f = floor(zid, x, y, s[3])
        if f: pts.append((int(f[0]), int(f[1]), int(f[2])))
        if len(pts) >= CAMP_MAX - 1: break
    ring = 0
    while len(pts) < CAMP_MIN - 1 and ring < 24:
        r, a = 350 + 150 * (ring // 6), math.radians(60 * ring + 25 * (ring // 6))
        ring += 1
        x, y = p["x"] + r * math.cos(a), p["y"] + r * math.sin(a)
        f = floor(zid, x, y, p["z"])
        if f and not any((f[0] - a2) ** 2 + (f[1] - b2) ** 2 < 200 ** 2 for a2, b2, _ in pts):
            pts.append((int(f[0]), int(f[1]), int(f[2])))
    return [dict(x=x, y=y, z=z) for x, y, z in pts]
for e in plan.values():
    # a standing NPC, not a temporary quest spawn (anchors "world": talked to, or hunted, on a quest step)
    if (anchors.get(e["name"]) or {}).get("world"): e["event"] = False
for e in plan.values():
    # kill-task monsters and the species a quest collects from live in camps (owner 2026-10-07)
    species = e.get("role") == "drop source" or (e.get("role") == "collect" and e["name"][:1].islower())
    if species and not e.get("event") and (e.get("place") or {}).get("on_mesh"):
        e["camp"] = camp_points(e)
json.dump(sorted(plan.values(), key=lambda e: (e["realm"], e["name"])), open(os.path.join(HERE, "spawn_plan.json"), "w", encoding="utf-8"), indent=1)
by = collections.Counter(("event" if e["event"] else "permanent", "placed" if e["place"] and e["place"].get("on_mesh") else
                          "placed-off-mesh" if e["place"] else "NO PLACE", "template" if e["template"] else "no template") for e in plan.values())
for k, v in sorted(by.items()): print(v, k)
for e in sorted(plan.values(), key=lambda e: (e["realm"], e["name"])):
    if not e["place"] or not e["place"].get("on_mesh"): print("  needs a place:", e["realm"], "|", e["name"], "|", e.get("todo") or e["loc_note"], "|", (e["place"] or {}).get("source"))
