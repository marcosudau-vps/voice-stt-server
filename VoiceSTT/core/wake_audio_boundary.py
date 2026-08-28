"""AP-SRV-060 wake audio boundary: what the transcript is allowed to see.

The legacy path removed ``sample_rate * wake_word_buffer_duration`` samples
from the head of the recording, regardless of where the wake word really
ended. That is a fixed-duration guess: too small and the wake word leaks into
the transcript, too large and the first user word is cut off.

What this module knows, and what it does not (Root F4)
------------------------------------------------------

The classifier tells us one thing only: **at which sample position it decided**.
That position is *not* the same as the acoustic end of the spoken wake word:

``detection sample``
    Measured. The absolute stream position at which the accepted classifier
    produced its decision.
``model receptive field``
    Measured. The audio span that classifier still had in view, derived from
    its input frame count.
``estimated wake end``
    **Estimated, not measured.** This module currently equates it with the
    detection sample. That is a deliberate, conservative provisional choice -
    the classifier cannot decide before the wake word is over, so the decision
    point is at or after the acoustic end. Whether it is *exactly* the acoustic
    end, and by how much it lags, requires real positive wake-word recordings.
    WW-19 is therefore ``EVIDENCE_BLOCKED``, and every projection of this
    module says so through ``boundaryBasis``/``boundaryMeasured``.
``speech start``
    Unknown here. It is a property of the following user speech and is not
    derived from the classifier at all.
``release boundary``
    What the transcript actually starts from:
    ``max(receptive field start, estimated wake end - preRollMs)``.

No field, name or document in this module may present the detection sample as
a proven acoustic wake end while WW-19 is unmeasured. With
``wakeWord.preRollMs = 0`` the transcript starts at the estimated wake end, so
the wake word is excluded and the following user speech is preserved under that
estimate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple


DEFAULT_SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2

#: How the wake end of a boundary was obtained. Only ``measured_wake_end`` may
#: ever be treated as an acoustic fact, and nothing produces it yet.
BASIS_DETECTION_SAMPLE_ESTIMATE = "detection_sample_estimate"
BASIS_MEASURED_WAKE_END = "measured_wake_end"


def ms_to_samples(milliseconds: Any, sample_rate: int) -> int:
    try:
        value = float(milliseconds)
    except (TypeError, ValueError):
        return 0
    if value <= 0:
        return 0
    return int(round(value * float(sample_rate) / 1000.0))


@dataclass(frozen=True)
class WakeAudioBoundary:
    """One accepted detection's audio boundary, in absolute stream samples.

    ``estimated_wake_end_sample`` is named for what it is. ``boundary_basis``
    records how it was obtained, and ``boundary_measured`` is ``False`` for
    every basis that is not a real acoustic measurement.
    """

    sample_rate: int
    detection_sample: int
    receptive_field_start_sample: int
    estimated_wake_end_sample: int
    release_sample: int
    pre_roll_samples: int
    receptive_field_ms: float
    boundary_basis: str = BASIS_DETECTION_SAMPLE_ESTIMATE

    @property
    def boundary_measured(self) -> bool:
        """Whether the wake end rests on a real acoustic measurement."""
        return self.boundary_basis == BASIS_MEASURED_WAKE_END

    @property
    def pre_roll_ms(self) -> float:
        return self.pre_roll_samples * 1000.0 / float(
            self.sample_rate or DEFAULT_SAMPLE_RATE
        )

    @property
    def released_pre_roll_samples(self) -> int:
        """Pre-roll actually released after clamping to the receptive field."""
        return max(0, self.estimated_wake_end_sample - self.release_sample)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sampleRate": int(self.sample_rate),
            "detectionSample": int(self.detection_sample),
            "receptiveFieldStartSample": int(self.receptive_field_start_sample),
            "estimatedWakeEndSample": int(self.estimated_wake_end_sample),
            "releaseSample": int(self.release_sample),
            "preRollSamples": int(self.pre_roll_samples),
            "releasedPreRollSamples": int(self.released_pre_roll_samples),
            "receptiveFieldMs": float(self.receptive_field_ms),
            "boundaryBasis": self.boundary_basis,
            "boundaryMeasured": bool(self.boundary_measured),
        }


def resolve_wake_audio_boundary(
    *,
    detection_sample_position: int,
    receptive_field_ms: float,
    pre_roll_ms: Any = 0,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    detector_history_start_sample: int = 0,
    wake_end_sample: Any = None,
) -> WakeAudioBoundary:
    """The boundary one accepted detection establishes.

    ``detection_sample_position`` is the measured stream position at which the
    accepted classifier decided. ``wake_end_sample`` is the *measured* acoustic
    wake end and may be passed once WW-19 has been measured; until then the
    detection sample is used as a conservative estimate and the result says so.
    """
    rate = int(sample_rate or DEFAULT_SAMPLE_RATE)
    history_start = int(detector_history_start_sample)
    detection = max(history_start, int(detection_sample_position))

    if wake_end_sample is None:
        estimated_wake_end = detection
        basis = BASIS_DETECTION_SAMPLE_ESTIMATE
    else:
        estimated_wake_end = max(history_start, int(wake_end_sample))
        basis = BASIS_MEASURED_WAKE_END

    window = ms_to_samples(receptive_field_ms, rate)
    receptive_field_start = max(history_start, detection - window)
    pre_roll = ms_to_samples(pre_roll_ms, rate)
    release = max(receptive_field_start, estimated_wake_end - pre_roll)
    return WakeAudioBoundary(
        sample_rate=rate,
        detection_sample=detection,
        receptive_field_start_sample=receptive_field_start,
        estimated_wake_end_sample=estimated_wake_end,
        release_sample=release,
        pre_roll_samples=pre_roll,
        receptive_field_ms=float(receptive_field_ms),
        boundary_basis=basis,
    )


def trim_frames_to_boundary(
    frames: Sequence[bytes],
    *,
    first_frame_start_sample: int,
    release_sample: int,
    bytes_per_sample: int = BYTES_PER_SAMPLE,
) -> Tuple[List[bytes], int]:
    """Drops everything before ``release_sample`` from a PCM frame list.

    Returns the retained frames and the number of removed samples. This is the
    boundary-anchored replacement for the blanket fixed-duration removal: it
    cuts at the position the accepted detection established, never at a
    configured duration.
    """
    retained: List[bytes] = []
    cursor = int(first_frame_start_sample)
    removed = 0
    target = int(release_sample)
    for frame in frames or ():
        frame_samples = len(frame) // bytes_per_sample
        frame_end = cursor + frame_samples
        if frame_end <= target:
            removed += frame_samples
            cursor = frame_end
            continue
        if cursor < target:
            offset = target - cursor
            retained.append(frame[offset * bytes_per_sample:])
            removed += offset
        else:
            retained.append(frame)
        cursor = frame_end
    return retained, removed
