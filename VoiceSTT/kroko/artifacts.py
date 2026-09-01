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

import contextlib
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple

from . import buildinputs
from .fingerprint import canonical_json

#: OS advisory-lock primitives (AP-SRV-070 W4A-C2, Root Finding H). Guarded
#: import: ``fcntl`` does not exist on Windows, ``msvcrt`` only exists there.
if os.name == "nt":
    import msvcrt

    def _acquire_os_lock(handle) -> bool:
        """Attempts to take an exclusive, non-blocking lock on ``handle``."""
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    def _release_os_lock(handle) -> None:
        """Releases a lock previously taken by :func:`_acquire_os_lock`."""
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:
    import fcntl

    def _acquire_os_lock(handle) -> bool:
        """Attempts to take an exclusive, non-blocking lock on ``handle``."""
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def _release_os_lock(handle) -> None:
        """Releases a lock previously taken by :func:`_acquire_os_lock`."""
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass

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

#: Directory holding the per-slot lock files (Root Hardening: concurrent access
#: to the same variant+fingerprint slot).
LOCK_DIR_NAME = ".locks"

#: Name marker for the last-known-good copy of a slot that a force rebuild is
#: in the middle of replacing (AP-SRV-070 W4A-C2/C3). The replacement moves the
#: current artifact aside under ``<fingerprint><suffix><unique>`` before the
#: new one is moved into place, which is what makes the swap recoverable: a
#: process killed between the two moves leaves the last known-good artifact
#: sitting right next to the slot, under the same variant namespace, where
#: :meth:`KrokoArtifactStore.recover_slot` can find and re-verify it.
REPLACED_SUFFIX = ".replaced-"

#: How long ``store()`` waits for another process to finish writing the same
#: slot before giving up. A real native build can take on the order of
#: minutes, so this is generous; it is not a build timeout, only a lock wait.
DEFAULT_LOCK_TIMEOUT_SECONDS = 1800.0
DEFAULT_LOCK_POLL_SECONDS = 0.05

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


#: Architecture tokens a wheel's platform tag may use for one fingerprint
#: architecture value. A wheel can legitimately spell amd64 as "amd64" or
#: "x86_64" depending on the toolchain that produced it.
_PLATFORM_ARCH_TOKENS = {
    "amd64": ("amd64", "x86_64"),
    "arm64": ("arm64", "aarch64"),
}

#: Recognized platform-tag family prefixes per fingerprint target platform.
_PLATFORM_FAMILY_PREFIXES = {
    "windows": ("win",),
    "linux": ("linux", "manylinux", "musllinux"),
    "darwin": ("macosx",),
}


def wheel_platform_tag_matches_target(
    platform_tag: str, target_platform: str, architecture: str
) -> bool:
    """Whether one wheel platform tag is compatible with the expected target.

    ``verify_artifact`` used to check only that a wheel's tag *started with*
    the expected Python/ABI fragment, never the platform component. A
    structurally valid ``cp312-cp312-win_amd64`` tag would therefore pass
    verification for a Linux-targeted fingerprint whose Python tag/ABI
    happened to match (AP-SRV-070 W4A-C1, Root Finding D). This checks the
    actual platform component of the tag against the target platform family
    and, where the tag encodes it, the architecture.
    """
    platform_tag = (platform_tag or "").lower()
    target_platform = (target_platform or "").lower()
    architecture = (architecture or "").lower()

    if not platform_tag:
        return False

    family_prefixes = _PLATFORM_FAMILY_PREFIXES.get(target_platform)
    if family_prefixes is not None:
        if not any(platform_tag.startswith(prefix) for prefix in family_prefixes):
            return False
    # An unrecognized target platform family cannot be matched by prefix, so
    # fall through to the architecture check alone rather than reject blindly
    # - this keeps the function from becoming a second variant allowlist.

    arch_tokens = _PLATFORM_ARCH_TOKENS.get(architecture)
    if arch_tokens and not any(token in platform_tag for token in arch_tokens):
        return False

    return True


def _wheel_tag_platform_component(tag: str) -> str:
    """The platform component of one dash-joined wheel compatibility tag."""
    parts = str(tag).split("-", 2)
    return parts[2] if len(parts) == 3 else ""


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
        if tags:
            # Root Finding D: a wheel tag's Python/ABI prefix matching is not
            # enough on its own - the tag's own platform component must also
            # be checked against the expected target, or a wheel built for the
            # wrong OS/architecture can pass under a coincidentally matching
            # Python tag (e.g. a Windows cp312 wheel accepted for a Linux
            # cp312 fingerprint). Metadata's self-reported targetPlatform is
            # not sufficient by itself: this checks the wheel's own tag.
            compatible = any(
                tag.startswith(expected_tag_fragment)
                and wheel_platform_tag_matches_target(
                    _wheel_tag_platform_component(tag),
                    target.get("platform", ""),
                    target.get("architecture", ""),
                )
                for tag in tags
            )
            if not compatible:
                problems.append(
                    f"wheel tags {tags} are not compatible with target "
                    f"{target.get('platform', '')}/{target.get('architecture', '')} "
                    f"({expected_tag_fragment})"
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

    def _slot_lock_path(self, variant: str, fingerprint: str) -> Path:
        return (
            self.root / LOCK_DIR_NAME
            / f"{buildinputs.normalize_variant(variant)}__{fingerprint}.lock"
        )

    @contextlib.contextmanager
    def _slot_lock(
        self,
        variant: str,
        fingerprint: str,
        *,
        timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
        poll_interval: float = DEFAULT_LOCK_POLL_SECONDS,
    ) -> Iterator[None]:
        """Exclusive, per-(variant, fingerprint) lock (Root Hardening).

        AP-SRV-070 W4A-C2, Root Finding H made this crash-recoverable. The
        original (C1) implementation treated the lock **file's existence**
        (``os.open(..., O_CREAT | O_EXCL)``) as the mutex: correct for two
        live, well-behaved processes, but if the holder was killed after
        acquiring it, the ``finally`` that deleted the file never ran, and the
        file stayed behind forever - every future acquirer of that slot would
        then wait out the full timeout on every attempt, with no automatic or
        manual way to recover short of deleting the file by hand.

        The mutex is now a real OS advisory lock (POSIX ``flock`` / Windows
        ``LK_NBLCK``) held on an *open file handle*, not the file's mere
        presence. That is what makes it crash-recoverable: the OS itself
        releases the lock the instant the holding handle closes, for any
        reason at all - a normal exit, an exception, or a hard kill - with no
        stale-file detection, lease or heartbeat logic needed.

        The lock file is deliberately **never deleted** (unlike the C1
        version). Unlinking it while another process might already have it
        open is the classic advisory-lock "unlink race": a second process
        could ``open()`` and lock a *new* file at the same path while a third,
        already-waiting process still holds a lock tied to the *old*
        (unlinked) inode - both would then believe they hold the slot at the
        same time. Leaving the small, otherwise-inert marker file in place
        permanently avoids that race entirely; only the OS lock state, never
        the file's existence, is the actual mutex.
        """
        lock_path = self._slot_lock_path(variant, fingerprint)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(lock_path, "a+b")
        try:
            if handle.seek(0, 2) == 0:
                # msvcrt.locking() needs at least one lockable byte.
                handle.write(b"\0")
                handle.flush()
            deadline = time.monotonic() + timeout
            while not _acquire_os_lock(handle):
                if time.monotonic() >= deadline:
                    raise KrokoArtifactError(
                        f"timed out waiting for the Kroko artifact slot lock: {lock_path}"
                    )
                time.sleep(poll_interval)
            try:
                yield
            finally:
                _release_os_lock(handle)
        finally:
            handle.close()

    # -- read ----------------------------------------------------------------

    def read_metadata_in(self, slot_dir: Path) -> Optional[Dict[str, Any]]:
        """Reads the metadata document of one concrete slot directory."""
        path = Path(slot_dir) / ARTIFACT_METADATA_NAME
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def read_metadata(self, variant: str, fingerprint: str) -> Optional[Dict[str, Any]]:
        return self.read_metadata_in(self.slot_dir(variant, fingerprint))

    def _verify_slot_dir(
        self,
        slot_dir: Path,
        *,
        variant: str,
        fingerprint: str,
        inputs: Optional[Mapping[str, Any]] = None,
    ) -> Tuple[Optional[ArtifactRecord], List[str]]:
        """Full verification of one concrete directory as an artifact slot.

        Used for the live slot *and* for a last-known-good backup, so a backup
        is never trusted on the strength of its name: it has to satisfy exactly
        the same fingerprint, variant, inputs, byte count, SHA-256 and wheel-tag
        checks a stored artifact does before it can be activated.
        """
        metadata = self.read_metadata_in(slot_dir)
        if metadata is None:
            return None, ["no stored artifact for this variant/fingerprint"]

        wheel_path = self.wheel_path_in(Path(slot_dir), metadata)
        ok, problems = verify_artifact(
            metadata,
            wheel_path,
            expected_fingerprint=fingerprint,
            expected_variant=variant,
            expected_inputs=inputs,
        )
        if not ok:
            return None, problems
        return (
            ArtifactRecord(
                metadata=metadata, wheel_path=wheel_path, slot_dir=Path(slot_dir)
            ),
            [],
        )

    def replaced_backups(self, variant: str, fingerprint: str) -> List[Path]:
        """The last-known-good backups left next to one slot, oldest name first.

        Cheap: a single directory glob, no hashing. ``lookup`` uses it to decide
        whether a slot needs the (locked) recovery pass at all, so the ordinary
        case - a healthy slot with no interrupted replacement behind it - stays
        exactly as fast as it was.
        """
        variant_dir = self.variant_dir(variant)
        if not variant_dir.is_dir():
            return []
        pattern = "{0}{1}*".format(fingerprint, REPLACED_SUFFIX)
        return sorted(path for path in variant_dir.glob(pattern) if path.is_dir())

    def _recover_slot_locked(
        self,
        variant: str,
        fingerprint: str,
        inputs: Optional[Mapping[str, Any]] = None,
    ) -> Optional[str]:
        """Crash recovery and backup cleanup for one slot. Lock must be held.

        AP-SRV-070 W4A-C3, Root Finding K. ``store()`` replaces an existing
        slot with two moves - ``final -> backup`` then ``staging -> final`` -
        and rolls back on a Python exception. A *hard* process kill between the
        two moves runs no rollback at all: the OS releases the slot lock, the
        final path is simply gone, and the last known-good artifact survives
        only under its backup name. An ordinary ``lookup()`` knew nothing about
        that state and reported a plain cache miss, so the declared contract
        "a failed force rebuild must not destroy the known-good artifact" did
        not hold for exactly the crash class C2 already hardened the lock
        against - the next run would recompile for ~30 minutes to reproduce an
        artifact that was still sitting on disk.

        Two directions, both decided here under the same per-slot OS lock so
        concurrent recoverers can never activate different states:

        * a **verified** final slot means the replacement completed; the
          leftover backups are debris from a crash between the second move and
          the cleanup, and are removed;
        * a **missing** final slot with a backup that verifies completely is
          the interrupted replacement; the backup is moved back into place.

        A final slot that exists but fails verification is deliberately left
        untouched: ``os.replace`` is atomic, so that state is not this crash
        window, and overwriting it from a backup would be a repair this
        function has no evidence to justify.

        Returns ``"restored"``, ``"cleaned"`` or ``None`` for diagnostics.
        """
        backups = self.replaced_backups(variant, fingerprint)
        if not backups:
            return None

        final = self.slot_dir(variant, fingerprint)
        if final.exists():
            record, _ = self._verify_slot_dir(
                final, variant=variant, fingerprint=fingerprint, inputs=inputs
            )
            if record is None:
                return None
            for backup in backups:
                shutil.rmtree(backup, ignore_errors=True)
            return "cleaned"

        for backup in backups:
            record, _ = self._verify_slot_dir(
                backup, variant=variant, fingerprint=fingerprint, inputs=inputs
            )
            if record is None:
                # Corrupt, foreign or half-written: never activated. Left in
                # place rather than deleted so it stays available for
                # diagnosis; a later successful store cleans the slot up.
                continue
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(backup, final)
            for other in backups:
                if other != backup:
                    shutil.rmtree(other, ignore_errors=True)
            return "restored"
        return None

    def recover_slot(
        self,
        *,
        variant: str,
        fingerprint: str,
        inputs: Optional[Mapping[str, Any]] = None,
        timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
    ) -> Optional[str]:
        """Takes the slot lock and runs :meth:`_recover_slot_locked`."""
        variant = buildinputs.normalize_variant(variant)
        with self._slot_lock(variant, fingerprint, timeout=timeout):
            return self._recover_slot_locked(variant, fingerprint, inputs)

    def lookup(
        self,
        *,
        variant: str,
        fingerprint: str,
        inputs: Optional[Mapping[str, Any]] = None,
        recover: bool = True,
    ) -> Tuple[Optional[ArtifactRecord], List[str]]:
        """Looks up a verified artifact.

        Returns ``(record, problems)``. A record is returned *only* when every
        verification passed; anything else is a miss with a diagnosis, so a
        damaged or foreign artifact can never be consumed as a hit.

        ``recover`` (AP-SRV-070 W4A-C3, Root Finding K) governs whether an
        interrupted force replacement is repaired first. It is on by default -
        that is what makes an ordinary run after a crashed rebuild find the
        last known-good artifact instead of recompiling - and is only turned
        off by ``store()``, which already holds the slot lock and must not try
        to take it a second time.
        """
        record, problems = self._verify_slot_dir(
            self.slot_dir(variant, fingerprint),
            variant=variant,
            fingerprint=fingerprint,
            inputs=inputs,
        )
        if not recover or not self.replaced_backups(variant, fingerprint):
            return record, problems

        # A backup next to this slot means a force replacement was interrupted:
        # either it never finished (restore the last known-good artifact) or it
        # finished but was killed before its own cleanup (drop the debris).
        # Both decisions belong under the slot lock, so they happen there.
        self.recover_slot(variant=variant, fingerprint=fingerprint, inputs=inputs)
        return self._verify_slot_dir(
            self.slot_dir(variant, fingerprint),
            variant=variant,
            fingerprint=fingerprint,
            inputs=inputs,
        )

    # -- write ---------------------------------------------------------------

    def store(
        self,
        *,
        wheel_path: Any,
        fingerprint: str,
        inputs: Mapping[str, Any],
        adopt_existing: bool = True,
    ) -> ArtifactRecord:
        """Verifies a freshly built wheel and stores it atomically.

        The new artifact is fully staged and verified *before* it replaces an
        existing one, and the previous artifact is only deleted after the swap
        succeeded. A failed store therefore leaves the last known-good artifact
        exactly as it was.

        Root Hardening: staging and verifying a candidate needs no
        coordination (each caller stages into its own uniquely named
        directory), but deciding what ends up at the final slot path does -
        two callers finishing at nearly the same moment must not race each
        other's ``os.replace``. That decision is made under a short-held,
        per-(variant, fingerprint) lock.

        ``adopt_existing`` (default ``True``) governs what happens when
        another caller already finished storing a verified artifact for this
        exact slot while this call was staging its own:

        - ``True`` (the reuse-by-default path, after an ordinary cache miss):
          the existing artifact is adopted rather than replaced. Both are
          equally valid for this fingerprint - a second build was only
          started because two callers raced past the same cache-miss check -
          so there is nothing to gain from clobbering a good artifact with
          another one, and every concurrent caller converges on the same,
          single stored artifact instead of doing redundant work for nothing.
        - ``False`` (``--rebuild-kroko``): the caller explicitly asked for a
          fresh build to replace whatever is there, so it always does -
          adopting a stale existing artifact here would silently defeat the
          entire point of a force rebuild.
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

            with self._slot_lock(variant, fingerprint):
                # Root Finding K: a previous force rebuild may have been killed
                # mid-swap, leaving the last known-good artifact under its
                # backup name and no final slot at all. Settle that first, in
                # the same critical section, so `adopt_existing` sees the real
                # state of the slot rather than an apparent cache miss.
                self._recover_slot_locked(variant, fingerprint, inputs)

                if adopt_existing:
                    existing, _ = self.lookup(
                        variant=variant,
                        fingerprint=fingerprint,
                        inputs=inputs,
                        recover=False,
                    )
                    if existing is not None:
                        return existing

                backup = None
                if final.exists():
                    backup = final.with_name(
                        final.name + REPLACED_SUFFIX + uuid.uuid4().hex
                    )
                    os.replace(final, backup)
                try:
                    os.replace(staging, final)
                except OSError:
                    if backup is not None:
                        os.replace(backup, final)
                    raise
                # Purge every backup of this slot, not only the one this call
                # created: a crash between the swap and this cleanup in an
                # earlier run can have left its own behind, and the freshly
                # verified final artifact makes all of them obsolete.
                for stale in self.replaced_backups(variant, fingerprint):
                    shutil.rmtree(stale, ignore_errors=True)
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
    "DEFAULT_LOCK_POLL_SECONDS",
    "DEFAULT_LOCK_TIMEOUT_SECONDS",
    "LOCK_DIR_NAME",
    "REPLACED_SUFFIX",
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
    "wheel_platform_tag_matches_target",
]
