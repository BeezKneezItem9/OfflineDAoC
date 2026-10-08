"""CapnBry sightings for the quest NPCs/monsters the server lacks. Writes quests/npc_sightings.json."""
import json, os, re, time, urllib.request, collections
HERE = os.path.dirname(os.path.abspath(__file__))
r = json.load(open(os.path.join(HERE, 'resolved.json'), encoding='utf-8'))
names = sorted({s['needs_spawn']['name'] for q in r for s in q['steps'] if s.get('needs_spawn')})
capn = json.load(open(os.path.join(HERE, '..', 'bestiary', 'capnbry_zones.json'), encoding='utf-8'))
ids = {}
for zid, v in capn.items():
    for m in v.get('mobs', []):
        if m['name'].lower().strip() in {n.lower() for n in names}: ids[str(m['id'])] = m['name']
out_path = os.path.join(HERE, 'npc_sightings.json')
out = json.load(open(out_path, encoding='utf-8')) if os.path.exists(out_path) else {}
for mid, name in ids.items():
    if mid in out: continue
    try:
        req = urllib.request.Request(f"http://capnbry.net/daoc/mobs.php?f=xml&m={mid}", headers={'User-Agent': 'Mozilla/5.0'})
        s = urllib.request.urlopen(req, timeout=40).read().decode('latin-1')
    except Exception as e:
        print('fail', mid, e); time.sleep(5); continue
    seen = [[int(z), int(x), int(y), int(zz), int(l)] for z, x, y, zz, l in
            re.findall(r'<zone>(\d+)</zone>\s*<x>(\d+)</x>\s*<y>(\d+)</y>\s*<z>(-?\d+)</z>\s*<level>(\d+)</level>', s)]
    out[mid] = dict(name=name, seen=seen)
    json.dump(out, open(out_path, 'w', encoding='utf-8'))
    time.sleep(1.5)
print('fetched', len(out), 'with sightings', sum(1 for v in out.values() if v['seen']))
for mid, v in out.items():
    zones = collections.Counter(s[0] for s in v['seen'])
    print(v['name'], dict(zones.most_common(3)), 'levels', sorted({s[4] for s in v['seen']})[:4])
