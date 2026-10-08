"""One-off edit: quest rewards (fixed items, per-class rows, choose-one steps) in gen_dataquests.py."""
p = 'gen_dataquests.py'
s = open(p, encoding='utf-8').read()


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:70]
    s = s.replace(old, new)


rep("""rows, items, skipped = [], {}, Counter()""", r'''import rewards as RW
# Period classes per realm (Catacombs and later classes have no trainer here; Sluaghbinder takes only its own line).
REALM_CLASSES = {
    'Albion': ['Paladin', 'Armsman', 'Scout', 'Minstrel', 'Theurgist', 'Cleric', 'Wizard', 'Sorcerer', 'Infiltrator', 'Friar',
               'Mercenary', 'Necromancer', 'Cabalist', 'Reaver', 'Fighter', 'Acolyte', 'AlbionRogue', 'Mage', 'Elementalist', 'Disciple'],
    'Midgard': ['Thane', 'Warrior', 'Shadowblade', 'Skald', 'Hunter', 'Healer', 'Spiritmaster', 'Shaman', 'Runemaster',
                'Bonedancer', 'Berserker', 'Savage', 'Viking', 'Mystic', 'Seer', 'MidgardRogue'],
    'Hibernia': ['Eldritch', 'Enchanter', 'Mentalist', 'Blademaster', 'Hero', 'Champion', 'Warden', 'Druid', 'Bard', 'Nightshade',
                 'Ranger', 'Animist', 'Valewalker', 'Guardian', 'Naturalist', 'Stalker', 'Magician', 'Forester'],
}
ID_CLASS = {v: k for k, v in CLASS_IDS.items()}
REWARD_ITEMS = {}  # item id -> {'name', 'realm', 'quests'} for the reward item builder
LEDGER_REWARDS = []  # reward entries the walkthrough left unrecorded

STEP_FIELDS = ('StepType', 'TargetName', 'StepItemTemplates', 'CollectItemTemplate', 'AdvanceText', 'SourceText', 'TargetText',
               'StepText', 'RewardMoney', 'RewardXP')

def reward_id(name, realm):
    return 'cq_' + re.sub(r'[^a-z0-9]+', '_', (realm[:3] + ' ' + name).lower()).strip('_')[:60]

def add_choose_step(row, names, npc, region):
    """A last step at the NPC who ends the quest: it names the rewards as keywords; whispering one gives that item."""
    choices, keys = {}, {}
    for n in names:
        key = RW.display_name(n)
        if key in keys.values(): key = n
        keys[n] = key
        choices[key] = reward_id(n, row['realm'])
        REWARD_ITEMS.setdefault(choices[key], {'name': RW.display_name(n), 'full': n, 'realm': row['realm'], 'quests': set()})['quests'].add(row['Name'])
    f = {k: (row.get(k) or '').split('|') for k in STEP_FIELDS}
    n = len(f['StepType'])
    for k in f:
        f[k] += [''] * (n - len(f[k]))
    last = int(f['StepType'][-1])
    if last % 2 == 1: f['StepType'][-1] = str(last - 1)
    money, xp = f['RewardMoney'][-1] or '0', f['RewardXP'][-1] or '0'
    f['RewardMoney'][-1], f['RewardXP'][-1] = '0', '0'
    f['StepType'].append('9')
    f['TargetName'].append(f"{npc};{region}")
    for k in ('StepItemTemplates', 'CollectItemTemplate', 'AdvanceText', 'TargetText'): f[k].append('')
    listing = ', '.join(f"[{k}]" for k in choices)
    # Placeholder line (the walkthroughs do not record the period wording of the reward choice); listed in the ledger.
    f['SourceText'].append(f"Choose your reward: {listing}.")
    f['StepText'].append(f"Choose your reward: whisper {npc} the name of the item you want ({', '.join(choices)}).")
    f['RewardMoney'].append(money)
    f['RewardXP'].append(xp)
    for k in f: row[k] = '|'.join(f[k])
    row['_markers'].append(row['_markers'][-1] if row['_markers'] else None)
    row['_spawns'].append(None)
    row['_custom'].append({'Kind': 'choose', 'Target': npc, 'Choices': choices})
    row['_grants'].append(None)

def apply_rewards(row, spec, cls):
    fixed, groups = RW.reward_plan(spec, cls, row['StartName'])
    ids = [i for i in (row.get('FinalRewardItemTemplates') or '').split('|') if i]
    for n in fixed:
        iid = reward_id(n, row['realm'])
        REWARD_ITEMS.setdefault(iid, {'name': RW.display_name(n), 'full': n, 'realm': row['realm'], 'quests': set()})['quests'].add(row['Name'])
        ids.append(iid)
    row['FinalRewardItemTemplates'] = '|'.join(dict.fromkeys(ids))
    if groups:
        last_target = (row['TargetName'].split('|')[-1] or '').split(';')
        npc, region = (last_target[0], last_target[1]) if last_target[0] else (row['StartName'], row['StartRegionID'])
        for g in groups: add_choose_step(row, g, npc, region)
    return row

def copy_row(row, **over):
    out = dict(row, **over)
    for k in ('_markers', '_named', '_spawns', '_custom', '_grants'): out[k] = list(row[k])
    return out

rows, items, skipped = [], {}, Counter()''')

rep("""            per = dict(row, StartName=t['name'], StartRegionID=t['region'], AllowedClasses=str(cid),
                       _markers=list(row['_markers']), _named=list(row['_named']), _spawns=list(row['_spawns']),
                       _custom=list(row['_custom']), _grants=list(row['_grants']))
            rows.append(per)
        continue
    rows.append(row)""", """            per = copy_row(row, StartName=t['name'], StartRegionID=t['region'], AllowedClasses=str(cid))
            rows.append(apply_rewards(per, q['spec'], t.get('cls') or cls))
        continue
    LEDGER_REWARDS.extend((q['spec']['name'], m) for m in RW.dropped_markers(q['spec']))
    keyed = RW.class_keys(q['spec'].get('rewards') or {})
    if keyed:
        # Rewards differ by class: a row per listed class, and one for the realm's other classes allowed the quest.
        allowed = [ID_CLASS[int(c)] for c in row['AllowedClasses'].split('|') if c] or REALM_CLASSES.get(q['realm'], [])
        rogue = {'Rogue': {'Albion': 'AlbionRogue', 'Midgard': 'MidgardRogue', 'Hibernia': 'Stalker'}.get(q['realm'])}
        keyed = {rogue.get(k, k) for k in keyed}
        mine = [c for c in allowed if c in keyed]
        rest = [c for c in allowed if c not in keyed]
        for c in mine:
            rows.append(apply_rewards(copy_row(row, AllowedClasses=str(CLASS_IDS[c])), q['spec'], c))
        if rest:
            rows.append(apply_rewards(copy_row(row, AllowedClasses='|'.join(str(CLASS_IDS[c]) for c in rest)), q['spec'], None))
        continue
    rows.append(apply_rewards(row, q['spec'], None))""")

rep("""json.dump({'rows': rows, 'items': items, 'dupes': dupes}, open(""", """for v in REWARD_ITEMS.values(): v['quests'] = sorted(v['quests'])
json.dump({'items': REWARD_ITEMS, 'unrecorded': LEDGER_REWARDS}, open(os.path.join(HERE, 'reward_items_needed.json'), 'w', encoding='utf-8'), indent=1)
print(f"reward items needed={len(REWARD_ITEMS)} unrecorded reward entries={len(LEDGER_REWARDS)}")
json.dump({'rows': rows, 'items': items, 'dupes': dupes}, open(""")
open(p, 'w', encoding='utf-8').write(s)
print('ok')
