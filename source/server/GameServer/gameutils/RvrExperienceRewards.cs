using System;
using System.Collections.Generic;
using System.Linq;
using DOL.GS.ServerProperties;

namespace DOL.GS
{
    /// <summary>Character XP for realm opponents. RP/BP remain on their existing paths.</summary>
    public static class RvrExperienceRewards
    {
        private const string LastDeathKey = "beez.rvr.xp.last.death";
        private static readonly object HistoryLock = new();
        private static readonly Dictionary<(string Recipient, string Victim), Queue<long>> History = new();
        private static long _nextHistoryCleanupTick;

        public static long Calculate(byte recipientLevel, byte victimLevel, int participants, double contribution)
        {
            if (recipientLevel >= GamePlayer.MAX_LEVEL || recipientLevel < 1 || victimLevel < 1 || victimLevel > GamePlayer.MAX_LEVEL || participants < 1 ||
                !double.IsFinite(contribution) || contribution <= 0 || ConLevels.GetConLevel(recipientLevel, victimLevel) < -2)
                return 0;
            // Preserve the existing real-player victim value: four same-level NPC kills.
            long victimXp = GameServer.ServerRules.GetExperienceForLiving(victimLevel) * 4;
            long cap = (long)(GameServer.ServerRules.GetExperienceForLiving(recipientLevel) * 4.0 * Math.Max(0, Properties.XP_PVP_CAP_PERCENT) / 100.0);
            double reward = Math.Min(victimXp / participants, cap) * Math.Min(1, contribution);
            return (long)Math.Min(long.MaxValue, Math.Max(0, reward));
        }

        public static bool TryRecordReward(string recipient, string victim, long now)
        {
            if (string.IsNullOrEmpty(recipient) || string.IsNullOrEmpty(victim)) return false;
            long window = Math.Max(1, Properties.RVR_XP_REPEAT_WINDOW_SECONDS) * 1000L;
            lock (HistoryLock)
            {
                // Thousands of autonomous opponents must not copy/scan the complete
                // ledger on every member's reward. Global expiry runs once per minute;
                // the requested pair is always expired before checking its quota.
                if (now >= _nextHistoryCleanupTick)
                {
                    foreach (var pair in History.ToArray())
                    {
                        while (pair.Value.Count > 0 && now - pair.Value.Peek() >= window) pair.Value.Dequeue();
                        if (pair.Value.Count == 0) History.Remove(pair.Key);
                    }
                    _nextHistoryCleanupTick = now + 60_000;
                }
                var key = (recipient, victim);
                if (!History.TryGetValue(key, out Queue<long> kills)) History[key] = kills = new();
                while (kills.Count > 0 && now - kills.Peek() >= window) kills.Dequeue();
                if (kills.Count >= Math.Max(1, Properties.RVR_XP_REPEAT_MAX_KILLS)) return false;
                kills.Enqueue(now);
                return true;
            }
        }

        private static string Identity(GameLiving living) => living switch
        {
            GamePlayer player when !string.IsNullOrEmpty(player.ObjectId) => "player:" + player.ObjectId,
            GameBot bot when bot.DatabaseID > 0 => "bot:" + bot.DatabaseID,
            _ => null
        };

        public static void Award(GameLiving victim)
        {
            if (victim is not GamePlayer && victim is not GameNPC ||
                victim is GameNPC npcVictim && !AutonomousBotRealmPointRewards.IsEligibleVictim(npcVictim) ||
                victim.Realm == eRealm.None || victim is GamePlayer { ReleaseType: eReleaseType.Duel }) return;
            long now = GameLoop.GameLoopTime;
            long last;
            KeyValuePair<GameLiving, double>[] raw;
            lock (victim.XpGainersLock)
            {
                last = victim.TempProperties.GetProperty<long>(LastDeathKey, -1);
                victim.TempProperties.SetProperty(LastDeathKey, now); // Includes invalid/PvE deaths, like RP worthiness.
                raw = victim.XPGainers.ToArray();
            }
            if (last >= 0 && now - last < Math.Max(1, Properties.RP_WORTH_SECONDS) * 1000L) return;
            if (victim is GamePlayer real && real.DeathTime + Properties.RP_WORTH_SECONDS > real.PlayedTime) return;
            if (victim is GameBot && victim.TempProperties.GetProperty<long>(AutonomousBotRealmPointRewards.LastRealmPointDeathTickProperty, -1) is long previous &&
                previous >= 0 && now - previous < Math.Max(1, Properties.RP_WORTH_SECONDS) * 1000L) return;

            double totalDamage = raw.Sum(pair => double.IsFinite(pair.Value) ? Math.Max(0, pair.Value) : 0);
            if (totalDamage <= 0) return;
            Dictionary<GameLiving, double> eligible = new();
            foreach (var pair in raw)
            {
                if (!double.IsFinite(pair.Value)) continue;
                GameLiving recipient = AutonomousBotRealmPointRewards.ResolveRootRewardOwner(pair.Key);
                if (recipient == null || recipient.Realm == eRealm.None || recipient.Realm == victim.Realm ||
                    recipient.ObjectState != GameObject.eObjectState.Active || !recipient.IsAlive ||
                    recipient is GamePlayer { GainXP: false } ||
                    !recipient.IsWithinRadius(victim, WorldMgr.MAX_EXPFORKILL_DISTANCE) ||
                    recipient is not GamePlayer && recipient is not GameBot { IsAutonomousWorldBot: true, IsTemporaryGroupHelper: false }) continue;
                if (recipient is GamePlayer player && victim is GamePlayer target &&
                    player.Client?.Account?.ObjectId is string account && account == target.Client?.Account?.ObjectId) continue;
                eligible[recipient] = eligible.GetValueOrDefault(recipient) + Math.Max(0, pair.Value);
            }
            foreach (var pair in eligible)
            {
                var members = pair.Key.Group == null ? new[] { pair } : eligible.Where(other => other.Key.Group == pair.Key.Group).ToArray();
                long xp = Calculate(pair.Key.Level, victim.Level, members.Length, members.Sum(other => other.Value) / totalDamage);
                if (xp <= 0 || !TryRecordReward(Identity(pair.Key), Identity(victim), now)) continue;
                // Apply normal progression and recipient caps, without location/item multipliers on PvP XP.
                if (pair.Key is GamePlayer player)
                {
                    xp += DOL.GS.ServerRules.AbstractServerRules.CalculateOutpostExperienceBonus(player, xp);
                    lock (player.AwardLock) player.GainExperience(eXPSource.Player, xp);
                }
                else pair.Key.GainExperience(eXPSource.Player, xp);
            }
        }
    }
}
