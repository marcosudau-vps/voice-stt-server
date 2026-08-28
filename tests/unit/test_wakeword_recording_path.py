"""AP-SRV-060 / FIND-011: one utterance, one detection, one audio boundary.

FIND-011 described the real defect precisely: ``recording.py`` kept calling the
detector for the following chunks even after ``wakeword_detected`` was set, so
a sustained high score could invoke ``on_wakeword_detected`` again and again.
These tests drive the production recording worker against a fake detector and
assert the fixed behaviour.
"""

import queue
import threading
import time
import unittest
from unittest import mock

from VoiceSTT.core.recording import run_recording_worker
from VoiceSTT.core.wake_audio_boundary import WakeAudioBoundary
from VoiceSTT.core.wake_detection import (
    WakeDetectionEvaluator,
    WakeRuntimePolicy,
)


SAMPLE_RATE = 16000
CHUNK_SAMPLES = 512
CHUNK = b"\x00\x00" * CHUNK_SAMPLES


class ScriptedDetector:
    """A backend whose score stays above the threshold for every chunk."""

    def __init__(self, score=0.9, model_key="jarvis_v2"):
        self.model_key = model_key
        self.models = {model_key: object()}
        self.model_inputs = {model_key: 16}
        self.prediction_buffer = {model_key: [score]}
        self.predict_calls = 0

    def predict(self, _pcm):
        self.predict_calls += 1
        return {self.model_key: self.prediction_buffer[self.model_key][-1]}


def build_recorder(chunk_count, *, admission):
    recorder = mock.Mock()
    recorder.use_extended_logging = False
    recorder.is_running = True
    recorder.audio_queue = queue.Queue()
    for _ in range(chunk_count):
        recorder.audio_queue.put(CHUNK)
    recorder.last_words_buffer = []
    recorder.on_recorded_chunk = None
    recorder.handle_buffer_overflow = False
    recorder.allowed_latency_limit = 100
    recorder.sample_rate = SAMPLE_RATE

    # Not recording: the worker takes the wake-word branch.
    recorder.is_recording = False
    recorder.recording_stop_time = 0
    # A listen window that already started, so the activation delay passed.
    recorder.listen_start = time.time() - 10
    recorder.use_wake_words = True
    recorder.wake_word_activation_delay = 0.0
    recorder.wakeword_detected = False
    recorder.wake_word_detect_time = 0
    recorder.wake_word_timeout = 5.0
    recorder.wake_word_buffer_duration = 0.1
    recorder.wakeword_backend = "openwakeword"
    recorder.debug_mode = False
    recorder.speech_end_silence_start = 0
    recorder.on_turn_detection_stop = None
    recorder.on_wakeword_timeout = None
    recorder.on_wakeword_detected = admission
    recorder.start_callback_in_new_thread = False
    recorder.silero_check_time = 0
    recorder.frames = []
    recorder.continuous_listening = False

    recorder.owwModel = ScriptedDetector()
    recorder.wake_word_model_key_to_id = {"jarvis_v2": "hey_jarvis"}
    recorder.wake_word_input_frames = {"jarvis_v2": 16}
    recorder.wake_word_pre_roll_ms = 0
    recorder.wake_audio_boundary = None
    recorder.wake_stream_sample_position = 0
    recorder.wake_detection_evaluator = WakeDetectionEvaluator(
        policy_supplier=lambda: WakeRuntimePolicy(
            sensitivity=0.5, cooldown_ms=0,
            pre_roll_ms=recorder.wake_word_pre_roll_ms,
        ),
        rearm_ms=0.0,
    )
    return recorder


def drain(recorder):
    """Runs the worker until the queue is exhausted."""
    def stop_when_empty():
        while not recorder.audio_queue.empty():
            pass
        recorder.is_running = False

    watcher = threading.Thread(target=stop_when_empty, daemon=True)
    watcher.start()
    with mock.patch(
        "VoiceSTT.core.recording.recording_activation_gate_is_open",
        return_value=False,
    ), mock.patch("VoiceSTT.core.recording.set_recorder_state"):
        run_recording_worker(recorder)
    watcher.join(timeout=5)


class Find011Tests(unittest.TestCase):
    def test_a_sustained_score_admits_exactly_once(self):
        calls = []

        def admission(candidate, boundary):
            calls.append((candidate, boundary))
            return recorder.wake_detection_evaluator.accept(
                candidate, activation_id="act-1", boundary=boundary
            )

        recorder = build_recorder(40, admission=admission)
        drain(recorder)

        self.assertEqual(len(calls), 1)
        self.assertTrue(recorder.wakeword_detected)
        self.assertEqual(calls[0][0].canonical_wake_word_id, "hey_jarvis")

    def test_the_detector_is_not_run_again_while_latched(self):
        def admission(candidate, boundary):
            return recorder.wake_detection_evaluator.accept(
                candidate, activation_id="act-1", boundary=boundary
            )

        recorder = build_recorder(40, admission=admission)
        drain(recorder)

        # The guard stops the detector after the first accepted hit; without it
        # every one of the 40 chunks would have been predicted.
        self.assertEqual(recorder.owwModel.predict_calls, 1)

    def test_a_refused_admission_leaves_no_latch_and_no_boundary(self):
        calls = []

        def admission(candidate, boundary):
            calls.append(candidate)
            recorder.wake_detection_evaluator.refuse(candidate)
            return None

        recorder = build_recorder(10, admission=admission)
        drain(recorder)

        self.assertFalse(recorder.wakeword_detected)
        self.assertIsNone(recorder.wake_audio_boundary)
        # Re-arm is 0 ms here, so every chunk may be offered again - but not a
        # single one produced a latch or a boundary.
        self.assertEqual(len(calls), 10)

    def test_an_accepted_hit_stores_the_boundary_for_the_audio_release(self):
        def admission(candidate, boundary):
            return recorder.wake_detection_evaluator.accept(
                candidate, activation_id="act-1", boundary=boundary
            )

        recorder = build_recorder(5, admission=admission)
        drain(recorder)

        boundary = recorder.wake_audio_boundary
        self.assertIsInstance(boundary, WakeAudioBoundary)
        # First chunk, so the detection sample is the end of that chunk.
        self.assertEqual(boundary.detection_sample, CHUNK_SAMPLES)
        self.assertEqual(
            boundary.release_sample, boundary.estimated_wake_end_sample
        )
        self.assertEqual(boundary.receptive_field_ms, 1960)
        self.assertFalse(boundary.boundary_measured)

    def test_pre_roll_moves_the_release_without_reaching_past_the_wake_start(self):
        def admission(candidate, boundary):
            return recorder.wake_detection_evaluator.accept(
                candidate, activation_id="act-1", boundary=boundary
            )

        recorder = build_recorder(5, admission=admission)
        recorder.wake_word_pre_roll_ms = 10
        drain(recorder)

        boundary = recorder.wake_audio_boundary
        self.assertEqual(boundary.pre_roll_samples, 160)
        self.assertEqual(
            boundary.release_sample, boundary.estimated_wake_end_sample - 160
        )
        self.assertGreaterEqual(
            boundary.release_sample, boundary.receptive_field_start_sample
        )

    def test_a_latched_detector_is_not_released_by_the_legacy_timeout(self):
        timeouts = []

        def admission(candidate, boundary):
            return recorder.wake_detection_evaluator.accept(
                candidate, activation_id="act-1", boundary=boundary
            )

        recorder = build_recorder(20, admission=admission)
        recorder.wake_word_timeout = 0.0
        recorder.on_wakeword_timeout = lambda: timeouts.append(True)
        drain(recorder)

        # The v2 latch belongs to the accepted activation and is released at its
        # safe input close - never by a detector timeout.
        self.assertEqual(timeouts, [])
        self.assertTrue(recorder.wakeword_detected)


class LegacyPathTests(unittest.TestCase):
    def test_without_an_evaluator_the_legacy_index_path_still_runs(self):
        calls = []
        recorder = build_recorder(6, admission=lambda *_args: None)
        recorder.wake_detection_evaluator = None
        recorder.on_wakeword_detected = lambda: calls.append(True)

        with mock.patch(
            "VoiceSTT.core.recording.process_wakeword", return_value=0
        ) as process:
            drain(recorder)

        self.assertEqual(len(calls), 1)
        # The FIND-011 guard applies to the legacy path as well: the detector
        # is not called again once a hit is latched.
        self.assertEqual(process.call_count, 1)


if __name__ == "__main__":
    unittest.main()
