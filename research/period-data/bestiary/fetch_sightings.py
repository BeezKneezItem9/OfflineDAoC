"""Fetch CapnBry sighting coordinates (mobs.php?f=xml&m=ID) for the species named in a work list.
Usage: python fetch_sightings.py zone_id[,zone_id...] [--all-missing]
Writes/extends sightings.json: {mob_id: {name, seen: [[zone, x, y, z, level], ...]}}"""
import json, os, re, sys, time, urllib.request, csv

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'sightings.json')
data = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}
capn = json.load(open(os.path.join(HERE, 'capnbry_zones.json'), encoding='utf-8'))

zones = sys.argv[1].split(',') if len(sys.argv) > 1 and sys.argv[1] != '-' else []
wanted = set()
missing = list(csv.DictReader(open(os.path.join(HERE, 'report_missing.csv'), encoding='utf-8')))
for r in missing:
    if r['zone_id'] in zones or '--all-missing' in sys.argv:
        wanted.add((r['zone_id'], r['name']))
ids = {}
for zid, name in wanted:
    for m in capn.get(zid, {}).get('mobs', []):
        if m['name'].lower().strip() == name:
            ids[str(m['id'])] = m['name']
print('mob ids to fetch', len([i for i in ids if i not in data]), flush=True)
for mid, name in sorted(ids.items(), key=lambda kv: int(kv[0])):
    if mid in data: continue
    try:
        req = urllib.request.Request(f"http://capnbry.net/daoc/mobs.php?f=xml&m={mid}", headers={'User-Agent': 'Mozilla/5.0'})
        s = urllib.request.urlopen(req, timeout=40).read().decode('latin-1')
    except Exception as e:
        print('fail', mid, e, flush=True); time.sleep(10); continue
    seen = [[int(z), int(x), int(y), int(zz), int(l)] for z, x, y, zz, l in
            re.findall(r'<zone>(\d+)</zone>\s*<x>(\d+)</x>\s*<y>(\d+)</y>\s*<z>(-?\d+)</z>\s*<level>(\d+)</level>', s)]
    data[mid] = dict(name=name, seen=seen)
    json.dump(data, open(OUT, 'w', encoding='utf-8'))
    time.sleep(1.5)
print('done', len(data), flush=True)
