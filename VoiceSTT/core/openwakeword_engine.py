"""AP-SRV-060 C3 thin OpenWakeWord adapter - one engine, one backend.

``openwakeword.Model`` stays the inference implementation. This module does not
fork, copy or reimplement feature extraction, the ONNX loader, the
TFLite/LiteRT loader, Speex noise suppression, the Silero VAD gate or the
neural prediction. It owns exactly the three things upstream cannot know:

which models, in which backend
    a live engine holds **one** upstream model instance built from the admitted
    :class:`~VoiceSTT.core.wakeword_catalog.WakeWordSelection`: exactly the
    selected classifiers, exactly one common inference framework, plus the
    shared pipeline models the catalog owns. There is no per-model mixture and
    no unselected model in a running session;
what a prediction frame is
    upstream buffers audio internally: it produces one new prediction every
    1280 samples (80 ms at 16 kHz) and re-appends the previous score for a
    shorter chunk. Recorder chunks of 20 ms or 40 ms must therefore *not*
    advance the wake-hit counter, and a repeated/cached score must never be
    counted twice. The engine accounts for the submitted samples itself and
    emits one :class:`PredictionFrame` per genuinely new prediction;
detector-only gain
    ``wakeWord.detectorGain`` is applied to a **copy** of the PCM that only the
    wake inference sees, with saturating int16 clipping. The original buffer -
    the one that reaches the recording, the transcription and the audio history
    - is never modified.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

import numpy as np


logger = logging.getLogger("voicestt")

#: OpenWakeWord advances one prediction frame per 1280 samples.
PREDICTION_FRAME_SAMPLES = 1280

DEFAULT_SAMPLE_RATE = 16000

INT16_MIN = -32768
INT16_MAX = 32767


@dataclass(frozen=True)
class PredictionFrame:
    """One genuinely new OpenWakeWord prediction, not one recorder chunk."""

    index: int
    end_sample: int
    scores: Mapping[str, float]

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "index": int(self.index),
            "endSample": int(self.end_sample),
            "scores": {key: float(value) for key, value in self.scores.items()},
        }


def apply_detector_gain(pcm: np.ndarray, gain: Any) -> np.ndarray:
    """A gained int16 **copy**, saturating instead of wrapping.

    The multiplication runs in float32 and is clipped to the int16 range before
    the cast, so a loud sample plus a large gain becomes ``32767`` rather than
    wrapping around into a negative value.
    """
    try:
        factor = float(gain)
    except (TypeError, ValueError):
        factor = 1.0
    if factor == 1.0:
        return pcm.copy()
    scaled = pcm.astype(np.float32) * factor
    np.clip(scaled, INT16_MIN, INT16_MAX, out=scaled)
    return scaled.astype(np.int16)


def _default_model_factory(**kwargs):
    """The real upstream constructor. Imported lazily so tests stay offline."""
    from openwakeword.model import Model

    return Model(**kwargs)


class OpenWakeWordEngine:
    """One live wake engine: one upstream model, one backend, selected only."""

    def __init__(
        self,
        *,
        selection,
        model_factory=None,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        detector_gain: float = 1.0,
        noise_suppression_enabled: bool = False,
        vad_threshold: float = 0.0,
        device: str = "cpu",
    ):
        self._lock = threading.RLock()
        self._selection = selection
        self._sample_rate = int(sample_rate or DEFAULT_SAMPLE_RATE)
        self._detector_gain = float(detector_gain)
        self._noise_suppression_enabled = bool(noise_suppression_enabled)
        self._vad_threshold = float(vad_threshold)
        self._backend = str(getattr(selection, "backend", "") or "")
        self._model_key_to_id = dict(
            getattr(selection, "model_key_to_id", None) or {}
        )
        loader_kwargs = dict(selection.loader_kwargs())
        loader_kwargs.setdefault("inference_framework", self._backend)
        loader_kwargs["enable_speex_noise_suppression"] = (
            self._noise_suppression_enabled
        )
        loader_kwargs["vad_threshold"] = self._vad_threshold
        if device:
            loader_kwargs.setdefault("device", device)
        self._loader_kwargs = loader_kwargs
        factory = model_factory or _default_model_factory
        self._model = factory(**loader_kwargs)
        self._pending_samples = 0
        self._total_samples = 0
        self._frame_index = 0
        self._closed = False

    # -- identity ------------------------------------------------------------

    @property
    def model(self):
        """The one upstream ``openwakeword.Model`` instance."""
        return self._model

    @property
    def backend(self) -> str:
        """The one common inference backend of this engine."""
        return self._backend

    @property
    def selection(self):
        return self._selection

    @property
    def frame_index(self) -> int:
        """How many genuinely new prediction frames this engine emitted."""
        with self._lock:
            return self._frame_index

    @property
    def sample_position(self) -> int:
        """Absolute stream position of all audio submitted so far."""
        with self._lock:
            return self._total_samples

    @property
    def input_frames(self) -> Dict[str, Any]:
        """Measured classifier input frame counts of the loaded models."""
        inputs = getattr(self._model, "model_inputs", None)
        return dict(inputs) if isinstance(inputs, dict) else {}

    # -- inference -----------------------------------------------------------

    def process(self, data, *, gain: Optional[float] = None) -> Tuple[PredictionFrame, ...]:
        """Submits one recorder chunk and returns the *new* prediction frames.

        ``data`` is never modified: the gain runs on a copy that only the wake
        inference sees.
        """
        if self._closed:
            return ()
        pcm = (
            data if isinstance(data, np.ndarray)
            else np.frombuffer(data, dtype=np.int16)
        )
        sample_count = int(pcm.shape[0])
        if sample_count <= 0:
            return ()
        factor = self._detector_gain if gain is None else gain
        payload = apply_detector_gain(pcm, factor)

        with self._lock:
            try:
                self._model.predict(payload)
            except Exception:  # noqa: BLE001 - one bad chunk is not fatal
                logger.exception("OpenWakeWord-Inferenz ist fehlgeschlagen")
                return ()
            self._total_samples += sample_count
            self._pending_samples += sample_count
            new_frames = self._pending_samples // PREDICTION_FRAME_SAMPLES
            if new_frames <= 0:
                # A short chunk: upstream re-appended a cached score. It is not
                # a new prediction frame and must never be counted.
                return ()
            self._pending_samples -= new_frames * PREDICTION_FRAME_SAMPLES
            scores_by_id = self._tail_scores(new_frames)
            first_frame_end = (
                self._total_samples - self._pending_samples
                - (new_frames - 1) * PREDICTION_FRAME_SAMPLES
            )
            frames = []
            for offset in range(new_frames):
                index = self._frame_index + offset
                end_sample = first_frame_end + offset * PREDICTION_FRAME_SAMPLES
                frames.append(PredictionFrame(
                    index=index,
                    end_sample=end_sample,
                    scores={
                        wake_word_id: values[offset]
                        for wake_word_id, values in scores_by_id.items()
                    },
                ))
            self._frame_index += new_frames
            return tuple(frames)

    def _tail_scores(self, new_frames: int) -> Dict[str, Tuple[float, ...]]:
        """The last ``new_frames`` scores of every *selected* model.

        A model key that is not part of the admitted selection is diagnostics
        only: it can never contribute a score, so a stray model in the upstream
        buffer cannot open an activation.
        """
        buffer = getattr(self._model, "prediction_buffer", None) or {}
        scores: Dict[str, Tuple[float, ...]] = {}
        for model_key, values in buffer.items():
            wake_word_id = self._model_key_to_id.get(model_key)
            if wake_word_id is None:
                continue
            series = list(values)
            if not series:
                continue
            tail = series[-new_frames:]
            if len(tail) < new_frames:
                tail = [tail[0]] * (new_frames - len(tail)) + tail
            scores[wake_word_id] = tuple(float(value) for value in tail)
        return scores

    # -- lifecycle -----------------------------------------------------------

    def reset(self) -> None:
        """Drops the buffered audio accounting and the upstream score buffer."""
        with self._lock:
            self._pending_samples = 0
            reset = getattr(self._model, "reset", None)
            if callable(reset):
                try:
                    reset()
                except Exception:  # noqa: BLE001 - a reset must not be fatal
                    logger.exception("OpenWakeWord-Reset ist fehlgeschlagen")

    def close(self) -> None:
        """Releases the engine. The upstream model is dropped, never reused."""
        with self._lock:
            self._closed = True
            self._model = None

    # -- diagnostics ---------------------------------------------------------

    def diagnostics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "backend": self._backend,
                "wakeWordIds": list(getattr(self._selection, "wake_word_ids", ())),
                "frameIndex": self._frame_index,
                "pendingSamples": self._pending_samples,
                "totalSamples": self._total_samples,
                "detectorGain": self._detector_gain,
                "noiseSuppressionEnabled": self._noise_suppression_enabled,
                "vadThreshold": self._vad_threshold,
                "closed": self._closed,
            }
