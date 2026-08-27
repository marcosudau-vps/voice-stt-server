"""AP-SRV-060 wake-word catalog authority.

This module is the single source of truth for *which wake words this build
offers*. It owns exactly five things and deliberately nothing else:

``models.json``
    The bundled manifest under ``VoiceSTT/assets/wakeword_models/`` is the
    canonical catalog authority of the v2 path. A file that merely happens to
    lie next to it never becomes public build capability; unreferenced files
    are reported as diagnostics only.
one resolver
    :func:`normalize_wake_word_token` is the only normalisation in the
    product. Human configuration values resolve against canonical ids,
    display names and *explicit* aliases - never against a heuristic. The
    frozen contract forbids stripping "Hey", so ``jarvis`` resolves to
    ``hey_jarvis`` only because the manifest lists it as an alias.
one snapshot
    :class:`WakeWordCatalogSnapshot` is immutable and carries the public
    projection, the internal artifact projection, availability and the
    resolver index of one consistent catalog state.
one authority
    :class:`WakeWordCatalogAuthority` is server-wide and thread-safe. It keeps
    the last-known-good snapshot, swaps atomically and only on complete
    success, and owns ``catalogRevision``.
``catalogRevision``
    Separate from ``settingsRevision`` and raised only when the *visible*
    catalog projection actually changed.

Public payloads never contain filesystem paths, ``source`` markers, internal
``paths`` maps, runtime objects or secrets. The artifact projection that does
carry paths is internal and is only handed to the loader.
"""

from __future__ import annotations

import copy
import json
import os
import re
import threading
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


#: Override for the bundled asset root. Deployments and tests may point this at
#: another bundle; there is no runtime download and no second discovery path.
WAKEWORD_ASSET_ROOT_ENV = "VOICESTT_WAKEWORD_ASSET_ROOT"

MANIFEST_NAME = "models.json"

#: The one framework the bundled build ships. tflite artifacts are not part of
#: the bundle, so the v2 catalog resolves ONNX only.
BUNDLED_FRAMEWORK = "onnx"

REASON_GLOBALLY_DISABLED = "globally_disabled"
REASON_ARTIFACT_MISSING = "artifact_missing"
REASON_PIPELINE_UNAVAILABLE = "pipeline_unavailable"

#: The frozen wire code of every wake-selection admission problem. It stays a
#: single code so the v2 ``session.rejected`` surface does not change; the
#: precise cause travels in the additive ``reason`` field next to it.
CODE_UNAVAILABLE = "wake_word_unavailable"

REASON_UNKNOWN = "unknown"

_SEPARATORS = re.compile(r"[\s._\-]+")


class WakeWordManifestError(ValueError):
    """A manifest that cannot become a catalog.

    Raised for schema violations, unusable artifacts declarations and, most
    importantly, for id/alias collisions. A collision is a catalog error and is
    never resolved heuristically, by ordering or by file name.
    """


def normalize_wake_word_token(value: Any) -> str:
    """The one tolerant normalisation for human-edited wake-word names.

    Unicode-normalise, trim the outside, casefold, and fold every run of
    separators between word parts into a single ``_``. ``hey_jarvis``,
    ``Hey Jarvis``, ``HEY-JARVIS``, ``hey.jarvis`` and ``hey__jarvis``
    therefore all normalise to the same token. Nothing is added or removed
    beyond that: no word is stripped, no prefix is guessed.
    """
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKC", text).strip()
    text = _SEPARATORS.sub("_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text.casefold()


@dataclass(frozen=True)
class WakeWordArtifact:
    """One classifier artifact of one wake word, in one framework."""

    framework: str
    file_name: str
    path: Path
    sha256: str
    byte_size: int

    @property
    def model_key(self) -> str:
        """The key OpenWakeWord derives from the file name.

        ``openwakeword.model.Model`` names a loaded model by
        ``splitext(basename(path))[0]``. The catalog therefore has to be able
        to translate that key back into the canonical id; the detection layer
        must never publish a file stem as a domain id.
        """
        return Path(self.file_name).stem


@dataclass(frozen=True)
class WakeWordPipeline:
    """The shared feature/pipeline models of one framework.

    Ownership: these two artifacts belong to the *catalog*, not to a single
    wake word. The real OpenWakeWord API takes them per model instance, so
    every session-scoped instance receives the same two paths; they are never
    duplicated per selected classifier and never loaded twice per instance.
    """

    framework: str
    melspectrogram_path: Optional[Path]
    embedding_path: Optional[Path]

    @property
    def available(self) -> bool:
        return bool(
            self.melspectrogram_path
            and self.melspectrogram_path.is_file()
            and self.embedding_path
            and self.embedding_path.is_file()
        )

    def loader_kwargs(self) -> Dict[str, str]:
        """The kwargs the real OpenWakeWord model constructor expects."""
        if not self.available:
            return {}
        return {
            "melspec_model_path": str(self.melspectrogram_path),
            "embedding_model_path": str(self.embedding_path),
        }


@dataclass(frozen=True)
class WakeWordEntry:
    """One catalog entry with its resolved availability."""

    id: str
    display_name: str
    aliases: Tuple[str, ...]
    artifact_version: str
    artifact: WakeWordArtifact
    available: bool
    unavailable_reason: Optional[str] = None

    def public_dict(self) -> Dict[str, Any]:
        """The public catalog projection. Never carries a path or a source."""
        payload: Dict[str, Any] = {
            "id": self.id,
            "displayName": self.display_name,
            "aliases": list(self.aliases),
            "artifactVersion": self.artifact_version,
            "available": bool(self.available),
        }
        if not self.available and self.unavailable_reason:
            payload["unavailableReason"] = self.unavailable_reason
        return payload


@dataclass(frozen=True)
class WakeWordSelection:
    """The internal artifact projection of one admitted selection."""

    entries: Tuple[WakeWordEntry, ...]
    pipeline: WakeWordPipeline
    catalog_revision: int

    @property
    def wake_word_ids(self) -> Tuple[str, ...]:
        return tuple(entry.id for entry in self.entries)

    @property
    def model_paths(self) -> Tuple[str, ...]:
        """Exactly the selected classifiers - selected-only initialisation."""
        return tuple(str(entry.artifact.path) for entry in self.entries)

    @property
    def model_key_to_id(self) -> Dict[str, str]:
        """OpenWakeWord model key -> canonical id, for the detection layer."""
        return {entry.artifact.model_key: entry.id for entry in self.entries}

    def loader_kwargs(self) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"wakeword_models": list(self.model_paths)}
        kwargs.update(self.pipeline.loader_kwargs())
        return kwargs


@dataclass(frozen=True)
class SelectionError:
    """One machine-readable admission error of a rejected selection.

    ``code`` stays the frozen ``wake_word_unavailable``; ``reason`` and
    ``wakeWordId`` are additive fields that name the precise cause and the
    problematic id, as the atomic admission rule requires.
    """

    wake_word_id: str
    reason: str
    message: str
    code: str = CODE_UNAVAILABLE
    field: str = "requestedSession.wakeWordIds"

    def to_dict(self) -> Dict[str, str]:
        return {
            "field": self.field,
            "code": self.code,
            "message": self.message,
            "reason": self.reason,
            "wakeWordId": self.wake_word_id,
        }


@dataclass(frozen=True)
class RefreshResult:
    """The outcome of one catalog refresh or global-disable change."""

    ok: bool
    changed: bool
    catalog_revision: int
    availability_changed: bool = False
    available_wake_word_ids: Tuple[str, ...] = ()
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "ok": bool(self.ok),
            "changed": bool(self.changed),
            "catalogRevision": int(self.catalog_revision),
            "availabilityChanged": bool(self.availability_changed),
            "availableWakeWordIds": list(self.available_wake_word_ids),
        }
        if self.error:
            payload["error"] = self.error
        return payload


class WakeWordCatalogSnapshot:
    """One immutable, fully validated catalog state."""

    def __init__(
        self,
        *,
        catalog_revision: int,
        entries: Sequence[WakeWordEntry],
        pipeline: WakeWordPipeline,
        resolver_index: Mapping[str, str],
        manifest_path: Optional[Path] = None,
        diagnostics: Optional[Mapping[str, Any]] = None,
    ):
        self._catalog_revision = int(catalog_revision)
        self._entries = tuple(sorted(entries, key=lambda entry: entry.id))
        self._by_id = {entry.id: entry for entry in self._entries}
        self._pipeline = pipeline
        self._resolver_index = dict(resolver_index)
        self._manifest_path = manifest_path
        self._diagnostics = dict(diagnostics or {})

    # -- identity ------------------------------------------------------------

    @property
    def catalog_revision(self) -> int:
        return self._catalog_revision

    @property
    def entries(self) -> Tuple[WakeWordEntry, ...]:
        return self._entries

    @property
    def pipeline(self) -> WakeWordPipeline:
        return self._pipeline

    @property
    def manifest_path(self) -> Optional[Path]:
        return self._manifest_path

    @property
    def diagnostics(self) -> Dict[str, Any]:
        return copy.deepcopy(self._diagnostics)

    # -- projections ---------------------------------------------------------

    def public_catalog(self) -> List[Dict[str, Any]]:
        """The public ``wakeWords[]`` projection, deterministically ordered."""
        return [entry.public_dict() for entry in self._entries]

    def available_ids(self) -> Tuple[str, ...]:
        return tuple(entry.id for entry in self._entries if entry.available)

    def capabilities(self) -> Dict[str, Any]:
        """The ``wakeWordCapabilities`` block of ``session.snapshot``."""
        return {
            "catalogRevision": self._catalog_revision,
            "availableWakeWordIds": list(self.available_ids()),
        }

    def visible_projection(self) -> Any:
        """What ``catalogRevision`` is allowed to react to.

        Everything a client can observe, and nothing else. Two catalogs with
        the same visible projection are the same revision, even if an internal
        path or a diagnostic changed.
        """
        return json.dumps(self.public_catalog(), sort_keys=True, ensure_ascii=False)

    # -- resolver ------------------------------------------------------------

    def get(self, wake_word_id: str) -> Optional[WakeWordEntry]:
        return self._by_id.get(wake_word_id)

    def resolve(self, value: Any) -> Optional[str]:
        """The canonical id for one human-entered value, or ``None``.

        Resolution is exact after normalisation. There is no fuzzy match, no
        best match and no ordering rule: a value either normalises onto a
        catalogued id, display name or explicit alias, or it does not resolve.
        """
        token = normalize_wake_word_token(value)
        if not token:
            return None
        return self._resolver_index.get(token)

    def resolve_selection(
        self, values: Sequence[Any]
    ) -> Tuple[Optional[WakeWordSelection], Tuple[SelectionError, ...]]:
        """Atomic admission of one requested selection.

        A single problematic entry rejects the *whole* selection. There is no
        partial load, no default fallback and no silent removal, and every
        problematic id is named. Duplicates in the request collapse onto one
        canonical entry without becoming an error.
        """
        errors: List[SelectionError] = []
        resolved: List[WakeWordEntry] = []
        seen = set()
        for value in values:
            raw = "" if value is None else str(value)
            identifier = self.resolve(raw)
            if identifier is None:
                errors.append(SelectionError(
                    wake_word_id=raw,
                    reason=REASON_UNKNOWN,
                    message=(
                        f"Das Wake Word '{raw}' ist in diesem Build nicht "
                        "bekannt."
                    ),
                ))
                continue
            entry = self._by_id[identifier]
            if not entry.available:
                errors.append(SelectionError(
                    wake_word_id=identifier,
                    reason=entry.unavailable_reason or REASON_ARTIFACT_MISSING,
                    message=(
                        f"Das Wake Word '{identifier}' ist nicht verfügbar "
                        f"({entry.unavailable_reason})."
                    ),
                ))
                continue
            if identifier in seen:
                continue
            seen.add(identifier)
            resolved.append(entry)

        if not errors and not resolved:
            errors.append(SelectionError(
                wake_word_id="",
                code="wake_word_selection_required",
                reason="selection_required",
                message=(
                    "Bei aktivierter Wake-Word-Quelle muss mindestens eine "
                    "Wake-Word-ID ausgewählt sein."
                ),
            ))
        if errors:
            return None, tuple(errors)
        return (
            WakeWordSelection(
                entries=tuple(resolved),
                pipeline=self._pipeline,
                catalog_revision=self._catalog_revision,
            ),
            (),
        )

    # -- derived snapshots ---------------------------------------------------

    def with_catalog_revision(self, revision: int) -> "WakeWordCatalogSnapshot":
        return WakeWordCatalogSnapshot(
            catalog_revision=int(revision),
            entries=self._entries,
            pipeline=self._pipeline,
            resolver_index=self._resolver_index,
            manifest_path=self._manifest_path,
            diagnostics=self._diagnostics,
        )

    def with_global_disabled(
        self, disabled_ids: Sequence[Any]
    ) -> "WakeWordCatalogSnapshot":
        """The same catalog with the global disable projection applied.

        The global disable list is an AP-SRV-050 server setting; the catalog
        only projects it into availability. Values are resolved through the
        one resolver, so an admin may write ``Hey Jarvis`` as well.
        """
        disabled = set()
        for value in disabled_ids or ():
            identifier = self.resolve(value)
            if identifier is not None:
                disabled.add(identifier)
            else:
                token = normalize_wake_word_token(value)
                if token:
                    disabled.add(token)

        entries = []
        for entry in self._entries:
            if entry.id in disabled:
                if entry.available or entry.unavailable_reason != REASON_GLOBALLY_DISABLED:
                    entry = WakeWordEntry(
                        id=entry.id,
                        display_name=entry.display_name,
                        aliases=entry.aliases,
                        artifact_version=entry.artifact_version,
                        artifact=entry.artifact,
                        available=False,
                        unavailable_reason=REASON_GLOBALLY_DISABLED,
                    )
            elif entry.unavailable_reason == REASON_GLOBALLY_DISABLED:
                entry = _entry_with_resolved_availability(entry, self._pipeline)
            entries.append(entry)
        diagnostics = dict(self._diagnostics)
        diagnostics["globalDisabledIds"] = sorted(disabled)
        return WakeWordCatalogSnapshot(
            catalog_revision=self._catalog_revision,
            entries=entries,
            pipeline=self._pipeline,
            resolver_index=self._resolver_index,
            manifest_path=self._manifest_path,
            diagnostics=diagnostics,
        )


def _entry_with_resolved_availability(
    entry: WakeWordEntry, pipeline: WakeWordPipeline
) -> WakeWordEntry:
    available, reason = _artifact_availability(entry.artifact, pipeline)
    return WakeWordEntry(
        id=entry.id,
        display_name=entry.display_name,
        aliases=entry.aliases,
        artifact_version=entry.artifact_version,
        artifact=entry.artifact,
        available=available,
        unavailable_reason=reason,
    )


def _artifact_availability(
    artifact: WakeWordArtifact, pipeline: WakeWordPipeline
) -> Tuple[bool, Optional[str]]:
    if not artifact.path.is_file():
        return False, REASON_ARTIFACT_MISSING
    if not pipeline.available:
        return False, REASON_PIPELINE_UNAVAILABLE
    return True, None


# -- manifest loading ----------------------------------------------------------

def default_asset_root() -> Path:
    """The bundled asset root of this installation.

    Resolved through the package itself so a wheel/sdist installation on
    Windows and on Ubuntu finds the same assets, with an explicit environment
    override for deployments that ship the bundle elsewhere. There is never a
    runtime download.
    """
    override = os.getenv(WAKEWORD_ASSET_ROOT_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    try:
        from importlib import resources

        return Path(str(resources.files("VoiceSTT") / "assets" / "wakeword_models"))
    except Exception:  # noqa: BLE001 - packaging fallback, never fatal here
        return Path(__file__).resolve().parent.parent / "assets" / "wakeword_models"


def load_snapshot(asset_root: Optional[Path] = None) -> WakeWordCatalogSnapshot:
    """Reads and fully validates one manifest into a candidate snapshot.

    Every failure raises :class:`WakeWordManifestError`; the caller decides
    whether that means "no catalog yet" or "keep the last known good one".
    """
    root = Path(asset_root) if asset_root is not None else default_asset_root()
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise WakeWordManifestError(f"missing wake-word manifest: {manifest_path}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise WakeWordManifestError(f"unreadable wake-word manifest: {exc}") from exc
    if not isinstance(payload, dict):
        raise WakeWordManifestError("wake-word manifest must be a JSON object")

    pipeline = _parse_pipeline(payload, root)
    entries, resolver_index = _parse_entries(payload, root, pipeline)

    declared = payload.get("catalogRevision")
    revision = int(declared) if isinstance(declared, int) and not isinstance(declared, bool) else 1
    if revision < 1:
        raise WakeWordManifestError("catalogRevision must be >= 1")

    declared_files = {entry.artifact.file_name for entry in entries}
    if pipeline.melspectrogram_path is not None:
        declared_files.add(pipeline.melspectrogram_path.name)
    if pipeline.embedding_path is not None:
        declared_files.add(pipeline.embedding_path.name)
    unmanaged = sorted(
        path.name for path in root.glob("*.onnx")
        if path.name not in declared_files
    ) if root.is_dir() else []

    return WakeWordCatalogSnapshot(
        catalog_revision=revision,
        entries=entries,
        pipeline=pipeline,
        resolver_index=resolver_index,
        manifest_path=manifest_path,
        diagnostics={
            "manifestVersion": payload.get("manifestVersion"),
            "assetRoot": str(root),
            # Diagnostic only: a file that merely lies in the asset directory
            # is never public build capability.
            "unmanagedArtifacts": unmanaged,
        },
    )


def _parse_pipeline(payload: Mapping[str, Any], root: Path) -> WakeWordPipeline:
    pipeline_section = payload.get("pipeline")
    if not isinstance(pipeline_section, dict):
        raise WakeWordManifestError("wake-word manifest has no 'pipeline' section")
    framework_section = pipeline_section.get(BUNDLED_FRAMEWORK)
    if not isinstance(framework_section, dict):
        raise WakeWordManifestError(
            f"wake-word manifest has no '{BUNDLED_FRAMEWORK}' pipeline models"
        )
    paths = {}
    for role in ("melspectrogram", "embedding"):
        spec = framework_section.get(role)
        if not isinstance(spec, dict) or not str(spec.get("file") or "").strip():
            raise WakeWordManifestError(
                f"wake-word manifest pipeline model '{role}' is missing"
            )
        paths[role] = root / str(spec["file"]).strip()
    return WakeWordPipeline(
        framework=BUNDLED_FRAMEWORK,
        melspectrogram_path=paths["melspectrogram"],
        embedding_path=paths["embedding"],
    )


def _parse_entries(
    payload: Mapping[str, Any], root: Path, pipeline: WakeWordPipeline
) -> Tuple[Tuple[WakeWordEntry, ...], Dict[str, str]]:
    raw_entries = payload.get("wakeWords")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise WakeWordManifestError("wake-word manifest has no 'wakeWords' entries")

    entries: List[WakeWordEntry] = []
    resolver_index: Dict[str, str] = {}
    # token -> ("id" | "displayName" | "alias", owning canonical id)
    origins: Dict[str, Tuple[str, str]] = {}

    def claim(token: str, kind: str, owner: str) -> None:
        if not token:
            raise WakeWordManifestError(
                f"empty {kind} for wake word '{owner}' after normalisation"
            )
        existing = origins.get(token)
        if existing is not None and existing[1] != owner:
            raise WakeWordManifestError(
                "wake-word catalog collision after normalisation: "
                f"'{token}' is claimed by {existing[0]} of '{existing[1]}' "
                f"and by {kind} of '{owner}'"
            )
        if existing is None:
            origins[token] = (kind, owner)
            resolver_index[token] = owner

    for raw in raw_entries:
        if not isinstance(raw, dict):
            raise WakeWordManifestError("every wakeWords entry must be an object")
        identifier = str(raw.get("id") or "").strip()
        if not identifier:
            raise WakeWordManifestError("wakeWords entry without 'id'")
        if normalize_wake_word_token(identifier) != identifier:
            raise WakeWordManifestError(
                f"wake-word id '{identifier}' is not canonical; expected "
                f"'{normalize_wake_word_token(identifier)}'"
            )
        display_name = str(raw.get("displayName") or "").strip()
        if not display_name:
            raise WakeWordManifestError(f"wake word '{identifier}' has no displayName")
        artifact_version = str(raw.get("artifactVersion") or "").strip()
        if not artifact_version:
            raise WakeWordManifestError(
                f"wake word '{identifier}' has no artifactVersion"
            )

        aliases_raw = raw.get("aliases", [])
        if not isinstance(aliases_raw, list) or any(
            not isinstance(item, str) for item in aliases_raw
        ):
            raise WakeWordManifestError(
                f"wake word '{identifier}' has a non-string alias list"
            )

        artifacts = raw.get("artifacts")
        if not isinstance(artifacts, dict):
            raise WakeWordManifestError(
                f"wake word '{identifier}' has no artifacts mapping"
            )
        spec = artifacts.get(BUNDLED_FRAMEWORK)
        if not isinstance(spec, dict) or not str(spec.get("file") or "").strip():
            raise WakeWordManifestError(
                f"wake word '{identifier}' has no {BUNDLED_FRAMEWORK} artifact"
            )
        file_name = str(spec["file"]).strip()
        artifact = WakeWordArtifact(
            framework=BUNDLED_FRAMEWORK,
            file_name=file_name,
            path=root / file_name,
            sha256=str(spec.get("sha256") or ""),
            byte_size=int(spec.get("bytes") or 0),
        )

        claim(normalize_wake_word_token(identifier), "id", identifier)
        claim(normalize_wake_word_token(display_name), "displayName", identifier)
        aliases = []
        for alias in aliases_raw:
            token = normalize_wake_word_token(alias)
            claim(token, "alias", identifier)
            if token not in aliases:
                aliases.append(token)

        available, reason = _artifact_availability(artifact, pipeline)
        entries.append(WakeWordEntry(
            id=identifier,
            display_name=display_name,
            aliases=tuple(aliases),
            artifact_version=artifact_version,
            artifact=artifact,
            available=available,
            unavailable_reason=reason,
        ))

    model_keys: Dict[str, str] = {}
    for entry in entries:
        key = entry.artifact.model_key
        owner = model_keys.get(key)
        if owner is not None:
            raise WakeWordManifestError(
                "wake-word catalog collision: artifact file stem "
                f"'{key}' is shared by '{owner}' and '{entry.id}'"
            )
        model_keys[key] = entry.id

    return tuple(entries), resolver_index


class WakeWordCatalogAuthority:
    """The one server-wide, thread-safe wake-word catalog authority.

    It owns the last-known-good snapshot and ``catalogRevision``. A refresh
    builds a complete candidate first and swaps atomically only on total
    success; a failing refresh leaves the running catalog untouched. The
    revision is raised only when the *visible* projection changed, and any
    availability change is announced through the injected callback, which the
    server binds to the existing AP-SRV-040 event authority.
    """

    def __init__(
        self,
        *,
        asset_root: Optional[Path] = None,
        loader=None,
        global_disabled_ids: Sequence[Any] = (),
        on_availability_changed=None,
    ):
        self._asset_root = Path(asset_root) if asset_root is not None else None
        self._loader = loader or load_snapshot
        self._lock = threading.RLock()
        self._on_availability_changed = on_availability_changed
        self._global_disabled = tuple(global_disabled_ids or ())
        self._snapshot: Optional[WakeWordCatalogSnapshot] = None
        self._load_error: Optional[str] = None
        self._reload_locked(initial=True)

    # -- state ---------------------------------------------------------------

    @property
    def load_error(self) -> Optional[str]:
        with self._lock:
            return self._load_error

    @property
    def catalog_revision(self) -> int:
        with self._lock:
            return self._snapshot.catalog_revision if self._snapshot else 0

    def snapshot(self) -> Optional[WakeWordCatalogSnapshot]:
        """The current last-known-good snapshot (immutable)."""
        with self._lock:
            return self._snapshot

    def available_ids(self) -> Tuple[str, ...]:
        snapshot = self.snapshot()
        return snapshot.available_ids() if snapshot else ()

    def capabilities(self) -> Dict[str, Any]:
        snapshot = self.snapshot()
        if snapshot is None:
            return {"catalogRevision": 0, "availableWakeWordIds": []}
        return snapshot.capabilities()

    def public_payload(self, *, protocol_version: int = 2) -> Dict[str, Any]:
        """The ``GET /api/v2/wake-words`` body (SET-13b)."""
        snapshot = self.snapshot()
        return {
            "protocolVersion": int(protocol_version),
            "catalogRevision": snapshot.catalog_revision if snapshot else 0,
            "wakeWords": snapshot.public_catalog() if snapshot else [],
        }

    def resolve(self, value: Any) -> Optional[str]:
        snapshot = self.snapshot()
        return snapshot.resolve(value) if snapshot else None

    def resolve_selection(self, values: Sequence[Any]):
        """Atomic admission against the current snapshot."""
        snapshot = self.snapshot()
        if snapshot is None:
            return None, (SelectionError(
                wake_word_id="",
                reason="catalog_unavailable",
                message=(
                    "Der Wake-Word-Katalog ist auf diesem Server nicht "
                    "verfügbar."
                ),
            ),)
        return snapshot.resolve_selection(values)

    # -- mutation ------------------------------------------------------------

    def refresh(self) -> RefreshResult:
        """Re-reads manifest and artifacts and swaps atomically on success."""
        with self._lock:
            return self._reload_locked(initial=False)

    def set_global_disabled(self, disabled_ids: Sequence[Any]) -> RefreshResult:
        """Applies the AP-SRV-050 global disable list to availability."""
        with self._lock:
            self._global_disabled = tuple(disabled_ids or ())
            if self._snapshot is None:
                return RefreshResult(
                    ok=False,
                    changed=False,
                    catalog_revision=0,
                    error=self._load_error or "catalog_unavailable",
                )
            candidate = self._snapshot.with_global_disabled(self._global_disabled)
            return self._commit_locked(candidate)

    # -- internals -----------------------------------------------------------

    def _reload_locked(self, *, initial: bool) -> RefreshResult:
        try:
            candidate = self._loader(self._asset_root)
        except WakeWordManifestError as exc:
            self._load_error = str(exc)
            if self._snapshot is None:
                return RefreshResult(
                    ok=False, changed=False, catalog_revision=0, error=str(exc)
                )
            # Last-known-good stays in place, untouched.
            return RefreshResult(
                ok=False,
                changed=False,
                catalog_revision=self._snapshot.catalog_revision,
                available_wake_word_ids=self._snapshot.available_ids(),
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 - a refresh must never crash the server
            self._load_error = f"{type(exc).__name__}: {exc}"
            revision = self._snapshot.catalog_revision if self._snapshot else 0
            return RefreshResult(
                ok=False,
                changed=False,
                catalog_revision=revision,
                error=self._load_error,
            )

        self._load_error = None
        candidate = candidate.with_global_disabled(self._global_disabled)
        return self._commit_locked(candidate, initial=initial)

    def _commit_locked(
        self, candidate: WakeWordCatalogSnapshot, *, initial: bool = False
    ) -> RefreshResult:
        current = self._snapshot
        if current is None:
            self._snapshot = candidate
            return RefreshResult(
                ok=True,
                changed=True,
                catalog_revision=candidate.catalog_revision,
                availability_changed=not initial,
                available_wake_word_ids=candidate.available_ids(),
            )

        changed = candidate.visible_projection() != current.visible_projection()
        if not changed:
            # No *visible* change: the revision must not move. The candidate is
            # still adopted so internal paths and diagnostics stay current.
            self._snapshot = candidate.with_catalog_revision(
                current.catalog_revision
            )
            return RefreshResult(
                ok=True,
                changed=False,
                catalog_revision=current.catalog_revision,
                available_wake_word_ids=current.available_ids(),
            )

        revision = current.catalog_revision + 1
        committed = candidate.with_catalog_revision(revision)
        availability_changed = committed.available_ids() != current.available_ids()
        self._snapshot = committed
        result = RefreshResult(
            ok=True,
            changed=True,
            catalog_revision=revision,
            availability_changed=True,
            available_wake_word_ids=committed.available_ids(),
        )
        callback = self._on_availability_changed
        if callback is not None:
            try:
                callback(revision, list(committed.available_ids()), availability_changed)
            except Exception:  # noqa: BLE001 - a subscriber must not break the swap
                pass
        return result
