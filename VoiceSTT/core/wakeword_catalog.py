"""AP-SRV-060 wake-word catalog authority.

This module is the single source of truth for *which wake words this build
offers, and under which inference backend they can really be loaded*.

``models.json``
    The bundled manifest under ``VoiceSTT/assets/wakeword_models/`` is the
    canonical catalog authority of the v2 path. A file that merely happens to
    lie next to it never becomes public build capability; unreferenced files
    are reported as diagnostics only.

two clearly separated admission paths (Root F1)
    :func:`normalize_wake_word_token` is the only normalisation in the
    product, and it serves **human configuration only**: config values resolve
    against canonical ids, display names and *explicit* aliases - never
    against a heuristic. That is :meth:`WakeWordCatalogSnapshot.resolve` /
    :meth:`resolve_human_selection`.

    The **v2 wire** is different: ``requestedSession.wakeWordIds`` carries
    canonical ids, full stop. :meth:`admit_selection` accepts nothing else.

loadability at load and refresh (Root F3, corrected by Root F12)
    A model is never ``available=true`` just because a file exists. At the
    initial catalog load and at **every** ``POST /api/v2/wake-words/refresh``
    the authority validates the manifest, the canonical ids/aliases, the
    declared artifact integrity, *both* declared artifact formats, the runtime
    availability, the shared pipeline assets and the **real probe loadability**
    of every declared classifier artifact, and records per-backend health.

    C2 skipped the real ONNX probe when ONNXRuntime did not import, which made
    "no runtime" look like "healthy". C3 treats an absent runtime as an
    unhealthy backend (``runtime_unavailable``) - never as a passed probe.

dual backend (C3 section 10)
    Health is per backend; admission is per *selection*. A live engine holds
    one upstream model and therefore one inference framework, so a selection is
    admitted only when a single common backend is healthy for **all** of its
    wake words. The choice itself lives in :mod:`VoiceSTT.core.wake_backend`.

one snapshot / one authority
    :class:`WakeWordCatalogSnapshot` is immutable and carries the public
    projection, the internal artifact projection, availability and the resolver
    index of one consistent catalog state.
    :class:`WakeWordCatalogAuthority` is server-wide and thread-safe. It keeps
    the last-known-good snapshot, swaps atomically and only on complete
    success, and owns ``catalogRevision``.

``catalogRevision``
    Separate from ``settingsRevision`` and raised only when the *visible*
    catalog projection actually changed. Every public entry carries the
    revision of the snapshot it came from (Root F9), and every refresh returns
    an immutable snapshot so a caller never has to read the authority twice and
    can never mix two states (Root F10).

public semantics (C3 section 11.1)
    A model that cannot be loaded does **not** disappear from the public
    catalog. It stays queryable with ``available=false`` and a machine-readable,
    non-secret ``unavailableReason``; only genuinely available ids appear in
    ``availableWakeWordIds``. Public payloads never contain filesystem paths,
    ``source`` markers, internal ``paths`` maps, runtime objects or secrets.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .wake_backend import (
    BACKEND_AUTO,
    BACKEND_ONNX,
    BACKEND_TFLITE,
    INFERENCE_BACKENDS,
    REASON_BACKEND_UNAVAILABLE,
    REASON_NO_COMMON_BACKEND,
    select_common_backend,
)


#: Override for the bundled asset root. Deployments and tests may point this at
#: another bundle; there is no runtime download and no second discovery path.
WAKEWORD_ASSET_ROOT_ENV = "VOICESTT_WAKEWORD_ASSET_ROOT"

MANIFEST_NAME = "models.json"

#: Historical name of the single bundled framework. Kept so external readers of
#: the constant do not break; the catalog itself is backend-plural now.
BUNDLED_FRAMEWORK = BACKEND_ONNX

#: File suffix of one backend's artifacts, used only for diagnostics of files
#: that are not declared in the manifest.
BACKEND_SUFFIX = {BACKEND_ONNX: ".onnx", BACKEND_TFLITE: ".tflite"}

REASON_GLOBALLY_DISABLED = "globally_disabled"
REASON_ARTIFACT_MISSING = "artifact_missing"
REASON_PIPELINE_UNAVAILABLE = "pipeline_unavailable"
#: The artifact exists but the real inference runtime refuses to load it.
REASON_ARTIFACT_UNLOADABLE = "artifact_unloadable"
#: The artifact on disk does not match the integrity data of the manifest.
REASON_ARTIFACT_INTEGRITY = "artifact_integrity_mismatch"
#: No inference runtime for that backend is installed, so nothing can be
#: probed. Root F12: this is *not* a passed probe.
REASON_RUNTIME_UNAVAILABLE = "runtime_unavailable"
#: A wire value that is not a canonical id - an alias, a display name or any
#: other tolerated human spelling. Tolerance is a config feature, not a wire
#: feature (Root F1).
REASON_NOT_CANONICAL = "not_canonical"

#: The frozen wire code of every wake-selection admission problem. It stays a
#: single code so the v2 ``session.rejected`` surface does not change; the
#: precise cause travels in the additive ``reason`` field next to it.
CODE_UNAVAILABLE = "wake_word_unavailable"

REASON_UNKNOWN = "unknown"

#: Deterministic order in which an entry's unavailability reason is reported.
_REASON_BACKEND_ORDER = INFERENCE_BACKENDS

_SEPARATORS = re.compile(r"[\s._\-]+")

#: Distinguishes "argument not given" from an explicit ``None``.
_UNSET = object()


class WakeWordArtifactError(RuntimeError):
    """One artifact that the real inference runtime refuses to load."""


class WakeWordManifestError(ValueError):
    """A manifest that cannot become a catalog.

    Raised for schema violations, unusable artifact declarations and, most
    importantly, for id/alias collisions. A collision is a catalog error and is
    never resolved heuristically, by ordering or by file name.
    """


def normalize_wake_word_token(value: Any) -> str:
    """The one tolerant normalisation for human-edited wake-word names.

    Unicode-normalise, trim the outside, casefold, and fold every run of
    separators between word parts into a single ``_``. Nothing is added or
    removed beyond that: no word is stripped, no prefix is guessed.
    """
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKC", text).strip()
    text = _SEPARATORS.sub("_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text.casefold()


def _sha256_of(path: Path) -> Optional[str]:
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError:
        return None


@dataclass(frozen=True)
class WakeWordArtifact:
    """One classifier artifact of one wake word, in one inference backend."""

    backend: str
    file_name: str
    path: Path
    sha256: str = ""
    byte_size: int = 0

    @property
    def framework(self) -> str:
        """Historical name of :attr:`backend`."""
        return self.backend

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
    """The shared feature/pipeline models, per inference backend.

    Ownership: these artifacts belong to the *catalog*, not to a single wake
    word. The real OpenWakeWord API takes them per model instance, so every
    session-scoped instance receives the same two paths of its backend; they
    are never duplicated per selected classifier.
    """

    paths: Mapping[str, Tuple[Optional[Path], Optional[Path]]]

    @property
    def backends(self) -> Tuple[str, ...]:
        return tuple(
            backend for backend in INFERENCE_BACKENDS if backend in self.paths
        )

    @property
    def framework(self) -> str:
        """Historical single-framework accessor: the first declared backend."""
        backends = self.backends
        return backends[0] if backends else BACKEND_ONNX

    def artifacts(self, backend: str) -> Tuple[Optional[Path], Optional[Path]]:
        return self.paths.get(backend, (None, None))

    def files_present(self, backend: str) -> bool:
        melspec, embedding = self.artifacts(backend)
        return bool(
            melspec and melspec.is_file() and embedding and embedding.is_file()
        )

    def available_for(self, backend: str) -> bool:
        return self.files_present(backend)

    @property
    def available(self) -> bool:
        """Whether at least one backend's pipeline files are present."""
        return any(self.files_present(backend) for backend in self.backends)

    def loader_kwargs(self, backend: str) -> Dict[str, str]:
        """The kwargs the real OpenWakeWord model constructor expects."""
        if not self.files_present(backend):
            return {}
        melspec, embedding = self.artifacts(backend)
        return {
            "melspec_model_path": str(melspec),
            "embedding_model_path": str(embedding),
        }


@dataclass(frozen=True)
class BackendHealth:
    """Whether one wake word can really be loaded under one backend."""

    backend: str
    available: bool
    reason: Optional[str] = None

    def public_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"available": bool(self.available)}
        if not self.available and self.reason:
            payload["unavailableReason"] = self.reason
        return payload


@dataclass(frozen=True)
class WakeWordEntry:
    """One catalog entry with its per-backend health and its availability."""

    id: str
    display_name: str
    aliases: Tuple[str, ...]
    artifact_version: str
    artifacts: Mapping[str, WakeWordArtifact]
    backend_health: Mapping[str, BackendHealth] = None
    available: bool = False
    unavailable_reason: Optional[str] = None

    @property
    def declared_backends(self) -> Tuple[str, ...]:
        return tuple(
            backend for backend in INFERENCE_BACKENDS if backend in self.artifacts
        )

    @property
    def healthy_backends(self) -> Tuple[str, ...]:
        health = self.backend_health or {}
        return tuple(
            backend for backend in INFERENCE_BACKENDS
            if backend in health and health[backend].available
        )

    @property
    def artifact(self) -> Optional[WakeWordArtifact]:
        """The first declared artifact. Historical single-backend accessor."""
        for backend in self.declared_backends:
            return self.artifacts[backend]
        return None

    def artifact_for(self, backend: str) -> Optional[WakeWordArtifact]:
        return self.artifacts.get(backend)

    def public_dict(self) -> Dict[str, Any]:
        """The public catalog projection. Never carries a path or a source."""
        health = self.backend_health or {}
        payload: Dict[str, Any] = {
            "id": self.id,
            "displayName": self.display_name,
            "aliases": list(self.aliases),
            "artifactVersion": self.artifact_version,
            "available": bool(self.available),
            "backends": {
                backend: (
                    health[backend].public_dict() if backend in health
                    else {
                        "available": False,
                        "unavailableReason": REASON_ARTIFACT_MISSING,
                    }
                )
                for backend in INFERENCE_BACKENDS
            },
        }
        if not self.available and self.unavailable_reason:
            payload["unavailableReason"] = self.unavailable_reason
        return payload


@dataclass(frozen=True)
class WakeWordSelection:
    """The internal artifact projection of one admitted selection.

    ``backend`` is the **one** inference backend every entry of this selection
    runs on. There is no per-model mixture inside a live engine.
    """

    entries: Tuple[WakeWordEntry, ...]
    pipeline: WakeWordPipeline
    catalog_revision: int
    backend: str = BACKEND_ONNX
    fallback_used: bool = False
    requested_backend: str = BACKEND_AUTO

    @property
    def wake_word_ids(self) -> Tuple[str, ...]:
        return tuple(entry.id for entry in self.entries)

    @property
    def model_paths(self) -> Tuple[str, ...]:
        """Exactly the selected classifiers - selected-only initialisation."""
        return tuple(
            str(entry.artifacts[self.backend].path) for entry in self.entries
        )

    @property
    def model_key_to_id(self) -> Dict[str, str]:
        """OpenWakeWord model key -> canonical id, for the detection layer."""
        return {
            entry.artifacts[self.backend].model_key: entry.id
            for entry in self.entries
        }

    def loader_kwargs(self) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "wakeword_models": list(self.model_paths),
            "inference_framework": self.backend,
        }
        kwargs.update(self.pipeline.loader_kwargs(self.backend))
        return kwargs

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wakeWordIds": list(self.wake_word_ids),
            "backend": self.backend,
            "requestedBackend": self.requested_backend,
            "fallbackUsed": bool(self.fallback_used),
            "catalogRevision": int(self.catalog_revision),
        }


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
    """The outcome of one catalog refresh or global-disable change.

    Root F10: the result carries the immutable ``snapshot`` it describes, so an
    HTTP handler renders revision, entries and availability from **one** state
    and never reads the authority a second time.
    """

    ok: bool
    changed: bool
    catalog_revision: int
    availability_changed: bool = False
    available_wake_word_ids: Tuple[str, ...] = ()
    error: Optional[str] = None
    snapshot: Optional["WakeWordCatalogSnapshot"] = None

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

    def public_payload(self, *, protocol_version: int = 2) -> Dict[str, Any]:
        """One atomic public projection of exactly the snapshot described."""
        payload = self.to_dict()
        payload["protocolVersion"] = int(protocol_version)
        snapshot = self.snapshot
        payload["wakeWords"] = snapshot.public_catalog() if snapshot else []
        if snapshot is not None:
            payload["catalogRevision"] = snapshot.catalog_revision
            payload["availableWakeWordIds"] = list(snapshot.available_ids())
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
        """The public ``wakeWords[]`` projection, deterministically ordered.

        Root F9: every entry carries the revision of the snapshot it came from,
        so a client can never pair an entry with the wrong top-level revision.
        C3 section 11.1: unloadable entries stay listed with ``available=false``
        and a machine-readable reason.
        """
        payload = []
        for entry in self._entries:
            item = entry.public_dict()
            item["catalogRevision"] = self._catalog_revision
            payload.append(item)
        return payload

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

        Everything a client can observe *except the revision itself*. Including
        the per-entry revision here would make every catalog differ from every
        other one and bump the revision on each refresh, so the comparison runs
        on the revision-free entry projection.
        """
        entries = [entry.public_dict() for entry in self._entries]
        return json.dumps(entries, sort_keys=True, ensure_ascii=False)

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

    def admit_selection(
        self,
        values: Sequence[Any],
        *,
        canonical_only: bool = True,
        requested_backend: Any = BACKEND_AUTO,
        platform: Optional[str] = None,
    ) -> Tuple[Optional[WakeWordSelection], Tuple[SelectionError, ...]]:
        """Atomic admission of one requested selection.

        A single problematic entry rejects the *whole* selection. There is no
        partial load, no default fallback and no silent removal, and every
        problematic id is named. Duplicates in the request collapse onto one
        canonical entry without becoming an error.

        ``canonical_only`` is the v2 wire mode (Root F1): a value that is not
        already a canonical id is refused with ``reason=not_canonical``, even
        when the tolerant human resolver would have understood it.

        The backend gate (Root F12) runs last: the selection is admitted only
        when a single common backend is healthy for **every** selected wake
        word under the requested backend policy.
        """
        errors: List[SelectionError] = []
        resolved: List[WakeWordEntry] = []
        seen = set()
        for value in values:
            raw = "" if value is None else str(value)
            if canonical_only:
                identifier = raw if raw in self._by_id else None
                if identifier is None:
                    tolerated = self.resolve(raw)
                    errors.append(SelectionError(
                        wake_word_id=raw,
                        reason=(
                            REASON_NOT_CANONICAL if tolerated is not None
                            else REASON_UNKNOWN
                        ),
                        message=(
                            f"'{raw}' ist keine kanonische Wake-Word-ID."
                            if tolerated is not None else
                            f"Das Wake Word '{raw}' ist in diesem Build nicht "
                            "bekannt."
                        ),
                    ))
                    continue
            else:
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

        backend_selection = select_common_backend(
            requested_backend,
            self.common_backends(resolved),
            platform=platform,
        )
        if not backend_selection.admitted:
            return None, (self._backend_error(resolved, backend_selection),)

        return (
            WakeWordSelection(
                entries=tuple(resolved),
                pipeline=self._pipeline,
                catalog_revision=self._catalog_revision,
                backend=backend_selection.backend,
                fallback_used=backend_selection.fallback_used,
                requested_backend=backend_selection.requested,
            ),
            (),
        )

    def common_backends(self, entries: Sequence[WakeWordEntry]) -> Tuple[str, ...]:
        """Backends healthy for **every** entry of one selection."""
        if not entries:
            return ()
        common = set(INFERENCE_BACKENDS)
        for entry in entries:
            common &= set(entry.healthy_backends)
            if not common:
                break
        return tuple(
            backend for backend in INFERENCE_BACKENDS if backend in common
        )

    def _backend_error(self, entries, backend_selection) -> SelectionError:
        wake_word_ids = ", ".join(entry.id for entry in entries)
        if backend_selection.reason == REASON_BACKEND_UNAVAILABLE:
            message = (
                f"Das Inference-Backend '{backend_selection.requested}' ist "
                f"für die gewählten Wake Words ({wake_word_ids}) nicht "
                "verfügbar."
            )
        else:
            message = (
                "Für die gewählten Wake Words "
                f"({wake_word_ids}) gibt es kein gemeinsames verfügbares "
                "Inference-Backend."
            )
        return SelectionError(
            wake_word_id=entries[0].id if entries else "",
            reason=backend_selection.reason,
            message=message,
        )

    def resolve_human_selection(self, values: Sequence[Any], **kwargs):
        """Tolerant admission for human configuration values only."""
        return self.admit_selection(values, canonical_only=False, **kwargs)

    # -- derived snapshots ---------------------------------------------------

    def _derive(self, entries, *, revision=None, diagnostics=None):
        return WakeWordCatalogSnapshot(
            catalog_revision=(
                self._catalog_revision if revision is None else int(revision)
            ),
            entries=entries,
            pipeline=self._pipeline,
            resolver_index=self._resolver_index,
            manifest_path=self._manifest_path,
            diagnostics=(
                self._diagnostics if diagnostics is None else diagnostics
            ),
        )

    def with_catalog_revision(self, revision: int) -> "WakeWordCatalogSnapshot":
        return self._derive(self._entries, revision=revision)

    def with_backend_health(self, probers: Mapping[str, Any]) -> "WakeWordCatalogSnapshot":
        """The same catalog with per-backend health really resolved.

        This is the C3 loadability gate. It runs at the initial load and at
        every refresh, and it probes each declared classifier artifact and the
        shared pipeline models of its backend with the real inference runtime.
        """
        entries = [
            _entry_with_backend_health(entry, self._pipeline, probers)
            for entry in self._entries
        ]
        diagnostics = dict(self._diagnostics)
        diagnostics["probedBackends"] = sorted(
            backend for backend in INFERENCE_BACKENDS if backend in (probers or {})
        )
        diagnostics["runtimeUnavailableBackends"] = sorted(
            backend for backend in INFERENCE_BACKENDS
            if (probers or {}).get(backend) is None
        )
        return self._derive(entries, diagnostics=diagnostics)

    def with_global_disabled(
        self, disabled_ids: Sequence[Any]
    ) -> "WakeWordCatalogSnapshot":
        """The same catalog with the global disable projection applied.

        The global disable list is an AP-SRV-050 server setting; the catalog
        only projects it into availability. Values are resolved through the one
        resolver, so an admin may write ``Hey Jarvis`` as well.
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
                    entry = _replace_entry(
                        entry,
                        available=False,
                        unavailable_reason=REASON_GLOBALLY_DISABLED,
                    )
            elif entry.unavailable_reason == REASON_GLOBALLY_DISABLED:
                entry = _replace_entry(
                    entry,
                    available=bool(entry.healthy_backends),
                    unavailable_reason=_entry_reason(entry),
                )
            entries.append(entry)
        diagnostics = dict(self._diagnostics)
        diagnostics["globalDisabledIds"] = sorted(disabled)
        return self._derive(entries, diagnostics=diagnostics)


def _replace_entry(entry: WakeWordEntry, **changes) -> WakeWordEntry:
    values = {
        "id": entry.id,
        "display_name": entry.display_name,
        "aliases": entry.aliases,
        "artifact_version": entry.artifact_version,
        "artifacts": entry.artifacts,
        "backend_health": entry.backend_health,
        "available": entry.available,
        "unavailable_reason": entry.unavailable_reason,
    }
    values.update(changes)
    return WakeWordEntry(**values)


def _entry_reason(entry: WakeWordEntry) -> Optional[str]:
    """The deterministic public reason of an unavailable entry."""
    if entry.healthy_backends:
        return None
    health = entry.backend_health or {}
    for backend in _REASON_BACKEND_ORDER:
        record = health.get(backend)
        if record is not None and record.reason:
            return record.reason
    return REASON_ARTIFACT_MISSING


def probe_backend_health(
    artifact: Optional[WakeWordArtifact],
    pipeline: WakeWordPipeline,
    backend: str,
    probers: Mapping[str, Any],
) -> BackendHealth:
    """The real health of one artifact under one backend.

    The order of the checks is deliberate, so the most specific cause wins:
    declaration, file existence, declared integrity, the shared pipeline files,
    runtime availability, the classifier probe, the pipeline probe.
    """
    if artifact is None:
        return BackendHealth(backend, False, REASON_ARTIFACT_MISSING)
    if not artifact.path.is_file():
        return BackendHealth(backend, False, REASON_ARTIFACT_MISSING)
    if artifact.sha256:
        digest = _sha256_of(artifact.path)
        if digest is not None and digest.lower() != artifact.sha256.strip().lower():
            return BackendHealth(backend, False, REASON_ARTIFACT_INTEGRITY)
    if artifact.byte_size:
        try:
            if artifact.path.stat().st_size != int(artifact.byte_size):
                return BackendHealth(backend, False, REASON_ARTIFACT_INTEGRITY)
        except OSError:
            return BackendHealth(backend, False, REASON_ARTIFACT_MISSING)
    if not pipeline.files_present(backend):
        return BackendHealth(backend, False, REASON_PIPELINE_UNAVAILABLE)
    prober = (probers or {}).get(backend)
    if prober is None:
        # Root F12: an absent runtime is an unhealthy backend, never a passed
        # probe. C2 skipped the probe here and reported the model as available.
        return BackendHealth(backend, False, REASON_RUNTIME_UNAVAILABLE)
    try:
        prober(str(artifact.path))
    except Exception:  # noqa: BLE001 - reason must not leak internals
        return BackendHealth(backend, False, REASON_ARTIFACT_UNLOADABLE)
    for path in pipeline.artifacts(backend):
        try:
            prober(str(path))
        except Exception:  # noqa: BLE001 - reason must not leak internals
            return BackendHealth(backend, False, REASON_PIPELINE_UNAVAILABLE)
    return BackendHealth(backend, True, None)


def _entry_with_backend_health(
    entry: WakeWordEntry,
    pipeline: WakeWordPipeline,
    probers: Mapping[str, Any],
) -> WakeWordEntry:
    health = {
        backend: probe_backend_health(
            entry.artifacts.get(backend), pipeline, backend, probers
        )
        for backend in entry.declared_backends
    }
    candidate = _replace_entry(entry, backend_health=health)
    available = bool(candidate.healthy_backends)
    return _replace_entry(
        candidate,
        available=available,
        unavailable_reason=None if available else _entry_reason(candidate),
    )


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
    whether that means "no catalog yet" or "keep the last known good one". The
    per-backend health is resolved afterwards by the authority, which owns the
    probers.
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

    declared_files = set()
    for entry in entries:
        for artifact in entry.artifacts.values():
            declared_files.add(artifact.file_name)
    for backend in pipeline.backends:
        for path in pipeline.artifacts(backend):
            if path is not None:
                declared_files.add(path.name)
    unmanaged = sorted(
        path.name
        for suffix in BACKEND_SUFFIX.values()
        for path in root.glob(f"*{suffix}")
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
            "declaredBackends": list(pipeline.backends),
            # Diagnostic only: a file that merely lies in the asset directory
            # is never public build capability.
            "unmanagedArtifacts": unmanaged,
        },
    )


def _parse_pipeline(payload: Mapping[str, Any], root: Path) -> WakeWordPipeline:
    pipeline_section = payload.get("pipeline")
    if not isinstance(pipeline_section, dict):
        raise WakeWordManifestError("wake-word manifest has no 'pipeline' section")
    paths: Dict[str, Tuple[Optional[Path], Optional[Path]]] = {}
    for backend in INFERENCE_BACKENDS:
        framework_section = pipeline_section.get(backend)
        if framework_section is None:
            continue
        if not isinstance(framework_section, dict):
            raise WakeWordManifestError(
                f"wake-word manifest '{backend}' pipeline section is invalid"
            )
        roles = {}
        for role in ("melspectrogram", "embedding"):
            spec = framework_section.get(role)
            if not isinstance(spec, dict) or not str(spec.get("file") or "").strip():
                raise WakeWordManifestError(
                    f"wake-word manifest pipeline model '{role}' is missing "
                    f"for backend '{backend}'"
                )
            roles[role] = root / str(spec["file"]).strip()
        paths[backend] = (roles["melspectrogram"], roles["embedding"])
    if not paths:
        raise WakeWordManifestError(
            "wake-word manifest declares no inference backend pipeline"
        )
    return WakeWordPipeline(paths=paths)


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

        artifacts_raw = raw.get("artifacts")
        if not isinstance(artifacts_raw, dict):
            raise WakeWordManifestError(
                f"wake word '{identifier}' has no artifacts mapping"
            )
        artifacts: Dict[str, WakeWordArtifact] = {}
        for backend in INFERENCE_BACKENDS:
            spec = artifacts_raw.get(backend)
            if spec is None:
                continue
            if not isinstance(spec, dict) or not str(spec.get("file") or "").strip():
                raise WakeWordManifestError(
                    f"wake word '{identifier}' has an invalid {backend} artifact"
                )
            file_name = str(spec["file"]).strip()
            artifacts[backend] = WakeWordArtifact(
                backend=backend,
                file_name=file_name,
                path=root / file_name,
                sha256=str(spec.get("sha256") or ""),
                byte_size=int(spec.get("bytes") or 0),
            )
        if not artifacts:
            raise WakeWordManifestError(
                f"wake word '{identifier}' declares no supported artifact"
            )

        claim(normalize_wake_word_token(identifier), "id", identifier)
        claim(normalize_wake_word_token(display_name), "displayName", identifier)
        aliases = []
        for alias in aliases_raw:
            token = normalize_wake_word_token(alias)
            claim(token, "alias", identifier)
            if token not in aliases:
                aliases.append(token)

        entries.append(WakeWordEntry(
            id=identifier,
            display_name=display_name,
            aliases=tuple(aliases),
            artifact_version=artifact_version,
            artifacts=artifacts,
            backend_health={},
            available=False,
            unavailable_reason=REASON_RUNTIME_UNAVAILABLE,
        ))

    for backend in INFERENCE_BACKENDS:
        model_keys: Dict[str, str] = {}
        for entry in entries:
            artifact = entry.artifacts.get(backend)
            if artifact is None:
                continue
            owner = model_keys.get(artifact.model_key)
            if owner is not None:
                raise WakeWordManifestError(
                    "wake-word catalog collision: artifact file stem "
                    f"'{artifact.model_key}' is shared by '{owner}' and "
                    f"'{entry.id}'"
                )
            model_keys[artifact.model_key] = entry.id

    return tuple(entries), resolver_index


def default_artifact_probers() -> Dict[str, Any]:
    """The real loadability probes of the shipped inference runtimes.

    A backend whose runtime is not importable maps to ``None``: Root F12 -
    "no runtime" must never look like "the probe passed". The catalog then
    reports that backend as ``runtime_unavailable`` and the other one, if any,
    carries the selection.
    """
    return {
        BACKEND_ONNX: _default_onnx_prober(),
        BACKEND_TFLITE: _default_tflite_prober(),
    }


def _default_onnx_prober():
    """Creating an ``InferenceSession`` is what OpenWakeWord itself does."""
    try:
        import onnxruntime as ort
    except Exception:  # noqa: BLE001 - no runtime, no probe
        return None

    options = ort.SessionOptions()
    options.log_severity_level = 3

    def probe(path: str) -> None:
        ort.InferenceSession(
            str(path), sess_options=options, providers=["CPUExecutionProvider"]
        )

    return probe


def _default_tflite_prober():
    """Allocating an interpreter is what OpenWakeWord itself does."""
    interpreter_factory = None
    try:
        from tflite_runtime.interpreter import Interpreter as interpreter_factory  # noqa: N813
    except Exception:  # noqa: BLE001 - fall through to the full TensorFlow
        try:
            from tensorflow.lite.python.interpreter import (  # noqa: N813
                Interpreter as interpreter_factory,
            )
        except Exception:  # noqa: BLE001 - no runtime, no probe
            return None

    def probe(path: str) -> None:
        interpreter = interpreter_factory(model_path=str(path))
        interpreter.allocate_tensors()

    return probe


#: Historical single-backend accessor. Kept so external readers do not break.
def default_artifact_prober():
    """The ONNX loadability probe, or ``None`` when no runtime is installed."""
    return _default_onnx_prober()


class WakeWordCatalogAuthority:
    """The one server-wide, thread-safe wake-word catalog authority.

    It owns the last-known-good snapshot and ``catalogRevision``. A refresh
    builds a complete candidate first - manifest, ids, integrity, both declared
    formats, runtime availability, pipeline assets and the real probe of every
    declared classifier - and swaps atomically only on total success; a failing
    refresh leaves the running catalog untouched.

    Everything that can change the catalog runs under one lock, so a refresh
    and a global-disable change are linearised and every result describes one
    single snapshot (Root F10/F14). The revision is raised only when the visible
    projection changed, and *every* such change notifies the subscriber, not
    just an availability change (Root F8).
    """

    def __init__(
        self,
        *,
        asset_root: Optional[Path] = None,
        loader=None,
        global_disabled_ids: Sequence[Any] = (),
        on_catalog_changed=None,
        on_availability_changed=None,
        artifact_prober=_UNSET,
        artifact_probers=_UNSET,
    ):
        self._asset_root = Path(asset_root) if asset_root is not None else None
        self._loader = loader or load_snapshot
        self._lock = threading.RLock()
        self._on_catalog_changed = on_catalog_changed or on_availability_changed
        self._global_disabled = tuple(global_disabled_ids or ())
        self._snapshot: Optional[WakeWordCatalogSnapshot] = None
        self._load_error: Optional[str] = None
        self._probers = _resolve_probers(artifact_prober, artifact_probers)
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
        """The ``GET /api/v2/wake-words`` body (SET-13b).

        Read from one snapshot, so the top-level revision, the per-entry
        revisions and availability always describe the same state.
        """
        snapshot = self.snapshot()
        if snapshot is None:
            return {
                "protocolVersion": int(protocol_version),
                "catalogRevision": 0,
                "wakeWords": [],
            }
        return {
            "protocolVersion": int(protocol_version),
            "catalogRevision": snapshot.catalog_revision,
            "wakeWords": snapshot.public_catalog(),
        }

    def resolve(self, value: Any) -> Optional[str]:
        """The tolerant human-config resolver. Never used for the v2 wire."""
        snapshot = self.snapshot()
        return snapshot.resolve(value) if snapshot else None

    # -- admission -----------------------------------------------------------

    def _unavailable_catalog_error(self):
        return (None, (SelectionError(
            wake_word_id="",
            reason="catalog_unavailable",
            message=(
                "Der Wake-Word-Katalog ist auf diesem Server nicht verfügbar."
            ),
        ),))

    def admit_selection(
        self,
        values: Sequence[Any],
        *,
        requested_backend: Any = BACKEND_AUTO,
        platform: Optional[str] = None,
    ):
        """The v2 wire admission: canonical ids only, plus the backend gate."""
        snapshot = self.snapshot()
        if snapshot is None:
            return self._unavailable_catalog_error()
        return snapshot.admit_selection(
            values, requested_backend=requested_backend, platform=platform
        )

    def resolve_human_selection(
        self,
        values: Sequence[Any],
        *,
        requested_backend: Any = BACKEND_AUTO,
        platform: Optional[str] = None,
    ):
        """The tolerant admission for human configuration values."""
        snapshot = self.snapshot()
        if snapshot is None:
            return self._unavailable_catalog_error()
        return snapshot.resolve_human_selection(
            values, requested_backend=requested_backend, platform=platform
        )

    def set_artifact_prober(self, prober) -> None:
        """Replaces the loadability probe of every backend and re-resolves."""
        with self._lock:
            self._probers = {backend: prober for backend in INFERENCE_BACKENDS}
            self._reload_locked(initial=False)

    def set_artifact_probers(self, probers) -> None:
        """Replaces the per-backend loadability probes and re-resolves."""
        with self._lock:
            self._probers = _resolve_probers(_UNSET, probers)
            self._reload_locked(initial=False)

    def set_loader_for_tests(self, loader) -> None:
        """Replaces the manifest loader. Fault injection seam for tests."""
        with self._lock:
            self._loader = loader

    def backend_health(self) -> Dict[str, Dict[str, Any]]:
        """Per wake word, per backend health. Diagnostics, never a payload."""
        snapshot = self.snapshot()
        if snapshot is None:
            return {}
        return {
            entry.id: {
                backend: record.public_dict()
                for backend, record in (entry.backend_health or {}).items()
            }
            for entry in snapshot.entries
        }

    # -- mutation ------------------------------------------------------------

    def refresh(self, *, global_disabled_ids: Any = _UNSET) -> RefreshResult:
        """Re-reads manifest and artifacts and swaps atomically on success.

        ``global_disabled_ids`` is applied inside the very same locked
        operation, so a refresh and a disable change can never interleave into
        two half-applied states (Root F10).
        """
        with self._lock:
            if global_disabled_ids is not _UNSET:
                self._global_disabled = tuple(global_disabled_ids or ())
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
                snapshot=self._snapshot,
            )
        except Exception as exc:  # noqa: BLE001 - a refresh must never crash the server
            self._load_error = f"{type(exc).__name__}: {exc}"
            revision = self._snapshot.catalog_revision if self._snapshot else 0
            return RefreshResult(
                ok=False,
                changed=False,
                catalog_revision=revision,
                available_wake_word_ids=(
                    self._snapshot.available_ids() if self._snapshot else ()
                ),
                error=self._load_error,
                snapshot=self._snapshot,
            )

        self._load_error = None
        # Loadability is resolved on every load and on every refresh, never
        # once at start-up and never only for a selected subset.
        candidate = candidate.with_backend_health(self._probers)
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
                snapshot=candidate,
            )

        changed = candidate.visible_projection() != current.visible_projection()
        if not changed:
            # No *visible* change: the revision must not move. The candidate is
            # still adopted so internal paths and diagnostics stay current.
            committed = candidate.with_catalog_revision(current.catalog_revision)
            self._snapshot = committed
            return RefreshResult(
                ok=True,
                changed=False,
                catalog_revision=committed.catalog_revision,
                available_wake_word_ids=committed.available_ids(),
                snapshot=committed,
            )

        revision = current.catalog_revision + 1
        committed = candidate.with_catalog_revision(revision)
        availability_changed = committed.available_ids() != current.available_ids()
        self._snapshot = committed
        result = RefreshResult(
            ok=True,
            changed=True,
            catalog_revision=revision,
            availability_changed=availability_changed,
            available_wake_word_ids=committed.available_ids(),
            snapshot=committed,
        )
        # Root F8: every *visible* change is announced, not only an
        # availability change. A client that only learns about new/removed ids
        # would otherwise silently miss a revision it can observe elsewhere.
        callback = self._on_catalog_changed
        if callback is not None:
            try:
                callback(
                    revision,
                    list(committed.available_ids()),
                    availability_changed,
                )
            except Exception:  # noqa: BLE001 - a subscriber must not break the swap
                pass
        return result


def _resolve_probers(artifact_prober, artifact_probers) -> Dict[str, Any]:
    """Normalises the two constructor spellings into one per-backend map.

    ``artifact_probers`` is the C3 form. ``artifact_prober`` is the historical
    single-callable form and is applied to every backend, which keeps existing
    callers and tests working without introducing a second probe authority.
    """
    if artifact_probers is not _UNSET:
        probers = dict(artifact_probers or {})
        return {
            backend: probers.get(backend) for backend in INFERENCE_BACKENDS
        }
    if artifact_prober is not _UNSET:
        return {backend: artifact_prober for backend in INFERENCE_BACKENDS}
    return default_artifact_probers()
