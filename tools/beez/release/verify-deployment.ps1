param([Parameter(Mandatory=$true)][string]$Package)
$ErrorActionPreference = 'Stop'
$root = Join-Path $env:RUNNER_TEMP ('beez-deploy-proof-' + [Guid]::NewGuid().ToString('N'))
$install = Join-Path $root 'playable'
$backup = Join-Path $root 'backup'
$sentinels = @('runtime/data/opendaoc.sqlite3.db','runtime/server/config/serverconfig.xml','runtime/account.txt','runtime/client-opendaoc/app/game.dll','runtime/server/navmesh/keep.nv')
foreach ($path in $sentinels) {
    $target = [IO.Path]::GetFullPath((Join-Path $install $path))
    New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
    [IO.File]::WriteAllText($target, 'PERSISTENT SENTINEL ' + $path)
}
$rows = @(Import-Csv (Join-Path $Package 'REPLACEMENTS.csv'))
foreach ($row in $rows) {
    $target = Join-Path $install $row.Target
    New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
    [IO.File]::WriteAllText($target, 'ORIGINAL BINARY ' + $row.Target)
}
$before = @{}
foreach ($file in Get-ChildItem $install -File -Recurse) { $before[$file.FullName] = (Get-FileHash $file.FullName).Hash }
& (Join-Path $Package 'Deploy-TestBuild.ps1') -InstallRoot $install -IncludeLauncher
foreach ($path in $before.Keys) { if ((Get-FileHash $path).Hash -ne $before[$path]) { throw 'Preview changed an installation file.' } }
& (Join-Path $Package 'Deploy-TestBuild.ps1') -InstallRoot $install -BackupRoot $backup -IncludeLauncher -Apply
foreach ($row in $rows) { if ((Get-FileHash (Join-Path $install $row.Target)).Hash -ne $row.SHA256) { throw 'Deployed binary hash mismatch.' } }
foreach ($path in $sentinels) { $target = [IO.Path]::GetFullPath((Join-Path $install $path)); if ((Get-FileHash $target).Hash -ne $before[$target]) { throw 'Persistent data changed.' } }
& (Join-Path $Package 'Rollback-TestBuild.ps1') -BackupRoot $backup -Apply
foreach ($path in $before.Keys) { if ((Get-FileHash $path).Hash -ne $before[$path]) { throw 'Rollback did not restore original bytes.' } }
Write-Host "PASS: actual package preview, $($rows.Count) deployed binary hashes, persistent sentinels and rollback verified. No executable launched."
