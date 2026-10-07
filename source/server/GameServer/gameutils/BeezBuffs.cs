using System;
using System.Collections.Generic;
using System.Linq;
using DOL.GS.PacketHandler;
using DOL.GS.Spells;

namespace DOL.GS
{
    public static class BeezBuffs
    {
        public readonly record struct Entry(string Line, int Id);
        public sealed record Application(GamePlayer Owner, long Generation)
        {
            public bool IsValid => Owner.IsAlive && Owner.ObjectState == GameObject.eObjectState.Active &&
                Owner.TempProperties.GetProperty<long>(GenerationKey) == Generation;
        }
        private const string GenerationKey = "beez.buff.session.generation";
        private static readonly Entry[] Albion =
        [
            new("Enhancement",1457), new("Enhancement",1486), new("Enhancement",1476), new("Enhancement",1467),
            new("Guardian Angel",1517), new("Guardian Angel",1526), new("Guardian Angel",1538), new("Guardian Angel",1506),
            new("Guardian Angel",1549), new("Guardian Angel",1543), new("Guardian Angel",1546),
            new("Friar Enhancement Spec",1733), new("Friar Enhancement Spec",1736), new("Friar Enhancement Spec",1739),
            new("Path of Air",407), new("Path of Earth",18), new("Domination",980), new("Guardian Angel",1534)
        ];
        private static readonly Entry[] Midgard =
        [
            new("Augmentation",3168), new("Augmentation",3187), new("Augmentation",3176), new("Augmentation",3157),
            new("Shaman Augmentation Spec",3268), new("Shaman Augmentation Spec",3278), new("Shaman Augmentation Spec",3284),
            new("Healer Augmentation Spec",3216), new("Healer Augmentation Spec",3228), new("Healer Augmentation Spec",3231),
            new("Healer Augmentation Spec",3234), new("Shaman Augmentation Spec",3287), new("Shaman Augmentation Spec",3290),
            new("Shaman Augmentation Spec",3293), new("Pacification Spec",3365),
            new("Shaman Augmentation Spec",3298), new("Runes of Darkness",2557)
        ];
        private static readonly Entry[] Hibernia =
        [
            new("Nurture",5007), new("Nurture",5036), new("Nurture",5026), new("Nurture",5020),
            new("Druid Nurture Spec",5067), new("Druid Nurture Spec",5076), new("Druid Nurture Spec",5080),
            new("Druid Nurture Spec",5056), new("Nurture Warden Spec",5143), new("Nurture Warden Spec",5146),
            new("Nurture Warden Spec",5149), new("Druid Nurture Spec",5083), new("Druid Nurture Spec",5086),
            new("Druid Nurture Spec",5089), new("Enchantment Mastery",4758), new("Holism",4439)
        ];

        public static IReadOnlyList<Entry> Manifest(eRealm realm) => Array.AsReadOnly(realm switch
        {
            eRealm.Albion => Albion, eRealm.Midgard => Midgard, eRealm.Hibernia => Hibernia, _ => Array.Empty<Entry>()
        });

        public static bool IsSupported(Spell spell) => spell != null && spell.Level <= 50 && spell.IsHelpful &&
            !spell.IsPulsing && !spell.IsFocus && !spell.HasSubSpell && spell.Target is eSpellTarget.REALM or eSpellTarget.GROUP &&
            spell.SpellType is eSpellType.StrengthBuff or eSpellType.ConstitutionBuff or eSpellType.DexterityBuff or
                eSpellType.BaseArmorFactorBuff or eSpellType.SpecArmorFactorBuff or eSpellType.StrengthConstitutionBuff or
                eSpellType.DexterityQuicknessBuff or eSpellType.AcuityBuff or eSpellType.CombatSpeedBuff or
                eSpellType.BodyResistBuff or eSpellType.SpiritResistBuff or eSpellType.EnergyResistBuff or
                eSpellType.HeatResistBuff or eSpellType.ColdResistBuff or eSpellType.MatterResistBuff or
                eSpellType.DamageAdd or eSpellType.PowerRegenBuff or eSpellType.EnduranceRegenBuff or eSpellType.HealthRegenBuff;

        // Normal donor spec bonus attainable by an equipped specialist; no recipient ToA bonuses.
        public static double Effectiveness(Spell spell) => spell.SpellType is
            eSpellType.StrengthBuff or eSpellType.ConstitutionBuff or eSpellType.DexterityBuff or
            eSpellType.BaseArmorFactorBuff or eSpellType.SpecArmorFactorBuff or eSpellType.StrengthConstitutionBuff or
            eSpellType.DexterityQuicknessBuff or eSpellType.AcuityBuff or eSpellType.DamageAdd ? 1.25 : 1.0;

        public static void Apply(GamePlayer player, GameInventoryItem item)
        {
            lock (player)
            {
                if (item.OwnerID != player.ObjectId || !player.IsAlive ||
                    player.ObjectState != GameObject.eObjectState.Active || player.IsCrowdControlled || player.IsCasting)
                    return;
                var application = new Application(player, player.TempProperties.GetProperty<long>(GenerationKey));
                // Fail the package before applying anything if a required entry is missing or excluded.
                var handlers = new List<SpellHandler>();
                foreach (Entry entry in Manifest(player.Realm))
                {
                    Spell source = SkillBase.GetSpellList(entry.Line)?.FirstOrDefault(spell => spell.ID == entry.Id);
                    SpellLine line = SkillBase.GetSpellLine(entry.Line, false);
                    if (!IsSupported(source) || line == null ||
                        ScriptMgr.CreateSpellHandler(player, (Spell)source.Clone(), line) is not SpellHandler handler)
                    {
                        player.Out.SendMessage($"Buff Stone cannot resolve verified spell {entry.Id} in {entry.Line}.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                        return;
                    }
                    handler.BeezApplication = application;
                    handlers.Add(handler);
                }
                foreach (SpellHandler handler in handlers)
                    handler.ApplyEffectOnTarget(player); // Deliberately bypass group target expansion, not target restrictions.
                player.Out.SendMessage("Beez's Buff Stone applies your realm's buffs. Stronger existing effects are preserved.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
            }
        }

        public static void Clear(GamePlayer player)
        {
            player.TempProperties.SetProperty(GenerationKey, player.TempProperties.GetProperty<long>(GenerationKey) + 1);
            foreach (ECSGameSpellEffect effect in player.effectListComponent.GetSpellEffects())
                if (effect.IsBeezBuff)
                    effect.End();
        }
    }
}
