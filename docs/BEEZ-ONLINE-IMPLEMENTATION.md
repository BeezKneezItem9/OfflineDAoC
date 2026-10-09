# Beez Online — retained custom features and upstream integration

The integration branch adopts `shadowofze/OfflineDAoC` main at
`d337d184034f4c84e1e1748fda7f5b2deef135b8`. Per the owner's integration instruction,
the original Beez RP recovery and enemy naming systems have been removed in favor
of upstream. The Developer Ring, Buff Stone, simultaneous songs/chants, owner-only
Bind Stone portals, and single-rank level-15 Mana Roots remain.

This describes the integration branch, not a deployed playable installation.
No server startup or deployment was performed. Automated results are recorded in
`docs/BEEZ-UPSTREAM-INTEGRATION.md`; real gameplay still requires acceptance.

## Upstream realm points and identity

Autonomous victim rewards now use upstream's repeat-kill eligibility window:
a recent victim pays no RP until `rates/rp_worth_seconds` has elapsed. The old
Beez linear recovery floor, persistent-BotId recovery cache, RvR-only victim gate,
and shared replacement for human-victim arithmetic are gone. Upstream awards
participating gamebots RP, derives their realm levels from the player table, and
allows them to train and use realm abilities. Death diagnostics are retained.

Enemy identity now uses upstream `AutonomousNameMask` and its normal server-rule
and staff exceptions. The 1.124 NPC serializer shows race and realm rank title
rather than Beez's blank guild field. Upstream combat, spell and death message
paths are used unchanged. Beez's additional serializer, examine, pet-message,
effect-message and loot-message overrides have been removed. This intentionally
uses upstream's coverage; it does not certify every client/UI surface.

`BeezRealmRewards.cs`, `BeezEnemyIdentity.cs`, their call sites and nine tests of
the removed custom behavior no longer exist. Upstream RP/rank/name tests remain.

## Retained feature changes and boundaries

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

Primary use retains the normal recall handler. Secondary `/use2` on an owned personal-bind recall item snapshots the expedition position and bind point, recalls through normal movement APIs, and creates two owner-only temporary static gateway objects after confirmed arrival. Arrival allows normal heading and small position updates; client loading gets a bounded 60-second wait. Gateways use stock ITEM model `4319` (Caledonia Portal), have a ten-minute lifetime, and create no database records. See [gateway asset evidence and client limitations](BEEZ-BIND-GATEWAYS.md); in-game visual and interaction acceptance remains pending.

Creation and every traversal check ownership, alive/active state, combat, movement, CC, casting, mounts, relics, valid endpoints, disabled/restricted regions, RvR regions/zones, battlegrounds, instances, jail, keep areas, and normal zoning rules. House interiors are rejected because the endpoint snapshot has no house-instance identity. Existing item reuse is respected. Death, disconnect, bind changes, replacement, failed arrival/world insertion, and expiry dispose the pair. Server restart drops the runtime state. Companion travel continues through the existing normal movement coordinator; portals themselves accept only their owner.

### 7. Mana Roots

The single Animist spell remains available at level 15, for 60 seconds, with no
extra ranks, power cost or reuse timer. It locks movement independently of native
roots and restores only the native out-of-combat power-tick cadence. Native tick
amounts, health cadence and combat state are unchanged. Purge still cannot remove
it, including after upstream's support for bot Purge. See [MANA-ROOTS.md](MANA-ROOTS.md)
for implementation details and manual acceptance.

## Database and configuration

The retained custom features need no schema migration. On a later approved
startup, `BeezDeveloperItems.Load` creates missing `ItemTemplate` rows
`beez_developer_ring` and `beez_buff_stone`, with the custom types
`DOL.GS.BeezDeveloperRing` and `DOL.GS.BeezBuffStone`. Existing matching IDs are
left intact; verify their class types before gameplay. Character creation and
`/beezitems` use ordinary owned inventory records.

Bind portals, Buff Stone effects and the song registry remain session state.
Mana Roots registration stays in memory and active effects are not saved.
Upstream's bot realm-ability points use the existing serialized-abilities field.
New upstream server properties and release quest/navigation assets are listed
in the integration report. No live database or configuration has been changed.

## Manual acceptance

Use a separately approved disposable playable copy with a backed-up database.

- Confirm upstream RP repeat-kill gating, player/bot/pet/group splits, bot realm
  ranks and trainer abilities, plus human progression and battleground caps.
- Check enemy race/rank display and upstream messages from allied, hostile and
  staff clients. Review older packet versions and examine/pet/effect/loot text
  for differences from the removed broader Beez naming overrides.
- Check new/existing character grants, ring equip/remove/relog and legal caps.
- Check all three Buff Stone packages, stronger-buff preservation, concentration,
  zoning, death/logout cleanup and absence of saved effects.
- Check simultaneous songs for each eligible class: learned ranks, instruments,
  melee switching, travel, crowd control and normal child-effect conflicts.
- Check owner-only two-way Bind Stone use, return journeys, cooldowns, expiry,
  death/logout/rebinding and forbidden locations. Verify companions travel normally.
- Run the Mana Roots acceptance steps in its guide and check that bot Purge does
  not weaken the Animist movement lock.
