"""Canonical V1 preservation candidate identity.

The candidate binds one Python distribution (wheel + sdist), two internal
Kroko native build artifacts (Free + Pro), and two OCI product variants to one
exact source commit/tree.  Publication must consume this identity; it must not
rebuild any public artifact after qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v1_kroko_release as kroko  # noqa: E402

VERSION = "1.0.0"
PYPI_DISTRIBUTION = "voice-stt-server"
IMAGE_NAMES = {"free": "voice-stt-server", "pro": "voice-stt-server-pro"}
SCHEMA_VERSION = 1
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class CandidateManifestError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(path: Path) -> dict[str, Any]:
    path = Path(path)
    return {"filename": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size}


def build_python_identity(dist_dir: Path) -> dict[str, Any]:
    dist_dir = Path(dist_dir)
    wheels = sorted(dist_dir.glob("*.whl"))
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise CandidateManifestError(
            f"expected exactly one V1 wheel and one sdist in {dist_dir}, got {wheels=} {sdists=}"
        )
    expected_wheel = f"voice_stt_server-{VERSION}-py3-none-any.whl"
    expected_sdist = f"voice_stt_server-{VERSION}.tar.gz"
    if wheels[0].name != expected_wheel or sdists[0].name != expected_sdist:
        raise CandidateManifestError(
            f"unexpected V1 Python artifacts: {wheels[0].name!r}, {sdists[0].name!r}"
        )
    return {
        "distribution": PYPI_DISTRIBUTION,
        "version": VERSION,
        "wheel": _artifact(wheels[0]),
        "sdist": _artifact(sdists[0]),
    }


def write_python_identity(dist_dir: Path, out: Path) -> dict[str, Any]:
    identity = build_python_identity(dist_dir)
    Path(out).write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return identity


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CandidateManifestError(f"could not read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CandidateManifestError(f"{path} must contain a JSON object")
    return value


def validate_image_record(variant: str, record: dict[str, Any]) -> None:
    expected_name = IMAGE_NAMES[variant]
    if record.get("variant") != variant:
        raise CandidateManifestError(f"image record variant mismatch for {variant}")
    if record.get("image") != expected_name:
        raise CandidateManifestError(
            f"image record for {variant} must name {expected_name!r}, got {record.get('image')!r}"
        )
    digest = str(record.get("digest") or "")
    if not _DIGEST.fullmatch(digest):
        raise CandidateManifestError(f"invalid OCI digest for {variant}: {digest!r}")
    staging = str(record.get("stagingReference") or "")
    if not staging.endswith("@" + digest):
        raise CandidateManifestError(
            f"staging reference for {variant} is not digest-bound: {staging!r}"
        )
    if ":1.0.0" in staging:
        raise CandidateManifestError("candidate staging must not use the public final version tag")


def assemble_candidate(
    *,
    candidate_dir: Path,
    candidate_id: str,
    source_commit: str,
    source_tree: str,
    run_url: str,
    evidence_ref: str,
) -> dict[str, Any]:
    candidate_dir = Path(candidate_dir)
    if not _SHA40.fullmatch(source_commit):
        raise CandidateManifestError(f"invalid source commit: {source_commit!r}")
    if not _SHA40.fullmatch(source_tree):
        raise CandidateManifestError(f"invalid source tree: {source_tree!r}")

    python_identity = _load_json(candidate_dir / "python" / "python-artifact.json")
    expected_python = build_python_identity(candidate_dir / "python")
    if python_identity != expected_python:
        raise CandidateManifestError("Python artifact identity does not match downloaded bytes")

    kroko_records = {}
    image_records = {}
    for variant in ("free", "pro"):
        artifact_dir = candidate_dir / "kroko" / variant
        try:
            kroko_records[variant] = kroko.verify_artifact(variant, artifact_dir)
        except kroko.ReleaseKrokoError as exc:
            raise CandidateManifestError(str(exc)) from exc
        image = _load_json(candidate_dir / "images" / f"{variant}.json")
        validate_image_record(variant, image)
        image_records[variant] = image

    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "productVersion": VERSION,
        "sourceCommit": source_commit,
        "sourceTree": source_tree,
        "candidate": {"id": candidate_id, "runUrl": run_url},
        "python": python_identity,
        "kroko": kroko_records,
        "images": image_records,
        "qualification": {
            "status": "QUALIFIED",
            "evidenceRef": evidence_ref,
            "publicWritesPerformed": False,
        },
    }
    validate_candidate(manifest)
    return manifest


def validate_candidate(manifest: dict[str, Any]) -> None:
    if manifest.get("schemaVersion") != SCHEMA_VERSION:
        raise CandidateManifestError("unsupported candidate manifest schema")
    if manifest.get("productVersion") != VERSION:
        raise CandidateManifestError("V1 preservation candidate must be version 1.0.0")
    if not _SHA40.fullmatch(str(manifest.get("sourceCommit") or "")):
        raise CandidateManifestError("candidate sourceCommit is invalid")
    if not _SHA40.fullmatch(str(manifest.get("sourceTree") or "")):
        raise CandidateManifestError("candidate sourceTree is invalid")

    python_identity = manifest.get("python") or {}
    if python_identity.get("distribution") != PYPI_DISTRIBUTION:
        raise CandidateManifestError("V1 has exactly one PyPI distribution: voice-stt-server")
    if python_identity.get("version") != VERSION:
        raise CandidateManifestError("Python artifact version mismatch")
    if "voice-stt-server-pro" in json.dumps(python_identity, sort_keys=True):
        raise CandidateManifestError("V1 Pro must not become a second PyPI distribution")

    for kind in ("wheel", "sdist"):
        artifact = python_identity.get(kind) or {}
        if not re.fullmatch(r"[0-9a-f]{64}", str(artifact.get("sha256") or "")):
            raise CandidateManifestError(f"Python {kind} is missing an SHA-256 identity")

    kroko_records = manifest.get("kroko") or {}
    images = manifest.get("images") or {}
    for variant in ("free", "pro"):
        record = kroko_records.get(variant) or {}
        if record.get("variant") != variant:
            raise CandidateManifestError(f"Kroko {variant} identity is missing or crossed")
        validate_image_record(variant, images.get(variant) or {})

    qualification = manifest.get("qualification") or {}
    if qualification.get("status") != "QUALIFIED":
        raise CandidateManifestError("publication requires a QUALIFIED candidate")
    if not qualification.get("evidenceRef"):
        raise CandidateManifestError("qualified candidate is missing evidenceRef")
    if qualification.get("publicWritesPerformed") is not False:
        raise CandidateManifestError("candidate qualification must not perform final/public writes")


def build_inventory(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    entries = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if path.name == "sha256-inventory.json":
            continue
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return {"schemaVersion": 1, "files": entries}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="V1 preservation candidate manifest helper")
    sub = parser.add_subparsers(dest="command", required=True)

    py = sub.add_parser("python")
    py.add_argument("--dist-dir", type=Path, required=True)
    py.add_argument("--out", type=Path, required=True)

    assemble = sub.add_parser("assemble")
    assemble.add_argument("--candidate-dir", type=Path, required=True)
    assemble.add_argument("--candidate-id", required=True)
    assemble.add_argument("--source-commit", required=True)
    assemble.add_argument("--source-tree", required=True)
    assemble.add_argument("--run-url", required=True)
    assemble.add_argument("--evidence-ref", required=True)
    assemble.add_argument("--out", type=Path, required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("manifest", type=Path)

    inventory = sub.add_parser("inventory")
    inventory.add_argument("--candidate-dir", type=Path, required=True)
    inventory.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "python":
            args.out.parent.mkdir(parents=True, exist_ok=True)
            write_python_identity(args.dist_dir, args.out)
        elif args.command == "assemble":
            manifest = assemble_candidate(
                candidate_dir=args.candidate_dir,
                candidate_id=args.candidate_id,
                source_commit=args.source_commit,
                source_tree=args.source_tree,
                run_url=args.run_url,
                evidence_ref=args.evidence_ref,
            )
            args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        elif args.command == "validate":
            validate_candidate(_load_json(args.manifest))
        elif args.command == "inventory":
            args.out.write_text(
                json.dumps(build_inventory(args.candidate_dir), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    except CandidateManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
