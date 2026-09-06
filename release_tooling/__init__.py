"""AP-SRV-070 W5 release orchestration tooling.

This package backs the single repository-root entry point ``release.py``. It
has no runtime dependency on the VoiceSTT product itself beyond the one
existing version authority (``VoiceSTT._version``) and the one existing
Free/Pro image-name authority (``tools.build_production``) - it does not
invent a second version or product-identity authority.

Scope (AP-SRV-070 W5, corrected in W5-R01-C1): preflight, resumable release
state, RC manifest handling, fixed-order/conflict enforcement, and real,
W6-capable publication adapters for PyPI, GHCR, Docker Hub, the Git tag,
and GitHub Releases (``release_tooling.adapters``). ``release_tooling.engine``
is the one shared operation graph/state machine both ``release.py dry-run``
and ``release.py publish`` walk - the only difference between them is
``ExecutionMode.DRY_RUN`` versus ``ExecutionMode.REAL``, which decides
whether any adapter's ``publish()`` is ever actually called. No public
write has been performed by this codebase itself: every adapter is
qualified here exclusively through injected fake/mock test doubles (see
``tests/unit/test_release_adapters.py`` and
``tests/unit/test_release_engine.py``), because a real write cannot be
exercised safely in this environment without live credentials and a real
public registry. W6 invokes this same, already-qualified engine with real
credentials rather than introducing new critical publication logic after
RC qualification.
"""

__all__: list = []
