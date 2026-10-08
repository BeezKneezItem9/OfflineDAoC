"""One-off edit: hand-resolved generic targets (generic_targets.json) in resolve_specs.py, and per-class step targets
(class_targets) honoured by gen_dataquests.py for trainer quests."""


def edit(p, pairs):
    s = open(p, encoding='utf-8').read()
    for old, new in pairs:
        assert s.count(old) == 1, (p, old[:70])
        s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s)


edit('resolve_specs.py', [
    ('''            if npc and npc.startswith("<"):
                hit = find_generic(npc, st, giver, realm)''',
     '''            ov = GENERIC.get(f'{spec["src"]}|{npc}') if npc else None
            if ov and ov.get("npc"):
                hit = find_npc(ov["npc"], ov.get("zone") or st.get("zone") or g.get("zone"), realm)
                if hit:
                    r["target"], r["override"] = hit, ov["why"]
                    r["marker"] = dict(region=hit["region"], x=hit["x"], y=hit["y"], z=hit["z"])
                    steps.append(r)
                    continue
            if ov and ov.get("trainer_of"):
                # another class's trainer, nearest each class row's own giver (the trainer that gave the quest)
                wanted = ov["trainer_of"].split("|")
                givers_by_class = class_givers or ({None: giver} if giver else {})
                per = {}
                for cls, gv in givers_by_class.items():
                    cands = []
                    for w in wanted:
                        if cls and w.lower() == str(cls).lower(): continue
                        for h in TRAINERS.get(w.lower(), []):
                            if gv and h[1] == gv["region"]:
                                cands.append(((h[2] - gv["x"]) ** 2 + (h[3] - gv["y"]) ** 2, w, h))
                    cands.sort(key=lambda t: t[0])
                    seen_cls, picks = set(), []
                    for d, w, h in cands:
                        if w in seen_cls: continue
                        seen_cls.add(w); picks.append(h)
                    k = int(ov.get("pick") or 0)
                    if len(picks) > k:
                        h = picks[k]
                        hz = zone_of(h[1], h[2], h[3])
                        per[cls] = dict(name=h[0], region=h[1], x=h[2], y=h[3], z=h[4], mob_id=h[5], level=h[6],
                                        zone=hz[2] if hz else None, count=1, same_zone=True)
                if per:
                    first = next(iter(per.values()))
                    r["target"], r["override"] = first, ov["why"]
                    if None not in per: r["class_targets"] = per
                    r["marker"] = dict(region=first["region"], x=first["x"], y=first["y"], z=first["z"])
                    steps.append(r)
                    continue
            if ov and ov.get("spawn"):
                spn = ov["spawn"]
                wp = world_point(spn["zone"], spn.get("loc"), realm)
                r["needs_spawn"] = dict(name=spn["name"], at=wp, zone=spn["zone"], loc_note=ov["why"],
                                        spawn={k: v for k, v in spn.items() if k in ("level", "like")}, role=spn.get("role"))
                r["override"] = ov["why"]
                if wp: r["marker"] = wp
                planned = PLANNED.get(spn["name"].lower())
                if planned:
                    r["target"] = planned
                    r["marker"] = dict(region=planned["region"], x=planned["x"], y=planned["y"], z=planned["z"])
                steps.append(r)
                continue
            if npc and npc.startswith("<"):
                hit = find_generic(npc, st, giver, realm)'''),
    ('''# This generator's own planned spawns''', '''# Hand-resolved generic targets ("<guard>", "<faerie court>"): generic_targets.json.
GENERIC = {k: v for k, v in json.load(open(os.path.join(HERE, "generic_targets.json"), encoding="utf-8")).items() if not k.startswith("_")}

# This generator's own planned spawns'''),
])

edit('plan_spawns.py', [
    ('''                                                   loc_note=ns.get("loc_note"), role=s["do"]))
        entry["quests"].append(f'{q["name"]} step {s["index"]}')''',
     '''                                                   loc_note=ns.get("loc_note"), role=ns.get("role") or s["do"]))
        entry["quests"].append(f'{q["name"]} step {s["index"]}')'''),
])

edit('gen_dataquests.py', [
    ('''        spans.append((start, len(steps)))''',
     '''        spans.append((start, len(steps)))
        if s.get('class_targets'):  # "your trainer" / "another trainer": each class row's own NPC
            for k in range(start, len(steps)):
                class_tgts[k] = {cls: (f"{t['name']};{t['region']}", dict(region=t['region'], x=t['x'], y=t['y'], z=t['z']))
                                 for cls, t in s['class_targets'].items()}'''),
    ('''    spans = []  # plan step -> (first, end) generated step indexes''',
     '''    spans = []  # plan step -> (first, end) generated step indexes
    class_tgts = {}  # generated step index -> {class: (target, marker)}'''),
    ('''        '_grants': [grants.get(k) for k in range(len(steps))],''',
     '''        '_grants': [grants.get(k) for k in range(len(steps))],
        '_class_targets': class_tgts,'''),
    ('''            per = copy_row(row, StartName=t['name'], StartRegionID=t['region'], AllowedClasses=str(cid))''',
     '''            per = copy_row(row, StartName=t['name'], StartRegionID=t['region'], AllowedClasses=str(cid))
            if row['_class_targets']:
                tn = per['TargetName'].split('|')
                for k, by_cls in row['_class_targets'].items():
                    if cls in by_cls:
                        tn[k] = by_cls[cls][0]
                        per['_markers'][k] = by_cls[cls][1]
                per['TargetName'] = '|'.join(tn)'''),
    ('''    customs = r.pop('_custom')''', '''    customs = r.pop('_custom')
    r.pop('_class_targets', None)'''),
])
print('ok')
