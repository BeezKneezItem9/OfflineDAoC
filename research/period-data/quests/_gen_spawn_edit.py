p = 'gen_dataquests.py'
s = open(p, encoding='utf-8').read()
old = """    level = num(sw.get('level')) or (num(t[1]) if t else 0)
    offset = 0 if on_death else 180  # beside the NPC who calls them, or where the first one fell
    return {'Name': sp.get('npc'), 'TemplateId': t[0] if t else 0, 'Level': level,
            'Model': num(t[2]) if t and not t[0] else 0,
            'Region': anchor['region'], 'X': anchor['x'] + offset, 'Y': anchor['y'], 'Z': anchor['z'],
            'TriggerRadius': 1200, 'DespawnSeconds': 600}"""
new = """    level = num(sw.get('level')) or (num(t[1]) if t else 0) or num(q['spec'].get('level'))
    # Owner 2026-10-07: monsters that come for the player (on talking to an NPC, on the kill before) appear beside it
    # wherever it is (TriggerRadius 0); "appears when you get there" ones wait until the player is near the point.
    return {'Name': sp.get('npc'), 'TemplateId': t[0] if t else 0, 'Level': level,
            'Model': num(t[2]) if t and not t[0] else 0,
            'Region': anchor['region'], 'X': anchor['x'], 'Y': anchor['y'], 'Z': anchor['z'],
            'TriggerRadius': 0 if on_talk or on_death else 1200, 'DespawnSeconds': 600, 'Count': 1}"""
assert s.count(old) == 1; s = s.replace(old, new)
old2 = """        spawn = event_spawn(q, s) if s['do'] in ('kill', 'collect') else None
        for k in range(start, len(steps)):
            steps[k] += [marker, named, spawn]"""
new2 = """        spawn = event_spawn(q, s) if s['do'] in ('kill', 'collect') else None
        for k in range(start, len(steps)):
            # A group ("two youths") all appear on its first step; the later steps only respawn one if it went missing.
            per = dict(spawn, Count=len(steps) - start if k == start else 1) if spawn else None
            steps[k] += [marker, named, per]"""
assert s.count(old2) == 1; s = s.replace(old2, new2)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
