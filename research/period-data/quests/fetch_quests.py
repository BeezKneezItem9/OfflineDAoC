"""Fetch Allakhazam quest detail pages for Classic + Shrouded Isles quests (period scope for goal 10)."""
import csv, json, os, re, time, html, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'details.jsonl')
done = set()
if os.path.exists(OUT):
    for line in open(OUT, encoding='utf-8'):
        try: done.add(json.loads(line)['id'])
        except Exception: pass

rows = list(csv.DictReader(open(os.path.join(HERE, 'allakhazam_quests.csv'), encoding='utf-8')))
scope = [r for r in rows if r['exp'] in ('Classic', 'Shrouded Isle expansion')
         and r['type'] not in ('Master Level', 'Artifact', 'Champion')]

def field(text, name):
    m = re.search(re.escape(name) + r':\s*\|(.*?)(?:\|\s*\|\s*\|\s*\|\s*\|)', text)
    if not m: return ''
    return ' / '.join(p.strip() for p in m.group(1).split('|') if p.strip() and p.strip() != '&nbsp;&nbsp;')

with open(OUT, 'a', encoding='utf-8') as out:
    for r in scope:
        qid = int(r['id'])
        if qid in done: continue
        url = f"https://camelot.allakhazam.com/quests.html?realm={r['realm']}&cquest={qid}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            s = urllib.request.urlopen(req, timeout=30).read().decode('latin-1')
        except Exception as e:
            print('fail', qid, e, flush=True); time.sleep(5); continue
        s = re.sub(r'<script.*?</script>', '', s, flags=re.S)
        s = re.sub(r'<style.*?</style>', '', s, flags=re.S)
        t = html.unescape(re.sub(r'\s+', ' ', re.sub('<[^>]+>', ' | ', s)))
        rec = dict(r, id=qid, start=field(t, 'Start NPC'), classes=field(t, 'Class'), qtype=field(t, 'Type'),
                   zones=field(t, 'Zones'), minlevel=field(t, 'Min Level'), maxlevel=field(t, 'Max Level'),
                   related=field(t, 'Related Quests'),
                   note=('1.79' if 'Patch Version 1.79' in t else ''))
        out.write(json.dumps(rec) + '\n'); out.flush()
        time.sleep(0.6)
print('done', flush=True)
