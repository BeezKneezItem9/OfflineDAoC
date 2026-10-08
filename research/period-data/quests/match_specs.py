"""Match quest specs against the server: every named NPC/monster a spec uses (giver, step npc, kill targets),
found or missing, by realm/zone. Read-only. Writes spec_match.json and prints a summary.
python match_specs.py"""
import json, os, re, sqlite3, collections, glob

HERE = os.path.dirname(os.path.abspath(__file__))
DB = r"C:/OfflineDAoC/scratch/dbcopy.db"  # lock-free copy of the live DB (cp it first)
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
zones = list(c.execute("select ZoneID,RegionID,Name,OffsetX,OffsetY,Width,Height from Zones"))
def zkey(n): return re.sub(r"[^a-z]", "", (n or "").lower().replace("mountains", "mts").replace("mtns", "mts"))
zone_by_name = collections.defaultdict(list)
for z in zones: zone_by_name[zkey(z[2])].append(z)
ALIASES = {"camelot": "camelotcity", "jordheim": "jordheim", "tirnanog": "tirnanog", "castlesauvage": "camelothills",
           "catacombsofcornwall": "catacombsofcornwall", "aegirslanding": "aegirslanding"}

mobs = collections.defaultdict(list)
for name, region, x, y in c.execute("select Name,Region,X,Y from Mob"):
    mobs[name.lower().strip()].append((region, x, y))

def zone_of(region, x, y):
    for z in zones:
        if z[1] == region and z[3] * 8192 <= x < (z[3] + z[5]) * 8192 and z[4] * 8192 <= y < (z[4] + z[6]) * 8192: return z[2]
    return None

def names_in(spec):
    out = []
    g = spec.get("giver", {}).get("name")
    if g: out.append((g, spec["giver"].get("zone"), "giver"))
    for st in spec.get("steps", []):
        for key in ("npc", "also_npc", "also_kill"):
            v = st.get(key)
            if isinstance(v, str): out.append((v, st.get("zone"), st.get("do")))
        if st.get("do") == "collect" and st.get("from"): out.append((st["from"], st.get("zone"), "collect-from"))
    return out

results = []
for path in sorted(glob.glob(os.path.join(HERE, "specs", "*.jsonl"))):
    if os.path.basename(path).startswith(("_", "b_")): continue
    for line in open(path, encoding="utf-8"):
        spec = json.loads(line)
        for name, zone, role in names_in(spec):
            if name.startswith("<") or name.lower() in ("trainer", "class trainer") or "|" in name: continue
            hits = mobs.get(name.lower().strip(), [])
            hit_zones = sorted({zone_of(*h) or f"region {h[0]}" for h in hits})
            same_zone = any(zkey(z) == zkey(zone) for z in hit_zones) if zone else bool(hits)
            results.append(dict(quest=spec["name"], realm=spec["realm"], src=spec["src"], name=name, zone=zone, role=role,
                                found=bool(hits), same_zone=same_zone, server_zones=hit_zones[:4], count=len(hits)))
import difflib
allnames = list(mobs.keys())
for r in results:
    if not r["found"]:
        close = difflib.get_close_matches(r["name"].lower(), allnames, n=2, cutoff=0.86)
        r["close"] = [(n, sorted({zone_of(*h) or f"region {h[0]}" for h in mobs[n]})[:2]) for n in close]
json.dump(results, open(os.path.join(HERE, "spec_match.json"), "w"), indent=1)
by = collections.Counter((r["realm"], "ok" if r["same_zone"] else "elsewhere" if r["found"] else "missing") for r in results)
print(by)
for r in results:
    if not r["found"]: print("MISSING", r["realm"], "|", r["name"], "|", r["zone"], "|", r["role"], "| close:", r.get("close"))
