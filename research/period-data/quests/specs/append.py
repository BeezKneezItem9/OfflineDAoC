import json,sys
realm=sys.argv[1]
rows=[json.loads(l) for l in open(sys.argv[2] if len(sys.argv)>2 else '_batch.jsonl',encoding='utf-8') if l.strip()]
have={json.loads(l)['src'] for l in open(f'{realm}.jsonl',encoding='utf-8')} if __import__('os').path.exists(f'{realm}.jsonl') else set()
new=[r for r in rows if r['src'] not in have]
with open(f'{realm}.jsonl','a',encoding='utf-8') as f:
    for r in new: f.write(json.dumps(r,ensure_ascii=False)+'\n')
print(realm,'added',len(new),'total',len(have)+len(new))
