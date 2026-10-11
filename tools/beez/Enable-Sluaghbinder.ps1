#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$InstallRoot = 'C:\Games\Offline DAOC BEEZ Edition\playable-v0.34',
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-BeezClosed {
    if ($env:OS -eq 'Windows_NT') {
        $running = @(Get-CimInstance Win32_Process | Where-Object {
            $_.Name -match '^(CoreServer|OfflineDAoC|OfflineDAoC\.Launcher|game|connect)\.exe$' -or
            ($_.Name -eq 'dotnet.exe' -and $_.CommandLine -match 'CoreServer\.dll')
        })
    } else {
        # Allows native SQLite fixture tests on Linux; Windows always uses CIM.
        $running = @(Get-Process -Name CoreServer,OfflineDAoC,game,connect -ErrorAction SilentlyContinue)
    }
    if ($running.Count) { throw 'BLOCKED: Close the server, launcher and game client first. No processes will be stopped.' }
}

Assert-BeezClosed
$InstallRoot = (Resolve-Path -LiteralPath $InstallRoot).Path
$database = Join-Path $InstallRoot 'runtime/data/opendaoc.sqlite3.db'
$client = Join-Path $InstallRoot 'runtime/client-opendaoc/app/game.dll'
if (!(Test-Path -LiteralPath $database -PathType Leaf)) { throw 'BLOCKED: Active playable database not found.' }
if (!(Test-Path -LiteralPath $client -PathType Leaf)) { throw 'BLOCKED: game.dll not found; no client will be downloaded.' }
$clientHash = (Get-FileHash -LiteralPath $client -Algorithm SHA256).Hash.ToLowerInvariant()
$expectedClient = 'e1d471bb19108610ab9c8ca77dd41af40afe716685b03f4cdeda88c05678463b'
if ($clientHash -ne $expectedClient) {
    if ($clientHash -eq 'f55ed6b068e22ce8e1106871c2fad6ee10c18390bbb8b5dc772219ad8c8b83bb') {
        throw 'BLOCKED: Plain 0.35 client detected. The author''s 0.35b class-label/race patches are required. Client files were not changed.'
    }
    throw "BLOCKED: Unverified client SHA-256 $clientHash. Expected the original 0.35b client. No data changed."
}
# Windows 10/11 includes native SQLite in winsqlite3.dll. No managed SQLite assembly,
# Python, editor, downloaded dependency or PowerShell 7 feature is required.
if (-not ('Beez.NativeSqlite' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;
namespace Beez {
 public sealed class NativeSqlite : IDisposable {
  IntPtr db;
  const string Library = "winsqlite3.dll";
  [DllImport(Library, CallingConvention=CallingConvention.Cdecl)] static extern int sqlite3_open_v2(byte[] name, out IntPtr db, int flags, IntPtr vfs);
  [DllImport(Library, CallingConvention=CallingConvention.Cdecl)] static extern int sqlite3_close(IntPtr db);
  [DllImport(Library, CallingConvention=CallingConvention.Cdecl)] static extern int sqlite3_busy_timeout(IntPtr db, int ms);
  [DllImport(Library, CallingConvention=CallingConvention.Cdecl)] static extern IntPtr sqlite3_errmsg(IntPtr db);
  [DllImport(Library, CallingConvention=CallingConvention.Cdecl)] static extern int sqlite3_prepare_v2(IntPtr db, byte[] sql, int count, out IntPtr stmt, IntPtr tail);
  [DllImport(Library, CallingConvention=CallingConvention.Cdecl)] static extern int sqlite3_step(IntPtr stmt);
  [DllImport(Library, CallingConvention=CallingConvention.Cdecl)] static extern IntPtr sqlite3_column_text(IntPtr stmt, int col);
  [DllImport(Library, CallingConvention=CallingConvention.Cdecl)] static extern int sqlite3_finalize(IntPtr stmt);
  static byte[] Utf8(string s) { return Encoding.UTF8.GetBytes(s + "\0"); }
  static string Text(IntPtr p) {
   if (p == IntPtr.Zero) return null;
   int n=0; while (Marshal.ReadByte(p,n)!=0) n++;
   byte[] b=new byte[n]; Marshal.Copy(p,b,0,n); return Encoding.UTF8.GetString(b);
  }
  void Check(int rc) { if(rc!=0) throw new InvalidOperationException("SQLite: " + Text(sqlite3_errmsg(db))); }
  public NativeSqlite(string path) {
   try { Check(sqlite3_open_v2(Utf8(path),out db,2,IntPtr.Zero)); Check(sqlite3_busy_timeout(db,2500)); }
   catch { Dispose(); throw; }
  }
  public string Scalar(string sql) {
   IntPtr stmt=IntPtr.Zero;
   try {
    Check(sqlite3_prepare_v2(db,Utf8(sql),-1,out stmt,IntPtr.Zero));
    int rc=sqlite3_step(stmt);
    if(rc==100) return Text(sqlite3_column_text(stmt,0));
    if(rc==101) return null;
    Check(rc); return null;
   } finally { if(stmt!=IntPtr.Zero) sqlite3_finalize(stmt); }
  }
  public void Exec(string sql) {
   IntPtr stmt=IntPtr.Zero;
   try { Check(sqlite3_prepare_v2(db,Utf8(sql),-1,out stmt,IntPtr.Zero)); int rc=sqlite3_step(stmt); if(rc!=101) Check(rc); }
   finally { if(stmt!=IntPtr.Zero) sqlite3_finalize(stmt); }
  }
  public void Dispose() { if(db!=IntPtr.Zero) { sqlite3_close(db); db=IntPtr.Zero; } }
 }
}
'@
}
$db = $null
$transaction = $false
try {
    $db = New-Object Beez.NativeSqlite($database)
    # Writer lock prevents prerequisites or the property changing between checks and update.
    $db.Exec('BEGIN IMMEDIATE'); $transaction = $true
    if ($db.Scalar('PRAGMA quick_check') -ne 'ok') { throw 'BLOCKED: Database integrity check failed.' }
    if ($db.Scalar('SELECT COUNT(*) FROM ClassXSpecialization WHERE ClassID=63') -ne '9') {
        throw 'BLOCKED: ClassID 63 must have exactly nine specialization records. No world data will be imported.'
    }
    if ($db.Scalar("SELECT COUNT(*) FROM Mob WHERE Mob_ID='sluaghbinder_trainer_tir_na_nog' AND ClassType='DOL.GS.Trainer.SluaghbinderTrainer'") -ne '1') {
        throw 'BLOCKED: Original Sluaghbinder trainer missing or ambiguous.'
    }
    if ($db.Scalar("SELECT COUNT(*) FROM ServerProperty WHERE `"Key`"='enable_sluaghbinder'") -ne '1') {
        throw 'BLOCKED: enable_sluaghbinder must have exactly one saved property row.'
    }
    if ($db.Scalar("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND lower(tbl_name)='serverproperty'") -ne '0') {
        throw 'BLOCKED: Custom ServerProperty triggers require review before changing the setting.'
    }
    $before = $db.Scalar("SELECT Value FROM ServerProperty WHERE `"Key`"='enable_sluaghbinder'")
    Assert-BeezClosed
    if ($CheckOnly) {
        $db.Exec('ROLLBACK'); $transaction = $false
        Write-Output "READY: Sluaghbinder prerequisites verified. Current setting: $before. No setting changed."
    } elseif ($null -ne $before -and $before.Trim().Equals('True',[StringComparison]::OrdinalIgnoreCase)) {
        $db.Exec('ROLLBACK'); $transaction = $false
        Write-Output 'ALREADY ENABLED: Sluaghbinder is True; no data changed.'
    } else {
        $db.Exec("UPDATE ServerProperty SET Value='True' WHERE `"Key`"='enable_sluaghbinder'")
        if ($db.Scalar('SELECT changes()') -ne '1' -or
            $db.Scalar("SELECT Value FROM ServerProperty WHERE `"Key`"='enable_sluaghbinder'") -cne 'True') {
            throw 'BLOCKED: Post-update verification failed; transaction will be rolled back.'
        }
        $db.Exec('COMMIT'); $transaction = $false
        Write-Output 'ENABLED: Sluaghbinder is now True. Only its saved setting changed. Open the launcher normally; no server was started.'
    }
} catch {
    throw "Sluaghbinder enablement failed: $($_.Exception.Message)"
} finally {
    if ($null -ne $db) {
        if ($transaction) { try { $db.Exec('ROLLBACK') } catch { Write-Warning 'SQLite rollback failed; review database before startup.' } }
        $db.Dispose()
    }
}
