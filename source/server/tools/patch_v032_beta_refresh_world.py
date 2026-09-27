#!/usr/bin/env python3
"""Reproduce the narrow v0.32 beta-refresh world-data delta on a clean copy.

This is for source users rebuilding the release. The playable update already
contains these rows. Pass a disposable clean v0.32 SQLite database, never a
running server's database. Without --apply the tool only validates its input.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
from pathlib import Path


ORB_SOURCE = "381ccf94-bb14-4c58-a24d-4d4e5f9f2ff9"
SNEEZER_SOURCE = "100024390"
CNIOGCRAG_MOB = "100027065"
CNIOGCRAG_TEMPLATE = 60162463

# (Mob_ID, X, Y, Z, Heading). Names/levels/loot/AI/respawn are inherited
# unchanged from the corresponding preexisting clean v0.32 source row.
ORBS = (
    ("1e5cdddd-55ae-57d0-9ee1-f182425d27b4", 381803, 499988, 5200, 256),
    ("2a7ac6af-c772-5c68-b7fa-a9d5745401b8", 381901, 500258, 5200, 512),
    ("4f391ead-15fd-573f-82d4-eee33ff2df70", 381554, 500672, 5200, 1536),
    ("5446524f-04b5-57b6-a2ec-92255f59f707", 381271, 500622, 5200, 2048),
    ("79f199d8-6047-5015-945a-67150f444be9", 381803, 500528, 5200, 1024),
    ("9078a393-c577-581f-be57-da6f52815f55", 381086, 500114, 5200, 3072),
    ("91c81746-117c-5ff6-9e2b-da9c4f6b7771", 381271, 499894, 5200, 3584),
    ("a343ea70-206d-5a3c-bb51-9b8b581f85fb", 381554, 499844, 5200, 0),
    ("c80736b4-e993-5138-b3e7-3c13c0160331", 381086, 500402, 5200, 2560),
)
SNEEZERS = (
    ("sneezer-domnann-20260926-01", 417650, 408050, 4378, 1921),
    ("sneezer-domnann-20260926-02", 418300, 408100, 4379, 1921),
    ("sneezer-domnann-20260926-03", 417520, 408420, 4378, 1921),
    ("sneezer-domnann-20260926-04", 418420, 408410, 4382, 1921),
    ("sneezer-domnann-20260926-05", 417700, 408730, 4382, 1921),
    ("sneezer-domnann-20260926-06", 418150, 408800, 4387, 1921),
    ("sneezer-domnann-20260926-07", 418450, 408850, 4391, 1921),
)


def one(db: sqlite3.Connection, sql: str, values: tuple):
    rows = db.execute(sql, values).fetchall()
    if len(rows) != 1:
        raise RuntimeError(f"Expected one clean v0.32 source row, found {len(rows)}: {values}")
    return rows[0]


def validate_clean_base(db: sqlite3.Connection) -> None:
    # Never run a source-data migration against a player's progress database.
    for table in ("Account", "DOLCharacters", "offline_world_bots", "bot_profiles"):
        if db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]:
            raise RuntimeError(f"Refusing to modify a database containing {table} progress")
    for mob_id, name, region, level, model in (
        (ORB_SOURCE, "empyrean orb", 200, 10, 1391),
        (SNEEZER_SOURCE, "sneezer", 181, 14, 906),
    ):
        row = one(db, 'SELECT * FROM Mob WHERE Mob_ID=?', (mob_id,))
        if (row["Name"], row["Region"], row["Level"], row["Model"]) != (name, region, level, model):
            raise RuntimeError(f"Unexpected source monster: {mob_id}")
    mob = one(db, 'SELECT * FROM Mob WHERE Mob_ID=?', (CNIOGCRAG_MOB,))
    if (mob["Name"], mob["Region"], mob["Level"], mob["Model"]) not in (
        ("insidious cniogcrag", 181, 18, 666),
        ("insidious cniogcrag", 181, 18, 769),
    ):
        raise RuntimeError("Unexpected cniogcrag spawn")
    template = one(db, 'SELECT * FROM NpcTemplate WHERE TemplateId=?', (CNIOGCRAG_TEMPLATE,))
    if template["Model"] not in ("769;666", "769"):
        raise RuntimeError("Unexpected cniogcrag template model")


def expected_clone(source: sqlite3.Row, spec: tuple) -> dict:
    mob_id, x, y, z, heading = spec
    row = dict(source)
    row.update(Mob_ID=mob_id, X=x, Y=y, Z=z, Heading=heading)
    return row


def upsert_checked_clone(db: sqlite3.Connection, row: dict) -> bool:
    existing = db.execute('SELECT * FROM Mob WHERE Mob_ID=?', (row["Mob_ID"],)).fetchone()
    if existing is not None:
        if dict(existing) != row:
            raise RuntimeError(f"Existing spawn differs from the release row: {row['Mob_ID']}")
        return False
    columns = list(row)
    names = ",".join('"' + name + '"' for name in columns)
    placeholders = ",".join("?" for _ in columns)
    db.execute(f'INSERT INTO Mob ({names}) VALUES ({placeholders})', tuple(row.values()))
    return True


def verify_final(db: sqlite3.Connection) -> None:
    for source_id, specs in ((ORB_SOURCE, ORBS), (SNEEZER_SOURCE, SNEEZERS)):
        source = one(db, 'SELECT * FROM Mob WHERE Mob_ID=?', (source_id,))
        for spec in specs:
            actual = one(db, 'SELECT * FROM Mob WHERE Mob_ID=?', (spec[0],))
            if dict(actual) != expected_clone(source, spec):
                raise RuntimeError(f"Spawn contents do not match release: {spec[0]}")
    mob = one(db, 'SELECT * FROM Mob WHERE Mob_ID=?', (CNIOGCRAG_MOB,))
    template = one(db, 'SELECT * FROM NpcTemplate WHERE TemplateId=?', (CNIOGCRAG_TEMPLATE,))
    if mob["Model"] != 769 or template["Model"] != "769":
        raise RuntimeError("Cniogcrag visible-model repair is incomplete")
    if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise RuntimeError("SQLite quick_check failed")


def apply(db: sqlite3.Connection) -> int:
    db.execute("BEGIN IMMEDIATE")
    try:
        validate_clean_base(db)
        changes = 0
        for source_id, specs in ((ORB_SOURCE, ORBS), (SNEEZER_SOURCE, SNEEZERS)):
            source = one(db, 'SELECT * FROM Mob WHERE Mob_ID=?', (source_id,))
            for spec in specs:
                changes += upsert_checked_clone(db, expected_clone(source, spec))
        changes += db.execute(
            'UPDATE Mob SET Model=769 WHERE Mob_ID=? AND Model=666',
            (CNIOGCRAG_MOB,),
        ).rowcount
        changes += db.execute(
            'UPDATE NpcTemplate SET Model=? WHERE TemplateId=? AND Model=?',
            ("769", CNIOGCRAG_TEMPLATE, "769;666"),
        ).rowcount
        verify_final(db)
        db.commit()
        return changes
    except Exception:
        db.rollback()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True, help="disposable clean v0.32 SQLite DB")
    parser.add_argument("--apply", action="store_true", help="back up and apply the narrow delta")
    args = parser.parse_args()
    path = args.database.resolve(strict=True)
    if not path.is_file():
        raise SystemExit("Database must be a file")
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    try:
        validate_clean_base(db)
        if not args.apply:
            print("Clean v0.32 source rows verified; no changes made. Use --apply on a disposable copy.")
            return
        backup = path.with_name(path.name + ".before-v032-beta-refresh-" +
                                dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S") + ".bak")
        with sqlite3.connect(backup) as copy:
            db.backup(copy)
        changed = apply(db)
        print(f"Applied {changed} world-data row changes; verified SQLite quick_check. Backup: {backup}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
