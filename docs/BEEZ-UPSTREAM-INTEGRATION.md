# Beez Online upstream integration report

Integrated upstream repository: https://github.com/shadowofze/OfflineDAoC

Upstream default branch: `main`; exact fetched commit:
`d337d184034f4c84e1e1748fda7f5b2deef135b8`.

Original Beez development HEAD and backup commit:
`fb4a21785ee353e4f8da47189f12ce292d809e8e`.

Backup branch: `beez-online-backup-20261009T003242Z` (timestamp in UTC).
Integration branch: `beez-upstream-integration`. Its merge parents identify the
original Beez HEAD and exact upstream HEAD; obtain its commit with
`git rev-parse beez-upstream-integration`.

The development branch `beez-online-six-features` is not promoted. No server
was started, DLL deployed, playable installation altered, or persistent database
replaced. The existing ignored local build configuration was preserved.

## Investigation and upstream changes

Git 2.52.0, Bash 5.2.37, and .NET SDK 10.0.401 work in this Linux workspace.
Native Git read operations and the backup push succeeded with existing platform
authentication. GitHub's repository page embeds fork-parent and network-root
metadata naming `shadowofze/OfflineDAoC`; the checkout's origin names
`BeezKneezItem9/OfflineDAoC`. The GitHub API route returned a proxy 403, so fork
identity was verified from GitHub's page metadata instead. The upstream HEAD
symbolic ref identifies `main`. OpenDAoC-Core was not assumed to be the parent.

The common ancestor is `296d05f1209a00ebc7885ff8891b022411b429ed`.
There are **25 upstream commits** absent from the original Beez branch. Their
combined diff affects 249 files, including documentation and release-file renames.
The integration uses a two-parent Git merge, with no squash or history replacement.

- Features: staged keep/relic sieges, larger relic forces, siege squads/equipment,
  battleground goals and UI, neutral dungeon raids, bot realm ranks/abilities,
  announcements, classic quests/Quest Guide, and client war-map/quest patch tools.
- Fixes: first-contact pull timing, route threats, border and stable landings,
  teleporter stand-off, companion pet travel, stealth visibility, protected keep
  lords, summoned/hostile quest NPCs, pet damage scaling, and siege cleanup.
- Performance: reduces population-wide party sweep frequency and roster-array
  rebuilding; raid healing finds the lowest-health target without sorting whole
  rosters. Native navigation query timing was added. No performance benchmark or
  large-population playable run was performed here.
- Dependencies: no upstream changes to project package versions, project/solution
  manifests, native navigation imports, or database model files. .NET 10 remains
  required. Release tooling now expects bundled runtime 10.0.11 and 0.35 assets.

## Overlap and merge resolutions

Eleven files changed on both sides:

1. `source/server/GameServer/ECS-Components/AttackComponent.cs`
2. `source/server/GameServer/bots/BotBrain.cs`
3. `source/server/GameServer/bots/GameBot.cs`
4. `source/server/GameServer/bots/autonomous/AutonomousBotRealmPointRewards.cs`
5. `source/server/GameServer/gameobjects/GameNPC.cs`
6. `source/server/GameServer/gameobjects/GamePlayer.cs`
7. `source/server/GameServer/packets/Server/PacketLib1124.cs`
8. `source/server/GameServer/realmabilities/handlers/PurgeAbility.cs`
9. `source/server/GameServer/serverrules/AbstractServerRules.cs`
10. `source/server/GameServer/spells/SpellHandler.cs`
11. `source/server/Tests/UnitTests/UT_RvrExpansion.cs`

Git reported content conflicts in five files. Final resolutions follow the owner's
subsequent instruction to remove Beez RP and enemy naming and adopt upstream:

| Conflicting file | Final resolution |
| --- | --- |
| AttackComponent.cs | Upstream combat name handling, unchanged. |
| AutonomousBotRealmPointRewards.cs | Entire upstream reward implementation; no Beez recovery cache or bot-payout exclusion. |
| GameNPC.cs | Upstream viewer-relative gamebot death messages and normal NPC behavior. |
| PacketLib1124.cs | Upstream race name and realm-rank title in the guild field. |
| SpellHandler.cs | Upstream name/message paths; retains Beez Buff Stone/song concentration, effectiveness and target-isolation hooks. |

The auto-merged files were reviewed too. BotBrain retains simultaneous-song
maintenance alongside upstream siege/combat/travel changes. GamePlayer retains
ring, stone, portal, song and Mana Roots lifecycle hooks. PurgeAbility retains
Mana Roots exclusion while supporting upstream bot Purge. GameBot and
AbstractServerRules now match upstream, removing Beez death-recovery/examine,
loot-name and shared human RP overrides. The extra Beez packet, pet, effect and
spell naming overrides are removed. Beez's RP/name helper files are deleted.

## Final behavior and preserved customizations

The Developer Ring, Buff Stone, simultaneous songs/chants, owner-only two-way
Bind Stone portals, and single-rank level-15 Mana Roots remain. Their dedicated
implementation files and fixture data are unchanged from the verified baseline;
shared hooks were reviewed and regression-tested. Ordinary monster loot/equipment,
Realm Exchange, stable routes, and earned gamebot equipment remain in the merged
code; upstream introduces faster town-teleporter routing as an option.

RP intentionally changes from Beez's gradual recovery to upstream's all-or-nothing
repeat-kill eligibility window using `rp_worth_seconds`. Recovery is upstream
per-object temporary state rather than Beez's persistent-BotId cache. Upstream's
autonomous-victim path no longer has Beez's explicit RvR-only victim gate, and
participating bots can earn RP, gain realm ranks, buy abilities and use supported
actives. Human-victim arithmetic is restored to upstream.

Identity intentionally uses upstream's race/rank display and message coverage,
rather than Beez's race-only/blank-guild display and broader additional hooks.
Older packet versions, examine and incidental pet/effect/loot text require manual
review; no additional Beez masking policy is retained.

Other gameplay changes include companions counting toward Bring A Friend by
default, staged sieges, relic attacker caps increasing from 192 to 240, true
stealth detection for gamebots, and no loot from keep guards/gamebots/owned pets.
Treat these as upstream behavior changes during in-game acceptance.

## Validation and test-count reconciliation

| Check | Outcome |
| --- | --- |
| Original Beez baseline Release build | Passed. |
| Original Beez baseline regression | 2,659 passed; 58 NotExecuted. |
| Final Release solution/GameServer build | Passed; 0 errors, 623 warnings. |
| Final full available server regression | 2,785 passed; 0 failed; 61 NotExecuted. |
| Focused retained Beez/Mana Roots and upstream RP/RA/name checks | 81 passed; 0 failed. |
| Windows launcher and launcher-test cross-compilation | Passed; 0 errors, 1 warning. |
| Progress importer Windows cross-compilation | Passed; 0 errors. |
| Windows launcher test execution | Aborted: Linux has no Microsoft.WindowsDesktop.App runtime; no passing execution claim. |
| Git conflict-marker and CRLF-aware whitespace review | Passed. |

The focused selection contains 42 retained Beez cases, 18 Mana Roots cases,
and 21 upstream RP/realm-ability/name cases. Nine former Beez RP/name cases were
removed because their behavior was explicitly retired, not to hide a failure.
Upstream adds a net 135 executed cases: **2,659 + 135 - 9 = 2,785**. Existing
upstream pull/siege tests also update parameter cases for the new behavior; the
count difference is not solely new fixture files. Three new explicit probes
(`UT_PathProbe`, `UT_ZoneBoundaryLeakProbe`, `UT_ZoneStepProbe`) increase the
unexecuted installed-data/navmesh checks from 58 to 61. The TRX has 2,846 total
outcomes; the runner's console summary omits explicit probes from its total.

Results are outside tracked source under
`/workspace/setup/beez-integration-results/final-regression.trx` and
`final-focused.trx`; build/test logs are under `/workspace/setup/`.
Existing compiler/analyzer and NuGet OpenTelemetry vulnerability warnings remain.
No dependency versions were changed to suppress them.

## Database, configuration and build/deployment actions

No upstream schema or database-model migration was added, and no live database
was opened or written during integration. Bot realm-ability expenditure extends
the existing serialized-abilities value (`trained-level|N|realm-points|M`); older
records without the new suffix parse as zero spent points. Back up data before
any later approved startup and assess rollback of this saved representation.

New upstream server properties use normal database-backed property loading:

| Category / property | Default |
| --- | --- |
| pve / baf_companion_bots_count | True |
| autonomous / bot_use_town_teleporters | True |
| autonomous / rvr_siege_staged_assault | True |
| autonomous / rvr_siege_defense_ratio | 0.5 |
| autonomous / player_keep_defense_horn_sound | 219 (0 disables) |
| autonomous / rvr_battleground_announcements | True |
| autonomous / pve_realm_event_announcements | True |
| autonomous / neutral_raid_encounter_level_cap | 0 (disabled) |

The new neutral-raid cap key deliberately does not reuse the obsolete
`neutral_raid_encounter_level` key. Existing three-column bot-goal JSON stays
valid: `Battlegrounds` defaults to 0; level-50 battleground weight must be 0.
Review defaults before any approved playable rollout; no settings were changed here.

Full upstream world features require release data, beyond compiled DLLs:
`classic-quests.json`, `classic-quest-guides.json`, matching world quest/spawn
rows, and navigation `navmesh/seams.json` / `navmesh/pockets.json` with matching
meshes. These generated runtime assets and a playable world database are absent
from this checkout. Missing quest files disable the new event/marker support or
fall back to journal text; missing seam/pocket files keep fallback navigation.
Client classic-war-map and Quest Guide button/marker improvements additionally
require verified 0.35 client patches/textures. Existing clients are not patched.
New embedded period-restoration IDs alone do not apply world database updates.

No active GitHub Actions build/deploy workflow exists in this checkout
(`.github` contains CODEOWNERS). Existing solution build commands remain valid.
External automation calling `build_release_034.py`, `assemble_release_034.py`,
`seal_release_034.py`, `smoke_release_034.py` or `test_release_import_034.py`
must update to their `_035.py` names. New package tooling requires the new client
hashes, 0.35 profile/layout, runtime and release metadata. It builds clean public
packages by clearing progress in staging; do not use it against a playable save.
Package assembly/import/gameplay smoke tests were not run: they require Windows
and actual release assets; the smoke command also starts a server, which is not
authorized. Cross-compilation does not certify packaged runtime compatibility.

## Recommended acceptance before promotion/deployment

Use an approved disposable playable copy and backed-up SQLite data:

1. RP: first/repeat kills before/after the eligibility window; bot/player/pet and
   mixed groups; bot ranks/abilities/trainer visits; human progression and BG caps.
2. Identity: allied/enemy/staff viewers; race/rank packet display and combat,
   spell, death, examine, pet, effect and loot surfaces on supported clients.
3. Developer Ring and Buff Stone: grants, caps, equip/unequip/relog, all realms,
   stronger-buff preservation, zoning, death/logout and save exclusion.
4. Songs/chants: every eligible class, instruments, simultaneous families,
   melee switching, movement and CC suspension/recovery.
5. Bind Stone: owner-only return trips, companions, expiry, combat/location
   restrictions, death/logout/rebinding and failed/slow arrivals.
6. Mana Roots: level 14 versus 15, one 60-second rank, native mana ticks,
   no early Purge/cancel, overlapping roots, mount guard and death/logout cleanup.
7. Upstream runtime: town/stable routing, companion pets, stealth detection,
   staged sieges/keep loot/BAF, quest assets and client UI, large-population load.

Windows tests, installed-world probes, package import/smoke tests and in-game
acceptance remain outstanding. Retain the integration branch for review; no
promotion or playable compatibility guarantee is made from Linux tests alone.

## Incorporated upstream commits

```text
d337d18 0.35 / 0.35b "Claude Takeover III": release tooling, docs and changelog
0a2e17a Source update: classic war map and QUEST GUIDE client patch tools, teleporter stand-off, quest fixes (CLAUDE VERSION 0bcba1e), period data
c129b6d Changelog: summoned quest NPCs and quest NPCs that turn hostile (local, 0.4)
70e9f12 Changelog: classic frontier war map, working QUEST GUIDE button (local, 0.4)
2da0855 Changelog: bots stop beside teleporter NPCs (local, 0.4)
dcdf5ef Source update: 0.4 / 0.4b work in progress (CLAUDE VERSION ff3c104), period data, navmesh builder
ab95f03 Changelog: correct the classic quest count
e4d7bfc Changelog: Quest Guide button, red quest markers, 86 more classic quests
73a2e2e Changelog: siege armies as full groups, relic focus
b20d2da Changelog: bigger sieges, siege dashboard, border keep entry, bestiary spawns, classic quests
c32a8d2 Changelog: bot siege equipment, sieges end when the attackers are driven off, Caer Sidi Sacristan
b0f2c49 Changelog: keep door rams set up in the courtyard
e9dbae6 Changelog: bots set up rams at the keep door once the gate is broken
6984c73 Changelog: keep lord safe from bots and siege while the keep door stands; rams skip posterns
e3b0911 Changelog: raid bots leave wall archers to ranged bots, never moved onto keep walls
6d338bd Changelog: defense wave 80%/10 min, retake after a lost keep, lords safe from siege (local, 0.35)
bb453b1 Changelog: companions keep pets when travelling, enemy gamebot names hidden in death messages (local, 0.35)
a6fea0a Changelog: bot siege weapons, siege start on arrival, player keep defense, raid siege squads, levers, stealth, no guard/bot loot (local, 0.35)
059ae62 Changelog: final boss and battleground siege announcements, Options tab switches, Govannon health (local, 0.35)
0f4979a Changelog: siege armies march as a column, raids lead bosses home and switch fighters to the boss, Coruscating Mine thinned (local, 0.35)
926ebae Changelog: hidden enemy gamebot names, frontier commitment, battleground monsters and keeps, Howth/Connla monsters (local, 0.35)
2994829 Changelog: battlegrounds goal, teleporter option, muster wait, PvP stalemate, Midgard BG exit (local, 0.35)
baaad4b Changelog: town teleporters for gamebots are on by default
aa434f8 Changelog: town teleporters for gamebots, siege army strength and attendance, on-screen siege and raid notices
d60aac4 Changelog (local): route pulls, ranged pulls for all groups, raid boss calls (Summoner's Hall cleared), siege muster, memory churn
```
