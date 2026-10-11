[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$BackupRoot, [switch]$Apply)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$BackupRoot = (Resolve-Path -LiteralPath $BackupRoot).Path
$record = Get-Content -LiteralPath (Join-Path $BackupRoot 'ROLLBACK.json') -Raw | ConvertFrom-Json
$running = @(Get-Process -Name CoreServer,OfflineDAoC,game -ErrorAction SilentlyContinue)
if ($running.Count -gt 0) { throw 'Close the launcher, client and server before rollback.' }
foreach ($row in $record.Records) {
    if ($row.Target -match '\.\.|^[/\\]|:' -or !$row.Target.StartsWith('runtime/') -or $row.Target -notmatch '\.(dll|exe|pdb)$|\.(deps|runtimeconfig)\.json$') { throw 'Unsafe rollback target.' }
    if ($row.Existed) {
        $backup = Join-Path $BackupRoot $row.Target
        if ((Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash -ne $row.OldSHA256) { throw "Backup hash mismatch: $backup" }
    }
    $target = Join-Path $record.InstallRoot $row.Target
    if (Test-Path -LiteralPath $target -PathType Leaf) {
        $hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
        if ($hash -ne $row.NewSHA256 -and $hash -ne $row.OldSHA256) { throw "File changed after deployment; review before rollback: $target" }
    }
}
if (!$Apply) { Write-Host 'Verified binary rollback plan. No changes made; pass -Apply to restore.'; return }
foreach ($row in $record.Records) {
    $target = Join-Path $record.InstallRoot $row.Target
    if ($row.Existed) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $BackupRoot $row.Target) -Destination $target -Force
        if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $row.OldSHA256) { throw "Restore failed: $target" }
    } elseif (Test-Path -LiteralPath $target -PathType Leaf) {
        Remove-Item -LiteralPath $target
    }
}
Write-Host 'Backed-up binaries restored; newly added binary files removed. Persistent files and databases were not changed. No server was started.'
