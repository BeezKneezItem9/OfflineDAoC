"""Historical (pre-Catacombs, <= 2004-12-07) Allakhazam item pages for the classic quest rewards, fetched ahead of the
full Wayback pass. Item ids come from the quest pages (archived quest pages' item links and quest_item_links.jsonl);
names wanted from quests/reward_items_report.json "missing". For each id: the CDX list of its captures, the last one on
or before the cutoff, fetched raw (id_). Appends {citem, name, timestamp, url, body} to items_direct.jsonl.gz.
Polite: one request at a time, 2 s apart; resumes."""
import gzip, html, json, os, re, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
Q = os.path.join(HERE, '..', '..', 'quests')
OUT = os.path.join(HERE, 'items_direct.jsonl.gz')
CUTOFF = '20041207'
UA = {'User-Agent': 'Mozilla/5.0 (period-data archive; one request at a time)'}


def get(url):
    for i in range(6):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 404): return None
            time.sleep(30 * (i + 1))
        except Exception:
            time.sleep(30 * (i + 1))
    return None


ids = {}  # lower name -> set of citem ids
for l in open(os.path.join(Q, 'quest_item_links.jsonl'), encoding='utf-8'):
    for it in json.loads(l).get('items') or []:
        cid, _, name = it.partition('|')
        if cid.isdigit(): ids.setdefault(name.lower().strip(), set()).add(cid)
try:
    for l in gzip.open(os.path.join(HERE, '..', 'allakhazam-live', 'quest.jsonl.gz'), 'rt', encoding='utf-8'):
        r = json.loads(l)
        for cid, name in re.findall(r'item\.html\?citem=(\d+)"[^>]*>(.*?)</a>', r.get('html') or ''):
            ids.setdefault(html.unescape(re.sub(r'<[^>]+>', '', name)).lower().strip(), set()).add(cid)
except (EOFError, OSError):
    pass

missing = json.load(open(os.path.join(Q, 'reward_items_report.json'), encoding='utf-8'))['missing']
done = set()
if os.path.exists(OUT):
    try:
        for l in gzip.open(OUT, 'rt', encoding='utf-8'): done.add(json.loads(l)['citem'])
    except (EOFError, OSError):
        pass
todo = []
for v in missing.values():
    for cid in sorted(ids.get(v['name'].lower(), set()) | ids.get(v['full'].lower(), set())):
        if cid not in done: todo.append((cid, v['name']))
todo = list(dict.fromkeys(todo))
print('wanted', len(missing), 'with ids', len({n for _, n in todo}), 'pages', len(todo), flush=True)
for n, (cid, name) in enumerate(todo):
    q = urllib.parse.urlencode(dict(url=f'camelot.allakhazam.com/item.html?citem={cid}', to=CUTOFF, fl='timestamp,original,statuscode',
                                    filter='statuscode:200'))
    body = get('http://web.archive.org/cdx/search/cdx?' + q)
    time.sleep(2)
    rows = [l.split(' ') for l in (body or b'').decode('utf-8', 'replace').splitlines() if l.strip()]
    rec = dict(citem=cid, name=name, timestamp=None, url=None, body=None)
    if rows:
        ts, orig = rows[-1][0], rows[-1][1]
        page = get(f'http://web.archive.org/web/{ts}id_/{orig}')
        time.sleep(2)
        rec.update(timestamp=ts, url=orig, body=page.decode('latin-1') if page else None)
    with gzip.open(OUT, 'at', encoding='utf-8') as f:
        f.write(json.dumps(rec) + '\n')
    if n % 50 == 0: print(n, '/', len(todo), flush=True)
print('done', flush=True)
