# Beez Online regeneration overhaul

Implemented on `beez-online-six-features`, based on deployed commit
`d39eb0a9a4d56c80630421c99b92472b33fba6fe`. This is the approved balance change;
no playable files, database, release package or client assets are modified.
The [previous investigation](BEEZ-MANA-ROOTS-INVESTIGATION.md) records the old behavior.

## Formulas and scope

For level `L`, define `A = BaseBuffBonus + AbilityBonus + ItemBonus` and
`D = abs(SpecBuffBonus)`, separately for each regeneration property.

- Power per tick: `max(1, truncate(2 * (2.5 + 0.2*L + A - D) * mana_regen_amount_modifier))`.
- Health per tick: `max(1, truncate(2 * (2.5 + 0.25*L + A - D) * health_regen_amount_modifier))`.
  Disease or bleed still returns zero before this calculation.
- Player/bot endurance per one-second tick:
  `max(0, truncate((B + A - D) * endurance_regen_amount_modifier))`, where
  `B = 4` out of combat, including walking/running, and `B = 0` in combat.
  Sprint consumption, Long Wind, fatigue-consumption modifiers and Charge are
  applied by the existing callback afterward. Movement does not give free sprinting.

Health and power double the native base and net aids **once**, before the
independent configured rate multiplier and the single final truncation. Debuff
contributions scale with the same net subtotal. Equipment/stat/power-pool caps,
stacking categories, buff replacement rules and maximum-resource calculations
are unchanged. Larger maximum power does not directly increase recovery per tick.

The old `mana_regen_amount_halved_below_50_percent` key and Boolean field remain
loadable, default to **False**, and are intentionally ignored, even if a saved
configuration contains **True**. This fully adopts 1.78 without editing saved data.
Existing health, power and endurance amount multipliers retain their saved values.
There are no new properties, schema changes or migrations.

## Timing and historical interpretation

| Resource/state | Old interval | New interval |
|---|---:|---:|
| Health/power standing OOC | 6 s | 3 s |
| Health/power sitting OOC | 3 s | 3 s |
| Health/power standing combat | 14 s | 7 s |
| Health/power sitting combat | 10 s | 5 s |
| Endurance, all stances | 1 s | 1 s |
| Mana Roots power while in combat | OOC cadence | OOC cadence (3 s) |

The source already contained the 1.87 patch descriptions, but its shared cadence
and health/power amount calculators explicitly reverted those improvements. This
implementation doubles **this fork's existing level curves**, rather than adopting
DOL's different `5 + L/2.75` power or piecewise health curve. Thus level-50 native
power is exactly 25, rather than approximately 23. This is a documented
interpretation of the requested doubling, not a claim of exact original-client formulas.

Endurance already ran on a one-second clock and used a seated +4 contribution.
Standing and moving OOC now match that throughput with +4 on that existing clock;
there is no extra frequency or amount multiplier. This maps the historical
standing/sitting and moving improvement onto this fork's existing timer model.
Combat still requires endurance aids/Tireless. Endurance aids are not doubled;
the quoted aid-doubling change applies to health and power. Atlas-style Tireless
already contributes +1 per tick and remains unchanged.

These player timing rules apply to real players, companion bots and autonomous
playerbots. Bot enhanced rest retains its separate one-second clock, one-time
immediate first tick, and ten-percent-of-maximum recovery floor. Its native amount
input improves, but that percentage floor is not doubled. Ordinary NPCs keep
separate 30-second combat/6-second OOC health timing, their combat half-amount rule,
and their special 12.5%-maximum evade recovery. Their ordinary level/aid subtotal
uses the doubled health calculator, but the evade amount replaces it, as before.
Vampiir/Mauler special negative-power behavior remains unchanged.

## Mana Roots lifecycle repair

Health and power timers opt into a dynamic interval provider. TimerService
reconciles that interval **before** testing whether the tick is due, so combat,
stance, pet-combat and Roots expiration are observed without waiting for the old
cadence. Other timers retain their existing callback behavior.

For an interval change, the proposed due time is
`oldNextTick - oldInterval + newInterval`. A slower cadence uses that phase anchor.
A faster cadence keeps the earlier pending tick; if its new anchor is already in
the past, it uses the earlier of the pending tick and `now + newInterval`, avoiding
a burst of retroactive awards. Repeating a refresh with unchanged interval is a
no-op. Bot timers explicitly preserve their initial scheduled recovery tick.

Roots start/stop refreshes the existing timer instead of stopping and restarting
it. Dead/inactive cancellation stops it. Roots refresh never awards power or
resets the timer. An expired/ending effect is excluded before deferred effect
cleanup, so late cleanup cannot re-arm an already-native timer.

The reproduced offset case previously produced a **19.9-second** post-expiration
gap. It now produces **7 seconds** between the last rooted tick and the next native
standing-combat tick (4.1 seconds still pending at cleanup). Tests also cover late
cleanup, no immediate mana award, buff addition/removal, repeated refreshes,
three complete activation cycles, pending-start cancellation and dead/inactive
cancellation followed by regeneration restoration.

Roots remains level 15, instant, free, with no cooldown, a 60-second self-root,
casting permissions and its original visuals. It adds no recovery multiplier.

## Numerical comparisons

Controlled level-50 Animist, maximum power 2,000, standing, no spending, rate
modifier 1. Starting power 200 (below half) or 1,100 (above half). These pools keep
all measured windows away from the full-power cap and the 50% boundary.
Old totals use the validated deployed formula/timing; new totals are asserted
against production calculators, native callbacks and real ECS effects/timers.
Each window includes the 60-second endpoint. Numbers are power recovered per window.

| Scenario | Old below/above half | New both | New % of max | New ticks |
|---|---:|---:|---:|---:|
| OOC unbuffed | 60 / 120 | 500 | 25% | 20 × 25 |
| OOC Buff Stone | 80 / 170 | 700 | 35% | 20 × 35 |
| Combat unbuffed | 24 / 48 | 200 | 10% | 8 × 25 |
| Combat Buff Stone | 32 / 68 | 280 | 14% | 8 × 35 |
| Combat Roots only, actual 60-s effect | 60 / 120 | 475 | 23.75% | 19 × 25 |
| Combat Roots + Stone, actual 60-s effect | 80 / 170 | 665 | 33.25% | 19 × 35 |
| First minute after Roots expires, combat + Stone | 32 / 68 | 315 | 15.75% | 9 × 35 |
| First minute after Roots expires and combat ends + Stone | 64 / 136 | 665 | 33.25% | 19 × 35 |
| Roots refreshed at 5, 30 and 50 s + Stone | 80 / 170 | 700 | 35% | 20 × 35 |

At precisely 60 seconds Roots is expired: reconciliation changes the pending tick
from 60 to 64 seconds, anchored at the last rooted tick at 57. Hence 19 rooted ticks,
then nine combat ticks at relative times 4, 11, ..., 60 in the following minute.
When combat ends at that boundary, the first faster tick is due at 3.1 seconds in
the 100-ms sampled test, followed by 3-second ticks. These phase-dependent first
minutes differ from steady-state throughput; they are not missing/duplicated ticks.
Sitting OOC produces the same 500/700 power per minute. Sitting combat produces
300/420 per minute (12 ticks). Roots prevents movement regardless of the chosen
regeneration stance.

| Other native recovery, level 50, modifier 1, no aids | Old per 60 s | New per 60 s |
|---|---:|---:|
| Health standing OOC | 150 | 600 |
| Health sitting OOC | 300 | 600 |
| Health standing combat | 60 | 240 |
| Health sitting combat | 90 | 360 |
| Endurance standing OOC | 60 | 240 |
| Endurance sitting OOC | 240 | 240 |
| Endurance moving OOC | 0 | 240 |
| Endurance in combat without aids | 0 | 0 |

Endurance totals are uncapped throughput; an actual 100-point endurance pool caps
at full. The callback test spends each recovered tick to keep measuring all 60 ticks.
Health tests normalize the pool to 2,000 to avoid clamping.

The actual Hibernian Stone donor remains spell **4439**, **Empowering Perfection**,
Holism 44, value **5**, effectiveness 1. Its property contribution remains +5 and
becomes exactly **+10** in the power calculator: `(12.5 + 5)*2 = 35`. There is no
spell-value rewrite, second spell multiplier, stacking change or duration change.
Equal/stronger native buffs keep their existing timed expiration; Stone-origin
buffs retain their session lifetime and cleanly remove their +5 contribution.

## Validation and acceptance

Validation completed with .NET SDK 10.0.401 on Linux:

- Release GameServer and its referenced projects built successfully through
  `dotnet test source/server/Tests/Tests.csproj -c Release --no-restore`.
- Full server regression suite: **2,839 passed, zero failed**. The TRX additionally
  records **61 NotExecuted** installed-world/navigation fixtures; these are not passes.
- Within that run: Mana Roots/regeneration **71 passed**, Beez Online **43 passed**,
  bot resting **47 passed**, bot spell/power **80 passed**.
- Compared with deployed d39eb0a: 2,786 → 2,839 passes, exactly **53 added cases**
  (38 investigation/lifecycle cases updated for the new behavior, plus 15 overhaul
  cases). Existing cases were retained; rate expectations were updated where the
  approved balance changed. The 61 unexecuted fixtures are unchanged.
- Windows launcher and test project cross-build succeeded with
  `dotnet test ...OfflineDaoc.Launcher.Tests.csproj -c Release -p:EnableWindowsTargeting=true`;
  execution then aborted because `Microsoft.WindowsDesktop.App` is unavailable on Linux.
- Existing compiler/analyzer and OpenTelemetry NuGet audit warnings remain;
  no dependency declarations were changed. Whitespace checks pass.
- Raw results: `source/server/Tests/TestResults/regen-approved-final.trx` locally.

The automated fixtures never start the server or use a played database. Existing
character objects and both legacy saved Boolean values are exercised without
schema changes.

Windows launcher test execution requires Windows Desktop and cannot run on this
Linux workspace. Installed-world/navigation fixtures require the playable install
and remain unexecuted. No in-game validation is claimed.

Before release approval, verify on a backed-up playable install: standing/sitting
above and below half power; stone off/on (25 versus 35 at level 50 with modifier 1);
continuous combat with Roots; Roots expiring just before a native tick; repeated
Roots; pet combat transitions; death/relog; walking versus sprinting endurance;
disease/bleed suppression. Check that casts remain permitted while rooted, movement
remains locked, both visuals appear, and ordinary recovery resumes after expiration.
