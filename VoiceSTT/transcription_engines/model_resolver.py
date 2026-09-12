"""Resolve local ASR model aliases without silently downloading model data."""

import os
from pathlib import Path

from .base import TranscriptionEngineError


TRUE_VALUES = {"1", "true", "yes", "on"}
FASTER_WHISPER_ROOT_ENV = "VOICESTT_FASTER_WHISPER_MODEL_ROOT"
FASTER_WHISPER_AUTO_DOWNLOAD_ENV = "VOICESTT_FASTER_WHISPER_AUTO_DOWNLOAD"
KROKO_ROOT_ENV = "VOICESTT_KROKO_MODEL_ROOT"
KROKO_VARIANT_ENV = "VOICESTT_KROKO_VARIANT"
OFFLINE_MODELS_ENV = "VOICESTT_OFFLINE_MODELS"
KROKO_HOME_URL = "https://kroko.ai/"

# V1.0.0 intentionally exposes a small, reviewed download allowlist. Local
# absolute model directories remain valid regardless of this registry. The
# registry only governs network-backed resolution when the operator explicitly
# opts in to automatic download.
FASTER_WHISPER_MODEL_REGISTRY = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
    "large": "Systran/faster-whisper-large-v3",
    "large_turbo": "deepdml/faster-whisper-large-v3-turbo-ct2",
}


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


def faster_whisper_auto_download_enabled(options=None):
    """Return whether a reviewed faster-whisper alias may be downloaded.

    V1.0.0 defaults this to *disabled*. Network-backed resolution therefore
    requires an explicit per-engine option or the dedicated environment flag.
    """

    options = options or {}
    if "auto_download_model" in options:
        return _bool(options["auto_download_model"], False)
    if "download_model" in options:
        return _bool(options["download_model"], False)
    return _bool(os.getenv(FASTER_WHISPER_AUTO_DOWNLOAD_ENV), False)


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


def _normalized_faster_whisper_alias(value):
    alias = str(value).strip().lower().replace("-", "_")
    if alias == "large_v3":
        return "large"
    if alias in {"large_v3_turbo", "large_turbo"}:
        return "large_turbo"
    return alias


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
    """Resolve a faster-whisper model without implicit network access.

    Existing local model directories are always accepted. If no local model is
    found, V1.0.0 fails closed by default. An operator may explicitly opt into
    download, but only for aliases in :data:`FASTER_WHISPER_MODEL_REGISTRY`.
    """

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
    if offline_models_enabled(options) or not faster_whisper_auto_download_enabled(options):
        raise TranscriptionEngineError(
            "faster-whisper model '%s' was not found locally and automatic model "
            "download is disabled by default. Checked: %s. Set %s to the mounted "
            "CTranslate2 model root or pass an absolute model directory. To opt "
            "in to a reviewed model download, set engine option "
            "auto_download_model=true or %s=1." % (
                value,
                locations,
                FASTER_WHISPER_ROOT_ENV,
                FASTER_WHISPER_AUTO_DOWNLOAD_ENV,
            )
        )

    alias = _normalized_faster_whisper_alias(value)
    repo_id = FASTER_WHISPER_MODEL_REGISTRY.get(alias)
    if repo_id is None:
        allowed = ", ".join(FASTER_WHISPER_MODEL_REGISTRY)
        raise TranscriptionEngineError(
            "Automatic faster-whisper download only accepts reviewed aliases: %s. "
            "Requested '%s'. Use a local absolute model directory for any other model."
            % (allowed, value)
        )
    return repo_id


def resolve_kroko_model(model, download_root=None, options=None):
    """Resolve a Kroko .data model against its dedicated mounted root.

    Pro runtime images are identified explicitly by ``VOICESTT_KROKO_VARIANT``
    (or ``runtime_variant`` in engine options). Missing Pro/private model data
    is never auto-downloaded: the caller receives an actionable provisioning
    error before the Kroko backend's download path is reached.
    """

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

    runtime_variant = str(
        options.get("runtime_variant") or os.getenv(KROKO_VARIANT_ENV) or "free"
    ).strip().lower()
    locations = ", ".join(checked) if checked else str(path)
    if runtime_variant == "pro":
        raise TranscriptionEngineError(
            "Kroko Pro runtime is installed, but the Pro/private model file '%s' "
            "was not found. Pro models are never downloaded automatically. "
            "Provision the licensed .data model locally, set %s to its model "
            "directory (or pass engine_options['model_path']), and provide the "
            "runtime license/API key through KROKO_API_KEY or the documented "
            "Kroko key option. Checked: %s. Kroko: %s"
            % (path.name, KROKO_ROOT_ENV, locations, KROKO_HOME_URL)
        )

    if offline_models_enabled(options):
        raise TranscriptionEngineError(
            "Offline model mode is enabled and Kroko model "
            f"'{path.name}' was not found. Checked: {locations}. Set "
            f"{KROKO_ROOT_ENV} to the mounted Kroko model root or pass an "
            "absolute .data file."
        )
    return str(path)
