"""
Internal wake-word backend setup and runtime helpers.
"""

from importlib import import_module
import logging
import struct
from pathlib import Path

import numpy as np

from .openwakeword_catalog import (
    OPENWAKEWORD_MODEL_ROOT_ENV,
    OpenWakeWordCatalog,
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
def _resolve_openwakeword_paths(
    model_paths,
    wake_words,
    inference_framework="onnx",
):
    """Resolve classifier and feature models without performing network I/O."""

    explicit = [Path(value.strip()).expanduser() for value in (model_paths or "").split(",") if value.strip()]
    catalog = OpenWakeWordCatalog(configured_paths=explicit)
    explicit_classifiers = [
        path for path in explicit
        if path.suffix.lower() in {".onnx", ".tflite"}
    ]
    if explicit_classifiers:
        classifiers = explicit_classifiers
    else:
        resolved, missing = catalog.resolve(
            wake_words,
            preferred_framework=inference_framework,
        )
        if missing:
            raise FileNotFoundError(
                "OpenWakeWord model IDs are missing in offline mode: "
                + ", ".join(missing)
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
    if len(feature_paths) != 2:
        raise FileNotFoundError(
            "OpenWakeWord feature models are missing in offline mode for "
            + str(Path(classifiers[0]).parent)
        )
    return [str(path.resolve()) for path in classifiers], feature_paths


def _normalize_wakeword_backend(wakeword_backend, wake_words):
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
):
    """
    Configures the selected wake-word backend on the recorder.
    """
    if not (
        recorder.use_wake_words
        or normalized_wakeword_backend in PORCUPINE_WAKEWORD_BACKENDS
    ):
        return

    recorder.wakeword_backend = normalized_wakeword_backend

    recorder.wake_words_list = [
        word.strip() for word in wake_words.lower().split(',')
        if word.strip()
    ] if wake_words else []
    recorder.wake_words_sensitivity = wake_words_sensitivity
    recorder.wake_words_sensitivities = [
        float(wake_words_sensitivity)
        for _ in range(len(recorder.wake_words_list))
    ]

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
                wake_words,
                openwakeword_inference_framework,
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


def process_wakeword(recorder, data):
    """
    Processes one audio chunk through the configured wake-word backend.
    """
    if recorder.wakeword_backend in PORCUPINE_WAKEWORD_BACKENDS:
        pcm = struct.unpack_from(
            "h" * recorder.buffer_size,
            data
        )
        porcupine_index = recorder.porcupine.process(pcm)
        if recorder.debug_mode:
            logger.info(f"wake words porcupine_index: {porcupine_index}")
        return porcupine_index

    elif recorder.wakeword_backend in OPENWAKEWORD_BACKENDS:
        pcm = np.frombuffer(data, dtype=np.int16)
        prediction = recorder.owwModel.predict(pcm)
        max_score = -1
        max_index = -1
        wake_words_in_prediction = len(recorder.owwModel.prediction_buffer.keys())
        recorder.wake_words_sensitivities
        if wake_words_in_prediction:
            for idx, mdl in enumerate(recorder.owwModel.prediction_buffer.keys()):
                scores = list(recorder.owwModel.prediction_buffer[mdl])
                if scores[-1] >= recorder.wake_words_sensitivity and scores[-1] > max_score:
                    max_score = scores[-1]
                    max_index = idx
            if recorder.debug_mode:
                logger.info(f"wake words oww max_index, max_score: {max_index} {max_score}")
            return max_index
        else:
            if recorder.debug_mode:
                logger.info(f"wake words oww_index: -1")
            return -1

    if recorder.debug_mode:
        logger.info("wake words no match")

    return -1
