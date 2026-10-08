"""Uthgard 2.0 bestiary locations: each monster page shows a zone map (map.php?monster=ID) with a dot wherever players'
logs saw it. Maps without recorded locations are the plain zone map, so the plain map of a zone is the most common of
several monsters' maps; a monster's dots are the pixels where its map differs. A 1024-pixel map covers the 65536-unit
zone, so a dot at pixel (px, py) is zone loc (px * 64, py * 64).
  python uthgard_locations.py name [name ...]      or      python uthgard_locations.py --from-plan
Fetches only the maps it needs (2 s apart), keeps them in maps/, and writes locations.json:
{name: [{zone, monster_id, locs: [[x, y], ...]}]}. Uthgard is a later freeshard: a fallback where the period sources
(CapnBry radar, walkthrough locs) say nothing."""
import collections, gzip, hashlib, io, json, os, re, sys, time, urllib.request, zlib
from PIL import Image, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
MAPS = os.path.join(HERE, 'maps')
OUT = os.path.join(HERE, 'locations.json')
os.makedirs(MAPS, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (period-data archive; one request at a time)'}


def zone_pages():
    """zone id -> (zone name, [(monster id, name)])"""
    out = {}
    try:
        _read_zones(out)
    except (EOFError, OSError, zlib.error):
        pass  # the crawler is still appending: stop at its unfinished last batch
    return out


def _read_zones(out):
    with gzip.open(os.path.join(HERE, 'raw_pages.jsonl.gz'), 'rt', encoding='utf-8') as f:
        for line in f:
            try: r = json.loads(line)
            except ValueError: continue
            m = re.search(r'zone\.php\?load=(\d+)$', r['url'])
            if not m: continue
            title = re.search(r'Zone ::\s*(.*?)</title>', r['body'])
            mobs = [(i, re.sub(r'<[^>]+>', '', n).strip()) for i, n in re.findall(r'monster\.php\?load=(\d+)"[^>]*>(.*?)</a>', r['body'])]
            out[m.group(1)] = ((title.group(1).strip() if title else ''), mobs)


def fetch_map(mid):
    path = os.path.join(MAPS, f'{mid}.jpg')
    if not os.path.exists(path):
        body = urllib.request.urlopen(urllib.request.Request(f'https://disorder.dk/daoc/bestiary/map.php?monster={mid}', headers=UA), timeout=60).read()
        open(path, 'wb').write(body)
        time.sleep(2)
    return path


def plain_map(zone_mobs):
    """The zone's plain map: the most common image among up to 5 of its monsters' maps."""
    seen = collections.Counter()
    paths = {}
    for mid, _ in zone_mobs[:5]:
        p = fetch_map(mid)
        h = hashlib.md5(open(p, 'rb').read()).hexdigest()
        seen[h] += 1; paths[h] = p
        if seen[h] >= 2: return Image.open(p).convert('RGB')
    return Image.open(paths[seen.most_common(1)[0][0]]).convert('RGB') if seen else None


def dots(base, path):
    d = ImageChops.difference(base, Image.open(path).convert('RGB')).convert('L')
    px, (w, h) = d.load(), d.size
    pts = {(x, y) for x in range(w) for y in range(h) if px[x, y] > 60}
    clusters = []
    while pts:
        stack = [pts.pop()]; group = []
        while stack:
            x, y = stack.pop(); group.append((x, y))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q in pts: pts.remove(q); stack.append(q)
        if len(group) >= 3:
            cx = sum(p[0] for p in group) / len(group); cy = sum(p[1] for p in group) / len(group)
            clusters.append([int(cx * 64), int(cy * 64)])
    return clusters


def main():
    if '--from-plan' in sys.argv:
        plan = json.load(open(os.path.join(HERE, '..', '..', 'quests', 'spawn_plan.json'), encoding='utf-8'))
        wanted = {e['name'].lower() for e in plan if not (e.get('place') or {}).get('on_mesh')}
    else:
        wanted = {a.lower() for a in sys.argv[1:]}
    zones = zone_pages()
    result = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}
    bases = {}
    for zid, (zname, mobs) in sorted(zones.items(), key=lambda kv: int(kv[0])):
        hits = [(mid, n) for mid, n in mobs if n.lower() in wanted]
        if not hits: continue
        if zid not in bases: bases[zid] = plain_map([m for m in mobs if m not in hits])
        base = bases[zid]
        if base is None: continue
        for mid, name in hits:
            locs = dots(base, fetch_map(mid))
            entries = [e for e in result.get(name, []) if e['monster_id'] != mid]
            result[name] = entries + [dict(zone=zname, zone_id=zid, monster_id=mid, locs=locs)]
            print(name, zname, len(locs), flush=True)
            json.dump(result, open(OUT, 'w', encoding='utf-8'), indent=1)
    print('done', len(result))


if __name__ == '__main__':
    main()
