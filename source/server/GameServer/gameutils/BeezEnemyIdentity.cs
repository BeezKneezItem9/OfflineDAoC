using System;
using System.Linq;
using DOL.GS.PacketHandler;

namespace DOL.GS
{
    public static class BeezEnemyIdentity
    {
        public static bool IsEnemy(GamePlayer viewer, GameObject target) =>
            viewer != null && target is GameBot { IsAutonomousWorldBot: true, IsTemporaryGroupHelper: false } bot &&
            viewer.Realm != eRealm.None && bot.Realm != eRealm.None &&
            !GameServer.ServerRules.IsSameRealm(viewer, bot, true);

        public static string Name(GamePlayer viewer, GameObject target) =>
            IsEnemy(viewer, target) && target is GameBot bot
                ? viewer.RaceToTranslatedName(bot.Race, bot.Gender)
                : target?.GetName(0, false) ?? string.Empty;

        // Only names of the entities participating in this message are rewritten.
        public static string Message(GamePlayer viewer, string message, params GameObject[] targets)
        {
            if (string.IsNullOrEmpty(message))
                return message;
            foreach (GameObject target in targets.Distinct())
                if (IsEnemy(viewer, target) && !string.IsNullOrEmpty(target.Name))
                    message = message.Replace(target.Name, Name(viewer, target), StringComparison.Ordinal);
            return message;
        }

        public static void SystemToArea(GameObject center, string message, eChatType type,
            GameObject[] targets, params GameObject[] excludes)
        {
            if (center == null || string.IsNullOrEmpty(message))
                return;
            foreach (GamePlayer viewer in center.GetPlayersInRadius(WorldMgr.INFO_DISTANCE))
                if (!excludes.Contains(viewer))
                    viewer.MessageFromArea(center, Message(viewer, message, targets), type, eChatLoc.CL_SystemWindow);
        }

        public static void Resolve(GamePlayer viewer, GameNPC npc, ref string name, ref string guild)
        {
            if (!IsEnemy(viewer, npc))
                return;
            name = Name(viewer, npc);
            guild = string.Empty;
        }
    }
}
