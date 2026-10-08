"""Goal 10: apply dataquest_preview.json + classic-quests.preview.json to the game database (server must be stopped).
Backs up the DB first, inserts DataQuest (ids 20000+) and ItemTemplate (cq_*) rows in one transaction, asserts the
row counts, and writes runtime/server/classic-quests.json. Re-running replaces the previous classic quest rows."""
import json, os, shutil, sqlite3, subprocess, sys, uuid, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:/OfflineDAoC\runtime"
DB = os.path.join(ROOT, "data", "opendaoc.sqlite3.db")
CONFIG_OUT = os.path.join(ROOT, "server", "classic-quests.json")

running = subprocess.run(["tasklist"], capture_output=True, text=True).stdout.lower()
if "coreserver" in running:
    sys.exit("CoreServer is running; stop the server first.")

prev = json.load(open(os.path.join(HERE, "dataquest_preview.json"), encoding="utf-8"))
config = json.load(open(os.path.join(HERE, "classic-quests.preview.json"), encoding="utf-8"))
rows, items = prev["rows"], list(prev["item_rows"])
# Reward equipment and one-time-drop items built from the period item pages (build_reward_items.py).
reward_path = os.path.join(HERE, "reward_item_rows.json")
if os.path.exists(reward_path):
    built = {it["Id_nb"].lower(): it for it in json.load(open(reward_path, encoding="utf-8"))}
    # a quest item that is real equipment on its period page is loaded with its stats instead of as a plain token
    items = [built.pop(it["Id_nb"].lower(), it) for it in items] + list(built.values())

stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
backup = os.path.join(ROOT, "data", f"opendaoc.sqlite3.before-classic-quests-{stamp}.db")
shutil.copy2(DB, backup)
print("backup", backup)

now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
con = sqlite3.connect(DB)
cur = con.cursor()
dq_cols = [r[1] for r in cur.execute("pragma table_info(DataQuest)")]
it_cols = [r[1] for r in cur.execute("pragma table_info(ItemTemplate)")]
before_dq = cur.execute("select count(*) from DataQuest").fetchone()[0]
before_it = cur.execute("select count(*) from ItemTemplate").fetchone()[0]
old_dq = cur.execute("select count(*) from DataQuest where ID >= 20000").fetchone()[0]
old_it = cur.execute("select count(*) from ItemTemplate where PackageID = 'ClassicQuest'").fetchone()[0]
try:
    cur.execute("begin")
    cur.execute("delete from DataQuest where ID >= 20000")
    cur.execute("delete from ItemTemplate where PackageID = 'ClassicQuest'")
    for r in rows:
        values = {k: v for k, v in r.items() if k in dq_cols}
        values["LastTimeRowUpdated"] = now
        cols = list(values)
        cur.execute(f"insert into DataQuest ({','.join(cols)}) values ({','.join('?' * len(cols))})", [values[c] for c in cols])
    for it in items:
        values = {k: v for k, v in it.items() if k in it_cols}
        values["LastTimeRowUpdated"] = now
        values["ItemTemplate_ID"] = str(uuid.uuid4())
        values.setdefault("AllowedClasses", "0")
        cols = list(values)
        cur.execute(f"insert into ItemTemplate ({','.join(cols)}) values ({','.join('?' * len(cols))})", [values[c] for c in cols])
    after_dq = cur.execute("select count(*) from DataQuest").fetchone()[0]
    after_it = cur.execute("select count(*) from ItemTemplate").fetchone()[0]
    assert after_dq == before_dq - old_dq + len(rows), (before_dq, old_dq, after_dq, len(rows))
    assert after_it == before_it - old_it + len(items), (before_it, old_it, after_it, len(items))
    con.commit()
except Exception:
    con.rollback()
    raise
finally:
    con.close()
json.dump(config, open(CONFIG_OUT, "w", encoding="utf-8"), indent=1)
print(f"DataQuest {before_dq} -> {after_dq} (+{len(rows)}, replaced {old_dq}); ItemTemplate {before_it} -> {after_it} "
      f"(+{len(items)}, replaced {old_it}); wrote {CONFIG_OUT}")
