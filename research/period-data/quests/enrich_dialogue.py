"""Goal 10: turn the collected walkthrough pages (walkthroughs.jsonl) into quest dialogue (dialogue.json, read by the
generator). Only recorded dialogue ("X says, ...") is used (owner rule; placeholders only where a checked page has none).
  offer        the giver's first line (shown on right-click), with its [keyword]
  chat         NPC -> keyword -> that NPC's next line (the classic [keyword] conversations, offer and mid-quest)
  accept       accept keyword: the last [keyword] of the giver's final offer line; a line without one (it popped a dialog
               in 1.65) gets one of its own words bracketed (owner rule)
  accept_line  the giver's first line after accepting (SourceText of step 1)
  giver_turnins the giver's later lines, in order, for the steps that return to the giver (TargetText)
  finish       the giver's last line before the final reward (FinishText)
  npc_lines    other NPCs' lines by name (TargetText of their talk/turn-in step)
  checked      True: the page was read
Walkthrough placeholders "(player name)", "(race)", "(class)" and the submitter's character name become <Player>/<Race>/<Class>.
  python enrich_dialogue.py"""
import json, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
SAYS = re.compile(r'^(?P<npc>[A-Z][^"]{0,60}?) (?:says|asks|exclaims|shouts|whispers|yells|replies|cries|states)[^"]{0,20}?,? ?"(?P<text>.*)$')
GIVEN = re.compile(r'^You have (?:been given|accepted) the (.+?) quest', re.I)
REWARD = re.compile(r'^You (?:receive|are awarded|have been awarded|get|gain) ', re.I)
STOP = set('that this with from have your they them their there what when will would could should about into some just been were very much more only than then also over such need here help come back know make take tell look good well like want please'.split())
PLACEHOLDERS = [(re.compile(r'[\(\[<]\s*(?:player|your|char(?:acter)?)?\s*name\s*[.!?,]?\s*[\)\]>]', re.I), '<Player>'),
                (re.compile(r'[\(\[<]\s*(?:player|your)?\s*race\s*[\)\]>]', re.I), '<Race>'),
                (re.compile(r'[\(\[<]\s*(?:player|your)?\s*class\s*[\)\]>]', re.I), '<Class>')]

specs = {}
for f in ('albion', 'midgard', 'hibernia'):
    for line in open(os.path.join(HERE, 'specs', f + '.jsonl'), encoding='utf-8'):
        s = json.loads(line)
        specs.setdefault(int(re.search(r'\d+', s['src']).group(0)), []).append(s)
pages = {}
for line in open(os.path.join(HERE, 'walkthroughs.jsonl'), encoding='utf-8'):
    r = json.loads(line)
    if int(r.get('id', -1)) > 0: pages[int(r['id'])] = r

def utterances(lines):
    """Join quotes wrapped over several lines; yield (npc, text, kind)."""
    out, cur = [], None
    for l in lines:
        m, g, rw = SAYS.match(l), GIVEN.match(l), REWARD.match(l)
        if m or g or rw:
            if cur: out.append(cur); cur = None
            if m:
                cur = [m.group('npc').strip(), m.group('text').strip(), 'say']
                if cur[1].endswith('"'): cur[1] = cur[1][:-1]; out.append(cur); cur = None
            else:
                out.append(['', l, 'given' if g else 'reward'])
        elif cur:
            cur[1] += ' ' + l.strip()
            if l.rstrip().endswith('"'): cur[1] = cur[1].rstrip()[:-1]; out.append(cur); cur = None
    if cur: out.append(cur)
    return [(n, re.sub(r'\s+', ' ', t).strip(), k) for n, t, k in out]

def personalize(text, player_names):
    for rx, tok in PLACEHOLDERS: text = rx.sub(tok, text)
    for name in player_names: text = re.sub(r'\b' + re.escape(name) + r'\b', '<Player>', text)
    return text

def submitter_names(utts, npcs):
    """Character names the NPCs address ("Thank you, Nesie!"): not an NPC of the page, used after a greeting/comma."""
    c = collections.Counter()
    for n, t, k in utts:
        if k != 'say': continue
        for m in re.finditer(r'(?:,|\b(?:thank you|thanks|greetings|hello|welcome|hail|well done|good|ah|oh|yes|farewell)) ([A-Z][a-z]{2,14})\b(?=[!?.,]|$)', t):
            w = m.group(1)
            if w.lower() not in npcs and w not in ('Albion', 'Midgard', 'Hibernia', 'Camelot', 'Jordheim', 'Tir', 'Arawn', 'Friend', 'Sir', 'Lady', 'Lord', 'Master', 'Mistress', 'Brother', 'Sister', 'Father', 'Mother', 'God', 'Gods'):
                c[w] += 1
    return {w for w, n in c.items() if n >= 1}

def bracket_word(line):
    words = [(m.start(), m.group(0)) for m in re.finditer(r"[A-Za-z][A-Za-z'-]{3,}", line) if m.group(0).lower() not in STOP and not m.group(0).startswith('Player')]
    if not words: words = [(m.start(), m.group(0)) for m in re.finditer(r"[A-Za-z][A-Za-z'-]{2,}", line)]
    if not words: return line, None
    pos, word = max(words, key=lambda w: (len(w[1]), w[0]))
    return line[:pos] + '[' + word + ']' + line[pos + len(word):], word

KW = re.compile(r'\[([^\]]+)\]')
out, stats = {}, collections.Counter()
for qid, page in pages.items():
    utts = utterances(page.get('body') or [])
    npcs = {n.lower() for n, t, k in utts if k == 'say'} | {w.lower() for n, t, k in utts if k == 'say' for w in n.split()}
    players = submitter_names(utts, npcs)
    utts = [(n, personalize(t, players), k) for n, t, k in utts]
    for spec in specs.get(qid, []):
        giver = ((spec.get('giver') or {}).get('name') or '').lower()
        trainer = giver in ('trainer', 'class trainer')
        if trainer:  # the trainer is whoever speaks first
            first = next((n for n, t, k in utts if k == 'say'), '')
            giver = first.lower()
        d = {'checked': True}
        gidx = [i for i, u in enumerate(utts) if u[2] == 'say' and u[0].lower() == giver]
        given_at = next((i for i, u in enumerate(utts) if u[2] == 'given'), None)
        if given_at is None and gidx:
            # no "You have been given" line: the offer ends at the giver's first line without a [keyword]
            end = next((i for i in gidx if not KW.search(utts[i][1])), None)
            given_at = (end + 0.5) if end is not None else None
        offer_idx = [i for i in gidx if given_at is None or i < given_at]
        chat = collections.defaultdict(dict)
        if offer_idx:
            chain = [utts[i][1] for i in offer_idx]
            d['offer'] = chain[0]
            for a, b in zip(chain, chain[1:]):
                kws = KW.findall(a)
                if kws: chat[spec['giver']['name']][kws[-1]] = b
            last = chain[-1]
            kws = KW.findall(last)
            if len(chain) == 1 and kws:
                d['accept'] = kws[-1]
            elif kws and len(chain) > 1:
                d['accept'] = kws[-1]
            else:
                final, word = bracket_word(last)
                d['accept'] = word
                if len(chain) == 1: d['offer'] = final
                else:
                    prev_kws = KW.findall(chain[-2])
                    if prev_kws: chat[spec['giver']['name']][prev_kws[-1]] = final
        later = [i for i in gidx if given_at is not None and i > given_at]
        rewards = [i for i, u in enumerate(utts) if u[2] == 'reward']
        if later:
            d['accept_line'] = utts[later[0]][1]
            final_reward = rewards[-1] if rewards else None
            fin = [i for i in later[1:] if final_reward is None or i < final_reward]
            if fin: d['finish'] = utts[fin[-1]][1]
            replies = {b for x, b in zip([utts[i][1] for i in gidx], [utts[i][1] for i in gidx][1:]) if KW.search(x)}
            d['giver_turnins'] = [utts[i][1] for i in fin[:-1] if utts[i][1] not in replies] if fin else []
        # mid-quest keyword chains, for every NPC
        by_npc = collections.defaultdict(list)
        for i, u in enumerate(utts):
            if u[2] == 'say' and (given_at is None or i > given_at): by_npc[u[0]].append(u[1])
        for npc, said in by_npc.items():
            name = spec['giver']['name'] if npc.lower() == giver else npc
            for a, b in zip(said, said[1:]):
                kws = KW.findall(a)
                if kws: chat[name].setdefault(kws[-1], b)
        if chat: d['chat'] = {k: v for k, v in chat.items() if v}
        others = {npc: ' '.join(said) for npc, said in by_npc.items() if npc.lower() != giver}
        if others: d['npc_lines'] = others
        if trainer: d['trainer_voice'] = giver
        out[spec['src']] = d
        stats['checked'] += 1
        for k in ('offer', 'accept', 'accept_line', 'finish', 'chat', 'npc_lines', 'giver_turnins'):
            if d.get(k): stats[k] += 1
json.dump(out, open(os.path.join(HERE, 'dialogue.json'), 'w', encoding='utf-8'), indent=1)
print(dict(stats))
