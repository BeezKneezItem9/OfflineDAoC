using System;
using System.Collections.Generic;
using System.Linq;
using DOL.Database;
using DOL.Events;
using DOL.GS.PacketHandler;

namespace DOL.GS
{
    public static class BeezDeveloperItems
    {
        public const string RingId = "beez_developer_ring";
        public const string StoneId = "beez_buff_stone";

        public static IEnumerable<(eProperty Property, int Value)> RingBonuses()
        {
            foreach (eProperty property in new[] { eProperty.Strength, eProperty.Constitution, eProperty.Dexterity,
                eProperty.Quickness, eProperty.Intelligence, eProperty.Piety, eProperty.Empathy, eProperty.Charisma })
                yield return (property, 250);
            foreach (eProperty property in new[] { eProperty.Resist_Body, eProperty.Resist_Cold, eProperty.Resist_Energy,
                eProperty.Resist_Heat, eProperty.Resist_Matter, eProperty.Resist_Spirit,
                eProperty.Resist_Crush, eProperty.Resist_Slash, eProperty.Resist_Thrust })
                yield return (property, 100);
            yield return (eProperty.MaxHealth, 500);
            yield return (eProperty.MaxMana, 100);
            yield return (eProperty.AllSkills, 100);
        }

        public static void ApplyRingBonuses(GamePlayer player, DbInventoryItem item, int sign)
        {
            if (item?.Id_nb != RingId)
                return;
            foreach (var bonus in RingBonuses())
                player.ItemBonus[bonus.Property] += sign * bonus.Value;
        }

        public static DbItemTemplate Template(string id) => new()
        {
            Id_nb = id, Name = id == RingId ? "Beez's Developer Ring" : "Beez's Buff Stone",
            ClassType = id == RingId ? typeof(BeezDeveloperRing).FullName : typeof(BeezBuffStone).FullName,
            Item_Type = id == RingId ? (int)eInventorySlot.LeftRing : (int)eInventorySlot.FirstBackpack,
            Object_Type = (int)eObjectType.Magical, Model = id == RingId ? 103 : 602,
            Level = 1, Quality = 100, Condition = 50000, MaxCondition = 50000,
            Durability = 50000, MaxDurability = 50000, IsPickable = true,
            IsDropable = false, IsTradable = false, IsIndestructible = false,
            MaxCount = 1, Weight = 1
        };

        public static DbItemTemplate EnsureTemplate(string id)
        {
            DbItemTemplate template = GameServer.Database.FindObjectByKey<DbItemTemplate>(id);
            if (template != null)
                return template;
            template = Template(id);
            GameServer.Database.AddObject(template);
            return template;
        }

        private static bool HasSavedItem(string ownerId, string id) =>
            DOLDB<DbInventoryItem>.SelectObjects(DB.Column("OwnerID").IsEqualTo(ownerId))
                .Any(item => item.Id_nb == id);

        [ScriptLoadedEvent]
        public static void Load(DOLEvent e, object sender, EventArgs args)
        {
            EnsureTemplate(RingId);
            EnsureTemplate(StoneId);

        }

        // Called after normal creation handlers finish, so starter equipment owns its slots first.
        public static void GrantCreated(CharacterEventArgs creation)
        {
            if (creation?.Character == null || creation.GameClient == null || creation.GameClient is BotDummyClient)
                return;
            DbCoreCharacter character = creation.Character;
            var items = DOLDB<DbInventoryItem>.SelectObjects(DB.Column("OwnerID").IsEqualTo(character.ObjectId));
            var occupied = items.Select(item => item.SlotPosition).ToHashSet();
            foreach (string id in new[] { RingId, StoneId })
            {
                if (items.Any(item => item.Id_nb == id))
                    continue;
                int slot = Enumerable.Range((int)eInventorySlot.FirstBackpack,
                    (int)eInventorySlot.LastBackpack - (int)eInventorySlot.FirstBackpack + 1)
                    .FirstOrDefault(slot => !occupied.Contains(slot));
                if (slot == 0)
                    break;
                GameInventoryItem item = GameInventoryItem.Create(EnsureTemplate(id));
                item.OwnerID = character.ObjectId;
                item.SlotPosition = slot;
                item.Realm = character.Realm;
                GameServer.Database.AddObject(item);
                occupied.Add(slot);
            }
        }

        public static void Grant(GamePlayer player)
        {
            lock (player.Inventory.Lock)
            {
                foreach (string id in new[] { RingId, StoneId })
                {
                    if (player.Inventory.AllItems.Any(item => item.Id_nb == id) || HasSavedItem(player.ObjectId, id))
                        continue;
                    if (!player.Inventory.AddItem(eInventorySlot.FirstEmptyBackpack, GameInventoryItem.Create(EnsureTemplate(id))))
                    {
                        player.Out.SendMessage("Make room in your backpack for Beez's items.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                        break;
                    }
                }
            }
        }
    }

    public class BeezDeveloperRing : GameInventoryItem
    {
        public BeezDeveloperRing(DbItemTemplate item) : base(item) { }
        public BeezDeveloperRing(DbItemUnique item) : base(item) { }
        public BeezDeveloperRing(DbInventoryItem item) : base(item) { }
        public override void Delve(List<string> delve, GamePlayer player)
        {
            base.Delve(delve, player);
            delve.Add("Supplies all eight stats, nine resists, hits, flat power and all skills through normal equipment caps.");
            foreach (var bonus in BeezDeveloperItems.RingBonuses())
                delve.Add($"{SkillBase.GetPropertyName(bonus.Property)}: +{bonus.Value}");
        }
    }

    public class BeezBuffStone : GameInventoryItem
    {
        public BeezBuffStone(DbItemTemplate item) : base(item) { }
        public BeezBuffStone(DbItemUnique item) : base(item) { }
        public BeezBuffStone(DbInventoryItem item) : base(item) { }
        public override bool Use(GamePlayer player)
        {
            BeezBuffs.Apply(player, this);
            return true;
        }
    }
}
