"""Tiny local receiver: the browser page POSTs JSON lines here; GET /todo returns the quest list still to fetch."""
import csv, json, os
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'details_browser.jsonl')

def todo():
    done = set()
    for name in ('details.jsonl', 'details_browser.jsonl'):
        p = os.path.join(HERE, name)
        if os.path.exists(p):
            for line in open(p, encoding='utf-8'):
                try: done.add(int(json.loads(line)['id']))
                except Exception: pass
    rows = list(csv.DictReader(open(os.path.join(HERE, 'allakhazam_quests.csv'), encoding='utf-8')))
    return [[int(r['id']), r['realm']] for r in rows
            if r['exp'] in ('Classic', 'Shrouded Isle expansion') and r['type'] not in ('Master Level', 'Artifact', 'Champion')
            and int(r['id']) not in done]

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
        body = json.dumps(todo()).encode()
        self.send_response(200); self.cors(); self.send_header('Content-Type', 'application/json'); self.end_headers()
        self.wfile.write(body)
    def do_POST(self):
        data = self.rfile.read(int(self.headers.get('Content-Length', 0))).decode('utf-8')
        with open(OUT, 'a', encoding='utf-8') as f:
            for rec in json.loads(data):
                f.write(json.dumps(rec) + '\n')
        self.send_response(200); self.cors(); self.end_headers(); self.wfile.write(b'ok')
    def log_message(self, *a): pass

HTTPServer(('127.0.0.1', 8765), H).serve_forever()
