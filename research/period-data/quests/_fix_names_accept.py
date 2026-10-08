p = 'resolve_specs.py'
s = open(p, encoding='utf-8').read()
old = """MOBS = collections.defaultdict(list)
for name, region, x, y, z, mid, level in c.execute("select Name,Region,X,Y,Z,Mob_ID,Level from Mob"):
    MOBS[name.lower().strip()].append((region, x, y, z, mid, level))"""
new = """MOBS = collections.defaultdict(list)
DBNAME = {}  # lower name -> the server's own spelling (targets must match the spawn's name)
for name, region, x, y, z, mid, level in c.execute("select Name,Region,X,Y,Z,Mob_ID,Level from Mob"):
    MOBS[name.lower().strip()].append((region, x, y, z, mid, level))
    DBNAME.setdefault(name.lower().strip(), name.strip())"""
assert s.count(old) == 1; s = s.replace(old, new)
old = """    hits, spelled = MOBS.get(key, []), name
    if not hits:
        close = difflib.get_close_matches(key, ALL, n=1, cutoff=0.86)
        if close: hits, spelled = MOBS[close[0]], close[0]"""
new = """    hits, spelled = MOBS.get(key, []), DBNAME.get(key, name)
    if not hits:
        close = difflib.get_close_matches(key, ALL, n=1, cutoff=0.86)
        if close: hits, spelled = MOBS[close[0]], DBNAME[close[0]]"""
assert s.count(old) == 1; s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)

p = 'gen_dataquests.py'
s = open(p, encoding='utf-8').read()
old = """    dlg = DIALOGUE.get(spec['src']) or {}
    if dlg.get('offer') and dlg.get('accept'):
        return dlg['offer'], dlg['accept']"""
new = """    dlg = DIALOGUE.get(spec['src']) or {}
    if dlg.get('offer') and dlg.get('accept'):
        # The recorded accept word must be clickable somewhere the player reads (the offer or a reply of the chain);
        # when the page recorded it unbracketed, the chain's last unanswered keyword stands in (owner: an existing
        # quest word, even if not the period one).
        replies = [v for chat in (dlg.get('chat') or {}).values() for v in chat.values()]
        seen = dlg['offer'] + ' ' + ' '.join(replies)
        if '[' + dlg['accept'] + ']' in seen:
            return dlg['offer'], dlg['accept']
        answered = {k.lower() for chat in (dlg.get('chat') or {}).values() for k in chat}
        open_kw = [k for v in replies for k in _re.findall(r'\[([^\]]+)\]', v) if k.lower() not in answered]
        if open_kw:
            return dlg['offer'], open_kw[-1]"""
assert s.count(old) == 1; s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
