[CmdletBinding()]
param([string]$OutputDirectory = (Get-Location).Path,
      [string]$Revision = 'beez-test-d39eb0a-download')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$manifest = @'
{
  "commit": "d39eb0a9a4d56c80630421c99b92472b33fba6fe",
  "filename": "beez-online-d39eb0a-win-x64-release.zip",
  "bytes": 116442595,
  "sha256": "28001694c4da079cddabae38cebd1623863f11f43cbfccb07db2f445513bf102",
  "parts": [
    {
      "name": "beez-online-d39eb0a-win-x64-release.zip.part01",
      "bytes": 33554432,
      "sha256": "0473ee060fb4e0fde5a48fb1f8f5a55e97ba1d6dd2d3729d89ffee49d7b283ef"
    },
    {
      "name": "beez-online-d39eb0a-win-x64-release.zip.part02",
      "bytes": 33554432,
      "sha256": "8fa33244361cd12fbb4f35d4fccbca6ef7f9c949158a55de61b7ac0723739610"
    },
    {
      "name": "beez-online-d39eb0a-win-x64-release.zip.part03",
      "bytes": 33554432,
      "sha256": "0cd3a574efcb34b15ad4dea6f56df5b3aba01fcc7a84fcbb76f305179b39dd5f"
    },
    {
      "name": "beez-online-d39eb0a-win-x64-release.zip.part04",
      "bytes": 15779299,
      "sha256": "98dd667973eb6a388e44ac0155e274f6da5bbd15199ef55f76ec3fcfa10262e3"
    }
  ]
}
'@ | ConvertFrom-Json
$base = "https://raw.githubusercontent.com/BeezKneezItem9/OfflineDAoC/$Revision"
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$OutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path
$output = Join-Path $OutputDirectory $manifest.filename
if (Test-Path -LiteralPath $output) {
    if ((Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash -eq $manifest.sha256) {
        Write-Host "Already downloaded and verified: $output"; return
    }
    throw "Destination exists with a different hash; choose another output directory: $output"
}
foreach ($part in $manifest.parts) {
    $path = Join-Path $OutputDirectory $part.name
    if (!(Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -ne $part.bytes -or
        (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $part.sha256) {
        Write-Host "Downloading $($part.name)"
        Invoke-WebRequest -Uri "$base/$($part.name)" -OutFile $path -UseBasicParsing
    }
    if ((Get-Item -LiteralPath $path).Length -ne $part.bytes -or
        (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $part.sha256) {
        throw "Download verification failed: $path"
    }
}
$temporary = $output + '.assembling'
$destination = [IO.File]::Open($temporary, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
try {
    foreach ($part in $manifest.parts) {
        $source = [IO.File]::OpenRead((Join-Path $OutputDirectory $part.name))
        try { $source.CopyTo($destination) } finally { $source.Dispose() }
    }
} finally { $destination.Dispose() }
if ((Get-Item -LiteralPath $temporary).Length -ne $manifest.bytes -or
    (Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash -ne $manifest.sha256) {
    throw "Assembled ZIP verification failed; retained for inspection: $temporary"
}
Move-Item -LiteralPath $temporary -Destination $output
Write-Host "Verified original ZIP: $output"
Write-Host "SHA-256: $($manifest.sha256)"
Write-Host 'No deployment or server launch was performed. Extract and review DEPLOYMENT.md before testing.'
