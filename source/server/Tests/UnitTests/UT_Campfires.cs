using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using DOL.AI.Brain;
using DOL.Database;
using DOL.GS;
using DOL.GS.PropertyCalc;
using DOL.GS.ServerProperties;
using DOL.GS.Styles;
using NUnit.Framework;

namespace DOL.UnitTests
{
    // Reuse the existing real-player / native regeneration fixture. These tests execute GameServer.dll,
    // EffectListComponent, EffectService, inventory and world objects, without opening a server socket.
    public partial class UT_ManaRoots
    {
        private sealed class CampfireBot : GameBot
        {
            private CampfireBot() : base((OfflineWorldBotRecord)null) { }
            public override eRealm Realm { get; set; }
            public override bool IsAlive => true;
        }
        private sealed class CampfireCombatNpc : GameNPC
        {
            public override double GetPseudoDoubleIncl(RandomDeckEvent deckEvent) => 0.5;
            public override double GetPseudoDouble(RandomDeckEvent deckEvent) => 0.5;
            public override int GetModified(eProperty property) => property == eProperty.CriticalMeleeHitChance ? 0 : base.GetModified(property);
        }
        private sealed class CampfireHitTarget(GameLiving owner) : AttackComponent(owner)
        {
            public override eAttackResult CalculateEnemyAttackResult(WeaponAction action, AttackData attack, DbInventoryItem weapon, ref double effectiveness) => eAttackResult.HitUnstyled;
        }

        private static void CampfireSpatialTick(GameObject actor)
        {
            if ((bool)typeof(SubZoneObject).GetField("_isTransitionQueued", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(actor.SubZoneObject))
                typeof(ZoneService).GetMethod("TickInternal", BindingFlags.Static | BindingFlags.NonPublic).Invoke(null, [actor.SubZoneObject]);
        }

        private static BeezCampfires.CampfireEffect Campfire(GameLiving actor, int tier = 4)
        {
            BeezCampfires.Apply(actor, tier, actor.Realm);
            actor.effectListComponent.BeginTick();
            return actor.effectListComponent.GetSpellEffects(eEffect.Campfire).OfType<BeezCampfires.CampfireEffect>().Single(e => e.IsActive);
        }

        [TestCase(0, 0)] [TestCase(1, 1)] [TestCase(14, 1)] [TestCase(15, 2)] [TestCase(24, 2)]
        [TestCase(25, 3)] [TestCase(39, 3)] [TestCase(40, 4)] [TestCase(50, 4)] [TestCase(80, 4)]
        public void CampfireLevelBrackets(int level, int tier) => Assert.That(BeezCampfires.TierForLevel(level), Is.EqualTo(tier));

        [TestCase(1, 115)] [TestCase(2, 120)] [TestCase(3, 125)] [TestCase(4, 130)]
        public void CampfireMeleeAndStyleBonusLeavesProcSnapshotsAlone(int tier, double expected)
        {
            GamePlayer player = Player();
            Campfire(player, tier);
            var attack = new AttackData { Attacker = player, AttackType = AttackData.eAttackType.MeleeOneHand, StyleDamage = 20, BaseDamage = 80, BaseDamageCap = 240 };
            double damage = 100;
            BeezCampfires.EnhanceMelee(attack, ref damage);
            Assert.That(damage, Is.EqualTo(expected).Within(0.0001));
            Assert.That(attack.StyleDamage, Is.EqualTo((int)(20 * expected / 100)));
            Assert.That(attack.BaseDamage, Is.EqualTo(80));
            Assert.That(attack.BaseDamageCap, Is.EqualTo(240));
        }

        [TestCase(1, false)] [TestCase(2, false)] [TestCase(3, false)] [TestCase(4, false)]
        [TestCase(1, true)] [TestCase(2, true)] [TestCase(3, true)] [TestCase(4, true)]
        public void CampfireNativeMeleePipelineActuallyIncreasesTargetHealthLoss(int tier, bool styled)
        {
            GamePlayer owner = Player();
            var pet = new CampfireCombatNpc();
            var target = new GameNPC();
            Region region = new(new RegionData { Id = 1, Name = "Campfire combat", Description = "test", Mobs = [] });
            owner.CurrentRegion = region;
            pet.CurrentRegion = target.CurrentRegion = region;
            pet.SetOwnBrain(new ControlledMobBrain(owner));
            pet.Level = target.Level = 50;
            pet.Constitution = target.Constitution = 60; pet.Strength = 80;
            pet.ObjectState = target.ObjectState = GameObject.eObjectState.Active;
            pet.Health = pet.MaxHealth; target.Health = target.MaxHealth;
            pet.TargetObject = target;
            pet.attackComponent.attackAction = new NpcAttackAction(pet);
            target.attackComponent = new CampfireHitTarget(target);
            double f1 = Properties.PVE_MOB_DAMAGE_F1, f2 = Properties.PVE_MOB_DAMAGE_F2, rate = Properties.PVE_MELEE_DAMAGE;
            try
            {
                Properties.PVE_MOB_DAMAGE_F1 = 3.2; Properties.PVE_MOB_DAMAGE_F2 = 150; Properties.PVE_MELEE_DAMAGE = 1;
                Style style = styled ? new Style(new DbStyle { Name = "Test strike", ID = 1, GrowthRate = 1, SpecKeyName = "Slash" }, null) : null;
                var action = new WeaponAction(pet, target, null, null, 1, 3000, style);
                AttackData before = pet.attackComponent.LivingMakeAttack(action, target, null, style, 1, 3000, false, true);
                Assert.That(before.Damage, Is.GreaterThan(0));
                Campfire(pet, tier);
                AttackData after = pet.attackComponent.LivingMakeAttack(action, target, null, style, 1, 3000, false, true);
                Assert.That(after.Damage, Is.EqualTo(before.Damage * (1 + BeezCampfires.Bonus(tier) * 0.01)).Within(2));
                Assert.That(after.BaseDamage, Is.EqualTo(before.BaseDamage).Within(0.00001));
                Assert.That(after.BaseDamageCap, Is.EqualTo(before.BaseDamageCap));
                if (styled) Assert.That(after.StyleDamage, Is.GreaterThanOrEqualTo(before.StyleDamage));
                int health = target.Health;
                pet.DealDamage(after);
                Assert.That(health - target.Health, Is.EqualTo(after.Damage));
            }
            finally
            {
                Properties.PVE_MOB_DAMAGE_F1 = f1; Properties.PVE_MOB_DAMAGE_F2 = f2; Properties.PVE_MELEE_DAMAGE = rate;
                foreach (GameNPC npc in new GameNPC[] { pet, target })
                {
                    foreach (ECSGameEffect effect in npc.effectListComponent.GetEffects()) effect.End();
                    npc.effectListComponent.BeginTick(); npc.Brain?.Stop();
                    npc.StopHealthRegeneration(); npc.StopPowerRegeneration(); npc.StopEnduranceRegeneration();
                    ServiceObjectStore.Remove(npc.effectListComponent); ServiceObjectStore.Remove(npc.castingComponent);
                }
            }
        }

        [TestCase(AttackData.eAttackType.Spell)] [TestCase(AttackData.eAttackType.Ranged)]
        public void CampfireDoesNotInflateSpellsDotsProcsOrRanged(AttackData.eAttackType type)
        {
            GamePlayer player = Player();
            Campfire(player);
            var attack = new AttackData { Attacker = player, AttackType = type };
            double damage = 100;
            BeezCampfires.EnhanceMelee(attack, ref damage);
            Assert.That(damage, Is.EqualTo(100));
            Assert.That(player.GetModified(eProperty.SpellDamage), Is.Zero);
            Assert.That(player.GetModified(eProperty.MeleeDamage), Is.Zero, "The dedicated final-melee bonus must not leak into proc snapshots.");
        }

        [Test]
        public void CampfireRefreshHasFullSixtySecondsAndDoesNotAccumulateRegeneration()
        {
            GamePlayer player = Player();
            BeezCampfires.CampfireEffect first = Campfire(player);
            Assert.That(first.ExpireTick - GameLoop.GameLoopTime, Is.EqualTo(60_000));
            Assert.That(first.GetSavedEffect(), Is.Null);
            for (int i = 0; i < 20; i++) { Time(GameLoop.GameLoopTime + 5000); Campfire(player); }
            var current = player.effectListComponent.GetSpellEffects(eEffect.Campfire).Single(e => e.IsActive);
            Assert.That(current.ExpireTick - GameLoop.GameLoopTime, Is.EqualTo(60_000));
            Assert.That(player.BaseBuffBonusCategory[eProperty.PowerRegenerationAmount], Is.EqualTo(5));
            Assert.That(player.BaseBuffBonusCategory[eProperty.HealthRegenerationAmount], Is.EqualTo(5));
            Time(current.ExpireTick - 1);
            TickActualEffects(player);
            Assert.That(current.IsActive, Is.True);
            Time(current.ExpireTick + 1);
            TickActualEffects(player);
            Assert.That(current.IsEnded, Is.True);
            Assert.That(player.BaseBuffBonusCategory[eProperty.PowerRegenerationAmount], Is.Zero);
            Assert.That(player.BaseBuffBonusCategory[eProperty.HealthRegenerationAmount], Is.Zero);
        }

        [TestCase(1, 4)] [TestCase(4, 1)] [TestCase(4, 4)]
        public void CampfireOverlapKeepsOnlyStrongestAndOneRegenContribution(int first, int second)
        {
            GamePlayer player = Player();
            Campfire(player, first);
            Campfire(player, second);
            var active = player.effectListComponent.GetSpellEffects(eEffect.Campfire).Where(e => e.IsActive).ToArray();
            Assert.That(active, Has.Length.EqualTo(1));
            Assert.That(((BeezCampfires.CampfireEffect)active[0]).Tier, Is.EqualTo(Math.Max(first, second)));
            Assert.That(player.BaseBuffBonusCategory[eProperty.PowerRegenerationAmount], Is.EqualTo(5));
            Time(active[0].ExpireTick + 1); TickActualEffects(player);
            Campfire(player, 1);
            Assert.That(player.BaseBuffBonusCategory[eProperty.PowerRegenerationAmount], Is.EqualTo(5));
        }

        [Test]
        public void CampfireUsesNativePowerTimerAndStacksOnceWithBuffStoneAndRoots()
        {
            GamePlayer player = MeasurementAnimist(true);
            player.LastAttackedByEnemyTickPvE = GameLoop.GameLoopTime;
            Apply(player);
            long due = PowerTimer(player).NextTick;
            Campfire(player);
            Assert.That(player.BaseBuffBonusCategory[eProperty.PowerRegenerationAmount], Is.EqualTo(10));
            Assert.That(player.GetModified(eProperty.PowerRegenerationAmount), Is.EqualTo(45));
            Assert.That(PowerTimer(player).NextTick, Is.EqualTo(due));
            int before = player.Mana;
            Time(due); PowerTimer(player).Tick();
            Assert.That(player.Mana - before, Is.EqualTo(45));
            Campfire(player);
            Assert.That(player.GetModified(eProperty.PowerRegenerationAmount), Is.EqualTo(45));
        }

        [Test]
        public void CampfireHealthAidUsesTheNativeCalculatorAndLeavesEnduranceAlone()
        {
            GamePlayer player = Player();
            double modifier = Properties.HEALTH_REGEN_AMOUNT_MODIFIER;
            try
            {
                Properties.HEALTH_REGEN_AMOUNT_MODIFIER = 1;
                Assert.That(player.GetModified(eProperty.HealthRegenerationAmount), Is.EqualTo(30));
                int endurance = player.GetModified(eProperty.EnduranceRegenerationAmount);
                Campfire(player);
                Assert.That(player.GetModified(eProperty.HealthRegenerationAmount), Is.EqualTo(40));
                Assert.That(player.GetModified(eProperty.EnduranceRegenerationAmount), Is.EqualTo(endurance));
                var timer = (ECSGameTimer)typeof(GameLiving).GetField("m_healthRegenerationTimer", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(player);
                Time(timer.NextTick);
                int health = player.Health;
                timer.Tick();
                Assert.That(player.Health - health, Is.EqualTo(40));
            }
            finally { Properties.HEALTH_REGEN_AMOUNT_MODIFIER = modifier; }
        }

        [Test]
        public void CampfireBuffSurvivesFriendlyZoningButDeathCleanupRemovesItsAids()
        {
            GamePlayer player = Player();
            var effect = Campfire(player);
            long expires = effect.ExpireTick;
            player.CurrentRegion = new Region(new RegionData { Id = 100, Name = "Other region", Description = "test", Mobs = [] });
            Time(GameLoop.GameLoopTime + 5000);
            TickActualEffects(player);
            Assert.That(effect.IsActive, Is.True);
            Assert.That(effect.ExpireTick, Is.EqualTo(expires));
            player.effectListComponent.CancelAll(); player.effectListComponent.BeginTick();
            Assert.That(effect.IsEnded, Is.True);
            Assert.That(player.BaseBuffBonusCategory[eProperty.HealthRegenerationAmount], Is.Zero);
            Assert.That(player.BaseBuffBonusCategory[eProperty.PowerRegenerationAmount], Is.Zero);
        }

        [Test]
        public void CampfireHasIndependentPlayerAndPetExpiryAndRejectsHostileOwnership()
        {
            GamePlayer owner = Player();
            GameNPC pet = new() { CurrentRegion = new Region(new RegionData { Id = 1, Name = "Campfire pet", Description = "test", Mobs = [] }) };
            try
            {
                pet.SetOwnBrain(new ControlledMobBrain(owner));
                pet.ObjectState = GameObject.eObjectState.Active;
                pet.Level = 40; pet.Constitution = 60;
                pet.Health = pet.MaxHealth;
                var ownerBuff = Campfire(owner);
                var petBuff = Campfire(pet);
                Time(GameLoop.GameLoopTime + 30_000);
                petBuff = Campfire(pet);
                Assert.That(petBuff.ExpireTick - ownerBuff.ExpireTick, Is.EqualTo(30_000));
                Time(ownerBuff.ExpireTick + 1); TickActualEffects(owner);
                Assert.That(ownerBuff.IsEnded, Is.True);
                Assert.That(petBuff.IsActive, Is.True);
                double damage = 100;
                BeezCampfires.EnhanceMelee(new AttackData { Attacker = pet, AttackType = AttackData.eAttackType.MeleeOneHand }, ref damage);
                Assert.That(damage, Is.EqualTo(130));
                owner.Realm = eRealm.Midgard;
                damage = 100;
                BeezCampfires.EnhanceMelee(new AttackData { Attacker = pet, AttackType = AttackData.eAttackType.MeleeOneHand }, ref damage);
                Assert.That(damage, Is.EqualTo(100), "Cross-realm ownership invalidates damage immediately.");
                petBuff.OnEffectPulse(); pet.effectListComponent.BeginTick();
                Assert.That(pet.BaseBuffBonusCategory[eProperty.PowerRegenerationAmount], Is.Zero);
            }
            finally
            {
                foreach (ECSGameEffect effect in pet.effectListComponent.GetEffects()) effect.End();
                pet.effectListComponent.BeginTick();
                pet.Brain?.Stop();
                pet.StopHealthRegeneration(); pet.StopPowerRegeneration(); pet.StopEnduranceRegeneration();
                ServiceObjectStore.Remove(pet.effectListComponent); ServiceObjectStore.Remove(pet.castingComponent);
            }
        }

        [TestCase(false)] [TestCase(true)]
        public void CampfireIncludesCompanionAndAutonomousBotPetTrees(bool autonomous)
        {
            var bot = (CampfireBot)RuntimeHelpers.GetUninitializedObject(typeof(CampfireBot));
            Field(typeof(GameNPC), bot, "m_brains", new System.Collections.ArrayList());
            bot.Realm = eRealm.Albion; bot.ObjectState = GameObject.eObjectState.Active;
            Field(typeof(GameBot), bot, "<IsAutonomousWorldBot>k__BackingField", autonomous);
            Field(typeof(GameBot), bot, "<IsTemporaryGroupHelper>k__BackingField", !autonomous);
            var pet = new GameNPC();
            try
            {
                pet.SetOwnBrain(new ControlledMobBrain(bot));
                pet.Level = 40; pet.Constitution = 60; pet.ObjectState = GameObject.eObjectState.Active; pet.Health = pet.MaxHealth;
                Assert.That(BeezCampfires.Friendly(eRealm.Albion, bot), Is.True);
                Assert.That(BeezCampfires.Root(pet), Is.SameAs(bot));
                Campfire(pet);
                Assert.That(pet.BaseBuffBonusCategory[eProperty.PowerRegenerationAmount], Is.EqualTo(5));
                Assert.That(BeezCampfires.Friendly(eRealm.Midgard, pet), Is.False);
            }
            finally
            {
                foreach (ECSGameEffect effect in pet.effectListComponent.GetEffects()) effect.End();
                pet.effectListComponent.BeginTick(); pet.Brain?.Stop();
                pet.StopHealthRegeneration(); pet.StopPowerRegeneration(); pet.StopEnduranceRegeneration();
                ServiceObjectStore.Remove(pet.effectListComponent); ServiceObjectStore.Remove(pet.castingComponent);
            }
        }

        [TestCase("Cabalist")] [TestCase("Spiritmaster")] [TestCase("Sorcerer")]
        [TestCase("Bonedancer")] [TestCase("Animist")] [TestCase("Sluaghbinder")]
        public void CampfireAcceptsRealPetBodyAndNestedOwnership(string kind)
        {
            GamePlayer owner = Player();
            GameNPC pet = kind switch
            {
                "Bonedancer" => new BdSubPet(null), "Animist" => new TurretPet(null),
                "Sluaghbinder" => new SluaghbinderPet(null), "Sorcerer" => new GameNPC(),
                _ => new GameSummonedPet(null)
            };
            GameNPC commander = new();
            try
            {
                commander.SetOwnBrain(new ControlledMobBrain(owner));
                pet.SetOwnBrain(new ControlledMobBrain(kind == "Bonedancer" ? commander : owner));
                pet.ObjectState = GameObject.eObjectState.Active;
                pet.Level = 40; pet.Constitution = 60;
                pet.Health = pet.MaxHealth;
                Assert.That(BeezCampfires.Root(pet), Is.SameAs(owner));
                Assert.That(BeezCampfires.Friendly(owner.Realm, pet), Is.True);
                Campfire(pet, 2);
                Assert.That(pet.BaseBuffBonusCategory[eProperty.HealthRegenerationAmount], Is.EqualTo(5));
                Assert.That(BeezCampfires.Friendly(eRealm.Hibernia, pet), Is.False);
            }
            finally
            {
                foreach (ECSGameEffect effect in pet.effectListComponent.GetEffects()) effect.End();
                pet.effectListComponent.BeginTick();
                pet.Brain?.Stop(); commander.Brain?.Stop();
                pet.StopHealthRegeneration(); pet.StopPowerRegeneration(); pet.StopEnduranceRegeneration();
                ServiceObjectStore.Remove(pet.effectListComponent); ServiceObjectStore.Remove(pet.castingComponent);
                ServiceObjectStore.Remove(commander.effectListComponent); ServiceObjectStore.Remove(commander.castingComponent);
            }
        }

        [TestCase(true)] [TestCase(false)]
        public void CampfireRealWorldPlacementAssignsCooldownOnlyAfterSuccessAndCleansUp(bool completeSucceeds)
        {
            GamePlayer player = Player();
            Region region = new(new RegionData { Id = 1, Name = "Campfire world", Description = "test", Mobs = [] });
            Zone zone = new(region, 1, "test", 0, 0, 65536, 65536, 1, false, 0, false, 0, 0, 0, 0, 1);
            ((List<Zone>)typeof(Region).GetField("m_zones", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(region)).Add(zone);
            player.CurrentRegion = region; player.X = 1000; player.Y = 1000;
            var item = GameInventoryItem.Create(BeezCampfires.Template());
            item.Count = 1;
            Assert.That(player.Inventory.AddItem(eInventorySlot.FirstBackpack, item), Is.True);
            var fire = new BeezCampfires.Fire(player, 3);
            int calls = 0;
            try
            {
                bool placed = BeezCampfires.Deploy(fire, () =>
                {
                    calls++;
                    Assert.That(fire.ObjectState, Is.EqualTo(GameObject.eObjectState.Active));
                    if (!completeSucceeds) return false;
                    item.CanUseAgainIn = BeezCampfires.CooldownSeconds;
                    return true;
                });
                Assert.That(calls, Is.EqualTo(1));
                Assert.That(placed, Is.EqualTo(completeSucceeds));
                Assert.That(item.Count, Is.EqualTo(1));
                Assert.That(item.CanUseAgainIn, completeSucceeds ? Is.InRange(599, 600) : Is.Zero);
                Assert.That(fire.Model, Is.EqualTo(3460));
                if (placed)
                {
                    Time(fire.Expires - 5000);
                    Campfire(player, 3);
                    var buff = player.effectListComponent.GetSpellEffects(eEffect.Campfire).Single(e => e.IsActive);
                    Time(fire.Expires);
                    Assert.That(fire.Tick(), Is.Zero);
                    Assert.That(fire.ObjectState, Is.EqualTo(GameObject.eObjectState.Deleted));
                    Assert.That(buff.IsActive, Is.True, "Deleting a fire must not remove its recipients' timed buffs.");
                }
            }
            finally { fire.Delete(); zone.Delete(); }
        }

        [Test]
        public void CampfireFailedWorldPlacementNeverStartsCooldown()
        {
            GamePlayer player = Player();
            var fire = new BeezCampfires.Fire(player, 1);
            int calls = 0;
            Assert.That(BeezCampfires.Deploy(fire, () => { calls++; return true; }), Is.False);
            Assert.That(calls, Is.Zero);
            Assert.That(fire.ObjectState, Is.EqualTo(GameObject.eObjectState.Deleted));
        }

        [TestCase(1, 1)] [TestCase(14, 1)] [TestCase(15, 2)] [TestCase(24, 2)]
        [TestCase(25, 3)] [TestCase(39, 3)] [TestCase(40, 4)] [TestCase(50, 4)]
        public void CampfireRealItemUseAndWorldPulsesTrackOwnerAndPetPositionsIndependently(int level, int tier)
        {
            GamePlayer player = Player(level);
            Region region = new(new RegionData { Id = 1, Name = "Campfire pulse", Description = "test", Mobs = [] });
            Zone zone = new(region, 1, "test", 0, 0, 65536, 65536, 1, false, 0, false, 0, 0, 0, 0, 1);
            ((List<Zone>)typeof(Region).GetField("m_zones", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(region)).Add(zone);
            player.CurrentRegion = region; player.X = 1000; player.Y = 1000;
            GameNPC pet = new() { CurrentRegion = region, X = 1000, Y = 1000 };
            pet.movementComponent.ForceUpdatePosition();
            pet.SetOwnBrain(new ControlledMobBrain(player));
            pet.ObjectState = GameObject.eObjectState.Active; pet.Level = 40; pet.Constitution = 60; pet.Health = pet.MaxHealth;
            // Register actual spatial membership without invoking player login or starting a server.
            typeof(Region).GetMethod("AddObject", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(region, [player]);
            typeof(Region).GetMethod("AddObject", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(region, [pet]);
            typeof(Zone).GetMethod("AddObject", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic).Invoke(zone, [player]);
            typeof(Zone).GetMethod("AddObject", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic).Invoke(zone, [pet]);
            CampfireSpatialTick(player); CampfireSpatialTick(pet);
            var item = GameInventoryItem.Create(BeezCampfires.Template()); item.Count = 1;
            Assert.That(player.Inventory.AddItem(eInventorySlot.FirstBackpack, item), Is.True);
            BeezCampfires.Fire fire = null;
            try
            {
                Assert.That(item.Use(player), Is.True);
                Assert.That(item.Count, Is.EqualTo(1));
                Assert.That(item.CanUseAgainIn, Is.InRange(599, 600));
                foreach (var deployed in ((System.Collections.IDictionary)typeof(BeezCampfires).GetField("Fires", BindingFlags.Static | BindingFlags.NonPublic).GetValue(null)).Values)
                    CampfireSpatialTick((GameObject)deployed);
                fire = player.GetItemsInRadius(350).OfType<BeezCampfires.Fire>().Single();
                Assert.That(fire.Tier, Is.EqualTo(tier));
                var timer = (ECSGameTimer)typeof(BeezCampfires.Fire).GetField("_timer", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(fire);
                Assert.That(timer.IsAlive, Is.True);
                Assert.That(item.Use(player), Is.True);
                Assert.That(item.Count, Is.EqualTo(1), "A duplicate use cannot consume the reusable item.");
                Assert.That(fire.GetPlayersInRadius(350), Does.Contain(player));
                Assert.That(fire.GetNPCsInRadius(350), Does.Contain(pet));
                Assert.That(fire.Tick(), Is.EqualTo(5000));
                player.effectListComponent.BeginTick(); pet.effectListComponent.BeginTick();
                var playerBuff = player.effectListComponent.GetSpellEffects(eEffect.Campfire).Single(e => e.IsActive);
                var petBuff = pet.effectListComponent.GetSpellEffects(eEffect.Campfire).Single(e => e.IsActive);
                Assert.That(playerBuff.ExpireTick, Is.EqualTo(petBuff.ExpireTick));
                player.X = 2000; player.SubZoneObject.CheckForRelocation(); CampfireSpatialTick(player);
                Time(GameLoop.GameLoopTime + 5000);
                fire.Tick(); player.effectListComponent.BeginTick(); pet.effectListComponent.BeginTick();
                petBuff = pet.effectListComponent.GetSpellEffects(eEffect.Campfire).Single(e => e.IsActive);
                Assert.That(petBuff.ExpireTick, Is.EqualTo(playerBuff.ExpireTick + 5000));
                player.X = 1000; pet.X = 2000; pet.movementComponent.ForceUpdatePosition();
                player.SubZoneObject.CheckForRelocation(); pet.SubZoneObject.CheckForRelocation();
                CampfireSpatialTick(player); CampfireSpatialTick(pet);
                Time(GameLoop.GameLoopTime + 5000);
                fire.Tick(); player.effectListComponent.BeginTick(); pet.effectListComponent.BeginTick();
                playerBuff = player.effectListComponent.GetSpellEffects(eEffect.Campfire).Single(e => e.IsActive);
                Assert.That(playerBuff.ExpireTick, Is.EqualTo(petBuff.ExpireTick + 5000));
                BeezCampfires.Stop(null, null, EventArgs.Empty);
                Assert.That(timer.IsAlive, Is.False);
                Assert.That(fire.ObjectState, Is.EqualTo(GameObject.eObjectState.Deleted));
                Assert.That(playerBuff.IsActive, Is.True);
                Assert.That(petBuff.IsActive, Is.True);
            }
            finally
            {
                BeezCampfires.Stop(null, null, EventArgs.Empty);
                fire?.Delete();
                foreach (ECSGameEffect effect in pet.effectListComponent.GetEffects()) effect.End();
                pet.effectListComponent.BeginTick();
                pet.Brain?.Stop(); pet.StopHealthRegeneration(); pet.StopPowerRegeneration(); pet.StopEnduranceRegeneration();
                ServiceObjectStore.Remove(pet.effectListComponent); ServiceObjectStore.Remove(pet.castingComponent);
                typeof(Region).GetMethod("RemoveObject", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(region, [player]);
                typeof(Region).GetMethod("RemoveObject", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(region, [pet]);
                player.SubZoneObject.InitiateSubZoneTransition(null, null); pet.SubZoneObject.InitiateSubZoneTransition(null, null);
                CampfireSpatialTick(player); CampfireSpatialTick(pet);
                zone.Delete();
            }
        }
    }
}
