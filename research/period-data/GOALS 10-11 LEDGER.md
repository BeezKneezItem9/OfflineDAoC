# Goal 10 ledger (old goals 10 + 11): classic quests, NPCs and monster spawns

Local notes only, never on GitHub. Every addition, removal and change made for goals 10 and 11 is listed
here so the owner can review it ("10 and 11 status"). Each database change has a backup next to the
database (`runtime/data/opendaoc.sqlite3.before-*.db`).

## Owner rules (2026-10-07)

- Add and wire up, for the player only, every 1.65 and classic Shrouded Isles quest: every epic step with
  its reward and the experience it gave (where it can be found), all trainer quests, all optional quests
  in classic and SI zones. None missed. Spawn any missing quest monsters.
- Markers: the period quests had none, but add map markers: yellow on the map for quest givers and red for
  quest locations, including in dungeons, handled the same way as the owner's bounty, emissary and
  Sluaghbinder epic markers. Leave the owner's existing custom epic, bounty and emissary markers alone.
- Add very-high-likelihood missing NPCs (several sources agree), placed properly and reachable by bots.
- Add high-likelihood missing monster spawns and remove high-likelihood custom spawns, then adjust the bot
  goals, the bounty quest pool, the gamebot/companion charm pool and the players' custom charm list.
- Bonus: thin Coruscating Mine where period data shows its monsters were sparse.

- Quest monsters vs gamebots (owner 2026-10-07: "i dont want gamebots killing a quest npc and then it not
  being there for the player"):
  - event monsters (shades, summoned bosses, scripted appearances) spawn only when a player on that quest
    step triggers them, only for that encounter, and despawn after; gamebots cannot trigger them;
  - quest givers and turn-in NPCs are friendly/neutral and never targets;
  - named quest monsters that live in the world are excluded from gamebot camp goals, the bounty pool and
    the charm pools (like the raid encounters), gamebots ignore them unless attacked first, and they get a
    short respawn.
- No quest can be lost to a restart (owner 2026-10-07: "make sure there is no scenario where a player grabs a quest,
  stops the game and turns off server, comes back and the quest mob is gone forever"):
  - quest progress is saved per character (CharacterXDataQuest), so a restart resumes the same step;
  - event monsters are never saved; they appear whenever a player on that step comes near the spot, so a restart,
    despawn, death without a drop, or a kill by someone else just means it appears again on the next approach;
  - named world quest monsters are normal DB spawns with a short respawn (never -1), never in a removal list;
  - a lost or destroyed quest item is handed out again by that step's NPC.

## Sources

- Quests: Allakhazam's DAoC quest database (1,750 Classic and Shrouded Isles quests, walkthroughs being
  collected 2026-10-07); report https://claude.ai/artifact/KB8oAhoiBYc8rPUTq8ZL7B
- Monsters: CapnBry radar logs, Illia's Camelot Bestiary, Uthgard (semi-accurate); report
  https://claude.ai/artifact/WhyQGzzn6BtAqPP7BJcKTF

## Applied

| Date | What | Rows | Backup |
|---|---|---|---|
| 2026-10-07 02:32 | Howth (Silvermine Mts.) and Connla (Shannon Estuary) low-level monsters: every species CapnBry saw there at level 15 or lower that the server lacked, placed at CapnBry's sighting spots on the navmesh (enchanted spraggonoll left out: sources disagree on its level). List: `hc_plan.json` in the session scratchpad. | +631 Mob | before-howth-connla-20261007-023230 |
| 2026-10-07 02:32 | (Goal 9, listed for completeness) Battleground monsters for Abermenai, Thidranki, Murdaigean, Caledonia, capped at each bracket; Dun Murdaigean and Dun Abermenai keeps with Renegade guards. | +311 Mob, +2 Keep, +12 NpcTemplate, guards | before battleground plan (bg backup 20261007-023216) |
| 2026-10-07 03:40 | Fixed 54 size/model fields on 47 of the new rows (small walking rock, ire wolf, haunted driftwood kept template lists like "50;53"). | 54 fields | before-size-fix-20261007-0340xx |
| 2026-10-07 03:40 | Coruscating Mine thinned: 51 stacked duplicates merged, 37 rare-species caps, 8 "gemklicker horder" renamed (details below). | -88 Mob, 8 renamed | before-coruscating-thin-20261007-034027 |

## Applied details and pending

- Coruscating Mine (bonus): why it is overpopulated, and the fix (`thin_coruscating.py`, plan
  `coruscating_plan.json`), 384 spawns -> 296.
  - Cause: all 384 rows come from the imported public database (placeholder 2000-01-01 dates, none from our 1.65
    restoration). That import recorded many monsters twice a few steps apart, so camps come in doubled: 83
    same-species pairs stand within 150 units of each other (Spraggon Den 46, Treibh Caillte 43, Koalinth
    Caverns 7), and a spawn here has about 6 others within 500 units, the densest of the Hibernian dungeons.
    Every spawn also returns after 3 minutes (same as the other dungeons).
  - Fix 1: merge each stacked duplicate into one spawn (51 rows).
  - Fix 2: cap the species period data shows as rare (Illia's bestiary for species/levels, Uthgard kill counts
    for abundance) - 37 rows, densest clusters first:

  | Monster | After merge | Uthgard kills | Keep |
  |---|---|---|---|
  | unseelie viewer | 9 | 9 | 2 |
  | casolith | 8 | 2 | 2 |
  | haunting draft | 3 | 8 | 2 |
  | vein golem | 10 | 71 | 4 |
  | lode protector | 13 | 148 | 8 |
  | guardian of the silver hand | 6 | 41 | 3 |
  | lode runner | 6 | 32 | 2 |
  | unseelie overman | 5 | 15 | 2 |
  | silver-flecked skeleton | 3 | 14 | 1 |

  (weewere fell from 20 to 9 by the merge alone.) The 8 "gemklicker horder" rows (a misspelling no source has)
  are renamed "gemclicker horder". Not changed: species that look under-represented (trammer, tunnel imp,
  unseelie mango, larval predator, silver-maddened werewolf).

## Progress

- 2026-10-07 03:25: quest specs written from the walkthroughs (session scratchpad quests/specs/*.jsonl):
  Albion 55 (every old-epic step for all four guild lines, the SI starter epics, Traveler's Way, Chains of
  Death, Heart of Albion), Midgard 52 (all five lines incl. the Rod of Mimir, Grenlock and Red Dagger
  chains, SI starters, Cape of the Mother Wolf, Jewel Hunt), Hibernia 22 so far (Cad Goddeau, Path of
  Focus, Moonstone lines; Last Heir, Unnatural Powers 43, Silver Run and a few more pages still being
  collected). The level 50 finales already on the server are reused (their prerequisite checks get turned
  back on once the earlier steps exist).
- NPC match against the server: 409 of the named quest NPCs/monsters exist (several under a period
  spelling: Sir Tilian, Caelin Finan, Lidmann Halsey, Maeve, the Crone, Gordin Tuhan; Catacombs of Cornwall =
  Catacombs of Cardova); about 131 names have no spawn at all, mostly quest-event monsters (shades, named
  quest bosses such as Centurion Favius, Fasius Previlus, Sockburn worm, Morven and his heirs) that the
  generator will spawn.
- 2026-10-07 04:00: all 145 epic-line specs done (Albion 55, Midgard 52, Hibernia 38; the six level 50
  finales on the server, including Hibernia's Harmony50 "The Horn Twin" = Last Heir 50, are reused).
  Generator stage 1 (resolve_specs.py): 678 steps, 572 with a map-marker point; 104 quest NPCs/monsters have
  no spawn. Stage 2 (plan_spawns.py -> spawn_plan.json): 76 of the 104 have an NPC template in the database
  (defined but never spawned); 54 have CapnBry period sightings (positions and levels); 96 placed on the
  navmesh (sightings, walkthrough locs or landmarks), 12 are event monsters (player-triggered). Still to
  research before spawning: Centurion Favius, Commander Blaen, Erich, Esmond, Lunaris Primus Pilus, Shaman
  Saelonna (no Arawnites in Snowdonia on the server), Raemon (no cyclopes in Breifine), Keapi.
  Reward items: pass 2 is collecting every quest's item pages (class, slot, armor, AF, bonuses, level); the
  first ones already correct guesses (Redoubled Leggings are Paladin chain, not Cleric).
- 2026-10-07 05:00: all period non-epic quests specced. Era sort of the 1,382 Allakhazam quests missing from
  the server: 425 period (earliest comment by Oct 2003, or an early Allakhazam id), 927 later (the 2004 newbie
  revamp, Catacombs, Trials of Atlantis, 1.70+ realm quests, Darkness Rising and later), 30 borderline checked by
  hand. Dropped as already on the server or covered elsewhere: Immediate Resolution v2 (ImmediateResolutionVB
  script), Traveler's Way (Hib) index page (its three class quests are in the epic specs), Reawakening (inside
  Cad Goddeau A), Last Heir 50 (on the server). Dropped as later content: The Riches of Atlantis, Expanding the
  Family Business, Studies Abroad (all lead into Atlantis), Gair's Hand-Me-Downs (needs /level), the Ulfgar
  one-time drop (removed Jan 2003, replaced by Price of Excellence), Worn Tradeskill Tools (crafting).
  Added back: Strange Bedfellows (Alb, Hib) and Breaking the Blade (Hib) - the 1.65 Black Plague chain exists in
  all three realms even though Allakhazam entered two of the pages later.
  Specs now: Albion 186, Midgard 210, Hibernia 196 = 592 (145 epic + 447 other: regular quests, mini quests,
  one-time drops, kill tasks). New spec shapes used: repeatable trade turn-ins (Flint Weapons, Rock Imps,
  Bandit Ears), one-time drops (`type: otd`, item once per character from a named monster) and kill tasks
  (`type: kill_task`, XP per item with a turn-in limit). Quests whose walkthroughs are fragmentary are flagged
  in their notes for research before generation (e.g. Stoneheart, Mammoth Hunt, The Anxious Healer).

## Planned

Quest pipeline (2026-10-07): (1) collect every Classic/SI walkthrough (1,750 pages; steps, NPCs, zone locs,
rewards); (2) second pass for reward item links and their stats from the equipment pages; (3) one structured
spec per quest (giver, steps, targets, counts, items, prerequisites, class limits, rewards, XP) read from the
walkthrough, using pre-1.75 locations (1.65 era) where a walkthrough notes a later move; (4) a generator that
matches specs to existing NPCs/monsters/items, spawns what is missing on the navmesh, and writes data quests
(or scripts for steps data quests cannot express), with map markers; (5) every addition listed below.
First check: most epic quest NPCs already exist (Belef, Master Vismer, Nia Loaman, Sacrificer Harish, Morlin
Caan, Masrim, Scout Argyle, Hunter Derwyn); Centurion Favius is missing; none of the epic reward items exist.


- Monster additions (326 species, several sources agree), camp fills (504 camps of 1-2 with period
  camps of 5+), level fixes (19), removals (7): see the bestiary report's "Recommended changes".
- Quests: all old epic steps (levels 5/7/11/15-48 before the existing level 50 finales), trainer quests and
  optional quests, built as data quests with their NPCs, monsters, items, rewards and experience.
- NPCs: very-high-likelihood missing quest and service NPCs.
- Afterwards: bot goals, bounty pool, gamebot/companion charm pool and players' charm list follow the
  changed spawns.

## Generator stage 3 design (2026-10-07 06:05)
DataQuest rows (one row per quest; per-step lists joined with "|"; existing 238 rows are all collection turn-ins):
- talk -> Interact (4) / InteractFinish (5); deliver -> Deliver (2) / DeliverFinish (3) with StepItemTemplates;
  whisper -> Whisper (6/7); search -> Search (8/9) plus a SourceName "SEARCH;step;text;region;x;y;radius;seconds";
  collect -> Kill steps with a StepItemTemplates drop chance, then a Deliver/Collect step; kill N -> N Kill steps
  (no per-step counter in DataQuest); quest prerequisite -> QuestDependency (quest names); class lists ->
  AllowedClasses; rewards -> RewardMoney/RewardXP per step, FinalRewardItemTemplates / Optional "N|a|b".
- TargetName per step is "npc name;region". Steps DataQuest cannot express (use_item, drop_item, group, buy,
  die_to, event spawns) get a small script per quest family.
- otd -> StartType KillComplete (3); kill_task -> StartType Collection (1) with MaxCount.
- Markers from classic-quests.json (yellow givers, red step locations) via ClassicQuests.cs (0xFFFE0004).
- Generator detail (DataQuest.AdvanceQuestStep): StepItemTemplates per step is "template;chance"; a kill/search step
  with a chance gives the item on its kill and only advances when the roll succeeds; advancing INTO a Deliver step
  hands the player that step's item (letters/packages). So "collect a drop then turn it in" = Kill steps with the
  drop + a Collect/CollectFinish turn-in (not Deliver, which would hand out a duplicate). 207 of 592 specs are
  ready to generate now (giver and every target resolved, only DataQuest step kinds); blockers: 213 need spawns,
  186 givers unresolved, 25 generic targets ("<guard>"), 29 use_item, 21 unresolved targets, a few custom kinds.
- 2026-10-07 06:15: generator stage 3 dry run (scratchpad quests/gen_dataquests.py -> dataquest_preview.json): 146
  DataQuest rows ready (Albion 48, Midgard 61, Hibernia 37; 1-8 steps), 183 quest items (type 40, not tradable or
  droppable, PackageID ClassicQuest, model borrowed from existing items with the same keyword; 27 use a plain sack),
  no name or item id collisions. XP: walkthrough numbers where given; "auto" = median share of the level's XP from
  the 159 quests with numbers (L1-5 16%, 6-10 15%, 11-20 8.4%, 21-30 2.6%, 31-40 1.5%, 41-50 5.6%); "N bubbles" =
  N tenths of the level. Not yet in the database. Next: one-time drops / kill tasks (51), reward equipment (pass
  2), markers, then the DB insert with a backup; then the blocked 395 (spawns, givers, custom steps).
- Spec types: 460 quests, 79 one-time drops, 53 kill tasks. One-time drops -> StartType KillComplete (3) on the named
  monster with the item as FinalRewardItemTemplates (needs the item's real stats from pass 2). Kill tasks -> StartType
  Collection (1) at the giver with CollectItemTemplate/MaxCount, and the item added to the named monsters' loot
  (LootTemplate/MobXLootTemplate rows at the spec's chance), like the existing Atlas XP-item turn-ins.
- 2026-10-07 06:16: generator also writes classic-quests.preview.json for the 146: DataQuest ids 20000+ (reserved;
  existing 1-408), ClassType DOL.GS.Quests.ClassicQuestStep, 579 red step markers, 76 named quest monsters for the
  gamebot exclusion, and 102 deliver steps whose item is re-issued by the handing NPC if lost. To apply at the next
  server stop (DB backup first, asserted row counts): 146 DataQuest + 183 ItemTemplate rows + classic-quests.json.
- Correction (06:18): one-time drops use the server's own LootOTD table (MobName, ItemTemplateID, MinLevel; 63 rows
  today), not DataQuest. Kill tasks: LootTemplate (TemplateName, ItemTemplateID, Chance, Count) + MobXLootTemplate
  (MobName -> template) for the drop, plus a Collection DataQuest at the giver.
- 2026-10-07 08:25: owner (testing goal 11 live): hold the classic quest DB load until they say to resume my runs; then
  run scratchpad quests/apply_dataquests.py with the server stopped (146 quests, 183 items, classic-quests.json).
