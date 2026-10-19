"""Immutable package provenance; no subprocesses, native imports or model IO."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from importlib import metadata
from pathlib import Path
from urllib.parse import unquote, urlparse

from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

RESOURCE_NAME = "_build_identity.json"
PRODUCT_DISTRIBUTIONS = ("voicestt", "voice-stt-server", "voice-stt-server-pro")
PRODUCT_VARIANTS = {"voice-stt-server": "free", "voice-stt-server-pro": "pro"}


class IdentityError(ValueError):
    """A redacted identity/configuration error suitable for startup reporting."""


def package_version_for(product_version: str) -> str:
    from ._version import parse_semver

    try:
        parsed = parse_semver(product_version)
    except ValueError:
        raise IdentityError("invalid SemVer product version") from None
    if parsed.prerelease and not re.fullmatch(r"(alpha|beta|rc)\.(0|[1-9]\d*)", parsed.prerelease):
        raise IdentityError("packaging supports only alpha.N, beta.N and rc.N prereleases")
    try:
        return str(Version(product_version))
    except InvalidVersion:
        raise IdentityError("product version has no supported PEP 440 representation") from None


def validate_commit(value: str | None) -> str:
    text = (value or "").strip()
    if not text or text == "unknown":
        return "unknown"
    if not re.fullmatch(r"[0-9a-f]{40}", text):
        raise IdentityError("VOICESTT_SERVER_COMMIT must be a full lowercase Git SHA")
    return text


def package_root() -> Path:
    return Path(__file__).resolve().parent.parent


def is_source_checkout(root: Path | None = None) -> bool:
    root = root or package_root()
    return (root / "setup.py").is_file() and (
        (root / ".git").exists() or not (root / "PKG-INFO").is_file()
    )


def installed_distribution() -> tuple[str | None, str | None]:
    """Resolve the distribution owning this import, not an unrelated install."""
    root = package_root()
    candidates = []
    # "" and an explicit cwd commonly occur together on sys.path.
    paths = list(dict.fromkeys(os.path.normcase(str(Path(path or ".").resolve())) for path in sys.path))
    for name in PRODUCT_DISTRIBUTIONS:
        for dist in metadata.distributions(name=name, path=paths):
            try:
                owns_package = any(
                    str(entry).replace("\\", "/") == "VoiceSTT/_version.py"
                    and Path(dist.locate_file(entry)).resolve() == root / "VoiceSTT" / "_version.py"
                    for entry in dist.files or ()
                )
                direct_url = dist.read_text("direct_url.json")
                if direct_url:
                    direct = json.loads(direct_url)
                    url = urlparse(direct.get("url", ""))
                    path = unquote(url.path)
                    if os.name == "nt":
                        path = path.lstrip("/")
                    owns_package |= (
                        direct.get("dir_info", {}).get("editable") is True
                        and url.scheme == "file" and Path(path).resolve() == root
                    )
                if owns_package:
                    actual_name = dist.metadata.get("Name")
                    if not isinstance(actual_name, str) or canonicalize_name(actual_name) != name:
                        raise IdentityError("conflicting product distribution name")
                    candidates.append((name, dist.version))
            except (OSError, ValueError, TypeError, AttributeError):
                raise IdentityError("invalid product distribution metadata") from None
    if len(candidates) > 1:
        raise IdentityError("multiple product distributions own this installation")
    return candidates[0] if candidates else (None, None)


@dataclass(frozen=True)
class BuildIdentity:
    schemaVersion: int
    productVersion: str
    packageVersion: str
    sourceCommit: str | None
    sourceTree: str | None
    sourceDirty: bool | None
    sourceDate: str | None
    distributionName: str
    krokoVariant: str | None
    provenance: str

    @classmethod
    def from_dict(cls, payload) -> BuildIdentity:
        if not isinstance(payload, dict) or set(payload) != set(cls.__dataclass_fields__):
            raise IdentityError("invalid build identity fields")
        if type(payload["schemaVersion"]) is not int or payload["schemaVersion"] != 1:
            raise IdentityError("unsupported build identity schema")
        if not isinstance(payload["productVersion"], str):
            raise IdentityError("invalid product version type")
        expected = package_version_for(payload["productVersion"])
        if payload["packageVersion"] != expected:
            raise IdentityError("product and package versions conflict")
        if payload["distributionName"] not in PRODUCT_DISTRIBUTIONS:
            raise IdentityError("unsupported product distribution")
        for key in ("sourceCommit", "sourceTree"):
            value = payload[key]
            if value is not None and (
                not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value)
            ):
                raise IdentityError("invalid source commit/tree")
        if payload["sourceDirty"] is not None and type(payload["sourceDirty"]) is not bool:
            raise IdentityError("invalid source dirty status")
        if payload["sourceDate"] is not None:
            try:
                value = payload["sourceDate"]
                stamp = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
                if stamp.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
                    raise ValueError
            except (ValueError, TypeError):
                raise IdentityError("invalid UTC source date") from None
        if payload["krokoVariant"] not in (None, "free", "pro"):
            raise IdentityError("unsupported Kroko variant")
        expected_variant = PRODUCT_VARIANTS.get(payload["distributionName"])
        if payload["krokoVariant"] != expected_variant:
            raise IdentityError("distribution and bound package variant conflict")
        if payload["provenance"] not in ("git", "manual"):
            raise IdentityError("unsupported provenance source")
        return cls(**payload)

    @property
    def complete(self) -> bool:
        return (
            self.sourceCommit is not None and self.sourceTree is not None
            and self.sourceDirty is False and self.sourceDate is not None
            and self.provenance == "git"
        )

    def require_complete(self) -> None:
        if not self.complete:
            raise IdentityError("official candidate requires complete clean source provenance")

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise IdentityError("duplicate build identity field")
        result[key] = value
    return result


def parse_identity(text: str) -> BuildIdentity:
    try:
        payload = json.loads(text, object_pairs_hook=_unique_object)
    except (ValueError, TypeError):
        raise IdentityError("unreadable build identity JSON") from None
    return BuildIdentity.from_dict(payload)


def load_build_identity(path: Path | None = None) -> BuildIdentity | None:
    if path is None:
        if is_source_checkout():
            return None  # A generated source-tree file must never contaminate a build.
        path = package_root() / "VoiceSTT" / RESOURCE_NAME
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError):
        raise IdentityError("unreadable build identity resource") from None
    return parse_identity(text)


def validated_build_identity() -> BuildIdentity | None:
    identity = load_build_identity()
    if identity is None:
        return None
    if not (package_root() / "setup.py").is_file():
        name, version = installed_distribution()
        if (name, version) != (identity.distributionName, identity.packageVersion):
            raise IdentityError("build identity conflicts with installed product metadata")
    override = os.environ.get("VOICESTT_BUILD_VERSION", "").strip()
    if override and override != identity.productVersion:
        raise IdentityError("VOICESTT_BUILD_VERSION conflicts with package identity")
    commit = os.environ.get("VOICESTT_SERVER_COMMIT", "").strip()
    if commit and validate_commit(commit) != (identity.sourceCommit or "unknown"):
        raise IdentityError("VOICESTT_SERVER_COMMIT conflicts with package identity")
    return identity
