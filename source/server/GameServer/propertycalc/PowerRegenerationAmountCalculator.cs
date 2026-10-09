using System;

namespace DOL.GS.PropertyCalc
{
    /// <summary>
    /// The power regen rate calculator
    /// 
    /// BuffBonusCategory1 is used for all buffs
    /// BuffBonusCategory2 is used for all debuffs (positive values expected here)
    /// BuffBonusCategory3 unused
    /// BuffBonusCategory4 unused
    /// BuffBonusMultCategory1 unused
    /// </summary>
    [PropertyCalculator(eProperty.PowerRegenerationAmount)]
    public class PowerRegenerationAmountCalculator : PropertyCalculator
    {
        public PowerRegenerationAmountCalculator() { }

        public override int CalcValue(GameLiving living, eProperty property)
        {
            /* PATCH 1.87 COMBAT AND REGENERATION
              - While in combat, health and power regeneration ticks will happen twice as often.
              - Each tick of health and power is now twice as effective.
              - All health and power regeneration aids are now twice as effective.
             */

            // 1.78 removes the low-power penalty, including legacy saved True settings.
            // 1.87 doubles the native base and every net aid exactly once, before
            // the independent server modifier and final integer truncation.
            double regen = 2.5 + living.Level * 0.2;
            int debuff = Math.Abs(living.SpecBuffBonusCategory[property]);
            regen += living.BaseBuffBonusCategory[property] + living.AbilityBonus[property] + living.ItemBonus[property] - debuff;
            regen *= 2 * ServerProperties.Properties.MANA_REGEN_AMOUNT_MODIFIER;
            return Math.Max(1, (int)regen);
        }
    }
}
