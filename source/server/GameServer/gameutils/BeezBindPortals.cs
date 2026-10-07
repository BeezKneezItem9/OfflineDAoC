using System;
using System.Collections.Concurrent;
using System.Linq;
using DOL.Database;
using DOL.GS.Keeps;
using DOL.GS.PacketHandler;

namespace DOL.GS
{
    public static class BeezBindPortals
    {
        public readonly record struct Endpoint(ushort Region, int X, int Y, int Z, ushort Heading);
        public static Endpoint Position(GamePlayer player) => new(player.CurrentRegionID, player.X, player.Y, player.Z, player.Heading);
        public static Endpoint BindPoint(GamePlayer player) => new((ushort)player.BindRegion, player.BindXpos, player.BindYpos, player.BindZpos, (ushort)player.BindHeading);
        // Arrival tolerates normal client heading/position updates after loading.
        public static bool HasArrived(GamePlayer player, Endpoint destination) =>
            player.ObjectState == GameObject.eObjectState.Active && player.CurrentRegionID == destination.Region &&
            player.IsWithinRadius(new Point3D(destination.X, destination.Y, destination.Z), 256);
        private static readonly ConcurrentDictionary<GamePlayer, Pair> Pairs = new();
        public const long Lifetime = 10 * 60 * 1000;

        public static bool AllowedLocation(GamePlayer player, Endpoint endpoint)
        {
            Region region = WorldMgr.GetRegion(endpoint.Region);
            Zone zone = region?.GetZone(endpoint.X, endpoint.Y);
            return region != null && zone != null && !region.IsDisabled && !region.IsInstance && !region.IsRvR && region.ID != 497 &&
                !zone.IsRvR && !zone.IsBG && GameServer.ServerRules.IsAllowedToZone(player, region) &&
                !region.GetAreasOfSpot(new Point3D(endpoint.X, endpoint.Y, endpoint.Z)).Any(area => area is KeepArea);
        }

        public static bool AllowedState(GamePlayer player) => player != null && player.IsAlive &&
            player.ObjectState == GameObject.eObjectState.Active && !player.InCombat && !player.IsMoving &&
            !player.IsCrowdControlled && !player.IsCasting && !player.InHouse && !player.IsOnHorse && player.Steed == null &&
            !GameRelic.IsPlayerCarryingRelic(player);

        public static bool TryUse(GamePlayer player, DbInventoryItem item, int useType)
        {
            if (useType != 2 || SkillBase.GetSpellByID(item.SpellID)?.SpellType != eSpellType.GatewayPersonalBind)
                return false;
            if (item.OwnerID != player.ObjectId || item.CanUseAgainIn > 0 || !AllowedState(player) ||
                !AllowedLocation(player, Position(player)) || !AllowedLocation(player, BindPoint(player)) ||
                !GameServer.ServerRules.IsAllowedToMoveToBind(player))
            {
                player.Out.SendMessage("You cannot create a return portal here or in your current state.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return true;
            }
            lock (player)
            {
                Clear(player);
                Pair pair = new(player, Position(player), BindPoint(player));
                if (!player.MoveToBind())
                    return true;
                item.CanUseAgainIn = item.CanUseEvery;
                Pairs[player] = pair;
                pair.Start();
            }
            return true;
        }

        public static void Clear(GamePlayer player)
        {
            lock (player)
            {
                if (Pairs.TryRemove(player, out Pair pair))
                    pair.Dispose();
            }
        }

        private sealed class Pair
        {
            private readonly GamePlayer _owner;
            private readonly Endpoint _expedition;
            private readonly Endpoint _bind;
            private readonly long _created = GameLoop.GameLoopTime;
            private Portal _home;
            private Portal _away;
            private ECSGameTimer _timer;
            private bool _disposed;
            public Pair(GamePlayer owner, Endpoint expedition, Endpoint bind)
            {
                _owner = owner;
                _expedition = expedition;
                _bind = bind;
            }
            public void Start() => _timer = new ECSGameTimer(_owner, Tick, 250);
            private int Tick(ECSGameTimer timer)
            {
                lock (_owner)
                {
                    if (_disposed)
                        return 0;
                    if (_owner.Health <= 0 || _owner.IsBeingHandledByReaperService || BindPoint(_owner) != _bind || GameLoop.GameLoopTime - _created >= Lifetime ||
                        !AllowedLocation(_owner, _bind) || !AllowedLocation(_owner, _expedition))
                    {
                        Clear(_owner);
                        return 0;
                    }
                    if (_home == null)
                    {
                        if (!HasArrived(_owner, _bind))
                        {
                            if (GameLoop.GameLoopTime - _created > 60000)
                            {
                                Clear(_owner);
                                return 0;
                            }
                            return 250;
                        }
                        _home = new Portal(this, _bind, _expedition);
                        _away = new Portal(this, _expedition, _bind);
                        if (!_home.AddToWorld() || !_away.AddToWorld())
                        {
                            Clear(_owner);
                            return 0;
                        }
                        _owner.Out.SendMessage("Your private return portals will remain for ten minutes. Use /use2 on the recall stone to replace them.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                    }
                    return 1000;
                }
            }
            public bool Travel(GamePlayer player, Portal portal, Endpoint destination)
            {
                lock (_owner)
                {
                    if (player != _owner || _disposed || !Pairs.TryGetValue(player, out Pair current) || current != this ||
                        GameLoop.GameLoopTime - _created >= Lifetime || BindPoint(player) != _bind ||
                        !player.IsWithinRadius(portal, 256) || !AllowedState(player) ||
                        !AllowedLocation(player, Position(player)) || !AllowedLocation(player, destination))
                        return false;
                    player.LeaveHouse();
                    return player.MoveTo(destination.Region, destination.X, destination.Y, destination.Z, destination.Heading);
                }
            }
            public void Dispose()
            {
                _disposed = true;
                _timer?.Stop();
                _home?.Delete();
                _away?.Delete();
            }
        }

        private sealed class Portal : GameNPC
        {
            private readonly Pair _pair;
            private readonly Endpoint _destination;
            public Portal(Pair pair, Endpoint position, Endpoint destination)
            {
                _pair = pair;
                _destination = destination;
                Name = "Beez's Private Return Portal";
                Model = 0x783; // Existing FrontiersPortalStone.TeleporterEffect stock model.
                MaxSpeedBase = 0;
                Flags = eFlags.PEACE;
                Realm = eRealm.None;
                Level = 1;
                CurrentRegionID = position.Region;
                X = position.X; Y = position.Y; Z = position.Z; Heading = position.Heading;
            }
            public override bool Interact(GamePlayer player) => _pair.Travel(player, this, _destination);
        }
    }
}
