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
        /// <summary>Native PvP base after group division, cap, contribution and truncation.</summary>
        public static long CalculateNative(byte recipientLevel, byte victimLevel, int participants, double contribution)
        {
            if (recipientLevel >= GamePlayer.MAX_LEVEL || recipientLevel < 1 || victimLevel < 1 || victimLevel > GamePlayer.MAX_LEVEL || participants < 1 ||
                !double.IsFinite(contribution) || contribution <= 0 || ConLevels.GetConLevel(recipientLevel, victimLevel) < -2)
                return 0;
            // Decimal intermediates prevent overflow even with extreme cap settings.
            decimal victimXp = Math.Max(0, GameServer.ServerRules.GetExperienceForLiving(victimLevel)) * 4m;
            decimal cap = decimal.Truncate(Math.Max(0, GameServer.ServerRules.GetExperienceForLiving(recipientLevel)) * 4m * Math.Max(0, Properties.XP_PVP_CAP_PERCENT) / 100m);
            decimal reward = Math.Min(decimal.Truncate(victimXp / participants), cap) * (decimal)Math.Min(1, contribution);
            return ClampExperience(decimal.Truncate(reward));
        }

        private static long ClampExperience(decimal value) => (long)Math.Clamp(value, 0m, (decimal)long.MaxValue);

        /// <summary>Scale the complete native reward once, bounded by signed XP storage headroom.</summary>
        public static long ScaleReward(long nativeReward, long currentExperience)
        {
            decimal scaled = Math.Max(0, nativeReward) * (decimal)Math.Max(0, Properties.RVR_KILL_XP_MULTIPLIER);
            decimal headroom = (decimal)long.MaxValue - Math.Max(0, currentExperience);
            return ClampExperience(Math.Min(scaled, headroom));
        }

        public static void Award(GameLiving victim, bool? nativeWorthiness = null)
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
            if (nativeWorthiness == false) return;
            if (nativeWorthiness == null && victim is GameBot && victim.TempProperties.GetProperty<long>(AutonomousBotRealmPointRewards.LastRealmPointDeathTickProperty, -1) is long previous &&
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
                long xp = CalculateNative(pair.Key.Level, victim.Level, members.Length, members.Sum(other => other.Value) / totalDamage);
                if (xp <= 0) continue;
                // Apply normal progression and recipient caps, without location/item multipliers on PvP XP.
                if (pair.Key is GamePlayer player)
                {
                    xp = ClampExperience((decimal)xp + DOL.GS.ServerRules.AbstractServerRules.CalculateOutpostExperienceBonus(player, xp));
                    lock (player.AwardLock)
                    {
                        long reward = ScaleReward(xp, player.Experience);
                        if (reward > 0) player.GainExperience(eXPSource.Player, reward);
                    }
                }
                else if (pair.Key is GameBot bot)
                {
                    long reward = ScaleReward(xp, bot.Experience);
                    if (reward > 0) bot.GainExperience(eXPSource.Player, reward);
                }
            }
        }
    }
}
