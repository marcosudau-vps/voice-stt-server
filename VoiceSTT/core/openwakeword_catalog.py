"""Offline OpenWakeWord model discovery backed by an optional models.json."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


OPENWAKEWORD_MODEL_ROOT_ENV = "VOICESTT_OPENWAKEWORD_MODEL_ROOT"
OPENWAKEWORD_MANIFEST_NAME = "models.json"
BUNDLED_OPENWAKEWORD_MODEL_ROOT = (
    Path(__file__).resolve().parent.parent / "assets" / "wakeword_models"
)
OPENWAKEWORD_SUPPORT_IDS = {
    "embedding_model",
    "melspectrogram",
    "silero_vad",
}


def _split_paths(values):
    if values is None:
        return []
    if isinstance(values, (list, tuple, set)):
        raw_values = values
    else:
        raw_values = str(values).split(",")
    return [
        Path(str(value).strip()).expanduser()
        for value in raw_values
        if str(value).strip()
    ]


def _wakeword_id(stem):
    return re.sub(r"_v\d+(?:\.\d+)*$", "", stem, flags=re.IGNORECASE)


class OpenWakeWordCatalog:
    """Resolve local wake-word classifiers and pipeline models without downloads."""

    def __init__(self, model_root=None, configured_paths=None):
        configured_root = model_root or os.getenv(OPENWAKEWORD_MODEL_ROOT_ENV, "")
        self.model_root = (
            Path(configured_root).expanduser()
            if configured_root
            else None
        )
        self.configured_paths = _split_paths(configured_paths)
        self._manifest_path = None
        self._manifest_section = None
        self._model_base = None
        self._manifest_sources = []
        self._load_manifest()

    @property
    def manifest_path(self):
        return self._manifest_path

    @property
    def default_model(self):
        for _path, section, _base in reversed(self._manifest_sources):
            value = str(section.get("default_model") or "").strip()
            if value:
                return value
        return None

    def _manifest_candidates(self):
        candidates = []

        def add(path):
            if path is None:
                return
            path = Path(path).expanduser()
            candidate = (
                path
                if path.name.lower() == OPENWAKEWORD_MANIFEST_NAME
                else path / OPENWAKEWORD_MANIFEST_NAME
                if path.is_dir()
                else path.parent / OPENWAKEWORD_MANIFEST_NAME
            )
            if candidate not in candidates:
                candidates.append(candidate)

        add(BUNDLED_OPENWAKEWORD_MODEL_ROOT)
        add(self.model_root)
        for configured in self.configured_paths:
            add(configured)
        return candidates

    def _load_manifest(self):
        for path in self._manifest_candidates():
            if not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                section = payload.get("openwakeword_models")
            except (OSError, UnicodeError, ValueError, TypeError):
                continue
            if not isinstance(section, dict):
                continue
            source = (
                path.resolve(),
                section,
                self._resolve_model_base(section, path),
            )
            self._manifest_sources.append(source)
        if self._manifest_sources:
            self._manifest_path, self._manifest_section, self._model_base = (
                self._manifest_sources[-1]
            )

    def _resolve_model_base(self, section, manifest_path):
        declared = str(section.get("path") or "").strip()
        candidates = []
        if declared:
            declared_path = Path(declared).expanduser()
            candidates.append(declared_path)
            if not declared_path.is_absolute():
                candidates.append(manifest_path.parent / declared_path)
        candidates.append(manifest_path.parent)
        if self.model_root is not None:
            candidates.append(self.model_root)

        mapped_names = []
        for mapping_name in ("onnx_models", "tflite_models", "pipeline_models"):
            mapping = section.get(mapping_name)
            if isinstance(mapping, dict):
                mapped_names.extend(
                    str(value).strip()
                    for value in mapping.values()
                    if str(value).strip()
                )

        for candidate in candidates:
            if not candidate.is_dir():
                continue
            if not mapped_names or any((candidate / name).is_file() for name in mapped_names):
                return candidate.resolve()
        return manifest_path.parent.resolve()

    def _manifest_entries(self):
        if not self._manifest_sources:
            return []
        grouped = {}
        for manifest_path, section, model_base in self._manifest_sources:
            pipeline = section.get("pipeline_models")
            pipeline_filenames = {
                str(value).strip().lower()
                for value in pipeline.values()
                if str(value).strip()
            } if isinstance(pipeline, dict) else set()
            for framework, mapping_name in (
                ("onnx", "onnx_models"),
                ("tflite", "tflite_models"),
            ):
                mapping = section.get(mapping_name)
                if not isinstance(mapping, dict):
                    continue
                for model_id, filename in mapping.items():
                    model_id = str(model_id).strip()
                    filename = str(filename).strip()
                    if not model_id or not filename:
                        continue
                    if (
                        model_id.lower() in OPENWAKEWORD_SUPPORT_IDS
                        or filename.lower() in pipeline_filenames
                    ):
                        continue
                    path = (model_base / filename).resolve()
                    if not path.is_file():
                        continue
                    key = model_id.lower()
                    entry = grouped.setdefault(key, {
                        "id": model_id,
                        "label": model_id.replace("_", " ").title(),
                        "backend": "openwakeword",
                        "formats": {},
                        "default": False,
                        "source": "bundled" if manifest_path.parent == BUNDLED_OPENWAKEWORD_MODEL_ROOT.resolve() else "models.json",
                    })
                    entry["id"] = model_id
                    entry["label"] = model_id.replace("_", " ").title()
                    entry["source"] = "bundled" if manifest_path.parent == BUNDLED_OPENWAKEWORD_MODEL_ROOT.resolve() else "models.json"
                    entry["formats"][framework] = str(path)

        default_id = str(self.default_model or "").lower()
        for key, entry in grouped.items():
            entry["default"] = key == default_id
        return list(grouped.values())

    def _scanned_entries(self):
        candidates = []
        if self.model_root is not None and self.model_root.is_dir():
            candidates.extend(path for path in self.model_root.iterdir() if path.is_file())
        for configured in self.configured_paths:
            if configured.is_dir():
                candidates.extend(
                    path for path in configured.iterdir()
                    if path.is_file()
                )
            elif configured.is_file():
                candidates.append(configured)

        grouped = {}
        for path in candidates:
            suffix = path.suffix.lower()
            if suffix not in {".onnx", ".tflite"}:
                continue
            stem = path.stem
            if stem.lower() in OPENWAKEWORD_SUPPORT_IDS:
                continue
            model_id = _wakeword_id(stem)
            entry = grouped.setdefault(model_id.lower(), {
                "id": model_id,
                "label": model_id.replace("_", " ").title(),
                "backend": "openwakeword",
                "formats": {},
                "default": False,
                "source": "filesystem",
            })
            entry["formats"][suffix.lstrip(".")] = str(path.resolve())
        return list(grouped.values())

    def entries(self, preferred_framework="onnx", include_paths=True):
        grouped_by_id = {
            entry["id"].lower(): entry for entry in self._manifest_entries()
        }
        for scanned in self._scanned_entries():
            key = scanned["id"].lower()
            if key in grouped_by_id:
                grouped_by_id[key]["formats"].update(scanned["formats"])
                grouped_by_id[key]["source"] = scanned["source"]
            else:
                grouped_by_id[key] = scanned
        grouped = list(grouped_by_id.values())
        preferred = str(preferred_framework or "onnx").strip().lower()
        result = []
        for source in grouped:
            formats = dict(source["formats"])
            path = (
                formats.get(preferred)
                or formats.get("onnx")
                or formats.get("tflite")
            )
            if path is None:
                continue
            entry = {
                "id": source["id"],
                "label": source["label"],
                "backend": "openwakeword",
                "availableFormats": sorted(formats),
                "default": bool(source.get("default")),
                "source": source.get("source", "filesystem"),
            }
            if include_paths:
                entry["path"] = path
                entry["paths"] = formats
            result.append(entry)
        return sorted(
            result,
            key=lambda item: (
                not item["default"],
                item["label"].lower(),
            ),
        )

    def resolve(self, model_ids, preferred_framework="onnx"):
        if isinstance(model_ids, str):
            requested = [
                value.strip()
                for value in model_ids.split(",")
                if value.strip()
            ]
        else:
            requested = [
                str(value).strip()
                for value in (model_ids or ())
                if str(value).strip()
            ]
        if not requested and self.default_model:
            requested = [self.default_model]
        entries = self.entries(preferred_framework, include_paths=True)
        by_id = {entry["id"].lower(): entry for entry in entries}
        preferred = str(
            preferred_framework or "onnx"
        ).strip().lower()
        resolved = []
        missing = []
        for requested_id in requested:
            entry = by_id.get(requested_id.lower())
            if (
                entry is None
                or preferred not in entry.get("availableFormats", ())
            ):
                missing.append(requested_id)
            else:
                entry = dict(entry)
                entry["path"] = entry["paths"][preferred]
                resolved.append(entry)
        return resolved, missing

    def pipeline_paths(self, framework="onnx", classifier_path=None):
        framework = str(framework or "onnx").strip().lower()
        sources = list(reversed(self._manifest_sources))
        matching = []
        if classifier_path:
            classifier = Path(classifier_path).expanduser().resolve()
            remaining = []
            for source in sources:
                _manifest_path, section, model_base = source
                mapped = []
                for mapping_name in ("onnx_models", "tflite_models"):
                    mapping = section.get(mapping_name)
                    if isinstance(mapping, dict):
                        mapped.extend((model_base / str(name)).resolve() for name in mapping.values())
                (matching if classifier in mapped else remaining).append(source)
            sources = remaining

        def from_manifest(source):
            _manifest_path, section, model_base = source
            mapping = section.get("pipeline_models")
            mapping = mapping if isinstance(mapping, dict) else {}
            names = {
                "melspec_model_path": mapping.get(
                    f"melspectrogram_{framework}"
                ),
                "embedding_model_path": mapping.get(
                    f"embedding_model_{framework}"
                ),
            }
            paths = {
                key: (model_base / str(name)).resolve()
                for key, name in names.items()
                if name
            }
            if len(paths) == 2 and all(path.is_file() for path in paths.values()):
                return {key: str(path) for key, path in paths.items()}
            return {}

        for source in matching:
            resolved = from_manifest(source)
            if resolved:
                return resolved

        root = (
            Path(classifier_path).expanduser().parent
            if classifier_path
            else self.model_root
        )
        extension = ".tflite" if framework == "tflite" else ".onnx"
        if root is not None:
            paths = {
                "melspec_model_path": root / f"melspectrogram{extension}",
                "embedding_model_path": root / f"embedding_model{extension}",
            }
            resolved = {
                key: str(path.resolve())
                for key, path in paths.items()
                if path.is_file()
            }
            if len(resolved) == 2:
                return resolved

        for source in sources:
            resolved = from_manifest(source)
            if resolved:
                return resolved
        return {}
