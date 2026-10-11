using System;
using DOL.GS.ServerProperties;

namespace DOL.GS
{
    /// <summary>Location adjustment for NPC XP only; existing camp/group/cap rules run first.</summary>
    public static class BeezExperiencePolicy
    {
        public const ushort DarknessFallsRegion = 249;

        public static double PlayerRate(eXPSource source, ushort region, bool isRvR)
        {
            if (source == eXPSource.NPC && region == DarknessFallsRegion)
                return Math.Max(Properties.XP_RATE, Properties.RvR_XP_RATE);
            return isRvR ? Properties.RvR_XP_RATE : Properties.XP_RATE;
        }

        public static int ZoneBonus(eXPSource source, ushort region, int existingBonus)
        {
            int bonus = Properties.ENABLE_ZONE_BONUSES ? existingBonus : 0;
            return source == eXPSource.NPC && region == DarknessFallsRegion
                ? Math.Max(bonus, Math.Clamp(Properties.DARKNESS_FALLS_XP_BONUS_PERCENT, 0, 1000)) : bonus;
        }
    }
}
