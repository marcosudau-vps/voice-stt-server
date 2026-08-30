"""Server identity published on the v2 wire.

The frozen contract requires ``serverVersion`` and ``serverCommit`` in
``hello.accepted``, ``session.snapshot`` and both refusal messages.

The version is the served API version, read from the one product version
authority in :mod:`VoiceSTT._version` (AP-SRV-070) - it is not a second,
independently hardcoded value. The commit is a build input: it is read from
``VOICESTT_SERVER_COMMIT`` and falls back to the literal ``unknown``, which is
the same convention the contract allows for ``clientCommit``. No git call
happens at runtime - a container has no repository, and a slow or failing
subprocess must never be able to delay a handshake.
"""

import os

from VoiceSTT._version import resolve_version

UNKNOWN_COMMIT = "unknown"


def server_version():
    return resolve_version()


def server_commit():
    commit = os.environ.get("VOICESTT_SERVER_COMMIT")
    if commit is None:
        return UNKNOWN_COMMIT
    commit = commit.strip()
    return commit or UNKNOWN_COMMIT
