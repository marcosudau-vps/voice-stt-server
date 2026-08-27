"""
Internal wake-word backend setup and runtime helpers.

Two paths live here side by side until AP-SRV-070 retires the legacy one:

* the **v2 path** takes a
  :class:`~VoiceSTT.core.wakeword_catalog.WakeWordSelection` from the one
  catalog authority, hands OpenWakeWord *exactly* the selected classifiers and
  the shared pipeline models, and reports structured
  :class:`~VoiceSTT.core.wake_detection.RawWakeCandidate` objects carrying the
  canonical wake-word id;
* the **legacy path** keeps resolving comma separated names through
  :class:`~VoiceSTT.core.openwakeword_catalog.OpenWakeWordCatalog` and still
  answers with the historical integer index.

The v2 path never derives an id from a file name: OpenWakeWord names a loaded
model by its file stem, and the catalog owns the stem-to-canonical-id map.
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
from .wake_detection import RawWakeCandidate

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
    wake_word_selection=None,
):
    """
    Configures the selected wake-word backend on the recorder.

    ``wake_word_selection`` is the AP-SRV-060 v2 path: an already admitted
    :class:`~VoiceSTT.core.wakeword_catalog.WakeWordSelection`. When it is
    given, *only* its classifiers are handed to OpenWakeWord - no catalog
    scan, no default fallback, no extra model.
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
            if wake_word_selection is not None:
                # AP-SRV-060 selected-only initialisation: exactly the admitted
                # classifiers plus the shared pipeline models the catalog owns.
                loader_kwargs = wake_word_selection.loader_kwargs()
                model_paths = list(loader_kwargs["wakeword_models"])
                feature_paths = {
                    key: value for key, value in loader_kwargs.items()
                    if key != "wakeword_models"
                }
            else:
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
            bind_wake_word_selection(recorder, wake_word_selection)

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


def bind_wake_word_selection(recorder, selection):
    """Publishes the admitted selection's identity map onto the recorder.

    The canonical ids and the measured classifier receptive fields come from
    the catalog and the *real* loaded backend; nothing here is derived from a
    file name or guessed.
    """
    recorder.wake_word_selection = selection
    recorder.wake_word_model_key_to_id = (
        dict(selection.model_key_to_id) if selection is not None else {}
    )
    recorder.wake_word_input_frames = {}
    model = getattr(recorder, "owwModel", None)
    inputs = getattr(model, "model_inputs", None)
    if isinstance(inputs, dict):
        recorder.wake_word_input_frames = {
            key: value for key, value in inputs.items()
        }
    return recorder.wake_word_model_key_to_id


def _canonical_wake_word_id(recorder, model_key):
    """The canonical id of one loaded OpenWakeWord model key.

    Returns ``None`` when the key is not part of the admitted selection, so a
    stray model can never publish a domain id.
    """
    mapping = getattr(recorder, "wake_word_model_key_to_id", None) or {}
    return mapping.get(model_key)


def collect_wake_candidates(recorder, data, *, sample_position=0, frame_index=0,
                            detector_generation=0):
    """Every raw OpenWakeWord observation of one audio chunk.

    Raw candidates are diagnostics. This function applies **no** threshold, no
    latch and no de-duplication; those belong to
    :class:`~VoiceSTT.core.wake_detection.WakeDetectionEvaluator`.
    """
    if recorder.wakeword_backend not in OPENWAKEWORD_BACKENDS:
        return []
    pcm = np.frombuffer(data, dtype=np.int16)
    recorder.owwModel.predict(pcm)
    candidates = []
    buffer = getattr(recorder.owwModel, "prediction_buffer", {}) or {}
    end_position = int(sample_position) + int(pcm.shape[0])
    for model_key in buffer.keys():
        scores = list(buffer[model_key])
        if not scores:
            continue
        identifier = _canonical_wake_word_id(recorder, model_key)
        if identifier is None:
            # Not part of the admitted selection - diagnostics only, never a
            # candidate, so an unexpected model cannot open an activation.
            if recorder.debug_mode:
                logger.info("wake words: ignoring unmapped model key %s", model_key)
            continue
        candidates.append(RawWakeCandidate(
            canonical_wake_word_id=identifier,
            raw_score=float(scores[-1]),
            frame_index=int(frame_index),
            sample_position=end_position,
            detector_generation=int(detector_generation),
            model_key=model_key,
        ))
    if recorder.debug_mode and candidates:
        logger.info(
            "wake words raw candidates: %s",
            [candidate.diagnostics() for candidate in candidates],
        )
    return candidates


def process_wakeword(recorder, data):
    """
    Processes one audio chunk through the configured wake-word backend.

    Legacy integer-index API. The v2 path uses
    :func:`collect_wake_candidates` instead and never sees an index.
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
