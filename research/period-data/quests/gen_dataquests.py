"""Goal 10 generator stage 3 (dry run): resolved specs -> DataQuest rows + the quest items they need.
Writes dataquest_preview.json; touches nothing in the database.

DataQuest (GameServer/quests/QuestsMgr/DataQuest.cs): one row per quest, per-step lists joined with "|".
StepType: Kill 0/KillFinish 1, Deliver 2/3, Interact 4/5, Whisper 6/7, Search 8/9, Collect 10/11.
StepItemTemplates per step: "template[;chance]" - a kill/search step with a chance gives the item on its kill
(and advances only when the roll succeeds); advancing INTO a Deliver step hands the player that step's item.
So: talk -> Interact; kill xN -> N Kill steps; collect (drop) -> Kill steps carrying the drop + Collect turn-in;
deliver of an item the NPC gave -> the giving step's next step is Deliver with the item.
"""
import json, re, sys, os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
resolved = json.load(open(os.path.join(HERE, 'resolved.json'), encoding='utf-8'))

SIMPLE = {'talk', 'kill', 'deliver', 'whisper', 'search', 'collect'}
# Steps DataQuest has no type for: a journal step (Search, no search area) that ClassicQuests completes on its trigger.
CUSTOM = {'use_item', 'drop_item', 'travel', 'buy', 'trade', 'event', 'interact', 'quest', 'subquests', 'group', 'die_to', 'say'}
CLASS_IDS = {  # eCharacterClass ids for AllowedClasses
    'Paladin': 1, 'Armsman': 2, 'Scout': 3, 'Minstrel': 4, 'Theurgist': 5, 'Cleric': 6, 'Wizard': 7, 'Sorcerer': 8,
    'Infiltrator': 9, 'Friar': 10, 'Mercenary': 11, 'Necromancer': 12, 'Cabalist': 13, 'Fighter': 14, 'Elementalist': 15,
    'Acolyte': 16, 'AlbionRogue': 17, 'Mage': 18, 'Reaver': 19, 'Disciple': 20, 'Thane': 21, 'Warrior': 22,
    'Shadowblade': 23, 'Skald': 24, 'Hunter': 25, 'Healer': 26, 'Spiritmaster': 27, 'Shaman': 28, 'Runemaster': 29,
    'Bonedancer': 30, 'Berserker': 31, 'Savage': 32, 'Heretic': 33, 'Valkyrie': 34, 'Viking': 35, 'Mystic': 36,
    'Seer': 37, 'MidgardRogue': 38, 'Bainshee': 39, 'Eldritch': 40, 'Enchanter': 41, 'Mentalist': 42, 'Blademaster': 43,
    'Hero': 44, 'Champion': 45, 'Warden': 46, 'Druid': 47, 'Bard': 48, 'Nightshade': 49, 'Ranger': 50, 'Magician': 51,
    'Guardian': 52, 'Naturalist': 53, 'Stalker': 54, 'Animist': 55, 'Valewalker': 56, 'Forester': 57, 'Vampiir': 58,
    'Warlock': 59, 'Mauler_Alb': 60, 'Mauler_Mid': 61, 'Mauler_Hib': 62,
}
BASE_ALIASES = {'Rogue': None}  # realm-specific base class; resolved below

def coin(text):
    """'3s' / '1g 20s 5c' -> copper."""
    if not text: return 0
    total = 0
    for amount, unit in re.findall(r'(\d+)\s*([pgsc])', str(text).lower()):
        total += int(amount) * {'p': 10_000_000, 'g': 10_000, 's': 100, 'c': 1}[unit]
    return total

XP = json.load(open(os.path.join(HERE, 'xp_table.json')))  # cumulative xp to reach level N+1 (GamePlayer.XPForLevel)
# Median quest XP as a share of the level's span, from the 159 specs whose walkthrough gives a number.
BAND = [(5, 0.16), (10, 0.15), (20, 0.084), (30, 0.026), (40, 0.015), (50, 0.056)]

def quest_xp(value, level):
    level = max(1, min(49, int(level or 1)))
    span = XP[level] - XP[level - 1]
    if isinstance(value, (int, float)): return int(value)
    if value in (None, ''): return 0
    text = str(value).lower()
    if text == 'auto': return int(span * next(share for top, share in BAND if level <= top))
    words = {'quarter': 0.25, 'half': 0.5, 'three quarters': 0.75, '3/4': 0.75, 'one': 1, 'two': 2, 'three': 3, 'four': 4}
    m = re.search(r'(\d+(?:\.\d+)?)\s*bubble', text)
    n = float(m.group(1)) if m else next((v for k, v in words.items() if k in text), 0.5 if 'small' in text else 1)
    if 'almost' in text or 'nearly' in text: n *= 0.9
    return int(span * n / 10)

def item_id(name):
    if isinstance(name, list): name = name[0]  # a step that gives several things: its first is the step item
    return 'cq_' + re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')[:60]

def classes(spec):
    out = []
    for c in spec.get('classes') or []:
        if c == 'Rogue':
            c = {'Albion': 'AlbionRogue', 'Midgard': 'MidgardRogue', 'Hibernia': 'Stalker'}[spec['realm']]
        if c in CLASS_IDS: out.append(str(CLASS_IDS[c]))
    return out

def ready(q):
    if q.get('giver') is None: return False
    for i, s in enumerate(q['steps']):
        if s['do'] in CUSTOM:
            if custom_step(q, s, i) is None: return False
            continue
        if s['do'] not in SIMPLE: return False
        if s.get('target') is None and s['do'] in ('kill', 'collect') and event_spawn(q, s): continue
        if s.get('target') is None and s['do'] in ('talk', 'kill', 'deliver', 'whisper', 'collect'): return False
    return True

import sqlite3 as _sqlite
_tdb = _sqlite.connect(r"file:C:/OfflineDAoC/scratch/dbcopy.db?mode=ro", uri=True)
def _template(name):
    if not name: return None
    return _tdb.execute("select TemplateId, Level, Model from NpcTemplate where lower(Name)=lower(?) limit 1", (name,)).fetchone()

# Planned spawn points (plan_spawns.py, snapped to the navmesh): the height an event spawn's walkthrough loc lacks.
PLAN_PLACE = {e['name'].lower(): e['place'] for e in json.load(open(os.path.join(HERE, 'spawn_plan.json'), encoding='utf-8'))
              if (e.get('place') or {}).get('on_mesh') and e['place'].get('z') is not None}
APPEARS = re.compile(r'\b(appears?|pops?|summon\w*|spawns? when|will pop)\b', re.I)

def event_spawn(q, s):
    """A monster the walkthrough has appear on this step (on talking to an NPC, on another monster's death, or when you
    arrive): spawned for the player by ClassicQuests, even when monsters of that name live elsewhere in the world."""
    sp = s['spec']; sw = sp.get('spawn') if isinstance(sp.get('spawn'), dict) else {}
    on_talk, on_death = sw.get('on_talk') or sp.get('spawn_on_talk'), sw.get('on_death_of') or sp.get('spawn_on_death_of')
    # Owner 2026-10-07 (the 17 blocked quests): a named monster that shows up after you thin its camp (on_kills_of) or
    # "appears when you arrive" and has no NPC in the world is spawned when the player reaches its point.
    arrives = not s.get('target') and (sw.get('on_kills_of') or sp.get('spawn_on_kills_of') or sw.get('on_search') or
                                       APPEARS.search((sp.get('loc_note') or '') + ' ' + (sp.get('text') or '')))
    if not (on_talk or on_death or sw.get('for_player') or arrives or sp.get('do') == 'event'): return None
    def where(name):
        if not name: return None
        g = q.get('giver')
        if g and g.get('name', '').lower() == name.lower(): return g
        for o in q['steps']:
            t = o.get('target')
            if t and t.get('name', '').lower() == name.lower(): return t
        return None
    anchor = where(on_talk) or where(on_death) or s.get('marker') or (q.get('giver') if on_talk or on_death else None)
    planned = PLAN_PLACE.get((sp.get('npc') or '').lower())
    if planned and not (on_talk or on_death) and (not anchor or anchor.get('z') is None):
        anchor = planned
    if not anchor or anchor.get('region') is None: return None
    if anchor.get('z') is None and not (on_talk or on_death): return None
    anchor = dict(anchor, x=anchor.get('x') or 0, y=anchor.get('y') or 0, z=anchor.get('z') or 0)
    t = _template(sw.get('like')) or _template(sp.get('npc'))
    def num(v):
        m = re.search(r'\d+', str(v or ''))
        return int(m.group(0)) if m else 0
    level = num(sw.get('level')) or (num(t[1]) if t else 0) or num(q['spec'].get('level'))
    # Owner 2026-10-07: monsters that come for the player (on talking to an NPC, on the kill before) appear beside it
    # wherever it is (TriggerRadius 0); "appears when you get there" ones wait until the player is near the point.
    return {'Name': sp.get('npc'), 'TemplateId': t[0] if t else 0, 'Level': level,
            'Model': num(t[2]) if t and not t[0] else 0,
            'Region': anchor['region'], 'X': anchor['x'], 'Y': anchor['y'], 'Z': anchor['z'],
            'TriggerRadius': 0 if on_talk or on_death else 1200, 'DespawnSeconds': 600, 'Count': 1}

def strip_name(n):
    return re.sub(r'\s*\(.*?\)\s*$', '', n or '').strip()

def produced_before(q, i, item):
    """Does an earlier step put this item in the player's hands?"""
    low = (item or '').lower()
    for p in q['steps'][:i]:
        sp = p['spec']
        got = [sp.get('item') if p['do'] == 'collect' else None, sp.get('drop'), sp.get('drops'), sp.get('gives'),
               *(sp.get('trades') or {}).values()]
        if p['do'] == 'deliver' and (sp.get('returns_item') or sp.get('gives')): got.append(sp.get('item'))
        if any(g and g.lower() == low for g in got if isinstance(g, str)): return True
    return False

def place(s, radius=600):
    """Where a scripted step happens: the walkthrough's point, else anywhere in the named zone (its bounds as a circle)."""
    m = s.get('marker') or {}
    sp = s['spec']
    if m.get('region') is not None and m.get('x') is not None:
        return {'Region': m['region'], 'X': m['x'], 'Y': m['y'], 'Z': m.get('z') or 0,
                'Radius': max(int(sp.get('radius') or radius), 1500 if s.get('wide') else 0)}
    za = s.get('zone_area')
    if za: return {'Region': za['region'], 'X': za['x'], 'Y': za['y'], 'Z': 0, 'Radius': za['radius']}
    return None

READ_ONLY = re.compile(r'letter|journal|note|scroll|book|map|diary|tome|page|axe|charm', re.I)
NO_ITEM = re.compile(r'(coin|xp|\+|\s)+')

def custom_step(q, s, i):
    """(step type, target, step item, custom trigger) for a scripted step, or None when the data is not there."""
    sp, t = s['spec'], s.get('target') or {}
    kind = s['do']
    target = f"{t['name']};{t['region']}" if t else ''
    if kind in ('use_item', 'drop_item') or (kind == 'interact' and not t):
        item = sp.get('item') or sp.get('item_from_giver') or (sp.get('consumes') or [None])[0]
        if not item: return None
        where = place(s, 400 if kind == 'drop_item' else 600)
        if kind == 'interact' and sp.get('npc', '').startswith('<') and not where: return None
        c = {'Kind': 'use_item', 'Item': item_id(item),
             'Consume': kind == 'drop_item' or bool(sp.get('consumes')) or not READ_ONLY.search(item),
             'Give': not produced_before(q, i, item), '_item': item}
        if where and (s.get('marker') or sp.get('zone')): c.update(where)
        return (8, '', item_id(sp['gives']) if sp.get('gives') else '', c)
    if kind == 'interact':  # "read the scrolls and tell Masrim": a conversation with the named NPC
        return (4, target, '', None)
    if kind == 'travel' or (kind == 'event' and not sp.get('npc')):
        where = place(s, 500)
        if not where: return None
        return (8, '', '', dict(where, Kind='travel'))
    if kind == 'event':  # a monster that appears for the player: a kill step with an event spawn
        return (0, '', '', None) if event_spawn(q, s) else None
    if kind == 'buy':
        item = sp.get('item')
        if not item: return None
        # No merchant on this server sells it (checked: Ludlow has no barkeep or ale): the quest hands it over (ledger).
        return (8, '', '', {'Kind': 'has_item', 'Item': item_id(item), 'Give': True, '_item': item})
    if kind == 'trade':
        if not t or not sp.get('trades'): return None
        trades = {item_id(k): ('' if NO_ITEM.fullmatch(v or '') else item_id(v)) for k, v in sp['trades'].items()}
        names = {item_id(k): k for k in sp['trades']}
        names.update({item_id(v): v for v in sp['trades'].values() if not NO_ITEM.fullmatch(v or '')})
        c = {'Kind': 'trade', 'Target': t['name'], 'Trades': trades, '_items': names}
        if sp.get('from'):
            c['Drops'] = [{'Mob': m, 'Item': item_id(k), 'Chance': int(sp.get('chance') or 50)} for m in sp['from'] for k in sp['trades']]
        return (8, target, '', c)
    if kind in ('quest', 'subquests'):
        names = [sp['quest']] if kind == 'quest' else (sp.get('in_order') or sp.get('of') or [])
        names = list(dict.fromkeys(strip_name(x) for n in names for x in n.split(' | ')))
        if not names: return None
        return (8, '', '', {'Kind': 'quest', 'Quest': '|'.join(names), 'Count': int(sp.get('pick') or 0)})
    if kind == 'group':
        return (8, '', '', {'Kind': 'group'})
    if kind == 'say':  # words of power spoken aloud on a point (ClassicQuests OnSay)
        where = place(s, 800)
        if not where or not sp.get('keyword'): return None
        return (8, '', '', dict(where, Kind='say', Words=sp['keyword'], NightOnly=bool(sp.get('night_only'))))
    if kind == 'die_to':
        if not sp.get('npc'): return None
        return (8, target, '', {'Kind': 'die_to', 'Target': t.get('name') or sp['npc']})
    return None

# Walkthrough bodies (Allakhazam quest pages, kept in walkthroughs.jsonl): the recorded "You are awarded ..." lines.
WALK = {}
for _l in open(os.path.join(HERE, 'walkthroughs.jsonl'), encoding='utf-8'):
    try:
        _w = json.loads(_l)
        WALK[int(_w['id'])] = _w.get('body') or []
    except (ValueError, KeyError):
        pass

def step_awards(spec, steps, level):
    """{step index: (copper, xp)} for awards the walkthrough records mid-quest. Each award line belongs to the NPC who
    spoke last before it; consecutive xp/coin lines are one award. Awards at the last step are left to the spec's
    final reward (the same thing, counted once)."""
    m = re.search(r'\d+', spec['src'])
    body = WALK.get(int(m.group(0))) if m else None
    if not isinstance(body, list): return {}
    events, speaker, cur = [], None, None
    for line in body:
        sm = re.match(r"([A-Z][\w' -]{1,40}?) says,", line)
        if sm:
            speaker, cur = sm.group(1).strip(), None
            continue
        am = re.search(r'You are awarded (.*?)[.!]?$', line)
        if not am or not speaker: continue
        what = am.group(1)
        xm = re.search(r'([\d,]+) experience', what)
        xp = int(xm.group(1).replace(',', '')) if xm else (-1 if 'experience' in what else 0)
        cp = coin(' '.join(f"{n}{u[0]}" for n, u in re.findall(r'(\d+) (platinum|gold|silver|copper)', what)))
        if cur is not None and cur[0] == speaker and ((xp and not cur[2]) or (cp and not cur[1])):
            cur[1] += cp; cur[2] = cur[2] or xp
        else:
            cur = [speaker, cp, xp, len(events)]; events.append(cur)
            cur.append(body.index(line))
    # An award is mid-quest only when the same NPC talks again later on the page (a later visit); the last award of the
    # NPC who ends the quest is the final reward, already counted from the spec.
    def speaks_after(who, pos):
        return any(re.match(re.escape(who) + r" says,", l) for l in body[pos + 1:])
    events = [e for e in events if speaks_after(e[0], e[4])]
    out, start = {}, 0
    names = [st[1].split(';')[0].lower() for st in steps]
    for who, cp, xp, _, _ in events:
        hits = [k for k in range(start, len(steps)) if names[k] and (names[k] == who.lower() or who.lower() in names[k] or names[k] in who.lower())]
        if not hits: continue
        k = hits[0]
        start = k + 1
        if k == len(steps) - 1: continue
        if xp == -1: xp = quest_xp('auto', level) // 4  # "You are awarded experience!" with no number: a small share
        out[k] = (cp, xp)
    return out

DIALOGUE = json.load(open(os.path.join(HERE, 'dialogue.json'), encoding='utf-8')) if os.path.exists(os.path.join(HERE, 'dialogue.json')) else {}
CHAT = {}  # npc -> keyword -> reply, merged into the ClassicQuests config

STOP = set('that this with from have your they them their there what when will would could should about into some just been were very much more only than then also over such need here help come back know make take tell look good well like want'.split())

def accept_keyword(spec):
    """Offer text with one of its own words bracketed as the accept keyword: the recorded chain's last keyword when the
    walkthrough has one, else the longest plain word of the offer (later wins ties), else a word of the quest name."""
    import re as _re
    dlg = DIALOGUE.get(spec['src']) or {}
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
            return dlg['offer'], open_kw[-1]
    offer = (spec.get('offer') or '').strip()
    chosen = (spec.get('accept_keyword') or '').strip()
    if chosen and chosen.lower() in offer.lower():
        i = offer.lower().index(chosen.lower())
        return offer[:i] + '[' + offer[i:i + len(chosen)] + ']' + offer[i + len(chosen):], offer[i:i + len(chosen)]
    words = [(m.start(), m.group(0)) for m in _re.finditer(r"[A-Za-z][A-Za-z'-]{3,}", offer) if m.group(0).lower() not in STOP]
    if words:
        pos, word = max(words, key=lambda w: (len(w[1]), w[0]))
        return offer[:pos] + '[' + word + ']' + offer[pos + len(word):], word
    word = max(_re.findall(r"[A-Za-z][A-Za-z'-]{2,}", spec['name']) or [spec['name']], key=len)
    return (offer + (' ' if offer else '') + '[' + word + ']').strip(), word

def source_texts(spec, steps):
    """Step 1: the giver's recorded line on accepting; with a checked page and no recorded line, the step's own
    instruction stands in (owner placeholder rule). Later steps: recorded lines only."""
    dlg = DIALOGUE.get(spec['src']) or {}
    out = [''] * len(steps)
    if dlg.get('accept_line'): out[0] = dlg['accept_line']
    elif dlg.get('checked'): out[0] = steps[0][3]
    return [t.replace('|', '/') for t in out]

def target_texts(spec, steps, giver_names=()):
    """What a talk/turn-in NPC says when its step ends: the giver's recorded turn-in lines in order for the steps that
    return to the giver (the last step's line is the FinishText), other NPCs' recorded lines for theirs."""
    dlg = DIALOGUE.get(spec['src']) or {}
    lines, turnins = dlg.get('npc_lines') or {}, list(dlg.get('giver_turnins') or [])
    gnames = {n.lower() for n in giver_names} | {((spec.get('giver') or {}).get('name') or '').lower()}
    out = []
    for k, st in enumerate(steps):
        npc = st[1].split(';')[0]
        text = ''
        if st[0] in (2, 4, 6, 10) and npc.lower() in gnames and turnins:
            text = turnins.pop(0)
        elif st[0] in (2, 3, 4, 5, 6, 7, 10, 11) and npc.lower() not in gnames:
            text = lines.get(npc) or ''
        out.append(text.replace('|', '/'))
    return out

def server_name(q, npc):
    """The server's spelling of a walkthrough NPC name (the giver or a step's target), so its chat answers in game."""
    low = (npc or '').lower()
    g, gs = q.get('giver') or {}, q.get('giver_spec') or {}
    if g and (low == (gs.get('name') or '').lower() or low == g.get('name', '').lower()): return g['name']
    for st in q['steps']:
        t = st.get('target')
        if t and low in ((st['spec'].get('npc') or '').lower(), t['name'].lower()): return t['name']
    import difflib
    names = [g.get('name')] + [st['target']['name'] for st in q['steps'] if st.get('target')]
    close = difflib.get_close_matches(npc, [n for n in names if n], n=1, cutoff=0.8)
    return close[0] if close else npc

def build(q):
    spec = q['spec']
    for npc, chat in ((DIALOGUE.get(spec['src']) or {}).get('chat') or {}).items():
        # A trainer quest's conversation belongs to every class trainer that offers it.
        names = [t['name'] for t in (q.get('class_givers') or {}).values()] if npc in ('Trainer', 'Class Trainer') else [server_name(q, npc)]
        for name in names:
            for kw, reply in chat.items():
                CHAT.setdefault(name, {}).setdefault(kw, reply)
    steps = []  # (type, target "name;region", item template, step text, target text, marker, named mob id)
    items = {}
    advance = {}  # step index -> whispered keyword (DataQuest AdvanceText)
    spans = []  # plan step -> (first, end) generated step indexes
    class_tgts = {}  # generated step index -> {class: (target, marker)}
    plan = q['steps']
    for i, s in enumerate(plan):
        sp = s['spec']; t = s.get('target') or {}
        target = f"{t['name']};{t['region']}" if t else ''
        if not t and s['do'] in ('kill', 'collect'):
            ev = event_spawn(q, s)
            if ev: target = f"{ev['Name']};{ev['Region']}"
        if not s.get('marker') and s['do'] in ('kill', 'collect') and not t:
            pass
        text = sp.get('text', '')
        marker = s.get('marker') if (s.get('marker') or {}).get('z') is not None else None
        if marker is None and s['do'] in ('kill', 'collect', 'event'):
            ev = event_spawn(q, s)  # the red dot goes where the step's monster will appear
            if ev and ev['TriggerRadius']: marker = {'region': ev['Region'], 'x': ev['X'], 'y': ev['Y'], 'z': ev['Z']}
        # Owner 2026-10-07: every quest step with a known place shows its red dot. A walkthrough loc carries no height:
        # the step's NPC where it really stands, else the loc itself (map dots only need x and y outdoors).
        if marker is None and t and t.get('region') is not None and t.get('x') is not None:
            marker = {'region': t['region'], 'x': t['x'], 'y': t['y'], 'z': t.get('z') or 0}
        if marker is None and (s.get('marker') or {}).get('x') is not None and s['marker'].get('region') is not None:
            marker = {'region': s['marker']['region'], 'x': s['marker']['x'], 'y': s['marker']['y'], 'z': 0}
        if marker is None and s['do'] in CUSTOM | {'search'}:
            w = place(s)  # a scripted step's point; a whole-zone area is too wide to mark
            if w and 0 < w['Radius'] <= 6000: marker = {'region': w['Region'], 'x': w['X'], 'y': w['Y'], 'z': w.get('Z') or 0}
        named = t.get('mob_id') if t and s['do'] in ('kill', 'collect') and t['name'][:1].isupper() else None
        start = len(steps)
        if s['do'] == 'talk':
            steps.append([4, target, '', text, sp.get('say', '')])
        elif s['do'] == 'whisper':
            # "say [defeated] or [victorious]": DataQuest takes one word; the first one, the journal names both.
            words = sp.get('keywords') or []
            keyword = (sp.get('keyword') or sp.get('whisper') or (words[0] if words else '')).strip()
            if len(words) > 1: text += f" (either answer works here: {words[0]})"
            # The journal names the words to whisper (journal text, not NPC speech).
            steps.append([6, target, '', text + (f" (whisper: {keyword})" if keyword else ''), sp.get('say', '')])
            advance[len(steps) - 1] = keyword
        elif s['do'] == 'kill':
            for k in range(max(1, int(sp.get('count') or 1))):
                n = max(1, int(sp.get('count') or 1))
                steps.append([0, target, '', text + (f" ({k + 1}/{n})" if n > 1 else ''), ''])
        elif s['do'] == 'collect':
            item = sp['item']; iid = item_id(item); items[iid] = item
            chance = int(sp.get('chance') or 100)
            n = max(1, int(sp.get('count') or 1))
            for k in range(n):
                steps.append([0, target, f"{iid};{chance}" if chance < 100 else iid, text + (f" ({k + 1}/{n})" if n > 1 else ''), ''])
        elif s['do'] == 'deliver' and not (sp.get('item') or sp.get('item_from_giver')):
            # "Return to X" with nothing to hand over is a conversation, not a delivery (DataQuest needs an item).
            steps.append([4, target, '', text, sp.get('say', '')])
        elif s['do'] == 'deliver':
            item = sp.get('item') or sp.get('item_from_giver')
            iid = item_id(item) if item else ''
            if item: items[iid] = item
            # A dropped item is turned in with Collect (Deliver would hand the player a second copy).
            dropped = any(p['do'] == 'collect' and p['spec'].get('item') == item for p in plan[:i])
            steps.append([10 if dropped else 2, target, iid, text, sp.get('say', '')])
        elif s['do'] in CUSTOM:
            stype, ctarget, citem, custom = custom_step(q, s, i)
            if custom:
                if custom.get('_item'): items[custom['Item']] = custom.pop('_item')
                for iid, nm in (custom.pop('_items', None) or {}).items(): items[iid] = nm
            if citem: items[citem] = sp['gives'][0] if isinstance(sp['gives'], list) else sp['gives']
            if stype == 0:  # an event monster: killed like any other, spawned for the player
                ev = event_spawn(q, s)
                steps.append([0, f"{ev['Name']};{ev['Region']}", '', text, ''])
            elif stype == 4:
                steps.append([4, ctarget, '', text, sp.get('say', '')])
            else:
                steps.append([8, ctarget, citem, text, '', None, None, None, None, custom])
        elif s['do'] == 'search':
            m = s.get('marker') or {}
            area = None
            if m.get('x') is not None and m.get('region') is not None:
                area = {'text': (sp.get('found') or '').replace(';', ',').replace('|', '/'), 'region': m['region'], 'x': m['x'],
                        'y': m['y'], 'radius': max(int(sp.get('radius') or 300), 1500 if s.get('wide') else 0), 'seconds': int(sp.get('seconds') or 5)}
            elif place(s):
                # No point recorded ("the crates in the slaver camp"): search anywhere in the named zone (owner 2026-10-07,
                # the 17 blocked quests); the journal text says where.
                w = place(s)
                area = {'text': (sp.get('found') or '').replace(';', ',').replace('|', '/'), 'region': w['Region'], 'x': w['X'],
                        'y': w['Y'], 'radius': w['Radius'], 'seconds': int(sp.get('seconds') or 5)}
            steps.append([8, '', '', text, '', None, None, None, area])
        spawn = event_spawn(q, s) if s['do'] in ('kill', 'collect', 'event') else None
        spans.append((start, len(steps)))
        if s.get('class_targets'):  # "your trainer" / "another trainer": each class row's own NPC
            for k in range(start, len(steps)):
                class_tgts[k] = {cls: (f"{t['name']};{t['region']}", dict(region=t['region'], x=t['x'], y=t['y'], z=t['z']))
                                 for cls, t in s['class_targets'].items()}
        for k in range(start, len(steps)):
            # A group ("two youths") all appear on its first step; the later steps only respawn one if it went missing.
            per = dict(spawn, Count=len(steps) - start if k == start else 1) if spawn else None
            if len(steps[k]) > 5:  # search steps already carry their slots
                steps[k][5:8] = [marker, named, per]
            else:
                steps[k] += [marker, named, per, None]
    if not steps: return None, items
    # Gifts: what each step hands the player. The next step being a delivery of it: DataQuest gives it as that step
    # begins. Else the step's own item slot (kill, talk, whisper, search, scripted steps give it on completion). The
    # rest: granted on the next step by ClassicQuests (and again if lost). The last step's gifts are final rewards.
    grants, final_items = {}, []
    for i, s in enumerate(plan):
        if i >= len(spans): break
        a, b = spans[i]
        if a == b: continue
        sp, t = s['spec'], s.get('target') or {}
        gifts = []
        for g in (sp.get('gives'), sp.get('drop') if s['do'] == 'kill' else None, sp.get('drops') if s['do'] == 'kill' else None):
            gifts += g if isinstance(g, list) else [g]
        if s['do'] == 'deliver' and sp.get('returns_item') and sp.get('item'): gifts.append(sp['item'])
        gifts = [g for g in dict.fromkeys(gifts) if isinstance(g, str) and g.strip() and not re.match(r'(coin|xp)\b', g, re.I)
                 and not g.startswith('<')]
        if not gifts: continue
        for g in gifts: items[item_id(g)] = g
        nxt = steps[b] if b < len(steps) else None
        if nxt and nxt[0] in (2, 3):
            gifts = [g for g in gifts if item_id(g) != nxt[2]]
        if b == len(steps):
            final_items += [item_id(g) for g in gifts]
            continue
        last = steps[b - 1]
        if gifts and last[0] in (0, 4, 6, 8) and not last[2]:
            last[2] = item_id(gifts.pop(0))
        if gifts:
            grants[b] = ([item_id(g) for g in gifts], t.get('name') if s['do'] in ('talk', 'deliver', 'whisper', 'interact') and t else None)
    steps[-1][0] += 1  # the last step finishes the quest (each *Finish type is base + 1)
    offer_text, accept_word = accept_keyword(spec)
    search_areas = []
    for i, st in enumerate(steps):
        if st[0] in (8, 9) and st[8]:
            a = st[8]
            search_areas.append(f"SEARCH;{i + 1};{a['text']};{a['region']};{a['x']};{a['y']};{a['radius']};{a['seconds']}")
    rewards = spec.get('rewards') or {}
    awards = step_awards(spec, steps, spec.get('level'))
    for i, ps in enumerate(plan):  # a step's own recorded award ("coin": "4s", "xp": 20 on that step of the spec)
        if i < len(spans) and spans[i][1] - 1 < len(steps) - 1 and (ps['spec'].get('coin') or ps['spec'].get('xp')):
            awards[spans[i][1] - 1] = (coin(ps['spec'].get('coin')), quest_xp(ps['spec'].get('xp'), spec.get('level')) if ps['spec'].get('xp') else 0)
    row = {
        # The listing's disambiguators ("(Mid)", "(level 30)", "(Shaman)", "(version 1)") are not part of the in-game name.
        'Name': re.sub(r'\s*\(.*?\)\s*$', '', spec['name']).strip() or spec['name'], 'StartType': 0, 'StartName': q['giver']['name'], 'StartRegionID': q['giver']['region'],
        # StartType 0 (Standard) starts on a whispered AcceptText. Owner 2026-10-07: no generic "Will you help?"; a word of
        # the NPC's own offer is the clickable keyword, even if it is not the period one.
        'Description': offer_text, 'AcceptText': accept_word, 'StepType': '|'.join(str(s[0]) for s in steps),
        'TargetName': '|'.join(s[1] for s in steps),
        'StepItemTemplates': '|'.join('' if s[0] in (10, 11) else s[2] for s in steps),
        'SourceName': '|'.join(search_areas),
        # Turn-ins: DataQuest ignores a handed item unless CollectItemTemplate lists it for the step (owner: Troya never
        # took the larva skin). Whisper steps advance on AdvanceText.
        'CollectItemTemplate': '|'.join(s[2].split(';')[0] if s[0] in (2, 3, 10, 11) else '' for s in steps),
        'AdvanceText': '|'.join(advance.get(i, '') for i in range(len(steps))),
        # One SourceText per step (the NPC's line as the step begins); DataQuest logs an error per step without it.
        # One SourceText per step (the NPC's own line as the step begins, from the walkthrough's recorded dialogue only;
        # owner 2026-10-07: never walkthrough narration in NPC speech). DataQuest errors on a step without an entry.
        # Placeholder rule (owner 2026-10-07): only when the walkthrough page was checked and records no dialogue for the
        # step may its instruction stand in as the NPC's line; an unchecked quest gets no placeholder.
        'SourceText': '|'.join(source_texts(spec, steps)),
        'TargetText': '|'.join(target_texts(spec, steps, [q['giver']['name']] + [t['name'] for t in (q.get('class_givers') or {}).values()])),
        'StepText': '|'.join(s[3].replace('|', '/') for s in steps),
        'MinLevel': spec.get('level', 1), 'MaxLevel': spec.get('max', 50), 'MaxCount': int(spec.get('limit') or (30 if spec.get('type') == 'kill_task' or all(st['do'] == 'trade' for st in plan) else 1)),
        'RewardMoney': '|'.join([str(awards.get(k, (0, 0))[0]) for k in range(len(steps) - 1)] + [str(coin(rewards.get('coin')))]),
        'RewardXP': '|'.join([str(awards.get(k, (0, 0))[1]) for k in range(len(steps) - 1)] + [str(quest_xp(rewards.get('xp'), spec.get('level')))]),
        # Reawakening is part of Cad Goddeau A on the period server (ledger 2026-10-07 05:00).
        'QuestDependency': '|'.join({'Reawakening': 'Cad Goddeau A'}.get(d, d) for d in
                                    (re.sub(r'\s*\(.*?\)\s*$', '', r).strip() for r in spec.get('requires') or [])),
        'AllowedClasses': '|'.join(classes(spec)),
        'FinishText': ((DIALOGUE.get(spec['src']) or {}).get('finish') or '').replace('|', '/'),
        'src': spec['src'], 'realm': spec['realm'],
        'ClassType': 'DOL.GS.Quests.ClassicQuestStep',
        '_markers': [s[5] for s in steps], '_named': [s[6] for s in steps if s[6]], '_spawns': [s[7] for s in steps],
        '_custom': [s[9] if len(s) > 9 else None for s in steps],
        '_grants': [grants.get(k) for k in range(len(steps))],
        '_class_targets': class_tgts,
        'FinalRewardItemTemplates': '|'.join(dict.fromkeys(final_items)),
    }
    return row, items

import rewards as RW
# Period classes per realm (Catacombs and later classes have no trainer here; Sluaghbinder takes only its own line).
REALM_CLASSES = {
    'Albion': ['Paladin', 'Armsman', 'Scout', 'Minstrel', 'Theurgist', 'Cleric', 'Wizard', 'Sorcerer', 'Infiltrator', 'Friar',
               'Mercenary', 'Necromancer', 'Cabalist', 'Reaver', 'Fighter', 'Acolyte', 'AlbionRogue', 'Mage', 'Elementalist', 'Disciple'],
    'Midgard': ['Thane', 'Warrior', 'Shadowblade', 'Skald', 'Hunter', 'Healer', 'Spiritmaster', 'Shaman', 'Runemaster',
                'Bonedancer', 'Berserker', 'Savage', 'Viking', 'Mystic', 'Seer', 'MidgardRogue'],
    'Hibernia': ['Eldritch', 'Enchanter', 'Mentalist', 'Blademaster', 'Hero', 'Champion', 'Warden', 'Druid', 'Bard', 'Nightshade',
                 'Ranger', 'Animist', 'Valewalker', 'Guardian', 'Naturalist', 'Stalker', 'Magician', 'Forester'],
}
ID_CLASS = {v: k for k, v in CLASS_IDS.items()}
REWARD_ITEMS = {}  # item id -> {'name', 'realm', 'quests'} for the reward item builder
LEDGER_REWARDS = []  # reward entries the walkthrough left unrecorded

STEP_FIELDS = ('StepType', 'TargetName', 'StepItemTemplates', 'CollectItemTemplate', 'AdvanceText', 'SourceText', 'TargetText',
               'StepText', 'RewardMoney', 'RewardXP')

def reward_id(name, realm):
    return 'cq_' + re.sub(r'[^a-z0-9]+', '_', (realm[:3] + ' ' + name).lower()).strip('_')[:60]

def add_choose_step(row, names, npc, region):
    """A last step at the NPC who ends the quest: it names the rewards as keywords; whispering one gives that item."""
    choices, keys = {}, {}
    for n in names:
        key = RW.display_name(n)
        if key in keys.values(): key = n
        keys[n] = key
        choices[key] = reward_id(n, row['realm'])
        REWARD_ITEMS.setdefault(choices[key], {'name': RW.display_name(n), 'full': n, 'realm': row['realm'], 'quests': set()})['quests'].add(row['Name'])
    f = {k: (row.get(k) or '').split('|') for k in STEP_FIELDS}
    n = len(f['StepType'])
    for k in f:
        f[k] += [''] * (n - len(f[k]))
    last = int(f['StepType'][-1])
    if last % 2 == 1: f['StepType'][-1] = str(last - 1)
    money, xp = f['RewardMoney'][-1] or '0', f['RewardXP'][-1] or '0'
    f['RewardMoney'][-1], f['RewardXP'][-1] = '0', '0'
    f['StepType'].append('9')
    f['TargetName'].append(f"{npc};{region}")
    for k in ('StepItemTemplates', 'CollectItemTemplate', 'AdvanceText', 'TargetText'): f[k].append('')
    listing = ', '.join(f"[{k}]" for k in choices)
    # Placeholder line (the walkthroughs do not record the period wording of the reward choice); listed in the ledger.
    f['SourceText'].append(f"Choose your reward: {listing}.")
    f['StepText'].append(f"Choose your reward: whisper {npc} the name of the item you want ({', '.join(choices)}).")
    f['RewardMoney'].append(money)
    f['RewardXP'].append(xp)
    for k in f: row[k] = '|'.join(f[k])
    row['_markers'].append(row['_markers'][-1] if row['_markers'] else None)
    row['_spawns'].append(None)
    row['_custom'].append({'Kind': 'choose', 'Target': npc, 'Choices': choices})
    row['_grants'].append(None)

def apply_rewards(row, spec, cls):
    fixed, groups = RW.reward_plan(spec, cls, row['StartName'])
    ids = [i for i in (row.get('FinalRewardItemTemplates') or '').split('|') if i]
    for n in fixed:
        iid = reward_id(n, row['realm'])
        REWARD_ITEMS.setdefault(iid, {'name': RW.display_name(n), 'full': n, 'realm': row['realm'], 'quests': set()})['quests'].add(row['Name'])
        ids.append(iid)
    row['FinalRewardItemTemplates'] = '|'.join(dict.fromkeys(ids))
    if groups:
        last_target = (row['TargetName'].split('|')[-1] or '').split(';')
        npc, region = (last_target[0], last_target[1]) if last_target[0] else (row['StartName'], row['StartRegionID'])
        for g in groups: add_choose_step(row, g, npc, region)
    return row

def copy_row(row, **over):
    out = dict(row, **over)
    for k in ('_markers', '_named', '_spawns', '_custom', '_grants'): out[k] = list(row[k])
    return out

rows, items, skipped = [], {}, Counter()
for q in resolved:
    # One-time drops are world loot (LootOTD, apply_world.py), not quests.
    if q['spec'].get('type') == 'otd': skipped['one-time drop (world loot)'] += 1; continue
    if not ready(q): skipped['not ready'] += 1; continue
    row, its = build(q)
    if row is None: skipped['already in game (Atlas XP Item quest)' if q['spec'].get('already_in_game') else 'no steps'] += 1; continue
    items.update(its)
    if q.get('class_givers'):
        # A trainer quest: one row per class, offered by that class's own trainer and only to that class.
        for cls, t in q['class_givers'].items():
            cid = CLASS_IDS.get(t.get('cls') or cls)
            if cid is None: skipped['trainer class without id'] += 1; continue
            per = copy_row(row, StartName=t['name'], StartRegionID=t['region'], AllowedClasses=str(cid))
            if row['_class_targets']:
                tn = per['TargetName'].split('|')
                for k, by_cls in row['_class_targets'].items():
                    if cls in by_cls:
                        tn[k] = by_cls[cls][0]
                        per['_markers'][k] = by_cls[cls][1]
                per['TargetName'] = '|'.join(tn)
            rows.append(apply_rewards(per, q['spec'], t.get('cls') or cls))
        continue
    LEDGER_REWARDS.extend((q['spec']['name'], m) for m in RW.dropped_markers(q['spec']))
    keyed = RW.class_keys(q['spec'].get('rewards') or {})
    if keyed:
        # Rewards differ by class: a row per listed class, and one for the realm's other classes allowed the quest.
        allowed = [ID_CLASS[int(c)] for c in row['AllowedClasses'].split('|') if c] or REALM_CLASSES.get(q['realm'], [])
        rogue = {'Rogue': {'Albion': 'AlbionRogue', 'Midgard': 'MidgardRogue', 'Hibernia': 'Stalker'}.get(q['realm'])}
        keyed = {rogue.get(k, k) for k in keyed}
        mine = [c for c in allowed if c in keyed]
        rest = [c for c in allowed if c not in keyed]
        for c in mine:
            rows.append(apply_rewards(copy_row(row, AllowedClasses=str(CLASS_IDS[c])), q['spec'], c))
        if rest:
            rows.append(apply_rewards(copy_row(row, AllowedClasses='|'.join(str(CLASS_IDS[c]) for c in rest)), q['spec'], None))
        continue
    rows.append(apply_rewards(row, q['spec'], None))
FIRST_ID = 20000  # reserved block for classic quests (existing DataQuest ids are 1-408)
RACES = {q['spec']['src']: q['spec']['races'] for q in resolved if q['spec'].get('races')}
# Stable ids: a quest already in the database keeps its id (a player's quest in progress is stored by id); new
# quests take the next free ones.
import sqlite3 as _sq
_db = _sq.connect(r"file:C:/OfflineDAoC/scratch/dbcopy.db?mode=ro", uri=True)
known = {(n, s, str(a or '')): i for i, n, s, a in _db.execute("select ID, Name, StartName, AllowedClasses from DataQuest where ID >= ?", (FIRST_ID,))}
used = set(known.values())
next_id = max(used | {FIRST_ID - 1}) + 1
config = {'Quests': {}, 'QuestMonsterIds': []}
named_ids = set()
for n, r in enumerate(rows):
    key = (r['Name'], r['StartName'], str(r['AllowedClasses'] or ''))
    if key in known and known[key] in used:
        r['ID'] = known[key]; used.discard(known[key])
    else:
        r['ID'] = next_id; next_id += 1
    types = [int(t) for t in r['StepType'].split('|')]
    targets = r['TargetName'].split('|')
    stepitems = r['StepItemTemplates'].split('|')
    steps_out = []
    spawns = r.pop('_spawns')
    customs = r.pop('_custom')
    r.pop('_class_targets', None)
    grants = r.pop('_grants')
    for k, m in enumerate(r.pop('_markers')):
        info = {'Marker': {'Region': m['region'], 'X': m['x'], 'Y': m['y'], 'Z': m['z']}} if m else {}
        if spawns[k]:
            # The red marker points where the monster will appear, not at same-named monsters elsewhere.
            info['Spawn'] = spawns[k]
            info['Marker'] = {'Region': spawns[k]['Region'], 'X': spawns[k]['X'], 'Y': spawns[k]['Y'], 'Z': spawns[k]['Z']}
        # A Deliver step's item is handed over by the NPC of the step before it; if the player loses it, that NPC
        # gives another (owner: no quest may be lost).
        if types[k] in (2, 3) and stepitems[k] and k > 0 and targets[k - 1]:
            info['NeedsItem'] = stepitems[k]
            info['Issuer'] = targets[k - 1].split(';')[0]
        if customs[k]:
            info['Custom'] = customs[k]
        if grants[k]:
            info['Grant'] = grants[k][0]
            if grants[k][1]: info['GrantFrom'] = grants[k][1]
        steps_out.append(info)
    config['Quests'][str(r['ID'])] = {'Steps': [None] + steps_out}
    if RACES.get(r['src']): config['Quests'][str(r['ID'])]['Races'] = RACES[r['src']]  # DataQuest has no race limit
    named_ids.update(r.pop('_named'))
config['QuestMonsterIds'] = sorted(named_ids)
config['Chat'] = CHAT
json.dump(config, open(os.path.join(HERE, 'classic-quests.preview.json'), 'w', encoding='utf-8'), indent=1)
print(f"classic-quests.preview.json: quests={len(config['Quests'])} questMonsters={len(named_ids)} "
      f"steps with markers={sum(1 for q in config['Quests'].values() for st in q['Steps'][1:] if st)}")
names = Counter((r['realm'], r['Name']) for r in rows)
dupes = [k for k, v in names.items() if v > 1]
# One-time drops' items (world loot, apply_world.py) are period equipment too: built with the rewards.
for q in resolved:
    sp = q['spec']
    if sp.get('type') != 'otd': continue
    for n in ([sp['item']] if sp.get('item') else []) + list((sp.get('item_by_class') or {}).values()):
        if isinstance(n, str) and n and not n.startswith('<'):
            REWARD_ITEMS.setdefault('cq_otd_' + re.sub(r'[^a-z0-9]+', '_', n.lower()).strip('_')[:54],
                                    {'name': RW.display_name(n), 'full': n, 'realm': sp['realm'], 'quests': set()})['quests'].add(sp['name'])
for v in REWARD_ITEMS.values(): v['quests'] = sorted(v['quests'])
json.dump({'items': REWARD_ITEMS, 'unrecorded': LEDGER_REWARDS}, open(os.path.join(HERE, 'reward_items_needed.json'), 'w', encoding='utf-8'), indent=1)
print(f"reward items needed={len(REWARD_ITEMS)} unrecorded reward entries={len(LEDGER_REWARDS)}")
json.dump({'rows': rows, 'items': items, 'dupes': dupes}, open(os.path.join(HERE, 'dataquest_preview.json'), 'w', encoding='utf-8'), indent=1)
print(f"rows={len(rows)} items={len(items)} skipped={dict(skipped)} duplicate names={len(dupes)}")
print(Counter(r['realm'] for r in rows))
print("steps per quest:", Counter(len(r['StepType'].split('|')) for r in rows).most_common(8))

# ---- Quest items (dry run): model borrowed from existing items sharing a keyword ----
import sqlite3
DB = r"file:C:/OfflineDAoC/scratch/dbcopy.db?mode=ro"  # lock-free copy of the live DB (cp it first)
con = sqlite3.connect(DB, uri=True)
# Classic quest items already loaded are replaced on apply, so only other items count as collisions.
existing_ids = {r[0].lower() for r in con.execute("select Id_nb from ItemTemplate where PackageID is null or PackageID <> 'ClassicQuest'")}
named = con.execute("select lower(Name), Model from ItemTemplate where Item_Type in (0,40) and Model > 0").fetchall()
def donor(name):
    for word in sorted(re.findall(r'[a-z]+', name.lower()), key=len, reverse=True):
        if len(word) < 4: continue
        models = Counter(model for n, model in named if re.search(r'\b' + word + r'\b', n))
        if models: return models.most_common(1)[0][0], word
    return 488, None  # a plain sack
item_rows, collisions = [], []
for iid, name in sorted(items.items()):
    if iid.lower() in existing_ids: collisions.append(iid); continue
    model, word = donor(name)
    item_rows.append(dict(Id_nb=iid, Name=name, Level=1, Item_Type=40, Model=model, Weight=1, Quality=100,
        Durability=50000, MaxDurability=50000, Condition=50000, MaxCondition=50000, IsPickable=1, IsDropable=1,
        CanDropAsLoot=0, IsTradable=0, Price=0, MaxCount=1, PackSize=1, PackageID='ClassicQuest', donor=word))
prev = json.load(open(os.path.join(HERE, 'dataquest_preview.json'), encoding='utf-8'))
prev['item_rows'] = item_rows; prev['item_collisions'] = collisions
json.dump(prev, open(os.path.join(HERE, 'dataquest_preview.json'), 'w', encoding='utf-8'), indent=1)
print(f"item rows={len(item_rows)} collisions with existing ids={len(collisions)} generic sack={sum(1 for r in item_rows if r['donor'] is None)}")
