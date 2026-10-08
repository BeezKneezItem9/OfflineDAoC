"""Historical (<= 2004-12-07) Allakhazam quest pages for every classic quest walkthrough, fetched ahead of the full
Wayback pass so the in-game Quest Guide can show the period text (owner 2026-10-07). Quest ids come from
quests/walkthroughs.jsonl. For each quest: the captures of quests.html?cquest=<id> (same realm, or no realm) from the
local cdx_index.txt, else a CDX query; the last capture on or before the cutoff, plain page preferred over a comment
link (&mid=), fetched raw (id_). Appends {id, realm, title, timestamp, url, body} to quest_pages.jsonl.gz.
Polite: one request at a time, 2 s apart; resumes."""
import gzip, json, os, re, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
Q = os.path.join(HERE, '..', '..', 'quests')
OUT = os.path.join(HERE, 'quest_pages.jsonl.gz')
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


def params(url):
    return {k.lower(): v for k, v in urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query, keep_blank_values=True)}


def matches(url, qid, realm):
    p = params(url)
    if p.get('cquest') != str(qid): return False
    r = p.get('realm', '').lower()
    return r in ('', 'all', realm.lower())


captures = {}  # cquest id -> [(timestamp, url)]
for line in open(os.path.join(HERE, 'cdx_index.txt'), encoding='utf-8', errors='replace'):
    parts = line.split(' ')
    if len(parts) < 3 or parts[2] != '200' or 'cquest=' not in parts[1] or 'quest' not in parts[1].lower(): continue
    if parts[0][:8] > CUTOFF: continue
    cid = params(parts[1]).get('cquest')
    if cid and cid.isdigit(): captures.setdefault(cid, []).append((parts[0], parts[1]))

walks = []
for l in open(os.path.join(Q, 'walkthroughs.jsonl'), encoding='utf-8'):
    w = json.loads(l)
    walks.append((int(w['id']), w['realm'], w.get('title') or ''))
done = set()
if os.path.exists(OUT):
    try:
        for l in gzip.open(OUT, 'rt', encoding='utf-8'):
            r = json.loads(l); done.add((r['id'], r['realm']))
    except (EOFError, OSError):
        pass
todo = [w for w in dict.fromkeys(walks) if (w[0], w[1]) not in done]
print('quests', len(walks), 'todo', len(todo), 'with local captures', sum(1 for w in todo if str(w[0]) in captures), flush=True)


def best(rows, qid, realm):
    rows = [r for r in rows if matches(r[1], qid, realm)]
    plain = [r for r in rows if 'mid' not in params(r[1])]
    pick = sorted(plain or rows)
    return pick[-1] if pick else None


for n, (qid, realm, title) in enumerate(todo):
    choice = best(captures.get(str(qid), []), qid, realm)
    if choice is None:
        q = urllib.parse.urlencode(dict(url='camelot.allakhazam.com/db/quests.html', matchType='prefix', to=CUTOFF,
                                        fl='timestamp,original,statuscode', filter=['statuscode:200', f'original:.*cquest={qid}(&.*)?$']),
                                   doseq=True)
        body = get('http://web.archive.org/cdx/search/cdx?' + q)
        time.sleep(2)
        rows = [tuple(l.split(' ')[:2]) for l in (body or b'').decode('utf-8', 'replace').splitlines() if l.strip()]
        choice = best(rows, qid, realm)
    rec = dict(id=qid, realm=realm, title=title, timestamp=None, url=None, body=None)
    if choice:
        page = get(f'http://web.archive.org/web/{choice[0]}id_/{choice[1]}')
        time.sleep(2)
        rec.update(timestamp=choice[0], url=choice[1], body=page.decode('latin-1') if page else None)
    with gzip.open(OUT, 'at', encoding='utf-8') as f:
        f.write(json.dumps(rec) + '\n')
    if n % 25 == 0: print(n, '/', len(todo), qid, realm, rec['timestamp'], flush=True)
print('done', flush=True)
