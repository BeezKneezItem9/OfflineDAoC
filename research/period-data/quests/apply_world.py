"""Goal 10: put the spawn plan and the one-time drops into the game database (server must be stopped for --apply).
  python apply_world.py            dry run against the DB copy: prints what would be written, writes world_preview.json
  python apply_world.py --apply    backs up the live DB, replaces every PackageID='ClassicQuest' Mob row and the
                                   one-time-drop rows this script owns (classic-otd.json), asserts the row counts.
Spawns: permanent spawn_plan entries placed on the navmesh, built from the NPC template of that name or the donor template
named in the spec ("like"). Talk/deliver/whisper NPCs belong to the quest realm; monsters are neutral (realm 0).
Event monsters (appear on a quest step) are left to the ClassicQuests config. Nothing is invented: an entry with no
template and no donor is listed and skipped."""
import json, os, sys, uuid, shutil, sqlite3, subprocess, datetime, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:/OfflineDAoC\runtime"
LIVE = os.path.join(ROOT, "data", "opendaoc.sqlite3.db")
COPY = r"C:/OfflineDAoC/scratch/dbcopy.db"  # lock-free copy of the live DB
APPLY = "--apply" in sys.argv
TO_COPY = "--copy" in sys.argv  # write into the scratch DB copy (so the resolver sees the new spawns); never the live DB
REALM = {"Albion": 1, "Midgard": 2, "Hibernia": 3}
FRIENDLY_ROLES = {"talk", "deliver", "whisper", "trade"}

if APPLY:
    if "coreserver" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout.lower():
        sys.exit("CoreServer is running; stop the server first.")
    db = LIVE
else:
    db = COPY
con = sqlite3.connect(db)
cur = con.cursor()

plan = json.load(open(os.path.join(HERE, "spawn_plan.json"), encoding="utf-8"))
specs = [json.loads(l) for f in ("albion", "midgard", "hibernia") for l in open(os.path.join(HERE, "specs", f + ".jsonl"), encoding="utf-8")]
tcols = [r[1] for r in cur.execute("pragma table_info(NpcTemplate)")]
def template_row(tid=None, name=None):
    q = "select * from NpcTemplate where TemplateId=?" if tid is not None else "select * from NpcTemplate where lower(Name)=lower(?) limit 1"
    r = cur.execute(q, (tid if tid is not None else name,)).fetchone()
    return dict(zip(tcols, r)) if r else None
def first(v, default=0):
    # "47;52;49", "49-50" (a template's level range: the western basilisk spawned at level 1), "12,14"
    m = _re.match(r"\s*(\d+)", str(v if v is not None else ""))
    return int(m.group(1)) if m else default

now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

# Appearance donors (owner rule: invent only with zero data). No period source records a creature's model, so a spawn
# with no NPC template of its own name looks like (in order): a creature of the same species (its name's words, then
# the species the walkthrough names in its note), a peaceful townsperson of its realm nearest the spot (quest NPCs),
# or the nearest local creature of a similar level (named monsters). Level: the period sightings, else the spec, else
# the donor. Every donor is listed in world_preview.json (donor, why) for the ledger.
import re as _re
MCOLS = [r[1] for r in cur.execute("pragma table_info(Mob)")]
SPECIES_STOP = {"wandering", "young", "old", "enchanted", "noble", "lord", "lady", "the", "of", "corrupt", "dark", "elder",
                "great", "lesser", "greater", "ancient", "angry", "enraged", "lost", "spirit", "shade", "ghost", "captain"}
SPECIES_WORDS = ("banshee", "cyclops", "demon", "scrag", "stepper", "imp", "merush", "treant", "giant", "troll", "dwarf",
                 "kobold", "wolf", "bear", "spider", "goblin", "orc", "ogre", "siabra", "fomorian", "sylvan", "drakoran",
                 "werewolf", "skeleton", "zombie", "ghoul", "wraith", "spectre", "specter", "golem", "worm", "drake",
                 "dragon", "basilisk", "griffin", "boar", "cat", "badger", "fairy", "faerie", "sprite", "pixie", "wisp",
                 "satyr", "centaur", "minotaur", "harpy", "bwca", "roman", "centurion", "legionnaire", "cultist", "druid",
                 "witch", "hag", "lich", "vampire", "undead", "phantom", "wickerman", "dervish", "tree", "crab", "eel",
                 "shark", "lunger", "anglator", "curmudgeon", "koalinth", "morvalt", "svartalf", "tomte", "nisse",
                 "huldu", "dverge", "jotun", "frost giant", "wyvern", "grimwood", "fellwood", "afanc", "lurikeen")
def mob_template(row):
    d = dict(zip(MCOLS, row))
    return dict(TemplateId=-1, Name=d["Name"], GuildName=d.get("Guild") or "", Model=d["Model"], Size=d["Size"], Level=d["Level"],
                MaxSpeed=d.get("Speed") or 191, Strength=d.get("Strength"), Constitution=d.get("Constitution"),
                Dexterity=d.get("Dexterity"), Quickness=d.get("Quickness"), Intelligence=d.get("Intelligence"),
                Piety=d.get("Piety"), Empathy=d.get("Empathy"), Charisma=d.get("Charisma"),
                EquipmentTemplateID=d.get("EquipmentTemplateID"), ItemsListTemplateID=None, Race=d.get("Race"),
                Flags=(d.get("Flags") or 0) & ~16, AggroLevel=d.get("AggroLevel"), AggroRange=d.get("AggroRange"),
                MeleeDamageType=d.get("MeleeDamageType"), FactionID=d.get("FactionID"), BodyType=d.get("BodyType"),
                Gender=d.get("Gender"), VisibleWeaponSlots=d.get("VisibleWeaponSlots"))
def species_donor(words, place, friendly):
    for w in words:
        rows = cur.execute(f"select {','.join(MCOLS)} from Mob where lower(Name) like ? and Model > 0 and Realm {'>' if friendly else '='} 0 "
                           "and (PackageID is null or PackageID <> 'ClassicQuest')", (f"%{w}%",)).fetchall()
        if rows:
            reg = place.get("region")
            best = min(rows, key=lambda r: (dict(zip(MCOLS, r))["Region"] != reg,
                                            (dict(zip(MCOLS, r))["X"] - place.get("x", 0)) ** 2 + (dict(zip(MCOLS, r))["Y"] - place.get("y", 0)) ** 2))
            return mob_template(best), f"species '{w}' -> {dict(zip(MCOLS, best))['Name']}"
    return None, None
NOT_DONOR = _re.compile(r"horse|pack|ambient|stable|cart|boat|guard|sentinel|keep|captain|lord|merchant|trainer|teleport|hastener|banker|vault", _re.I)
def local_donor(place, friendly, level, humanoid=False):
    rows = []
    for reach in (15000, 40000, 400000):
        q = (f"select {','.join(MCOLS)} from Mob where (Region=? or ? = -1) and Model > 0 and (abs(X-?) < {reach} and abs(Y-?) < {reach} or ? = -1) and "
             + ("Realm > 0 and ClassType='DOL.GS.GameNPC' and EquipmentTemplateID is not null and EquipmentTemplateID <> ''" if friendly else "Realm = 0 and Level > 0") +
             # dressed (an equipment template) = a person, not a beast
             (" and EquipmentTemplateID is not null and EquipmentTemplateID <> ''" if humanoid and not friendly else "") +
             " and (PackageID is null or PackageID <> 'ClassicQuest')")
        rows = [r for r in cur.execute(q, (place["region"], place["region"], place["x"], place["y"], place["region"])).fetchall()
                if not NOT_DONOR.search(dict(zip(MCOLS, r))["Name"])]
        if rows: break
    if not rows and humanoid: return local_donor(place, friendly, level)
    if not rows and friendly and place.get("region") != -1:  # nobody of the kind in that region (Darkness Falls): anywhere
        return local_donor(dict(place, region=-1), friendly, level)
    if not rows: return None, None
    best = min(rows, key=lambda r: (abs((dict(zip(MCOLS, r))["Level"] or 0) - level) // 5 if not friendly else 0,
                                    (dict(zip(MCOLS, r))["X"] - place["x"]) ** 2 + (dict(zip(MCOLS, r))["Y"] - place["y"]) ** 2))
    t = mob_template(best)
    if friendly: t = dict(t, Level=min(int(t["Level"] or 20), 50))
    return t, ("nearest townsperson " if friendly else "nearest local humanoid " if humanoid else "nearest local creature ") + dict(zip(MCOLS, best))["Name"]
def find_donor(e, place):
    friendly = e.get("role") in FRIENDLY_ROLES
    name_words = [w for w in _re.findall(r"[a-z'-]+", e["name"].lower()) if w not in SPECIES_STOP and len(w) > 2]
    lowercase = e["name"][:1].islower()
    note = " ".join(str(x or "") for x in (e.get("loc_note"), (e.get("spec_spawn") or {}).get("like") if isinstance(e.get("spec_spawn"), dict) else ""))
    note_words = [w for w in SPECIES_WORDS if _re.search(r"\b" + w + r"s?\b", note.lower())]
    if lowercase and friendly:  # a person described, not named ("missing man"): only real species words (2026-10-08:
        # "man" matched a monster's name and the missing man in Howth looked like a small earth golem)
        tries = [w for w in SPECIES_WORDS if _re.search(r"\b" + w + r"s?\b", e["name"].lower())] + note_words
        if not tries:
            levels = place.get("levels") or []
            return local_donor(place, friendly, int(sorted(levels)[len(levels) // 2]) if levels else 20, humanoid=True)
    elif lowercase:   # a species name ("tidal mongrel"): the whole name, then its words from the head noun back
        tries = ([" ".join(name_words)] if len(name_words) > 1 else []) + name_words[::-1] + note_words
    else:           # a personal name: only words that are species ("Noble Werewolf Alina"), then the note's species
        tries = [w for w in SPECIES_WORDS if _re.search(r"\b" + w + r"\b", e["name"].lower())] + note_words
    if not friendly or lowercase:
        t, why = species_donor([w for w in tries if w], place, friendly=False)
        if t: return t, why
    levels = place.get("levels") or []
    level = int(sorted(levels)[len(levels) // 2]) if levels else int((e.get("spec_spawn") or {}).get("level") or 0) if isinstance(e.get("spec_spawn"), dict) and str((e.get("spec_spawn") or {}).get("level") or "").isdigit() else 0
    return local_donor(place, friendly, level or 20, humanoid=not lowercase)
mob_rows, skipped = [], []
for e in plan:
    place = e.get("place") or {}
    if e.get("event") or not place.get("on_mesh"): continue
    t = template_row(tid=e["template"]["id"]) if e.get("template") else None
    spawn = e.get("spec_spawn") or {}
    if t is None and spawn.get("like"): t = template_row(name=spawn["like"])
    donor_note = None
    if t is None:
        t, donor_note = find_donor(e, place)
        levels = place.get("levels") or []
        if t is not None and levels: t = dict(t, Level=sorted(levels)[len(levels) // 2])  # the period sightings' level
        elif t is not None and e.get("qlevel") and e.get("role") not in FRIENDLY_ROLES: t = dict(t, Level=e["qlevel"])  # else the quest's level
    if t is None: skipped.append((e["realm"], e["name"], e.get("role"), "no template or donor")); continue
    friendly = e.get("role") in FRIENDLY_ROLES
    named = e["name"][:1].isupper()
    level = first(spawn.get("level") or t["Level"], 1)
    mob_rows.append(dict(
        ClassType="DOL.GS.GameNPC", Name=e["name"], Guild=t.get("GuildName") or "", X=place["x"], Y=place["y"], Z=place["z"],
        Speed=first(t.get("MaxSpeed"), 191), Heading=random.Random(e["name"]).randrange(4096), Region=place["region"],
        Model=first(t["Model"], 1), Size=first(t["Size"], 50), Strength=first(t.get("Strength")), Constitution=first(t.get("Constitution")),
        Dexterity=first(t.get("Dexterity")), Quickness=first(t.get("Quickness")), Intelligence=first(t.get("Intelligence")),
        Piety=first(t.get("Piety")), Empathy=first(t.get("Empathy")), Charisma=first(t.get("Charisma")), Level=level,
        Realm=REALM[e["realm"]] if friendly else 0, EquipmentTemplateID=t.get("EquipmentTemplateID"),
        ItemsListTemplateID=t.get("ItemsListTemplateID"), NPCTemplateID=t["TemplateId"] if e.get("template") else -1,  # -1: no template (stats from the row)
        Race=first(t.get("Race")), Flags=first(t.get("Flags")) | (16 if friendly else 0),  # 16 = PEACE
        AggroLevel=0 if friendly else first(t.get("AggroLevel")), AggroRange=0 if friendly else first(t.get("AggroRange"), 400),
        MeleeDamageType=first(t.get("MeleeDamageType")), RespawnInterval=(600 if named else 120) if not friendly else 30,
        FactionID=first(t.get("FactionID")), BodyType=first(t.get("BodyType")), HouseNumber=0, RoamingRange=0 if friendly or named else 300,
        IsCloakHoodUp=0, Gender=first(t.get("Gender")), PackageID="ClassicQuest", VisibleWeaponSlots=first(t.get("VisibleWeaponSlots")),
        LastTimeRowUpdated=now, Mob_ID=str(uuid.uuid5(uuid.NAMESPACE_URL, "classicquest:" + e["realm"] + ":" + e["name"])),
        _role=e.get("role"), _quests=e.get("quests"), _donor=donor_note))
    # A kill-task monster's camp (plan_spawns camp_points): the same monster at each further point, roaming.
    for k, pt in enumerate(e.get("camp") or [], 1):
        mob_rows.append(dict(mob_rows[-1], X=pt["x"], Y=pt["y"], Z=pt["z"], RoamingRange=0 if friendly else 300,
                             Heading=random.Random(f'{e["name"]}:{k}').randrange(4096),
                             Mob_ID=str(uuid.uuid5(uuid.NAMESPACE_URL, f'classicquest:{e["realm"]}:{e["name"]}:camp{k}'))))

# One-time drops whose item exists but have no LootOTD row.
# rows this script owns (classic-otd.json) are replaced on apply, so they do not count as "already has a drop"
_owned_otd = set(json.load(open(os.path.join(ROOT, "server", "classic-otd.json")))) if os.path.exists(os.path.join(ROOT, "server", "classic-otd.json")) else set()
otd_mobs = {r[0].lower() for r in cur.execute("select MobName, LootOTD_ID from LootOTD") if r[1] not in _owned_otd}
items = {}
for iid, name in cur.execute("select Id_nb, Name from ItemTemplate"): items.setdefault(name.lower(), iid)
otd_rows = []
for s in specs:
    if s.get("type") != "otd" or not s.get("npc"): continue
    wanted = [s["item"]] if s.get("item") else list((s.get("item_by_class") or {}).values())
    for item in wanted:
        iid = items.get(item.lower())
        if not iid or s["npc"].lower() in otd_mobs and not s.get("item_by_class"): continue
        if any(cur.execute("select LootOTD_ID from LootOTD where lower(MobName)=lower(?) and ItemTemplateID=?", (s["npc"], iid)).fetchall()
               and r[0] not in _owned_otd for r in cur.execute("select LootOTD_ID from LootOTD where lower(MobName)=lower(?) and ItemTemplateID=?", (s["npc"], iid)).fetchall()): continue
        otd_rows.append(dict(MobName=s["npc"], ItemTemplateID=iid, MinLevel=int(s.get("level") or 1),
                             LastTimeRowUpdated=now, LootOTD_ID=str(uuid.uuid5(uuid.NAMESPACE_URL, "classicotd:" + s["npc"] + ":" + iid))))

print(f"spawns {len(mob_rows)} (friendly {sum(1 for r in mob_rows if r['Realm'])}, monsters {sum(1 for r in mob_rows if not r['Realm'])}), "
      f"skipped {len(skipped)}; one-time-drop rows {len(otd_rows)}")
for s in skipped: print("  skip", s)
json.dump(dict(mobs=mob_rows, otd=otd_rows, skipped=skipped), open(os.path.join(HERE, "world_preview.json"), "w", encoding="utf-8"), indent=1)
if not APPLY and not TO_COPY:
    sys.exit(0)

if APPLY:
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(ROOT, "data", f"opendaoc.sqlite3.before-classic-world-{stamp}.db")
    con.close(); shutil.copy2(LIVE, backup); print("backup", backup)
    con = sqlite3.connect(LIVE); cur = con.cursor()
else:
    con.close(); con = sqlite3.connect(COPY); cur = con.cursor()
mcols = [r[1] for r in cur.execute("pragma table_info(Mob)")]
owned_path = os.path.join(ROOT, "server", "classic-otd.json")
owned = json.load(open(owned_path)) if os.path.exists(owned_path) else []
before_mob = cur.execute("select count(*) from Mob").fetchone()[0]
old_mob = cur.execute("select count(*) from Mob where PackageID='ClassicQuest'").fetchone()[0]
before_otd = cur.execute("select count(*) from LootOTD").fetchone()[0]
try:
    cur.execute("begin")
    cur.execute("delete from Mob where PackageID='ClassicQuest'")
    removed_otd = sum(cur.execute("delete from LootOTD where LootOTD_ID=?", (i,)).rowcount for i in owned)
    for r in mob_rows:
        v = {k: r[k] for k in mcols if k in r}
        cur.execute(f"insert into Mob ({','.join(v)}) values ({','.join('?' * len(v))})", list(v.values()))
    for r in otd_rows:
        cur.execute(f"insert into LootOTD ({','.join(r)}) values ({','.join('?' * len(r))})", list(r.values()))
    after_mob = cur.execute("select count(*) from Mob").fetchone()[0]
    after_otd = cur.execute("select count(*) from LootOTD").fetchone()[0]
    assert after_mob == before_mob - old_mob + len(mob_rows), (before_mob, old_mob, after_mob)
    assert after_otd == before_otd - removed_otd + len(otd_rows), (before_otd, removed_otd, after_otd)
    con.commit()
except Exception:
    con.rollback(); raise
if APPLY: json.dump([r["LootOTD_ID"] for r in otd_rows], open(owned_path, "w"))
print(f"Mob {before_mob} -> {after_mob} (+{len(mob_rows)}, replaced {old_mob}); LootOTD {before_otd} -> {after_otd} (+{len(otd_rows)}, replaced {removed_otd})")
