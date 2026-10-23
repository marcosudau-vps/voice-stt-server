"""Kroko runtime productization (AP-SRV-070 W4A).

Decouples the expensive native Kroko build from the ordinary VoiceSTT build and
gives the Kroko runtime and its models an explicit, verifiable identity:

:mod:`~VoiceSTT.kroko.buildinputs`
    The declared, source-controlled build inputs - above all the *immutable*
    upstream revision that replaces the previous moving branch reference.

:mod:`~VoiceSTT.kroko.fingerprint`
    The canonical fingerprint over those inputs. It decides reuse, and it
    deliberately excludes the VoiceSTT product version, server code, docs and
    wake-word code so a normal change never triggers a native rebuild.

:mod:`~VoiceSTT.kroko.artifacts`
    The persistent, variant-namespaced artifact store: reuse by default, strict
    verification before consumption, atomic replace on an explicit rebuild.

:mod:`~VoiceSTT.kroko.models`
    The model authority: manifested identity, integrity, license class and the
    runtime variant each model requires - with no implicit downloads.

:mod:`~VoiceSTT.kroko.license_runtime`
    The volatile, server-wide license/runtime authority: generation-bound
    proofs, fail-closed decisions and a redacted status projection. No key
    material, no network, no persistence.

:mod:`~VoiceSTT.kroko.bootstrap`
    The cold pre-import bootstrap: exactly one private native payload root,
    foreign runtimes treated as conflicts. Native-import-free.

:mod:`~VoiceSTT.kroko.supervisor`
    Owner-process supervision: one active native generation, start deadline,
    bounded retries, confirmed exit and stale-generation invalidation.
    Native-import-free and secret-free.

Nothing in this package ever handles a Kroko license key. The Pro *build* is a
capability switch; the Pro *key* is a runtime secret that lives only in the
process environment and is never written to an artifact, its metadata or a log.
Callers prove key changes with a one-way credential fingerprint only.
"""

from . import (
    artifacts,
    bootstrap,
    buildinputs,
    fingerprint,
    license_runtime,
    models,
    supervisor,
)

__all__ = [
    "artifacts",
    "bootstrap",
    "buildinputs",
    "fingerprint",
    "license_runtime",
    "models",
    "supervisor",
]
