# Beez Online — Progression and Companion Refresh Windows Test Release

Source: **992b959fbf44a48497a4e5baae5a9937dce4a6c2**, branch `beez-online-six-features`.
Prerelease tag: `beez-test-992b959`.

Self-contained Windows x64 Release **update package** for an existing playable
Beez Online / OfflineDAoC 0.35/0.35b installation. Server, optional launcher and
matching .NET 10.0.12 dependencies are included. Existing world/client content
is reused; this is not a fresh-world/client distribution.

## New since beez-test-d583ee3

- Darkness Falls PvE uses the higher of ordinary PvE and RvR location rates,
  fixing lower XP caused by its RvR classification. A configurable 20% minimum
  zone bonus rewards its danger without stacking on top of a higher enabled
  installed zone bonus. Other regions' PvE rates remain unchanged.
- Enemy-player character XP uses one shared path for real and eligible autonomous
  victims, including the actual character XP grant. `rvr_kill_xp_multiplier`
  defaults to **100 times native PvP XP**, with no additional server 10x PvE rate.
  Native level/group/contribution/cap rules apply before that multiplier;
  level-50 recipients remain capped. RP/BP are not multiplied.
- Removed hourly/rolling repeat-kill XP quotas and tracking. Duplicate-death,
  invalid-kill and native recent-death worthiness protections remain.
- `/spawn refresh` and the clickable **Refresh** menu option update eligible
  grouped companions to your current level in place, up or down. The same bots,
  identity, equipment, build plans and group slots remain. Stats, pools, learned
  skills/spells/styles and client level/status information are refreshed.
  The menu remains usable with seven companions. Combat, casting and stable
  travel reject refresh; dead/inactive bots are skipped. Changed companions'
  old summons are released through the normal lifecycle so AI can summon the
  new learned rank. Recruited autonomous XP aligns with the new level to prevent
  old XP immediately reversing a downward refresh.

Equal-level RvR XP per member, no keep/item/location bonus, fully eligible damage:

| Level | Solo, either victim type | Two-member group, each |
|---|---:|---:|
| 10 | 2,048,000 | 1,024,000 |
| 30 | 660,561,600 | 330,280,800 |
| 49 | 14,605,414,800 | 7,302,707,400 |

Native maximum storage headroom prevents signed integer overflow. Normal
character training/level stages remain. In controlled level-30 cases with PvE
rate 10, DF equal-level solo NPC XP changes from 2,741,330 to 20,906,766;
open-world and other dungeon rates remain unchanged. See the included XP report
for assumptions, caps, rounding and installed-world limitations. The original
real-player blanket-zero report was not reproduced; the autonomous-victim
missing XP grant was confirmed and corrected.

## Included regeneration overhaul

The earlier 1.78/1.87 overhaul remains: no below-50% power penalty (even with
an old saved True flag); standing OOC health/power ticks every 3 seconds;
combat ticks every 7 seconds standing / 5 sitting; native recovery and applicable
regeneration aids doubled once. Buff Stone's stored +5 power aid contributes
+10. OOC endurance recovery works while standing/moving on the one-second clock.
Mana Roots retains its level-15 rank, 60-second root, free/instant activation,
casting permissions and visuals. Its reproduced 19.9-second post-expiry tick gap
is corrected, with no Roots-specific multiplier. Full formulas are included in
`notices/BEEZ-REGENERATION-OVERHAUL.md`.

## Persistence and installation

Extract outside your installation. Close the server, launcher and client before
replacing binaries. Review `DEPLOYMENT.md` and `REPLACEMENTS.csv`; replace only
manifest-listed files and keep dependency sets together. Existing deployment
scripts and manifest conventions are retained, without introducing new backup
procedures. Your existing installation copies remain your reference fallback.

No database, character/account data, saved configuration, world scripts, quests,
translations, navigation meshes or client files are included for replacement.
No schema migration, installed-world replacement or new client patch is required.
On your next authorized startup, native property registration adds missing
`darkness_falls_xp_bonus_percent=20` and `rvr_kill_xp_multiplier=100` defaults.
Existing saved values remain. Old rolling-quota settings are unused; no rows need
deleting. The package does not deploy or launch anything automatically.

## Validation

Windows server and launcher self-contained Release publish succeeded.
Full server regression: **2,940 passed, zero failed; 61 existing ignored cases**.
Focused progression/companion tests: **400 passed**. Actual XP record changes,
levels 10/30/49, both victim types, group distribution, caps/overflow, in-place
bot identity/equipment preservation, spell damage, melee weapon skill and
command/menu routing are covered. All 400 focused cases also passed against
the exact packaged managed server DLLs in an isolated Linux test harness.

Windows AMD64 apphost/native headers, complete runtime/native dependency closure,
embedded source revision in five project binaries, replacement/package hashes
and deployment-file completeness are verified. Deployment preservation checks
use disposable PowerShell fixture data only. Windows launcher execution and
rendered client/in-game behavior are not claimed tested in this Linux workspace.
After a separately approved deployment, test real/autonomous RvR XP, DF PvE,
Refresh with seven companions, pet resummoning, dead-bot skipping and combat
rejection. No playable server or client was started.
