"""GitHub-native release-candidate orchestrator (AP-SRV-070 W5-R04).

One command produces a complete, qualifiable release candidate from an exact
source commit on a clean Linux runner:

.. code-block:: text

    exact source commit/tree
        |
        +-- Kroko Free native artifact  -> voice-stt-server wheel  -> Free image
        +-- Kroko Pro  native artifact  -> voice-stt-server-pro wheel -> Pro image
        |
        +-- private GHCR staging packages (digest-pinned)
        +-- canonical RC manifest + SHA-256 inventory

Why this lives in Python rather than in workflow YAML
-----------------------------------------------------

AP-SRV-070 W5-R04 section 31 forbids a second release implementation living in
shell: the release semantics must have exactly one home. So the workflow's job
is to supply a runner, credentials and permissions, and to call this; every
decision about what a candidate *is* stays here and in
``release_tooling.candidate``. It also makes the whole candidate path testable
with an injected runner, which a YAML script never is.

Nothing here publishes anything public. The only remote write it can perform is
pushing to the **private** staging packages, and even that is opt-in
(``--push-staging``). Staging is not a release surface and must never be
presented as one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
_TOOLS_DIR = REPO_ROOT / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import build_distribution  # noqa: E402
import build_production  # noqa: E402

from release_tooling import candidate as candidate_module  # noqa: E402
from release_tooling import config as release_config  # noqa: E402
from release_tooling import rc_manifest  # noqa: E402

VARIANTS = rc_manifest.VARIANTS


class CandidateError(RuntimeError):
    """The candidate could not be produced, or an input was inconsistent."""


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_candidate_id(env: Optional[Dict[str, str]] = None) -> str:
    """A stable candidate id derived from the workflow run that produced it.

    On a GitHub runner this is ``gh-<run-id>-<attempt>``, which is unique per
    candidate build and traceable back to the exact run. Off GitHub it falls
    back to a local marker, which is deliberately obvious - a locally produced
    candidate should never be mistaken for one a workflow qualified.
    """
    import os

    env = env if env is not None else dict(os.environ)
    run_id = (env.get("GITHUB_RUN_ID") or "").strip()
    attempt = (env.get("GITHUB_RUN_ATTEMPT") or "1").strip()
    if run_id:
        return f"gh-{run_id}-{attempt}"
    return "local-candidate"


def candidate_run_info(env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Traceability back to the workflow run, or an explicit local marker."""
    import os

    env = env if env is not None else dict(os.environ)
    run_id = (env.get("GITHUB_RUN_ID") or "").strip()
    if not run_id:
        return {"environment": "local", "workflow": "", "runId": "", "runAttempt": ""}
    server = (env.get("GITHUB_SERVER_URL") or "https://github.com").rstrip("/")
    repository = env.get("GITHUB_REPOSITORY") or release_config.GITHUB_REPO_SLUG
    return {
        "environment": "github-actions",
        "workflow": env.get("GITHUB_WORKFLOW", ""),
        "runId": run_id,
        "runAttempt": env.get("GITHUB_RUN_ATTEMPT", "1"),
        "runUrl": f"{server}/{repository}/actions/runs/{run_id}",
        "repository": repository,
    }


# --------------------------------------------------------------------------
# Staging: the qualified image bytes must survive until publication
# --------------------------------------------------------------------------


def staging_reference_for(variant: str, candidate_id: str, staging_root: str) -> str:
    """The private staging tag one candidate's image is pushed to."""
    name = release_config.staging_image_name_for(variant)
    return f"{staging_root}/{name}:{candidate_id}"


def push_staging_image(
    *,
    variant: str,
    local_tag: str,
    candidate_id: str,
    staging_root: str,
    runner=build_production.default_runner,
) -> Dict[str, Any]:
    """Pushes one qualified image to private staging and reads back its digest.

    The digest returned here is the identity the whole rest of the release
    hangs on: publication promotes *this* manifest to Docker Hub and then that
    exact manifest to GHCR, so nothing is ever rebuilt after qualification.
    """
    reference = staging_reference_for(variant, candidate_id, staging_root)
    runner(["docker", "tag", local_tag, reference])
    runner(["docker", "push", reference])
    result = runner(
        [
            "docker", "buildx", "imagetools", "inspect", reference,
            "--format", "{{.Manifest.Digest}}",
        ]
    )
    digest = (result.stdout or "").strip()
    if not digest.startswith("sha256:"):
        raise CandidateError(
            f"could not read back the pushed staging manifest digest for "
            f"{reference!r}: {digest!r}"
        )
    return {
        "variant": variant,
        "reference": f"{staging_root}/{release_config.staging_image_name_for(variant)}@{digest}",
        "tagReference": reference,
        "digest": digest,
        "pushed": True,
        "private": True,
    }


def unpushed_staging_record(variant: str, reason: str) -> Dict[str, Any]:
    """A staging record for a run that deliberately did not push.

    Deliberately carries no digest. A candidate whose qualified image bytes
    were never persisted cannot be published later without rebuilding, so the
    RC-manifest assembly must fail closed on it rather than accept a candidate
    that only looks complete.
    """
    return {"variant": variant, "pushed": False, "reason": reason}


# --------------------------------------------------------------------------
# The candidate
# --------------------------------------------------------------------------


def build_candidate(
    *,
    out_dir: Path,
    candidate_id: str,
    source_tree: str,
    qualification_context: str,
    qualification_evidence_ref: str,
    kroko_artifact_store: Optional[Path] = None,
    kroko_work_dir: Optional[Path] = None,
    staging_root: Optional[str] = None,
    push_staging: bool = False,
    assemble_manifest: bool = True,
    runner=build_production.default_runner,
) -> Dict[str, Any]:
    """Builds every candidate artifact and (optionally) the RC manifest."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dist_dir = build_production.default_dist_dir()
    staging_root = staging_root or release_config.staging_repo_root()

    produced: Dict[str, Any] = {"candidateId": candidate_id, "variants": {}}

    for variant in VARIANTS:
        # 1. Production image + Kroko artifact resolve (existing W4C authority).
        build_manifest = build_production.run(
            variant,
            dist_dir=dist_dir,
            kroko_artifact_store=kroko_artifact_store,
            kroko_work_dir=kroko_work_dir,
            runner=runner,
        )
        _write_json(
            out_dir / candidate_module.BUILD_MANIFEST_TEMPLATE.format(variant=variant),
            build_manifest,
        )

        # 2. The complete public distribution wheel, with that exact qualified
        #    Kroko runtime merged in.
        kroko_payload = build_manifest["variants"][variant]["kroko"]
        distribution = build_distribution.build_distribution(
            variant=variant,
            kroko_wheel=Path(kroko_payload["hostWheelPath"]),
            out_dir=out_dir / "dist",
            work_dir=out_dir / "work",
            fingerprint=kroko_payload["fingerprint"],
            timestamp=datetime.fromisoformat(
                build_manifest["buildDate"].replace("Z", "+00:00")
            ),
        )
        _write_json(
            out_dir / candidate_module.DISTRIBUTION_MANIFEST_TEMPLATE.format(variant=variant),
            distribution,
        )

        # 3. Persist the qualified image so publication never rebuilds it.
        if push_staging:
            staging = push_staging_image(
                variant=variant,
                local_tag=build_manifest["variants"][variant]["image"]["versionTag"],
                candidate_id=candidate_id,
                staging_root=staging_root,
                runner=runner,
            )
        else:
            staging = unpushed_staging_record(
                variant, "staging push not requested for this run"
            )
        _write_json(
            out_dir / candidate_module.STAGING_MANIFEST_TEMPLATE.format(variant=variant),
            staging,
        )

        produced["variants"][variant] = {
            "buildManifest": build_manifest,
            "distribution": distribution,
            "staging": staging,
        }

    # 4. The SHA-256 inventory of everything a reviewer can hash themselves.
    inventory = build_inventory(out_dir)
    _write_json(out_dir / "sha256-inventory.json", inventory)
    produced["inventory"] = inventory

    if assemble_manifest:
        manifest = candidate_module.assemble_rc_manifest(
            candidate_dir=out_dir,
            candidate_id=candidate_id,
            source_tree=source_tree,
            qualification_timestamp_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            qualification_context=qualification_context,
            qualification_evidence_ref=qualification_evidence_ref,
            candidate_run=candidate_run_info(),
        )
        rc_manifest.write_rc_manifest(out_dir / "rc-manifest.json", manifest)
        produced["rcManifest"] = manifest

    return produced


def build_windows_candidate(
    *,
    out_dir: Path,
    candidate_id: str,
    source_tree: str,
    kroko_artifact_store: Optional[Path] = None,
    kroko_work_dir: Optional[Path] = None,
    runner=build_production.default_runner,
) -> Dict[str, Any]:
    """Builds Windows AMD64 distribution wheels for Free and Pro (AP-SRV-070 B2)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dist_dir = out_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    work_dir = out_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    store_path = kroko_artifact_store or (REPO_ROOT / ".kroko-artifacts")
    work_path = kroko_work_dir or (REPO_ROOT / ".kroko-work")

    produced: Dict[str, Any] = {"candidateId": candidate_id, "variants": {}}

    for variant in VARIANTS:
        # 1. Build or reuse Kroko Windows artifact via install_kroko.py
        cmd = [
            sys.executable,
            str(REPO_ROOT / "VoiceSTT" / "install_kroko.py"),
            "--variant", variant,
            "--build",
            "--skip-install",
            "--artifact-store", str(store_path),
            "--work-dir", str(work_path),
        ]
        runner(cmd, cwd=REPO_ROOT)

        # 2. Describe artifact to read fingerprint and wheelPath
        desc_cmd = [
            sys.executable,
            str(REPO_ROOT / "VoiceSTT" / "install_kroko.py"),
            "--variant", variant,
            "--describe-artifact",
            "--artifact-store", str(store_path),
        ]
        res = runner(desc_cmd, cwd=REPO_ROOT)
        desc_payload = json.loads(res.stdout)
        artifact = desc_payload.get("artifact")
        if not artifact:
            raise CandidateError(
                f"could not resolve Windows Kroko artifact for {variant}: {desc_payload.get('problems')}"
            )

        kroko_wheel = Path(artifact["wheelPath"])
        fingerprint = desc_payload["fingerprint"]

        # 3. Build Windows distribution wheel
        distribution = build_distribution.build_distribution(
            variant=variant,
            kroko_wheel=kroko_wheel,
            out_dir=dist_dir,
            work_dir=work_dir,
            fingerprint=fingerprint,
        )

        manifest_path = out_dir / f"distribution-{variant}-win_amd64.json"
        _write_json(manifest_path, distribution)
        produced["variants"][variant] = {"distribution": distribution}

    return produced


def build_inventory(out_dir: Path) -> Dict[str, Any]:
    """A machine-readable SHA-256 inventory of every produced candidate file."""
    out_dir = Path(out_dir)
    entries: List[Dict[str, Any]] = []
    for path in sorted(out_dir.rglob("*")):
        if not path.is_file() or path.name == "sha256-inventory.json":
            continue
        entries.append(
            {
                "path": path.relative_to(out_dir).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_of(path),
            }
        )
    return {"root": out_dir.name, "files": entries}


def print_fingerprints(
    *,
    kroko_artifact_store: Optional[Path] = None,
    kroko_work_dir: Optional[Path] = None,
    runner=build_production.default_runner,
) -> Dict[str, str]:
    """The authoritative Kroko fingerprint per variant, for cache keys.

    The fingerprint has to be resolved **inside the builder container**, not on
    the host: a Linux Kroko fingerprint includes the real ``cmake``/``cc``/
    ``c++``/OpenSSL identity that will actually compile the wheel, and on a
    GitHub runner the host toolchain is not the builder toolchain. Keying an
    Actions cache on a host-computed fingerprint would therefore key it on the
    wrong thing and could hand a build the artifact of a different toolchain.

    Building the (small, layer-cached) builder image first is the price of
    getting the key right; the expensive native compile is what the cache
    actually saves.
    """
    builder_image = build_production.build_kroko_builder_image(runner=runner)
    store = kroko_artifact_store or (REPO_ROOT / ".kroko-artifacts")
    work = kroko_work_dir or (REPO_ROOT / ".kroko-work")
    fingerprints: Dict[str, str] = {}
    for variant in VARIANTS:
        payload = build_production.describe_kroko_artifact(
            variant=variant,
            builder_image=builder_image,
            artifact_store_host=Path(store),
            work_dir_host=Path(work),
            runner=runner,
        )
        fingerprints[variant] = payload["fingerprint"]
    return fingerprints


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="release_candidate.py",
        description=(
            "AP-SRV-070 W5-R04: build a complete VoiceSTT release candidate "
            "(both distributions, both images, manifests) on a clean runner."
        ),
    )
    parser.add_argument("--out-dir", default=None, type=Path)
    parser.add_argument("--candidate-id", default=None)
    parser.add_argument("--source-tree", default=None)
    parser.add_argument("--kroko-artifact-store", default=None, type=Path)
    parser.add_argument("--kroko-work-dir", default=None, type=Path)
    parser.add_argument("--staging-root", default=None)
    parser.add_argument(
        "--push-staging", action="store_true",
        help="Push the qualified images to the PRIVATE staging packages. "
             "Required for a candidate that will actually be published later.",
    )
    parser.add_argument(
        "--no-manifest", action="store_true",
        help="Skip RC-manifest assembly (useful when staging was not pushed).",
    )
    parser.add_argument(
        "--print-fingerprints", action="store_true",
        help="Resolve and print the authoritative per-variant Kroko "
             "fingerprints (used as GitHub Actions cache keys) and exit.",
    )
    parser.add_argument(
        "--platform", choices=["linux", "windows", "all"], default="linux",
        help="Target platform to build candidate artifacts for (linux, windows, all).",
    )
    parser.add_argument("--qualification-context", default="github-native candidate build")
    parser.add_argument("--qualification-evidence-ref", default="")
    return parser.parse_args(argv)


def resolve_source_tree(runner=build_production.default_runner) -> str:
    result = runner(["git", "rev-parse", "HEAD^{tree}"], cwd=REPO_ROOT, check=False)
    tree = (result.stdout or "").strip()
    if len(tree) != 40:
        raise CandidateError(f"could not resolve the exact source tree: {tree!r}")
    return tree


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.print_fingerprints:
        try:
            print(json.dumps(
                print_fingerprints(
                    kroko_artifact_store=args.kroko_artifact_store,
                    kroko_work_dir=args.kroko_work_dir,
                ),
                indent=2, sort_keys=True,
            ))
        except build_production.BuildError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.out_dir is None:
        print("ERROR: --out-dir is required unless --print-fingerprints is given", file=sys.stderr)
        return 2

    try:
        if args.platform == "windows":
            produced = build_windows_candidate(
                out_dir=args.out_dir,
                candidate_id=args.candidate_id or default_candidate_id(),
                source_tree=args.source_tree or resolve_source_tree(),
                kroko_artifact_store=args.kroko_artifact_store,
                kroko_work_dir=args.kroko_work_dir,
            )
        else:
            produced = build_candidate(
                out_dir=args.out_dir,
                candidate_id=args.candidate_id or default_candidate_id(),
                source_tree=args.source_tree or resolve_source_tree(),
                qualification_context=args.qualification_context,
                qualification_evidence_ref=args.qualification_evidence_ref
                or candidate_run_info().get("runUrl", "local"),
                kroko_artifact_store=args.kroko_artifact_store,
                kroko_work_dir=args.kroko_work_dir,
                staging_root=args.staging_root,
                push_staging=args.push_staging,
                assemble_manifest=not args.no_manifest,
            )
    except (CandidateError, build_production.BuildError,
            build_distribution.DistributionBuildError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps({"candidateId": produced["candidateId"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
