"""AP-SRV-060 wake detection domain: raw candidates versus accepted detections.

``wakeword_index`` was never a domain boundary - it was a list position. This
module introduces the two distinct concepts the frozen contract needs:

``RawWakeCandidate``
    What a detector *observed* in one audio chunk: a canonical wake-word id, a
    raw score, where in the stream it happened and which detector generation
    produced it. Raw candidates are diagnostics. They are never a domain event.

``AcceptedWakeDetection``
    What the system *decided*: one canonical wake word, its score, the
    ``activationId`` that the very same hit opened, and the audio boundary that
    hit established. Exactly one of these exists per accepted utterance.

:class:`WakeDetectionEvaluator` is detector hygiene only - threshold, the
stable multi-model rule, duplicate suppression and re-arm. It holds no
activation state machine: whether a candidate may become an activation is
decided by the wake admission coordinator, which asks the source-neutral
``ActivationController``.

Re-arm window
-------------

The window in which one utterance can keep producing raw candidates is not a
guess: OpenWakeWord streams one embedding frame per 1280 samples (80 ms at
16 kHz) and the embedding model itself looks at 76 melspectrogram frames
(760 ms). A classifier with ``N`` input frames therefore still sees the same
utterance for ``(N - 1) * 80 + 760`` milliseconds. The evaluator derives its
mandatory de-duplication window from the *measured* frame count of the models
actually selected, and ``wakeWord.cooldownMs`` is an operator addition on top
of that measurement - not a replacement for it.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence


#: One OpenWakeWord embedding frame advances the stream by 1280 samples.
EMBEDDING_FRAME_STEP_MS = 80.0

#: The embedding model consumes 76 melspectrogram frames at a 10 ms hop.
EMBEDDING_WINDOW_MS = 760.0

DEFAULT_SAMPLE_RATE = 16000


def receptive_field_ms(input_frames: Any) -> float:
    """The audio span one classifier with ``input_frames`` frames still sees."""
    try:
        frames = int(input_frames)
    except (TypeError, ValueError):
        return EMBEDDING_WINDOW_MS
    if frames < 1:
        return EMBEDDING_WINDOW_MS
    return (frames - 1) * EMBEDDING_FRAME_STEP_MS + EMBEDDING_WINDOW_MS


def selection_receptive_field_ms(input_frames_by_model: Mapping[str, Any]) -> float:
    """The widest measured receptive field of one selected model set."""
    values = [receptive_field_ms(value) for value in (input_frames_by_model or {}).values()]
    return max(values) if values else EMBEDDING_WINDOW_MS


@dataclass(frozen=True)
class RawWakeCandidate:
    """One observed detector hit. Diagnostics only - never a domain event."""

    canonical_wake_word_id: str
    raw_score: float
    frame_index: int
    sample_position: int
    detector_generation: int
    model_key: Optional[str] = None

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "wakeWordId": self.canonical_wake_word_id,
            "rawScore": float(self.raw_score),
            "frameIndex": int(self.frame_index),
            "samplePosition": int(self.sample_position),
            "detectorGeneration": int(self.detector_generation),
            "modelKey": self.model_key,
        }


@dataclass(frozen=True)
class AcceptedWakeDetection:
    """One accepted wake detection - the only wake fact the domain publishes."""

    canonical_wake_word_id: str
    score: float
    activation_id: str
    boundary: Any = None
    detector_generation: int = 0

    def event_fields(self) -> Dict[str, Any]:
        """The ``wakeword.detected`` payload fields owned by this module."""
        return {
            "wakeWordId": self.canonical_wake_word_id,
            "score": float(self.score),
            "activationId": self.activation_id,
        }


def select_candidate(
    candidates: Iterable[RawWakeCandidate], threshold: float
) -> Optional[RawWakeCandidate]:
    """The stable multi-model rule.

    The highest valid score wins. On an *exact* tie the lexicographically
    smallest canonical id wins - a documented, deterministic rule, so neither
    dictionary order, model load order nor a file name can decide which wake
    word an utterance was.
    """
    best: Optional[RawWakeCandidate] = None
    for candidate in candidates or ():
        if candidate is None:
            continue
        if float(candidate.raw_score) < float(threshold):
            continue
        if best is None:
            best = candidate
            continue
        if float(candidate.raw_score) > float(best.raw_score):
            best = candidate
        elif (
            float(candidate.raw_score) == float(best.raw_score)
            and candidate.canonical_wake_word_id < best.canonical_wake_word_id
        ):
            best = candidate
    return best


class WakeDetectionEvaluator:
    """Detector hygiene for one session: threshold, tie rule, latch, re-arm.

    This class deliberately knows nothing about activations. It answers one
    question - "may this observation be offered to the admission right now?" -
    and remembers the answer until the admission tells it otherwise.
    """

    def __init__(
        self,
        *,
        threshold: float,
        rearm_ms: float = EMBEDDING_WINDOW_MS,
        cooldown_ms: float = 0.0,
        clock=None,
    ):
        self._lock = threading.RLock()
        self._threshold = float(threshold)
        self._rearm_ms = max(0.0, float(rearm_ms))
        self._cooldown_ms = max(0.0, float(cooldown_ms))
        self._clock = clock or time.monotonic
        self._generation = 0
        self._latched_activation_id: Optional[str] = None
        self._blocked_until: Optional[float] = None
        self._last_candidate: Optional[RawWakeCandidate] = None

    # -- configuration -------------------------------------------------------

    @property
    def threshold(self) -> float:
        return self._threshold

    @property
    def rearm_ms(self) -> float:
        """Measured artifact window plus the configured operator cooldown."""
        return self._rearm_ms + self._cooldown_ms

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    @property
    def latched(self) -> bool:
        with self._lock:
            return self._latched_activation_id is not None

    @property
    def latched_activation_id(self) -> Optional[str]:
        with self._lock:
            return self._latched_activation_id

    def new_generation(self) -> int:
        """Starts a new detector generation; older callbacks become stale."""
        with self._lock:
            self._generation += 1
            self._latched_activation_id = None
            self._blocked_until = None
            self._last_candidate = None
            return self._generation

    # -- evaluation ----------------------------------------------------------

    def offer(
        self, candidates: Sequence[RawWakeCandidate], *, now: Optional[float] = None
    ) -> Optional[RawWakeCandidate]:
        """The candidate that may be offered to the admission, if any.

        Returns ``None`` while the detection is latched, while the re-arm
        window of a previous hit is still open, or when the observation belongs
        to a stale detector generation.
        """
        with self._lock:
            timestamp = self._clock() if now is None else float(now)
            if self._latched_activation_id is not None:
                return None
            if self._blocked_until is not None and timestamp < self._blocked_until:
                return None
            fresh = [
                candidate for candidate in candidates or ()
                if candidate is not None
                and candidate.detector_generation == self._generation
            ]
            best = select_candidate(fresh, self._threshold)
            if best is not None:
                self._last_candidate = best
            return best

    def accept(
        self,
        candidate: RawWakeCandidate,
        *,
        activation_id: str,
        boundary: Any = None,
        now: Optional[float] = None,
    ) -> AcceptedWakeDetection:
        """Latches the detection onto one accepted activation."""
        with self._lock:
            timestamp = self._clock() if now is None else float(now)
            self._latched_activation_id = str(activation_id)
            self._blocked_until = timestamp + self.rearm_ms / 1000.0
            return AcceptedWakeDetection(
                canonical_wake_word_id=candidate.canonical_wake_word_id,
                score=float(candidate.raw_score),
                activation_id=str(activation_id),
                boundary=boundary,
                detector_generation=candidate.detector_generation,
            )

    def refuse(self, candidate: RawWakeCandidate, *, now: Optional[float] = None) -> None:
        """A refused admission arms the re-arm window but never the latch.

        A rejected candidate is not a fachliches Ereignis and does not open an
        activation, but the same utterance must not be re-offered chunk after
        chunk either. Re-arm is detector hygiene, not a second activation state
        machine.
        """
        with self._lock:
            timestamp = self._clock() if now is None else float(now)
            self._blocked_until = timestamp + self.rearm_ms / 1000.0

    def release_latch(self, *, activation_id: Optional[str] = None) -> bool:
        """Releases the latch at the safe input close of the same activation.

        Not at VAD end, not at segment end, not when a final inference starts
        or ends, and not when a cooldown expires.
        """
        with self._lock:
            if self._latched_activation_id is None:
                return False
            if activation_id is not None and str(activation_id) != self._latched_activation_id:
                return False
            self._latched_activation_id = None
            return True

    # -- diagnostics ---------------------------------------------------------

    def diagnostics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "threshold": self._threshold,
                "rearmMs": self._rearm_ms,
                "cooldownMs": self._cooldown_ms,
                "effectiveRearmMs": self.rearm_ms,
                "generation": self._generation,
                "latchedActivationId": self._latched_activation_id,
                "lastCandidate": (
                    self._last_candidate.diagnostics()
                    if self._last_candidate is not None
                    else None
                ),
            }
