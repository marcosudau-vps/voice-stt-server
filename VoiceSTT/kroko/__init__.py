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

Nothing in this package ever handles a Kroko license key. The Pro *build* is a
capability switch; the Pro *key* is a runtime secret that lives only in the
process environment and is never written to an artifact, its metadata or a log.
"""

from . import artifacts, buildinputs, fingerprint, models

__all__ = ["artifacts", "buildinputs", "fingerprint", "models"]
