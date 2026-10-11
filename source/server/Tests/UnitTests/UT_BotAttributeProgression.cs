using System;
using System.Collections;
using System.Collections.Generic;
using System.Collections.Concurrent;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Text.Json;
using DOL.Database;
using DOL.GS;
using DOL.GS.Database;
using DOL.GS.PlayerClass;
using DOL.GS.Commands;
using DOL.GS.Spells;
using DOL.GS.Styles;
using DOL.GS.PacketHandler;
using DOL.GS.PropertyCalc;
using DOL.GS.ServerProperties;
using DOL.Logging;
using NUnit.Framework;

namespace DOL.UnitTests
{
    [TestFixture, NonParallelizable]
    public sealed class UT_BotAttributeProgression
    {
        private const BindingFlags Hidden = BindingFlags.Instance | BindingFlags.NonPublic;
        private static readonly IObjectDatabase Empty = DispatchProxy.Create<IObjectDatabase, ReadDatabase>();
        public class ReadDatabase : DispatchProxy
        {
            public BotProfile Profile;
            protected override object Invoke(MethodInfo method, object[] args)
            {
                if (!method.Name.StartsWith("Select") && !method.Name.StartsWith("Find"))
                    throw new InvalidOperationException("No database writes allowed: " + method.Name);
                if (method.ReturnType == typeof(BotProfile)) return Profile;
                Type type = method.ReturnType;
                return type.IsGenericType && typeof(IEnumerable).IsAssignableFrom(type)
                    ? Activator.CreateInstance(typeof(List<>).MakeGenericType(type.GetGenericArguments()[0])) : null;
            }
        }
        private sealed class Server : GameServer
        {
            protected override IObjectDatabase DataBaseImpl => Empty;
            protected override GS.ServerRules.IServerRules ServerRulesImpl => new GS.ServerRules.NormalServerRules();
        }
        private GameServer _previous;
        private PetTestLanguageScope _language;
        private IPropertyCalculator[] _originalCalculators;
        private readonly List<GameBot> _constructed = new();
        private readonly List<(Logger Logger, object Previous, BlockingCollection<LogEntry> Entries)> _logs = new();
        [SetUp] public void Setup()
        {
            _previous = GameServer.Instance;
            _language = new PetTestLanguageScope();
            GameServer.LoadTestDouble((Server)RuntimeHelpers.GetUninitializedObject(typeof(Server)));
            var calculators = (IPropertyCalculator[])typeof(GameLiving).GetField("m_propertyCalc", BindingFlags.Static | BindingFlags.NonPublic).GetValue(null);
            _originalCalculators = calculators.ToArray();
            GameLiving.LoadCalculators();
            foreach (string name in new[] { "GameBot", "BotEquipment", "BotDatabase", "CreationStartupEquipment" })
            {
                var type = typeof(GameBot).Assembly.GetTypes().Single(t => t.Name == name);
                var logger = (Logger)type.GetField("log", BindingFlags.Static | BindingFlags.NonPublic).GetValue(null);
                var field = typeof(Logger).GetField("_queueProcessor", Hidden);
                object previous = field.GetValue(logger);
                var queue = new LogEntryQueueProcessor(); var entries = new BlockingCollection<LogEntry>();
                typeof(LogEntryQueueProcessor).GetField("_loggingQueue", Hidden).SetValue(queue, entries);
                field.SetValue(logger, queue);
                _logs.Add((logger, previous, entries));
            }
        }
        [TearDown] public void Cleanup()
        {
            foreach (var bot in _constructed)
            {
                if (bot.castingComponent != null) ServiceObjectStore.Remove(bot.castingComponent);
                if (bot.effectListComponent != null) ServiceObjectStore.Remove(bot.effectListComponent);
                if (bot.movementComponent != null) ServiceObjectStore.Remove(bot.movementComponent);
                if (bot.Owner != null) DOL.Events.GameEventMgr.RemoveAllHandlersForObject(bot.Owner);
            }
            _constructed.Clear();
            foreach (var entry in _logs)
            {
                typeof(Logger).GetField("_queueProcessor", Hidden).SetValue(entry.Logger, entry.Previous);
                entry.Entries.Dispose();
            }
            _logs.Clear();
            ((ReadDatabase)Empty).Profile = null;
            var calculators = (IPropertyCalculator[])typeof(GameLiving).GetField("m_propertyCalc", BindingFlags.Static | BindingFlags.NonPublic).GetValue(null);
            Array.Copy(_originalCalculators, calculators, calculators.Length);
            GameServer.LoadTestDouble(_previous);
            _language.Dispose();
        }
        private sealed class StatBot : GameBot
        {
            private StatBot() : base((OfflineWorldBotRecord)null) { }
            public ICharacterClass Class;
            public override ICharacterClass CharacterClass => Class;
            // Keep inherited Level, ChangeBaseStat, SetStats and resources. Use real
            // stat/pool calculators without requiring the world service to start.
            public override int GetModified(eProperty property) => property switch
            {
                eProperty.MaxHealth => new MaxHealthCalculator().CalcValue(this, property),
                eProperty.MaxMana => new MaxManaCalculator().CalcValue(this, property),
                >= eProperty.Stat_First and <= eProperty.Stat_Last => new StatCalculator().CalcValue(this, property),
                _ => 0
            };
        }

        [TestCase(5, eStat.STR, 60)] [TestCase(5, eStat.INT, 70)]
        [TestCase(6, eStat.INT, 71)] [TestCase(10, eStat.INT, 75)]
        [TestCase(10, eStat.DEX, 73)] [TestCase(10, eStat.QUI, 72)]
        public void RequestedFormula(int level, eStat stat, int expected)
        {
            Assert.That(BotAttributeProgression.Calculate(60, level, stat, eStat.INT, eStat.DEX, eStat.QUI, true), Is.EqualTo(expected));
        }

        [TestCase(1, 70, 70, 70)] [TestCase(5, 70, 70, 70)]
        [TestCase(6, 71, 71, 71)] [TestCase(8, 73, 72, 71)]
        [TestCase(9, 74, 72, 72)] [TestCase(50, 115, 93, 85)]
        public void ClassGrowthBoundaries(int level, int primary, int secondary, int tertiary)
        {
            Assert.That(BotAttributeProgression.Calculate(60, level, eStat.INT, eStat.INT, eStat.DEX, eStat.QUI, true), Is.EqualTo(primary));
            Assert.That(BotAttributeProgression.Calculate(60, level, eStat.DEX, eStat.INT, eStat.DEX, eStat.QUI, true), Is.EqualTo(secondary));
            Assert.That(BotAttributeProgression.Calculate(60, level, eStat.QUI, eStat.INT, eStat.DEX, eStat.QUI, true), Is.EqualTo(tertiary));
        }

        [TestCase(50, 7, false, 7)] [TestCase(7, 20, false, 20)]
        [TestCase(7, 0, false, 7)] [TestCase(7, 20, true, 7)] [TestCase(7, 0, true, 7)]
        public void SavedLevelWinsOnlyForNonTemporaryBots(byte owner, byte requested, bool temporary, byte expected)
        {
            Assert.That(BotAttributeProgression.InitialLevel(owner, requested, temporary), Is.EqualTo(expected));
        }

        [Test]
        public void RebuildIsAbsoluteIdempotentAndPreservesAllBonusesAndResources()
        {
            var bot = Make(); bot.Level = 10;
            bot.ItemBonus[eProperty.Intelligence] = 5;
            bot.BaseBuffBonusCategory[eProperty.Intelligence] = 4;
            bot.SpecBuffBonusCategory[eProperty.Intelligence] = 3;
            bot.AbilityBonus[eProperty.Intelligence] = 2;
            bot.DebuffCategory[eProperty.Intelligence] = 1;
            int expectedModified = bot.GetModified(eProperty.Intelligence);
            var stats = (short[])typeof(GameLiving).GetField("m_charStat", Hidden).GetValue(bot);
            Array.Fill(stats, (short)500); // Reproduce an already-inflated instance.
            Raw(bot, "m_health", 12); Raw(bot, "m_mana", 8); Raw(bot, "m_endurance", 9);
            bot.RebuildPlayerBaseStats();
            var once = Stats(bot);
            bot.RebuildPlayerBaseStats();
            Invoke(bot, "InitializeBotStats"); Invoke(bot, "ApplyLevelStatGrowth", 6);
            Assert.That(Stats(bot), Is.EqualTo(once));
            Assert.That(bot.Intelligence, Is.EqualTo(75));
            Assert.That(bot.GetModified(eProperty.Intelligence), Is.EqualTo(expectedModified));
            Assert.That(bot.ItemBonus[eProperty.Intelligence], Is.EqualTo(5));
            Assert.That(bot.BaseBuffBonusCategory[eProperty.Intelligence], Is.EqualTo(4));
            Assert.That(bot.SpecBuffBonusCategory[eProperty.Intelligence], Is.EqualTo(3));
            Assert.That(bot.AbilityBonus[eProperty.Intelligence], Is.EqualTo(2));
            Assert.That(bot.DebuffCategory[eProperty.Intelligence], Is.EqualTo(1));
            Assert.That(bot.Health, Is.EqualTo(12), "CON delta must not heal");
            Assert.That(bot.Mana, Is.EqualTo(8)); Assert.That(bot.Endurance, Is.EqualTo(9));
        }

        [Test]
        public void LevelAssignmentAlwaysBypassesNpcAutoStatsAndTemplateValues()
        {
            bool force = Properties.FORCE_MOB_AUTOSET_STATS;
            try
            {
                var bot = Make();
                foreach (bool enabled in new[] { true, false })
                {
                    Properties.FORCE_MOB_AUTOSET_STATS = enabled;
                    bot.Level = 10;
                    Assert.That(bot.Intelligence, Is.EqualTo(75));
                    Assert.That(bot.MaxMana, Is.EqualTo(75));
                    Raw(bot, "m_mana", 900);
                    bot.Level = 6;
                    Assert.That(bot.Intelligence, Is.EqualTo(71));
                    Assert.That(bot.MaxMana, Is.EqualTo(51));
                    Assert.That(bot.Mana, Is.EqualTo(51));
                    bot.SetStats(new DbMob { Intelligence = 900, Strength = 900 });
                    Assert.That(bot.Intelligence, Is.EqualTo(71));
                    bot.Level = 10;
                    Assert.That(bot.Mana, Is.EqualTo(51), "A stat-only level assignment does not refill");
                    Assert.That(bot.Strength, Is.EqualTo(60));
                }
            }
            finally { Properties.FORCE_MOB_AUTOSET_STATS = force; }
        }

        [Test]
        public void UsesActualRaceAndUnknownFallbackAndIndividualMissingStatFallback()
        {
            var bot = Make(); bot.RaceId = (byte)eRace.Briton; bot.Race = (short)eRace.Avalonian; bot.Level = 10;
            Assert.That(bot.Intelligence, Is.EqualTo(95)); Assert.That(bot.Strength, Is.EqualTo(45));
            bot.Race = short.MaxValue; bot.SetStats();
            Assert.That(bot.Intelligence, Is.EqualTo(75));
            var original = GlobalConstants.STARTING_STATS_DICT[eRace.Unknown];
            try
            {
                GlobalConstants.STARTING_STATS_DICT[eRace.Unknown] = new Dictionary<eStat, int> { [eStat.INT] = 80 };
                bot.SetStats();
                Assert.That(bot.Intelligence, Is.EqualTo(95)); Assert.That(bot.Strength, Is.EqualTo(60));
                GlobalConstants.STARTING_STATS_DICT.Remove(eRace.Unknown);
                bot.SetStats();
                Assert.That(bot.Intelligence, Is.EqualTo(75));
            }
            finally { GlobalConstants.STARTING_STATS_DICT[eRace.Unknown] = original; }
        }

        [Test]
        public void PreClassConstructorAndDeadBotsDoNotHealOrUseNpcStats()
        {
            var bot = Make(); bot.Class = null; Raw(bot, "m_health", 0); bot.Level = 1;
            Assert.That(Stats(bot), Is.All.EqualTo(60)); Assert.That(bot.Health, Is.Zero);
            bot.Class = new ClassWizard(); bot.Level = 10;
            Assert.That(bot.Intelligence, Is.EqualTo(75)); Assert.That(bot.Health, Is.Zero);
        }

        [Test]
        public void NonBotsStillUseOriginalNpcAutosetAndDbMobStats()
        {
            bool force = Properties.FORCE_MOB_AUTOSET_STATS;
            try
            {
                var npc = (PlainNpc)RuntimeHelpers.GetUninitializedObject(typeof(PlainNpc));
                Raw(npc, "m_charStat", new short[8]);
                Properties.FORCE_MOB_AUTOSET_STATS = true;
                npc.SetStats();
                Assert.That(npc.Intelligence, Is.EqualTo((short)Math.Max(1, Properties.MOB_AUTOSET_INT_BASE - Properties.MOB_AUTOSET_INT_MULTIPLIER)));
                Properties.FORCE_MOB_AUTOSET_STATS = false;
                // Override only MaxHealth in the fixture used for the CON setter.
                var normal = (PlainNpc)RuntimeHelpers.GetUninitializedObject(typeof(PlainNpc));
                Raw(normal, "m_charStat", new short[8]);
                normal.SetStats(new DbMob { Strength=81, Constitution=82, Dexterity=83, Quickness=84, Intelligence=85, Piety=86, Empathy=87, Charisma=88 });
                Assert.That(normal.Intelligence, Is.EqualTo(85)); Assert.That(normal.Strength, Is.EqualTo(81));
            }
            finally { Properties.FORCE_MOB_AUTOSET_STATS = force; }
        }

        private sealed class PlainNpc : GameNPC { public override int MaxHealth => 100; }

        private sealed class Owner : GamePlayer
        {
            private Owner() : base(null, null) { }
            public override byte Level { get; set; }
            public override string Name { get; set; }
            public override bool IsAttacking => false;
            public bool Fighting, Casting, Dead;
            public IPacketLib Packets;
            public GameClient Connection;
            public override bool InCombat => Fighting;
            public override bool IsCasting => Casting;
            public override bool IsAlive => !Dead;
            public override IPacketLib Out => Packets;
            public override GameClient Client => Connection;
        }

        public class Packets : DispatchProxy
        {
            public readonly List<(string Method, object[] Args)> Calls = new();
            protected override object Invoke(MethodInfo method, object[] args)
            {
                Calls.Add((method.Name, args));
                return method.ReturnType != typeof(void) && method.ReturnType.IsValueType ? Activator.CreateInstance(method.ReturnType) : null;
            }
        }

        private Owner RefreshOwner(byte level)
        {
            var owner = (Owner)RuntimeHelpers.GetUninitializedObject(typeof(Owner));
            owner.Level = level; owner.Realm = eRealm.Albion; owner.Name = "RefreshTester";
            owner.Packets = DispatchProxy.Create<IPacketLib, Packets>();
            owner.Connection = (GameClient)RuntimeHelpers.GetUninitializedObject(typeof(GameClient));
            owner.Connection.Out = owner.Packets;
            owner.Connection.ClientState = GameClient.eClientState.Playing;
            owner.Connection.Player = owner;
            return owner;
        }

        private GameBot RefreshBot(Owner owner, byte level, bool world = false)
        {
            GameBot bot = world
                ? new GameBot(new OfflineWorldBotRecord { BotId=0, Name="Recruited", Realm=(int)eRealm.Albion,
                    ClassId=(int)eCharacterClass.Wizard, RaceId=(int)eRace.Briton, Level=level, Health=20 })
                : new GameBot(owner, (byte)eCharacterClass.Wizard, "Helper", (byte)eRace.Briton, temporaryGroupHelper:true);
            _constructed.Add(bot);
            bot.Level = level;
            bot.Health = bot.MaxHealth;
            bot.ObjectState = GameObject.eObjectState.Active;
            typeof(GameBot).GetProperty(nameof(GameBot.PlayerGroupLeader)).SetValue(bot, owner);
            return bot;
        }

        private static Group RefreshGroup(Owner owner, params GameLiving[] bots)
        {
            var group = new Group(owner);
            var members = (List<GameLiving>)typeof(Group).GetField("_groupMembers", Hidden).GetValue(group);
            members.Add(owner); owner.Group = group;
            foreach (var bot in bots) { members.Add(bot); bot.Group = group; bot.GroupIndex = (byte)(members.Count - 1); }
            return group;
        }

        [TestCase(10, 35, false)] [TestCase(40, 12, false)]
        [TestCase(10, 35, true)] [TestCase(40, 12, true)]
        public void SpawnRefreshRebuildsRealBotsInBothDirectionsAndPreservesIdentity(byte before, byte after, bool world)
        {
            Owner owner = RefreshOwner(after); GameBot bot = RefreshBot(owner, before, world);
            Group group = RefreshGroup(owner, bot);
            string id = bot.InternalID; var inventory = bot.Inventory; var items = inventory.AllItems.ToArray();
            var plan = bot.BotSpec; var brain = bot.Brain; int classId = bot.CharacterClass.ID;
            int health = bot.MaxHealth, mana = bot.MaxMana;
            string result = CompanionLevelRefresh.Refresh(owner);
            Assert.That(result, Is.EqualTo($"Refreshed 1 companions to level {after}."));
            Assert.That(bot.Level, Is.EqualTo(after));
            Assert.That(bot.Intelligence, Is.EqualTo(70 + Math.Max(0, after - 5)));
            Assert.That(bot.MaxHealth, before < after ? Is.GreaterThan(health) : Is.LessThan(health));
            Assert.That(bot.MaxMana, before < after ? Is.GreaterThan(mana) : Is.LessThan(mana));
            Assert.That(bot.Health, Is.EqualTo(bot.MaxHealth)); Assert.That(bot.Mana, Is.EqualTo(bot.MaxMana));
            Assert.That(bot.Endurance, Is.EqualTo(bot.MaxEndurance));
            Assert.That(bot.Group, Is.SameAs(group)); Assert.That(bot.InternalID, Is.EqualTo(id));
            Assert.That(bot.BotSpec, Is.SameAs(plan)); Assert.That(bot.Brain, Is.SameAs(brain));
            Assert.That(bot.Inventory, Is.SameAs(inventory)); Assert.That(bot.Inventory.AllItems, Is.EquivalentTo(items));
            Assert.That(bot.CharacterClass.ID, Is.EqualTo(classId)); Assert.That(bot.Realm, Is.EqualTo(eRealm.Albion));
            Assert.That(group.MemberCount, Is.EqualTo(2));
            Assert.That(((Packets)owner.Packets).Calls.Any(c => c.Method == "SendGroupMemberUpdate"), Is.True);
            Assert.That(((Packets)owner.Packets).Calls.Any(c => c.Method == "SendGroupWindowUpdate"), Is.True);
            if (world)
            {
                Assert.That(bot.Experience, Is.EqualTo(GamePlayer.GetExperienceAmountForLevel(after - 1)));
                Assert.That(bot.AutonomousStateDirty, Is.True);
            }
        }

        [TestCase(10, 35)] [TestCase(40, 12)]
        public void RefreshAlsoChangesActualMeleeWeaponSkill(byte initial, byte target)
        {
            Owner owner = RefreshOwner(initial);
            GameBot bot = new GameBot(owner, (byte)eCharacterClass.Armsman, "MeleeHelper", (byte)eRace.Briton, temporaryGroupHelper:true);
            _constructed.Add(bot); bot.ObjectState = GameObject.eObjectState.Active;
            RefreshGroup(owner, bot);
            var weapon = new DbInventoryItem { Object_Type=(int)eObjectType.SlashingWeapon, SlotPosition=(int)eInventorySlot.RightHandWeapon };
            double before = bot.GetWeaponSkill(weapon);
            owner.Level = target;
            Assert.That(CompanionLevelRefresh.Refresh(owner), Does.StartWith("Refreshed 1"));
            Assert.That(bot.GetWeaponSkill(weapon), initial < target ? Is.GreaterThan(before) : Is.LessThan(before));
        }

        [Test]
        public void SpawnRefreshMixedSevenSlotsPreservesEveryMemberAndOnlyChangesMismatches()
        {
            Owner owner = RefreshOwner(35);
            GameBot[] bots = new byte[] { 10, 20, 30, 35, 40, 45, 50 }.Select(l => RefreshBot(owner, l)).ToArray();
            Group group = RefreshGroup(owner, bots);
            bots[3].Health = 17;
            Assert.That(CompanionLevelRefresh.Refresh(owner), Is.EqualTo("Refreshed 6 companions to level 35."));
            Assert.That(bots[3].Health, Is.EqualTo(17), "Already-correct bots must not be healed by refresh");
            Assert.That(bots.Select(b => b.Level), Is.All.EqualTo(35));
            Assert.That(group.GetMembersInTheGroup(), Is.EquivalentTo(bots.Cast<GameLiving>().Prepend(owner)));
            Assert.That(bots.Select(b => b.GroupIndex), Is.EqualTo(Enumerable.Range(1, 7)));
            Assert.That(CompanionLevelRefresh.Refresh(owner), Does.StartWith("No changes needed"));
        }

        [TestCase("combat")] [TestCase("casting")] [TestCase("deadPlayer")] [TestCase("travel")] [TestCase("botCombat")]
        public void UnsafeRefreshDoesNotPartiallyChangeCompanions(string reason)
        {
            Owner owner = RefreshOwner(35); GameBot first = RefreshBot(owner, 10), second = RefreshBot(owner, 20);
            RefreshGroup(owner, first, second);
            if (reason == "botCombat") Raw(second, "<LastAttackedByEnemyTickPvE>k__BackingField", GameLoop.GameLoopTime + 1);
            owner.Fighting = reason == "combat"; owner.Casting = reason == "casting"; owner.Dead = reason == "deadPlayer";
            if (reason == "travel") typeof(GameBot).GetProperty(nameof(GameBot.IsOnStableMasterRoute)).SetValue(second, true);
            Assert.That(CompanionLevelRefresh.Refresh(owner), Does.StartWith(reason == "deadPlayer" ? "You must" : "Cannot refresh"));
            Assert.That(first.Level, Is.EqualTo(10)); Assert.That(second.Level, Is.EqualTo(20));
        }

        [Test]
        public void DeadUnavailableAndUnrelatedGroupMembersAreNotChanged()
        {
            Owner owner = RefreshOwner(35), other = RefreshOwner(40);
            GameBot live = RefreshBot(owner, 10), dead = RefreshBot(owner, 20), inactive = RefreshBot(owner, 20), stranger = RefreshBot(other, 20);
            dead.Health = 0; inactive.ObjectState = GameObject.eObjectState.Inactive;
            var npc = new GameNPC { Level = 20, Realm = eRealm.Albion };
            RefreshGroup(owner, live, dead, inactive, stranger, other, npc);
            Assert.That(CompanionLevelRefresh.Refresh(owner), Does.StartWith("Refreshed 1 companions").And.Contain("Skipped 2"));
            Assert.That(dead.Level, Is.EqualTo(20)); Assert.That(dead.Health, Is.Zero);
            Assert.That(inactive.Level, Is.EqualTo(20)); Assert.That(stranger.Level, Is.EqualTo(20));
            Assert.That(other.Level, Is.EqualTo(40)); Assert.That(npc.Level, Is.EqualTo(20));
            ServiceObjectStore.Remove(npc.effectListComponent); ServiceObjectStore.Remove(npc.castingComponent); ServiceObjectStore.Remove(npc.movementComponent);
        }

        [Test]
        public void FullGroupCanRequestMenuAndRefreshWithoutRespawning()
        {
            Owner owner = RefreshOwner(35);
            GameBot[] bots = Enumerable.Range(0, 7).Select(_ => RefreshBot(owner, 10)).ToArray();
            RefreshGroup(owner, bots);
            // No world region in this test: Open reports its normal location fallback,
            // rather than the old full-group rejection that hid the Refresh link.
            new SpawnTemporaryGroupBotCommandHandler().OnCommand(owner.Connection, new[] { "/spawn" });
            Assert.That(((Packets)owner.Packets).Calls.Any(c => c.Method == "SendMessage" && c.Args[0].ToString().Contains("menu could not open here")), Is.True);
            Assert.That(((Packets)owner.Packets).Calls.Any(c => c.Method == "SendMessage" && c.Args[0].ToString() == "Your group is full."), Is.False);
            new SpawnTemporaryGroupBotCommandHandler().OnCommand(owner.Connection, new[] { "/spawn", "refresh" });
            Assert.That(bots.Select(b => b.Level), Is.All.EqualTo(35));
            Assert.That(((Packets)owner.Packets).Calls.Any(c => c.Method == "SendMessage" && c.Args[0].ToString() == "Refreshed 7 companions to level 35."), Is.True);
        }

        [Test]
        public void SpawnRefreshEmptyGroupIsGraceful()
        {
            Owner owner = RefreshOwner(35);
            Assert.That(CompanionLevelRefresh.Refresh(owner), Does.Contain("no grouped companions"));
            RefreshGroup(owner);
            Assert.That(CompanionLevelRefresh.Refresh(owner), Does.Contain("no eligible grouped companions"));
        }

        [Test]
        public void TypedAndClickableRefreshUseSamePathAndMenuAcceptsOnlyItsOwner()
        {
            Owner owner = RefreshOwner(35); GameBot bot = RefreshBot(owner, 10); RefreshGroup(owner, bot);
            new SpawnTemporaryGroupBotCommandHandler().OnCommand(owner.Connection, new[] { "/spawn", "refresh" });
            Assert.That(bot.Level, Is.EqualTo(35));
            bot.Level = 10;
            var menu = (TemporaryGroupSpawnMenu)RuntimeHelpers.GetUninitializedObject(typeof(TemporaryGroupSpawnMenu));
            typeof(TemporaryGroupSpawnMenu).GetField("_owner", Hidden).SetValue(menu, owner);
            Assert.That(menu.WhisperReceive(RefreshOwner(35), "Refresh"), Is.False);
            Assert.That(bot.Level, Is.EqualTo(10));
            Assert.That(menu.WhisperReceive(owner, "Refresh"), Is.True);
            Assert.That(bot.Level, Is.EqualTo(35));
            Assert.That(((Packets)owner.Packets).Calls.Count(c => c.Method == "SendMessage" && c.Args[0].ToString() == "Refreshed 1 companions to level 35."), Is.EqualTo(2));
        }

        private static T SkillCache<T>(string name) => (T)typeof(SkillBase)
            .GetField(name, BindingFlags.Static | BindingFlags.NonPublic).GetValue(null);

        [TestCase(10, 40)] [TestCase(40, 10)] [TestCase(40, 5)]
        public void RefreshRebuildsLearnedSpellsAbilitiesSpecsAndActualDamage(byte initial, byte target)
        {
            const string key = "UnitTestRefreshSpec", ability = "UnitTestRefreshAbility";
            var careers = SkillCache<Dictionary<int, Dictionary<string, int>>>("m_specsByClass");
            var definitions = SkillCache<Dictionary<string, Tuple<Type, string, ushort, int>>>("m_specsByName");
            var lines = SkillCache<Dictionary<string, List<Tuple<SpellLine, int>>>>("m_specsSpellLines");
            var spells = SkillCache<Dictionary<string, List<Spell>>>("m_lineSpells");
            var abilities = SkillCache<Dictionary<string, List<Tuple<string, byte, int, int>>>>("m_specsAbilities");
            var abilityDefinitions = SkillCache<Dictionary<string, DbAbility>>("m_abilityIndex");
            int wizard = (int)eCharacterClass.Wizard;
            careers.TryGetValue(wizard, out var saved);
            try
            {
                careers[wizard] = new Dictionary<string, int> { [key] = 1 };
                definitions[key] = Tuple.Create(typeof(Specialization), key, (ushort)0, 60001);
                lines[key] = new() { Tuple.Create(new SpellLine(key, key, key, true), wizard) };
                spells[key] = new()
                {
                    new Spell(new DbSpell { SpellID=60001, Name="Refresh low rank", Type="DirectDamage", Target="Enemy", Damage=25, DamageType=(int)eDamageType.Heat, CastTime=2 }, 10),
                    new Spell(new DbSpell { SpellID=60002, Name="Refresh high rank", Type="DirectDamage", Target="Enemy", Damage=125, DamageType=(int)eDamageType.Heat, CastTime=2 }, 30)
                };
                abilityDefinitions[ability] = new DbAbility { KeyName=ability, Name=ability };
                abilities[key] = new() { Tuple.Create(ability, (byte)30, 1, 0) };
                Owner owner = RefreshOwner(initial);
                GameBot bot = RefreshBot(owner, initial);
                bot.BotSpec.SpecLines = new() { new BotSpecLine(key, 50, 1) };
                // Initialize the real build/catalog at the starting level.
                owner.Level = initial == 40 ? (byte)39 : (byte)9;
                RefreshGroup(owner, bot);
                CompanionLevelRefresh.Refresh(owner);
                owner.Level = initial;
                CompanionLevelRefresh.Refresh(owner);
                Assert.That(bot.GetBaseSpecLevel(key), Is.EqualTo(initial));
                Assert.That(bot.HasAbility(ability), Is.EqualTo(initial >= 30));
                Spell oldSpell = bot.Spells.Single();
                double beforeDamage = new DirectDamageSpellHandler(bot, oldSpell, bot.GetSpellLine(key)).CalculateDamageBase(bot);
                // A stale style/AI selection must disappear on a level reduction.
                bot.Styles.Add(new Style(new DbStyle { Name="Old style", SpecLevelRequirement=30 }, null));
                typeof(GameBot).GetProperty(nameof(GameBot.HealBig)).SetValue(bot, oldSpell);
                bot.CrowdControlSpells = new() { oldSpell };
                owner.Level = target;
                Assert.That(CompanionLevelRefresh.Refresh(owner), Does.StartWith("Refreshed 1"));
                Assert.That(bot.GetBaseSpecLevel(key), Is.EqualTo(target));
                Assert.That(bot.HasAbility(ability), Is.EqualTo(target >= 30));
                Assert.That(bot.Styles, Is.Empty);
                if (target < 10)
                {
                    Assert.That(bot.Spells, Is.Empty);
                    Assert.That(bot.HarmfulSpells?.Count ?? 0, Is.Zero);
                    Assert.That(bot.HealBig, Is.Null);
                    Assert.That(bot.CrowdControlSpells?.Count ?? 0, Is.Zero);
                    Assert.That(bot.CanCastHarmfulSpells, Is.False);
                }
                else
                {
                    Spell learned = bot.Spells.Single();
                    Assert.That(learned.Level, Is.EqualTo(target >= 30 ? 30 : 10));
                    Assert.That(bot.HarmfulSpells.Single(), Is.SameAs(learned));
                    double damage = new DirectDamageSpellHandler(bot, learned, bot.GetSpellLine(key)).CalculateDamageBase(bot);
                    Assert.That(damage, initial < target ? Is.GreaterThan(beforeDamage) : Is.LessThan(beforeDamage));
                }
            }
            finally
            {
                if (saved == null) careers.Remove(wizard); else careers[wizard] = saved;
                definitions.Remove(key); lines.Remove(key); spells.Remove(key);
                abilities.Remove(key); abilityDefinitions.Remove(ability);
            }
        }

        [TestCase(false, 7, 7)] [TestCase(false, 0, 20)] [TestCase(true, 7, 20)]
        public void RealOwnerBoundConstructorUsesSavedLevelBeforeStatsSpecsAndEquipment(bool temporary, byte requested, byte expected)
        {
            var owner = (Owner)RuntimeHelpers.GetUninitializedObject(typeof(Owner)); owner.Level = 20;
            var bot = new GameBot(owner, (byte)eCharacterClass.Wizard, "StatTester", (byte)eRace.Briton,
                temporaryGroupHelper: temporary, botLevel: requested);
            _constructed.Add(bot);
            Assert.That(bot.Level, Is.EqualTo(expected));
            Assert.That(bot.Intelligence, Is.EqualTo(70 + Math.Max(0, expected - 5)));
            Assert.That(bot.GetSpecList().All(spec => spec.Level <= expected), Is.True);
        }

        [Test]
        public void SavedProfileLoadingDoesNotConstructAtOwnersHigherLevel()
        {
            var owner = (Owner)RuntimeHelpers.GetUninitializedObject(typeof(Owner)); owner.Level = 30;
            ((ReadDatabase)Empty).Profile = new BotProfile { BotId=999991, OwnerCharacterID=owner.ObjectId,
                Name="ProfileTester", ClassId=(byte)eCharacterClass.Wizard, RaceId=(byte)eRace.Briton, Level=7 };
            var bot = BotDatabase.LoadBot(owner, 999991);
            Assert.That(bot, Is.Not.Null);
            _constructed.Add(bot);
            Assert.That(bot.Level, Is.EqualTo(7));
            Assert.That(bot.Intelligence, Is.EqualTo(72));
            Assert.That(bot.GetSpecList().All(spec => spec.Level <= 7), Is.True);
        }

        [Test]
        public void RealAutonomousConstructorRetainsSavedLevelAndReconstructsAfterLevelChange()
        {
            var record = new OfflineWorldBotRecord { BotId=0, Name="AutonomousStatTester", Realm=(int)eRealm.Albion,
                ClassId=(int)eCharacterClass.Wizard, RaceId=(int)eRace.Briton, Level=6, Health=12, Mana=9, Endurance=20 };
            var first = new GameBot(record); _constructed.Add(first);
            Assert.That(first.Level, Is.EqualTo(6)); Assert.That(first.Intelligence, Is.EqualTo(71));
            Assert.That(first.MaxMana, Is.EqualTo(51)); Assert.That(first.Mana, Is.EqualTo(9));
            first.Level = 10;
            Invoke(first, "ApplyLevelStatGrowth", 10);
            Assert.That(first.Intelligence, Is.EqualTo(75)); Assert.That(first.MaxMana, Is.EqualTo(75));
            Assert.That(first.Mana, Is.EqualTo(9)); Assert.That(first.Health, Is.EqualTo(12));
            var saved = JsonSerializer.Deserialize<OfflineWorldBotRecord>(JsonSerializer.Serialize(first.PrepareAutonomousStateSnapshot()));
            var reloaded = new GameBot(saved); _constructed.Add(reloaded);
            Assert.That(reloaded.Level, Is.EqualTo(10)); Assert.That(Stats(reloaded), Is.EqualTo(Stats(first)));
            Assert.That(reloaded.MaxMana, Is.EqualTo(75)); Assert.That(reloaded.Mana, Is.EqualTo(9));
        }

        [Test]
        public void PatchedLifecycleMethodsLoadAndJit()
        {
            foreach (MethodInfo method in new[] { typeof(GameNPC).GetMethod(nameof(GameNPC.SetStats)),
                typeof(GameBot).GetMethod("InitializeBotStats", Hidden), typeof(GameBot).GetMethod("ApplyLevelStatGrowth", Hidden),
                typeof(GameBot).GetMethod(nameof(GameBot.RebuildPlayerBaseStats)) })
            {
                RuntimeHelpers.PrepareMethod(method.MethodHandle);
                Assert.That(method.MethodHandle.GetFunctionPointer(), Is.Not.EqualTo(IntPtr.Zero));
            }
        }

        private StatBot Make()
        {
            var bot = (StatBot)RuntimeHelpers.GetUninitializedObject(typeof(StatBot));
            Raw(bot, "m_charStat", new short[8]);
            Raw(bot, "m_abilities", new Dictionary<string, Ability>());
            Raw(bot, "_abilitiesLock", new System.Threading.Lock());
            Raw(bot, "<TempProperties>k__BackingField", new PropertyCollection());
            Raw(bot, "<BuffBonusMultCategory1>k__BackingField", new MultiplicativePropertiesHybrid());
            bot.effectListComponent = EffectListComponent.Create(bot);
            _constructed.Add(bot);
            foreach (string p in new[] { "ItemBonus", "AbilityBonus", "BaseBuffBonusCategory", "SpecBuffBonusCategory", "OtherBonus", "DebuffCategory", "SpecDebuffCategory" })
                Raw(bot, "<"+p+">k__BackingField", new PropertyIndexer());
            bot.Class = new ClassWizard(); bot.Race = (short)eRace.Briton;
            return bot;
        }
        private static int[] Stats(GameBot bot) => Enumerable.Range((int)eStat._First, 8).Select(i => bot.GetBaseStat((eStat)i)).ToArray();
        private static void Raw(GameLiving actor, string field, object value) => typeof(GameLiving).GetField(field, Hidden).SetValue(actor, value);
        private static void Invoke(GameBot bot, string method, params object[] args) => typeof(GameBot).GetMethod(method, Hidden).Invoke(bot, args);
    }
}
