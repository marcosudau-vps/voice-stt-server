"""The ``release.py`` CLI (AP-SRV-070 W5 / W5-R01-C1, section 6).

This is the one canonical release-operator surface for AP-SRV-070. It
exposes:

* ``preflight``       - read-only checks against the *current* prepared
                         version (never bumps ``VERSION``).
* ``dry-run``          - walks the real release engine
                         (``release_tooling.engine``) in
                         ``ExecutionMode.DRY_RUN``: the exact same operation
                         graph and ordering logic ``publish`` uses, with
                         zero writes.
* ``status``           - the current resumable release state, if any.
* ``manifest build``   - assembles a canonical RC manifest from already-built
                         artifact identities (used by W5-R02).
* ``manifest validate``- validates an existing RC manifest file.
* ``prepare-next-version`` - computes (never writes, unless ``--apply``) the
                         *future* patch/minor/major version, kept explicitly
                         separate from publishing the already-prepared
                         current version (section 6.2).
* ``publish``          - walks the same release engine in
                         ``ExecutionMode.REAL`` using the real, W6-capable
                         adapters (Twine, Docker, Git, ``gh``). Requires
                         ``--yes`` and a passing preflight before touching
                         anything; every adapter still fails closed on any
                         conflicting remote identity and every credential
                         is left for the underlying tool to read from its
                         own environment contract - this process never
                         holds one.

Every subcommand that could mutate anything defaults to not mutating
anything; the current-version path (``preflight``/``dry-run``/``status``)
never mutates ``VERSION``, release notes, Git, a registry, or release state
as though a publish had happened.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from . import candidate as candidate_module
from . import config, gitinfo, pipeline, rc_manifest
from .errors import ManifestError, ReleaseError
from .state import (
    STATE_ORDER,
    default_state_path,
    ensure_same_identity,
    ensure_same_version,
    load_state,
    new_state,
    save_state,
)
from VoiceSTT._version import bump, read_version_file, resolve_bump_kind  # noqa: E402

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_NOT_IMPLEMENTED = 3


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _cmd_preflight(args: argparse.Namespace) -> int:
    from .preflight import run_preflight

    repo_root = config.REPO_ROOT
    expected_version = args.version or read_version_file()
    expected_commit = args.commit
    expected_tree = args.tree
    if expected_commit is None or expected_tree is None:
        try:
            identity = gitinfo.resolve_identity(repo_root)
            expected_commit = expected_commit or identity.commit
            expected_tree = expected_tree or identity.tree
        except gitinfo.GitError:
            pass  # surfaced as a normal FAIL check inside run_preflight instead

    report = run_preflight(
        repo_root=repo_root,
        expected_version=expected_version,
        expected_commit=expected_commit,
        expected_tree=expected_tree,
        rc_manifest_path=args.manifest,
        require_qualified=getattr(args, "require_qualified", False),
    )
    _print_json(report.to_json_dict())
    return EXIT_OK if report.passed else EXIT_FAILED


def _placeholder_manifest(*, version: str, commit: Optional[str], tree: Optional[str]) -> Dict[str, Any]:
    """A schema-valid but obviously-fake RC manifest, for planning only.

    Used when the operator has not supplied a real manifest to ``dry-run``.
    Every identity in it is a visible placeholder, and ``publish`` refuses to
    run without an explicit ``--manifest``, so a placeholder can never reach a
    real publication. No placeholder value here could match a real remote
    artifact identity either, so a dry-run against one reports "would publish"
    rather than a false "already published".
    """
    commit = commit or ("0" * 40)
    tree = tree or ("0" * 40)
    zero_sha = "0" * 64
    zero_digest = "sha256:" + zero_sha

    def _distribution(variant: str, name: str) -> Dict[str, Any]:
        return {
            "name": name,
            "krokoVariant": variant,
            "krokoFingerprint": "unresolved-placeholder",
            "krokoArtifactSha256": zero_sha,
            "wheels": [
                {
                    "filename": f"{name.replace('-', '_')}-{version}-cp312-cp312-linux_x86_64.whl",
                    "sha256": zero_sha,
                    "pythonTag": "cp312",
                    "abiTag": "cp312",
                    "platformTag": "linux_x86_64",
                },
                {
                    "filename": f"{name.replace('-', '_')}-{version}-cp312-cp312-win_amd64.whl",
                    "sha256": zero_sha,
                    "pythonTag": "cp312",
                    "abiTag": "cp312",
                    "platformTag": "win_amd64",
                },
            ],
        }

    def _image(variant: str, digest_seed: str) -> Dict[str, Any]:
        image = config.image_name_for(variant)
        staging = config.staging_image_name_for(variant)
        digest = "sha256:" + (digest_seed * 64)[:64]
        return {
            "tag": f"{image}:{version}",
            "digest": digest,
            "staging": f"{config.staging_repo_root()}/{staging}@{digest}",
        }

    return rc_manifest.build_rc_manifest(
        candidate_id="W5-RC0",
        product_version=version,
        source_commit=commit,
        source_tree=tree,
        distributions={
            variant: _distribution(variant, config.distribution_name_for(variant))
            for variant in rc_manifest.VARIANTS
        },
        images={"free": _image("free", "0"), "pro": _image("pro", "1")},
        oci_version=version,
        oci_revision=commit,
        qualification_timestamp_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        qualification_context="unqualified placeholder - no RC manifest was given",
        qualification_evidence_ref="none",
    )


def _load_or_placeholder_manifest(args: argparse.Namespace, *, version: str) -> Dict[str, Any]:
    if args.manifest:
        return rc_manifest.load_rc_manifest(Path(args.manifest))
    expected_commit = None
    expected_tree = None
    try:
        identity = gitinfo.resolve_identity(config.REPO_ROOT)
        expected_commit, expected_tree = identity.commit, identity.tree
    except gitinfo.GitError:
        pass
    return _placeholder_manifest(version=version, commit=expected_commit, tree=expected_tree)


def _cmd_dry_run(args: argparse.Namespace) -> int:
    repo_root = config.REPO_ROOT
    version = args.version or read_version_file()
    manifest = _load_or_placeholder_manifest(args, version=version)
    state_path = Path(args.state_file) if args.state_file else default_state_path(repo_root, version)
    state = load_state(state_path)
    if state is None:
        print(
            f"No release state exists yet for version {version} at {state_path}; "
            "dry-run reports the plan starting from PREPARED.",
            file=sys.stderr,
        )
        identity = rc_manifest.state_identity(manifest)
        state = new_state(
            version=version,
            source_commit=manifest["sourceCommit"],
            source_tree=manifest["sourceTree"],
            distributions=identity["distributions"],
            images=identity["images"],
            candidate=rc_manifest.candidate_identity(manifest),
        )
    result = pipeline.dry_run(state, manifest, stop_after=args.until)
    _print_json(result.to_json_dict())
    return EXIT_OK


def _cmd_status(args: argparse.Namespace) -> int:
    repo_root = config.REPO_ROOT
    version = args.version or read_version_file()
    state_path = Path(args.state_file) if args.state_file else default_state_path(repo_root, version)
    state = load_state(state_path)
    if state is None:
        _print_json({"version": version, "statePath": str(state_path), "state": None})
        return EXIT_OK
    _print_json({"statePath": str(state_path), **state.to_json_dict()})
    return EXIT_OK


def _cmd_manifest_validate(args: argparse.Namespace) -> int:
    try:
        rc_manifest.load_rc_manifest(Path(args.path))
    except ReleaseError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return EXIT_FAILED
    print(f"VALID: {args.path}")
    return EXIT_OK


def _cmd_manifest_build(args: argparse.Namespace) -> int:
    """Assembles the canonical RC manifest from one candidate output directory.

    The assembly itself lives in ``release_tooling.candidate`` so that this
    command and the GitHub candidate workflow's orchestrator
    (``tools/release_candidate.py``) can never build it two different ways.
    """
    manifest = candidate_module.assemble_rc_manifest(
        candidate_dir=Path(args.candidate_dir),
        candidate_id=args.candidate_id,
        source_tree=args.source_tree,
        qualification_timestamp_utc=args.qualification_timestamp,
        qualification_context=args.qualification_context,
        qualification_evidence_ref=args.qualification_evidence_ref,
        candidate_run=json.loads(args.candidate_run) if args.candidate_run else None,
        release_readiness=args.release_readiness,
    )
    rc_manifest.write_rc_manifest(Path(args.out), manifest)
    print(f"Wrote RC manifest: {args.out}")
    return EXIT_OK


def _cmd_manifest_qualify(args: argparse.Namespace) -> int:
    """Transitions an RC manifest to QUALIFIED status (Option A)."""
    manifest_path = Path(args.manifest)
    manifest = rc_manifest.load_rc_manifest(manifest_path)
    qualified = rc_manifest.qualify_manifest(
        manifest,
        evidence_ref=args.evidence_ref,
        context=args.context,
        timestamp_utc=args.timestamp,
    )
    out_path = Path(args.out) if args.out else manifest_path
    rc_manifest.write_rc_manifest(out_path, qualified)
    print(f"Qualified RC manifest written to: {out_path}")
    return EXIT_OK


def _cmd_prepare_next_version(args: argparse.Namespace) -> int:
    """Computes the next patch/minor/major version. Never mutates ``VERSION``
    unless ``--apply`` is explicitly given - and even then, this is *future*
    version preparation, never the current-version publish path."""
    kind = resolve_bump_kind(minor=args.minor, major=args.major)
    current = read_version_file()
    proposed = bump(current, kind)
    if not args.apply:
        _print_json({"currentVersion": current, "bumpKind": kind, "proposedNextVersion": proposed, "applied": False})
        return EXIT_OK

    version_path = config.REPO_ROOT / "VERSION"
    version_path.write_text(proposed + "\n", encoding="utf-8")
    _print_json({"currentVersion": current, "bumpKind": kind, "proposedNextVersion": proposed, "applied": True})
    print(
        "NOTE: VERSION was written. RELEASE_NOTES.md was NOT touched - add a fresh "
        "'Unreleased' section by hand before this becomes a real release.",
        file=sys.stderr,
    )
    return EXIT_OK


def _cmd_publish(args: argparse.Namespace) -> int:
    """Walks the real release engine in ``ExecutionMode.REAL``.

    Requires an explicit ``--manifest`` (never a placeholder - a real
    publish must never run against a fabricated identity) and ``--yes``,
    then a passing preflight, before a single adapter is even constructed.
    Every credential stays inside the tool it belongs to (Twine, Docker,
    git, ``gh``) - this function never reads one.
    """
    from .adapters import build_default_adapters
    from .engine import ExecutionMode, run_engine
    from .preflight import run_preflight
    from .state import STATE_ORDER

    if not args.manifest:
        print("ERROR: publish requires --manifest <path> - a real publish never runs against a placeholder identity.", file=sys.stderr)
        return EXIT_USAGE
    if not args.yes:
        print(
            "release.py publish performs REAL public writes once preflight passes. "
            "Refusing to proceed without --yes.",
            file=sys.stderr,
        )
        return EXIT_USAGE

    manifest = rc_manifest.load_rc_manifest(Path(args.manifest))
    if args.version and str(args.version).strip() != manifest["productVersion"]:
        print(
            f"ERROR: Expected version {args.version!r} does not match candidate "
            f"manifest productVersion {manifest['productVersion']!r}.",
            file=sys.stderr,
        )
        return EXIT_FAILED

    readiness = manifest.get("releaseReadiness")
    if readiness != rc_manifest.READINESS_QUALIFIED:
        print(
            f"ERROR: Cannot publish candidate with releaseReadiness={readiness!r}. "
            f"Only {rc_manifest.READINESS_QUALIFIED!r} candidates may be published.",
            file=sys.stderr,
        )
        return EXIT_FAILED
    qual = manifest.get("qualification") or {}
    evidence_ref = qual.get("evidenceRef")
    if not evidence_ref or str(evidence_ref).strip() == "" or evidence_ref == "none":
        print(
            "ERROR: Candidate manifest lacks valid qualification evidenceRef; "
            "cannot publish without qualification evidence.",
            file=sys.stderr,
        )
        return EXIT_FAILED

    repo_root = config.REPO_ROOT
    # The manifest is the release identity authority. ``--version`` above is
    # only an operator/dispatch assertion that must agree with it.
    version = manifest["productVersion"]

    report = run_preflight(
        repo_root=repo_root,
        expected_version=version,
        expected_commit=manifest["sourceCommit"],
        expected_tree=manifest["sourceTree"],
        rc_manifest_path=Path(args.manifest),
        require_qualified=True,
    )
    if not report.passed:
        print("Preflight failed; refusing to publish.", file=sys.stderr)
        _print_json(report.to_json_dict())
        return EXIT_FAILED

    identity = rc_manifest.state_identity(manifest)
    candidate = rc_manifest.candidate_identity(manifest)

    state_path = Path(args.state_file) if args.state_file else default_state_path(repo_root, version)
    state = load_state(state_path)
    if state is None:
        state = new_state(
            version=version,
            source_commit=manifest["sourceCommit"],
            source_tree=manifest["sourceTree"],
            distributions=identity["distributions"],
            images=identity["images"],
            candidate=candidate,
        )
    else:
        ensure_same_version(state, version)
        ensure_same_identity(
            state,
            source_commit=manifest["sourceCommit"],
            source_tree=manifest["sourceTree"],
            distributions=identity["distributions"],
            images=identity["images"],
            candidate=candidate,
        )

    adapters = build_default_adapters(
        dist_dir=args.dist_dir, trusted_publishing=args.trusted_publishing
    )

    def persist(updated_state):
        save_state(state_path, updated_state)

    result = run_engine(
        state,
        manifest,
        mode=ExecutionMode.REAL,
        adapters=adapters,
        persist=persist,
        stop_after=args.until,
    )
    _print_json(result.to_json_dict())
    return EXIT_FAILED if result.stoppedEarly else EXIT_OK


def _cmd_precheck_pypi(args: argparse.Namespace) -> int:
    """Read-only PyPI conflict check against candidate manifest (B4).

    Fails closed if any conflict, hash mismatch, or unverifiable state is
    detected. If --stage-dir is given, stages missing files per variant.
    """
    from . import remote_checks

    manifest = rc_manifest.load_rc_manifest(Path(args.manifest))
    report = remote_checks.precheck_pypi(manifest)

    if args.stage_dir:
        import hashlib
        import shutil

        stage_dir = Path(args.stage_dir)
        dist_dir = Path(args.dist_dir) if args.dist_dir else config.REPO_ROOT / "dist"

        for variant in ("free", "pro"):
            v_report = report[variant]
            v_stage_dir = stage_dir / variant
            v_stage_dir.mkdir(parents=True, exist_ok=True)
            for filename in v_report.get("absent", []):
                src = dist_dir / filename
                if not src.is_file():
                    raise ManifestError(
                        f"PyPI precheck reports {filename} absent on PyPI but wheel file not found in {dist_dir}"
                    )
                content = src.read_bytes()
                sha256 = hashlib.sha256(content).hexdigest()
                expected_sha256 = next(
                    w["sha256"]
                    for w in manifest["distributions"][variant]["wheels"]
                    if w["filename"] == filename
                )
                if sha256 != expected_sha256:
                    raise ManifestError(
                        f"Wheel {filename} SHA-256 mismatch before PyPI upload: expected {expected_sha256}, got {sha256}"
                    )
                shutil.copy2(src, v_stage_dir / filename)

    _print_json(report)
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="release.py",
        description="AP-SRV-070 release orchestrator: preflight, dry-run, resumable "
        "release state, and RC manifest handling for the fixed W6 publication order.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight_parser = subparsers.add_parser("preflight", help="Read-only release preflight checks.")
    preflight_parser.add_argument("--version", default=None, help="Expected product version (default: VERSION file).")
    preflight_parser.add_argument("--commit", default=None, help="Expected exact Git commit.")
    preflight_parser.add_argument("--tree", default=None, help="Expected exact Git tree.")
    preflight_parser.add_argument("--manifest", type=Path, default=None, help="RC manifest path to validate.")
    preflight_parser.add_argument(
        "--require-qualified", action="store_true", default=False,
        help="Require candidate manifest to have releaseReadiness == 'QUALIFIED'.",
    )
    preflight_parser.set_defaults(func=_cmd_preflight)

    dry_run_parser = subparsers.add_parser(
        "dry-run", help="Walk the real release engine with zero writes. Same operation graph as publish."
    )
    dry_run_parser.add_argument("--version", default=None, help="Version to plan for (default: VERSION file).")
    dry_run_parser.add_argument("--state-file", default=None, help="Explicit release-state file path.")
    dry_run_parser.add_argument(
        "--manifest", type=Path, default=None,
        help="RC manifest to plan against (default: an obvious placeholder identity - no RC exists before W5-R02).",
    )
    dry_run_parser.add_argument(
        "--until", default=None, choices=list(STATE_ORDER),
        help="Plan only as far as this state (the same boundary publish uses).",
    )
    dry_run_parser.set_defaults(func=_cmd_dry_run)

    status_parser = subparsers.add_parser("status", help="Show the current resumable release state, if any.")
    status_parser.add_argument("--version", default=None, help="Version to inspect (default: VERSION file).")
    status_parser.add_argument("--state-file", default=None, help="Explicit release-state file path.")
    status_parser.set_defaults(func=_cmd_status)

    manifest_parser = subparsers.add_parser("manifest", help="RC manifest build/validate helpers.")
    manifest_subparsers = manifest_parser.add_subparsers(dest="manifest_command", required=True)

    validate_parser = manifest_subparsers.add_parser("validate", help="Validate an existing RC manifest file.")
    validate_parser.add_argument("path", type=Path)
    validate_parser.set_defaults(func=_cmd_manifest_validate)

    qualify_parser = manifest_subparsers.add_parser(
        "qualify",
        help="Transition an RC manifest to QUALIFIED status.",
    )
    qualify_parser.add_argument("--manifest", required=True, type=Path, help="Path to RC manifest.")
    qualify_parser.add_argument("--evidence-ref", required=True, help="Evidence URL or reference.")
    qualify_parser.add_argument("--context", default=None, help="Optional qualification context description.")
    qualify_parser.add_argument("--timestamp", default=None, help="Optional qualification timestamp ISO8601 UTC.")
    qualify_parser.add_argument("--out", default=None, type=Path, help="Output manifest path (default: overwrite in-place).")
    qualify_parser.set_defaults(func=_cmd_manifest_qualify)

    build_manifest_parser = manifest_subparsers.add_parser(
        "build",
        help="Assemble the canonical RC manifest from a candidate output directory.",
    )
    build_manifest_parser.add_argument(
        "--candidate-dir", required=True, type=Path,
        help="Directory holding build-manifest-<variant>.json, "
             "distribution-<variant>.json and staging-<variant>.json.",
    )
    build_manifest_parser.add_argument("--candidate-id", required=True, help="e.g. W5-RC1 or gh-<run-id>-<attempt>")
    build_manifest_parser.add_argument("--source-tree", required=True)
    build_manifest_parser.add_argument("--qualification-timestamp", required=True)
    build_manifest_parser.add_argument("--qualification-context", required=True)
    build_manifest_parser.add_argument("--qualification-evidence-ref", required=True)
    build_manifest_parser.add_argument(
        "--candidate-run", default=None,
        help="JSON object describing the workflow run that produced the candidate.",
    )
    build_manifest_parser.add_argument(
        "--release-readiness", default=rc_manifest.READINESS_NOT_QUALIFIED, choices=rc_manifest.READINESS_STATES
    )
    build_manifest_parser.add_argument("--out", required=True, type=Path)
    build_manifest_parser.set_defaults(func=_cmd_manifest_build)

    prepare_parser = subparsers.add_parser(
        "prepare-next-version",
        help="Compute the future patch/minor/major version. Read-only unless --apply is given.",
    )
    prepare_group = prepare_parser.add_mutually_exclusive_group()
    prepare_group.add_argument("--minor", action="store_true")
    prepare_group.add_argument("--major", action="store_true")
    prepare_parser.add_argument("--apply", action="store_true", help="Actually write the new VERSION file.")
    prepare_parser.set_defaults(func=_cmd_prepare_next_version)

    precheck_pypi_parser = subparsers.add_parser(
        "precheck-pypi",
        help="Run read-only PyPI precheck against candidate manifest and optionally stage absent files.",
    )
    precheck_pypi_parser.add_argument("--manifest", required=True, type=Path, help="Candidate manifest path.")
    precheck_pypi_parser.add_argument("--dist-dir", type=Path, default=None, help="Directory holding candidate distribution wheels.")
    precheck_pypi_parser.add_argument("--stage-dir", type=Path, default=None, help="Directory where absent wheels will be staged per variant.")
    precheck_pypi_parser.set_defaults(func=_cmd_precheck_pypi)

    publish_parser = subparsers.add_parser(
        "publish", help="Walk the real release engine for real. Requires --manifest and --yes; fails closed on any conflict."
    )
    publish_parser.add_argument("--manifest", type=Path, default=None, required=False, help="The frozen RC manifest to publish (required).")
    publish_parser.add_argument(
        "--version", default=None,
        help="Expected product version (validates that dispatch/operator version matches candidate manifest).",
    )
    publish_parser.add_argument("--yes", action="store_true", help="Required to actually proceed past preflight.")
    publish_parser.add_argument(
        "--dist-dir", type=Path, default=None,
        help="Where the qualified distribution wheels live (default: dist/).",
    )
    publish_parser.add_argument(
        "--state-file", default=None, help="Explicit release-state file path.",
    )
    publish_parser.add_argument(
        "--until", default=None,
        help="Advance the canonical state machine only as far as this state. "
             "Used by the GitHub publish workflow so each job holds only the "
             "credentials its own steps need; the order and every barrier "
             "still come from the one release graph.",
    )
    publish_parser.add_argument(
        "--trusted-publishing", action="store_true",
        help="PyPI uploads are performed by the official OIDC publish action; "
             "the engine verifies them instead of holding a token.",
    )
    publish_parser.set_defaults(func=_cmd_publish)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ReleaseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
