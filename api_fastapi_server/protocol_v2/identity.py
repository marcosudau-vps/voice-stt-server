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

import json
import os
import re
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from VoiceSTT._version import resolve_version
from VoiceSTT._build_identity import (
    IdentityError, installed_distribution, validate_commit, validated_build_identity,
)
from . import schema

UNKNOWN_COMMIT = "unknown"


def runtime_variant(distribution_name=None, package_version=None, product_version=None):
    """Read existing provenance only; never import a native runtime."""
    embedded_path = (
        Path(__file__).resolve().parents[2]
        / "voice_stt_server" / "_embedded_kroko.json"
    )
    embedded_variant = None
    if embedded_path.is_file():
        try:
            payload = json.loads(embedded_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise IdentityError("unreadable embedded Kroko identity") from None
        if (
            not isinstance(payload, dict)
            or type(payload.get("schemaVersion")) is not int
            or payload["schemaVersion"] != 1
            or payload.get("variant") not in ("free", "pro")
            or payload.get("distribution") != distribution_name
            or payload.get("productVersion") != (product_version or package_version)
        ):
            raise IdentityError("invalid or conflicting embedded Kroko identity")
        embedded_variant = payload["variant"]
    separate_variant = None
    try:
        wheel = metadata.distribution("kroko-onnx").read_text("WHEEL") or ""
    except metadata.PackageNotFoundError:
        wheel = ""
    tags = re.findall(r"(?mi)^Build:\s*(\S+)\s*$", wheel)
    if tags:
        if len(tags) != 1 or not re.fullmatch(r"\d+(free|pro)", tags[0]):
            raise IdentityError("invalid Kroko WHEEL variant")
        separate_variant = "pro" if tags[0].endswith("pro") else "free"
    if embedded_variant and separate_variant:
        raise IdentityError("embedded and separately installed Kroko runtimes conflict")
    variant = embedded_variant or separate_variant
    expected = {"voice-stt-server": "free", "voice-stt-server-pro": "pro"}.get(
        distribution_name
    )
    if expected and variant and expected != variant:
        raise IdentityError("product and Kroko runtime variants conflict")
    return variant


@dataclass(frozen=True)
class RuntimeIdentity:
    version: str
    commit: str
    distribution_name: str | None
    package_version: str | None
    kroko_variant: str | None
    source_tree: str | None = None
    source_dirty: bool | None = None
    source_date: str | None = None

    def public_info(self, instance_id):
        complete = (
            self.commit != UNKNOWN_COMMIT and self.source_tree is not None
            and self.source_dirty is False and self.source_date is not None
            and self.distribution_name is not None and self.kroko_variant is not None
        )
        return {
            "schemaVersion": 1,
            "protocolVersion": schema.PROTOCOL_VERSION,
            "serverVersion": self.version,
            "serverCommit": self.commit,
            "identityStatus": "complete" if complete else "incomplete",
            "build": {
                "sourceTree": self.source_tree,
                "sourceDirty": self.source_dirty,
                "sourceDate": self.source_date,
            },
            "distribution": {
                "name": self.distribution_name,
                "packageVersion": self.package_version,
            },
            "runtime": {"krokoVariant": self.kroko_variant},
            "serverInstanceId": instance_id,
        }


def resolve_runtime_identity():
    build = validated_build_identity()
    name, package_version = installed_distribution()
    version = server_version()
    variant = runtime_variant(name, package_version, version)
    if build and build.krokoVariant and variant != build.krokoVariant:
        raise IdentityError("package identity and installed Kroko provenance conflict")
    return RuntimeIdentity(
        version=version,
        commit=server_commit(),
        distribution_name=name,
        package_version=package_version,
        kroko_variant=variant,
        source_tree=build.sourceTree if build else None,
        source_dirty=build.sourceDirty if build else None,
        source_date=build.sourceDate if build else None,
    )


def server_version():
    return resolve_version()


def server_commit():
    build = validated_build_identity()
    if build is not None:
        return build.sourceCommit or UNKNOWN_COMMIT
    return validate_commit(os.environ.get("VOICESTT_SERVER_COMMIT"))
