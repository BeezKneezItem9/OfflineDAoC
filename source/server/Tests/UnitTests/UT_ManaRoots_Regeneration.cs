using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using DOL.Database;
using DOL.GS;
using DOL.GS.Spells;
using NUnit.Framework;

namespace DOL.UnitTests
{
    public partial class UT_ManaRoots
    {
        private static ECSGameTimer PowerTimer(GamePlayer player) =>
            (ECSGameTimer)typeof(GameLiving).GetField("m_powerRegenerationTimer", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(player);

        private sealed class RegenerationBuffFixture
        {
            public string Line { get; set; }
            public int Level { get; set; }
            public DbSpell Spell { get; set; }
        }

        private ECSGameSpellEffect ApplyActualStonePowerBuff(GamePlayer player)
        {
            using var stream = typeof(UT_ManaRoots).Assembly.GetManifestResourceStream("Tests.Fixtures.BeezBuffSpells.json");
            var row = JsonSerializer.Deserialize<RegenerationBuffFixture[]>(stream).Single(r => r.Spell.SpellID == 4439);
            Assert.That(BeezBuffs.Manifest(player.Realm), Does.Contain(new BeezBuffs.Entry(row.Line, row.Spell.SpellID)));
            var handler = new PowerRegenSpellHandler(player, new Spell(row.Spell, row.Level), new SpellLine(row.Line, row.Line, "", false));
            typeof(SpellHandler).GetProperty(nameof(SpellHandler.BeezApplication)).SetValue(handler, new BeezBuffs.Application(player, 0));
            handler.ApplyEffectOnTarget(player);
            player.effectListComponent.BeginTick();
            return player.effectListComponent.GetSpellEffects().Single(e => e.EffectType == eEffect.PowerRegenBuff);
        }

        private GamePlayer MeasurementAnimist(bool buff = false, int startingPower = 200)
        {
            DOL.GS.ServerProperties.Properties.MANA_REGEN_AMOUNT_HALVED_BELOW_50_PERCENT = true;
            GamePlayer player = Animist();
            if (buff) ApplyActualStonePowerBuff(player);
            // Normalize the pool using the native flat ability channel; no production calculator override.
            player.AbilityBonus[eProperty.MaxMana] += 2000 - player.MaxMana;
            Assert.That(player.MaxMana, Is.EqualTo(2000));
            player.Mana = startingPower;
            player.StopPowerRegeneration();
            return player;
        }

        private static readonly MethodInfo RegenerationEffectTick = typeof(EffectService).GetMethod("TickSpellEffect", BindingFlags.Static | BindingFlags.NonPublic);
        private static void TickActualEffects(GamePlayer player)
        {
            foreach (ECSGameSpellEffect effect in player.effectListComponent.GetSpellEffects().ToArray())
                if (effect.IsActive && !effect.IsEnding) RegenerationEffectTick.Invoke(null, [effect]);
            player.effectListComponent.BeginTick();
        }

        // TimerService precedes EffectService and EffectListService in the real GameLoop sequence.
        private static List<(long At, int Gained)> Measure(GamePlayer player, bool combat, Action<long> before = null)
        {
            long start = GameLoop.GameLoopTime;
            var ticks = new List<(long At, int Gained)>();
            for (long elapsed = 100; elapsed <= 60000; elapsed += 100)
            {
                Time(start + elapsed);
                if (combat) player.LastAttackedByEnemyTickPvE = GameLoop.GameLoopTime;
                before?.Invoke(elapsed);
                ECSGameTimer timer = PowerTimer(player);
                timer.RefreshInterval();
                if (timer.IsAlive && GameServiceUtils.ShouldTick(timer.NextTick))
                {
                    int prior = player.Mana;
                    timer.Tick();
                    ticks.Add((elapsed, player.Mana - prior));
                }
                TickActualEffects(player);
            }
            return ticks;
        }

        [TestCase("OOC unbuffed", false, false, false, false, false, 500, 20, 200)]
        [TestCase("OOC unbuffed above 50%", false, false, false, false, false, 500, 20, 1100)]
        [TestCase("OOC Buff Stone", true, false, false, false, false, 700, 20, 200)]
        [TestCase("OOC Buff Stone above 50%", true, false, false, false, false, 700, 20, 1100)]
        [TestCase("Combat unbuffed", false, true, false, false, false, 200, 8, 200)]
        [TestCase("Combat unbuffed above 50%", false, true, false, false, false, 200, 8, 1100)]
        [TestCase("Combat Buff Stone", true, true, false, false, false, 280, 8, 200)]
        [TestCase("Combat Buff Stone above 50%", true, true, false, false, false, 280, 8, 1100)]
        [TestCase("Combat Roots", false, true, true, false, false, 475, 19, 200)]
        [TestCase("Combat Roots above 50%", false, true, true, false, false, 475, 19, 1100)]
        [TestCase("Combat Roots and Buff Stone", true, true, true, false, false, 665, 19, 200)]
        [TestCase("Combat Roots and Buff Stone above 50%", true, true, true, false, false, 665, 19, 1100)]
        [TestCase("Post-expiry combat Buff Stone", true, true, false, true, false, 315, 9, 200)]
        [TestCase("Post-expiry combat Buff Stone above 50%", true, true, false, true, false, 315, 9, 1100)]
        [TestCase("Post-expiry then combat ends Buff Stone", true, false, false, true, false, 665, 19, 200)]
        [TestCase("Post-expiry then combat ends Buff Stone above 50%", true, false, false, true, false, 665, 19, 1100)]
        [TestCase("Repeated Roots and Buff Stone", true, true, true, false, true, 700, 20, 200)]
        [TestCase("Repeated Roots and Buff Stone above 50%", true, true, true, false, true, 700, 20, 1100)]
        public void RegenerationControlledSixtySecondMeasurements(string scenario, bool buff, bool combat, bool roots, bool expired, bool repeat, int expectedGain, int expectedTicks, int startingPower)
        {
            GamePlayer player = MeasurementAnimist(buff, startingPower);
            if (combat || expired) player.LastAttackedByEnemyTickPvE = GameLoop.GameLoopTime;
            player.StartPowerRegeneration();
            if (roots || expired) Apply(player);
            if (expired)
            {
                // Prime an actual 60-second rooted combat window before measuring recovery.
                Measure(player, true);
                Assert.That(ManaRoots.IsRestoring(player), Is.False);
                player.LastAttackedByEnemyTickPvE = combat ? GameLoop.GameLoopTime : 0;
                player.Mana = startingPower;
            }
            var ticks = Measure(player, combat, elapsed =>
            {
                if (repeat && elapsed is 5000 or 30000 or 50000) Apply(player);
            });
            Assert.That(player.Mana - startingPower, Is.EqualTo(expectedGain));
            Assert.That(ticks.Count, Is.EqualTo(expectedTicks));
            Assert.That(player.MaxMana, Is.EqualTo(2000));
            TestContext.WriteLine("REGEN_MEASUREMENT " + JsonSerializer.Serialize(new
            {
                Scenario = scenario, Level = player.Level, MaxPower = player.MaxMana, StartingPower = startingPower,
                PowerGained = player.Mana - startingPower, PercentMaxRecovered = (player.Mana - startingPower) * 100.0 / player.MaxMana,
                Ticks = ticks.Select(t => new { Milliseconds = t.At, t.Gained }),
                NextDueIn = PowerTimer(player).NextTick - GameLoop.GameLoopTime,
                RootActive = ManaRoots.IsRestoring(player), BuffAmount = player.BaseBuffBonusCategory[eProperty.PowerRegenerationAmount]
            }));
        }

        [Test]
        public void RegenerationStoneAddsFivePersistsAndCleansUpWithoutStacking()
        {
            GamePlayer player = MeasurementAnimist(true);
            Assert.That(player.BaseBuffBonusCategory[eProperty.PowerRegenerationAmount], Is.EqualTo(5));
            Assert.That(player.GetModified(eProperty.PowerRegenerationAmount), Is.EqualTo(35));
            player.Mana = 1000;
            Assert.That(player.GetModified(eProperty.PowerRegenerationAmount), Is.EqualTo(35));
            ApplyActualStonePowerBuff(player);
            Assert.That(player.BaseBuffBonusCategory[eProperty.PowerRegenerationAmount], Is.EqualTo(5));
            ECSGameSpellEffect buff = player.effectListComponent.GetSpellEffects().Single(e => e.EffectType == eEffect.PowerRegenBuff);
            Assert.That(buff.Effectiveness, Is.EqualTo(1));
            Assert.That(buff.ExpireTick, Is.Zero);
            Time(GameLoop.GameLoopTime + 1200001);
            TickActualEffects(player);
            Assert.That(buff.IsActive, Is.True, "Stone's session duration overrides donor's 20-minute duration");
            BeezBuffs.Clear(player); player.effectListComponent.BeginTick();
            Assert.That(player.BaseBuffBonusCategory[eProperty.PowerRegenerationAmount], Is.Zero);
            Assert.That(player.GetModified(eProperty.PowerRegenerationAmount), Is.EqualTo(25));
        }

        [Test]
        public void RegenerationBuffFixtureAppliedAndRemovedDuringRootsChangesTheNextNativeTick()
        {
            GamePlayer player = MeasurementAnimist();
            player.LastAttackedByEnemyTickPvE = GameLoop.GameLoopTime;
            Apply(player);
            long due = PowerTimer(player).NextTick;
            ApplyActualStonePowerBuff(player);
            Assert.That(PowerTimer(player).NextTick, Is.EqualTo(due));
            Time(due); PowerTimer(player).Tick();
            Assert.That(player.Mana, Is.EqualTo(235));
            BeezBuffs.Clear(player); player.effectListComponent.BeginTick();
            Time(PowerTimer(player).NextTick); PowerTimer(player).Tick();
            Assert.That(player.Mana, Is.EqualTo(260));
            Assert.That(ManaRoots.IsRestoring(player), Is.True);
        }

        [Test]
        public void ActivationPreservesAnImminentNativeTick()
        {
            GamePlayer player = MeasurementAnimist();
            player.LastAttackedByEnemyTickPvE = GameLoop.GameLoopTime;
            player.StartPowerRegeneration();
            long oldDue = PowerTimer(player).NextTick;
            Time(oldDue - 100);
            player.LastAttackedByEnemyTickPvE = GameLoop.GameLoopTime;
            Apply(player);
            Assert.That(PowerTimer(player).NextTick, Is.EqualTo(oldDue));
            Assert.That(PowerTimer(player).NextTick - oldDue, Is.Zero);
            Assert.That(player.Mana, Is.EqualTo(200));
        }

        [Test]
        public void RegenerationExpiryAfterACombatEndedTransitionDoesNotLeaveAnOverride()
        {
            GamePlayer player = MeasurementAnimist(true);
            player.LastAttackedByEnemyTickPvE = GameLoop.GameLoopTime;
            Apply(player);
            var ticks = Measure(player, false); // No new hostile event; combat naturally expires during Roots.
            Assert.That(ticks.Count, Is.EqualTo(20));
            Assert.That(player.InCombat, Is.False);
            Assert.That(ManaRoots.IsRestoring(player), Is.False);
            Assert.That(Interval(player), Is.EqualTo(3000));
            Assert.That(PowerTimer(player).NextTick - GameLoop.GameLoopTime, Is.EqualTo(3000));
            Assert.That(player.BaseBuffBonusCategory[eProperty.PowerRegenerationAmount], Is.EqualTo(5));
            Assert.That(player.BuffBonusMultCategory1.Get((int)eProperty.MaxSpeed), Is.EqualTo(1));
        }

        [TestCase(false)]
        [TestCase(true)]
        public void RegenerationInactiveOrDeadCancellationStopsThePowerTimer(bool dead)
        {
            GamePlayer player = MeasurementAnimist(true);
            player.LastAttackedByEnemyTickPvE = GameLoop.GameLoopTime;
            var (effect, _) = Apply(player);
            if (dead) player.Health = 0;
            else player.ObjectState = GameObject.eObjectState.Inactive;
            effect.OnEffectPulse(); player.effectListComponent.BeginTick();
            Assert.That(ManaRoots.ActiveEffect(player), Is.Null);
            Assert.That(PowerTimer(player).IsAlive, Is.False);
            player.ObjectState = GameObject.eObjectState.Active; player.Health = 100;
            player.LastAttackedByEnemyTickPvE = 0; player.StartPowerRegeneration();
            Time(PowerTimer(player).NextTick); PowerTimer(player).Tick();
            Assert.That(player.Mana, Is.EqualTo(235));
        }

        [TestCase(200, 1.0, true, 37)]
        [TestCase(1100, 1.0, true, 37)]
        [TestCase(200, 1.5, true, 55)]
        [TestCase(1100, 1.5, true, 55)]
        [TestCase(200, 2.0, true, 74)]
        [TestCase(1100, 2.0, true, 74)]
        [TestCase(200, 1.5, false, 55)]
        public void LegacyPenaltyIsIgnoredAndAllSourcesScaleOnceBeforeFinalTruncation(int startingPower, double modifier, bool halve, int expected)
        {
            GamePlayer player = MeasurementAnimist(true, startingPower);
            player.ItemBonus[eProperty.PowerRegenerationAmount] = 3;
            player.AbilityBonus[eProperty.PowerRegenerationAmount] = 2;
            player.SpecBuffBonusCategory[eProperty.PowerRegenerationAmount] = 4;
            DOL.GS.ServerProperties.Properties.MANA_REGEN_AMOUNT_MODIFIER = modifier;
            DOL.GS.ServerProperties.Properties.MANA_REGEN_AMOUNT_HALVED_BELOW_50_PERCENT = halve;
            Assert.That(player.GetModified(eProperty.PowerRegenerationAmount), Is.EqualTo(expected));
            player.LastAttackedByEnemyTickPvE = GameLoop.GameLoopTime;
            Apply(player);
            Assert.That(player.GetModified(eProperty.PowerRegenerationAmount), Is.EqualTo(expected));
        }

        [Test]
        public void CrossingHalfPowerDoesNotChangeRegeneration()
        {
            GamePlayer player = MeasurementAnimist(true, 999);
            player.StartPowerRegeneration();
            Time(PowerTimer(player).NextTick); PowerTimer(player).Tick();
            Assert.That(player.Mana, Is.EqualTo(1034));
            Time(PowerTimer(player).NextTick); PowerTimer(player).Tick();
            Assert.That(player.Mana, Is.EqualTo(1069));
            player.Mana = 1000;
            Assert.That(player.GetModified(eProperty.PowerRegenerationAmount), Is.EqualTo(35));
            player.Mana = 999;
            Assert.That(player.GetModified(eProperty.PowerRegenerationAmount), Is.EqualTo(35));
        }

        [Test]
        public void OocActivationThenCombatPreservesPhaseOnExpiry()
        {
            GamePlayer player = MeasurementAnimist(true);
            player.StartPowerRegeneration();
            long originalDue = PowerTimer(player).NextTick;
            Time(originalDue - 100); // Start OOC, preserving a tick due in 100 ms.
            Apply(player);
            Assert.That(PowerTimer(player).NextTick, Is.EqualTo(originalDue));
            player.LastAttackedByEnemyTickPvE = GameLoop.GameLoopTime;
            long start = GameLoop.GameLoopTime;
            var ticks = Measure(player, true);
            Assert.That(ManaRoots.IsRestoring(player), Is.False);
            long lastPowerTick = start + ticks.Last().At;
            Assert.That(PowerTimer(player).NextTick - lastPowerTick, Is.EqualTo(7000));
            Assert.That(PowerTimer(player).NextTick - GameLoop.GameLoopTime, Is.EqualTo(4100));
            TestContext.WriteLine("OBSERVED_EXPIRY_GAP_MS " + (PowerTimer(player).NextTick - lastPowerTick));
        }

        [Test]
        public void LateExpiryCleanupDoesNotResetAnAlreadyNativeTimer()
        {
            GamePlayer player = MeasurementAnimist(true);
            player.LastAttackedByEnemyTickPvE = GameLoop.GameLoopTime;
            var (effect, _) = Apply(player);
            long expiry = effect.ExpireTick;
            while (PowerTimer(player).NextTick < expiry)
            {
                Time(PowerTimer(player).NextTick);
                player.LastAttackedByEnemyTickPvE = GameLoop.GameLoopTime;
                PowerTimer(player).Tick();
            }
            Time(expiry + 1500); // A late game-loop frame.
            player.LastAttackedByEnemyTickPvE = GameLoop.GameLoopTime;
            PowerTimer(player).RefreshInterval(); // TimerService reconciles native cadence before checking due.
            if (GameServiceUtils.ShouldTick(PowerTimer(player).NextTick)) PowerTimer(player).Tick();
            long nativeDue = PowerTimer(player).NextTick;
            int powerBeforeCleanup = player.Mana;
            TickActualEffects(player);
            Assert.That(player.Mana, Is.EqualTo(powerBeforeCleanup));
            Assert.That(PowerTimer(player).NextTick - nativeDue, Is.Zero);
            Assert.That(Interval(player), Is.EqualTo(7000));
        }

        [Test]
        public void RegenerationThreeExpiredActivationCyclesHaveNoBonusOrRootLeak()
        {
            GamePlayer player = MeasurementAnimist(true);
            for (int cycle = 0; cycle < 3; cycle++)
            {
                player.LastAttackedByEnemyTickPvE = GameLoop.GameLoopTime;
                Apply(player);
                Assert.That(player.effectListComponent.GetEffects().Count(e => e.EffectType == eEffect.ManaRoots), Is.EqualTo(1));
                Measure(player, true);
                Assert.That(ManaRoots.ActiveEffect(player), Is.Null);
                Assert.That(player.BaseBuffBonusCategory[eProperty.PowerRegenerationAmount], Is.EqualTo(5));
                Assert.That(player.BuffBonusMultCategory1.Get((int)eProperty.MaxSpeed), Is.EqualTo(1));
                Assert.That(Interval(player), Is.EqualTo(7000));
            }
        }

        [Test]
        public void RegenerationCancellingPendingStartCannotLeaveARegenOrMovementOverride()
        {
            GamePlayer player = MeasurementAnimist(true);
            player.LastAttackedByEnemyTickPvE = GameLoop.GameLoopTime;
            var handler = new VisualHandler(player);
            handler.ApplyEffectOnTarget(player); // Effect start hook is still queued.
            player.effectListComponent.CancelAll();
            player.effectListComponent.BeginTick();
            Assert.That(ManaRoots.IsRestoring(player), Is.False);
            Assert.That(Interval(player), Is.EqualTo(7000));
            Assert.That(player.BuffBonusMultCategory1.Get((int)eProperty.MaxSpeed), Is.EqualTo(1));
        }

        [TestCase(5)]
        [TestCase(9)]
        public void RegenerationStonePreservesEqualOrStrongerNativePowerBuffAndItsExpiry(int value)
        {
            GamePlayer player = MeasurementAnimist();
            var native = new PowerRegenSpellHandler(player,
                new Spell(new DbSpell { SpellID = 4439, Name = "Native power regen", Type = "PowerRegenBuff", Value = value, Duration = 1200, Target = "Realm", EffectGroup = 60 }, 44),
                new SpellLine("Holism", "Holism", "", false));
            native.ApplyEffectOnTarget(player); player.effectListComponent.BeginTick();
            ECSGameSpellEffect existing = player.effectListComponent.GetSpellEffects().Single(e => e.EffectType == eEffect.PowerRegenBuff);
            ApplyActualStonePowerBuff(player);
            Assert.That(player.effectListComponent.GetSpellEffects().Single(e => e.EffectType == eEffect.PowerRegenBuff), Is.SameAs(existing));
            Assert.That(existing.IsBeezBuff, Is.False);
            Assert.That(player.BaseBuffBonusCategory[eProperty.PowerRegenerationAmount], Is.EqualTo(value));
            Time(existing.ExpireTick); TickActualEffects(player);
            Assert.That(player.BaseBuffBonusCategory[eProperty.PowerRegenerationAmount], Is.Zero);
            Assert.That(player.effectListComponent.ContainsEffectForEffectType(eEffect.PowerRegenBuff), Is.False);
        }
        [TestCase(false, false, 20, 600)]
        [TestCase(true, false, 20, 600)]
        [TestCase(false, true, 8, 240)]
        [TestCase(true, true, 12, 360)]
        public void HealthUsesNewAmountsAndCadence(bool sitting, bool combat, int expectedTicks, int expectedGain)
        {
            double previous = DOL.GS.ServerProperties.Properties.HEALTH_REGEN_AMOUNT_MODIFIER;
            try
            {
                DOL.GS.ServerProperties.Properties.HEALTH_REGEN_AMOUNT_MODIFIER = 1;
                GamePlayer player = MeasurementAnimist();
                player.AbilityBonus[eProperty.MaxHealth] += 2000 - player.MaxHealth;
                player.StopHealthRegeneration();
                player.Health = 100;
                player.IsSitting = sitting;
                if (combat) player.LastAttackedByEnemyTickPvE = GameLoop.GameLoopTime;
                ECSGameTimer timer = (ECSGameTimer)typeof(GameLiving).GetField("m_healthRegenerationTimer", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(player);
                player.StopHealthRegeneration(); player.StartHealthRegeneration();
                long start = GameLoop.GameLoopTime;
                int ticks = 0;
                for (int elapsed = 100; elapsed <= 60000; elapsed += 100)
                {
                    Time(start + elapsed);
                    if (combat) player.LastAttackedByEnemyTickPvE = GameLoop.GameLoopTime;
                    timer.RefreshInterval();
                    if (GameServiceUtils.ShouldTick(timer.NextTick)) { timer.Tick(); ticks++; }
                }
                Assert.That(ticks, Is.EqualTo(expectedTicks));
                Assert.That(player.Health - 100, Is.EqualTo(expectedGain));
            }
            finally { DOL.GS.ServerProperties.Properties.HEALTH_REGEN_AMOUNT_MODIFIER = previous; }
        }

        [TestCase(eProperty.HealthRegenerationAmount, 60)]
        [TestCase(eProperty.PowerRegenerationAmount, 52)]
        public void HealthAndPowerAidChannelsAndSignedDebuffsScaleOnce(eProperty property, int expected)
        {
            double previous = DOL.GS.ServerProperties.Properties.HEALTH_REGEN_AMOUNT_MODIFIER;
            try
            {
                DOL.GS.ServerProperties.Properties.HEALTH_REGEN_AMOUNT_MODIFIER = 1.5;
                DOL.GS.ServerProperties.Properties.MANA_REGEN_AMOUNT_MODIFIER = 1.5;
                GamePlayer player = MeasurementAnimist();
                player.BaseBuffBonusCategory[property] = 5;
                player.AbilityBonus[property] = 2;
                player.ItemBonus[property] = 3;
                foreach (int sign in new[] { -1, 1 })
                {
                    player.SpecBuffBonusCategory[property] = 5 * sign;
                    Assert.That(player.GetModified(property), Is.EqualTo(expected));
                }
            }
            finally { DOL.GS.ServerProperties.Properties.HEALTH_REGEN_AMOUNT_MODIFIER = previous; }
        }

        [Test]
        public void EnduranceAidsAndModifierRemainIndependentOfHealthPowerDoubling()
        {
            double previous = DOL.GS.ServerProperties.Properties.ENDURANCE_REGEN_AMOUNT_MODIFIER;
            try
            {
                DOL.GS.ServerProperties.Properties.ENDURANCE_REGEN_AMOUNT_MODIFIER = 1.5;
                GamePlayer player = MeasurementAnimist();
                player.BaseBuffBonusCategory[eProperty.EnduranceRegenerationAmount] = 5;
                player.AbilityBonus[eProperty.EnduranceRegenerationAmount] = 1;
                player.ItemBonus[eProperty.EnduranceRegenerationAmount] = 2;
                player.SpecBuffBonusCategory[eProperty.EnduranceRegenerationAmount] = 3;
                Assert.That(player.GetModified(eProperty.EnduranceRegenerationAmount), Is.EqualTo(13));
                player.LastAttackedByEnemyTickPvE = GameLoop.GameLoopTime;
                Assert.That(player.GetModified(eProperty.EnduranceRegenerationAmount), Is.EqualTo(7));
            }
            finally { DOL.GS.ServerProperties.Properties.ENDURANCE_REGEN_AMOUNT_MODIFIER = previous; }
        }

        [Test]
        public void CombatTransitionsRephaseWithoutRestartingHealthOrPowerTimers()
        {
            GamePlayer player = MeasurementAnimist();
            player.StartPowerRegeneration();
            ECSGameTimer timer = PowerTimer(player);
            long start = GameLoop.GameLoopTime;
            Time(start + 1000);
            player.LastAttackedByEnemyTickPvE = GameLoop.GameLoopTime;
            timer.RefreshInterval();
            Assert.That(timer.NextTick, Is.EqualTo(start + 7000));
            Time(timer.NextTick); timer.Tick();
            player.LastAttackedByEnemyTickPvE = 0;
            timer.RefreshInterval();
            Assert.That(timer.NextTick, Is.EqualTo(start + 10000));
            Time(timer.NextTick); timer.Tick();
            Assert.That(player.Mana, Is.EqualTo(250));
            long due = timer.NextTick;
            timer.RefreshInterval();
            Assert.That(timer.NextTick, Is.EqualTo(due));
        }

        [TestCase(false, false, 240)]
        [TestCase(true, false, 240)]
        [TestCase(false, true, 240)]
        public void EnduranceRecoveryUsesOneSecondClockWhileStandingSittingOrMoving(bool sitting, bool moving, int expectedGain)
        {
            double previous = DOL.GS.ServerProperties.Properties.ENDURANCE_REGEN_AMOUNT_MODIFIER;
            try
            {
                DOL.GS.ServerProperties.Properties.ENDURANCE_REGEN_AMOUNT_MODIFIER = 1;
                GamePlayer player = MeasurementAnimist();
                player.IsSitting = sitting;
                player.CurrentSpeed = (short)(moving ? 100 : 0);
                Assert.That(player.IsMoving, Is.EqualTo(moving));
                player.DBMaxEndurance = 100;
                Assert.That(player.MaxEndurance, Is.EqualTo(100));
                player.Endurance = 50;
                ECSGameTimer timer = (ECSGameTimer)typeof(GameLiving).GetField("m_enduRegenerationTimer", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(player);
                player.StopEnduranceRegeneration(); player.StartEnduranceRegeneration();
                long start = GameLoop.GameLoopTime;
                int gain = 0;
                for (int second = 1; second <= 60; second++)
                {
                    Time(start + second * 1000);
                    Assert.That(GameServiceUtils.ShouldTick(timer.NextTick), Is.True);
                    timer.Tick();
                    gain += player.Endurance - 50;
                    player.Endurance = 50; // Controlled spending prevents the 100-point pool cap.
                }
                Assert.That(gain, Is.EqualTo(expectedGain));
                Assert.That(timer.Interval, Is.EqualTo(1000));
            }
            finally { DOL.GS.ServerProperties.Properties.ENDURANCE_REGEN_AMOUNT_MODIFIER = previous; }
        }

        [TestCase("True")]
        [TestCase("False")]
        public void LegacySavedPenaltyValueRemainsReadableButCannotChangeRecovery(string savedValue)
        {
            var field = typeof(DOL.GS.ServerProperties.Properties).GetField("MANA_REGEN_AMOUNT_HALVED_BELOW_50_PERCENT");
            var attribute = field.GetCustomAttribute<DOL.GS.ServerProperties.ServerPropertyAttribute>();
            Assert.That(attribute.DefaultValue, Is.EqualTo(false));
            Assert.That(attribute.Key, Is.EqualTo("mana_regen_amount_halved_below_50_percent"));
            // Same typed conversion used by the unchanged server-property loader.
            field.SetValue(null, Convert.ChangeType(savedValue, attribute.DefaultValue.GetType()));
            GamePlayer player = MeasurementAnimist();
            field.SetValue(null, Convert.ChangeType(savedValue, attribute.DefaultValue.GetType()));
            Assert.That(player.GetModified(eProperty.PowerRegenerationAmount), Is.EqualTo(25));
            Assert.That(typeof(GamePlayer).GetProperty("DBCharacter", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(player), Is.Not.Null);
            Assert.That(player.Level, Is.EqualTo(50));
        }

        [TestCase(false, 1000)]
        [TestCase(true, 1)]
        public void BotStyleImmediateFirstRecoveryTickCanBePreserved(bool preserve, int expectedDelay)
        {
            var timer = new ECSGameTimer(null, _ => 1000)
            {
                IntervalProvider = () => 1000,
                PreserveInitialTick = preserve
            };
            try
            {
                long start = GameLoop.GameLoopTime;
                timer.Start(1);
                timer.RefreshInterval();
                Assert.That(timer.NextTick - start, Is.EqualTo(expectedDelay));
                Time(timer.NextTick); timer.Tick(); timer.RefreshInterval();
                Assert.That(timer.NextTick - GameLoop.GameLoopTime, Is.EqualTo(1000));
            }
            finally { timer.Stop(); }
        }

    }
}
