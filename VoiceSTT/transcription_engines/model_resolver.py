"""Resolve local ASR model aliases without silently downloading model data."""

import os
from pathlib import Path

from .base import TranscriptionEngineError


TRUE_VALUES = {"1", "true", "yes", "on"}
FASTER_WHISPER_ROOT_ENV = "VOICESTT_FASTER_WHISPER_MODEL_ROOT"
KROKO_ROOT_ENV = "VOICESTT_KROKO_MODEL_ROOT"
OFFLINE_MODELS_ENV = "VOICESTT_OFFLINE_MODELS"


def _bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in TRUE_VALUES
    return bool(value)


def offline_models_enabled(options=None):
    """Return whether model resolution must remain strictly local."""

    options = options or {}
    if "local_files_only" in options:
        return _bool(options["local_files_only"])
    if "offline_models" in options:
        return _bool(options["offline_models"])
    return _bool(os.getenv(OFFLINE_MODELS_ENV), False)


def _is_ctranslate2_model(path):
    return path.is_dir() and (path / "config.json").is_file() and (path / "model.bin").is_file()


def _snapshot_model(path):
    if _is_ctranslate2_model(path):
        return path
    snapshots = path / "snapshots"
    if snapshots.is_dir():
        for candidate in sorted(snapshots.iterdir(), reverse=True):
            if _is_ctranslate2_model(candidate):
                return candidate
    return None


def _model_aliases(model):
    value = str(model).strip()
    normalized = value.lower().replace("_", "-")
    aliases = [value]
    if normalized.startswith("models--"):
        aliases.append(normalized)
    else:
        aliases.extend(
            [
                f"models--Systran--faster-whisper-{normalized}",
                f"faster-whisper-{normalized}",
                normalized,
            ]
        )
    return list(dict.fromkeys(aliases))


def resolve_faster_whisper_model(model, download_root=None, options=None):
    """Resolve a faster-whisper name against a mounted local model root."""

    options = dict(options or {})
    value = str(model).strip()
    direct = Path(value).expanduser()
    resolved = _snapshot_model(direct)
    if resolved is not None:
        return str(resolved.resolve())

    roots = [
        options.get("model_root"),
        os.getenv(FASTER_WHISPER_ROOT_ENV),
        download_root,
    ]
    checked = []
    for root_value in roots:
        if not root_value:
            continue
        root = Path(str(root_value)).expanduser()
        for alias in _model_aliases(value):
            candidate = root / alias
            checked.append(str(candidate))
            resolved = _snapshot_model(candidate)
            if resolved is not None:
                return str(resolved.resolve())

        if root.is_dir():
            suffix = value.lower().replace("_", "-")
            for candidate in sorted(root.glob("models--*--*")):
                if candidate.name.lower().endswith(suffix):
                    checked.append(str(candidate))
                    resolved = _snapshot_model(candidate)
                    if resolved is not None:
                        return str(resolved.resolve())

    locations = ", ".join(checked) if checked else value
    prefix = "Offline model mode: " if offline_models_enabled(options) else ""
    raise TranscriptionEngineError(
        prefix + "The server-authoritative STT model manager could not resolve local "
        f"faster-whisper model '{value}'. Checked: {locations}. Provision it "
        "through the model-management API or configure a local model root; "
        "engine libraries are not allowed to download models implicitly."
    )


def resolve_kroko_model(model, download_root=None, options=None):
    """Resolve a Kroko .data model against its dedicated mounted root."""

    options = dict(options or {})
    value = options.get("model_path") or options.get("model_file") or model
    path = Path(str(value)).expanduser()
    if path.is_file():
        return str(path.resolve())

    roots = [
        options.get("model_root"),
        options.get("model_dir"),
        os.getenv(KROKO_ROOT_ENV),
        download_root,
    ]
    checked = []
    for root_value in roots:
        if not root_value:
            continue
        root = Path(str(root_value)).expanduser()
        candidate = root / path.name
        checked.append(str(candidate))
        if candidate.is_file():
            return str(candidate.resolve())

    model_dir = options.get("model_dir")
    if model_dir:
        root = Path(str(model_dir)).expanduser()
        local_models = sorted(
            item for item in root.glob("*.data")
            if item.is_file() and not item.name.lower().endswith(".part")
        ) if root.is_dir() else []
        if len(local_models) == 1:
            return str(local_models[0].resolve())

    locations = ", ".join(checked) if checked else str(path)
    prefix = "Offline model mode: " if offline_models_enabled(options) else ""
    raise TranscriptionEngineError(
        prefix + "Missing kroko-onnx model. The server-authoritative STT model manager "
        "could not resolve local "
        f"Kroko model '{path.name}'. Checked: {locations}. Provision it "
        "through the model-management API or configure a local model root; "
        "engine libraries are not allowed to download models implicitly."
    )
