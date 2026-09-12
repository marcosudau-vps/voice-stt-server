"""Read-only prechecks and candidate verification for V1 publication.

All public writes remain in ``release-publish.yml`` behind the protected
``release`` environment.  This module classifies existing remote state as
ABSENT, MATCH, CONFLICT or UNKNOWN and verifies that downloaded candidate bytes
still match the qualified manifest/inventory before a write is attempted.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v1_kroko_release as kroko  # noqa: E402
import v1_release_manifest as manifest_tools  # noqa: E402

ABSENT = "ABSENT"
MATCH = "MATCH"
CONFLICT = "CONFLICT"
UNKNOWN = "UNKNOWN"
VERSION = "1.0.0"
TAG = "v1.0.0"


class PublicationPrecheckError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PublicationPrecheckError(f"could not read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PublicationPrecheckError(f"{path} is not a JSON object")
    return value


def verify_candidate_dir(candidate_dir: Path) -> dict[str, Any]:
    candidate_dir = Path(candidate_dir).resolve()
    manifest = _load_json(candidate_dir / "rc-manifest.json")
    try:
        manifest_tools.validate_candidate(manifest)
    except manifest_tools.CandidateManifestError as exc:
        raise PublicationPrecheckError(str(exc)) from exc

    python_identity = manifest["python"]
    for kind in ("wheel", "sdist"):
        identity = python_identity[kind]
        path = candidate_dir / "python" / identity["filename"]
        if not path.is_file():
            raise PublicationPrecheckError(f"candidate {kind} is missing: {path}")
        actual = manifest_tools.sha256_file(path)
        if actual != identity["sha256"]:
            raise PublicationPrecheckError(
                f"candidate {kind} hash mismatch: {actual} != {identity['sha256']}"
            )

    for variant in ("free", "pro"):
        try:
            verified = kroko.verify_artifact(variant, candidate_dir / "kroko" / variant)
        except kroko.ReleaseKrokoError as exc:
            raise PublicationPrecheckError(str(exc)) from exc
        if verified != manifest["kroko"][variant]:
            raise PublicationPrecheckError(
                f"candidate Kroko {variant} identity differs from rc-manifest"
            )

    inventory_path = candidate_dir / "sha256-inventory.json"
    inventory = _load_json(inventory_path)
    expected = manifest_tools.build_inventory(candidate_dir)
    # build_inventory excludes sha256-inventory.json itself, so the equality
    # below proves both content and completeness of every persisted candidate
    # file rather than checking only a hand-picked subset.
    if inventory != expected:
        raise PublicationPrecheckError("candidate SHA-256 inventory does not match downloaded bytes")
    return manifest


PyPIFetcher = Callable[[str], dict[str, Any] | None]


def _fetch_pypi(url: str) -> dict[str, Any] | None:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def inspect_pypi(
    manifest: dict[str, Any], *, fetch: PyPIFetcher = _fetch_pypi
) -> dict[str, Any]:
    python_identity = manifest["python"]
    project = python_identity["distribution"]
    version = python_identity["version"]
    expected = {
        python_identity["wheel"]["filename"]: python_identity["wheel"]["sha256"],
        python_identity["sdist"]["filename"]: python_identity["sdist"]["sha256"],
    }
    url = f"https://pypi.org/pypi/{project}/{version}/json"
    try:
        payload = fetch(url)
    except Exception as exc:
        return {"status": UNKNOWN, "reason": f"PyPI verification unavailable: {exc}"}
    if payload is None:
        return {"status": ABSENT, "matched": [], "absent": sorted(expected), "conflicts": []}
    urls = payload.get("urls") if isinstance(payload, dict) else None
    if not isinstance(urls, list):
        return {"status": UNKNOWN, "reason": "PyPI response has no valid urls list"}

    remote: dict[str, str] = {}
    for item in urls:
        if not isinstance(item, dict):
            return {"status": UNKNOWN, "reason": "PyPI returned malformed file metadata"}
        filename = item.get("filename")
        digest = (item.get("digests") or {}).get("sha256")
        if not filename or not digest:
            return {"status": UNKNOWN, "reason": "PyPI file metadata lacks filename/SHA-256"}
        remote[str(filename)] = str(digest).lower()

    unexpected = sorted(set(remote) - set(expected))
    conflicts = list(unexpected)
    matched = []
    absent = []
    for filename, expected_sha in expected.items():
        if filename not in remote:
            absent.append(filename)
        elif remote[filename] == expected_sha.lower():
            matched.append(filename)
        else:
            conflicts.append(filename)
    if conflicts:
        return {
            "status": CONFLICT,
            "matched": sorted(matched),
            "absent": sorted(absent),
            "conflicts": sorted(conflicts),
        }
    if not absent:
        status = MATCH
    elif not matched:
        status = ABSENT
    else:
        status = "PARTIAL"
    return {
        "status": status,
        "matched": sorted(matched),
        "absent": sorted(absent),
        "conflicts": [],
    }


def stage_missing_pypi_files(
    candidate_dir: Path, stage_dir: Path, report: dict[str, Any], manifest: dict[str, Any]
) -> None:
    status = report.get("status")
    if status in (UNKNOWN, CONFLICT):
        raise PublicationPrecheckError(f"PyPI precheck is not publishable: {report}")
    stage_dir = Path(stage_dir)
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)
    absent = set(report.get("absent") or [])
    for kind in ("wheel", "sdist"):
        filename = manifest["python"][kind]["filename"]
        if filename in absent:
            shutil.copy2(Path(candidate_dir) / "python" / filename, stage_dir / filename)


def classify_digest(actual: str | None, expected: str) -> str:
    if not actual:
        return ABSENT
    actual = actual.strip().lower()
    expected = expected.strip().lower()
    if actual == expected:
        return MATCH
    return CONFLICT


def aliases_for(version: str = VERSION) -> list[str]:
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise PublicationPrecheckError(f"invalid SemVer for V1 aliases: {version!r}")
    major, minor, _patch = parts
    aliases = [f"{major}.{minor}"]
    if int(major) >= 1:
        aliases.append(major)
    aliases.append("latest")
    return aliases


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="V1 preservation publication prechecks")
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify-candidate")
    verify.add_argument("--candidate-dir", type=Path, required=True)

    pypi = sub.add_parser("precheck-pypi")
    pypi.add_argument("--candidate-dir", type=Path, required=True)
    pypi.add_argument("--stage-dir", type=Path, required=True)
    pypi.add_argument("--out", type=Path, required=True)

    verify_pypi = sub.add_parser("verify-pypi")
    verify_pypi.add_argument("--candidate-dir", type=Path, required=True)

    digest = sub.add_parser("classify-digest")
    digest.add_argument("--actual", default="")
    digest.add_argument("--expected", required=True)

    alias = sub.add_parser("aliases")
    alias.add_argument("--version", default=VERSION)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "verify-candidate":
            verify_candidate_dir(args.candidate_dir)
            print(MATCH)
        elif args.command == "precheck-pypi":
            manifest = verify_candidate_dir(args.candidate_dir)
            report = inspect_pypi(manifest)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if report["status"] in (CONFLICT, UNKNOWN):
                raise PublicationPrecheckError(f"PyPI precheck hard-stop: {report}")
            stage_missing_pypi_files(args.candidate_dir, args.stage_dir, report, manifest)
            print(report["status"])
        elif args.command == "verify-pypi":
            manifest = verify_candidate_dir(args.candidate_dir)
            report = inspect_pypi(manifest)
            if report.get("status") != MATCH:
                raise PublicationPrecheckError(f"PyPI verification did not MATCH: {report}")
            print(MATCH)
        elif args.command == "classify-digest":
            print(classify_digest(args.actual or None, args.expected))
        elif args.command == "aliases":
            print("\n".join(aliases_for(args.version)))
    except PublicationPrecheckError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
