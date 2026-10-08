p = 'gen_dataquests.py'
s = open(p, encoding='utf-8').read()

old = """    steps = []  # (type, target "name;region", item template, step text, target text, marker, named mob id)
    items = {}"""
new = """    steps = []  # (type, target "name;region", item template, step text, target text, marker, named mob id)
    items = {}
    advance = {}  # step index -> whispered keyword (DataQuest AdvanceText)"""
assert s.count(old) == 1; s = s.replace(old, new)

old = """        elif s['do'] == 'whisper':
            steps.append([6, target, '', text, sp.get('say', '')])"""
new = """        elif s['do'] == 'whisper':
            keyword = (sp.get('keyword') or sp.get('whisper') or '').strip()
            # The journal names the words to whisper (journal text, not NPC speech).
            steps.append([6, target, '', text + (f" (whisper: {keyword})" if keyword else ''), sp.get('say', '')])
            advance[len(steps) - 1] = keyword"""
assert s.count(old) == 1; s = s.replace(old, new)

old = """        'TargetName': '|'.join(s[1] for s in steps), 'StepItemTemplates': '|'.join(s[2] for s in steps),"""
new = """        'TargetName': '|'.join(s[1] for s in steps), 'StepItemTemplates': '|'.join(s[2] for s in steps),
        # Turn-ins: DataQuest ignores a handed item unless CollectItemTemplate lists it for the step (owner: Troya never
        # took the larva skin). Whisper steps advance on AdvanceText.
        'CollectItemTemplate': '|'.join(s[2].split(';')[0] if s[0] in (2, 3, 10, 11) else '' for s in steps),
        'AdvanceText': '|'.join(advance.get(i, '') for i in range(len(steps))),"""
assert s.count(old) == 1; s = s.replace(old, new)

old = """Durability=50000, MaxDurability=50000, Condition=50000, MaxCondition=50000, IsPickable=1, IsDropable=0,"""
new = """Durability=50000, MaxDurability=50000, Condition=50000, MaxCondition=50000, IsPickable=1, IsDropable=1,"""
assert s.count(old) == 1; s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
