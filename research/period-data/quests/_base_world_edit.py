"""One-off edit: the pipeline reads the shipped world (Mob rows that are not PackageID 'ClassicQuest') and treats this
generator's own spawns (world_preview.json) as planned, so re-running against a database that already holds the
classic quest spawns gives the same plan (apply_world replaces every ClassicQuest row on apply)."""
BASE = "(PackageID is null or PackageID <> 'ClassicQuest')"


def edit(p, pairs):
    s = open(p, encoding='utf-8').read()
    for old, new in pairs:
        assert s.count(old) == 1, (p, old[:70])
        s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s)


edit('resolve_specs.py', [
    ('''for name, region, x, y, z, mid, level in c.execute("select Name,Region,X,Y,Z,Mob_ID,Level from Mob"):''',
     f'''for name, region, x, y, z, mid, level in c.execute("select Name,Region,X,Y,Z,Mob_ID,Level from Mob where {BASE}"):'''),
    ('''    rows = list(c.execute(f"select Name, Region, X, Y, Z, Mob_ID, Level from Mob where Region=? and {rule} and Realm = ? "''',
     f'''    rows = list(c.execute(f"select Name, Region, X, Y, Z, Mob_ID, Level from Mob where {BASE} and Region=? and {{rule}} and Realm = ? "'''),
    ('''                else:
                    unresolved[(realm, npc)] += 1
                    wp = world_point(st.get("zone"), st.get("loc"), realm)
                    r["needs_spawn"] = dict(name=npc, at=wp, zone=st.get("zone"), loc_note=st.get("loc_note"), spawn=st.get("spawn"))
                    if wp: r["marker"] = wp''',
     '''                else:
                    unresolved[(realm, npc)] += 1
                    wp = world_point(st.get("zone"), st.get("loc"), realm)
                    r["needs_spawn"] = dict(name=npc, at=wp, zone=st.get("zone"), loc_note=st.get("loc_note"), spawn=st.get("spawn"))
                    if wp: r["marker"] = wp
                    planned = PLANNED.get(npc.lower())
                    if planned:  # the spawn this generator adds (apply_world): the step can use it
                        r["target"] = planned
                        r["marker"] = dict(region=planned["region"], x=planned["x"], y=planned["y"], z=planned["z"])'''),
    ('''def zone_of(region, x, y):''', '''# This generator's own planned spawns (apply_world.py dry run -> world_preview.json).
PLANNED = {}
_wp = os.path.join(HERE, "world_preview.json")
if os.path.exists(_wp):
    for m in json.load(open(_wp, encoding="utf-8")).get("mobs", []):
        PLANNED.setdefault(m["Name"].lower(), dict(name=m["Name"], region=m["Region"], x=m["X"], y=m["Y"], z=m["Z"], mob_id=m["Mob_ID"],
                                                    level=m["Level"], zone=None, count=1, same_zone=True, planned=True))

def zone_of(region, x, y):'''),
])

edit('plan_spawns.py', [
    ('''spawned = {r[0].lower() for r in c.execute("select distinct Name from Mob")}''',
     f'''spawned = {{r[0].lower() for r in c.execute("select distinct Name from Mob where {BASE}")}}'''),
])

edit('validate_quests.py', [
    ('''for name, region in c.execute("select Name, Region from Mob"): mobs[name.lower()].add(region)''',
     f'''for name, region in c.execute("select Name, Region from Mob where {BASE}"): mobs[name.lower()].add(region)'''),
])
print('ok')
