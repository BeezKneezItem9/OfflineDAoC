# Beez Online — Windows playable test build

Source and promoted development HEAD: **d39eb0a9a4d56c80630421c99b92472b33fba6fe**.
Both `beez-upstream-integration` and `beez-online-six-features` were verified at this commit and the target was fast-forwarded and pushed without force.

Pushed backup: **beez-online-pre-promotion-20261009T005845Z**, at **fb4a21785ee353e4f8da47189f12ce292d809e8e**. This Git reference protects source history; it is not a backup of installed binaries or saved characters.

## Build and verification

- Release, Windows x64 (`win-x64`), self-contained server and launcher publishes succeeded using SDK 10.0.401.
- Server includes .NET Core and ASP.NET Core **10.0.12**; launcher includes .NET Core and Windows Desktop **10.0.12**. Upstream's public-package script documents 10.0.11; this package uses the official runtime packs selected by the current SDK. Existing `tools/dotnet` is neither changed nor required for these apphosts.
- Fresh Linux regression: **2,786 passed, zero failed, 61 NotExecuted**. The last focused Beez fixture run passed 43 tests. The +1 from 2,785 is the gateway authorization/cleanup test.
- Previous Release GameServer build: zero errors, 584 warnings. Existing package advisories and compiler warnings remain; publish succeeds but does not remove those advisories.
- `CoreServer.exe`, `OfflineDAoC.exe`, both SQLite native DLLs and `Detour.dll` have verified AMD64 PE headers. Server and launcher `.deps.json` and `.runtimeconfig.json` are included, together with their published dependencies.
- The scripts were exercised with the complete payload against a disposable PowerShell 7.5.4 Linux fixture: preview made no changes, deployment matched every hash, persistent sentinels stayed unchanged, and rollback restored old files and removed added files.
- **No Windows executable, real server, launcher or game client was run.** Windows launcher tests require Windows and were not executed here. Installed-world probes and in-game gateway targeting/travel remain outstanding. Cross-compilation and PE checks are not Windows runtime or playable compatibility verification.

## Exact replacements

**REPLACEMENTS.csv is the complete per-file list**, including source path, destination relative to the playable root, SHA-256 and byte size. It has 800 server mappings and 273 optional launcher mappings. SHA256SUMS covers the package files.

| Package source | Installation destination | Purpose |
| --- | --- | --- |
| `payload/server/*` (all manifest-listed files) | `runtime/server/*` and `runtime/server/win-x64/*` | Matching self-contained CoreServer apphost, CoreServer/GameServer/CoreBase/CoreDatabase assemblies and PDBs, runtime configs, managed/native dependencies, culture resources |
| `payload/server/GameServer.dll/.pdb`, `CoreBase.dll/.pdb`, `CoreDatabase.dll/.pdb` | `runtime/server/lib/` | Keep the server's managed assembly copies consistent |
| `payload/server/lib/Detour.dll` | `runtime/server/lib/Detour.dll` and `runtime/server/win-x64/lib/Detour.dll` | Native navigation dependency from verified upstream v0.35b release |
| `payload/launcher/*` (optional, use `-IncludeLauncher`) | `runtime/*` | Updated upstream launcher/UI and matching self-contained Windows Desktop dependencies |

The native Detour SHA-256 is `fb3b51ee4df86b219eda7f6d64ea9eff312cbf1be9bfde10b023aa58b666f787`; ZIP CRC and release package manifest were checked. Native OS dependencies include Windows Universal CRT; use supported Windows x64 (Windows 10/11). Existing navigation mesh compatibility still needs a playable check.

**Do not copy the whole staging directory into an installation.** Only apply the manifest. The publish-time `config/serverconfig.xml` and `CoreServer.dll.config` were deliberately excluded; all existing configuration is preserved. Do not delete other DLLs or runtime files merely because they are absent from this package.

No database, character/account data, config XML, bot-goal/state JSON, logs, navigation meshes, quest JSON or client files are replaced by the scripts. Existing `languages/`, `scripts/`, `wwwroot/`, `navmesh/`, launcher/account files and all other unlisted files remain. Translation sources and project dependency versions did not change in this integration; an existing playable installation must already contain its language/runtime world assets. This is an update package, not a complete clean-world distribution.

## Safe deployment procedure

Prefer a **separate stopped copy of the existing playable installation** for the first test. Keep the original installation untouched until Windows and in-game acceptance passes.

1. Close the launcher and client and gracefully stop the server. Confirm `CoreServer.exe` is gone; do not copy a database while the server has it open.
2. Make a full stopped-installation snapshot outside that installation, including `runtime/data/`, database sidecars if present, server and launcher config, account/client profiles, bot settings and records. Keep the SQLite database and its WAL/SHM companions together. This snapshot protects persistent data if subsequent test startup writes it. Do not substitute a release database or run `build_release_035.py`, clean-slate tools or edition database swap scripts on your save.
3. Make a separate test copy. Inspect configuration in the copy, especially database connection paths, root paths, client paths and profile settings. Any absolute path pointing at the original database or configuration must be redirected to the test copy before any launch. Ensure only one server/client/launcher is running during a later test. Do not treat a filesystem copy with an unchanged absolute database connection as isolated.
4. Extract this ZIP outside both installation and backup directories. Review `BUILD-INFO.json`, `REPLACEMENTS.csv` and this document. You can verify all package hashes in PowerShell:

```powershell
Set-Location 'C:\BeezBuilds\beez-online-d39eb0a'
Get-Content .\SHA256SUMS | ForEach-Object {
    $expected, $relative = $_ -split '  ', 2
    if ((Get-FileHash -LiteralPath $relative -Algorithm SHA256).Hash -ne $expected) {
        throw "Package hash mismatch: $relative"
    }
}
```

5. Preview against the actual test-copy root (the directory containing `runtime`). The scripts refuse a root without the existing playable database and refuse deployment while named server/launcher/client processes are running:

```powershell
.\Deploy-TestBuild.ps1 -InstallRoot 'C:\Games\BeezOnline-Test' -IncludeLauncher
```

6. Apply only after reviewing the preview and manifest. Use a new external binary backup directory:

```powershell
.\Deploy-TestBuild.ps1 -InstallRoot 'C:\Games\BeezOnline-Test' `
    -BackupRoot 'C:\BeezBackups\pre-d39eb0a-test' -IncludeLauncher -Apply
```

`-IncludeLauncher` is recommended to test upstream's new siege, battleground and option UI; omit it for a server-only update. Both binaries and all dependencies for the selected components are backed up and hash-checked **before** the first replacement. `ROLLBACK.json` records pre-existing files and newly added files. After copying, all deployed hashes are checked. If copying fails, do not launch; use rollback.

The scripts neither start/stop processes nor edit persistent data. A copied script is not a backup; retain the whole binary backup directory and full-install snapshot. If PowerShell policy blocks a script, use your usual reviewed-script policy/process rather than disabling security globally.

7. Compare the preserved configuration to the notes below. Run Windows/in-game acceptance yourself only when ready; no launch command is included in this package. For the usual launcher layout the server entry point remains `runtime/server/CoreServer.exe`. Use the test copy's launcher, not the original installation's shortcut. Close the test copy completely before any return to the original.

## Upstream 0.35 runtime assets and client requirements

DLL updates alone do not install the newer world. `UPSTREAM-ASSETS.json` records exact released paths, sizes and hashes of the quest/navigation metadata observed in v0.35b. Those files are **not included or automatically applied**:

- `runtime/server/classic-quests.json`: markers, quest event spawns and related classic quest behavior need this plus matching quest/NPC/spawn/item/database rows. Missing file leaves that support inactive.
- `runtime/server/classic-quest-guides.json`: period walkthroughs; missing file falls back to existing journal text. Guides include third-party source attribution.
- `runtime/server/navmesh/seams.json` and `pockets.json`: cross-zone border and enclosed-pocket metadata. They must match the navigation meshes that generated them. Missing metadata retains fallback behavior. Do not drop these files onto unrelated old meshes or globally replace navigation to perform this binary test.
- Full classic quest populations, restored spawns and new world content require a reviewed **data migration** against the existing saved world. No such migration is delivered here; importing the clean release database would erase/replace your saved world. Upstream introduced no database model/schema change in this integration.
- Existing language files, `config/logconfig.xml`, scripts and world/navigation data are prerequisites and are preserved. No new mandatory XML configuration was added. Ordinary startup can still register properties and write bot/world/player state.

The server/client feature set includes newer upstream work documented as 0.4 work in progress on top of the 0.35 release. Recorded v0.35b data is a source for investigation, not proof of full alignment with every new code path or the owner's existing database.

Client improvements are feature-specific, not requirements to merely load the server assemblies:

- Classic frontier war-map icons require `source/server/tools/patch_classic_warmap_client.py`, matching `build_classic_warmap_textures.py` output and the matching war-map XML (milegate icons removed).
- Red quest markers require `patch_quest_marker_range_client.py`. QUEST GUIDE button routing requires `patch_quest_journal_button_client.py`; its code requires the `.bounty` section produced by `patch_bounty_map_client.py`.
- The documented 0.35 no-custom-class chain is the supported v0.32 base client → bounty-map → quest-marker → classic-war-map → quest-journal-button. Verify full base/intermediate hashes and each tool's byte guards; do not run these on an unknown or already patched client. No patches were executed or packaged here.
- Released 0.35 no-custom-class `game.dll` SHA-256: `f55ed6b068e22ce8e1106871c2fad6ee10c18390bbb8b5dc772219ad8c8b83bb`; 0.35b Sluaghbinder client: `e1d471bb19108610ab9c8ca77dd41af40afe716685b03f4cdeda88c05678463b`. Class enablement and world/client edition must agree. Preserve existing `enable_sluaghbinder`; do not infer edition from the DLL filename.
- Bind gateway fallback needs ITEM catalog model **4319** → items NIF **2334** → `items/magprtl2.nif`, with `Lthenge.dds`, `Henge.dds`, `PRTLUNE.dds`. No new client code patch is required by this stock fallback, and no client files are installed here. Confirm those catalog rows/assets in the actual client. Its expansion flag and classic-client compatibility are documented in `notices/BEEZ-BIND-GATEWAYS.md`. Upright appearance, targetability, scale, collision and two-way travel are still pending in-game verification.
- The cyan carved custom gateway and swirling vortex are not provided by a concept image or this binary update. Exact art requires private model/texture/animation catalog additions and client packaging.

## New configuration defaults to review

These are database-backed server properties, not fields to overwrite in `serverconfig.xml`. Existing values remain authoritative; absent properties normally load defaults. Inspect through existing server/launcher configuration facilities during the approved test.

| Property | Default |
| --- | --- |
| `baf_companion_bots_count` (pve) | True |
| `bot_use_town_teleporters` (autonomous) | True |
| `rvr_siege_staged_assault` | True |
| `rvr_siege_defense_ratio` | 0.5 |
| `player_keep_defense_horn_sound` | 219; 0 disables |
| `rvr_battleground_announcements` | True |
| `pve_realm_event_announcements` | True |
| `neutral_raid_encounter_level_cap` | 0; disabled |

The last seven are autonomous settings. The obsolete `neutral_raid_encounter_level` key is not the new cap key. Existing three-column bot-goal JSON remains valid; missing `Battlegrounds` defaults to 0 and level-50 battleground weight must be 0. The integrated RP/name behavior is intentionally shadowofze's implementation; Beez's old RP recovery and additional name masking were removed at the owner's request.

## Rollback

Stop the test launcher, client and server first. Preview then apply against the binary backup created above:

```powershell
.\Rollback-TestBuild.ps1 -BackupRoot 'C:\BeezBackups\pre-d39eb0a-test'
.\Rollback-TestBuild.ps1 -BackupRoot 'C:\BeezBackups\pre-d39eb0a-test' -Apply
```

The script verifies backup hashes, refuses to overwrite binaries modified since deployment, restores every old binary and removes newly added files. It does not delete existing directories or restore/edit databases/configuration.

**Binary rollback is not data rollback after startup.** New code may have persisted bot realm abilities (`trained-level|N|realm-points|M`), property defaults, character progress and world state. For a complete test rollback, retain the current test data separately, then revert the disposable test copy to the full stopped-installation snapshot. This discards test-session progress. Do not blindly roll an older database over newer real character progress. The original install can simply remain untouched when all testing occurred in a correctly isolated copy.

Git source rollback reference is the pre-promotion backup branch. No force-push or branch rewrite is needed to restore installed binaries, and this package does not change Git branches.

## Acceptance before a real-install rollout

Confirm Windows server/launcher startup and SQLite/native-navigation loading on the test copy. Test login, existing characters/inventory, normal loot/equipment and saved settings. Exercise the Developer Ring, Buff Stone, simultaneous songs/chants and single-rank level-15 Mana Roots. Check upstream RP/repeat-kill eligibility and race/rank names, companion pet travel, stable/town routes, siege/BAF behavior and any installed quest/client UI features.

For Bind Stone `/use2`, confirm two visible upright targetable gateways, owner-only interaction in both directions, ten-minute expiry, restrictions, replacement, death/logout/rebind cleanup and absence of duplicates. Do not promote the visual fallback as client-verified until these checks pass.
