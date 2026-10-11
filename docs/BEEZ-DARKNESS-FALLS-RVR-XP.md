# Darkness Falls and enemy-realm character XP

Investigated against `d583ee32832a108cc030e6bb4d4f776052de6a00` on
`beez-online-six-features`. This change does not publish a release, deploy
binaries, start a server, or replace an installed database/world catalog.

## Findings: Darkness Falls PvE

Darkness Falls (region 249) **already receives dungeon camp bonuses**. It is
hardcoded as both a dungeon and an RvR location in `world/Zone.cs` and
`world/Region.cs`; the catalog's `IsFrontier=False` does not undo that RvR
classification.

The relevant reward pipeline is:

1. `GameNPC.ProcessDeath` calls `AbstractServerRules.OnNpcKilled` before clearing
   `XPGainers`. Reward eligibility rejects invalid/previously rewarded NPCs.
2. `ProcessXpGainers` resolves owners and groups. `AwardPlayerOnNpcKill` uses the
   level-indexed `GameLiving.XPForLiving` table through
   `AbstractServerRules.GetExperienceForLiving`; ordinary NPCs have no generic
   additional armor/health/difficulty XP multiplier. Script overrides and
   `ExceedXPCapAmount` can change individual NPC rewards.
3. Group challenge/con rules and equal-level distribution apply. Gray group
   encounters yield zero. Otherwise, equal-level shares use ceiling division.
4. The base is capped at the recipient's same-level NPC value times
   `XP_Cap_Percent / 100` times the NPC's cap factor. Damage contribution is
   applied **after** that cap, preventing low-level tagging from bypassing it.
5. Camp bonuses are added to that capped base: outside maximum 0.55, dungeon
   maximum 0.66, scaled by the camp's remaining value. Long-idle spawns reset
   toward full camp; repeated kills deplete camp. Group bonus is
   `(members - 1) * 0.125 * base`; existing guild, BAF and keep bonuses follow.
6. `GamePlayer.GainExperience` applies location/global rates and item XP bonuses
   to the base, while retaining the separate camp/group/other amounts. Zone XP
   is a separate additive grant with integer truncation. Character XP opt-out,
   stage thresholds, training requirements and level transitions remain native.

**Confirmed rate discrepancy:** before this change, DF's RvR classification
selected `rvr_zones_xp_rate` instead of `xp_rate` for its PvE base. With a boosted
ordinary PvE rate and a default RvR rate, equal mobs can therefore give much less
XP in DF. This is configuration-dependent; it is not a demonstrated universal
penalty at default equal rates.

**Verified source/data difference:** the source `scripts/dbupdater/insert/Zones.xml`
sets DF zone Experience to 0. The read-only public 0.35b SQLite catalog inspected
here has DF Experience **75**, Barrows **25**, and Camelot Hills **0**. That public
DB has `enable_zone_bonuses=False`, `xp_rate=1`, `rvr_zones_xp_rate=1`, cap values
125, and camp limits .55/.66. Thus its stored 75% is inactive. It does not prove
the user's retained Windows world has those values. The public DB was opened
read-only; SHA-256:
`0fff1a26913430a9c8f258484a1e2bae69102354c5e287d7d505d200dd3fdfe6`.

There are 2,321 ordinary `DOL.GS.GameNPC` rows in its DF population, alongside
bosses, guards and merchants. Templates may replace mob levels/attributes.
Some scripted boss **adds**, such as LegionAdd and Baln/Beliathan minions,
explicitly have zero ExperienceValue; those intentional exclusions are retained.
No evidence supports rewriting every DF mob/template or replacing installed data.

### Correction and controlled numbers

For NPC XP in DF only, use `max(xp_rate, rvr_zones_xp_rate)` for the player base
and zone bonus. Add a configurable **20% minimum zone bonus**, independently of
the global zone-bonus toggle. When ordinary zone bonuses are enabled, keep the
higher installed DF bonus instead of adding the floor on top. This is a Beez
progression policy, not a claimed exact historical DF rule. It rewards danger
without changing other zones, con scaling, group sharing or camp depletion.

Let `B` be the native capped/contribution-adjusted base, `C` all native separate
camp/group/guild/BAF/keep bonuses, `R` the chosen rate, `I` the item XP percentage,
and `Z` the higher of the enabled installed zone bonus and DF floor:

```
base = truncate(B * R)
base += truncate(base * I / 100)
zone = truncate(truncate(B * Z / 100) * R)
DF player NPC XP = base + C + zone
```

Zone bonus retains the native separate-grant behavior and does not multiply the
camp bonus or item bonus. Existing per-kill caps remain base caps, as before.
Autonomous bot PvE retains its independent `bot_xp_rate`; DF removes a below-1
RvR location penalty and applies the same floor without adopting player `xp_rate`.
Temporary companion progression is unchanged.

These are deterministic calculations/native reward tests, **not invented live
observations**. Player level 30; ordinary NPC; full camp; no items, guild, BAF,
keep bonus or competing damage. All zone bonuses disabled/zero for this table;
DF's new independent floor is 20%. Group rows are XP **per member**, two
same-level members doing all damage.

| Location / encounter | Before XP | After XP |
|---|---:|---:|
| Open world, level-30 mob, solo, rate 1 | 2,559,676 | 2,559,676 |
| Standard dungeon, level-30 mob, solo, rate 1 | 2,741,330 | 2,741,330 |
| DF, level-30 mob, solo, rate 1 | 2,741,330 | 3,071,610 |
| DF, level-33 mob, solo, rate 1 | 3,426,663 | 3,839,514 |
| Standard dungeon, level-30 mob, two-member group | 1,473,877 | 1,473,877 |
| DF, level-30 mob, two-member group | 1,473,877 | 1,639,017 |
| Open world, level-30 mob, solo, PvE rate 10 | 17,422,312 | 17,422,312 |
| Standard dungeon, level-30 mob, solo, PvE rate 10 | 17,603,966 | 17,603,966 |
| DF, level-30 mob, solo, PvE rate 10 / RvR rate 1 | 2,741,330 | 20,906,766 |

For an enabled installed DF bonus of 75%, the same rate-1 solo kill gives
**3,979,883** XP. The floor does not make that 95%.
Native base at level 30 is 1,651,404; level-33 solo base is capped at 2,064,255.
The test includes the actual native NPC reward method and actual
`GamePlayer.GainExperience`/character-record changes, not only this written formula.

## Findings: enemy-player XP in every zone

This investigation is separate from DF PvE. Enemy-kill XP has no DF-only gate.

**Confirmed autonomous-victim defect:** `OnNpcKilled` routes persistent
`GameBot` victims to `AutonomousBotRealmPointRewards.Award` and returns before
ordinary NPC XP distribution. That reward path paid RP but did not grant
character XP. This explains zero character XP from eligible autonomous enemy
bots in every zone. `/spawn` companions, controlled pets, and ordinary NPCs are
not autonomous player victims.

**Real-player distinction:** the baseline already had `RewardExperience` in
`AwardPlayerOnPlayerKill`, including `GainExperience(eXPSource.Player, amount)`.
In controlled cases it was not merely calculating and discarding XP. `GamePlayer.Die` calls
`OnPlayerKilled` before recording the current death's `DeathTime`.
`GainExperience` then writes `DbCoreCharacter.Experience`, used by normal
character persistence. The reported blanket zero for actual human victims is
**not reproduced or fully explained** by the controlled binary tests; do not describe the
bot bypass as a proven human-victim defect. The user confirmed the reported killers are below level 50 with XP enabled,
so cap/opt-out must not be assumed to explain that report. Native hardcore-group
restrictions (members more than five levels higher), range/contribution and the
victim's recent-death worthiness remain relevant. In particular, level-50 killers do not get further character leveling
XP under the new explicitly capped policy.

### Shared reward path and protections

`gameutils/RvrExperienceRewards.cs` is called from both player and eligible-bot
reward entry points. It snapshots authoritative damage under `XpGainersLock`,
resolves pet/companion damage to the root owner, and includes nearby enrolled
zero-damage support members in group sharing. The existing damage intake path
already enrolls such members. Nonparticipant/guard damage remains in the total,
so tagging does not earn full reward. Nonfinite damage is ignored.

For each eligible recipient:

```
victim value = 4 * native same-level NPC XP(victim level)
recipient cap = 4 * native same-level NPC XP(recipient level) * XP_PVP_Cap_Percent / 100
share = truncate(min(floor(victim value / eligible group members), cap)
                 * group damage / all nonnegative finite damage)
```

The four-times victim value preserves existing real-player XP valuation;
autonomous victims now use that same valuation. Solo contribution uses the same
formula with one member. The cap applies before damage fraction. Human recipients
retain native outpost XP bonuses on their adjusted share. There is no extra
PvE/RvR location, item, camp or group-multiplier amplification on PvP XP.
Native character gain/progression and autonomous XP/state-dirty persistence
paths apply the result. Existing RP, BP and money calculations are retained.
In particular, autonomous victims previously awarded no BP and still award none;
this change does not silently add or remove BP rewards.

Reject friendly/neutral victims, nonautonomous/helper NPC victims, duel deaths,
inactive/dead/out-of-range recipients, gray targets, zero contribution, same
human-account kills, XP opt-out, and maximum-level recipients. Native
`rp_worth_seconds` applies to recent human deaths and bot RP death timestamps.
An XP death stamp also prevents duplicate/reentrant reward calls.

A separate rolling limit permits **3 XP-rewarded kills per recipient/victim
identity per 3,600 seconds**. It uses stable character ObjectId / bot DatabaseID,
so recreating a bot object or relogging a character within the running server
cannot evade that pair quota. This limit affects XP only, preserving RP/BP rules.
It does not grant extra XP for the final blow or pay the old player XP path again.
The history is server memory and resets on server restart; it is not a new
persistent schema or a cross-server anti-farming ledger.

### Numerical enemy-kill comparisons

Level-30 killer/victim, no keep/item/location bonus, all damage eligible, rates
1, recent-death cooldown clear. Values before are baseline **code rewards**; the solo human and bot values
were also measured against the published release binary. These are not claimed
to reproduce the user's installed-world state. After values are tested
through death reward entry points into actual character records.

| Encounter | Before character XP | After character XP |
|---|---:|---:|
| Solo human enemy victim | 6,605,616 verified release-binary reward | 6,605,616 |
| Solo autonomous enemy victim | 0 | 6,605,616 |
| Two-member group, human enemy victim, each member | 3,302,808 nominal native reward | 3,302,808 |
| Two-member group, autonomous enemy victim, each member | 0 | 3,302,808 |
| Solo level-33 autonomous victim, level-30 killer | 0 | 8,257,020 (cap) |
| Solo autonomous victim; killer contributes 25%, guard 75% | 0 | 1,651,404 |
| Friendly, gray, helper, same-account, duel or invalid kill | No legitimate XP entitlement | 0 |
| Fourth rewarded kill of same identity pair in rolling hour | No rolling XP quota | 0 |
| Level-50 recipient | No further character level possible | 0 |

Actual-record tests exercise regions 1, 20, 249 and 163 for **both** human and
bot victims, including RP=100 and human BP=19 versus bot BP=0 in controlled solo
kills. Autonomous recipient tests call the real `GameBot.GainExperience` and
verify increased Experience and dirty progression state.

## Configuration, installed data and acceptance

No schema migration, world replacement, character reset or new runtime dependency
is required. Existing saved property values are preserved by the native property
loader; missing keys are registered with defaults at the next authorized startup:

| Property | Default | Meaning |
|---|---:|---|
| `darkness_falls_xp_bonus_percent` | 20 | Independent DF NPC zone-bonus floor; 0 disables floor; clamp 0–1000 |
| `rvr_xp_repeat_window_seconds` | 3600 | Rolling recipient/victim XP window; minimum effective 1 second |
| `rvr_xp_repeat_max_kills` | 3 | Maximum XP-rewarded kills per pair; minimum effective 1 |

Restoring DF's ordinary PvE rate does not change saved `xp_rate` or
`rvr_zones_xp_rate`, nor rates for any other region. Setting the floor to zero
disables that added bonus but retains rate parity. An enabled unusually high
bonus in another zone can still outpay the default DF floor; the new property
can be tuned after comparing actual installed values.

On an offline copy of the retained installation, these **read-only** queries
help distinguish catalog differences and character state:

```sql
SELECT Key, Value FROM ServerProperty
WHERE lower(Key) IN ('xp_rate','rvr_zones_xp_rate','bot_xp_rate',
 'enable_zone_bonuses','xp_cap_percent','xp_pvp_cap_percent','rp_worth_seconds',
 'darkness_falls_xp_bonus_percent','rvr_xp_repeat_window_seconds','rvr_xp_repeat_max_kills');
SELECT ZoneID, RegionID, Name, Experience FROM Zones WHERE RegionID IN (1,20,249);
SELECT Name, Level, Realm, Experience, GainXP, HCFlag, DeathTime, PlayedTime
FROM DOLCharacters WHERE Name = '<test character>';
SELECT Name, Region, Level, ClassType, NPCTemplateID FROM Mob
WHERE Region = 249 AND Name = '<reported monster>';
```

Do not publish character/account rows or played SQLite data. Check templates with
ReplaceMobValues before equating a stored Mob.Level to actual spawned level.
No installed Windows database was accessed during this work.

Recommended in-game checks after a separately approved build/deployment: use a
below-50 XP-enabled character; compare actual XP counters before/after equal
ordinary NPCs with comparable camp age, then an autonomous enemy and a separate
human enemy; repeat with two nearby group members (one doing no damage). Verify
XP opt-out, level-50 cap, gray kills, recent-death exclusion and fourth same-pair
kill suppression. Confirm RP/BP remain correct. Keep DF and enemy-kill measurements
separate. Existing Mana Roots, Bind Stone, Buff Stone and other custom mechanics
are outside this change.

## Validation

Release GameServer compilation succeeded. The final available-workspace full
suite passed **2,936 tests**, with **61 pre-existing ignored/NotExecuted tests**.
The console summary says “Skipped: 0”; the TRX contains those 61 ignored rows,
so they are explicitly included in this report rather than described as passing.
There are **56 new XP cases**. The 41 pre-existing, uncommitted Animist diagnostic
cases are left outside this commit; the committed baseline was 2,839 passes.
The final committed-scope suite passed **2,895 tests**, plus the same 61 ignored
cases. The final focused XP/RP/BP/rate suite passed **78 tests**. Counts match
2,839 committed baseline cases + 56 new XP cases; adding the 41 earlier
uncommitted diagnostics produces the 2,936 available-workspace pass count.

One earlier committed-scope run had an unrelated intermittent failure in
`UT_BotCombatRefinement.MillionHandoffDecisionsAllocateNothing`: 808 bytes versus
expected zero. It passed in isolation and on the unchanged full-suite retry.
The bot movement implementation/test was not modified to conceal that failure.
Existing compile/analyzer and package advisory warnings remain; no dependency
changes are part of this task.

An additional read-only console probe referenced the **existing published
Windows release's managed DLL**, with an in-memory database/packet test adapter;
it did not launch a server. The DLL SHA-256 was verified against the published
ZIP payload: `cf73de9d800487acf30d04293fddac570f58811e612e677bba29eeef73ba1145`.
Across 24 controlled cases (levels 10, 30, 49; regions 1, 20, 249, 163;
human versus autonomous victim), actual real-player XP increased by 20,480,
6,605,616 or 146,054,148 respectively. Autonomous victims yielded **0** in all
12 baseline cases. This verifies the bot omission in the deployed release and
shows that its real-player award can actually work; the remaining installation
report must not be mislabeled as a proven global real-player formula defect.

Automated tests use isolated in-memory character records and mocked packet/DB
adapters. Actual record XP gain is asserted; physical saves to a played SQLite
database and Windows in-game execution are not claimed.


## Source references

| Stage | Source |
|---|---|
| NPC level XP table and value | [GameLiving.cs](../source/server/GameServer/gameobjects/GameLiving.cs#L483) |
| NPC death and clearing credit | [GameNPC.cs](../source/server/GameServer/gameobjects/GameNPC.cs#L2953) |
| NPC routing / bot bypass | [AbstractServerRules.cs](../source/server/GameServer/serverrules/AbstractServerRules.cs#L1032) |
| NPC cap, group, camp and distribution | [AbstractServerRules.cs](../source/server/GameServer/serverrules/AbstractServerRules.cs#L1345) |
| Player death entry point | [GamePlayer.cs](../source/server/GameServer/gameobjects/GamePlayer.cs#L6081) |
| Player reward entry point | [AbstractServerRules.cs](../source/server/GameServer/serverrules/AbstractServerRules.cs#L1909) |
| Actual human XP gain and hardcore gate | [GamePlayer.cs](../source/server/GameServer/gameobjects/GamePlayer.cs#L4336) |
| Actual bot progression/persistence queue | [GameBot.cs](../source/server/GameServer/bots/GameBot.cs#L1588) |
| Bot realm reward entry point | [AutonomousBotRealmPointRewards.cs](../source/server/GameServer/bots/autonomous/AutonomousBotRealmPointRewards.cs#L75) |
| DF location policy | [BeezExperiencePolicy.cs](../source/server/GameServer/gameutils/BeezExperiencePolicy.cs) |
| Shared XP calculation, eligibility, anti-farming and application | [RvrExperienceRewards.cs](../source/server/GameServer/gameutils/RvrExperienceRewards.cs) |
| Focused/end-to-end regression fixture | [UT_BeezExperience.cs](../source/server/Tests/UnitTests/UT_BeezExperience.cs) |

Historical group/challenge, 1.49 dungeon camp and 1.54 outpost explanations are
inherited references in `AbstractServerRules.cs`, including
`http://www.camelotherald.com/more/110.shtml`,
`http://news-daoc.goa.com/view_patchnote_archive.php?id_article=2478`, and
`http://www.camelotherald.com/more/567.shtml`. Their live availability was not
verified here; they are not independent evidence for the new DF floor or repeat
quota. Those two rules are explicitly configurable Beez policy.
