p = 'plan_spawns.py'
s = open(p, encoding='utf-8').read()
old = """anchors = json.load(open(os.path.join(HERE, "anchors.json"), encoding="utf-8"))"""
new = """# Kill-task drop sources (goal 10): the monsters a trade step's item drops from must be in the world.
for q in resolved:
    for s in q["steps"]:
        st = s["spec"]
        if st.get("do") != "trade": continue
        for name in st.get("from") or []:
            if name.lower() in spawned: continue
            entry = plan.setdefault(name.lower(), dict(name=name, realm=q["realm"], quests=[], event=False, place=None,
                                                       template=template(name), spec_spawn=None,
                                                       zone=st.get("zone") or (q["spec"].get("zone")), loc_note=q["spec"].get("notes"),
                                                       role="drop source"))
            entry["quests"].append(f'{q["name"]} (drops {", ".join(st.get("trades") or {})})')
            if entry["place"] is None:
                place = classic_sighting(name)
                if place and place.get("zone_id") is not None:
                    f = floor(place["zone_id"], place["x"], place["y"], place["z"])
                    if f: place.update(x=int(f[0]), y=int(f[1]), z=int(f[2]), on_mesh=True)
                    else: place["on_mesh"] = False
                entry["place"] = place

anchors = json.load(open(os.path.join(HERE, "anchors.json"), encoding="utf-8"))"""
assert s.count(old) == 1; s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
