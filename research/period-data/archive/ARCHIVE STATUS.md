# Archive jobs - status and how to resume (updated 2026-10-07 23:55)

Every job writes straight into this folder and resumes from what it already saved: re-run the same script.
When a job finishes, its output stays here (owner: keep everything locally in period-data).

| Job | Script | Output | State at 22:26 |
|---|---|---|---|
| CapnBry radar archive | `capnbry/fetch_capnbry_all.py` | `capnbry/raw_pages.jsonl.gz`, `capnbry/sightings_index.json` (`index_sightings.py`) | DONE: 5,805 mobs, 176,970 sightings |
| Uthgard bestiary crawl | `uthgard/crawl_uthgard.py` | `uthgard/raw_pages.jsonl.gz` | running: 9,200 pages |
| Uthgard map dots | `uthgard/uthgard_locations.py --from-plan` | `uthgard/locations.json`, `uthgard/maps/` | run on demand (quest spawns) |
| Wayback Allakhazam (pre-2004-12-07) | `wayback-allakhazam/wayback_allakhazam.py` | `cdx_index.txt`, `raw_pages.jsonl.gz` | CDX index ~280k lines; Archive slow (504s), retries |
| Wayback reward items | `wayback-allakhazam/fetch_reward_items.py` | `wayback-allakhazam/items_direct.jsonl.gz` | running: 100 / 834 |
| Wayback Warcry | `wayback-warcry/wayback_warcry.py` | `cdx_index.txt`, `raw_pages.jsonl.gz` | CDX done (40,901); pages 11,625 to fetch |
| Allakhazam live | browser worker `allakhazam-live/zam_worker.js` (tab on camelot.allakhazam.com) | `allakhazam-live/<kind>.jsonl.gz` via `../quests/walk_receiver.py` + `zam_handoff.js` | 2,969 pages saved (quests, quest items, comments); mobs/items/zones queued |

Hand-off for the browser worker: run `zam_handoff.js`'s `zamHandoff(15e6)` in a second camelot.allakhazam.com tab
with `walk_receiver.py` running (127.0.0.1:8766), check `allakhazam-live/handoff.log`, go back to the site and run
`zamConfirm(<last seq>)`.


## Update 2026-10-07 23:55
- **Wayback quest pages: DONE.** `wayback-allakhazam/fetch_quest_pages.py` -> `quest_pages.jsonl.gz` (590 quests, 588 with a pre-2004-12-07 capture). Feeds `quests/build_quest_guides.py`.
- **Allakhazam mob pages for quest monsters:** `allakhazam-live/mob_direct.jsonl` (4 pages fetched by hand for the kill-task camps).
- **Allakhazam live worker:** hand-off saved seq 2970-3894 (925 records) to `allakhazam-live/<kind>.jsonl.gz`; IndexedDB cleared through 3894 (__zamSent 3894). Queue left: quests+items ~4,000, zones 276, mobs ~3,890, items 278.
- **Uthgard crawl: DONE** (12,612 pages in `uthgard/raw_pages.jsonl.gz`).
- **Wayback Allakhazam:** CDX index 284,000 lines; it kept failing on one truncated CDX page, so `wayback_allakhazam.py` now asks for smaller pages when that happens; restarted (task b3ghrk1i6).
- **Wayback reward items:** 200 / 834 (running, task b0ob8iebh).
- **Wayback Warcry:** 2,929 / 11,625 pages (running with retries, task byzz51itr).
