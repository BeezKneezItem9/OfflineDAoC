"""Goal 10: classify every friendly (non-monster) NPC on the server against period evidence.

Evidence: CapnBry radar lists (2002-2004): capitalized names seen in the zone (or the same realm).
Origin flags: class types known to come from Atlas/later versions, our own additions, teleporters.
"""
import json, sqlite3, re, collections, os, csv

ROOT = r"C:/OfflineDAoC"
DB = os.path.join(ROOT, r"runtime\data\opendaoc.sqlite3.db")
HERE = os.path.dirname(os.path.abspath(__file__))
PEACE = 0x10

ATLAS_OR_LATER = {
    'DOL.GS.Scripts.OFAssistant': 'Atlas frontier medallion assistant',
    'DOL.GS.Scripts.OFTeleporter': 'Atlas frontier medallion teleporter',
    'DOL.GS.Scripts.AtlasTrainer': 'Atlas trainer',
    'DOL.GS.MarketExplorer': 'Market Explorer (housing consignment search, post-1.65 / Atlas)',
    'DOL.GS.Recharger': 'Atlas charge recharger',
    'DOL.GS.DPSDummy': 'Atlas training dummy',
    'DOL.GS.HitbackDummy': 'Atlas training dummy',
    'DOL.GS.EffectNPC': 'Atlas cosmetic effect vendor',
    'DOL.GS.GameEmeraldSealsMerchant': 'Seals merchant (Darkness Rising era, used by Atlas)',
    'DOL.GS.GameDiamondSealsMerchant': 'Seals merchant (Darkness Rising era, used by Atlas)',
    'DOL.GS.GameSapphireSealsMerchant': 'Seals merchant (Darkness Rising era, used by Atlas)',
    'DOL.GS.AccountVaultKeeper': 'Account vault keeper (post-1.65 live feature)',
    'DOL.GS.Scripts.OFMerchantHome': 'Atlas frontier medallion merchant',
    'DOL.GS.HealDummy': 'Atlas training dummy',
}
# Period by patch notes, not flagged: GameBountyMerchant (bounty points and stores, patch 1.42).
TELEPORTERS = {'DOL.GS.Scripts.LiveTeleporter', 'DOL.GS.Scripts.InlandTeleporter', 'DOL.GS.Scripts.BGTeleporter',
               'DOL.GS.Scripts.OFTeleporter', 'DOL.GS.Scripts.EpicTeleporter'}
OURS = re.compile(r"bounty|emissary|realm exchange|brynhild|adalyn|sluagh", re.I)

def norm(n): return re.sub(r"\s+", " ", n.strip().lower())

c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
zones = c.execute("select ZoneID,RegionID,Name,OffsetX,OffsetY,Width,Height from Zones").fetchall()
zbr = collections.defaultdict(list)
for z in zones: zbr[z[1]].append(z)
def zone_of(region, x, y):
    for z in zbr.get(region, []):
        if z[3] * 8192 <= x < (z[3] + z[5]) * 8192 and z[4] * 8192 <= y < (z[4] + z[6]) * 8192:
            return z
    return None

capn = json.load(open(os.path.join(HERE, 'capnbry_zones.json'), encoding='utf-8'))
cap_zone = {int(k): {norm(m['name']) for m in v['mobs']} for k, v in capn.items()}
cap_all = set().union(*cap_zone.values())
# Illia's Camelot Bestiary (Allakhazam) NPC entries per zone name: a second period source for NPC names.
illia = json.load(open(os.path.join(HERE, 'illia_zones.json'), encoding='utf-8'))
def zkey(n): return re.sub(r"[^a-z]", "", n.lower().replace("mountains", "mts").replace("mtns", "mts"))
illia_zone = collections.defaultdict(set)
for v in illia.values():
    for row in v.get('rows', []):
        if len(row) >= 3: illia_zone[zkey(v['name'])].add(norm(row[0]))
illia_all = set().union(*illia_zone.values()) if illia_zone else set()
covered = {int(k) for k, v in capn.items() if v['mobs']}

rows = []
for name, guild, region, x, y, realm, flags, ctype, level in c.execute(
        "select Name, Guild, Region, X, Y, Realm, Flags, ClassType, Level from Mob"):
    if not name: continue
    friendly = (realm or 0) != 0 or (flags or 0) & PEACE
    if not friendly: continue
    if 'Keeps.Guard' in (ctype or '') or ctype in ('DOL.GS.GameGuard',):
        kind = 'guard'
    else:
        kind = 'npc'
    z = zone_of(region, x, y)
    zid = z[0] if z else None
    n = norm(name)
    if OURS.search(name) or OURS.search(guild or ''):
        origin = 'added by this project (excluded)'
    elif ctype in TELEPORTERS:
        origin = 'teleporter (not 1.65; listed separately)'
    elif ctype in ATLAS_OR_LATER:
        origin = 'Atlas / later: ' + ATLAS_OR_LATER[ctype]
    elif zid in cap_zone and n in cap_zone[zid]:
        origin = '1.65-era: seen in this zone by CapnBry'
    elif z and n in illia_zone.get(zkey(z[2]), ()):
        origin = "likely period: listed in this zone by Illia's bestiary (2001-2010 data, may include later NPCs)"
    elif n in cap_all:
        origin = '1.65-era: seen by CapnBry (another zone)'
    elif n in illia_all:
        origin = "likely period: listed by Illia's bestiary in another zone"
    elif zid in covered:
        origin = 'unverified: not in CapnBry for this zone'
    else:
        origin = 'unverified: no CapnBry data for this zone'
    rows.append(dict(name=name, guild=guild or '', classtype=(ctype or '').replace('DOL.GS.', ''), kind=kind,
                     realm=realm, level=level, region=region, zone=z[2] if z else '', zone_id=zid, origin=origin))

with open(os.path.join(HERE, 'npc_audit.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print('friendly NPC rows', len(rows))
print(collections.Counter((r['kind'], r['origin'].split(':')[0]) for r in rows).most_common())
unver = collections.Counter((r['classtype']) for r in rows if r['origin'].startswith('unverified: not in') and r['kind'] == 'npc')
print('unverified (covered zones) by class:', unver.most_common(15))
