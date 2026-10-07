using System;
using System.Collections.Generic;

namespace DOL.GS
{
    /// <summary>Shared PvP arithmetic; only the autonomous victim policy depreciates rewards.</summary>
    public static class BeezRealmRewards
    {
        public static int Calculate(int victimValue, int victimRank, int recipientValue, int recipientRank,
            int participants, int groupMembers, double fraction, bool adjustRank)
        {
            if (victimValue <= 0 || recipientValue <= 0 || participants <= 0 || fraction <= 0)
                return 0;
            int reward = (int)(Math.Min(victimValue / participants, recipientValue * 2) * Math.Min(1, fraction));
            if (adjustRank)
                reward = (int)(reward * (1 + 2.0 * (victimRank - recipientRank) / 900));
            if (groupMembers > 1)
                reward += (int)(reward * (groupMembers - 1) * 0.125);
            return Math.Max(0, reward);
        }

        public static int Recover(int normalReward, long elapsedMilliseconds, long intervalMilliseconds)
        {
            if (normalReward <= 0)
                return 0;
            if (intervalMilliseconds <= 0 || elapsedMilliseconds >= intervalMilliseconds)
                return normalReward;
            return Math.Max(1, (int)(normalReward * Math.Clamp((double)elapsedMilliseconds / intervalMilliseconds, 0, 1)));
        }

        // Process-local recovery window. Survives object reconstruction, never changes player saves.
        private static readonly Dictionary<long, long> Deaths = new();
        private static readonly object Sync = new();
        private static long _nextPrune;
        public static long RecordDeath(long botId, long now, long interval)
        {
            lock (Sync)
            {
                if (interval <= 0)
                {
                    Deaths.Remove(botId);
                    return long.MaxValue;
                }
                if (now >= _nextPrune)
                {
                    foreach (long key in new List<long>(Deaths.Keys))
                        if (now - Deaths[key] >= interval)
                            Deaths.Remove(key);
                    _nextPrune = now + 1000;
                }
                long elapsed = Deaths.TryGetValue(botId, out long previous) ? Math.Max(0, now - previous) : long.MaxValue;
                Deaths[botId] = now;
                return elapsed;
            }
        }
    }
}
