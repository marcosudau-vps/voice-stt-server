"""AP-SRV-060 wake audio boundary: what the transcript is allowed to see.

The legacy path removed ``sample_rate * wake_word_buffer_duration`` samples
from the head of the recording, regardless of where the wake word really
ended. That is a fixed-duration guess: too small and the wake word leaks into
the transcript, too large and the first user word is cut off.

The operational audio zero point (AP-SRV-060 C3, section 7)
------------------------------------------------------------

C1/C2 treated the wake end as an *unknown* quantity and called the classifier's
decision sample a provisional estimate of it, blocked on real recordings. Root
has since defined the zero point as a deliberate server-side product decision,
so it no longer has to be discovered by external audio annotation.

The zero point is **not**:

* the first prediction frame above the threshold;
* the frame at which the minimum run length was reached;
* the end of a classifier receptive field;
* an externally annotated "true" phonemic wake-word end.

It **is** the trailing edge of the winning qualified hit region: the transition
from the last prediction frame with ``score >= sensitivity`` to the first one
below it. :class:`~VoiceSTT.core.wake_detection.WakeHit` carries exactly that
sample position.

``wakeWord.preRollMs`` then moves the release boundary back from the zero
point::

    releaseBoundary = operationalZeroPoint - preRoll

clamped to the audio history that actually still exists. ``preRollMs = 0``
releases the audio at the zero point, so the wake word itself is excluded and
the following user speech is preserved.

What stays open is the *empirical calibration* - which threshold, which minimum
run length, which pre-roll, which cooldown are the right operating points. That
needs real positive wake-word recordings (WW-18/WW-19) and is reported as
``EVIDENCE_BLOCKED``. The zero point itself is not part of that gap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple


DEFAULT_SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2

#: The one boundary basis of the C3 contract: a defined product decision, not
#: an estimate waiting for external annotation.
BASIS_OPERATIONAL_ZERO_POINT = "operational_zero_point"


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
    """One accepted hit's audio boundary, in absolute stream samples."""

    sample_rate: int
    operational_zero_point_sample: int
    history_start_sample: int
    release_sample: int
    pre_roll_samples: int
    boundary_basis: str = BASIS_OPERATIONAL_ZERO_POINT

    @property
    def boundary_defined(self) -> bool:
        """Whether the zero point rests on the defined product boundary."""
        return self.boundary_basis == BASIS_OPERATIONAL_ZERO_POINT

    @property
    def pre_roll_ms(self) -> float:
        return self.pre_roll_samples * 1000.0 / float(
            self.sample_rate or DEFAULT_SAMPLE_RATE
        )

    @property
    def released_pre_roll_samples(self) -> int:
        """Pre-roll actually released after clamping to the audio history."""
        return max(0, self.operational_zero_point_sample - self.release_sample)

    @property
    def pre_roll_clamped(self) -> bool:
        """Whether the requested pre-roll exceeded the retained audio."""
        return self.released_pre_roll_samples < self.pre_roll_samples

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sampleRate": int(self.sample_rate),
            "operationalZeroPointSample": int(self.operational_zero_point_sample),
            "historyStartSample": int(self.history_start_sample),
            "releaseSample": int(self.release_sample),
            "preRollSamples": int(self.pre_roll_samples),
            "releasedPreRollSamples": int(self.released_pre_roll_samples),
            "preRollClamped": bool(self.pre_roll_clamped),
            "boundaryBasis": self.boundary_basis,
            "boundaryDefined": bool(self.boundary_defined),
        }


def resolve_wake_audio_boundary(
    *,
    operational_zero_point_sample: int,
    pre_roll_ms: Any = 0,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    history_start_sample: int = 0,
) -> WakeAudioBoundary:
    """The boundary one accepted wake hit establishes.

    ``operational_zero_point_sample`` is the trailing edge of the winning
    qualified hit region - the position
    :class:`~VoiceSTT.core.wake_detection.WakeHit` reports. The release
    boundary is that point minus the configured pre-roll, clamped to the audio
    history the session really still holds.
    """
    rate = int(sample_rate or DEFAULT_SAMPLE_RATE)
    history_start = int(history_start_sample)
    zero_point = max(history_start, int(operational_zero_point_sample))
    pre_roll = ms_to_samples(pre_roll_ms, rate)
    release = max(history_start, zero_point - pre_roll)
    return WakeAudioBoundary(
        sample_rate=rate,
        operational_zero_point_sample=zero_point,
        history_start_sample=history_start,
        release_sample=release,
        pre_roll_samples=pre_roll,
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
    cuts at the position the accepted hit established, never at a configured
    duration.
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
