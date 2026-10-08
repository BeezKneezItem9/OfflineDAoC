"""Howth (Silvermine Mts, zone 201) and Connla (Shannon Estuary, zone 202): restore the missing low-level
populations (owner, 2026-10-07: "100% getting their low level mobs added").

Species: every species CapnBry recorded in the zone at level 15 or lower that the server lacks there.
Positions: CapnBry's own sighting spots in that zone (rounded to 150 units, at most 25 per species), snapped
to the navmesh floor. Rows are cloned from the same species elsewhere on the server, or built from its NPC
template. Levels: the sighting's level when recorded, else CapnBry's range.

python gen_hc_spawns.py           dry run -> hc_plan.json
python gen_hc_spawns.py --apply   back up the DB and insert (server stopped)
"""
import csv, json, math, os, random, re, sqlite3, sys, uuid, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:/OfflineDAoC"
DB = os.path.join(ROOT, r"runtime\data\opendaoc.sqlite3.db")
NAV = os.path.join(ROOT, r"runtime\server\navmesh")
sys.path.insert(0, os.path.join(ROOT, r"development-source\server\tools\navmesh_splice"))
from navcomp import NavAreas, _inside  # noqa: E402
random.seed(201202)
ZONES = {201: 'Silvermine Mts.', 202: 'Shannon Estuary'}
MAX_LEVEL, PER_SPECIES = 15, 25

def norm(n): return re.sub(r"\s+", " ", re.sub(r"^(a|an|the) ", "", n.lower().strip()))
capn = json.load(open(os.path.join(HERE, 'capnbry_zones.json'), encoding='utf-8'))
sight = json.load(open(os.path.join(HERE, 'sightings.json'), encoding='utf-8'))
missing = [r for r in csv.DictReader(open(os.path.join(HERE, 'report_missing.csv'), encoding='utf-8'))
           if int(r['zone_id']) in ZONES and r['capnbry_levels'] != 'unknown' and int(r['capnbry_levels'].split('-')[1]) <= MAX_LEVEL]
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
cols = [r[1] for r in c.execute('pragma table_info(Mob)')]
zinfo = {z[0]: z for z in c.execute("select ZoneID,RegionID,Name,OffsetX,OffsetY from Zones")}

def one(v):
    """NpcTemplate Model/Size hold lists ("40;50" or "40-50"); a Mob row holds one number."""
    import re as _re, random as _random
    nums = [int(x) for x in _re.findall(r"\d+", str(v or ""))]
    if not nums: return None
    if "-" in str(v) and len(nums) == 2: return _random.randint(min(nums), max(nums))
    return _random.choice(nums)

def source_row(name):
    r = c.execute("select * from Mob where lower(Name)=? and Realm=0 order by Region=200 desc limit 1", (name,)).fetchone()
    if r: return dict(zip(cols, r)), 'clone'
    t = c.execute("select TemplateId, Name, Model, Size, Flags, Level from NpcTemplate where lower(Name)=? limit 1", (name,)).fetchone()
    if not t: return None, None
    base = dict(zip(cols, c.execute("select * from Mob where Region=200 and Realm=0 and ClassType='DOL.GS.GameNPC' limit 1").fetchone()))
    base.update(Name=t[1], Model=one(t[2]), Size=one(t[3]) or base['Size'], Flags=t[4] or 0, NPCTemplateID=t[0], EquipmentTemplateID=None)
    return base, 'template'

meshes = {}
def floor(zid, x, y, z):
    m = meshes.get(zid) or NavAreas(os.path.join(NAV, f"zone{zid:03d}.nav")); meshes[zid] = m
    best = None
    for r in (0, 60, 120, 200, 300):
        for a in range(0, 360, 45 if r else 360):
            px, py = x + r * math.cos(math.radians(a)), y + r * math.sin(math.radians(a))
            for i in m._grid().get((int(px // m.CELL), int(py // m.CELL)), ()):
                p = m.polys[i]
                if p[4] or not _inside(p[1], px, py): continue
                h = m.height(i, px, py)
                if h is not None and abs(h - z) <= 250 and (best is None or abs(h - z) < abs(best[2] - z)): best = (px, py, h)
        if best: return best
    return None

# Sources disagree: CapnBry has one level 8 sighting, its template is level 21 and Illia's bestiary says 24-25.
CONFLICTING = {'enchanted spraggonoll'}
plan, notes = [], []
for r in missing:
    zid = int(r['zone_id']); name = r['name']
    if name in CONFLICTING:
        notes.append(f"{name} ({ZONES[zid]}): left out, the sources disagree on its level"); continue
    mid = next((str(m['id']) for m in capn[str(zid)]['mobs'] if norm(m['name']) == name), None)
    seen = [s for s in sight.get(mid, {}).get('seen', []) if s[0] == zid] if mid else []
    if not seen: notes.append(f"{name} ({ZONES[zid]}): no sighting coordinates; skipped"); continue
    src, how = source_row(name)
    if not src: notes.append(f"{name} ({ZONES[zid]}): no spawn or template on the server to build from; skipped"); continue
    spots = {}
    for s in seen: spots.setdefault((round(s[1] / 150), round(s[2] / 150)), s)
    chosen = list(spots.values()); random.shuffle(chosen); chosen = chosen[:PER_SPECIES]
    lo, hi = (int(x) for x in r['capnbry_levels'].split('-'))
    z = zinfo[zid]; placed = 0
    for s in chosen:
        gx, gy = s[1] + z[3] * 8192, s[2] + z[4] * 8192
        f = floor(zid, gx, gy, s[3])
        if not f: continue
        row = dict(src)
        lvl = s[4] if 0 < s[4] <= MAX_LEVEL else random.randint(max(1, lo), max(1, hi))
        row.update(Region=z[1], X=int(f[0]), Y=int(f[1]), Z=int(f[2]), Heading=random.randint(0, 4095), Level=lvl, Realm=0,
                   PathID=None, Mob_ID=str(uuid.uuid4()), LastTimeRowUpdated=datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
        plan.append(row); placed += 1
    notes.append(f"{name} ({ZONES[zid]}): {placed} spawns from {len(seen)} sightings, levels {lo}-{hi}, {how}")

json.dump(dict(rows=plan, notes=notes), open(os.path.join(HERE, 'hc_plan.json'), 'w'), indent=1, default=str)
print('spawns', len(plan)); [print(' ', n) for n in notes]
if '--apply' in sys.argv:
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    w = sqlite3.connect(DB); bk = sqlite3.connect(os.path.join(os.path.dirname(DB), f'opendaoc.sqlite3.before-howth-connla-{stamp}.db'))
    w.backup(bk); bk.close()
    before = w.execute("select count(*) from Mob where Region=200").fetchone()[0]
    for row in plan:
        k = list(row.keys()); w.execute(f"insert into Mob ({','.join('['+x+']' for x in k)}) values ({','.join('?' for _ in k)})", [row[x] for x in k])
    after = w.execute("select count(*) from Mob where Region=200").fetchone()[0]
    assert after - before == len(plan), (before, after)
    w.commit(); print('inserted', len(plan), 'backup', stamp)
