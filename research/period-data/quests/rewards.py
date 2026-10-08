"""Goal 10 quest rewards: what each class gets at the end of a classic quest (from the walkthrough's reward lines).

A spec's rewards come in several shapes (all from Allakhazam's quest pages):
  items: {class: [names]} ('*' = everyone)  - given at the end; with choice: true the class picks one of its list
  items_by_class: same as items
  choice_by_class: {class: [names]} or [names] - pick one
  choice / choice2 / belt_choice / weapon_choice / choice_by_armor: [names] - pick one from each list
  items_by_choice: {answer: name} - pick one
  items_by_start: {giver: {...same shapes...}} - by which NPC gave the quest
  class_belt_choice: name - one item
  material_choice: words only (the armour material of a pick-one item) - no item of its own
reward_plan(spec, cls, start) -> (fixed names, [choice groups]) for one class row. Names in <angle brackets> are
the walkthrough's own "not recorded" markers and are dropped (listed in the ledger)."""
import re

CHOICE_LISTS = ('choice', 'choice2', 'belt_choice', 'weapon_choice', 'choice_by_armor')


def _clean(names):
    return [n for n in names if isinstance(n, str) and n.strip() and not n.startswith('<')]


def _for_class(value, cls):
    """A {class: [names]} map's list for one class (with the '*' entries), or a plain list as is."""
    if isinstance(value, dict):
        out = list(value.get('*') or [])
        for k, v in value.items():
            if k != '*' and cls and k.lower() == cls.lower():
                out += v if isinstance(v, list) else [v]
        return out
    if isinstance(value, list):
        return value
    return [value] if isinstance(value, str) else []


def class_keys(rewards):
    """Classes whose rewards differ (a row per class is needed for these)."""
    keys = set()
    for k in ('items', 'items_by_class', 'choice_by_class'):
        v = rewards.get(k)
        if isinstance(v, dict):
            keys |= {c for c in v if c != '*'}
    for v in (rewards.get('items_by_start') or {}).values():
        if isinstance(v, dict):
            for k in ('items', 'items_by_class', 'choice_by_class'):
                if isinstance(v.get(k), dict):
                    keys |= {c for c in v[k] if c != '*'}
    return keys


def reward_plan(spec, cls=None, start=None):
    rw = dict(spec.get('rewards') or {})
    by_start = rw.get('items_by_start')
    if isinstance(by_start, dict) and start:
        for giver, part in by_start.items():
            if giver.lower() == start.lower() and isinstance(part, dict):
                rw.update(part)
    fixed, groups = [], []
    items = _clean(_for_class(rw.get('items'), cls)) + _clean(_for_class(rw.get('items_by_class'), cls))
    if rw.get('choice') is True and len(items) > 1:
        groups.append(items)
    else:
        fixed += items
    cbc = _clean(_for_class(rw.get('choice_by_class'), cls))
    if cbc: groups.append(cbc)
    for k in CHOICE_LISTS:
        v = rw.get(k)
        if isinstance(v, list):
            v = _clean(v)
            if len(v) > 1: groups.append(v)
            elif v: fixed += v
    ibc = rw.get('items_by_choice')
    if isinstance(ibc, dict):
        v = _clean(list(ibc.values()))
        if v: groups.append(v)
    if isinstance(rw.get('class_belt_choice'), str):
        fixed += _clean([rw['class_belt_choice']])
    return list(dict.fromkeys(fixed)), [list(dict.fromkeys(g)) for g in groups]


def dropped_markers(spec):
    """The walkthrough's '<not recorded>' reward entries (for the ledger)."""
    out = []
    def walk(v):
        if isinstance(v, str) and v.startswith('<'): out.append(v)
        elif isinstance(v, list): [walk(x) for x in v]
        elif isinstance(v, dict): [walk(x) for x in v.values()]
    walk({k: v for k, v in (spec.get('rewards') or {}).items() if k not in ('xp', 'coin', 'xp_note', 'faction', 'sell')})
    return out


def display_name(name):
    """'Skinner's Gloves (Cloth)' -> 'Skinner's Gloves' (the bracket is the listing's disambiguator)."""
    return re.sub(r'\s*\((?:alb|mid|hib|albion|midgard|hibernia|cloth|leather|reinf|reinforced|scale|studded|chain|plate|'
                  r'[A-Z][a-z]+(?:/[A-Z][a-z]+)*)\)\s*$', '', name, flags=re.I).strip() or name
