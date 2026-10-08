"""Full Uthgard bestiary archive (disorder.dk/daoc/bestiary): breadth-first crawl of every page under the bestiary path
(zones, monsters with drops, items, factions, salvage, remains, XP items...). Raw pages kept verbatim in
raw_pages.jsonl.gz; resumes from it. Polite: one request at a time, 1 s apart. Skips form posts and images."""
import collections, gzip, html, json, os, re, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = 'https://disorder.dk/daoc/bestiary/'
RAW = os.path.join(HERE, 'raw_pages.jsonl.gz')
SKIP = re.compile(r'\.(png|gif|jpe?g|ico|css|js)(\?|$)|submit\.php|/gfx/|logout|login', re.I)

seen, queue = set(), collections.deque()
def norm(u):
    u = urllib.parse.urljoin(ROOT, html.unescape(u)).split('#')[0].replace('http://', 'https://').replace('://www.', '://')
    return u if u.startswith(ROOT) and not SKIP.search(u) else None
def links(body, base):
    out = []
    for h in re.findall(r'(?:href|action)\s*=\s*["\']([^"\']+)["\']', body, re.I):
        u = urllib.parse.urljoin(base, html.unescape(h))
        u = norm(u)
        if u: out.append(u)
    return out

if os.path.exists(RAW):
    try:
        with gzip.open(RAW, 'rt', encoding='utf-8') as f:
            for line in f:
                try: r = json.loads(line)
                except Exception: continue
                seen.add(r['url'])
                for u in links(r['body'], r['url']):
                    if u not in seen: queue.append(u)
    except EOFError:
        pass
if not seen: queue.append(ROOT)
n = 0
while queue:
    url = queue.popleft()
    if url in seen: continue
    seen.add(url)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (period-data archive; one request/s)'})
        body = urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'replace')
    except Exception as e:
        print('fail', url, e, flush=True); time.sleep(5); continue
    with gzip.open(RAW, 'at', encoding='utf-8') as f:
        f.write(json.dumps(dict(url=url, fetched=time.strftime('%Y-%m-%d %H:%M:%S'), body=body)) + '\n')
    for u in links(body, url):
        if u not in seen: queue.append(u)
    n += 1
    if n % 100 == 0: print(n, 'pages, queue', len(queue), flush=True)
    time.sleep(1.0)
print('done', n, flush=True)
