p = 'gen_dataquests.py'
s = open(p, encoding='utf-8').read()

# Load the researched dialogue once.
old = """STOP = set('that this with"""
new = """DIALOGUE = json.load(open(os.path.join(HERE, 'dialogue.json'), encoding='utf-8')) if os.path.exists(os.path.join(HERE, 'dialogue.json')) else {}
CHAT = {}  # npc -> keyword -> reply, merged into the ClassicQuests config

STOP = set('that this with"""
assert s.count(old) == 1; s = s.replace(old, new)

# Accept keyword: the recorded offer and its accept word first.
old = """    offer = (spec.get('offer') or '').strip()
    chosen = (spec.get('accept_keyword') or '').strip()"""
new = """    dlg = DIALOGUE.get(spec['src']) or {}
    if dlg.get('offer') and dlg.get('accept'):
        return dlg['offer'], dlg['accept']
    offer = (spec.get('offer') or '').strip()
    chosen = (spec.get('accept_keyword') or '').strip()"""
assert s.count(old) == 1; s = s.replace(old, new)

# SourceText / TargetText / FinishText from the recorded dialogue.
old = """        'SourceText': '|'.join(((spec.get('dialogue') or {}).get(str(i + 1))
                                or (steps[i][3] if spec.get('dialogue_checked') else '')).replace('|', '/') for i in range(len(steps))),"""
new = """        'SourceText': '|'.join(source_texts(spec, steps)),
        'TargetText': '|'.join(target_texts(spec, steps)),"""
assert s.count(old) == 1; s = s.replace(old, new)

old = """        'FinishText': spec.get('finish_text') or (spec.get('finish') if isinstance(spec.get('finish'), str) else ''),"""
new = """        'FinishText': ((DIALOGUE.get(spec['src']) or {}).get('finish') or '').replace('|', '/'),"""
assert s.count(old) == 1; s = s.replace(old, new)

# The old TargetText built from s[4] is replaced: drop the duplicate key if present.
s = s.replace("""        'TargetText': '|'.join(s[4].replace('|', '/') for s in steps),\n""", "")

old = """def build(q):
    spec = q['spec']"""
new = """def source_texts(spec, steps):
    \"\"\"Step 1: the giver's recorded line on accepting; with a checked page and no recorded line, the step's own
    instruction stands in (owner placeholder rule). Later steps: recorded lines only.\"\"\"
    dlg = DIALOGUE.get(spec['src']) or {}
    out = [''] * len(steps)
    if dlg.get('accept_line'): out[0] = dlg['accept_line']
    elif dlg.get('checked'): out[0] = steps[0][3]
    return [t.replace('|', '/') for t in out]

def target_texts(spec, steps):
    \"\"\"What a talk/turn-in NPC says when its step ends: its recorded lines.\"\"\"
    lines = (DIALOGUE.get(spec['src']) or {}).get('npc_lines') or {}
    out = []
    for st in steps:
        npc = st[1].split(';')[0]
        out.append((lines.get(npc) or '').replace('|', '/') if st[0] in (2, 3, 4, 5, 6, 7, 10, 11) else '')
    return out

def build(q):
    spec = q['spec']
    for npc, chat in ((DIALOGUE.get(spec['src']) or {}).get('chat') or {}).items():
        for kw, reply in chat.items():
            CHAT.setdefault(npc, {}).setdefault(kw, reply)"""
assert s.count(old) == 1; s = s.replace(old, new)

old = """config['QuestMonsterIds'] = sorted(named_ids)"""
new = """config['QuestMonsterIds'] = sorted(named_ids)
config['Chat'] = CHAT"""
assert s.count(old) == 1; s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
