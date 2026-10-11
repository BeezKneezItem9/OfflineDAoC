#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$InstallRoot = 'C:\Games\Offline DAOC BEEZ Edition\playable-v0.34',
    [string]$CacheRoot,
    [switch]$IncludeLauncher,
    [switch]$EnableSluaghbinder,
    [switch]$RepairSluaghbinder,
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repository = 'BeezKneezItem9/OfflineDAoC'
$runningNames = 'CoreServer','OfflineDAoC','game','connect'
function Assert-Closed {
    if ($env:OS -eq 'Windows_NT') {
        $running = @(Get-CimInstance Win32_Process | Where-Object {
            $_.Name -match '^(CoreServer|OfflineDAoC|OfflineDAoC\.Launcher|game|connect)\.exe$' -or
            ($_.Name -eq 'dotnet.exe' -and $_.CommandLine -match 'CoreServer\.dll')
        })
    } else { $running = @(Get-Process -Name $runningNames -ErrorAction SilentlyContinue) }
    if ($running.Count) { throw 'Close the server, launcher and client first. No processes will be stopped.' }
}
function Assert-PlainPath([string]$path) {
    $cursor = [IO.Path]::GetFullPath($path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Symbolic link/junction requires review: $cursor"
            }
        }
        $parent = [IO.Path]::GetDirectoryName($cursor)
        if ($parent -eq $cursor) { break }; $cursor = $parent
    }
}
function Get-CanonicalPath([string]$path) {
    $full = [IO.Path]::GetFullPath($path)
    $tail = New-Object 'System.Collections.Generic.List[string]'
    while (!(Test-Path -LiteralPath $full)) {
        $tail.Insert(0,[IO.Path]::GetFileName($full))
        $full = [IO.Path]::GetDirectoryName($full)
        if (!$full) { throw 'Cannot resolve cache parent.' }
    }
    $full = (Resolve-Path -LiteralPath $full).Path
    if ($env:OS -eq 'Windows_NT') {
        if (-not ('Beez.LongPath' -as [type])) {
            Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
namespace Beez { public static class LongPath {
 [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
 static extern uint GetLongPathName(string path, StringBuilder result, uint size);
 public static string Expand(string path) {
  var result=new StringBuilder(32768);
  uint n=GetLongPathName(path,result,(uint)result.Capacity);
  if(n==0 || n>=result.Capacity) throw new InvalidOperationException("Cannot resolve Windows long path");
  return result.ToString();
 }
} }
'@
        }
        $full = [Beez.LongPath]::Expand($full)
    }
    foreach ($part in $tail) { $full = Join-Path $full $part }
    return [IO.Path]::GetFullPath($full).TrimEnd([IO.Path]::DirectorySeparatorChar)
}
function Assert-Relative([string]$path) {
    if ([string]::IsNullOrWhiteSpace($path) -or $path -match '\\|:|^/|[\x00-\x1f]' -or
        @($path.Split('/') | Where-Object { $_ -eq '..' -or $_ -eq '.' -or $_ -eq '' -or $_ -match '[. ]$' }).Count) {
        throw "Unsafe package path: $path"
    }
}
function Get-ReleaseAsset($asset, [string]$destination, [string]$tag) {
    $prefix = "https://github.com/$repository/releases/download/$tag/"
    if (!$asset.browser_download_url.StartsWith($prefix,[StringComparison]::Ordinal)) { throw 'Unexpected release asset URL.' }
    if ([IO.Path]::GetFileName($asset.browser_download_url) -ne $asset.name) { throw 'Release asset URL/name mismatch.' }
    Invoke-WebRequest -UseBasicParsing -Uri $asset.browser_download_url -OutFile $destination
}
function Read-Package([string]$zipPath, [string]$stage) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        $names = @{}; [long]$total = 0
        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName.TrimEnd('/')
            Assert-Relative $name
            if ($names.ContainsKey($name)) { throw 'Duplicate/case-colliding ZIP entry.' }
            $names[$name] = $true
            if (($entry.ExternalAttributes -shr 16 -band 0xF000) -eq 0xA000) { throw 'ZIP symbolic link rejected.' }
            $total += $entry.Length
            if ($total -gt 4GB -or $names.Count -gt 15000) { throw 'Package exceeds supported extraction limits.' }
        }
        New-Item -ItemType Directory -Path $stage | Out-Null
        foreach ($entry in $zip.Entries) {
            $target = Join-Path $stage $entry.FullName
            if ($entry.FullName.EndsWith('/')) { New-Item -ItemType Directory -Path $target -Force | Out-Null; continue }
            New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
            $inputStream = $entry.Open(); $outputStream = [IO.File]::Create($target)
            try { $inputStream.CopyTo($outputStream) } finally { $inputStream.Dispose(); $outputStream.Dispose() }
        }
    } finally { $zip.Dispose() }
    $hashes = @{}
    foreach ($line in [IO.File]::ReadAllLines((Join-Path $stage 'SHA256SUMS'))) {
        if ($line -notmatch '^([0-9a-fA-F]{64})  (.+)$') { throw 'Invalid package SHA256SUMS entry.' }
        $hash = $Matches[1]; $name = $Matches[2]; Assert-Relative $name
        if ($name -eq 'SHA256SUMS' -or $hashes.ContainsKey($name)) { throw 'Duplicate/invalid package hash entry.' }
        $hashes[$name] = $hash
        $file = Join-Path $stage $name
        if (!(Test-Path -LiteralPath $file -PathType Leaf) -or
            (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $hash) { throw "Package hash mismatch: $name" }
    }
    $files = @(Get-ChildItem -LiteralPath $stage -File -Recurse)
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($stage.Length + 1).Replace('\','/')
        if ($relative -ne 'SHA256SUMS' -and !$hashes.ContainsKey($relative)) { throw "Unhashed package file: $relative" }
    }
    if ($files.Count -ne $hashes.Count + 1) { throw 'Package file/hash count mismatch.' }
}
function Validate-Replacements([string]$stage, $info) {
    $rows = @(Import-Csv -LiteralPath (Join-Path $stage 'REPLACEMENTS.csv'))
    if ($rows.Count -eq 0 -or $rows.Count -ne $info.replacementCount) { throw 'Replacement count mismatch.' }
    $targets = @{}
    foreach ($row in $rows) {
        Assert-Relative $row.Source; Assert-Relative $row.Target
        if ($row.Component -notin @('server','launcher')) { throw 'Unknown replacement component.' }
        if (!$row.Source.StartsWith("payload/$($row.Component)/",[StringComparison]::Ordinal)) { throw 'Unexpected replacement source.' }
        $suffix = $row.Source.Substring(("payload/$($row.Component)/").Length)
        if ($suffix -notmatch '^[^/]+\.(dll|exe|pdb)$|^[^/]+\.(deps|runtimeconfig)\.json$|^[a-z]{2,3}(?:-[A-Za-z]{2,4})?/[^/]+\.resources\.dll$|^lib/[^/]+\.dll$') {
            throw "Unsupported binary source (persistent/world/client paths are forbidden): $suffix"
        }
        if ($row.Component -eq 'server') {
            $allowed = @("runtime/server/$suffix", "runtime/server/lib/$suffix", "runtime/server/win-x64/$suffix")
            if ($row.Target -cnotin $allowed) { throw 'Unexpected server destination.' }
        } elseif ($row.Target -cne "runtime/$suffix" -or $suffix.StartsWith('lib/')) { throw 'Unexpected launcher destination.' }
        if ($targets.ContainsKey($row.Target)) { throw 'Duplicate/case-colliding replacement target.' }
        $targets[$row.Target] = $true
        $source = Join-Path $stage $row.Source
        if ($row.SHA256 -notmatch '^[0-9a-fA-F]{64}$' -or
            (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $row.SHA256 -or
            (Get-Item -LiteralPath $source).Length -ne [long]$row.Bytes) { throw 'Replacement hash/size mismatch.' }
        Assert-PlainPath (Join-Path $InstallRoot $row.Target)
    }
    if (!($rows | Where-Object { $_.Component -eq 'server' -and $_.Target -ceq 'runtime/server/GameServer.dll' })) {
        throw 'GameServer replacement missing.'
    }
    return $rows
}

if (![Environment]::Is64BitOperatingSystem) { throw 'Beez Windows x64 releases require 64-bit Windows.' }
Assert-Closed
$InstallRoot = Get-CanonicalPath (Resolve-Path -LiteralPath $InstallRoot).Path.TrimEnd([IO.Path]::DirectorySeparatorChar)
Assert-PlainPath $InstallRoot
if (!(Test-Path -LiteralPath (Join-Path $InstallRoot 'runtime/data/opendaoc.sqlite3.db') -PathType Leaf)) { throw 'Active playable database not found.' }
if ($EnableSluaghbinder -and $RepairSluaghbinder) { throw 'Choose only one explicit class option.' }
$classHelper = if ($RepairSluaghbinder) { 'Repair-Sluaghbinder.ps1' } else { 'Enable-Sluaghbinder.ps1' }
if ($EnableSluaghbinder -or $RepairSluaghbinder) {
    # Same standalone validated logic; ordinary updates do not open a database.
    & (Join-Path $PSScriptRoot $classHelper) -InstallRoot $InstallRoot -CheckOnly
}
if (!$CacheRoot) { $CacheRoot = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'BeezUpdater' }
$CacheRoot = Get-CanonicalPath $CacheRoot
if ($CacheRoot.Equals($InstallRoot,[StringComparison]::OrdinalIgnoreCase) -or
    $CacheRoot.StartsWith($InstallRoot + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Updater cache and backups must be outside the playable installation.'
}
Assert-PlainPath $CacheRoot
New-Item -ItemType Directory -Path $CacheRoot -Force | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$releases = @(); $page = 1
# /releases/latest excludes prereleases: enumerate release pages instead.
while ($page -le 20) {
    $batch = @(Invoke-RestMethod -Uri "https://api.github.com/repos/$repository/releases?per_page=100&page=$page" -Headers @{ 'User-Agent'='Beez-Updater'; 'Accept'='application/vnd.github+json' } | ForEach-Object { $_ })
    $releases += $batch
    if ($batch.Count -lt 100) { break }; $page++
}
$candidates = @($releases | Where-Object { !$_.draft -and $_.tag_name -match '^beez-test-[0-9a-f]{7,40}$' } | Sort-Object published_at -Descending)
$release = $null; $zipAsset = $null; $sumAsset = $null
foreach ($candidate in $candidates) {
    $short = $candidate.tag_name.Substring(10)
    $filename = "beez-online-$short-win-x64-release.zip"
    $z = @($candidate.assets | Where-Object { $_.name -ceq $filename })
    $s = @($candidate.assets | Where-Object { $_.name -ceq "$filename.sha256" })
    if ($z.Count -eq 1 -and $s.Count -eq 1) { $release=$candidate; $zipAsset=$z[0]; $sumAsset=$s[0]; break }
}
if ($null -eq $release) { throw 'No compatible Beez Windows x64 test release with ZIP and checksum found.' }
$work = Join-Path $CacheRoot ([Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work | Out-Null
$zipPath = Join-Path $work $zipAsset.name
$sumPath = Join-Path $work $sumAsset.name
Get-ReleaseAsset $sumAsset $sumPath $release.tag_name
$lines = @([IO.File]::ReadAllLines($sumPath) | Where-Object { $_.Trim() })
if ($lines.Count -ne 1 -or $lines[0] -notmatch '^([0-9a-fA-F]{64})\s+\*?([^/\\]+)$' -or $Matches[2] -cne $zipAsset.name) { throw 'Release checksum filename/format mismatch.' }
$expectedZip = $Matches[1]
Get-ReleaseAsset $zipAsset $zipPath $release.tag_name
if ((Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash -ne $expectedZip) { throw 'Release ZIP checksum mismatch. Installation untouched.' }
$stage = Join-Path $work 'package'; Read-Package $zipPath $stage
$info = Get-Content -LiteralPath (Join-Path $stage 'BUILD-INFO.json') -Raw | ConvertFrom-Json
if ($info.repository -cne $repository -or $info.targetBranch -cne 'beez-online-six-features' -or
    $info.rid -cne 'win-x64' -or $info.configuration -cne 'Release' -or $info.selfContained -ne $true -or
    $info.commit -notmatch '^[0-9a-f]{40}$' -or !$info.commit.StartsWith($release.tag_name.Substring(10),[StringComparison]::Ordinal)) {
    throw 'Release metadata is incompatible with this updater.'
}
foreach ($required in @('Deploy-TestBuild.ps1','Rollback-TestBuild.ps1','REPLACEMENTS.csv')) {
    if (!(Test-Path -LiteralPath (Join-Path $stage $required) -PathType Leaf)) { throw "Deployment file missing: $required" }
}
$allRows = @(Validate-Replacements $stage $info)
$rows = @($allRows | Where-Object { $_.Component -eq 'server' -or ($IncludeLauncher -and $_.Component -eq 'launcher') })
$different = @($rows | Where-Object {
    $target = Join-Path $InstallRoot $_.Target
    !(Test-Path -LiteralPath $target -PathType Leaf) -or (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $_.SHA256
})
Assert-Closed
if ($different.Count -eq 0) {
    Write-Output "ALREADY INSTALLED: $($info.commit), selected components match verified release hashes."
    if (($EnableSluaghbinder -or $RepairSluaghbinder) -and $Apply) { & (Join-Path $PSScriptRoot $classHelper) -InstallRoot $InstallRoot }
    return
}
if (!$Apply) {
    & (Join-Path $stage 'Deploy-TestBuild.ps1') -InstallRoot $InstallRoot -IncludeLauncher:$IncludeLauncher
    Write-Output "READY: $($release.tag_name), commit $($info.commit); $($different.Count) changed paths. Pass -Apply to install. No playable files changed."
    return
}
$backup = Join-Path $CacheRoot ('backups/' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N'))
try {
    Assert-Closed
    & (Join-Path $stage 'Deploy-TestBuild.ps1') -InstallRoot $InstallRoot -BackupRoot $backup -IncludeLauncher:$IncludeLauncher -Apply
    foreach ($row in $rows) {
        if ((Get-FileHash -LiteralPath (Join-Path $InstallRoot $row.Target) -Algorithm SHA256).Hash -ne $row.SHA256) { throw 'Installed binary verification failed.' }
    }
} catch {
    $failure = $_.Exception.Message
    if (Test-Path -LiteralPath (Join-Path $backup 'ROLLBACK.json')) {
        try {
            & (Join-Path $stage 'Rollback-TestBuild.ps1') -BackupRoot $backup -Apply
            throw "Update failed; original binaries restored. Cause: $failure"
        } catch {
            if ($_.Exception.Message.StartsWith('Update failed; original binaries restored.')) { throw }
            throw "Update failed: $failure. Automatic rollback failed: $($_.Exception.Message). Keep server closed; backup: $backup"
        }
    }
    throw "Update failed before a complete backup: $failure. Keep server closed and review $backup"
}
[pscustomobject]@{ InstallRoot=$InstallRoot; Commit=$info.commit; Tag=$release.tag_name; IncludeLauncher=[bool]$IncludeLauncher; BackupRoot=$backup; PackageRoot=$stage } |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $work 'INSTALLED.json') -Encoding UTF8
Write-Output "UPDATED: $($release.tag_name), commit $($info.commit). Verified $($rows.Count) binary paths. Backup: $backup"
Write-Output 'Database, characters, configuration, client and world assets preserved. No server or game was started.'
if ($EnableSluaghbinder -or $RepairSluaghbinder) {
    try { & (Join-Path $PSScriptRoot $classHelper) -InstallRoot $InstallRoot }
    catch { throw "Binaries updated successfully, but explicit Sluaghbinder enablement failed: $($_.Exception.Message)" }
}
