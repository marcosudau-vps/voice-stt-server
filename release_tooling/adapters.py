"""Real, publication-capable release adapters (AP-SRV-070 W5-R04).

Each adapter is the one place that knows how to talk to one external release
surface (PyPI, Docker Hub, GHCR, the movable aliases, the Git remote, GitHub
Releases). Every adapter exposes exactly two operations:

* ``verify(manifest, state)`` - always read-only, safe to call in a dry-run or
  a real run alike. Returns :data:`remote_checks.ABSENT` or
  :data:`remote_checks.MATCH`, or raises :class:`ConflictError` if a
  conflicting artifact already exists, or
  :class:`VerificationUnavailableError` if the check could not be completed at
  all (no network, tool missing, unconfigured registry).
* ``publish(manifest, state)`` - the one real write action. It is never invoked
  by anything in this codebase except ``release_tooling.engine``, and only when
  running in ``ExecutionMode.REAL`` *and* ``verify()`` just returned ``ABSENT``.

No adapter ever reads, logs, stores, or returns a credential value. Each relies
on the already-established credential contract of the underlying tool (Docker's
own ``docker login`` session, git's configured credential helper, ``gh``'s
``GH_TOKEN``/``GITHUB_TOKEN``, and - on the GitHub path - PyPI Trusted
Publishing, where no token exists at all). None of those values is ever read
into this process; they are left for the subprocess to inherit from its own
environment. That is what makes "no secret in state/logs/evidence" true by
construction rather than by discipline.

Two W5-R04 properties are worth stating explicitly, because they are what make
"publication consumes the qualified bytes" real rather than aspirational:

* **Nothing here ever builds an image.** Docker Hub publication promotes the
  qualified private staging manifest by digest; GHCR publication promotes the
  *Docker Hub* manifest by digest. There is no second production build
  anywhere in the graph.
* **Every irreversible public write asserts the tag barrier itself**
  (``assert_public_publication_allowed``), so "the Git tag exists before the
  first public artifact" holds even if an adapter is ever driven by something
  other than the engine.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Tuple

from . import aliases as alias_rules
from . import config, gitinfo, rc_manifest
from .errors import ConflictError, ReleaseError, VerificationUnavailableError
from .redaction import redact_text
from .remote_checks import (
    ABSENT,
    MATCH,
    CommandResult,
    check_pypi_release,
    check_registry_alias,
    check_registry_image,
    default_pypi_fetcher,
)
from .state import (
    ReleaseState,
    assert_aliases_allowed,
    assert_github_release_allowed,
    assert_public_publication_allowed,
    assert_tag_allowed,
)

VARIANTS = rc_manifest.VARIANTS


def default_runner(cmd: Sequence[str], *, cwd: Optional[Path] = None) -> CommandResult:
    """The one real subprocess runner every adapter's default wiring uses.

    Deliberately minimal: it never sets, reads, or forwards anything beyond the
    current process environment (so a caller's ``GH_TOKEN`` reaches the child
    process the normal OS way without this function ever holding the value),
    and it never raises on a non-zero exit - callers decide what a given exit
    code means.
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
        # The tool itself is not installed - a "cannot verify" condition for
        # the caller, never a crash, so a missing optional binary degrades a
        # dry-run gracefully instead of aborting it.
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
# PyPI - two complete alternative distributions
# ---------------------------------------------------------------------------


class TwineUploader:
    """Uploads one distribution's wheels with Twine (local operator path).

    Twine reads its own credentials from ``TWINE_USERNAME``/``TWINE_PASSWORD``
    or ``TWINE_API_KEY`` in the process environment; this class never reads
    them.
    """

    name = "twine"

    def __init__(self, *, dist_dir: Path, runner=default_runner):
        self._dist_dir = Path(dist_dir)
        self._runner = runner

    def upload(self, distribution: str, filenames: Sequence[str]) -> None:
        paths = [self._dist_dir / name for name in filenames]
        missing = [str(path) for path in paths if not path.is_file()]
        if missing:
            raise ReleaseError(
                f"cannot publish {distribution} to PyPI: qualified artifact(s) "
                f"missing under {self._dist_dir}: {missing}"
            )
        result = self._runner(
            ["twine", "upload", "--non-interactive", "--skip-existing", *[str(p) for p in paths]]
        )
        if result.returncode != 0:
            raise ReleaseError(
                f"twine upload of {distribution} failed (exit {result.returncode}): "
                f"{redact_text(result.stderr.strip())}"
            )


class ExternalUploader:
    """The GitHub Trusted-Publishing boundary (AP-SRV-070 W5-R04, section 17).

    Under PyPI Trusted Publishing the upload is performed by the official
    ``pypa/gh-action-pypi-publish`` action using a short-lived OIDC token that
    this process deliberately never sees and could not use. So the release
    engine does not *perform* the PyPI write on that path - it **verifies** it.

    That keeps the state machine authoritative rather than decorative: the
    engine advances to ``PYPI_PUBLISHED`` only after its own read-only check
    confirms the exact expected filenames and SHA-256 hashes are really on
    PyPI. An action that exits 0 without producing them advances nothing, and
    this uploader's ``upload()`` refuses loudly instead of silently trying some
    other credential path.
    """

    name = "external"

    def __init__(self, executor: str = "pypa/gh-action-pypi-publish"):
        self._executor = executor

    def upload(self, distribution: str, filenames: Sequence[str]) -> None:
        raise ReleaseError(
            f"{distribution} is not present on PyPI, and this release run is "
            f"configured for Trusted Publishing: the upload must be performed "
            f"by {self._executor} before the release engine can verify and "
            f"record it. Refusing to fall back to any other credential path."
        )


class PyPIAdapter:
    """The aggregate PyPI step over **both** public distributions.

    ``voice-stt-server`` and ``voice-stt-server-pro`` are two complete
    alternative distributions, each embedding a different native Kroko runtime.
    ``PYPI_PUBLISHED`` therefore means "both are published and both verify",
    never "one of them worked".

    Resume falls out of that definition: each distribution is checked
    independently inside ``publish()``, so a run where Free succeeded and Pro
    failed uploads only Pro on the next attempt - and never republishes or
    bumps a version to work around the partial failure.
    """

    name = "pypi"

    def __init__(self, *, uploader, fetch=default_pypi_fetcher):
        self._uploader = uploader
        self._fetch = fetch

    def _variant_status(self, manifest: Dict[str, Any], variant: str) -> str:
        distribution = manifest["distributions"][variant]["name"]
        expected_files = rc_manifest.expected_pypi_files(manifest, variant)
        try:
            return check_pypi_release(
                distribution, manifest["productVersion"], expected_files, fetch=self._fetch
            )
        except ConflictError:
            raise
        except Exception as exc:  # noqa: BLE001 - network/DNS/etc, not a conflict
            raise VerificationUnavailableError(
                f"could not verify PyPI state for {distribution}: {redact_text(str(exc))}"
            ) from exc

    def verify(self, manifest: Dict[str, Any], state: ReleaseState) -> str:
        statuses = [self._variant_status(manifest, variant) for variant in VARIANTS]
        return MATCH if all(status == MATCH for status in statuses) else ABSENT

    def publish(self, manifest: Dict[str, Any], state: ReleaseState) -> None:
        assert_public_publication_allowed(state, "PyPI")
        for variant in VARIANTS:
            if self._variant_status(manifest, variant) == MATCH:
                continue  # already published in an earlier, interrupted run
            distribution = manifest["distributions"][variant]["name"]
            filenames = sorted(rc_manifest.expected_pypi_files(manifest, variant))
            self._uploader.upload(distribution, filenames)


# ---------------------------------------------------------------------------
# Registries - exact manifest promotion, never a second build
# ---------------------------------------------------------------------------


SourceRefResolver = Callable[[Dict[str, Any], str], str]


class _RegistryPromotionAdapter:
    """Promotes the qualified OCI manifest of both variants into one registry.

    The state machine has exactly one ``*_PUBLISHED`` slot per registry (not
    one per variant), so "Free and Pro both verified" is this step's ``MATCH``.
    Each variant is re-checked independently inside ``publish()``, so a variant
    that already succeeded in an interrupted run is never re-promoted.

    Promotion uses ``docker buildx imagetools create``, which copies an
    existing manifest by digest between repositories/registries. It never
    rebuilds, never re-layers, and never invents a new identity - which is
    exactly why the digest recorded at qualification is still the digest that
    ends up published.
    """

    def __init__(
        self,
        *,
        name: str,
        repo_root: str,
        source_ref: SourceRefResolver,
        runner=default_runner,
    ):
        self.name = name
        self._repo_root = repo_root
        self._source_ref = source_ref
        self._runner = runner

    def _remote_ref(self, manifest: Dict[str, Any], variant: str) -> str:
        if not self._repo_root:
            raise VerificationUnavailableError(
                f"cannot verify/publish to {self.name}: no repository root is "
                f"configured (see release_tooling.config)"
            )
        image_name = config.image_name_for(variant)
        version = alias_rules.exact_tag_for(manifest["productVersion"])
        return f"{self._repo_root}/{image_name}:{version}"

    def _variant_status(self, manifest: Dict[str, Any], variant: str) -> str:
        remote_ref = self._remote_ref(manifest, variant)
        expected = rc_manifest.expected_image_digest(manifest, variant)
        try:
            return check_registry_image(remote_ref, expected or "", runner=self._runner)
        except (ConflictError, VerificationUnavailableError):
            raise
        except Exception as exc:  # noqa: BLE001 - network/DNS/etc, not a conflict
            raise VerificationUnavailableError(
                f"could not verify {self.name} state for variant {variant}: "
                f"{redact_text(str(exc))}"
            ) from exc

    def verify(self, manifest: Dict[str, Any], state: ReleaseState) -> str:
        statuses = [self._variant_status(manifest, variant) for variant in VARIANTS]
        return MATCH if all(status == MATCH for status in statuses) else ABSENT

    def publish(self, manifest: Dict[str, Any], state: ReleaseState) -> None:
        assert_public_publication_allowed(state, self.name)
        for variant in VARIANTS:
            if self._variant_status(manifest, variant) == MATCH:
                continue  # already promoted in an earlier, interrupted run
            remote_ref = self._remote_ref(manifest, variant)
            source = self._source_ref(manifest, variant)
            result = self._runner(
                ["docker", "buildx", "imagetools", "create", "--tag", remote_ref, source]
            )
            if result.returncode != 0:
                raise ReleaseError(
                    f"{self.name} manifest promotion {source} -> {remote_ref} failed "
                    f"(exit {result.returncode}): {redact_text(result.stderr.strip())}"
                )


def _staging_source_ref(manifest: Dict[str, Any], variant: str) -> str:
    """The digest-pinned private staging reference of the qualified image."""
    reference = rc_manifest.staging_reference(manifest, variant)
    if not reference:
        raise VerificationUnavailableError(
            f"the candidate manifest records no staging reference for variant "
            f"{variant!r}; publication cannot locate the qualified image"
        )
    return reference


class DockerHubAdapter(_RegistryPromotionAdapter):
    """Publishes the exact Free/Pro images to Docker Hub *first*.

    Docker Hub is the mandatory first public registry: GHCR is then a
    promotion of exactly what Docker Hub received, which is what makes the two
    registries provably identical rather than independently built.
    """

    def __init__(self, *, repo_root: Optional[str] = None, runner=default_runner):
        super().__init__(
            name="dockerhub",
            repo_root=repo_root if repo_root is not None else config.dockerhub_repo_root(),
            source_ref=_staging_source_ref,
            runner=runner,
        )


class GHCRAdapter(_RegistryPromotionAdapter):
    """Promotes the exact Docker Hub manifests to GHCR by digest."""

    def __init__(
        self,
        *,
        repo_root: Optional[str] = None,
        dockerhub_root: Optional[str] = None,
        runner=default_runner,
    ):
        self._dockerhub_root = (
            dockerhub_root if dockerhub_root is not None else config.dockerhub_repo_root()
        )
        super().__init__(
            name="ghcr",
            repo_root=repo_root if repo_root is not None else config.ghcr_repo_root(),
            source_ref=self._dockerhub_source_ref,
            runner=runner,
        )

    def _dockerhub_source_ref(self, manifest: Dict[str, Any], variant: str) -> str:
        if not self._dockerhub_root:
            raise VerificationUnavailableError(
                "cannot promote to GHCR: the Docker Hub repository root is not "
                "configured, so the source manifest cannot be addressed"
            )
        digest = rc_manifest.expected_image_digest(manifest, variant)
        if not digest:
            raise VerificationUnavailableError(
                f"the candidate manifest records no image digest for variant {variant!r}"
            )
        return f"{self._dockerhub_root}/{config.image_name_for(variant)}@{digest}"


# ---------------------------------------------------------------------------
# Movable aliases
# ---------------------------------------------------------------------------


class AliasAdapter:
    """Moves the SemVer aliases in both registries onto the verified digests.

    Aliases are the only mutable part of a release, so this step is the one
    that most needs its barrier: it runs strictly after ``EXTERNAL_VERIFIED``,
    which means every exact Free and Pro artifacts has already been verified in
    both registries. ``latest`` therefore cannot point at a release candidate,
    a failed release or a half-published one.

    An alias that currently points elsewhere is *not* a conflict - moving it is
    the point - so this step's ``verify()`` treats "not yet on the expected
    digest" as ``ABSENT`` and is idempotent on a resume.
    """

    name = "aliases"

    def __init__(self, *, registry_roots: Optional[Dict[str, str]] = None, runner=default_runner):
        self._registry_roots = (
            dict(registry_roots)
            if registry_roots is not None
            else {
                "dockerhub": config.dockerhub_repo_root(),
                "ghcr": config.ghcr_repo_root(),
            }
        )
        self._runner = runner

    def _targets(self, manifest: Dict[str, Any]) -> List[Tuple[str, str, str]]:
        """``(alias_ref, source_ref, digest)`` for every alias that must exist."""
        version = manifest["productVersion"]
        alias_tags = alias_rules.alias_tags_for(version)
        targets: List[Tuple[str, str, str]] = []
        for registry, root in sorted(self._registry_roots.items()):
            if not root:
                raise VerificationUnavailableError(
                    f"cannot verify/publish aliases: the {registry} repository "
                    f"root is not configured"
                )
            for variant in VARIANTS:
                digest = rc_manifest.expected_image_digest(manifest, variant)
                if not digest:
                    raise VerificationUnavailableError(
                        f"the candidate manifest records no image digest for "
                        f"variant {variant!r}"
                    )
                image = config.image_name_for(variant)
                source = f"{root}/{image}@{digest}"
                for alias in alias_tags:
                    targets.append((f"{root}/{image}:{alias}", source, digest))
        return targets

    def verify(self, manifest: Dict[str, Any], state: ReleaseState) -> str:
        targets = self._targets(manifest)
        if not targets:
            # A pre-release owns no aliases at all; there is nothing to do and
            # nothing to wait for, so the step is trivially satisfied.
            return MATCH
        for alias_ref, _source, digest in targets:
            if check_registry_alias(alias_ref, digest, runner=self._runner) != MATCH:
                return ABSENT
        return MATCH

    def publish(self, manifest: Dict[str, Any], state: ReleaseState) -> None:
        assert_aliases_allowed(state)
        for alias_ref, source, digest in self._targets(manifest):
            if check_registry_alias(alias_ref, digest, runner=self._runner) == MATCH:
                continue  # already pointing at the verified digest
            result = self._runner(
                ["docker", "buildx", "imagetools", "create", "--tag", alias_ref, source]
            )
            if result.returncode != 0:
                raise ReleaseError(
                    f"alias update {source} -> {alias_ref} failed "
                    f"(exit {result.returncode}): {redact_text(result.stderr.strip())}"
                )


# ---------------------------------------------------------------------------
# Git tag
# ---------------------------------------------------------------------------


class GitTagAdapter:
    """Creates and pushes the release tag - now the *first* publishing step.

    The tag must exist before the first irreversible public package/registry
    write, so that a partially published version always has an immutable source
    anchor. ``assert_tag_allowed`` is asserted here directly as well as being
    enforced by the engine's fixed order.

    The remote tag is the completion authority. A correct local tag left behind
    by a failed push is resumable input, but it is not ``MATCH`` until the
    remote tag exists and resolves to the expected commit.
    """

    name = "git_tag"

    def __init__(self, *, repo_root: Path, remote: str = config.GIT_REMOTE_NAME, runner=None):
        self._repo_root = Path(repo_root)
        self._remote = remote
        self._runner = runner  # unused; git operations go through gitinfo

    @staticmethod
    def tag_name(manifest: Dict[str, Any]) -> str:
        return alias_rules.git_tag_for(manifest["productVersion"])

    def _tag_commits(self, manifest: Dict[str, Any]) -> Tuple[str, str, Optional[str], Optional[str]]:
        tag = self.tag_name(manifest)
        expected_commit = manifest["sourceCommit"]
        try:
            local_commit = gitinfo.local_tag_commit(self._repo_root, tag)
            remote_commit = gitinfo.remote_tag_commit(self._repo_root, self._remote, tag)
        except gitinfo.GitError as exc:
            raise VerificationUnavailableError(
                f"could not check tag {tag!r}: {redact_text(str(exc))}"
            ) from exc

        if local_commit is not None and local_commit != expected_commit:
            raise ConflictError(
                f"local tag {tag!r} points at commit {local_commit}, expected {expected_commit}"
            )
        if remote_commit is not None and remote_commit != expected_commit:
            raise ConflictError(
                f"remote tag {tag!r} points at commit {remote_commit}, expected {expected_commit}"
            )
        return tag, expected_commit, local_commit, remote_commit

    def verify(self, manifest: Dict[str, Any], state: ReleaseState) -> str:
        _tag, _expected_commit, _local_commit, remote_commit = self._tag_commits(manifest)
        return MATCH if remote_commit is not None else ABSENT

    def publish(self, manifest: Dict[str, Any], state: ReleaseState) -> None:
        assert_tag_allowed(state)
        tag, expected_commit, local_commit, remote_commit = self._tag_commits(manifest)
        if remote_commit is not None:
            return
        if local_commit is None:
            gitinfo.create_tag(self._repo_root, tag, expected_commit)
        gitinfo.push_tag(self._repo_root, self._remote, tag)


# ---------------------------------------------------------------------------
# GitHub Release
# ---------------------------------------------------------------------------


class GitHubReleaseAdapter:
    """Creates the GitHub Release via the ``gh`` CLI - the last public marker.

    ``gh`` reads ``GH_TOKEN``/``GITHUB_TOKEN`` from the environment itself;
    this adapter never touches that value. It is never invoked before every
    exact artifact and every alias is published and verified: enforced by the
    engine's fixed order and defensively by ``assert_github_release_allowed``.
    """

    name = "github_release"

    def __init__(
        self,
        *,
        repo_slug: str = config.GITHUB_REPO_SLUG,
        notes_path: Optional[Path] = None,
        runner=default_runner,
    ):
        self._repo_slug = repo_slug
        self._notes_path = Path(notes_path) if notes_path else None
        self._runner = runner

    @staticmethod
    def tag_name(manifest: Dict[str, Any]) -> str:
        return alias_rules.git_tag_for(manifest["productVersion"])

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
        assert_github_release_allowed(state)
        tag = self.tag_name(manifest)
        cmd = ["gh", "release", "create", tag, "--repo", self._repo_slug, "--title", manifest["productVersion"]]
        if self._notes_path is not None:
            cmd += ["--notes-file", str(self._notes_path)]
        else:
            cmd += ["--generate-notes"]
        result = self._runner(cmd)
        if result.returncode != 0:
            raise ReleaseError(
                f"gh release create failed (exit {result.returncode}): "
                f"{redact_text(result.stderr.strip())}"
            )


# ---------------------------------------------------------------------------
# External / final verification (read-only aggregate barriers)
# ---------------------------------------------------------------------------


class AggregateVerificationAdapter:
    """A read-only barrier requiring every wrapped adapter to be ``MATCH``.

    Never writes anything - ``publish()`` is a hard error the engine only ever
    reaches if ``verify()`` unexpectedly still says ``ABSENT`` on the real
    path, which the fixed step order makes impossible and which is therefore
    treated as a hard stop rather than silently retried.
    """

    def __init__(self, *, name: str, sub_adapters: Sequence[PublicationAdapter]):
        self.name = name
        self._sub_adapters = list(sub_adapters)

    def verify(self, manifest: Dict[str, Any], state: ReleaseState) -> str:
        for adapter in self._sub_adapters:
            status = adapter.verify(manifest, state)  # propagates Conflict/Unavailable
            if status != MATCH:
                return ABSENT
        return MATCH

    def publish(self, manifest: Dict[str, Any], state: ReleaseState) -> None:
        raise ReleaseError(
            f"{self.name} has no publish action of its own - it only aggregates "
            f"other adapters' verify() results"
        )


def build_default_adapters(
    *,
    dist_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None,
    notes_path: Optional[Path] = None,
    trusted_publishing: bool = False,
) -> Dict[str, Any]:
    """The real, publication-capable adapter bundle keyed by step key.

    Both ``release.py dry-run`` and ``release.py publish`` build the bundle
    this way; the only thing that differs between them is the
    :class:`~release_tooling.engine.ExecutionMode` passed to
    :func:`release_tooling.engine.run_engine`, which decides whether any
    adapter's ``publish()`` is ever actually called.

    ``trusted_publishing`` selects the PyPI write path: the GitHub workflow
    sets it, so the engine verifies an upload performed by the official PyPI
    OIDC action instead of holding a token itself.
    """
    dist_dir = Path(dist_dir) if dist_dir is not None else (config.REPO_ROOT / "dist")
    repo_root = Path(repo_root) if repo_root is not None else config.REPO_ROOT

    uploader = (
        ExternalUploader() if trusted_publishing else TwineUploader(dist_dir=dist_dir)
    )
    pypi = PyPIAdapter(uploader=uploader)
    dockerhub = DockerHubAdapter()
    ghcr = GHCRAdapter()
    alias_adapter = AliasAdapter()
    git_tag = GitTagAdapter(repo_root=repo_root)
    github_release = GitHubReleaseAdapter(notes_path=notes_path)
    external_verification = AggregateVerificationAdapter(
        name="external_verification", sub_adapters=[pypi, dockerhub, ghcr]
    )
    final_verification = AggregateVerificationAdapter(
        name="final_verification",
        sub_adapters=[pypi, dockerhub, ghcr, alias_adapter, git_tag, github_release],
    )
    return {
        "git_tag": git_tag,
        "pypi": pypi,
        "dockerhub": dockerhub,
        "ghcr": ghcr,
        "external_verification": external_verification,
        "aliases": alias_adapter,
        "github_release": github_release,
        "final_verification": final_verification,
    }


__all__ = [
    "default_runner",
    "PublicationAdapter",
    "TwineUploader",
    "ExternalUploader",
    "PyPIAdapter",
    "DockerHubAdapter",
    "GHCRAdapter",
    "AliasAdapter",
    "GitTagAdapter",
    "GitHubReleaseAdapter",
    "AggregateVerificationAdapter",
    "build_default_adapters",
]
