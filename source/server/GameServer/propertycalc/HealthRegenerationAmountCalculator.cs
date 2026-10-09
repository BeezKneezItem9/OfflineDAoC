using System;
using DOL.AI.Brain;

namespace DOL.GS.PropertyCalc
{
    /// <summary>
    /// The health regen rate calculator
    /// 
    /// BuffBonusCategory1 is used for all buffs
    /// BuffBonusCategory2 is used for all debuffs (positive values expected here)
    /// BuffBonusCategory3 unused
    /// BuffBonusCategory4 unused
    /// BuffBonusMultCategory1 unused
    /// </summary>
    [PropertyCalculator(eProperty.HealthRegenerationAmount)]
    public class HealthRegenerationAmountCalculator : PropertyCalculator
    {
        public HealthRegenerationAmountCalculator() { }

        public override int CalcValue(GameLiving living, eProperty property)
        {
            if (living.IsDiseased || living.effectListComponent.ContainsEffectForEffectType(eEffect.Bleed))
                return 0;

            /* PATCH 1.87 COMBAT AND REGENERATION
              - While in combat, health and power regeneration ticks will happen twice as often.
              - Each tick of health and power is now twice as effective.
              - All health and power regeneration aids are now twice as effective.
             */

            // Apply 1.87 to the existing level curve and net aids, before server modifiers.
            // Ordinary NPC evade recovery below deliberately retains its separate rule.
            // The classic level-50 base of 15 becomes 30 before aids.
            double regen = 2.5 + living.Level * 0.25;
            int debuff = living.SpecBuffBonusCategory[property];

            if (debuff < 0)
                debuff = -debuff;

            regen += living.BaseBuffBonusCategory[property] + living.AbilityBonus[property] + living.ItemBonus[property] - debuff;

            regen *= 2;

            if (living is GameNPC npc && living is not GameBot)
            {
                // Halved regeneration amount for NPCs in combat.
                // NPCs (necromancer pets excluded) out of combat and without anything in their aggro list (so that it doesn't trigger when NPCs are being kited) get a huge bonus.
                if (npc.InCombat)
                    regen /= 2.0;
                else if (npc is not NecromancerPet && (npc.Brain is not StandardMobBrain brain || !brain.HasAggro))
                    regen = npc.MaxHealth * 0.125;
            }

            regen *= ServerProperties.Properties.HEALTH_REGEN_AMOUNT_MODIFIER;
            return Math.Max(1, (int) regen);
        }
    }
}
