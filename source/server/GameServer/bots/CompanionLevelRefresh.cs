using System.Linq;
using DOL.AI.Brain;

namespace DOL.GS
{
    public static class CompanionLevelRefresh
    {
        public static string Refresh(GamePlayer player)
        {
            Group group = player?.Group;
            if (group == null)
                return "You have no grouped companions to refresh.";

            GameLiving[] members = group.GetMembersInTheGroup().ToArray();
            GameBot[] companions = members.OfType<GameBot>().Where(bot =>
                bot.Group == group && bot.Realm == player.Realm &&
                (bot.IsTemporaryGroupHelper && bot.Owner == player ||
                 bot.IsAutonomousWorldBot && bot.IsPlayerLedGroup)).ToArray();
            if (companions.Length == 0)
                return "You have no eligible grouped companions to refresh.";
            if (!player.IsAlive || player.Level < 1 || player.Level > GamePlayer.MAX_LEVEL)
                return "You must be alive and at a valid character level to refresh companions.";

            // Preflight before changing any bot: avoid a partly refreshed party
            // if another member/pet is fighting, casting or travelling.
            if (members.Any(member => member.InCombat || member.IsAttacking || member.IsCasting ||
                    member.ControlledBrain?.Body is { InCombat: true }) ||
                companions.Any(bot => bot.IsOnStableMasterRoute ||
                    bot.Brain is BotBrain { HasAggro: true } ||
                    bot.castingComponent?.HasPendingSkillRequests == true))
                return "Cannot refresh companions during combat, casting or stable travel. Try again when the group is idle.";

            GameBot[] changed = companions.Where(bot => bot.IsAlive &&
                bot.ObjectState == GameObject.eObjectState.Active && bot.Level != player.Level).ToArray();
            int unavailable = companions.Count(bot => !bot.IsAlive || bot.ObjectState != GameObject.eObjectState.Active);
            if (changed.Length == 0)
                return unavailable > 0
                    ? $"No changes needed for living companions; {unavailable} dead or unavailable companions were skipped."
                    : $"No changes needed; all companions are already level {player.Level}.";

            foreach (GameBot bot in changed)
            {
                bot.RefreshCompanionLevel(player.Level);
                // NPC movement updates do not carry level. Reannounce the same
                // object ID through the existing visibility/target-safe packet path.
                if (bot.CurrentRegion != null)
                    ClientService.CreateObjectForPlayers(bot);
                group.UpdateMember(bot, true, true);
            }
            group.UpdateGroupWindow();
            return $"Refreshed {changed.Length} companions to level {player.Level}." +
                (unavailable > 0 ? $" Skipped {unavailable} dead or unavailable companions." : "");
        }
    }
}
