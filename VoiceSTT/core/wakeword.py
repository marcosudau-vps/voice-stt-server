"""
Internal wake-word backend setup and runtime helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
import logging
from pathlib import Path
import struct
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from .openwakeword_catalog import (
    OPENWAKEWORD_MODEL_ROOT_ENV,
    OpenWakeWordCatalog,
    _wakeword_id,
)

logger = logging.getLogger("voicestt")

PORCUPINE_WAKEWORD_BACKENDS = {"pvp", "pvporcupine", "porcupine"}
OPENWAKEWORD_BACKENDS = {
    "oww",
    "openwakeword",
    "openwakewords",
    "open_wakeword",
    "open_wakewords",
}

DEFAULT_WAKE_WORDS_SENSITIVITY = 0.5


@dataclass(frozen=True)
class WakeWordDetection:
    """Immutable domain representation of an accepted wake-word detection."""

    wake_word_id: str
    score: float
    detected_at: float = 0.0


def _resolve_openwakeword_paths(
    model_paths: Optional[str],
    wake_words: Union[str, Sequence[str], None],
    inference_framework: str = "onnx",
    disable_provider: Optional[Any] = None,
) -> Tuple[List[str], Dict[str, str]]:
    """Resolve classifier and feature models without performing network I/O."""

    explicit = [
        Path(value.strip()).expanduser()
        for value in (model_paths or "").split(",")
        if value.strip()
    ]
    catalog = OpenWakeWordCatalog(
        configured_paths=explicit,
        disable_provider=disable_provider,
    )
    explicit_classifiers = [
        path for path in explicit
        if path.suffix.lower() in {".onnx", ".tflite"}
    ]
    if explicit_classifiers:
        classifiers = explicit_classifiers
    else:
        resolved, missing, reasons = catalog.resolve_detailed(
            wake_words,
            preferred_framework=inference_framework,
        )
        if missing:
            detail = ", ".join(f"{m} ({reasons.get(m, 'unavailable')})" for m in missing)
            raise FileNotFoundError(
                "OpenWakeWord model IDs are missing or unavailable in offline mode: "
                + detail
            )
        classifiers = [Path(entry["path"]) for entry in resolved]

    missing = [str(path) for path in classifiers if not path.is_file()]
    if not classifiers or missing:
        detail = ", ".join(missing) if missing else str(catalog.model_root or "<unset>")
        raise FileNotFoundError(
            "OpenWakeWord model files are missing in offline mode: " + detail + ". Set "
            + OPENWAKEWORD_MODEL_ROOT_ENV + " or pass openwakeword_model_paths."
        )
    feature_paths = catalog.pipeline_paths(
        inference_framework,
        classifier_path=classifiers[0],
    )
    if "melspec_model_path" not in feature_paths or "embedding_model_path" not in feature_paths:
        raise FileNotFoundError(
            "OpenWakeWord feature models are missing in offline mode for "
            + str(Path(classifiers[0]).parent)
        )
    return [str(path.resolve()) for path in classifiers], feature_paths


def _normalize_wakeword_backend(wakeword_backend: Optional[str], wake_words: Any) -> str:
    """
    Normalizes the configured wake-word backend.
    """
    backend = (wakeword_backend or "").strip().lower().replace("-", "_")
    if not backend and wake_words:
        return "pvporcupine"
    return backend


def _load_porcupine_module(importer=None):
    """
    Loads the optional Porcupine wake-word module.
    """
    if importer is None:
        importer = import_module
    try:
        return importer("pvporcupine")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Porcupine wake word detection requires the optional "
            "'pvporcupine' package. Install it with "
            "'pip install \"VoiceSTT[porcupine]\"'."
        ) from exc


def _load_openwakeword_modules(importer=None):
    """
    Loads optional OpenWakeWord modules.
    """
    if importer is None:
        importer = import_module
    try:
        openwakeword_module = importer("openwakeword")
        model_module = importer("openwakeword.model")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "OpenWakeWord wake word detection requires the optional "
            "'openwakeword' package. Install it with "
            "'pip install \"VoiceSTT[openwakeword]\"'."
        ) from exc
    return openwakeword_module, model_module.Model


def setup_wakeword_detection(
    recorder,
    normalized_wakeword_backend,
    wake_words,
    wake_words_sensitivity,
    openwakeword_model_paths,
    openwakeword_inference_framework,
    load_porcupine_module=None,
    load_openwakeword_modules=None,
    disable_provider=None,
):
    """
    Configures the selected wake-word backend on the recorder with selected-only loading.
    """
    if not (
        recorder.use_wake_words
        or normalized_wakeword_backend in PORCUPINE_WAKEWORD_BACKENDS
    ):
        return

    recorder.wakeword_backend = normalized_wakeword_backend

    if isinstance(wake_words, (list, tuple)):
        raw_words = [str(w).strip() for w in wake_words if str(w).strip()]
    elif wake_words:
        raw_words = [
            word.strip() for word in str(wake_words).split(',')
            if word.strip()
        ]
    else:
        raw_words = []

    recorder.wake_words_list = raw_words

    # Sensitivity validation: Frozen Range 0.0 - 1.0
    if wake_words_sensitivity is not None:
        try:
            sens_val = float(wake_words_sensitivity)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"wake_words_sensitivity must be float between 0.0 and 1.0, got: {wake_words_sensitivity}") from exc
        if sens_val < 0.0 or sens_val > 1.0:
            raise ValueError(f"wake_words_sensitivity must be between 0.0 and 1.0, got {sens_val}")
        recorder.wake_words_sensitivity = sens_val
    else:
        recorder.wake_words_sensitivity = DEFAULT_WAKE_WORDS_SENSITIVITY

    recorder.wake_words_sensitivities = [
        float(recorder.wake_words_sensitivity)
        for _ in range(len(recorder.wake_words_list))
    ]
    recorder.last_wakeword_detection = None

    if recorder.wakeword_backend in PORCUPINE_WAKEWORD_BACKENDS:
        if not recorder.wake_words_list:
            raise ValueError(
                "Porcupine wake word detection requires wake_words. "
                "Pass a comma-separated Porcupine keyword list, or use "
                "wakeword_backend='openwakeword' for OpenWakeWord models."
            )

        try:
            if load_porcupine_module is None:
                load_porcupine_module = _load_porcupine_module
            pvporcupine = load_porcupine_module()
            recorder.porcupine = pvporcupine.create(
                keywords=recorder.wake_words_list,
                sensitivities=recorder.wake_words_sensitivities
            )
            recorder.buffer_size = recorder.porcupine.frame_length
            recorder.sample_rate = recorder.porcupine.sample_rate

        except Exception as e:
            logger.exception(
                "Error initializing porcupine "
                f"wake word detection engine: {e}. "
                f"Wakewords: {recorder.wake_words_list}."
            )
            raise

        logger.debug(
            "Porcupine wake word detection engine initialized successfully"
        )

    elif recorder.wakeword_backend in OPENWAKEWORD_BACKENDS:
        try:
            if load_openwakeword_modules is None:
                load_openwakeword_modules = _load_openwakeword_modules
            _openwakeword, Model = load_openwakeword_modules()
            model_paths, feature_paths = _resolve_openwakeword_paths(
                openwakeword_model_paths,
                recorder.wake_words_list or wake_words,
                openwakeword_inference_framework,
                disable_provider=disable_provider,
            )
            recorder.owwModel = Model(
                wakeword_models=model_paths,
                inference_framework=openwakeword_inference_framework,
                device="cpu",
                **feature_paths,
            )
            logger.info("Successfully loaded offline wakeword model(s): %s", model_paths)

            recorder.oww_n_models = len(recorder.owwModel.models.keys())
            if not recorder.oww_n_models:
                logger.error(
                    "No wake word models loaded."
                )

            for model_key in recorder.owwModel.models.keys():
                logger.info(
                    "Successfully loaded openwakeword model: "
                    f"{model_key}"
                )

        except Exception as e:
            logger.exception(
                "Error initializing openwakeword "
                f"wake word detection engine: {e}"
            )
            raise

        logger.debug(
            "Open wake word detection engine initialized successfully"
        )

    else:
        raise ValueError(
            f"Wakeword engine {recorder.wakeword_backend} unknown or unsupported. "
            "Please specify one of: pvporcupine, openwakeword."
        )


def process_wakeword(recorder, data: bytes) -> int:
    """
    Processes one audio chunk through the configured wake-word backend.
    Evaluates candidate models deterministically and attaches domain WakeWordDetection.
    """
    if recorder.wakeword_backend in PORCUPINE_WAKEWORD_BACKENDS:
        pcm = struct.unpack_from(
            "h" * recorder.buffer_size,
            data
        )
        porcupine_index = recorder.porcupine.process(pcm)
        if porcupine_index >= 0:
            word_id = (
                recorder.wake_words_list[porcupine_index]
                if porcupine_index < len(recorder.wake_words_list)
                else f"keyword_{porcupine_index}"
            )
            detection = WakeWordDetection(
                wake_word_id=word_id,
                score=1.0,
                detected_at=time.time(),
            )
            recorder.last_wakeword_detection = detection
            if recorder.debug_mode:
                logger.info(f"wake words porcupine match: {word_id} (index {porcupine_index})")
        else:
            recorder.last_wakeword_detection = None
        return porcupine_index

    elif recorder.wakeword_backend in OPENWAKEWORD_BACKENDS:
        pcm = np.frombuffer(data, dtype=np.int16)
        recorder.owwModel.predict(pcm)

        candidates: List[Tuple[float, str, int]] = []
        models_keys = list(recorder.owwModel.prediction_buffer.keys())

        if models_keys:
            for idx, mdl in enumerate(models_keys):
                scores = list(recorder.owwModel.prediction_buffer[mdl])
                if not scores:
                    continue
                score = float(scores[-1])
                if score >= recorder.wake_words_sensitivity:
                    canonical_id = _wakeword_id(Path(mdl).stem) if ("." in mdl or "/" in mdl or "\\" in mdl) else mdl
                    candidates.append((score, canonical_id, idx))

            if candidates:
                # Deterministic selection: highest score first; tie break: alphabetical by canonical ID
                candidates.sort(key=lambda x: (-x[0], x[1].lower(), x[2]))
                best_score, best_id, best_index = candidates[0]
                detection = WakeWordDetection(
                    wake_word_id=best_id,
                    score=best_score,
                    detected_at=time.time(),
                )
                recorder.last_wakeword_detection = detection
                if recorder.debug_mode:
                    logger.info(f"wake words oww match: {best_id}, score: {best_score:.4f}, index: {best_index}")
                return best_index
            else:
                recorder.last_wakeword_detection = None
                if recorder.debug_mode:
                    logger.info("wake words oww_index: -1")
                return -1
        else:
            recorder.last_wakeword_detection = None
            if recorder.debug_mode:
                logger.info("wake words oww_index: -1")
            return -1

    recorder.last_wakeword_detection = None
    if recorder.debug_mode:
        logger.info("wake words no match")

    return -1
