"""AP-SRV-060 wake detection domain: prediction frames, hit regions, decisions.

What "1 Wake Word = 1 ``wakeword.detected``" means (AP-SRV-060 C3 / Root F13)
-----------------------------------------------------------------------------

It is an **exactly-once eventing** rule about one spoken wake-word utterance,
not a claim that a single score frame is already a wake word. OpenWakeWord
emits a score per selected classifier on every prediction frame, and a spoken
wake word produces a whole *run* of frames above the threshold. Those frames
are one logical hit and must produce at most one domain event.

The C1/C2 documentation read the rule the other way round and wrote sentences
like "keine Mehrfach-Chunk-Regel" and "keine 5/10 Treffer" into the product
contract. Those formulations are withdrawn; this module implements the model
Root confirmed instead.

The model
---------

``wakeWord.sensitivity``
    the score threshold every selected wake word is compared against;
``wakeWord.minConsecutivePredictionFrames``
    how many *consecutive* prediction frames must reach that threshold before a
    run may become a hit at all.

Per selected wake word the tracker follows one contiguous run:

run grows
    every further prediction frame with ``score >= sensitivity``;
run discarded
    the first frame below the threshold *before* the minimum was reached - no
    hit, no event, the counter starts from zero on the next frame;
qualification
    the frame at which the minimum is reached. The candidate is now eligible;
    it is not yet the decision and not yet the event;
finalization
    the first frame below the threshold *after* qualification. That transition
    closes the run, and its trailing edge is the operational audio zero point.

Arbitration between several selected wake words is first-come-first-served: the
first qualified candidate that finalizes wins, every other candidate of that
decision is discarded, and there is no waiting period, no "prefer the longer
word" and no retrospective peak-score contest. Only a theoretical tie inside
one and the same prediction frame needs the deterministic chain in
:func:`arbitrate_finalized`.

One attempt, one settings revision (Root F11)
---------------------------------------------

:class:`WakeAttemptPolicy` is the immutable snapshot of every value one wake
attempt uses. It is frozen at the linearization point - the prediction frame
that starts a new run while no other run is active - and it stays in force for
the score comparison, the frame counter, qualification, finalization, pre-roll,
the cooldown decision, the accepted detection and the activation's effective
settings. A patch that lands mid-utterance applies to the *next* attempt. There
is no mixed-revision attempt.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


#: One OpenWakeWord embedding frame advances the stream by 1280 samples.
EMBEDDING_FRAME_STEP_MS = 80.0

#: The embedding model consumes 76 melspectrogram frames at a 10 ms hop.
EMBEDDING_WINDOW_MS = 760.0

DEFAULT_SAMPLE_RATE = 16000


def receptive_field_ms(input_frames: Any) -> float:
    """The audio span one classifier with ``input_frames`` frames still sees.

    Kept as a *diagnostic* measurement of the bundled classifiers. Since C3 it
    is no longer an authority over anything: neither the audio boundary nor the
    pre-roll range is derived from it.
    """
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
class WakeAttemptPolicy:
    """The immutable wake values of exactly one wake attempt (Root F11).

    ``settings_revision`` records which AP-SRV-050 revision the values came
    from. Once a hit region has frozen a snapshot, every later step of that
    same region uses it - a snapshot can never mix two revisions.
    """

    sensitivity: float = 0.5
    min_consecutive_prediction_frames: int = 1
    detector_gain: float = 1.0
    cooldown_ms: int = 0
    pre_roll_ms: int = 0
    settings_revision: int = 0

    @property
    def min_frames(self) -> int:
        return max(1, int(self.min_consecutive_prediction_frames))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensitivity": float(self.sensitivity),
            "minConsecutivePredictionFrames": self.min_frames,
            "detectorGain": float(self.detector_gain),
            "cooldownMs": int(self.cooldown_ms),
            "preRollMs": int(self.pre_roll_ms),
            "settingsRevision": int(self.settings_revision),
        }


#: Historical name of the attempt snapshot. C2 called it a *runtime* policy and
#: latched it per activation; C3 freezes it per wake attempt. The alias keeps
#: existing imports working without creating a second policy type.
WakeRuntimePolicy = WakeAttemptPolicy


def _coerce_policy(value: Any) -> WakeAttemptPolicy:
    """Accepts a policy, a mapping or ``None`` and returns a policy."""
    if isinstance(value, WakeAttemptPolicy):
        return value
    if isinstance(value, Mapping):
        return WakeAttemptPolicy(
            sensitivity=float(value.get("sensitivity", 0.5)),
            min_consecutive_prediction_frames=int(
                value.get(
                    "min_consecutive_prediction_frames",
                    value.get("minConsecutivePredictionFrames", 1),
                )
            ),
            detector_gain=float(
                value.get("detector_gain", value.get("detectorGain", 1.0))
            ),
            cooldown_ms=int(value.get("cooldown_ms", value.get("cooldownMs", 0))),
            pre_roll_ms=int(value.get("pre_roll_ms", value.get("preRollMs", 0))),
            settings_revision=int(
                value.get("settings_revision", value.get("settingsRevision", 0))
            ),
        )
    return WakeAttemptPolicy()


@dataclass(frozen=True)
class RawWakeCandidate:
    """One observed detector score. Diagnostics only - never a domain event."""

    canonical_wake_word_id: str
    raw_score: float
    frame_index: int
    sample_position: int
    detector_generation: int = 0
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
class WakeHit:
    """One finalized contiguous hit region - the unit of a wake decision.

    It groups every prediction frame of one spoken wake-word utterance. A hit
    is what may become **one** logical ``wakeword.detected``; a single frame
    never is.
    """

    canonical_wake_word_id: str
    peak_score: float
    start_frame_index: int
    start_sample: int
    qualification_frame_index: int
    qualification_sample: int
    finalization_frame_index: int
    operational_zero_point_sample: int
    prediction_frame_count: int
    policy: WakeAttemptPolicy = field(default_factory=WakeAttemptPolicy)
    detector_generation: int = 0

    @property
    def score(self) -> float:
        """The score the domain publishes: the peak of the whole hit region."""
        return float(self.peak_score)

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "wakeWordId": self.canonical_wake_word_id,
            "peakScore": float(self.peak_score),
            "startFrameIndex": int(self.start_frame_index),
            "startSample": int(self.start_sample),
            "qualificationFrameIndex": int(self.qualification_frame_index),
            "qualificationSample": int(self.qualification_sample),
            "finalizationFrameIndex": int(self.finalization_frame_index),
            "operationalZeroPointSample": int(self.operational_zero_point_sample),
            "predictionFrameCount": int(self.prediction_frame_count),
            "detectorGeneration": int(self.detector_generation),
            "policy": self.policy.to_dict(),
        }


@dataclass(frozen=True)
class AcceptedWakeDetection:
    """One accepted wake detection - the only wake fact the domain publishes."""

    canonical_wake_word_id: str
    score: float
    activation_id: str
    boundary: Any = None
    detector_generation: int = 0
    wake_hit: Optional[WakeHit] = None

    def event_fields(self) -> Dict[str, Any]:
        """The ``wakeword.detected`` payload fields owned by this module."""
        return {
            "wakeWordId": self.canonical_wake_word_id,
            "score": float(self.score),
            "activationId": self.activation_id,
        }


def arbitration_key(hit: WakeHit) -> Tuple[int, int, str]:
    """The deterministic tie-breaker chain of one finalization frame.

    Only reached when several qualified candidates finalize in the *same*
    prediction frame:

    1. the earlier qualification wins;
    2. on an equal qualification the earlier run start wins;
    3. on a full tie the lexicographically smallest canonical id wins.

    These rules exist so a theoretical tie is resolved deterministically. They
    are not a semantic classification, they add no waiting period, and they are
    never consulted when one candidate finalizes before another.
    """
    return (
        int(hit.qualification_frame_index),
        int(hit.start_frame_index),
        str(hit.canonical_wake_word_id),
    )


def arbitrate_finalized(hits: Iterable[WakeHit]) -> Optional[WakeHit]:
    """The winner of one finalization frame, or ``None`` for no candidate."""
    candidates = [hit for hit in hits or () if hit is not None]
    if not candidates:
        return None
    return min(candidates, key=arbitration_key)


class _HitRegion:
    """One growing contiguous run of frames above the threshold."""

    __slots__ = (
        "wake_word_id", "start_frame_index", "start_sample", "frames",
        "peak_score", "qualification_frame_index", "qualification_sample",
        "last_frame_index", "last_sample",
    )

    def __init__(self, wake_word_id: str, frame_index: int, end_sample: int,
                 score: float):
        self.wake_word_id = wake_word_id
        self.start_frame_index = int(frame_index)
        self.start_sample = int(end_sample)
        self.frames = 1
        self.peak_score = float(score)
        self.qualification_frame_index: Optional[int] = None
        self.qualification_sample: Optional[int] = None
        self.last_frame_index = int(frame_index)
        #: End of the last prediction frame that reached the threshold. This
        #: is the trailing edge, and therefore the operational zero point.
        self.last_sample = int(end_sample)

    def extend(self, frame_index: int, end_sample: int, score: float) -> None:
        self.frames += 1
        self.peak_score = max(self.peak_score, float(score))
        self.last_frame_index = int(frame_index)
        self.last_sample = int(end_sample)

    def qualify(self, frame_index: int, end_sample: int) -> None:
        self.qualification_frame_index = int(frame_index)
        self.qualification_sample = int(end_sample)

    @property
    def qualified(self) -> bool:
        return self.qualification_frame_index is not None


class WakeHitTracker:
    """Threshold, minimum run length, qualification, trailing edge, arbitration.

    This class owns our domain logic and nothing else. Feature extraction,
    loaders, VAD, noise suppression and the neural prediction all stay upstream
    in ``openwakeword``; the tracker only interprets the scores that come out.
    """

    def __init__(self, *, policy_supplier=None, generation: int = 0):
        if policy_supplier is None:
            constant = WakeAttemptPolicy()
            policy_supplier = lambda: constant  # noqa: E731 - one-line constant
        self._policy_supplier = policy_supplier
        self._lock = threading.RLock()
        self._regions: Dict[str, _HitRegion] = {}
        self._attempt_policy: Optional[WakeAttemptPolicy] = None
        self._frame_index = -1
        self._generation = int(generation)
        self._last_scores: Dict[str, float] = {}

    # -- state ---------------------------------------------------------------

    @property
    def active(self) -> bool:
        """Whether at least one run is currently open."""
        with self._lock:
            return bool(self._regions)

    @property
    def attempt_policy(self) -> Optional[WakeAttemptPolicy]:
        """The frozen snapshot of the running attempt, if one is running."""
        with self._lock:
            return self._attempt_policy

    @property
    def frame_index(self) -> int:
        with self._lock:
            return self._frame_index

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    def current_policy(self) -> WakeAttemptPolicy:
        """The frozen attempt snapshot while an attempt runs, else the current.

        The engine asks for this before it applies ``detectorGain``, so the
        amplification of a running attempt can never come from a newer revision
        than the attempt itself (Root F11).
        """
        with self._lock:
            if self._attempt_policy is not None:
                return self._attempt_policy
            return self._read_policy_locked()

    def reset(self, *, generation: Optional[int] = None) -> int:
        """Drops every running region and starts a new detector generation."""
        with self._lock:
            self._regions.clear()
            self._attempt_policy = None
            self._frame_index = -1
            self._last_scores = {}
            self._generation = (
                self._generation + 1 if generation is None else int(generation)
            )
            return self._generation

    # -- evaluation ----------------------------------------------------------

    def observe(
        self,
        scores: Mapping[str, Any],
        *,
        end_sample: Optional[int] = None,
        policy: Optional[WakeAttemptPolicy] = None,
    ) -> Optional[WakeHit]:
        """One **prediction frame**, not one recorder chunk.

        ``scores`` maps canonical wake-word ids to the score of this frame;
        ``end_sample`` is the absolute stream position the frame ends at.
        Returns the finalized :class:`WakeHit` of this frame, or ``None``.
        """
        with self._lock:
            self._frame_index += 1
            frame_index = self._frame_index
            position = (
                int(end_sample) if end_sample is not None
                else (frame_index + 1) * 1280
            )
            self._last_scores = {
                str(key): float(value) for key, value in (scores or {}).items()
            }

            active_policy = self._attempt_policy
            if active_policy is None:
                active_policy = _coerce_policy(
                    policy if policy is not None else self._read_policy_locked()
                )
            threshold = float(active_policy.sensitivity)
            minimum = active_policy.min_frames

            finalized: List[WakeHit] = []
            started = False
            # A wake word that stops reporting a score is treated as below the
            # threshold, so a run can never survive its own model going quiet.
            observed = sorted(set(self._last_scores) | set(self._regions))
            for wake_word_id in observed:
                score = self._last_scores.get(wake_word_id, 0.0)
                region = self._regions.get(wake_word_id)
                if score >= threshold:
                    if region is None:
                        region = _HitRegion(
                            wake_word_id, frame_index, position, score
                        )
                        self._regions[wake_word_id] = region
                        started = True
                    else:
                        region.extend(frame_index, position, score)
                    if not region.qualified and region.frames >= minimum:
                        region.qualify(frame_index, position)
                    continue
                if region is None:
                    continue
                # First frame below the threshold closes this run.
                del self._regions[wake_word_id]
                if region.qualified:
                    finalized.append(
                        self._build_hit(region, frame_index, active_policy)
                    )

            # A run that starts while no attempt is open is the linearization
            # point of a new attempt: freeze the snapshot here.
            if started and self._attempt_policy is None:
                self._attempt_policy = active_policy
            if not self._regions and not finalized:
                self._attempt_policy = None

            if not finalized:
                return None

            winner = arbitrate_finalized(finalized)
            # First-finalized-wins: every other candidate of this decision is
            # discarded, including the ones still running.
            self._regions.clear()
            self._attempt_policy = None
            return winner

    def _build_hit(
        self,
        region: _HitRegion,
        frame_index: int,
        policy: WakeAttemptPolicy,
    ) -> WakeHit:
        # The operational zero point is the trailing edge of the run: the
        # transition from the last prediction frame >= threshold to the first
        # one below it, i.e. the end of that last qualifying frame.
        zero_point = region.last_sample
        return WakeHit(
            canonical_wake_word_id=region.wake_word_id,
            peak_score=region.peak_score,
            start_frame_index=region.start_frame_index,
            start_sample=region.start_sample,
            qualification_frame_index=int(region.qualification_frame_index),
            qualification_sample=int(region.qualification_sample),
            finalization_frame_index=int(frame_index),
            operational_zero_point_sample=int(zero_point),
            prediction_frame_count=int(region.frames),
            policy=policy,
            detector_generation=self._generation,
        )

    def _read_policy_locked(self) -> WakeAttemptPolicy:
        try:
            return _coerce_policy(self._policy_supplier())
        except Exception:  # noqa: BLE001 - never break detection on a read
            return WakeAttemptPolicy()

    # -- diagnostics ---------------------------------------------------------

    def diagnostics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "frameIndex": self._frame_index,
                "generation": self._generation,
                "attemptPolicy": (
                    self._attempt_policy.to_dict()
                    if self._attempt_policy is not None else None
                ),
                "lastScores": dict(self._last_scores),
                "runningRegions": {
                    key: {
                        "startFrameIndex": region.start_frame_index,
                        "frames": region.frames,
                        "peakScore": region.peak_score,
                        "qualified": region.qualified,
                    }
                    for key, region in self._regions.items()
                },
            }


class WakeDetectionEvaluator:
    """The session-level wake gate around one :class:`WakeHitTracker`.

    It answers one question - "may this finalized hit be offered to the
    admission right now?" - and remembers the answer until the admission tells
    it otherwise. It holds no activation state machine: whether a hit may open
    an activation is decided by the wake admission coordinator, which asks the
    source-neutral ``ActivationController``.

    Two things block an offer, and only two:

    the latch
        a detection that already opened an activation. It is released at the
        *safe input close* of that same activation - not at VAD end, not at
        segment end, not when a final inference starts or ends, and not when a
        cooldown expires;
    ``wakeWord.cooldownMs``
        an explicitly configured operator value after an accepted hit. Its
        default is ``0``, and it is deliberately *not* the same thing as the
        grouping of one hit region: grouping is the tracker's job and needs no
        timer at all.
    """

    def __init__(
        self,
        *,
        policy_supplier=None,
        engine=None,
        threshold: Optional[float] = None,
        clock=None,
        tracker=None,
    ):
        if policy_supplier is None:
            constant = WakeAttemptPolicy(
                sensitivity=0.5 if threshold is None else float(threshold)
            )
            policy_supplier = lambda: constant  # noqa: E731 - one-line constant
        self._lock = threading.RLock()
        self._policy_supplier = policy_supplier
        self._clock = clock or time.monotonic
        self._engine = engine
        self._tracker = tracker or WakeHitTracker(policy_supplier=policy_supplier)
        self._latched_activation_id: Optional[str] = None
        self._cooldown_until: Optional[float] = None
        self._last_hit: Optional[WakeHit] = None
        self._active_policy = _coerce_policy(self._read_policy())

    # -- runtime policy ------------------------------------------------------

    def _read_policy(self) -> WakeAttemptPolicy:
        try:
            return _coerce_policy(self._policy_supplier())
        except Exception:  # noqa: BLE001 - never break detection on a read
            return WakeAttemptPolicy()

    @property
    def active_policy(self) -> WakeAttemptPolicy:
        """The attempt snapshot in force right now.

        While a hit region is open the tracker's frozen snapshot is the answer;
        otherwise the current settings are read, which is exactly what
        ``applyPolicy = next_activation`` means for the *next* attempt.
        """
        with self._lock:
            if self._tracker.active:
                return self._tracker.current_policy()
            if self._latched_activation_id is None:
                self._active_policy = self._read_policy()
            return self._active_policy

    @property
    def engine(self):
        return self._engine

    @property
    def tracker(self) -> WakeHitTracker:
        return self._tracker

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
    def min_consecutive_prediction_frames(self) -> int:
        return self.active_policy.min_frames

    @property
    def generation(self) -> int:
        return self._tracker.generation

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
            self._latched_activation_id = None
            self._cooldown_until = None
            self._last_hit = None
            self._active_policy = self._read_policy()
            return self._tracker.reset()

    # -- evaluation ----------------------------------------------------------

    def process(self, data, *, now: Optional[float] = None) -> Tuple[WakeHit, ...]:
        """Feeds one recorder chunk through the engine and the tracker.

        The gain and the threshold of one attempt come from the *same* frozen
        snapshot, so the amplification a running attempt was scored with can
        never belong to a newer revision than the attempt (Root F11).
        """
        engine = self._engine
        if engine is None:
            return ()
        policy = self._tracker.current_policy()
        frames = engine.process(data, gain=policy.detector_gain)
        hits: List[WakeHit] = []
        for frame in frames:
            hit = self.observe_scores(
                frame.scores, end_sample=frame.end_sample, now=now
            )
            if hit is not None:
                hits.append(hit)
        return tuple(hits)

    def observe_scores(
        self,
        scores: Mapping[str, Any],
        *,
        end_sample: Optional[int] = None,
        now: Optional[float] = None,
    ) -> Optional[WakeHit]:
        """One prediction frame; the offered hit of this frame, if any."""
        with self._lock:
            timestamp = self._clock() if now is None else float(now)
            if self._latched_activation_id is not None:
                # One lifecycle only: while an activation is open the wake
                # source has no trigger effect at all.
                self._tracker.reset(generation=self._tracker.generation)
                return None
            hit = self._tracker.observe(scores, end_sample=end_sample)
            if hit is None:
                return None
            self._last_hit = hit
            if self._cooldown_until is not None and timestamp < self._cooldown_until:
                # An explicitly configured operator cooldown is still running.
                return None
            return hit

    #: Historical name of :meth:`observe_scores` for one prediction frame.
    offer_scores = observe_scores

    def accept(
        self,
        hit: WakeHit,
        *,
        activation_id: str,
        boundary: Any = None,
        now: Optional[float] = None,
    ) -> AcceptedWakeDetection:
        """Latches the detection onto one accepted activation."""
        with self._lock:
            timestamp = self._clock() if now is None else float(now)
            self._latched_activation_id = str(activation_id)
            # The running activation keeps the very snapshot its own hit region
            # was scored with; the next attempt re-reads the settings.
            self._active_policy = hit.policy
            self._arm_cooldown_locked(hit, timestamp)
            return AcceptedWakeDetection(
                canonical_wake_word_id=hit.canonical_wake_word_id,
                score=float(hit.peak_score),
                activation_id=str(activation_id),
                boundary=boundary,
                detector_generation=hit.detector_generation,
                wake_hit=hit,
            )

    def _arm_cooldown_locked(self, hit: Optional[WakeHit], timestamp: float) -> None:
        policy = getattr(hit, "policy", None) or self._active_policy
        if policy.cooldown_ms > 0:
            self._cooldown_until = timestamp + policy.cooldown_ms / 1000.0

    def refuse(self, hit: Optional[WakeHit] = None, *, now: Optional[float] = None) -> None:
        """A refused admission arms the cooldown but never the latch.

        A rejected hit is not a fachliches Ereignis and does not open an
        activation. There is no implicit blocking window beyond the operator's
        own ``wakeWord.cooldownMs``: the next utterance is a new hit region and
        must be admissible as soon as it finalizes.
        """
        with self._lock:
            timestamp = self._clock() if now is None else float(now)
            self._arm_cooldown_locked(hit, timestamp)

    def release_latch(self, *, activation_id: Optional[str] = None) -> bool:
        """Releases the latch at the safe input close of the same activation.

        An **explicitly configured** ``wakeWord.cooldownMs`` is deliberately not
        cleared here - that one is post-close semantics an operator asked for.
        """
        with self._lock:
            if self._latched_activation_id is None:
                return False
            if activation_id is not None and str(activation_id) != self._latched_activation_id:
                return False
            self._latched_activation_id = None
            self._tracker.reset(generation=self._tracker.generation)
            self._active_policy = self._read_policy()
            return True

    # -- diagnostics ---------------------------------------------------------

    def diagnostics(self) -> Dict[str, Any]:
        with self._lock:
            policy = self._active_policy
            payload: Dict[str, Any] = {
                "threshold": policy.sensitivity,
                "minConsecutivePredictionFrames": policy.min_frames,
                "cooldownMs": policy.cooldown_ms,
                "preRollMs": policy.pre_roll_ms,
                "detectorGain": policy.detector_gain,
                "policy": policy.to_dict(),
                "generation": self._tracker.generation,
                "latchedActivationId": self._latched_activation_id,
                "cooldownUntil": self._cooldown_until,
                "tracker": self._tracker.diagnostics(),
                "lastHit": (
                    self._last_hit.diagnostics()
                    if self._last_hit is not None else None
                ),
            }
            if self._engine is not None:
                try:
                    payload["engine"] = self._engine.diagnostics()
                except Exception:  # noqa: BLE001 - diagnostics never break
                    payload["engine"] = None
            return payload
