using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using DOL.Database;
using DOL.Database.Handlers;
using DOL.GS;
using DOL.GS.PacketHandler;
using DOL.GS.PropertyCalc;
using DOL.GS.ServerRules;
using DOL.GS.Spells;
using NUnit.Framework;

namespace DOL.UnitTests
{

    [TestFixture, NonParallelizable]
    public class UT_BeezOnline
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
        private object _oldTranslations;
        private string _oldLanguage;
        private IPropertyCalculator[] _oldCalculators;
        [SetUp]
        public void SetUp()
        {
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
                foreach (ECSGameSpellEffect effect in actor.effectListComponent.GetSpellEffects()) effect.End();
                actor.effectListComponent.BeginTick();
                actor.StopHealthRegeneration();
                actor.StopPowerRegeneration();
                actor.StopEnduranceRegeneration();
                ServiceObjectStore.Remove(actor.effectListComponent);
                ServiceObjectStore.Remove(actor.castingComponent);
            }
            _actors.Clear();
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
            _actors.Add(player);
            return player;
        }

        private static Spell Strength(int id = 1457, int value = 50, int duration = 1200) =>
            new(new DbSpell { SpellID = id, Type = "StrengthBuff", Target = "Realm", Value = value, Duration = duration,
                EffectGroup = 4, Icon = id }, 50);

        private static ECSGameSpellEffect StrengthEffect(GamePlayer player, bool stone, double effectiveness, int value = 50)
        {
            Spell spell = Strength(value: value);
            var handler = new StrengthBuff(player, spell, new SpellLine("Enhancement", "Enhancement", "Enhancement", true));
            if (stone)
                typeof(SpellHandler).GetProperty(nameof(SpellHandler.BeezApplication)).SetValue(handler, new BeezBuffs.Application(player, player.TempProperties.GetProperty<long>("beez.buff.session.generation")));
            return new StatBuffECSEffect(new(player, spell.Duration, effectiveness, handler));
        }

        [TestCase(1)]
        [TestCase(20)]
        [TestCase(50)]
        public void RingUsesExistingLevelCapsAndRemovesExactlyItsContribution(int level)
        {
            GamePlayer player = Player(level);
            GameInventoryItem ring = GameInventoryItem.Create(BeezDeveloperItems.Template(BeezDeveloperItems.RingId));
            BeezDeveloperItems.ApplyRingBonuses(player, ring, 1);
            Assert.That(new StatCalculator().CalcValueFromItems(player, eProperty.Strength), Is.EqualTo((int)(level * 1.5)));
            Assert.That(new ResistCalculator().CalcValueFromItems(player, eProperty.Resist_Heat), Is.EqualTo(level / 2 + 1));
            Assert.That(new SkillLevelCalculator().CalcValueFromItems(player, eProperty.Skill_Sword), Is.EqualTo(level / 5 + 1));
            Assert.That(MaxHealthCalculator.GetItemBonusCap(player), Is.EqualTo(level * 4));
            player.ItemBonus[eProperty.Strength] += 10;
            BeezDeveloperItems.ApplyRingBonuses(player, ring, -1);
            Assert.That(player.ItemBonus[eProperty.Strength], Is.EqualTo(10));
            Assert.That(player.ItemBonus[eProperty.Resist_Heat], Is.Zero);
            Assert.That(BeezDeveloperItems.RingBonuses().Select(x => x.Property).Distinct().Count(), Is.EqualTo(20));
        }

        [Test]
        public void OrdinaryItemsHaveNoDeveloperBonuses()
        {
            GamePlayer player = Player();
            BeezDeveloperItems.ApplyRingBonuses(player, GameInventoryItem.Create(new DbItemTemplate { Id_nb = "ordinary" }), 1);
            Assert.That(player.ItemBonus[eProperty.Strength], Is.Zero);
        }

        [TestCase(eRealm.Albion, 18)]
        [TestCase(eRealm.Midgard, 17)]
        [TestCase(eRealm.Hibernia, 16)]
        [TestCase(eRealm.None, 0)]
        public void VerifiedManifestIsUniqueAndExcludesCombatAndSongSpells(eRealm realm, int count)
        {
            var ids = BeezBuffs.Manifest(realm).Select(x => x.Id).ToArray();
            Assert.That(ids.Length, Is.EqualTo(count));
            Assert.That(ids.Distinct().Count(), Is.EqualTo(count));
            Assert.That(ids.Intersect(new[] { 3238, 3100, 3117, 10069, 113, 2723, 5123, 1085, 5165 }), Is.Empty);
        }

        [Test]
        public void StoneLifecycleDoesNotAlterNormalSpellDataOrEffects()
        {
            GamePlayer player = Player();
            ECSGameSpellEffect stone = StrengthEffect(player, true, 1.25);
            ECSGameSpellEffect normal = StrengthEffect(player, false, 1.25);
            Assert.That(stone.EffectType, Is.EqualTo(eEffect.StrengthBuff));
            Assert.That(stone.Duration, Is.Zero);
            Assert.That(stone.GetRemainingTimeForClient(), Is.Zero);
            Assert.That(stone.GetSavedEffect(), Is.Null);
            Assert.That(stone.IsConcentrationEffect(), Is.False);
            Assert.That(stone.ShouldBeAddedToConcentrationList(), Is.False);
            Assert.That(stone.SpellHandler.Spell.Duration, Is.EqualTo(1200000));
            Assert.That(normal.Duration, Is.EqualTo(1200000));
            Assert.That(normal.GetSavedEffect(), Is.Not.Null);
        }

        [Test]
        public void StoneConcentrationEffectsConsumeNoPoolOrSlots()
        {
            GamePlayer player = Player();
            Spell spell = new(new DbSpell { SpellID = 1457, Type = "StrengthBuff", Target = "Realm", Value = 50, Concentration = 19 }, 50);
            var handler = new StrengthBuff(player, spell, new SpellLine("Enhancement", "Enhancement", "Enhancement", true));
            typeof(SpellHandler).GetProperty(nameof(SpellHandler.BeezApplication)).SetValue(handler, new BeezBuffs.Application(player, 0));
            var effect = new StatBuffECSEffect(new(player, 0, 1.25, handler));
            Assert.That(handler.CheckConcentrationCost(true), Is.True);
            Assert.That(effect.IsConcentrationEffect(), Is.False);
            Assert.That(effect.ShouldBeAddedToConcentrationList(), Is.False);
            Assert.That(effect.SpellHandler.Spell.Concentration, Is.EqualTo(19));
        }

        [Test]
        public void StoneCannotDowngradeStrongerSameIdAndCanReplaceWeakerSameId()
        {
            GamePlayer player = Player();
            ECSGameSpellEffect strong = StrengthEffect(player, false, 1.5);
            strong.Start();
            ECSGameSpellEffect stone = StrengthEffect(player, true, 1.25);
            stone.Start();
            Assert.That(player.effectListComponent.GetSpellEffects(), Does.Contain(strong));
            Assert.That(player.effectListComponent.GetSpellEffects(), Does.Not.Contain(stone));
            strong.End();
            ECSGameSpellEffect weak = StrengthEffect(player, false, 1.0);
            weak.Start();
            ECSGameSpellEffect replacement = StrengthEffect(player, true, 1.25);
            replacement.Start();
            Assert.That(player.effectListComponent.GetSpellEffects(), Does.Contain(replacement));
            Assert.That(player.effectListComponent.GetSpellEffects(), Does.Not.Contain(weak));
            ECSGameSpellEffect repeated = StrengthEffect(player, true, 1.25);
            repeated.Start();
            Assert.That(player.effectListComponent.GetSpellEffects(), Does.Not.Contain(repeated));
        }

        [Test]
        public void LogoutCleanupInvalidatesPendingEffectsAndClearsDisabledOnes()
        {
            GamePlayer player = Player();
            ECSGameSpellEffect pending = StrengthEffect(player, true, 1.25);
            ECSGameSpellEffect active = StrengthEffect(player, true, 1.25);
            active.Start();
            active.Disable();
            BeezBuffs.Clear(player);
            pending.Start();
            Assert.That(player.effectListComponent.GetSpellEffects(), Is.Empty);
            Assert.That(pending.BeezApplication.IsValid, Is.False);
        }

        [Test]
        public void StoneSingleTargetContextRejectsAnotherPlayer()
        {
            GamePlayer owner = Player();
            GamePlayer other = Player();
            ECSGameSpellEffect effect = StrengthEffect(owner, true, 1.25);
            ((SpellHandler)effect.SpellHandler).ApplyEffectOnTarget(other);
            Assert.That(other.effectListComponent.GetSpellEffects(), Is.Empty);
        }

        [TestCase(eCharacterClass.Paladin, "Chants", true)]
        [TestCase(eCharacterClass.Minstrel, "Instruments", true)]
        [TestCase(eCharacterClass.Skald, "Battlesongs", true)]
        [TestCase(eCharacterClass.Bard, "Bard Nurture Spec", true)]
        [TestCase(eCharacterClass.Warden, "Nurture Warden Spec", true)]
        [TestCase(eCharacterClass.Theurgist, "Abrasion", false)]
        [TestCase(eCharacterClass.Friar, "Friar Enhancement Spec", false)]
        [TestCase(eCharacterClass.Warden, "Regrowth Warden Spec", false)]
        public void SongScopeIsRestrictedToApprovedClassAndLine(eCharacterClass cls, string line, bool expected)
        {
            Spell spell = new(new DbSpell { SpellID = 1, Type = "SpeedEnhancement", Target = "Group", Pulse = 1, Duration = 6 }, 1);
            Assert.That(BeezSongs.IsEligible(cls, spell, line), Is.EqualTo(expected));
        }

        [TestCase("Enemy", false)]
        [TestCase("Pet", false)]
        [TestCase("Self", false)]
        [TestCase("Group", true)]
        public void SongScopeDoesNotGrantHostilePetOrSelfPulseExceptions(string target, bool expected)
        {
            Spell spell = new(new DbSpell { SpellID = 1, Type = "DamageAdd", Target = target, Pulse = 1, Duration = 6 }, 1);
            Assert.That(BeezSongs.IsEligible(eCharacterClass.Paladin, spell, "Chants"), Is.EqualTo(expected));
        }

        [Test]
        public void PortalRejectsUnknownEndpointsAndDeadPlayers()
        {
            GamePlayer player = Player();
            Assert.That(BeezBindPortals.AllowedLocation(player, new(65535, 0, 0, 0, 0)), Is.False);
            player.ObjectState = GameObject.eObjectState.Inactive;
            Assert.That(BeezBindPortals.AllowedState(player), Is.False);
            Assert.That(BeezBindPortals.TryUse(player, GameInventoryItem.Create(new DbItemTemplate { Id_nb = "ordinary" }), 1), Is.False);
        }

        [Test]
        public void PortalSnapshotsPreserveHeadingAndRejectChangedBind()
        {
            GamePlayer player = Player();
            player.BindRegion = 1; player.BindXpos = 123; player.BindYpos = 456; player.BindZpos = 789; player.BindHeading = 1024;
            var snapshot = BeezBindPortals.BindPoint(player);
            Assert.That(snapshot, Is.EqualTo(new BeezBindPortals.Endpoint(1, 123, 456, 789, 1024)));
            player.BindXpos++;
            Assert.That(BeezBindPortals.BindPoint(player), Is.Not.EqualTo(snapshot));
        }

        private static ECSPulseEffect Pulse(GamePlayer player, int id, string type, string line = "Chants")
        {
            Spell spell = new(new DbSpell { SpellID = id, Type = type, Target = "Group", Pulse = 1,
                Duration = 6, Frequency = 6, PulsePower = 15 }, 50);
            var handler = new SpellHandler(player, spell, new SpellLine(line, line, line, true));
            return new ECSPulseEffect(new(player, 6000, 1, handler), 6000);
        }

        [Test]
        public void EligibleSongFamiliesCoexistAndOrdinaryPulseStillCancelsThem()
        {
            GamePlayer player = Player(characterClass: new DOL.GS.PlayerClass.ClassPaladin());
            ECSPulseEffect damage = Pulse(player, 90101, "DamageAdd");
            ECSPulseEffect heal = Pulse(player, 90102, "CombatHeal");
            Assert.That(damage.Start(), Is.True);
            Assert.That(heal.Start(), Is.True);
            player.effectListComponent.BeginTick();
            Assert.That(player.effectListComponent.GetPulseEffects(), Has.Count.EqualTo(2));
            Assert.That(player.BeezPulseSources.Count, Is.EqualTo(2));
            Assert.That(damage.ShouldBeAddedToConcentrationList(), Is.False);
            Assert.That(heal.SpellHandler.CheckConcentrationCost(true), Is.True);
            ECSPulseEffect ordinary = Pulse(player, 90103, "SpeedEnhancement", "unrelated");
            ordinary.Start();
            player.effectListComponent.BeginTick();
            Assert.That(player.effectListComponent.GetPulseEffects(), Does.Not.Contain(damage).And.Not.Contain(heal));
            Assert.That(player.BeezPulseSources, Is.Empty);
            Assert.That(BeezSongs.PulseCost(player, ordinary.SpellHandler.Spell), Is.EqualTo(15));
            ordinary.End();
            player.effectListComponent.BeginTick();
        }

        [Test]
        public void StoppingAnOldSongDoesNotUnregisterItsReplacement()
        {
            GamePlayer player = Player(characterClass: new DOL.GS.PlayerClass.ClassPaladin());
            ECSPulseEffect old = Pulse(player, 90111, "DamageAdd");
            ECSPulseEffect replacement = Pulse(player, 90112, "DamageAdd");
            old.OnStartEffect();
            replacement.OnStartEffect();
            old.OnStopEffect();
            Assert.That(player.ActivePulseSpells[eSpellType.DamageAdd], Is.SameAs(replacement.SpellHandler.Spell));
            Assert.That(BeezSongs.IsRegistered(player, replacement), Is.True);
            replacement.OnStopEffect();
            Assert.That(player.BeezPulseSources, Is.Empty);
        }

        [Test]
        public void StoneIgnoresItsOriginalExpirationAndPreservesNormalEffectsDuringCleanup()
        {
            GamePlayer player = Player();
            ECSGameSpellEffect stone = StrengthEffect(player, true, 1.25);
            Assert.That(stone.Start(), Is.True);
            player.effectListComponent.BeginTick();
            // Invoke the same expiry branch the effect service executes, with a due original deadline.
            stone.ExpireTick = GameLoop.GameLoopTime - 1;
            typeof(EffectService).GetMethod("TickSpellEffect", BindingFlags.Static | BindingFlags.NonPublic).Invoke(null, [stone]);
            EffectHelper.SaveAllEffects(player);
            Assert.That(((EmptyProxy)EmptyDatabase).Writes.OfType<DbPlayerXEffect>(), Is.Empty);
            Assert.That(stone.IsActive, Is.True);
            Assert.That(player.BaseBuffBonusCategory[eProperty.Strength], Is.EqualTo(62));
            BeezBuffs.Clear(player);
            player.effectListComponent.BeginTick();
            Assert.That(player.BaseBuffBonusCategory[eProperty.Strength], Is.Zero);
            ECSGameSpellEffect normal = StrengthEffect(player, false, 1.0);
            normal.Start();
            BeezBuffs.Clear(player);
            Assert.That(player.effectListComponent.GetSpellEffects(), Does.Contain(normal));
            normal.End();
            player.effectListComponent.BeginTick();
        }

        private sealed class PortalRegion : Region
        {
            private PortalRegion() : base(null) { }
            public bool Instance;
            public List<IArea> Areas = new();
            public override bool IsInstance => Instance;
            public override List<IArea> GetAreasOfSpot(IPoint3D point) => Areas;
        }

        [TestCase(1, 1, false, false, true)]
        [TestCase(1, 11, false, false, false)]
        [TestCase(1, 252, false, false, false)]
        [TestCase(497, 1, false, false, false)]
        [TestCase(1, 1, true, false, false)]
        [TestCase(1, 1, false, true, false)]
        public void PortalRechecksRestrictedLocations(int regionId, int zoneId, bool instance, bool keep, bool expected)
        {
            PortalRegion region = (PortalRegion)RuntimeHelpers.GetUninitializedObject(typeof(PortalRegion));
            Field(typeof(Region), region, "m_regionData", new RegionData { Id = (ushort)regionId });
            Field(typeof(Region), region, "m_zones", new List<Zone> { new(region, (ushort)zoneId, "test", 0, 0, 1000, 1000, 0, false, 0, false, 0, 0, 0, 0, 0) });
            region.Instance = instance;
            region.Areas = keep ? [(IArea)RuntimeHelpers.GetUninitializedObject(typeof(DOL.GS.Keeps.KeepArea))] : [];
            var regions = (System.Collections.Concurrent.ConcurrentDictionary<ushort, Region>)typeof(WorldMgr).GetField("m_regions", BindingFlags.Static | BindingFlags.NonPublic).GetValue(null);
            regions.TryGetValue((ushort)regionId, out Region previous);
            regions[(ushort)regionId] = region;
            try { Assert.That(BeezBindPortals.AllowedLocation(Player(), new((ushort)regionId, 100, 100, 0, 0)), Is.EqualTo(expected)); }
            finally
            {
                if (previous == null) regions.TryRemove((ushort)regionId, out _);
                else regions[(ushort)regionId] = previous;
            }
        }

        public sealed class VerifiedBuff
        {
            public string Line { get; set; }
            public int Level { get; set; }
            public bool BaseLine { get; set; }
            public DbSpell Spell { get; set; }
        }

        [Test]
        public void AllVerifiedRealmEntriesResolveTheirOriginalHandlerAndMetadata()
        {
            using var stream = typeof(UT_BeezOnline).Assembly.GetManifestResourceStream("Tests.Fixtures.BeezBuffSpells.json");
            Assert.That(stream, Is.Not.Null);
            var rows = System.Text.Json.JsonSerializer.Deserialize<VerifiedBuff[]>(stream);
            var manifest = new[] { eRealm.Albion, eRealm.Midgard, eRealm.Hibernia }.SelectMany(BeezBuffs.Manifest).ToArray();
            Assert.That(rows, Has.Length.EqualTo(51));
            Assert.That(manifest.Select(entry => (entry.Line, entry.Id)), Is.EquivalentTo(rows.Select(row => (row.Line, row.Spell.SpellID))));
            GamePlayer player = Player();
            foreach (VerifiedBuff row in rows)
            {
                Spell spell = new(row.Spell, row.Level);
                Assert.That(BeezBuffs.IsSupported(spell), Is.True, row.Spell.Name);
                Assert.That(spell.HasSubSpell, Is.False);
                var handler = ScriptMgr.CreateSpellHandler(player, spell, new SpellLine(row.Line, row.Line, row.Line, row.BaseLine));
                Assert.That(handler, Is.InstanceOf<SpellHandler>(), row.Spell.Name);
                typeof(SpellHandler).GetProperty(nameof(SpellHandler.BeezApplication)).SetValue(handler, new BeezBuffs.Application(player, 0));
                var effect = ((SpellHandler)handler).CreateECSEffect(new(player, spell.Duration, BeezBuffs.Effectiveness(spell), handler));
                Assert.That(effect.IsBeezBuff, Is.True);
                Assert.That(effect.Icon, Is.EqualTo(spell.Icon));
                Assert.That(effect.SpellHandler.Spell.EffectGroup, Is.EqualTo(spell.EffectGroup));
                Assert.That(effect.Duration, Is.Zero);
                Assert.That(effect.GetSavedEffect(), Is.Null);
            }
        }

        [Test]
        public void NewHumanItemsAreGrantedWithoutSavingAnythingForBotClients()
        {
            GamePlayer player = Player();
            BeezDeveloperItems.GrantCreated(new DOL.Events.CharacterEventArgs((DbCoreCharacter)typeof(GamePlayer).GetField("m_dbCharacter", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(player), player.Client));
            var items = ((EmptyProxy)EmptyDatabase).Writes.OfType<DbInventoryItem>().ToArray();
            Assert.That(items.Select(item => item.Id_nb), Is.EquivalentTo(new[] { BeezDeveloperItems.RingId, BeezDeveloperItems.StoneId }));
            Assert.That(items.Select(item => item.SlotPosition).Distinct().Count(), Is.EqualTo(2));
            Assert.That(items.All(item => item.OwnerID == player.ObjectId), Is.True);
            ((EmptyProxy)EmptyDatabase).Writes.Clear();
            var dummy = (BotDummyClient)RuntimeHelpers.GetUninitializedObject(typeof(BotDummyClient));
            BeezDeveloperItems.GrantCreated(new DOL.Events.CharacterEventArgs((DbCoreCharacter)typeof(GamePlayer).GetField("m_dbCharacter", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(player), dummy));
            Assert.That(((EmptyProxy)EmptyDatabase).Writes, Is.Empty);
        }

        [Test]
        public void PortalIsOwnerOnlyAndCleanupDisposesThePairWithoutSavedNpcs()
        {
            GamePlayer owner = Player();
            GamePlayer stranger = Player();
            var bind = BeezBindPortals.BindPoint(owner);
            Type pairType = typeof(BeezBindPortals).GetNestedType("Pair", BindingFlags.NonPublic);
            Type portalType = typeof(BeezBindPortals).GetNestedType("Portal", BindingFlags.NonPublic);
            object pair = Activator.CreateInstance(pairType, [owner, bind, bind]);
            GameStaticItem portal = (GameStaticItem)Activator.CreateInstance(portalType, [pair, bind, bind]);
            var pairs = (IDictionary)typeof(BeezBindPortals).GetField("Pairs", BindingFlags.Static | BindingFlags.NonPublic).GetValue(null);
            pairs[owner] = pair;
            try
            {
                Assert.That(portal.Interact(stranger), Is.False);
                owner.BindXpos++;
                Assert.That(portal.Interact(owner), Is.False);
                Assert.That(portal.InternalID, Is.Null.Or.Empty);
                Assert.That(portal.Model, Is.EqualTo(4319));
                Assert.That(portal.GameObjectType, Is.EqualTo(eGameObjectType.ITEM));
                Assert.That(portal.LoadedFromScript, Is.True);
                BeezBindPortals.Clear(owner);
                Assert.That(pairs.Contains(owner), Is.False);
                Assert.That(portal.Interact(owner), Is.False);
                Assert.That(((EmptyProxy)EmptyDatabase).Writes, Is.Empty);
            }
            finally { BeezBindPortals.Clear(owner); }
        }

        [Test]
        public void RingEquipRefreshAndRemovalDoNotDoubleCountOrDiscardOtherEquipment()
        {
            GamePlayer player = Player();
            GameInventoryItem ring = GameInventoryItem.Create(BeezDeveloperItems.Template(BeezDeveloperItems.RingId));
            ring.SlotPosition = (int)eInventorySlot.LeftRing;
            var equipment = (Dictionary<eInventorySlot, DbInventoryItem>)typeof(GameLivingInventory)
                .GetField("m_items", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(player.Inventory);
            equipment[eInventorySlot.LeftRing] = ring;
            player.OnItemEquipped(ring, eInventorySlot.LeftRing);
            Assert.That(player.ItemBonus[eProperty.Strength], Is.EqualTo(250));
            player.RefreshItemBonuses();
            player.RefreshItemBonuses();
            Assert.That(player.ItemBonus[eProperty.Strength], Is.EqualTo(250));
            var other = GameInventoryItem.Create(new DbItemTemplate { Id_nb = "ordinary_ring", Object_Type = (int)eObjectType.Magical,
                Item_Type = (int)eInventorySlot.RightRing, Bonus1 = 10, Bonus1Type = (int)eProperty.Strength });
            other.SlotPosition = (int)eInventorySlot.RightRing;
            equipment[eInventorySlot.RightRing] = other;
            player.RefreshItemBonuses();
            Assert.That(player.ItemBonus[eProperty.Strength], Is.EqualTo(260));
            Assert.That(new StatCalculator().CalcValueFromItems(player, eProperty.Strength), Is.EqualTo(75));
            equipment.Remove(eInventorySlot.LeftRing);
            player.OnItemUnequipped(ring, eInventorySlot.LeftRing);
            Assert.That(player.ItemBonus[eProperty.Strength], Is.EqualTo(10));
            player.RefreshItemBonuses();
            Assert.That(player.ItemBonus[eProperty.Strength], Is.EqualTo(10));
        }

        [Test]
        public void ADisabledStoneEffectIsRemovedWithoutSubtractingItsBonusTwice()
        {
            GamePlayer player = Player();
            ECSGameSpellEffect effect = StrengthEffect(player, true, 1.25);
            effect.Start();
            player.effectListComponent.BeginTick();
            effect.Disable();
            player.effectListComponent.BeginTick();
            Assert.That(effect.IsDisabled, Is.True);
            BeezBuffs.Clear(player);
            player.effectListComponent.BeginTick();
            Assert.That(effect.IsEnded, Is.True);
            Assert.That(player.BaseBuffBonusCategory[eProperty.Strength], Is.Zero);
        }

        [Test]
        public void GatewayPairAllowsBothDirectionsAndRemovesAnOrphanedEndpoint()
        {
            PortalRegion region = (PortalRegion)RuntimeHelpers.GetUninitializedObject(typeof(PortalRegion));
            Field(typeof(Region), region, "m_regionData", new RegionData { Id = 1 });
            Field(typeof(Region), region, "m_zones", new List<Zone> { new(region, 1, "test", 0, 0, 1000, 1000, 0, false, 0, false, 0, 0, 0, 0, 0) });
            region.Areas = [];
            var regions = (System.Collections.Concurrent.ConcurrentDictionary<ushort, Region>)typeof(WorldMgr).GetField("m_regions", BindingFlags.Static | BindingFlags.NonPublic).GetValue(null);
            regions.TryGetValue(1, out Region previous);
            regions[1] = region;
            GamePlayer owner = Player();
            owner.CurrentRegion = region;
            owner.BindRegion = 1; owner.BindXpos = 100; owner.BindYpos = 100;
            var bind = BeezBindPortals.BindPoint(owner);
            var expedition = new BeezBindPortals.Endpoint(1, 800, 800, 0, 1024);
            Type pairType = typeof(BeezBindPortals).GetNestedType("Pair", BindingFlags.NonPublic);
            Type portalType = typeof(BeezBindPortals).GetNestedType("Portal", BindingFlags.NonPublic);
            object pair = Activator.CreateInstance(pairType, [owner, expedition, bind]);
            GameStaticItem home = (GameStaticItem)Activator.CreateInstance(portalType, [pair, bind, expedition]);
            GameStaticItem away = (GameStaticItem)Activator.CreateInstance(portalType, [pair, expedition, bind]);
            Field(pairType, pair, "_home", home); Field(pairType, pair, "_away", away);
            var pairs = (IDictionary)typeof(BeezBindPortals).GetField("Pairs", BindingFlags.Static | BindingFlags.NonPublic).GetValue(null);
            pairs[owner] = pair;
            MethodInfo canTravel = pairType.GetMethod("CanTravel", BindingFlags.Instance | BindingFlags.NonPublic);
            try
            {
                home.ObjectState = away.ObjectState = GameObject.eObjectState.Active;
                owner.X = bind.X; owner.Y = bind.Y;
                Assert.That(canTravel.Invoke(pair, [owner, home, expedition]), Is.True);
                Assert.That(canTravel.Invoke(pair, [owner, away, bind]), Is.False, "Remote endpoint cannot be activated");
                owner.X = expedition.X; owner.Y = expedition.Y;
                Assert.That(canTravel.Invoke(pair, [owner, away, bind]), Is.True);
                Assert.That(home.Model, Is.EqualTo(away.Model));
                away.ObjectState = GameObject.eObjectState.Inactive;
                Assert.That(canTravel.Invoke(pair, [owner, away, bind]), Is.False);
                home.ObjectState = GameObject.eObjectState.Inactive; // Neither fixture object is registered in Region.
                Assert.That(pairType.GetMethod("Tick", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(pair, [null]), Is.Zero);
                Assert.That(pairs.Contains(owner), Is.False);
                Assert.That(home.ObjectState, Is.EqualTo(GameObject.eObjectState.Deleted));
                Assert.That(away.ObjectState, Is.EqualTo(GameObject.eObjectState.Deleted));
            }
            finally
            {
                // The fixture never registers objects in Region; avoid asking its stub to remove them.
                home.ObjectState = away.ObjectState = GameObject.eObjectState.Inactive;
                BeezBindPortals.Clear(owner);
                if (previous == null) regions.TryRemove(1, out _); else regions[1] = previous;
            }
        }

        [Test]
        public void PortalArrivalWaitSurvivesRegionLoadingButDeathAndExpiryDisposeIt()
        {
            PortalRegion region = (PortalRegion)RuntimeHelpers.GetUninitializedObject(typeof(PortalRegion));
            Field(typeof(Region), region, "m_regionData", new RegionData { Id = 1 });
            Field(typeof(Region), region, "m_zones", new List<Zone> { new(region, 1, "test", 0, 0, 1000, 1000, 0, false, 0, false, 0, 0, 0, 0, 0) });
            region.Areas = [];
            var regions = (System.Collections.Concurrent.ConcurrentDictionary<ushort, Region>)typeof(WorldMgr).GetField("m_regions", BindingFlags.Static | BindingFlags.NonPublic).GetValue(null);
            regions.TryGetValue(1, out Region previous);
            regions[1] = region;
            GamePlayer owner = Player();
            owner.CurrentRegion = region;
            owner.BindRegion = 1; owner.BindXpos = 100; owner.BindYpos = 100;
            var endpoint = BeezBindPortals.BindPoint(owner);
            Type pairType = typeof(BeezBindPortals).GetNestedType("Pair", BindingFlags.NonPublic);
            var pairs = (IDictionary)typeof(BeezBindPortals).GetField("Pairs", BindingFlags.Static | BindingFlags.NonPublic).GetValue(null);
            object pair = Activator.CreateInstance(pairType, [owner, endpoint, endpoint]);
            pairs[owner] = pair;
            MethodInfo tick = pairType.GetMethod("Tick", BindingFlags.Instance | BindingFlags.NonPublic);
            try
            {
                owner.X = 110; owner.Y = 100; owner.Z = endpoint.Z; owner.Heading = 1024;
            Assert.That(BeezBindPortals.HasArrived(owner, endpoint), Is.True, "Minor motion and heading updates still confirm arrival");
            owner.ObjectState = GameObject.eObjectState.Inactive; // Client loading another region, health still positive.
            Assert.That(BeezBindPortals.HasArrived(owner, endpoint), Is.False);
                Assert.That(tick.Invoke(pair, [null]), Is.EqualTo(250));
                Assert.That(pairs.Contains(owner), Is.True);
                pairType.GetField("_created", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(pair, GameLoop.GameLoopTime - BeezBindPortals.Lifetime);
                Assert.That(tick.Invoke(pair, [null]), Is.Zero);
                Assert.That(pairs.Contains(owner), Is.False);
                pair = Activator.CreateInstance(pairType, [owner, endpoint, endpoint]);
                pairs[owner] = pair;
                var character = (DbCoreCharacter)typeof(GamePlayer).GetField("m_dbCharacter", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(owner);
                character.Health = 0;
                Assert.That(tick.Invoke(pair, [null]), Is.Zero);
                Assert.That(pairs.Contains(owner), Is.False);
            }
            finally
            {
                BeezBindPortals.Clear(owner);
                if (previous == null) regions.TryRemove(1, out _);
                else regions[1] = previous;
            }
        }
    }
}
