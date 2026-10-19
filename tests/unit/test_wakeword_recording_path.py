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
import json
import queue
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from VoiceSTT.core.openwakeword_engine import (
    PREDICTION_FRAME_SAMPLES,
    OpenWakeWordEngine,
)
from VoiceSTT.core.recording import _wake_detection_step, run_recording_worker
from VoiceSTT.core.wake_audio_boundary import WakeAudioBoundary
from VoiceSTT.core.wake_detection import (
    WakeAttemptPolicy,
    WakeDetectionEvaluator,
)
from api_fastapi_server.activation import ActivationController
from api_fastapi_server.wake_admission import WakeAdmissionCoordinator


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
    recorder.accepted_wake_detection = None
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


class RetainedHistoryModel(ScriptedModel):
    """A real input hit leaves delayed feature history, not just a cached score."""

    def __init__(self):
        super().__init__([])
        self._audio = b""
        self._tail = collections.deque()
        self.reset_calls = 0

    def predict(self, pcm):
        self.predict_calls += 1
        self._audio += np.asarray(pcm, dtype=np.int16).tobytes()
        produced = False
        while len(self._audio) >= 2 * PREDICTION_FRAME_SAMPLES:
            frame, self._audio = (
                self._audio[:2 * PREDICTION_FRAME_SAMPLES],
                self._audio[2 * PREDICTION_FRAME_SAMPLES:],
            )
            if np.any(np.frombuffer(frame, dtype=np.int16) == 1):
                score = 0.91
                self._tail = collections.deque([0.0, 0.83, 0.0])
            else:
                score = self._tail.popleft() if self._tail else 0.0
            self.prediction_buffer[self.model_key].append(score)
            produced = True
        if not produced:
            values = self.prediction_buffer[self.model_key]
            values.append(values[-1] if values else 0.0)

    def reset(self):
        self.reset_calls += 1
        self._audio = b""
        self._tail.clear()
        self.prediction_buffer[self.model_key].clear()


class WakeRearmRegressionTests(unittest.TestCase):
    def build(self, *, policy=None, selection=None):
        self.clock = 0.0
        self.policy = policy or WakeAttemptPolicy()
        self.model = RetainedHistoryModel()
        self.engine = OpenWakeWordEngine(
            selection=selection or FakeSelection(),
            model_factory=lambda **_kwargs: self.model,
        )
        self.evaluator = WakeDetectionEvaluator(
            engine=self.engine, policy_supplier=lambda: self.policy,
            clock=lambda: self.clock,
        )
        self.controller = ActivationController(
            manual_trigger_enabled=True, wake_word_trigger_enabled=True,
            clock=lambda: self.clock,
        )
        self.delivered = []
        self.coordinator = WakeAdmissionCoordinator(
            evaluator=self.evaluator, activate=self.activate,
            publish=self.delivered.append,
        )
        self.position = 0

    def activate(self, _hit, _boundary):
        decision = self.controller.activate("wake_word")
        return decision.snapshot["activationId"] if decision.accepted else None

    def feed(self, data, *, admit=True):
        self.position += len(data) // 2
        hits = self.evaluator.process(data, end_sample=self.position)
        return [
            self.coordinator.admit(hit) if admit else hit for hit in hits
        ]

    def speak(self):
        self.feed(np.ones(CHUNK_SAMPLES, dtype=np.int16).tobytes())
        return self.feed(CHUNK)

    def close_input(self, path="finish"):
        snapshot = self.controller.snapshot()
        activation_id = snapshot["activationId"]
        if path in ("finish", "cancel"):
            decision = getattr(self.controller, path)(activation_id=activation_id)
        else:
            if path == "followup_timeout":
                self.controller.recording_started()
                self.controller.recording_ended()
            snapshot = self.controller.snapshot()
            self.clock = snapshot["deadline"]
            decision = self.controller.tick(snapshot["timerToken"])
        self.assertTrue(decision.accepted)
        decision = self.controller.input_closed(
            activation_id=activation_id,
            activation_sequence=snapshot["activationSequence"],
        )
        self.assertTrue(decision.accepted)
        return activation_id

    def test_input_close_then_digital_silence_never_opens_a_second_activation(self):
        controller = ActivationController(
            manual_trigger_enabled=True, wake_word_trigger_enabled=True
        )
        accepted = []
        closed = []

        def activate(_hit, _boundary):
            decision = controller.activate("wake_word")
            return decision.snapshot["activationId"] if decision.accepted else None

        recorder = build_recorder(0, admission=lambda *_args: None)
        model = RetainedHistoryModel()
        engine = OpenWakeWordEngine(
            selection=FakeSelection(), model_factory=lambda **_kwargs: model
        )
        recorder.wake_engine = engine
        evaluator = WakeDetectionEvaluator(engine=engine)
        recorder.wake_detection_evaluator = evaluator
        coordinator = WakeAdmissionCoordinator(
            evaluator=evaluator, activate=activate, publish=accepted.append
        )
        recorder.on_wakeword_detected = coordinator.admit

        # The first two chunks finalize the genuine hit. The activation stays
        # open for ten more chunks, which the production worker must not infer.
        recorder.audio_queue.put(np.ones(CHUNK_SAMPLES, dtype=np.int16).tobytes())
        for _ in range(25):
            recorder.audio_queue.put(CHUNK)

        def close_on_chunk(_data):
            if len(recorder.last_words_buffer) != 13:
                return
            self.assertEqual(model.predict_calls, 2)
            activation_id = controller.snapshot()["activationId"]
            controller.finish(activation_id=activation_id)
            decision = controller.input_closed(
                activation_id=activation_id,
                activation_sequence=controller.snapshot()["activationSequence"],
            )
            self.assertTrue(decision.accepted)
            closed.append(activation_id)
            self.assertTrue(coordinator.release(activation_id))
            recorder.wakeword_detected = False
            recorder.wake_word_detect_time = 0

        recorder.on_recorded_chunk = close_on_chunk
        drain(recorder)

        self.assertEqual(len(closed), 1)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(coordinator.logical_event_count(), 1)
        self.assertEqual(controller.snapshot()["phase"], "idle")

    def test_repeated_close_paths_allow_immediate_new_speech_without_history(self):
        self.build()
        for cycle, path in enumerate(
            ("finish", "cancel", "initial_timeout", "followup_timeout") * 3
        ):
            with self.subTest(cycle=cycle, path=path):
                self.assertEqual(len(self.speak()), 1)
                before = self.model.predict_calls
                self.assertEqual(self.feed(CHUNK * 20), [])
                self.assertEqual(self.model.predict_calls, before)
                activation_id = self.close_input(path)
                self.assertTrue(self.coordinator.release(activation_id))
                self.assertFalse(self.coordinator.release(activation_id))
                self.assertEqual(self.model.reset_calls, cycle + 1)
                self.assertEqual(self.feed(CHUNK * 4), [])
                self.assertEqual(len(self.delivered), cycle + 1)
        # No clock advance after release and no synthetic cooldown.
        self.assertEqual(len(self.speak()), 1)
        self.assertEqual(len(self.delivered), 13)
        self.assertEqual(self.coordinator.logical_event_count(), 13)

    def test_partial_prediction_history_is_discarded_for_20_40_80_ms_chunks(self):
        for samples in (320, 640, 1280):
            with self.subTest(samples=samples):
                self.build()
                self.feed(np.ones(CHUNK_SAMPLES, dtype=np.int16).tobytes())
                # A finalized hit and 20 ms of not-yet-inferred old audio.
                accepted = self.feed(CHUNK + CHUNK[:640])[0]
                self.assertEqual(self.engine.diagnostics()["pendingSamples"], 320)
                self.close_input()
                self.coordinator.release(accepted.activation_id)
                self.assertEqual(self.engine.diagnostics()["pendingSamples"], 0)
                frame_index = self.engine.frame_index
                for index in range(1280 // samples):
                    self.assertEqual(self.feed(b"\x01\x00" * samples), [])
                    self.assertEqual(
                        self.engine.frame_index - frame_index,
                        1 if index == 1280 // samples - 1 else 0,
                    )
                hits = []
                for _ in range(1280 // samples):
                    hits.extend(self.feed(b"\0\0" * samples))
                self.assertEqual(len(hits), 1)
                self.assertEqual(hits[0].wake_hit.prediction_frame_count, 1)
                self.assertEqual(hits[0].score, 0.91)

    def test_rearm_boundary_uses_stream_cursor_and_keeps_first_user_samples(self):
        for pre_roll_ms in (0, 10, 10000):
            with self.subTest(pre_roll_ms=pre_roll_ms):
                detections = []
                recorder = build_recorder(
                    0, admission=None, pre_roll_ms=pre_roll_ms
                )
                model = RetainedHistoryModel()
                recorder.wake_detection_evaluator = WakeDetectionEvaluator(
                    engine=OpenWakeWordEngine(
                        selection=FakeSelection(),
                        model_factory=lambda **_kwargs: model,
                    ),
                    policy_supplier=lambda: WakeAttemptPolicy(
                        pre_roll_ms=pre_roll_ms
                    ),
                )
                evaluator = recorder.wake_detection_evaluator

                def admit(hit, boundary):
                    detection = evaluator.accept(
                        hit, activation_id=f"act-{len(detections)}",
                        boundary=boundary,
                    )
                    detections.append(detection)
                    return detection

                recorder.on_wakeword_detected = admit
                wake = b"\x01\x00" * CHUNK_SAMPLES
                speech = b"\x02\x00" * CHUNK_SAMPLES
                for data in [wake, CHUNK] + [CHUNK] * 100 + [wake, speech, speech]:
                    recorder.audio_queue.put(data)

                def advance(_data):
                    index = len(recorder.last_words_buffer)
                    if index == 103:
                        evaluator.release_latch(activation_id="act-0")
                        # A delayed worker write must not re-latch v2 detection.
                        recorder.wakeword_detected = True
                    elif index == 105:
                        recorder.frames = list(recorder.audio_buffer)
                        recorder.is_recording = True
                        recorder.stop_recording_on_voice_deactivity = False

                recorder.on_recorded_chunk = advance
                drain(recorder)
                self.assertEqual(len(detections), 2)
                boundary = detections[1].boundary
                zero_point = 103 * CHUNK_SAMPLES
                self.assertEqual(
                    detections[1].wake_hit.operational_zero_point_sample,
                    zero_point,
                )
                self.assertEqual(boundary.operational_zero_point_sample, zero_point)
                self.assertEqual(
                    boundary.release_sample,
                    max(boundary.history_start_sample,
                        zero_point - pre_roll_ms * 16),
                )
                retained = b"".join(recorder.frames)
                self.assertTrue(retained.endswith(speech * 2))
                self.assertEqual(
                    len(retained) // 2,
                    105 * CHUNK_SAMPLES - boundary.release_sample,
                )
                if pre_roll_ms == 0:
                    self.assertEqual(retained, speech * 2)
                elif pre_roll_ms == 10:
                    self.assertEqual(retained, wake[-320:] + speech * 2)
                else:
                    self.assertTrue(boundary.pre_roll_clamped)

    def test_reset_failure_blocks_only_wake_and_can_be_retried_explicitly(self):
        self.build()
        first = self.speak()[0]
        self.close_input()
        with mock.patch.object(self.model, "reset", side_effect=RuntimeError("reset failed")):
            with self.assertLogs("voicestt", level="ERROR"):
                self.assertFalse(self.coordinator.release(first.activation_id))
            self.assertTrue(self.evaluator.latched)
            self.assertEqual(self.feed(CHUNK * 20), [])
            self.assertIsNone(self.coordinator.admit(first.wake_hit))
            self.assertEqual(len(self.delivered), 1)
            self.assertTrue(self.controller.activate("manual").accepted)
            self.assertEqual(self.controller.snapshot()["primarySource"], "manual")
            with self.assertLogs("voicestt", level="ERROR"):
                self.coordinator.reset()
            self.assertTrue(self.engine.diagnostics()["resetFailed"])
            self.assertEqual(self.engine.process(CHUNK * 20), ())
            self.assertEqual(self.speak(), [])
        self.coordinator.reset()
        self.controller.reset()
        self.assertEqual(len(self.speak()), 1)

    def test_missing_reset_is_not_a_successful_rearm(self):
        self.build()
        first = self.speak()[0]
        self.close_input()
        self.model.reset = None
        with self.assertLogs("voicestt", level="ERROR"):
            self.assertFalse(self.coordinator.release(first.activation_id))
        self.assertEqual(self.feed(CHUNK * 10), [])
        self.assertEqual(len(self.delivered), 1)

    def test_rearm_is_independent_of_the_selected_catalog_word(self):
        manifest = (
            Path(__file__).resolve().parents[2] / "VoiceSTT" / "assets"
            / "wakeword_models" / "models.json"
        )
        identifiers = [
            entry["id"] for entry in json.loads(manifest.read_text())["wakeWords"]
        ]
        self.assertIn("alexa", identifiers)
        self.assertIn("hey_jarvis", identifiers)
        for identifier in identifiers:
            with self.subTest(identifier=identifier):
                selection = FakeSelection()
                selection.wake_word_ids = (identifier,)
                selection.model_key_to_id = {"jarvis_v2": identifier}
                self.build(selection=selection)
                first = self.speak()[0]
                self.close_input()
                self.coordinator.release(first.activation_id)
                self.assertEqual(self.feed(CHUNK * 10), [])
                second = self.speak()[0]
                self.assertEqual(second.canonical_wake_word_id, identifier)
                self.assertEqual(len(self.delivered), 2)

    def test_configured_cooldown_and_next_attempt_snapshot_survive_rearm(self):
        self.build(policy=WakeAttemptPolicy(cooldown_ms=2000))
        first = self.speak()[0]
        self.close_input()
        self.coordinator.release(first.activation_id)
        self.policy = WakeAttemptPolicy(
            sensitivity=0.8, min_consecutive_prediction_frames=2,
            pre_roll_ms=320, detector_gain=1.0, settings_revision=7,
        )
        self.assertEqual(self.speak(), [])  # only one frame >= threshold
        self.feed(CHUNK * 4)
        self.feed(b"\x01\x00" * CHUNK_SAMPLES * 2)
        self.assertEqual(self.feed(CHUNK), [])  # configured cooldown still active
        self.feed(CHUNK * 4)
        self.clock = 2.0
        self.feed(b"\x01\x00" * CHUNK_SAMPLES * 2)
        second = self.feed(CHUNK)[0]
        self.assertEqual(second.wake_hit.policy, self.policy)
        self.assertEqual(second.wake_hit.prediction_frame_count, 2)
        self.assertEqual(second.score, 0.91)
        self.assertEqual(len(self.delivered), 2)

    def test_old_hits_and_close_callbacks_cannot_affect_a_new_generation(self):
        self.build()
        old_hit = self.feed(
            b"\x01\x00" * CHUNK_SAMPLES + CHUNK, admit=False
        )[0]
        self.coordinator.reset()
        self.assertIsNone(self.coordinator.admit(old_hit))
        self.assertEqual(self.controller.snapshot()["phase"], "idle")
        current = self.speak()[0]
        resets = self.model.reset_calls
        self.assertFalse(self.coordinator.release("old-activation"))
        self.assertEqual(self.model.reset_calls, resets)
        self.assertEqual(self.evaluator.latched_activation_id, current.activation_id)
        self.assertEqual(len(self.delivered), 1)

    def test_a_queued_hit_cannot_be_reused_after_an_accepted_activation_closes(self):
        self.build()
        old_hit = self.feed(
            b"\x01\x00" * CHUNK_SAMPLES + CHUNK, admit=False
        )[0]
        accepted = self.coordinator.admit(old_hit)
        self.close_input()
        self.coordinator.release(accepted.activation_id)
        self.assertIsNone(self.coordinator.admit(old_hit))
        self.assertEqual(len(self.delivered), 1)

    def test_inference_and_generation_reset_are_serialized_without_stale_admission(self):
        self.build()
        self.feed(b"\x01\x00" * CHUNK_SAMPLES)
        entered = threading.Event()
        resume = threading.Event()
        reset_started = threading.Event()
        reset_done = threading.Event()
        hits = []
        errors = []
        original = self.model.predict

        def predict(data):
            entered.set()
            if not resume.wait(5):
                raise AssertionError("inference was never resumed")
            return original(data)

        def infer():
            try:
                hits.extend(self.feed(CHUNK, admit=False))
            except Exception as exc:
                errors.append(exc)

        def reset():
            reset_started.set()
            try:
                self.coordinator.reset()
            except Exception as exc:
                errors.append(exc)
            reset_done.set()

        with mock.patch.object(self.model, "predict", side_effect=predict):
            worker = threading.Thread(target=infer, daemon=True)
            worker.start()
            self.assertTrue(entered.wait(5))
            resetter = threading.Thread(target=reset, daemon=True)
            resetter.start()
            self.assertTrue(reset_started.wait(5))
            self.assertFalse(reset_done.is_set())
            resume.set()
            for thread in (worker, resetter):
                thread.join(5)
                self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(hits), 1)
        self.assertIsNone(self.coordinator.admit(hits[0]))
        self.assertEqual(self.feed(CHUNK * 10), [])
        self.assertEqual(len(self.speak()), 1)

    def test_rearm_reset_cannot_overlap_direct_engine_inference(self):
        self.build()
        first = self.speak()[0]
        self.close_input()
        entered = threading.Event()
        resume = threading.Event()
        release_started = threading.Event()
        result = []
        original = self.model.predict

        def predict(data):
            entered.set()
            if not resume.wait(5):
                raise AssertionError("inference was never resumed")
            return original(data)

        def release():
            release_started.set()
            result.append(self.coordinator.release(first.activation_id))

        with mock.patch.object(self.model, "predict", side_effect=predict):
            inference = threading.Thread(
                target=lambda: self.engine.process(CHUNK), daemon=True
            )
            inference.start()
            self.assertTrue(entered.wait(5))
            releaser = threading.Thread(target=release, daemon=True)
            releaser.start()
            self.assertTrue(release_started.wait(5))
            self.assertEqual(self.model.reset_calls, 0)
            resume.set()
            for thread in (inference, releaser):
                thread.join(5)
                self.assertFalse(thread.is_alive())
        self.assertEqual(result, [True])
        self.assertEqual(self.feed(CHUNK * 10), [])

    def test_close_before_the_admission_callback_returns_leaves_no_stale_boundary(self):
        recorder = build_recorder(0, admission=None)
        model = RetainedHistoryModel()
        evaluator = WakeDetectionEvaluator(engine=OpenWakeWordEngine(
            selection=FakeSelection(), model_factory=lambda **_kwargs: model,
        ))
        recorder.wake_detection_evaluator = evaluator

        def close_before_return(hit, boundary):
            accepted = evaluator.accept(hit, activation_id="closed", boundary=boundary)
            evaluator.release_latch(activation_id="closed")
            return accepted

        recorder.on_wakeword_detected = close_before_return
        self.assertIsNone(_wake_detection_step(
            recorder, b"\x01\x00" * CHUNK_SAMPLES, 0, CHUNK_SAMPLES
        ))
        self.assertIsNone(_wake_detection_step(
            recorder, CHUNK, 1, CHUNK_SAMPLES * 2
        ))
        self.assertFalse(evaluator.latched)
        self.assertIsNone(recorder.accepted_wake_detection)
        self.assertIsNone(recorder.wake_audio_boundary)


if __name__ == "__main__":
    unittest.main()
