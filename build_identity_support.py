"""Build-time provenance capture and staging; never imported by HTTP handlers."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import zipfile
from email.parser import Parser
from typing import Literal, overload

from VoiceSTT._build_identity import (
    BuildIdentity, IdentityError, RESOURCE_NAME, load_build_identity, package_version_for,
    parse_identity,
)


def capture_identity(root: Path, product_version: str, distribution_name: str,
                     *, runner=None) -> BuildIdentity:
    root = Path(root)
    variant = {"voice-stt-server": "free", "voice-stt-server-pro": "pro"}.get(distribution_name)
    if not (root / ".git").exists() and (root / "PKG-INFO").is_file():
        inherited = load_build_identity(root / "VoiceSTT" / RESOURCE_NAME)
        if inherited is not None:
            if (inherited.productVersion, inherited.distributionName) != (
                product_version, distribution_name
            ):
                raise IdentityError("sdist identity conflicts with build inputs")
            return inherited
    values = {
        "schemaVersion": 1, "productVersion": product_version,
        "packageVersion": package_version_for(product_version),
        "sourceCommit": None, "sourceTree": None, "sourceDirty": None,
        "sourceDate": None, "distributionName": distribution_name,
        "krokoVariant": variant, "provenance": "manual",
    }
    # Do not discover a repository above an unpacked/manual source directory.
    if (root / ".git").exists():
        def git(*args):
            if runner is None:
                try:
                    result = subprocess.run(
                        ["git", *args], cwd=root, capture_output=True,
                        text=True, encoding="utf-8", errors="strict",
                    )
                except OSError:
                    raise IdentityError("source identity Git probe unavailable") from None
            else:
                result = runner(["git", *args], cwd=root, check=False)
            if result.returncode:
                raise IdentityError("source identity Git probe failed")
            return result.stdout.strip()

        values.update(
            sourceCommit=git("rev-parse", "HEAD"),
            sourceTree=git("rev-parse", "HEAD^{tree}"),
            sourceDirty=bool(git("status", "--porcelain")),
            provenance="git",
        )
        try:
            stamp = datetime.fromisoformat(git("show", "-s", "--format=%cI", values["sourceCommit"]))
            if stamp.tzinfo is None:
                raise ValueError
            values["sourceDate"] = stamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            raise IdentityError("source identity timestamp invalid") from None
    return BuildIdentity.from_dict(values)


def write_identity(directory: Path, identity: BuildIdentity) -> None:
    destination = Path(directory) / "VoiceSTT" / RESOURCE_NAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(identity.to_json(), encoding="utf-8", newline="\n")


def match_identity(actual: BuildIdentity, expected: BuildIdentity) -> None:
    if asdict(actual) != asdict(expected):
        raise IdentityError("artifact provenance does not match the source build identity")


@overload
def wheel_identity(path: Path, *, required: Literal[True] = True) -> BuildIdentity: ...


@overload
def wheel_identity(path: Path, *, required: Literal[False]) -> BuildIdentity | None: ...


def wheel_identity(path: Path, *, required: bool = True) -> BuildIdentity | None:
    try:
        with zipfile.ZipFile(path) as archive:
            resource = "VoiceSTT/" + RESOURCE_NAME
            if resource not in archive.namelist():
                if required:
                    raise IdentityError("official wheel lacks build identity resource")
                return None
            if archive.namelist().count(resource) != 1:
                raise IdentityError("wheel has ambiguous build identity resources")
            identity = parse_identity(archive.read(resource).decode("utf-8"))
            names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
            if len(names) != 1:
                raise IdentityError("wheel has ambiguous distribution metadata")
            meta = Parser().parsestr(archive.read(names[0]).decode("utf-8"))
            if (meta["Name"], meta["Version"]) != (
                identity.distributionName, identity.packageVersion
            ):
                raise IdentityError("wheel metadata conflicts with build identity")
    except (OSError, zipfile.BadZipFile, UnicodeError):
        raise IdentityError("unreadable wheel identity") from None
    return identity
