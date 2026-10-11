"""Recovery SQL/rollback tests. Real binary patch checks require verified author clients."""
import hashlib,json,os,shutil,sqlite3,subprocess,tempfile,unittest
from pathlib import Path
from contextlib import closing
TOOLS=Path(__file__).resolve().parents[1]
REFERENCE=json.loads((TOOLS/'Sluaghbinder-Reference.json').read_text())
PS=os.environ.get('BEEZ_TEST_POWERSHELL','powershell.exe' if os.name=='nt' else 'pwsh')
REAL=os.environ.get('BEEZ_TEST_REPAIR_CLIENT_DIR')

class RecoveryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='beez-repair-');self.root=Path(self.tmp.name)/'playable';self.root.mkdir()
  self.db=self.root/'runtime/data/opendaoc.sqlite3.db';self.db.parent.mkdir(parents=True)
  with closing(sqlite3.connect(self.db)) as c:
   for t in REFERENCE['tables']:
    cols=list(t['rows'][0]);defs=['"'+s+'"'+(' INTEGER PRIMARY KEY AUTOINCREMENT' if s==t['auto'] else '') for s in cols]
    c.execute('CREATE TABLE "'+t['name']+'" ('+','.join(defs)+')')
    c.executemany('INSERT INTO "'+t['name']+'" VALUES ('+','.join('?' for _ in cols)+')',[list(r.values()) for r in t['rows']])
   c.executescript("CREATE TABLE ServerProperty(Key TEXT,Value TEXT);INSERT INTO ServerProperty VALUES('enable_sluaghbinder','False'),('xp_rate','10');CREATE TABLE Character(Name TEXT,XP INTEGER);INSERT INTO Character VALUES('Saved character',123456789);CREATE TABLE Account(Name TEXT);INSERT INTO Account VALUES('Preserved account');")
   c.commit()
  self.client=self.root/'runtime/client-opendaoc/app/game.dll';self.client.parent.mkdir(parents=True)
  self.mock={}
  if REAL:shutil.copyfile(Path(REAL)/'game.dll',self.client)
  else:
   self.client.write_bytes(b'Beez repair CI known client');self.mock[hashlib.sha256(self.client.read_bytes()).hexdigest()]=REFERENCE['states'][-1]['sha256']
  for a in REFERENCE['assets']:
   p=self.client.parent/a['path'];p.parent.mkdir(parents=True,exist_ok=True)
   if REAL:shutil.copyfile(Path(REAL)/'class-assets'/a['path'],p)
   else:p.write_bytes(a['path'].encode());self.mock[hashlib.sha256(p.read_bytes()).hexdigest()]=a['sha256']
  self.config=self.root/'runtime/server/config.xml';self.config.parent.mkdir();self.config.write_bytes(b'original configuration')
 def tearDown(self):self.tmp.cleanup()
 def sql(self,s):
  with closing(sqlite3.connect(self.db)) as c:c.executescript(s);c.commit()
 def snapshot(self):
  with closing(sqlite3.connect(self.db)) as c:return {t:c.execute('SELECT * FROM "'+t+'" ORDER BY rowid').fetchall() for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' and name!='sqlite_sequence'")}
 def ps(self,*args,ok=True,extra='',script='Repair-Sluaghbinder.ps1'):
  def q(s):return "'"+str(s).replace("'","''")+"'"
  prelude=''
  if not REAL:
   maps=';'.join(q(k)+'='+q(v) for k,v in self.mock.items())
   prelude="Import-Module Microsoft.PowerShell.Utility;$global:BeezTestHashes=@{"+maps+"};function Get-FileHash {param($LiteralPath,$Algorithm) $h=Microsoft.PowerShell.Utility\\Get-FileHash -LiteralPath $LiteralPath -Algorithm $Algorithm; if($global:BeezTestHashes.ContainsKey($h.Hash.ToLowerInvariant())) {[pscustomobject]@{Hash=$global:BeezTestHashes[$h.Hash.ToLowerInvariant()]}}else{$h}};"
   # Known complete-client stand-in only. Patch code is never exercised through this double.
   fake='''using System; using System.Security.Cryptography; namespace Beez {public static class ClientPatch {public static byte[] Hex(string s){throw new Exception("CI client must never be patched");}public static void Checksum(byte[] b){throw new Exception("CI client must never be patched");}public static string Hash(byte[] b){using(var h=SHA256.Create()){string s=BitConverter.ToString(h.ComputeHash(b)).Replace("-","").ToLowerInvariant();return s=="CLIENTHASH"?"FINALHASH":s;}}}}'''.replace('CLIENTHASH',hashlib.sha256(b'Beez repair CI known client').hexdigest()).replace('FINALHASH',REFERENCE['states'][-1]['sha256'])
   prelude+='Add-Type -TypeDefinition '+q(fake)+';'
  cmd=prelude+extra+'; & '+q(TOOLS/script)+' -InstallRoot '+q(self.root)+' '+' '.join(str(a) if str(a).startswith('-') else q(a) for a in args)
  p=subprocess.run([PS,'-NoProfile','-Command',cmd],text=True,capture_output=True,timeout=60)
  if ok:self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  else:self.assertNotEqual(p.returncode,0,p.stdout+p.stderr)
  return p.stdout+p.stderr
 def blocked(self):
  before=self.snapshot();client=self.client.read_bytes();out=self.ps(ok=False);self.assertIn('BLOCKED',out);self.assertEqual(before,self.snapshot());self.assertEqual(client,self.client.read_bytes())
 def test_035_missing_eleven_records_and_rollback(self):
  self.sql("DELETE FROM ClassXSpecialization WHERE ClassID=63;DELETE FROM Mob;")
  before=self.snapshot();client=self.client.read_bytes()
  self.assertIn('Restored 11',self.ps())
  state=self.snapshot();self.assertEqual(state['Character'],before['Character']);self.assertEqual(state['Account'],before['Account']);self.assertEqual(state['ServerProperty'],[('enable_sluaghbinder','True'),('xp_rate','10')])
  self.assertEqual(self.config.read_bytes(),b'original configuration')
  backup=next((self.root/'runtime/deployment-backups').glob('sluaghbinder-*'))
  self.assertIn('ROLLED BACK',self.ps('-Rollback',backup));self.assertEqual(before,self.snapshot());self.assertEqual(client,self.client.read_bytes())
 def test_035b_complete_idempotence(self):
  self.assertIn('ENABLED',self.ps());before=self.db.read_bytes();client=self.client.read_bytes()
  self.assertIn('ALREADY ENABLED',self.ps());self.assertEqual(before,self.db.read_bytes());self.assertEqual(client,self.client.read_bytes())
 def test_partial_missing_class_records(self):
  self.sql("DELETE FROM ClassXSpecialization WHERE SpecKeyName='Sluagh Host';DELETE FROM Spell WHERE SpellID=59000;DELETE FROM NpcTemplate WHERE TemplateId=60170001;")
  self.assertIn('Restored 3',self.ps())
 def test_preview_does_not_change_data_or_client(self):
  self.sql('DELETE FROM Mob');before=self.db.read_bytes();client=self.client.read_bytes();self.assertIn('READY',self.ps('-CheckOnly'));self.assertEqual(before,self.db.read_bytes());self.assertEqual(client,self.client.read_bytes())
 def test_modified_existing_spell_blocked(self):self.sql('UPDATE Spell SET Damage=9999 WHERE SpellID=59000');self.blocked()
 def test_duplicate_bindings_blocked(self):self.sql("INSERT INTO ClassXSpecialization(ClassID,SpecKeyName) VALUES(63,'Sluagh Host')");self.blocked()
 def test_extra_binding_blocked(self):self.sql("INSERT INTO ClassXSpecialization(ClassID,SpecKeyName) VALUES(63,'Unexpected')");self.blocked()
 def test_missing_property_blocked(self):self.sql('DELETE FROM ServerProperty');self.blocked()
 def test_missing_asset_blocked(self):next(iter(REFERENCE['assets']));(self.client.parent/REFERENCE['assets'][0]['path']).unlink();self.blocked()
 def test_unknown_client_blocked(self):self.client.write_bytes(b'unknown client');self.blocked()
 def test_trigger_blocked(self):self.sql("CREATE TRIGGER changed AFTER INSERT ON Mob BEGIN DELETE FROM Character;END;DELETE FROM Mob;");self.blocked()
 def test_failed_insert_rolls_back_previous_inserts(self):self.sql("DELETE FROM ClassXSpecialization;DROP TABLE Spell;");before=self.snapshot();self.ps(ok=False);self.assertEqual(before,self.snapshot())
 def test_running_process_blocked(self):
  extra="function Get-CimInstance {param($ClassName) [pscustomobject]@{Name='CoreServer.exe';CommandLine='CoreServer.exe'}};function Get-Process {param($Name,$ErrorAction) [pscustomobject]@{Name='CoreServer'}}"
  before=self.snapshot();self.assertIn('Close server',self.ps(ok=False,extra=extra));self.assertEqual(before,self.snapshot())
 def test_missing_shared_ability_blocked(self):self.sql("DELETE FROM Ability WHERE KeyName='QuickCast'");self.blocked()
 def test_explicit_updater_repair_and_ordinary_update_preservation(self):
  from test_tools import ToolTests
  fixture=ToolTests();fixture.root=Path(self.tmp.name);fixture.install=self.root
  ToolTests.package(fixture)
  ad=str(fixture.asset_dir).replace("'","''")
  extra="function Invoke-RestMethod {param($Uri,$Headers) Get-Content -Raw '"+ad+"/releases.json'|ConvertFrom-Json};function Invoke-WebRequest {param([switch]$UseBasicParsing,$Uri,$OutFile) [IO.File]::Copy((Join-Path '"+ad+"' ([IO.Path]::GetFileName($Uri))),$OutFile)}"
  self.sql('DELETE FROM Mob');before=self.snapshot();client=self.client.read_bytes()
  self.assertIn('UPDATED',self.ps('-CacheRoot',Path(self.tmp.name)/'cache','-Apply',extra=extra,script='Update-Beez.ps1'));self.assertEqual(before,self.snapshot());self.assertEqual(client,self.client.read_bytes())
  out=self.ps('-CacheRoot',Path(self.tmp.name)/'cache','-Apply','-RepairSluaghbinder',extra=extra,script='Update-Beez.ps1')
  self.assertIn('ALREADY INSTALLED',out);self.assertIn('ENABLED',out);self.assertEqual(self.snapshot()['ServerProperty'][0],('enable_sluaghbinder','True'))
 def test_bootstrap_verifies_tools_and_preserves_installation(self):
  toolpath=str(TOOLS).replace("'","''");dest=str(Path(self.tmp.name)/'localappdata').replace("'","''")
  extra="$env:LOCALAPPDATA='"+dest+"';function Invoke-WebRequest {param([switch]$UseBasicParsing,$Uri,$OutFile) [IO.File]::Copy((Join-Path '"+toolpath+"' ([IO.Path]::GetFileName($Uri))),$OutFile)}"
  before=self.snapshot();client=self.client.read_bytes();self.assertIn('Verified maintenance tools',self.ps('-Revision','a'*40,'-ToolsOnly',extra=extra,script='Install-BeezTools.ps1'))
  self.assertEqual(before,self.snapshot());self.assertEqual(client,self.client.read_bytes());self.assertTrue((Path(dest)/'BeezUpdater/tools/Update-Beez.cmd').is_file())
 def test_bootstrap_bad_download_does_not_install_or_repair(self):
  toolpath=str(TOOLS).replace("'","''");dest=str(Path(self.tmp.name)/'localappdata').replace("'","''")
  extra="$env:LOCALAPPDATA='"+dest+"';function Invoke-WebRequest {param([switch]$UseBasicParsing,$Uri,$OutFile) if($Uri.EndsWith('BeezNativeSqlite.cs')) {[IO.File]::WriteAllText($OutFile,'wrong download')}else{[IO.File]::Copy((Join-Path '"+toolpath+"' ([IO.Path]::GetFileName($Uri))),$OutFile)}}"
  before=self.snapshot();self.assertIn('Tool checksum mismatch',self.ps('-Revision','a'*40,ok=False,extra=extra,script='Install-BeezTools.ps1'));self.assertEqual(before,self.snapshot());self.assertFalse((Path(dest)/'BeezUpdater/tools').exists())
 def test_locked_db_blocked(self):
  with closing(sqlite3.connect(self.db)) as c:
   c.execute('BEGIN IMMEDIATE');self.blocked()
 def test_rollback_refuses_changed_inserted_data(self):
  self.sql('DELETE FROM Mob');self.ps();backup=next((self.root/'runtime/deployment-backups').glob('sluaghbinder-*'));self.sql("UPDATE Mob SET Name='Edited' WHERE Mob_ID='sluaghbinder_trainer_tir_na_nog'");before=self.snapshot();self.ps('-Rollback',backup,ok=False);self.assertEqual(before,self.snapshot())
 def test_commit_failure_restores_client_and_database(self):
  self.sql('DELETE FROM Mob')
  if REAL:shutil.copyfile(Path(REAL)/'base.dll',self.client)
  before=self.snapshot();client=self.client.read_bytes()
  source=(TOOLS/'BeezNativeSqlite.cs').read_text().replace('NativeSqlite','RealSqlite')
  wrapper="namespace Beez {public sealed class NativeSqlite : System.IDisposable {RealSqlite db;public NativeSqlite(string path){db=new RealSqlite(path);}public string Scalar(string sql){return db.Scalar(sql);}public void Exec(string sql){if(sql==\"COMMIT\")throw new System.Exception(\"Injected commit failure\");db.Exec(sql);}public void Dispose(){db.Dispose();}}}"
  quote=lambda x:"'"+x.replace("'","''")+"'"
  extra='Add-Type -TypeDefinition '+quote(source+'\n'+wrapper)
  self.assertIn('Injected commit failure',self.ps(ok=False,extra=extra));self.assertEqual(before,self.snapshot());self.assertEqual(client,self.client.read_bytes())
 @unittest.skipUnless(REAL,'Verified author client files required for real binary patch test')
 def test_all_verified_client_patch_states(self):
  for state in REFERENCE['states']:
   with self.subTest(family=state['family'],stage=state['stage']):
    name=state['family'].replace('.','')+'-stage'+str(state['stage'])+'.dll';shutil.copyfile(Path(REAL)/name,self.client)
    self.sql("UPDATE ServerProperty SET Value='False' WHERE Key='enable_sluaghbinder'")
    self.assertIn('ENABLED',self.ps());end=next(s for s in REFERENCE['states'] if s['family']==state['family'] and s['stage']==3)
    self.assertEqual(hashlib.sha256(self.client.read_bytes()).hexdigest(),end['sha256'])

if __name__=='__main__':unittest.main()
