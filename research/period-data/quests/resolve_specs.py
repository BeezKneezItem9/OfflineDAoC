"""Generator stage 1: resolve every quest spec against the server.
For each step: the server spelling and region of its NPC/monster, the map-marker point (live spawn position, or the
walkthrough's zone-local loc converted to world coordinates), and whether something must be spawned. Read-only.
Writes resolved.json and prints what is still unresolved.   python resolve_specs.py"""
import json, os, re, sqlite3, collections, glob, difflib, math

HERE = os.path.dirname(os.path.abspath(__file__))
DB = r"C:/OfflineDAoC/scratch/dbcopy.db"  # lock-free copy of the live DB (cp it first)
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
ZONES = list(c.execute("select ZoneID,RegionID,Name,OffsetX,OffsetY,Width,Height from Zones"))
def zk(n): return re.sub(r"[^a-z]", "", (n or "").lower().replace("mountains", "mts").replace("mtns", "mts"))
ALIAS = {"camelot": "cityofcamelot", "castlesauvage": "forestsauvage", "catacombsofcornwall": "catacombsofcardova",
         "caifelle": "isleofglass", "lethantis": "campacorentinforest", "svealandwest": "westsvealand",
         "svealandeast": "eastsvealand", "brileith": "valleyofbrileith", "koalinthtribalcaverns": "koalinthcaverns",
         "plainsofgwyddneu": "gwyddneau"}
ZBY = collections.defaultdict(list)
for z in ZONES: ZBY[zk(z[2])].append(z)
HOME = {"Albion": {1, 10, 51, 20, 22, 23, 24}, "Midgard": {100, 101, 151, 125, 127}, "Hibernia": {200, 201, 181, 220, 224}}
FRONTIER = {"Albion": 1, "Midgard": 100, "Hibernia": 200}

def zone_for(name, realm):
    cands = ZBY.get(ALIAS.get(zk(name), zk(name)), [])
    if not cands: return None
    # Old frontier zones exist twice (classic region and the 163 New Frontiers copy): the period one is the classic.
    cands = sorted(cands, key=lambda z: (z[1] == 163, z[1] not in HOME.get(realm, ())))
    return cands[0]

MOBS = collections.defaultdict(list)
DBNAME = {}  # lower name -> the server's own spelling (targets must match the spawn's name)
for name, region, x, y, z, mid, level in c.execute("select Name,Region,X,Y,Z,Mob_ID,Level from Mob where (PackageID is null or PackageID <> 'ClassicQuest')"):
    MOBS[name.lower().strip()].append((region, x, y, z, mid, level))
    DBNAME.setdefault(name.lower().strip(), name.strip())
ALL = list(MOBS.keys())

# Hand-resolved generic targets ("<guard>", "<faerie court>"): generic_targets.json.
GENERIC = {k: v for k, v in json.load(open(os.path.join(HERE, "generic_targets.json"), encoding="utf-8")).items() if not k.startswith("_")}

# This generator's own planned spawns (apply_world.py dry run -> world_preview.json).
PLANNED = {}
_wp = os.path.join(HERE, "world_preview.json")
if os.path.exists(_wp):
    for m in json.load(open(_wp, encoding="utf-8")).get("mobs", []):
        PLANNED.setdefault(m["Name"].lower(), dict(name=m["Name"], region=m["Region"], x=m["X"], y=m["Y"], z=m["Z"], mob_id=m["Mob_ID"],
                                                    level=m["Level"], zone=None, count=1, same_zone=True, planned=True))

def zone_of(region, x, y):
    for z in ZONES:
        if z[1] == region and z[3] * 8192 <= x < (z[3] + z[5]) * 8192 and z[4] * 8192 <= y < (z[4] + z[6]) * 8192: return z
    return None

NPC_ALIAS = {"ornis": "omis", "keaghan": "keagan", "oriana": "oriara"}

def find_npc(name, zone_name, realm):
    """Server spawn for a spec NPC: exact name, else a close spelling; prefer the named zone, then the realm."""
    key = NPC_ALIAS.get(name.lower().strip(), name.lower().strip())
    hits, spelled = MOBS.get(key, []), DBNAME.get(key, name)
    if not hits and zone_name:
        # The server often adds a title: "Andryn" is "Stable boy Andryn", "Lenna" is "Huntress Lenna" (same zone only).
        zz = zone_for(zone_name, realm)
        titled = [k for k in ALL if k.endswith(' ' + key) and zz and
                  any((zone_of(h[0], h[1], h[2]) or (None,))[0] == zz[0] for h in MOBS[k])]
        if len(titled) == 1: hits, spelled = MOBS[titled[0]], DBNAME[titled[0]]
    if not hits:
        close = difflib.get_close_matches(key, ALL, n=1, cutoff=0.86)
        if close: hits, spelled = MOBS[close[0]], DBNAME[close[0]]
    if not hits: return None
    z = zone_for(zone_name, realm) if zone_name else None
    def score(h):
        hz = zone_of(h[0], h[1], h[2])
        return (0 if z and hz and hz[0] == z[0] else 1, 0 if h[0] in HOME.get(realm, ()) or h[0] == FRONTIER.get(realm) else 1)
    best = min(hits, key=score)
    hz = zone_of(best[0], best[1], best[2])
    return dict(name=spelled, region=best[0], x=best[1], y=best[2], z=best[3], mob_id=best[4], level=best[5],
                zone=hz[2] if hz else None, count=len(hits), same_zone=bool(z and hz and hz[0] == z[0]))

# Generic step targets ("<smith in Haggerfel>", "<Basar tower guard>"): the nearest NPC of that role, of the quest's realm,
# to the named place (an Area or zone), else to the step's loc, else to the giver.
ROLE = [(r'guard|sentinel|watch', "(ClassType like '%Guard%' or Name like '%Guard%' or Name like '%Sentinel%' or Name like '%Watch%')"),
        (r'smith', "(ClassType like '%Smith%' or Name like '%smith%')"),
        (r'stable', "(ClassType like '%Stable%' or Name like '%Stable%')"),
        (r'vault', "(ClassType like '%Vault%' or Name like '%Vault%')"),
        (r'barkeep|bartender|innkeeper|tavern', "(Name like '%Barkeep%' or Name like '%Bartender%' or Name like '%Innkeeper%' or ClassType like '%Bar%')"),
        (r'merchant|vendor|trader', "(ClassType like '%Merchant%')"),
        (r'townsperson|citizen|villager', "(Realm > 0 and Flags & 16 = 16)")]
AREAS = list(c.execute("select Description, Region, X, Y from Area where Description is not null"))
REALM_ID = {"Albion": 1, "Midgard": 2, "Hibernia": 3}

def place_point(text, realm):
    words = re.findall(r"[A-Z][A-Za-z'-]+(?: [A-Z][A-Za-z'-]+)*", text)
    for w in sorted(words, key=len, reverse=True):
        for desc, region, x, y in AREAS:
            if desc and (desc.lower() == w.lower() or len(w) > 4 and w.lower() in desc.lower().split(' ')[0:3] + [desc.lower()]
                         or len(w) > 4 and desc.lower().startswith(w.lower())):
                return dict(region=region, x=x, y=y)
        z = zone_for(w, realm)
        if z: return dict(region=z[1], x=z[3] * 8192 + z[5] * 4096, y=z[4] * 8192 + z[6] * 4096)
    return None

def species_in_zone(name, zone_name, realm):
    z = zone_for(zone_name, realm) if zone_name else None
    if not z: return None
    word = name.lower().strip()
    cands = collections.Counter()
    for key, spawns in MOBS.items():
        # the server's name contains the species ("crab" -> "sand crab"), or drops only an age/size word
        # ("young lunger" -> "lunger"); never a different creature ("undead farmer" is not a "farmer").
        loose = key in word and key != word and word.endswith(key) and             set(word[:-len(key)].split()) <= {"young", "enchanted", "wandering", "large", "small", "greater", "lesser", "old", "elder", "giant"}
        if word in key and key != word or loose:
            for h in spawns:
                hz = zone_of(h[0], h[1], h[2])
                if hz and hz[0] == z[0]: cands[key] += 1
    if not cands: return None
    key = cands.most_common(1)[0][0]
    best = next(h for h in MOBS[key] if (zone_of(h[0], h[1], h[2]) or (None,))[0] == z[0])
    return dict(name=DBNAME[key], region=best[0], x=best[1], y=best[2], z=best[3], mob_id=best[4], level=best[5],
                zone=z[2], count=cands[key], same_zone=True, species_of=name)

def area_point(text):
    """A named place (town, village, camp) from the server's Area table; zone names do not count."""
    words = re.findall(r"[A-Z][A-Za-z'-]+(?: [A-Z][A-Za-z'-]+)*", text)
    for w in sorted(words, key=len, reverse=True):
        for desc, region, x, y in AREAS:
            if desc and desc.lower() == w.lower(): return dict(region=region, x=x, y=y, area=desc)
    return None

def find_generic(tag, step, giver, realm):
    text = tag.strip('<>')
    rule = next((cond for rx, cond in ROLE if re.search(rx, text, re.I)), None)
    if not rule: return None
    anchor = place_point(text, realm) or world_point(step.get('zone'), step.get('loc'), realm) or giver
    if not anchor: return None
    rows = list(c.execute(f"select Name, Region, X, Y, Z, Mob_ID, Level from Mob where (PackageID is null or PackageID <> 'ClassicQuest') and Region=? and {rule} and Realm = ? "
                          "and ClassType not like '%Trainer%' "
                          "and abs(X-?) < 12000 and abs(Y-?) < 12000", (anchor['region'], REALM_ID.get(realm, 0), anchor['x'], anchor['y'])))
    if not rows: return None
    best = min(rows, key=lambda r: (r[2] - anchor['x']) ** 2 + (r[3] - anchor['y']) ** 2)
    hz = zone_of(best[1], best[2], best[3])
    return dict(name=best[0], region=best[1], x=best[2], y=best[3], z=best[4], mob_id=best[5], level=best[6],
                zone=hz[2] if hz else None, count=1, same_zone=True, generic=tag)

def world_point(zone_name, loc, realm):
    z = zone_for(zone_name, realm)
    if not z or not loc: return None
    return dict(region=z[1], x=z[3] * 8192 + int(loc[0]), y=z[4] * 8192 + int(loc[1]), z=None, zone=z[2])

TRAINER = {"Trainer", "Class Trainer"}
# Trainer quests: the giver is the player's own class trainer in the named town (one DataQuest row per class).
ROGUE = {"Albion": "AlbionRogue", "Midgard": "MidgardRogue", "Hibernia": "Stalker"}
CLASS_NAMES = ['Paladin','Armsman','Scout','Minstrel','Theurgist','Cleric','Wizard','Sorcerer','Infiltrator','Friar','Mercenary',
    'Necromancer','Cabalist','Fighter','Elementalist','Acolyte','AlbionRogue','Mage','Reaver','Disciple','Thane','Warrior',
    'Shadowblade','Skald','Hunter','Healer','Spiritmaster','Shaman','Runemaster','Bonedancer','Berserker','Savage','Heretic',
    'Valkyrie','Viking','Mystic','Seer','MidgardRogue','Bainshee','Eldritch','Enchanter','Mentalist','Blademaster','Hero',
    'Champion','Warden','Druid','Bard','Nightshade','Ranger','Magician','Guardian','Naturalist','Stalker','Animist','Valewalker',
    'Forester','Vampiir','Warlock']
TRAINERS = collections.defaultdict(list)
for name, region, x, y, z, mid, level, ctype in c.execute(
        "select Name,Region,X,Y,Z,Mob_ID,Level,ClassType from Mob where ClassType like 'DOL.GS.Trainer.%Trainer'"):
    TRAINERS[ctype.rsplit(".", 1)[1][:-len("Trainer")].lower()].append((name, region, x, y, z, mid, level))

def find_trainer(cls, zone_name, realm):
    cls = ROGUE[realm] if cls == "Rogue" else cls
    hits = TRAINERS.get(cls.lower(), [])
    if not hits: return None
    z = zone_for(zone_name, realm) if zone_name else None
    def score(h):
        hz = zone_of(h[1], h[2], h[3])
        return (0 if z and hz and hz[0] == z[0] else 1, 0 if h[1] in HOME.get(realm, ()) else 1)
    best = min(hits, key=score)
    hz = zone_of(best[1], best[2], best[3])
    return dict(name=best[0], region=best[1], x=best[2], y=best[3], z=best[4], mob_id=best[5], level=best[6],
                zone=hz[2] if hz else None, count=len(hits), same_zone=bool(z and hz and hz[0] == z[0]), cls=cls)
out, unresolved = [], collections.Counter()
for path in sorted(glob.glob(os.path.join(HERE, "specs", "*.jsonl"))):
    if os.path.basename(path).startswith(("_", "b_")): continue
    for line in open(path, encoding="utf-8"):
        spec = json.loads(line)
        realm = spec["realm"]
        g = spec.get("giver", {})
        if spec.get("type") == "kill_task" and not spec.get("steps") and spec.get("item") and spec.get("from"):
            # A kill task is one repeatable turn-in: the item drops from the listed monsters, the giver takes it.
            # Atlas's "XP Item" DataQuests already carry many of them (same giver and item): those stay as they are.
            words = [w for w in re.findall(r"[a-z]{4,}", spec["item"].lower())]
            have = [n for (n,) in c.execute("select Name from DataQuest where ID < 20000 and lower(StartName)=lower(?) and Name like '%XP Item%'",
                                            (g.get("name") or "",))]
            if not any(any(w in n.lower() for w in words) for n in have):
                mobs_text = ", ".join(spec["from"])
                spec["steps"] = [dict(do="trade", npc=g.get("name"), zone=g.get("zone"), trades={spec["item"]: "xp"},
                                      **{"from": spec["from"]}, chance=spec.get("chance") or 15,
                                      text=f"Kill {mobs_text} and bring {g.get('name')} the {spec['item']}." +
                                           (" " + spec["notes"] if spec.get("notes") else ""))]
            else:
                spec["already_in_game"] = True
        giver, class_givers, giver_needs = None, None, None
        if g.get("name") in TRAINER:
            classes = g.get("trainer") or spec.get("classes") or []
            if not classes:
                # "Any trainer": every class whose trainer stands in that town offers it (one row per class).
                z = zone_for(g.get("zone"), realm) if g.get("zone") else None
                classes = sorted({ct for ct, hits in TRAINERS.items() for h in hits
                                  if z and (zone_of(h[1], h[2], h[3]) or (None,))[0] == z[0]})
                # Owner rule: the custom Sluaghbinder gets class quests only from Muirenn's own (scripted) line.
                classes = [next((k for k in CLASS_NAMES if k.lower() == ct), ct) for ct in classes if ct != "sluaghbinder"]
            found = {cls: find_trainer(cls, g.get("zone"), realm) for cls in classes}
            # Later walkthrough class lists add post-1.65 classes (Heretic, Vampiir, Bainshee, Necromancer...) that
            # have no trainer on this Classic + SI server; the quest goes to the classes that do.
            found = {cls: t for cls, t in found.items() if t}
            if found:
                class_givers = found
                giver = next(iter(found.values()))
        else:
            giver = find_npc(g.get("name", ""), g.get("zone"), realm) if g.get("name") else None
            if giver is None and g.get("name") and not g["name"].startswith("<"):
                # Not in the shipped world: the spawn this generator adds (planned), and the planner is told to add it.
                giver = PLANNED.get(g["name"].lower())
                giver_needs = dict(name=g["name"], at=world_point(g.get("zone"), g.get("loc"), realm), zone=g.get("zone"),
                                   loc_note=g.get("loc_note"), spawn=None)
        steps = []
        for i, st in enumerate(spec["steps"], 1):
            r = dict(index=i, do=st["do"], spec=st)
            npc = st.get("npc")
            if npc and (npc in TRAINER or re.search(r'guild trainer|class trainer|\btrainer\b', npc, re.I)) and npc.startswith(("<", "T", "C")):
                # "Return to your trainer": each class row's own trainer (resolved per class below)
                classes_here = list((class_givers or {}).keys()) or (spec.get("classes") or [])
                per = {cls: find_trainer(cls, st.get("zone") or g.get("zone"), realm) for cls in classes_here}
                per = {k: v for k, v in per.items() if v}
                if per:
                    r["class_targets"] = per
                    r["target"] = next(iter(per.values()))
                    r["marker"] = dict(region=r["target"]["region"], x=r["target"]["x"], y=r["target"]["y"], z=r["target"]["z"])
                # no class rows to resolve against: a hand-resolved override (generic_targets.json) may still name one
                if per or not GENERIC.get(f'{spec["src"]}|{npc}'):
                    steps.append(r)
                    continue
            ov = GENERIC.get(f'{spec["src"]}|{npc}') if npc else None
            if ov and ov.get("npc"):
                hit = find_npc(ov["npc"], ov.get("zone") or st.get("zone") or g.get("zone"), realm)
                if hit:
                    r["target"], r["override"] = hit, ov["why"]
                    r["marker"] = dict(region=hit["region"], x=hit["x"], y=hit["y"], z=hit["z"])
                    steps.append(r)
                    continue
            if ov and ov.get("trainer_of"):
                # another class's trainer, nearest each class row's own giver (the trainer that gave the quest)
                wanted = ov["trainer_of"].split("|")
                givers_by_class = class_givers or ({None: giver} if giver else {})
                per = {}
                for cls, gv in givers_by_class.items():
                    cands = []
                    for w in wanted:
                        if cls and w.lower() == str(cls).lower(): continue
                        for h in TRAINERS.get(w.lower(), []):
                            if gv and h[1] == gv["region"]:
                                cands.append(((h[2] - gv["x"]) ** 2 + (h[3] - gv["y"]) ** 2, w, h))
                    cands.sort(key=lambda t: t[0])
                    seen_cls, picks = set(), []
                    for d, w, h in cands:
                        if w in seen_cls: continue
                        seen_cls.add(w); picks.append(h)
                    k = int(ov.get("pick") or 0)
                    if len(picks) > k:
                        h = picks[k]
                        hz = zone_of(h[1], h[2], h[3])
                        per[cls] = dict(name=h[0], region=h[1], x=h[2], y=h[3], z=h[4], mob_id=h[5], level=h[6],
                                        zone=hz[2] if hz else None, count=1, same_zone=True)
                if per:
                    first = next(iter(per.values()))
                    r["target"], r["override"] = first, ov["why"]
                    if None not in per: r["class_targets"] = per
                    r["marker"] = dict(region=first["region"], x=first["x"], y=first["y"], z=first["z"])
                    steps.append(r)
                    continue
            if ov and ov.get("spawn"):
                spn = ov["spawn"]
                wp = world_point(spn["zone"], spn.get("loc"), realm)
                r["needs_spawn"] = dict(name=spn["name"], at=wp, zone=spn["zone"], loc_note=ov["why"],
                                        spawn={k: v for k, v in spn.items() if k in ("level", "like", "look_only")}, role=spn.get("role"))
                r["override"] = ov["why"]
                if wp: r["marker"] = wp
                planned = PLANNED.get(spn["name"].lower())
                if planned:
                    r["target"] = planned
                    r["marker"] = dict(region=planned["region"], x=planned["x"], y=planned["y"], z=planned["z"])
                steps.append(r)
                continue
            if npc and npc.startswith("<"):
                hit = find_generic(npc, st, giver, realm)
                if hit:
                    r["target"] = hit
                    r["marker"] = dict(region=hit["region"], x=hit["x"], y=hit["y"], z=hit["z"])
                    steps.append(r)
                    continue
            if npc and not npc.startswith("<") and npc not in TRAINER:
                hit = find_npc(npc, st.get("zone"), realm)
                if (not hit or not hit["same_zone"]) and npc[:1].islower() and st.get("do") in ("kill", "collect"):
                    # A species the walkthrough names loosely ("crab", "siabra", "curmudgeon"): the server's own monsters
                    # of that species living in the named zone ("sand crab", "siabra raider").
                    hit = species_in_zone(npc, st.get("zone"), realm) or hit
                r["target"] = hit
                if hit: r["marker"] = dict(region=hit["region"], x=hit["x"], y=hit["y"], z=hit["z"])
                else:
                    unresolved[(realm, npc)] += 1
                    wp = world_point(st.get("zone"), st.get("loc"), realm)
                    r["needs_spawn"] = dict(name=npc, at=wp, zone=st.get("zone"), loc_note=st.get("loc_note"), spawn=st.get("spawn"))
                    if wp: r["marker"] = wp
                    planned = PLANNED.get(npc.lower())
                    if planned:  # the spawn this generator adds (apply_world): the step can use it
                        r["target"] = planned
                        r["marker"] = dict(region=planned["region"], x=planned["x"], y=planned["y"], z=planned["z"])
            elif st.get("loc"):
                r["marker"] = world_point(st.get("zone"), st.get("loc"), realm)
            if st.get("do") in ("kill", "collect") and st.get("loc") and r.get("target") and not r["target"]["same_zone"]:
                # The named spawn lives elsewhere; mark the walkthrough's own camp.
                wp = world_point(st.get("zone"), st.get("loc"), realm)
                if wp: r["marker"] = wp
            if not r.get("marker") and st.get("do") in ("search", "use_item", "drop_item", "travel", "event", "interact"):
                # The walkthrough describes the place by what stands there ("near Merle the Old", "beside Olav",
                # "north of Ardee"): the named NPC's spawn, else the named town/area (wider radius), in that zone.
                text = " ".join(str(st.get(k) or "") for k in ("where", "loc_note", "text"))
                for phrase in sorted(set(re.findall(r"[A-Z][a-z'-]+(?: (?:the |of )?[A-Z][a-z'-]+)*", text)), key=len, reverse=True):
                    if phrase in ("The", "Find", "Search", "Swim", "Use", "Investigate", "Clear", "Wear", "Travel", "Step"): continue
                    hit = find_npc(phrase, st.get("zone"), realm)
                    if hit and hit["same_zone"]:
                        r["marker"] = dict(region=hit["region"], x=hit["x"], y=hit["y"], z=hit["z"])
                        r["anchor"] = f"near {hit['name']} (walkthrough: {st.get('where') or st.get('loc_note') or ''})"
                        break
                if not r.get("marker"):
                    pp = area_point(text)
                    if pp and (not st.get("zone") or (zone_for(st["zone"], realm) or (None, None))[1] == pp["region"]):
                        r["marker"] = dict(region=pp["region"], x=pp["x"], y=pp["y"], z=None)
                        r["anchor"] = f"{pp['area']} area centre ({st.get('where') or ''})"
                        r["wide"] = True
            zz = zone_for(st.get("zone"), realm) if st.get("zone") else None
            if zz:  # scripted steps with only a zone: anywhere in that zone (its bounds as a circle)
                r["zone_region"] = zz[1]
                r["zone_area"] = dict(region=zz[1], x=int((zz[3] + zz[5] / 2) * 8192), y=int((zz[4] + zz[6] / 2) * 8192),
                                      radius=int(max(zz[5], zz[6]) * 8192 / 2))
            steps.append(r)
        out.append(dict(src=spec["src"], name=spec["name"], realm=realm, level=spec["level"], giver=giver, giver_needs=giver_needs,
                        class_givers=class_givers, giver_spec=g, steps=steps, spec=spec))
json.dump(out, open(os.path.join(HERE, "resolved.json"), "w", encoding="utf-8"), indent=1, default=str)
n_steps = sum(len(q["steps"]) for q in out)
with_marker = sum(1 for q in out for s in q["steps"] if s.get("marker"))
print(f"quests {len(out)} steps {n_steps} with marker {with_marker} unresolved names {len(unresolved)}")
for (realm, name), n in sorted(unresolved.items()): print(" ", realm, "|", name, n)
