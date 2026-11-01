"""Build the existing Beez binary-update contract; never package a world/client/save."""
import argparse
import csv
import hashlib
import io
import json
import pathlib
import re
import shutil
import struct
import zipfile

PREVIOUS_SHA = "c84eab380a394f493ad86fcd6f7b3ec5766b763ced59d730b98e93057806e942"
REPO = "BeezKneezItem9/OfflineDAoC"
ALLOWED = re.compile(r"(?:[^/]+\.(?:dll|exe|pdb)|[^/]+\.(?:deps|runtimeconfig)\.json|[a-z]{2,3}(?:-[A-Za-z]{2,4})?/[^/]+\.resources\.dll|lib/[^/]+\.dll)\Z")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser()
    for name in ("previous", "publish", "source", "commit", "out"):
        p.add_argument("--" + name, required=True)
    a = p.parse_args()
    assert re.fullmatch("[0-9a-f]{40}", a.commit)
    previous = pathlib.Path(a.previous).read_bytes()
    assert sha(previous) == PREVIOUS_SHA, "Previous package integrity failed"
    z = zipfile.ZipFile(io.BytesIO(previous))
    hashes = dict((name, digest) for digest, name in (line.split("  ", 1) for line in z.read("SHA256SUMS").decode().splitlines()))
    for name in z.namelist():
        if name != "SHA256SUMS":
            assert sha(z.read(name)) == hashes[name], "Previous package entry hash failed: " + name
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stage = out / "package"
    assert not stage.exists(), "Use an empty output directory"
    stage.mkdir()
    payload = {}
    for name in z.namelist():
        if name.startswith("payload/"):
            component, rel = name.split("/", 2)[1:]
            assert component in ("server", "launcher") and ALLOWED.fullmatch(rel), name
            payload[name] = z.read(name)
    published = pathlib.Path(a.publish)
    for f in published.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(published).as_posix()
        if rel.endswith("/SQLite.Interop.dll") and "win-x64" in rel:
            rel = "SQLite.Interop.dll"
        if ALLOWED.fullmatch(rel):
            payload["payload/server/" + rel] = f.read_bytes()
    for name in ("GameServer", "CoreServer", "CoreBase", "CoreDatabase"):
        b = payload["payload/server/" + name + ".dll"]
        assert a.commit.encode() in b or a.commit.encode("utf-16le") in b, "Wrong embedded source revision: " + name
        assert b == (published / (name + ".dll")).read_bytes()
    pe_checks = []
    for name in ("CoreServer.exe", "coreclr.dll", "clrjit.dll", "SQLite.Interop.dll", "lib/Detour.dll"):
        b = payload["payload/server/" + name]
        assert b[:2] == b"MZ"
        offset = struct.unpack_from("<I", b, 0x3C)[0]
        assert b[offset:offset + 4] == b"PE\0\0" and struct.unpack_from("<H", b, offset + 4)[0] == 0x8664, name
        pe_checks.append(dict(path="payload/server/" + name, machine="AMD64", sha256=sha(b)))
    for name, data in payload.items():
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    old_rows = list(csv.DictReader(io.StringIO(z.read("REPLACEMENTS.csv").decode("utf-8-sig"))))
    by_source = {}
    for row in old_rows:
        by_source.setdefault(row["Source"], []).append(row["Target"])
    rows = []
    for name, data in sorted(payload.items()):
        component, rel = name.split("/", 2)[1:]
        targets = by_source.get(name)
        if targets is None:
            targets = ["runtime/" + rel] if component == "launcher" else ["runtime/server/" + rel, "runtime/server/win-x64/" + rel]
        for target in targets:
            permitted = ["runtime/" + rel] if component == "launcher" else [prefix + rel for prefix in ("runtime/server/", "runtime/server/lib/", "runtime/server/win-x64/")]
            assert target in permitted
            rows.append(dict(Component=component, Source=name, Target=target, SHA256=sha(data), Bytes=len(data)))
    with (stage / "REPLACEMENTS.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Component", "Source", "Target", "SHA256", "Bytes"])
        writer.writeheader()
        writer.writerows(rows)
    for name in ("Deploy-TestBuild.ps1", "Rollback-TestBuild.ps1"):
        script = z.read(name).decode("utf-8-sig").replace("992b959fbf44a48497a4e5baae5a9937dce4a6c2", a.commit)
        (stage / name).write_text(script, encoding="utf-8-sig")
    source = pathlib.Path(a.source)
    shutil.copyfile(source / "docs/BEEZ-CAMPFIRES.md", stage / "CAMPFIRES.md")
    notes = """Beez Online — reusable campfire test update

Use /beezitems to obtain Beez's Campfire. New characters receive it automatically.
One reusable item, saved 10-minute cooldown; failed placement starts no cooldown.
Stationary fire: 10 minutes, 350-unit radius, pulses every 5 seconds.
Friendly players and owned pets retain independently timed buffs for 60 seconds after their last pulse.
Melee/styles: +15%, +20%, +25%, +30% at deployer levels 1, 15, 25, 40.
Health/power regeneration uses native aids; strongest campfire wins. Loot tables unchanged.
One item template is registered additively at startup; no database replacement or client patch.
Existing launcher and verified Windows native Detour are retained from release 992b959.
Stock campfire model 3460 and in-game behavior still require Windows gameplay acceptance.
No Sorcerer work-in-progress or uncommitted source is included.
"""
    (stage / "RELEASE-NOTES.md").write_text(notes, encoding="utf-8")
    (stage / "DEPLOYMENT.md").write_text("""# Binary update only
Close the game, launcher and server. Prefer the existing Update-Beez.cmd workflow.
For manual preview: .\\Deploy-TestBuild.ps1 -InstallRoot '<playable root>' -IncludeLauncher
Apply only after reviewing REPLACEMENTS.csv, with -Apply and an external -BackupRoot.
Only manifest-listed server/launcher binaries are replaced. Never copy this package over the entire installation.
Database, accounts, characters, client, configuration, world content and navmeshes are excluded.
The included established Rollback-TestBuild.ps1 accepts the reported BackupRoot if needed.
No script starts or stops the game/server. See CAMPFIRES.md for in-game acceptance checks.
""", encoding="utf-8")
    config = json.loads((published / "CoreServer.runtimeconfig.json").read_text())
    info = dict(repository=REPO, targetBranch="beez-online-six-features", commit=a.commit,
                rid="win-x64", configuration="Release", selfContained=True, replacementCount=len(rows),
                runtimeOptions=config["runtimeOptions"], peChecks=pe_checks,
                launcherSourceCommit="992b959fbf44a48497a4e5baae5a9937dce4a6c2",
                trackedSourceMatchesCommit=True, untrackedDiagnosticsExcludedFromProduction=True,
                packageType="Self-contained binary update for existing playable world/client",
                databaseMigrations=["Add missing beez_campfire item template at startup; preserve existing records"],
                newClientPatches=[], windowsGameplayVerified=False)
    (stage / "BUILD-INFO.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    sums = []
    for f in sorted(stage.rglob("*")):
        if f.is_file(): sums.append(sha(f.read_bytes()) + "  " + f.relative_to(stage).as_posix())
    (stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    filename = "beez-online-" + a.commit[:7] + "-win-x64-release.zip"
    archive = out / filename
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as package:
        for f in sorted(stage.rglob("*")):
            if f.is_file(): package.write(f, f.relative_to(stage).as_posix())
    with zipfile.ZipFile(archive) as package:
        for line in sums:
            digest, name = line.split("  ", 1)
            assert sha(package.read(name)) == digest
        assert len(package.namelist()) == len(sums) + 1
    (out / (filename + ".sha256")).write_text(sha(archive.read_bytes()) + "  " + filename + "\n", encoding="ascii")
    print(json.dumps(dict(zip=filename, sha256=sha(archive.read_bytes()), replacementCount=len(rows))))


if __name__ == "__main__":
    main()
