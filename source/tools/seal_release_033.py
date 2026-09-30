"""Seal an assembled 0.33 package into verified, split release assets.

    python seal_release_033.py --package <staging>/OfflineDAoC-v0.33b --out <assets folder>

Writes PACKAGE MANIFEST.sha256 into the package, zips it (root folder OfflineDAoC-v0.33b/),
re-reads every zip entry against the manifest, splits the archive into parts below GitHub's 2 GB
limit, and writes the download manifests Get-OfflineDAoC.ps1 reads:
  <out>/v0.33b/  OfflineDAoC-v0.33b.zip.001… , download-manifest.json, SHA256SUMS.txt
  <out>/v0.33/   download-manifest.json (edition swap of the same parts), SHA256SUMS.txt
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

PART_BYTES = 1_900_000_000
SEVEN_ZIP = Path(r"C:\Program Files\7-Zip\7z.exe")
EDITION_FOLDER = "0.33-no-custom-class"
EDITION_FILES = ("runtime\\data\\opendaoc.sqlite3.db", "runtime\\client-opendaoc\\app\\game.dll")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    package, out = args.package.resolve(), args.out.resolve()
    root = package.name
    assert root == "OfflineDAoC-v0.33b", "the package folder must be named OfflineDAoC-v0.33b"
    if out.exists():
        raise SystemExit(f"{out} exists; refusing to overwrite release assets")
    (out / "v0.33b").mkdir(parents=True)
    (out / "v0.33").mkdir(parents=True)

    print("Hashing every package file...", flush=True)
    manifest_file = package / "PACKAGE MANIFEST.sha256"
    files = sorted(p for p in package.rglob("*") if p.is_file() and p != manifest_file)
    hashes = {p.relative_to(package).as_posix(): sha(p) for p in files}
    manifest_file.write_text("".join(f"{h}  {name}\n" for name, h in hashes.items()), encoding="utf-8")
    total = sum(p.stat().st_size for p in files)
    print(f"{len(files)} files, {total / 1024**3:.2f} GiB", flush=True)

    archive = out / f"{root}.zip"
    print("Zipping...", flush=True)
    subprocess.run([str(SEVEN_ZIP), "a", "-tzip", "-mx=5", "-mmt=on", "-bso0", "-bsp0", str(archive), root],
                   cwd=package.parent, check=True)

    print("Verifying every zip entry against the manifest...", flush=True)
    with zipfile.ZipFile(archive) as zf:
        entries = [i for i in zf.infolist() if not i.is_dir()]
        assert all(i.filename.startswith(root + "/") and "\\" not in i.filename for i in zf.infolist())
        seen = {}
        for item in entries:
            digest = hashlib.sha256()
            with zf.open(item) as stream:
                for block in iter(lambda: stream.read(1 << 20), b""):
                    digest.update(block)
            seen[item.filename[len(root) + 1:]] = digest.hexdigest()
    expected = dict(hashes)
    expected["PACKAGE MANIFEST.sha256"] = sha(manifest_file)
    assert seen == expected, "zip contents do not match the package manifest"
    archive_sha = sha(archive)

    print("Splitting into parts...", flush=True)
    parts = []
    with archive.open("rb") as source:
        index = 1
        while True:
            block = source.read(PART_BYTES)
            if not block:
                break
            name = f"{root}.zip.{index:03d}"
            (out / "v0.33b" / name).write_bytes(block)
            parts.append({"Name": name, "Bytes": len(block), "SHA256": hashlib.sha256(block).hexdigest()})
            index += 1
    archive.unlink()

    edition_root = package / "editions" / EDITION_FOLDER
    full = {"Version": "0.33b", "Title": 'Offline DAoC 0.33b "Claude Takeover"', "RootFolder": root,
            "ArchiveSHA256": archive_sha, "ArchiveBytes": sum(p["Bytes"] for p in parts), "Parts": parts}
    edition = {"Version": "0.33", "Title": 'Offline DAoC 0.33 "Claude Takeover" (no custom class)', "Mode": "edition",
               "BaseVersion": "0.33b", "EditionFolder": EDITION_FOLDER,
               "EditionFiles": [{"Path": path, "SHA256": sha(edition_root / path.replace("\\", "/"))} for path in EDITION_FILES]}
    (out / "v0.33b/download-manifest.json").write_text(json.dumps(full, indent=2) + "\n", encoding="utf-8")
    (out / "v0.33/download-manifest.json").write_text(json.dumps(edition, indent=2) + "\n", encoding="utf-8")
    for folder in ("v0.33b", "v0.33"):
        lines = [f"{sha(p)}  {p.name}" for p in sorted((out / folder).iterdir()) if p.is_file() and p.name != "SHA256SUMS.txt"]
        if folder == "v0.33b":
            lines.append(f"{archive_sha}  {root}.zip (joined parts)")
        (out / folder / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"files": len(files) + 1, "unpacked_bytes": total, "archive_sha256": archive_sha,
                      "parts": [(p["Name"], p["Bytes"]) for p in parts]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
