"""Goal 9 (owner 2026-10-07): apply the classic bestiary ledger - add the missing monster species and fill the
under-spawned camps, from the period radar data (CapnBry's full archive: every species' sighting coordinates).

Scope: the classic and Shrouded Isles zones CapnBry recorded (Trials of Atlantis 73-91 and the New Frontiers copies
163-178 left out, as in compare_all.py); monsters only (lowercase names, radar noise such as pets, mounts, guards and
holiday invaders filtered by compare_all.NOISE).

- Missing species: no spawn of that name in the zone; added when at least two sources agree it lived there (CapnBry
  plus Illia's bestiary or Uthgard) and the radar saw it at 3+ distinct spots. Spawns go on those spots (distinct
  150-unit spots, up to 25 per species per zone), snapped to the navmesh floor.
- Under-spawned camps: the species' radar spots in the zone grouped into camps (1,200-unit clusters). A camp whose
  server spawns (within 600 of its spots) are fewer than half its radar spots and at least 2 short gets the
  difference (at most 10 per camp) on its own unused radar spots.
- Rows: cloned from the species elsewhere on the server (same zone first), else built from its NPC template, else
  the look of a same-species monster (listed). Level: the sighting's level, else CapnBry's range for the zone.
- Removals and level fixes: recommend.py's (only species no source lists in the zone / 5+ levels off with
  CapnBry and Illia agreeing).
python goal9_plan.py           dry run -> goal9_plan.json + summary
python goal9_plan.py --apply   back up the live DB and write (server stopped); PackageID 'BestiaryG9'"""
import collections, datetime, json, math, os, random, re, sqlite3, subprocess, sys, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:/OfflineDAoC"
LIVE = os.path.join(ROOT, r"runtime\data\opendaoc.sqlite3.db")
COPY = r"C:/OfflineDAoC/scratch/dbcopy.db"
NAV = os.path.join(ROOT, r"runtime\server\navmesh")
sys.path.insert(0, os.path.join(ROOT, r"development-source\server\tools\navmesh_splice"))
from navcomp import NavAreas, _inside  # noqa: E402
APPLY = '--apply' in sys.argv
PACKAGE = 'BestiaryG9'
random.seed(9)

NOISE = re.compile(r"^(horse|sleigh horse|skiff|boat|.*necroservant|skeletal commander|returned commander|decayed commander|"
                   r"ghastly .* invader|ghostly .* invader|.*invader|guardsman|elite guard|.*guard|.*sentry|.*pet|"
                   r"spirit (warrior|soldier|champion|hunter)|(lesser |greater )?(air|earth|ice|fire) (spirit|beast)|.*elemental ward|underhill .*|.*minion of .*)$")
def norm(n): return re.sub(r"\s+", " ", re.sub(r"^(a|an|the) ", "", (n or '').lower().strip()))
def zkey(n): return re.sub(r"[^a-z]", "", (n or '').lower().replace("mountains", "mts").replace("mtns", "mts"))

capn = json.load(open(os.path.join(HERE, 'capnbry_zones.json'), encoding='utf-8'))
sight = json.load(open(os.path.join(HERE, '..', 'archive', 'capnbry', 'sightings_index.json'), encoding='utf-8'))
uth = {zkey(v['name']): {norm(m['name']) for m in v['mobs']} for v in json.load(open(os.path.join(HERE, 'uthgard_zones.json'), encoding='utf-8')).values()}
illia = {}
for v in json.load(open(os.path.join(HERE, 'illia_zones.json'), encoding='utf-8')).values():
    illia[zkey(v.get('name'))] = {norm(r[0]) for r in v.get('rows', []) if r}
rec = json.load(open(os.path.join(HERE, 'recommendations.json'), encoding='utf-8'))

if APPLY and "coreserver" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout.lower():
    sys.exit("CoreServer is running; stop the server first.")
c = sqlite3.connect(f"file:{COPY}?mode=ro", uri=True)
cols = [r[1] for r in c.execute('pragma table_info(Mob)')]
ZONES = {z[0]: z for z in c.execute("select ZoneID,RegionID,Name,OffsetX,OffsetY,Width,Height from Zones")}
def zone_of(region, x, y):
    for z in ZONES.values():
        if z[1] == region and z[3] * 8192 <= x < (z[3] + z[5]) * 8192 and z[4] * 8192 <= y < (z[4] + z[6]) * 8192: return z[0]
    return None

server = collections.defaultdict(list)  # (zone, name) -> [(x, y) local]
rows_by_name = collections.defaultdict(list)
for r in c.execute(f"select {','.join(cols)} from Mob where Realm = 0"):
    d = dict(zip(cols, r))
    zid = zone_of(d['Region'], d['X'], d['Y'])
    n = norm(d['Name'])
    rows_by_name[n].append((zid, d))
    if zid is not None:
        z = ZONES[zid]
        server[(zid, n)].append((d['X'] - z[3] * 8192, d['Y'] - z[4] * 8192))
templates = {norm(r[1]): r for r in c.execute("select TemplateId, Name, Model, Size, Flags, Level, BodyType, Race, MaxSpeed, AggroLevel, AggroRange, EquipmentTemplateID from NpcTemplate")}
# a plain monster row to build template/look-alike spawns on (ordinary class, respawning)
BASE = dict(zip(cols, c.execute(f"select {','.join(cols)} from Mob where Realm=0 and ClassType='DOL.GS.GameNPC' and RespawnInterval>0 and Region=1 limit 1").fetchone()))

def ordinary(row):
    if row.get('ClassType') != 'DOL.GS.GameNPC' and ('Epic' in row.get('ClassType', '') or '.Keeps.' in row.get('ClassType', '')):
        row['ClassType'] = 'DOL.GS.GameNPC'
    if (row.get('RespawnInterval') or 0) <= 0: row['RespawnInterval'] = 300
    return row

def one(v):
    nums = [int(x) for x in re.findall(r"\d+", str(v or ""))]
    if not nums: return None
    if "-" in str(v) and len(nums) == 2: return random.randint(min(nums), max(nums))
    return random.choice(nums)

def source_row(name, zid):
    cands = rows_by_name.get(name)
    if cands:
        region = ZONES[zid][1]
        plain = lambda d: d['ClassType'] == 'DOL.GS.GameNPC'
        # an ordinary row of the species, nearest first; never an epic-dungeon body (GameEpicNPC: raid-boss health) or a
        # keep guard; a scripted class only where it is native (same zone)
        order = sorted(cands, key=lambda zd: (not plain(zd[1]), zd[0] != zid, zd[1]['Region'] != region))
        z0, best = order[0]
        row = dict(best)
        if not plain(row) and (z0 != zid or 'Epic' in row['ClassType'] or '.Keeps.' in row['ClassType']):
            row['ClassType'] = 'DOL.GS.GameNPC'
        if (row.get('RespawnInterval') or 0) <= 0: row['RespawnInterval'] = 300
        return row, 'clone of the server\'s own ' + name
    t = templates.get(name)
    if t:
        base = dict(BASE)
        base.update(Name=t[1], Model=one(t[2]) or base['Model'], Size=one(t[3]) or base['Size'], Flags=t[4] or 0,
                    NPCTemplateID=t[0], EquipmentTemplateID=t[11], Guild='', BodyType=t[6] or 0, Race=t[7] or 0,
                    Speed=t[8] or base['Speed'], AggroLevel=t[9] if t[9] is not None else base['AggroLevel'],
                    AggroRange=t[10] if t[10] is not None else base['AggroRange'])
        return ordinary(base), 'NPC template ' + t[1]
    words = [w for w in name.split() if len(w) > 2][::-1]
    for w in words:
        hit = [d for n2, lst in rows_by_name.items() if re.search(r'\b' + re.escape(w) + r'\b', n2) for z, d in lst[:1]]
        if hit:
            base = ordinary(dict(hit[0])); base.update(Name=name, NPCTemplateID=-1, Guild='')
            return base, f"look of {hit[0]['Name']} (no model or template for {name} on the server)"
    return None, None

meshes = {}
def floor(zid, x, y, z):
    path = os.path.join(NAV, f"zone{zid:03d}.nav")
    if not os.path.exists(path): return None
    m = meshes.get(zid) or NavAreas(path); meshes[zid] = m
    best = None
    for r in (0, 60, 120, 200, 300):
        for a in range(0, 360, 45 if r else 360):
            px, py = x + r * math.cos(math.radians(a)), y + r * math.sin(math.radians(a))
            for i in m._grid().get((int(px // m.CELL), int(py // m.CELL)), ()):
                p = m.polys[i]
                if p[4] or not _inside(p[1], px, py): continue
                h = m.height(i, px, py)
                if h is not None and abs(h - z) <= 250 and (best is None or abs(h - z) < abs(best[2] - z)) and reachable(m, i):
                    best = (px, py, h)
        if best: return best
    return None

def reachable(m, i):
    """The polygon belongs to one of the zone's main walkable areas (at least a fifth of the largest connected
    area), so bots route to the spawn; small islands and enclosed pockets are refused."""
    if not hasattr(m, '_main'):
        biggest = max(m.area.values()) if m.area else 0
        m._main = {root for root, a in m.area.items() if a >= 0.2 * biggest}
    return m.root[i] in m._main

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

ROAM = 600  # one spawn per 600-unit disk of radar spots: calibrated so typical camps match the server (calib.py: median 0.9)

def spawn_points(pts):
    """Greedy disk cover of radar spots: each disk (the densest first) stands for one spawn point; returns its centre spot."""
    left = list(pts); out = []
    while left:
        best = max(left, key=lambda p: sum(1 for q in left if math.hypot(p[0] - q[0], p[1] - q[1]) <= ROAM))
        out.append(best)
        left = [q for q in left if math.hypot(best[0] - q[0], best[1] - q[1]) > ROAM]
    return out

now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
# Towns: radar also saw monsters that chased players into a town. No spawn within 900 units of a realm guard or of
# a peaceful townsperson (owner 2026-10-07: a lynx cub restored inside Howth's walls).
TOWNSFOLK = collections.defaultdict(list)
for region, x, y in c.execute("select Region, X, Y from Mob where Realm > 0 and (ClassType like '%Guard%' or ClassType like '%Merchant%' "
                              "or ClassType like '%Trainer%' or (Flags & 16) = 16)"):
    TOWNSFOLK[(region, x // 4096, y // 4096)].append((x, y))
def in_town(region, x, y, reach=900):
    for gx in (x // 4096 - 1, x // 4096, x // 4096 + 1):
        for gy in (y // 4096 - 1, y // 4096, y // 4096 + 1):
            if any((px - x) ** 2 + (py - y) ** 2 <= reach * reach for px, py in TOWNSFOLK.get((region, gx, gy), ())): return True
    return False

def make(src, zid, s, lo, hi, why):
    z = ZONES[zid]
    if in_town(z[1], s[1] + z[3] * 8192, s[2] + z[4] * 8192): return None
    f = floor(zid, s[1] + z[3] * 8192, s[2] + z[4] * 8192, s[3])
    if not f: return None
    row = dict(src)
    lvl = s[4] if s[4] > 0 else random.randint(max(1, lo), max(1, hi)) if 0 < lo <= hi else int(src.get('Level') or 1)
    row.update(Region=z[1], X=int(f[0]), Y=int(f[1]), Z=int(f[2]), Heading=random.randint(0, 4095), Level=lvl, Realm=0,
               PathID=None, PackageID=PACKAGE, LastTimeRowUpdated=now,
               # stable ids: the bot camp list (classic165_period_restored_spawn_ids.txt) names these rows
               Mob_ID=str(uuid.uuid5(uuid.NAMESPACE_URL, f"bestiary-g9:{zid}:{src['Name'].lower()}:{s[1]}:{s[2]}")))
    row['_why'] = why
    return row

plan, notes, stats = [], [], collections.Counter()
# Radar logs record a monster wherever it was seen, many times, and heavily logged zones (starter zones) collect far
# more sightings per real spawn. So the server itself is the yardstick: in each zone, sightings near a species' server
# spawns divided by those spawns gives how many sightings one spawn produces there. Radar camps of that species with
# no server spawn within 1,500 units get round(camp sightings / that ratio) spawns (1-6 per camp) on the camp's
# busiest spots. Missing species use the zone's overall ratio (up to 25 per species).
CAMP_GAP, PER_CAMP, PER_SPECIES = 1500, 6, 25
RAID_REGIONS = {60, 160, 191, 249}  # Caer Sidi, Tuscaran Glacier, Galladoria, Darkness Falls: owner 2026-10-07, never changed
for zid_s, zinfo in sorted(capn.items(), key=lambda kv: int(kv[0])):
    zid = int(zid_s)
    if zid not in ZONES or not zinfo['mobs'] or 73 <= zid <= 91 or 163 <= zid <= 178: continue
    # Owner 2026-10-07: the epic dungeons and Darkness Falls are not changed at all.
    if ZONES[zid][1] in RAID_REGIONS: stats['zones excluded (epic dungeons, Darkness Falls)'] += 1; continue
    zname = ZONES[zid][2]
    by_name, levels = collections.defaultdict(list), {}
    for m in zinfo['mobs']:
        if not m['name'][:1].islower() or NOISE.search(m['name']): continue
        n = norm(m['name'])
        by_name[n] += [s for s in sight.get(str(m['id']), {}).get('seen', []) if s[0] == zid]
        lo, hi = levels.get(n, (m['min'] or 99, m['max'] or 0))
        levels[n] = (min(lo, m['min'] or lo), max(hi, m['max'] or hi))
    ratios, zone_cov, zone_have = {}, 0, 0
    for n, seen in by_name.items():
        have = server.get((zid, n), [])
        if not have or not seen: continue
        near = sum(1 for s in seen if min(math.hypot(p[0] - s[1], p[1] - s[2]) for p in have) <= CAMP_GAP)
        if near: ratios[n] = near / len(have); zone_cov += near; zone_have += len(have)
    zone_ratio = zone_cov / zone_have if zone_have else None
    for n, seen in by_name.items():
        if not seen: continue
        lo, hi = levels[n]
        have = server.get((zid, n), [])
        weight = collections.Counter((round(s[1] / 150) * 150, round(s[2] / 150) * 150) for s in seen)
        spots = {}
        for s in seen: spots.setdefault((round(s[1] / 150) * 150, round(s[2] / 150) * 150), s)
        if not have:
            agree = 1 + (n in illia.get(zkey(zname), set())) + (n in uth.get(zkey(zname), set()))
            if agree < 2 or len(spots) < 3 or not zone_ratio: stats['missing, not enough agreement'] += 1; continue
            ratio = zone_ratio
        else:
            ratio = ratios.get(n)
            if not ratio: continue
        src, how = source_row(n, zid)
        if not src:
            notes.append(f"{zname}: {n} - nothing on the server to build it from; skipped"); continue
        added_here = []
        for camp in clusters(list(spots.keys())):
            if have and min(math.hypot(p[0] - q[0], p[1] - q[1]) for q in camp for p in have) <= CAMP_GAP: continue
            camp_sightings = sum(weight[q] for q in camp)
            want = max(1, min(PER_CAMP, round(camp_sightings / ratio)))
            if camp_sightings < 3: continue
            busiest = sorted(camp, key=lambda q: -weight[q])
            pts = []
            for q in busiest:
                if all(math.hypot(q[0] - r[0], q[1] - r[1]) >= 250 for r in pts): pts.append(q)
                if len(pts) >= want: break
            why = (f"missing species ({'3' if n in uth.get(zkey(zname), set()) and n in illia.get(zkey(zname), set()) else '2'} sources)" if not have
                   else f"uncovered radar camp: {camp_sightings} sightings, ~{ratio:.1f} per spawn in this zone")
            added_here += [r for r in (make(src, zid, spots[q], lo, hi, why) for q in pts) if r]
        if not have: added_here = added_here[:PER_SPECIES]
        if added_here:
            plan += added_here
            stats['species added' if not have else 'species with new camps'] += 1
            stats['spawns for missing species' if not have else 'spawns for uncovered camps'] += len(added_here)
            if not have: notes.append(f"{zname}: + {n} x{len(added_here)} ({how})")
removals = rec.get('removals', [])
level_fixes = rec.get('level_fixes', [])
json.dump(dict(rows=plan, notes=notes, removals=removals, level_fixes=level_fixes), open(os.path.join(HERE, 'goal9_plan.json'), 'w', encoding='utf-8'), indent=1, default=str)
print(dict(stats), 'total new spawns', len(plan), 'removals', len(removals), 'level fixes', len(level_fixes))
print('by zone', collections.Counter(ZONES[zone_of(r['Region'], r['X'], r['Y'])][2] for r in plan).most_common(15))

if APPLY:
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    w = sqlite3.connect(LIVE)
    bk = sqlite3.connect(os.path.join(os.path.dirname(LIVE), f'opendaoc.sqlite3.before-bestiary-g9-{stamp}.db')); w.backup(bk); bk.close()
    lcols = [r[1] for r in w.execute('pragma table_info(Mob)')]
    before = w.execute("select count(*) from Mob").fetchone()[0]
    old = w.execute("select count(*) from Mob where PackageID=?", (PACKAGE,)).fetchone()[0]
    try:
        w.execute("begin")
        w.execute("delete from Mob where PackageID=?", (PACKAGE,))
        for row in plan:
            k = [x for x in row if x in lcols]
            w.execute(f"insert into Mob ({','.join('['+x+']' for x in k)}) values ({','.join('?' for _ in k)})", [row[x] for x in k])
        removed = 0
        # Howth/Connla restoration rows that stood inside a town (lynx cub in Howth, owner 2026-10-07)
        for mid in json.load(open(os.path.join(HERE, 'hc_in_town.json'))):
            removed += w.execute("delete from Mob where Mob_ID=?", (mid,)).rowcount
        for r in removals:
            z = next((zz for zz in ZONES.values() if zz[2] == r['zone']), None)
            if not z: continue
            removed += w.execute("delete from Mob where Realm=0 and lower(Name)=? and Region=? and X>=? and X<? and Y>=? and Y<? and (PackageID is null or PackageID<>?)",
                                 (r['name'], z[1], z[3] * 8192, (z[3] + z[5]) * 8192, z[4] * 8192, (z[4] + z[6]) * 8192, PACKAGE)).rowcount
        fixed = 0
        for f in level_fixes:
            z = next((zz for zz in ZONES.values() if zz[2] == f['zone']), None)
            if not z: continue
            lo, hi = (int(x) for x in f['period'].split('-'))
            for (mid,) in w.execute("select Mob_ID from Mob where Realm=0 and lower(Name)=? and Region=? and X>=? and X<? and Y>=? and Y<?",
                                    (f['name'], z[1], z[3] * 8192, (z[3] + z[5]) * 8192, z[4] * 8192, (z[4] + z[6]) * 8192)).fetchall():
                fixed += w.execute("update Mob set Level=? where Mob_ID=?", (random.randint(lo, hi), mid)).rowcount
        after = w.execute("select count(*) from Mob").fetchone()[0]
        assert after == before - old + len(plan) - removed, (before, old, len(plan), removed, after)
        w.commit()
    except Exception:
        w.rollback(); raise
    print(f"Mob {before} -> {after} (+{len(plan)}, replaced {old}, removed {removed}); levels fixed {fixed}; backup {stamp}")
