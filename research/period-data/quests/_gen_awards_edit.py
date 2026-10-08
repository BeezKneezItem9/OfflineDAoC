"""One-off edit: per-step coin/XP from the walkthrough's "You are awarded ..." lines (gen_dataquests.py)."""
p = 'gen_dataquests.py'
s = open(p, encoding='utf-8').read()


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:70]
    s = s.replace(old, new)


rep("""DIALOGUE = json.load(open(""", r'''# Walkthrough bodies (Allakhazam quest pages, kept in walkthroughs.jsonl): the recorded "You are awarded ..." lines.
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
            cur = [speaker, cp, xp]; events.append(cur)
    out, start = {}, 0
    names = [st[1].split(';')[0].lower() for st in steps]
    for who, cp, xp in events:
        hits = [k for k in range(start, len(steps)) if names[k] and (names[k] == who.lower() or who.lower() in names[k] or names[k] in who.lower())]
        if not hits: continue
        k = hits[0]
        start = k + 1
        if k == len(steps) - 1: continue
        if xp == -1: xp = quest_xp('auto', level) // 4  # "You are awarded experience!" with no number: a small share
        out[k] = (cp, xp)
    return out

DIALOGUE = json.load(open(''')

rep("""        'RewardMoney': '|'.join(['0'] * (len(steps) - 1) + [str(coin(rewards.get('coin')))]),
        'RewardXP': '|'.join(['0'] * (len(steps) - 1) + [str(quest_xp(rewards.get('xp'), spec.get('level')))]),""",
    """        'RewardMoney': '|'.join([str(awards.get(k, (0, 0))[0]) for k in range(len(steps) - 1)] + [str(coin(rewards.get('coin')))]),
        'RewardXP': '|'.join([str(awards.get(k, (0, 0))[1]) for k in range(len(steps) - 1)] + [str(quest_xp(rewards.get('xp'), spec.get('level')))]),""")

rep("""    rewards = spec.get('rewards') or {}
    row = {""", """    rewards = spec.get('rewards') or {}
    awards = step_awards(spec, steps, spec.get('level'))
    row = {""")
open(p, 'w', encoding='utf-8').write(s)
print('ok')
