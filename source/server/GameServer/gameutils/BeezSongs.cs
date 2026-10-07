using System;
using System.Collections.Generic;
using System.Linq;
using DOL.GS.Spells;
using DOL.AI.Brain;

namespace DOL.GS
{
    public static class BeezSongs
    {
        public static string[] Lines(eCharacterClass characterClass) => characterClass switch
        {
            eCharacterClass.Paladin => ["Chants"],
            eCharacterClass.Minstrel => ["Instruments"],
            eCharacterClass.Skald => ["Battlesongs"],
            eCharacterClass.Bard => ["Bard Music Spec", "Bard Nurture Spec", "Regrowth Bard Spec"],
            eCharacterClass.Warden => ["Nurture Warden Spec"],
            _ => []
        };

        public static eCharacterClass Class(GameLiving living) => living switch
        {
            GamePlayer player => (eCharacterClass)player.CharacterClass.ID,
            GameBot bot when bot.CharacterClass != null => (eCharacterClass)bot.CharacterClass.ID,
            _ => eCharacterClass.Unknown
        };

        public static bool IsEligible(eCharacterClass characterClass, Spell spell, string line) =>
            Lines(characterClass).Contains(line) && spell != null && spell.IsPulsing && !spell.IsFocus &&
            spell.IsHelpful && spell.Target == eSpellTarget.GROUP && spell.SpellType is
                eSpellType.SpeedEnhancement or eSpellType.HealthRegenBuff or eSpellType.PowerRegenBuff or
                eSpellType.EnduranceRegenBuff or eSpellType.DamageAdd or eSpellType.SpecArmorFactorBuff or
                eSpellType.CombatHeal or eSpellType.AblativeArmor or eSpellType.Bladeturn or
                eSpellType.BodyResistBuff or eSpellType.SpiritResistBuff or eSpellType.EnergyResistBuff or
                eSpellType.HeatResistBuff or eSpellType.ColdResistBuff or eSpellType.MatterResistBuff or
                eSpellType.BodySpiritEnergyBuff or eSpellType.HeatColdMatterBuff;

        public static bool IsEligible(GameLiving living, Spell spell, SpellLine line = null)
        {
            eCharacterClass characterClass = Class(living);
            if (line != null && IsEligible(characterClass, spell, line.KeyName))
                return true;
            return Lines(characterClass).Any(key => IsEligible(characterClass, spell, key) &&
                SkillBase.GetSpellList(key).Any(native => native.ID == spell.ID));
        }

        public static bool IsEligible(ISpellHandler handler) =>
            handler != null && IsEligible(handler.Caster, handler.Spell, handler.SpellLine);

        public static int PulseCost(GameLiving caster, Spell spell) => IsEligible(caster, spell) ? 0 : spell.PulsePower;

        public static bool IsRegistered(GameLiving caster, ECSPulseEffect source) =>
            IsEligible(source.SpellHandler) ? caster.BeezPulseSources.ContainsKey(source) :
                caster.ActivePulseSpells.ContainsKey(source.SpellHandler.Spell.SpellType);

        public static bool Maintain(GameBot bot)
        {
            long now = GameLoop.GameLoopTime;
            if (!bot.IsAlive || bot.IsCasting || bot.IsCrowdControlled || bot.IsSilenced || bot.IsOnStableMasterRoute ||
                bot.castingComponent.HasPendingSkillRequests ||
                now < bot.TempProperties.GetProperty<long>("beez.songs.next"))
                return false;
            bot.TempProperties.SetProperty("beez.songs.next", now + 1000);
            IEnumerable<Spell> spells = (bot.MiscSpells ?? []).Concat(bot.InstantMiscSpells ?? [])
                .Where(spell => spell != null && spell.Level <= bot.Level && IsEligible(bot, spell))
                .GroupBy(spell => spell.SpellType)
                .Select(group => group.OrderByDescending(spell => spell.Level).ThenByDescending(spell => spell.Value).First())
                .OrderByDescending(spell => spell.SpellType == eSpellType.SpeedEnhancement && !bot.InCombat);
            foreach (Spell spell in spells)
            {
                if (bot.effectListComponent.GetPulseEffects().Any(source => !source.IsEnding && !source.IsEnded &&
                    source.SpellHandler.Spell.ID == spell.ID))
                    continue;
                if (bot.GetSkillDisabledDuration(spell) > 0 || bot.Mana < bot.PowerCost(spell))
                    continue;
                if (spell.NeedInstrument && !BotBrain.TryEquipRealInstrument(bot, spell.InstrumentRequirement))
                    continue;
                string key = Lines(Class(bot)).First(line => SkillBase.GetSpellList(line).Any(native => native.ID == spell.ID));
                GameObject oldTarget = bot.TargetObject;
                try
                {
                    bot.TargetObject = bot;
                    return bot.CastSpell(spell, SkillBase.GetSpellLine(key, false), null, false);
                }
                finally { bot.TargetObject = oldTarget; }
            }
            return false;
        }
    }
}
