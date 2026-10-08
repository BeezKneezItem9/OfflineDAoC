"""The in-game Quest Guide (owner 2026-10-07): the Allakhazam walkthrough of every classic quest on the server, shown by
the Quest Journal's QUEST GUIDE button (/task) and /questguide.

Text, per quest: the period copy of its Allakhazam page (Wayback, captured on or before 2004-12-07:
../archive/wayback-allakhazam/quest_pages.jsonl.gz), else the current Allakhazam page (walkthroughs.jsonl) with the
lines that describe later patches removed (New Frontiers, Catacombs, patch 1.7x/1.8x changes, later classes). Player
comments are left out; only the walkthrough body is kept. Every guide records which source it came from.

Writes quest_guides.json here and classic-quest-guides.json next to the server (read by GameServer QuestGuide).
   python build_quest_guides.py"""
import gzip, html, json, os, re, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
OUT = os.path.join(HERE, 'quest_guides.json')
SERVER_OUT = os.path.join(ROOT, 'runtime', 'server', 'classic-quest-guides.json')
PERIOD = os.path.join(HERE, '..', 'archive', 'wayback-allakhazam', 'quest_pages.jsonl.gz')

# Lines of a current page that describe the game after 2004 (the server is classic + Shrouded Isles, pre-New Frontiers).
LATER = re.compile(r'new frontiers|\bNF\b|catacomb|darkness rising|labyrinth|champion level|vampiir|bainshee|mauler|'
                   r'heroic|minstrel ?skin|\b1\.(?:7[4-9]|8\d|9\d|1\d\d)\b|patch (?:version )?1\.(?:7[4-9]|8|9|1\d\d)|'
                   r'created after patch|no longer|has been moved|can now be found|now (?:drops?|gives?|located)|'
                   r'\b20(?:0[5-9]|1\d|2\d)\b', re.I)


def norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'\s*\((?:level \d+|alb|mid|hib)\)\s*$', '', (s or '').strip(), flags=re.I)).lower()


def clean(fragment):
    t = re.sub(r'<br\s*/?>|</p>|<p[^>]*>|</li>|<li[^>]*>', '\n', fragment, flags=re.I)
    t = html.unescape(re.sub(r'<[^>]+>', '', t)).replace('\xa0', ' ')
    return [re.sub(r'[ \t\r]+', ' ', x).strip() for x in t.split('\n')]


def period_body(page):
    """The walkthrough part of a 2002-2004 Allakhazam quest page: after the disclaimer, before 'Send a correction'."""
    b = page or ''
    i = b.find('DISCLAIMER')
    if i < 0: return None, None
    j = b.find('Send a correction', i)
    body = b[b.find('<br>', i):j if j > 0 else i + 60000]
    body = body[:body.rfind('<tr>')] if '<tr>' in body else body
    lines = [x for x in clean(body) if x]
    m = re.search(r'Last Updated:.*?<i>\s*([^<]+?)\s*</i>', b, re.S)
    return lines, (m.group(1).strip() if m else None)


specs = {}
for realm in ('albion', 'midgard', 'hibernia'):
    for l in open(os.path.join(HERE, 'specs', f'{realm}.jsonl'), encoding='utf-8'):
        s = json.loads(l)
        specs[s['src']] = s
walk = {}
for l in open(os.path.join(HERE, 'walkthroughs.jsonl'), encoding='utf-8'):
    w = json.loads(l)
    walk.setdefault((w['realm'], norm(w.get('title'))), w)
period = {}
if os.path.exists(PERIOD):
    try:
        for l in gzip.open(PERIOD, 'rt', encoding='utf-8'):
            r = json.loads(l)
            period[(r['id'], r['realm'])] = r
    except (EOFError, OSError, zlib.error):
        pass

rows = json.load(open(os.path.join(HERE, 'dataquest_preview.json'), encoding='utf-8'))['rows']
guides, stats = {}, {'period': 0, 'current': 0, 'none': 0}
for r in rows:
    key = f"{r['realm']}|{r['Name']}".lower()
    if key in guides: continue
    spec = specs.get(r.get('src')) or {}
    w = walk.get((r['realm'], norm(spec.get('name') or r['Name']))) or walk.get((r['realm'], norm(r['Name'])))
    lines, source, updated = None, None, None
    if w:
        p = period.get((int(w['id']), w['realm']))
        if p and p.get('body'):
            lines, updated = period_body(p['body'])
            if lines:
                ts = p['timestamp']
                source = f"Allakhazam quest page as archived {ts[:4]}-{ts[4:6]}-{ts[6:8]} (Wayback Machine)"
        if not lines and w.get('body'):
            lines = [x for x in w['body'] if x.strip() and not LATER.search(x)]
            source = "Allakhazam quest page (current copy; notes about later patches removed)"
    if lines:
        stats['period' if 'archived' in source else 'current'] += 1
    else:
        # No Allakhazam page: the quest's own journal steps (the spec the quest was built from).
        lines = [f"Step {i + 1}: {st.get('text')}" for i, st in enumerate(spec.get('steps') or []) if st.get('text')]
        source = "No Allakhazam walkthrough was found; these are the quest's journal steps"
        stats['none'] += 1
    guides[key] = {'Name': r['Name'], 'Realm': r['realm'], 'Source': source, 'Updated': updated,
                   'Level': spec.get('level'), 'Lines': lines}

data = {'_about': __doc__.split('\n\n')[0], 'Guides': guides}
for path in (OUT, SERVER_OUT):
    json.dump(data, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print(f"guides {len(guides)}: period copies {stats['period']}, current pages {stats['current']}, none {stats['none']}")
