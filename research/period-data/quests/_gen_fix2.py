p = 'gen_dataquests.py'
s = open(p, encoding='utf-8').read()

# 1. Accept keyword: a word of the NPC's own offer, bracketed (owner: no generic "Will you help? [Quest Name]").
old = """        # StartType 0 (Standard) starts on a whispered AcceptText; the clickable [name] in the offer whispers it.
        # (Without it the offer had no way to accept: owner test at Mandra, 2026-10-07.)
        'Description': (spec.get('offer', '').rstrip() + f" Will you help? [{spec['name']}]").strip(),
        'AcceptText': spec['name'], 'StepType':"""
new = """        # StartType 0 (Standard) starts on a whispered AcceptText. Owner 2026-10-07: no generic "Will you help?"; a word of
        # the NPC's own offer is the clickable keyword, even if it is not the period one.
        'Description': offer_text, 'AcceptText': accept_word, 'StepType':"""
assert s.count(old) == 1; s = s.replace(old, new)

old = """    if not steps: return None, items
    steps[-1][0] += 1  # the last step finishes the quest (each *Finish type is base + 1)"""
new = """    if not steps: return None, items
    steps[-1][0] += 1  # the last step finishes the quest (each *Finish type is base + 1)
    offer_text, accept_word = accept_keyword(spec)
    search_areas = []
    for i, st in enumerate(steps):
        if st[0] in (8, 9) and st[8]:
            a = st[8]
            search_areas.append(f"SEARCH;{i + 1};{a['text']};{a['region']};{a['x']};{a['y']};{a['radius']};{a['seconds']}")"""
assert s.count(old) == 1; s = s.replace(old, new)

# 2. Search steps carry their area (DataQuest SourceName SEARCH entries); everything else None at index 8.
old = """        elif s['do'] == 'search':
            steps.append([8, '', '', text, ''])"""
new = """        elif s['do'] == 'search':
            m = s.get('marker') or {}
            area = None
            if m.get('x') is not None and m.get('region') is not None:
                area = {'text': (sp.get('found') or '').replace(';', ',').replace('|', '/'), 'region': m['region'], 'x': m['x'],
                        'y': m['y'], 'radius': int(sp.get('radius') or 300), 'seconds': int(sp.get('seconds') or 5)}
            steps.append([8, '', sp.get('gives') and item_id(sp['gives']) or '', text, '', None, None, None, area])
            if sp.get('gives'): items[item_id(sp['gives'])] = sp['gives']"""
assert s.count(old) == 1; s = s.replace(old, new)

old = """            per = dict(spawn, Count=len(steps) - start if k == start else 1) if spawn else None
            steps[k] += [marker, named, per]"""
new = """            per = dict(spawn, Count=len(steps) - start if k == start else 1) if spawn else None
            if len(steps[k]) > 5:  # search steps already carry their slots
                steps[k][5:8] = [marker, named, per]
            else:
                steps[k] += [marker, named, per, None]"""
assert s.count(old) == 1; s = s.replace(old, new)

# 3. Item slots: collect turn-ins are not given on completion; deliveries are given at step start (DataQuest).
old = """        'TargetName': '|'.join(s[1] for s in steps), 'StepItemTemplates': '|'.join(s[2] for s in steps),"""
new = """        'TargetName': '|'.join(s[1] for s in steps),
        'StepItemTemplates': '|'.join('' if s[0] in (10, 11) else s[2] for s in steps),
        'SourceName': '|'.join(search_areas),"""
assert s.count(old) == 1; s = s.replace(old, new)

# helper
old = """def build(q):
    spec = q['spec']"""
new = """STOP = set('that this with from have your they them their there what when will would could should about into some just been were very much more only than then also over such need here help come back know make take tell look good well like want'.split())

def accept_keyword(spec):
    \"\"\"Offer text with one of its own words bracketed as the accept keyword: the recorded chain's last keyword when the
    walkthrough has one, else the longest plain word of the offer (later wins ties), else a word of the quest name.\"\"\"
    import re as _re
    offer = (spec.get('offer') or '').strip()
    chosen = (spec.get('accept_keyword') or '').strip()
    if chosen and chosen.lower() in offer.lower():
        i = offer.lower().index(chosen.lower())
        return offer[:i] + '[' + offer[i:i + len(chosen)] + ']' + offer[i + len(chosen):], offer[i:i + len(chosen)]
    words = [(m.start(), m.group(0)) for m in _re.finditer(r"[A-Za-z][A-Za-z'-]{3,}", offer) if m.group(0).lower() not in STOP]
    if words:
        pos, word = max(words, key=lambda w: (len(w[1]), w[0]))
        return offer[:pos] + '[' + word + ']' + offer[pos + len(word):], word
    word = max(_re.findall(r"[A-Za-z][A-Za-z'-]{2,}", spec['name']) or [spec['name']], key=len)
    return (offer + (' ' if offer else '') + '[' + word + ']').strip(), word

def build(q):
    spec = q['spec']"""
assert s.count(old) == 1; s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
