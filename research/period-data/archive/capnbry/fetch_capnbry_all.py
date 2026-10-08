"""Full CapnBry archive (owner 2026-10-07: keep everything): every zone index page, every zone mob list, and the radar
sighting XML (zone, x, y, z, level per sighting) for every mob id. Raw responses are kept verbatim (gzipped jsonl) so
nothing the parser misses is lost; parsed summaries go next to them. Polite: one request at a time, 1 s apart; resumes."""
import gzip, json, os, re, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = 'http://capnbry.net/daoc/'
RAW = os.path.join(HERE, 'raw_pages.jsonl.gz')

done = set()
if os.path.exists(RAW):
    try:
        with gzip.open(RAW, 'rt', encoding='utf-8') as f:
            for line in f:
                try: done.add(json.loads(line)['url'])
                except Exception: pass
    except EOFError:
        pass

def get(path):
    url = BASE + path
    if url in done: return None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (period-data archive; one request/s)'})
            body = urllib.request.urlopen(req, timeout=60).read().decode('latin-1')
            with gzip.open(RAW, 'at', encoding='utf-8') as f:
                f.write(json.dumps(dict(url=url, fetched=time.strftime('%Y-%m-%d %H:%M:%S'), body=body)) + '\n')
            done.add(url)
            time.sleep(1.0)
            return body
        except Exception as e:
            print('fail', url, e, flush=True); time.sleep(10 * (attempt + 1))
    return None

def cached(path):
    url = BASE + path
    with gzip.open(RAW, 'rt', encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            if r['url'] == url: return r['body']

get('mobs.php')
for r in range(1, 6):
    get(f'mobs.php?r={r}'); get(f'mobs.php?a=typetag&r={r}')
zone_ids = []
for r in range(1, 6):
    s = get(f'mobs.php?a=zones&r={r}') or cached(f'mobs.php?a=zones&r={r}')
    zone_ids += re.findall(r'mobs\.php\?z=(\d+)', s or '')
zone_ids = sorted(set(zone_ids), key=int)
print('zones', len(zone_ids), flush=True)
mob_ids = []
for z in zone_ids:
    s = get(f'mobs.php?z={z}') or cached(f'mobs.php?z={z}')
    mob_ids += re.findall(r'mobs\.php\?z=\d+&(?:amp;)?m=(\d+)', s or '')
mob_ids = sorted(set(mob_ids), key=int)
print('mobs', len(mob_ids), flush=True)
for i, m in enumerate(mob_ids):
    get(f'mobs.php?f=xml&m={m}')
    if i % 200 == 0: print('sightings', i, '/', len(mob_ids), flush=True)
print('done', flush=True)
