"""Goal 11: compare server monster spawns (Mob table) with the CapnBry bestiary catalog, per zone."""
import json, sqlite3, re, collections, math, os, csv

ROOT = r"C:/OfflineDAoC"
DB = os.path.join(ROOT, r"runtime\data\opendaoc.sqlite3.db")
CAPN = os.path.join(ROOT, r"development-source\server\GameServer\bots\autonomous\data\capnbry_classic_si_goals.json")
OUT = os.path.dirname(os.path.abspath(__file__))
PEACE = 0x10

def norm(name):
    n = name.lower().strip()
    n = re.sub(r"^(a|an|the) ", "", n)
    return re.sub(r"\s+", " ", n)

def parse_levels(text, fallback):
    if not text: return [fallback]
    out = []
    for part in re.split(r"[;,]", str(text)):
        part = part.strip()
        if '-' in part:
            a, b = part.split('-', 1)
            try: out += list(range(int(a), int(b) + 1))
            except ValueError: pass
        elif part.isdigit(): out.append(int(part))
    return out or [fallback]

c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
zones = c.execute("select ZoneID,RegionID,Name,OffsetX,OffsetY,Width,Height from Zones").fetchall()
zone_by_region = collections.defaultdict(list)
for z in zones: zone_by_region[z[1]].append(z)
zone_name = {z[0]: z[2] for z in zones}

def zone_of(region, x, y):
    for z in zone_by_region.get(region, []):
        if z[3] * 8192 <= x < (z[3] + z[5]) * 8192 and z[4] * 8192 <= y < (z[4] + z[6]) * 8192:
            return z
    return None

templates = {r[0]: r[1] for r in c.execute("select TemplateId, Level from NpcTemplate")}
server = collections.defaultdict(lambda: collections.defaultdict(list))  # zone -> name -> [(x,y,levels,classtype)]
for name, region, x, y, level, tid, flags, ctype in c.execute(
        "select Name, Region, X, Y, Level, NPCTemplateID, Flags, ClassType from Mob where Realm=0"):
    if (flags or 0) & PEACE or not name: continue
    z = zone_of(region, x, y)
    if not z: continue
    lx, ly = x - z[3] * 8192, y - z[4] * 8192
    levels = parse_levels(templates.get(tid), level) if tid and tid > 0 else [level]
    server[z[0]][norm(name)].append((lx, ly, levels, ctype))

cap = json.load(open(CAPN, encoding='utf-8'))
capz = collections.defaultdict(lambda: collections.defaultdict(list))
for g in cap['goals']:
    capz[g['zone_id']][g['normalized_name']].append(g)

def clusters(points, radius=1500):
    """Greedy spawn clusters (camps) by distance."""
    left = list(points); out = []
    while left:
        seed = left.pop(); group = [seed]; changed = True
        while changed:
            changed = False
            for p in left[:]:
                if any(math.hypot(p[0] - q[0], p[1] - q[1]) <= radius for q in group):
                    group.append(p); left.remove(p); changed = True
        out.append(group)
    return out

rows_missing, rows_level, rows_extra, rows_small = [], [], [], []
summary = []
for zid in sorted(cap['covered_zone_ids']):
    zname = zone_name.get(zid, str(zid))
    s, k = server.get(zid, {}), capz.get(zid, {})
    missing = sorted(set(k) - set(s))
    extra = sorted(set(s) - set(k))
    for n in missing:
        lv = sorted({l for g in k[n] for l in g['levels']})
        rows_missing.append(dict(zone=zname, zone_id=zid, name=n, capnbry_levels=f"{lv[0]}-{lv[-1]}" if lv else '',
                                 capnbry_sightings=sum(g['sightings'] for g in k[n]), capnbry_cells=len(k[n])))
    for n in sorted(set(k) & set(s)):
        cl = sorted({l for g in k[n] for l in g['levels']})
        sl = sorted({l for p in s[n] for l in p[2]})
        if not cl or not sl: continue
        gap = max(cl[0] - sl[0], sl[0] - cl[0], cl[-1] - sl[-1], sl[-1] - cl[-1])
        if gap >= 3:
            rows_level.append(dict(zone=zname, zone_id=zid, name=n, capnbry_levels=f"{cl[0]}-{cl[-1]}",
                                   server_levels=f"{sl[0]}-{sl[-1]}", difference=gap, server_spawns=len(s[n])))
    for n in extra:
        sl = sorted({l for p in s[n] for l in p[2]})
        rows_extra.append(dict(zone=zname, zone_id=zid, name=n, server_levels=f"{sl[0]}-{sl[-1]}", server_spawns=len(s[n]),
                               classtypes=';'.join(sorted({p[3] for p in s[n]}))))
    for n, pts in s.items():
        if len(pts) > 400: continue
        for group in clusters(pts):
            if len(group) <= 2:
                cx = sum(p[0] for p in group) / len(group); cy = sum(p[1] for p in group) / len(group)
                near = [g for g in k.get(n, []) if math.hypot(g['local_x'] - cx, g['local_y'] - cy) <= 4200]
                cap_count = max((g['local_spawn_count'] for g in near), default=0)
                cap_sight = sum(g['sightings'] for g in near)
                rows_small.append(dict(zone=zname, zone_id=zid, name=n, server_spawns_here=len(group),
                                       local_x=int(cx), local_y=int(cy),
                                       capnbry_nearby=bool(near), capnbry_local_spawn_count=cap_count, capnbry_sightings=cap_sight,
                                       levels='-'.join(map(str, (min(l for p in group for l in p[2]), max(l for p in group for l in p[2])))),
                                       verdict=('likely short (CapnBry saw more here)' if cap_count >= 3 else
                                                'matches CapnBry (small/rare camp)' if near else
                                                'not seen by CapnBry here')))
    summary.append(dict(zone=zname, zone_id=zid, capnbry_species=len(k), server_species=len(s), missing=len(missing),
                        server_only=len(extra), level_mismatches=sum(1 for r in rows_level if r['zone_id'] == zid),
                        small_camps=sum(1 for r in rows_small if r['zone_id'] == zid)))

def write(name, rows):
    if not rows: return
    with open(os.path.join(OUT, name), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
write('capnbry_missing.csv', rows_missing)
write('capnbry_level_mismatch.csv', rows_level)
write('server_only.csv', rows_extra)
write('small_camps.csv', rows_small)
write('zone_summary.csv', summary)
print('zones', len(summary), 'missing', len(rows_missing), 'level', len(rows_level), 'server_only', len(rows_extra), 'small', len(rows_small))
print(collections.Counter(r['verdict'] for r in rows_small))
for r in summary:
    if r['zone'] in ('Silvermine Mts.', 'Shannon Estuary', 'Lough Derg', 'Cliffs of Moher', 'Connacht'): print(r)
