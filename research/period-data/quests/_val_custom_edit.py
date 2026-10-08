p = 'validate_quests.py'
s = open(p, encoding='utf-8').read()
def rep(old, new):
    global s
    assert s.count(old) == 1, old[:60]
    s = s.replace(old, new)
rep("""        spawn = (steps_conf[k + 1] or {}).get('Spawn') if k + 1 < len(steps_conf) and steps_conf[k + 1] else None""",
"""        sc = steps_conf[k + 1] if k + 1 < len(steps_conf) and steps_conf[k + 1] else {}
        spawn, custom = sc.get('Spawn'), sc.get('Custom')
        for g in sc.get('Grant') or []:                                  # handed over as the step begins
            if g not in items: p.append(f"step {k + 1}: granted item {g} missing")
            obtained.add(g)
        if custom:
            kind = custom.get('Kind')
            for it in [custom.get('Item')] + list((custom.get('Trades') or {}).keys()) + [v for v in (custom.get('Trades') or {}).values() if v]:
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
            if kind in ('travel',) and not custom.get('Region'): p.append(f"step {k + 1}: travel without a place")""")
rep("""        if base == 8 and f"SEARCH;{k + 1};" not in (r.get('SourceName') or ''): p.append(f"step {k + 1}: search step without area")""",
"""        if base == 8 and not custom and f"SEARCH;{k + 1};" not in (r.get('SourceName') or ''): p.append(f"step {k + 1}: search step without area")""")
rep("""    for dep in [d for d in (r.get('QuestDependency') or '').split('|') if d]:""",
"""    for it in [i for i in (r.get('FinalRewardItemTemplates') or '').split('|') if i]:
        if it not in items: p.append(f"final reward {it} missing")
    for dep in [d for d in (r.get('QuestDependency') or '').split('|') if d]:""")
open(p, 'w', encoding='utf-8').write(s)
print('ok')
