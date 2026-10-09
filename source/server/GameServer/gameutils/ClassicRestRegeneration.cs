namespace DOL.GS
{
    /// <summary>One timing/stance rule for real players and NPC-backed playerbots.
    /// Native property calculators still apply level, buffs, debuffs and server modifiers.</summary>
    public static class ClassicRestRegeneration
    {
        public static int HealthAndPowerInterval(bool sitting, bool inCombat)
        {
            // 1.87: standing OOC matches sitting; halve the classic combat intervals.
            return !inCombat ? 3000 : sitting ? 5000 : 7000;
        }

        public static int BaseEndurancePerTick(bool sitting, bool inCombat, bool moving)
        {
            // One-second endurance clock already exists. Match seated OOC throughput,
            // including movement; combat and sprint costs remain separate.
            return inCombat ? 0 : 4;
        }
    }
}
