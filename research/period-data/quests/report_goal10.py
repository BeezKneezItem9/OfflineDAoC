"""Goal 10 report page: 1.65-era quests (in the server / missing) and the NPC audit."""
import csv, json, gzip, os, re, html, collections, datetime, sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
BEST = os.path.join(os.path.dirname(HERE), 'bestiary')
ROOT = r"C:/OfflineDAoC"
DB = r"C:/OfflineDAoC/scratch/dbcopy.db"  # lock-free copy of the live DB (cp it first)
OUT = os.path.join(HERE, 'quest-npc-report.html')
E = html.escape

quests = list(csv.DictReader(open(os.path.join(HERE, 'allakhazam_quests.csv'), encoding='utf-8')))
details = {}
for line in open(os.path.join(HERE, 'details.jsonl'), encoding='utf-8'):
    d = json.loads(line); details[int(d['id'])] = dict(start=d['start'], classes=d['classes'], qtype=d['qtype'],
                                                      minlevel=d['minlevel'], maxlevel=d['maxlevel'], note=d['note'])
bp = os.path.join(HERE, 'allakhazam-quests-classic.json.gz')
if os.path.exists(bp):
    for rec in json.loads(gzip.open(bp).read()):
        qid, realm, start, cls, qtype, zones, mn, mx, npcs, related, flag179 = rec
        details[int(qid)] = dict(start=start, classes=cls, qtype=qtype, minlevel=mn, maxlevel=mx, note='1.79' if flag179 else '')

def norm(s):
    s = s.lower()
    s = re.sub(r'\(level \d+\)|\(alb\)|\(mid\)|\(hib\)|-- kill task|xp item', '', s)
    s = re.sub(r'[^a-z ]', '', s)
    return ' '.join(w.rstrip('s') for w in s.split() if w not in ('the', 'of', 'a', 'piece'))

# ---- what the server has --------------------------------------------------------------------------------
SRC = os.path.join(ROOT, r"development-source\server\GameServer")
script_titles = {}
for base in ('scripts/quests', 'quests'):
    for dp, _, fs in os.walk(os.path.join(SRC, base)):
        for f in fs:
            if not f.endswith('.cs'): continue
            t = open(os.path.join(dp, f), encoding='utf-8', errors='replace').read()
            for m in re.finditer(r'questTitle\s*=\s*"([^"]+)"', t):
                script_titles[m.group(1)] = os.path.relpath(os.path.join(dp, f), SRC).replace('\\', '/')
# Shadows50.cs (Guild of Shadows) reuses the Defenders title "Feast of the Decadent" by mistake; its quest is
# the Guild of Shadows level 50 epic, Lord of Deceit.
script_titles['Feast of the Decadent'] = 'scripts/quests/Albion/epic/Defenders50.cs'
script_titles['Lord of Deceit'] = 'scripts/quests/Albion/epic/Shadows50.cs (titled "Feast of the Decadent" in the script by mistake)'
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
dataquests = [r[0] for r in c.execute("select Name from DataQuest")]
dq_norm = {norm(n): n for n in dataquests}
EPIC50 = {'Feast of the Decadent', 'Lord of Deceit', 'Passage to Eternity', 'Symbol of the Broken', 'An End to the Daggers',
          'Saving the Clan', 'The Desire of a God', 'War Concluded', 'Last Heir', 'The Moonstone Twin', 'Unnatural Powers', 'The Horn Twin'}

def era(q, d):
    n = q['name']
    # Allakhazam marks the OLD epic quests with "characters created after Patch Version 1.79 do not receive
    # this Epic quest" (note 1.79): those are the period epics. The "(Epic N)" chains are the 1.79 replacements.
    if re.search(r'\(Epic \d\)', n):
        return 'post', 'Epic 1-9 chain from patch 1.79 (2005)'
    cls = (d or {}).get('classes', '')
    if re.search(r'Mauler|Vampiir|Bainshee|Valewalker|Heretic|Animist|Necromancer|Warlock|Savage|Bonedancer|Valkyrie', cls) and \
       not re.search(r'Armsman|Wizard|Cleric|Warrior|Healer|Druid|Hero|Ranger|Shadowblade|Infiltrator|Thane|Minstrel|Champion|Bard|Mentalist|Runemaster|Spiritmaster|Shaman|Skald|Hunter|Berserker|Friar|Paladin|Mercenary|Reaver|Cabalist|Sorcerer|Theurgist|Scout|Enchanter|Eldritch|Nightshade|Blademaster|Warden', cls):
        return 'post?', 'only for classes added after 1.65 or in Shrouded Isles'
    return 'period', ''

rows = []
for q in quests:
    if q['exp'] not in ('Classic', 'Shrouded Isle expansion') or q['type'] in ('Master Level', 'Artifact', 'Champion'): continue
    d = details.get(int(q['id']))
    e, why = era(q, d)
    n = norm(q['name'])
    base_title = re.sub(r'\s*\(level \d+\)', '', q['name']).strip()
    if base_title in script_titles and (base_title not in EPIC50 or q['level'] in ('48', '50') or q['name'].endswith('(level 50)')):
        status, where = 'in server', script_titles[base_title]
        if base_title in EPIC50 and not q['name'].endswith('(level 50)'):
            status, where = 'missing', f'only the level 50 step exists ({script_titles[base_title]})'
    elif n in dq_norm:
        status, where = 'in server', f'DataQuest "{dq_norm[n]}"'
    else:
        status, where = 'missing', ''
    rows.append(dict(realm=q['realm'], id=q['id'], name=q['name'], level=q['level'], zone=q['zone'], type=q['type'],
                     exp='SI' if q['exp'].startswith('Shrouded') else 'Classic', era=e, why=why, status=status, where=where,
                     start=(d or {}).get('start', ''), classes=(d or {}).get('classes', '')))

period = [r for r in rows if r['era'] == 'period']
post = [r for r in rows if r['era'] != 'period']
have = [r for r in period if r['status'] == 'in server']
miss = [r for r in period if r['status'] != 'in server']
old_epic_ids = {qid for qid, d in details.items() if d.get('note') == '1.79'}
epic_rows = [r for r in period if int(r['id']) in old_epic_ids or re.search(r'\(level \d+\)', r['name']) or
             re.sub(r'\s*\(level \d+\)', '', r['name']) in EPIC50]

ATLAS_QUESTS = sorted(t for t in script_titles if t.startswith('['))
OURS = sorted(t for t, f in script_titles.items() if re.search(r'Bounty|Reputation|Sluagh', f))

npc = list(csv.DictReader(open(os.path.join(BEST, 'npc_audit.csv'), encoding='utf-8')))
npc_counts = collections.Counter(r['origin'].split(':')[0] for r in npc if r['kind'] == 'npc')
atlas_npcs = collections.Counter((r['origin'].split(': ', 1)[1], r['classtype']) for r in npc if r['origin'].startswith('Atlas'))
tele = collections.Counter((r['name'], r['classtype'], r['zone']) for r in npc if r['origin'].startswith('teleporter'))
unver = [r for r in npc if r['origin'].startswith('unverified') and r['kind'] == 'npc']
period_npcs = [r for r in npc if r['origin'].startswith('1.65') and r['kind'] == 'npc']

def table(head, body):
    h = ''.join(f'<th>{E(x)}</th>' for x in head)
    b = ''.join('<tr>' + ''.join(f'<td>{E(str(x))}</td>' for x in row) + '</tr>' for row in body)
    return f'<div class="tw"><table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'

def grouped(items, key, head, cols, label):
    g = collections.defaultdict(list)
    for r in items: g[key(r)].append(r)
    out = []
    for k in sorted(g):
        out.append(f'<details><summary><span>{E(k)}</span><span class="n">{len(g[k])} {label}</span></summary>' +
                   table(head, [cols(r) for r in sorted(g[k], key=lambda r: (int(r["level"] or 0), r["name"]))]) + '</details>')
    return ''.join(out)

stamp = datetime.date.today().isoformat()
page = f'''<title>Classic Quests and NPCs</title>
<style>
/* Layout: one reading column; headline counts, then the class epic picture, then per-realm evidence. */
:root {{
  --bg: #f5f4f0; --panel: #ffffff; --fg: #20231f; --muted: #5f655d; --line: #dadcd4; --accent: #6b4e2f;
  --ok: #2f6b45; --miss: #9b3a2c; --chip: #efe9df;
  --display: "Cormorant Garamond", Georgia, serif; --body: "Source Sans 3", "Segoe UI", system-ui, sans-serif;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg: #151714; --panel: #1c1f1b; --fg: #e6e7e2;
  --muted: #a3a99f; --line: #30352e; --accent: #d7b48a; --ok: #85c79c; --miss: #ef9585; --chip: #2a2620; color-scheme: dark; }} }}
:root[data-theme="dark"] {{ --bg: #151714; --panel: #1c1f1b; --fg: #e6e7e2; --muted: #a3a99f; --line: #30352e;
  --accent: #d7b48a; --ok: #85c79c; --miss: #ef9585; --chip: #2a2620; color-scheme: dark; }}
body {{ background: var(--bg); color: var(--fg); font: 15px/1.55 var(--body); }}
main {{ max-width: 1060px; margin: 0 auto; padding-inline: 16px; padding-block: 28px 64px; display: grid; gap: 28px; }}
h1 {{ font: 600 2.2rem/1.1 var(--display); margin: 0; text-wrap: balance; }}
h2 {{ font: 600 1.45rem/1.2 var(--display); margin: 0 0 8px; text-wrap: balance; }}
p, li {{ max-width: 68ch; }}
.lede {{ color: var(--muted); margin: 6px 0 0; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; }}
.stat {{ background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 12px 14px; }}
.stat b {{ display: block; font: 600 1.7rem/1.1 var(--display); font-variant-numeric: tabular-nums; }}
.stat span {{ color: var(--muted); font-size: .85rem; }}
section {{ display: grid; gap: 10px; min-width: 0; }}
details {{ background: var(--panel); border: 1px solid var(--line); border-radius: 6px; }}
summary {{ cursor: pointer; padding: 9px 14px; display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; }}
summary:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
summary .n {{ color: var(--muted); font-variant-numeric: tabular-nums; }}
.tw {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: .87rem; font-variant-numeric: tabular-nums; }}
th, td {{ text-align: left; padding: 6px 10px; border-top: 1px solid var(--line); vertical-align: top; }}
th {{ font-weight: 600; color: var(--muted); font-size: .78rem; letter-spacing: .03em; text-transform: uppercase; white-space: nowrap; }}
.ok {{ color: var(--ok); font-weight: 600; }} .miss {{ color: var(--miss); font-weight: 600; }}
</style>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600&family=Source+Sans+3:wght@400;600&display=swap">
<main>
<header>
<h1>Classic Quests and NPCs</h1>
<p class="lede">Classic and Shrouded Isles quests from Allakhazam's quest database (start NPC, classes, levels) checked against the server's quest scripts and quest tables, plus every friendly NPC checked against period sightings. Generated {stamp}. Nothing on the server was changed.</p>
</header>
<div class="stats">
<div class="stat"><b>{len(period)}</b><span>period quests listed (Classic + Shrouded Isles)</span></div>
<div class="stat"><b>{len(have)}</b><span>of them present on the server</span></div>
<div class="stat"><b>{len(miss)}</b><span>missing</span></div>
<div class="stat"><b>{len(post)}</b><span>later quests in classic zones (left out)</span></div>
<div class="stat"><b>{len(ATLAS_QUESTS)}</b><span>Atlas repeatable / memorial quests on the server</span></div>
</div>

<section>
<h2>Original class epics</h2>
<p>The pre-1.79 epic lines are guild and class quest chains given by trainers from level 15 up to the level 50 epic armour. The server has only the final level 50 step of each realm's lines (eleven scripts), with the checks for the earlier steps switched off. Every earlier step is missing. The 1.79 "Epic 1–9" chains that start at level 5 replaced these lines after 1.65, so they are listed separately as later content. Two server scripts have no matching row in the bestiary's quest list: Hibernia's Harmony line finale <i>The Horn Twin</i> (scripts/quests/Hibernia/epic/Harmony50.cs) is on the server, and Albion's Guild of Shadows finale (Shadows50.cs) carries the wrong title "Feast of the Decadent" in its script.</p>
{table(['Realm', 'Quest', 'Level', 'Starts at', 'Classes', 'On the server'], [(r['realm'], r['name'], r['level'], r['start'] or r['zone'], r['classes'], (r['where'] or 'no') if r['status'] == 'in server' else ('no — ' + r['where'] if r['where'] else 'no')) for r in sorted(epic_rows, key=lambda r: (r['realm'], r['name'], int(r['level'] or 0)))])}
</section>

<section>
<h2>Period quests on the server</h2>
<p>Quest scripts and DataQuest rows that match a period quest. Most of the matches are the classic "kill task" turn-ins, which Atlas re-entered as XP-item DataQuests.</p>
{table(['Realm', 'Quest', 'Level', 'Type', 'Where on the server'], [(r['realm'], r['name'], r['level'], r['type'], r['where']) for r in sorted(have, key=lambda r: (r['realm'], int(r['level'] or 0)))])}
</section>

<section>
<h2>Missing period quests by realm and zone</h2>
{grouped(miss, lambda r: f"{r['realm']} — {r['zone'] or 'unknown zone'}", ['Quest', 'Level', 'Type', 'Start NPC', 'Classes', 'Expansion'],
         lambda r: (r['name'], r['level'], r['type'], r['start'], r['classes'], r['exp']), 'missing')}
</section>

<section>
<h2>Freeshard quests and our own</h2>
<p><b>Atlas repeatable quests</b> (daily, weekly, monthly, hardcore and memorial; none existed in 1.65):</p>
{table(['Quest', 'Script'], [(t, script_titles[t]) for t in ATLAS_QUESTS])}
<p>Also from Atlas: the Thidranki and Caledonia keep capture and kill quests, and roughly a dozen low-level XP-item turn-ins (levels 5–19) with no period counterpart. Added by this project and not part of the audit: {E(', '.join(OURS) if OURS else 'Bounty Masters, faction emissaries and the Sluaghbinder epic')}.</p>
</section>

<section>
<h2>NPCs</h2>
<p>Every friendly NPC on the server ({sum(npc_counts.values())} rows, keep guards excluded) checked against the NPC names CapnBry's radar recorded in 2002–2004.</p>
{table(['Finding', 'NPCs'], sorted(npc_counts.items(), key=lambda kv: -kv[1]))}
<p><b>From Atlas or later versions</b> (by NPC type):</p>
{table(['What it is', 'Type', 'Count'], [(k[0], k[1], v) for k, v in atlas_npcs.most_common()])}
<p><b>Teleporters</b> (not in 1.65; listed separately as asked):</p>
{table(['Name', 'Type', 'Zone', 'Count'], [(k[0], k[1], k[2], v) for k, v in sorted(tele.items())])}
{grouped(unver, lambda r: r['zone'] or 'unknown zone', ['Name', 'Guild', 'Type', 'Level'], lambda r: (r['name'], r['guild'], r['classtype'], r['level']), 'unverified')}
<p>Unverified means CapnBry has no sighting of that name in that zone; many are period NPCs radar never caught, and some may be freeshard additions. Confirmed period NPCs: {len(period_npcs)}.</p>
</section>

<section>
<h2>Sources and method</h2>
<ul>
<li>Allakhazam (camelot.allakhazam.com) quest lists per realm; each Classic and Shrouded Isles quest page for start NPC, classes, type and levels.</li>
<li>Server: quest scripts (questTitle), the DataQuest table, the task and mission systems. A period quest counts as present when a script title or DataQuest name matches it.</li>
<li>Era: quests named "(Epic N)" or flagged on Allakhazam as replaced in patch 1.79, and quests only for classes outside 1.65, are later content. Trials of Atlantis, Catacombs and later expansions are left out entirely.</li>
<li>NPC check: CapnBry radar lists (capitalized names are NPCs), per zone; class types known to come from Atlas or later; teleporters; this project's own NPCs excluded.</li>
</ul>
</section>
</main>
'''
open(OUT, 'w', encoding='utf-8').write(page)
print('written', OUT, len(page), 'period', len(period), 'have', len(have), 'missing', len(miss), 'post', len(post), 'epic rows', len(epic_rows), 'details', len(details))
