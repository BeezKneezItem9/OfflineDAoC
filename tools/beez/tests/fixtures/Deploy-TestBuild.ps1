[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$InstallRoot,
    [string]$BackupRoot,
    [switch]$IncludeLauncher,
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$InstallRoot = (Resolve-Path -LiteralPath $InstallRoot).Path.TrimEnd('\')
$PackageRoot = $PSScriptRoot
if (!(Test-Path -LiteralPath (Join-Path $InstallRoot 'runtime\data\opendaoc.sqlite3.db'))) { throw 'Expected playable database not found; check InstallRoot.' }
$running = @(Get-Process -Name CoreServer,OfflineDAoC,game -ErrorAction SilentlyContinue)
if ($running.Count -gt 0) { throw 'Close the launcher, client and server before deployment. This script never stops or starts them.' }
$rows = @(Import-Csv -LiteralPath (Join-Path $PackageRoot 'REPLACEMENTS.csv') | Where-Object { $_.Component -eq 'server' -or ($IncludeLauncher -and $_.Component -eq 'launcher') })
foreach ($row in $rows) {
    if ($row.Source -match '\.\.|^[/\\]|:' -or $row.Target -match '\.\.|^[/\\]|:') { throw 'Unsafe manifest path.' }
    if ($row.Component -eq 'server' -and !$row.Target.StartsWith('runtime/server/')) { throw 'Unexpected server target.' }
    if ($row.Component -eq 'launcher' -and (!$row.Target.StartsWith('runtime/') -or $row.Target.StartsWith('runtime/server/'))) { throw 'Unexpected launcher target.' }
    if ($row.Target -notmatch '\.(dll|exe|pdb)$|\.(deps|runtimeconfig)\.json$') { throw 'Non-binary/configuration target rejected.' }
    $source = Join-Path $PackageRoot $row.Source
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $row.SHA256) { throw "Payload hash mismatch: $source" }
}
Write-Host "Verified $($rows.Count) replacement/addition paths. Launcher included: $IncludeLauncher"
if (!$Apply) { Write-Host 'Review REPLACEMENTS.csv. No changes made; pass -Apply with an external BackupRoot to deploy.'; return }
if (!$BackupRoot) { throw 'An explicit external BackupRoot is required with -Apply.' }
$BackupRoot = [IO.Path]::GetFullPath($BackupRoot).TrimEnd('\')
if ($BackupRoot -eq $InstallRoot -or $BackupRoot.StartsWith($InstallRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'BackupRoot must be outside the playable installation.' }
if (Test-Path -LiteralPath $BackupRoot) { throw 'BackupRoot must be a new directory.' }
New-Item -ItemType Directory -Path $BackupRoot | Out-Null
# Complete every binary backup before replacing anything. The database is never copied or opened here.
$records = @()
foreach ($row in $rows) {
    $target = Join-Path $InstallRoot $row.Target
    $existed = Test-Path -LiteralPath $target -PathType Leaf
    $oldHash = $null
    if ($existed) {
        $backup = Join-Path $BackupRoot $row.Target
        New-Item -ItemType Directory -Path (Split-Path -Parent $backup) -Force | Out-Null
        $oldHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
        Copy-Item -LiteralPath $target -Destination $backup
        if ((Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash -ne $oldHash) { throw "Backup failed: $target" }
    }
    $records += [pscustomobject]@{ Target=$row.Target; Existed=$existed; OldSHA256=$oldHash; NewSHA256=$row.SHA256 }
}
[pscustomobject]@{ InstallRoot=$InstallRoot; Commit='992b959fbf44a48497a4e5baae5a9937dce4a6c2'; Records=$records } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $BackupRoot 'ROLLBACK.json') -Encoding UTF8
foreach ($row in $rows) {
    $target = Join-Path $InstallRoot $row.Target
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $PackageRoot $row.Source) -Destination $target -Force
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $row.SHA256) { throw "Copy failed: $target. Use Rollback-TestBuild.ps1 before any startup." }
}
Write-Host "Build files installed and verified. Binary backup: $BackupRoot. No server was started."
