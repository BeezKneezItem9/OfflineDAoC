"""One-off edit: appearance donors for quest spawns with no NPC template (apply_world.py), and one-time-drop items in
the reward item list (gen_dataquests.py)."""
p = 'apply_world.py'
s = open(p, encoding='utf-8').read()


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:70]
    s = s.replace(old, new)


rep('''COPY = os.path.join(os.path.dirname(HERE), "dbcopy.db")''',
    '''COPY = r"C:/OfflineDAoC/scratch/dbcopy.db"  # lock-free copy of the live DB''')

rep('''now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")''', '''now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

# Appearance donors (owner rule: invent only with zero data). No period source records a creature's model, so a spawn
# with no NPC template of its own name looks like (in order): a creature of the same species (its name's words, then
# the species the walkthrough names in its note), a peaceful townsperson of its realm nearest the spot (quest NPCs),
# or the nearest local creature of a similar level (named monsters). Level: the period sightings, else the spec, else
# the donor. Every donor is listed in world_preview.json (donor, why) for the ledger.
import re as _re
MCOLS = [r[1] for r in cur.execute("pragma table_info(Mob)")]
SPECIES_STOP = {"wandering", "young", "old", "enchanted", "noble", "lord", "lady", "the", "of", "corrupt", "dark", "elder",
                "great", "lesser", "greater", "ancient", "angry", "enraged", "lost", "spirit", "shade", "ghost", "captain"}
SPECIES_WORDS = ("banshee", "cyclops", "demon", "scrag", "stepper", "imp", "merush", "treant", "giant", "troll", "dwarf",
                 "kobold", "wolf", "bear", "spider", "goblin", "orc", "ogre", "siabra", "fomorian", "sylvan", "drakoran",
                 "werewolf", "skeleton", "zombie", "ghoul", "wraith", "spectre", "specter", "golem", "worm", "drake",
                 "dragon", "basilisk", "griffin", "boar", "cat", "badger", "fairy", "faerie", "sprite", "pixie", "wisp",
                 "satyr", "centaur", "minotaur", "harpy", "bwca", "roman", "centurion", "legionnaire", "cultist", "druid",
                 "witch", "hag", "lich", "vampire", "undead", "phantom", "wickerman", "dervish", "tree", "crab", "eel",
                 "shark", "lunger", "anglator", "curmudgeon", "koalinth", "morvalt", "svartalf", "tomte", "nisse",
                 "huldu", "dverge", "jotun", "frost giant", "wyvern", "grimwood", "fellwood", "afanc", "lurikeen")
def mob_template(row):
    d = dict(zip(MCOLS, row))
    return dict(TemplateId=-1, Name=d["Name"], GuildName=d.get("Guild") or "", Model=d["Model"], Size=d["Size"], Level=d["Level"],
                MaxSpeed=d.get("Speed") or 191, Strength=d.get("Strength"), Constitution=d.get("Constitution"),
                Dexterity=d.get("Dexterity"), Quickness=d.get("Quickness"), Intelligence=d.get("Intelligence"),
                Piety=d.get("Piety"), Empathy=d.get("Empathy"), Charisma=d.get("Charisma"),
                EquipmentTemplateID=d.get("EquipmentTemplateID"), ItemsListTemplateID=None, Race=d.get("Race"),
                Flags=(d.get("Flags") or 0) & ~16, AggroLevel=d.get("AggroLevel"), AggroRange=d.get("AggroRange"),
                MeleeDamageType=d.get("MeleeDamageType"), FactionID=d.get("FactionID"), BodyType=d.get("BodyType"),
                Gender=d.get("Gender"), VisibleWeaponSlots=d.get("VisibleWeaponSlots"))
def species_donor(words, place, friendly):
    for w in words:
        rows = cur.execute(f"select {','.join(MCOLS)} from Mob where lower(Name) like ? and Model > 0 and Realm {'>' if friendly else '='} 0 "
                           "and (PackageID is null or PackageID <> 'ClassicQuest')", (f"%{w}%",)).fetchall()
        if rows:
            reg = place.get("region")
            best = min(rows, key=lambda r: (dict(zip(MCOLS, r))["Region"] != reg,
                                            (dict(zip(MCOLS, r))["X"] - place.get("x", 0)) ** 2 + (dict(zip(MCOLS, r))["Y"] - place.get("y", 0)) ** 2))
            return mob_template(best), f"species '{w}' -> {dict(zip(MCOLS, best))['Name']}"
    return None, None
def local_donor(place, friendly, level):
    q = (f"select {','.join(MCOLS)} from Mob where Region=? and Model > 0 and abs(X-?) < 15000 and abs(Y-?) < 15000 and "
         + ("Realm > 0 and ClassType='DOL.GS.GameNPC'" if friendly else "Realm = 0 and Level > 0") +
         " and (PackageID is null or PackageID <> 'ClassicQuest')")
    rows = cur.execute(q, (place["region"], place["x"], place["y"])).fetchall()
    if not rows: return None, None
    best = min(rows, key=lambda r: (abs((dict(zip(MCOLS, r))["Level"] or 0) - level) // 5 if not friendly else 0,
                                    (dict(zip(MCOLS, r))["X"] - place["x"]) ** 2 + (dict(zip(MCOLS, r))["Y"] - place["y"]) ** 2))
    return mob_template(best), ("nearest townsperson " if friendly else "nearest local creature ") + dict(zip(MCOLS, best))["Name"]
def find_donor(e, place):
    friendly = e.get("role") in FRIENDLY_ROLES
    name_words = [w for w in _re.findall(r"[a-z'-]+", e["name"].lower()) if w not in SPECIES_STOP and len(w) > 2]
    lowercase = e["name"][:1].islower()
    note = " ".join(str(x or "") for x in (e.get("loc_note"), (e.get("spec_spawn") or {}).get("like") if isinstance(e.get("spec_spawn"), dict) else ""))
    note_words = [w for w in SPECIES_WORDS if _re.search(r"\\b" + w + r"s?\\b", note.lower())]
    tries = ([" ".join(name_words)] if len(name_words) > 1 else []) + (name_words[::-1] if lowercase or len(name_words) > 1 else []) + note_words
    if not friendly or lowercase:
        t, why = species_donor([w for w in tries if w], place, friendly=False)
        if t: return t, why
    levels = place.get("levels") or []
    level = int(sorted(levels)[len(levels) // 2]) if levels else int((e.get("spec_spawn") or {}).get("level") or 0) if isinstance(e.get("spec_spawn"), dict) and str((e.get("spec_spawn") or {}).get("level") or "").isdigit() else 0
    return local_donor(place, friendly, level or 20)''')

rep('''    if t is None and spawn.get("like"): t = template_row(name=spawn["like"])
    if t is None: skipped.append((e["realm"], e["name"], e.get("role"), "no template or donor")); continue''',
    '''    if t is None and spawn.get("like"): t = template_row(name=spawn["like"])
    donor_note = None
    if t is None:
        t, donor_note = find_donor(e, place)
        levels = place.get("levels") or []
        if t is not None and levels: t = dict(t, Level=sorted(levels)[len(levels) // 2])  # the period sightings' level
    if t is None: skipped.append((e["realm"], e["name"], e.get("role"), "no template or donor")); continue''')

rep('''        _role=e.get("role"), _quests=e.get("quests")))''', '''        _role=e.get("role"), _quests=e.get("quests"), _donor=donor_note))''')
open(p, 'w', encoding='utf-8').write(s)

p = 'gen_dataquests.py'
s = open(p, encoding='utf-8').read()
rep('''for v in REWARD_ITEMS.values(): v['quests'] = sorted(v['quests'])''', '''# One-time drops' items (world loot, apply_world.py) are period equipment too: built with the rewards.
for q in resolved:
    sp = q['spec']
    if sp.get('type') != 'otd': continue
    for n in ([sp['item']] if sp.get('item') else []) + list((sp.get('item_by_class') or {}).values()):
        if isinstance(n, str) and n and not n.startswith('<'):
            REWARD_ITEMS.setdefault('cq_otd_' + re.sub(r'[^a-z0-9]+', '_', n.lower()).strip('_')[:54],
                                    {'name': RW.display_name(n), 'full': n, 'realm': sp['realm'], 'quests': set()})['quests'].add(sp['name'])
for v in REWARD_ITEMS.values(): v['quests'] = sorted(v['quests'])''')
open(p, 'w', encoding='utf-8').write(s)
print('ok')
