# Beez Online Windows x64 test build — d39eb0a

The GitHub prerelease is now published: [beez-test-d39eb0a](https://github.com/BeezKneezItem9/OfflineDAoC/releases/tag/beez-test-d39eb0a). Download the [original ZIP directly](https://github.com/BeezKneezItem9/OfflineDAoC/releases/download/beez-test-d39eb0a/beez-online-d39eb0a-win-x64-release.zip) and [checksum](https://github.com/BeezKneezItem9/OfflineDAoC/releases/download/beez-test-d39eb0a/beez-online-d39eb0a-win-x64-release.zip.sha256). Local API access was blocked, so the publish-only GitHub Actions workflow uploaded the existing package without rebuilding it. This branch retains an alternative split-file download.

The original validated ZIP was split into four files to meet GitHub's per-file storage limit. It has **not been rebuilt or changed**. Reassembly produces the same ZIP, preserving the deployment scripts, complete replacement manifest, checksum manifest and rollback instructions.

- Build/source commit: `d39eb0a9a4d56c80630421c99b92472b33fba6fe`
- ZIP bytes: `116442595`
- ZIP SHA-256: `28001694c4da079cddabae38cebd1623863f11f43cbfccb07db2f445513bf102`
- Windows x64 self-contained Release server and optional launcher; .NET 10.0.12 dependencies.
- Automated server regression: 2,786 passed, 61 NotExecuted. Windows execution/in-game validation remains outstanding.

## Download the unchanged ZIP on Windows

Download [Download-BeezTest.ps1](https://raw.githubusercontent.com/BeezKneezItem9/OfflineDAoC/beez-test-d39eb0a-download/Download-BeezTest.ps1) and review it. From PowerShell in the directory containing that script:

```powershell
.\Download-BeezTest.ps1 -OutputDirectory 'C:\BeezBuilds\d39eb0a'
```

The script downloads four parts, verifies each part's hash/size, concatenates them in order and verifies the original ZIP hash/size. It does not extract, deploy, modify an installation or start anything. It refuses to replace a different existing ZIP. The parts remain beside the assembled ZIP and can be removed manually afterward.

If script execution policy blocks it, use your usual reviewed-script policy/process. Part order and hashes appear in [DOWNLOAD-MANIFEST.json](DOWNLOAD-MANIFEST.json).

- [Original ZIP checksum](https://raw.githubusercontent.com/BeezKneezItem9/OfflineDAoC/beez-test-d39eb0a-download/beez-online-d39eb0a-win-x64-release.zip.sha256)
- [Deployment and rollback instructions](DEPLOYMENT.md)

Start with a separate stopped playable-installation copy and check absolute database paths. Package deployment scripts default to preview mode. They preserve SQLite data, accounts, configuration and unlisted files. Binary rollback does not restore data written during later testing.

Development and integration branches remain at the source commit. This branch contains download files only, on separate history.
