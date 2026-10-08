"""Builds the goal 11 bestiary report page (HTML) from the comparison CSVs plus Illia-only zones."""
import csv, json, re, os, sqlite3, collections, math, html, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:/OfflineDAoC"
DB = os.path.join(ROOT, r"runtime\data\opendaoc.sqlite3.db")
OUT = os.path.join(HERE, 'bestiary-report.html')
E = html.escape

def rows(name): return list(csv.DictReader(open(os.path.join(HERE, name), encoding='utf-8')))
def norm(n): return re.sub(r"\s+", " ", re.sub(r"^(a|an|the) ", "", n.lower().strip()))
def zkey(n): return re.sub(r"[^a-z]", "", n.lower().replace("mountains", "mts").replace("mtns", "mts"))

missing, levels, extra, small, zones = (rows(f) for f in
    ('report_missing.csv', 'report_levels.csv', 'report_server_only.csv', 'report_small_camps.csv', 'report_zones.csv'))
capn = json.load(open(os.path.join(HERE, 'capnbry_zones.json'), encoding='utf-8'))
illia = json.load(open(os.path.join(HERE, 'illia_zones.json'), encoding='utf-8'))

# Darkness Falls monsters that radar users logged under the DF entrance zones are not part of those zones.
df_names = {norm(m['name']) for m in capn.get('249', {}).get('mobs', [])}
missing = [r for r in missing if not (r['zone_id'] in ('0', '100', '200') and r['name'] in df_names)]

# ---- Illia-only zones (no CapnBry data): server vs Illia species ------------------------------------------
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
zrows = c.execute("select ZoneID,RegionID,Name,OffsetX,OffsetY,Width,Height from Zones").fetchall()
zone_by_key = {}
for z in zrows: zone_by_key.setdefault(zkey(z[2]), z)
cap_keys = {zkey(v['name']) for v in capn.values() if v['mobs']}
by_region = collections.defaultdict(list)
for z in zrows: by_region[z[1]].append(z)
server_zone = collections.defaultdict(lambda: collections.defaultdict(list))
for name, region, x, y, level, flags, realm in c.execute("select Name, Region, X, Y, Level, Flags, Realm from Mob"):
    if not name or realm or (flags or 0) & 0x10: continue
    for z in by_region.get(region, []):
        if z[3] * 8192 <= x < (z[3] + z[5]) * 8192 and z[4] * 8192 <= y < (z[4] + z[6]) * 8192:
            server_zone[z[0]][norm(name)].append(level); break
SKIP = {'NPC', 'Merchant', 'Guard', 'Realm Guard', 'Trainer', 'Unknown'}
illia_only = []
for v in illia.values():
    k = zkey(v['name'])
    if k in cap_keys or not v.get('rows') or k not in zone_by_key: continue
    z = zone_by_key[k]
    if z[1] in (250, 251, 252, 253): continue  # battlegrounds handled in their own section
    if z[1] in (10, 101, 201) or zkey(z[2]) in ('camelot', 'jordheim', 'tirnanog', 'avaloncity'): continue  # capitals
    il = {}
    for r in v['rows']:
        if len(r) < 3 or r[2] in SKIP: continue
        m = re.match(r'(\d+)\s*-\s*(\d+)', r[1])
        if m: il[norm(r[0])] = (int(m.group(1)), int(m.group(2)))
    sv = server_zone.get(z[0], {})
    if not il: continue
    miss = sorted(n for n in il if n not in sv)
    lv = []
    for n in sorted(set(il) & set(sv)):
        lo, hi = il[n]
        if hi - lo > 15: continue
        smin, smax = min(sv[n]), max(sv[n])
        gap = max(abs(lo - smin), abs(hi - smax))
        if gap >= 3: lv.append((n, f"{lo}-{hi}", f"{smin}-{smax}", gap))
    illia_only.append(dict(zone=z[2], zone_id=z[0], illia_species=len(il), server_species=len(sv),
                           missing=[(n, f"{il[n][0]}-{il[n][1]}") for n in miss], levels=lv))

# ---- Howth / Connla -------------------------------------------------------------------------------------
towns = {}
for t in ('Howth', 'Connla', 'Mag Mell', 'Tir na mBeo', 'Ardagh'):
    r = c.execute("select X,Y from Teleport where Type='' and RegionID=200 and TeleportID=?", (t,)).fetchone()
    if not r: continue
    mobs = [lv for (x, y, lv, fl) in c.execute("select X,Y,Level,Flags from Mob where Region=200 and Realm=0")
            if not (fl or 0) & 0x10 and math.hypot(x - r[0], y - r[1]) <= 8000]
    towns[t] = (len(mobs), sum(1 for l in mobs if l <= 10), (min(mobs), max(mobs)) if mobs else None)

# ---- totals ---------------------------------------------------------------------------------------------
short = [r for r in small if r['verdict'].startswith('likely short')]
tot_missing = len(missing)
illia_missing = sum(len(z['missing']) for z in illia_only)
confirmed = sum(1 for r in missing if r['illia'] not in ('no', 'no data'))
tot_levels = len(levels)
illia_levels = sum(len(z['levels']) for z in illia_only)
by_zone_missing = collections.defaultdict(list)
for r in missing: by_zone_missing[r['zone']].append(r)

def table(head, body, cls=''):
    h = ''.join(f'<th>{E(x)}</th>' for x in head)
    b = ''.join('<tr>' + ''.join(f'<td>{E(str(x))}</td>' for x in row) + '</tr>' for row in body)
    return f'<div class="tw"><table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'

def agree(r):
    s = 1 + (r['illia'] not in ('no', 'no data')) + (r['uthgard'] == 'yes')
    return s

zone_order = sorted(by_zone_missing, key=lambda z: -len(by_zone_missing[z]))
missing_sections = []
for z in zone_order:
    rs = sorted(by_zone_missing[z], key=lambda r: (-agree(r), r['name']))
    body = [(r['name'], r['capnbry_levels'], r['illia'] if r['illia'] not in ('no data',) else '—', r['uthgard'], f"{agree(r)} of 3") for r in rs]
    missing_sections.append(f'<details><summary><span>{E(z)}</span><span class="n">{len(rs)} missing</span></summary>'
                            + table(['Monster', 'CapnBry levels', "Illia's levels", 'Uthgard lists it', 'Sources agreeing'], body) + '</details>')
illia_sections = []
for z in sorted(illia_only, key=lambda z: -len(z['missing'])):
    if not z['missing'] and not z['levels']: continue
    parts = []
    if z['missing']: parts.append(table(["Monster in Illia's bestiary, not on the server", "Illia's levels"], z['missing']))
    if z['levels']: parts.append(table(['Monster', "Illia's levels", 'Server levels', 'Difference'], z['levels']))
    illia_sections.append(f'<details><summary><span>{E(z["zone"])}</span><span class="n">{len(z["missing"])} missing · {len(z["levels"])} level gaps</span></summary>' + ''.join(parts) + '</details>')

lv_sorted = sorted(levels, key=lambda r: -int(r['difference']))
lv_body = [(r['zone'], r['name'], r['capnbry_levels'], r['server_levels'], r['difference'], r['direction'], r['server_spawns']) for r in lv_sorted]

short_by_zone = collections.Counter(r['zone'] for r in short)
short_examples = sorted(short, key=lambda r: -int(r['capnbry_spawns_seen_nearby']))[:150]
short_body = [(r['zone'], r['name'], r['spawns_in_camp'], r['capnbry_spawns_seen_nearby'], f"{r['local_x']}, {r['local_y']}") for r in short_examples]

extra_by_zone = collections.defaultdict(list)
for r in extra: extra_by_zone[r['zone']].append(r)
extra_sections = []
for z in sorted(extra_by_zone, key=lambda z: -len(extra_by_zone[z])):
    rs = sorted(extra_by_zone[z], key=lambda r: -int(r['server_spawns']))
    extra_sections.append(f'<details><summary><span>{E(z)}</span><span class="n">{len(rs)} species</span></summary>'
                          + table(['Monster', 'Server levels', 'Spawns', 'Uthgard lists it', 'Class'],
                                  [(r['name'], r['server_levels'], r['server_spawns'], r['uthgard'], r['classtypes']) for r in rs]) + '</details>')

zone_body = [(z['zone'], z['capnbry_species'], z['server_species'], z['uthgard_species'] or '—',
              len(by_zone_missing.get(z['zone'], [])), z['level_mismatch'], z['server_only'], z['small_camps_likely_short'])
             for z in sorted(zones, key=lambda z: -len(by_zone_missing.get(z['zone'], [])))]

town_rows = [(t, v[0], v[1], f"{v[2][0]}–{v[2][1]}" if v[2] else '—') for t, v in towns.items()]
silver = [r for r in missing if r['zone_id'] == '201' and r['capnbry_levels'] != 'unknown' and int(r['capnbry_levels'].split('-')[-1]) <= 12]
shannon = [r for r in missing if r['zone_id'] == '202' and r['capnbry_levels'] != 'unknown' and int(r['capnbry_levels'].split('-')[-1]) <= 12]

recs = json.load(open(os.path.join(HERE, 'recommendations.json'), encoding='utf-8')) if os.path.exists(os.path.join(HERE, 'recommendations.json')) else dict(additions=[], fills=[], removals=[], level_fixes=[])
hc = json.load(open(os.path.join(HERE, 'hc_plan.json'), encoding='utf-8')) if os.path.exists(os.path.join(HERE, 'hc_plan.json')) else dict(rows=[], notes=[])
adds = [a for a in recs['additions'] if a['zone_id'] not in (201, 202)]
add_by_zone = collections.defaultdict(list)
for a in adds: add_by_zone[a['zone']].append(a)
add_sections = []
for z in sorted(add_by_zone, key=lambda z: -len(add_by_zone[z])):
    rs = sorted(add_by_zone[z], key=lambda a: (-a['agree'], -a['sightings']))
    body = [(a['name'], a['capnbry_levels'], a['illia'] if a['illia'] not in ('no', 'no data') else '—', a['uthgard'], f"{a['agree']} of 3",
             a['sightings'], '; '.join(f"{k['x']}, {k['y']} ({k['spots']})" for k in a['camps'][:3]), a['source']) for a in rs]
    add_sections.append(f'<details><summary><span>{E(z)}</span><span class="n">{len(rs)} to add</span></summary>'
        + table(['Monster', 'CapnBry levels', "Illia's levels", 'Uthgard', 'Sources', 'CapnBry sightings', 'Main camps (zone-local x, y and spots)', 'Build from'], body) + '</details>')
fills = sorted(recs['fills'], key=lambda f: (-(f['period'] - f['have']), f['zone']))
fill_body = [(f['zone'], f['name'], f['have'], f['period'], f['add'], f"{f['local_x']}, {f['local_y']}") for f in fills]
rem_body = [(r['zone'], r['name'], r['server_levels'], r['spawns'], r.get('elsewhere', '')) for r in sorted(recs['removals'], key=lambda r: (r['zone'], -r['spawns']))]
lvfix_body = [(r['zone'], r['name'], r['server'], r['period'], r['illia'], r['spawns']) for r in recs['level_fixes']]
hc_notes = ''.join(f'<li>{E(n)}</li>' for n in hc['notes'])
stamp = datetime.date.today().isoformat()
page = f'''<title>Classic Bestiary Audit</title>
<style>
/* Layout: one reading column; summary first, then evidence in collapsible per-zone tables. */
:root {{
  --bg: #f6f5f1; --panel: #ffffff; --fg: #1f2421; --muted: #5d655f; --line: #d9ddd6;
  --accent: #2f6b4f; --warn: #a3541b; --crit: #9b2c2c; --chip: #e6efe9;
  --display: "Fraunces", Georgia, serif; --body: "Source Sans 3", "Segoe UI", system-ui, sans-serif;
  --mono: "JetBrains Mono", ui-monospace, Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #141816; --panel: #1b201d; --fg: #e4e8e2; --muted: #a2aba4; --line: #2f3632;
  --accent: #7cc4a0; --warn: #e3a066; --crit: #ef8a8a; --chip: #23302a; color-scheme: dark; }} }}
:root[data-theme="dark"] {{ --bg: #141816; --panel: #1b201d; --fg: #e4e8e2; --muted: #a2aba4; --line: #2f3632;
  --accent: #7cc4a0; --warn: #e3a066; --crit: #ef8a8a; --chip: #23302a; color-scheme: dark; }}
body {{ background: var(--bg); color: var(--fg); font: 15px/1.55 var(--body); }}
main {{ max-width: 1060px; margin: 0 auto; padding-inline: 16px; padding-block: 28px 64px; display: grid; gap: 28px; }}
h1 {{ font: 600 2rem/1.15 var(--display); margin: 0; text-wrap: balance; }}
h2 {{ font: 600 1.3rem/1.25 var(--display); margin: 0 0 8px; text-wrap: balance; }}
h3 {{ font: 600 1.05rem/1.3 var(--body); margin: 14px 0 4px; }}
p, li {{ max-width: 68ch; }}
.lede {{ color: var(--muted); margin: 6px 0 0; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }}
.stat {{ background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 12px 14px; }}
.stat b {{ display: block; font: 600 1.6rem/1.1 var(--display); font-variant-numeric: tabular-nums; }}
.stat span {{ color: var(--muted); font-size: .85rem; }}
section {{ display: grid; gap: 10px; min-width: 0; }}
.callout {{ border-left: 4px solid var(--crit); background: var(--panel); padding: 12px 16px; border-radius: 0 6px 6px 0; }}
details {{ background: var(--panel); border: 1px solid var(--line); border-radius: 6px; }}
summary {{ cursor: pointer; padding: 9px 14px; display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; }}
summary:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
summary .n {{ color: var(--muted); font-variant-numeric: tabular-nums; }}
.tw {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: .88rem; font-variant-numeric: tabular-nums; }}
th, td {{ text-align: left; padding: 6px 10px; border-top: 1px solid var(--line); white-space: nowrap; }}
th {{ font-weight: 600; color: var(--muted); font-size: .78rem; letter-spacing: .03em; text-transform: uppercase; }}
.src li {{ margin-bottom: 4px; }}
code {{ font-family: var(--mono); font-size: .85em; }}
.k {{ display: inline-block; background: var(--chip); color: var(--accent); border-radius: 999px; padding: 1px 8px; font-size: .78rem; }}
</style>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=Source+Sans+3:wght@400;600&family=JetBrains+Mono&display=swap">
<main>
<header>
<h1>Classic Bestiary Audit</h1>
<p class="lede">The server's monster spawns checked against period bestiaries (patch 1.65 era). Generated {stamp} from the live database. Nothing on the server was changed by this report.</p>
</header>
<div class="stats">
<div class="stat"><b>{tot_missing}</b><span>monster species a period source saw in a zone that the server lacks there</span></div>
<div class="stat"><b>{confirmed}</b><span>of the CapnBry gaps also confirmed by Illia's bestiary</span></div>
<div class="stat"><b>{tot_levels}</b><span>species whose server levels differ by 3+ from the period range</span></div>
<div class="stat"><b>{len(short)}</b><span>camps of 1–2 spawns where CapnBry saw 3 or more</span></div>
<div class="stat"><b>{len(extra)}</b><span>server species no period source saw in that zone</span></div>
<div class="stat"><b>{illia_missing}</b><span>more names to review in zones only Illia's bestiary covers (includes named and quest monsters)</span></div>
</div>

<section>
<h2>Hibernia around Howth and Connla</h2>
<div class="callout"><p><b>Confirmed gap.</b> The low-level populations around both towns are missing. There are no monsters at all within 8,000 units of Howth, and Connla's surroundings hold only level 25–30 spawns, while CapnBry, Illia's bestiary and Uthgard all list spraggons, mudmen, water beetles, skeletal pawns, feccans and villainous youths there. CapnBry's own sighting coordinates put feccans and skeletal pawns within 1,400–4,400 units of the two towns.</p></div>
{table(['Town', 'Monsters within 8,000 units', 'Of them level 10 or lower', 'Level range'], town_rows)}
<p>Silvermine Mountains (Howth) is missing {len(silver)} species of level 12 or lower; Shannon Estuary (Connla) is missing {len(shannon)}.</p>
{table(['Zone', 'Monster', 'CapnBry levels', "Illia's levels", 'Uthgard'], [(r['zone'], r['name'], r['capnbry_levels'], r['illia'], r['uthgard']) for r in silver + shannon])}
</section>


<section>
<h2>Recommended changes</h2>
<p>The changes this audit is most confident about. An addition needs CapnBry to have seen the monster in that zone at least three times and at least one other source (Illia's bestiary or Uthgard) to list it there; camps come from CapnBry's own sighting coordinates. Removals are server species that none of the three sources lists in a zone all three cover well. Nothing here has been applied except where it says so.</p>
<h3>Howth and Connla (being added)</h3>
<p>Every species CapnBry recorded at level 15 or lower around the two towns that the server lacks, placed at CapnBry's sighting spots on the navmesh: {len(hc['rows'])} spawns.</p>
<ul>{hc_notes}</ul>
<h3>Add: monsters several sources agree on ({len(adds)})</h3>
{''.join(add_sections)}
<h3>Fill out: camps with 1–2 monsters where the period had a full camp ({len(fills)}, {sum(f['add'] for f in fills)} spawns)</h3>
<p>Only the clear cases: the server has one or two of the monster at the spot and CapnBry saw five or more of it around the same spot. Ordered by how far short the camp is. "Add" tops the camp up to CapnBry's count, at most six. Camps CapnBry saw with three or four are left out here and stay in the full list further down.</p>
{table(['Zone', 'Monster', 'Server spawns', 'CapnBry saw', 'Add', 'Zone-local position'], fill_body)}
<h3>Level fixes ({len(lvfix_body)})</h3>
<p>Server levels five or more away from CapnBry's period range, where Illia's bestiary agrees with CapnBry.</p>
{table(['Zone', 'Monster', 'Server levels', 'CapnBry levels', "Illia's levels", 'Spawns'], lvfix_body)}
<h3>Remove or review ({len(rem_body)})</h3>
<p>Monsters with three or more spawns in a zone where CapnBry, Illia's bestiary and Uthgard all have good coverage and none of them lists the species there. Keep guards, training dummies, Darkness Falls and scripted NPCs are left out. "Seen elsewhere" says whether CapnBry recorded the monster in some other zone, which points to a misplaced spawn rather than an invented one.</p>
{table(['Zone', 'Monster', 'Server levels', 'Spawns', 'Seen elsewhere'], rem_body)}
</section>

<section>
<h2>Zones at a glance</h2>
<p>Zones with CapnBry radar data, ordered by missing species. The old Midgard frontier (Uppland, Yggdra Forest, Jamtland Mountains, Odin's Gate) and Emain Macha carry a fraction of their period populations.</p>
{table(['Zone', 'CapnBry species', 'Server species', 'Uthgard species', 'Missing', 'Level gaps', 'Server-only', 'Short camps'], zone_body)}
</section>

<section>
<h2>Missing monsters by zone</h2>
<p>Species CapnBry recorded in the zone that have no spawn there on the server. <span class="k">3 of 3</span> means CapnBry, Illia's bestiary and Uthgard all list it.</p>
{''.join(missing_sections)}
</section>

<section>
<h2>Zones only Illia's bestiary covers</h2>
<p>Zones CapnBry has no radar data for (Dartmoor, several Shrouded Isles zones and many dungeons), compared with Illia's bestiary. Illia's lists also include named and quest monsters, so these are names to review rather than confirmed gaps. Illia's level ranges merge many years of player reports, so very wide ranges were not used for level checks.</p>
{''.join(illia_sections)}
</section>

<section>
<h2>Level mismatches</h2>
<p>Species present in both, where the server's levels differ from CapnBry's period range by three or more levels.</p>
{table(['Zone', 'Monster', 'CapnBry levels', 'Server levels', 'Difference', 'Direction', 'Server spawns'], lv_body)}
</section>

<section>
<h2>Camps with only one or two monsters</h2>
<p>Server camps of one or two spawns of a species, checked against CapnBry's spawn counts at the same spot. Of {len(small)} such camps, {len(short)} look short (CapnBry saw three or more there), {sum(1 for r in small if r['verdict'].startswith('matches'))} match a small camp CapnBry also saw, {sum(1 for r in small if r['verdict'].startswith('rare'))} are rare or named species, and the rest have no CapnBry sighting at that spot to judge by. The 150 clearest cases:</p>
{table(['Zone', 'Monster', 'Server spawns here', 'CapnBry saw here', 'Zone-local position'], short_body)}
<p>Zones with the most short camps: {E(', '.join(f"{z} ({n})" for z, n in short_by_zone.most_common(12)))}.</p>
</section>

<section>
<h2>Server monsters no period source saw</h2>
<p>Species on the server in zones where CapnBry never recorded them. Some are rare or named spawns radar users missed; others may be later additions or freeshard placements and are worth a second look.</p>
{''.join(extra_sections)}
</section>

<section class="src">
<h2>Sources and method</h2>
<ul>
<li><b>CapnBry's Bestiary</b> (capnbry.net/daoc): radar captures from 2002–2004, names and level ranges per zone, plus sighting coordinates. The primary period source here.</li>
<li><b>Illia's Camelot Bestiary</b> (Allakhazam's DAoC bestiary): per-zone monster lists and level ranges collected from players over many years; used to confirm CapnBry and to cover zones CapnBry lacks.</li>
<li><b>Uthgard 2.0</b> (disorder.dk): a classic freeshard's kill database. Its species lists are used as a third opinion only; its levels and battleground brackets were changed from live and are not used.</li>
<li>Left out: Trials of Atlantis zones and the post-1.80 New Frontiers zones (the server runs Classic and Shrouded Isles with the old frontiers), player pets, mounts, boats and holiday invasion monsters seen by radar.</li>
<li>Server data: every realm-less monster spawn in the Mob table, grouped by zone; levels from the spawn's template range where it has one.</li>
</ul>
</section>
</main>
'''
open(OUT, 'w', encoding='utf-8').write(page)
print('written', OUT, len(page), 'missing', tot_missing, 'confirmed', confirmed, 'levels', tot_levels, 'illia-only zones', len(illia_sections))
