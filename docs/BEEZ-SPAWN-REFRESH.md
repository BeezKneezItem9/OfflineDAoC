# `/spawn refresh`

Type `/spawn refresh`, or open `/spawn` and click **Refresh**, to synchronize
eligible living companions in your current group to your character's level.
The menu remains accessible when all seven companion slots are occupied;
adding another class still uses the existing full-group rejection.

The command changes the existing bots in place. It does not disband the group,
change slots, replace bots, generate equipment, change roles/build plans, or
spawn new companions. It supports your own temporary `/spawn` helpers and
same-realm autonomous world bots recruited into a player-led group. Other
players, their owned temporary helpers, ordinary NPCs, and unrelated bots are
excluded. A persistent owner-bound `/bot` companion is a separate bot type and
is not included by this command.

Changed bots are rebuilt using `GameBot`'s existing player stat formulas,
class specialization loading, point spending, skill/spell resolution and
combat spell/style sorting. Specializations are rebuilt from the same build
plan, including when lowering levels. Previous class-derived abilities and
cached spells/styles are removed before learning the appropriate ranks;
realm abilities and existing nonclass configuration are retained. Spell
sorting also clears previous healing/crowd-control selections when no spells
remain at the new level. Combat calculations read the new level, stats,
specializations and spell ranks.

The same equipment instances and bonuses remain; items are neither upgraded
nor rerolled. A refresh to level 50 suppresses the existing deferred automatic
helper gear reroll. Retained high-level equipment is subject to the normal
equipment rules after lowering the companion's level.

Health, power and endurance are restored to their recalculated maximums for
changed bots. Already-correct companions are untouched, including their
current resources. Group member/status and group window packets are sent;
the native group window packet includes each member's level. Nearby observers
also receive refreshed NPC information for the same object ID through the
existing visibility/target-safe packet path, because movement updates do not
carry the NPC level. This does not remove or replace the server-side bot.

The entire group is checked before any changes. Combat, attacking, casting,
bot aggro/pending skill requests, fighting controlled pets, or companion stable
travel reject the command with an explanatory message. The player must be
alive. Dead or inactive companions are skipped without revival or replacement.
Missing companions and empty groups produce a normal informational response.

Changed bots' existing summons are released through the same lifecycle used
by the existing level-50 helper upgrade, including pending charms and field
turrets. This avoids leaving independently leveled pets at an inappropriate
old rank. The normal AI can then summon the newly learned rank. The companion
itself and its configuration remain intact.

For recruited persistent autonomous bots, XP is aligned to the start of the
new level and the trained-level marker is updated. This prevents old XP from
immediately undoing a downward refresh on the next kill. The existing dirty
state/save mechanism retains the new progression; realm points, inventory,
identity and lifetime build plan are preserved. Temporary helpers remain
unsaved as before. No database migration, client patch or world-data update is
required.

Examples:

- Seven mismatched companions: `Refreshed 7 companions to level 35.`
- Six mismatches and one already level 35: `Refreshed 6 companions to level 35.`
- Everyone already matches: `No changes needed; all companions are already level 35.`
- Dead/unavailable members are identified separately in the response.

## Verification

Automated tests exercise real bot initialization and refresh in both directions,
temporary and recruited autonomous types, mixed/full seven-slot groups,
identity/group-slot/equipment/build preservation, recalculated pools and stats,
learned spell ranks and abilities, actual spell damage calculations, removal of
stale spell/style selections, combat/travel rejection, dead/unavailable/foreign
members, empty groups, group packet calls, and the actual command/menu whisper
paths. Test world catalogs and packet/database adapters are isolated in memory.

Verified before commit/push:

- GameServer Release build: **0 errors**, 584 warnings.
- Focused companion/command/combat tests: **302 passed**, no failures.
- Full committed-scope regression suite: **2,940 passed**, no failures; 61
  existing ignored cases. This is 19 additional passing cases over `9cbc279`.
- Full available workspace suite: **2,981 passed**, no failures; the same 61
  ignored cases. Its extra 41 earlier turret diagnostics remain outside this commit.

No server, client, playable installation, or played SQLite database is started
or modified. Automated packet-call/menu routing tests do not claim a rendered
Windows client has been tested.

After a separately approved release/deployment, check `/spawn` with a full
group, click Refresh after leveling up, inspect the seven levels and pools,
and test one caster and one melee companion against an ordinary enemy. Check
new pet summoning, the combat rejection message, and a dead companion remaining
dead. A controlled lower-level test should also confirm obsolete spell ranks
are no longer cast.
