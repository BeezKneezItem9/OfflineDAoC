"""For each blocked quest target: every location hint in the period sources (owner 2026-10-07: all quests in)."""
import json, re, gzip, html, zlib, os, sys
targets = [l.split('|') for l in sys.argv[1:]]
walk = {}
for l in open('walkthroughs.jsonl', encoding='utf-8'):
    w = json.loads(l); walk.setdefault(w['title'].lower(), w)
period = {}
try:
    for l in gzip.open('../archive/wayback-allakhazam/quest_pages.jsonl.gz', 'rt', encoding='utf-8'):
        r = json.loads(l); period[(r['title'] or '').lower()] = r
except Exception: pass
def txt(h): return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', h or '')))
warcry = []
try:
    for l in gzip.open('../archive/wayback-warcry/raw_pages.jsonl.gz', 'rt', encoding='utf-8', errors='replace'):
        if 'spoilquest' in l or 'detail_quest' in l: warcry.append(json.loads(l))
except (EOFError, OSError, zlib.error): pass
for quest, npc in targets:
    print('#####', quest, '->', npc)
    w = walk.get(quest.lower())
    lines = (w or {}).get('body') or []
    p = period.get(quest.lower())
    if p and p.get('body'): lines = lines + ['[1999-2004 copy] ' + txt(p['body'])[:4000]]
    for b in lines:
        for m in re.finditer(r'[^.]*(?:' + re.escape(npc.split()[0]) + r'|loc)[^.]*\.', b, re.I):
            s = m.group(0).strip()
            if len(s) > 15: print('   ZAM:', s[:300])
    for r in warcry:
        t = txt(r.get('html') or r.get('body'))
        if quest.lower()[:20] in t.lower() and npc.split()[0].lower() in t.lower():
            for m in re.finditer(r'[^.]*' + re.escape(npc.split()[0]) + r'[^.]*\.', t, re.I):
                print('   WARCRY:', m.group(0).strip()[:300])
            break
