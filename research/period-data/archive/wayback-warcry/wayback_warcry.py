"""Historical Camelot Warcry (daoc.warcry.com: quests with full walkthroughs and hints, NPCs, items, compendium) from the Internet Archive, cut off at the Catacombs launch (2004-12-07):
for every archived URL, the LAST capture on or before the cutoff, fetched raw (id_ mode, no Wayback toolbar).
Owner 2026-10-07: period data only (classic, Shrouded Isles, Trials of Atlantis as it was before Catacombs/New Frontiers).

Stage 1 (cdx_index.txt): the CDX index of every capture <= cutoff (timestamp original status digest), streamed and resumable.
Stage 2 (raw_pages.jsonl.gz): one record per URL {url, timestamp, body}. Skips images/ads/forum posts/user pages.
Polite: one request at a time, 1.5 s apart, long backoff when the Archive says it is busy or offline. Resumes."""
import gzip, json, os, re, sys, time, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
CUTOFF = '20041207'
INDEX = os.path.join(HERE, 'cdx_index.txt')
RAW = os.path.join(HERE, 'raw_pages.jsonl.gz')
UA = {'User-Agent': 'Mozilla/5.0 (period-data archive; one request at a time)'}
SKIP = re.compile(r'\.(gif|jpe?g|png|css|js|ico|swf|zip|exe|wav|mp3)(\?|$)|forum|/members?/|login|account|profile|'
                  r'adclick|banner|/ads?/|newcomments|eqoarace|mid=\d|print\.html|/cgi-bin/|poster\.html|journal\.html|post=|replyto=|/add|admin|feedback|/forums?/|&ad=|lpop=', re.I)

def get(url, tries=8):
    for i in range(tries):
        try:
            body = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
            text = body.decode('utf-8', 'replace')
            if 'Internet Archive services are temporarily offline' in text or 'Too Many Requests' in text[:500]:
                raise IOError('archive busy')
            return body
        except urllib.error.HTTPError as e:
            if e.code in (404, 403): return None
            print('http', e.code, url, flush=True); time.sleep(min(600, 30 * 2 ** i))
        except Exception as e:
            print('wait', e, url[:120], flush=True); time.sleep(min(600, 30 * 2 ** i))
    return None

# Stage 1: CDX index, page by page (resume key kept in index.state)
STATE = os.path.join(HERE, 'index.state')
if not os.path.exists(STATE) or open(STATE).read().strip() != 'done':
    resume = open(STATE).read().strip() if os.path.exists(STATE) else ''
    while True:
        q = dict(url='daoc.warcry.com/*', to=CUTOFF, fl='timestamp,original,statuscode,digest', filter='statuscode:200',
                 limit='5000', showResumeKey='true')
        if resume: q['resumeKey'] = resume
        body = get('http://web.archive.org/cdx/search/cdx?' + urllib.parse.urlencode(q))
        if body is None: print('cdx failed; retry later', flush=True); sys.exit(1)
        lines = body.decode('utf-8', 'replace').rstrip('\n').split('\n')
        resume = ''
        if len(lines) >= 2 and lines[-2] == '':
            resume = lines[-1]; lines = lines[:-2]
        with open(INDEX, 'a', encoding='utf-8') as f:
            for l in lines:
                if l.strip(): f.write(l + '\n')
        open(STATE, 'w').write(resume or 'done')
        print('index +', len(lines), 'resume', bool(resume), flush=True)
        if not resume: break
        time.sleep(2)

# Stage 2: last capture per URL on or before the cutoff
latest = {}
for l in open(INDEX, encoding='utf-8'):
    p = l.split(' ')
    if len(p) < 3: continue
    ts, orig = p[0], p[1]
    key = re.sub(r'^https?://(www\.)?daoc\.warcry\.com(:80)?', '', orig).lower()
    if SKIP.search(key): continue
    if key not in latest or ts > latest[key][0]: latest[key] = (ts, orig)
done = set()
if os.path.exists(RAW):
    try:
        with gzip.open(RAW, 'rt', encoding='utf-8') as f:
            for line in f:
                try: done.add(json.loads(line)['key'])
                except Exception: pass
    except EOFError: pass
def priority(k):
    # quests and their dialogue first, then monsters, items, NPCs/merchants, zones, then everything else
    for i, rx in enumerate((r'spoilquest|detail_quest|hintquest|minquest', r'npc', r'item', r'compendium|maps', r'quest')):
        if re.search(rx, k): return i
    return 9
todo = sorted(((k, v) for k, v in latest.items() if k not in done), key=lambda kv: (priority(kv[0]), kv[0]))
print('urls', len(latest), 'todo', len(todo), flush=True)
for n, (key, (ts, orig)) in enumerate(todo):
    body = get(f'http://web.archive.org/web/{ts}id_/{orig}')
    with gzip.open(RAW, 'at', encoding='utf-8') as f:
        f.write(json.dumps(dict(key=key, url=orig, timestamp=ts,
                                body=body.decode('latin-1') if body is not None else None)) + '\n')
    if n % 200 == 0: print('pages', n, '/', len(todo), flush=True)
    time.sleep(3)  # shares the Archive with the Allakhazam fetcher
print('done', flush=True)
