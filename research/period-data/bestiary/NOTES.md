# Goals 10 (NPC/quest audit) and 11 (bestiary audit) — research notes (2026-10-07)

## Sources and access
- Allakhazam (camelot.allakhazam.com): quest lists per realm downloaded -> ../quests/allakhazam_quests.csv
  (3187 rows; 1838 Classic+SI). Quest detail pages: ../quests/details.jsonl (147 done before Allakhazam
  started returning 403 at ~00:45; fetcher ../quests/fetch_quests.py resumes, use >=4 s delay).
  "Illia's Camelot Bestiary" WAS Allakhazam's DAoC bestiary (title on archived page). Live bestiary
  /db/mobsbyzone.html currently 403 for us. Mirror snapshot: chadwickgjohnson.com/data/20091205062016/
  index.html (needs browser UA + Accept headers; only that page seen so far). Wayback CDX was
  "Temporarily Offline" at 00:53 — retry for 2003-2005 copies of camelot.allakhazam.com mob pages.
- CapnBry (capnbry.net/daoc): live. mobs.php?a=zones&r=1..5 (zone index), mobs.php?z=N (name, min, avg,
  max level; capitalized names = NPCs, lowercase = monsters). fetch_capnbry.py -> capnbry_zones.json.
  Several zones have 0 rows (Dartmoor, Llyn Barfog, Old Sarum, SI Caldey/Dales/Gwyddneau/Aldland...).
  The repo's capnbry_classic_si_goals.json is PRE-FILTERED to species matched on the server (can't show
  missing species) — use the raw download.
- Uthgard 2.0 (disorder.dk/daoc/bestiary): zone.php?load=N (own ids, map by zone name), name, level
  from/to, aggro, kills. fetch_uthgard.py -> uthgard_zones.json. Shifted brackets/species: fallback only.

## Findings so far
- Quests in server: 12 level-50 old-epic finales only (Academy50, Church50, Defenders50, Shadows50,
  Essence50, Focus50, Harmony50, MidgardRogue50, Mystic50, Seer50, Viking50; prerequisites commented out).
  Old epic chains on Allakhazam (pre-1.79): Alb Feast of the Decadent 43/45/48/50, Lord of Deceit
  43-50, Passage to Eternity 43-50, Symbol of the Broken 43-50, Legend of the Lake 15/20/25, Regal
  Nobility 25/30; Mid A War of Old 15-30, An End to the Daggers 43-50, Saving the Clan 43-50, Desire of a
  God 43-50, Red Dagger 15-25, War Concluded 45/50; Hib Cad Goddeau A-D 15-30, Last Heir 43-50,
  Moonstone Twin 43-50, Unnatural Powers 43/50, Stolen Ore A/B 15/20, Secret of Nuada's Silver A/B 25/30.
  Allakhazam Epic_List.html = the 1.79 "Epic 1-9" chains (post-period; not 1.65).
- DataQuest table (238 "XP Item" quests) = live "Kill Task" turn-ins (Allakhazam type Kill Task, low
  cquest ids, Classic/SI) re-implemented as DataQuests by Atlas; ~189 of 275 match by exact-ish name,
  rest mostly spelling variants; DB-only low-level ones (levels 5-19, ids 400-408) likely Atlas additions.
  Uthgard 2.0 also lists the same XP items.
- Other quest scripts: SI quests LostStoneOfArawn, TheLostSeed, AncestralSecrets, WildWilderness;
  Alb ImmediateResolutionVB, WolfPeltCloak; tasks (Kill/Money/Craft) and missions frameworks;
  Atlas repeatables: AtlasQuests/DailyQuests (daily/weekly/monthly, PvE/RvR/Frontier/Hardcore per realm),
  HelpSirLukas, PlayTheLastSong, PowerOfNature; BattlegroundQuests (Thid/Cale keep capture + kill);
  ours: Bounty*, Reputation* (exclude), Sluaghbinder* (our class).
- Atlas-ish NPC class types in Mob: OFAssistant 54, LiveTeleporter 50, OFTeleporter 9, AtlasTrainer 17,
  MarketExplorer 36, Recharger 20, DPSDummy 20, HitbackDummy 11, EffectNPC 11, Emerald/Diamond/Sapphire
  Seals merchants 9 each, AccountVaultKeeper 13, GameBountyMerchant 13 (check era), BGTeleporter script.
- Howth = Silvermine Mts (zone 201); Connla = Shannon Estuary (zone 202).
- Run-15 side finding: KeepManager.ExitBattleground used "Svasudheim Faste" (no row) — fixed in source.

## Battleground keeps (2026-10-07)
- Client fixtures: centre (33280,38272) = Thidranki Norse keep (nfrontkeep1), Caledonia Albion keep
  (bfrontkeep1), Murdaigean/Abermenai Hibernian keep (Hfrontkeep, rot 4096). Portal keeps: Alb bfrontkeep1
  (37504,52736), Mid nfrontkeep1 (53888,24576), Hib Hfrontkeep (18048,18176, rot 3000) in every BG.
- All 4 BGs share terrain.pcx/offset.pcx; 251-253 use_texture=250; Abermenai fixtures == Murdaigean's.
- NAVMESH .nav COORDINATES ARE GLOBAL (do not subtract the zone offset). All arrivals/portals/centre are on
  one connected field component (Alb 4153, Mid 4576, Hib 4323, centre 3721).
- TODO Dun Murdaigean / Dun Abermenai: Keep rows (next free KeepID, Region 251/253, 33089,38271,3720) +
  guards placed from the mesh (wall tops ~4137, courtyard 3721, tower floors 4937/5291 near 34070,38912),
  lord on the top tower floor; guard levels within the bracket; verify doors attach (KeepArea).
  Rotating the Hib portal keep's guard offsets by 1096/4096 turns matched only 4-5 of 10: don't use.
- Quest detail collection runs in the Allakhazam tab (window.__qout); extract gzip+base64 when done.

## Goal 12 (hide enemy gamebot names) design notes
- NormalServerRules: enemy PLAYERS -> GetPlayerName = viewer.RaceToTranslatedName(race, gender), last name =
  RealmRankTitle, guild/title empty (period behaviour). NPC create packet (PacketLib1124.SendNPCCreate ~line 236)
  writes npc.Name / npc.GuildName for everyone -> enemy GameBots leak names.
- Plan: AutonomousNameMask.For(GamePlayer viewer, GameObject obj) -> race name for an autonomous GameBot of
  another realm (normal RvR rules), else real name; guild = realm rank title (mirrors player last name).
  Apply in SendNPCCreate (+1125-1127 if they override), GamePlayer attack messages (HitsYou/HitsYour/Critical,
  ~5230-5250 use ad.Attacker.GetName(0,true)), spell damage/resist messages to the target, death/kill
  broadcasts, /who-style lists, target examine. Combat log for enemy players also uses real names today.
