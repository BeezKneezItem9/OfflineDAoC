Windows x64 playable **test update package**, built from `d39eb0a9a4d56c80630421c99b92472b33fba6fe`.

This publishes the existing validated ZIP unchanged; no rebuild was performed. SHA-256:

`28001694c4da079cddabae38cebd1623863f11f43cbfccb07db2f445513bf102`

The package contains the self-contained Release server and optional launcher, .NET 10.0.12 dependencies, exact replacement manifest, deployment/rollback scripts and instructions, and verification logs. Download the ZIP and `.sha256` asset and verify them before use.

Validation: 2,786 automated server tests passed; 61 NotExecuted. Windows x64 publishes and native PE/dependency checks passed. Deployment and rollback were exercised against a disposable Linux PowerShell fixture. **Windows execution, installed-world checks and in-game gateway appearance/targetability/two-way travel remain outstanding.**

Use a separate stopped playable-installation copy first. Back up the full installation and check absolute database paths. Read `DEPLOYMENT.md` before applying anything. The scripts default to preview mode and preserve persistent data/configuration; binary rollback does not reverse data written during subsequent testing. Quest/world data, navigation meshes and client patches are not included or automatically installed. The exact custom cyan gateway/vortex art is not part of this build.

The development branch was fast-forwarded to the source commit. Its old HEAD is preserved by `beez-online-pre-promotion-20261009T005845Z` at `fb4a21785ee353e4f8da47189f12ce292d809e8e`.

No server was deployed or started to prepare or publish this package.
