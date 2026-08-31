"""Persistent Kroko artifact store with reuse-by-default (AP-SRV-070 W4A).

The store turns the expensive native Kroko build into a cacheable step:

.. code-block:: text

    build inputs -> fingerprint -> matching verified artifact?
                                     yes -> REUSE (no compilation)
                                     no  -> BUILD ONCE -> VERIFY -> STORE

"Persistent" is meant literally. This is not a Docker layer cache that a
routine image rebuild can evict: the store lives at a configurable filesystem
root outside the source repository, so local builds, the VPS, CI and the later
W4B container build can all share the same qualified artifacts.

Free and Pro are kept strictly apart twice over: the variant is part of the
fingerprint *and* the store lays each variant out under its own namespace
directory. A Pro artifact can therefore never be served for a free request even
if a fingerprint were somehow to collide.

Verification is deliberately unforgiving. A wheel whose recorded fingerprint,
SHA-256, byte count, variant, platform or Python ABI does not match exactly is
a hard cache miss, never a "close enough" hit - a silently mismatched native
runtime is far worse than recompiling.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from . import buildinputs
from .fingerprint import canonical_json

#: Version of the stored metadata document.
ARTIFACT_SCHEMA_VERSION = 1

#: Metadata file written next to every stored wheel.
ARTIFACT_METADATA_NAME = "artifact.json"

#: Operator override for the artifact store root. Deliberately an environment
#: variable plus an explicit CLI argument, so no personal absolute path is ever
#: baked into the product.
ARTIFACT_STORE_ENV = "VOICESTT_KROKO_ARTIFACT_STORE"

#: Directory used for staging a new artifact before it atomically replaces the
#: current one.
STAGING_DIR_NAME = ".staging"

_WHEEL_NAME_RE = re.compile(
    r"^(?P<name>[^-]+)-(?P<version>[^-]+)"
    r"(?:-(?P<build>[^-]+))?"
    r"-(?P<python>[^-]+)-(?P<abi>[^-]+)-(?P<platform>[^-]+)\.whl$"
)


class KrokoArtifactError(RuntimeError):
    """A Kroko artifact could not be stored, verified or consumed."""


def default_store_root() -> Path:
    """The per-user default artifact store root for this OS.

    Chosen to sit next to the platform's other caches rather than inside the
    repository, so a ``git clean`` cannot destroy a 30-minute build.
    """
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA")
        if root:
            return Path(root) / "VoiceSTT" / "kroko-artifacts"
    elif sys.platform == "darwin":  # pragma: no cover - platform specific
        return Path.home() / "Library" / "Caches" / "VoiceSTT" / "kroko-artifacts"
    else:
        root = os.environ.get("XDG_CACHE_HOME")
        if root:
            return Path(root) / "voicestt" / "kroko-artifacts"
        return Path.home() / ".cache" / "voicestt" / "kroko-artifacts"
    return Path(tempfile.gettempdir()) / "voicestt-kroko-artifacts"


def resolve_store_root(explicit: Optional[Any] = None) -> Path:
    """Resolves the artifact store root: argument, then env, then OS default."""
    if explicit:
        return Path(str(explicit)).expanduser().resolve()
    from_env = os.environ.get(ARTIFACT_STORE_ENV, "").strip()
    if from_env:
        return Path(from_env).expanduser().resolve()
    return default_store_root().expanduser().resolve()


def sha256_of(path: Path) -> str:
    """The SHA-256 of one file, streamed so a large wheel is not buffered."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_wheel_filename(filename: str) -> Dict[str, str]:
    """Splits a wheel filename into its PEP 427 components.

    Kroko encodes the license variant in the optional build tag - the qualified
    free wheel is ``kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl`` - which
    makes the filename itself one of the free/pro signals this store checks.
    """
    match = _WHEEL_NAME_RE.match(filename)
    if not match:
        raise KrokoArtifactError(f"not a PEP 427 wheel filename: {filename}")
    return {key: (value or "") for key, value in match.groupdict().items()}


def read_wheel_metadata(wheel_path: Path) -> Dict[str, Any]:
    """Reads the wheel's own ``WHEEL`` document (tags plus build tag).

    Read from inside the archive rather than inferred from the filename, so a
    renamed file cannot misrepresent what it actually contains.
    """
    import zipfile

    try:
        with zipfile.ZipFile(wheel_path) as archive:
            names = [n for n in archive.namelist() if n.endswith(".dist-info/WHEEL")]
            if not names:
                raise KrokoArtifactError(f"wheel has no WHEEL metadata: {wheel_path}")
            raw = archive.read(sorted(names)[0]).decode("utf-8", "replace")
    except zipfile.BadZipFile as exc:
        raise KrokoArtifactError(f"corrupt wheel archive: {wheel_path}") from exc

    parsed: Dict[str, Any] = {"tags": []}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "tag":
            parsed["tags"].append(value)
        elif key == "build":
            parsed["build"] = value
    return parsed


def variant_of_wheel(wheel_path: Path) -> Optional[str]:
    """The ``free``/``pro`` variant a wheel declares, or ``None`` if it says nothing.

    The archive's own ``WHEEL`` document is the authority; the filename's build
    tag is only consulted when the archive is readable but declares no build
    tag of its own. An unreadable or corrupt archive returns ``None`` rather
    than falling back to the filename - a filename is trivially forgeable and
    must never out-vote the artifact's actual content.

    Returning ``None`` is meaningful: the caller must then treat the variant as
    unproven rather than assume a default, because guessing here is exactly how
    a Pro runtime could silently be served as free.
    """
    try:
        metadata = read_wheel_metadata(wheel_path)
    except KrokoArtifactError:
        return None

    candidates: List[str] = [str(metadata.get("build", ""))]
    try:
        candidates.append(parse_wheel_filename(wheel_path.name)["build"])
    except KrokoArtifactError:
        pass

    for candidate in candidates:
        lowered = candidate.lower()
        # Check "pro" first: it is the restricted variant, so an ambiguous tag
        # must never be downgraded into the unrestricted one.
        if buildinputs.VARIANT_PRO in lowered:
            return buildinputs.VARIANT_PRO
        if buildinputs.VARIANT_FREE in lowered:
            return buildinputs.VARIANT_FREE
    return None


@dataclass(frozen=True)
class ArtifactRecord:
    """One stored, verified Kroko artifact."""

    metadata: Mapping[str, Any]
    wheel_path: Path
    slot_dir: Path

    @property
    def fingerprint(self) -> str:
        return str(self.metadata.get("fingerprint", ""))

    @property
    def variant(self) -> str:
        return str(self.metadata.get("variant", ""))

    @property
    def wheel_sha256(self) -> str:
        return str(self.metadata.get("wheelSha256", ""))

    def public_dict(self) -> Dict[str, Any]:
        """A machine-readable description for CI/W4B. Carries no secrets."""
        return {
            "fingerprint": self.fingerprint,
            "variant": self.variant,
            "wheelPath": str(self.wheel_path),
            "wheelFilename": self.wheel_path.name,
            "wheelSha256": self.wheel_sha256,
            "wheelBytes": self.metadata.get("wheelBytes"),
            "upstreamRevision": self.metadata.get("upstreamRevision"),
            "targetPlatform": self.metadata.get("targetPlatform"),
            "architecture": self.metadata.get("architecture"),
            "pythonTag": self.metadata.get("pythonTag"),
            "abiTag": self.metadata.get("abiTag"),
        }


def build_metadata(
    *,
    fingerprint: str,
    inputs: Mapping[str, Any],
    wheel_path: Path,
    wheel_sha256: str,
) -> Dict[str, Any]:
    """The metadata document stored beside a wheel.

    ``builtAt`` is recorded for operators but is deliberately *not* part of the
    fingerprint - otherwise every rebuild would look like a different artifact
    and reuse could never happen.
    """
    target = dict(inputs.get("target", {}))
    python = dict(inputs.get("python", {}))
    wheel_tags = read_wheel_metadata(wheel_path)
    return {
        "schemaVersion": ARTIFACT_SCHEMA_VERSION,
        "fingerprint": fingerprint,
        "fingerprintInputs": dict(inputs),
        "upstreamRepo": dict(inputs.get("upstream", {})).get("repo"),
        "upstreamRevision": dict(inputs.get("upstream", {})).get("revision"),
        "variant": inputs.get("variant"),
        "targetPlatform": target.get("platform"),
        "architecture": target.get("architecture"),
        "pythonTag": python.get("tag"),
        "abiTag": python.get("abi"),
        "buildFlags": dict(inputs.get("build", {})),
        "toolchain": dict(inputs.get("toolchain", {})),
        "wheelFilename": wheel_path.name,
        "wheelSha256": wheel_sha256,
        "wheelBytes": wheel_path.stat().st_size,
        "wheelTags": wheel_tags.get("tags", []),
        "wheelBuildTag": wheel_tags.get("build", ""),
        "builtAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def verify_artifact(
    metadata: Mapping[str, Any],
    wheel_path: Path,
    *,
    expected_fingerprint: str,
    expected_variant: str,
    expected_inputs: Optional[Mapping[str, Any]] = None,
) -> Tuple[bool, List[str]]:
    """Full structural and integrity verification of one stored artifact.

    Returns ``(ok, problems)``. Every failure is collected rather than raising
    on the first one, so a diagnosis names everything that is wrong at once.
    """
    problems: List[str] = []
    expected_variant = buildinputs.normalize_variant(expected_variant)

    if str(metadata.get("schemaVersion")) != str(ARTIFACT_SCHEMA_VERSION):
        problems.append(
            f"metadata schemaVersion {metadata.get('schemaVersion')!r} "
            f"!= {ARTIFACT_SCHEMA_VERSION}"
        )
    if str(metadata.get("fingerprint")) != str(expected_fingerprint):
        problems.append(
            f"fingerprint {metadata.get('fingerprint')!r} != {expected_fingerprint!r}"
        )
    if str(metadata.get("variant")) != expected_variant:
        problems.append(
            f"variant {metadata.get('variant')!r} != {expected_variant!r}"
        )

    if not wheel_path.is_file():
        problems.append(f"wheel file missing: {wheel_path}")
        return False, problems

    declared_bytes = metadata.get("wheelBytes")
    actual_bytes = wheel_path.stat().st_size
    if declared_bytes is not None and int(declared_bytes) != actual_bytes:
        problems.append(f"wheel bytes {actual_bytes} != declared {declared_bytes}")

    declared_sha = str(metadata.get("wheelSha256", ""))
    actual_sha = sha256_of(wheel_path)
    if declared_sha.lower() != actual_sha.lower():
        problems.append("wheel sha256 does not match the stored metadata")

    # The wheel must itself declare the variant we are about to consume; an
    # unlabelled wheel is refused rather than optimistically accepted.
    declared_wheel_variant = variant_of_wheel(wheel_path)
    if declared_wheel_variant is None:
        problems.append("wheel does not declare a free/pro build tag")
    elif declared_wheel_variant != expected_variant:
        problems.append(
            f"wheel declares variant {declared_wheel_variant!r}, expected {expected_variant!r}"
        )

    if expected_inputs is not None:
        if canonical_json(dict(metadata.get("fingerprintInputs", {}))) != canonical_json(
            dict(expected_inputs)
        ):
            problems.append("stored fingerprint inputs differ from the expected inputs")

        target = dict(expected_inputs.get("target", {}))
        python = dict(expected_inputs.get("python", {}))
        if metadata.get("targetPlatform") != target.get("platform"):
            problems.append(
                f"target platform {metadata.get('targetPlatform')!r} != {target.get('platform')!r}"
            )
        if metadata.get("architecture") != target.get("architecture"):
            problems.append(
                f"architecture {metadata.get('architecture')!r} != {target.get('architecture')!r}"
            )
        if metadata.get("abiTag") != python.get("abi"):
            problems.append(
                f"ABI tag {metadata.get('abiTag')!r} != {python.get('abi')!r}"
            )

        expected_tag_fragment = "{0}-{1}".format(
            python.get("tag", ""), python.get("abi", "")
        )
        tags = [str(tag) for tag in metadata.get("wheelTags", [])]
        if tags and not any(tag.startswith(expected_tag_fragment) for tag in tags):
            problems.append(
                f"wheel tags {tags} are not compatible with {expected_tag_fragment}"
            )

    return (not problems), problems


class KrokoArtifactStore:
    """A persistent, variant-namespaced Kroko artifact store."""

    def __init__(self, root: Optional[Any] = None):
        self.root = resolve_store_root(root)

    # -- layout --------------------------------------------------------------

    def variant_dir(self, variant: str) -> Path:
        """The namespace directory of one variant. Free and Pro never share."""
        return self.root / buildinputs.normalize_variant(variant)

    def slot_dir(self, variant: str, fingerprint: str) -> Path:
        """The directory holding the artifact for one variant+fingerprint."""
        return self.variant_dir(variant) / str(fingerprint)

    def wheel_path_in(self, slot_dir: Path, metadata: Mapping[str, Any]) -> Path:
        return slot_dir / str(metadata.get("wheelFilename", ""))

    # -- read ----------------------------------------------------------------

    def read_metadata(self, variant: str, fingerprint: str) -> Optional[Dict[str, Any]]:
        path = self.slot_dir(variant, fingerprint) / ARTIFACT_METADATA_NAME
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def lookup(
        self,
        *,
        variant: str,
        fingerprint: str,
        inputs: Optional[Mapping[str, Any]] = None,
    ) -> Tuple[Optional[ArtifactRecord], List[str]]:
        """Looks up a verified artifact.

        Returns ``(record, problems)``. A record is returned *only* when every
        verification passed; anything else is a miss with a diagnosis, so a
        damaged or foreign artifact can never be consumed as a hit.
        """
        metadata = self.read_metadata(variant, fingerprint)
        if metadata is None:
            return None, ["no stored artifact for this variant/fingerprint"]

        slot = self.slot_dir(variant, fingerprint)
        wheel_path = self.wheel_path_in(slot, metadata)
        ok, problems = verify_artifact(
            metadata,
            wheel_path,
            expected_fingerprint=fingerprint,
            expected_variant=variant,
            expected_inputs=inputs,
        )
        if not ok:
            return None, problems
        return ArtifactRecord(metadata=metadata, wheel_path=wheel_path, slot_dir=slot), []

    # -- write ---------------------------------------------------------------

    def store(
        self,
        *,
        wheel_path: Any,
        fingerprint: str,
        inputs: Mapping[str, Any],
    ) -> ArtifactRecord:
        """Verifies a freshly built wheel and stores it atomically.

        The new artifact is fully staged and verified *before* it replaces an
        existing one, and the previous artifact is only deleted after the swap
        succeeded. A failed store therefore leaves the last known-good artifact
        exactly as it was.
        """
        source = Path(str(wheel_path))
        if not source.is_file():
            raise KrokoArtifactError(f"wheel to store does not exist: {source}")

        variant = buildinputs.normalize_variant(str(inputs.get("variant", "")))
        digest = sha256_of(source)
        metadata = build_metadata(
            fingerprint=fingerprint,
            inputs=inputs,
            wheel_path=source,
            wheel_sha256=digest,
        )

        staging_root = self.root / STAGING_DIR_NAME
        staging_root.mkdir(parents=True, exist_ok=True)
        staging = staging_root / f"{variant}-{fingerprint}-{uuid.uuid4().hex}"
        staging.mkdir(parents=True)

        try:
            staged_wheel = staging / source.name
            shutil.copy2(source, staged_wheel)
            (staging / ARTIFACT_METADATA_NAME).write_text(
                json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            ok, problems = verify_artifact(
                metadata,
                staged_wheel,
                expected_fingerprint=fingerprint,
                expected_variant=variant,
                expected_inputs=inputs,
            )
            if not ok:
                raise KrokoArtifactError(
                    "refusing to store an artifact that fails verification: "
                    + "; ".join(problems)
                )

            final = self.slot_dir(variant, fingerprint)
            final.parent.mkdir(parents=True, exist_ok=True)
            backup = None
            if final.exists():
                backup = final.with_name(final.name + f".replaced-{uuid.uuid4().hex}")
                os.replace(final, backup)
            try:
                os.replace(staging, final)
            except OSError:
                if backup is not None:
                    os.replace(backup, final)
                raise
            if backup is not None:
                shutil.rmtree(backup, ignore_errors=True)
        finally:
            shutil.rmtree(staging, ignore_errors=True)

        stored_wheel = self.wheel_path_in(final, metadata)
        return ArtifactRecord(metadata=metadata, wheel_path=stored_wheel, slot_dir=final)


def verify_installed_runtime(expected_variant: str) -> Dict[str, Any]:
    """Verifies the Kroko runtime *installed in this interpreter*.

    W4A-06 requires that consuming an artifact proves the module actually
    imports and that the installed runtime is the expected license variant -
    the checks that only become possible once the wheel is installed.
    """
    expected_variant = buildinputs.normalize_variant(expected_variant)
    result: Dict[str, Any] = {"expectedVariant": expected_variant}

    try:
        from importlib import import_module

        import_module("kroko_onnx")
        result["importable"] = True
    except Exception as exc:  # noqa: BLE001 - reported, never raised blindly
        result["importable"] = False
        result["importError"] = f"{type(exc).__name__}: {exc}"
        result["ok"] = False
        return result

    installed_variant = None
    try:
        from importlib import metadata as importlib_metadata

        wheel_text = importlib_metadata.distribution("kroko-onnx").read_text("WHEEL") or ""
        for line in wheel_text.splitlines():
            if line.lower().startswith("build:"):
                build_tag = line.partition(":")[2].strip().lower()
                if buildinputs.VARIANT_PRO in build_tag:
                    installed_variant = buildinputs.VARIANT_PRO
                elif buildinputs.VARIANT_FREE in build_tag:
                    installed_variant = buildinputs.VARIANT_FREE
                result["installedBuildTag"] = build_tag
    except Exception as exc:  # noqa: BLE001 - absence is reported, not fatal
        result["metadataError"] = f"{type(exc).__name__}: {exc}"

    result["installedVariant"] = installed_variant
    result["ok"] = installed_variant == expected_variant
    if not result["ok"]:
        result["problem"] = (
            f"installed Kroko runtime variant {installed_variant!r} "
            f"does not match the expected {expected_variant!r}"
        )
    return result


__all__ = [
    "ARTIFACT_METADATA_NAME",
    "ARTIFACT_SCHEMA_VERSION",
    "ARTIFACT_STORE_ENV",
    "ArtifactRecord",
    "KrokoArtifactError",
    "KrokoArtifactStore",
    "build_metadata",
    "default_store_root",
    "parse_wheel_filename",
    "read_wheel_metadata",
    "resolve_store_root",
    "sha256_of",
    "variant_of_wheel",
    "verify_artifact",
    "verify_installed_runtime",
]
