p = 'gen_dataquests.py'
s = open(p, encoding='utf-8').read()
old = """        names = [t['name'] for t in (q.get('class_givers') or {}).values()] if npc in ('Trainer', 'Class Trainer') else [npc]"""
new = """        names = [t['name'] for t in (q.get('class_givers') or {}).values()] if npc in ('Trainer', 'Class Trainer') else [server_name(q, npc)]"""
assert s.count(old) == 1; s = s.replace(old, new)
old = """def build(q):"""
new = """def server_name(q, npc):
    \"\"\"The server's spelling of a walkthrough NPC name (the giver or a step's target), so its chat answers in game.\"\"\"
    low = (npc or '').lower()
    g, gs = q.get('giver') or {}, q.get('giver_spec') or {}
    if g and (low == (gs.get('name') or '').lower() or low == g.get('name', '').lower()): return g['name']
    for st in q['steps']:
        t = st.get('target')
        if t and low in ((st['spec'].get('npc') or '').lower(), t['name'].lower()): return t['name']
    import difflib
    names = [g.get('name')] + [st['target']['name'] for st in q['steps'] if st.get('target')]
    close = difflib.get_close_matches(npc, [n for n in names if n], n=1, cutoff=0.8)
    return close[0] if close else npc

def build(q):"""
assert s.count(old) == 1; s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
