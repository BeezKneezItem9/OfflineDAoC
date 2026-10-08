p = 'resolve_specs.py'
s = open(p, encoding='utf-8').read()
old = """        spec = json.loads(line)
        realm = spec["realm"]
        g = spec.get("giver", {})"""
new = """        spec = json.loads(line)
        realm = spec["realm"]
        g = spec.get("giver", {})
        if spec.get("type") == "kill_task" and not spec.get("steps") and spec.get("item") and spec.get("from"):
            # A kill task is one repeatable turn-in: the item drops from the listed monsters, the giver takes it.
            # Atlas's "XP Item" DataQuests already carry many of them (same giver and item): those stay as they are.
            words = [w for w in re.findall(r"[a-z]{4,}", spec["item"].lower())]
            have = [n for (n,) in c.execute("select Name from DataQuest where ID < 20000 and lower(StartName)=lower(?) and Name like '%XP Item%'",
                                            (g.get("name") or "",))]
            if not any(any(w in n.lower() for w in words) for n in have):
                mobs_text = ", ".join(spec["from"])
                spec["steps"] = [dict(do="trade", npc=g.get("name"), zone=g.get("zone"), trades={spec["item"]: "xp"},
                                      **{"from": spec["from"]}, chance=spec.get("chance") or 15,
                                      text=f"Kill {mobs_text} and bring {g.get('name')} the {spec['item']}." +
                                           (" " + spec["notes"] if spec.get("notes") else ""))]
            else:
                spec["already_in_game"] = True"""
assert s.count(old) == 1; s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)

p = 'gen_dataquests.py'
s = open(p, encoding='utf-8').read()
old = """'MaxCount': 1,"""
new = """'MaxCount': int(spec.get('limit') or (30 if spec.get('type') == 'kill_task' or all(st['do'] == 'trade' for st in plan) else 1)),"""
assert s.count(old) == 1; s = s.replace(old, new)
old = """    if row is None: skipped['no steps'] += 1; continue"""
new = """    if row is None: skipped['already in game (Atlas XP Item quest)' if q['spec'].get('already_in_game') else 'no steps'] += 1; continue"""
assert s.count(old) == 1; s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
