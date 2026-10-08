p = 'apply_world.py'
s = open(p, encoding='utf-8').read()
def rep(old, new):
    global s
    assert s.count(old) == 1, old[:70]
    s = s.replace(old, new)
rep('''def local_donor(place, friendly, level):
    q = (f"select {','.join(MCOLS)} from Mob where Region=? and Model > 0 and abs(X-?) < 15000 and abs(Y-?) < 15000 and "
         + ("Realm > 0 and ClassType='DOL.GS.GameNPC'" if friendly else "Realm = 0 and Level > 0") +
         " and (PackageID is null or PackageID <> 'ClassicQuest')")
    rows = cur.execute(q, (place["region"], place["x"], place["y"])).fetchall()
    if not rows: return None, None''', '''NOT_DONOR = _re.compile(r"horse|pack|ambient|stable|cart|boat|guard|sentinel|keep|captain|lord|merchant|trainer|teleport|hastener|banker|vault", _re.I)
def local_donor(place, friendly, level, humanoid=False):
    rows = []
    for reach in (15000, 40000, 400000):
        q = (f"select {','.join(MCOLS)} from Mob where Region=? and Model > 0 and abs(X-?) < {reach} and abs(Y-?) < {reach} and "
             + ("Realm > 0 and ClassType='DOL.GS.GameNPC' and Race between 1 and 20" if friendly else "Realm = 0 and Level > 0") +
             (" and (Race between 1 and 30 or EquipmentTemplateID is not null)" if humanoid and not friendly else "") +
             " and (PackageID is null or PackageID <> 'ClassicQuest')")
        rows = [r for r in cur.execute(q, (place["region"], place["x"], place["y"])).fetchall() if not NOT_DONOR.search(dict(zip(MCOLS, r))["Name"])]
        if rows: break
    if not rows and humanoid: return local_donor(place, friendly, level)
    if not rows: return None, None''')
rep('''    return mob_template(best), ("nearest townsperson " if friendly else "nearest local creature ") + dict(zip(MCOLS, best))["Name"]''',
    '''    t = mob_template(best)
    if friendly: t = dict(t, Level=min(int(t["Level"] or 20), 50))
    return t, ("nearest townsperson " if friendly else "nearest local humanoid " if humanoid else "nearest local creature ") + dict(zip(MCOLS, best))["Name"]''')
rep('''    tries = ([" ".join(name_words)] if len(name_words) > 1 else []) + (name_words[::-1] if lowercase or len(name_words) > 1 else []) + note_words
    if not friendly or lowercase:
        t, why = species_donor([w for w in tries if w], place, friendly=False)
        if t: return t, why''', '''    if lowercase:   # a species name ("tidal mongrel"): the whole name, then its words from the head noun back
        tries = ([" ".join(name_words)] if len(name_words) > 1 else []) + name_words[::-1] + note_words
    else:           # a personal name: only words that are species ("Noble Werewolf Alina"), then the note's species
        tries = [w for w in SPECIES_WORDS if _re.search(r"\b" + w + r"\b", e["name"].lower())] + note_words
    if not friendly or lowercase:
        t, why = species_donor([w for w in tries if w], place, friendly=False)
        if t: return t, why''')
rep('''    return local_donor(place, friendly, level or 20)''', '''    return local_donor(place, friendly, level or 20, humanoid=not lowercase)''')
open(p, 'w', encoding='utf-8').write(s)
print('ok')
