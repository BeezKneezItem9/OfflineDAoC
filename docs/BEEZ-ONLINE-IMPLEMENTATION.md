# Beez Online — six-feature implementation review

Status: implemented in the working tree; deployment and playable-server startup are awaiting approval. No played database, client binary, bot roster, or live installation was modified. No live validation was performed. Animist work and historical RP research are excluded.

## Feature changes and boundaries

### 1. Autonomous enemy RP and normal human RR progression

Eligible autonomous, non-temporary enemy victims in RvR regions/zones use the shared player RP arithmetic: victim value, contribution fraction, participant split, recipient cap, rank adjustment, and group bonus. Pets resolve to their reward owner. Nearby autonomous contributors count toward a mixed group's split but receive no RP or RR progression. The normal human `GainRealmPoints` path retains rate, progression, and battleground policies. Ordinary human-victim repeat-death eligibility remains unchanged.

For a positive normal share B, recovery is `min(B, max(1, floor(B * clamp(elapsed / interval, 0, 1))))`. The existing `rates/rp_worth_seconds` setting supplies the interval, default 300 seconds. An unseen victim pays the full normal share. Every autonomous death updates victim-wide state, even when nobody qualifies for payout. State uses persistent BotId, survives bot-object reconstruction, and resets with the server process. Expired identities are pruned during activity without evicting recovering victims or imposing a capacity-dependent reward exception. No RP history claim is made for this approved custom rule.

### 2. Viewer-relative classic enemy identity

Hostile autonomous gamebots show their translated race/gender name and no personal guild label in all three NPC-create serializers. Friendly names remain intact, and stored bot identities remain intact. Examine, attacking/defending/pet combat, observer messages, spell messages, death messages, and loot text use the recipient's relation to the bot. Loot creator metadata defensively uses a generic realm-adventurer label for autonomous victims. Staff and PvE realm exceptions still follow existing server rules.

NPC inheritance and packet classification remain unchanged. Existing realm/hostility flags are preserved. Automated name-policy tests do **not** establish the client's exact red-name shade, target-window presentation, or all incidental UI surfaces.

### 3. Beez's Developer Ring

A reusable, non-tradable ring provides an extended server-side equipment bonus vector: eight stats at +250 each, nine resists at +100 each, hits +500, flat power +100, and all skills +100. These oversized raw inputs feed existing item calculators; no stat/resist/skill/hits/power caps, cap-increase properties, ToA bonuses, weapon DPS, armor, or AF caps were changed. The ring's custom delve lists its bonus vector.

Equip, unequip, and inventory refresh apply/remove exactly the ring's contribution. Other equipment remains present and legal caps still apply. New real characters receive the ring and Buff Stone after starter-equipment creation. Existing players can use `/beezitems`, which checks inventory and saved owned items before granting. Bot clients are excluded from new-character grants.

### 4. Beez's Buff Stone

The exact verified manifests contain 18 Albion, 17 Midgard, and 16 Hibernia entries. Their source IDs, native lines, levels, handlers, groups, icons, and values are preserved; the stone clones spell objects without changing spell records. Missing/excluded entries or unresolved handlers reject the package before application. Celerity, combat recovery, bladeturn/PBT, songs/chants, self/pet-only spells, RA/ML/champion spells, unsupported subspells, and the previously excluded categories are absent.

A stone-only application context tags effects as session effects. They have no expiry/maintenance pulse, no concentration reservation/list entry, and return no saved-effect record. Normal zoning does not cancel them. Death and disconnect invalidate pending applications and clear active or disabled stone effects. Release follows death cleanup. No NPC casts these effects.

Application targets only the item's real-player user. A strength/compatibility guard precedes the existing same-ID refresh shortcut and preserves stronger or equal legitimate effects. Missing effects are restored; weaker eligible effects use normal replacement/coexistence rules. This guard and lifetime override apply only to stone-origin effects. Normal spell casting and ordinary refresh/stacking remain unchanged.

The selected qualifying stat/AF/damage-add spells use the approved 1.25 specialist-spec factor; other selected effects use 1.0. Recipient buff-effectiveness gear does not become a donor bonus. Normal effect/stat caps still apply. Tests cover every verified entry and handler's session metadata, plus stronger same-ID preservation, upgrades, repeated use, target isolation, concentration exemption, expiry, disabled-effect cleanup, and saved-effect exclusion.

### 5. Simultaneous songs/chants

The exception covers helpful, non-focus group pulses in these native class lines:

| Class | Lines |
| --- | --- |
| Paladin | Chants |
| Minstrel | Instruments |
| Skald | Battlesongs |
| Bard | Bard Music Spec; Bard Nurture Spec; Regrowth Bard Spec |
| Warden | Nurture Warden Spec |

Hostile charm/mez, self/pet pulses, focus spells, unrelated lines/classes, and other pulse types retain ordinary behavior. Eligible families coexist, use an independent source registry, and pay no continuing pulse-power or concentration-list cost. Activation mana, reuse, learned ranks, native range, child-effect conflicts, caps, and crowd-control pulse suspension remain in place. Instruments are still required for activation; eligible songs continue after switching to melee.

Humans, companions, and autonomous bots use the same scoped policy. Bot maintenance starts one best learned rank per family at a bounded cadence, prioritizes travel speed outside combat, equips actual instruments, preserves buff-batch/resurrection safeguards, and no longer twists or stops eligible sources during ordinary upkeep. Other sources retain existing cancellation and upkeep behavior.

### 6. Two-way Bind Stone

Primary use retains the normal recall handler. Secondary `/use2` on an owned personal-bind recall item snapshots the expedition position and bind point, recalls through normal movement APIs, and creates two owner-only temporary portal NPCs after confirmed arrival. Arrival allows normal heading and small position updates; client loading gets a bounded 60-second wait. Portals use the existing stock teleport-effect model (`0x783`), do not move, have a ten-minute lifetime, and have no database mob records.

Creation and every traversal check ownership, alive/active state, combat, movement, CC, casting, mounts, relics, valid endpoints, disabled/restricted regions, RvR regions/zones, battlegrounds, instances, jail, keep areas, and normal zoning rules. House interiors are rejected because the endpoint snapshot has no house-instance identity. Existing item reuse is respected. Death, disconnect, bind changes, replacement, failed arrival/world insertion, and expiry dispose the pair. Server restart drops the runtime state. Companion travel continues through the existing normal movement coordinator; portals themselves accept only their owner.

## Exact materially changed files/classes

Paths below are relative to the repository root. Shared hooks intentionally appear once.

| File | Class / responsibility |
| --- | --- |
| `source/server/GameServer/gameutils/BeezRealmRewards.cs` | BeezRealmRewards: shared arithmetic and victim-wide recovery cache |
| `source/server/GameServer/bots/autonomous/AutonomousBotRealmPointRewards.cs` | AutonomousBotRealmPointRewards: eligibility/contributions/human awards |
| `source/server/GameServer/bots/GameBot.cs` | GameBot: death recording and enemy examine |
| `source/server/GameServer/serverrules/AbstractServerRules.cs` | AbstractServerRules: shared player arithmetic and loot presentation |
| `source/server/GameServer/gameutils/BeezEnemyIdentity.cs` | BeezEnemyIdentity: viewer-relative names and messages |
| `source/server/GameServer/packets/Server/PacketLib168.cs` | PacketLib168: NPC-create name/guild |
| `source/server/GameServer/packets/Server/PacketLib171.cs` | PacketLib171: NPC-create name/guild |
| `source/server/GameServer/packets/Server/PacketLib1124.cs` | PacketLib1124: NPC-create name/guild |
| `source/server/GameServer/ECS-Components/AttackComponent.cs` | AttackComponent: combat/observer presentation |
| `source/server/GameServer/gameobjects/GameLiving.cs` | GameLiving: pet combat presentation and song-source registry |
| `source/server/GameServer/gameobjects/GameNPC.cs` | GameNPC: viewer-relative deaths |
| `source/server/GameServer/ECS-Effects/ECSGameEffect.cs` | ECSGameEffect: viewer-relative effect messages |
| `source/server/GameServer/spells/DamageAddAndShield.cs` | DamageAddSpellHandler / DamageShieldSpellHandler: combat names |
| `source/server/GameServer/gameutils/BeezDeveloperItems.cs` | BeezDeveloperItems, BeezDeveloperRing, BeezBuffStone: templates/grants/item behavior |
| `source/server/GameServer/commands/playercommands/beezitems.cs` | BeezItemsCommandHandler: self grant |
| `source/server/GameServer/packets/Client/168/CharacterCreateRequestHandler.cs` | CharacterCreateRequestHandler: grant after starter handlers |
| `source/server/GameServer/gameobjects/GamePlayer.cs` | GamePlayer: item bonuses, lifecycle cleanup, item-use dispatch, weapon switch |
| `source/server/GameServer/gameutils/BeezBuffs.cs` | BeezBuffs: verified manifests and stone-only application context |
| `source/server/GameServer/spells/SpellHandler.cs` | SpellHandler: stone context, concentration/song scope, combat names |
| `source/server/GameServer/spells/SingleStatBuff.cs` | SingleStatBuff: stone-only effectiveness |
| `source/server/GameServer/ECS-Effects/ECSGameSpellEffect.cs` | ECSGameSpellEffect: session lifetime, save exclusion, concentration policy |
| `source/server/GameServer/ECS-Components/EffectListComponent.cs` | EffectListComponent: stronger-buff guard and scoped pulse coexistence |
| `source/server/GameServer/ECS-Services/EffectService.cs` | EffectService: stone expiry exemption and scoped source upkeep |
| `source/server/GameServer/gameutils/BeezSongs.cs` | BeezSongs: class/line/family policy and bot maintenance |
| `source/server/GameServer/ECS-Effects/ECSPulseEffect.cs` | ECSPulseEffect: scoped source registration/removal |
| `source/server/GameServer/bots/BotBrain.cs` | BotBrain: concurrent maintenance replaces twisting |
| `source/server/GameServer/bots/BotSpellPower.cs` | BotSpellPower: scoped upkeep cost |
| `source/server/GameServer/gameutils/BeezBindPortals.cs` | BeezBindPortals / Pair / Portal: session portal lifecycle and safeguards |
| `source/server/Tests/UnitTests/UT_BeezOnline.cs` | UT_BeezOnline: 51 targeted cases across six features |
| `source/server/Tests/Fixtures/BeezBuffSpells.json` | 51 verified spell/line metadata entries; no database or save data |
| `source/server/Tests/Tests.csproj` | Embeds the spell metadata fixture |
| `source/server/Tests/UnitTests/UT_BotMobileSongs.cs` | Updates native-line fixtures and old twisting expectations; preserves movement/melee/reuse checks |
| `source/server/Tests/UnitTests/UT_RvrExpansion.cs` | Supplies normal viewer/brain context for the enemy examine regression |

## Database/configuration additions

No schema migration or new server-property setting is required. On a later approved startup, `BeezDeveloperItems.Load` creates missing `ItemTemplate` records with IDs `beez_developer_ring` and `beez_buff_stone` and custom class types `DOL.GS.BeezDeveloperRing` and `DOL.GS.BeezBuffStone`. Existing matching IDs are left intact and should be checked for the intended class types before gameplay. Character creation and `/beezitems` create ordinary owned `Inventory` records. The bonus vector itself is implemented in code because it exceeds the ordinary template's bonus-field count.

The existing bind item/primary spell is identified by its `GatewayPersonalBind` handler; no secondary spell record or item-template rewrite was added. RP uses the existing `rp_worth_seconds` setting. Buffs, recovery history, song-source registry, and portal NPCs require no new saved records. Buff Stone effects never enter `PlayerXEffect` storage.

The supplied spell-only database was opened read-only. Its SHA-256 remains `54a92c0691e7d778e1a344890325cd02ed7d2e99767ee3bb676339b9df316f6b`. Only selected world-spell metadata was copied into the test fixture; the SQLite database is not part of the repository changes.

## Automated/build validation

- Release solution build: **passed, 0 errors, 637 warnings**. Warnings include existing obsolete-code, analyzer, and NuGet advisory messages; dependency upgrades were outside this scope.
- Targeted feature and nearby regression selection: **308 passed, 0 failed**.
- Final full server test suite: **2,641 executed/passed, 0 failed; 58 not executed**. The TRX contains 2,699 outcomes; the console's `Skipped: 0` summary omits the 58 `NotExecuted` installed-data/navmesh probe outcomes.
- The new six-feature fixture contains **51 passing cases**, including all 51 verified buff entries in its catalog/handler test.
- Whitespace review uses `cr-at-eol` to respect the repository's CRLF convention.

Commands:

```bash
dotnet build "source/server/Dawn of Light.sln" -c Release -p:EnableWindowsTargeting=true
dotnet test source/server/Tests/Tests.csproj -c Release --no-build --logger 'trx;LogFileName=beez-final.trx'
```

The full-run result artifact is `source/server/Tests/TestResults/beez-final.trx` (ignored by git). Earlier failures were corrected: isolated fixture initialization, native song-line fixtures, obsolete twisting expectations, and bot cast dispatch/instrument maintenance. No unresolved automated test failure remains. Installed-data probes, client presentation, and actual in-game behavior are not established by these results.

## Implementation refinements / deviations

The six-feature scope and exclusions are unchanged. Creation grants run after starter handlers to avoid slot-order collisions. Recovery state is pruned by the active time window rather than imposing a hard ID capacity that could change first-kill rewards. Portal arrival uses a small positional tolerance rather than exact heading equality; house interiors are rejected rather than storing unsafe house-local coordinates. Portals reuse the stock teleport-effect model and existing movement APIs. The secondary bind action is dispatched server-side without adding a guessed secondary spell record. These choices keep the implementation reviewable and avoid changing world spell data or the client.

## Remaining manual acceptance tests and risks

Use a separately approved test install/copy database. None of these checks has been performed here.

| Feature | Required in-game checks |
| --- | --- |
| RP/RR | Known native-equivalent first reward; immediate and 75/150/300-second repeat kills; another attacker killing the same victim; deaths without human payout; unload/reload; pets/companions; mixed/solo groups and range; normal human RR/RA/save/relog progression; no bot RR gains; RvR/BG caps; no ordinary NPC/friendly rewards |
| Identity | Normal player viewers from all realms; allied and enemy views simultaneously; race/gender text, guild suppression, target/examine/combat/spell/death/loot surfaces; all supported packet/client versions; exact hostile red-name shade; staff exceptions and neutral/temporary companions |
| Ring | New-human grant after all starters; existing-player `/beezitems`; full backpack and saved/vault ownership; equip/remove/relog/refresh; all stat/resist/skill/hits/power caps; other ROG bonuses; tooltip/delve/stat-window presentation; no damage/armor cap bypass or bot grants |
| Buff Stone | Each realm/class package, especially caster-only acuity behavior; duration beyond original timers; missing-effect restoration and weaker upgrades; stronger/equal ordinary buffs and same-ID effects; disabled buffs; zoning/reload; death/release/logout/relog; concentration and icons; no companions/groups/bots/nearby recipients; no saved effect records |
| Songs/chants | Every eligible class/line with multiple families; learned ranks, activation costs/reuse/instruments; melee weapon changes and travel; CC suspension/recovery; child-effect stacking/range; bot maintenance and resurrection priorities; unrelated caster speed, PBT, focus, charm/mez and pet/self pulses retain their behavior |
| Bind portals | Primary recall unchanged; client actually sends secondary `/use2` for the existing recall item; same/cross-region loading; both directions, owner-only access, proximity and heading; same stock model is visible/selectable; ten-minute/reuse/bind-change/death/logout cleanup; failed transfer/insertion; RvR/BG/keep/relic/jail/instance/disabled region/combat/mount/interior restrictions; normal companion travel |

Client-dependent points remain the exact enemy name color, target/UI presentation, unlimited-session buff icon display, custom item tooltip/use affordances, secondary bind-use signaling, and portal visibility/selectability. If the client refuses a required action or presentation, that is a separately reviewable blocker; no client patch has been made. Portal floor geometry and asynchronous loading, large bot populations, and the installed playable spell/item catalogs still require runtime acceptance.

Deployment and playable-server startup are not approved or performed. Stop here for review.
