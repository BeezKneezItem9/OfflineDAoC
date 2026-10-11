# Beez Windows recovery and permanent updater

These tools run with **Windows PowerShell 5.1 on Windows 10/11**. They never start,
stop or deploy to a remote installation. Close the server, launcher and client
before using them. No permanent execution-policy change is needed.

## Immediate Sluaghbinder recovery

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Enable-Sluaghbinder.ps1 -InstallRoot 'C:\Games\Offline DAOC BEEZ Edition\playable-v0.34'
```

The standalone script uses the Windows-native `winsqlite3.dll` SQLite API through
an embedded C# P/Invoke wrapper. It does not load System.Data.SQLite, need Python,
download any world/client, or require another program installed. Its C# uses
syntax supported by Windows PowerShell's .NET Framework compiler.

Before writing it verifies:

- server/launcher/client processes are closed (including `dotnet CoreServer.dll`);
- the active `runtime/data/opendaoc.sqlite3.db` exists and passes quick_check;
- ClassID 63 has exactly nine ClassXSpecialization records;
- the original Muirenn trainer row and trainer class type exist;
- exactly one `enable_sluaghbinder` property exists;
- the client's `runtime/client-opendaoc/app/game.dll` matches original 0.35b
  SHA-256 `e1d471bb19108610ab9c8ca77dd41af40afe716685b03f4cdeda88c05678463b`;
- no custom ServerProperty trigger can mutate other data during the update.

A single `BEGIN IMMEDIATE` transaction encloses data checks, the one-row UPDATE,
post-update value/row-count verification and COMMIT. Errors roll back; an already
True value rolls back without a write. `-CheckOnly` checks prerequisites without
changing the setting. The script reports READY, ENABLED, ALREADY ENABLED or the
blocked prerequisite. A missing/mismatched client or stripped plain-edition world
is rejected rather than repaired by replacing saved data.

The launcher reads this property to label the edition. Open it normally after
success: it should show 0.35b. The server reads the setting on normal startup.
In-game class creation, promotion, spells/pets and bot availability still need
acceptance testing; automated SQL tests do not claim that live validation.

Author references: [edition guidance](../../docs/DEVELOPMENT.md#editions-and-the-custom-class),
[original release](https://github.com/shadowofze/OfflineDAoC/releases/tag/v0.35b).

## Permanent command

Keep `Update-Beez.cmd`, `Update-Beez.ps1` and `Enable-Sluaghbinder.ps1` together in
`%LOCALAPPDATA%\BeezUpdater\tools`. Obtain the scripts from a reviewed Git commit,
checking the supplied SHA-256 hashes before executing them.

From PowerShell, one reusable command installs the newest compatible published
Beez Windows x64 test release, including the launcher:

```powershell
& "$env:LOCALAPPDATA\BeezUpdater\tools\Update-Beez.cmd" -InstallRoot 'C:\Games\Offline DAOC BEEZ Edition\playable-v0.34'
```

Class enablement is a **separate explicit choice**:

```powershell
& "$env:LOCALAPPDATA\BeezUpdater\tools\Update-Beez.cmd" -InstallRoot 'C:\Games\Offline DAOC BEEZ Edition\playable-v0.34' -EnableSluaghbinder
```

For a preview, run Update-Beez.ps1 without `-Apply`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\BeezUpdater\tools\Update-Beez.ps1" -InstallRoot 'C:\Games\Offline DAOC BEEZ Edition\playable-v0.34' -IncludeLauncher
```

The PS1 excludes launcher replacements unless `-IncludeLauncher` is supplied.
The CMD supplies both `-Apply` and `-IncludeLauncher`. `-CacheRoot` optionally sets
an external cache/backup directory. Cache/backup paths inside the playable install
and symbolic links/junctions in protected paths are rejected.

## Update behavior

1. Enumerate GitHub Releases (including prereleases); skip drafts/non-Beez tags.
   Choose the newest published `beez-test-<commit>` with the matching Windows x64
   ZIP and `.zip.sha256` asset. An API/network error stops the update.
2. Download over HTTPS from this repository's release asset paths. Check the ZIP
   checksum and its filename before extraction.
3. Reject traversal, symlink and duplicate/case-colliding archive entries. Verify
   every package file against SHA256SUMS, including deployment/rollback scripts;
   reject missing hashes, extra files or unexpected archive sizes.
4. Verify BUILD-INFO repository, branch, commit/tag, Release configuration,
   self-contained Windows x64 metadata and replacement count.
5. Validate every REPLACEMENTS.csv source/target, payload size and hash. Only
   supported binary/deps/runtimeconfig files under the existing server/launcher
   layout are accepted. Database, client, configuration and world destinations
   cannot be substituted into the manifest. Preview has no playable writes.
6. If all selected installed hashes already match, report ALREADY INSTALLED.
   Otherwise invoke the package's established Deploy-TestBuild.ps1 with an
   external binary backup, then verify every selected installed hash.
7. On a deployment failure, invoke the same package's Rollback-TestBuild.ps1.
   If rollback cannot safely restore a file, report the failure/backup location
   and instruct keeping the server closed. Never force through that check.
8. Ordinary updates **never open a database or change a class setting**. The
   explicit enablement option runs the standalone preflight before deployment,
   then the same transactional helper after success (or on an already-installed
   build). A post-update enablement failure is reported separately.

Verified downloads, the package and INSTALLED.json remain in the external cache;
backups/ROLLBACK.json remain under its backups directory. Installed-version
recognition uses actual selected binary hashes rather than trusting a stale stamp.
No new database migrations or changes to gameplay binaries are introduced.

Compatibility currently means the existing Beez binary-update package contract
used by d39eb0a, d583ee3 and 992b959. Unsupported metadata or a newer corrupt
matching package stops with an error; it does not silently deploy an older package.
GitHub checksum assets plus HTTPS provide integrity against accidental corruption;
this workflow trusts the repository's release publisher.

## Verification

Cloud tests use real PowerShell 7 with the native SQLite ABI and the independently
verified public 0.35b client, without any played database or server startup. The
suite covers data preservation, idempotence, preview/apply, launcher inclusion,
explicit enablement, process checks, locks, missing/duplicate class prerequisites,
custom triggers, hashes, metadata, traversal, protected targets and rollback.

```sh
BEEZ_TEST_CLIENT=/path/to/verified/game.dll \
BEEZ_TEST_POWERSHELL=/path/to/powershell \
python -m unittest discover -s tools/beez/tests -v
```

On Linux only, expose native libsqlite3.so.0 as `winsqlite3.dll` on LD_LIBRARY_PATH
for this ABI test. This is not a claim that Linux exercises Windows' DLL loader.
The Windows CI workflow uses **Windows PowerShell 5.1 and real winsqlite3.dll**.
It substitutes only the hash of an identified tiny client stand-in; ZIP, package,
payload and database behavior remain real. No game release is published by CI.
Fixture deployment/rollback scripts are the unchanged scripts from published
beez-test-992b959, retained to test reuse of the established mechanisms.
