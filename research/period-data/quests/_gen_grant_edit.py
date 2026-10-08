"""One-off edit: every item a step hands over (an NPC's gift in conversation, a turn-in's gift, a named monster's drop)
reaches the player: DataQuest's own step item where the step type gives one, else ClassicQuests grants it on the next
step, else (last step) it is a final reward."""
p = 'gen_dataquests.py'
s = open(p, encoding='utf-8').read()


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:70]
    s = s.replace(old, new)


rep("""            gives = sp.get('gives')
            steps.append([4, target, '', text, sp.get('say', '')])
            if gives: items[item_id(gives)] = gives""", """            steps.append([4, target, '', text, sp.get('say', '')])""")

rep("""            steps.append([8, '', sp.get('gives') and item_id(sp['gives']) or '', text, '', None, None, None, area])
            if sp.get('gives'): items[item_id(sp['gives'])] = sp['gives']""",
    """            steps.append([8, '', '', text, '', None, None, None, area])""")

rep("""        for k in range(start, len(steps)):
            # A group ("two youths") all appear on its first step; the later steps only respawn one if it went missing.""",
    """        spans.append((start, len(steps)))
        for k in range(start, len(steps)):
            # A group ("two youths") all appear on its first step; the later steps only respawn one if it went missing.""")

rep("""    advance = {}  # step index -> whispered keyword (DataQuest AdvanceText)""",
    """    advance = {}  # step index -> whispered keyword (DataQuest AdvanceText)
    spans = []  # plan step -> (first, end) generated step indexes""")

rep("""    if not steps: return None, items
    steps[-1][0] += 1  # the last step finishes the quest (each *Finish type is base + 1)""",
    """    if not steps: return None, items
    # Gifts: what each step hands the player. The next step being a delivery of it: DataQuest gives it as that step
    # begins. Else the step's own item slot (kill, talk, whisper, search, scripted steps give it on completion). The
    # rest: granted on the next step by ClassicQuests (and again if lost). The last step's gifts are final rewards.
    grants, final_items = {}, []
    for i, s in enumerate(plan):
        if i >= len(spans): break
        a, b = spans[i]
        if a == b: continue
        sp, t = s['spec'], s.get('target') or {}
        gifts = []
        for g in (sp.get('gives'), sp.get('drop') if s['do'] == 'kill' else None, sp.get('drops') if s['do'] == 'kill' else None):
            gifts += g if isinstance(g, list) else [g]
        if s['do'] == 'deliver' and sp.get('returns_item') and sp.get('item'): gifts.append(sp['item'])
        gifts = [g for g in dict.fromkeys(gifts) if isinstance(g, str) and g.strip() and not re.match(r'(coin|xp)\\b', g, re.I)
                 and not g.startswith('<')]
        if not gifts: continue
        for g in gifts: items[item_id(g)] = g
        nxt = steps[b] if b < len(steps) else None
        if nxt and nxt[0] in (2, 3):
            gifts = [g for g in gifts if item_id(g) != nxt[2]]
        if b == len(steps):
            final_items += [item_id(g) for g in gifts]
            continue
        last = steps[b - 1]
        if gifts and last[0] in (0, 4, 6, 8) and not last[2]:
            last[2] = item_id(gifts.pop(0))
        if gifts:
            grants[b] = ([item_id(g) for g in gifts], t.get('name') if s['do'] in ('talk', 'deliver', 'whisper', 'interact') and t else None)
    steps[-1][0] += 1  # the last step finishes the quest (each *Finish type is base + 1)""")

rep("""        '_custom': [s[9] if len(s) > 9 else None for s in steps],""",
    """        '_custom': [s[9] if len(s) > 9 else None for s in steps],
        '_grants': [grants.get(k) for k in range(len(steps))],
        'FinalRewardItemTemplates': '|'.join(dict.fromkeys(final_items)),""")

rep("""                       _custom=list(row['_custom']))""", """                       _custom=list(row['_custom']), _grants=list(row['_grants']))""")

rep("""    customs = r.pop('_custom')""", """    customs = r.pop('_custom')
    grants = r.pop('_grants')""")

rep("""        if customs[k]:
            info['Custom'] = customs[k]""", """        if customs[k]:
            info['Custom'] = customs[k]
        if grants[k]:
            info['Grant'] = grants[k][0]
            if grants[k][1]: info['GrantFrom'] = grants[k][1]""")

open(p, 'w', encoding='utf-8').write(s)
print('ok')
