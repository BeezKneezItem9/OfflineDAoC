#requires -Version 5.1
[CmdletBinding()]
param(
 [string]$InstallRoot='C:\Games\Offline DAOC BEEZ Edition\playable-v0.34',
 [switch]$CheckOnly,
 [string]$Rollback
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
function Assert-Closed {
 if ($env:OS -eq 'Windows_NT') {
  $p=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(CoreServer|OfflineDAoC|OfflineDAoC\.Launcher|game|connect)\.exe$' -or ($_.Name -eq 'dotnet.exe' -and $_.CommandLine -match 'CoreServer\.dll') })
 } else { $p=@(Get-Process -Name CoreServer,OfflineDAoC,game,connect -ErrorAction SilentlyContinue) }
 if ($p.Count) { throw 'BLOCKED: Close server, launcher and client first.' }
}
function Hash([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Literal($value) {
 if ($null -eq $value) { return 'NULL' }
 if ($value -is [bool]) { return [string][int]$value }
 if ($value -is [ValueType]) { return $value.ToString([Globalization.CultureInfo]::InvariantCulture) }
 return "'" + ([string]$value).Replace("'","''") + "'"
}
function Where-Row($row,$keys) {
 return (@($keys | ForEach-Object { '"'+$_+'" IS '+(Literal $row.$_) }) -join ' AND ')
}
function Assert-Paths([string]$path) {
 $p=[IO.Path]::GetFullPath($path)
 while ($p) {
  if ((Test-Path -LiteralPath $p) -and ((Get-Item -LiteralPath $p -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "BLOCKED: Reparse point in repair path $p" }
  $p=[IO.Path]::GetDirectoryName($p)
 }
}
function Write-ClientAtomic([string]$path,[byte[]]$bytes) {
 $temp=Join-Path (Split-Path -Parent $path) ('.beez-class-'+[Guid]::NewGuid().ToString('N'))
 try {
  [IO.File]::WriteAllBytes($temp,$bytes)
  if ((Hash $temp) -ne [Beez.ClientPatch]::Hash($bytes)) { throw 'Staged DLL checksum mismatch.' }
  [IO.File]::Replace($temp,$path,[NullString]::Value)
 } finally { if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Force } }
}
function Patch-Client([byte[]]$b,$state,$reference) {
 # Class registration from verified author's published client, then authoritative
 # patch_sluaghbinder_client_label.py, then patch_sluaghbinder_client_races.py.
 for ($stage=[int]$state.stage; $stage -lt 3; $stage++) {
  $changes=if ($stage -eq 0) { @($reference.core) } elseif ($stage -eq 1) {
   @([pscustomobject]@{offset=0x4f3d1;before='bebc0a9400';after='be8b2b9200'})
  } else {
   @([pscustomobject]@{offset=0x1b3adc;before='e8840f0000';after='83c4049090'},[pscustomobject]@{offset=0x1b3aee;before='e8720f0000';after='83c4049090'})
  }
  foreach ($change in $changes) {
   $old=[Beez.ClientPatch]::Hex($change.before);$new=[Beez.ClientPatch]::Hex($change.after)
   for ($i=0;$i -lt $old.Length;$i++) { if ($b[[int]$change.offset+$i] -ne $old[$i]) { throw 'BLOCKED: Client patch signature mismatch.' } }
   [Array]::Copy($new,0,$b,[int]$change.offset,$new.Length)
  }
  [Beez.ClientPatch]::Checksum($b)
  $next=@($reference.states | Where-Object { $_.family -eq $state.family -and $_.stage -eq ($stage+1) })[0]
  if ([Beez.ClientPatch]::Hash($b) -ne $next.sha256) { throw 'BLOCKED: Patched client does not match verified author state.' }
 }
 return ,$b
}
Assert-Closed
$InstallRoot=(Resolve-Path -LiteralPath $InstallRoot).Path
$database=Join-Path $InstallRoot 'runtime/data/opendaoc.sqlite3.db'
$client=Join-Path $InstallRoot 'runtime/client-opendaoc/app/game.dll'
Assert-Paths $database; Assert-Paths $client
if (!(Test-Path -LiteralPath $database -PathType Leaf)) { throw 'BLOCKED: Active database missing.' }
if (!(Test-Path -LiteralPath $client -PathType Leaf)) { throw 'BLOCKED: game.dll missing.' }
$refPath=Join-Path $PSScriptRoot 'Sluaghbinder-Reference.json'
if ((Hash $refPath) -ne 'bbbbba525a6211b023f551dfee3f5a5ecbd18e616aa8216bd87c0f403dd230a1') { throw 'BLOCKED: Recovery reference checksum mismatch.' }
$reference=Get-Content -LiteralPath $refPath -Raw | ConvertFrom-Json
if ((Hash (Join-Path $PSScriptRoot 'BeezNativeSqlite.cs')) -ne 'd5592bcc432b43ea2625574fb582214fe3d1908febdc669684d878a5b33457ef') { throw 'BLOCKED: SQLite helper checksum mismatch.' }
if (-not ('Beez.NativeSqlite' -as [type])) { Add-Type -Path (Join-Path $PSScriptRoot 'BeezNativeSqlite.cs') }
if (-not ('Beez.ClientPatch' -as [type])) {
 Add-Type -TypeDefinition @'
using System;
using System.Security.Cryptography;
namespace Beez {
 public static class ClientPatch {
  public static byte[] Hex(string s) { byte[] b=new byte[s.Length/2];for(int i=0;i<b.Length;i++) b[i]=Convert.ToByte(s.Substring(i*2,2),16);return b; }
  public static string Hash(byte[] b) { using(var h=SHA256.Create()) return BitConverter.ToString(h.ComputeHash(b)).Replace("-","").ToLowerInvariant(); }
  public static void Checksum(byte[] b) {
   int pe=BitConverter.ToInt32(b,60),o=pe+24+64;
   if(pe<0 || o+4>b.Length || b[pe]!=80 || b[pe+1]!=69 || BitConverter.ToUInt16(b,pe+4)!=0x14c) throw new Exception("Invalid x86 PE image");
   Array.Clear(b,o,4);uint sum=0;
   for(int i=0;i<b.Length;i+=2) { sum+=(uint)(b[i]+(i+1<b.Length ? b[i+1]<<8 : 0));sum=(sum&65535)+(sum>>16); }
   sum=(sum&65535)+(sum>>16);Array.Copy(BitConverter.GetBytes(sum+(uint)b.Length),0,b,o,4);
  }
 }
}
'@
}
$db=$null;$transaction=$false;$changedClient=$false;$backup=$null
try {
 $db=New-Object Beez.NativeSqlite($database)
 $db.Exec('BEGIN IMMEDIATE');$transaction=$true
 if ($db.Scalar('PRAGMA quick_check') -ne 'ok') { throw 'BLOCKED: SQLite integrity check failed.' }
 if ($Rollback) {
  $record=Get-Content -LiteralPath (Join-Path $Rollback 'REPAIR.json') -Raw | ConvertFrom-Json
  if ($record.installRoot -ne $InstallRoot -or (Hash $client) -ne $record.afterClientHash) { throw 'BLOCKED: Rollback installation or client no longer matches.' }
  if ((Hash (Join-Path $Rollback 'game.dll')) -ne $record.beforeClientHash) { throw 'BLOCKED: Original DLL backup checksum mismatch.' }
  if ($db.Scalar("SELECT Value FROM ServerProperty WHERE `"Key`"='enable_sluaghbinder'") -cne 'True') { throw 'BLOCKED: Class setting changed since repair.' }
  foreach ($row in $record.inserted) {
   $definition=@($reference.tables | Where-Object { $_.name -ceq $row.table })
   if ($definition.Count -ne 1 -or @($definition[0].rows | Where-Object { $columns=@($_.PSObject.Properties.Name | Where-Object { $_ -ne $definition[0].auto -and $_ -ne 'LastTimeRowUpdated' }); (Where-Row $_ $columns) -ceq $row.verify }).Count -ne 1) { throw 'BLOCKED: Invalid rollback record.' }
   if ($db.Scalar('SELECT COUNT(*) FROM "'+$row.table+'" WHERE '+$row.verify) -ne '1') { throw 'BLOCKED: Inserted row changed since repair; rollback requires review.' }
  }
  foreach ($row in $record.inserted) { $db.Exec('DELETE FROM "'+$row.table+'" WHERE '+$row.verify) }
  $db.Exec('UPDATE ServerProperty SET Value='+(Literal $record.beforeValue)+" WHERE `"Key`"='enable_sluaghbinder'")
  if (!$CheckOnly) {
   Assert-Closed
   $current=[IO.File]::ReadAllBytes($client)
   try { Write-ClientAtomic $client ([IO.File]::ReadAllBytes((Join-Path $Rollback 'game.dll')));$db.Exec('COMMIT');$transaction=$false }
   catch { Write-ClientAtomic $client $current;throw }
   Write-Output 'ROLLED BACK: Only repair-created records, setting and client DLL restored.'
  } else { Write-Output 'READY: Targeted rollback verified; no changes committed.' }
  return
 }
 $beforeHash=Hash $client
 $states=@($reference.states | Where-Object {$_.sha256 -eq $beforeHash})
 if ($states.Count -ne 1) { throw "BLOCKED: Unsupported or ambiguous game.dll SHA-256 $beforeHash. No patch applied." }
 $state=$states[0]
 Write-Output "CLIENT: Verified author $($state.family) client, class patch stage $($state.stage)/3; SHA-256 $beforeHash"
 foreach ($asset in $reference.assets) {
  $path=Join-Path (Split-Path -Parent $client) $asset.path;Assert-Paths $path
  if (!(Test-Path -LiteralPath $path -PathType Leaf) -or (Hash $path) -ne $asset.sha256) { throw "BLOCKED: Required class client asset/catalog differs or is missing: $($asset.path). An asset-specific compatibility review is required; no client/world download will be attempted." }
 }
 $patched=Patch-Client ([IO.File]::ReadAllBytes($client)) $state $reference
 if ($db.Scalar("SELECT COUNT(*) FROM ServerProperty WHERE `"Key`"='enable_sluaghbinder'") -ne '1') { throw 'BLOCKED: Exactly one saved enable_sluaghbinder property required.' }
 $before=$db.Scalar("SELECT Value FROM ServerProperty WHERE `"Key`"='enable_sluaghbinder'")
 if ($before -notmatch '^(?i:true|false)$') { throw 'BLOCKED: Unsupported saved setting value.' }
 $inserted=New-Object System.Collections.Generic.List[object]
 foreach ($table in $reference.tables) {
  $name=$table.name
  if ($name -notmatch '^[A-Za-z]+$') { throw 'BLOCKED: Invalid reference table.' }
  if ($db.Scalar("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND lower(tbl_name)=lower("+(Literal $name)+")") -ne '0') { throw "BLOCKED: Custom triggers on $name require review." }
  foreach ($row in $table.rows) {
   $keys=@($table.keys);$where=Where-Row $row $keys
   $columns=@($row.PSObject.Properties.Name | Where-Object { $_ -ne $table.auto -and $_ -ne 'LastTimeRowUpdated' })
   $verify=Where-Row $row $columns
   $count=$db.Scalar('SELECT COUNT(*) FROM "'+$name+'" WHERE '+$where)
   if ($count -eq '1') {
    if ($db.Scalar('SELECT COUNT(*) FROM "'+$name+'" WHERE '+$verify) -ne '1') { throw "BLOCKED: Existing $name class record differs from authoritative 0.35b data ($where); preserved for review." }
   } elseif ($count -eq '0') {
    # Common career specialization/abilities must already exist; never import them.
    $own=$table.restore -or ($name -eq 'Specialization' -and $row.KeyName -notmatch '^Character|^Epic Spells$') -or ($name -eq 'SpecXAbility' -and $row.Spec -notmatch '^Character')
    if (!$own) { throw "BLOCKED: Shared class dependency missing: $name ($where)." }
    $writeColumns=@($row.PSObject.Properties.Name | Where-Object {$_ -ne $table.auto})
    $sql='INSERT INTO "'+$name+'" ('+(@($writeColumns | ForEach-Object {'"'+$_+'"'}) -join ',')+') VALUES ('+(@($writeColumns | ForEach-Object {Literal $row.$_}) -join ',')+')'
    $db.Exec($sql)
    if ($db.Scalar('SELECT COUNT(*) FROM "'+$name+'" WHERE '+$verify) -ne '1') { throw 'BLOCKED: Insert verification failed.' }
    $inserted.Add([pscustomobject]@{table=$name;verify=$verify})
   } else { throw "BLOCKED: Ambiguous duplicate $name class record ($where)." }
  }
 }
 if ($db.Scalar('SELECT COUNT(*) FROM ClassXSpecialization WHERE ClassID=63') -ne '9') { throw 'BLOCKED: ClassID 63 requires exactly nine verified bindings.' }
 if ($db.Scalar("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND lower(tbl_name)='serverproperty'") -ne '0') { throw 'BLOCKED: Custom property triggers require review.' }
 Assert-Closed
 if ($CheckOnly) { Write-Output "READY: Client and class dependencies verified; $($inserted.Count) missing records can be restored. No changes committed.";return }
 if ($inserted.Count -eq 0 -and $state.stage -eq 3 -and $before -ceq 'True') { Write-Output 'ALREADY ENABLED: Verified client and complete class data; no changes.';return }
 $backup=Join-Path $InstallRoot ('runtime/deployment-backups/sluaghbinder-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'-'+[Guid]::NewGuid().ToString('N'))
 Assert-Paths $backup
 New-Item -ItemType Directory -Path $backup | Out-Null
 Copy-Item -LiteralPath $client -Destination (Join-Path $backup 'game.dll')
 if ((Hash (Join-Path $backup 'game.dll')) -ne $beforeHash) { throw 'BLOCKED: Original client backup verification failed.' }
 $record=[pscustomobject]@{format=1;installRoot=$InstallRoot;beforeValue=$before;beforeClientHash=$beforeHash;afterClientHash=[Beez.ClientPatch]::Hash($patched);inserted=@($inserted.ToArray())}
 $record | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $backup 'REPAIR.json') -Encoding UTF8
 $db.Exec("UPDATE ServerProperty SET Value='True' WHERE `"Key`"='enable_sluaghbinder'")
 if ($db.Scalar('SELECT changes()') -ne '1' -or $db.Scalar("SELECT Value FROM ServerProperty WHERE `"Key`"='enable_sluaghbinder'") -cne 'True') { throw 'BLOCKED: Class setting verification failed.' }
 if ((Hash $client) -ne $beforeHash) { throw 'BLOCKED: Client changed during verification.' }
 if ($state.stage -lt 3) { $changedClient=$true;Write-ClientAtomic $client $patched }
 if ((Hash $client) -ne $record.afterClientHash) { throw 'BLOCKED: Client write verification failed.' }
 $db.Exec('COMMIT');$transaction=$false
 Write-Output "ENABLED: Restored $($inserted.Count) missing class records; verified class-only client patches and setting True. Targeted backup: $backup"
 Write-Output 'Characters, accounts, inventories, progression, configuration and unrelated world/client data preserved. No server started.'
} catch {
 if ($transaction -and $null -ne $db) { $db.Exec('ROLLBACK');$transaction=$false }
 if ($changedClient -and $backup -and (Hash $client) -ne $beforeHash) {
  try { Write-ClientAtomic $client ([IO.File]::ReadAllBytes((Join-Path $backup 'game.dll')));if ((Hash $client) -ne $beforeHash) {throw 'Original client hash mismatch'} }
  catch { throw "REPAIR FAILED; CLIENT ROLLBACK FAILED: $($_.Exception.Message). Keep everything closed; backup $backup" }
 }
 throw "BLOCKED: Sluaghbinder repair failed: $($_.Exception.Message)"
} finally { if ($null -ne $db) {if ($transaction) {$db.Exec('ROLLBACK')};$db.Dispose()} }
