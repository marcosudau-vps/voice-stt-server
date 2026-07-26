"""Offline OpenWakeWord model discovery backed by an optional models.json."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


OPENWAKEWORD_MODEL_ROOT_ENV = "VOICESTT_OPENWAKEWORD_MODEL_ROOT"
OPENWAKEWORD_MANIFEST_NAME = "models.json"
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
        self._load_manifest()

    @property
    def manifest_path(self):
        return self._manifest_path

    @property
    def default_model(self):
        if not self._manifest_section:
            return None
        value = str(self._manifest_section.get("default_model") or "").strip()
        return value or None

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
            self._manifest_path = path.resolve()
            self._manifest_section = section
            self._model_base = self._resolve_model_base(section, path)
            return

    def _resolve_model_base(self, section, manifest_path):
        declared = str(section.get("path") or "").strip()
        candidates = []
        if declared:
            declared_path = Path(declared).expanduser()
            candidates.append(declared_path)
            if not declared_path.is_absolute():
                candidates.append(manifest_path.parent / declared_path)
        if self.model_root is not None:
            candidates.append(self.model_root)
        candidates.append(manifest_path.parent)

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
        if not self._manifest_section or self._model_base is None:
            return []
        pipeline = self._manifest_section.get("pipeline_models")
        pipeline_filenames = {
            str(value).strip().lower()
            for value in pipeline.values()
            if str(value).strip()
        } if isinstance(pipeline, dict) else set()
        grouped = {}
        for framework, mapping_name in (
            ("onnx", "onnx_models"),
            ("tflite", "tflite_models"),
        ):
            mapping = self._manifest_section.get(mapping_name)
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
                path = (self._model_base / filename).resolve()
                if not path.is_file():
                    continue
                entry = grouped.setdefault(model_id.lower(), {
                    "id": model_id,
                    "label": model_id.replace("_", " ").title(),
                    "backend": "openwakeword",
                    "formats": {},
                    "default": False,
                    "source": "models.json",
                })
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
        grouped = self._manifest_entries() or self._scanned_entries()
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
        return sorted(result, key=lambda item: item["label"].lower())

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
        if self._manifest_section and self._model_base is not None:
            mapping = self._manifest_section.get("pipeline_models")
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
                key: (self._model_base / str(name)).resolve()
                for key, name in names.items()
                if name
            }
            if len(paths) == 2 and all(path.is_file() for path in paths.values()):
                return {key: str(path) for key, path in paths.items()}

        root = (
            Path(classifier_path).expanduser().parent
            if classifier_path
            else self.model_root
        )
        if root is None:
            return {}
        extension = ".tflite" if framework == "tflite" else ".onnx"
        paths = {
            "melspec_model_path": root / f"melspectrogram{extension}",
            "embedding_model_path": root / f"embedding_model{extension}",
        }
        return {
            key: str(path.resolve())
            for key, path in paths.items()
            if path.is_file()
        }
