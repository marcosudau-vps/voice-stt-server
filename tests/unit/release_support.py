"""Shared fixtures for the AP-SRV-070 W5-R04 release-tooling tests.

One place that knows what a *valid* candidate looks like, so a schema change
does not have to be re-typed into a dozen test modules, and so every test that
wants "a valid manifest with one thing wrong" starts from something that is
genuinely valid.

Nothing here touches the network, Docker, git, PyPI or a registry. Every
external interaction in these tests goes through an injected fake runner or
fetcher, so the whole suite is offline and side-effect free - which is itself
part of the contract: a release test must never publish anything.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from release_tooling import rc_manifest  # noqa: E402
from release_tooling.remote_checks import CommandResult  # noqa: E402
from release_tooling.state import ReleaseState, STATE_ORDER, advance, new_state  # noqa: E402

VERSION = "2.0.0"
COMMIT = "934e3be7c78aa9358f9b42b9fa4dc282bed54d6c"
TREE = "2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb"

FREE_DIGEST = "sha256:" + "a1" * 32
PRO_DIGEST = "sha256:" + "b2" * 32
FREE_WHEEL_SHA = "c3" * 32
FREE_WHEEL_WIN_SHA = "c5" * 32
PRO_WHEEL_SHA = "d4" * 32
PRO_WHEEL_WIN_SHA = "d6" * 32
KROKO_FREE_SHA = "e5" * 32
KROKO_PRO_SHA = "f6" * 32

FREE_WHEEL = "voice_stt_server-2.0.0-cp312-cp312-linux_x86_64.whl"
FREE_WHEEL_WIN = "voice_stt_server-2.0.0-cp312-cp312-win_amd64.whl"
PRO_WHEEL = "voice_stt_server_pro-2.0.0-cp312-cp312-linux_x86_64.whl"
PRO_WHEEL_WIN = "voice_stt_server_pro-2.0.0-cp312-cp312-win_amd64.whl"

STAGING_ROOT = "ghcr.io/marcosudau-vps"
DOCKERHUB_ROOT = "marcosudau"
GHCR_ROOT = "ghcr.io/marcosudau-vps"


def make_manifest(**overrides: Any) -> Dict[str, Any]:
    """A complete, valid schema-v2 RC manifest."""
    manifest = rc_manifest.build_rc_manifest(
        candidate_id="gh-12345-1",
        product_version=VERSION,
        source_commit=COMMIT,
        source_tree=TREE,
        distributions={
            "free": {
                "name": "voice-stt-server",
                "krokoVariant": "free",
                "krokoFingerprint": "578d6c898adac1b1",
                "krokoArtifactSha256": KROKO_FREE_SHA,
                "wheels": [
                    {
                        "filename": FREE_WHEEL,
                        "sha256": FREE_WHEEL_SHA,
                        "pythonTag": "cp312",
                        "abiTag": "cp312",
                        "platformTag": "linux_x86_64",
                        "krokoFingerprint": "578d6c898adac1b1",
                        "krokoArtifactSha256": KROKO_FREE_SHA,
                    },
                    {
                        "filename": FREE_WHEEL_WIN,
                        "sha256": FREE_WHEEL_WIN_SHA,
                        "pythonTag": "cp312",
                        "abiTag": "cp312",
                        "platformTag": "win_amd64",
                        "krokoFingerprint": "578d6c898adac1b1",
                        "krokoArtifactSha256": KROKO_FREE_SHA,
                    },
                ],
            },
            "pro": {
                "name": "voice-stt-server-pro",
                "krokoVariant": "pro",
                "krokoFingerprint": "36b440630c0a9475",
                "krokoArtifactSha256": KROKO_PRO_SHA,
                "wheels": [
                    {
                        "filename": PRO_WHEEL,
                        "sha256": PRO_WHEEL_SHA,
                        "pythonTag": "cp312",
                        "abiTag": "cp312",
                        "platformTag": "linux_x86_64",
                        "krokoFingerprint": "36b440630c0a9475",
                        "krokoArtifactSha256": KROKO_PRO_SHA,
                    },
                    {
                        "filename": PRO_WHEEL_WIN,
                        "sha256": PRO_WHEEL_WIN_SHA,
                        "pythonTag": "cp312",
                        "abiTag": "cp312",
                        "platformTag": "win_amd64",
                        "krokoFingerprint": "36b440630c0a9475",
                        "krokoArtifactSha256": KROKO_PRO_SHA,
                    },
                ],
            },
        },
        images={
            "free": {
                "tag": f"voice-stt-server:{VERSION}",
                "digest": FREE_DIGEST,
                "staging": f"{STAGING_ROOT}/voice-stt-server-staging@{FREE_DIGEST}",
            },
            "pro": {
                "tag": f"voice-stt-server-pro:{VERSION}",
                "digest": PRO_DIGEST,
                "staging": f"{STAGING_ROOT}/voice-stt-server-pro-staging@{PRO_DIGEST}",
            },
        },
        oci_version=VERSION,
        oci_revision=COMMIT,
        candidate_run={"runId": "12345", "runAttempt": "1", "environment": "github-actions"},
        qualification_timestamp_utc="2026-09-08T00:00:00Z",
        qualification_context="unit test",
        qualification_evidence_ref="W5-R04",
        release_readiness=overrides.pop(
            "release_readiness", overrides.pop("releaseReadiness", rc_manifest.READINESS_QUALIFIED)
        ),
    )
    manifest.update(overrides)
    return manifest


def make_state(state_name: str = "PREPARED", manifest: Optional[Dict[str, Any]] = None) -> ReleaseState:
    """A release state bound to ``manifest``, advanced to ``state_name``."""
    manifest = manifest or make_manifest()
    identity = rc_manifest.state_identity(manifest)
    state = new_state(
        version=manifest["productVersion"],
        source_commit=manifest["sourceCommit"],
        source_tree=manifest["sourceTree"],
        distributions=identity["distributions"],
        images=identity["images"],
        candidate=rc_manifest.candidate_identity(manifest),
    )
    for target in STATE_ORDER[1:STATE_ORDER.index(state_name) + 1]:
        state = advance(state, target)
    return state


class RecordingRunner:
    """A fake subprocess runner that records every command it is asked to run.

    Responses are matched by a substring of the joined command line, so a test
    can say "any imagetools inspect of this ref returns that digest" without
    reproducing the exact argument vector. Anything unmatched returns the
    configured default, which by default is a registry "not found" - the safe
    ABSENT answer.
    """

    ABSENT_STDERR = "ERROR: docker.io/x: not found"

    def __init__(
        self,
        responses: Optional[Sequence[Any]] = None,
        default: Optional[CommandResult] = None,
    ):
        self.responses = list(responses or [])
        self.default = default
        self.calls: List[List[str]] = []

    def __call__(self, cmd: Sequence[str], **kwargs: Any) -> CommandResult:
        parts = [str(part) for part in cmd]
        self.calls.append(parts)
        joined = " ".join(parts)
        for needle, result in self.responses:
            if needle in joined:
                return result
        if self.default is not None:
            return self.default
        # A read-only probe of something that does not exist is the ABSENT
        # answer; anything else (a push, a promotion, a tag) succeeds. Modelling
        # write commands as failures would make every publish test assert on an
        # error path instead of on the command that was actually issued.
        if "inspect" in joined or "release view" in joined:
            return CommandResult(args=parts, returncode=1, stdout="", stderr=self.ABSENT_STDERR)
        return CommandResult(args=parts, returncode=0, stdout="", stderr="")

    # -- assertions the tests share -------------------------------------

    @property
    def commands(self) -> List[str]:
        return [" ".join(call) for call in self.calls]

    def assert_no_writes(self, testcase) -> None:
        """No command may mutate a remote or the repository."""
        forbidden = (
            "docker push",
            "docker buildx imagetools create",
            "git tag",
            "git push",
            "gh release create",
            "twine upload",
        )
        for command in self.commands:
            for needle in forbidden:
                testcase.assertNotIn(
                    needle, command, f"a write command escaped: {command!r}"
                )


def ok(stdout: str = "") -> CommandResult:
    return CommandResult(args=[], returncode=0, stdout=stdout, stderr="")


def absent() -> CommandResult:
    return CommandResult(args=[], returncode=1, stdout="", stderr=RecordingRunner.ABSENT_STDERR)


def failed(stderr: str, returncode: int = 1) -> CommandResult:
    """A command that failed for a reason other than "the tag is absent"."""
    return CommandResult(args=[], returncode=returncode, stdout="", stderr=stderr)


def digest_response(digest: str) -> CommandResult:
    return ok(digest + "\n")


def pypi_fetcher(published: Optional[Dict[str, Dict[str, str]]] = None):
    """A fake PyPI JSON fetcher.

    ``published`` maps ``project`` -> ``{filename: sha256}``. A project that is
    absent from the mapping is reported as not published at all (the ABSENT
    case); a project that is present is reported with exactly those files
    using the official release-specific PyPI JSON API shape (info and top-level urls).
    """
    published = published or {}

    def fetch(url: str) -> Optional[dict]:
        # https://pypi.org/pypi/<project>/<version>/json
        parts = url.rstrip("/").split("/")
        project, version = parts[-3], parts[-2]
        files = published.get(project)
        if files is None:
            return None
        return {
            "info": {"name": project, "version": version},
            "urls": [
                {"filename": name, "digests": {"sha256": sha}}
                for name, sha in files.items()
            ],
        }

    return fetch


__all__ = [
    "VERSION",
    "COMMIT",
    "TREE",
    "FREE_DIGEST",
    "PRO_DIGEST",
    "FREE_WHEEL",
    "FREE_WHEEL_WIN",
    "PRO_WHEEL",
    "PRO_WHEEL_WIN",
    "FREE_WHEEL_SHA",
    "FREE_WHEEL_WIN_SHA",
    "PRO_WHEEL_SHA",
    "PRO_WHEEL_WIN_SHA",
    "DOCKERHUB_ROOT",
    "GHCR_ROOT",
    "STAGING_ROOT",
    "make_manifest",
    "make_state",
    "RecordingRunner",
    "ok",
    "absent",
    "failed",
    "digest_response",
    "pypi_fetcher",
]
