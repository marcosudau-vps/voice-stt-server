"""AP-SRV-060 wake audio boundary: what the transcript is actually allowed to see.

The legacy path removed ``sample_rate * wake_word_buffer_duration`` samples
from the head of the recording, regardless of where the wake word really
ended. That is a fixed-duration guess: too small and the wake word leaks into
the transcript, too large and the first user word is cut off.

This module separates the five things the frozen contract distinguishes:

``detector history``
    Everything the detector consumed. Never released as transcript audio on
    its own.
``wake word audio``
    The measured span the accepted classifier still saw, ending at the
    detection sample position.
``wake end boundary``
    The sample position at which the wake word is over. This is the anchor -
    not a duration.
``user speech pre-roll``
    ``wakeWord.preRollMs`` of audio released *before* the wake end, clamped so
    it can never reach back past the wake start. ``0 ms`` is valid and correct.
``released transcript audio``
    Everything from the release sample onwards.

With ``preRollMs = 0`` the transcript starts exactly at the wake end: the wake
word is not transcribed and the first user word, which follows the wake end,
is fully preserved.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple


DEFAULT_SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2


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
    """One accepted detection's audio boundary, in absolute stream samples."""

    sample_rate: int
    wake_start_sample: int
    wake_end_sample: int
    release_sample: int
    pre_roll_samples: int
    receptive_field_ms: float

    @property
    def pre_roll_ms(self) -> float:
        return self.pre_roll_samples * 1000.0 / float(self.sample_rate or DEFAULT_SAMPLE_RATE)

    @property
    def released_pre_roll_samples(self) -> int:
        """Pre-roll actually released after clamping to the wake start."""
        return max(0, self.wake_end_sample - self.release_sample)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sampleRate": int(self.sample_rate),
            "wakeStartSample": int(self.wake_start_sample),
            "wakeEndSample": int(self.wake_end_sample),
            "releaseSample": int(self.release_sample),
            "preRollSamples": int(self.pre_roll_samples),
            "releasedPreRollSamples": int(self.released_pre_roll_samples),
            "receptiveFieldMs": float(self.receptive_field_ms),
        }


def resolve_wake_audio_boundary(
    *,
    detection_sample_position: int,
    receptive_field_ms: float,
    pre_roll_ms: Any = 0,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    detector_history_start_sample: int = 0,
) -> WakeAudioBoundary:
    """The boundary one accepted detection establishes.

    ``detection_sample_position`` is the absolute stream position of the last
    sample the accepted classifier consumed - the wake end. The wake start is
    that position minus the *measured* receptive field of the model that fired,
    clamped to the oldest sample the detector history still holds.
    """
    rate = int(sample_rate or DEFAULT_SAMPLE_RATE)
    wake_end = max(int(detector_history_start_sample), int(detection_sample_position))
    window = ms_to_samples(receptive_field_ms, rate)
    wake_start = max(int(detector_history_start_sample), wake_end - window)
    pre_roll = ms_to_samples(pre_roll_ms, rate)
    release = max(wake_start, wake_end - pre_roll)
    return WakeAudioBoundary(
        sample_rate=rate,
        wake_start_sample=wake_start,
        wake_end_sample=wake_end,
        release_sample=release,
        pre_roll_samples=pre_roll,
        receptive_field_ms=float(receptive_field_ms),
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
