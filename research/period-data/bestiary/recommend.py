"""High-confidence recommendations from the comparison: additions (multiple sources agree), camps to fill,
removals (no source lists the species) and level fixes. Writes recommendations.json for the report and the
spawn generator. Additions carry camp positions from CapnBry's own sighting coordinates."""
import csv, json, os, re, math, sqlite3, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:/OfflineDAoC"
DB = os.path.join(ROOT, r"runtime\data\opendaoc.sqlite3.db")
def rows(n): return list(csv.DictReader(open(os.path.join(HERE, n), encoding='utf-8')))
def norm(n): return re.sub(r"\s+", " ", re.sub(r"^(a|an|the) ", "", n.lower().strip()))

missing, levels, extra, small, zones = (rows(f) for f in
    ('report_missing.csv', 'report_levels.csv', 'report_server_only.csv', 'report_small_camps.csv', 'report_zones.csv'))
capn = json.load(open(os.path.join(HERE, 'capnbry_zones.json'), encoding='utf-8'))
sight = json.load(open(os.path.join(HERE, 'sightings.json'), encoding='utf-8')) if os.path.exists(os.path.join(HERE, 'sightings.json')) else {}
df_names = {norm(m['name']) for m in capn.get('249', {}).get('mobs', [])}
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
zinfo = {z[0]: z for z in c.execute("select ZoneID,RegionID,Name,OffsetX,OffsetY from Zones")}
server_names = {norm(r[0]) for r in c.execute("select distinct Name from Mob where Realm=0")}
template_names = {norm(r[0]) for r in c.execute("select distinct Name from NpcTemplate")}

def capn_id(zid, name):
    for m in capn.get(zid, {}).get('mobs', []):
        if norm(m['name']) == name: return str(m['id'])
    return None

def clusters(points, radius=1200):
    left = list(points); out = []
    while left:
        group = [left.pop()]; changed = True
        while changed:
            changed = False
            for p in left[:]:
                if any(math.hypot(p[0] - q[0], p[1] - q[1]) <= radius for q in group):
                    group.append(p); left.remove(p); changed = True
        out.append(group)
    return out

additions = []
for r in missing:
    if r['zone_id'] in ('0', '100', '200') and r['name'] in df_names: continue
    if r['capnbry_levels'] == 'unknown': continue
    agree = 1 + (r['illia'] not in ('no', 'no data')) + (r['uthgard'] == 'yes')
    mid = capn_id(r['zone_id'], r['name'])
    seen = [s for s in sight.get(mid, {}).get('seen', []) if str(s[0]) == r['zone_id']] if mid else []
    if agree < 2 or len(seen) < 3: continue
    # distinct spawn spots: sightings rounded to 150 units, then camps from 1,200-unit clusters
    spots = {(round(s[1] / 150) * 150, round(s[2] / 150) * 150): s for s in seen}
    camps = []
    for g in clusters(list(spots.keys())):
        zs = [spots[p][3] for p in g]; lv = [spots[p][4] for p in g if spots[p][4] > 0]
        camps.append(dict(x=int(sum(p[0] for p in g) / len(g)), y=int(sum(p[1] for p in g) / len(g)), z=int(sorted(zs)[len(zs) // 2]),
                          spots=len(g), levels=[min(lv), max(lv)] if lv else None,
                          points=[[p[0], p[1], spots[p][3]] for p in g][:8]))
    camps.sort(key=lambda k: -k['spots'])
    additions.append(dict(zone=r['zone'], zone_id=int(r['zone_id']), region=zinfo[int(r['zone_id'])][1], name=r['name'],
                          capnbry_levels=r['capnbry_levels'], illia=r['illia'], uthgard=r['uthgard'], agree=agree,
                          sightings=len(seen), camps=camps[:6],
                          source=('spawn elsewhere on server' if r['name'] in server_names else
                                  'NPC template' if r['name'] in template_names else 'no model on server')))

fills = []
for r in small:
    if not r['verdict'].startswith('likely short'): continue
    seen = int(r['capnbry_spawns_seen_nearby']); have = int(r['spawns_in_camp'])
    fills.append(dict(zone=r['zone'], zone_id=int(r['zone_id']), name=r['name'], have=have, period=seen,
                      add=min(seen, 6) - have, local_x=int(r['local_x']), local_y=int(r['local_y'])))
# Only the obvious ones: one or two spawns where CapnBry saw five or more of the species around the spot.
fills = [f for f in fills if f['add'] > 0 and f['period'] >= 5]

illia = json.load(open(os.path.join(HERE, 'illia_zones.json'), encoding='utf-8'))
def zkey(n): return re.sub(r"[^a-z]", "", n.lower().replace("mountains", "mts").replace("mtns", "mts"))
illia_lv = collections.defaultdict(dict)
for v in illia.values():
    for row in v.get('rows', []):
        m = re.match(r'(\d+)\s*-\s*(\d+)', row[1]) if len(row) > 1 else None
        if m: illia_lv[zkey(v['name'])][norm(row[0])] = (int(m.group(1)), int(m.group(2)))
zone_cov = {int(z['zone_id']): z for z in zones}
capn_anywhere = {norm(m['name']) for v in capn.values() for m in v.get('mobs', [])}
MONSTER_CLASSES = {'GameNPC', 'NightSpawn', 'DOL.GS.GameNPC'}
removals = []
for r in extra:
    z = zone_cov.get(int(r['zone_id']))
    if not z or not z['uthgard_species'] or int(z['capnbry_species']) < 20: continue
    if r['uthgard'] != 'no' or int(r['server_spawns']) < 3: continue
    if r['zone'] == 'Darkness Falls' or r['name'] in ('new mob',) or r['name'].startswith('total:'): continue
    if not set(r['classtypes'].split(';')) <= MONSTER_CLASSES: continue      # keep guards, dummies, scripted NPCs
    if r['name'] in illia_lv.get(zkey(r['zone']), {}): continue              # Illia's bestiary lists it there
    removals.append(dict(zone=r['zone'], zone_id=int(r['zone_id']), name=r['name'], server_levels=r['server_levels'],
                         spawns=int(r['server_spawns']), classtypes=r['classtypes'],
                         elsewhere='yes' if r['name'] in capn_anywhere else 'no'))
level_fixes = []
for r in levels:
    if int(r['difference']) < 5: continue
    cl = [int(x) for x in r['capnbry_levels'].split('-')]
    il = illia_lv.get(zkey(r['zone']), {}).get(r['name'])
    if not il or abs(il[0] - cl[0]) > 2 or abs(il[1] - cl[1]) > 2: continue
    level_fixes.append(dict(zone=r['zone'], name=r['name'], server=r['server_levels'], period=r['capnbry_levels'],
                            illia=f"{il[0]}-{il[1]}", spawns=int(r['server_spawns'])))

json.dump(dict(additions=additions, fills=fills, removals=removals, level_fixes=level_fixes),
          open(os.path.join(HERE, 'recommendations.json'), 'w', encoding='utf-8'), indent=1)
print('additions', len(additions), 'with camps', sum(1 for a in additions if a['camps']), 'fills', len(fills),
      'spawns to add in fills', sum(f['add'] for f in fills), 'removals', len(removals), 'level fixes', len(level_fixes))
print(collections.Counter(a['source'] for a in additions))
