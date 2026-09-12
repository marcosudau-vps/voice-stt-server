"""Pinned Free/Pro Kroko runtime build authority for V1.0.0.

Produces four intermediate native wheels: free/pro x linux_x86_64/win_amd64.
The platform and variant are part of the fingerprint. KROKO_API_KEY is a runtime
credential and is rejected from every release build invocation.
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
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "VoiceSTT" / "install_kroko.py"
BUILDER_DOCKERFILE = ROOT / "build" / "v1-kroko-builder.Dockerfile"
UPSTREAM_REPO = "https://github.com/kroko-ai/kroko-onnx.git"
UPSTREAM_REVISION = "8657e655192623b98d7708e742a72987f953d3a2"
PYTHON_TAG = "cp312"
SCHEMA_VERSION = 2
SUPPORTED_VARIANTS = ("free", "pro")
SUPPORTED_PLATFORMS = ("linux_x86_64", "win_amd64")
RUNTIME_CREDENTIAL_ENV = "KROKO_API_KEY"

class ReleaseKrokoError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize(value: str, allowed: tuple[str, ...], label: str) -> str:
    value = str(value or "").strip().lower()
    if value not in allowed:
        raise ReleaseKrokoError(f"unknown {label} {value!r}; expected {allowed}")
    return value


def normalize_variant(value: str) -> str:
    return _normalize(value, SUPPORTED_VARIANTS, "variant")


def normalize_platform(value: str) -> str:
    return _normalize(value, SUPPORTED_PLATFORMS, "platform")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint_payload(variant: str, platform: str = "linux_x86_64") -> dict[str, Any]:
    variant = normalize_variant(variant)
    platform = normalize_platform(platform)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "variant": variant,
        "platform": platform,
        "pythonTag": PYTHON_TAG,
        "upstreamRepo": UPSTREAM_REPO,
        "upstreamRevision": UPSTREAM_REVISION,
        "v1InstallerSha256": sha256_file(INSTALLER),
        "builderDockerfileSha256": sha256_file(BUILDER_DOCKERFILE),
        "buildMode": "linux-native-wheel" if platform == "linux_x86_64" else "windows-docker-cross-wheel",
    }


def fingerprint_for(variant: str, platform: str = "linux_x86_64") -> str:
    payload = fingerprint_payload(variant, platform)
    return _sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


def _load_installer():
    spec = importlib.util.spec_from_file_location("v1_install_kroko", INSTALLER)
    if spec is None or spec.loader is None:
        raise ReleaseKrokoError(f"could not load {INSTALLER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(cmd: list[str], cwd: Path | None = None, env=None) -> None:
    print("+ " + " ".join(str(x) for x in cmd))
    subprocess.run([str(x) for x in cmd], cwd=str(cwd) if cwd else None, env=env, check=True)


def _materialize_pinned_checkout(work_dir: Path) -> Path:
    repo = work_dir / "kroko-onnx"
    _run(["git", "init", str(repo)])
    _run(["git", "-C", str(repo), "remote", "add", "origin", UPSTREAM_REPO])
    _run(["git", "-C", str(repo), "fetch", "--depth", "1", "origin", UPSTREAM_REVISION])
    _run(["git", "-C", str(repo), "checkout", "--detach", "FETCH_HEAD"])
    actual = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    if actual != UPSTREAM_REVISION:
        raise ReleaseKrokoError(f"pinned checkout resolved to {actual}")
    return repo


def _wheel_tags(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".dist-info/WHEEL"))
        text = zf.read(name).decode("utf-8")
    return [line.split(":", 1)[1].strip() for line in text.splitlines() if line.startswith("Tag:")]


def _select_wheel(repo: Path, variant: str, platform: str) -> Path:
    if platform == "linux_x86_64":
        wheels = sorted((repo / "release_artifacts" / "linux").glob("*.whl"))
    else:
        wheels = sorted((repo / "release_artifacts" / "windows").glob(f"*1{variant}*cp312*win_amd64.whl"))
        if not wheels:
            wheels = sorted((repo / "release_artifacts" / "windows").glob("*cp312*win_amd64.whl"))
    if len(wheels) != 1:
        raise ReleaseKrokoError(f"expected exactly one {variant}/{platform} Kroko wheel, got {wheels}")
    tags = _wheel_tags(wheels[0])
    if not any(t.startswith("cp312-") and t.endswith("-" + platform) for t in tags):
        raise ReleaseKrokoError(f"wrong native tag for {wheels[0].name}: {tags}")
    return wheels[0]


def _build(variant: str, platform: str, out_dir: Path) -> dict[str, Any]:
    variant = normalize_variant(variant)
    platform = normalize_platform(platform)
    if os.environ.get(RUNTIME_CREDENTIAL_ENV):
        raise ReleaseKrokoError(f"{RUNTIME_CREDENTIAL_ENV} is runtime-only and must not enter release builds")
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.whl"):
        old.unlink()
    manifest_path = out_dir / "artifact.json"
    if manifest_path.exists():
        manifest_path.unlink()

    installer = _load_installer()
    with tempfile.TemporaryDirectory(prefix=f"v1-kroko-{variant}-{platform}-") as tmp:
        repo = _materialize_pinned_checkout(Path(tmp))
        args = SimpleNamespace(variant=variant, skip_install=True)
        if platform == "linux_x86_64":
            installer.install_linux(args, repo)
        else:
            # The pinned upstream commit contains build_windows.sh/.bat and a
            # Docker cross-build that produces cp312-cp312-win_amd64 wheels.
            installer.prepare_windows_checkout(repo)
            if os.name == "nt":
                _run(["cmd.exe", "/c", str(repo / "build_windows.bat"), "--variant", variant], cwd=repo)
            else:
                _run(["bash", str(repo / "build_windows.sh"), "--variant", variant], cwd=repo)
        source = _select_wheel(repo, variant, platform)
        destination = out_dir / source.name
        shutil.copy2(source, destination)

    manifest = {
        **fingerprint_payload(variant, platform),
        "fingerprint": fingerprint_for(variant, platform),
        "wheel": {
            "filename": destination.name,
            "sha256": sha256_file(destination),
            "bytes": destination.stat().st_size,
            "tags": _wheel_tags(destination),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def verify_artifact(variant: str, artifact_dir: Path, platform: str = "linux_x86_64") -> dict[str, Any]:
    variant = normalize_variant(variant)
    platform = normalize_platform(platform)
    artifact_dir = Path(artifact_dir)
    manifest_path = artifact_dir / "artifact.json"
    if not manifest_path.is_file():
        raise ReleaseKrokoError(f"missing artifact manifest {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ReleaseKrokoError(f"invalid artifact manifest: {exc}") from exc
    expected = fingerprint_payload(variant, platform)
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ReleaseKrokoError(f"artifact mismatch {key}: {manifest.get(key)!r} != {value!r}")
    if manifest.get("fingerprint") != fingerprint_for(variant, platform):
        raise ReleaseKrokoError("artifact fingerprint mismatch")
    info = manifest.get("wheel") or {}
    wheel = artifact_dir / str(info.get("filename") or "")
    if not wheel.is_file() or sha256_file(wheel) != info.get("sha256"):
        raise ReleaseKrokoError("Kroko wheel missing or SHA-256 mismatch")
    if _wheel_tags(wheel) != info.get("tags"):
        raise ReleaseKrokoError("Kroko wheel tag metadata mismatch")
    return manifest


def main(argv=None):
    p = argparse.ArgumentParser(description="V1 pinned Kroko runtime builder")
    sub = p.add_subparsers(dest="command", required=True)
    fp = sub.add_parser("fingerprint")
    fp.add_argument("--variant", choices=SUPPORTED_VARIANTS, required=True)
    fp.add_argument("--platform", choices=SUPPORTED_PLATFORMS, required=True)
    b = sub.add_parser("build")
    b.add_argument("--variant", choices=SUPPORTED_VARIANTS, required=True)
    b.add_argument("--platform", choices=SUPPORTED_PLATFORMS, required=True)
    b.add_argument("--out-dir", type=Path, required=True)
    v = sub.add_parser("verify")
    v.add_argument("--variant", choices=SUPPORTED_VARIANTS, required=True)
    v.add_argument("--platform", choices=SUPPORTED_PLATFORMS, required=True)
    v.add_argument("--artifact-dir", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if args.command == "fingerprint":
            print(fingerprint_for(args.variant, args.platform))
        elif args.command == "build":
            print(json.dumps(_build(args.variant, args.platform, args.out_dir), sort_keys=True))
        else:
            print(json.dumps(verify_artifact(args.variant, args.artifact_dir, args.platform), sort_keys=True))
    except (ReleaseKrokoError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
