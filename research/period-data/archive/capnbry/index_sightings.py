"""Index of the CapnBry radar archive: every mob's name, typetag and sightings (zone, x, y, z, level) parsed from the raw
sighting XML in raw_pages.jsonl.gz. Writes sightings_index.json {mob_id: {name, typetag, seen: [[zone,x,y,z,level],...]}}.
Re-run any time (reads whatever has been downloaded)."""
import gzip, json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
out = {}
try:
    with gzip.open(os.path.join(HERE, 'raw_pages.jsonl.gz'), 'rt', encoding='utf-8') as f:
        for line in f:
            try: r = json.loads(line)
            except ValueError: continue
            if 'f=xml' not in r['url']: continue
            for mob in re.findall(r'<mob>(.*?)</mob>', r['body'], re.S):
                mid = re.search(r'<mob_id>(\d+)</mob_id>', mob)
                if not mid: continue
                name = re.search(r'<name>(.*?)</name>', mob, re.S)
                tag = re.search(r'<typetag>(.*?)</typetag>', mob, re.S)
                seen = [[int(z), int(x), int(y), int(zz), int(l)] for z, x, y, zz, l in re.findall(
                    r'<zone>(\d+)</zone>\s*<x>(-?\d+)</x>\s*<y>(-?\d+)</y>\s*<z>(-?\d+)</z>\s*<level>(\d+)</level>', mob)]
                out[mid.group(1)] = dict(name=(name.group(1).strip() if name else ''), typetag=(tag.group(1).strip() if tag else ''), seen=seen)
except EOFError:
    pass
json.dump(out, open(os.path.join(HERE, 'sightings_index.json'), 'w', encoding='utf-8'))
print('mobs', len(out), 'sightings', sum(len(v['seen']) for v in out.values()))
