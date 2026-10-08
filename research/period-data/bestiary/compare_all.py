"""Goal 11: server monster spawns vs CapnBry raw zone lists (period radar data) and Uthgard 2.0 (secondary)."""
import json, sqlite3, re, collections, math, os, csv

ROOT = r"C:/OfflineDAoC"
DB = os.path.join(ROOT, r"runtime\data\opendaoc.sqlite3.db")
CATALOG = os.path.join(ROOT, r"development-source\server\GameServer\bots\autonomous\data\capnbry_classic_si_goals.json")
HERE = os.path.dirname(os.path.abspath(__file__))
PEACE = 0x10
# Player pets/summons, mounts, boats and holiday-invasion mobs seen by radar: not zone populations.
NOISE = re.compile(r"^(horse|sleigh horse|skiff|boat|.*necroservant|skeletal commander|returned commander|decayed commander|"
                   r"ghastly .* invader|ghostly .* invader|.*invader|guardsman|elite guard|.*guard|.*sentry|.*pet|"
                   r"spirit (warrior|soldier|champion|hunter)|(lesser |greater )?(air|earth|ice|fire) (spirit|beast)|.*elemental ward|underhill .*|.*minion of .*)$")

def norm(name):
    n = name.lower().strip()
    n = re.sub(r"^(a|an|the) ", "", n)
    return re.sub(r"\s+", " ", n)

def zkey(name):
    return re.sub(r"[^a-z]", "", name.lower().replace("mountains", "mts").replace("mtns", "mts"))

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
zone_region = {z[0]: z[1] for z in zones}

def zone_of(region, x, y):
    for z in zone_by_region.get(region, []):
        if z[3] * 8192 <= x < (z[3] + z[5]) * 8192 and z[4] * 8192 <= y < (z[4] + z[6]) * 8192:
            return z
    return None

templates = {r[0]: r[1] for r in c.execute("select TemplateId, Level from NpcTemplate")}
server = collections.defaultdict(lambda: collections.defaultdict(list))
server_npcs = collections.defaultdict(lambda: collections.defaultdict(list))
for name, region, x, y, level, tid, flags, ctype, realm, guild in c.execute(
        "select Name, Region, X, Y, Level, NPCTemplateID, Flags, ClassType, Realm, Guild from Mob"):
    if not name: continue
    z = zone_of(region, x, y)
    if not z: continue
    lx, ly = x - z[3] * 8192, y - z[4] * 8192
    if realm or (flags or 0) & PEACE:
        server_npcs[z[0]][name].append((lx, ly, level, ctype, guild or ''))
        continue
    levels = parse_levels(templates.get(tid), level) if tid and tid > 0 else [level]
    server[z[0]][norm(name)].append((lx, ly, levels, ctype))

capn = json.load(open(os.path.join(HERE, 'capnbry_zones.json'), encoding='utf-8'))
uth = json.load(open(os.path.join(HERE, 'uthgard_zones.json'), encoding='utf-8'))
# Illia's Camelot Bestiary (Allakhazam), {cmzone: {name, rows: [[name, "a - b", type, damage]]}}
ILLIA_PATH = os.path.join(HERE, 'illia_zones.json')
illia = json.load(open(ILLIA_PATH, encoding='utf-8')) if os.path.exists(ILLIA_PATH) else {}
illia_by_key = {}
for v in illia.values():
    mobs = {}
    for row in v.get('rows', []):
        if len(row) < 3 or row[2] in ('NPC', 'Merchant', 'Guard', 'Realm Guard', 'Trainer'): continue
        m = re.match(r'(\d+)\s*-\s*(\d+)', row[1])
        if m: mobs[norm(row[0])] = (int(m.group(1)), int(m.group(2)))
    illia_by_key[zkey(v['name'])] = mobs
uth_by_key = {zkey(v['name']): v for v in uth.values()}
catalog = json.load(open(CATALOG, encoding='utf-8'))
camp_counts = collections.defaultdict(list)
for g in catalog['goals']:
    camp_counts[(g['zone_id'], g['normalized_name'])].append(g)

def clusters(points, radius=1500):
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

missing, levels, extra, small, summary = [], [], [], [], []
for zid_s, zinfo in sorted(capn.items(), key=lambda kv: int(kv[0])):
    zid = int(zid_s)
    if zid not in zone_name or not zinfo['mobs']: continue
    # Out of scope: Trials of Atlantis zones (73-91, 1.62+ expansion the server lacks) and the New Frontiers
    # zone set (163-176, patch 1.80). The server's own frontiers are the old ones (11-15, 111-115, 210-214).
    if 73 <= zid <= 91 or 163 <= zid <= 178: continue
    zname = zone_name[zid]
    cap_mobs = {}
    for m in zinfo['mobs']:
        if not m['name'][:1].islower(): continue  # capitalized = NPC or named; handled in the NPC audit
        if NOISE.search(m['name']): continue
        k = norm(m['name'])
        prev = cap_mobs.get(k)
        cap_mobs[k] = dict(min=min(m['min'], prev['min']) if prev else m['min'], max=max(m['max'], prev['max']) if prev else m['max'])
    il = illia_by_key.get(zkey(zname))
    u = uth_by_key.get(zkey(zname))
    u_mobs = {norm(m['name']): m for m in u['mobs']} if u else {}
    s = server.get(zid, {})
    for n, cm in sorted(cap_mobs.items()):
        if n not in s:
            missing.append(dict(zone=zname, zone_id=zid, name=n, capnbry_levels=f"{cm['min']}-{cm['max']}" if cm['max'] else 'unknown',
                                illia=('%d-%d' % il[n] if il and n in il else 'no' if il else 'no data'),
                                uthgard=('yes' if n in u_mobs else 'no' if u else 'no data')))
        elif cm['max'] > 0:
            sl = sorted({l for p in s[n] for l in p[2]})
            gap = max(abs(cm['min'] - sl[0]), abs(cm['max'] - sl[-1]))
            if gap >= 3:
                levels.append(dict(zone=zname, zone_id=zid, name=n, capnbry_levels=f"{cm['min']}-{cm['max']}",
                                   server_levels=f"{sl[0]}-{sl[-1]}", difference=gap, server_spawns=len(s[n]),
                                   direction='server higher' if sl[-1] > cm['max'] else 'server lower'))
    for n, pts in sorted(s.items()):
        if n in cap_mobs: continue
        sl = sorted({l for p in pts for l in p[2]})
        extra.append(dict(zone=zname, zone_id=zid, name=n, server_levels=f"{sl[0]}-{sl[-1]}", server_spawns=len(pts),
                          uthgard=('yes' if n in u_mobs else 'no' if u else 'no data'),
                          classtypes=';'.join(sorted({p[3].split('.')[-1] for p in pts}))))
    for n, pts in s.items():
        if len(pts) > 600: continue
        for group in clusters(pts):
            if len(group) > 2: continue
            cx = sum(p[0] for p in group) / len(group); cy = sum(p[1] for p in group) / len(group)
            near = [g for g in camp_counts.get((zid, n), []) if math.hypot(g['local_x'] - cx, g['local_y'] - cy) <= 4200]
            seen = max((g['local_spawn_count'] for g in near), default=0)
            named = any(ch.isupper() for ch in n) or len(pts) <= 2
            small.append(dict(zone=zname, zone_id=zid, name=n, spawns_in_camp=len(group), local_x=int(cx), local_y=int(cy),
                              capnbry_spawns_seen_nearby=seen, species_total_in_zone=len(pts),
                              verdict=('likely short: CapnBry saw %d here' % seen if seen >= 3 else
                                       'matches CapnBry (1-2 seen here)' if near else
                                       'rare/named species (1-2 in whole zone)' if len(pts) <= 2 else
                                       'no CapnBry sighting at this spot')))
    summary.append(dict(zone=zname, zone_id=zid, region=zone_region[zid], capnbry_species=len(cap_mobs), server_species=len(s),
                        uthgard_species=len(u_mobs) if u else '', missing=sum(1 for r in missing if r['zone_id'] == zid),
                        level_mismatch=sum(1 for r in levels if r['zone_id'] == zid),
                        server_only=sum(1 for r in extra if r['zone_id'] == zid),
                        small_camps_likely_short=sum(1 for r in small if r['zone_id'] == zid and r['verdict'].startswith('likely short'))))

def write(name, rows):
    with open(os.path.join(HERE, name), 'w', newline='', encoding='utf-8') as f:
        if not rows: return
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
write('report_missing.csv', missing); write('report_levels.csv', levels); write('report_server_only.csv', extra)
write('report_small_camps.csv', small); write('report_zones.csv', summary)
print('zones', len(summary), 'missing', len(missing), 'level', len(levels), 'server_only', len(extra), 'small', len(small))
print(collections.Counter(r['verdict'].split(':')[0] for r in small))
for r in summary:
    if r['zone_id'] in (200, 201, 202, 203, 207): print(r)
