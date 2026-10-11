#requires -Version 5.1
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$Revision,
 [string]$InstallRoot='C:\Games\Offline DAOC BEEZ Edition\playable-v0.34',
 [switch]$CheckOnly,
 [switch]$ToolsOnly
)
$ErrorActionPreference='Stop'
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
$base="https://raw.githubusercontent.com/BeezKneezItem9/OfflineDAoC/$Revision/tools/beez"
$dest=Join-Path $env:LOCALAPPDATA 'BeezUpdater/tools'
$stage=Join-Path ([IO.Path]::GetTempPath()) ('beez-tools-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
 $manifest=Join-Path $stage 'TOOLS.sha256'
 Invoke-WebRequest -UseBasicParsing -Uri "$base/TOOLS.sha256" -OutFile $manifest
 if ((Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash -ne 'dcf749c5f8aa8d544b156d15d7730cebfc9710f39cc43fc3898bd5456a56bd55') { throw 'Tool manifest checksum mismatch.' }
 foreach ($line in [IO.File]::ReadAllLines($manifest)) {
  if ($line -notmatch '^([0-9a-f]{64})  ([A-Za-z0-9.-]+)$') { throw 'Invalid tool manifest.' }
  $hash=$Matches[1];$name=$Matches[2];$path=Join-Path $stage $name
  Invoke-WebRequest -UseBasicParsing -Uri "$base/$name" -OutFile $path
  if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $hash) { throw "Tool checksum mismatch: $name" }
 }
 New-Item -ItemType Directory -Path $dest -Force | Out-Null
 Get-ChildItem -LiteralPath $stage -File | Copy-Item -Destination $dest -Force
 Write-Output "Verified maintenance tools installed: $dest"
 if (!$ToolsOnly) { & (Join-Path $dest 'Repair-Sluaghbinder.ps1') -InstallRoot $InstallRoot -CheckOnly:$CheckOnly }
} finally { Remove-Item -LiteralPath $stage -Recurse -Force }
