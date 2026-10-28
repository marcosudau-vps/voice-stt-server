#!/usr/bin/env python3
"""Offline diagnostics for cleaned Kroko catalog metadata (no downloads)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from VoiceSTT.kroko.catalog import CatalogValidationError, create_download_plan, load_catalog
from VoiceSTT.kroko.models import KrokoModelError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("summary", "languages", "validate"):
        commands.add_parser(name)
    listing = commands.add_parser("list")
    listing.add_argument("--language")
    listing.add_argument("--edition", choices=("Community", "Pro"))
    listing.add_argument("--chunk", type=int)
    listing.add_argument("--size", choices=("S", "M", "L"))
    listing.add_argument("--streaming", choices=("yes", "no"))
    for name in ("inspect", "plan"):
        commands.add_parser(name).add_argument("--model-id", required=True)
    args = parser.parse_args(argv)
    try:
        catalog = load_catalog(args.catalog)
        if args.command == "summary":
            result = catalog.summary()
        elif args.command == "languages":
            result = catalog.languages
        elif args.command == "validate":
            result = {"valid": True, **catalog.summary()}
        elif args.command == "list":
            result = [entry.public_dict() for entry in catalog.filter(
                language=args.language, edition=args.edition, chunk=args.chunk,
                size=args.size, streaming=(None if args.streaming is None else args.streaming == "yes"),
            )]
        else:
            entry = catalog.get(args.model_id)
            if entry is None:
                print(json.dumps({"error": "model_not_found"}), file=sys.stderr)
                return 1
            result = entry.public_dict() if args.command == "inspect" else create_download_plan(entry).public_dict()
    except CatalogValidationError as exc:
        print(json.dumps({"valid": False, "diagnostics": [
            {"index": d.index, "code": d.code, "message": d.message} for d in exc.diagnostics
        ]}), file=sys.stderr)
        return 2
    except (KrokoModelError, OSError, ValueError):
        print(json.dumps({"error": "manifest_unavailable_or_invalid"}), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
