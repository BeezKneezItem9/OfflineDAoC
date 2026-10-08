p = 'resolve_specs.py'
s = open(p, encoding='utf-8').read()

old = """def world_point(zone_name, loc, realm):"""
new = """# Generic step targets ("<smith in Haggerfel>", "<Basar tower guard>"): the nearest NPC of that role, of the quest's realm,
# to the named place (an Area or zone), else to the step's loc, else to the giver.
ROLE = [(r'guard|sentinel|watch', "(ClassType like '%Guard%' or Name like '%Guard%' or Name like '%Sentinel%' or Name like '%Watch%')"),
        (r'smith', "(ClassType like '%Smith%' or Name like '%smith%')"),
        (r'stable', "(ClassType like '%Stable%' or Name like '%Stable%')"),
        (r'vault', "(ClassType like '%Vault%' or Name like '%Vault%')"),
        (r'barkeep|bartender|innkeeper|tavern', "(Name like '%Barkeep%' or Name like '%Bartender%' or Name like '%Innkeeper%' or ClassType like '%Bar%')"),
        (r'merchant|vendor|trader', "(ClassType like '%Merchant%')"),
        (r'townsperson|citizen|villager', "(Realm > 0 and Flags & 16 = 16)")]
AREAS = list(c.execute("select Description, Region, X, Y from Area where Description is not null"))
REALM_ID = {"Albion": 1, "Midgard": 2, "Hibernia": 3}

def place_point(text, realm):
    words = re.findall(r"[A-Z][A-Za-z'-]+(?: [A-Z][A-Za-z'-]+)*", text)
    for w in sorted(words, key=len, reverse=True):
        for desc, region, x, y in AREAS:
            if desc and desc.lower() == w.lower(): return dict(region=region, x=x, y=y)
        z = zone_for(w, realm)
        if z: return dict(region=z[1], x=z[3] * 8192 + z[5] * 4096, y=z[4] * 8192 + z[6] * 4096)
    return None

def find_generic(tag, step, giver, realm):
    text = tag.strip('<>')
    rule = next((cond for rx, cond in ROLE if re.search(rx, text, re.I)), None)
    if not rule: return None
    anchor = place_point(text, realm) or world_point(step.get('zone'), step.get('loc'), realm) or giver
    if not anchor: return None
    rows = list(c.execute(f"select Name, Region, X, Y, Z, Mob_ID, Level from Mob where Region=? and {rule} and Realm in (?, 0) "
                          "and abs(X-?) < 12000 and abs(Y-?) < 12000", (anchor['region'], REALM_ID.get(realm, 0), anchor['x'], anchor['y'])))
    if not rows: return None
    best = min(rows, key=lambda r: (r[2] - anchor['x']) ** 2 + (r[3] - anchor['y']) ** 2)
    hz = zone_of(best[1], best[2], best[3])
    return dict(name=best[0], region=best[1], x=best[2], y=best[3], z=best[4], mob_id=best[5], level=best[6],
                zone=hz[2] if hz else None, count=1, same_zone=True, generic=tag)

def world_point(zone_name, loc, realm):"""
assert s.count(old) == 1; s = s.replace(old, new)

old = """            npc = st.get("npc")
            if npc and not npc.startswith("<") and npc not in TRAINER:"""
new = """            npc = st.get("npc")
            if npc and (npc in TRAINER or re.search(r'guild trainer|class trainer|\\btrainer\\b', npc, re.I)) and npc.startswith(("<", "T", "C")):
                # "Return to your trainer": each class row's own trainer (resolved per class below)
                classes_here = list((class_givers or {}).keys()) or (spec.get("classes") or [])
                per = {cls: find_trainer(cls, st.get("zone") or g.get("zone"), realm) for cls in classes_here}
                per = {k: v for k, v in per.items() if v}
                if per:
                    r["class_targets"] = per
                    r["target"] = next(iter(per.values()))
                    r["marker"] = dict(region=r["target"]["region"], x=r["target"]["x"], y=r["target"]["y"], z=r["target"]["z"])
                steps.append(r)
                continue
            if npc and npc.startswith("<"):
                hit = find_generic(npc, st, giver, realm)
                if hit:
                    r["target"] = hit
                    r["marker"] = dict(region=hit["region"], x=hit["x"], y=hit["y"], z=hit["z"])
                    steps.append(r)
                    continue
            if npc and not npc.startswith("<") and npc not in TRAINER:"""
assert s.count(old) == 1; s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
