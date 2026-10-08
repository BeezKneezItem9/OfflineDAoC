import json,glob,os,collections,sys
done=set()
for p in glob.glob('specs/*.jsonl'):
    if os.path.basename(p).startswith(('b_','_')): continue
    for l in open(p,encoding='utf-8'):
        if l.strip(): done.add(json.loads(l)['src'])
t=json.load(open('period_todo.json',encoding='utf-8'))
left=[e for e in t if e['key'] not in done]
print(len(left), sorted(collections.Counter((e['realm'],e['type']) for e in left).items()))
realm=sys.argv[1] if len(sys.argv)>1 else None
if realm:
    l=[e for e in left if e['realm']==realm]
    print(' '.join(e['key']+':'+e['level']+':'+e['type'][:4]+':'+e['name'][:22] for e in l[:int(sys.argv[2]) if len(sys.argv)>2 else 40]))
