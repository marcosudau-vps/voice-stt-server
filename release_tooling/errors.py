"""Exception hierarchy for the AP-SRV-070 release orchestrator.

Every failure mode the release tooling can hit is one of these, so a caller
(the CLI, or a future W6 automation) can distinguish "nothing to do"
conditions from hard stops without parsing message text.
"""

from __future__ import annotations


class ReleaseError(RuntimeError):
    """Base class for every release-tooling failure."""


class ManifestError(ReleaseError):
    """An RC manifest is missing, malformed, or fails a required identity check."""


class StateError(ReleaseError):
    """The resumable release state is missing, corrupted, or an invalid transition
    was requested (including a version mismatch against an existing state file)."""


class OrderError(StateError):
    """A publication step was attempted out of the fixed W6 order (see
    ``release_tooling.pipeline``), e.g. tagging before external verification."""


class ConflictError(ReleaseError):
    """A pre-existing remote artifact does not match the expected release
    identity. This is always a hard stop - never resolved by picking a new
    version automatically."""


class SecretDetectedError(ReleaseError):
    """A value that looks like a secret was about to be written to release
    state, an RC manifest, or normal log output."""


class VerificationUnavailableError(ReleaseError):
    """A read-only remote identity check could not be completed (e.g. no
    network, tool missing) - distinct from :class:`ConflictError`, which
    means the check *did* complete and found a genuine mismatch. Real
    publication must fail closed on this too (it cannot tell match from
    conflict), but a dry-run may still report every other, independently
    checkable step."""


__all__ = [
    "ReleaseError",
    "ManifestError",
    "StateError",
    "OrderError",
    "ConflictError",
    "SecretDetectedError",
    "VerificationUnavailableError",
]
