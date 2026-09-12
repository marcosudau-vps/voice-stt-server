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
SCHEMA_VERSION = 3
SUPPORTED_VARIANTS = ("free", "pro")
SUPPORTED_PLATFORMS = ("linux_x86_64", "win_amd64")
RUNTIME_CREDENTIAL_ENV = "KROKO_API_KEY"

# The upstream Windows cross-build originally downloaded OpenSSL from moving
# Slproweb filenames. That is not suitable release authority: patch versions
# disappear and identical source inputs can stop building. Use the immutable
# versioned NuGet artifact instead. openssl-native 3.5.5 contains the exact
# win-x64 headers, import libraries and runtime DLL names Kroko expects.
WINDOWS_OPENSSL_PACKAGE = "openssl-native"
WINDOWS_OPENSSL_VERSION = "3.5.5"
WINDOWS_OPENSSL_URL = (
    "https://api.nuget.org/v3-flatcontainer/openssl-native/3.5.5/"
    "openssl-native.3.5.5.nupkg"
)


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
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "variant": variant,
        "platform": platform,
        "pythonTag": PYTHON_TAG,
        "upstreamRepo": UPSTREAM_REPO,
        "upstreamRevision": UPSTREAM_REVISION,
        "v1InstallerSha256": sha256_file(INSTALLER),
        "builderDockerfileSha256": sha256_file(BUILDER_DOCKERFILE),
        "buildMode": "linux-native-wheel"
        if platform == "linux_x86_64"
        else "windows-docker-cross-wheel",
    }
    if platform == "win_amd64":
        payload["windowsOpenSsl"] = {
            "package": WINDOWS_OPENSSL_PACKAGE,
            "version": WINDOWS_OPENSSL_VERSION,
            "url": WINDOWS_OPENSSL_URL,
        }
    return payload


def fingerprint_for(variant: str, platform: str = "linux_x86_64") -> str:
    payload = fingerprint_payload(variant, platform)
    return _sha256_bytes(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    )


def _load_installer():
    spec = importlib.util.spec_from_file_location("v1_install_kroko", INSTALLER)
    if spec is None or spec.loader is None:
        raise ReleaseKrokoError(f"could not load {INSTALLER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(cmd: list[str], cwd: Path | None = None, env=None) -> None:
    print("+ " + " ".join(str(x) for x in cmd))
    subprocess.run(
        [str(x) for x in cmd],
        cwd=str(cwd) if cwd else None,
        env=env,
        check=True,
    )


def _materialize_pinned_checkout(work_dir: Path) -> Path:
    repo = work_dir / "kroko-onnx"
    _run(["git", "init", str(repo)])
    _run(["git", "-C", str(repo), "remote", "add", "origin", UPSTREAM_REPO])
    _run(
        [
            "git",
            "-C",
            str(repo),
            "fetch",
            "--depth",
            "1",
            "origin",
            UPSTREAM_REVISION,
        ]
    )
    _run(["git", "-C", str(repo), "checkout", "--detach", "FETCH_HEAD"])
    actual = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual != UPSTREAM_REVISION:
        raise ReleaseKrokoError(f"pinned checkout resolved to {actual}")
    return repo


def _patch_windows_openssl_source(repo: Path) -> None:
    """Replace the rotating Slproweb block with pinned openssl-native NuGet.

    This patch is release-only. It is applied after the historical V1 Windows
    compatibility patches and before upstream ``build_windows.sh`` constructs
    its Docker image.
    """

    path = repo / "Dockerfile.windows"
    text = path.read_text(encoding="utf-8", errors="replace")
    start = text.find("# Windows-native OpenSSL")
    end = text.find("ENV OPENSSL_ROOT_DIR=", start)
    if start < 0 or end < 0:
        raise ReleaseKrokoError(
            "could not locate Windows OpenSSL block in pinned Dockerfile.windows"
        )

    block = f'''# Windows-native OpenSSL -- release-pinned binary package.
# The pinned upstream Dockerfile used rotating Slproweb filenames, which can
# disappear without a source change. openssl-native {WINDOWS_OPENSSL_VERSION}
# is a versioned NuGet package containing x64 headers, import libraries and
# libcrypto/libssl runtime DLLs. Keep the package version in the release
# fingerprint above; do not replace this with an unversioned/latest URL.
RUN apt-get update && apt-get install -y --no-install-recommends \\
        curl unzip \\
 && rm -rf /var/lib/apt/lists/* \\
 && mkdir -p /tmp/openssl-native /opt/openssl-win64/app/bin \\
        /opt/openssl-win64/app/lib /opt/openssl-win64/app/include \\
        /opt/openssl-win64/licenses \\
 && curl -fL --retry 4 --retry-all-errors \\
        "{WINDOWS_OPENSSL_URL}" \\
        -o /tmp/openssl-native.nupkg \\
 && unzip -q /tmp/openssl-native.nupkg -d /tmp/openssl-native \\
 && test -f /tmp/openssl-native/include/openssl/ssl.h \\
 && test -f /tmp/openssl-native/lib/win-x64/native/libcrypto.lib \\
 && test -f /tmp/openssl-native/lib/win-x64/native/libssl.lib \\
 && test -f /tmp/openssl-native/runtimes/win-x64/native/libcrypto-3-x64.dll \\
 && test -f /tmp/openssl-native/runtimes/win-x64/native/libssl-3-x64.dll \\
 && cp -a /tmp/openssl-native/include/. /opt/openssl-win64/app/include/ \\
 && cp -a /tmp/openssl-native/lib/win-x64/native/libcrypto.lib \\
        /opt/openssl-win64/app/lib/libcrypto.lib \\
 && cp -a /tmp/openssl-native/lib/win-x64/native/libssl.lib \\
        /opt/openssl-win64/app/lib/libssl.lib \\
 && cp -a /tmp/openssl-native/runtimes/win-x64/native/libcrypto-3-x64.dll \\
        /opt/openssl-win64/app/bin/libcrypto-3-x64.dll \\
 && cp -a /tmp/openssl-native/runtimes/win-x64/native/libssl-3-x64.dll \\
        /opt/openssl-win64/app/bin/libssl-3-x64.dll \\
 && cp -a /tmp/openssl-native/docs/license.txt \\
        /opt/openssl-win64/licenses/openssl-native-3.5.5-license.txt \\
 && test -s /opt/openssl-win64/app/lib/libcrypto.lib \\
 && test -s /opt/openssl-win64/app/lib/libssl.lib \\
 && test -s /opt/openssl-win64/app/bin/libcrypto-3-x64.dll \\
 && test -s /opt/openssl-win64/app/bin/libssl-3-x64.dll \\
 && rm -rf /tmp/openssl-native /tmp/openssl-native.nupkg

'''
    path.write_text(text[:start] + block + text[end:], encoding="utf-8")
    print(
        "Patched Dockerfile.windows to use pinned "
        f"{WINDOWS_OPENSSL_PACKAGE} {WINDOWS_OPENSSL_VERSION}."
    )


def _patch_windows_output_ownership(repo: Path) -> None:
    """Make upstream's Docker-created temporary output removable by the host.

    The pinned ``build_windows.sh`` writes its bind-mounted output as root.
    On Linux release runners its final ``rm -rf`` therefore fails after the
    native wheel was built successfully.  Reuse the already-built, pinned
    builder image to restore the invoking uid/gid immediately before cleanup.
    """

    path = repo / "build_windows.sh"
    text = path.read_text(encoding="utf-8", errors="replace")
    cleanup = '    rm -rf "$host_out"'
    if cleanup not in text:
        raise ReleaseKrokoError(
            "could not locate Windows temporary-output cleanup in build_windows.sh"
        )
    replacement = '''    docker run --rm --platform linux/amd64 \\
        --entrypoint chown \\
        -v "$host_out:/out" \\
        "$IMAGE" -R "$(id -u):$(id -g)" /out
    rm -rf "$host_out"'''
    path.write_text(text.replace(cleanup, replacement, 1), encoding="utf-8")
    print("Patched build_windows.sh to normalize Docker output ownership.")


def _wheel_tags(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".dist-info/WHEEL"))
        text = zf.read(name).decode("utf-8")
    return [
        line.split(":", 1)[1].strip()
        for line in text.splitlines()
        if line.startswith("Tag:")
    ]


def _select_wheel(repo: Path, variant: str, platform: str) -> Path:
    if platform == "linux_x86_64":
        wheels = sorted((repo / "release_artifacts" / "linux").glob("*.whl"))
    else:
        wheels = sorted(
            (repo / "release_artifacts" / "windows").glob(
                f"*1{variant}*cp312*win_amd64.whl"
            )
        )
        if not wheels:
            wheels = sorted(
                (repo / "release_artifacts" / "windows").glob(
                    "*cp312*win_amd64.whl"
                )
            )
    if len(wheels) != 1:
        raise ReleaseKrokoError(
            f"expected exactly one {variant}/{platform} Kroko wheel, got {wheels}"
        )
    tags = _wheel_tags(wheels[0])
    if not any(t.startswith("cp312-") and t.endswith("-" + platform) for t in tags):
        raise ReleaseKrokoError(f"wrong native tag for {wheels[0].name}: {tags}")
    return wheels[0]


def _build(variant: str, platform: str, out_dir: Path) -> dict[str, Any]:
    variant = normalize_variant(variant)
    platform = normalize_platform(platform)
    if os.environ.get(RUNTIME_CREDENTIAL_ENV):
        raise ReleaseKrokoError(
            f"{RUNTIME_CREDENTIAL_ENV} is runtime-only and must not enter release builds"
        )
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.whl"):
        old.unlink()
    manifest_path = out_dir / "artifact.json"
    if manifest_path.exists():
        manifest_path.unlink()

    installer = _load_installer()
    with tempfile.TemporaryDirectory(
        prefix=f"v1-kroko-{variant}-{platform}-"
    ) as tmp:
        repo = _materialize_pinned_checkout(Path(tmp))
        args = SimpleNamespace(variant=variant, skip_install=True)
        if platform == "linux_x86_64":
            installer.install_linux(args, repo)
        else:
            # Keep historical source-compatibility patches, but replace the
            # moving OpenSSL download with a release-pinned binary dependency.
            installer.prepare_windows_checkout(repo)
            _patch_windows_openssl_source(repo)
            _patch_windows_output_ownership(repo)
            if os.name == "nt":
                _run(
                    [
                        "cmd.exe",
                        "/c",
                        str(repo / "build_windows.bat"),
                        "--variant",
                        variant,
                    ],
                    cwd=repo,
                )
            else:
                _run(
                    ["bash", str(repo / "build_windows.sh"), "--variant", variant],
                    cwd=repo,
                )
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
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def verify_artifact(
    variant: str,
    artifact_dir: Path,
    platform: str = "linux_x86_64",
) -> dict[str, Any]:
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
            raise ReleaseKrokoError(
                f"artifact mismatch {key}: {manifest.get(key)!r} != {value!r}"
            )
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
            print(
                json.dumps(
                    _build(args.variant, args.platform, args.out_dir),
                    sort_keys=True,
                )
            )
        else:
            print(
                json.dumps(
                    verify_artifact(
                        args.variant,
                        args.artifact_dir,
                        args.platform,
                    ),
                    sort_keys=True,
                )
            )
    except (ReleaseKrokoError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
