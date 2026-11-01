using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using DOL.AI.Brain;
using DOL.Database;
using DOL.Events;
using DOL.GS.PacketHandler;
using DOL.GS.Spells;
using P = DOL.GS.ServerProperties.Properties;

namespace DOL.GS
{
    /// <summary>Reusable, stationary support fires. No persistent world spawns or independent recovery clock.</summary>
    public static class BeezCampfires
    {
        public const int BuffMilliseconds = 60_000;
        // Stock ITEM model, identified in CommanderPet's stock-model correction; not an NPC figure ID.
        public const ushort Model = 3460;
        public const int FirstSpellId = 59840;
        public const string ItemId = "beez_campfire";
        public const int CooldownSeconds = 600;
        private static readonly ConcurrentDictionary<string, Fire> Fires = new();
        private static readonly SpellLine Line = new("Beez Campfire", "Beez Campfire", "Beez Campfire", true);
        public static int TierForLevel(int level) => level < 1 ? 0 : level < 15 ? 1 : level < 25 ? 2 : level < 40 ? 3 : 4;
        public static int Bonus(int tier) => tier is >= 1 and <= 4 ? 10 + tier * 5 : 0;

        public static DbItemTemplate Template()
        {
            return new DbItemTemplate
            {
                Id_nb = ItemId, Name = "Beez's Campfire",
                ClassType = typeof(BeezCampfireItem).FullName, PackageID = "BeezCampfire",
                Item_Type = (int)eInventorySlot.FirstBackpack, Object_Type = (int)eObjectType.Magical,
                Model = Model, Level = 1, MaxCount = 1, CanUseEvery = CooldownSeconds, Weight = 5, Quality = 100,
                Condition = 50000, MaxCondition = 50000, Durability = 50000, MaxDurability = 50000,
                IsPickable = true, IsDropable = false, IsTradable = false,
                Description = "Reusable campfire. 10-minute cooldown. Level-scaled melee damage bonus and health/power regeneration. " +
                    "Friendly players and controlled pets receive rolling 60-second buffs. Use while stationary out of combat."
            };
        }

        public static DbItemTemplate EnsureTemplate()
        {
            VerifyRuntimeIds();
            DbItemTemplate existing = GameServer.Database.FindObjectByKey<DbItemTemplate>(ItemId);
            if (existing != null)
            {
                if (existing.PackageID != "BeezCampfire" || existing.ClassType != typeof(BeezCampfireItem).FullName)
                    throw new InvalidOperationException($"Campfire item ID collision: {existing.Id_nb}; existing data was not changed.");
                return existing;
            }
            DbItemTemplate template = Template();
            if (!GameServer.Database.AddObject(template)) throw new InvalidOperationException("Could not register " + template.Id_nb);
            return template;
        }

        [ScriptLoadedEvent]
        public static void Load(DOLEvent e, object sender, EventArgs args)
        {
            // Add-only and restart-safe, including recovery after a partially completed registration.
            EnsureTemplate();
        }

        private static void VerifyRuntimeIds()
        {
            for (int tier = 1; tier <= 4; tier++)
                if (SkillBase.GetSpellByID(FirstSpellId + tier) != null)
                    throw new InvalidOperationException("Campfire runtime spell ID collision: " + (FirstSpellId + tier));
        }

        [GameServerStoppedEvent]
        [ScriptUnloadedEvent]
        public static void Stop(DOLEvent e, object sender, EventArgs args)
        {
            lock (Fires)
            {
                foreach (Fire fire in Fires.Values) fire.Delete();
                Fires.Clear();
            }
        }

        public static GameLiving Root(GameLiving living)
        {
            int depth = 0;
            while (living is GameNPC npc && living is not GameBot)
            {
                if (++depth > 16 || npc.Brain is not IControlledBrain controlled) return null;
                living = controlled.Owner;
            }
            return living is GamePlayer or GameBot ? living : null;
        }

        public static bool Friendly(eRealm realm, GameLiving living) => living != null && living.IsAlive &&
            living.ObjectState == GameObject.eObjectState.Active && realm != eRealm.None &&
            Root(living)?.Realm == realm && living.Realm == realm;

        public static bool PlacementAllowed(GamePlayer player) => player != null && player.IsAlive &&
            player.ObjectState == GameObject.eObjectState.Active && player.CurrentRegion != null &&
            !player.CurrentRegion.IsDisabled && player.CurrentZone != null && !player.InHouse &&
            !player.InCombat && !player.IsMoving && !player.IsCrowdControlled && !player.IsCasting &&
            !player.IsOnHorse && player.Steed == null && player.Realm != eRealm.None;

        public static bool Use(GamePlayer player, DbInventoryItem item)
        {
            if (item?.Id_nb != ItemId) return false;
            try { VerifyRuntimeIds(); }
            catch (InvalidOperationException)
            {
                Tell(player, "Campfire spell IDs conflict with installed world data. No cooldown was started.");
                return true;
            }
            int tier = TierForLevel(player.Level);
            lock (player.Inventory.Lock)
            {
                if (tier == 0 || !PlacementAllowed(player) || item.Count < 1 || item.OwnerID != player.InternalID ||
                    item.SlotPosition < (int)eInventorySlot.FirstBackpack || item.SlotPosition > (int)eInventorySlot.LastBackpack ||
                    !ReferenceEquals(player.Inventory.GetItem((eInventorySlot)item.SlotPosition), item))
                {
                    Tell(player, "You must stand still, out of combat, in a valid location with a campfire in your backpack.");
                    return true;
                }
                if (item.CanUseAgainIn > 0)
                {
                    Tell(player, $"Your campfire is ready again in {item.CanUseAgainIn} seconds.");
                    return true;
                }
                lock (Fires)
                {
                    if (Fires.ContainsKey(player.ObjectId)) { Tell(player, "Your previous campfire is still burning."); return true; }
                    Fire fire = new(player, tier);
                    if (!Deploy(fire, () => { item.CanUseAgainIn = CooldownSeconds; return true; }))
                    {
                        Tell(player, "The campfire could not be placed. No cooldown was started.");
                        return true;
                    }
                    Fires[player.ObjectId] = fire;
                    fire.Start();
                }
                Tell(player, $"You deploy {item.Name}. A 10-minute cooldown begins. Nearby allies receive rolling 60-second buffs.");
            }
            return true;
        }

        // World placement precedes cooldown assignment. A failed completion removes the unused object.
        public static bool Deploy(Fire fire, Func<bool> complete)
        {
            try
            {
                if (!fire.AddToWorld()) { fire.Delete(); return false; }
                if (complete()) return true;
                fire.Delete();
                return false;
            }
            catch
            {
                fire.Delete();
                throw;
            }
        }

        private static void Tell(GamePlayer player, string text) => player.Out.SendMessage(text, eChatType.CT_System, eChatLoc.CL_SystemWindow);

        public static void Apply(GameLiving recipient, int tier, eRealm realm)
        {
            if (!Friendly(realm, recipient) || Bonus(tier) == 0) return;
            // The recipient is the effect caster: no dependency on a dead/deleted campfire or a departed deployer.
            var handler = new CampfireHandler(recipient, new Spell(new DbSpell
            {
                SpellID = FirstSpellId + tier, Name = $"Campfire {tier}: +{Bonus(tier)}% melee",
                Type = "MeleeDamageBuff", Target = "Self", Value = Bonus(tier), Duration = 60,
                Frequency = 10, EffectGroup = FirstSpellId, Icon = 7245
            }, 1), Line);
            ECSGameEffectFactory.Create(new(recipient, BuffMilliseconds, 1, handler), tier, realm,
                static (in i, t, r) => new CampfireEffect(i, t, r));
        }

        public static void EnhanceMelee(AttackData attack, ref double damage)
        {
            if (!attack.IsMeleeAttack) return;
            CampfireEffect effect = attack.Attacker.effectListComponent.GetSpellEffects(eEffect.Campfire)?
                .OfType<CampfireEffect>().FirstOrDefault(e => e.IsActive && e.Valid);
            if (effect == null) return;
            double multiplier = 1 + Bonus(effect.Tier) * 0.01;
            damage *= multiplier;
            attack.StyleDamage = (int)(attack.StyleDamage * multiplier);
            // Deliberately leave BaseDamage and BaseDamageCap snapshots untouched: damage adds/procs are independent.
        }

        private sealed class CampfireHandler(GameLiving caster, Spell spell, SpellLine line) : SpellHandler(caster, spell, line)
        {
            public override bool HasConflictingEffectWith(ISpellHandler other) => other is CampfireHandler;
            public override string ShortDescription => $"Increases melee attack and style damage by {Spell.Value}%, with health and power regeneration aids. Lasts 60 seconds after the last campfire pulse.";
        }

        public sealed class CampfireEffect : ECSGameSpellEffect
        {
            public int Tier { get; }
            private readonly eRealm _realm;
            private readonly int _health = Math.Clamp(P.BEEZ_CAMPFIRE_HEALTH_AID, 0, 100);
            private readonly int _power = Math.Clamp(P.BEEZ_CAMPFIRE_POWER_AID, 0, 100);
            public bool Valid => GameLoop.GameLoopTime < ExpireTick && Friendly(_realm, Owner);
            public CampfireEffect(in ECSGameEffectInitParams args, int tier, eRealm realm) : base(args)
            {
                EffectType = eEffect.Campfire;
                Tier = tier;
                _realm = realm;
            }
            public override void OnStartEffect()
            {
                Owner.BaseBuffBonusCategory[eProperty.HealthRegenerationAmount] += _health;
                Owner.BaseBuffBonusCategory[eProperty.PowerRegenerationAmount] += _power;
                Owner.StartHealthRegeneration();
                Owner.StartPowerRegeneration();
            }
            public override void OnStopEffect()
            {
                Owner.BaseBuffBonusCategory[eProperty.HealthRegenerationAmount] -= _health;
                Owner.BaseBuffBonusCategory[eProperty.PowerRegenerationAmount] -= _power;
            }
            public override void OnEffectPulse() { if (!Valid) End(); }
            // Runtime-only buff definitions cannot be restored from saved world spell rows.
            public override DbPlayerXEffect GetSavedEffect() => null;
        }

        public class Fire : GameStaticItem
        {
            public int Tier { get; }
            public long Expires { get; }
            private readonly string _deployerId;
            private readonly ushort _radius;
            private readonly int _interval;
            private ECSGameTimer _timer;
            public Fire(GamePlayer player, int tier)
            {
                Tier = tier;
                _deployerId = player.ObjectId;
                Name = $"Beez Campfire {tier}";
                Model = BeezCampfires.Model;
                Realm = player.Realm;
                CurrentRegion = player.CurrentRegion;
                X = player.X; Y = player.Y; Z = player.Z; Heading = player.Heading;
                RespawnInterval = 0;
                Expires = GameLoop.GameLoopTime + Math.Clamp(P.BEEZ_CAMPFIRE_LIFETIME_SECONDS, 1, 3600) * 1000L;
                _radius = (ushort)Math.Clamp(P.BEEZ_CAMPFIRE_RADIUS, 1, 2000);
                _interval = Math.Clamp(P.BEEZ_CAMPFIRE_PULSE_SECONDS, 1, 30) * 1000;
            }
            public void Start()
            {
                lock (this)
                {
                    _timer?.Stop();
                    _timer = new ECSGameTimer(this, _ => Tick(), 1);
                }
            }
            public int Tick()
            {
                lock (this)
                {
                    if (ObjectState != eObjectState.Active || CurrentRegion == null || CurrentRegion.IsDisabled || GameLoop.GameLoopTime >= Expires)
                    { Delete(); return 0; }
                    foreach (GameLiving recipient in GetPlayersInRadius(_radius).Cast<GameLiving>().Concat(GetNPCsInRadius(_radius)))
                        Apply(recipient, Tier, Realm);
                    return (int)Math.Min(_interval, Expires - GameLoop.GameLoopTime);
                }
            }
            public override bool RemoveFromWorld(int respawnSeconds)
            {
                lock (this)
                {
                    _timer?.Stop();
                    _timer = null;
                    if (Fires.TryGetValue(_deployerId, out Fire current) && ReferenceEquals(current, this)) Fires.TryRemove(_deployerId, out _);
                    return base.RemoveFromWorld(0);
                }
            }
        }
    }

    public sealed class BeezCampfireItem : GameInventoryItem
    {
        public BeezCampfireItem(DbItemTemplate template) : base(template) { }
        public BeezCampfireItem(DbItemUnique template) : base(template) { }
        public BeezCampfireItem(DbInventoryItem item) : base(item) { }
        public override bool Use(GamePlayer player) => BeezCampfires.Use(player, this);
        public override void Delve(List<string> lines, GamePlayer player)
        {
            base.Delve(lines, player);
            lines.Add(Description);
            lines.Add($"Current tier: {BeezCampfires.TierForLevel(player.Level)}. Melee damage: +{BeezCampfires.Bonus(BeezCampfires.TierForLevel(player.Level))}%. Cooldown: 10 minutes.");
            lines.Add($"Lifetime: {P.BEEZ_CAMPFIRE_LIFETIME_SECONDS}s. Radius: {P.BEEZ_CAMPFIRE_RADIUS}. Pulse: {P.BEEZ_CAMPFIRE_PULSE_SECONDS}s.");
            lines.Add($"Regeneration aids: health +{P.BEEZ_CAMPFIRE_HEALTH_AID}, power +{P.BEEZ_CAMPFIRE_POWER_AID} before native modifiers.");
        }
    }
}
