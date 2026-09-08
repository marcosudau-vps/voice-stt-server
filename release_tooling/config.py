"""Release-tooling configuration: reuses existing authorities, invents none.

Three identities already have exactly one authority in this repository and
this module deliberately reuses all of them instead of hardcoding a copy:

* The product version: ``VoiceSTT._version``.
* The Free/Pro production **image** names: ``tools.build_production``
  (AP-SRV-070 W4C). That module has no package ``__init__.py`` - it is
  imported the same way its own unit tests import it, by adding ``tools/`` to
  ``sys.path``.
* The Free/Pro public **distribution** names: ``tools.build_distribution``
  (AP-SRV-070 W5-R04), imported the same way.

AP-SRV-070 W5-R04 changed how the registry roots are resolved. Previously both
GHCR and Docker Hub required a full repository-root environment variable, and
preflight failed closed if either was missing. That is still the behaviour for
a local operator run, but it made the GitHub-native path require redundant
configuration: a workflow already knows its own repository owner. The roots are
therefore *derived* where that is safe and unambiguous, and only the genuinely
unknowable part - the Docker Hub namespace - is asked for, as an ordinary
repository variable rather than a secret.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

_TOOLS_DIR = REPO_ROOT / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from build_production import IMAGE_NAMES, SUPPORTED_VARIANTS, image_name_for  # noqa: E402
from build_distribution import (  # noqa: E402
    DISTRIBUTION_NAMES,
    distribution_name_for,
)

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from VoiceSTT._version import DISTRIBUTION_NAME  # noqa: E402

#: The historical single-distribution name (``voicestt``). Kept because the
#: development/editable install still uses it; it is **not** a public release
#: surface any more - the two names in :data:`DISTRIBUTION_NAMES` are.
LEGACY_DISTRIBUTION_NAME = DISTRIBUTION_NAME

#: Explicit registry-root overrides for a fully manual operator run.
GHCR_REPO_ENV = "VOICESTT_RELEASE_GHCR_REPO"
DOCKERHUB_REPO_ENV = "VOICESTT_RELEASE_DOCKERHUB_REPO"

#: The Docker Hub namespace. ``DOCKERHUB_USERNAME`` is the name the workflow
#: uses (an ordinary repository *variable*, never a secret - it is not
#: sensitive and making it a secret only makes it invisible in logs where it
#: would be useful).
DOCKERHUB_NAMESPACE_ENV = "DOCKERHUB_USERNAME"

#: GitHub Actions supplies this on every runner; it is what lets the GHCR root
#: be derived instead of configured.
GITHUB_OWNER_ENV = "GITHUB_REPOSITORY_OWNER"

GHCR_REGISTRY = "ghcr.io"
DOCKERHUB_REGISTRY = "docker.io"

#: The private staging repository suffix. Staging holds the *qualified but not
#: yet published* candidate images so publication never has to rebuild them
#: (section 13). It must never be presented as a public release surface.
STAGING_SUFFIX = "-staging"

#: Env vars checked for *presence only* (never read into state/manifest/logs)
#: so preflight can report auth readiness without touching a secret value.
DOCKERHUB_TOKEN_ENV = "DOCKERHUB_TOKEN"
GITHUB_TOKEN_ENV = "GITHUB_TOKEN"

#: The actual, already-public GitHub repository this project lives in (see
#: ``setup.py``'s ``url``).
GITHUB_REPO_SLUG = "marcosudau-vps/voice-stt-server"

#: The remote name real Git tag operations push to.
GIT_REMOTE_NAME = "origin"

RELEASE_STATE_DIRNAME = "release_state"


def release_state_dir(repo_root: Path = REPO_ROOT) -> Path:
    return repo_root / RELEASE_STATE_DIRNAME


def github_owner() -> str:
    """The GitHub owner, from the runner environment or the known slug."""
    from_env = os.environ.get(GITHUB_OWNER_ENV, "").strip()
    if from_env:
        return from_env
    return GITHUB_REPO_SLUG.split("/", 1)[0]


def ghcr_repo_root() -> str:
    """``ghcr.io/<owner>``, derived unless explicitly overridden.

    Deriving this is safe: GHCR packages always live under the repository
    owner, and the owner is not a guess - it is either supplied by the runner
    or taken from the one GitHub repository this source is hosted in.
    """
    explicit = os.environ.get(GHCR_REPO_ENV, "").strip()
    if explicit:
        return explicit.rstrip("/")
    return f"{GHCR_REGISTRY}/{github_owner()}"


def dockerhub_namespace() -> str:
    """The configured Docker Hub namespace, or ``""`` if unset."""
    return os.environ.get(DOCKERHUB_NAMESPACE_ENV, "").strip()


def dockerhub_repo_root() -> str:
    """The Docker Hub repository root, or ``""`` if not configured.

    Unlike GHCR this genuinely cannot be derived - a Docker Hub namespace has
    no relationship to the GitHub owner - so it stays operator-configured and
    preflight fails closed when it is missing rather than guessing one.
    """
    explicit = os.environ.get(DOCKERHUB_REPO_ENV, "").strip()
    if explicit:
        return explicit.rstrip("/")
    namespace = dockerhub_namespace()
    return namespace if namespace else ""


def staging_repo_root() -> str:
    """The private GHCR root that holds qualified candidate images."""
    return ghcr_repo_root()


def staging_image_name_for(variant: str) -> str:
    """The private staging package name for one variant."""
    return f"{image_name_for(variant)}{STAGING_SUFFIX}"


def credential_presence() -> Dict[str, bool]:
    """Boolean-only auth readiness, safe to embed in preflight output."""
    return {
        "dockerhubTokenPresent": bool(os.environ.get(DOCKERHUB_TOKEN_ENV, "").strip()),
        "githubTokenPresent": bool(os.environ.get(GITHUB_TOKEN_ENV, "").strip()),
        "dockerhubNamespaceConfigured": bool(dockerhub_namespace()),
    }


__all__ = [
    "REPO_ROOT",
    "IMAGE_NAMES",
    "SUPPORTED_VARIANTS",
    "image_name_for",
    "DISTRIBUTION_NAMES",
    "distribution_name_for",
    "LEGACY_DISTRIBUTION_NAME",
    "GHCR_REPO_ENV",
    "DOCKERHUB_REPO_ENV",
    "DOCKERHUB_NAMESPACE_ENV",
    "GITHUB_OWNER_ENV",
    "GHCR_REGISTRY",
    "DOCKERHUB_REGISTRY",
    "STAGING_SUFFIX",
    "DOCKERHUB_TOKEN_ENV",
    "GITHUB_TOKEN_ENV",
    "GITHUB_REPO_SLUG",
    "GIT_REMOTE_NAME",
    "RELEASE_STATE_DIRNAME",
    "release_state_dir",
    "github_owner",
    "ghcr_repo_root",
    "dockerhub_namespace",
    "dockerhub_repo_root",
    "staging_repo_root",
    "staging_image_name_for",
    "credential_presence",
]
