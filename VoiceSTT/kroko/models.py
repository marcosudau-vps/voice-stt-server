"""The Kroko model authority (AP-SRV-070 W4A).

Before W4A the product treated whatever happened to sit behind
``VOICESTT_KROKO_MODEL_ROOT`` as its model authority: any ``.data`` file with a
plausible name was accepted, nothing was integrity-checked, nothing knew which
license tier or runtime variant a file belonged to, and a missing model quietly
turned into a Hugging Face download at server start.

This module replaces that with an explicit manifest
(``VoiceSTT/assets/kroko/models.json``) that pins, for every known model, its
identity, immutable upstream revision, SHA-256, byte count, license class,
redistribution status and the Kroko runtime variant it requires.

Three boundaries are enforced here:

**License.** The manifest ships *metadata only*. No Kroko model is bundled in
Git, in the wheel/sdist or in an image, because the upstream redistribution
grant for the Community models is not unambiguous (see ``licensePolicy`` in the
manifest for the recorded evidence). Provisioning is a deliberate, hash-verified
operator step.

**Variant.** A Pro model requires a Pro runtime. The mismatch is refused loudly
rather than papered over, so a Pro model can never appear to work on a free
runtime and vice versa.

**Determinism.** Nothing here reaches the network. A model that is not present
is a clear provisioning error, never an implicit download.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

#: Existing operator override for the model root. Kept for compatibility, but
#: its contents are now validated against the manifest instead of trusted.
KROKO_MODEL_ROOT_ENV = "VOICESTT_KROKO_MODEL_ROOT"

#: Explicit opt-in for downloading a model. Absent or falsy means the product
#: never downloads by itself (W4A-08).
ALLOW_MODEL_DOWNLOAD_ENV = "VOICESTT_KROKO_ALLOW_MODEL_DOWNLOAD"

#: Opt-in for full SHA-256 verification on the *runtime* path.
#:
#: Provisioning always verifies by hash - that is the moment a wrong or
#: truncated model must be caught. Re-hashing a 150 MB model on every server
#: start buys much less and costs real start-up time, so the runtime path
#: checks the cheap invariants (existence, size, variant) by default and
#: re-hashes only when an operator asks for it here.
VERIFY_MODEL_HASH_ENV = "VOICESTT_KROKO_VERIFY_MODEL_HASH"

MANIFEST_NAME = "models.json"

TRUE_VALUES = {"1", "true", "yes", "on"}

REDISTRIBUTION_ALLOWED = "ALLOWED"
REDISTRIBUTION_POLICY_REQUIRED = "POLICY_REQUIRED"
REDISTRIBUTION_PROHIBITED = "PROHIBITED"


class KrokoModelError(RuntimeError):
    """A Kroko model is unknown, unavailable, corrupt or variant-incompatible."""


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in TRUE_VALUES


def model_download_allowed(options: Optional[Mapping[str, Any]] = None) -> bool:
    """Whether this process may download a Kroko model at all.

    Default ``False``. W4A-08 requires a deterministic production mode: a
    normal server start must never reach out to the network on its own. A
    download is therefore only ever an explicit, opted-in provisioning action.
    """
    options = options or {}
    for key in ("auto_download_model", "download_model"):
        if key in options:
            value = options[key]
            if isinstance(value, str):
                return value.strip().lower() in TRUE_VALUES
            return bool(value)
    return _bool_env(ALLOW_MODEL_DOWNLOAD_ENV, False)


def hash_verification_enabled(options: Optional[Mapping[str, Any]] = None) -> bool:
    """Whether the *runtime* path re-verifies models by full SHA-256.

    Off by default; see :data:`VERIFY_MODEL_HASH_ENV`. Provisioning and the
    explicit verification API do not consult this - they always hash.
    """
    options = options or {}
    if "verify_model_hash" in options:
        value = options["verify_model_hash"]
        if isinstance(value, str):
            return value.strip().lower() in TRUE_VALUES
        return bool(value)
    return _bool_env(VERIFY_MODEL_HASH_ENV, False)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class KrokoModelEntry:
    """One manifested Kroko model."""

    id: str
    filename: str
    language: str
    tier: str
    requires_runtime_variant: str
    license_class: str
    redistribution_status: str
    sha256: str
    bytes: int
    provenance: Mapping[str, Any]

    @property
    def redistributable(self) -> bool:
        """Whether this build may ship the model itself.

        Only an explicit ``ALLOWED`` counts. ``POLICY_REQUIRED`` - the current
        state of the Community models - deliberately does not.
        """
        return self.redistribution_status == REDISTRIBUTION_ALLOWED

    def public_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "filename": self.filename,
            "language": self.language,
            "tier": self.tier,
            "requiresRuntimeVariant": self.requires_runtime_variant,
            "licenseClass": self.license_class,
            "redistributionStatus": self.redistribution_status,
            "sha256": self.sha256,
            "bytes": self.bytes,
        }


class KrokoModelManifest:
    """The loaded, validated model manifest."""

    def __init__(self, payload: Mapping[str, Any], *, path: Optional[Path] = None):
        self._payload = dict(payload)
        self._path = path
        self._entries: Tuple[KrokoModelEntry, ...] = tuple(
            _parse_entry(raw) for raw in payload.get("models", [])
        )
        self._by_id = {entry.id: entry for entry in self._entries}
        self._by_filename = {entry.filename: entry for entry in self._entries}
        self._by_filename_lower = {
            entry.filename.lower(): entry for entry in self._entries
        }

    @property
    def path(self) -> Optional[Path]:
        return self._path

    @property
    def schema_version(self) -> int:
        return int(self._payload.get("schemaVersion", 0))

    @property
    def manifest_revision(self) -> int:
        return int(self._payload.get("manifestRevision", 0))

    @property
    def entries(self) -> Tuple[KrokoModelEntry, ...]:
        return self._entries

    @property
    def license_policy(self) -> Dict[str, Any]:
        return dict(self._payload.get("licensePolicy", {}))

    @property
    def upstream(self) -> Dict[str, Any]:
        return dict(self._payload.get("upstream", {}))

    def get(self, value: Any) -> Optional[KrokoModelEntry]:
        """Looks one model up by id or by file name (case-insensitively)."""
        text = str(value or "").strip()
        if not text:
            return None
        if text in self._by_id:
            return self._by_id[text]
        name = Path(text).name
        if name in self._by_filename:
            return self._by_filename[name]
        return self._by_filename_lower.get(name.lower())

    def redistributable_entries(self) -> Tuple[KrokoModelEntry, ...]:
        """Models this build would be allowed to ship. Currently none."""
        return tuple(entry for entry in self._entries if entry.redistributable)


def _parse_entry(raw: Mapping[str, Any]) -> KrokoModelEntry:
    required = ("id", "filename", "requiresRuntimeVariant", "redistributionStatus")
    for key in required:
        if not str(raw.get(key) or "").strip():
            raise KrokoModelError(f"model manifest entry is missing {key!r}: {raw!r}")
    return KrokoModelEntry(
        id=str(raw["id"]).strip(),
        filename=str(raw["filename"]).strip(),
        language=str(raw.get("language") or "").strip(),
        tier=str(raw.get("tier") or "").strip(),
        requires_runtime_variant=str(raw["requiresRuntimeVariant"]).strip().lower(),
        license_class=str(raw.get("licenseClass") or "").strip(),
        redistribution_status=str(raw["redistributionStatus"]).strip().upper(),
        sha256=str(raw.get("sha256") or "").strip().lower(),
        bytes=int(raw.get("bytes") or 0),
        provenance=dict(raw.get("provenance") or {}),
    )


def default_manifest_path() -> Path:
    """The manifest inside this installed distribution.

    Resolved through the package itself so a wheel install on Windows and on
    Linux finds the same file, exactly like the wake-word bundle does.
    """
    try:
        from importlib import resources

        return Path(str(resources.files("VoiceSTT") / "assets" / "kroko" / MANIFEST_NAME))
    except Exception:  # noqa: BLE001 - packaging fallback, never fatal here
        return Path(__file__).resolve().parent.parent / "assets" / "kroko" / MANIFEST_NAME


def load_manifest(path: Optional[Any] = None) -> KrokoModelManifest:
    """Loads and validates the model manifest."""
    manifest_path = Path(path) if path is not None else default_manifest_path()
    if not manifest_path.is_file():
        raise KrokoModelError(f"missing Kroko model manifest: {manifest_path}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise KrokoModelError(f"unreadable Kroko model manifest: {exc}") from exc
    if not isinstance(payload, dict):
        raise KrokoModelError("Kroko model manifest must be a JSON object")
    return KrokoModelManifest(payload, path=manifest_path)


def candidate_roots(
    options: Optional[Mapping[str, Any]] = None,
    download_root: Optional[Any] = None,
) -> List[Path]:
    """The ordered, explicit model roots this process may read from.

    Only roots an operator actually configured. There is no implicit search of
    the working directory or of any network location.
    """
    options = options or {}
    raw_roots = [
        options.get("model_root"),
        options.get("model_dir"),
        os.environ.get(KROKO_MODEL_ROOT_ENV),
        download_root,
    ]
    roots: List[Path] = []
    for value in raw_roots:
        if not value:
            continue
        candidate = Path(str(value)).expanduser()
        if candidate.suffix == ".data":
            candidate = candidate.parent
        if candidate not in roots:
            roots.append(candidate)
    return roots


def verify_model_file(
    entry: KrokoModelEntry,
    path: Path,
    *,
    verify_hash: bool = True,
) -> Tuple[bool, List[str]]:
    """Verifies one provisioned model file against its manifest entry."""
    problems: List[str] = []
    if not path.is_file():
        return False, [f"model file not found: {path}"]

    actual_bytes = path.stat().st_size
    if entry.bytes and actual_bytes != entry.bytes:
        problems.append(
            f"model size {actual_bytes} does not match the manifested {entry.bytes}"
        )
    if verify_hash and entry.sha256:
        actual = sha256_of(path)
        if actual.lower() != entry.sha256.lower():
            problems.append("model sha256 does not match the manifest")
    return (not problems), problems


def check_variant_compatibility(
    entry: KrokoModelEntry, runtime_variant: Optional[str]
) -> Tuple[bool, Optional[str]]:
    """Whether a model may run on the given Kroko runtime variant.

    An unknown runtime variant is *not* treated as compatible. Refusing to
    guess is the point: a Pro model silently accepted by a free runtime is the
    exact failure W4A-01 forbids.
    """
    if runtime_variant is None:
        return False, (
            f"model {entry.id!r} requires the {entry.requires_runtime_variant!r} "
            "Kroko runtime, but the installed runtime variant could not be determined"
        )
    normalized = str(runtime_variant).strip().lower()
    if normalized != entry.requires_runtime_variant:
        return False, (
            f"model {entry.id!r} requires the {entry.requires_runtime_variant!r} "
            f"Kroko runtime, but the installed runtime is {normalized!r}"
        )
    return True, None


def locate_model(
    value: Any,
    *,
    manifest: Optional[KrokoModelManifest] = None,
    options: Optional[Mapping[str, Any]] = None,
    download_root: Optional[Any] = None,
) -> Dict[str, Any]:
    """Resolves one model request into a fully described, validated result.

    The result is a report rather than a bare path: it names the manifest entry
    (if any), where the file was found, whether it verified, and - when it is
    missing - what an operator has to provision. Nothing is downloaded.
    """
    options = dict(options or {})
    manifest = manifest if manifest is not None else load_manifest()
    requested = str(value or "").strip()
    entry = manifest.get(requested)

    report: Dict[str, Any] = {
        "requested": requested,
        "manifested": entry is not None,
        "entry": entry.public_dict() if entry is not None else None,
        "path": None,
        "verified": False,
        "problems": [],
        "searchedRoots": [],
    }

    direct = Path(requested).expanduser() if requested else None
    found: Optional[Path] = None
    if direct is not None and direct.is_file():
        found = direct.resolve()

    if found is None:
        filename = entry.filename if entry is not None else (
            Path(requested).name if requested else ""
        )
        roots = candidate_roots(options, download_root)
        report["searchedRoots"] = [str(root) for root in roots]
        for root in roots:
            candidate = root / filename
            if candidate.is_file():
                found = candidate.resolve()
                break

    if found is None:
        report["problems"].append("model file is not provisioned on this host")
        return report

    report["path"] = str(found)

    if entry is None:
        # An explicit operator override outside the manifest stays possible,
        # but it is reported as unmanaged rather than silently blessed.
        report["unmanaged"] = True
        report["verified"] = True
        return report

    ok, problems = verify_model_file(
        entry, found, verify_hash=hash_verification_enabled(options)
    )
    report["verified"] = ok
    report["problems"].extend(problems)
    return report


def describe_local_availability(
    manifest: Optional[KrokoModelManifest] = None,
    *,
    options: Optional[Mapping[str, Any]] = None,
    verify_hash: bool = False,
) -> Dict[str, Any]:
    """A machine-readable inventory of manifested models on this host.

    Availability is computed, never stored in the manifest: it is a property of
    the machine, not of the product.
    """
    manifest = manifest if manifest is not None else load_manifest()
    roots = candidate_roots(options)
    models: List[Dict[str, Any]] = []
    for entry in manifest.entries:
        located: Optional[Path] = None
        for root in roots:
            candidate = root / entry.filename
            if candidate.is_file():
                located = candidate
                break
        record = entry.public_dict()
        record["available"] = located is not None
        if located is not None:
            record["path"] = str(located)
            ok, problems = verify_model_file(entry, located, verify_hash=verify_hash)
            record["verified"] = ok
            if problems:
                record["problems"] = problems
        models.append(record)
    return {
        "manifestRevision": manifest.manifest_revision,
        "searchedRoots": [str(root) for root in roots],
        "downloadAllowed": model_download_allowed(),
        "models": models,
    }


def provisioning_error(entry: Optional[KrokoModelEntry], requested: str) -> KrokoModelError:
    """The error raised when a model is required but not provisioned.

    It states what to provision and why the product will not fetch it, so an
    operator is never left guessing whether a download was silently skipped.
    """
    if entry is None:
        return KrokoModelError(
            f"Kroko model {requested!r} is not provisioned and is not part of the "
            "model manifest. Provide an existing .data file, or set "
            f"{KROKO_MODEL_ROOT_ENV} to the directory holding it."
        )
    return KrokoModelError(
        f"Kroko model {entry.id!r} ({entry.filename}) is not provisioned on this host. "
        f"Its redistribution status is {entry.redistribution_status}, so this build "
        "does not ship it and will not download it automatically. Provision the file "
        f"into {KROKO_MODEL_ROOT_ENV} (expected sha256 {entry.sha256 or 'unknown'}), "
        f"or set {ALLOW_MODEL_DOWNLOAD_ENV}=1 to allow an explicit download."
    )


__all__ = [
    "ALLOW_MODEL_DOWNLOAD_ENV",
    "KROKO_MODEL_ROOT_ENV",
    "MANIFEST_NAME",
    "REDISTRIBUTION_ALLOWED",
    "REDISTRIBUTION_POLICY_REQUIRED",
    "REDISTRIBUTION_PROHIBITED",
    "VERIFY_MODEL_HASH_ENV",
    "KrokoModelEntry",
    "KrokoModelError",
    "KrokoModelManifest",
    "candidate_roots",
    "check_variant_compatibility",
    "default_manifest_path",
    "describe_local_availability",
    "hash_verification_enabled",
    "load_manifest",
    "locate_model",
    "model_download_allowed",
    "provisioning_error",
    "sha256_of",
    "verify_model_file",
]
