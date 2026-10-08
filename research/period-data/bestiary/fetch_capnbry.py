"""Download CapnBry per-zone name/level lists (all realms) into capnbry_zones.json."""
import json, os, re, time, html, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'capnbry_zones.json')
data = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    return urllib.request.urlopen(req, timeout=40).read().decode('latin-1')

zones = {}
for r in range(1, 6):
    s = get(f"http://capnbry.net/daoc/mobs.php?a=zones&r={r}")
    for zid in re.findall(r'href="mobs.php\?z=(\d+)"[^>]*>AllMobs<', s):
        zones[zid] = r
    time.sleep(1.5)
print('zones', len(zones), flush=True)

for zid, realm in sorted(zones.items(), key=lambda kv: int(kv[0])):
    if zid in data: continue
    try:
        s = get(f"http://capnbry.net/daoc/mobs.php?z={zid}")
    except Exception as e:
        print('fail', zid, e, flush=True); time.sleep(10); continue
    title = re.search(r'<h2>(.*?)</h2>', s)
    rows = re.findall(r'<tr><td><a href="mobs.php\?z=\d+&m=(\d+)">(.*?)</a></td><td align="center">(\d+)</td>'
                      r'<td align="center">(\d+)</td><td align="center">(\d+)</td></tr>', s)
    data[zid] = dict(realm_group=realm, name=html.unescape(title.group(1)) if title else '',
                     mobs=[dict(id=int(m), name=html.unescape(n), min=int(a), avg=int(b), max=int(c)) for m, n, a, b, c in rows])
    json.dump(data, open(OUT, 'w', encoding='utf-8'))
    print(zid, data[zid]['name'], len(rows), flush=True)
    time.sleep(1.5)
print('done', flush=True)
