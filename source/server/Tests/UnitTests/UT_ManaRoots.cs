using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using DOL.Database;
using DOL.GS;
using DOL.GS.PacketHandler;
using DOL.GS.PlayerClass;
using DOL.GS.PropertyCalc;
using DOL.GS.ServerRules;
using DOL.GS.Spells;
using NUnit.Framework;

namespace DOL.UnitTests
{
    [TestFixture, NonParallelizable]
    public class UT_ManaRoots
    {
        private sealed class TestServer : GameServer
        {
            protected override IServerRules ServerRulesImpl => new NormalServerRules();
            protected override IObjectDatabase DataBaseImpl => EmptyDatabase;
        }
        private static readonly IObjectDatabase EmptyDatabase = DispatchProxy.Create<IObjectDatabase, EmptyProxy>();
        public class EmptyProxy : DispatchProxy
        {
            public readonly List<DataObject> Writes = new();
            protected override object Invoke(MethodInfo method, object[] args)
            {
                if (method.Name == "AddObject" && args[0] is DataObject row)
                {
                    Writes.Add(row);
                    return true;
                }
                Type type = method.ReturnType;
                if (type == typeof(void)) return null;
                if (type.IsGenericType && typeof(IEnumerable).IsAssignableFrom(type))
                    return Activator.CreateInstance(typeof(List<>).MakeGenericType(type.GetGenericArguments()[0]));
                return type.IsValueType ? Activator.CreateInstance(type) : null;
            }
        }
        private readonly List<GamePlayer> _actors = new();
        private GameServer _oldServer;
        private long _oldTime;
        private bool _oldHalving;
        private double _oldModifier;
        private object _oldTranslations;
        private string _oldLanguage;
        private IPropertyCalculator[] _oldCalculators;
        [SetUp]
        public void SetUp()
        {
            _oldTime = GameLoop.GameLoopTime;
            Time(100000);
            _oldHalving = DOL.GS.ServerProperties.Properties.MANA_REGEN_AMOUNT_HALVED_BELOW_50_PERCENT;
            _oldModifier = DOL.GS.ServerProperties.Properties.MANA_REGEN_AMOUNT_MODIFIER;
            DOL.GS.ServerProperties.Properties.MANA_REGEN_AMOUNT_HALVED_BELOW_50_PERCENT = false;
            DOL.GS.ServerProperties.Properties.MANA_REGEN_AMOUNT_MODIFIER = 1;
            ((EmptyProxy)EmptyDatabase).Writes.Clear();
            _oldLanguage = DOL.GS.ServerProperties.Properties.SERV_LANGUAGE;
            DOL.GS.ServerProperties.Properties.SERV_LANGUAGE = "EN";
            var translations = typeof(DOL.Language.LanguageMgr).GetProperty("Translations");
            _oldTranslations = translations.GetValue(null);
            if (_oldTranslations == null) translations.SetValue(null, Activator.CreateInstance(translations.PropertyType));
            _oldServer = GameServer.Instance;
            GameServer.LoadTestDouble((TestServer)RuntimeHelpers.GetUninitializedObject(typeof(TestServer)));
            var calculators = (IPropertyCalculator[])typeof(GameLiving).GetField("m_propertyCalc", BindingFlags.Static | BindingFlags.NonPublic).GetValue(null);
            _oldCalculators = (IPropertyCalculator[])calculators.Clone();
            Assert.That(GameLiving.LoadCalculators(), Is.True);
        }
        [TearDown]
        public void TearDown()
        {
            foreach (GamePlayer actor in _actors)
            {
                foreach (ECSGameEffect effect in actor.effectListComponent.GetEffects()) effect.End();
                actor.effectListComponent.BeginTick();
                ((ECSGameTimer)typeof(GamePlayer).GetField("m_combatTimer", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(actor)).Stop();
                actor.StopHealthRegeneration();
                actor.StopPowerRegeneration();
                actor.StopEnduranceRegeneration();
                ServiceObjectStore.Remove(actor.effectListComponent);
                ServiceObjectStore.Remove(actor.castingComponent);
            }
            _actors.Clear();
            Time(_oldTime);
            DOL.GS.ServerProperties.Properties.MANA_REGEN_AMOUNT_HALVED_BELOW_50_PERCENT = _oldHalving;
            DOL.GS.ServerProperties.Properties.MANA_REGEN_AMOUNT_MODIFIER = _oldModifier;
            var calculators = (IPropertyCalculator[])typeof(GameLiving).GetField("m_propertyCalc", BindingFlags.Static | BindingFlags.NonPublic).GetValue(null);
            Array.Copy(_oldCalculators, calculators, calculators.Length);
            GameServer.LoadTestDouble(_oldServer);
            DOL.GS.ServerProperties.Properties.SERV_LANGUAGE = _oldLanguage;
            typeof(DOL.Language.LanguageMgr).GetProperty("Translations").SetValue(null, _oldTranslations);
        }

        private static void Field(Type type, object target, string name, object value) =>
            type.GetField(name, BindingFlags.Instance | BindingFlags.NonPublic)!.SetValue(target, value);

        private GamePlayer Player(int level = 50, eRealm realm = eRealm.Albion, ICharacterClass characterClass = null)
        {
            GamePlayer player = characterClass == null ? GamePlayer.CreateTestableGamePlayer() : GamePlayer.CreateTestableGamePlayer(characterClass);
            Field(typeof(GamePlayer), player, "m_dbCharacter", new DbCoreCharacter { Level = level, Realm = (int)realm, Name = "Human", Health = 1 });
            GameClient client = (GameClient)RuntimeHelpers.GetUninitializedObject(typeof(GameClient));
            Field(typeof(GameClient), client, "<Account>k__BackingField", new DbAccount { Language = "EN", PrivLevel = 1 });
            client.Out = DispatchProxy.Create<IPacketLib, EmptyProxy>();
            Field(typeof(GamePlayer), player, "m_client", client);
            Field(typeof(GamePlayer), player, "m_steed", new WeakReference(null));
            Field(typeof(GameLiving), player, "m_inventory", new GamePlayerInventory(player));
            player.ObjectState = GameObject.eObjectState.Active;
            Field(typeof(GamePlayer), player, "m_combatTimer", new ECSGameTimer(player, _ => 0));
            player.Health = 100;
            player.ItemBonus[eProperty.MaxMana] = 1000;
            _actors.Add(player);
            return player;
        }


        private static void Time(long value) => typeof(GameLoop).GetProperty(nameof(GameLoop.GameLoopTime)).SetValue(null, value);
        private static int Interval(GamePlayer player, string kind = "Power") =>
            (int)typeof(GamePlayer).GetMethod("Get" + kind + "RegenerationInterval", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(player, null);
        private GamePlayer Animist(int level = 50) => Player(level, eRealm.Hibernia, new ClassAnimist());
        private static SpellLine Line() => new(ManaRoots.LineKey, "Mana Roots", "", true) { Level = 50 };

        private class VisualHandler : ManaRootsSpellHandler
        {
            public List<(ushort Id, bool Quiet)> Visuals = new();
            public VisualHandler(GameLiving owner) : base(owner, ManaRoots.CreateSpell(), Line()) { }
            public override void SendEffectAnimation(GameObject target, ushort clientEffect, ushort boltDuration, bool noSound, byte success)
            {
                Assert.That(target, Is.SameAs(Caster));
                Assert.That(boltDuration, Is.Zero);
                Assert.That(success, Is.EqualTo(1));
                Visuals.Add((clientEffect, noSound));
            }
        }

        private static (ManaRootsECSEffect Effect, VisualHandler Handler) Apply(GamePlayer player)
        {
            var handler = new VisualHandler(player);
            handler.ApplyEffectOnTarget(player);
            player.effectListComponent.BeginTick();
            return (ManaRoots.ActiveEffect(player), handler);
        }

        [Test]
        public void SpellHasExactlyTheApprovedSingleRank()
        {
            Spell spell = ManaRoots.CreateSpell();
            Assert.Multiple(() =>
            {
                Assert.That(spell.Level, Is.EqualTo(15));
                Assert.That(spell.Duration, Is.EqualTo(60000));
                Assert.That(spell.CastTime, Is.Zero);
                Assert.That(spell.Power, Is.Zero);
                Assert.That(spell.RecastDelay, Is.Zero);
                Assert.That(spell.SharedTimerGroup, Is.Zero);
                Assert.That(spell.Concentration, Is.Zero);
                Assert.That(spell.Pulse, Is.Zero);
                Assert.That(spell.SpellType, Is.EqualTo(eSpellType.ManaRoots));
                Assert.That(spell.Target, Is.EqualTo(eSpellTarget.SELF));
                Assert.That(spell.ClientEffect, Is.EqualTo(5201));
            });
        }

        [TestCase(14, false)]
        [TestCase(15, true)]
        [TestCase(30, true)]
        [TestCase(40, true)]
        [TestCase(50, true)]
        public void ListCasterGetsOneSpellByCharacterLevel(int level, bool eligible)
        {
            GamePlayer player = Animist(level);
            var lists = player.GetAllUsableListSpells(true);
            var spells = lists.Where(entry => entry.Item1.KeyName == ManaRoots.LineKey).SelectMany(entry => entry.Item2).OfType<Spell>().ToList();
            Assert.That(spells.Count, Is.EqualTo(eligible ? 1 : 0));
            if (eligible) Assert.That(spells.Single().ID, Is.EqualTo(ManaRoots.SpellId));
            Assert.That(player.GetAllUsableListSpells(true).Count(entry => entry.Item1.KeyName == ManaRoots.LineKey), Is.EqualTo(eligible ? 1 : 0));
            Assert.That(((EmptyProxy)EmptyDatabase).Writes, Is.Empty);
        }

        [Test]
        public void ForeignClassLowLevelAndOtherTargetsCannotReceiveRoots()
        {
            GamePlayer foreign = Player();
            GamePlayer low = Animist(14);
            Assert.That(foreign.GetAllUsableListSpells(true).Any(entry => entry.Item1.KeyName == ManaRoots.LineKey), Is.False);
            Assert.That(Apply(foreign).Effect, Is.Null);
            Assert.That(Apply(low).Effect, Is.Null);
            GamePlayer caster = Animist();
            var handler = new VisualHandler(caster);
            handler.ApplyEffectOnTarget(foreign);
            foreign.effectListComponent.BeginTick();
            Assert.That(foreign.effectListComponent.ContainsEffectForEffectType(eEffect.ManaRoots), Is.False);
            Assert.That(handler.Visuals, Is.Empty);
        }

        [TestCase(0, 0, 0, 0)]
        [TestCase(5, 3, 2, 0)]
        [TestCase(5, 3, 2, 6)]
        [TestCase(0, 0, 0, 100)]
        public void RestoresNativeOocRateWithoutDuplicatingOrSuppressingSources(int buff, int item, int ability, int debuff)
        {
            GamePlayer player = Animist();
            player.BaseBuffBonusCategory[eProperty.PowerRegenerationAmount] = buff;
            player.ItemBonus[eProperty.PowerRegenerationAmount] = item;
            player.AbilityBonus[eProperty.PowerRegenerationAmount] = ability;
            player.SpecBuffBonusCategory[eProperty.PowerRegenerationAmount] = debuff;
            int amount = player.GetModified(eProperty.PowerRegenerationAmount);
            Assert.That(Interval(player), Is.EqualTo(6000));
            player.LastAttackTickPvE = GameLoop.GameLoopTime;
            Assert.That(Interval(player), Is.EqualTo(14000));
            var (effect, _) = Apply(player);
            Assert.That(effect, Is.Not.Null);
            Assert.Multiple(() =>
            {
                Assert.That(Interval(player), Is.EqualTo(6000));
                Assert.That(Interval(player, "Health"), Is.EqualTo(14000));
                Assert.That(player.GetModified(eProperty.PowerRegenerationAmount), Is.EqualTo(amount));
                Assert.That(player.InCombat, Is.True);
                Assert.That(player.LastAttackTickPvE, Is.EqualTo(100000));
            });
            long expiry = effect.ExpireTick;
            player.LastAttackTickPvE = 0;
            Assert.That(Interval(player), Is.EqualTo(6000));
            Assert.That(effect.ExpireTick, Is.EqualTo(expiry));
            player.LastAttackedByEnemyTickPvP = GameLoop.GameLoopTime;
            Assert.That(Interval(player), Is.EqualTo(6000));
            Assert.That(effect.ExpireTick, Is.EqualTo(expiry));
            effect.End();
            player.effectListComponent.BeginTick();
            Assert.That(Interval(player), Is.EqualTo(14000));
            Assert.That(player.GetModified(eProperty.PowerRegenerationAmount), Is.EqualTo(amount));
        }

        [Test]
        public void LowPowerPenaltyModifierAndSittingRetainNativeFormulas()
        {
            GamePlayer player = Animist();
            player.IsSitting = true;
            player.LastAttackTickPvE = GameLoop.GameLoopTime;
            Assert.That(Interval(player), Is.EqualTo(10000));
            DOL.GS.ServerProperties.Properties.MANA_REGEN_AMOUNT_HALVED_BELOW_50_PERCENT = true;
            DOL.GS.ServerProperties.Properties.MANA_REGEN_AMOUNT_MODIFIER = 2;
            int amount = player.GetModified(eProperty.PowerRegenerationAmount);
            Apply(player);
            Assert.That(Interval(player), Is.EqualTo(3000));
            Assert.That(Interval(player, "Health"), Is.EqualTo(10000));
            Assert.That(player.GetModified(eProperty.PowerRegenerationAmount), Is.EqualTo(amount));
        }

        [Test]
        public void ActivationIsNotInstantManaAndNativeCallbackAwardsOnlyOneTick()
        {
            GamePlayer player = Animist();
            player.Mana = 100;
            player.LastAttackTickPvE = GameLoop.GameLoopTime;
            Apply(player);
            Assert.That(player.Mana, Is.EqualTo(100));
            int amount = player.GetModified(eProperty.PowerRegenerationAmount);
            int interval = (int)typeof(GameLiving).GetMethod("PowerRegenerationTimerCallback", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(player, new object[] { null });
            Assert.That(player.Mana, Is.EqualTo(100 + amount));
            Assert.That(interval, Is.EqualTo(6000));
        }

        [Test]
        public void RootIsIndependentUnbreakableUncancelableAndSessionOnly()
        {
            GamePlayer player = Animist();
            var (effect, handler) = Apply(player);
            Assert.That(player.BuffBonusMultCategory1.Get((int)eProperty.MaxSpeed), Is.Zero);
            Assert.That(player.IsCrowdControlled, Is.False);
            Assert.That(handler.IsUnPurgeAble, Is.True);
            Assert.That(effect.End(true), Is.False);
            Assert.That(player.MountSteed(new GameNPC(), false), Is.False);
            player.HandleCrowdControlOnAttacked(new AttackData { AttackResult = eAttackResult.HitUnstyled, AttackType = AttackData.eAttackType.MeleeOneHand, Damage = 10 });
            player.effectListComponent.BeginTick();
            Assert.That(ManaRoots.ActiveEffect(player), Is.SameAs(effect));
            var ordinary = new SpellHandler(player, new Spell(new DbSpell { SpellID = 5201, Type = "SpeedDecrease", Value = 99, Duration = 30, Target = "Enemy" }, 15), Line());
            Assert.That(handler.HasConflictingEffectWith(ordinary), Is.False);
            var otherRoot = ECSGameEffectFactory.Create(new(player, 30000, 1, ordinary), static (in i) => new StatDebuffECSEffect(i));
            player.effectListComponent.BeginTick();
            effect.End();
            player.effectListComponent.BeginTick();
            Assert.That(player.BuffBonusMultCategory1.Get((int)eProperty.MaxSpeed), Is.EqualTo(0.01).Within(0.000001));
            Assert.That(effect.GetSavedEffect(), Is.Null);
            Assert.That(effect.ShouldBeAddedToConcentrationList(), Is.False);
            Assert.That(effect.ShouldBeRemovedFromConcentrationList(), Is.False);
            otherRoot.End();
            player.effectListComponent.BeginTick();
            Assert.That(((EmptyProxy)EmptyDatabase).Writes, Is.Empty);
        }

        [Test]
        public void PurgeCannotReleaseManaRoots()
        {
            GamePlayer player = Animist();
            var (effect, _) = Apply(player);
            Type purge = typeof(DOL.GS.RealmAbilities.PurgeAbility);
            purge.GetMethod("RemoveNegativeEffects", BindingFlags.Static | BindingFlags.NonPublic).Invoke(null, new object[] { player, null, true });
            player.effectListComponent.BeginTick();
            Assert.That(ManaRoots.ActiveEffect(player), Is.SameAs(effect));
        }

        [Test]
        public void RecastRefreshesSameRootWithoutStackingOrReleasingMovement()
        {
            GamePlayer player = Animist();
            var (effect, handler) = Apply(player);
            Time(110000);
            handler.ApplyEffectOnTarget(player);
            player.effectListComponent.BeginTick();
            Assert.That(ManaRoots.ActiveEffect(player), Is.SameAs(effect));
            Assert.That(effect.ExpireTick, Is.EqualTo(170000));
            Assert.That(player.effectListComponent.GetEffects().Count(e => e.EffectType == eEffect.ManaRoots), Is.EqualTo(1));
            Assert.That(player.BuffBonusMultCategory1.Get((int)eProperty.MaxSpeed), Is.Zero);
        }

        [Test]
        public void ApprovedVisualsPulseQuietlyWithoutCatchupOrPostExpiryScheduling()
        {
            GamePlayer player = Animist();
            var (effect, handler) = Apply(player);
            Assert.That(handler.Visuals, Is.EqualTo(new[] { ((ushort)5201, false), ((ushort)4435, false) }));
            Time(107999); effect.OnEffectPulse();
            Assert.That(handler.Visuals.Count, Is.EqualTo(2));
            Time(108000); effect.OnEffectPulse();
            Assert.That(handler.Visuals.Last(), Is.EqualTo(((ushort)4435, true)));
            Time(140000); effect.OnEffectPulse();
            Assert.That(handler.Visuals.Count, Is.EqualTo(4)); // One packet, not four catch-up packets.
            Time(157000); effect.OnEffectPulse();
            Assert.That(handler.Visuals.Count, Is.EqualTo(4)); // Less than the catalog lifetime remains.
            effect.End(); player.effectListComponent.BeginTick();
            Time(170000); effect.OnEffectPulse();
            Assert.That(handler.Visuals.Count, Is.EqualTo(4));
        }

        [Test]
        public void NativeExpiryAndDeathLogoutCancellationRestoreMovementAndCadence()
        {
            GamePlayer player = Animist();
            player.LastAttackTickPvE = GameLoop.GameLoopTime;
            var (effect, handler) = Apply(player);
            Time(effect.ExpireTick);
            typeof(EffectService).GetMethod("TickSpellEffect", BindingFlags.Static | BindingFlags.NonPublic).Invoke(null, new object[] { effect });
            player.effectListComponent.BeginTick();
            Assert.That(effect.IsEnded, Is.True);
            Assert.That(player.BuffBonusMultCategory1.Get((int)eProperty.MaxSpeed), Is.EqualTo(1));
            Apply(player);
            player.effectListComponent.CancelAll(); // Native death/logout cleanup path.
            player.effectListComponent.BeginTick();
            Assert.That(ManaRoots.ActiveEffect(player), Is.Null);
            Assert.That(player.BuffBonusMultCategory1.Get((int)eProperty.MaxSpeed), Is.EqualTo(1));
        }
    }
}
