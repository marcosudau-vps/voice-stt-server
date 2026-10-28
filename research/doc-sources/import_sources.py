#!/usr/bin/env python3
"""Import verified historical sources into the temporary Jules research branch.

This never creates a commit or pushes. Check that sources are safe to publish
because the GitHub repository and all branches are public.
"""
import argparse
import csv
import hashlib
import io
import sys
import zipfile
from pathlib import Path, PurePosixPath

EXPECTED_SHA256 = "962d8ce569986d55bbc9fe0ff4fd9d6d287bba528b3ee42aee0e87817e8e8278"
BASE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    data = args.archive.read_bytes()
    got = hashlib.sha256(data).hexdigest()
    if got != EXPECTED_SHA256:
        parser.error(f"Archive SHA-256 mismatch: {got}")

    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)):
            parser.error("Duplicate ZIP member names")
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or str(path) != name:
                parser.error(f"Unsafe archive path: {name}")
            if not (name.startswith("sources/") or name in {
                "SOURCE_INDEX.csv", "AP_HISTORY_INDEX.csv",
                "README_VOR_COMMIT_PRUEFEN.md"
            }):
                parser.error(f"Unexpected archive member: {name}")
        index = bundle.read("SOURCE_INDEX.csv").decode("utf-8-sig")
        for row in csv.DictReader(io.StringIO(index)):
            name = row["bundle_path"]
            content = bundle.read(name)
            if hashlib.sha256(content).hexdigest() != row["sha256"]:
                parser.error(f"SHA-256 mismatch: {name}")
            if len(content) != int(row["bytes"]):
                parser.error(f"Size mismatch: {name}")
        existing = [str(BASE / name) for name in names if (BASE / name).exists()]
        if existing:
            parser.error("Refusing to overwrite existing sources: " + ", ".join(existing))
        for name in names:
            if name.endswith("/"):
                continue
            target = BASE.joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bundle.read(name))
    print(f"Imported {len(names)} source entries.")
    print("Review files for confidential information before committing or pushing.")


if __name__ == "__main__":
    sys.exit(main())
