"""Calibration for goal9_plan: radar spawn-point estimate vs server count, per zone/species, for several roam radii."""
import json, math, statistics, sys, re
src = open('goal9_plan.py', encoding='utf-8').read()
src = src[:src.index('plan, notes, stats')]
g = {'__file__': 'goal9_plan.py'}; sys.argv = ['x']; exec(compile(src, 'g9', 'exec'), g)
capn, sight, ZONES, server, norm, NOISE = g['capn'], g['sight'], g['ZONES'], g['server'], g['norm'], g['NOISE']
def cover(pts, roam):
    left = list(pts); n = 0
    while left:
        b = max(left, key=lambda p: sum(1 for q in left if math.hypot(p[0]-q[0], p[1]-q[1]) <= roam))
        left = [q for q in left if math.hypot(b[0]-q[0], b[1]-q[1]) > roam]; n += 1
    return n
pairs = []
for zid_s, zinfo in capn.items():
    zid = int(zid_s)
    if zid not in ZONES or 73 <= zid <= 91 or 163 <= zid <= 178: continue
    names = {}
    for m in zinfo['mobs']:
        if not m['name'][:1].islower() or NOISE.search(m['name']): continue
        names.setdefault(norm(m['name']), []).extend(s for s in sight.get(str(m['id']), {}).get('seen', []) if s[0] == zid)
    for n, seen in names.items():
        have = len(server.get((zid, n), []))
        spots = {(round(s[1]/150)*150, round(s[2]/150)*150) for s in seen}
        if have >= 8 and len(spots) >= 8: pairs.append((have, spots))
print('pairs', len(pairs))
import random; random.seed(1); sample = random.sample(pairs, min(150, len(pairs)))
for roam in (350, 600, 900, 1300, 1800):
    ratios = sorted(cover(sp, roam) / h for h, sp in sample)
    print(roam, 'median est/server', round(statistics.median(ratios), 2), 'p25', round(ratios[len(ratios)//4], 2), 'p75', round(ratios[3*len(ratios)//4], 2))
