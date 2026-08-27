"""AP-SRV-060: the wake/user-speech audio boundary replaces the fixed cut."""

import unittest

from VoiceSTT.core.wake_audio_boundary import (
    ms_to_samples,
    resolve_wake_audio_boundary,
    trim_frames_to_boundary,
)


SAMPLE_RATE = 16000


def frames_of(*sample_counts):
    """PCM frames whose bytes encode their own absolute sample index."""
    frames = []
    cursor = 0
    for count in sample_counts:
        frames.append(
            b"".join(
                (cursor + offset).to_bytes(2, "little", signed=False)
                for offset in range(count)
            )
        )
        cursor += count
    return frames


class MillisecondConversionTests(unittest.TestCase):
    def test_zero_and_negative_values_are_no_samples(self):
        for value in (0, -1, None, "nope"):
            with self.subTest(value=value):
                self.assertEqual(ms_to_samples(value, SAMPLE_RATE), 0)

    def test_milliseconds_convert_at_the_stream_rate(self):
        self.assertEqual(ms_to_samples(1000, SAMPLE_RATE), 16000)
        self.assertEqual(ms_to_samples(80, SAMPLE_RATE), 1280)


class BoundaryTests(unittest.TestCase):
    def test_zero_pre_roll_releases_exactly_at_the_wake_end(self):
        boundary = resolve_wake_audio_boundary(
            detection_sample_position=32000,
            receptive_field_ms=1960,
            pre_roll_ms=0,
            sample_rate=SAMPLE_RATE,
        )
        self.assertEqual(boundary.wake_end_sample, 32000)
        self.assertEqual(boundary.release_sample, 32000)
        self.assertEqual(boundary.released_pre_roll_samples, 0)

    def test_the_wake_start_is_the_measured_receptive_field(self):
        boundary = resolve_wake_audio_boundary(
            detection_sample_position=32000,
            receptive_field_ms=1960,
            sample_rate=SAMPLE_RATE,
        )
        self.assertEqual(boundary.wake_start_sample, 32000 - 31360)

    def test_pre_roll_moves_the_release_back_but_never_past_the_wake_start(self):
        boundary = resolve_wake_audio_boundary(
            detection_sample_position=32000,
            receptive_field_ms=1960,
            pre_roll_ms=500,
            sample_rate=SAMPLE_RATE,
        )
        self.assertEqual(boundary.release_sample, 32000 - 8000)

        clamped = resolve_wake_audio_boundary(
            detection_sample_position=32000,
            receptive_field_ms=1960,
            pre_roll_ms=5000,
            sample_rate=SAMPLE_RATE,
        )
        # Never reaches back before the wake word itself started.
        self.assertEqual(clamped.release_sample, clamped.wake_start_sample)

    def test_the_detector_history_start_clamps_the_boundary(self):
        boundary = resolve_wake_audio_boundary(
            detection_sample_position=5000,
            receptive_field_ms=1960,
            sample_rate=SAMPLE_RATE,
            detector_history_start_sample=4000,
        )
        self.assertEqual(boundary.wake_start_sample, 4000)

    def test_the_projection_is_json_safe_and_complete(self):
        payload = resolve_wake_audio_boundary(
            detection_sample_position=32000,
            receptive_field_ms=1960,
            pre_roll_ms=250,
            sample_rate=SAMPLE_RATE,
        ).to_dict()
        self.assertEqual(set(payload), {
            "sampleRate", "wakeStartSample", "wakeEndSample", "releaseSample",
            "preRollSamples", "releasedPreRollSamples", "receptiveFieldMs",
        })


class TrimTests(unittest.TestCase):
    def _samples(self, frames):
        joined = b"".join(frames)
        return [
            int.from_bytes(joined[index:index + 2], "little", signed=False)
            for index in range(0, len(joined), 2)
        ]

    def test_whole_frames_before_the_release_are_dropped(self):
        frames = frames_of(100, 100, 100)
        retained, removed = trim_frames_to_boundary(
            frames, first_frame_start_sample=0, release_sample=200
        )
        self.assertEqual(removed, 200)
        self.assertEqual(self._samples(retained)[0], 200)
        self.assertEqual(len(self._samples(retained)), 100)

    def test_a_partial_frame_is_cut_at_the_exact_sample(self):
        frames = frames_of(100, 100)
        retained, removed = trim_frames_to_boundary(
            frames, first_frame_start_sample=0, release_sample=150
        )
        self.assertEqual(removed, 150)
        samples = self._samples(retained)
        self.assertEqual(samples[0], 150)
        self.assertEqual(len(samples), 50)

    def test_a_release_before_the_first_frame_keeps_everything(self):
        frames = frames_of(100, 100)
        retained, removed = trim_frames_to_boundary(
            frames, first_frame_start_sample=500, release_sample=100
        )
        self.assertEqual(removed, 0)
        self.assertEqual(len(self._samples(retained)), 200)

    def test_the_wake_word_leaves_and_the_first_user_word_survives(self):
        """``[wake word][first user word][rest]`` -> ``[first user word][rest]``."""
        wake_samples = 16000          # 1000 ms of wake word
        first_word_samples = 4000     # 250 ms first user word
        rest_samples = 8000
        frames = frames_of(wake_samples, first_word_samples, rest_samples)

        boundary = resolve_wake_audio_boundary(
            detection_sample_position=wake_samples,
            receptive_field_ms=1000,
            pre_roll_ms=0,
            sample_rate=SAMPLE_RATE,
        )
        retained, removed = trim_frames_to_boundary(
            frames,
            first_frame_start_sample=0,
            release_sample=boundary.release_sample,
        )
        samples = self._samples(retained)
        self.assertEqual(removed, wake_samples)
        # No wake-word sample survived ...
        self.assertEqual(samples[0], wake_samples)
        # ... and not a single sample of the first user word was cut.
        self.assertEqual(len(samples), first_word_samples + rest_samples)


if __name__ == "__main__":
    unittest.main()
