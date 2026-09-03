"""Server-authoritative discovery, recovery and provisioning for STT models.

The module deliberately owns *policy* while small adapters own engine file
layouts.  It never treats mutable operator configuration as product or legal
authority and never asks an inference library to fetch a model.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import threading
import urllib.request
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from VoiceSTT.kroko import models as kroko_models
from VoiceSTT_server.credential_redaction import (
    kroko_credential_values,
    redact_secret_text,
)


DISCOVERED = "DISCOVERED"
VALIDATED = "VALIDATED"
LOAD_VERIFIED = "LOAD_VERIFIED"
MINIMUM_READY = "MINIMUM_READY"
NOT_READY = "NOT_READY"

ROLE_FINAL = "final"
ROLE_REALTIME = "realtime"
REQUIRED_ROLES = frozenset({ROLE_FINAL, ROLE_REALTIME})

_TARGET_LOCKS_GUARD = threading.Lock()
_TARGET_LOCKS: Dict[str, threading.Lock] = {}


def normalize_engine(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in {"kroko", "banafo_kroko"}:
        return "kroko_onnx"
    return normalized


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _stage_name(name: str) -> bool:
    lower = name.lower()
    return (
        lower.startswith(".")
        or lower.endswith(".part")
        or ".part." in lower
        or lower.endswith(".staging")
        or ".staging." in lower
    )


def _safe_error(error: Any, secrets: Iterable[Any] = ()) -> str:
    """Render diagnostics without ever echoing a configured Kroko secret."""
    return redact_secret_text(error, secrets)


@dataclass(frozen=True)
class ProductModel:
    """Immutable product facts for one known model."""

    id: str
    engine: str
    language: str = ""
    license_class: str = "unknown"
    runtime_variant: Optional[str] = None
    roles: Tuple[str, ...] = (ROLE_FINAL, ROLE_REALTIME)
    revision: Optional[str] = None
    filename: Optional[str] = None
    artifact_kind: str = "file"
    sha256: Optional[str] = None
    bytes: Optional[int] = None
    source: Optional[str] = None
    source_identity: Optional[str] = None
    provisioning_allowed: bool = False
    rights_status: str = "UNKNOWN"
    recovery_priority: Optional[int] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "engine", normalize_engine(self.engine))
        if not self.id or not self.engine:
            raise ValueError("product models require a stable id and engine")
        if self.filename and (
            Path(self.filename).name != self.filename
            or "/" in self.filename
            or "\\" in self.filename
            or self.filename in {".", ".."}
        ):
            raise ValueError("authoritative model filename must not contain a path")
        if self.provisioning_allowed:
            missing = [
                name for name, value in (
                    ("filename", self.filename),
                    ("sha256", self.sha256),
                    ("bytes", self.bytes),
                    ("source", self.source),
                ) if not value
            ]
            if missing:
                raise ValueError(
                    f"provisionable model {self.id!r} lacks immutable authority: "
                    + ", ".join(missing)
                )
            if self.artifact_kind != "file":
                raise ValueError("only verified file provisioning is supported")
            if (
                isinstance(self.bytes, bool)
                or int(self.bytes or 0) <= 0
                or len(str(self.sha256)) != 64
                or any(character not in "0123456789abcdefABCDEF" for character in str(self.sha256))
            ):
                raise ValueError(
                    f"provisionable model {self.id!r} has an invalid content identity"
                )

    def public_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "engine": self.engine,
            "language": self.language,
            "licenseClass": self.license_class,
            "runtimeVariant": self.runtime_variant,
            "roles": list(self.roles),
            "revision": self.revision,
            "filename": self.filename,
            "source": self.source,
            "artifactKind": self.artifact_kind,
            "sha256": self.sha256,
            "bytes": self.bytes,
            "provisioningAllowed": self.provisioning_allowed,
            "rightsStatus": self.rights_status,
            "recoveryPriority": self.recovery_priority,
        }


@dataclass(frozen=True)
class OperatorIntent:
    """Mutable operator intent, kept separate from :class:`ProductModel`."""

    global_auto_download: bool = False
    engines: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    models: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    defaults: Mapping[str, Tuple[str, str]] = field(default_factory=dict)
    kroko_runtime_variant: str = "free"
    redaction_values: Tuple[str, ...] = field(
        default=(),
        repr=False,
        compare=False,
    )

    @classmethod
    def from_settings(cls, settings: Any) -> "OperatorIntent":
        engines = {
            normalize_engine(key): dict(value)
            for key, value in (
                getattr(settings, "stt_engine_settings", None) or {}
            ).items()
            if isinstance(value, Mapping)
        }
        models = dict(getattr(settings, "stt_model_settings", None) or {})
        final_engine = normalize_engine(getattr(settings, "transcription_engine", ""))
        realtime_engine = normalize_engine(
            getattr(settings, "realtime_transcription_engine", None) or final_engine
        )
        defaults = {
            ROLE_FINAL: (final_engine, str(getattr(settings, "model", ""))),
            ROLE_REALTIME: (
                realtime_engine,
                str(getattr(settings, "realtime_model", None) or getattr(settings, "model", "")),
            ),
        }

        def add_legacy_paths(engine: str, options: Any) -> None:
            config = engines.setdefault(engine, {})
            paths = list(config.get("custom_paths", config.get("paths", ())) or ())
            if isinstance(config.get("custom_paths", config.get("paths")), (str, os.PathLike)):
                paths = [config.get("custom_paths", config.get("paths"))]
            if isinstance(options, Mapping):
                for key in ("model_path", "model_file", "model_root", "model_dir"):
                    if options.get(key) and options[key] not in paths:
                        paths.append(options[key])
            download_root = getattr(settings, "download_root", None)
            if download_root and download_root not in paths:
                paths.append(download_root)
            config["custom_paths"] = paths

        add_legacy_paths(
            final_engine, getattr(settings, "transcription_engine_options", None)
        )
        add_legacy_paths(
            realtime_engine,
            getattr(settings, "realtime_transcription_engine_options", None),
        )
        final_options = getattr(settings, "transcription_engine_options", None)
        realtime_options = getattr(
            settings, "realtime_transcription_engine_options", None
        )
        kroko_config = engines.get("kroko_onnx", {})
        runtime_variant = kroko_config.get("runtime_variant")
        if (
            not runtime_variant
            and final_engine == "kroko_onnx"
            and isinstance(final_options, Mapping)
        ):
            runtime_variant = final_options.get("runtime_variant")
        if (
            not runtime_variant
            and realtime_engine == "kroko_onnx"
            and isinstance(realtime_options, Mapping)
        ):
            runtime_variant = realtime_options.get("runtime_variant")
        if not runtime_variant:
            runtime_variant = os.getenv("VOICESTT_KROKO_VARIANT")
        runtime_variant = str(runtime_variant or "free").strip().lower()
        if runtime_variant not in {"free", "pro"}:
            raise ValueError(
                "Kroko runtime_variant must be explicitly 'free' or 'pro'"
            )
        redaction_values = kroko_credential_values({
            "transcription_engine_options": final_options,
            "realtime_transcription_engine_options": realtime_options,
            "stt_engine_settings": engines,
        })
        return cls(
            global_auto_download=_as_bool(
                getattr(settings, "stt_auto_download_enabled", False)
            ),
            engines=engines,
            models=models,
            defaults=defaults,
            kroko_runtime_variant=runtime_variant,
            redaction_values=redaction_values,
        )

    def engine_config(self, engine: str) -> Mapping[str, Any]:
        normalized = normalize_engine(engine)
        for key, value in self.engines.items():
            if normalize_engine(key) == normalized and isinstance(value, Mapping):
                return value
        return {}

    def model_config(self, model: ProductModel) -> Mapping[str, Any]:
        for key in (model.id, f"{model.engine}:{model.id}"):
            value = self.models.get(key)
            if isinstance(value, Mapping):
                return value
        return {}

    def engine_enabled(self, engine: str) -> bool:
        return _as_bool(self.engine_config(engine).get("enabled", True))

    def model_enabled(self, model: ProductModel) -> bool:
        return _as_bool(self.model_config(model).get("enabled", True))

    def effective_auto_download(self, model: ProductModel) -> bool:
        return bool(self.auto_download_scope(model))

    def auto_download_scope(self, model: ProductModel) -> Tuple[str, ...]:
        scopes = []
        if self.global_auto_download:
            scopes.append("global")
        if _as_bool(self.engine_config(model.engine).get("auto_download_enabled", False)):
            scopes.append("engine")
        if _as_bool(self.model_config(model).get("auto_download_enabled", False)):
            scopes.append("model")
        return tuple(scopes)

    def priority(self, model: ProductModel) -> Optional[int]:
        value = self.model_config(model).get("recovery_priority")
        if value is None:
            return model.recovery_priority
        if isinstance(value, bool):
            return model.recovery_priority
        try:
            return int(value)
        except (TypeError, ValueError):
            return model.recovery_priority


@dataclass(frozen=True)
class ModelCandidate:
    id: str
    engine: str
    path: str
    source_root: str
    product_id: Optional[str] = None
    state: str = DISCOVERED
    problems: Tuple[str, ...] = ()

    def public_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "engine": self.engine,
            "path": self.path,
            "sourceRoot": self.source_root,
            "productId": self.product_id,
            "state": self.state,
            "problems": list(self.problems),
        }


@dataclass(frozen=True)
class ModelSnapshot:
    revision: int
    readiness: str
    candidates: Tuple[ModelCandidate, ...]
    active: Mapping[str, ModelCandidate]
    optional_state: str = "complete"
    diagnostics: Tuple[Mapping[str, Any], ...] = ()

    @property
    def minimum_ready(self) -> bool:
        return self.readiness == MINIMUM_READY

    def public_dict(self) -> Dict[str, Any]:
        if self.minimum_ready:
            if self.optional_state == "provisioning":
                state = "ready_optional_provisioning"
            elif self.optional_state == "errors":
                state = "ready_optional_errors"
            else:
                state = "ready_complete"
        else:
            state = "not_ready"
        return {
            "revision": self.revision,
            "state": state,
            "readiness": self.readiness,
            "minimumReady": self.minimum_ready,
            "optionalProvisioning": self.optional_state,
            "active": {
                role: candidate.public_dict()
                for role, candidate in sorted(self.active.items())
            },
            "candidates": [candidate.public_dict() for candidate in self.candidates],
            "diagnostics": [dict(item) for item in self.diagnostics],
        }


def default_product_authority() -> Tuple[ProductModel, ...]:
    """Build the honest product authority from pinned in-package facts."""

    faster = tuple(
        ProductModel(
            id=f"faster-whisper-{name}",
            engine="faster_whisper",
            language=("en" if name.endswith(".en") else "multilingual"),
            license_class="upstream-local",
            artifact_kind="directory",
            provisioning_allowed=False,
            rights_status="LOCAL_ONLY_UNPINNED",
            recovery_priority=priority,
        )
        for name, priority in (
            ("tiny", 300),
            ("tiny.en", None),
            ("base", None),
            ("base.en", None),
            ("small", 200),
            ("small.en", None),
            ("medium", None),
            ("medium.en", None),
            ("large-v2", None),
            ("large-v3", None),
            ("large-v3-turbo", None),
        )
    )
    manifest = kroko_models.load_manifest()
    upstream = manifest.upstream
    repo_id = upstream.get("communityRepoId")
    revision = upstream.get("communityRevision")
    kroko = []
    for entry in manifest.entries:
        source = None
        if repo_id and revision and entry.tier.lower() == "community":
            source = (
                f"https://huggingface.co/{repo_id}/resolve/{revision}/"
                f"{entry.filename}"
            )
        # W4A's unresolved/prohibited redistribution states remain hard gates.
        allowed = bool(entry.redistributable and source and entry.sha256 and entry.bytes)
        kroko.append(ProductModel(
            id=entry.id,
            engine="kroko_onnx",
            language=entry.language,
            license_class=entry.license_class,
            runtime_variant=entry.requires_runtime_variant,
            revision=(
                str(entry.provenance.get("revision"))
                if entry.provenance.get("revision")
                else None
            ),
            filename=entry.filename,
            sha256=entry.sha256 or None,
            bytes=entry.bytes or None,
            source=source,
            source_identity=source,
            provisioning_allowed=allowed,
            rights_status=entry.redistribution_status,
            recovery_priority=(100 if entry.id == "kroko-de-community-64-l" else None),
        ))
    return faster + tuple(kroko)


class FasterWhisperAdapter:
    engine = "faster_whisper"

    @staticmethod
    def _model_path(path: Path) -> Optional[Path]:
        if _stage_name(path.name):
            return None
        if path.is_dir() and (path / "config.json").is_file() and (path / "model.bin").is_file():
            return path
        snapshots = path / "snapshots"
        if snapshots.is_dir():
            for candidate in sorted(snapshots.iterdir(), reverse=True):
                if _stage_name(candidate.name):
                    continue
                if (candidate / "config.json").is_file() and (candidate / "model.bin").is_file():
                    return candidate
        return None

    def discover(
        self, roots: Sequence[Path], products: Sequence[ProductModel]
    ) -> Tuple[ModelCandidate, ...]:
        result = []
        seen = set()
        for root in roots:
            if not root.is_dir():
                continue
            paths = [root] + [item for item in sorted(root.iterdir()) if item.is_dir()]
            for folder in paths:
                resolved = self._model_path(folder)
                if resolved is None:
                    continue
                key = str(resolved.resolve()).lower()
                if key in seen:
                    continue
                seen.add(key)
                token = folder.name
                lowered = token.lower().replace("_", "-")
                product = next(
                    (item for item in products if self._matches(item, lowered)), None
                )
                model_id = product.id if product else self._friendly_id(token)
                result.append(ModelCandidate(
                    id=model_id,
                    engine=self.engine,
                    path=str(resolved.resolve()),
                    source_root=str(root.resolve()),
                    product_id=product.id if product else None,
                ))
        return tuple(result)

    @staticmethod
    def _friendly_id(name: str) -> str:
        value = name
        if value.lower().startswith("models--"):
            parts = value.split("--", 2)
            if len(parts) == 3:
                value = parts[2]
        return value

    @staticmethod
    def _matches(product: ProductModel, value: str) -> bool:
        aliases = {
            product.id.lower().replace("_", "-"),
            product.id.lower().replace("faster-whisper-", ""),
            f"models--systran--{product.id.lower()}",
        }
        return value in aliases or value.endswith("--" + product.id.lower())

    @staticmethod
    def validate(candidate: ModelCandidate, product: Optional[ProductModel]) -> ModelCandidate:
        path = Path(candidate.path)
        problems = []
        if not (path / "config.json").is_file():
            problems.append("missing config.json")
        if not (path / "model.bin").is_file():
            problems.append("missing model.bin")
        return replace(
            candidate,
            state=VALIDATED if not problems else DISCOVERED,
            problems=tuple(problems),
        )


class KrokoAdapter:
    engine = "kroko_onnx"

    def discover(
        self, roots: Sequence[Path], products: Sequence[ProductModel]
    ) -> Tuple[ModelCandidate, ...]:
        result = []
        seen = set()
        by_name = {
            str(item.filename).lower(): item for item in products if item.filename
        }
        for root in roots:
            if root.is_file() and root.suffix.lower() == ".data":
                paths = (root,)
                source_root = root.parent
            elif root.is_dir():
                paths = tuple(sorted(root.glob("*.data")))
                source_root = root
            else:
                continue
            for path in paths:
                if _stage_name(path.name):
                    continue
                key = str(path.resolve()).lower()
                if key in seen:
                    continue
                seen.add(key)
                product = by_name.get(path.name.lower())
                result.append(ModelCandidate(
                    id=product.id if product else path.name,
                    engine=self.engine,
                    path=str(path.resolve()),
                    source_root=str(source_root.resolve()),
                    product_id=product.id if product else None,
                ))
        return tuple(result)

    @staticmethod
    def validate(candidate: ModelCandidate, product: Optional[ProductModel]) -> ModelCandidate:
        path = Path(candidate.path)
        problems = []
        if not path.is_file() or path.suffix.lower() != ".data":
            problems.append("not a Kroko .data file")
        if product is not None and product.bytes and path.is_file():
            if path.stat().st_size != product.bytes:
                problems.append(
                    f"size mismatch: {path.stat().st_size} != {product.bytes}"
                )
        return replace(
            candidate,
            state=VALIDATED if not problems else DISCOVERED,
            problems=tuple(problems),
        )


class AtomicModelProvisioner:
    """Verified, no-cache file provisioner with per-target serialization."""

    def __init__(
        self,
        fetcher: Optional[Callable[[str, Path], Optional[str]]] = None,
        writable_probe: Optional[Callable[[Path], bool]] = None,
    ) -> None:
        self._fetcher = fetcher or self._download
        self._writable_probe = writable_probe or self._is_writable

    @staticmethod
    def _download(source: str, destination: Path) -> Optional[str]:
        with urllib.request.urlopen(source) as response, destination.open("xb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
            return response.geturl()

    @staticmethod
    def _is_writable(root: Path) -> bool:
        try:
            root.mkdir(parents=True, exist_ok=True)
            probe = root / f".voicestt-write-probe-{uuid.uuid4().hex}"
            with probe.open("x", encoding="ascii") as handle:
                handle.write("probe")
            probe.unlink()
            return True
        except OSError:
            return False

    def choose_target(self, product: ProductModel, roots: Sequence[Path]) -> Path:
        if not product.filename:
            raise ValueError(f"model {product.id!r} has no authoritative filename")
        for root in roots:
            if self._writable_probe(root):
                return root / product.filename
        raise OSError(f"no writable provisioning target for {product.id!r}")

    def provision(self, product: ProductModel, roots: Sequence[Path]) -> Path:
        if not product.provisioning_allowed:
            raise PermissionError(
                f"model {product.id!r} is ineligible for automatic provisioning "
                f"({product.rights_status})"
            )
        target = self.choose_target(product, roots)
        lock_key = os.path.normcase(str(target.resolve()))
        with _TARGET_LOCKS_GUARD:
            lock = _TARGET_LOCKS.setdefault(lock_key, threading.Lock())
        with lock:
            if target.is_file() and self._verified(product, target):
                return target.resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.parent / f".{target.name}.{uuid.uuid4().hex}.part"
            try:
                observed_source = self._fetcher(str(product.source), temporary)
                expected_source = product.source_identity or product.source
                if expected_source and observed_source != expected_source:
                    raise ValueError("download source identity mismatch")
                if not self._verified(product, temporary):
                    raise ValueError("downloaded model content failed identity verification")
                os.replace(temporary, target)
                return target.resolve()
            finally:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass

    @staticmethod
    def _verified(product: ProductModel, path: Path) -> bool:
        if not path.is_file():
            return False
        if product.bytes is None or path.stat().st_size != product.bytes:
            return False
        if not product.sha256:
            return False
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest().lower() == product.sha256.lower()


class STTModelManager:
    """One transactional model registry and recovery policy for the server."""

    def __init__(
        self,
        *,
        runtime_root: Any,
        authority: Optional[Iterable[ProductModel]] = None,
        intent: Optional[OperatorIntent] = None,
        load_probe: Optional[Callable[[ModelCandidate], bool]] = None,
        provisioner: Optional[AtomicModelProvisioner] = None,
    ) -> None:
        self.runtime_root = Path(runtime_root).expanduser()
        self.authority = tuple(authority or default_product_authority())
        self.intent = intent or OperatorIntent()
        self.load_probe = load_probe or (lambda candidate: True)
        self.provisioner = provisioner or AtomicModelProvisioner()
        self._adapters = {
            "faster_whisper": FasterWhisperAdapter(),
            "kroko_onnx": KrokoAdapter(),
        }
        self._operation_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._snapshot = ModelSnapshot(0, NOT_READY, (), {})
        self._last_attempt_diagnostics: Tuple[Mapping[str, Any], ...] = ()
        self._refresh_running = False

    def default_root(self, engine: str) -> Path:
        name = "fasterwhisper" if normalize_engine(engine) == "faster_whisper" else "kroko_asr"
        return self.runtime_root / "models" / "stt" / name

    def discovery_roots(self, engine: str) -> Tuple[Path, ...]:
        config = self.intent.engine_config(engine)
        values = config.get("custom_paths", config.get("paths", ()))
        if isinstance(values, (str, os.PathLike)):
            values = (values,)
        roots = [Path(str(value)).expanduser() for value in (values or ()) if value]
        legacy_env = (
            os.getenv("VOICESTT_FASTER_WHISPER_MODEL_ROOT")
            if normalize_engine(engine) == "faster_whisper"
            else os.getenv("VOICESTT_KROKO_MODEL_ROOT")
        )
        if legacy_env:
            roots.append(Path(legacy_env).expanduser())
        roots.append(self.default_root(engine))
        unique = []
        for root in roots:
            if root not in unique:
                unique.append(root)
        return tuple(unique)

    def provisioning_roots(self, engine: str) -> Tuple[Path, ...]:
        config = self.intent.engine_config(engine)
        intended = config.get("provisioning_target")
        roots = []
        if intended:
            roots.append(Path(str(intended)).expanduser())
        roots.extend(self.discovery_roots(engine)[:-1])
        roots.append(self.default_root(engine))
        unique = []
        for root in roots:
            if root not in unique:
                unique.append(root)
        return tuple(unique)

    def status(self) -> Dict[str, Any]:
        with self._state_lock:
            data = self._snapshot.public_dict()
            for public, candidate in zip(
                data["candidates"], self._snapshot.candidates
            ):
                product = next(
                    (
                        item for item in self.authority
                        if item.id == candidate.product_id
                    ),
                    None,
                )
                eligible = self.candidate_eligible(candidate, product)
                public["eligible"] = eligible
                public["available"] = bool(
                    eligible and candidate.state in {VALIDATED, LOAD_VERIFIED}
                )
            data["authority"] = []
            for product in self.authority:
                item = product.public_dict()
                item["operatorEnabled"] = bool(
                    self.intent.engine_enabled(product.engine)
                    and self.intent.model_enabled(product)
                )
                item["autoDownloadRequestedScopes"] = list(
                    self.intent.auto_download_scope(product)
                )
                data["authority"].append(item)
            data["refreshInProgress"] = self._refresh_running
            data["lastRefreshDiagnostics"] = [
                dict(item) for item in self._last_attempt_diagnostics
            ]
            return data

    def readiness_summary(self) -> Dict[str, Any]:
        """Path-free status suitable for unauthenticated liveness surfaces."""

        with self._state_lock:
            public = self._snapshot.public_dict()
            return {
                "revision": public["revision"],
                "state": public["state"],
                "readiness": public["readiness"],
                "minimumReady": public["minimumReady"],
                "optionalProvisioning": public["optionalProvisioning"],
                "refreshInProgress": self._refresh_running,
                "candidateCount": len(self._snapshot.candidates),
                "diagnosticResults": sorted({
                    str(item.get("result"))
                    for item in self._last_attempt_diagnostics
                    if item.get("result")
                }),
            }

    def snapshot(self) -> ModelSnapshot:
        with self._state_lock:
            return self._snapshot

    def restore_last_known_good(
        self, snapshot: ModelSnapshot, message: str
    ) -> ModelSnapshot:
        """Restore a service-proven LKG after downstream activation failed."""

        if not isinstance(snapshot, ModelSnapshot):
            raise TypeError("last-known-good snapshot must be a ModelSnapshot")
        diagnostic = ({
            "stage": "activation",
            "result": "failed_lkg_restored",
            "message": _safe_error(message, self.intent.redaction_values),
        },)
        with self._state_lock:
            self._snapshot = snapshot
            self._last_attempt_diagnostics = diagnostic
            return self._snapshot

    def refresh(self) -> ModelSnapshot:
        """Build a candidate state and publish it only as one complete snapshot."""

        with self._operation_lock:
            with self._state_lock:
                self._refresh_running = True
            try:
                candidate = self._build_snapshot()
                with self._state_lock:
                    if candidate.minimum_ready or not self._snapshot.minimum_ready:
                        self._snapshot = candidate
                    self._last_attempt_diagnostics = candidate.diagnostics
                    return self._snapshot
            finally:
                with self._state_lock:
                    self._refresh_running = False

    def _build_snapshot(self) -> ModelSnapshot:
        products_by_id = {item.id: item for item in self.authority}
        candidates = []
        for engine, adapter in self._adapters.items():
            engine_products = [item for item in self.authority if item.engine == engine]
            discovered = adapter.discover(self.discovery_roots(engine), engine_products)
            for item in discovered:
                product = products_by_id.get(item.product_id or "")
                candidates.append(adapter.validate(item, product))

        diagnostics = []
        active: Dict[str, ModelCandidate] = {}
        probed: Dict[str, ModelCandidate] = {}

        def probe(item: ModelCandidate) -> Optional[ModelCandidate]:
            if item.state != VALIDATED:
                return None
            cached = probed.get(item.path)
            if cached is not None:
                return cached if cached.state == LOAD_VERIFIED else None
            try:
                if not self.load_probe(item):
                    raise RuntimeError("engine load probe returned false")
                verified = replace(item, state=LOAD_VERIFIED)
                probed[item.path] = verified
                return verified
            except Exception as exc:  # noqa: BLE001 - diagnostic boundary
                message = _safe_error(exc, self.intent.redaction_values)
                failed = replace(item, problems=item.problems + (message,))
                probed[item.path] = failed
                diagnostics.append({
                    "modelId": item.id,
                    "engine": item.engine,
                    "stage": "load_probe",
                    "result": "failed",
                    "message": message,
                })
                return None

        # Explicit configured defaults are always attempted first.
        for role in (ROLE_FINAL, ROLE_REALTIME):
            engine, requested = self.intent.defaults.get(role, ("", ""))
            product = self._find_product(engine, requested)
            if not self._eligible(product, engine, diagnostics):
                continue
            local = self._find_candidate(candidates, engine, requested, product)
            if local is None and product and self.intent.effective_auto_download(product):
                local = self._provision(product, diagnostics)
                if local is not None:
                    adapter = self._adapters[product.engine]
                    local = adapter.validate(local, product)
                    candidates.append(local)
            elif local is None:
                diagnostics.append({
                    "modelId": product.id if product else str(requested),
                    "engine": normalize_engine(engine),
                    "role": role,
                    "stage": "recovery",
                    "result": "configured_default_missing",
                    "requestedScope": (
                        list(self.intent.auto_download_scope(product))
                        if product else []
                    ),
                })
            verified = probe(local) if local is not None else None
            if verified is not None:
                active[role] = verified

        # Generic recovery has only explicitly prioritized candidates.
        missing = REQUIRED_ROLES - set(active)
        fallback = [
            item for item in self.authority
            if self.intent.priority(item) is not None
            and self.intent.engine_enabled(item.engine)
            and self.intent.model_enabled(item)
        ]
        fallback.sort(key=lambda item: (self.intent.priority(item), item.id))
        for product in fallback:
            if not missing:
                break
            cover = missing & set(product.roles)
            if not cover or not self._eligible(product, product.engine, diagnostics):
                continue
            local = self._find_candidate(candidates, product.engine, product.id, product)
            if local is None:
                if not self.intent.effective_auto_download(product):
                    diagnostics.append({
                        "modelId": product.id,
                        "stage": "recovery",
                        "result": "missing_not_requested",
                    })
                    continue
                local = self._provision(product, diagnostics)
                if local is not None:
                    adapter = self._adapters[product.engine]
                    local = adapter.validate(local, product)
                    candidates.append(local)
            verified = probe(local) if local is not None else None
            if verified is not None:
                for role in sorted(cover):
                    active[role] = verified
                missing = REQUIRED_ROLES - set(active)

        ready = not missing
        optional_state = "complete"
        if ready:
            requested_optional = [
                item for item in self.authority
                if self.intent.engine_enabled(item.engine)
                and self.intent.model_enabled(item)
                and self.intent.effective_auto_download(item)
                and self._find_candidate(candidates, item.engine, item.id, item) is None
            ]
            if requested_optional:
                optional_state = "provisioning"
                with self._state_lock:
                    # Transient status is complete and immutable; active LKG is
                    # not replaced while optional work is in progress.
                    self._snapshot = ModelSnapshot(
                        self._snapshot.revision,
                        MINIMUM_READY,
                        tuple(candidates),
                        dict(active),
                        optional_state="provisioning",
                        diagnostics=tuple(diagnostics),
                    )
                optional_failed = False
                for product in requested_optional:
                    if not self._eligible(product, product.engine, diagnostics):
                        optional_failed = True
                        continue
                    local = self._provision(product, diagnostics)
                    if local is None:
                        optional_failed = True
                        continue
                    adapter = self._adapters[product.engine]
                    candidates.append(adapter.validate(local, product))
                optional_state = "errors" if optional_failed else "complete"

        # Replace validated entries by their probed representation for public diagnostics.
        candidates = [probed.get(item.path, item) for item in candidates]
        with self._state_lock:
            revision = self._snapshot.revision + 1
        return ModelSnapshot(
            revision,
            MINIMUM_READY if ready else NOT_READY,
            tuple(candidates),
            dict(active),
            optional_state=optional_state,
            diagnostics=tuple(diagnostics),
        )

    def _find_product(self, engine: str, requested: str) -> Optional[ProductModel]:
        normalized_engine = normalize_engine(engine)
        token = str(requested or "").strip().lower()
        for product in self.authority:
            if product.engine != normalized_engine:
                continue
            aliases = {product.id.lower(), str(product.filename or "").lower()}
            if token in aliases or Path(token).name in aliases:
                return product
            if normalized_engine == "faster_whisper":
                short = product.id.lower().replace("faster-whisper-", "")
                if token.replace("_", "-") in {short, f"faster-whisper-{short}"}:
                    return product
        return None

    @staticmethod
    def _find_candidate(
        candidates: Sequence[ModelCandidate],
        engine: str,
        requested: str,
        product: Optional[ProductModel],
    ) -> Optional[ModelCandidate]:
        normalized_engine = normalize_engine(engine)
        token = str(requested or "").strip().lower()
        for candidate in candidates:
            if candidate.engine != normalized_engine:
                continue
            aliases = {
                candidate.id.lower(),
                Path(candidate.path).name.lower(),
                str(candidate.product_id or "").lower(),
            }
            if token in aliases or Path(token).name in aliases:
                return candidate
        return None

    def _eligible(
        self,
        product: Optional[ProductModel],
        engine: str,
        diagnostics: list,
    ) -> bool:
        if not self.intent.engine_enabled(engine):
            diagnostics.append({
                "engine": normalize_engine(engine),
                "stage": "eligibility",
                "result": "engine_disabled",
            })
            return False
        if product is None:
            if normalize_engine(engine) == "kroko_onnx":
                diagnostics.append({
                    "engine": "kroko_onnx",
                    "stage": "eligibility",
                    "result": "unmanaged_kroko_authority_missing",
                })
                return False
            return True  # explicit, locally discovered unmanaged Faster-Whisper
        if not self.intent.model_enabled(product):
            diagnostics.append({
                "modelId": product.id,
                "stage": "eligibility",
                "result": "model_disabled",
            })
            return False
        if product.engine == "kroko_onnx" and product.runtime_variant:
            if self.intent.kroko_runtime_variant != product.runtime_variant:
                diagnostics.append({
                    "modelId": product.id,
                    "stage": "eligibility",
                    "result": "runtime_variant_incompatible",
                })
                return False
        return True

    def candidate_eligible(
        self,
        candidate: ModelCandidate,
        product: Optional[ProductModel] = None,
    ) -> bool:
        """Side-effect-free eligibility projection for public registry views."""

        if not self.intent.engine_enabled(candidate.engine):
            return False
        if product is None and candidate.product_id:
            product = next(
                (item for item in self.authority if item.id == candidate.product_id),
                None,
            )
        if product is None:
            return candidate.engine != "kroko_onnx"
        if not self.intent.model_enabled(product):
            return False
        if product.engine == "kroko_onnx" and product.runtime_variant:
            if self.intent.kroko_runtime_variant != product.runtime_variant:
                return False
        return True

    def _provision(
        self, product: ProductModel, diagnostics: list
    ) -> Optional[ModelCandidate]:
        if not product.provisioning_allowed:
            diagnostics.append({
                "modelId": product.id,
                "stage": "provisioning",
                "result": "blocked_ineligible",
                "rightsStatus": product.rights_status,
                "requestedScope": list(self.intent.auto_download_scope(product)),
            })
            return None
        try:
            path = self.provisioner.provision(
                product, self.provisioning_roots(product.engine)
            )
            diagnostics.append({
                "modelId": product.id,
                "stage": "provisioning",
                "result": "installed",
                "requestedScope": list(self.intent.auto_download_scope(product)),
            })
            return ModelCandidate(
                id=product.id,
                engine=product.engine,
                path=str(path),
                source_root=str(path.parent),
                product_id=product.id,
            )
        except Exception as exc:  # noqa: BLE001 - result is diagnostic, never partial
            message = _safe_error(exc, self.intent.redaction_values)
            diagnostics.append({
                "modelId": product.id,
                "stage": "provisioning",
                "result": "failed",
                "message": message,
                "requestedScope": list(self.intent.auto_download_scope(product)),
            })
            return None


class ManagedModelRegistryView:
    """Legacy-shaped read view backed by the one transactional authority."""

    def __init__(self, manager: STTModelManager) -> None:
        self._manager = manager

    def list_models(self) -> list:
        entries = []
        for candidate in self._manager.snapshot().candidates:
            product = next(
                (
                    item for item in self._manager.authority
                    if item.id == candidate.product_id
                ),
                None,
            )
            eligible = self._manager.candidate_eligible(candidate, product)
            entries.append({
                "id": candidate.id,
                "object": "model",
                "engine": candidate.engine,
                "alias": None,
                "name": Path(candidate.path).name,
                "folder": Path(candidate.path).name,
                "path": candidate.path,
                "available": (
                    candidate.state in {VALIDATED, LOAD_VERIFIED} and eligible
                ),
                "eligible": eligible,
                "validationState": candidate.state,
                "problems": list(candidate.problems),
            })
        return entries

    @staticmethod
    def _tokens(value: Any) -> set:
        text = str(value or "").strip().lower().replace("_", "-")
        name = Path(text).name
        result = {text, name}
        if name.startswith("models--"):
            parts = name.split("--", 2)
            if len(parts) == 3:
                result.add(parts[2])
                name = parts[2]
        if name.startswith("faster-whisper-"):
            result.add(name[len("faster-whisper-"):])
        return {item for item in result if item}

    def aliases_for(self, engine: str, configured_model: Any) -> set:
        normalized = normalize_engine(engine)
        wanted = self._tokens(configured_model)
        aliases = {str(configured_model)}
        for entry in self.list_models():
            if entry["engine"] != normalized:
                continue
            values = set()
            for key in ("id", "name", "folder", "path"):
                values.update(self._tokens(entry.get(key)))
            if wanted & values:
                aliases.update(
                    str(entry[key]) for key in ("id", "name", "folder", "path")
                    if entry.get(key)
                )
        return aliases

    def resolve(self, requested: Any, preferred_engine: Optional[str] = None):
        wanted = self._tokens(requested)
        normalized = normalize_engine(preferred_engine) if preferred_engine else None
        for entry in self.list_models():
            if normalized and entry["engine"] != normalized:
                continue
            if not entry["available"]:
                continue
            values = set()
            for key in ("id", "name", "folder", "path"):
                values.update(self._tokens(entry.get(key)))
            if wanted & values:
                return entry
        return None


__all__ = [
    "AtomicModelProvisioner",
    "DISCOVERED",
    "FasterWhisperAdapter",
    "KrokoAdapter",
    "LOAD_VERIFIED",
    "MINIMUM_READY",
    "ManagedModelRegistryView",
    "ModelCandidate",
    "ModelSnapshot",
    "NOT_READY",
    "OperatorIntent",
    "ProductModel",
    "STTModelManager",
    "VALIDATED",
    "default_product_authority",
]
