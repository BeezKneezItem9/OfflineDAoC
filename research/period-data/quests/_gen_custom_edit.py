"""One-off edit: scripted step kinds (use_item, travel, trade, quest, group, die_to...) in gen_dataquests.py."""
p = 'gen_dataquests.py'
s = open(p, encoding='utf-8').read()


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:60]
    s = s.replace(old, new)


rep("""SIMPLE = {'talk', 'kill', 'deliver', 'whisper', 'search', 'collect'}""",
    """SIMPLE = {'talk', 'kill', 'deliver', 'whisper', 'search', 'collect'}
# Steps DataQuest has no type for: a journal step (Search, no search area) that ClassicQuests completes on its trigger.
CUSTOM = {'use_item', 'drop_item', 'travel', 'buy', 'trade', 'event', 'interact', 'quest', 'subquests', 'group', 'die_to'}""")

rep("""def ready(q):
    if q.get('giver') is None: return False
    for s in q['steps']:
        if s['do'] not in SIMPLE: return False""", """def ready(q):
    if q.get('giver') is None: return False
    for i, s in enumerate(q['steps']):
        if s['do'] in CUSTOM:
            if custom_step(q, s, i) is None: return False
            continue
        if s['do'] not in SIMPLE: return False""")

rep("""DIALOGUE = json.load(""", r'''def strip_name(n):
    return re.sub(r'\s*\(.*?\)\s*$', '', n or '').strip()

def produced_before(q, i, item):
    """Does an earlier step put this item in the player's hands?"""
    low = (item or '').lower()
    for p in q['steps'][:i]:
        sp = p['spec']
        got = [sp.get('item') if p['do'] == 'collect' else None, sp.get('drop'), sp.get('drops'), sp.get('gives'),
               *(sp.get('trades') or {}).values()]
        if p['do'] == 'deliver' and (sp.get('returns_item') or sp.get('gives')): got.append(sp.get('item'))
        if any(g and g.lower() == low for g in got if isinstance(g, str)): return True
    return False

def place(s, radius=600):
    """Where a scripted step happens: the walkthrough's point, else anywhere in the named zone (its bounds as a circle)."""
    m = s.get('marker') or {}
    sp = s['spec']
    if m.get('region') is not None and m.get('x') is not None:
        return {'Region': m['region'], 'X': m['x'], 'Y': m['y'], 'Z': m.get('z') or 0, 'Radius': int(sp.get('radius') or radius)}
    za = s.get('zone_area')
    if za: return {'Region': za['region'], 'X': za['x'], 'Y': za['y'], 'Z': 0, 'Radius': za['radius']}
    return None

READ_ONLY = re.compile(r'letter|journal|note|scroll|book|map|diary|tome|page|axe|charm', re.I)
NO_ITEM = re.compile(r'(coin|xp|\+|\s)+')

def custom_step(q, s, i):
    """(step type, target, step item, custom trigger) for a scripted step, or None when the data is not there."""
    sp, t = s['spec'], s.get('target') or {}
    kind = s['do']
    target = f"{t['name']};{t['region']}" if t else ''
    if kind in ('use_item', 'drop_item') or (kind == 'interact' and not t):
        item = sp.get('item') or sp.get('item_from_giver') or (sp.get('consumes') or [None])[0]
        if not item: return None
        where = place(s, 400 if kind == 'drop_item' else 600)
        if kind == 'interact' and sp.get('npc', '').startswith('<') and not where: return None
        c = {'Kind': 'use_item', 'Item': item_id(item),
             'Consume': kind == 'drop_item' or bool(sp.get('consumes')) or not READ_ONLY.search(item),
             'Give': not produced_before(q, i, item), '_item': item}
        if where and (s.get('marker') or sp.get('zone')): c.update(where)
        return (8, '', item_id(sp['gives']) if sp.get('gives') else '', c)
    if kind == 'interact':  # "read the scrolls and tell Masrim": a conversation with the named NPC
        return (4, target, '', None)
    if kind == 'travel' or (kind == 'event' and not sp.get('npc')):
        where = place(s, 500)
        if not where: return None
        return (8, '', '', dict(where, Kind='travel'))
    if kind == 'event':  # a monster that appears for the player: a kill step with an event spawn
        return (0, '', '', None) if event_spawn(q, s) else None
    if kind == 'buy':
        item = sp.get('item')
        if not item: return None
        # No merchant on this server sells it (checked: Ludlow has no barkeep or ale): the quest hands it over (ledger).
        return (8, '', '', {'Kind': 'has_item', 'Item': item_id(item), 'Give': True, '_item': item})
    if kind == 'trade':
        if not t or not sp.get('trades'): return None
        trades = {item_id(k): ('' if NO_ITEM.fullmatch(v or '') else item_id(v)) for k, v in sp['trades'].items()}
        names = {item_id(k): k for k in sp['trades']}
        names.update({item_id(v): v for v in sp['trades'].values() if not NO_ITEM.fullmatch(v or '')})
        c = {'Kind': 'trade', 'Target': t['name'], 'Trades': trades, '_items': names}
        if sp.get('from'):
            c['Drops'] = [{'Mob': m, 'Item': item_id(k), 'Chance': int(sp.get('chance') or 50)} for m in sp['from'] for k in sp['trades']]
        return (8, target, '', c)
    if kind in ('quest', 'subquests'):
        names = [sp['quest']] if kind == 'quest' else (sp.get('in_order') or sp.get('of') or [])
        names = list(dict.fromkeys(strip_name(x) for n in names for x in n.split(' | ')))
        if not names: return None
        return (8, '', '', {'Kind': 'quest', 'Quest': '|'.join(names), 'Count': int(sp.get('pick') or 0)})
    if kind == 'group':
        return (8, '', '', {'Kind': 'group'})
    if kind == 'die_to':
        if not sp.get('npc'): return None
        return (8, target, '', {'Kind': 'die_to', 'Target': t.get('name') or sp['npc']})
    return None

DIALOGUE = json.load(''')

rep("""        elif s['do'] == 'search':""", """        elif s['do'] in CUSTOM:
            stype, ctarget, citem, custom = custom_step(q, s, i)
            if custom:
                if custom.get('_item'): items[custom['Item']] = custom.pop('_item')
                for iid, nm in (custom.pop('_items', None) or {}).items(): items[iid] = nm
            if citem: items[citem] = sp['gives']
            if stype == 0:  # an event monster: killed like any other, spawned for the player
                ev = event_spawn(q, s)
                steps.append([0, f"{ev['Name']};{ev['Region']}", '', text, ''])
            elif stype == 4:
                steps.append([4, ctarget, '', text, sp.get('say', '')])
            else:
                steps.append([8, ctarget, citem, text, '', None, None, None, None, custom])
        elif s['do'] == 'search':""")

rep("""        spawn = event_spawn(q, s) if s['do'] in ('kill', 'collect') else None""",
    """        spawn = event_spawn(q, s) if s['do'] in ('kill', 'collect', 'event') else None""")

rep("""        '_markers': [s[5] for s in steps], '_named': [s[6] for s in steps if s[6]], '_spawns': [s[7] for s in steps],""",
    """        '_markers': [s[5] for s in steps], '_named': [s[6] for s in steps if s[6]], '_spawns': [s[7] for s in steps],
        '_custom': [s[9] if len(s) > 9 else None for s in steps],""")

rep("""                       _markers=list(row['_markers']), _named=list(row['_named']), _spawns=list(row['_spawns']))""",
    """                       _markers=list(row['_markers']), _named=list(row['_named']), _spawns=list(row['_spawns']),
                       _custom=list(row['_custom']))""")

rep("""    spawns = r.pop('_spawns')""", """    spawns = r.pop('_spawns')
    customs = r.pop('_custom')""")

rep("""        steps_out.append(info)""", """        if customs[k]:
            info['Custom'] = customs[k]
        steps_out.append(info)""")

open(p, 'w', encoding='utf-8').write(s)
print('ok')
