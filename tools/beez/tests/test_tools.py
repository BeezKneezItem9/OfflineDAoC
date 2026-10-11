"""Run with Python's unittest; PowerShell and a verified public 0.35b game.dll are test inputs.
BEEZ_TEST_CLIENT points to that client. On Linux, provide libsqlite3.so.0 as winsqlite3.dll
on LD_LIBRARY_PATH to exercise the exact native ABI without claiming Windows validation.
"""
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
import zipfile

TOOLS = Path(__file__).resolve().parents[1]
PS = os.environ.get('BEEZ_TEST_POWERSHELL', 'powershell.exe' if os.name == 'nt' else 'pwsh')
CLIENT = os.environ.get('BEEZ_TEST_CLIENT')

class ToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='beez-tools-')
        self.root = Path(self.tmp.name)
        self.install = self.root / 'playable'
        self.db = self.install / 'runtime/data/opendaoc.sqlite3.db'
        self.db.parent.mkdir(parents=True)
        with sqlite3.connect(self.db) as c:
            c.executescript("""CREATE TABLE ClassXSpecialization(ClassID INT,SpecKeyName TEXT);
            CREATE TABLE Mob(Mob_ID TEXT,ClassType TEXT);
            CREATE TABLE ServerProperty(Key TEXT,Value TEXT);
            CREATE TABLE Character(Name TEXT,XP INT);
            INSERT INTO Character VALUES('Character with preserved XP',987654321);
            INSERT INTO ServerProperty VALUES('enable_sluaghbinder','False'),('pve_rate','10');
            INSERT INTO Mob VALUES('sluaghbinder_trainer_tir_na_nog','DOL.GS.Trainer.SluaghbinderTrainer');""")
            c.executemany('INSERT INTO ClassXSpecialization VALUES(63,?)', [(str(i),) for i in range(9)])
        self.client = self.install / 'runtime/client-opendaoc/app/game.dll'
        self.client.parent.mkdir(parents=True)
        if CLIENT:
            shutil.copyfile(CLIENT, self.client)
        else:
            self.client.write_bytes(b'unverified client fixture')
        (self.install / 'runtime/server').mkdir(parents=True)
        self.config = self.install / 'runtime/server/serverconfig.xml'
        self.config.write_bytes(b'preserve saved configuration')
        self.world = self.install / 'runtime/server/world.nav'
        self.world.write_bytes(b'preserve installed world')

    def tearDown(self):
        self.tmp.cleanup()

    def sql(self, statement):
        with sqlite3.connect(self.db) as c:
            c.executescript(statement)

    def state(self):
        with sqlite3.connect(self.db) as c:
            return {name: c.execute('SELECT * FROM "'+name+'" ORDER BY rowid').fetchall()
                    for (name,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")}

    def ps(self, script, *args, prelude=None, ok=True):
        if os.environ.get('BEEZ_TEST_MOCK_CLIENT') == '1':
            # Windows CI tests the real winsqlite3 ABI with a tiny client stand-in.
            # Only its known test-byte hash is substituted; every other hash is real.
            mock_hash = hashlib.sha256(b'Beez CI client stand-in').hexdigest()
            prelude = ("function Get-FileHash { param($LiteralPath,$Path,$Algorithm) "
                "$p=$LiteralPath; if (!$p) {$p=$Path}; "
                "$h=Microsoft.PowerShell.Utility\\Get-FileHash -LiteralPath $p -Algorithm $Algorithm; "
                "if ($h.Hash -eq '"+mock_hash+"') {[pscustomobject]@{Hash='e1d471bb19108610ab9c8ca77dd41af40afe716685b03f4cdeda88c05678463b';Path=$p;Algorithm='SHA256'}} else {$h} }; "
                + (prelude or ''))
        if prelude is None:
            cmd = [PS, '-NoProfile', '-File', str(TOOLS / script), *map(str, args)]
        else:
            def quote(s): return "'" + str(s).replace("'", "''") + "'"
            call = '& '+quote(TOOLS / script)+' '+ ' '.join(quote(a) if not str(a).startswith('-') else str(a) for a in args)
            cmd = [PS, '-NoProfile', '-Command', prelude+'; '+call]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if ok: self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
        else: self.assertNotEqual(p.returncode, 0, p.stdout+p.stderr)
        return p.stdout+p.stderr

    def enable(self, *args, **kw):
        if not CLIENT: self.skipTest('Set BEEZ_TEST_CLIENT to the verified public 0.35b client')
        return self.ps('Enable-Sluaghbinder.ps1', '-InstallRoot', self.install, *args, **kw)

    def blocked(self):
        before = self.state()
        self.assertIn('BLOCKED', self.enable(ok=False))
        self.assertEqual(self.state(), before)

    def test_enable_only_one_setting_and_idempotence(self):
        before = self.state()
        client = self.client.read_bytes()
        self.assertIn('ENABLED:', self.enable())
        after = self.state()
        self.assertEqual({k:v for k,v in before.items() if k!='ServerProperty'},
                         {k:v for k,v in after.items() if k!='ServerProperty'})
        self.assertEqual(after['ServerProperty'], [('enable_sluaghbinder','True'), ('pve_rate','10')])
        self.assertEqual(self.client.read_bytes(), client)
        db_hash = hashlib.sha256(self.db.read_bytes()).hexdigest()
        self.assertIn('ALREADY ENABLED', self.enable())
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), db_hash)

    def test_check_only(self):
        before = self.state()
        self.assertIn('READY:', self.enable('-CheckOnly'))
        self.assertEqual(self.state(), before)

    def test_eight_specs(self):
        self.sql('DELETE FROM ClassXSpecialization WHERE rowid=1'); self.blocked()

    def test_ten_specs(self):
        self.sql("INSERT INTO ClassXSpecialization VALUES(63,'extra')"); self.blocked()

    def test_missing_trainer(self):
        self.sql('DELETE FROM Mob'); self.blocked()

    def test_wrong_trainer_type(self):
        self.sql("UPDATE Mob SET ClassType='DOL.GS.GameNPC'"); self.blocked()

    def test_missing_setting(self):
        self.sql("DELETE FROM ServerProperty WHERE Key='enable_sluaghbinder'"); self.blocked()

    def test_duplicate_setting(self):
        self.sql("INSERT INTO ServerProperty VALUES('enable_sluaghbinder','False')"); self.blocked()

    def test_custom_trigger(self):
        self.sql("CREATE TRIGGER change_other AFTER UPDATE ON ServerProperty BEGIN UPDATE Character SET XP=0; END;")
        self.blocked()

    def test_unknown_client(self):
        self.client.write_bytes(b'unknown build'); self.blocked()

    def test_missing_database(self):
        self.db.unlink()
        self.assertIn('BLOCKED', self.enable(ok=False)); self.assertFalse(self.db.exists())

    def test_locked_database(self):
        with sqlite3.connect(self.db) as c:
            c.execute('BEGIN IMMEDIATE')
            self.assertIn('locked', self.enable(ok=False))
        self.assertEqual(self.state()['ServerProperty'][0][1], 'False')

    def test_running_process(self):
        before = self.state()
        prelude = "function Get-Process { [pscustomobject]@{Name='CoreServer'} }; function Get-CimInstance { [pscustomobject]@{Name='CoreServer.exe';CommandLine='CoreServer.exe'} }"
        self.assertIn('BLOCKED', self.enable(ok=False, prelude=prelude))
        self.assertEqual(self.state(), before)

    def package(self, mutate=None, extra_zip=None):
        self.asset_dir = self.root / 'release'
        self.asset_dir.mkdir()
        package = self.root / 'package'
        package.mkdir()
        self.commit = 'a' * 40
        payload = package / 'payload/server/GameServer.dll'
        payload.parent.mkdir(parents=True)
        payload.write_bytes(b'new verified server binary fixture')
        launch = package / 'payload/launcher/OfflineDAoC.dll'
        launch.parent.mkdir(parents=True)
        launch.write_bytes(b'new launcher binary fixture')
        rows = []
        for component, src, targets in [
            ('server',payload,['runtime/server/GameServer.dll','runtime/server/lib/GameServer.dll','runtime/server/win-x64/GameServer.dll']),
            ('launcher',launch,['runtime/OfflineDAoC.dll'])]:
            for target in targets:
                rows.append(dict(Component=component, Source=src.relative_to(package).as_posix(), Target=target,
                                 SHA256=hashlib.sha256(src.read_bytes()).hexdigest(), Bytes=src.stat().st_size))
                target_path = self.install / target
                target_path.parent.mkdir(parents=True,exist_ok=True)
                target_path.write_bytes(b'original saved binary')
        info = dict(repository='BeezKneezItem9/OfflineDAoC', targetBranch='beez-online-six-features',
                    commit=self.commit,rid='win-x64',configuration='Release',selfContained=True,replacementCount=len(rows))
        for name in ['Deploy-TestBuild.ps1','Rollback-TestBuild.ps1']:
            shutil.copyfile(TOOLS / 'tests/fixtures' / name, package / name)
        if mutate: mutate(package,rows,info)
        (package / 'BUILD-INFO.json').write_text(json.dumps(info))
        with (package / 'REPLACEMENTS.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=['Component','Source','Target','SHA256','Bytes'])
            writer.writeheader();writer.writerows(rows)
        (package / 'SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.relative_to(package).as_posix()+'\n'
             for f in sorted(package.rglob('*')) if f.is_file() and f.name!='SHA256SUMS'))
        self.filename='beez-online-aaaaaaa-win-x64-release.zip'
        zip_path=self.asset_dir/self.filename
        with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
            for f in package.rglob('*'):
                if f.is_file():z.write(f,f.relative_to(package).as_posix())
            if extra_zip:extra_zip(z)
        (self.asset_dir/(self.filename+'.sha256')).write_text(hashlib.sha256(zip_path.read_bytes()).hexdigest()+'  '+self.filename+'\n')
        release=dict(tag_name='beez-test-aaaaaaa',draft=False,prerelease=True,published_at='2026-10-11T00:00:00Z',
            assets=[dict(name=n,browser_download_url='https://github.com/BeezKneezItem9/OfflineDAoC/releases/download/beez-test-aaaaaaa/'+n)
                    for n in [self.filename,self.filename+'.sha256']])
        (self.asset_dir/'releases.json').write_text(json.dumps([release]))
        return package

    def update(self, *args, **kwargs):
        ad=str(self.asset_dir).replace("'", "''")
        extra=kwargs.pop('prelude','')
        prelude="""function Invoke-RestMethod { param($Uri,$Headers) Get-Content -Raw '%s/releases.json' | ConvertFrom-Json }
        function Invoke-WebRequest { param([switch]$UseBasicParsing,$Uri,$OutFile) [IO.File]::Copy((Join-Path '%s' ([IO.Path]::GetFileName($Uri))),$OutFile) }
        """ % (ad,ad)
        if '-CacheRoot' in args:
            at=args.index('-CacheRoot'); cache=args[at+1]; args=args[:at]+args[at+2:]
        else: cache=self.root/'cache'
        return self.ps('Update-Beez.ps1','-InstallRoot',self.install,'-CacheRoot',cache,*args,prelude=prelude+extra,**kwargs)

    def persistent_bytes(self):
        return {str(f):f.read_bytes() for f in [self.db,self.client,self.config,self.world]}

    def test_update_applies_and_preserves_every_persistent_file(self):
        self.package(); before=self.persistent_bytes()
        self.assertIn('UPDATED:',self.update('-Apply'))
        self.assertEqual(self.persistent_bytes(),before)
        self.assertEqual((self.install/'runtime/OfflineDAoC.dll').read_bytes(),b'original saved binary')
        self.assertEqual((self.install/'runtime/server/GameServer.dll').read_bytes(),b'new verified server binary fixture')
        self.assertIn('ALREADY INSTALLED:',self.update('-Apply'))
        self.assertEqual(len(list((self.root/'cache/backups').glob('*'))),1)

    def test_update_preview_changes_no_playable_files(self):
        self.package();before={str(f):f.read_bytes() for f in self.install.rglob('*') if f.is_file()}
        self.assertIn('READY:',self.update())
        self.assertEqual({str(f):f.read_bytes() for f in self.install.rglob('*') if f.is_file()},before)

    def test_update_includes_launcher_explicitly(self):
        self.package();before=self.persistent_bytes()
        self.assertIn('UPDATED:',self.update('-Apply','-IncludeLauncher'))
        self.assertEqual((self.install/'runtime/OfflineDAoC.dll').read_bytes(),b'new launcher binary fixture')
        self.assertEqual(self.persistent_bytes(),before)

    def test_update_bad_archive_checksum(self):
        self.package();before=self.persistent_bytes()
        (self.asset_dir/(self.filename+'.sha256')).write_text('0'*64+'  '+self.filename)
        self.assertIn('checksum mismatch',self.update('-Apply',ok=False))
        self.assertEqual(self.persistent_bytes(),before)
        self.assertEqual((self.install/'runtime/server/GameServer.dll').read_bytes(),b'original saved binary')

    def test_update_bad_package_hash(self):
        def extra(z):z.writestr('unhashed.txt','unexpected')
        self.package(extra_zip=extra)
        self.assertIn('Unhashed package',self.update('-Apply',ok=False))

    def test_update_incompatible_metadata(self):
        self.package(mutate=lambda p,r,i:i.update(rid='linux-x64'))
        self.assertIn('incompatible',self.update('-Apply',ok=False))

    def test_update_rejects_persistent_target(self):
        self.package(mutate=lambda p,r,i:r[0].update(Target='runtime/data/opendaoc.sqlite3.db'))
        before=self.persistent_bytes()
        self.assertIn('Unexpected server destination',self.update('-Apply',ok=False))
        self.assertEqual(self.persistent_bytes(),before)

    def test_update_rejects_client_target(self):
        self.package(mutate=lambda p,r,i:r[-1].update(Target='runtime/client-opendaoc/app/game.dll'))
        before=self.persistent_bytes()
        self.assertIn('Unexpected launcher destination',self.update('-Apply',ok=False))
        self.assertEqual(self.persistent_bytes(),before)

    def test_update_rejects_manifest_traversal(self):
        self.package(mutate=lambda p,r,i:r[0].update(Target='../outside.dll'))
        self.assertIn('Unsafe package path',self.update('-Apply',ok=False))

    def test_update_rejects_zip_traversal(self):
        self.package(extra_zip=lambda z:z.writestr('../outside.dll','bad'))
        self.assertIn('Unsafe package path',self.update('-Apply',ok=False))
        self.assertFalse((self.root/'outside.dll').exists())

    def test_update_rejects_duplicate_targets(self):
        self.package(mutate=lambda p,r,i:r[1].update(Target=r[0]['Target']))
        self.assertIn('Duplicate/case-colliding replacement',self.update('-Apply',ok=False))

    def test_update_failure_automatically_reuses_rollback(self):
        self.package();before=self.persistent_bytes()
        original={f:f.read_bytes() for f in self.install.rglob('*.dll')}
        hook="""$global:beezFailureUsed=$false
        function Copy-Item { param($LiteralPath,$Destination,[switch]$Force)
        if (!$global:beezFailureUsed -and $LiteralPath -like '*package*' -and $Destination.Replace('\\','/') -like '*playable/runtime/server/lib/GameServer.dll') {
          $global:beezFailureUsed=$true; throw 'injected copy failure'
        }
        Microsoft.PowerShell.Management\Copy-Item -LiteralPath $LiteralPath -Destination $Destination -Force:$Force }
        """
        self.assertIn('original binaries restored',self.update('-Apply',ok=False,prelude=hook))
        self.assertEqual(self.persistent_bytes(),before)
        self.assertEqual({f:f.read_bytes() for f in original},original)

    def test_update_explicit_enable_uses_same_logic(self):
        if not CLIENT:self.skipTest('verified public client required')
        self.package();before=self.state()
        self.assertIn('ENABLED:',self.update('-Apply','-EnableSluaghbinder'))
        after=self.state()
        self.assertEqual(after['ServerProperty'][0][1],'True')
        self.assertEqual(before['Character'],after['Character'])
        self.assertIn('ALREADY ENABLED:',self.update('-Apply','-EnableSluaghbinder'))

    def test_update_blocked_enable_does_not_deploy(self):
        if not CLIENT:self.skipTest('verified public client required')
        self.package();self.sql('DELETE FROM Mob')
        self.assertIn('BLOCKED',self.update('-Apply','-EnableSluaghbinder',ok=False))
        self.assertEqual((self.install/'runtime/server/GameServer.dll').read_bytes(),b'original saved binary')

    def test_update_api_error_reports_failure(self):
        self.package()
        self.assertIn('network unavailable',self.update('-Apply',ok=False,prelude="function Invoke-RestMethod { throw 'network unavailable' }"))

    def test_update_skips_newer_non_beez_release(self):
        self.package()
        f=self.asset_dir/'releases.json';r=json.loads(f.read_text())
        r.insert(0,dict(tag_name='v0.99',draft=False,published_at='2027-01-01',assets=[]))
        f.write_text(json.dumps(r))
        self.assertIn('UPDATED:',self.update('-Apply'))


    def test_update_bad_replacement_hash(self):
        self.package(mutate=lambda p,r,i:r[0].update(SHA256='0'*64))
        self.assertIn('Replacement hash/size mismatch',self.update('-Apply',ok=False))

    def test_update_process_running(self):
        self.package();before=self.persistent_bytes()
        hook="function Get-Process { [pscustomobject]@{Name='CoreServer'} }; function Get-CimInstance { [pscustomobject]@{Name='CoreServer.exe';CommandLine='CoreServer.exe'} }"
        self.assertIn('Close the server',self.update('-Apply',ok=False,prelude=hook))
        self.assertEqual(self.persistent_bytes(),before)

    def test_update_no_compatible_assets(self):
        self.package();f=self.asset_dir/'releases.json';r=json.loads(f.read_text());r[0]['assets']=[];f.write_text(json.dumps(r))
        self.assertIn('No compatible Beez',self.update('-Apply',ok=False))

    def test_update_cache_inside_playable_blocked(self):
        self.package()
        self.assertIn('outside the playable',self.update('-CacheRoot',self.install/'cache','-Apply',ok=False))


if __name__ == '__main__':
    unittest.main()
