using System.Linq;
using System.Collections.Generic;
using DOL.Database;

namespace DOL.GS
{
    /// <summary>Animist affinity with the soil; not a regeneration property bonus.</summary>
    public static class ManaRoots
    {
        public const string LineKey = "Beez Mana Roots";
        public const int LineId = 32000;
        public const int SpellId = 760015; // Server-only scripted identity; never a client visual ID.
        public const int UnlockLevel = 15;
        public const int DurationMs = 60000;
        public const ushort RootVisual = 5201;
        public const ushort ManaVisual = 4435;
        public const int VisualIntervalMs = 8000;
        public const int VisualLifetimeMs = 4000;
        private static readonly object RegistrationLock = new();

        public static Spell CreateSpell() => new(new DbSpell
        {
            SpellID = SpellId,
            Name = "Mana Roots",
            Description = "Become one with the soil, calming your spirit and drawing upon the earth's reserves. " +
                "For 60 seconds you cannot move, but recover power at your normal out-of-combat rate even during combat. " +
                "You may continue casting. Damage does not free you, and you cannot cancel the roots early.",
            Type = "ManaRoots", Target = "Self", Duration = 60,
            CastTime = 0, Power = 0, RecastDelay = 0, Concentration = 0,
            ClientEffect = RootVisual, Icon = RootVisual,
            Message1 = "You become one with the soil, drawing upon the earth's reserves.",
            Message3 = "Your affinity with the soil fades, and you can move again."
        }, UnlockLevel);

        public static void GrantTo(GamePlayer player)
        {
            if (player.CharacterClass.ID != (int)eCharacterClass.Animist || player.Level < UnlockLevel)
            {
                if (player.GetSpellLine(LineKey) != null)
                    player.RemoveSpellLine(LineKey);
                return;
            }

            // In-memory registration only; never insert spells into the played database.
            // Check the actual registry rather than a once-only flag, so skill reloads work.
            lock (RegistrationLock)
            {
                SkillBase.RegisterSpellLine(new SpellLine(LineKey, "Mana Roots", LineId, "", true));
                if (!SkillBase.GetSpellList(LineKey).Any(s => s.ID == SpellId))
                    SkillBase.AddScriptedSpell(LineKey, CreateSpell());
            }
            player.AddSpellLine(new SpellLine(LineKey, "Mana Roots", LineId, "", true) { Level = player.Level }, false);
        }

        public static void AppendUsableSpells(GamePlayer player, List<(SpellLine, List<Skill>)> spells)
        {
            spells.RemoveAll(entry => entry.Item1.KeyName == LineKey);
            GrantTo(player);
            SpellLine line = player.GetSpellLine(LineKey);
            if (line != null)
                spells.Add((line, SkillBase.GetSpellList(LineKey).Cast<Skill>().ToList()));
        }

        public static ManaRootsECSEffect ActiveEffect(GamePlayer player) =>
            player.effectListComponent.GetEffects().OfType<ManaRootsECSEffect>().FirstOrDefault(e =>
                e.IsActive && !e.IsEnding && e.ExpireTick > GameLoop.GameLoopTime);

        public static bool IsRestoring(GamePlayer player) =>
            player.CharacterClass.ID == (int)eCharacterClass.Animist && ActiveEffect(player) != null;
    }
}
