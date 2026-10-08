p = 'gen_dataquests.py'
s = open(p, encoding='utf-8').read()

# ready(): a kill/collect step whose monster the quest itself spawns needs no world spawn of that name.
old = """def ready(q):
    if q.get('giver') is None: return False
    for s in q['steps']:
        if s['do'] not in SIMPLE: return False
        if s.get('target') is None and s['do'] in ('talk', 'kill', 'deliver', 'whisper', 'collect'): return False
    return True"""
new = """def ready(q):
    if q.get('giver') is None: return False
    for s in q['steps']:
        if s['do'] not in SIMPLE: return False
        if s.get('target') is None and s['do'] in ('kill', 'collect') and event_spawn(q, s): continue
        if s.get('target') is None and s['do'] in ('talk', 'kill', 'deliver', 'whisper', 'collect'): return False
    return True"""
assert s.count(old) == 1; s = s.replace(old, new)

# event_spawn(): an anchor needs only a region when the monster comes to the player (TriggerRadius 0).
old2 = """    anchor = where(on_talk) or where(on_death) or s.get('marker')
    if not anchor or anchor.get('z') is None: return None"""
new2 = """    anchor = where(on_talk) or where(on_death) or s.get('marker') or (q.get('giver') if on_talk or on_death else None)
    if not anchor or anchor.get('region') is None: return None
    if anchor.get('z') is None and not (on_talk or on_death): return None
    anchor = dict(anchor, x=anchor.get('x') or 0, y=anchor.get('y') or 0, z=anchor.get('z') or 0)"""
assert s.count(old2) == 1; s = s.replace(old2, new2)

# build(): the target of such a step is the spawned monster's name in its region.
old3 = """        sp = s['spec']; t = s.get('target') or {}
        target = f"{t['name']};{t['region']}" if t else ''"""
new3 = """        sp = s['spec']; t = s.get('target') or {}
        target = f"{t['name']};{t['region']}" if t else ''
        if not t and s['do'] in ('kill', 'collect'):
            ev = event_spawn(q, s)
            if ev: target = f"{ev['Name']};{ev['Region']}"
        if not s.get('marker') and s['do'] in ('kill', 'collect') and not t:
            pass"""
assert s.count(old3) == 1; s = s.replace(old3, new3)

# event_spawn must be defined before ready(): move ready() below event_spawn by renaming the call site order.
# (ready is only called at module level after both are defined, so definition order does not matter.)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
