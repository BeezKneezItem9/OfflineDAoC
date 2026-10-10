# Beez Online — Regeneration Overhaul Windows x64 Test Release

Source: **d583ee32832a108cc030e6bb4d4f776052de6a00**, `beez-online-six-features`.

Windows x64 self-contained Release **update package** for an existing playable
OfflineDAoC/Beez Online 0.35/0.35b installation. It includes the server, optional
launcher, matching .NET 10 runtime dependencies, deployment scripts, exact
replacement manifest and per-file checksums. It reuses your installed world and
client; it is not a fresh-world/client distribution.

## Regeneration improvements

- Removed the below-50% power penalty (DAoC 1.78), including saved configurations
  whose legacy penalty flag is True. The key remains readable; its default is False.
- Standing out-of-combat health/power ticks now match sitting: **3 seconds**.
- Combat health/power intervals halved: **7 seconds standing**, **5 sitting**.
- Native health/power recovery and net regeneration aids doubled exactly once,
  before independent configured rate modifiers and final truncation.
- The Hibernian Buff Stone's stored **+5** power aid now contributes **+10**;
  its spell value, stacking and session lifetime remain unchanged.
- OOC endurance now recovers at the seated rate while standing and moving, on the
  existing one-second clock. Sprint costs, combat aid requirements and Tireless remain.
- Mana Roots retains its level-15 rank, 60-second self-root, casting permissions,
  instant/free activation, no cooldown and visuals. It uses ordinary OOC power
  recovery in combat, with no additional multiplier.
- Fixed the reproduced **19.9-second** post-Roots tick gap: normal standing-combat
  **7-second** scheduling resumes without restarting the regeneration timer.

Level-50, modifier 1, sufficient missing power: steady OOC recovery is **500 power
per minute**, or **700 with the Stone**, regardless of whether power is below half.
Actual 60-second Roots and transition windows depend on the timer phase. Complete
formulas, numerical comparisons and historical interpretations are included in
`notices/BEEZ-REGENERATION-OVERHAUL.md`.

## Installation and persistence

Extract outside your installation and review `DEPLOYMENT.md` and `REPLACEMENTS.csv`.
Only manifest-listed binaries, symbols and runtime dependency JSON are replacements.
No SQLite database, character/account information, configuration, world scripts,
quests, navigation meshes or client files are included for replacement. Keep all
existing installed-world content. There is no regeneration database migration,
required configuration edit or new client patch. Do not replace your save with a
release database. The package does not automatically deploy or launch anything.

## Validation

Release builds and exact-source binary/package verification completed in the cloud.
Full server regression: **2,839 passed, zero failed; 61 installed-world fixtures
NotExecuted**. Mana Roots/regeneration: 71 passed; Beez Online: 43 passed.
Windows apphosts and native dependencies have verified AMD64 PE headers; published
runtime/native dependencies and every archive/manifest hash are checked.
Windows launcher tests and in-game behavior are not claimed verified on Linux.
