"""Public production Docker build orchestrator (AP-SRV-070 W4C).

Turns the already-qualified VoiceSTT wheel and a verified Linux/AMD64 Kroko
artifact into the two public production images:

.. code-block:: text

    VoiceSTT source
      -> VoiceSTT wheel (python -m build)
      -> Kroko artifact resolve (existing W4A fingerprint/artifact-store
         authority, run inside build/kroko-builder.Dockerfile - REUSE if a
         verified artifact already exists, BUILD ONCE via the existing
         authorized Linux path otherwise)
      -> production Docker image build (Dockerfile, no editable install, no
         native Kroko compilation)
      -> voice-stt-server / voice-stt-server-pro
      -> build manifest

This module never re-implements or redesigns the Kroko fingerprint/
artifact-store authority (``VoiceSTT.kroko.*``), the STT model management
authority, or the packaging/version authority (``VoiceSTT._version``) - it
only calls the public CLI/API each of those already expose.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from VoiceSTT._version import resolve_version  # noqa: E402
from VoiceSTT.kroko import artifacts as kroko_artifacts  # noqa: E402
from VoiceSTT.kroko.buildinputs import SUPPORTED_VARIANTS as KROKO_VARIANTS  # noqa: E402

PRODUCTION_DOCKERFILE = REPO_ROOT / "Dockerfile"
KROKO_BUILDER_DOCKERFILE = REPO_ROOT / "build" / "kroko-builder.Dockerfile"
KROKO_BUILDER_IMAGE = "voicestt-kroko-builder:w4c"

VARIANT_FREE = "free"
VARIANT_PRO = "pro"
SUPPORTED_VARIANTS = (VARIANT_FREE, VARIANT_PRO)
ALL_VARIANTS_TARGET = "all"

#: The two public production product identities (AP-SRV-070 W4C, section 5.2).
#: Free/Pro is a build-time-only choice; neither name is ever influenced by a
#: runtime Kroko license key.
IMAGE_NAMES = {
    VARIANT_FREE: "voice-stt-server",
    VARIANT_PRO: "voice-stt-server-pro",
}


class BuildError(RuntimeError):
    """A production build step failed, or a precondition was not met."""


@dataclass(frozen=True)
class CommandResult:
    args: List[str]
    returncode: int
    stdout: str
    stderr: str


CommandRunner = Callable[..., CommandResult]


def default_runner(
    cmd: Sequence[str],
    *,
    cwd: Optional[Path] = None,
    env: Optional[Dict[str, str]] = None,
    check: bool = True,
) -> CommandResult:
    """Runs one subprocess, echoing it, and returns a plain result object."""
    printable = " ".join(str(part) for part in cmd)
    print("+ " + printable)
    completed = subprocess.run(
        [str(part) for part in cmd],
        cwd=str(cwd) if cwd is not None else None,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="" if completed.stderr.endswith("\n") else "\n")
    if check and completed.returncode != 0:
        raise BuildError(f"command failed with exit code {completed.returncode}: {printable}")
    return CommandResult(
        args=list(cmd),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


# --------------------------------------------------------------------------
# 1. Variant selection / Free-Pro mapping
# --------------------------------------------------------------------------


def normalize_variant(variant: str) -> str:
    value = str(variant or "").strip().lower()
    if value not in SUPPORTED_VARIANTS:
        raise BuildError(
            f"unknown production build variant {variant!r}; expected one of {SUPPORTED_VARIANTS}"
        )
    return value


def image_name_for(variant: str) -> str:
    """The public image repository name for one build-time Kroko variant.

    This is the single Free/Pro authority for the production build: a
    runtime Kroko license key never reaches this function and can therefore
    never change which image name a build produces (AP-SRV-070 W4C, gate
    W4C-G30/G31).
    """
    return IMAGE_NAMES[normalize_variant(variant)]


def variants_for_target(target: str) -> List[str]:
    """The concrete variant list for one orchestrator CLI target."""
    value = str(target or "").strip().lower()
    if value in SUPPORTED_VARIANTS:
        return [value]
    if value == ALL_VARIANTS_TARGET:
        return list(SUPPORTED_VARIANTS)
    raise BuildError(
        f"unknown build target {target!r}; expected one of "
        f"{SUPPORTED_VARIANTS + (ALL_VARIANTS_TARGET,)}"
    )


# --------------------------------------------------------------------------
# 2. Preflight / commit / version
# --------------------------------------------------------------------------


def preflight(runner: CommandRunner = default_runner) -> Dict[str, str]:
    """Verifies the host tools this orchestrator needs are present."""
    versions = {}
    for tool, cmd in (
        ("git", ["git", "--version"]),
        ("docker", ["docker", "version", "--format", "{{.Server.Version}}"]),
    ):
        if shutil.which(cmd[0]) is None:
            raise BuildError(f"required tool not found on PATH: {cmd[0]}")
        result = runner(cmd, check=False)
        if result.returncode != 0:
            raise BuildError(
                f"{tool} preflight check failed (exit {result.returncode}): {result.stderr.strip()}"
            )
        versions[tool] = result.stdout.strip()
    return versions


def resolve_git_commit(runner: CommandRunner = default_runner, cwd: Path = REPO_ROOT) -> str:
    result = runner(["git", "rev-parse", "HEAD"], cwd=cwd)
    commit = result.stdout.strip()
    if not commit or len(commit) != 40:
        raise BuildError(f"could not resolve an exact git commit: {commit!r}")
    return commit


def resolve_dirty(runner: CommandRunner = default_runner, cwd: Path = REPO_ROOT) -> bool:
    result = runner(["git", "status", "--porcelain"], cwd=cwd)
    return bool(result.stdout.strip())


def resolve_voicestt_version() -> str:
    """The one product version authority (see ``VoiceSTT._version``)."""
    return resolve_version()


# --------------------------------------------------------------------------
# 3. VoiceSTT wheel build
# --------------------------------------------------------------------------


def build_voicestt_wheel(
    *,
    dist_dir: Path,
    runner: CommandRunner = default_runner,
) -> Path:
    """Builds the VoiceSTT wheel reproducibly with PEP 517 ``build``."""
    out_dir = dist_dir / "voicestt"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    runner(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(out_dir)],
        cwd=REPO_ROOT,
    )
    wheels = sorted(out_dir.glob("voicestt-*.whl"))
    if not wheels:
        raise BuildError(f"VoiceSTT wheel build produced no wheel in {out_dir}")
    if len(wheels) > 1:
        raise BuildError(f"VoiceSTT wheel build produced more than one wheel: {wheels}")
    return wheels[0]


# --------------------------------------------------------------------------
# 4. Kroko artifact resolution (existing W4A authority, run in a container)
# --------------------------------------------------------------------------


def build_kroko_builder_image(
    *,
    tag: str = KROKO_BUILDER_IMAGE,
    runner: CommandRunner = default_runner,
) -> str:
    """Builds the standalone Linux/AMD64 Kroko builder image.

    This is the existing, W4A-authorized Linux native build path, run as its
    own image rather than as a stage of the production Dockerfile (AP-SRV-070
    W4C, section 6: "Platform boundary" / section 7.2). It is never referenced
    by ``Dockerfile`` and never runs during a production image build.
    """
    runner(
        [
            "docker", "build",
            "--file", str(KROKO_BUILDER_DOCKERFILE),
            "--tag", tag,
            str(REPO_ROOT),
        ],
        cwd=REPO_ROOT,
    )
    return tag


def _run_kroko_builder(
    *,
    builder_image: str,
    artifact_store_host: Path,
    work_dir_host: Path,
    args: Sequence[str],
    runner: CommandRunner,
) -> Dict[str, Any]:
    artifact_store_host.mkdir(parents=True, exist_ok=True)
    work_dir_host.mkdir(parents=True, exist_ok=True)
    result = runner(
        [
            "docker", "run", "--rm",
            "--platform", "linux/amd64",
            "-v", f"{artifact_store_host}:/artifact-store",
            "-v", f"{work_dir_host}:/work",
            "-e", f"{kroko_artifacts.ARTIFACT_STORE_ENV}=/artifact-store",
            builder_image,
            *args,
        ],
    )
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise BuildError(
            f"Kroko builder container did not return JSON: {result.stdout!r}"
        ) from exc


def describe_kroko_artifact(
    *,
    variant: str,
    builder_image: str,
    artifact_store_host: Path,
    work_dir_host: Path,
    runner: CommandRunner = default_runner,
) -> Dict[str, Any]:
    """Read-only Linux/AMD64 fingerprint + REUSE availability. Compiles nothing."""
    variant = normalize_variant(variant)
    return _run_kroko_builder(
        builder_image=builder_image,
        artifact_store_host=artifact_store_host,
        work_dir_host=work_dir_host,
        args=["--describe-artifact", "--variant", variant],
        runner=runner,
    )


def build_kroko_artifact(
    *,
    variant: str,
    builder_image: str,
    artifact_store_host: Path,
    work_dir_host: Path,
    runner: CommandRunner = default_runner,
) -> None:
    """Runs a real native Kroko build (artifact miss only)."""
    variant = normalize_variant(variant)
    runner(
        [
            "docker", "run", "--rm",
            "--platform", "linux/amd64",
            "-v", f"{artifact_store_host}:/artifact-store",
            "-v", f"{work_dir_host}:/work",
            "-e", f"{kroko_artifacts.ARTIFACT_STORE_ENV}=/artifact-store",
            builder_image,
            "--build", "--skip-install",
            "--variant", variant,
            "--work-dir", "/work",
        ],
    )


def _host_wheel_path(artifact_store_host: Path, container_wheel_path: str) -> Path:
    """Translates the builder container's ``/artifact-store/...`` path to the host."""
    prefix = "/artifact-store/"
    if not container_wheel_path.startswith(prefix):
        raise BuildError(
            f"Kroko artifact wheel path is not inside the mounted store: {container_wheel_path!r}"
        )
    return artifact_store_host / container_wheel_path[len(prefix):]


def resolve_kroko_wheel(
    *,
    variant: str,
    builder_image: str,
    artifact_store_host: Path,
    work_dir_host: Path,
    runner: CommandRunner = default_runner,
) -> Dict[str, Any]:
    """Resolves one variant's Linux/AMD64 Kroko wheel: REUSE, else BUILD once.

    Returns the ``describe-artifact`` payload (fingerprint, inputs, artifact
    metadata) plus a ``hostWheelPath``/``reused`` field. Never falls back to
    compiling Kroko as part of the production image build (AP-SRV-070 W4C,
    "Platform boundary": use an existing verified artifact, use the existing
    authorized Linux build path, or abort - never move the compile into the
    production Docker build).
    """
    payload = describe_kroko_artifact(
        variant=variant,
        builder_image=builder_image,
        artifact_store_host=artifact_store_host,
        work_dir_host=work_dir_host,
        runner=runner,
    )
    reused = bool(payload.get("artifactPresent"))
    if not reused:
        build_kroko_artifact(
            variant=variant,
            builder_image=builder_image,
            artifact_store_host=artifact_store_host,
            work_dir_host=work_dir_host,
            runner=runner,
        )
        payload = describe_kroko_artifact(
            variant=variant,
            builder_image=builder_image,
            artifact_store_host=artifact_store_host,
            work_dir_host=work_dir_host,
            runner=runner,
        )
        if not payload.get("artifactPresent"):
            raise BuildError(
                f"Kroko {variant} build finished, but no verified artifact was found "
                f"afterwards: {payload}"
            )
    artifact = payload["artifact"]
    host_wheel = _host_wheel_path(artifact_store_host, artifact["wheelPath"])
    if not host_wheel.is_file():
        raise BuildError(f"resolved Kroko wheel does not exist on the host: {host_wheel}")
    payload["reused"] = reused
    payload["hostWheelPath"] = str(host_wheel)
    return payload


def copy_kroko_wheel_to_context(
    *, variant: str, host_wheel_path: Path, dist_dir: Path
) -> Path:
    """Copies the resolved Kroko wheel into the Docker build context."""
    dest_dir = dist_dir / "kroko"
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True)
    dest = dest_dir / host_wheel_path.name
    shutil.copy2(host_wheel_path, dest)
    return dest


# --------------------------------------------------------------------------
# 5. Production image build
# --------------------------------------------------------------------------


def build_production_image(
    *,
    variant: str,
    git_commit: str,
    voicestt_version: str,
    dist_dir: Path,
    runner: CommandRunner = default_runner,
    extra_tags: Sequence[str] = (),
) -> Dict[str, str]:
    """Builds one production image (``voice-stt-server``/``-pro``).

    ``dist_dir`` must already contain ``voicestt/*.whl`` and ``kroko/*.whl``
    (see :func:`build_voicestt_wheel` / :func:`copy_kroko_wheel_to_context`).
    The build context is the repository root, since the Dockerfile's ``COPY``
    instructions reference ``dist/...`` and ``api_fastapi_server/...``
    relative to it.
    """
    variant = normalize_variant(variant)
    image = image_name_for(variant)
    version_tag = f"{image}:{voicestt_version}"
    commit_tag = f"{image}:{git_commit[:12]}"
    build_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if not list((dist_dir / "voicestt").glob("*.whl")):
        raise BuildError(f"no VoiceSTT wheel found under {dist_dir / 'voicestt'}")
    if not list((dist_dir / "kroko").glob("*.whl")):
        raise BuildError(f"no Kroko wheel found under {dist_dir / 'kroko'}")

    cmd = [
        "docker", "build",
        "--file", str(PRODUCTION_DOCKERFILE),
        "--target", "runtime",
        "--platform", "linux/amd64",
        "--build-arg", f"VOICESTT_VERSION={voicestt_version}",
        "--build-arg", f"VOICESTT_GIT_COMMIT={git_commit}",
        "--build-arg", f"VOICESTT_KROKO_VARIANT={variant}",
        "--build-arg", f"BUILD_DATE={build_date}",
        "--tag", version_tag,
        "--tag", commit_tag,
    ]
    for tag in extra_tags:
        cmd += ["--tag", tag]
    cmd.append(str(REPO_ROOT))

    runner(cmd, cwd=REPO_ROOT)
    return {
        "variant": variant,
        "image": image,
        "versionTag": version_tag,
        "commitTag": commit_tag,
        "buildDate": build_date,
    }


def inspect_image(image_ref: str, runner: CommandRunner = default_runner) -> Dict[str, Any]:
    result = runner(["docker", "inspect", image_ref])
    payload = json.loads(result.stdout)
    if not payload:
        raise BuildError(f"docker inspect returned no data for {image_ref}")
    return payload[0]


# --------------------------------------------------------------------------
# 6. CLI
# --------------------------------------------------------------------------


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="build_production.py",
        description=(
            "AP-SRV-070 W4C production build orchestrator: VoiceSTT wheel -> "
            "Kroko artifact resolve -> production Docker image."
        ),
    )
    parser.add_argument(
        "target",
        choices=[*SUPPORTED_VARIANTS, ALL_VARIANTS_TARGET],
        help="Which product identity to build.",
    )
    parser.add_argument(
        "--dist-dir", type=Path, default=REPO_ROOT / "dist",
        help="Build context output directory for the VoiceSTT/Kroko wheels.",
    )
    parser.add_argument(
        "--kroko-artifact-store", type=Path, default=None,
        help="Persistent Kroko artifact store root (default: the shared W4A store).",
    )
    parser.add_argument(
        "--kroko-work-dir", type=Path, default=None,
        help="Scratch directory for a real Kroko native build (default: dist-dir/kroko-work).",
    )
    parser.add_argument(
        "--manifest-out", type=Path, default=None,
        help="Where to write the JSON build manifest (default: dist-dir/build-manifest.json).",
    )
    return parser.parse_args(argv)


def run(target: str, *, dist_dir: Path, kroko_artifact_store: Optional[Path] = None,
        kroko_work_dir: Optional[Path] = None, runner: CommandRunner = default_runner) -> Dict[str, Any]:
    """Runs the full orchestrated build for one target and returns the manifest."""
    variants = variants_for_target(target)
    artifact_store = kroko_artifact_store or kroko_artifacts.default_store_root()
    work_dir = kroko_work_dir or (dist_dir / "kroko-work")

    tool_versions = preflight(runner)
    git_commit = resolve_git_commit(runner)
    dirty = resolve_dirty(runner)
    voicestt_version = resolve_voicestt_version()

    dist_dir.mkdir(parents=True, exist_ok=True)
    wheel_path = build_voicestt_wheel(dist_dir=dist_dir, runner=runner)

    builder_image = build_kroko_builder_image(runner=runner)

    manifest: Dict[str, Any] = {
        "target": target,
        "gitCommit": git_commit,
        "gitDirty": dirty,
        "voicesttVersion": voicestt_version,
        "voicesttWheel": {
            "path": str(wheel_path),
            "name": wheel_path.name,
            "bytes": wheel_path.stat().st_size,
            "sha256": kroko_artifacts.sha256_of(wheel_path),
        },
        "toolVersions": tool_versions,
        "variants": {},
    }

    for variant in variants:
        kroko_payload = resolve_kroko_wheel(
            variant=variant,
            builder_image=builder_image,
            artifact_store_host=artifact_store,
            work_dir_host=work_dir,
            runner=runner,
        )
        copy_kroko_wheel_to_context(
            variant=variant,
            host_wheel_path=Path(kroko_payload["hostWheelPath"]),
            dist_dir=dist_dir,
        )
        image_info = build_production_image(
            variant=variant,
            git_commit=git_commit,
            voicestt_version=voicestt_version,
            dist_dir=dist_dir,
            runner=runner,
        )
        image_details = inspect_image(image_info["versionTag"], runner=runner)
        manifest["variants"][variant] = {
            "kroko": kroko_payload,
            "image": image_info,
            "imageId": image_details.get("Id"),
            "imageLabels": (image_details.get("Config") or {}).get("Labels"),
        }

    return manifest


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        manifest = run(
            args.target,
            dist_dir=args.dist_dir,
            kroko_artifact_store=args.kroko_artifact_store,
            kroko_work_dir=args.kroko_work_dir,
        )
    except BuildError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    manifest_out = args.manifest_out or (args.dist_dir / "build-manifest.json")
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    manifest_out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote build manifest: {manifest_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
