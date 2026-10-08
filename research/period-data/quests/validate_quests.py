"""Goal 10 validator: checks every generated classic quest (dataquest_preview.json + classic-quests.preview.json) against
the rules of DataQuest.cs and the world in the DB copy (plus spawns that apply_world adds). Writes validation.json and
prints a summary. A quest passes only when a player can actually walk it from offer to reward.
  python validate_quests.py"""
import json, os, re, sqlite3, collections

HERE = os.path.dirname(os.path.abspath(__file__))
c = sqlite3.connect("file:C:/OfflineDAoC/scratch/dbcopy.db?mode=ro", uri=True)  # lock-free copy of the live DB
prev = json.load(open(os.path.join(HERE, 'dataquest_preview.json'), encoding='utf-8'))
conf = json.load(open(os.path.join(HERE, 'classic-quests.preview.json'), encoding='utf-8'))
world = json.load(open(os.path.join(HERE, 'world_preview.json'), encoding='utf-8')) if os.path.exists(os.path.join(HERE, 'world_preview.json')) else {'mobs': []}

mobs = collections.defaultdict(set)  # lower name -> regions
for name, region in c.execute("select Name, Region from Mob where (PackageID is null or PackageID <> 'ClassicQuest')"): mobs[name.lower()].add(region)
for m in world.get('mobs', []): mobs[m['Name'].lower()].add(m['Region'])
items = {r[0] for r in c.execute("select Id_nb from ItemTemplate")} | {r['Id_nb'] for r in prev.get('item_rows', [])}
if os.path.exists(os.path.join(HERE, 'reward_item_rows.json')):  # reward equipment built from the period item pages
    items |= {r['Id_nb'] for r in json.load(open(os.path.join(HERE, 'reward_item_rows.json'), encoding='utf-8'))}
quest_names = {r['Name'] for r in prev['rows']} | {r[0] for r in c.execute("select Name from DataQuest")}
SRC = r"C:/OfflineDAoC\development-source\server\GameServer"
for dp, _, fs in os.walk(os.path.join(SRC, 'scripts', 'quests')):
    for f in fs:
        if f.endswith('.cs'):
            for m in re.finditer(r'questTitle\s*=\s*"([^"]+)"', open(os.path.join(dp, f), encoding='utf-8', errors='replace').read()):
                quest_names.add(m.group(1))

def split(v, n):
    parts = (v or '').split('|')
    return parts + [''] * (n - len(parts)) if len(parts) < n else parts

problems = {}
for r in prev['rows']:
    p = []
    types = [int(t) for t in r['StepType'].split('|')]
    n = len(types)
    targets, stepitems, collect, advance = split(r['TargetName'], n), split(r['StepItemTemplates'], n), split(r.get('CollectItemTemplate'), n), split(r.get('AdvanceText'), n)
    steps_conf = (conf['Quests'].get(str(r['ID'])) or {}).get('Steps') or []
    if r['StartRegionID'] not in mobs.get(r['StartName'].lower(), set()):
        p.append(f"giver {r['StartName']} not in region {r['StartRegionID']}")
    chat_lines = ' '.join((conf.get('Chat') or {}).get(r['StartName'], {}).values())
    if not r.get('AcceptText') or f"[{r['AcceptText']}]" not in (r.get('Description') or '') + ' ' + chat_lines:
        p.append("no clickable accept keyword in the offer or its conversation")
    elif f"[{r['AcceptText']}]" not in (r.get('Description') or ''):
        # reachable only through the chain: every keyword of the offer must lead somewhere
        for kw in re.findall(r'\[([^\]]+)\]', r.get('Description') or ''):
            if kw != r['AcceptText'] and kw not in (conf.get('Chat') or {}).get(r['StartName'], {}):
                p.append(f"offer keyword [{kw}] has no reply"); break
    if types[-1] % 2 == 0 and types[-1] != 8 or types[-1] in (8,) :
        if types[-1] not in (1, 3, 5, 7, 9, 11): p.append(f"last step type {types[-1]} is not a finish type")
    obtained = set()
    for k, t in enumerate(types):
        base = t - (t % 2) if t != 0 else 0
        base = {0: 0, 1: 0, 2: 2, 3: 2, 4: 4, 5: 4, 6: 6, 7: 6, 8: 8, 9: 8, 10: 10, 11: 10}[t]
        name, _, reg = targets[k].partition(';')
        sc = steps_conf[k + 1] if k + 1 < len(steps_conf) and steps_conf[k + 1] else {}
        spawn, custom = sc.get('Spawn'), sc.get('Custom')
        for g in sc.get('Grant') or []:                                  # handed over as the step begins
            if g not in items: p.append(f"step {k + 1}: granted item {g} missing")
            obtained.add(g)
        if custom:
            kind = custom.get('Kind')
            for it in [custom.get('Item')] + list((custom.get('Trades') or {}).keys()) + [v for v in (custom.get('Trades') or {}).values() if v] + list((custom.get('Choices') or {}).values()):
                if it and it not in items: p.append(f"step {k + 1}: {kind} item {it} missing")
            if kind in ('use_item', 'has_item') and custom.get('Item') not in obtained and not custom.get('Give'):
                p.append(f"step {k + 1}: {kind} item {custom.get('Item')} is never given")
            if kind in ('use_item', 'has_item') and custom.get('Item'): obtained.add(custom['Item'])
            if kind == 'trade':
                if not mobs.get((custom.get('Target') or '').lower()): p.append(f"step {k + 1}: trade npc {custom.get('Target')} missing")
                dropped = {d['Item'] for d in custom.get('Drops') or [] if mobs.get(d['Mob'].lower())}
                for d in custom.get('Drops') or []:
                    if not mobs.get(d['Mob'].lower()): p.append(f"step {k + 1}: drop monster {d['Mob']} missing")
                if not any(i in obtained or i in dropped for i in custom.get('Trades') or {}): p.append(f"step {k + 1}: no trade item is obtainable")
                obtained.update(v for v in (custom.get('Trades') or {}).values() if v)
            if kind == 'quest':
                for qn in custom.get('Quest', '').split('|'):
                    if qn not in quest_names: p.append(f"step {k + 1}: needs unknown quest '{qn}'")
            if kind == 'die_to' and not mobs.get((custom.get('Target') or '').lower()): p.append(f"step {k + 1}: killer {custom.get('Target')} missing")
            if kind in ('travel', 'say') and not custom.get('Region'): p.append(f"step {k + 1}: {kind} without a place")
            if kind == 'say' and not custom.get('Words'): p.append(f"step {k + 1}: say without words")
        if base in (0, 2, 4, 6, 10):
            if not name:
                p.append(f"step {k + 1}: no target")
            elif not spawn and (reg and int(reg) not in mobs.get(name.lower(), set()) and int(reg) != 0 or not mobs.get(name.lower())):
                p.append(f"step {k + 1}: target {name} not in region {reg}")
        item = stepitems[k].split(';')[0]
        if item and item not in items: p.append(f"step {k + 1}: item {item} missing")
        if base == 0 and item: obtained.add(item)                       # kill drop
        if base == 8 and item: obtained.add(item)                       # search find
        if base == 4 and item: obtained.add(item)                       # talk gives
        if base == 2:                                                   # delivery: item handed over at step start
            if not item and not collect[k]: p.append(f"step {k + 1}: delivery without an item")
            obtained.add(item or collect[k])
        if base in (2, 10):
            need = collect[k]
            if not need: p.append(f"step {k + 1}: turn-in without CollectItemTemplate")
            elif need not in obtained and need not in items: p.append(f"step {k + 1}: turn-in item {need} missing")
            elif need not in obtained: p.append(f"step {k + 1}: turn-in item {need} is never given or dropped earlier")
        if base == 6 and not advance[k]: p.append(f"step {k + 1}: whisper step without keyword")
        if base == 8 and not custom and f"SEARCH;{k + 1};" not in (r.get('SourceName') or ''): p.append(f"step {k + 1}: search step without area")
    for it in [i for i in (r.get('FinalRewardItemTemplates') or '').split('|') if i]:
        if it not in items: p.append(f"final reward {it} missing")
    for dep in [d for d in (r.get('QuestDependency') or '').split('|') if d]:
        if dep not in quest_names: p.append(f"requires unknown quest '{dep}'")
    if p: problems[r['ID']] = {'name': r['Name'], 'realm': r['realm'], 'problems': p}

json.dump(problems, open(os.path.join(HERE, 'validation.json'), 'w', encoding='utf-8'), indent=1)
kinds = collections.Counter(re.sub(r"step \d+: |'[^']*'|\b[A-Za-z_]*cq_\S+|target .* not in region \d+|giver .* not in", lambda m: m.group(0)[:6] if m.group(0).startswith('step') else '#', x)
                            for v in problems.values() for x in v['problems'])
print(f"quests {len(prev['rows'])} pass {len(prev['rows']) - len(problems)} fail {len(problems)}")
for k, v in kinds.most_common(20): print(f"  {v:4} {k}")
