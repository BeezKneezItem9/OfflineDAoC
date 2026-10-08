"""Local receiver for goal 10 walkthrough collection (the quest site blocks scripts; a real browser tab fetches the pages).
GET /todo -> [[id, realm], ...] still to fetch (every spec's quest); POST -> JSON list of {id, realm, title, text} appended
to walkthroughs.jsonl (raw page text: dialogue, steps, rewards and player comments, kept for the record)."""
import json, os, re
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'walkthroughs.jsonl')

def todo():
    done = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding='utf-8'):
            try: done.add(int(json.loads(line)['id']))
            except Exception: pass
    out, seen = [], set()
    for f in ('albion', 'midgard', 'hibernia'):
        for line in open(os.path.join(HERE, 'specs', f + '.jsonl'), encoding='utf-8'):
            s = json.loads(line)
            qid = int(re.search(r'\d+', s['src']).group(0))
            if qid in done or qid in seen: continue
            seen.add(qid); out.append([qid, s['realm']])
    return out

class H(BaseHTTPRequestHandler):
    def cors(self):
        self.send_header('Access-Control-Allow-Origin', self.headers.get('Origin') or '*')
        self.send_header('Vary', 'Origin')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
    def do_OPTIONS(self):
        self.send_response(204); self.cors(); self.end_headers()
    def do_GET(self):
        if self.path.startswith('/sink'):
            # A same-origin page the collector tab embeds: it forwards posted batches to this receiver.
            body = (b"<!doctype html><script>window.addEventListener('message',e=>{fetch('/',{method:'POST',body:e.data})"
                    b".then(()=>e.source.postMessage('ok:'+JSON.parse(e.data).length,'*'))});</script>")
            self.send_response(200); self.send_header('Content-Type', 'text/html'); self.end_headers(); self.wfile.write(body)
            return
        body = json.dumps(todo()).encode()
        self.send_response(200); self.cors(); self.send_header('Content-Type', 'application/json'); self.end_headers()
        self.wfile.write(body)
    def do_POST(self):
        data = self.rfile.read(int(self.headers.get('Content-Length', 0))).decode('utf-8')
        # A plain-text form submission (top-level navigation from the collector tab) arrives as "d=<json>".
        if data.startswith('d='):
            data = data[2:].strip()
        # Records may name their archive: kind quest_page / item_page / item / quest_items go to their own files (raw period
        # data preserved in the project; owner 2026-10-07: keep everything in case the sites go away).
        files = {}
        recs = json.loads(data)
        # Full-site archive pass (owner 2026-10-07, "grab literally everything"): kind zam_<type> records go to
        # ../archive/allakhazam-live/<type>.jsonl.gz (gzip members appended per batch).
        zam = [r for r in recs if str(r.get('kind', '')).startswith('zam_')]
        if zam:
            import gzip
            out_dir = os.path.join(HERE, '..', 'archive', 'allakhazam-live')
            os.makedirs(out_dir, exist_ok=True)
            by = {}
            for r in zam: by.setdefault(r['kind'][4:], []).append(r)
            for kind, rows in by.items():
                with gzip.open(os.path.join(out_dir, kind + '.jsonl.gz'), 'at', encoding='utf-8') as f:
                    for r in rows: f.write(json.dumps(r, ensure_ascii=False) + chr(10))
            with open(os.path.join(out_dir, 'handoff.log'), 'a', encoding='utf-8') as f:
                f.write(json.dumps({'n': len(zam), 'first': zam[0].get('seq'), 'last': zam[-1].get('seq')}) + chr(10))
        for rec in recs:
            if str(rec.get('kind', '')).startswith('zam_'): continue
            name = {'quest_page': 'archive_quest_pages.jsonl', 'item_page': 'archive_item_pages.jsonl',
                    'item': 'reward_items.jsonl', 'quest_items': 'quest_item_links.jsonl'}.get(rec.get('kind'), os.path.basename(OUT))
            files.setdefault(name, []).append(rec)
        for name, rows in files.items():
            with open(os.path.join(HERE, name), 'a', encoding='utf-8') as f:
                for rec in rows: f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        self.send_response(200); self.cors(); self.send_header('Content-Type', 'text/plain'); self.end_headers()
        self.wfile.write(('saved ' + str(len(recs))).encode())
    def log_message(self, *a): pass

HTTPServer(('127.0.0.1', 8766), H).serve_forever()
