"""
Internal catalog and model discovery helpers for OpenWakeWord.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

logger = logging.getLogger("voicestt")

OPENWAKEWORD_MODEL_ROOT_ENV = "VOICESTT_OPENWAKEWORD_MODEL_ROOT"
DEFAULT_OPENWAKEWORD_MODEL_ROOT = Path("~/.cache/openwakeword").expanduser()

DEFAULT_FEATURE_MODELS = {
    "onnx": ("melspectrogram.onnx", "embedding_model.onnx"),
    "tflite": ("melspectrogram.tflite", "embedding_model.tflite"),
}

# Machine-readable resolution error codes
REASON_NOT_FOUND = "not_found"
REASON_GLOBALLY_DISABLED = "globally_disabled"
REASON_MISSING_MODEL_FILES = "missing_model_files"
REASON_MISSING_FEATURE_MODELS = "missing_feature_models"
REASON_ALIAS_COLLISION = "alias_collision"
REASON_UNSUPPORTED_FRAMEWORK = "unsupported_framework"
REASON_UNKNOWN = "unknown"


def _normalize_id(value: Any) -> str:
    """Normalize wake-word identifier for matching using Unicode trim and casefold."""
    if value is None:
        return ""
    text = str(value).strip()
    return text.casefold()


def _wakeword_id(stem: str) -> str:
    """Derive canonical identifier from a model filename stem."""
    normalized = stem.strip()
    for prefix in ("openwakeword_", "oww_"):
        if normalized.lower().startswith(prefix):
            normalized = normalized[len(prefix):]
            break
    parts = normalized.split("_v")
    return parts[0] if parts else normalized


def _wakeword_id_and_version(stem: str) -> Tuple[str, Optional[str]]:
    """Extract canonical ID and artifact version if present in filename stem."""
    normalized = stem.strip()
    for prefix in ("openwakeword_", "oww_"):
        if normalized.lower().startswith(prefix):
            normalized = normalized[len(prefix):]
            break
    parts = normalized.split("_v")
    if len(parts) > 1 and parts[-1]:
        return parts[0], parts[-1]
    return normalized, None


def _display_name(word_id: str) -> str:
    return word_id.replace("_", " ").title()


@dataclass(frozen=True)
class InternalWakeWordCatalogEntry:
    """Internal representation of a catalog entry including paths and formats."""

    id: str
    displayName: str
    aliases: List[str] = field(default_factory=list)
    artifactVersion: Optional[str] = None
    available: bool = True
    unavailableReason: Optional[str] = None
    catalogRevision: int = 1
    availableFormats: List[str] = field(default_factory=list)
    default: bool = False
    source: str = "openwakeword"
    paths: Dict[str, str] = field(default_factory=dict)

    def to_public_dict(self) -> Dict[str, Any]:
        """Returns ONLY the frozen public catalog fields, omitting local paths."""
        data: Dict[str, Any] = {
            "id": self.id,
            "displayName": self.displayName,
            "aliases": list(self.aliases),
            "artifactVersion": self.artifactVersion,
            "available": self.available,
            "catalogRevision": self.catalogRevision,
        }
        if not self.available and self.unavailableReason:
            data["unavailableReason"] = self.unavailableReason
        return data

    def to_internal_dict(self) -> Dict[str, Any]:
        """Returns internal dictionary including formats and resolved paths."""
        data = self.to_public_dict()
        data["availableFormats"] = list(self.availableFormats)
        data["default"] = self.default
        data["source"] = self.source
        data["paths"] = dict(self.paths)
        return data


class OpenWakeWordCatalog:
    """
    Authoritative wake-word model catalog and resolution authority.
    Discovers local models, maps aliases without heuristic guessing,
    validates pipeline dependencies, and respects globally disabled IDs.
    """

    def __init__(
        self,
        model_root: Optional[Union[str, Path]] = None,
        configured_paths: Optional[Sequence[Union[str, Path]]] = None,
        disable_provider: Optional[Callable[[], Set[str]]] = None,
    ):
        self.model_root = (
            Path(model_root).expanduser()
            if model_root
            else self._discover_root()
        )
        self.configured_paths = [
            Path(p).expanduser() for p in (configured_paths or []) if str(p).strip()
        ]
        self.disable_provider = disable_provider
        self._catalog_revision = 1
        self._entries_cache: Optional[List[InternalWakeWordCatalogEntry]] = None

    @property
    def catalog_revision(self) -> int:
        self._scan_catalog()
        return self._catalog_revision

    @staticmethod
    def _discover_root() -> Optional[Path]:
        env_root = os.getenv(OPENWAKEWORD_MODEL_ROOT_ENV)
        if env_root:
            candidate = Path(env_root).expanduser()
            if candidate.exists():
                return candidate
        if DEFAULT_OPENWAKEWORD_MODEL_ROOT.exists():
            return DEFAULT_OPENWAKEWORD_MODEL_ROOT
        return None

    def _get_disabled_ids(self) -> Set[str]:
        if self.disable_provider is None:
            return set()
        try:
            raw = self.disable_provider()
            return {_normalize_id(item) for item in raw if item}
        except Exception:
            logger.exception("Error querying wake-word disable provider")
            return set()

    def _scan_catalog(self) -> List[InternalWakeWordCatalogEntry]:
        if self._entries_cache is not None:
            return self._entries_cache

        entries_by_id: Dict[str, InternalWakeWordCatalogEntry] = {}
        manifest_data = self._load_manifest()
        disabled_ids = self._get_disabled_ids()

        candidate_dirs: List[Path] = []
        if self.model_root and self.model_root.is_dir():
            candidate_dirs.append(self.model_root)
        manifest_path = manifest_data.get("path")
        if manifest_path:
            p = Path(manifest_path).expanduser()
            if p.is_dir() and p not in candidate_dirs:
                candidate_dirs.append(p)

        # Check availability of pipeline feature models
        has_onnx_pipeline = any(self._has_feature_models("onnx", d, manifest_data) for d in candidate_dirs)
        has_tflite_pipeline = any(self._has_feature_models("tflite", d, manifest_data) for d in candidate_dirs)

        # 1. Scan configured explicit paths
        for path in self.configured_paths:
            if path.is_file():
                if path.name.lower() == "models.json":
                    continue
                stem = path.stem
                canonical_id, art_version = _wakeword_id_and_version(stem)
                fmt = path.suffix.lower().lstrip(".")
                has_pipeline = has_onnx_pipeline if fmt == "onnx" else has_tflite_pipeline

                is_disabled = _normalize_id(canonical_id) in disabled_ids
                avail = has_pipeline and not is_disabled
                reason = None
                if is_disabled:
                    reason = REASON_GLOBALLY_DISABLED
                elif not has_pipeline:
                    reason = REASON_MISSING_FEATURE_MODELS

                entry = InternalWakeWordCatalogEntry(
                    id=canonical_id,
                    displayName=_display_name(canonical_id),
                    aliases=[],
                    artifactVersion=art_version,
                    available=avail,
                    unavailableReason=reason,
                    catalogRevision=self._catalog_revision,
                    availableFormats=[fmt] if fmt else [],
                    default=False,
                    source="configured_paths",
                    paths={fmt: str(path.resolve())},
                )
                entries_by_id[canonical_id] = entry

        # 2. Add manifest-mapped models
        base_dir = Path(manifest_path).expanduser() if manifest_path else (self.model_root or Path.cwd())
        for fmt, model_dict in [("onnx", manifest_data.get("onnx_models", {})), ("tflite", manifest_data.get("tflite_models", {}))]:
            for model_id, filename in model_dict.items():
                file_path = base_dir / filename
                if not file_path.is_file() and self.model_root:
                    file_path = self.model_root / filename
                if file_path.is_file():
                    canonical_id = model_id
                    has_pipeline = has_onnx_pipeline if fmt == "onnx" else has_tflite_pipeline
                    meta = manifest_data.get("metadata", {}).get(canonical_id, {})
                    display_name = meta.get("displayName") or _display_name(canonical_id)
                    aliases = list(meta.get("aliases") or [])
                    version = meta.get("artifactVersion")
                    is_disabled = _normalize_id(canonical_id) in disabled_ids
                    avail = has_pipeline and not is_disabled
                    reason = None
                    if is_disabled:
                        reason = REASON_GLOBALLY_DISABLED
                    elif not has_pipeline:
                        reason = REASON_MISSING_FEATURE_MODELS

                    is_default = (canonical_id == manifest_data.get("default_model") or canonical_id == "hey_jarvis")

                    if canonical_id in entries_by_id:
                        existing = entries_by_id[canonical_id]
                        updated_formats = list(set(existing.availableFormats + [fmt]))
                        updated_paths = dict(existing.paths)
                        updated_paths[fmt] = str(file_path.resolve())
                        entries_by_id[canonical_id] = InternalWakeWordCatalogEntry(
                            id=existing.id,
                            displayName=existing.displayName,
                            aliases=existing.aliases or aliases,
                            artifactVersion=existing.artifactVersion or version,
                            available=existing.available and avail,
                            unavailableReason=existing.unavailableReason or reason,
                            catalogRevision=self._catalog_revision,
                            availableFormats=updated_formats,
                            default=existing.default or is_default,
                            source="manifest",
                            paths=updated_paths,
                        )
                    else:
                        entries_by_id[canonical_id] = InternalWakeWordCatalogEntry(
                            id=canonical_id,
                            displayName=display_name,
                            aliases=aliases,
                            artifactVersion=version,
                            available=avail,
                            unavailableReason=reason,
                            catalogRevision=self._catalog_revision,
                            availableFormats=[fmt],
                            default=is_default,
                            source="manifest",
                            paths={fmt: str(file_path.resolve())},
                        )

        # 3. Scan model root and candidate directories for loose model files
        for candidate_dir in candidate_dirs:
            for file_path in candidate_dir.iterdir():
                if not file_path.is_file():
                    continue
                suffix = file_path.suffix.lower()
                if suffix not in {".onnx", ".tflite"}:
                    continue
                stem = file_path.stem
                if stem in {"melspectrogram", "embedding_model"}:
                    continue

                canonical_id, art_version = _wakeword_id_and_version(stem)
                fmt = suffix.lstrip(".")
                has_pipeline = has_onnx_pipeline if fmt == "onnx" else has_tflite_pipeline

                meta = manifest_data.get("metadata", {}).get(canonical_id, {})
                display_name = meta.get("displayName") or _display_name(canonical_id)
                aliases = list(meta.get("aliases") or [])
                manifest_version = meta.get("artifactVersion")
                version = manifest_version or art_version

                is_disabled = _normalize_id(canonical_id) in disabled_ids
                avail = has_pipeline and not is_disabled
                reason = None
                if is_disabled:
                    reason = REASON_GLOBALLY_DISABLED
                elif not has_pipeline:
                    reason = REASON_MISSING_FEATURE_MODELS

                is_default = (canonical_id == manifest_data.get("default_model") or canonical_id == "hey_jarvis")

                if canonical_id in entries_by_id:
                    existing = entries_by_id[canonical_id]
                    updated_formats = list(set(existing.availableFormats + [fmt]))
                    updated_paths = dict(existing.paths)
                    updated_paths[fmt] = str(file_path.resolve())
                    entries_by_id[canonical_id] = InternalWakeWordCatalogEntry(
                        id=existing.id,
                        displayName=existing.displayName,
                        aliases=existing.aliases or aliases,
                        artifactVersion=existing.artifactVersion or version,
                        available=existing.available and avail,
                        unavailableReason=existing.unavailableReason or reason,
                        catalogRevision=self._catalog_revision,
                        availableFormats=updated_formats,
                        default=existing.default or is_default,
                        source="model_root",
                        paths=updated_paths,
                    )
                else:
                    entries_by_id[canonical_id] = InternalWakeWordCatalogEntry(
                        id=canonical_id,
                        displayName=display_name,
                        aliases=aliases,
                        artifactVersion=version,
                        available=avail,
                        unavailableReason=reason,
                        catalogRevision=self._catalog_revision,
                        availableFormats=[fmt],
                        default=is_default,
                        source="model_root",
                        paths={fmt: str(file_path.resolve())},
                    )

        # Sort entries deterministically by canonical ID
        sorted_entries = sorted(entries_by_id.values(), key=lambda e: e.id)
        self._entries_cache = sorted_entries
        return sorted_entries

    def _load_manifest(self) -> Dict[str, Any]:
        manifest_files = []
        if self.model_root:
            if self.model_root.is_file() and self.model_root.name.lower() == "models.json":
                manifest_files.append(self.model_root)
            elif self.model_root.is_dir():
                manifest_files.append(self.model_root / "models.json")
        for cp in self.configured_paths:
            if cp.is_file() and cp.name.lower() == "models.json":
                manifest_files.append(cp)
            elif cp.is_dir() and (cp / "models.json").is_file():
                manifest_files.append(cp / "models.json")

        for manifest_file in manifest_files:
            if manifest_file.is_file():
                try:
                    data = json.loads(manifest_file.read_text(encoding="utf-8"))
                    oww_section = data.get("openwakeword_models", {})
                    rev = oww_section.get("catalog_revision")
                    if isinstance(rev, int):
                        self._catalog_revision = rev
                    return oww_section
                except Exception:
                    logger.exception("Error parsing openwakeword manifest %s", manifest_file)
        return {}

    def _has_feature_models(
        self,
        framework: str,
        target_dir: Optional[Path] = None,
        manifest_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        manifest = manifest_data or self._load_manifest()
        pipe_models = manifest.get("pipeline_models", {})
        mel_name = pipe_models.get(f"melspectrogram_{framework}") or DEFAULT_FEATURE_MODELS.get(framework, ("melspectrogram.onnx",))[0]
        emb_name = pipe_models.get(f"embedding_model_{framework}") or DEFAULT_FEATURE_MODELS.get(framework, ("", "embedding_model.onnx"))[1]

        search_dirs = []
        if target_dir and target_dir.is_dir():
            search_dirs.append(target_dir)
        if manifest.get("path"):
            p = Path(manifest["path"]).expanduser()
            if p.is_dir() and p not in search_dirs:
                search_dirs.append(p)
        if self.model_root and self.model_root.is_dir() and self.model_root not in search_dirs:
            search_dirs.append(self.model_root)

        for s_dir in search_dirs:
            if (s_dir / mel_name).is_file() and (s_dir / emb_name).is_file():
                return True
        return False

    def public_entries(
        self,
        framework: Optional[str] = "onnx",
    ) -> List[Dict[str, Any]]:
        """Returns the public catalog representation without local filesystem paths."""
        entries = self._scan_catalog()
        result = []
        for e in entries:
            if framework and framework not in e.availableFormats and e.availableFormats:
                continue
            result.append(e.to_public_dict())
        return result

    def entries(
        self,
        framework: Optional[str] = "onnx",
        include_paths: bool = False,
    ) -> List[Dict[str, Any]]:
        """Returns entries list for internal service/adapter usage."""
        scanned = self._scan_catalog()
        result = []
        for e in scanned:
            if framework and framework not in e.availableFormats and e.availableFormats:
                continue
            if include_paths:
                result.append(e.to_internal_dict())
            else:
                result.append(e.to_public_dict())
        return result

    @property
    def default_model(self) -> Optional[str]:
        scanned = self._scan_catalog()
        for e in scanned:
            if e.default and e.available:
                return e.id
        available = [e for e in scanned if e.available]
        return available[0].id if available else None

    def _build_alias_maps(self) -> Tuple[Dict[str, str], Set[str]]:
        """
        Build lookup map: normalized_key -> canonical_id.
        Detects alias-alias and alias-id collisions deterministically.
        """
        scanned = self._scan_catalog()
        lookup: Dict[str, str] = {}
        collisions: Set[str] = set()

        for entry in scanned:
            canon_norm = _normalize_id(entry.id)
            if canon_norm in lookup and lookup[canon_norm] != entry.id:
                collisions.add(canon_norm)
            lookup[canon_norm] = entry.id

            for alias in entry.aliases:
                alias_norm = _normalize_id(alias)
                if not alias_norm:
                    continue
                if alias_norm in lookup and lookup[alias_norm] != entry.id:
                    collisions.add(alias_norm)
                else:
                    lookup[alias_norm] = entry.id

        return lookup, collisions

    def resolve_detailed(
        self,
        model_ids: Optional[Union[str, Sequence[str]]],
        preferred_framework: str = "onnx",
    ) -> Tuple[List[Dict[str, Any]], List[str], Dict[str, str]]:
        """
        Authoritatively resolves model IDs / aliases against the catalog.
        Returns:
            - resolved_entries: List of resolved models with canonical ID and path
            - problematic_ids: List of requested IDs that could not be cleanly resolved
            - rejection_reasons: Dict mapping problematic ID -> reason code
        """
        scanned = self._scan_catalog()
        entries_by_id = {e.id: e for e in scanned}
        lookup_map, collisions = self._build_alias_maps()

        if model_ids is None or model_ids == "" or model_ids == []:
            default_id = self.default_model
            if default_id and default_id in entries_by_id:
                entry = entries_by_id[default_id]
                path = entry.paths.get(preferred_framework)
                if path and entry.available:
                    return [{"id": entry.id, "path": path, "source": entry.source}], [], {}
                reason = entry.unavailableReason or REASON_NOT_FOUND
                return [], [default_id], {default_id: reason}
            return [], ["<default>"], {"<default>": REASON_NOT_FOUND}

        if isinstance(model_ids, str):
            requested = [item.strip() for item in model_ids.split(",") if item.strip()]
        else:
            requested = [str(item).strip() for item in model_ids if str(item).strip()]

        if not requested:
            default_id = self.default_model
            if default_id and default_id in entries_by_id:
                entry = entries_by_id[default_id]
                path = entry.paths.get(preferred_framework)
                if path and entry.available:
                    return [{"id": entry.id, "path": path, "source": entry.source}], [], {}
                reason = entry.unavailableReason or REASON_NOT_FOUND
                return [], [default_id], {default_id: reason}
            return [], ["<default>"], {"<default>": REASON_NOT_FOUND}

        resolved: List[Dict[str, Any]] = []
        problematic: List[str] = []
        reasons: Dict[str, str] = {}

        for req in requested:
            norm = _normalize_id(req)
            if norm in collisions:
                problematic.append(req)
                reasons[req] = REASON_ALIAS_COLLISION
                continue

            canonical_id = lookup_map.get(norm)
            if not canonical_id or canonical_id not in entries_by_id:
                problematic.append(req)
                reasons[req] = REASON_NOT_FOUND
                continue

            entry = entries_by_id[canonical_id]
            if not entry.available:
                problematic.append(req)
                reasons[req] = entry.unavailableReason or REASON_UNKNOWN
                continue

            path = entry.paths.get(preferred_framework)
            if not path or not Path(path).is_file():
                problematic.append(req)
                reasons[req] = REASON_MISSING_MODEL_FILES
                continue

            resolved.append({
                "id": entry.id,  # Unmodified canonical ID
                "path": path,
                "source": entry.source,
            })

        return resolved, problematic, reasons

    def resolve(
        self,
        model_ids: Optional[Union[str, Sequence[str]]],
        preferred_framework: str = "onnx",
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        resolved, missing, _ = self.resolve_detailed(model_ids, preferred_framework)
        return resolved, missing

    def pipeline_paths(
        self,
        framework: str = "onnx",
        classifier_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, str]:
        """Resolves the feature extractor pipeline models for the given framework."""
        manifest = self._load_manifest()
        pipe_models = manifest.get("pipeline_models", {})
        mel_name = pipe_models.get(f"melspectrogram_{framework}") or DEFAULT_FEATURE_MODELS.get(framework, ("melspectrogram.onnx",))[0]
        emb_name = pipe_models.get(f"embedding_model_{framework}") or DEFAULT_FEATURE_MODELS.get(framework, ("", "embedding_model.onnx"))[1]

        candidates = []
        if classifier_path:
            candidates.append(Path(classifier_path).parent)
        if manifest.get("path"):
            candidates.append(Path(manifest["path"]).expanduser())
        if self.model_root:
            candidates.append(self.model_root)

        for candidate_dir in candidates:
            if not candidate_dir.is_dir():
                continue
            mel = candidate_dir / mel_name
            emb = candidate_dir / emb_name
            if mel.is_file() and emb.is_file():
                return {
                    "melspec_model_path": str(mel.resolve()),
                    "embedding_model_path": str(emb.resolve()),
                }
        return {}
