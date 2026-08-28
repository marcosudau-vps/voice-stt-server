"""AP-SRV-060 / FIND-011: one utterance, one detection, one audio boundary.

FIND-011 described the real defect precisely: ``recording.py`` kept calling the
detector for the following chunks even after ``wakeword_detected`` was set, so a
sustained high score could invoke ``on_wakeword_detected`` again and again.
These tests drive the production recording worker against a fake OpenWakeWord
model and assert the fixed behaviour.

Since AP-SRV-060 C3 the worker no longer treats a recorder chunk as a detection
unit at all: the chunk goes into the one
:class:`~VoiceSTT.core.openwakeword_engine.OpenWakeWordEngine`, which emits only
genuinely new prediction frames, and the
:class:`~VoiceSTT.core.wake_detection.WakeHitTracker` groups a contiguous run of
those frames into a single logical hit. The FIND-011 guard is still there and
still tested; it is now the second line of defence rather than the first.
"""

import collections
import queue
import threading
import time
import unittest
from unittest import mock

import numpy as np

from VoiceSTT.core.openwakeword_engine import (
    PREDICTION_FRAME_SAMPLES,
    OpenWakeWordEngine,
)
from VoiceSTT.core.recording import run_recording_worker
from VoiceSTT.core.wake_audio_boundary import WakeAudioBoundary
from VoiceSTT.core.wake_detection import (
    WakeAttemptPolicy,
    WakeDetectionEvaluator,
)


SAMPLE_RATE = 16000
#: One recorder chunk is one prediction frame here, so the scripts below read
#: as "frame 0 was 0.9, frame 1 was 0.9, frame 2 dropped".
CHUNK_SAMPLES = PREDICTION_FRAME_SAMPLES
CHUNK = b"\x00\x00" * CHUNK_SAMPLES


class ScriptedModel:
    """A fake ``openwakeword.Model`` with a scripted per-frame score."""

    def __init__(self, scores, **kwargs):
        self.kwargs = dict(kwargs)
        self.model_key = "jarvis_v2"
        self.models = {self.model_key: object()}
        self.model_inputs = {self.model_key: 16}
        self.prediction_buffer = {self.model_key: []}
        self.scores = list(scores)
        self.predict_calls = 0
        self._pending = 0
        self._produced = 0

    def predict(self, pcm):
        self.predict_calls += 1
        self._pending += int(np.asarray(pcm).shape[0])
        produced = 0
        while self._pending >= PREDICTION_FRAME_SAMPLES:
            self._pending -= PREDICTION_FRAME_SAMPLES
            score = (
                self.scores[self._produced]
                if self._produced < len(self.scores) else 0.0
            )
            self._produced += 1
            self.prediction_buffer[self.model_key].append(float(score))
            produced += 1
        if produced == 0:
            values = self.prediction_buffer[self.model_key]
            values.append(values[-1] if values else 0.0)
        return {self.model_key: self.prediction_buffer[self.model_key][-1]}


class FakeSelection:
    backend = "onnx"
    wake_word_ids = ("hey_jarvis",)
    model_paths = ("jarvis_v2.onnx",)
    model_key_to_id = {"jarvis_v2": "hey_jarvis"}

    def loader_kwargs(self):
        return {
            "wakeword_models": list(self.model_paths),
            "inference_framework": self.backend,
        }


def build_recorder(chunk_count, *, admission, scores=None, pre_roll_ms=0,
                   min_frames=1):
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
    # A real retained audio history, so the pre-roll clamp is exercised
    # against audio that really exists.
    recorder.audio_buffer = collections.deque(maxlen=64)
    recorder.audio_buffer_metadata = None

    model = ScriptedModel(scores if scores is not None else [0.9] * 200)
    engine = OpenWakeWordEngine(
        selection=FakeSelection(),
        model_factory=lambda **kwargs: model,
        sample_rate=SAMPLE_RATE,
    )
    recorder.owwModel = model
    recorder.wake_engine = engine
    recorder.wake_word_model_key_to_id = {"jarvis_v2": "hey_jarvis"}
    recorder.wake_word_input_frames = {"jarvis_v2": 16}
    recorder.wake_word_pre_roll_ms = pre_roll_ms
    recorder.wake_audio_boundary = None
    recorder.wake_stream_sample_position = 0
    recorder.wake_detection_evaluator = WakeDetectionEvaluator(
        policy_supplier=lambda: WakeAttemptPolicy(
            sensitivity=0.5,
            min_consecutive_prediction_frames=min_frames,
            cooldown_ms=0,
            pre_roll_ms=pre_roll_ms,
        ),
        engine=engine,
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


#: One spoken wake word: a run of qualifying frames, then a drop.
UTTERANCE = [0.9] * 5 + [0.0]


class Find011Tests(unittest.TestCase):
    def test_a_sustained_score_admits_exactly_once(self):
        calls = []

        def admission(hit, boundary):
            calls.append((hit, boundary))
            return recorder.wake_detection_evaluator.accept(
                hit, activation_id="act-1", boundary=boundary
            )

        recorder = build_recorder(40, admission=admission, scores=UTTERANCE)
        drain(recorder)

        self.assertEqual(len(calls), 1)
        self.assertTrue(recorder.wakeword_detected)
        self.assertEqual(calls[0][0].canonical_wake_word_id, "hey_jarvis")
        # Five prediction frames of one utterance are one logical hit.
        self.assertEqual(calls[0][0].prediction_frame_count, 5)

    def test_a_long_sustained_score_is_still_a_single_hit(self):
        calls = []

        def admission(hit, boundary):
            calls.append(hit)
            return recorder.wake_detection_evaluator.accept(
                hit, activation_id="act-1", boundary=boundary
            )

        recorder = build_recorder(
            40, admission=admission, scores=[0.9] * 30 + [0.0]
        )
        drain(recorder)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].prediction_frame_count, 30)

    def test_a_run_shorter_than_the_minimum_is_no_detection(self):
        calls = []

        recorder = build_recorder(
            20,
            admission=lambda hit, boundary: calls.append(hit),
            scores=[0.9] * 4 + [0.0] * 10,
            min_frames=10,
        )
        drain(recorder)
        self.assertEqual(calls, [])
        self.assertFalse(recorder.wakeword_detected)

    def test_the_detector_is_not_run_again_while_latched(self):
        def admission(hit, boundary):
            return recorder.wake_detection_evaluator.accept(
                hit, activation_id="act-1", boundary=boundary
            )

        recorder = build_recorder(40, admission=admission, scores=UTTERANCE)
        drain(recorder)

        # The guard stops the detector after the accepted hit; without it every
        # one of the 40 chunks would have been predicted.
        self.assertEqual(recorder.owwModel.predict_calls, len(UTTERANCE))

    def test_a_refused_admission_leaves_no_latch_and_no_boundary(self):
        calls = []

        def admission(hit, boundary):
            calls.append(hit)
            recorder.wake_detection_evaluator.refuse(hit)
            return None

        # Five separate utterances in ten chunks.
        recorder = build_recorder(
            10, admission=admission, scores=[0.9, 0.0] * 5
        )
        drain(recorder)

        self.assertFalse(recorder.wakeword_detected)
        self.assertIsNone(recorder.wake_audio_boundary)
        # The configured cooldown is 0, so every separate utterance may be
        # offered again - but not a single one produced a latch or a boundary.
        self.assertEqual(len(calls), 5)

    def test_an_accepted_hit_stores_the_boundary_for_the_audio_release(self):
        def admission(hit, boundary):
            return recorder.wake_detection_evaluator.accept(
                hit, activation_id="act-1", boundary=boundary
            )

        recorder = build_recorder(10, admission=admission, scores=[0.9, 0.0])
        drain(recorder)

        boundary = recorder.wake_audio_boundary
        self.assertIsInstance(boundary, WakeAudioBoundary)
        # The trailing edge of the single qualifying frame is the zero point.
        self.assertEqual(
            boundary.operational_zero_point_sample, PREDICTION_FRAME_SAMPLES
        )
        self.assertEqual(
            boundary.release_sample, boundary.operational_zero_point_sample
        )
        self.assertTrue(boundary.boundary_defined)

    def test_pre_roll_moves_the_release_back_from_the_zero_point(self):
        def admission(hit, boundary):
            return recorder.wake_detection_evaluator.accept(
                hit, activation_id="act-1", boundary=boundary
            )

        # Ten qualifying frames, so a real audio history exists behind the
        # trailing edge and the 10 ms pre-roll is not clamped away.
        recorder = build_recorder(
            20, admission=admission, scores=[0.9] * 10 + [0.0], pre_roll_ms=10
        )
        drain(recorder)

        boundary = recorder.wake_audio_boundary
        self.assertEqual(boundary.pre_roll_samples, 160)
        self.assertEqual(
            boundary.release_sample,
            boundary.operational_zero_point_sample - 160,
        )
        self.assertFalse(boundary.pre_roll_clamped)

    def test_the_pre_roll_never_reaches_past_the_retained_history(self):
        def admission(hit, boundary):
            return recorder.wake_detection_evaluator.accept(
                hit, activation_id="act-1", boundary=boundary
            )

        # A five second pre-roll against a session that has just started.
        recorder = build_recorder(
            10, admission=admission, scores=[0.9, 0.0], pre_roll_ms=5000
        )
        drain(recorder)

        boundary = recorder.wake_audio_boundary
        self.assertTrue(boundary.pre_roll_clamped)
        self.assertGreaterEqual(
            boundary.release_sample, boundary.history_start_sample
        )

    def test_a_latched_detector_is_not_released_by_the_legacy_timeout(self):
        timeouts = []

        def admission(hit, boundary):
            return recorder.wake_detection_evaluator.accept(
                hit, activation_id="act-1", boundary=boundary
            )

        recorder = build_recorder(20, admission=admission, scores=UTTERANCE)
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
        recorder.wake_engine = None
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
