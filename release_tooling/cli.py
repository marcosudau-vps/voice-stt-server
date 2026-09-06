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

from . import config, gitinfo, pipeline, rc_manifest
from .errors import ReleaseError
from .state import (
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
    )
    _print_json(report.to_json_dict())
    return EXIT_OK if report.passed else EXIT_FAILED


def _placeholder_manifest(*, version: str, commit: Optional[str], tree: Optional[str]) -> Dict[str, Any]:
    """A schema-valid but clearly-fake RC manifest for planning purposes,
    used only when the operator has not supplied a real one yet (there is
    no frozen RC before W5-R02). Every identity in it is an obvious
    placeholder - this is never mistaken for a real, W5-R02-qualified
    manifest because ``validate_rc_manifest`` still requires the correct
    shapes, and no placeholder value here could ever match a real remote
    artifact identity."""
    commit = commit or ("0" * 40)
    tree = tree or ("0" * 40)
    return rc_manifest.build_rc_manifest(
        candidate_id="W5-RC0",
        product_version=version,
        source_commit=commit,
        source_tree=tree,
        wheel_path=Path(f"voicestt-{version}-py3-none-any.whl"),
        wheel_sha256="0" * 64,
        sdist_path=Path(f"voicestt-{version}.tar.gz"),
        sdist_sha256="0" * 64,
        kroko_free_fingerprint="unresolved",
        kroko_free_artifact_sha256="0" * 64,
        kroko_pro_fingerprint="unresolved",
        kroko_pro_artifact_sha256="0" * 64,
        free_image_tag=f"{config.image_name_for('free')}:{version}",
        free_image_id="sha256:" + "0" * 64,
        pro_image_tag=f"{config.image_name_for('pro')}:{version}",
        pro_image_id="sha256:" + "0" * 64,
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
        state = new_state(
            version=version,
            source_commit=manifest["sourceCommit"],
            source_tree=manifest["sourceTree"],
            wheel=manifest["wheel"],
            sdist=manifest["sdist"],
            free_image=manifest["images"]["free"],
            pro_image=manifest["images"]["pro"],
        )
    result = pipeline.dry_run(state, manifest)
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
    free_manifest = json.loads(Path(args.free_build_manifest).read_text(encoding="utf-8"))
    pro_manifest = json.loads(Path(args.pro_build_manifest).read_text(encoding="utf-8"))

    if free_manifest["gitCommit"] != pro_manifest["gitCommit"]:
        print(
            "ERROR: free and pro build manifests were built from different commits "
            f"({free_manifest['gitCommit']} != {pro_manifest['gitCommit']})",
            file=sys.stderr,
        )
        return EXIT_FAILED

    manifest = rc_manifest.build_rc_manifest(
        candidate_id=args.candidate_id,
        product_version=free_manifest["voicesttVersion"],
        source_commit=free_manifest["gitCommit"],
        source_tree=args.source_tree,
        wheel_path=Path(free_manifest["voicesttWheel"]["name"]),
        wheel_sha256=free_manifest["voicesttWheel"]["sha256"],
        sdist_path=Path(args.sdist_path),
        sdist_sha256=args.sdist_sha256,
        kroko_free_fingerprint=free_manifest["variants"]["free"]["kroko"]["fingerprint"],
        kroko_free_artifact_sha256=free_manifest["variants"]["free"]["kroko"]["artifact"]["sha256"],
        kroko_pro_fingerprint=pro_manifest["variants"]["pro"]["kroko"]["fingerprint"],
        kroko_pro_artifact_sha256=pro_manifest["variants"]["pro"]["kroko"]["artifact"]["sha256"],
        free_image_tag=free_manifest["variants"]["free"]["image"]["versionTag"],
        free_image_id=free_manifest["variants"]["free"]["imageId"],
        pro_image_tag=pro_manifest["variants"]["pro"]["image"]["versionTag"],
        pro_image_id=pro_manifest["variants"]["pro"]["imageId"],
        oci_version=free_manifest["voicesttVersion"],
        oci_revision=free_manifest["gitCommit"],
        qualification_timestamp_utc=args.qualification_timestamp,
        qualification_context=args.qualification_context,
        qualification_evidence_ref=args.qualification_evidence_ref,
        release_readiness=args.release_readiness,
    )
    rc_manifest.write_rc_manifest(Path(args.out), manifest)
    print(f"Wrote RC manifest: {args.out}")
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
    repo_root = config.REPO_ROOT
    version = manifest["productVersion"]

    report = run_preflight(
        repo_root=repo_root,
        expected_version=version,
        expected_commit=manifest["sourceCommit"],
        expected_tree=manifest["sourceTree"],
        rc_manifest_path=Path(args.manifest),
    )
    if not report.passed:
        print("Preflight failed; refusing to publish.", file=sys.stderr)
        _print_json(report.to_json_dict())
        return EXIT_FAILED

    state_path = default_state_path(repo_root, version)
    state = load_state(state_path)
    if state is None:
        state = new_state(
            version=version,
            source_commit=manifest["sourceCommit"],
            source_tree=manifest["sourceTree"],
            wheel=manifest["wheel"],
            sdist=manifest["sdist"],
            free_image=manifest["images"]["free"],
            pro_image=manifest["images"]["pro"],
        )
    else:
        ensure_same_version(state, version)
        ensure_same_identity(
            state,
            source_commit=manifest["sourceCommit"],
            source_tree=manifest["sourceTree"],
            wheel=manifest["wheel"],
            sdist=manifest["sdist"],
            free_image=manifest["images"]["free"],
            pro_image=manifest["images"]["pro"],
        )

    adapters = build_default_adapters(dist_dir=args.dist_dir)

    def persist(updated_state):
        save_state(state_path, updated_state)

    result = run_engine(state, manifest, mode=ExecutionMode.REAL, adapters=adapters, persist=persist)
    _print_json(result.to_json_dict())
    return EXIT_FAILED if result.stoppedEarly else EXIT_OK


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

    build_manifest_parser = manifest_subparsers.add_parser(
        "build", help="Assemble a canonical RC manifest from Free/Pro build manifests (W5-R02)."
    )
    build_manifest_parser.add_argument("--candidate-id", required=True, help="e.g. W5-RC1")
    build_manifest_parser.add_argument("--free-build-manifest", required=True, type=Path)
    build_manifest_parser.add_argument("--pro-build-manifest", required=True, type=Path)
    build_manifest_parser.add_argument("--source-tree", required=True)
    build_manifest_parser.add_argument("--sdist-path", required=True, type=Path)
    build_manifest_parser.add_argument("--sdist-sha256", required=True)
    build_manifest_parser.add_argument("--qualification-timestamp", required=True)
    build_manifest_parser.add_argument("--qualification-context", required=True)
    build_manifest_parser.add_argument("--qualification-evidence-ref", required=True)
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

    publish_parser = subparsers.add_parser(
        "publish", help="Walk the real release engine for real. Requires --manifest and --yes; fails closed on any conflict."
    )
    publish_parser.add_argument("--manifest", type=Path, default=None, required=False, help="The frozen RC manifest to publish (required).")
    publish_parser.add_argument("--yes", action="store_true", help="Required to actually proceed past preflight.")
    publish_parser.add_argument("--dist-dir", type=Path, default=None, help="Where the qualified wheel/sdist live (default: dist/).")
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
