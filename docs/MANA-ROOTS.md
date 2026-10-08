# Beez Online — Mana Roots

## Final approved scope

Mana Roots is one Animist spell, unlocked at character level 15 regardless of
specialization. It lasts 60 seconds, is instant, self-only, costs no power or
concentration, and has no cooldown/shared reuse timer. There are no level 30 or
40 ranks. Earlier percentage/additive proposals are superseded.

The Animist becomes one with the soil, calming their spirit and drawing upon the
earth's reserves to recover the regeneration that combat would otherwise suppress.
This is combat-regeneration restoration, not a PowerRegenerationAmount buff.

During the effect, power ticks use the normal out-of-combat interval for the
current stance: 6 seconds standing or 3 seconds sitting. The existing native
PowerRegenerationAmountCalculator remains unchanged, including level, buffs,
equipment, abilities, debuffs, the configured low-power ListCaster penalty,
server modifier, integer rounding and minimum tick amount. The existing single
power timer awards one native amount per tick. There is no second regeneration
source, additive 100% bonus, total-regeneration ceiling, or multiplication of a
calculated tick amount. Health retains its native combat cadence. Actual combat
state and timestamps remain unchanged.

Out of combat, this is the ordinary cadence. Returning to combat keeps the
restored cadence for the remaining duration; combat transitions do not touch
expiry. Activation in combat re-arms the power timer at the restored interval,
without granting power. Ending in combat re-arms it at the native interval.
Out-of-combat activation/ending preserves an already-running normal timer.
Recasting refreshes the same effect to 60 seconds without briefly releasing the
movement lock or stacking effects.

A dedicated ManaRoots effect owns its zero-speed multiplier. It does not use
ordinary root mechanics, root immunity, duration reduction, damage-break logic,
or a crowd-control flag that would forbid casting/change combat state. Ordinary
roots retain their own effects and speed multipliers. Casting remains subject to
native interrupts, stun, mez and other normal rules. Shift-click cancellation and
Purge cannot release Mana Roots early. Activation requires an unmounted Animist. Voluntary NPC/steed mounting is blocked
while rooted so a taxi cannot carry the character around the movement lock; native
forced movement remains independent.
Death/logout use native effect cleanup; the effect is not saved/reconstructed.

Turret caps, durations, costs and all other Animist mechanics remain untouched.
No autonomous/companion bot AI or spell grants are added.

## Saved visual investigation

Read-only verification used the supplied `beez_spell_data.sqlite3` (SHA-256
`54a92c0691e7d778e1a344890325cd02ed7d2e99767ee3bb676339b9df316f6b`) and
`source/tools/observer-model-inspection/{spells,speffects,spnifs}.csv`.
The database itself is not committed or changed.

`ClientEffect` is the packet's spell-visual ID. The target-effect and NIF IDs below
are different client-catalog namespaces and are not substituted into that packet.

| Existing ClientEffect | Target-effect ID / attachment | NIF ID / filename | Catalog lifetime |
|---|---|---|---|
| 5201 Grasping Vines; 5204 Clutching Vines | 53, Vines whip around ankles / rootnode | 22 / vinewhip_hit | 4 seconds |
| 5208 Detaining Vines | 263, Vine wrapping / rootnode | 251 / hib_vinewrap_hit | 3 seconds |
| 4435 Empowering Unity; 4436 Harmony; 4437 Tranquility | 179, blue helix heal 2 / Bip01 Pelvis | 170 / alb_heal2_hit | 4 seconds |
| 4438 Empowering Concordance | 180, blue helix heal 3 / Bip01 Pelvis | 171 / alb_heal3_hit | 4 seconds |
| 4439 Empowering Perfection | 181, blue helix heal 4 / Bip01 Pelvis | 172 / alb_heal4_hit | 4 seconds |

CSV source lines: spells 2879/2882/2886 and 2429–2433; speffects 55/265 and
181–183; spnifs 24/253 and 172–174. All listed NIF rows have Expansion Only=0
and Housing Only=0. These are existing Classic-class spell associations; those
flags alone do not certify appearance in every historical Classic/SI client.

The supplied database confirms 5201/5204/5208 as Druid Nature roots and
4435–4439 as PowerRegenBuff spells in the Mentalist Holism/Mana specialization,
through Spell -> LineXSpell -> SpellLine (ClassIDHint 42). Mana Roots borrows
only their visual IDs.

The Mentalist rows also reference hand effects 1/2, NIF 2 `cast1`, described as
blue sparkles (speffects lines 3/4; spnifs line 4). These are casting handglows,
not a verified persistent impact sparkle. The verified impact is blue helix.
No purple candidate was verified in this set.

SpellHandler.SendEffectAnimation supports an explicit ClientEffect. PacketLib168
and PacketLib174.SendSpellEffectAnimation send caster, target, visual ID,
bolt travel time, sound and success. They have no buff-duration or independent
animation-instance cancellation handle. Icon duration is a separate packet.
The candidate root and mana visuals have different attachment nodes and blank
Remove Effect on Cast fields, supporting overlap as a candidate, not proving
actual client coexistence.

The implementation requests 5201 and 4435 on activation, then silent cosmetic
4435 pulses approximately every 8 seconds. These are packet requests, never
casts of the borrowed spells. Delayed servicing sends one pulse rather than a
catch-up burst. Pulses require at least the four-second catalog lifetime remaining
and stop when the effect ends. The root visual plays on activation; the effect
icon/movement lock lasts for the complete root duration.

Client rendering, particle load, observer visibility and exact lingering particle
termination remain manual acceptance items. Existing packets cannot cancel an
already-playing particle instance; death/logout or other early cleanup may leave
its brief natural visual tail. No client patches or catalog modifications are made.

## Source and runtime additions

- `GameServer/gameutils/ManaRoots.cs`: definition, level/class grant and usable-list
  integration. Scripted server SpellID 760015; line key `Beez Mana Roots`, ID 32000.
- `GameServer/spells/Animist/ManaRootsSpellHandler.cs`: native casting integration,
  eligibility, fixed duration, safe refresh and cosmetic packet requests.
- `GameServer/ECS-Effects/ManaRootsECSEffect.cs`: independent movement lock,
  cosmetic schedule, expiry, cleanup and save/concentration exclusion.
- `GamePlayer`: scoped power interval, skill refresh/list hooks and voluntary steed guard.
- `eSpellType`, `eEffect`, `EffectHelper`: dedicated registration/mapping.
- `PurgeAbility`: excludes only ManaRootsECSEffect from voluntary Purge cleanup.
- `Tests/UnitTests/UT_ManaRoots.cs`: focused automated coverage.

No schema, database migration, configuration, runtime asset or client addition is
required. Spell/line registration is in memory through SkillBase; it does not
insert Spell or LineXSpell records. The learned spell is rebuilt from class/level during skill refresh; active Mana
Roots never writes a saved-effect record.

## Review and local manual acceptance

Do not deploy/start the playable installation until reviewed. In a disposable
playable copy after deployment approval:

1. Verify Animist level 14 has no Mana Roots; level 15+ gets exactly one spell in
   the Mana Roots list, including existing characters after login/skill refresh.
2. Verify instant, free activation with no reuse timer; no instant power gain.
   Recast safely refreshes the same root without releasing movement.
3. Observe 60 seconds of immobilization under incoming damage and attempts to
   cancel/Purge. Cast normal turret spells while rooted, checking native interrupts,
   stun/mez, costs, turret durations and caps.
4. Compare combat and out-of-combat mana tick amount/cadence with no bonuses,
   regeneration buffs/equipment/abilities, low mana and debuffs. Confirm power
   uses normal out-of-combat cadence, health remains native, and there is no
   duplicated restoration or total baseline ceiling.
5. Enter/leave combat during the root; verify unchanged expiry. Test sitting and
   an ordinary enemy root ending before/after Mana Roots; each movement lock must
   survive the other effect's removal.
6. Check activation vines and blue mana overlay from self/another client, silent
   eight-second repeats, concurrent casting, last pulse and expiry particle tail.
7. Check death, release/logout, relog, and normal zoning: no saved roots, stale
   movement lock or post-cleanup pulse scheduler.

Automated/build outcomes are reported separately in the implementation handoff;
these manual checks have not been performed in the cloud.

## Automated validation (cloud, 2026-10-08)

- Release solution build: succeeded, 0 errors, 623 warnings; no warnings attributed
  to the new Mana Roots source/test files.
- Focused UT_ManaRoots: 18 passed, 0 failed.
- Server regression run: 2,659 passed, 0 failed.
- The 58 explicit installed-data/navmesh probes remain NotExecuted, separately
  from the passing regression count.
- CRLF-aware diff whitespace check passed.
- No playable server startup, database deployment, client rendering or live
  gameplay acceptance was performed.

Reproduction (with the .NET 10 SDK and dependencies already installed):

```bash
dotnet build "source/server/Dawn of Light.sln" -c Release --no-restore -m:2
dotnet test source/server/Tests/Tests.csproj -c Release --no-build --no-restore --filter "FullyQualifiedName~UT_ManaRoots"
dotnet test source/server/Tests/Tests.csproj -c Release --no-build --no-restore
```

Output: `source/server/Release/lib/GameServer.dll`.
