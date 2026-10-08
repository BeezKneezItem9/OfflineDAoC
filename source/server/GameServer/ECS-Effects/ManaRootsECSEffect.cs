using DOL.Database;
using DOL.GS.Spells;

namespace DOL.GS
{
    public sealed class ManaRootsECSEffect : ECSGameSpellEffect
    {
        private long _nextVisualTick;
        public override bool HasPositiveEffect => false; // Shift-click cannot remove this self-root.

        public ManaRootsECSEffect(in ECSGameEffectInitParams initParams) : base(initParams)
        {
            EffectType = eEffect.ManaRoots;
            Duration = ManaRoots.DurationMs;
            ExpireTick = StartTick + Duration;
            PulseFreq = 1000; // Lifecycle/visual checks only; never regenerates or casts a borrowed spell.
            NextTick = StartTick + PulseFreq;
        }

        public override DbPlayerXEffect GetSavedEffect() => null;
        public override bool ShouldBeAddedToConcentrationList() => false;
        public override bool ShouldBeRemovedFromConcentrationList() => false;

        public override void OnStartEffect()
        {
            Owner.BuffBonusMultCategory1.Set((int)eProperty.MaxSpeed, this, 0);
            Owner.OnMaxSpeedChange();
            RestartPowerTimer();
            ((ManaRootsSpellHandler)SpellHandler).SendVisuals(true);
            _nextVisualTick = GameLoop.GameLoopTime + ManaRoots.VisualIntervalMs;
            OnEffectStartsMsg(true, false, false);
        }

        public void Refresh()
        {
            ExpireTick = GameLoop.GameLoopTime + ManaRoots.DurationMs;
            _nextVisualTick = GameLoop.GameLoopTime + ManaRoots.VisualIntervalMs;
            ((ManaRootsSpellHandler)SpellHandler).SendVisuals(true);
            Owner.effectListComponent.RequestPlayerUpdate(EffectHelper.PlayerUpdate.Icons);
        }

        public override void OnEffectPulse()
        {
            if (!IsActive || IsEnding)
                return;
            if (!Owner.IsAlive || Owner.ObjectState != GameObject.eObjectState.Active ||
                OwnerPlayer.CharacterClass.ID != (int)eCharacterClass.Animist)
            {
                End();
                return;
            }
            long now = GameLoop.GameLoopTime;
            if (now >= _nextVisualTick && ExpireTick - now >= ManaRoots.VisualLifetimeMs)
            {
                ((ManaRootsSpellHandler)SpellHandler).SendVisuals(false);
                _nextVisualTick = now + ManaRoots.VisualIntervalMs; // No catch-up particle bursts.
            }
        }

        public override void OnStopEffect()
        {
            NextTick = 0;
            Owner.BuffBonusMultCategory1.Remove((int)eProperty.MaxSpeed, this);
            Owner.OnMaxSpeedChange();
            RestartPowerTimer();
            OnEffectExpiresMsg(true, false, false);
        }

        private void RestartPowerTimer()
        {
            // Leave an already-normal out-of-combat tick in place. In combat,
            // re-arm at the restored/native interval without awarding any power.
            if (Owner.InCombat)
                Owner.StopPowerRegeneration();
            if (Owner.IsAlive && Owner.ObjectState == GameObject.eObjectState.Active)
                Owner.StartPowerRegeneration();
        }
    }
}
