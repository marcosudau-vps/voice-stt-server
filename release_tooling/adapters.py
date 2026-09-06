"""Real, W6-capable publication adapters (AP-SRV-070 W5-R01-C1).

Each adapter is the one place that knows how to talk to one external
release surface (PyPI, GHCR, Docker Hub, the Git remote, GitHub Releases).
Every adapter exposes exactly two operations:

* ``verify(manifest, state)`` - always read-only, safe to call in a
  dry-run or a real run alike. Returns :data:`remote_checks.ABSENT` or
  :data:`remote_checks.MATCH`, or raises :class:`ConflictError` if a
  conflicting artifact already exists, or :class:`VerificationUnavailableError`
  if the check could not be completed at all (no network, tool missing).
* ``publish(manifest, state)`` - the one real write action. It is never
  invoked by anything in this codebase except ``release_tooling.engine``,
  and only when running in ``ExecutionMode.REAL`` *and* ``verify()`` just
  returned ``ABSENT``.

No adapter ever reads, logs, stores, or returns a credential value. Every
adapter relies on the standard, already-established credential contract of
the underlying tool (twine's ``TWINE_USERNAME``/``TWINE_PASSWORD``/
``TWINE_API_KEY``, Docker's own ``docker login`` session, git's configured
credential helper, and ``gh``'s ``GH_TOKEN``/``GITHUB_TOKEN``) - none of
those values are ever read into this process; they are left for the
subprocess to inherit from its own environment. This is deliberate: it is
the one design that makes "no secret in state/logs/evidence" true by
construction rather than by discipline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Protocol, Sequence

from . import config, gitinfo
from .errors import ConflictError, ReleaseError, VerificationUnavailableError
from .redaction import redact_text
from .remote_checks import (
    ABSENT,
    MATCH,
    CommandResult,
    check_pypi_release,
    check_registry_image,
    default_pypi_fetcher,
)
from .state import ReleaseState


def default_runner(cmd: Sequence[str], *, cwd: Optional[Path] = None) -> CommandResult:
    """The one real subprocess runner every adapter's default wiring uses.

    Deliberately minimal: it never sets, reads, or forwards anything beyond
    the current process environment (so a caller's ``TWINE_PASSWORD``/
    ``GH_TOKEN`` reaches the child process the normal OS way, without this
    function ever holding the value itself), and it never raises on a
    non-zero exit - callers decide what a given exit code means.
    """
    import subprocess

    try:
        completed = subprocess.run(
            [str(part) for part in cmd],
            cwd=str(cwd) if cwd is not None else None,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        # The tool itself is not installed - a "cannot verify" condition
        # for the caller, never a crash, so a missing optional binary
        # degrades a dry-run gracefully instead of aborting it.
        return CommandResult(args=list(cmd), returncode=127, stdout="", stderr=str(exc))
    return CommandResult(
        args=list(cmd),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


class PublicationAdapter(Protocol):
    name: str

    def verify(self, manifest: Dict[str, Any], state: ReleaseState) -> str: ...

    def publish(self, manifest: Dict[str, Any], state: ReleaseState) -> None: ...


# ---------------------------------------------------------------------------
# PyPI
# ---------------------------------------------------------------------------


class PyPIAdapter:
    """Publishes the qualified wheel + sdist to PyPI via Twine.

    Twine (not a hand-rolled upload protocol) reads its own credentials from
    ``TWINE_USERNAME``/``TWINE_PASSWORD`` or ``TWINE_API_KEY`` in the
    process environment; this adapter never reads them.
    """

    name = "pypi"

    def __init__(self, *, dist_dir: Path, runner=default_runner, fetch=default_pypi_fetcher):
        self._dist_dir = Path(dist_dir)
        self._runner = runner
        self._fetch = fetch

    def verify(self, manifest: Dict[str, Any], state: ReleaseState) -> str:
        expected_files = {
            manifest["wheel"]["filename"]: manifest["wheel"]["sha256"],
            manifest["sdist"]["filename"]: manifest["sdist"]["sha256"],
        }
        try:
            return check_pypi_release(
                config.DISTRIBUTION_NAME, manifest["productVersion"], expected_files, fetch=self._fetch
            )
        except ConflictError:
            raise
        except Exception as exc:  # noqa: BLE001 - network/DNS/etc, not a conflict
            raise VerificationUnavailableError(f"could not verify PyPI state: {redact_text(str(exc))}") from exc

    def publish(self, manifest: Dict[str, Any], state: ReleaseState) -> None:
        wheel_path = self._dist_dir / manifest["wheel"]["filename"]
        sdist_path = self._dist_dir / manifest["sdist"]["filename"]
        if not wheel_path.is_file() or not sdist_path.is_file():
            raise ReleaseError(
                f"cannot publish to PyPI: expected local artifact(s) missing under {self._dist_dir} "
                f"({wheel_path.name}, {sdist_path.name})"
            )
        result = self._runner(
            ["twine", "upload", "--non-interactive", "--skip-existing", str(wheel_path), str(sdist_path)]
        )
        if result.returncode != 0:
            raise ReleaseError(f"twine upload failed (exit {result.returncode}): {redact_text(result.stderr.strip())}")


# ---------------------------------------------------------------------------
# GHCR / Docker Hub (shared registry-push logic, different repo roots)
# ---------------------------------------------------------------------------


class _RegistryAdapter:
    """Pushes both the Free and Pro images to one registry for one step.

    The state machine has exactly one ``*_PUBLISHED`` slot per registry
    (not one per variant), so this adapter treats "Free and Pro both
    verified" as the step's ``MATCH`` and re-checks each variant
    independently inside ``publish()`` before pushing it - a variant that
    already succeeded in an earlier, interrupted run is never re-pushed.
    """

    name = "registry"

    def __init__(self, *, repo_root: str, runner=default_runner):
        self._repo_root = repo_root
        self._runner = runner

    def _remote_ref(self, manifest: Dict[str, Any], variant: str) -> str:
        if not self._repo_root:
            # Not configured is a "cannot verify" condition, not a hard
            # operational failure - the engine reports it as an unavailable
            # step rather than crashing the whole dry-run/publish walk.
            raise VerificationUnavailableError(
                f"cannot verify/publish to {self.name}: no repository root configured "
                f"(see release_tooling.config for the required environment variable)"
            )
        image_name = config.image_name_for(variant)
        version = manifest["productVersion"]
        return f"{self._repo_root}/{image_name}:{version}"

    def _variant_status(self, manifest: Dict[str, Any], variant: str) -> str:
        try:
            remote_ref = self._remote_ref(manifest, variant)
            expected = manifest["images"][variant]["imageId"]
            return check_registry_image(remote_ref, expected, runner=self._runner)
        except ConflictError:
            raise
        except VerificationUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise VerificationUnavailableError(
                f"could not verify {self.name} state for variant {variant}: {redact_text(str(exc))}"
            ) from exc

    def verify(self, manifest: Dict[str, Any], state: ReleaseState) -> str:
        statuses = [self._variant_status(manifest, variant) for variant in config.SUPPORTED_VARIANTS]
        return MATCH if all(status == MATCH for status in statuses) else ABSENT

    def publish(self, manifest: Dict[str, Any], state: ReleaseState) -> None:
        for variant in config.SUPPORTED_VARIANTS:
            if self._variant_status(manifest, variant) == MATCH:
                continue  # already published in an earlier, interrupted run - do not re-push
            remote_ref = self._remote_ref(manifest, variant)
            local_ref = manifest["images"][variant]["tag"]
            tag_result = self._runner(["docker", "tag", local_ref, remote_ref])
            if tag_result.returncode != 0:
                raise ReleaseError(f"docker tag {local_ref} -> {remote_ref} failed: {redact_text(tag_result.stderr.strip())}")
            push_result = self._runner(["docker", "push", remote_ref])
            if push_result.returncode != 0:
                raise ReleaseError(f"docker push {remote_ref} failed: {redact_text(push_result.stderr.strip())}")


class GHCRAdapter(_RegistryAdapter):
    name = "ghcr"

    def __init__(self, *, runner=default_runner):
        super().__init__(repo_root=config.ghcr_repo_root(), runner=runner)


class DockerHubAdapter(_RegistryAdapter):
    name = "dockerhub"

    def __init__(self, *, runner=default_runner):
        super().__init__(repo_root=config.dockerhub_repo_root(), runner=runner)


# ---------------------------------------------------------------------------
# Git tag
# ---------------------------------------------------------------------------


class GitTagAdapter:
    """Creates and pushes the release tag. Never invoked before external
    verification: enforced both by the fixed engine order and, defensively,
    by :func:`release_tooling.state.assert_tag_allowed` called here directly
    so the barrier holds even if something calls ``publish()`` out of turn.
    """

    name = "git_tag"

    def __init__(self, *, repo_root: Path, remote: str = config.GIT_REMOTE_NAME, runner=None):
        self._repo_root = Path(repo_root)
        self._remote = remote
        self._runner = runner  # unused; git operations go through gitinfo, kept for interface symmetry

    @staticmethod
    def tag_name(manifest: Dict[str, Any]) -> str:
        return f"v{manifest['productVersion']}"

    def verify(self, manifest: Dict[str, Any], state: ReleaseState) -> str:
        tag = self.tag_name(manifest)
        expected_commit = manifest["sourceCommit"]
        try:
            local_commit = gitinfo.local_tag_commit(self._repo_root, tag)
            remote_commit = gitinfo.remote_tag_commit(self._repo_root, self._remote, tag)
        except gitinfo.GitError as exc:
            raise VerificationUnavailableError(f"could not check tag {tag!r}: {redact_text(str(exc))}") from exc

        existing = remote_commit or local_commit
        if existing is None:
            return ABSENT
        if existing != expected_commit:
            raise ConflictError(
                f"tag {tag!r} already exists at commit {existing}, expected {expected_commit}"
            )
        return MATCH

    def publish(self, manifest: Dict[str, Any], state: ReleaseState) -> None:
        from .state import assert_tag_allowed

        assert_tag_allowed(state)
        tag = self.tag_name(manifest)
        gitinfo.create_tag(self._repo_root, tag, manifest["sourceCommit"])
        gitinfo.push_tag(self._repo_root, self._remote, tag)


# ---------------------------------------------------------------------------
# GitHub Release
# ---------------------------------------------------------------------------


class GitHubReleaseAdapter:
    """Creates the GitHub Release via the ``gh`` CLI, which reads
    ``GH_TOKEN``/``GITHUB_TOKEN`` from the environment itself - this adapter
    never touches that value. Never invoked before ``TAGGED``: enforced both
    by the fixed engine order and defensively here.
    """

    name = "github_release"

    def __init__(self, *, repo_slug: str = config.GITHUB_REPO_SLUG, notes_path: Optional[Path] = None, runner=default_runner):
        self._repo_slug = repo_slug
        self._notes_path = Path(notes_path) if notes_path else None
        self._runner = runner

    @staticmethod
    def tag_name(manifest: Dict[str, Any]) -> str:
        return f"v{manifest['productVersion']}"

    def verify(self, manifest: Dict[str, Any], state: ReleaseState) -> str:
        tag = self.tag_name(manifest)
        result = self._runner(
            ["gh", "release", "view", tag, "--repo", self._repo_slug, "--json", "tagName,name,isDraft"]
        )
        if result.returncode != 0:
            stderr = result.stderr.lower()
            if "release not found" in stderr or "404" in stderr:
                return ABSENT
            raise VerificationUnavailableError(
                f"could not verify GitHub Release {tag!r}: {redact_text(result.stderr.strip())}"
            )
        try:
            payload = json.loads(result.stdout)
        except ValueError as exc:
            raise VerificationUnavailableError(
                f"gh release view returned non-JSON output for {tag!r}"
            ) from exc
        if payload.get("tagName") != tag:
            raise ConflictError(
                f"GitHub Release for {tag!r} exists but is bound to tag {payload.get('tagName')!r}"
            )
        return MATCH

    def publish(self, manifest: Dict[str, Any], state: ReleaseState) -> None:
        from .state import assert_github_release_allowed

        assert_github_release_allowed(state)
        tag = self.tag_name(manifest)
        cmd = ["gh", "release", "create", tag, "--repo", self._repo_slug, "--title", manifest["productVersion"]]
        if self._notes_path is not None:
            cmd += ["--notes-file", str(self._notes_path)]
        else:
            cmd += ["--notes", f"AP-SRV-070 release {manifest['productVersion']}"]
        result = self._runner(cmd)
        if result.returncode != 0:
            raise ReleaseError(f"gh release create failed (exit {result.returncode}): {redact_text(result.stderr.strip())}")


# ---------------------------------------------------------------------------
# External / final verification (read-only aggregate barriers)
# ---------------------------------------------------------------------------


class AggregateVerificationAdapter:
    """A read-only barrier that requires every wrapped adapter to already be
    ``MATCH``. Never writes anything - ``publish()`` is a documented no-op
    the engine only calls when ``verify()`` unexpectedly still says
    ``ABSENT`` on the real path (which should never legitimately happen
    given the fixed step order, and is treated as a hard stop, not silently
    retried - see ``release_tooling.engine``).
    """

    def __init__(self, *, name: str, sub_adapters: Sequence[PublicationAdapter]):
        self.name = name
        self._sub_adapters = list(sub_adapters)

    def verify(self, manifest: Dict[str, Any], state: ReleaseState) -> str:
        for adapter in self._sub_adapters:
            status = adapter.verify(manifest, state)  # propagates ConflictError/VerificationUnavailableError
            if status != MATCH:
                return ABSENT
        return MATCH

    def publish(self, manifest: Dict[str, Any], state: ReleaseState) -> None:
        raise ReleaseError(
            f"{self.name} has no publish action of its own - it only aggregates other adapters' verify() results"
        )


def build_default_adapters(
    *,
    dist_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None,
    notes_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """The real, W6-capable adapter bundle keyed by ``StepDefinition.key``.

    Both ``release.py dry-run`` and ``release.py publish`` build the bundle
    this way; the only thing that ever differs between them is the
    :class:`~release_tooling.engine.ExecutionMode` passed to
    :func:`release_tooling.engine.run_engine`, which decides whether any
    adapter's ``publish()`` is ever actually called.
    """
    dist_dir = Path(dist_dir) if dist_dir is not None else (config.REPO_ROOT / "dist")
    repo_root = Path(repo_root) if repo_root is not None else config.REPO_ROOT

    pypi = PyPIAdapter(dist_dir=dist_dir)
    ghcr = GHCRAdapter()
    dockerhub = DockerHubAdapter()
    git_tag = GitTagAdapter(repo_root=repo_root)
    github_release = GitHubReleaseAdapter(notes_path=notes_path)
    external_verification = AggregateVerificationAdapter(
        name="external_verification", sub_adapters=[pypi, ghcr, dockerhub]
    )
    final_verification = AggregateVerificationAdapter(
        name="final_verification", sub_adapters=[pypi, ghcr, dockerhub, git_tag, github_release]
    )
    return {
        "pypi": pypi,
        "ghcr": ghcr,
        "dockerhub": dockerhub,
        "external_verification": external_verification,
        "git_tag": git_tag,
        "github_release": github_release,
        "final_verification": final_verification,
    }


__all__ = [
    "default_runner",
    "PublicationAdapter",
    "PyPIAdapter",
    "GHCRAdapter",
    "DockerHubAdapter",
    "GitTagAdapter",
    "GitHubReleaseAdapter",
    "AggregateVerificationAdapter",
    "build_default_adapters",
]
