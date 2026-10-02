using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;

namespace DOL.GS;

/// <summary>
/// Classic-frontier warbands assemble inside their own safe border keep before
/// entering the frontier. These are fixed realm contracts, not random PvE town
/// choices. The coordinator still projects and validates the point against the
/// installed navmesh before using it.
/// </summary>
public static class AutonomousRvrStaging
{
    public readonly record struct BorderKeep(ushort RegionId, Vector3 Position, string Name);

    public static bool TryGetBorderKeep(eRealm realm, out BorderKeep keep)
    {
        keep = realm switch
        {
            eRealm.Albion => new(1, new(585085, 477504, 2600), "Castle Sauvage"),
            eRealm.Midgard => new(100, new(766235, 669173, 5736), "Svasud Faste"),
            eRealm.Hibernia => new(200, new(333229, 419539, 5336), "Druim Ligen"),
            _ => default,
        };
        return keep.RegionId != 0;
    }

    /// <summary>
    /// Imported area centers can sit inside keep geometry rather than on a
    /// walkable courtyard polygon. Probe a deterministic set wholly inside the
    /// 3,500-unit safe-area radius; the coordinator still requires a connected
    /// floor and valid formation slots before accepting one.
    /// </summary>
    public static IEnumerable<Vector3> CandidateAnchors(BorderKeep keep, long formationKey = 0)
    {
        int offset = (int)(unchecked((ulong)formationKey) % 12);
        for (int ring = 0; ring < 4; ring++)
        for (int step = 0; step < 12; step++)
        {
            int radius = 600 * (1 + (ring + (int)(unchecked((ulong)formationKey) / 12 % 4)) % 4);
            double angle = Math.PI * 2d * ((step + offset) % 12) / 12d;
            yield return keep.Position + new Vector3(
                (float)(Math.Cos(angle) * radius),
                (float)(Math.Sin(angle) * radius), 0);
        }
        yield return keep.Position;
    }

    /// <summary>
    /// RvR leader candidates, closest to their realm's border keep first. A
    /// randomly drawn leader was often a roamer deep in an enemy frontier and
    /// missed the 20-minute staging window (244 of 2,099 warbands in one run).
    /// Realms take turns so one realm's nearby bots never crowd out another's
    /// formation; equal estimates keep the incoming (shuffled) order.
    /// </summary>
    public static List<T> ClosestToStagingFirst<T>(IEnumerable<T> candidates, Func<T, eRealm> realm,
        Func<T, double> minutesToStaging)
    {
        List<T>[] queues = candidates
            .Select((candidate, index) => (candidate, index, minutes: minutesToStaging(candidate)))
            .GroupBy(entry => realm(entry.candidate))
            .OrderBy(group => group.Key)
            .Select(group => group.OrderBy(entry => entry.minutes).ThenBy(entry => entry.index)
                .Select(entry => entry.candidate).ToList())
            .ToArray();
        var ordered = new List<T>();
        for (int rank = 0; queues.Any(queue => rank < queue.Count); rank++)
            foreach (List<T> queue in queues)
                if (rank < queue.Count)
                    ordered.Add(queue[rank]);
        return ordered;
    }

    /// <summary>Every formed warband member may acquire a local RvR target;
    /// PvE parties retain their single tank-or-leader puller.</summary>
    public static bool UsesIndependentCombatActors(eAutonomousObjectiveKind objectiveKind) =>
        objectiveKind == eAutonomousObjectiveKind.RvR;

    public static int RollWarbandSize(int maximumSize, double roll)
    {
        int maximum = Math.Clamp(maximumSize, 1, 8);
        double bounded = Math.Clamp(roll, 0d, Math.BitDecrement(1d));
        return 1 + (int)(bounded * maximum);
    }

    /// <summary>
    /// Spreads a warband deterministically across the closest visible enemies.
    /// Limiting the window to party size keeps the force converged instead of
    /// sending one member after a distant target.
    /// </summary>
    public static int TargetIndex(long actorKey, int candidateCount, int warbandSize)
    {
        if (candidateCount <= 1)
            return 0;
        int window = Math.Min(candidateCount, Math.Max(2, warbandSize));
        ulong positive = unchecked((ulong)actorKey);
        return (int)(positive % (uint)window);
    }
}
