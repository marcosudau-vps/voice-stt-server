"""Release-tooling configuration: reuses existing authorities, invents none.

Two identities already have exactly one authority in this repository and
this module deliberately reuses both instead of hardcoding a second copy:

* The product version / PyPI distribution name: ``VoiceSTT._version``.
* The Free/Pro production image names: ``tools.build_production`` (AP-SRV-070
  W4C). That module has no package ``__init__.py`` - it is imported the same
  way its own unit tests import it (``tests/unit/test_build_production.py``):
  by adding ``tools/`` to ``sys.path``.

GHCR and Docker Hub repository roots are intentionally **not** hardcoded
here. Guessing a registry namespace would be an invented, unverified claim
(AP-SRV-070 W5, section 13: "no invented claims"); the operator must supply
them explicitly before a real W6 publish, and preflight fails closed if they
are missing rather than silently assuming a placeholder.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_TOOLS_DIR = REPO_ROOT / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from build_production import IMAGE_NAMES, SUPPORTED_VARIANTS, image_name_for  # noqa: E402

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from VoiceSTT._version import DISTRIBUTION_NAME  # noqa: E402

#: Env vars that name the GHCR/Docker Hub repository roots for the two
#: product images. Unset = "not configured yet"; preflight reports this as a
#: FAIL, never as an assumed default.
GHCR_REPO_ENV = "VOICESTT_RELEASE_GHCR_REPO"
DOCKERHUB_REPO_ENV = "VOICESTT_RELEASE_DOCKERHUB_REPO"

#: Env vars checked for *presence only* (never read into state/manifest/logs)
#: so preflight can report auth readiness without touching a secret value.
PYPI_TOKEN_ENV = "VOICESTT_RELEASE_PYPI_TOKEN"
GHCR_TOKEN_ENV = "VOICESTT_RELEASE_GHCR_TOKEN"
DOCKERHUB_TOKEN_ENV = "VOICESTT_RELEASE_DOCKERHUB_TOKEN"
GITHUB_TOKEN_ENV = "VOICESTT_RELEASE_GITHUB_TOKEN"

#: The actual, already-public GitHub repository this project lives in (see
#: ``setup.py``'s ``url``) - unlike the GHCR/Docker Hub repository roots
#: above, this is not a guess: it is the one place this source is already
#: hosted, so naming it here invents nothing.
GITHUB_REPO_SLUG = "marcosudau-vps/voice-stt-server"

#: The remote name real Git tag operations push to.
GIT_REMOTE_NAME = "origin"

RELEASE_STATE_DIRNAME = "release_state"


def release_state_dir(repo_root: Path = REPO_ROOT) -> Path:
    return repo_root / RELEASE_STATE_DIRNAME


def ghcr_repo_root() -> str:
    return os.environ.get(GHCR_REPO_ENV, "").strip()


def dockerhub_repo_root() -> str:
    return os.environ.get(DOCKERHUB_REPO_ENV, "").strip()


def credential_presence() -> dict:
    """Boolean-only auth readiness, safe to embed in preflight output."""
    return {
        "pypiTokenPresent": bool(os.environ.get(PYPI_TOKEN_ENV, "").strip()),
        "ghcrTokenPresent": bool(os.environ.get(GHCR_TOKEN_ENV, "").strip()),
        "dockerhubTokenPresent": bool(os.environ.get(DOCKERHUB_TOKEN_ENV, "").strip()),
        "githubTokenPresent": bool(os.environ.get(GITHUB_TOKEN_ENV, "").strip()),
    }


__all__ = [
    "REPO_ROOT",
    "IMAGE_NAMES",
    "SUPPORTED_VARIANTS",
    "image_name_for",
    "DISTRIBUTION_NAME",
    "GHCR_REPO_ENV",
    "DOCKERHUB_REPO_ENV",
    "PYPI_TOKEN_ENV",
    "GHCR_TOKEN_ENV",
    "DOCKERHUB_TOKEN_ENV",
    "GITHUB_TOKEN_ENV",
    "GITHUB_REPO_SLUG",
    "GIT_REMOTE_NAME",
    "RELEASE_STATE_DIRNAME",
    "release_state_dir",
    "ghcr_repo_root",
    "dockerhub_repo_root",
    "credential_presence",
]
