"""Release-only Kroko artifact authority for the V1 preservation release.

The historical V1 runtime semantics stay in ``VoiceSTT/install_kroko.py``.
This helper adds only the release concerns that V1 did not have yet:

* pin the upstream checkout to one immutable commit;
* keep Free and Pro in distinct cache/artifact identities;
* record the exact wheel SHA-256 and reject a corrupt/mismatched cache;
* never accept a runtime Kroko API key as a build input.

It is deliberately a release helper under ``tools/`` rather than a new
``VoiceSTT.kroko`` runtime subsystem.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "VoiceSTT" / "install_kroko.py"
BUILDER_DOCKERFILE = ROOT / "build" / "v1-kroko-builder.Dockerfile"

UPSTREAM_REPO = "https://github.com/kroko-ai/kroko-onnx.git"
UPSTREAM_REVISION = "8657e655192623b98d7708e742a72987f953d3a2"
PLATFORM = "linux_amd64"
PYTHON_TAG = "cp312"
SCHEMA_VERSION = 1
SUPPORTED_VARIANTS = ("free", "pro")
RUNTIME_CREDENTIAL_ENV = "KROKO_API_KEY"


class ReleaseKrokoError(RuntimeError):
    pass


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_variant(value: str) -> str:
    variant = str(value or "").strip().lower()
    if variant not in SUPPORTED_VARIANTS:
        raise ReleaseKrokoError(
            f"unknown Kroko release variant {value!r}; expected {SUPPORTED_VARIANTS}"
        )
    return variant


def fingerprint_payload(variant: str) -> dict[str, Any]:
    variant = normalize_variant(variant)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "variant": variant,
        "platform": PLATFORM,
        "pythonTag": PYTHON_TAG,
        "upstreamRepo": UPSTREAM_REPO,
        "upstreamRevision": UPSTREAM_REVISION,
        "v1InstallerSha256": sha256_file(INSTALLER),
        "builderDockerfileSha256": sha256_file(BUILDER_DOCKERFILE),
        "buildMode": "v1-install-kroko-linux-skip-install",
    }


def fingerprint_for(variant: str) -> str:
    payload = fingerprint_payload(variant)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(canonical)


def _load_v1_installer():
    spec = importlib.util.spec_from_file_location("v1_install_kroko", INSTALLER)
    if spec is None or spec.loader is None:
        raise ReleaseKrokoError(f"could not load V1 Kroko installer from {INSTALLER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    printable = " ".join(cmd)
    print("+ " + printable)
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def _materialize_pinned_checkout(work_dir: Path) -> Path:
    repo_dir = work_dir / "kroko-onnx"
    _run(["git", "init", str(repo_dir)])
    _run(["git", "-C", str(repo_dir), "remote", "add", "origin", UPSTREAM_REPO])
    _run(
        [
            "git", "-C", str(repo_dir), "fetch", "--depth", "1", "origin",
            UPSTREAM_REVISION,
        ]
    )
    _run(["git", "-C", str(repo_dir), "checkout", "--detach", "FETCH_HEAD"])
    resolved = subprocess.check_output(
        ["git", "-C", str(repo_dir), "rev-parse", "HEAD"], text=True
    ).strip()
    if resolved != UPSTREAM_REVISION:
        raise ReleaseKrokoError(
            f"pinned Kroko checkout resolved to {resolved}, expected {UPSTREAM_REVISION}"
        )
    return repo_dir


def _build_inside_release_builder(variant: str, out_dir: Path) -> dict[str, Any]:
    variant = normalize_variant(variant)
    if os.environ.get(RUNTIME_CREDENTIAL_ENV):
        raise ReleaseKrokoError(
            f"{RUNTIME_CREDENTIAL_ENV} is a runtime credential and must not be present in a release build"
        )

    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    for path in out_dir.glob("*.whl"):
        path.unlink()
    manifest_path = out_dir / "artifact.json"
    if manifest_path.exists():
        manifest_path.unlink()

    installer = _load_v1_installer()
    with tempfile.TemporaryDirectory(prefix=f"v1-kroko-{variant}-") as tmp:
        repo_dir = _materialize_pinned_checkout(Path(tmp))
        # Preserve the V1 builder itself.  The only release-specific change is
        # that the checkout above is immutable rather than the moving branch.
        args = SimpleNamespace(variant=variant, skip_install=True)
        installer.install_linux(args, repo_dir)
        wheels = sorted((repo_dir / "release_artifacts" / "linux").glob("*.whl"))
        if len(wheels) != 1:
            raise ReleaseKrokoError(
                f"expected exactly one Kroko wheel for {variant}, found {wheels}"
            )
        destination = out_dir / wheels[0].name
        shutil.copy2(wheels[0], destination)

    manifest = {
        **fingerprint_payload(variant),
        "fingerprint": fingerprint_for(variant),
        "wheel": {
            "filename": destination.name,
            "sha256": sha256_file(destination),
            "bytes": destination.stat().st_size,
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def verify_artifact(variant: str, artifact_dir: Path) -> dict[str, Any]:
    variant = normalize_variant(variant)
    artifact_dir = Path(artifact_dir)
    manifest_path = artifact_dir / "artifact.json"
    if not manifest_path.is_file():
        raise ReleaseKrokoError(f"missing Kroko artifact manifest: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ReleaseKrokoError(f"invalid Kroko artifact manifest: {exc}") from exc

    expected_payload = fingerprint_payload(variant)
    for key, expected in expected_payload.items():
        if manifest.get(key) != expected:
            raise ReleaseKrokoError(
                f"cached Kroko artifact mismatch for {key}: {manifest.get(key)!r} != {expected!r}"
            )
    expected_fingerprint = fingerprint_for(variant)
    if manifest.get("fingerprint") != expected_fingerprint:
        raise ReleaseKrokoError("cached Kroko fingerprint does not match current release inputs")

    wheel_info = manifest.get("wheel") or {}
    filename = wheel_info.get("filename")
    expected_sha = wheel_info.get("sha256")
    if not filename or not expected_sha:
        raise ReleaseKrokoError("Kroko artifact manifest is missing wheel identity")
    wheel = artifact_dir / filename
    if not wheel.is_file():
        raise ReleaseKrokoError(f"cached Kroko wheel is missing: {wheel}")
    actual_sha = sha256_file(wheel)
    if actual_sha != expected_sha:
        raise ReleaseKrokoError(
            f"cached Kroko wheel hash mismatch: {actual_sha} != {expected_sha}"
        )
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="V1 preservation Kroko release helper")
    sub = parser.add_subparsers(dest="command", required=True)

    fp = sub.add_parser("fingerprint", help="Print the full authoritative cache fingerprint")
    fp.add_argument("--variant", choices=SUPPORTED_VARIANTS, required=True)

    build = sub.add_parser("build", help="Build one pinned V1 Kroko Linux wheel")
    build.add_argument("--variant", choices=SUPPORTED_VARIANTS, required=True)
    build.add_argument("--out-dir", type=Path, required=True)

    verify = sub.add_parser("verify", help="Verify one cached V1 Kroko release artifact")
    verify.add_argument("--variant", choices=SUPPORTED_VARIANTS, required=True)
    verify.add_argument("--artifact-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "fingerprint":
            print(fingerprint_for(args.variant))
        elif args.command == "build":
            print(json.dumps(_build_inside_release_builder(args.variant, args.out_dir), sort_keys=True))
        elif args.command == "verify":
            print(json.dumps(verify_artifact(args.variant, args.artifact_dir), sort_keys=True))
        else:  # pragma: no cover
            raise ReleaseKrokoError(f"unsupported command: {args.command}")
    except (ReleaseKrokoError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
