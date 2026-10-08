"""Coruscating Mine (region 220) bonus job, owner 2026-10-07: "seems like it has too many mob spawns, check
period accurate data for the sparse monsters in there against the server and thin it out in spots that are
accurate".

Evidence: Illia's bestiary (species and levels) and Uthgard's kill counts (relative abundance; 7,142 kills
over 47 species). CapnBry has no dungeon data. A species is thinned only when Uthgard shows it as rare
(its kill share points to far fewer spawns than the server has). Targets below keep at least one spawn of
every species and never touch named monsters. Removed spawns come out of the densest clusters first, so
every area keeps its monsters and only stacked spots lose them.

The misspelled "gemklicker horder" rows (no source has that name) are renamed to "gemclicker horder",
which Uthgard records 100 kills of and Illia lists at 36-44.

python thin_coruscating.py            dry run -> coruscating_plan.json
python thin_coruscating.py --apply    back up the DB, then delete/rename (server stopped)
"""
import json, math, os, sqlite3, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DB = r"C:/OfflineDAoC\runtime\data\opendaoc.sqlite3.db"
REGION = 220
# species: (server now, Uthgard kills, keep). Keep ~= the Uthgard kill share of the server's total, rounded up,
# never below 1.
KEEP = {
    'unseelie viewer': 2,      # 9 spawns, 9 kills
    'casolith': 2,             # 8 spawns, 2 kills
    'haunting draft': 2,       # 6 spawns, 8 kills
    'vein golem': 4,           # 10 spawns, 71 kills
    'weewere': 10,             # 20 spawns, 185 kills
    'lode protector': 8,       # 14 spawns, 148 kills
    'guardian of the silver hand': 3,  # 7 spawns, 41 kills
    'lode runner': 2,          # 6 spawns, 32 kills
    'unseelie overman': 2,     # 5 spawns, 15 kills
    'silver-flecked skeleton': 1,      # 3 spawns, 14 kills
}
RENAME = {'gemklicker horder': 'gemclicker horder'}

c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
rows = list(c.execute("select Mob_ID, lower(Name), X, Y, Z from Mob where Region=? and Realm=0", (REGION,)))
everything = [(r[2], r[3], r[4]) for r in rows]

def crowd(x, y, z):
    return sum(1 for (a, b, h) in everything if abs(h - z) < 400 and math.hypot(a - x, b - y) < 700)

plan, notes = [], []
# Step 1 - the cause: the imported (Public_DB, placeholder 2000-01-01 dates) rows record many monsters twice a few
# steps apart, so camps come doubled. 83 same-species pairs stand within 150 units of each other here (Spraggon Den 46,
# Treibh Caillte 43, Koalinth Caverns 7). Merge every such stack into its first spawn.
STACK = 150
removed = set()
for i, a in enumerate(rows):
    if a[0] in removed: continue
    for b in rows[i + 1:]:
        if b[0] in removed or a[1] != b[1] or abs(a[4] - b[4]) >= 100: continue
        if math.hypot(a[2] - b[2], a[3] - b[3]) < STACK:
            removed.add(b[0]); plan.append(dict(op='delete', mob_id=b[0], name=b[1], x=b[2], y=b[3], z=b[4], why='stacked duplicate'))
notes.append(f"stacked duplicates merged: {len(removed)}")
rows = [r for r in rows if r[0] not in removed]
everything = [(r[2], r[3], r[4]) for r in rows]
# Step 2 - species the period sources show as rare, capped at their Uthgard kill share.
for name, keep in KEEP.items():
    mine = [r for r in rows if r[1] == name]
    if len(mine) <= keep:
        notes.append(f"{name}: {len(mine)} spawns, nothing to thin"); continue
    # Remove from the densest spots, one at a time, so the survivors stay spread out.
    left = list(mine)
    while len(left) > keep:
        worst = max(left, key=lambda r: (crowd(r[2], r[3], r[4]) +
                                         sum(1 for o in left if o is not r and math.hypot(o[2] - r[2], o[3] - r[3]) < 900) * 3))
        left.remove(worst); plan.append(dict(op='delete', mob_id=worst[0], name=name, x=worst[2], y=worst[3], z=worst[4], why='rare in period data'))
    notes.append(f"{name}: {len(mine)} -> {keep}")
for old, new in RENAME.items():
    for r in rows:
        if r[1] == old: plan.append(dict(op='rename', mob_id=r[0], name=old, to=new, x=r[2], y=r[3], z=r[4]))
    notes.append(f"{old}: {sum(1 for r in rows if r[1] == old)} rows renamed to {new}")

json.dump(dict(region=REGION, total_before=len(rows) + len(removed), plan=plan, notes=notes),
          open(os.path.join(HERE, 'coruscating_plan.json'), 'w'), indent=1)
deletes = sum(1 for p in plan if p['op'] == 'delete')
print('spawns', len(rows) + len(removed), 'delete', deletes, 'rename', len(plan) - deletes); [print(' ', n) for n in notes]

if '--apply' in sys.argv:
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    w = sqlite3.connect(DB)
    bk = sqlite3.connect(os.path.join(os.path.dirname(DB), f'opendaoc.sqlite3.before-coruscating-thin-{stamp}.db')); w.backup(bk); bk.close()
    before = w.execute("select count(*) from Mob where Region=?", (REGION,)).fetchone()[0]
    for p in plan:
        if p['op'] == 'delete': w.execute("delete from Mob where Mob_ID=? and Region=?", (p['mob_id'], REGION))
        else: w.execute("update Mob set Name=? where Mob_ID=? and Region=?", (p['to'], p['mob_id'], REGION))
    after = w.execute("select count(*) from Mob where Region=?", (REGION,)).fetchone()[0]
    assert before - after == deletes, (before, after, deletes)
    w.commit(); print('applied; backup', stamp, 'spawns', before, '->', after)
