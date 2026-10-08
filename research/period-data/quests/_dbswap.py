import re
copy = "C:/OfflineDAoC/scratch/dbcopy.db"
for f in ['gen_dataquests.py','report_goal10.py','resolve_specs.py','match_specs.py','plan_spawns.py']:
    lines=open(f,encoding='utf-8').read().split('\n')
    for i,l in enumerate(lines):
        if re.match(r'^DB = ', l) and 'opendaoc.sqlite3.db' in l:
            uri = l.split('=',1)[1].strip().startswith('r"file:')
            lines[i] = ('DB = r"file:%s?mode=ro"' % copy if uri else 'DB = r"%s"' % copy) + '  # lock-free copy of the live DB (cp it first)'
    open(f,'w',encoding='utf-8').write('\n'.join(lines))
