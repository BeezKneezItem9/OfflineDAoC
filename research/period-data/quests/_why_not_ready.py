"""Report: why each not-ready quest is blocked (first blocking step)."""
import json, collections, os
src = open('gen_dataquests.py', encoding='utf-8').read()
src = src[:src.index('rows, items, skipped = [], {}, Counter()')]
g = {'__file__': os.path.abspath('gen_dataquests.py')}
exec(compile(src, 'gen', 'exec'), g)
r = g['resolved']
why = collections.Counter(); ex = collections.defaultdict(list)
for q in r:
    if g['ready'](q): continue
    if q.get('giver') is None:
        why['no giver'] += 1; ex['no giver'].append((q['spec']['name'], q['spec']['src'], (q.get('giver_spec') or {}).get('name'), (q.get('giver_spec') or {}).get('zone'))); continue
    for i, s in enumerate(q['steps']):
        k = s['do']
        if k in g['CUSTOM']:
            if g['custom_step'](q, s, i) is None:
                why['custom ' + k] += 1; ex['custom ' + k].append((q['spec']['name'], s['spec'].get('npc') or s['spec'].get('where'), s['spec'].get('zone'))); break
            continue
        if k not in g['SIMPLE']: why['kind ' + k] += 1; ex['kind ' + k].append(q['spec']['name']); break
        if s.get('target') is None and k in ('kill', 'collect') and g['event_spawn'](q, s): continue
        if s.get('target') is None and k in ('talk', 'kill', 'deliver', 'whisper', 'collect'):
            why['no target ' + k] += 1; ex['no target ' + k].append((q['spec']['name'], s['spec'].get('npc'), s['spec'].get('zone'), bool(s.get('needs_spawn')))); break
print(why)
for k, v in ex.items():
    print('==', k, len(v))
    for x in v: print('   ', x)
