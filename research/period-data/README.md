# Period data (Dark Age of Camelot 1.65 / classic Shrouded Isles)

Raw data collected from the period's public sources, kept in the project so the work can be checked, redone and backed up
even if the sites go offline. Owner rule (2026-10-07): keep everything — page text, player comments, item data, NPC and
monster locations — not only what the generators use.

Collected 2026-10-06/07 by Claude for goal 10 (classic quests) and the bestiary/spawn audits.

## quests/ — classic and Shrouded Isles quests

| File | What it is | Source |
|---|---|---|
| `allakhazam_quests.csv`, `Albion.html`, `Midgard.html`, `Hibernia.html` | full quest lists per realm (id, level, zone, reward, type, expansion) | camelot.allakhazam.com quest lists |
| `allakhazam-quests-classic.json.gz`, `details.jsonl` | per-quest detail fields (start NPC, classes, levels, related NPCs) | Allakhazam quest pages |
| `walkthroughs.jsonl` | every period quest page used by the specs: header fields, walkthrough text, recorded NPC dialogue, reward lines, stat comments | Allakhazam quest pages (589) |
| `archive_quest_pages.jsonl` | full page text of every quest page, all player comments with authors and dates | Allakhazam (archive pass) |
| `archive_item_pages.jsonl`, `reward_items.jsonl`, `quest_item_links.jsonl` | every linked item page (stats, bonuses, AF/DPS, levels, where it drops), its comments, and which quest links it | Allakhazam item pages |
| `npc_sightings.json` | NPC/monster sightings with zone, coordinates and levels | CapnBry classic sightings |
| `specs/*.jsonl` | the quest specs written from the walkthroughs (steps, NPCs, locations, items, rewards) | derived |
| `dialogue.json` | NPC dialogue parsed from the walkthroughs (offers, keyword chains, accept/turn-in/finish lines) | derived |
| `resolved.json`, `spawn_plan.json`, `dataquest_preview.json`, `classic-quests.preview.json`, `validation.json` | generator stages and the validator's report | derived |
| `quest-npc-report.html` | the goal 10 report page (period quests on the server / missing, NPC audit) | derived |
| `*.py` | the pipeline: resolve_specs → plan_spawns → apply_world → gen_dataquests → apply_dataquests, validate_quests, enrich_dialogue, walk_receiver | scripts |

## bestiary/ — monster populations

| File | What it is | Source |
|---|---|---|
| `illia-bestiary-classic.json.gz`, `illia_zones.json` | Illia's Camelot Bestiary (archived copy): monsters per zone with levels | Illia's bestiary |
| `capnbry_zones.json`, `capn_*.html` | CapnBry zone mob lists and sightings | CapnBry |
| `fetch_uthgard.py`, reports | Uthgard comparison | Uthgard |
| `report_*.csv`, `bestiary-report.html`, `npc_audit.csv`, `recommendations.json` | comparisons against the server's spawns | derived |

## GOALS 10-11 LEDGER.md
Everything added for goals 10 and 11, for the owner's review (placeholders and substitutions are listed there).

## archive/ — full-site period archive (2026-10-07, owner: "grab literally everything")
Raw pages kept verbatim (gzipped JSON lines, one page per line: url, fetch time, body/html) so nothing a parser
misses is lost. Scope: Classic, Shrouded Isles and Trials of Atlantis as they stood before Catacombs (cutoff
2004-12-07; New Frontiers came later still). Trials of Atlantis data is archived only — it is not put on this server.

| Folder | Source | What |
|---|---|---|
| `capnbry/` | capnbry.net/daoc (radar mob database) | every realm/zone/typetag index, every zone mob list, and the radar sighting XML (zone, x, y, z, level) of every mob id — `raw_pages.jsonl.gz`, fetcher `fetch_capnbry_all.py` |
| `uthgard/` | disorder.dk/daoc/bestiary (Uthgard 2.0 bestiary) | every zone, monster (levels, aggro, drops with rates, faction, zones), item, faction, salvage and XP-item page — `raw_pages.jsonl.gz`, crawler `crawl_uthgard.py` |
| `wayback-allakhazam/` | Internet Archive copies of camelot.allakhazam.com | the CDX index of every capture on or before 2004-12-07 (`cdx_index.txt`) and the last pre-cutoff capture of every quest, mob, item, NPC and zone page (`raw_pages.jsonl.gz`) — the historical (period) version of the pages, fetcher `wayback_allakhazam.py` |
| `wayback-allakhazam/quest_pages.jsonl.gz` | Internet Archive copies of every classic quest walkthrough page | the last capture on or before 2004-12-07 of each Allakhazam quest page the server's quests come from (588 of 590 found); fetcher `fetch_quest_pages.py`. Source of the in-game Quest Guide |
| `allakhazam-live/mob_direct.jsonl` | Allakhazam monster pages fetched one by one for quest needs | level, type, habitat, loot of the kill-task monsters (rubbish, rusty gyve, cliff yale yearling, billious goo) |
| `../quests/quest_guides.json` | the in-game Quest Guide text (built by `quests/build_quest_guides.py`) | per quest: period walkthrough (418 of 442 from 2001-2004 copies), its source and last-updated date; copied to runtime/server/classic-quest-guides.json |
| `wayback-warcry/` | Internet Archive copies of daoc.warcry.com (Camelot Warcry) | the period quest database (summaries, hints, full spoiler walkthroughs with player-submitted spawn notes), NPC and item databases, compendium maps — last capture on or before 2004-12-07; fetcher `wayback_warcry.py` |
| `allakhazam-live/` | camelot.allakhazam.com today | every Classic/SI/ToA quest page (all dialogue, steps, rewards, every player comment with dates), every period-zone bestiary page, every monster page (levels, habitats, drops, comments), every item page those link (full stats, sources, comments); one file per kind (`quest`, `item`, `mob`, `zone`, `zoneinfo`, `questlist`, `zonelist`, `*_comments`). Collected in a browser tab (the site refuses scripts) by `zam_worker.js`, handed to `../quests/walk_receiver.py`. Pages carry their own "Last Updated" dates; comments carry posting dates, so post-period additions can be told apart. |
