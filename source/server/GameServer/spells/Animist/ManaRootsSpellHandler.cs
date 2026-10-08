using DOL.GS.PacketHandler;

namespace DOL.GS.Spells
{
    [SpellHandler(eSpellType.ManaRoots)]
    public class ManaRootsSpellHandler : SpellHandler
    {
        public ManaRootsSpellHandler(GameLiving caster, Spell spell, SpellLine line) : base(caster, spell, line) { }
        public override bool HasPositiveEffect => true; // Self-only; never records an attack/combat event.
        public override bool IsUnPurgeAble => true;
        public override int PowerCost(GameLiving target) => 0;
        protected override int CalculateEffectDuration(GameLiving target) => ManaRoots.DurationMs;
        protected override double CalculateBuffDebuffEffectiveness() => 1;

        public override bool CheckBeginCast(GameLiving selectedTarget, bool quiet)
        {
            if (Caster is not GamePlayer player || player.CharacterClass.ID != (int)eCharacterClass.Animist ||
                player.Level < ManaRoots.UnlockLevel || player.IsOnHorse || player.Steed != null)
            {
                if (!quiet)
                    MessageToCaster("Mana Roots requires an unmounted Animist of level 15 or higher.", eChatType.CT_System);
                return false;
            }
            return base.CheckBeginCast(Caster, quiet);
        }

        public override void ApplyEffectOnTarget(GameLiving target)
        {
            if (target != Caster || Caster is not GamePlayer player ||
                player.CharacterClass.ID != (int)eCharacterClass.Animist || player.Level < ManaRoots.UnlockLevel ||
                player.IsOnHorse || player.Steed != null)
                return;
            base.ApplyEffectOnTarget(Caster);
        }

        public override void OnDurationEffectApply(GameLiving target)
        {
            if (target != Caster || target is not GamePlayer player || !target.IsAlive)
                return;
            ManaRootsECSEffect existing = ManaRoots.ActiveEffect(player);
            if (existing != null)
            {
                existing.Refresh(); // Never drop the movement lock between recasts.
                return;
            }
            CreateECSEffect(new(target, ManaRoots.DurationMs, 1, this));
        }

        public override ECSGameSpellEffect CreateECSEffect(in ECSGameEffectInitParams initParams) =>
            ECSGameEffectFactory.Create(initParams, static (in i) => new ManaRootsECSEffect(i));

        public void SendVisuals(bool activation)
        {
            if (activation)
                SendEffectAnimation(Caster, ManaRoots.RootVisual, 0, false, 1);
            SendEffectAnimation(Caster, ManaRoots.ManaVisual, 0, !activation, 1);
        }
    }
}
