using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Threading;
using DOL.AI.Brain;
using DOL.Database;
using DOL.Database.Handlers;
using DOL.Events;
using DOL.GS;
using DOL.GS.Keeps;
using DOL.GS.PacketHandler;
using DOL.GS.PropertyCalc;
using DOL.GS.ServerRules;
using NUnit.Framework;
using P = DOL.GS.ServerProperties.Properties;
using Contribution = DOL.GS.ServerRules.IServerRules.EntityCountTotalDamagePair;

namespace DOL.UnitTests
{
    [TestFixture, NonParallelizable]
    public class UT_BeezExperience
    {
        private sealed class Server : GameServer
        {
            protected override IServerRules ServerRulesImpl => new NormalServerRules();
            protected override IObjectDatabase DataBaseImpl => DispatchProxy.Create<IObjectDatabase, EmptyProxy>();
        }
        public class EmptyProxy : DispatchProxy
        {
            public Action<MethodInfo> OnCall;
            protected override object Invoke(MethodInfo method, object[] args)
            {
                OnCall?.Invoke(method);
                Type type = method.ReturnType;
                if (type.IsGenericType && typeof(IEnumerable).IsAssignableFrom(type))
                    return Activator.CreateInstance(typeof(List<>).MakeGenericType(type.GetGenericArguments()));
                return type == typeof(void) ? null : type.IsValueType ? Activator.CreateInstance(type) : null;
            }
        }
        private sealed class Player : GamePlayer
        {
            private Player() : base(null, null) { }
            public override byte Level { get; set; }
            public override eRealm Realm { get; set; }
            public override bool IsAlive => true;
            public override int EffectiveLevel => Level;
            public override int RealmPointsValue => 100;
            public override int BountyPointsValue => 100;
            public GainedExperienceEventArgs Reward;
            public override int X => 0;
            public override int Y => 0;
            public override int Z => 0;
            public long Total;
            public override void GainExperience(GainedExperienceEventArgs arguments, bool notify = true)
            { Reward = arguments; Total += arguments.ExpTotal; }
        }
        private sealed class Bot : GameBot
        {
            private Bot() : base((OfflineWorldBotRecord)null) { }
            public override byte Level { get; set; }
            public override eRealm Realm { get; set; }
            public override bool IsAlive => true;
            public override int EffectiveLevel => Level;
            public override int X => 0;
            public override int Y => 0;
            public override int Z => 0;
            public long Total;
            public bool ApplyActualExperience;
            public override void GainExperience(GainedExperienceEventArgs arguments, bool notify = true)
            { if (ApplyActualExperience) base.GainExperience(arguments, notify); else Total += arguments.ExpTotal; }
        }
        private GameServer _previous;
        private double _xp, _rvr, _camp, _dungeon, _rp, _bp;
        private int _cap, _pvpCap, _bonus, _multiplier, _worth;
        private bool _zones;
        private PetTestLanguageScope _language;
        private object _translations;
        private IPropertyCalculator[] _calculators;
        private readonly List<GamePlayer> _actors = new();
        [SetUp]
        public void SetUp()
        {
            DOL.Logging.LoggerManager.InitializeWithExplicitLibrary(null, DOL.Logging.LogLibrary.None);
            _language = new PetTestLanguageScope();
            _previous = GameServer.Instance;
            var translations = typeof(DOL.Language.LanguageMgr).GetProperty("Translations")!;
            _translations = translations.GetValue(null);
            if (_translations == null) translations.SetValue(null, Activator.CreateInstance(translations.PropertyType));
            var calculators = (IPropertyCalculator[])typeof(GameLiving).GetField("m_propertyCalc", BindingFlags.Static | BindingFlags.NonPublic)!.GetValue(null);
            _calculators = (IPropertyCalculator[])calculators.Clone();
            GameLiving.LoadCalculators();
            Server server = (Server)RuntimeHelpers.GetUninitializedObject(typeof(Server));
            Field(typeof(GameServer), server, "m_keepManager", DispatchProxy.Create<IKeepManager, EmptyProxy>());
            GameServer.LoadTestDouble(server);
            _rp = P.RP_RATE; _bp = P.BP_RATE; P.RP_RATE = P.BP_RATE = 1;
            _xp = P.XP_RATE; _rvr = P.RvR_XP_RATE; _camp = P.MAX_CAMP_BONUS; _dungeon = P.MAX_DUNGEON_CAMP_BONUS;
            _cap = P.XP_CAP_PERCENT; _pvpCap = P.XP_PVP_CAP_PERCENT; _bonus = P.DARKNESS_FALLS_XP_BONUS_PERCENT;
            _multiplier = P.RVR_KILL_XP_MULTIPLIER; _worth = P.RP_WORTH_SECONDS; _zones = P.ENABLE_ZONE_BONUSES;
            P.XP_RATE = P.RvR_XP_RATE = 1; P.MAX_CAMP_BONUS = .55; P.MAX_DUNGEON_CAMP_BONUS = .66;
            P.XP_CAP_PERCENT = P.XP_PVP_CAP_PERCENT = 125; P.DARKNESS_FALLS_XP_BONUS_PERCENT = 20;
            P.RVR_KILL_XP_MULTIPLIER = 100; P.RP_WORTH_SECONDS = 300; P.ENABLE_ZONE_BONUSES = true;
        }
        [TearDown]
        public void TearDown()
        {
            P.RP_RATE = _rp; P.BP_RATE = _bp;
            P.XP_RATE = _xp; P.RvR_XP_RATE = _rvr; P.MAX_CAMP_BONUS = _camp; P.MAX_DUNGEON_CAMP_BONUS = _dungeon;
            P.XP_CAP_PERCENT = _cap; P.XP_PVP_CAP_PERCENT = _pvpCap; P.DARKNESS_FALLS_XP_BONUS_PERCENT = _bonus;
            P.RVR_KILL_XP_MULTIPLIER = _multiplier; P.RP_WORTH_SECONDS = _worth; P.ENABLE_ZONE_BONUSES = _zones;
            foreach (var actor in _actors)
            {
                actor.StopHealthRegeneration(); actor.StopPowerRegeneration(); actor.StopEnduranceRegeneration();
                ServiceObjectStore.Remove(actor.effectListComponent); ServiceObjectStore.Remove(actor.castingComponent);
            }
            _actors.Clear();
            var calculators = (IPropertyCalculator[])typeof(GameLiving).GetField("m_propertyCalc", BindingFlags.Static | BindingFlags.NonPublic)!.GetValue(null);
            Array.Copy(_calculators, calculators, calculators.Length);
            typeof(DOL.Language.LanguageMgr).GetProperty("Translations")!.SetValue(null, _translations);
            GameServer.LoadTestDouble(_previous);
            _language.Dispose();
        }
        private static void Field(Type type, object target, string name, object value) =>
            type.GetField(name, BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public)!.SetValue(target, value);
        private static void Initialize(GameLiving actor)
        {
            Field(typeof(GameLiving), actor, "<TempProperties>k__BackingField", new PropertyCollection());
            Field(typeof(GameLiving), actor, "XpGainersLock", new Lock());
            Field(typeof(GameLiving), actor, "m_xpGainers", new Dictionary<GameLiving, double>());
            actor.ObjectState = GameObject.eObjectState.Active;
        }
        private static Player Human(byte level = 30, eRealm realm = eRealm.Albion)
        {
            Player player = (Player)RuntimeHelpers.GetUninitializedObject(typeof(Player));
            Initialize(player); player.Level = level; player.Realm = realm;
            Field(typeof(GamePlayer), player, "m_dbCharacter", new DbCoreCharacter { ObjectId = Guid.NewGuid().ToString(), GainXP = true, GainRP = true, LastPlayed = DateTime.Now, PlayedTime = 10000 });
            Field(typeof(GamePlayer), player, "<AwardLock>k__BackingField", new Lock());
            return player;
        }
        private GamePlayer Character(byte level = 30, eRealm realm = eRealm.Albion, ushort regionId = 1)
        {
            GamePlayer player = GamePlayer.CreateTestableGamePlayer();
            Field(typeof(GamePlayer), player, "m_dbCharacter", new DbCoreCharacter { ObjectId = Guid.NewGuid().ToString(), Level = level, Realm = (int)realm,
                GainXP = true, GainRP = true, LastPlayed = DateTime.Now, PlayedTime = 10000, Health = 1, Name = "XP character" });
            GameClient client = (GameClient)RuntimeHelpers.GetUninitializedObject(typeof(GameClient));
            Field(typeof(GameClient), client, "<Account>k__BackingField", new DbAccount { ObjectId = Guid.NewGuid().ToString(), Language = "EN", PrivLevel = 1 });
            client.Out = DispatchProxy.Create<IPacketLib, EmptyProxy>();
            Field(typeof(GamePlayer), player, "m_client", client);
            Field(typeof(GamePlayer), player, "m_steed", new WeakReference(null));
            Field(typeof(GameLiving), player, "m_inventory", new GamePlayerInventory(player));
            player.ObjectState = GameObject.eObjectState.Active;
            player.CurrentRegion = Location(regionId);
            player.Experience = player.ExperienceForCurrentLevel;
            player.CreateStatistics();
            _actors.Add(player);
            return player;
        }
        private static Bot Autonomous(byte level = 30, eRealm realm = eRealm.Midgard, bool temporary = false)
        {
            Bot bot = (Bot)RuntimeHelpers.GetUninitializedObject(typeof(Bot));
            Initialize(bot); bot.Level = level; bot.Realm = realm;
            Field(typeof(GameNPC), bot, "m_brains", new ArrayList());
            Field(typeof(GameNPC), bot, "m_ownBrain", new BotBrain { Body = bot });
            typeof(GameBot).GetProperty(nameof(GameBot.IsAutonomousWorldBot))!.SetValue(bot, true);
            typeof(GameBot).GetProperty(nameof(GameBot.IsTemporaryGroupHelper))!.SetValue(bot, temporary);
            typeof(GameBot).GetProperty(nameof(GameBot.DatabaseID))!.SetValue(bot, DateTime.UtcNow.Ticks);
            return bot;
        }
        private static Region Location(ushort id)
        {
            Region region = new(new RegionData { Id = id, Name = "XP test", Description = "XP test" });
            region.Zones.Add(new Zone(region, id, "XP test", 0, 0, 65536, 65536, id, false, 0, false, 0, 0, 0, 0, 0));
            return region;
        }
        [TestCase(1, 30, 1, 2559676L, 2559676L)]
        [TestCase(20, 30, 1, 2741330L, 2741330L)]
        [TestCase(249, 30, 1, 2741330L, 3071610L)]
        [TestCase(249, 33, 1, 3426663L, 3839514L)]
        [TestCase(249, 30, 2, 1473877L, 1639017L)]
        public void NativeNpcAwardRetainsCampGroupsCapsAndAddsDfFloor(int regionId, int mobLevel, int members, long before, long after)
        {
            Region region = Location((ushort)regionId);
            Player player = Human(); player.CurrentRegion = region;
            GameNPC mob = new() { Level = (byte)mobLevel, CurrentRegion = region, CampBonus = 1 };
            Contribution contribution = new(members, 100, player);
            Dictionary<GamePlayer, Contribution> solo = new() { [player] = contribution };
            Dictionary<Group, Contribution> groups = new();
            if (members > 1) { player.Group = new Group(player); groups[player.Group] = contribution; }
            typeof(AbstractServerRules).GetMethod("AwardPlayerOnNpcKill", BindingFlags.NonPublic | BindingFlags.Static)!.Invoke(null,
                new object[] { player, 100d, mob, solo, groups, new Dictionary<BattleGroup, Contribution>() });
            Assert.That(player.Reward.XPSource, Is.EqualTo(eXPSource.NPC));
            Assert.That(player.Reward.ExpTotal, Is.EqualTo(before));
            long zone = player.Reward.ExpBase * BeezExperiencePolicy.ZoneBonus(eXPSource.NPC, (ushort)regionId, 0) / 100;
            Assert.That(player.Reward.ExpTotal + zone, Is.EqualTo(after));
            TestContext.WriteLine($"Region {regionId}, mob {mobLevel}, group {members}: base={player.Reward.ExpBase}, camp={player.Reward.ExpCampBonus}, group={player.Reward.ExpGroupBonus}, before={before}, after={after}");
        }
        [Test]
        public void BoostedPveRateIsRestoredOnlyForDfNpcKills()
        {
            P.XP_RATE = 10; P.RvR_XP_RATE = 1;
            Assert.That(BeezExperiencePolicy.PlayerRate(eXPSource.NPC, 249, true), Is.EqualTo(10));
            Assert.That(BeezExperiencePolicy.PlayerRate(eXPSource.NPC, 163, true), Is.EqualTo(1));
            Assert.That(BeezExperiencePolicy.PlayerRate(eXPSource.Other, 249, true), Is.EqualTo(1));
            Assert.That(BeezExperiencePolicy.PlayerRate(eXPSource.NPC, 1, false), Is.EqualTo(10));
            P.RvR_XP_RATE = 12;
            Assert.That(BeezExperiencePolicy.PlayerRate(eXPSource.NPC, 249, true), Is.EqualTo(12));
        }
        [TestCase(0, 20)] [TestCase(15, 20)] [TestCase(50, 50)]
        public void DfBonusIsAFloorNotAnAdditionalMultiplier(int configured, int expected) =>
            Assert.That(BeezExperiencePolicy.ZoneBonus(eXPSource.NPC, 249, configured), Is.EqualTo(expected));
        [Test]
        public void DfBonusCanBeDisabledAndDoesNotChangeOtherSourcesOrRegions()
        {
            P.DARKNESS_FALLS_XP_BONUS_PERCENT = 0;
            Assert.That(BeezExperiencePolicy.ZoneBonus(eXPSource.NPC, 249, 0), Is.Zero);
            P.DARKNESS_FALLS_XP_BONUS_PERCENT = 20;
            Assert.That(BeezExperiencePolicy.ZoneBonus(eXPSource.Other, 249, 0), Is.Zero);
            Assert.That(BeezExperiencePolicy.ZoneBonus(eXPSource.NPC, 20, 0), Is.Zero);
            P.ENABLE_ZONE_BONUSES = false;
            Assert.That(BeezExperiencePolicy.ZoneBonus(eXPSource.NPC, 20, 50), Is.Zero);
            Assert.That(BeezExperiencePolicy.ZoneBonus(eXPSource.NPC, 249, 50), Is.EqualTo(20));
        }
        [TestCase(30, 30, 1, 1d, 6605616L)]
        [TestCase(30, 33, 1, 1d, 8257020L)]
        [TestCase(30, 30, 2, 1d, 3302808L)]
        [TestCase(30, 30, 1, .333d, 2199670L)]
        [TestCase(50, 50, 1, 1d, 0L)]
        [TestCase(30, 1, 1, 1d, 0L)]
        [TestCase(30, 30, 0, 1d, 0L)]
        [TestCase(30, 30, 1, 0d, 0L)]
        public void RvrAmountUsesVictimLevelCapsContributionAndIntegerRounding(int recipient, int victim, int count, double damage, long expected) =>
            Assert.That(RvrExperienceRewards.CalculateNative((byte)recipient, (byte)victim, count, damage), Is.EqualTo(expected));
        [TestCase(false)] [TestCase(true)]
        public void RealAndAutonomousVictimsAwardExactlyOnce(bool botVictim)
        {
            Player recipient = Human();
            GameLiving victim = botVictim ? Autonomous() : Human(30, eRealm.Midgard);
            victim.XPGainers[recipient] = 100;
            RvrExperienceRewards.Award(victim); RvrExperienceRewards.Award(victim);
            Assert.That(recipient.Total, Is.EqualTo(660561600));
            Assert.That(recipient.Reward.AllowMultiply, Is.False);
        }
        [Test]
        public void GroupIncludesZeroDamageSupportAndSharesWithAutonomousMember()
        {
            Player player = Human(); Bot bot = Autonomous(30, eRealm.Albion); Bot victim = Autonomous();
            Group group = new(player); player.Group = group; bot.Group = group;
            victim.XPGainers[player] = 100; victim.XPGainers[bot] = 0;
            RvrExperienceRewards.Award(victim);
            Assert.That(player.Total, Is.EqualTo(330280800)); Assert.That(bot.Total, Is.EqualTo(330280800));
        }
        [TestCase("friendly")] [TestCase("helper")] [TestCase("gray")] [TestCase("none")] [TestCase("inactive")] [TestCase("noXp")] [TestCase("recent")]
        public void InvalidKillsDoNotGiveXp(string reason)
        {
            Player player = Human(); Bot victim = Autonomous();
            if (reason == "friendly") victim.Realm = player.Realm;
            if (reason == "helper") typeof(GameBot).GetProperty(nameof(GameBot.IsTemporaryGroupHelper))!.SetValue(victim, true);
            if (reason == "gray") victim.Level = 1;
            if (reason == "none") victim.Realm = eRealm.None;
            if (reason == "inactive") player.ObjectState = GameObject.eObjectState.Inactive;
            if (reason == "noXp") player.GainXP = false;
            if (reason == "recent") victim.TempProperties.SetProperty((string)typeof(AutonomousBotRealmPointRewards).GetField("LastRealmPointDeathTickProperty", BindingFlags.Static | BindingFlags.NonPublic)!.GetRawConstantValue(), GameLoop.GameLoopTime);
            victim.XPGainers[player] = 100; RvrExperienceRewards.Award(victim);
            Assert.That(player.Total, Is.Zero);
        }
        [Test]
        public void GuardDamageReducesShareAndNonFiniteDamageCannotContaminateReward()
        {
            Player player = Human(); Bot victim = Autonomous(); GameNPC guard = new();
            victim.XPGainers[player] = 25; victim.XPGainers[guard] = 75;
            victim.XPGainers[Human()] = double.NaN;
            RvrExperienceRewards.Award(victim);
            Assert.That(player.Total, Is.EqualTo(165140400));
        }
        [TestCase(1, false)] [TestCase(20, false)] [TestCase(249, false)] [TestCase(163, false)]
        [TestCase(1, true)] [TestCase(20, true)] [TestCase(249, true)] [TestCase(163, true)]
        public void DeathRewardIncreasesActualCharacterExperienceInEveryRegion(int regionId, bool autonomous)
        {
            GamePlayer player = Character(regionId: (ushort)regionId);
            GameLiving victim = autonomous ? Autonomous() : Character(30, eRealm.Midgard, (ushort)regionId);
            victim.CurrentRegion = player.CurrentRegion;
            victim.XPGainers[player] = 100;
            long before = player.Experience;
            if (autonomous) GameServer.ServerRules.OnNpcKilled((GameNPC)victim, player);
            else GameServer.ServerRules.OnPlayerKilled((GamePlayer)victim, player);
            var db = (DbCoreCharacter)typeof(GamePlayer).GetField("m_dbCharacter", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(player);
            Assert.That(player.Experience - before, Is.EqualTo(660561600));
            Assert.That(db.Experience, Is.EqualTo(player.Experience), "Actual character record must change, not only a captured reward argument");
            Assert.That(player.RealmPoints, Is.EqualTo(100), "Existing RP must remain intact");
            Assert.That(player.BountyPoints, Is.EqualTo(autonomous ? 0 : 19), "Preserve existing BP: bot victims currently award none");
            TestContext.WriteLine($"Death region={regionId} autonomous={autonomous}: character XP={before}->{player.Experience}; RP={player.RealmPoints}; BP={player.BountyPoints}");
        }
        [TestCase(false)] [TestCase(true)]
        public void GroupDeathRewardIncreasesBothActualCharacterRecords(bool autonomous)
        {
            GamePlayer first = Character(), second = Character();
            GameLiving victim = autonomous ? Autonomous() : Character(30, eRealm.Midgard);
            victim.CurrentRegion = first.CurrentRegion; second.CurrentRegion = first.CurrentRegion;
            Group group = new(first); first.Group = group; second.Group = group;
            victim.XPGainers[first] = 100; victim.XPGainers[second] = 0;
            long beforeFirst = first.Experience, beforeSecond = second.Experience;
            if (autonomous) GameServer.ServerRules.OnNpcKilled((GameNPC)victim, first);
            else GameServer.ServerRules.OnPlayerKilled((GamePlayer)victim, first);
            Assert.That(first.Experience - beforeFirst, Is.EqualTo(330280800));
            Assert.That(second.Experience - beforeSecond, Is.EqualTo(330280800));
        }
        [TestCase(1, 30, 1, 1, 2559676L)] [TestCase(20, 30, 1, 1, 2741330L)] [TestCase(249, 30, 1, 1, 3071610L)]
        [TestCase(249, 33, 1, 1, 3839514L)] [TestCase(20, 30, 2, 1, 1473877L)] [TestCase(249, 30, 2, 1, 1639017L)]
        [TestCase(1, 30, 1, 10, 17422312L)] [TestCase(20, 30, 1, 10, 17603966L)] [TestCase(249, 30, 1, 10, 20906766L)]
        public void NativeNpcAwardIsActuallyAppliedToCharacterExperience(int regionId, int mobLevel, int members, int rate, long expected)
        {
            P.XP_RATE = rate;
            GamePlayer player = Character(regionId: (ushort)regionId);
            GameNPC mob = new() { Level = (byte)mobLevel, CurrentRegion = player.CurrentRegion, CampBonus = 1 };
            Contribution contribution = new(members, 100, player);
            Dictionary<GamePlayer, Contribution> solo = new() { [player] = contribution };
            Dictionary<Group, Contribution> groups = new();
            if (members > 1) { player.Group = new Group(player); groups[player.Group] = contribution; }
            long before = player.Experience;
            typeof(AbstractServerRules).GetMethod("AwardPlayerOnNpcKill", BindingFlags.NonPublic | BindingFlags.Static)!.Invoke(null,
                new object[] { player, 100d, mob, solo, groups, new Dictionary<BattleGroup, Contribution>() });
            Assert.That(player.Experience - before, Is.EqualTo(expected));
            TestContext.WriteLine($"Actual PvE XP region={regionId} mob={mobLevel} group={members} rate={rate}: +{player.Experience - before}");
        }
        [Test]
        public void StrongerInstalledDfBonusIsKeptWithoutDoubleApplication()
        {
            GamePlayer player = Character(regionId: 249);
            player.CurrentZone.BonusExperience = 75;
            long before = player.Experience;
            player.GainExperience(new GainedExperienceEventArgs(1651404, 1089926, 0, 0, 0, 0, false, true, eXPSource.NPC));
            Assert.That(player.Experience - before, Is.EqualTo(3979883));
        }
        [Test]
        public void AutonomousRecipientActuallyGainsProgressionExperience()
        {
            Bot recipient = Autonomous(49, eRealm.Albion), victim = Autonomous(49);
            recipient.ApplyActualExperience = true;
            typeof(GameBot).GetProperty(nameof(GameBot.Experience))!.SetValue(recipient, GamePlayer.GetExperienceAmountForLevel(48));
            long before = recipient.Experience;
            victim.XPGainers[recipient] = 100;
            RvrExperienceRewards.Award(victim);
            Assert.That(recipient.Experience - before, Is.EqualTo(14605414800L));
            Assert.That(recipient.AutonomousStateDirty, Is.True);
        }
        [Test]
        public void SameAccountAndOutOfRangeKillsDoNotAlterActualCharacterExperience()
        {
            GamePlayer player = Character(), victim = Character(30, eRealm.Midgard);
            victim.CurrentRegion = player.CurrentRegion;
            victim.Client.Account.ObjectId = player.Client.Account.ObjectId;
            victim.XPGainers[player] = 100;
            long before = player.Experience;
            RvrExperienceRewards.Award(victim);
            Assert.That(player.Experience, Is.EqualTo(before));
            Bot distant = Autonomous(); distant.CurrentRegion = player.CurrentRegion;
            player.X = WorldMgr.MAX_EXPFORKILL_DISTANCE + 1000;
            distant.XPGainers[player] = 100;
            RvrExperienceRewards.Award(distant);
            Assert.That(player.Experience, Is.EqualTo(before));
        }
        [Test]
        public void DuelAndRecentHumanDeathDoNotAlterActualCharacterExperience()
        {
            GamePlayer player = Character();
            foreach (bool duel in new[] { true, false })
            {
                GamePlayer victim = Character(30, eRealm.Midgard);
                victim.CurrentRegion = player.CurrentRegion;
                if (duel) Field(typeof(GamePlayer), victim, "m_releaseType", eReleaseType.Duel);
                else victim.DeathTime = victim.PlayedTime;
                victim.XPGainers[player] = 100;
                long before = player.Experience; RvrExperienceRewards.Award(victim);
                Assert.That(player.Experience, Is.EqualTo(before));
            }
        }
        [Test]
        public void LevelCapAndXpOptOutLeaveActualExperienceUnchanged()
        {
            foreach (byte level in new byte[] { 30, 50 })
            {
                GamePlayer player = Character(level); Bot victim = Autonomous(level);
                victim.CurrentRegion = player.CurrentRegion; victim.XPGainers[player] = 100;
                if (level == 30) player.GainXP = false;
                long before = player.Experience; RvrExperienceRewards.Award(victim);
                Assert.That(player.Experience, Is.EqualTo(before));
            }
        }
        [Test]
        public void PetAndOwnerContributionGrantOneActualOwnerReward()
        {
            GamePlayer player = Character(); Bot victim = Autonomous(); victim.CurrentRegion = player.CurrentRegion;
            GameNPC pet = new(new ControlledMobBrain(player));
            victim.XPGainers[player] = 50; victim.XPGainers[pet] = 50;
            long before = player.Experience;
            RvrExperienceRewards.Award(victim);
            Assert.That(player.Experience - before, Is.EqualTo(660561600));
        }
        [TestCase(10, 1, 2048000L)] [TestCase(10, 2, 1024000L)]
        [TestCase(30, 1, 660561600L)] [TestCase(30, 2, 330280800L)]
        [TestCase(49, 1, 14605414800L)] [TestCase(49, 2, 7302707400L)]
        public void MultipliedNativeSoloAndGroupRewardsMatchAtMultipleLevels(int level, int members, long expected)
        {
            long native = RvrExperienceRewards.CalculateNative((byte)level, (byte)level, members, 1);
            Assert.That(RvrExperienceRewards.ScaleReward(native, 0), Is.EqualTo(expected));
        }
        [TestCase(1, 6605616L)] [TestCase(100, 660561600L)] [TestCase(0, 0L)] [TestCase(-1, 0L)]
        public void MultiplierIsConfigurableAndNeverUsesPveRate(int multiplier, long expected)
        {
            P.RVR_KILL_XP_MULTIPLIER = multiplier; P.XP_RATE = 10; P.RvR_XP_RATE = 17;
            GamePlayer player = Character(); Bot victim = Autonomous(); victim.CurrentRegion = player.CurrentRegion;
            victim.XPGainers[player] = 100; long before = player.Experience;
            RvrExperienceRewards.Award(victim);
            Assert.That(player.Experience - before, Is.EqualTo(expected));
        }
        [TestCase(10, 1, false)] [TestCase(10, 1, true)] [TestCase(10, 2, false)] [TestCase(10, 2, true)]
        [TestCase(30, 1, false)] [TestCase(30, 1, true)] [TestCase(30, 2, false)] [TestCase(30, 2, true)]
        [TestCase(49, 1, false)] [TestCase(49, 1, true)] [TestCase(49, 2, false)] [TestCase(49, 2, true)]
        public void ActualSoloAndGroupDeathRewardsScaleAtMultipleLevelsWithoutPveRate(int level, int members, bool autonomous)
        {
            P.XP_RATE = P.RvR_XP_RATE = 10;
            GamePlayer player = Character((byte)level);
            GameLiving victim = autonomous ? Autonomous((byte)level) : Character((byte)level, eRealm.Midgard);
            victim.CurrentRegion = player.CurrentRegion; victim.XPGainers[player] = 100;
            GamePlayer support = null;
            if (members == 2)
            {
                support = Character((byte)level); support.CurrentRegion = player.CurrentRegion;
                Group group = new(player); player.Group = group; support.Group = group;
                victim.XPGainers[support] = 0;
            }
            long before = player.Experience, supportBefore = support?.Experience ?? 0;
            if (autonomous) GameServer.ServerRules.OnNpcKilled((GameNPC)victim, player);
            else GameServer.ServerRules.OnPlayerKilled((GamePlayer)victim, player);
            long expected = 4 * GameServer.ServerRules.GetExperienceForLiving(level) / members * 100;
            Assert.That(player.Experience - before, Is.EqualTo(expected));
            if (support != null) Assert.That(support.Experience - supportBefore, Is.EqualTo(expected));
        }
        [TestCase(false)] [TestCase(true)]
        public void RealmAndBountyPointsFinishBeforeLargeCharacterXpGrant(bool autonomous)
        {
            GamePlayer player = Character();
            GameLiving victim = autonomous ? Autonomous() : Character(30, eRealm.Midgard);
            victim.CurrentRegion = player.CurrentRegion; victim.XPGainers[player] = 100;
            long before = player.Experience;
            bool rpPaidBeforeXp = false, bpPaidBeforeXp = autonomous;
            ((EmptyProxy)player.Out).OnCall = method =>
            {
                if (method.Name != nameof(IPacketLib.SendUpdatePoints)) return;
                if (player.RealmPoints == 100 && player.Experience == before) rpPaidBeforeXp = true;
                if (player.BountyPoints == 19 && player.Experience == before) bpPaidBeforeXp = true;
            };
            if (autonomous) GameServer.ServerRules.OnNpcKilled((GameNPC)victim, player);
            else GameServer.ServerRules.OnPlayerKilled((GamePlayer)victim, player);
            Assert.That(rpPaidBeforeXp, Is.True);
            Assert.That(bpPaidBeforeXp, Is.True);
            Assert.That(player.Experience - before, Is.EqualTo(660561600));
        }
        [Test]
        public void NativeCapAppliesBeforeMultiplierAndRoundingIsNotRepeated()
        {
            Assert.That(RvrExperienceRewards.ScaleReward(RvrExperienceRewards.CalculateNative(30, 33, 1, 1), 0), Is.EqualTo(825702000));
            Assert.That(RvrExperienceRewards.ScaleReward(RvrExperienceRewards.CalculateNative(30, 30, 1, .333), 0), Is.EqualTo(219967000));
        }
        [Test]
        public void ExtremeSettingsAndStoredExperienceCannotOverflow()
        {
            P.RVR_KILL_XP_MULTIPLIER = int.MaxValue; P.XP_PVP_CAP_PERCENT = int.MaxValue;
            Assert.That(RvrExperienceRewards.CalculateNative(49, 50, 1, 1), Is.GreaterThan(0));
            Assert.That(RvrExperienceRewards.ScaleReward(long.MaxValue, 0), Is.EqualTo(long.MaxValue));
            Assert.That(RvrExperienceRewards.ScaleReward(long.MaxValue, long.MaxValue - 7), Is.EqualTo(7));
            Assert.That(RvrExperienceRewards.ScaleReward(long.MaxValue, long.MaxValue), Is.Zero);
            GamePlayer player = Character(); player.Experience = long.MaxValue - 7;
            Bot victim = Autonomous(); victim.CurrentRegion = player.CurrentRegion; victim.XPGainers[player] = 100;
            RvrExperienceRewards.Award(victim);
            Assert.That(player.Experience, Is.EqualTo(long.MaxValue));
        }
        [Test]
        public void MoreThanThreeEligibleDeathsOfSameVictimAreRewardedWithoutRollingLedger()
        {
            Player player = Human(); Bot victim = Autonomous();
            // Each iteration represents a new otherwise-eligible death after native worthiness clears.
            for (int i = 0; i < 5; i++)
            {
                victim.TempProperties.RemoveProperty("beez.rvr.xp.last.death");
                victim.XPGainers[player] = 100;
                RvrExperienceRewards.Award(victim);
            }
            Assert.That(player.Total, Is.EqualTo(5 * 660561600L));
        }
        [Test]
        public void ConcurrentDuplicateDeathPaysActualCharacterOnlyOnce()
        {
            GamePlayer player = Character(); Bot victim = Autonomous(); victim.CurrentRegion = player.CurrentRegion;
            victim.XPGainers[player] = 100; long before = player.Experience;
            System.Threading.Tasks.Parallel.For(0, 32, _ => RvrExperienceRewards.Award(victim));
            Assert.That(player.Experience - before, Is.EqualTo(660561600));
        }
    }
}
