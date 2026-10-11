# Beez Windows recovery and permanent updater

These tools run with **Windows PowerShell 5.1 on Windows 10/11**. They never start,
stop or deploy to a remote installation. Close the server, launcher and client
before using them. No permanent execution-policy change is needed.

## Immediate Sluaghbinder repair

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Repair-Sluaghbinder.ps1 -InstallRoot 'C:\Games\Offline DAOC BEEZ Edition\playable-v0.34'
```

Keep Repair-Sluaghbinder.ps1, BeezNativeSqlite.cs and Sluaghbinder-Reference.json
in the same directory. Install-BeezTools.ps1 downloads and verifies the complete
maintenance tool set from an exact reviewed Git revision, then runs this repair.
It needs no Python, SQLite editor, downloaded world, managed SQLite assembly or
external command-line utility. SQLite uses Windows 10/11's built-in winsqlite3.dll.

The repair checks closed server/launcher/client processes, ordinary paths without
junctions, database integrity, a single saved class setting, known complete DLL
hashes, and the required catalog, pet, weapon, armor and effect file hashes. It
only inserts missing authoritative class rows. Existing different/duplicate class
records, unsupported clients and missing/modified required art are rejected and
preserved for review. Shared career/ability dependencies must already exist.
No existing character, account, inventory or progression row is imported or edited.

The reference includes the nine class bindings, trainer and bound wisp, class
specializations, spell lines/bindings/spells, pets/equipment, abilities, styles,
start locations and class quest/reward templates from the author's public 0.35b
world. The source database SHA-256 is
`0fff1a26913430a9c8f258484a1e2bae69102354c5e287d7d505d200dd3fdfe6`.
The plain edition's builder removes only the nine bindings and two mobs; a normal
plain-edition repair therefore inserts **11 rows**, then changes the saved setting.
Auto-generated integer row IDs are allocated locally; unrelated IDs are preserved.
Custom triggers are refused. Missing tables/schema differences also fail safely.

### Verified client provenance and patch order

| Input | SHA-256 | Result |
|---|---|---|
| Author v0.32 native-raid base, matching the reported installation | `67dcf68a37b95a93946a943b99d5e19b4a03e08cd6469275e25c7b909de21e99` | Class-only author DLL `691a457c…` |
| Author plain 0.35 | `f55ed6b068e22ce8e1106871c2fad6ee10c18390bbb8b5dc772219ad8c8b83bb` | Original 0.35b DLL `e1d471bb…` |
| Original 0.35b | `e1d471bb19108610ab9c8ca77dd41af40afe716685b03f4cdeda88c05678463b` | Unchanged |

The base provenance is confirmed by tools/build-client-raid.py and exact hash
reproduction from the published plain DLL by reversing the four documented
unrelated patches in a diagnostic copy. **Those unrelated patches are never added,
removed or modified by recovery.**

There is an extra prerequisite beyond the two scripts mentioned in the edition
documentation: both base and plain DLLs lack the embedded Sluaghbinder resource.
The label script refuses them directly. The initial class registration has no
separate source patch script in the current repository. Its five precise changes
(two string slots and three class resource pointers) are taken from the verified
published author client `game.sluaghbinder-label-patched-20260919-081435.dll`, SHA
`691a457c0eb564c7ca6964e39015bd5df35c2a7965729d1572add2211c37ac78`.
This is an explicitly documented binary-reference prerequisite, not a claim that
an additional upstream source script exists.

Recovery applies that registration first, followed by exact translations of
[the author's class-label script](../../source/server/tools/patch_sluaghbinder_client_label.py)
and [race-link script](../../source/server/tools/patch_sluaghbinder_client_races.py),
in that order. Only these class bytes and the PE checksum change. Every stage
requires the exact input hash/signatures and independently verified output hash.
Known intermediate stages are accepted for idempotent partial recovery; unknown
or out-of-order patch combinations are refused. The base DLL retains its older
unrelated feature set; it is not silently upgraded to the full 0.35 client.

### Transactions, backups and limitations

`-CheckOnly` performs all checks and stages missing rows within a transaction,
then rolls back; it writes no installation files. Repair creates a targeted
`runtime/deployment-backups/sluaghbinder-<timestamp>-<unique>/` containing the
original DLL and REPAIR.json with the prior setting and exact inserted-row
predicates. It patches only game.dll, verifies the resulting hash and commits
class data/True in one BEGIN IMMEDIATE SQLite transaction. Ordinary exceptions
roll back SQLite and restore the original DLL. An unexpected rollback failure
reports its backup and requires keeping all processes closed.

Explicit targeted rollback, while the processes remain closed:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Repair-Sluaghbinder.ps1 -InstallRoot 'C:\Games\Offline DAOC BEEZ Edition\playable-v0.34' -Rollback '<reported backup directory>'
```

Rollback refuses changed DLLs, settings or inserted records. It deletes only the
rows created by that repair and restores the prior setting/DLL; it never swaps
the entire SQLite database. Power loss across filesystem/SQLite operations is not
an atomic transaction; retain the reported backup and review an interrupted repair
before launching. Ordinary handled-failure rollback is covered by tests.

Catalog/art hashes are deliberately conservative. If an older installation or
unrelated catalog modification fails a guard, the exact path/record is reported.
The minimum next step is an asset/record-specific compatibility review against
the author source, rather than overwriting gamedata, a skin archive or a world.
The reported DLL hash alone cannot establish those installed assets/data.
In-game creation, Celt/Firbolg selection, promotion, spells, pets and companions
remain player acceptance tests; no live Windows installation was accessed.

Enable-Sluaghbinder.ps1 remains a legacy setting-only helper, with its original
strict full-0.35b prerequisite. It is not a repair for stripped edition data.

Author references: [edition guidance](../../docs/DEVELOPMENT.md#editions-and-the-custom-class),
[edition database builder](../../source/tools/build_release_035.py),
[original release](https://github.com/shadowofze/OfflineDAoC/releases/tag/v0.35b).

## Permanent command

Keep the verified maintenance tool set together in
`%LOCALAPPDATA%\BeezUpdater\tools`. Obtain the scripts from a reviewed Git commit,
checking the supplied SHA-256 hashes before executing them.

From PowerShell, one reusable command installs the newest compatible published
Beez Windows x64 test release, including the launcher:

```powershell
& "$env:LOCALAPPDATA\BeezUpdater\tools\Update-Beez.cmd" -InstallRoot 'C:\Games\Offline DAOC BEEZ Edition\playable-v0.34'
```

Class repair is a **separate explicit choice**:

```powershell
& "$env:LOCALAPPDATA\BeezUpdater\tools\Update-Beez.cmd" -InstallRoot 'C:\Games\Offline DAOC BEEZ Edition\playable-v0.34' -RepairSluaghbinder
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
   explicit repair option runs the standalone preflight before deployment,
   then the same transactional repair helper after success (or on an already-installed
   build). A post-update class-repair failure is reported separately.

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
Its identified complete-client stand-ins substitute only hash identification
(including the repair's byte-array hash); their patch methods explicitly fail if
called. ZIP, package, payload and SQLite operations remain real. The full binary
patch test is explicitly skipped in CI; all eight verified real author DLL stages
are exercised separately in the cloud. Actual author-schema validation additionally
restored exactly 11 stripped rows and compared all 122 unrelated SQLite tables
and unrelated rows in the affected tables against the original copy. No game release is published by CI.
Fixture deployment/rollback scripts are the unchanged scripts from published
beez-test-992b959, retained to test reuse of the established mechanisms.
