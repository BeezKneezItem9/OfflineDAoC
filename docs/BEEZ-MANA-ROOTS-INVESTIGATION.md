# Mana Roots and Buff Stone power investigation

Archived investigation of **d39eb0a9a4d56c80630421c99b92472b33fba6fe**, before the approved overhaul. The formulas, numerical results and timer failures below describe that deployed baseline, not the corrected implementation. See [BEEZ-REGENERATION-OVERHAUL.md](BEEZ-REGENERATION-OVERHAUL.md) for the implemented behavior. Investigation measurements used in-memory fixtures and did not deploy or start a playable server.

Mana Roots restores the ordinary out-of-combat **tick interval**, using current native regeneration amounts including buffs. It does not bypass the classic below-half-power penalty. The Buff Stone's power buff works through the native effect/property pipeline in controlled tests. The primary slow-rate explanation is the small flat +5 buff, halved with all other regeneration below 50%, against a potentially large power pool. A separate, verified timer-phase problem can delay post-expiration regeneration; no persistent override or accumulating bonus was found.

The owner's actual character level, maximum power, stance and deployed database settings remain unknown. All measurements below are controlled in-memory production-code execution, not client observations.

## Complete pipeline and source evidence

Source references are pinned to the deployed commit:

- [ClassAnimist.cs:39](https://github.com/BeezKneezItem9/OfflineDAoC/blob/d39eb0a9a4d56c80630421c99b92472b33fba6fe/source/server/GameServer/playerclasses/hibernia/ClassAnimist.cs#L39): INT is the mana stat; Animist is a list caster, so it qualifies for the configured below-half penalty.
- [GameLiving.cs:2733](https://github.com/BeezKneezItem9/OfflineDAoC/blob/d39eb0a9a4d56c80630421c99b92472b33fba6fe/source/server/GameServer/gameobjects/GameLiving.cs#L2733): setting power clamps it to `[0, MaxMana]` and attempts to start regeneration if deficient. `ManaPercent` uses integer `Mana * 100 / MaxMana`.
- [GamePlayer.cs:2354](https://github.com/BeezKneezItem9/OfflineDAoC/blob/d39eb0a9a4d56c80630421c99b92472b33fba6fe/source/server/GameServer/gameobjects/GamePlayer.cs#L2354): start is ignored when dead/inactive or when a timer is already alive. It does not reschedule an alive timer when combat or stance changes.
- [GameLiving.cs:2618](https://github.com/BeezKneezItem9/OfflineDAoC/blob/d39eb0a9a4d56c80630421c99b92472b33fba6fe/source/server/GameServer/gameobjects/GameLiving.cs#L2618): the native timer callback reads `GetModified(PowerRegenerationAmount)` on every tick, calls `ChangeMana`, and returns the current interval. The full-power check stops the timer on a subsequent callback. The negative regeneration branch applies to Vampiir/Mauler, not Animist. Casting does not itself disable this callback; spell spending can exceed regeneration and reduce net observed recovery.
- [ClassicRestRegeneration.cs:7](https://github.com/BeezKneezItem9/OfflineDAoC/blob/d39eb0a9a4d56c80630421c99b92472b33fba6fe/source/server/GameServer/gameutils/ClassicRestRegeneration.cs#L7): standing OOC 6 seconds; sitting OOC 3; standing combat 14; sitting combat 10. [GamePlayer.cs:2339](https://github.com/BeezKneezItem9/OfflineDAoC/blob/d39eb0a9a4d56c80630421c99b92472b33fba6fe/source/server/GameServer/gameobjects/GamePlayer.cs#L2339) substitutes the OOC interval only while Mana Roots is currently active. Health and combat state remain native.
- [PowerRegenerationAmountCalculator.cs:30](https://github.com/BeezKneezItem9/OfflineDAoC/blob/d39eb0a9a4d56c80630421c99b92472b33fba6fe/source/server/GameServer/propertycalc/PowerRegenerationAmountCalculator.cs#L30) implements:

```
subtotal = 2.5 + 0.2 * level
         + BaseBuffBonus[PowerRegenerationAmount]
         + AbilityBonus[PowerRegenerationAmount]
         + ItemBonus[PowerRegenerationAmount]
         - abs(SpecBuffBonus[PowerRegenerationAmount])
if configured penalty && real-player list caster && current ManaPercent < 50:
    subtotal /= 2
amount = max(1, truncate(subtotal * mana_regen_amount_modifier))
```

The buff, ability, equipment and debuff contributions are summed **before** halving. The server modifier comes **after** halving. There is one final truncation, not a truncation before the modifier. Example with level 50, buff +5, item +3, ability +2 and debuff 4: subtotal 18.5; below half with modifier 1.5 gives `truncate(18.5 / 2 * 1.5) = 13`; above half gives 27. Exactly 50% is not halved. In the tested pool, 199/400 is halved; 200/400 is not. A buffed tick from 199 yields 207 (+8); the next tick yields 224 (+17). Thus the penalty is applied as the existing configuration and code intend, including to the Buff Stone bonus.

- [ServerProperties.cs:863](https://github.com/BeezKneezItem9/OfflineDAoC/blob/d39eb0a9a4d56c80630421c99b92472b33fba6fe/source/server/GameServer/serverproperty/ServerProperties.cs#L863): defaults are modifier 1 and halving True. GameBot is explicitly exempt from the list-caster low-bar penalty; bot resting shortcuts must not be used as a human Animist baseline.
- There is no explicit upper regeneration-amount cap in this calculator. Minimum result is 1; actual gains are limited by the remaining power deficit. Serenity is an additive ability bonus (Atlas OF ranks +1 through +5). Direct regeneration item bonuses are additive. INT, acuity, power-pool gear and maximum-power abilities affect pool size, not the level-derived regeneration subtotal.
- [MaxManaCalculator.cs:54](https://github.com/BeezKneezItem9/OfflineDAoC/blob/d39eb0a9a4d56c80630421c99b92472b33fba6fe/source/server/GameServer/propertycalc/MaxManaCalculator.cs#L54): native pool is based on level and modified casting stat; flat item power is capped at `level/2 + 1`, and item percentage pool is capped at `level/2 + min(pool-cap-bonus, level)`. Flat and percentage ability bonuses use their own additive/multiplicative channels. The stone also supplies acuity (Hibernian spell 5080, value 52 with the stone's 1.25 stat factor, yielding 65 before stat caps), potentially enlarging the pool and lowering recovery as a percentage of maximum. This is why the controlled comparisons normalize the pool.

## Buff Stone evidence

[BeezBuffs.cs:45](https://github.com/BeezKneezItem9/OfflineDAoC/blob/d39eb0a9a4d56c80630421c99b92472b33fba6fe/source/server/GameServer/gameutils/BeezBuffs.cs#L45) selects `Holism` spell **4439**, **Empowering Perfection**, level **44**, value **5**, effect group **60**. Spell resolution is from the actual server skill registry; a missing required entry rejects the whole package before application. The power buff receives effectiveness **1.0**, not the stat buffs' 1.25 factor.

These values were independently verified by reading only the **official public v0.35b release database**, extracted to investigation scratch space after ZIP CRC and package-manifest SHA-256 checks. The public DB hash is `0fff1a26913430a9c8f258484a1e2bae69102354c5e287d7d505d200dd3fdfe6`. Its `LineXSpell` row binds 4439 to Holism at level 44; its spell row has duration 1200 seconds, concentration 0 and value 5. Its saved rate settings are halving True and modifier 1. Albion spell 980 and Midgard spell 3365 also have value 5. No played/owner database was read or modified. A locally customized deployed spell/settings record could differ and must be checked separately.

[RegenBuff.cs:19](https://github.com/BeezKneezItem9/OfflineDAoC/blob/d39eb0a9a4d56c80630421c99b92472b33fba6fe/source/server/GameServer/spells/RegenBuff.cs#L19) selects `PowerRegenerationAmount` in the base-buff channel. The `PropertyChangingSpell` factory creates a `StatBuffECSEffect`; [StatBuffECSEffect.cs:19](https://github.com/BeezKneezItem9/OfflineDAoC/blob/d39eb0a9a4d56c80630421c99b92472b33fba6fe/source/server/GameServer/ECS-Effects/StatBuffECSEffect.cs#L19) adds value × effectiveness on start and subtracts it on stop. Starting/stopping a buff attempts to start regeneration but does not reset a living timer.

Stone-origin [ECSGameSpellEffect.cs:31](https://github.com/BeezKneezItem9/OfflineDAoC/blob/d39eb0a9a4d56c80630421c99b92472b33fba6fe/source/server/GameServer/ECS-Effects/ECSGameSpellEffect.cs#L31) sets duration, expiry, maintenance pulse and next tick to zero. Consequently the stone buff is session-long, despite the donor spell's normal 20-minute duration, and is not persisted as a saved effect. Cleanup removes +5 without touching Roots' independent cadence logic.

The stone-specific [EffectListComponent.cs:639](https://github.com/BeezKneezItem9/OfflineDAoC/blob/d39eb0a9a4d56c80630421c99b92472b33fba6fe/source/server/GameServer/ECS-Components/EffectListComponent.cs#L639) guard preserves **equal or stronger** conflicting native buffs. Repeated stone use does not add another +5. If an equal normal timed power buff already exists, the stone does not replace it with a session buff; that normal buff can still expire. Tests verify that behavior for values 5 and 9. A red icon alone does not prove which effect owns the bonus or whether its lifetime is stone-origin.

## Controlled measurements

Every row uses a level-50 real-player Animist, standing, maximum power **400**, no regen equipment/Serenity/debuff, modifier 1 and halving True. Below-half runs start at **40**; above-half runs at **210**. Conditions are identical within each column. The pool is normalized through the existing flat maximum-power ability channel, without overriding the production calculator. The actual stone **power-regeneration component** is applied using the verified spell, native handler and stone application context; other stone stat buffs are excluded to keep the same pool and isolate this modifier.

Production `ECSGameTimer.Tick`, its actual power callback, effect application, native expiration service method and effect-list processing are executed with a deterministic clock. Timers run before effects, matching `GameLoop.BuildTickSequence` (lines 147–154). New hostile timestamps sustain combat without spending power. Measurement window is `(0, 60 seconds]`, with no mana expenditure; percentages are gained power divided by 400, not percentage of missing power. Phase/tolerance and actual game-loop lag can shift a boundary tick in game.

| Scenario | Power/tick: below / above | Tick timing (seconds) | Ticks | 60s gain: below / above | % max gained: below / above |
| --- | --- | --- | --- | --- | --- |
| OOC unbuffed | 6 / 12 | 6, 12, …, 60 | 10 | 60 / 120 | 15% / 30% |
| OOC Buff Stone | 8 / 17 | 6, 12, …, 60 | 10 | 80 / 170 | 20% / 42.5% |
| Combat, no Roots, unbuffed | 6 / 12 | 14, 28, 42, 56 | 4 | 24 / 48 | 6% / 12% |
| Combat, no Roots, Buff Stone (extra comparison) | 8 / 17 | 14, 28, 42, 56 | 4 | 32 / 68 | 8% / 17% |
| Combat, Roots only | 6 / 12 | 6, 12, …, 60 | 10 | 60 / 120 | 15% / 30% |
| Combat, Roots + Buff Stone | 8 / 17 | 6, 12, …, 60 | 10 | 80 / 170 | 20% / 42.5% |
| After Roots expires, combat continues, stone retained | 8 / 17 | 14, 28, 42, 56 | 4 | 32 / 68 | 8% / 17% |
| Root expires in combat, then combat ends, stone retained | 8 / 17 | **14**, then 20, 26, 32, 38, 44, 50, 56 | 8 | 64 / 136 | 16% / 34% |
| Roots refreshed at 5, 30 and 50s, stone retained | 8 / 17 | 6, 12, …, 60 | 10 | 80 / 170 | 20% / 42.5% |

Post-expiry rows first execute an actual rooted combat minute, then reset only starting power to the controlled value and measure the next minute. The combat-ended row ends combat immediately after in-combat expiry cleanup; its already scheduled 14-second timer is retained. A separate test ends combat naturally **before** expiration: the next tick remains six seconds away, with no expiry override or phase reset.

No extra power is granted on activation/refresh/expiry. Roots does not use a cached unbuffed amount: adding the buff during Roots changes the next native tick from +6 to +8; removing it changes the next to +6, without resetting the timer. The strict 50% threshold and modifier order were independently tested. The figures agree with the native formulas; the lower post-combat-ended count is scheduling, not a weaker amount.

## Verified lifecycle problems and limits

1. **Imminent tick discarded on in-combat activation.** [ManaRootsECSEffect.cs:69](https://github.com/BeezKneezItem9/OfflineDAoC/blob/d39eb0a9a4d56c80630421c99b92472b33fba6fe/source/server/GameServer/ECS-Effects/ManaRootsECSEffect.cs#L69) stops/restarts any in-combat timer. [TimerService.cs:110](https://github.com/BeezKneezItem9/OfflineDAoC/blob/d39eb0a9a4d56c80630421c99b92472b33fba6fe/source/server/GameServer/ECS-Services/TimerService.cs#L110) sets `NextTick = now + interval`. Activating 0.1s before an existing tick postpones it by **5.9s**. No duplicate award occurs, but an already due-soon regeneration opportunity is displaced.
2. **Overlong gap on expiration when tick phase is carried from OOC.** Start an OOC timer at t=0; activate Roots at t=5.9, preserving a tick at t=6; enter combat. Root ticks occur at 6, 12, …, 60. Roots expires at 65.9. Its stop hook restarts from expiration, setting the next tick to **79.9**. The gap from the last tick is **19.9s**, compared with a native standing combat interval of 14s. Scheduling 14 seconds from the last actual tick would give t=74. This is unnecessary lost timer phase, up to approximately one carried OOC interval. It is not a persistent low-regeneration property or a permanently active root flag.
3. **Late cleanup adds delay even when the callback already selected native cadence.** At an expiry frame 1.5s late, TimerService runs first and returns the native interval (Roots' time predicate already excludes expiry). `NextTick += 14s` would preserve the prior schedule. The stop hook restarts again from now, shifting the next due tick by an unnecessary **1.5s**. This is reproduced without claiming live server lag was measured.
4. **Combat exit retains one slow pending tick.** `StartPowerRegeneration` refuses to alter an alive timer and combat expiry sends only a speed update. Ending combat just after root stop leaves its 14s due time; the callback then returns 6s. This occurs in native combat-to-OOC transitions too, so it is not evidence of a lingering Mana Roots override. In the controlled first recovery minute it loses two OOC opportunities (16 power below half with the stone).

Effect list finalizes active/ended state before running start/stop hooks. `ManaRoots.ActiveEffect` excludes ended/ending and time-expired effects; the stop hook removes only its own speed modifier and zeroes its visual/lifecycle tick. Roots never modifies attack timestamps, base regeneration amount, equipment/ability regeneration channels or server settings. Refresh reuses the same effect and does not restart the power timer. Three full expired activation cycles show no stacking or movement/regen-state leakage.

Native death cancels effects and stops regeneration timers (GameLiving.cs:2058–2065); removal from world also stops them (3605–3608). Root pulses end the effect on dead/inactive/foreign-class owners; its restart is guarded against dead/inactive players. Tests cover invalid-owner cancellation and normal recovery afterward, pending-start cancellation, and existing death/logout cleanup tests. Actual disconnect/reaper/network races and in-game death/release remain manual acceptance items; no playable server was started. Roots is instant and does not maintain a cancellable cast-time regeneration loop; ordinary spell interruption cannot leave such a loop behind. Casting permissions and visuals are unchanged.

Comparison with `fb4a217` found no changes in ManaRoots, its effect, BeezBuffs, the human power amount calculator, native timer implementation, stat-buff effect or effect arbitration. The relevant player regeneration method also did not change in integration. The issues are present in the Beez implementation, rather than a demonstrated new upstream regression. Upstream bot regeneration behavior must be distinguished from the human pipeline.

## Recommended correctness work (not implemented)

- Replace unconditional stop/start phase loss with scheduling that preserves elapsed time since the last actual power tick, changing cadence without awarding immediate or duplicate power.
- On activation, preserve an imminent existing tick instead of resetting it six seconds away; thereafter use OOC cadence.
- At expiration, use the native interval measured from the last actual tick, and avoid another reset if the timer callback already selected native cadence. Handle overdue deadlines explicitly so a late frame cannot cause duplicate catch-up awards.
- Decide separately whether to rephase ordinary combat/stance transitions, because that changes native scheduling for other characters too. Restoring six-second OOC scheduling promptly would remove the one stale combat interval, but should not be slipped into a Roots-only fix without agreeing scope.
- Preserve all source bonuses, the 50% rule, 60-second duration, instant/no-cost activation, independent self-root, casting permissions and visuals.

The new delay tests currently **characterize the observed defect**, rather than asserting the proposed behavior already exists. After an approved fix, change their expected deadlines to the preserved-phase deadlines and retain their scenarios to prevent regressions.

## Balance options, separate from correctness

While active, Roots currently functions as designed: ordinary standing OOC recovery in combat, still subject to native low-power penalties. With the controlled depleted 400-power character, Roots + stone restores only **80 power (20%) per minute**, or 1.33 power/second before casting costs. That can feel weak despite being 2.5 times the measured four-tick combat recovery in this 60-second window. Correct timer bugs first and assess actual character measurements before changing balance.

Illustrations below assume the same standing, level-50, max-400, starting-40 character, ten six-second ticks, no spending, and modifier 1. A multiplier would be applied to the already calculated native integer tick, then truncated; bonuses are not duplicated. All illustrated runs remain below half until their final tick or later.

| Optional Roots-only policy | Unbuffed gain over 60s | Stone gain over 60s |
| --- | --- | --- |
| Current behavior | 60 (15%) | 80 (20%) |
| 1.25× effective native tick | 70 (17.5%): floor(6×1.25)=7 | 100 (25%): floor(8×1.25)=10 |
| 1.5× effective native tick | 90 (22.5%): floor(6×1.5)=9 | 120 (30%): floor(8×1.5)=12 |
| Native tick + 1% maximum power each six-second tick | 100 (25%): 6+4 | 120 (30%): 8+4 |

The mild 1.25× or 1.5× option keeps the Buff Stone meaningful. An additive percentage top-up also preserves native buff contributions and scales with larger pools; its time budget needs definition for sitting/three-second cadence to prevent accidentally doubling the intended per-minute percentage. Actual totals must be recalculated when power crosses 50%, hits full, stance changes or casting consumes power. Do not change the global rate/halving properties merely to tune one ability.

## Verification and local changes

Focused Mana Roots suite: **56 passed**, including the original 18 and **38 added cases**. Full server suite: **2,824 passed, zero failed, 61 NotExecuted**, exactly baseline 2,786 plus the 38 new cases. Release test compilation succeeded. Production code/formulas are unchanged; no balance option or scheduling fix was applied.

Added `source/server/Tests/UnitTests/UT_ManaRoots_RegenerationInvestigation.cs`; made the existing fixture partial to reuse its native test actors, calculator loading and deterministic clock. Coverage includes both power ranges, modifier ordering, exact-half crossing, stone addition/removal and stacking/lifetime, native timed-buff preservation, refresh, repeated expiry cycles, delayed activation/expiry, combat transitions, invalid-owner cleanup and pending cancellation.

Detailed tick output and CSV/JSON measurements are in local investigation scratch space and the NUnit TRX results. The published Windows ZIP remains unchanged. No Git commit, push or publication was performed for these changes.
