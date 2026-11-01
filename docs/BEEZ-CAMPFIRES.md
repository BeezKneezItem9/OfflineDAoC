# Operation Campfire

## Research boundary

No numerical Eden campfire rule was independently verified in this workspace. Attempts to read
[Eden's public wiki](https://eden-daoc.net/wiki?title=Campfire) and public web search were denied
by the network proxy (HTTP 403), including the direct-site retry. The wiki URL was an attempted
research entry point, not evidence that a Campfire article exists. No Eden assets or code were used.

| Requested Eden detail | Evidence / confidence | Beez decision |
|---|---|---|
| Names, appearance, description, tier count | Unverified | One reusable Beez item; four level-scaled effects; stock model 3460 |
| Level brackets | Unverified | User-approved character-level scaling: 1–14 / 15–24 / 25–39 / 40+ |
| Drop rates and loot eligibility | Unverified | Not applicable to revised Beez design; no loot changes |
| Placement and consumption | Unverified | Player's position; consume nothing; successful placement starts a 10-minute cooldown |
| Deployed duration | Unverified | Configurable 600 seconds |
| Radius and pulse interval | Unverified | Configurable 350 units / 5 seconds |
| Regeneration strength and combat rules | Unverified | Native regeneration aids +5 health / +5 power before modifiers |
| Buff linger | User's explicit requirement | Exactly 60 seconds from each recipient's last accepted pulse |
| Group, realm, pets | Unverified for Eden | Same-realm players, GameBots and their controlled pet trees |
| Overlap | Unverified for Eden | Strongest tier wins; one regeneration contribution |
| Stack size / item restrictions | Unverified for Eden | One reusable nontradable item, no class/spec restriction |
| Deployer departing | Unverified for Eden | Fire stays at its original location until its lifetime ends |

These are Beez defaults, not claims about Eden. Matching an exact Eden implementation still
requires accessible authoritative documentation or an in-game reference supplied by the owner.

## Final specification

The owner approved a reusable item instead of consumable PvE drops. Existing loot generation and
all its probabilities remain completely unchanged.

| Character level at deployment | Tier | Melee bonus | Runtime spell ID |
|---|---|---|---|
| 1–14 | I | +15% | 59841 |
| 15–24 | II | +20% | 59842 |
| 25–39 | III | +25% | 59843 |
| 40+ | IV | +30% | 59844 |

The single item is **Beez's Campfire**, template `beez_campfire`, class
`DOL.GS.BeezCampfireItem`, package `BeezCampfire`, stock ITEM model 3460. It has max count 1,
weight 5, level 1 usability, neutral realm, `CanUseEvery=600`, and is not tradable or droppable.
There are no spell charges, concentration, class requirements or specialization requirements.
The deployed tier is snapshotted from the player's level; leveling later does not change an existing fire.

New human characters receive it with their Beez items. Existing players obtain it using **`/beezitems`**,
which retains the existing duplicate and saved-inventory checks. Bots do not receive developer items.
Friendly autonomous bots and companions can still benefit from player-deployed fires.

Use the item from the backpack/quickbar. Placement requires a living, stationary, noncasting,
non-CC'd, unmounted, out-of-combat player in a valid enabled zone, outside a house.
A successful world placement starts the **10-minute item cooldown** and never consumes the item.
A failed placement starts no cooldown. Cooldown uses the existing inventory persistence mechanism;
reconnecting does not reset a saved cooldown. The active-fire limit is keyed by character ID,
so reconnecting or using another copy does not move or duplicate a still-burning fire.
These placement restrictions are conservative Beez rules, not verified Eden rules.

The deployed object is a non-pickup `GameStaticItem`, never a pet, NPC replacement, movable actor,
or saved world spawn. It burns for 600 seconds, starts its first pulse on the next timer tick,
and refreshes qualifying recipients every 5 seconds within 350 units. It remains when its deployer
moves, zones, dies or disconnects. Expiration, explicit removal, script unload and server shutdown
remove its timer and world object. Fires are not restored after server restart.

Every recipient gets a separate 60,000 ms timed ECS effect. Leaving range stops refreshes but does
not cancel the effect. A pet is located and tested independently of its owner. The owner need not
be in range for its pet to benefit. Fire deletion does not cancel existing recipient effects.
Buffs are transient and are not saved across logout. Normal recipient death/effect cleanup still applies; a friendly zone transition does not change
an already-granted buff's deadline.

## Regeneration and existing Fonts

The existing `spells/Masterlevel/Perfecter.cs` implements FOH through `HealOverTime`, permits NPCs,
and uses a 350-unit radius. FOP uses `PowerOverTime`, a 350-unit radius, and does **not** apply to NPCs.
Both derive numerical amounts, duration and frequency from their installed spell rows; the handler
alone does not establish a universal Font amount. `MasterLevelBase.cs` defaults to excluding
in-combat recipients from Font application. These are repository facts, not Eden evidence.

Beez campfires deliberately use the existing natural-regeneration system instead of copying those
separate HoT/PoT clocks. The default +5 aid is a conservative support magnitude (the existing red
Buff Stone power-regeneration contribution is also +5), not an inferred historical Font value.
Both aid amounts are configurable and shared by all four tiers; only melee enhancement scales by tier.

For a level-50 real player, modifier 1, no debuffs or other aids:

| Recovery | Without fire, per tick | With fire, per tick | OOC nominal 60-second throughput |
|---|---:|---:|---:|
| Health | 30 | 40 | 600 → 800 |
| Power | 25 | 35 | 500 → 700 |
| Power with Buff Stone | 35 | 45 | 700 → 900 |

These throughput figures assume 20 three-second ticks, enough missing health/power, and no clipping.
Standing combat ticks remain seven seconds (seated combat: five), so eight ordinary standing-combat
power ticks give 200 → 280, or 280 → 360 with the stone. Actual first-tick alignment can differ.
Mana Roots continues to select the ordinary OOC power cadence in combat; it gains no special multiplier.

The native formula applies its 1.87 factor exactly once:

- Power: `max(1, int(2 * (2.5 + level*0.2 + net aids) * mana modifier))`.
- Health uses its existing level curve, disease/bleed restrictions, NPC behavior and health modifier.
- Campfire adds +5 to each native aid category once; it does not directly heal or restore power on a pulse.
- Other buffs, abilities, gear and debuffs keep their existing calculations. Fonts remain separate native
  HoT/PoT sources and may coexist; campfire does not reproduce their recovery through another timer.

Pet limitations follow existing NPC mechanics: ordinary NPC-backed pets have an unlimited/native
5000-power resource rather than a player-style consumable power pool. A power aid is present but
cannot create a meaningful recovery benefit in a pool the pet never spends. Native NPC OOC health
recovery can replace the aid-based amount with 12.5% of max health; in combat the native NPC health
halving still applies. These mechanics were not changed to inflate the apparent campfire benefit.

## Melee calculation and stacking

`ECS-Components/AttackComponent.cs` invokes `BeezCampfires.EnhanceMelee` after resistance, conversion,
base damage caps and style damage caps, immediately before final integer damage assignment.
It multiplies combined successful melee damage by 1.15 / 1.20 / 1.25 / 1.30, including the normal
melee critical calculation downstream. Style combat-log damage receives the same multiplier.

The hook rejects non-melee attack types. It does not grant Strength, weapon skill, generic spell
bonuses or a generic damage-stat bonus. `AttackData.BaseDamage` and `BaseDamageCap` remain unchanged,
so native damage adds/shields and procs do not inherit a larger damage snapshot. Ranged attacks,
spell hits and DoTs do not enter this multiplier. Integer rounding can make displayed low-damage
hits differ slightly from the exact percentage.

The appended `eEffect.Campfire` category is isolated from conventional buff categories. All four
ranks conflict with each other and native effect arbitration chooses the strongest active rank.
Equal-tier pulses replace/refresh one effect, subtracting and reapplying its native aids exactly once.
Weaker pulses cannot refresh or overwrite a stronger effect. The self-cast native arbitration path
rejects a weaker simultaneous rank rather than retaining it disabled: after a stronger rank expires,
a weaker fire takes effect on its next pulse. There is no additive or multiplicative campfire stacking.

Friendly eligibility resolves bounded ownership chains, including Bonedancer subpets, charmed world
NPCs, summoned pets, turrets and NPC-backed GameBots. Unowned friendly-looking scenery receives nothing.
Hostile realms, dead recipients and orphaned/cyclic ownership chains fail. A realm/ownership change
invalidates the melee benefit immediately; the effect's one-second validation pulse removes the aids.
The validation pulse is not a regeneration clock.

## Saved installations

At script load an add-only, idempotent registration creates the one missing `ItemTemplate` row.
It does not replace the database, change loot tables, edit existing rows, or touch accounts,
characters, progression or existing inventory. `/beezitems` then grants the item through the
established inventory path, without duplicating an already-held or saved copy.

A colliding item ID with another package/class is refused without overwriting it. Runtime spell ID
collisions are checked at initialization; the four buff spells themselves are runtime-only and need
no `Spell`/`LineXSpell` rows. `CanUseEvery` and saved `Inventory.Cooldown` use existing columns;
there is no new schema or saved-world replacement.

The normal server-property loader supplies these additional saved properties without overwriting
existing values:

| Property (category `beez_campfire`) | Default | Effective limits |
|---|---:|---|
| `beez_campfire_lifetime_seconds` | 600 | 1–3600 seconds |
| `beez_campfire_radius` | 350 | 1–2000 units |
| `beez_campfire_pulse_seconds` | 5 | 1–30 seconds |
| `beez_campfire_health_aid` | 5 | 0–100 native aid units |
| `beez_campfire_power_aid` | 5 | 0–100 native aid units |

No schema migration, client patch, new assets or world download is required. Stock model 3460 is
identified as a campfire by `gameobjects/Bonedancer/CommanderPet.cs` (the shield-model correction).
This source evidence does not constitute client visual verification. Icon 7245 is the existing FOH
icon; no new particle effects are emitted. Custom tooltip names and values are sent by the server;
stock icon artwork and exact model animation depend on the installed client.

## Validation and Windows acceptance

Automated results are recorded below after verification. Tests execute the Release GameServer assembly,
native ECS effect lifecycle, native regeneration calculators/timers, real item use and saved cooldowns,
real region/zone placement and spatial queries, and temporary SQLite migration. They do not launch
CoreServer, connect a Windows client, or test the user's retained world/client installation.

Windows checks before considering a release ready for gameplay:

1. Run `/beezitems` on an existing character and verify one campfire is granted. Repeat the command;
   no duplicate should appear. New human characters should start with it; bots should not.
2. Use it at a safe stationary location. Confirm no item is consumed, a visible stationary fire appears,
   and the next use is blocked for 10 minutes. Failed/combat/duplicate placement starts no new cooldown.
   Inspect the stock model and tooltip from multiple camera angles.
3. With a player and pet near it, move each outside the radius independently; confirm 60-second
   persistence from its last pulse and refresh on returning. Zone/disconnect the deployer: fire stays.
   Reconnect: cooldown and active-fire limit should prevent a second placement.
4. Check characters on either side of levels 15, 25 and 40. Verify tiers and bonuses. Overlap Tier I
   and IV from two players; verify only +30%, then allow IV's buff to expire and verify Tier I resumes
   on a subsequent pulse. Confirm no repeated regeneration increase over many pulses.
5. Exercise Sorcerer control, Cabalist, Spiritmaster, Bonedancer commander/subpets, Animist and Sluaghbinder
   bodies. Confirm enemies and ordinary world NPCs receive nothing.
6. Compare real melee/styles with and without each tier; confirm spell/DoT/proc damage remains unchanged.
   Test native health/power recovery, Buff Stone, Mana Roots, disease/debuffs and combat transitions.
7. Let the fire expire: object disappears, previously granted buffs run down normally. Restart cleanly;
   no saved fires should return, and characters, inventory, configuration and world remain intact.

## Recorded automated results

- Release server and test projects built successfully with .NET SDK 10.0.403; existing repository
  compiler/dependency warnings remain. No dependency versions were changed.
- Focused command: `dotnet test source/server/Tests/Tests.csproj -c Release --filter 'FullyQualifiedName~Campfire|FullyQualifiedName~UT_BeezOnline'`.
  **97 passed, zero failed**: 51 campfire gameplay cases, three isolated SQLite registration/persistence
  cases, and 43 existing Beez feature regressions. All 54 new campfire cases ran.
- Full command: `dotnet test source/server/Tests/Tests.csproj -c Release --no-build --no-restore`.
  **2,994 passed, zero failed**. The TRX contains 61 additional `NotExecuted` entries for explicit
  installed-world/navmesh/manual diagnostic probes. The console's final summary excludes these;
  they are not represented here as passing tests. Total entries in the TRX: 3,055.
- Real production paths exercised include all eight level-boundary item deployments, native region/
  subzone queries, independent player/pet range changes, item cooldown assignment and SQLite reload,
  native melee calculation through actual target health loss (unstyled and styled at all four tiers),
  timed effect replacement/expiration, regeneration with Buff Stone and Mana Roots, pet ownership and
  realm changes, and server/script cleanup. Tests use temporary actors/databases, never a played world.
- Windows client visuals, UI presentation, live class-specific pet behavior and installed-world
  compatibility still require the acceptance checks above. No Windows release was published or deployed.
