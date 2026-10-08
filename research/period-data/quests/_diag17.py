"""Diagnose the quests blocking the 17 failing ones (owner 2026-10-07)."""
import json, os, sys
src = open('gen_dataquests.py', encoding='utf-8').read()
src = src[:src.index('rows, items, skipped = [], {}, Counter()')]
g = {'__file__': os.path.abspath('gen_dataquests.py')}
exec(compile(src, 'gen', 'exec'), g)
want = set(sys.argv[1:])
for q in g['resolved']:
    if q['spec']['name'] not in want: continue
    print('=====', q['spec']['src'], q['spec']['name'], 'ready=', g['ready'](q), 'giver=', (q.get('giver') or {}).get('name') if isinstance(q.get('giver'), dict) else q.get('giver'))
    for i, s in enumerate(q['steps']):
        sp = s['spec']
        t = s.get('target')
        ev = None
        try: ev = bool(g['event_spawn'](q, s)) if s['do'] in ('kill', 'collect') else None
        except Exception as e: ev = 'ERR ' + str(e)
        cs = None
        if s['do'] in g['CUSTOM']:
            try: cs = g['custom_step'](q, s, i)
            except Exception as e: cs = 'ERR ' + str(e)
        print(f"  {i+1} {s['do']:8} npc={sp.get('npc')!r} zone={sp.get('zone')!r} target={(t or {}).get('name') if isinstance(t, dict) else t!r} needs_spawn={s.get('needs_spawn')} event={ev} custom={cs!r:.80}")
        print('      ', json.dumps(sp)[:300])
