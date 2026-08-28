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

Two separate windows (AP-SRV-060 C2 / Root F6)
---------------------------------------------

De-duplication and cooldown are deliberately *not* the same thing:

``de-duplication window``
    An implicit, purely technical guard against re-offering the **same
    acoustic hit**. Its length is the measured receptive field of the selected
    classifiers: OpenWakeWord streams one embedding frame per 1280 samples
    (80 ms at 16 kHz) and the embedding model looks at 76 melspectrogram
    frames (760 ms), so a classifier with ``N`` input frames still sees the
    same utterance for ``(N - 1) * 80 + 760`` ms. This window exists only to
    stop one utterance from being offered twice; it is **cleared at the safe
    input close**, because after that close a new, clearly separate utterance
    must be admissible immediately. It must never become a hidden second
    foreground lock.

``cooldown``
    An *explicitly configured* operator value (``wakeWord.cooldownMs``). It is
    deliberate post-close semantics: it may keep blocking after the safe input
    close, because that is what an operator asked for. Its default is ``0``,
    and its calibrated value is still open (WW-18, ``EVIDENCE_BLOCKED``).

Runtime policy (Root F2)
------------------------

``wakeWord.sensitivity``, ``wakeWord.cooldownMs`` and ``wakeWord.preRollMs``
are ``next_activation`` settings of the AP-SRV-050 control plane. The evaluator
therefore does not copy them once: it reads an immutable
:class:`WakeRuntimePolicy` from a supplier and latches it for the duration of
one activation. While a detection is latched the running activation keeps the
policy it started with; as soon as the latch is released the next admission
picks up the current one. There is no second settings authority here - only a
read of the one that exists.
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
class WakeRuntimePolicy:
    """The immutable wake runtime values of one activation.

    Resolved from the AP-SRV-050 session settings authority at admission time
    and latched for the whole activation, exactly like
    :class:`~api_fastapi_server.activation.ActivationTimingPolicy` does for the
    activation timings. ``settings_revision`` records which revision the values
    came from, so a snapshot can never mix two revisions.
    """

    sensitivity: float = 0.5
    cooldown_ms: int = 0
    pre_roll_ms: int = 0
    settings_revision: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensitivity": float(self.sensitivity),
            "cooldownMs": int(self.cooldown_ms),
            "preRollMs": int(self.pre_roll_ms),
            "settingsRevision": int(self.settings_revision),
        }


def _coerce_policy(value: Any) -> WakeRuntimePolicy:
    """Accepts a policy, a mapping or ``None`` and returns a policy."""
    if isinstance(value, WakeRuntimePolicy):
        return value
    if isinstance(value, Mapping):
        return WakeRuntimePolicy(
            sensitivity=float(value.get("sensitivity", 0.5)),
            cooldown_ms=int(value.get("cooldown_ms", value.get("cooldownMs", 0))),
            pre_roll_ms=int(value.get("pre_roll_ms", value.get("preRollMs", 0))),
            settings_revision=int(
                value.get("settings_revision", value.get("settingsRevision", 0))
            ),
        )
    return WakeRuntimePolicy()


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

    It holds two independent blocking windows, see the module docstring: the
    implicit de-duplication window of one acoustic hit, and the explicitly
    configured cooldown.
    """

    def __init__(
        self,
        *,
        policy_supplier=None,
        threshold: Optional[float] = None,
        rearm_ms: float = EMBEDDING_WINDOW_MS,
        clock=None,
    ):
        if policy_supplier is None:
            constant = WakeRuntimePolicy(
                sensitivity=0.5 if threshold is None else float(threshold)
            )
            policy_supplier = lambda: constant  # noqa: E731 - one-line constant
        self._lock = threading.RLock()
        self._policy_supplier = policy_supplier
        self._rearm_ms = max(0.0, float(rearm_ms))
        self._clock = clock or time.monotonic
        self._generation = 0
        self._latched_activation_id: Optional[str] = None
        #: Implicit de-duplication of the same acoustic hit. Cleared at the
        #: safe input close - it must never outlive the activation it guarded.
        self._dedupe_until: Optional[float] = None
        #: Explicitly configured cooldown. Deliberate post-close semantics.
        self._cooldown_until: Optional[float] = None
        self._last_candidate: Optional[RawWakeCandidate] = None
        self._active_policy = _coerce_policy(self._policy_supplier())

    # -- runtime policy ------------------------------------------------------

    def _refresh_policy_locked(self) -> WakeRuntimePolicy:
        """Picks up the current settings unless an activation is running.

        This is the whole ``next_activation`` binding: a running activation
        keeps the policy it latched, and the next admission sees the patched
        values for real.
        """
        if self._latched_activation_id is None:
            try:
                self._active_policy = _coerce_policy(self._policy_supplier())
            except Exception:  # noqa: BLE001 - never break detection on a read
                pass
        return self._active_policy

    @property
    def active_policy(self) -> WakeRuntimePolicy:
        """The policy in force right now (latched while an activation runs)."""
        with self._lock:
            return self._refresh_policy_locked()

    @property
    def threshold(self) -> float:
        return self.active_policy.sensitivity

    @property
    def cooldown_ms(self) -> int:
        return self.active_policy.cooldown_ms

    @property
    def pre_roll_ms(self) -> int:
        return self.active_policy.pre_roll_ms

    @property
    def dedupe_ms(self) -> float:
        """The measured de-duplication window of one acoustic hit."""
        return self._rearm_ms

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
            self._dedupe_until = None
            self._cooldown_until = None
            self._last_candidate = None
            self._active_policy = _coerce_policy(self._policy_supplier())
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
            policy = self._refresh_policy_locked()
            for window in (self._dedupe_until, self._cooldown_until):
                if window is not None and timestamp < window:
                    return None
            fresh = [
                candidate for candidate in candidates or ()
                if candidate is not None
                and candidate.detector_generation == self._generation
            ]
            best = select_candidate(fresh, policy.sensitivity)
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
            self._arm_windows_locked(timestamp)
            return AcceptedWakeDetection(
                canonical_wake_word_id=candidate.canonical_wake_word_id,
                score=float(candidate.raw_score),
                activation_id=str(activation_id),
                boundary=boundary,
                detector_generation=candidate.detector_generation,
            )

    def _arm_windows_locked(self, timestamp: float) -> None:
        """Arms the de-duplication window and the configured cooldown."""
        policy = self._active_policy
        if self._rearm_ms > 0:
            self._dedupe_until = timestamp + self._rearm_ms / 1000.0
        if policy.cooldown_ms > 0:
            self._cooldown_until = timestamp + policy.cooldown_ms / 1000.0

    def refuse(self, candidate: RawWakeCandidate, *, now: Optional[float] = None) -> None:
        """A refused admission arms the windows but never the latch.

        A rejected candidate is not a fachliches Ereignis and does not open an
        activation, but the same utterance must not be re-offered chunk after
        chunk either. This is detector hygiene, not a second activation state
        machine.
        """
        with self._lock:
            timestamp = self._clock() if now is None else float(now)
            self._refresh_policy_locked()
            self._arm_windows_locked(timestamp)

    def release_latch(self, *, activation_id: Optional[str] = None) -> bool:
        """Releases the latch at the safe input close of the same activation.

        Not at VAD end, not at segment end, not when a final inference starts
        or ends, and not when a cooldown expires.

        Root F6: the safe input close also clears the **implicit**
        de-duplication window. That window only ever protected the one acoustic
        hit of the activation that is now closed; letting it live on would be a
        hidden second foreground lock that the activation lifecycle model does
        not have. An **explicitly configured** ``wakeWord.cooldownMs`` is not
        cleared - that one is deliberate post-close semantics.
        """
        with self._lock:
            if self._latched_activation_id is None:
                return False
            if activation_id is not None and str(activation_id) != self._latched_activation_id:
                return False
            self._latched_activation_id = None
            self._dedupe_until = None
            self._refresh_policy_locked()
            return True

    def clear_dedupe_window(self) -> None:
        """Drops the implicit de-duplication window without touching the latch.

        Used by the close paths that release input without a latched detection
        (a refused hit followed by a safe close).
        """
        with self._lock:
            self._dedupe_until = None

    # -- diagnostics ---------------------------------------------------------

    def diagnostics(self) -> Dict[str, Any]:
        with self._lock:
            policy = self._active_policy
            return {
                "threshold": policy.sensitivity,
                "dedupeMs": self._rearm_ms,
                "cooldownMs": policy.cooldown_ms,
                "preRollMs": policy.pre_roll_ms,
                "policy": policy.to_dict(),
                "generation": self._generation,
                "latchedActivationId": self._latched_activation_id,
                "dedupeUntil": self._dedupe_until,
                "cooldownUntil": self._cooldown_until,
                "lastCandidate": (
                    self._last_candidate.diagnostics()
                    if self._last_candidate is not None
                    else None
                ),
            }
