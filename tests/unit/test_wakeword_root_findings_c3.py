"""AP-SRV-060 C3: the Root corrections F11-F15 and the C3 detection semantics.

Every test here was written RED-first against the C2 code: it reproduces the
behaviour Root rejected and pins the corrected C3 semantics afterwards. The
RED/GREEN matrix is in
``docs/.archiv/.../AP-SRV-060/runs/03_ROOT_CORRECTION/2026-08-28_REPORT.md``.

The five findings, in the order the prompt names them:

F11
    one wake attempt must not mix settings revisions;
F12
    runtime/loadability authority - availability is a *common backend* answer,
    never "the probe was skipped because the runtime did not import";
F13
    exactly one *logical* ``wakeword.detected`` per accepted wake hit, with
    fallible transport delivery separated from the logical mint;
F14
    real state-changing refresh races (A -> B), not A -> A;
F15
    contract/documentation correction of the detection semantics.
"""

import json
import tempfile
import threading
import unittest
from pathlib import Path

import numpy as np

from api_fastapi_server import settings_control as sc
from api_fastapi_server.protocol_v2 import ports
from api_fastapi_server.wake_admission import (
    LogicalWakeEventLedger,
    WakeActivationOutcome,
    WakeAdmissionCoordinator,
)
from VoiceSTT.core import wake_backend
from VoiceSTT.core.openwakeword_engine import (
    PREDICTION_FRAME_SAMPLES,
    OpenWakeWordEngine,
)
from VoiceSTT.core.wake_audio_boundary import (
    BASIS_OPERATIONAL_ZERO_POINT,
    resolve_wake_audio_boundary,
)
from VoiceSTT.core.wake_detection import (
    AcceptedWakeDetection,
    WakeAttemptPolicy,
    WakeDetectionEvaluator,
    WakeHit,
    WakeHitTracker,
    arbitrate_finalized,
)
from VoiceSTT.core.wakeword_catalog import (
    REASON_ARTIFACT_INTEGRITY,
    REASON_ARTIFACT_UNLOADABLE,
    REASON_BACKEND_UNAVAILABLE,
    REASON_NO_COMMON_BACKEND,
    REASON_RUNTIME_UNAVAILABLE,
    WakeWordCatalogAuthority,
)

from .wake_catalog_support import FakeCatalogService, build_bundle


REPO_ROOT = Path(__file__).resolve().parents[2]

ENTRIES = (
    ("hey_jarvis", "Hey Jarvis", ("jarvis",), "jarvis_v2.onnx"),
    ("alexa", "Alexa", (), "alexa.onnx"),
)


def policy(**kwargs):
    values = {
        "sensitivity": 0.70,
        "min_consecutive_prediction_frames": 10,
        "detector_gain": 1.0,
        "cooldown_ms": 0,
        "pre_roll_ms": 0,
        "settings_revision": 1,
    }
    values.update(kwargs)
    return WakeAttemptPolicy(**values)


def feed(tracker, scores_per_frame):
    """Feeds a script of per-frame score maps and returns the finalized hits."""
    hits = []
    end_sample = 0
    for scores in scores_per_frame:
        end_sample += PREDICTION_FRAME_SAMPLES
        hit = tracker.observe(scores, end_sample=end_sample)
        if hit is not None:
            hits.append(hit)
    return hits


def run(word, values):
    return [{word: value} for value in values]


# -- 1. WakeHitTracker ---------------------------------------------------------

class WakeHitTrackerTests(unittest.TestCase):
    """The eleven cases of the C3 required test matrix, section WakeHitTracker."""

    def setUp(self):
        self.policy = policy()
        self.tracker = WakeHitTracker(policy_supplier=lambda: self.policy)

    def test_1_nine_qualifying_frames_below_the_minimum_are_no_hit(self):
        hits = feed(self.tracker, run("alexa", [0.80] * 9 + [0.10]))
        self.assertEqual(hits, [])

    def test_2_exactly_the_minimum_then_below_finalizes_one_hit(self):
        hits = feed(self.tracker, run("alexa", [0.80] * 10 + [0.10]))
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].canonical_wake_word_id, "alexa")
        self.assertEqual(hits[0].prediction_frame_count, 10)

    def test_3_thirty_frames_above_the_threshold_are_still_one_hit(self):
        hits = feed(self.tracker, run("alexa", [0.80] * 30 + [0.10]))
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].prediction_frame_count, 30)

    def test_3b_the_prompt_example_sequence_is_one_hit_not_thirteen_events(self):
        scores = [0.73, 0.78, 0.81, 0.85, 0.88, 0.90, 0.91, 0.89, 0.86, 0.83,
                  0.79, 0.75, 0.71, 0.62]
        hits = feed(self.tracker, run("alexa", scores))
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].prediction_frame_count, 13)
        self.assertAlmostEqual(hits[0].peak_score, 0.91)

    def test_4_an_interrupted_run_resets_before_qualification(self):
        script = run("alexa", [0.80] * 9 + [0.10] + [0.80] * 9 + [0.10])
        self.assertEqual(feed(self.tracker, script), [])

    def test_5_the_qualification_frame_is_the_minimum_th_frame(self):
        hits = feed(self.tracker, run("alexa", [0.80] * 12 + [0.10]))
        hit = hits[0]
        self.assertEqual(hit.start_frame_index, 0)
        self.assertEqual(hit.qualification_frame_index, 9)
        self.assertEqual(
            hit.qualification_sample, 10 * PREDICTION_FRAME_SAMPLES
        )

    def test_6_finalization_happens_at_the_trailing_edge(self):
        hits = feed(self.tracker, run("alexa", [0.80] * 12 + [0.10]))
        hit = hits[0]
        self.assertEqual(hit.finalization_frame_index, 12)
        # The operational zero point is the last frame >= threshold.
        self.assertEqual(
            hit.operational_zero_point_sample, 12 * PREDICTION_FRAME_SAMPLES
        )

    def test_7_the_first_finalized_hit_wins(self):
        script = [{"alexa": 0.80, "alexander": 0.80} for _ in range(12)]
        script.append({"alexa": 0.10, "alexander": 0.80})
        script.append({"alexa": 0.10, "alexander": 0.10})
        hits = feed(self.tracker, script)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].canonical_wake_word_id, "alexa")

    def test_8_a_same_frame_tie_prefers_the_earlier_qualification(self):
        script = [{"early": 0.80}, {"early": 0.80}]
        script.extend({"early": 0.80, "late": 0.80} for _ in range(10))
        script.append({"early": 0.10, "late": 0.10})
        hits = feed(self.tracker, script)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].canonical_wake_word_id, "early")

    def test_9_an_equal_qualification_prefers_the_earlier_start(self):
        """Rule 2 of the deterministic tie-breaker chain, tested directly.

        Under one shared minimum an equal qualification frame implies an equal
        start, so this ordering rule is a defensive determinism guarantee. It
        is therefore proven against the arbitration function itself.
        """
        early = synthetic_hit("zulu", start=2, qualification=11, finalization=20)
        late = synthetic_hit("alpha", start=5, qualification=11, finalization=20)
        self.assertEqual(
            arbitrate_finalized([late, early]).canonical_wake_word_id, "zulu"
        )
        self.assertEqual(
            arbitrate_finalized([early, late]).canonical_wake_word_id, "zulu"
        )

    def test_9b_an_earlier_qualification_beats_a_smaller_id(self):
        first = synthetic_hit("zulu", start=0, qualification=9, finalization=20)
        second = synthetic_hit("alpha", start=2, qualification=11, finalization=20)
        self.assertEqual(
            arbitrate_finalized([second, first]).canonical_wake_word_id, "zulu"
        )

    def test_10_a_full_tie_is_broken_by_the_canonical_id(self):
        script = [{"zulu": 0.80, "alpha": 0.80} for _ in range(10)]
        script.append({"zulu": 0.10, "alpha": 0.10})
        hits = feed(self.tracker, script)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].canonical_wake_word_id, "alpha")
        # The rule is stable, not dictionary-order dependent.
        tracker = WakeHitTracker(policy_supplier=lambda: self.policy)
        script = [{"alpha": 0.80, "zulu": 0.80} for _ in range(10)]
        script.append({"alpha": 0.10, "zulu": 0.10})
        hits = feed(tracker, script)
        self.assertEqual(hits[0].canonical_wake_word_id, "alpha")

    def test_10b_the_losing_candidates_of_one_decision_are_discarded(self):
        script = [{"alpha": 0.80, "zulu": 0.80} for _ in range(10)]
        script.append({"alpha": 0.10, "zulu": 0.80})
        script.append({"alpha": 0.10, "zulu": 0.10})
        hits = feed(self.tracker, script)
        self.assertEqual([hit.canonical_wake_word_id for hit in hits], ["alpha"])

    def test_11_one_finalized_hit_yields_at_most_one_domain_event(self):
        evaluator = WakeDetectionEvaluator(policy_supplier=lambda: self.policy)
        offered = []
        for scores in run("alexa", [0.80] * 30 + [0.10]):
            hit = evaluator.observe_scores(scores)
            if hit is not None:
                offered.append(hit)
        self.assertEqual(len(offered), 1)

    def test_a_run_that_never_drops_never_finalizes(self):
        hits = feed(self.tracker, run("alexa", [0.80] * 50))
        self.assertEqual(hits, [])
        self.assertTrue(self.tracker.active)

    def test_a_minimum_of_one_still_groups_a_whole_run(self):
        tracker = WakeHitTracker(
            policy_supplier=lambda: policy(min_consecutive_prediction_frames=1)
        )
        hits = feed(tracker, run("alexa", [0.80] * 7 + [0.10]))
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].prediction_frame_count, 7)


def synthetic_hit(word, *, start, qualification, finalization):
    return WakeHit(
        canonical_wake_word_id=word,
        peak_score=0.9,
        start_frame_index=start,
        start_sample=(start + 1) * PREDICTION_FRAME_SAMPLES,
        qualification_frame_index=qualification,
        qualification_sample=(qualification + 1) * PREDICTION_FRAME_SAMPLES,
        finalization_frame_index=finalization,
        operational_zero_point_sample=finalization * PREDICTION_FRAME_SAMPLES,
        prediction_frame_count=finalization - start,
        policy=policy(),
    )


# -- 2. prediction frames, not recorder chunks ---------------------------------

class FakeUpstreamModel:
    """Emulates ``openwakeword.Model`` including its cached-score behaviour.

    The real upstream model buffers audio internally and only produces a new
    prediction every 1280 samples; a shorter chunk re-appends the previous
    score. Counting prediction-buffer entries would therefore over-count, which
    is exactly what C3 section 8 forbids.
    """

    def __init__(self, scripted_scores=(), **kwargs):
        self.kwargs = dict(kwargs)
        self.model_key = "jarvis_v2"
        self.models = {self.model_key: object()}
        self.model_inputs = {self.model_key: 16}
        self.prediction_buffer = {self.model_key: []}
        self.scripted = list(scripted_scores or [])
        self.received = []
        self._pending = 0
        self._produced = 0

    def predict(self, pcm):
        array = np.asarray(pcm)
        self.received.append(array.copy())
        self._pending += int(array.shape[0])
        produced = 0
        while self._pending >= PREDICTION_FRAME_SAMPLES:
            self._pending -= PREDICTION_FRAME_SAMPLES
            if self._produced < len(self.scripted):
                score = float(self.scripted[self._produced])
            else:
                score = 0.0
            self._produced += 1
            self.prediction_buffer[self.model_key].append(score)
            produced += 1
        if produced == 0:
            # Upstream re-appends the last known score for a short chunk.
            scores = self.prediction_buffer[self.model_key]
            scores.append(scores[-1] if scores else 0.0)
        return {self.model_key: self.prediction_buffer[self.model_key][-1]}

    def reset(self):
        self.prediction_buffer[self.model_key].clear()


class FakeSelection:
    """The minimum of a ``WakeWordSelection`` the engine consumes."""

    def __init__(self, backend="onnx"):
        self.backend = backend
        self.wake_word_ids = ("hey_jarvis",)
        self.model_paths = ("jarvis_v2.onnx",)
        self.model_key_to_id = {"jarvis_v2": "hey_jarvis"}

    def loader_kwargs(self):
        return {
            "wakeword_models": list(self.model_paths),
            "inference_framework": self.backend,
            "melspec_model_path": "melspectrogram.onnx",
            "embedding_model_path": "embedding_model.onnx",
        }


def build_engine(scripted=(), **kwargs):
    holder = {}

    def factory(**model_kwargs):
        model = FakeUpstreamModel(scripted_scores=list(scripted), **model_kwargs)
        holder["model"] = model
        return model

    engine = OpenWakeWordEngine(
        selection=FakeSelection(), model_factory=factory, **kwargs
    )
    return engine, holder["model"]


def pcm(samples, value=1000):
    return np.full(samples, value, dtype=np.int16).tobytes()


class PredictionFrameTests(unittest.TestCase):
    def test_short_recorder_chunks_do_not_advance_the_frame_counter(self):
        engine, model = build_engine(scripted=[0.9] * 8)
        # 20 ms at 16 kHz = 320 samples: four of them make one 1280 sample
        # prediction frame.
        self.assertEqual(engine.process(pcm(320)), ())
        self.assertEqual(engine.process(pcm(320)), ())
        self.assertEqual(engine.process(pcm(320)), ())
        frames = engine.process(pcm(320))
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].index, 0)
        self.assertEqual(frames[0].end_sample, PREDICTION_FRAME_SAMPLES)
        self.assertAlmostEqual(frames[0].scores["hey_jarvis"], 0.9)
        # The upstream buffer grew on every call; the engine did not.
        self.assertEqual(len(model.prediction_buffer["jarvis_v2"]), 4)

    def test_forty_millisecond_chunks_yield_one_frame_every_two_chunks(self):
        engine, _model = build_engine(scripted=[0.5, 0.6, 0.7])
        counts = [len(engine.process(pcm(640))) for _ in range(6)]
        self.assertEqual(counts, [0, 1, 0, 1, 0, 1])

    def test_one_large_chunk_yields_every_distinct_frame_in_order(self):
        engine, _model = build_engine(scripted=[0.1, 0.2, 0.3])
        frames = engine.process(pcm(PREDICTION_FRAME_SAMPLES * 3))
        self.assertEqual([frame.index for frame in frames], [0, 1, 2])
        self.assertEqual(
            [round(frame.scores["hey_jarvis"], 3) for frame in frames],
            [0.1, 0.2, 0.3],
        )
        self.assertEqual(
            [frame.end_sample for frame in frames],
            [PREDICTION_FRAME_SAMPLES * n for n in (1, 2, 3)],
        )

    def test_a_repeated_cached_score_is_never_counted_twice(self):
        engine, model = build_engine(scripted=[0.95])
        engine.process(pcm(PREDICTION_FRAME_SAMPLES))
        for _ in range(5):
            self.assertEqual(engine.process(pcm(64)), ())
        self.assertEqual(engine.frame_index, 1)
        self.assertGreater(len(model.prediction_buffer["jarvis_v2"]), 1)

    def test_only_selected_model_keys_become_scores(self):
        engine, model = build_engine(scripted=[0.9])
        model.prediction_buffer["stray_model"] = [0.99]
        frames = engine.process(pcm(PREDICTION_FRAME_SAMPLES))
        self.assertEqual(set(frames[0].scores), {"hey_jarvis"})


# -- 3. detector gain gate ------------------------------------------------------

class DetectorGainTests(unittest.TestCase):
    def test_the_original_pcm_buffer_is_byte_identical_after_a_gain_pass(self):
        engine, _model = build_engine(scripted=[0.9])
        original = pcm(PREDICTION_FRAME_SAMPLES, value=1000)
        snapshot = bytes(original)
        engine.process(original, gain=2.0)
        self.assertEqual(original, snapshot)

    def test_only_the_inference_copy_carries_the_gain(self):
        engine, model = build_engine(scripted=[0.9])
        engine.process(pcm(PREDICTION_FRAME_SAMPLES, value=1000), gain=2.0)
        self.assertEqual(int(model.received[0][0]), 2000)

    def test_the_gain_copy_saturates_instead_of_wrapping(self):
        engine, model = build_engine(scripted=[0.9])
        engine.process(pcm(PREDICTION_FRAME_SAMPLES, value=30000), gain=3.0)
        self.assertEqual(int(model.received[0].max()), 32767)
        engine.process(pcm(PREDICTION_FRAME_SAMPLES, value=-30000), gain=3.0)
        self.assertEqual(int(model.received[1].min()), -32768)

    def test_a_neutral_gain_does_not_change_a_single_sample(self):
        engine, model = build_engine(scripted=[0.9])
        payload = pcm(PREDICTION_FRAME_SAMPLES, value=-1234)
        engine.process(payload, gain=1.0)
        self.assertTrue(
            np.array_equal(
                model.received[0], np.frombuffer(payload, dtype=np.int16)
            )
        )


# -- 4. VAD / noise suppression architecture gate -------------------------------

class WakeDetectorVadTests(unittest.TestCase):
    def test_the_engine_hands_the_vad_gate_to_the_upstream_model(self):
        _engine, model = build_engine(vad_threshold=0.4)
        self.assertEqual(model.kwargs.get("vad_threshold"), 0.4)

    def test_a_zero_threshold_disables_the_upstream_vad_gate(self):
        _engine, model = build_engine(vad_threshold=0.0)
        self.assertEqual(model.kwargs.get("vad_threshold"), 0.0)

    def test_noise_suppression_uses_the_upstream_speex_support(self):
        _engine, model = build_engine(noise_suppression_enabled=True)
        self.assertTrue(model.kwargs.get("enable_speex_noise_suppression"))

    def test_the_engine_holds_exactly_one_upstream_model(self):
        engine, model = build_engine()
        self.assertIs(engine.model, model)
        self.assertEqual(engine.backend, "onnx")

    def test_the_wake_detector_has_no_second_activation_lifecycle(self):
        """A latched detection stops offering: there is one lifecycle only."""
        evaluator = WakeDetectionEvaluator(
            policy_supplier=lambda: policy(min_consecutive_prediction_frames=1)
        )
        hit = None
        for scores in run("alexa", [0.9, 0.1]):
            hit = evaluator.observe_scores(scores) or hit
        self.assertIsNotNone(hit)
        evaluator.accept(hit, activation_id="act-1")
        for scores in run("alexa", [0.9] * 20 + [0.1]):
            self.assertIsNone(evaluator.observe_scores(scores))


# -- 5. F11: one wake attempt, one settings revision ----------------------------

class F11AttemptSnapshotTests(unittest.TestCase):
    """RED against C2: the pre-roll/threshold were re-read mid-utterance."""

    def test_the_attempt_snapshot_carries_every_wake_value_and_the_revision(self):
        snapshot = policy()
        for name in ("settings_revision", "sensitivity",
                     "min_consecutive_prediction_frames", "detector_gain",
                     "cooldown_ms", "pre_roll_ms"):
            self.assertTrue(hasattr(snapshot, name), name)

    def test_a_running_hit_region_keeps_the_revision_it_started_with(self):
        current = {"policy": policy(settings_revision=7, sensitivity=0.70)}
        tracker = WakeHitTracker(policy_supplier=lambda: current["policy"])
        end_sample = 0
        for _index in range(4):
            end_sample += PREDICTION_FRAME_SAMPLES
            tracker.observe({"alexa": 0.80}, end_sample=end_sample)
        # The barrier: a patch lands in the middle of the same hit region.
        current["policy"] = policy(settings_revision=8, sensitivity=0.95)
        hit = None
        for _index in range(6):
            end_sample += PREDICTION_FRAME_SAMPLES
            hit = tracker.observe({"alexa": 0.80}, end_sample=end_sample) or hit
        end_sample += PREDICTION_FRAME_SAMPLES
        hit = tracker.observe({"alexa": 0.10}, end_sample=end_sample) or hit
        self.assertIsNotNone(hit)
        self.assertEqual(hit.policy.settings_revision, 7)
        self.assertAlmostEqual(hit.policy.sensitivity, 0.70)
        self.assertEqual(hit.prediction_frame_count, 10)

    def test_a_discarded_attempt_lets_the_next_one_take_the_new_revision(self):
        current = {"policy": policy(settings_revision=7)}
        tracker = WakeHitTracker(policy_supplier=lambda: current["policy"])
        end_sample = 0
        for score in (0.80, 0.80, 0.10):
            end_sample += PREDICTION_FRAME_SAMPLES
            tracker.observe({"alexa": score}, end_sample=end_sample)
        current["policy"] = policy(settings_revision=8)
        hit = None
        for score in [0.80] * 10 + [0.10]:
            end_sample += PREDICTION_FRAME_SAMPLES
            hit = tracker.observe({"alexa": score}, end_sample=end_sample) or hit
        self.assertEqual(hit.policy.settings_revision, 8)

    def test_the_evaluator_binds_gain_and_threshold_to_one_revision(self):
        current = {"policy": policy(settings_revision=3, detector_gain=1.0)}
        engine, model = build_engine(scripted=[0.8] * 12 + [0.1])
        evaluator = WakeDetectionEvaluator(
            policy_supplier=lambda: current["policy"], engine=engine
        )
        evaluator.process(pcm(PREDICTION_FRAME_SAMPLES * 3))
        current["policy"] = policy(settings_revision=4, detector_gain=3.0)
        hits = []
        for _ in range(10):
            hits.extend(evaluator.process(pcm(PREDICTION_FRAME_SAMPLES)))
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].policy.settings_revision, 3)
        # Not one sample of the running attempt was amplified with the newer
        # revision's gain.
        self.assertEqual({int(chunk.max()) for chunk in model.received}, {1000})


class C3SettingsPlaneTests(unittest.TestCase):
    def test_the_settings_plane_publishes_every_c3_wake_key(self):
        registry = sc.build_default_registry()
        expected = {
            sc.WAKE_WORD_SENSITIVITY: (sc.TYPE_FLOAT, sc.APPLY_NEXT_ACTIVATION),
            sc.WAKE_WORD_MIN_PREDICTION_FRAMES: (sc.TYPE_INT, sc.APPLY_NEXT_ACTIVATION),
            sc.WAKE_WORD_PRE_ROLL_MS: (sc.TYPE_INT, sc.APPLY_NEXT_ACTIVATION),
            sc.WAKE_WORD_COOLDOWN_MS: (sc.TYPE_INT, sc.APPLY_NEXT_ACTIVATION),
            sc.WAKE_WORD_DETECTOR_GAIN: (sc.TYPE_FLOAT, sc.APPLY_NEXT_ACTIVATION),
            sc.WAKE_WORD_NOISE_SUPPRESSION: (sc.TYPE_BOOL, sc.APPLY_NEXT_SESSION),
            sc.WAKE_WORD_VAD_THRESHOLD: (sc.TYPE_FLOAT, sc.APPLY_NEXT_SESSION),
            sc.WAKE_WORD_SELECTION: (sc.TYPE_STRING_LIST, sc.APPLY_NEXT_SESSION),
            sc.WAKE_WORD_INFERENCE_BACKEND: (sc.TYPE_STRING, sc.APPLY_NEXT_SESSION),
            sc.WAKE_WORD_GLOBAL_DISABLED: (sc.TYPE_STRING_LIST, sc.APPLY_NEXT_SESSION),
        }
        for key, (value_type, apply_policy) in expected.items():
            definition = registry.get(key)
            self.assertIsNotNone(definition, key)
            self.assertEqual(definition.type, value_type, key)
            self.assertEqual(definition.apply_policy, apply_policy, key)
            self.assertIn(definition.apply_policy, sc.APPLY_POLICIES, key)

    def test_the_c3_defaults_are_the_documented_ones(self):
        registry = sc.build_default_registry()
        self.assertEqual(
            registry.get(sc.WAKE_WORD_MIN_PREDICTION_FRAMES).default_value, 1
        )
        self.assertEqual(
            registry.get(sc.WAKE_WORD_MIN_PREDICTION_FRAMES).constraints["min"], 1
        )
        self.assertEqual(
            registry.get(sc.WAKE_WORD_DETECTOR_GAIN).default_value, 1.0
        )
        self.assertEqual(
            registry.get(sc.WAKE_WORD_DETECTOR_GAIN).constraints["max"], 3.0
        )
        self.assertEqual(
            registry.get(sc.WAKE_WORD_VAD_THRESHOLD).default_value, 0.0
        )
        self.assertIs(
            registry.get(sc.WAKE_WORD_NOISE_SUPPRESSION).default_value, False
        )
        self.assertEqual(
            registry.get(sc.WAKE_WORD_INFERENCE_BACKEND).default_value, "auto"
        )

    def test_the_pre_roll_range_is_no_longer_derived_from_the_receptive_field(self):
        registry = sc.build_default_registry()
        constraints = registry.get(sc.WAKE_WORD_PRE_ROLL_MS).constraints
        self.assertEqual(constraints["min"], 0)
        self.assertNotIn("max", constraints)
        constraints = registry.get(sc.WAKE_WORD_COOLDOWN_MS).constraints
        self.assertEqual(constraints["min"], 0)
        self.assertNotIn("max", constraints)

    def test_allowed_values_is_a_generic_registry_constraint(self):
        definition = sc.SettingDefinition(
            key="test.enum",
            scope=sc.SCOPE_SERVER,
            auth=sc.AUTH_ADMIN,
            type=sc.TYPE_STRING,
            constraints={"allowedValues": ["a", "b"]},
            default_value="a",
            apply_policy=sc.APPLY_NEXT_SESSION,
        )
        value, error = sc.coerce_definition_value(definition, "b")
        self.assertIsNone(error)
        self.assertEqual(value, "b")
        value, error = sc.coerce_definition_value(definition, "c")
        self.assertIsNone(value)
        self.assertEqual(error.code, sc.CODE_VALUE_NOT_ALLOWED)

    def test_the_backend_key_is_an_admin_server_setting_with_allowed_values(self):
        registry = sc.build_default_registry()
        definition = registry.get(sc.WAKE_WORD_INFERENCE_BACKEND)
        self.assertEqual(definition.scope, sc.SCOPE_SERVER)
        self.assertEqual(definition.auth, sc.AUTH_ADMIN)
        self.assertEqual(
            definition.constraints["allowedValues"], ["auto", "onnx", "tflite"]
        )
        value, _error = sc.coerce_definition_value(definition, "tflite")
        self.assertEqual(value, "tflite")
        _value, error = sc.coerce_definition_value(definition, "coreml")
        self.assertEqual(error.code, sc.CODE_VALUE_NOT_ALLOWED)

    def test_next_activation_and_next_session_keep_their_distinct_semantics(self):
        registry = sc.build_default_registry()
        state = sc.SessionSettingsState(registry)
        result = state.apply_patch(0, {
            sc.WAKE_WORD_MIN_PREDICTION_FRAMES: 12,
            sc.WAKE_WORD_VAD_THRESHOLD: 0.5,
        })
        self.assertTrue(result.accepted)
        effective = state.effective_values()
        self.assertEqual(effective[sc.WAKE_WORD_MIN_PREDICTION_FRAMES], 12)
        # next_session values only take effect on a rebuilt session.
        self.assertEqual(effective[sc.WAKE_WORD_VAD_THRESHOLD], 0.0)
        self.assertEqual(state.requested_values()[sc.WAKE_WORD_VAD_THRESHOLD], 0.5)

    def test_a_settings_race_never_splits_one_attempt(self):
        """The deterministic barrier test C3 section 13 asks for."""
        registry = sc.build_default_registry()
        state = sc.SessionSettingsState(registry)

        def supplier():
            bundle = state.activation_admission_settings()
            values = bundle.effective_settings
            return WakeAttemptPolicy(
                sensitivity=float(values[sc.WAKE_WORD_SENSITIVITY]),
                min_consecutive_prediction_frames=int(
                    values[sc.WAKE_WORD_MIN_PREDICTION_FRAMES]
                ),
                detector_gain=float(values[sc.WAKE_WORD_DETECTOR_GAIN]),
                cooldown_ms=int(values[sc.WAKE_WORD_COOLDOWN_MS]),
                pre_roll_ms=int(values[sc.WAKE_WORD_PRE_ROLL_MS]),
                settings_revision=int(bundle.settings_revision),
            )

        state.apply_patch(0, {
            sc.WAKE_WORD_SENSITIVITY: 0.7,
            sc.WAKE_WORD_MIN_PREDICTION_FRAMES: 10,
        })
        start_revision = state.settings_revision
        tracker = WakeHitTracker(policy_supplier=supplier)
        end_sample = 0
        patched = threading.Event()

        def patch():
            state.apply_patch(state.settings_revision, {
                sc.WAKE_WORD_SENSITIVITY: 0.95,
                sc.WAKE_WORD_MIN_PREDICTION_FRAMES: 40,
                sc.WAKE_WORD_PRE_ROLL_MS: 500,
            })
            patched.set()

        hit = None
        for index in range(14):
            end_sample += PREDICTION_FRAME_SAMPLES
            if index == 4:
                worker = threading.Thread(target=patch)
                worker.start()
                worker.join()
                self.assertTrue(patched.is_set())
            score = 0.80 if index < 13 else 0.10
            hit = tracker.observe({"alexa": score}, end_sample=end_sample) or hit
        self.assertIsNotNone(hit)
        self.assertEqual(hit.policy.settings_revision, start_revision)
        self.assertAlmostEqual(hit.policy.sensitivity, 0.7)
        self.assertEqual(hit.policy.min_consecutive_prediction_frames, 10)
        self.assertEqual(hit.policy.pre_roll_ms, 0)
        self.assertGreater(state.settings_revision, start_revision)


# -- 6. operational zero point and pre-roll ------------------------------------

class OperationalZeroPointTests(unittest.TestCase):
    def test_the_zero_point_is_the_trailing_edge_not_an_estimate(self):
        boundary = resolve_wake_audio_boundary(
            operational_zero_point_sample=32000,
            pre_roll_ms=0,
            sample_rate=16000,
            history_start_sample=0,
        )
        self.assertEqual(boundary.operational_zero_point_sample, 32000)
        self.assertEqual(boundary.release_sample, 32000)
        self.assertEqual(boundary.boundary_basis, BASIS_OPERATIONAL_ZERO_POINT)
        self.assertTrue(boundary.boundary_defined)

    def test_pre_roll_moves_the_release_before_the_zero_point(self):
        boundary = resolve_wake_audio_boundary(
            operational_zero_point_sample=32000,
            pre_roll_ms=500,
            sample_rate=16000,
            history_start_sample=0,
        )
        self.assertEqual(boundary.release_sample, 32000 - 8000)
        self.assertEqual(boundary.released_pre_roll_samples, 8000)
        self.assertFalse(boundary.pre_roll_clamped)

    def test_pre_roll_is_clamped_to_the_real_audio_history(self):
        boundary = resolve_wake_audio_boundary(
            operational_zero_point_sample=32000,
            pre_roll_ms=5000,
            sample_rate=16000,
            history_start_sample=30000,
        )
        self.assertEqual(boundary.release_sample, 30000)
        self.assertEqual(boundary.released_pre_roll_samples, 2000)
        self.assertTrue(boundary.pre_roll_clamped)

    def test_the_projection_never_claims_the_zero_point_is_unknown(self):
        payload = resolve_wake_audio_boundary(
            operational_zero_point_sample=1000, sample_rate=16000
        ).to_dict()
        self.assertEqual(payload["boundaryBasis"], BASIS_OPERATIONAL_ZERO_POINT)
        self.assertTrue(payload["boundaryDefined"])
        self.assertNotIn("estimatedWakeEndSample", payload)


# -- 7. F12: dual backend admission --------------------------------------------

class F12BackendPolicyTests(unittest.TestCase):
    def test_windows_auto_prefers_onnx(self):
        self.assertEqual(
            wake_backend.backend_preference("auto", platform="windows"),
            ("onnx", "tflite"),
        )

    def test_linux_auto_prefers_tflite(self):
        self.assertEqual(
            wake_backend.backend_preference("auto", platform="linux"),
            ("tflite", "onnx"),
        )

    def test_an_explicit_backend_has_no_fallback_preference(self):
        self.assertEqual(
            wake_backend.backend_preference("onnx", platform="linux"), ("onnx",)
        )
        self.assertEqual(
            wake_backend.backend_preference("tflite", platform="windows"),
            ("tflite",),
        )

    def test_auto_falls_back_to_the_other_backend_for_the_whole_selection(self):
        selection = wake_backend.select_common_backend(
            "auto", {"tflite"}, platform="windows"
        )
        self.assertEqual(selection.backend, "tflite")
        self.assertTrue(selection.fallback_used)
        self.assertIsNone(selection.reason)

    def test_auto_uses_the_preferred_backend_when_it_is_healthy(self):
        selection = wake_backend.select_common_backend(
            "auto", {"onnx", "tflite"}, platform="windows"
        )
        self.assertEqual(selection.backend, "onnx")
        self.assertFalse(selection.fallback_used)
        selection = wake_backend.select_common_backend(
            "auto", {"onnx", "tflite"}, platform="linux"
        )
        self.assertEqual(selection.backend, "tflite")

    def test_no_common_backend_is_a_rejection(self):
        selection = wake_backend.select_common_backend(
            "auto", set(), platform="linux"
        )
        self.assertIsNone(selection.backend)
        self.assertEqual(selection.reason, wake_backend.REASON_NO_COMMON_BACKEND)

    def test_an_explicit_backend_never_silently_switches(self):
        selection = wake_backend.select_common_backend(
            "onnx", {"tflite"}, platform="linux"
        )
        self.assertIsNone(selection.backend)
        self.assertEqual(
            selection.reason, wake_backend.REASON_BACKEND_UNAVAILABLE
        )
        self.assertFalse(selection.fallback_used)


class F12CatalogAdmissionTests(unittest.TestCase):
    def setUp(self):
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.tmp = Path(self._tempdir.name)

    def authority(self, *, backends=("onnx", "tflite"), probers=None,
                  entries=ENTRIES, name="bundle"):
        root = build_bundle(self.tmp / name, entries, backends=backends)
        if probers is None:
            probers = {backend: (lambda path: None) for backend in backends}
        return WakeWordCatalogAuthority(
            asset_root=root, artifact_probers=probers
        ), root

    def test_a_dual_format_bundle_reports_health_per_backend(self):
        authority, _root = self.authority()
        entry = authority.snapshot().get("alexa")
        self.assertEqual(set(entry.healthy_backends), {"onnx", "tflite"})
        public = entry.public_dict()
        self.assertTrue(public["backends"]["onnx"]["available"])
        self.assertTrue(public["backends"]["tflite"]["available"])

    def test_a_missing_runtime_makes_that_backend_unhealthy_not_available(self):
        def broken(path):
            raise RuntimeError("no tflite runtime")

        authority, _root = self.authority(
            probers={"onnx": lambda path: None, "tflite": broken}
        )
        entry = authority.snapshot().get("alexa")
        self.assertEqual(entry.healthy_backends, ("onnx",))
        self.assertTrue(entry.available)
        self.assertEqual(
            entry.public_dict()["backends"]["tflite"]["unavailableReason"],
            REASON_ARTIFACT_UNLOADABLE,
        )

    def test_an_absent_runtime_never_counts_as_a_passed_probe(self):
        """RED against C2: a missing ONNXRuntime skipped the probe entirely."""
        authority, _root = self.authority(
            backends=("onnx",), probers={"onnx": None}
        )
        entry = authority.snapshot().get("alexa")
        self.assertEqual(entry.healthy_backends, ())
        self.assertFalse(entry.available)
        self.assertEqual(
            entry.public_dict()["backends"]["onnx"]["unavailableReason"],
            REASON_RUNTIME_UNAVAILABLE,
        )

    def test_auto_admits_the_preferred_healthy_backend(self):
        authority, _root = self.authority()
        selection, errors = authority.admit_selection(
            ["alexa", "hey_jarvis"], requested_backend="auto", platform="windows"
        )
        self.assertEqual(errors, ())
        self.assertEqual(selection.backend, "onnx")
        selection, errors = authority.admit_selection(
            ["alexa", "hey_jarvis"], requested_backend="auto", platform="linux"
        )
        self.assertEqual(selection.backend, "tflite")

    def test_auto_falls_back_when_the_preferred_backend_is_bad(self):
        def broken(path):
            raise RuntimeError("bad tflite artifact")

        authority, _root = self.authority(
            probers={"onnx": lambda path: None, "tflite": broken}
        )
        selection, errors = authority.admit_selection(
            ["alexa", "hey_jarvis"], requested_backend="auto", platform="linux"
        )
        self.assertEqual(errors, ())
        self.assertEqual(selection.backend, "onnx")
        self.assertTrue(selection.fallback_used)

    def test_an_explicit_bad_backend_is_rejected_without_fallback(self):
        def broken(path):
            raise RuntimeError("bad tflite artifact")

        authority, _root = self.authority(
            probers={"onnx": lambda path: None, "tflite": broken}
        )
        selection, errors = authority.admit_selection(
            ["alexa"], requested_backend="tflite", platform="windows"
        )
        self.assertIsNone(selection)
        self.assertEqual(errors[0].reason, REASON_BACKEND_UNAVAILABLE)
        self.assertEqual(errors[0].code, "wake_word_unavailable")

    def test_individually_healthy_models_without_a_common_backend_are_rejected(self):
        root = build_bundle(
            self.tmp / "split", ENTRIES, backends=("onnx", "tflite")
        )

        def onnx_probe(path):
            if "jarvis" in str(path):
                raise RuntimeError("bad onnx")

        def tflite_probe(path):
            if "alexa" in str(path):
                raise RuntimeError("bad tflite")

        authority = WakeWordCatalogAuthority(
            asset_root=root,
            artifact_probers={"onnx": onnx_probe, "tflite": tflite_probe},
        )
        snapshot = authority.snapshot()
        self.assertEqual(snapshot.get("alexa").healthy_backends, ("onnx",))
        self.assertEqual(snapshot.get("hey_jarvis").healthy_backends, ("tflite",))
        selection, errors = authority.admit_selection(
            ["alexa", "hey_jarvis"], requested_backend="auto", platform="linux"
        )
        self.assertIsNone(selection)
        self.assertEqual(errors[0].reason, REASON_NO_COMMON_BACKEND)
        # Each alone still admits under its own healthy backend.
        selection, _errors = authority.admit_selection(
            ["alexa"], requested_backend="auto", platform="linux"
        )
        self.assertEqual(selection.backend, "onnx")
        selection, _errors = authority.admit_selection(
            ["hey_jarvis"], requested_backend="auto", platform="linux"
        )
        self.assertEqual(selection.backend, "tflite")

    def test_the_admitted_selection_loads_one_common_backend_only(self):
        authority, _root = self.authority()
        selection, _errors = authority.admit_selection(
            ["alexa", "hey_jarvis"], requested_backend="tflite"
        )
        kwargs = selection.loader_kwargs()
        self.assertEqual(kwargs["inference_framework"], "tflite")
        self.assertTrue(
            all(path.endswith(".tflite") for path in kwargs["wakeword_models"])
        )
        self.assertTrue(kwargs["melspec_model_path"].endswith(".tflite"))

    def test_the_wire_port_reports_the_backend_rejection_machine_readably(self):
        def broken(path):
            raise RuntimeError("bad tflite artifact")

        authority, _root = self.authority(
            probers={"onnx": lambda path: None, "tflite": broken}
        )
        port = ports.WakeWordPort(FakeCatalogService(authority))
        selection, errors = port.resolve_selection(
            ["alexa"], requested_backend="tflite"
        )
        self.assertIsNone(selection)
        self.assertEqual(errors[0]["code"], "wake_word_unavailable")
        self.assertEqual(errors[0]["reason"], REASON_BACKEND_UNAVAILABLE)
        self.assertEqual(errors[0]["field"], "requestedSession.wakeWordIds")


# -- 8. catalog loadability at load and refresh --------------------------------

class C3CatalogLoadabilityTests(unittest.TestCase):
    def setUp(self):
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.tmp = Path(self._tempdir.name)

    def test_every_declared_artifact_is_probed_at_the_initial_load(self):
        root = build_bundle(
            self.tmp / "bundle", ENTRIES, backends=("onnx", "tflite")
        )
        probed = []
        WakeWordCatalogAuthority(
            asset_root=root,
            artifact_probers={"onnx": probed.append, "tflite": probed.append},
        )
        names = {Path(path).name for path in probed}
        for expected in ("alexa.onnx", "alexa.tflite", "jarvis_v2.onnx",
                         "jarvis_v2.tflite", "melspectrogram.onnx",
                         "melspectrogram.tflite", "embedding_model.onnx",
                         "embedding_model.tflite"):
            self.assertIn(expected, names)

    def test_a_file_that_merely_exists_is_never_available(self):
        root = build_bundle(self.tmp / "bundle", ENTRIES)

        def probe(path):
            if Path(path).name == "alexa.onnx":
                raise RuntimeError("corrupt onnx")

        authority = WakeWordCatalogAuthority(
            asset_root=root, artifact_probers={"onnx": probe}
        )
        entry = authority.snapshot().get("alexa")
        self.assertTrue((root / "alexa.onnx").is_file())
        self.assertFalse(entry.available)
        self.assertEqual(entry.unavailable_reason, REASON_ARTIFACT_UNLOADABLE)

    def test_a_refresh_reprobes_a_repaired_artifact(self):
        root = build_bundle(self.tmp / "bundle", ENTRIES)
        broken = {"alexa.onnx"}

        def probe(path):
            if Path(path).name in broken:
                raise RuntimeError("corrupt onnx")

        authority = WakeWordCatalogAuthority(
            asset_root=root, artifact_probers={"onnx": probe}
        )
        self.assertNotIn("alexa", authority.available_ids())
        broken.clear()
        result = authority.refresh()
        self.assertTrue(result.ok)
        self.assertIn("alexa", authority.available_ids())

    def test_a_declared_integrity_mismatch_is_detected(self):
        root = build_bundle(self.tmp / "bundle", ENTRIES)
        (root / "alexa.onnx").write_bytes(b"tampered payload")
        authority = WakeWordCatalogAuthority(
            asset_root=root, artifact_probers={"onnx": lambda path: None}
        )
        entry = authority.snapshot().get("alexa")
        self.assertFalse(entry.available)
        self.assertEqual(entry.unavailable_reason, REASON_ARTIFACT_INTEGRITY)

    def test_a_missing_artifact_is_reported_as_missing(self):
        root = build_bundle(self.tmp / "bundle", ENTRIES)
        (root / "alexa.onnx").unlink()
        authority = WakeWordCatalogAuthority(
            asset_root=root, artifact_probers={"onnx": lambda path: None}
        )
        entry = authority.snapshot().get("alexa")
        self.assertFalse(entry.available)
        self.assertEqual(entry.unavailable_reason, "artifact_missing")

    def test_unavailable_entries_stay_publicly_listed(self):
        root = build_bundle(self.tmp / "bundle", ENTRIES)

        def probe(path):
            if Path(path).name == "alexa.onnx":
                raise RuntimeError("corrupt onnx")

        authority = WakeWordCatalogAuthority(
            asset_root=root, artifact_probers={"onnx": probe}
        )
        payload = authority.public_payload()
        ids = [item["id"] for item in payload["wakeWords"]]
        self.assertIn("alexa", ids)
        entry = next(item for item in payload["wakeWords"] if item["id"] == "alexa")
        self.assertFalse(entry["available"])
        self.assertEqual(entry["unavailableReason"], REASON_ARTIFACT_UNLOADABLE)
        self.assertNotIn("alexa", authority.available_ids())
        blob = json.dumps(payload)
        self.assertNotIn(str(root), blob)
        self.assertNotIn(".onnx", blob)

    def test_last_known_good_survives_a_failing_refresh(self):
        root = build_bundle(self.tmp / "bundle", ENTRIES)
        authority = WakeWordCatalogAuthority(
            asset_root=root, artifact_probers={"onnx": lambda path: None}
        )
        good = authority.available_ids()
        (root / "models.json").write_text("{ broken", encoding="utf-8")
        result = authority.refresh()
        self.assertFalse(result.ok)
        self.assertEqual(authority.available_ids(), good)


# -- 9. F14: real state-changing refresh races ---------------------------------

class StateChangingLoader:
    """A loader that really moves the catalog from state A to state B."""

    def __init__(self, root_b):
        from VoiceSTT.core.wakeword_catalog import load_snapshot

        self._load = load_snapshot
        self._root_b = root_b
        self.gate = threading.Event()
        self.entered = threading.Event()

    def __call__(self, asset_root):
        self.entered.set()
        self.gate.wait(10.0)
        return self._load(self._root_b)


class F14RefreshRaceTests(unittest.TestCase):
    REPEATS = 20

    def setUp(self):
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.tmp = Path(self._tempdir.name)

    def _roots(self, index):
        root_a = build_bundle(
            self.tmp / f"a{index}",
            (("alexa", "Alexa", (), "alexa.onnx"),),
        )
        root_b = build_bundle(
            self.tmp / f"b{index}",
            (
                ("alexa", "Alexa", (), "alexa.onnx"),
                ("hey_jarvis", "Hey Jarvis", ("jarvis",), "jarvis_v2.onnx"),
            ),
        )
        return root_a, root_b

    def _authority(self, root_a, root_b):
        authority = WakeWordCatalogAuthority(
            asset_root=root_a, artifact_probers={"onnx": lambda path: None}
        )
        loader = StateChangingLoader(root_b)
        authority.set_loader_for_tests(loader)
        return authority, loader

    def test_a_get_sees_state_a_or_state_b_but_never_a_mixture(self):
        for index in range(self.REPEATS):
            root_a, root_b = self._roots(index)
            authority, loader = self._authority(root_a, root_b)
            observations = []
            refresher = threading.Thread(target=authority.refresh)
            refresher.start()
            self.assertTrue(loader.entered.wait(10.0))
            reader = threading.Thread(
                target=lambda: observations.append(authority.public_payload())
            )
            reader.start()
            loader.gate.set()
            reader.join(10.0)
            refresher.join(10.0)

            self.assertEqual(len(observations), 1)
            payload = observations[0]
            ids = sorted(item["id"] for item in payload["wakeWords"])
            self.assertIn(ids, (["alexa"], ["alexa", "hey_jarvis"]))
            revisions = {item["catalogRevision"] for item in payload["wakeWords"]}
            self.assertEqual(revisions, {payload["catalogRevision"]})
            available = set(payload["wakeWords"][0].keys())
            self.assertIn("available", available)
            # After the refresh the catalog is fully in state B.
            after = authority.public_payload()
            self.assertEqual(
                sorted(item["id"] for item in after["wakeWords"]),
                ["alexa", "hey_jarvis"],
            )
            self.assertEqual(after["catalogRevision"], 2)

    def test_an_admission_decides_fully_against_one_snapshot(self):
        for index in range(self.REPEATS):
            root_a, root_b = self._roots(1000 + index)
            authority, loader = self._authority(root_a, root_b)
            results = []
            refresher = threading.Thread(target=authority.refresh)
            refresher.start()
            self.assertTrue(loader.entered.wait(10.0))
            admitter = threading.Thread(
                target=lambda: results.append(
                    authority.admit_selection(
                        ["hey_jarvis"], requested_backend="onnx"
                    )
                )
            )
            admitter.start()
            loader.gate.set()
            admitter.join(10.0)
            refresher.join(10.0)

            self.assertEqual(len(results), 1)
            selection, errors = results[0]
            if selection is None:
                # Decided fully against snapshot A: hey_jarvis does not exist.
                self.assertEqual(errors[0].wake_word_id, "hey_jarvis")
                self.assertEqual(errors[0].reason, "unknown")
            else:
                self.assertEqual(selection.wake_word_ids, ("hey_jarvis",))
                self.assertEqual(selection.catalog_revision, 2)
            after, after_errors = authority.admit_selection(
                ["hey_jarvis"], requested_backend="onnx"
            )
            self.assertEqual(after_errors, ())
            self.assertEqual(after.catalog_revision, 2)


# -- 10. F13: exactly one logical wakeword.detected ----------------------------

class FakeEvaluator:
    """Just enough of the evaluator for the admission coordinator."""

    def __init__(self):
        self.latched = None
        self.refusals = 0

    def accept(self, hit, *, activation_id, boundary=None, now=None):
        self.latched = activation_id
        return AcceptedWakeDetection(
            canonical_wake_word_id=hit.canonical_wake_word_id,
            score=float(hit.peak_score),
            activation_id=activation_id,
            boundary=boundary,
            wake_hit=hit,
        )

    def refuse(self, hit, *, now=None):
        self.refusals += 1

    def release_latch(self, *, activation_id=None):
        released = self.latched is not None
        self.latched = None
        return released

    def new_generation(self):
        self.latched = None
        return 1

    def diagnostics(self):
        return {}


def wake_hit(word="alexa"):
    return WakeHit(
        canonical_wake_word_id=word,
        peak_score=0.91,
        start_frame_index=0,
        start_sample=1280,
        qualification_frame_index=9,
        qualification_sample=12800,
        finalization_frame_index=13,
        operational_zero_point_sample=17920,
        prediction_frame_count=13,
        policy=policy(),
    )


class F13ExactlyOnceEventTests(unittest.TestCase):
    def build(self, *, activate=None, deliver=None):
        self.ledger = LogicalWakeEventLedger()
        self.delivered = []
        self.evaluator = FakeEvaluator()

        def default_activate(hit, boundary):
            return WakeActivationOutcome(committed=True, activation_id="act-1")

        def default_deliver(event, detection):
            self.delivered.append(event)

        return WakeAdmissionCoordinator(
            evaluator=self.evaluator,
            activate=activate or default_activate,
            deliver=deliver or default_deliver,
            ledger=self.ledger,
        )

    def test_one_accepted_hit_mints_exactly_one_logical_event(self):
        coordinator = self.build()
        detection = coordinator.admit(wake_hit())
        self.assertIsNotNone(detection)
        self.assertEqual(self.ledger.count(), 1)
        self.assertEqual(len(self.delivered), 1)
        self.assertEqual(self.delivered[0].activation_id, "act-1")

    def test_fault_a_a_failure_before_the_mint_leaves_no_event(self):
        def activate(hit, boundary):
            raise RuntimeError("pre-commit failure")

        coordinator = self.build(activate=activate)
        self.assertIsNone(coordinator.admit(wake_hit()))
        self.assertEqual(self.ledger.count(), 0)
        self.assertEqual(self.delivered, [])
        self.assertIsNone(self.evaluator.latched)

    def test_fault_b_a_transport_failure_after_the_mint_keeps_one_event(self):
        def deliver(event, detection):
            raise RuntimeError("transport is down")

        coordinator = self.build(deliver=deliver)
        detection = coordinator.admit(wake_hit())
        self.assertIsNotNone(detection)
        self.assertEqual(self.ledger.count(), 1)
        self.assertEqual(coordinator.logical_event_count("act-1"), 1)
        self.assertFalse(self.ledger.events[0].delivered)
        self.assertEqual(self.evaluator.latched, "act-1")

    def test_fault_c_a_retry_delivers_the_same_event_and_never_mints_a_second(self):
        attempts = {"count": 0}

        def deliver(event, detection):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("transport is down")
            self.delivered.append(event)

        coordinator = self.build(deliver=deliver)
        coordinator.admit(wake_hit())
        self.assertEqual(self.ledger.count(), 1)
        self.assertTrue(coordinator.redeliver())
        self.assertEqual(self.ledger.count(), 1)
        self.assertEqual(len(self.delivered), 1)
        self.assertTrue(self.ledger.events[0].delivered)
        # A second redelivery is a no-op, never a duplicate.
        self.assertFalse(coordinator.redeliver())
        self.assertEqual(len(self.delivered), 1)

    def test_fault_d_a_session_close_after_the_commit_keeps_exactly_one_event(self):
        def deliver(event, detection):
            raise RuntimeError("socket closed")

        coordinator = self.build(deliver=deliver)
        coordinator.admit(wake_hit())
        coordinator.release("act-1")
        coordinator.reset()
        self.assertEqual(self.ledger.count(), 1)
        self.assertEqual(self.ledger.events[0].wake_word_id, "alexa")
        self.assertEqual(self.ledger.events[0].activation_id, "act-1")

    def test_the_event_carries_the_activation_of_the_same_hit(self):
        coordinator = self.build()
        detection = coordinator.admit(wake_hit("hey_jarvis"))
        event = self.ledger.events[0]
        self.assertEqual(event.wake_word_id, "hey_jarvis")
        self.assertEqual(event.activation_id, detection.activation_id)
        self.assertEqual(event.sequence, 1)

    def test_a_second_admission_of_the_same_activation_is_not_a_second_event(self):
        coordinator = self.build()
        coordinator.admit(wake_hit())
        coordinator.admit(wake_hit())
        self.assertEqual(self.ledger.count("act-1"), 1)

    def test_a_refused_admission_never_mints_and_never_latches(self):
        coordinator = self.build(
            activate=lambda hit, boundary: WakeActivationOutcome.refused()
        )
        self.assertIsNone(coordinator.admit(wake_hit()))
        self.assertEqual(self.ledger.count(), 0)
        self.assertEqual(self.evaluator.refusals, 1)
        self.assertIsNone(self.evaluator.latched)


# -- 11. F15: the documentation says what the product does ----------------------

class F15ContractDocumentationTests(unittest.TestCase):
    def read(self, relative):
        return (REPO_ROOT / relative).read_text(encoding="utf-8")

    def test_the_wake_word_doc_describes_the_c3_detection_model(self):
        text = self.read("docs/wake-words.md")
        for needle in (
            "minConsecutivePredictionFrames",
            "prediction frame",
            "Trailing Edge",
            "operational audio zero point",
            "first qualified hit that finalizes wins",
            "exactly-once",
            "inferenceBackend",
            "detectorGain",
            "vadThreshold",
        ):
            self.assertIn(needle, text, needle)

    def test_the_trigger_doc_describes_the_c3_detection_model(self):
        text = self.read("docs/einheitliche-triggerarchitektur.md")
        for needle in (
            "wakeWord.minConsecutivePredictionFrames",
            "Prediction-Frame",
            "Trailing Edge",
            "operationale",
            "wakeWord.inferenceBackend",
            "wakeWord.detectorGain",
            "wakeWord.vadThreshold",
            "First-come-first-served",
        ):
            self.assertIn(needle, text, needle)

    def test_the_doc_no_longer_states_the_withdrawn_rules(self):
        """The withdrawn formulations may only appear as withdrawn.

        C3 section 17 asks for a correction, not for an erasure: naming what
        the earlier wording said and that it no longer holds is part of the
        contract fix. So the rule is not "the phrase must be gone" but "the
        phrase must never stand as current norm" - every paragraph that still
        contains one has to mark it as withdrawn.
        """
        markers = ("zurückgezogen", "withdrawn", "Fehlinterpretation")
        for relative in (
            "docs/wake-words.md",
            "docs/einheitliche-triggerarchitektur.md",
            "docs/configuration.md",
        ):
            text = self.read(relative)
            paragraphs = text.split("\n\n")
            for withdrawn in (
                "höchster Score gewinnt",
                "highest valid score",
                "5/10 Treffer",
                "5-of-10 hits",
                "Multi-Chunk-Regel",
                "multi-chunk rule",
                "Entprellfenster",
                "de-duplication window",
                "detection_sample_estimate",
                "boundaryMeasured",
            ):
                for paragraph in paragraphs:
                    if withdrawn not in paragraph:
                        continue
                    self.assertTrue(
                        any(marker in paragraph for marker in markers),
                        f"{relative}: '{withdrawn}' stands as current norm in:"
                        f"\n{paragraph}",
                    )

    def test_the_trigger_doc_explains_exactly_once_eventing(self):
        text = self.read("docs/einheitliche-triggerarchitektur.md")
        self.assertIn("Exactly-once", text)
        self.assertIn("logisch", text.lower())

    def test_the_configuration_doc_lists_every_c3_wake_key(self):
        text = self.read("docs/configuration.md")
        for key in (
            "wakeWord.minConsecutivePredictionFrames",
            "wakeWord.detectorGain",
            "wakeWord.noiseSuppressionEnabled",
            "wakeWord.vadThreshold",
            "wakeWord.inferenceBackend",
        ):
            self.assertIn(key, text)


if __name__ == "__main__":
    unittest.main()
