"""Download Uthgard 2.0 bestiary zone tables (name, level from/to, aggro, kills) into uthgard_zones.json."""
import json, os, re, time, html, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'uthgard_zones.json')
data = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    return urllib.request.urlopen(req, timeout=40).read().decode('utf-8', 'replace')

idx = get("https://disorder.dk/daoc/bestiary/")
ids = sorted({int(x) for x in re.findall(r'zone\.php\?load=(\d+)', idx)})
print('zones', len(ids), flush=True)
for zid in ids:
    if str(zid) in data: continue
    try:
        s = get(f"https://disorder.dk/daoc/bestiary/zone.php?load={zid}")
    except Exception as e:
        print('fail', zid, e, flush=True); time.sleep(10); continue
    s = re.sub(r'<script.*?</script>', '', s, flags=re.S)
    title = re.search(r'Zone ::\s*(.*?)</title>', s)
    mobs = []
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', s, re.S):
        tds = [html.unescape(re.sub(r'<[^>]+>', '', td)).strip() for td in re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)]
        if len(tds) >= 5 and tds[1].isdigit() and tds[2].isdigit():
            mobs.append(dict(name=tds[0], min=int(tds[1]), max=int(tds[2]), aggro=tds[3],
                             killed=int(tds[4]) if tds[4].isdigit() else 0))
    data[str(zid)] = dict(name=html.unescape(title.group(1)).strip() if title else '', mobs=mobs)
    json.dump(data, open(OUT, 'w', encoding='utf-8'))
    print(zid, data[str(zid)]['name'], len(mobs), flush=True)
    time.sleep(2)
print('done', flush=True)
