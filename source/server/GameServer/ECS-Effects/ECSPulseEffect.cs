using System.Collections.Generic;
using DOL.GS.Effects;

namespace DOL.GS
{
    public class ECSPulseEffect : ECSGameSpellEffect, IConcentrationEffect, IPooledList<ECSPulseEffect>
    {
        /// <summary>
        /// The name of the owner
        /// </summary>
        public override string OwnerName => $"Pulse: {SpellHandler.Spell.Name}";
        public System.Collections.Concurrent.ConcurrentDictionary<GameLiving, ECSGameSpellEffect> ChildEffects { get; } = new();

        public bool RemoveChildIfCurrent(GameLiving owner, ECSGameSpellEffect effect) =>
            ((ICollection<KeyValuePair<GameLiving, ECSGameSpellEffect>>)ChildEffects)
                .Remove(new KeyValuePair<GameLiving, ECSGameSpellEffect>(owner, effect));

        public ECSPulseEffect(in ECSGameEffectInitParams initParams, int pulseFreq)
            : base (initParams)
        {
            PulseFreq = pulseFreq;
            EffectType = eEffect.Pulse;
            StartTick = GameLoop.GameLoopTime;
            NextTick = pulseFreq + GameLoop.GameLoopTime;
        }

        public override void OnStartEffect()
        {
            Spell spell = SpellHandler.Spell;
            if (BeezSongs.IsEligible(SpellHandler))
                Owner.BeezPulseSources.TryAdd(this, 0);
            Owner.ActivePulseSpells.AddOrUpdate(spell.SpellType, spell, (x, y) => spell);
        }

        public override void OnStopEffect()
        {
            var key = SpellHandler.Spell.SpellType;
            if (BeezSongs.IsEligible(SpellHandler))
            {
                Owner.BeezPulseSources.TryRemove(this, out _);
                ((ICollection<KeyValuePair<eSpellType, Spell>>)Owner.ActivePulseSpells)
                    .Remove(new KeyValuePair<eSpellType, Spell>(key, SpellHandler.Spell));
                foreach (ECSPulseEffect remaining in Owner.BeezPulseSources.Keys)
                    if (remaining.SpellHandler.Spell.SpellType == key && !remaining.IsEnded && !remaining.IsEnding)
                        Owner.ActivePulseSpells.TryAdd(key, remaining.SpellHandler.Spell);
            }
            else
                Owner.ActivePulseSpells.TryRemove(key, out _);

            if (SpellHandler.Spell.IsFocus)
            {
                foreach (var pair in ChildEffects)
                {
                    ECSGameSpellEffect effect = pair.Value;
                    if (effect.EffectType is eEffect.FocusShield)
                        effect.End();
                }
            }

            ChildEffects.Clear();
        }
    }
}
