"""Goal 10: ItemTemplate rows for the classic quest rewards, from the period item pages (Allakhazam).
  python build_reward_items.py     reads reward_items_needed.json (written by gen_dataquests.py) and the item pages
                                   (reward_items.jsonl from the first pass, ../archive/allakhazam-live/item.jsonl.gz from
                                   the full archive pass); writes reward_item_rows.json and reward_items_report.json.
Stats come from the page: slot, armour/weapon type, AF/absorb or DPS/speed, damage type, every magical bonus, quality,
weight, levels, bonus level, charges/procs. Not on any period page, so borrowed and listed in the ledger:
  - the 3D model (an existing item of the same slot, type and realm, nearest in level),
  - a charge/proc spell (an existing spell of the same function, damage type and nearest strength).
An item with no page anywhere is reported, not invented."""
import collections, glob, gzip, html, json, os, re, sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DB = "file:C:/OfflineDAoC/scratch/dbcopy.db?mode=ro"
c = sqlite3.connect(DB, uri=True)
REALM = {'Albion': 1, 'Midgard': 2, 'Hibernia': 3, 'All': 0}
SLOT = {'Right Hand': 10, 'Left Hand': 11, 'Two Hand': 12, 'Two Handed': 12, 'Ranged': 13, 'Helm': 21, 'Head': 21, 'Hands': 22,
        'Feet': 23, 'Jewelry': 24, 'Jewel': 24, 'Torso': 25, 'Back': 26, 'Cloak': 26, 'Legs': 27, 'Arms': 28, 'Neck': 29,
        'Waist': 32, 'Wrist': 33, 'Ring': 35, 'Inventory': 40, 'Mythical': 37}
WEAPON = {'crush': 2, 'slash': 3, 'thrust': 4, 'two handed': 6, 'polearm': 7, 'staff': 8, 'longbow': 9, 'long bow': 9, 'crossbow': 10,
          'flexible': 24, 'sword': 11, 'hammer': 12, 'axe': 13, 'spear': 14, 'composite bow': 15, 'thrown': 16, 'left axe': 17,
          'hand to hand': 25, 'recurve bow': 18, 'recurved bow': 18, 'blades': 19, 'blunt': 20, 'piercing': 21,
          'large weapon': 22, 'large weapons': 22, 'celtic spear': 23, 'scythe': 26, 'shield': 42, 'instrument': 45,
          'shortbow': 5, 'short bow': 5, 'bow': 5}
ARMOR = {'cloth': 32, 'leather': 33, 'studded': 34, 'chain': 35, 'plate': 36, 'reinforced': 37, 'scale': 38}
DAMAGE = {'crush': 1, 'slash': 2, 'thrust': 3, 'body': 10, 'cold': 11, 'energy': 12, 'heat': 13, 'matter': 14, 'spirit': 15}
STATS = {'strength': 1, 'dexterity': 2, 'constitution': 3, 'quickness': 4, 'intelligence': 5, 'piety': 6, 'empathy': 7,
         'charisma': 8, 'power': 9, 'hits': 10, 'body resist': 11, 'cold resist': 12, 'crush resist': 13, 'energy resist': 14,
         'heat resist': 15, 'matter resist': 16, 'slash resist': 17, 'spirit resist': 18, 'thrust resist': 19, 'acuity': 156,
         'all primary melee skills': 164, 'all melee weapon skills': 164, 'all magic skills': 163, 'all dual wielding skills': 167,
         'all archery skills': 168, 'all focus levels': 165, 'armor factor': 148, 'af': 148, 'power pool': 196}
SKILLS = {'two handed': 20, 'body destruction': 21, 'body magic': 21, 'chants': 22, 'critical strike': 23, 'crossbow': 24,
          'crush': 25, 'death servant': 26, 'deathsight': 27, 'dual wield': 28, 'earth magic': 29, 'enhancement': 30, 'envenom': 31,
          'fire magic': 32, 'flexible': 33, 'cold magic': 34, 'instruments': 35, 'longbow': 36, 'long bow': 36, 'matter magic': 37,
          'mind magic': 38, 'mind twisting': 38, 'painworking': 39, 'parry': 40, 'polearm': 41, 'rejuvenation': 42, 'shield': 43,
          'slash': 44, 'smite': 45, 'soulrending': 46, 'spirit magic': 47, 'staff': 48, 'stealth': 49, 'thrust': 50, 'wind magic': 51,
          'sword': 52, 'hammer': 53, 'axe': 54, 'left axe': 55, 'spear': 56, 'mending': 57, 'augmentation': 58, 'darkness': 60,
          'suppression': 61, 'runecarving': 62, 'stormcalling': 63, 'beastcraft': 64, 'light': 65, 'void': 66, 'mana': 67,
          'composite bow': 68, 'battlesongs': 69, 'enchantment': 70, 'enchantments': 70, 'blades': 72, 'blunt': 73, 'piercing': 74,
          'large weapon': 75, 'large weapons': 75, 'mentalism': 76, 'regrowth': 77, 'nurture': 78, 'nature': 79, 'music': 80,
          'bard music': 80, 'celtic dual': 81, 'celtic spear': 82, 'recurve bow': 83, 'valor': 84, 'subterranean': 85,
          'bone army': 86, 'verdant path': 87, 'creeping path': 88, 'arboreal path': 89, 'scythe': 90, 'thrown weapons': 91,
          'hand to hand': 92, 'short bow': 93, 'pacification': 94, 'savagery': 95, 'nightshade magic': 96, 'pathfinding': 97,
          'summoning': 98, 'cursing (spec)': 106, 'cursing': 106, 'hexing': 107, 'witchcraft': 108, 'odin\'s will': 105,
          'path of fire': 32, 'path of earth': 29, 'path of ice': 34, 'path of air': 51, 'calefaction': 32, 'vampiiric embrace': 101}
FOCUS = {'darkness': 120, 'suppression': 121, 'runecarving': 122, 'spirit': 123, 'fire': 124, 'air': 125, 'wind': 125, 'cold': 126,
         'ice': 126, 'earth': 127, 'light': 128, 'body': 129, 'matter': 130, 'mind': 132, 'void': 133, 'mana': 134,
         'enchantments': 135, 'mentalism': 136, 'summoning': 137, 'bone army': 138, 'painworking': 139, 'deathsight': 140,
         'death servant': 141, 'verdant path': 142, 'creeping path': 143, 'arboreal path': 144, 'all': 165}
SPELL_TYPE = {'direct damage': 'DirectDamage', 'damage over time': 'DamageOverTime', 'heal': 'Heal', 'lifedrain': 'Lifedrain',
              'life drain': 'Lifedrain', 'damage shield': 'DamageShield', 'damage add': 'DamageAdd', 'snare': 'SpeedDecrease',
              'speed decrease': 'SpeedDecrease', 'strength buff': 'StrengthBuff', 'constitution buff': 'ConstitutionBuff',
              'dexterity buff': 'DexterityBuff', 'armor factor buff': 'BaseArmorFactorBuff', 'mesmerize': 'Mesmerize',
              'stun': 'Stun', 'disease': 'Disease', 'bolt': 'Bolt', 'str/con buff': 'StrengthConstitutionBuff',
              'dex/qui buff': 'DexterityQuicknessBuff', 'ablative armor': 'AblativeArmor', 'power regen': 'PowerRegenBuff',
              'health regen': 'HealthRegenBuff', 'haste': 'CombatSpeedBuff', 'combat speed buff': 'CombatSpeedBuff',
              'speed enhancement': 'SpeedEnhancement', 'resist buff': 'BodySpiritEnergyBuff'}


def html_lines(h):
    h = re.sub(r'<(script|style)[\s\S]*?</\1>', '', h, flags=re.I)
    h = re.sub(r'<br\s*/?>|</(td|th|tr|div|p|li|h\d|table)>', '\n', h, flags=re.I)
    t = html.unescape(re.sub(r'<[^>]+>', ' ', h))
    return [re.sub(r'[ \t\xa0]+', ' ', x).strip() for x in t.split('\n') if x.strip()]


def load_pages():
    """name (lower) -> list of {id, lines, source}."""
    out = collections.defaultdict(list)
    # Period copies first (Internet Archive, last capture on or before 2004-12-07): the item as it was then.
    for f in [os.path.join(HERE, '..', 'archive', 'wayback-allakhazam', 'items_direct.jsonl.gz')]:
        if not os.path.exists(f): continue
        try:
            for l in gzip.open(f, 'rt', encoding='utf-8'):
                try: r = json.loads(l)
                except ValueError: continue
                if not r.get('body'): continue
                lines = html_lines(r['body'])
                start = next((k for k, x in enumerate(lines) if x == r['name'] and k + 1 < len(lines) and lines[k + 1] == 'Realm:'), None)
                if start is None: continue
                out[r['name'].lower()].append(dict(id=r['citem'], lines=lines[start + 1:], source=f"allakhazam {r['timestamp'][:8]} (Internet Archive)"))
        except (EOFError, OSError):
            pass
    p = os.path.join(HERE, 'reward_items.jsonl')
    if os.path.exists(p):
        for l in open(p, encoding='utf-8'):
            r = json.loads(l)
            if r.get('name'): out[r['name'].lower().strip()].append(dict(id=r['id'], lines=r['lines'] + (r.get('from') or []), source='allakhazam (item pass)'))
    for f in glob.glob(os.path.join(HERE, '..', 'archive', 'allakhazam-live', 'item.jsonl.gz')):
        try:
            for l in gzip.open(f, 'rt', encoding='utf-8'):
                try: r = json.loads(l)
                except ValueError: continue
                if r.get('status') != 200: continue
                name = re.sub(r'\s*::.*$', '', r.get('title') or '').strip()
                if not name: continue
                out[name.lower()].append(dict(id=re.search(r'citem=(\d+)', r['url']).group(1), lines=html_lines(r['html']), source='allakhazam (archive)'))
        except EOFError:
            pass
    return out


def field(lines, key):
    for i, x in enumerate(lines):
        if x.rstrip(':') == key.rstrip(':') and x.endswith(':') and i + 1 < len(lines): return lines[i + 1]
        if x.startswith(key) and len(x) > len(key) and not x.endswith(':'): return x[len(key):].strip()
    return None


def section(lines, key):
    """Lines after 'key:' up to the next 'Something:' header."""
    if key not in lines: return []
    out = []
    for x in lines[lines.index(key) + 1:]:
        if x.endswith(':') or x in ('Armor Modifiers:', 'Damage Modifiers:'): break
        out.append(x)
    return out


def num(v, default=0.0):
    m = re.search(r'-?\d+(?:\.\d+)?', str(v or ''))
    return float(m.group(0)) if m else default


def bonuses(lines):
    out, unknown = [], []
    for x in section(lines, 'Magical Bonuses:') + section(lines, 'Item Bonuses:'):
        m = re.match(r'(.+?):\s*([+-]?\d+)\s*(pts|%|lvls?)?', x)
        if not m: continue
        name, val = m.group(1).strip().lower(), int(m.group(2))
        name = re.sub(r'\s+', ' ', name)
        prop = next((d.get(n) for n in (name, name.rstrip('s'), name.replace(' magic', ''), name.replace(' magic', '').rstrip('s'))
                     for d in (STATS, SKILLS) if d.get(n)), None)
        if prop: out.append((prop, val))
        else: unknown.append(x)
    for x in section(lines, 'Focus Bonuses:'):
        m = re.match(r'(.+?):\s*([+-]?\d+)', x)
        if not m: continue
        name = m.group(1).strip().lower().replace(' focus', '')
        prop = FOCUS.get(name)
        if prop: out.append((prop, int(m.group(2))))
        else: unknown.append(x)
    return out, unknown


MODEL_ROWS = list(c.execute("select Item_Type, Object_Type, Realm, Level, Model from ItemTemplate where Model > 0"))


def borrow_model(item_type, object_type, realm, level):
    best = None
    for it, ot, r, lv, model in MODEL_ROWS:
        if it != item_type or ot != object_type: continue
        score = (0 if r == realm else 1 if r == 0 else 2, abs((lv or 0) - level))
        if best is None or score < best[0]: best = (score, model)
    if best is None:
        for it, ot, r, lv, model in MODEL_ROWS:
            if it == item_type:
                score = (0 if r == realm else 1, abs((lv or 0) - level))
                if best is None or score < best[0]: best = (score, model)
    return best[1] if best else 488


SPELLS = list(c.execute("select SpellID, Name, Type, Damage, DamageType, Value from Spell"))


def borrow_spell(lines):
    ability = section(lines, 'Magical Ability:')
    if not ability: return None, None
    text = {k.strip().lower(): v.strip() for k, _, v in (x.partition(':') for x in ability) if v}
    fn = (text.get('function') or '').lower()
    stype = SPELL_TYPE.get(fn)
    if not stype: return None, f"proc/charge function '{fn}' has no server equivalent"
    dmg = num(text.get('damage') or text.get('value') or text.get('amount'))
    dtype = DAMAGE.get((text.get('damage type') or '').lower(), -1)
    cands = [s for s in SPELLS if s[2] == stype and (dtype < 0 or s[4] == dtype)] or [s for s in SPELLS if s[2] == stype]
    if not cands: return None, f"no {stype} spell on the server"
    s = min(cands, key=lambda s: abs((s[3] or s[5] or 0) - dmg))
    return s[0], f"{fn} {dmg:g} -> spell {s[0]} {s[1]} ({s[2]} {s[3] or s[5]})"


def build(iid, need, page):
    L = page['lines']
    realm = REALM.get(field(L, 'Realm:') or '', REALM.get(need['realm'], 0))
    slot = field(L, 'Slot:') or 'Inventory'
    item_type = SLOT.get(slot, 40)
    skill = (field(L, 'Requires Skill:') or field(L, 'Weapon Skill:') or '').lower()
    object_type = 41 if item_type in (24, 26, 29, 32, 33, 35, 37) else 0
    dps_af = spd_abs = type_damage = hand = 0
    if skill.startswith('armor:'):
        object_type = ARMOR.get(skill.split(':', 1)[1].strip(), 31)
        dps_af = int(num(field(L, 'Armor Factor:')))
        spd_abs = int(num(field(L, 'Armor Absorb:')))
    elif skill in WEAPON or field(L, 'DPS:') or field(L, 'Shield Size:'):
        object_type = WEAPON.get(skill, 42 if field(L, 'Shield Size:') else 0)
        if object_type == 42 or field(L, 'Shield Size:'):
            object_type = 42
            type_damage = {'small': 1, 'medium': 2, 'large': 3}.get((field(L, 'Shield Size:') or '').lower(), 1)
            dps_af = int(round(num(field(L, '- ') or re.search(r'([\d.]+) Base DPS', ' '.join(L)) and re.search(r'([\d.]+) Base DPS', ' '.join(L)).group(1)) * 10))
            m = re.search(r'([\d.]+) Shield Speed', ' '.join(L))
            spd_abs = int(round(float(m.group(1)) * 10)) if m else 0
        else:
            dps_af = int(round(num(field(L, 'DPS:')) * 10))
            spd_abs = int(round(num(field(L, 'Delay:') or field(L, 'Speed:')) * 10))
            type_damage = DAMAGE.get((field(L, 'Damage Type:') or '').lower(), 0)
        hand = 1 if item_type == 12 else 2 if item_type == 11 or object_type in (17,) else 0
    level = int(num(field(L, 'Level to Attain:')) or num((field(L, 'Levels of Use:') or '').split('-')[0]) or 1)
    if not level and dps_af and object_type >= 31: level = max(1, dps_af // 2)
    bon, unknown = bonuses(L)
    row = dict(Id_nb=iid, Name=need['name'], Level=level, Durability=50000, MaxDurability=50000, Condition=50000, MaxCondition=50000,
               Quality=int(num(field(L, 'Quality:'), 100)), DPS_AF=dps_af, SPD_ABS=spd_abs, Hand=hand, Type_Damage=type_damage,
               Object_Type=object_type, Item_Type=item_type, Weight=int(round(num(field(L, 'Weight:')) * 10)),
               Bonus=int(num(field(L, 'Default Bonus:'))), BonusLevel=int(num(field(L, 'Bonus Level:'))),
               LevelRequirement=int(num(field(L, 'Level Req:'))), Realm=realm, AllowedClasses='0',
               IsPickable=1, IsDropable=1, CanDropAsLoot=0, IsTradable=0, Price=0, MaxCount=1, PackSize=1,
               PackageID='ClassicQuest', Description=f"Classic quest reward ({', '.join(need['quests'][:3])})")
    for k, (prop, val) in enumerate(bon[:10], 1):
        row[f'Bonus{k}Type'], row[f'Bonus{k}'] = prop, val
    notes = []
    model = borrow_model(item_type, object_type, realm, level)
    row['Model'] = model
    notes.append(f"model {model} borrowed (no period page records models)")
    spell, why = borrow_spell(L)
    if spell:
        charges = int(num(field(L, 'Charges:')))
        if charges or object_type in (0, 41) or item_type in (24, 26, 29, 32, 33, 35, 40):
            row.update(SpellID=spell, Charges=charges or 10, MaxCharges=charges or 10)
        else:
            row.update(ProcSpellID=spell, ProcChance=0)
        notes.append(why)
    elif why:
        notes.append(why)
    if unknown: notes.append('bonuses with no server property: ' + '; '.join(unknown))
    return row, notes


def main():
    need = json.load(open(os.path.join(HERE, 'reward_items_needed.json'), encoding='utf-8'))['items']
    pages = load_pages()
    # Quest items that are real equipment on their period page (a trade's Flint Knife, a turn-in's gem): built with
    # their stats under the quest item's own id (apply_dataquests prefers these rows over the plain quest item).
    prev = json.load(open(os.path.join(HERE, 'dataquest_preview.json'), encoding='utf-8'))
    for iid, name in prev.get('items', {}).items():
        if iid in need: continue
        for pg in pages.get(name.lower(), []):
            slot = field(pg['lines'], 'Slot:') or 'Inventory'
            if slot != 'Inventory':
                need[iid] = {'name': name, 'full': name, 'realm': '', 'quests': ['(quest item)'], 'equipment': True}
                break
    rows, report = [], {'built': {}, 'missing': {}}
    for iid, n in sorted(need.items()):
        cands = pages.get(n['name'].lower()) or pages.get(n['full'].lower()) or []
        realm_id = REALM.get(n['realm'], 0)
        if n.get('equipment'):
            cands = [pg for pg in cands if (field(pg['lines'], 'Slot:') or 'Inventory') != 'Inventory']
        cands = sorted(cands, key=lambda p: 0 if REALM.get(field(p['lines'], 'Realm:') or '', -1) in (realm_id, 0) else 1)
        if not cands:
            report['missing'][iid] = n
            continue
        row, notes = build(iid, n, cands[0])
        rows.append(row)
        report['built'][iid] = {'name': n['name'], 'page': cands[0]['id'], 'source': cands[0]['source'], 'notes': notes}
    json.dump(rows, open(os.path.join(HERE, 'reward_item_rows.json'), 'w', encoding='utf-8'), indent=1)
    json.dump(report, open(os.path.join(HERE, 'reward_items_report.json'), 'w', encoding='utf-8'), indent=1)
    print(f"reward items needed {len(need)} built {len(rows)} missing a page {len(report['missing'])}")


if __name__ == '__main__':
    main()
