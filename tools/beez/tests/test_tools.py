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

if __name__ == '__main__':
    unittest.main()
