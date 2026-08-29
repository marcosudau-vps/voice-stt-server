"""AP-SRV-060: prediction frames, hit regions, arbitration, latch and cooldown.

The C1/C2 version of this file pinned ``select_candidate`` - "the highest valid
score wins, per chunk". AP-SRV-060 C3 withdrew that rule: a spoken wake word is
a *run* of prediction frames, arbitration is first-finalized-wins, and the peak
score is a property of the whole hit region rather than the decision criterion.
The tests below pin the corrected model; the full C3 matrix lives in
``test_wakeword_root_findings_c3.py``.
"""

import unittest

from VoiceSTT.core.wake_detection import (
    EMBEDDING_FRAME_STEP_MS,
    EMBEDDING_WINDOW_MS,
    RawWakeCandidate,
    WakeAttemptPolicy,
    WakeDetectionEvaluator,
    WakeHitTracker,
    WakeRuntimePolicy,
    arbitrate_finalized,
    receptive_field_ms,
    selection_receptive_field_ms,
)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def policy(**kwargs):
    values = {
        "sensitivity": 0.5,
        "min_consecutive_prediction_frames": 1,
        "cooldown_ms": 0,
        "pre_roll_ms": 0,
        "settings_revision": 0,
    }
    values.update(kwargs)
    return WakeAttemptPolicy(**values)


def drive(target, scores_per_frame, *, step=1280):
    """Feeds prediction frames and returns every finalized/offered hit."""
    hits = []
    end_sample = 0
    for scores in scores_per_frame:
        end_sample += step
        method = getattr(target, "observe", None) or target.observe_scores
        hit = method(scores, end_sample=end_sample)
        if hit is not None:
            hits.append(hit)
    return hits


class ReceptiveFieldTests(unittest.TestCase):
    """Still measured, but since C3 a diagnostic and no longer an authority."""

    def test_a_single_frame_window_is_the_embedding_window(self):
        self.assertEqual(receptive_field_ms(1), EMBEDDING_WINDOW_MS)

    def test_each_further_frame_adds_one_streaming_step(self):
        self.assertEqual(
            receptive_field_ms(16),
            15 * EMBEDDING_FRAME_STEP_MS + EMBEDDING_WINDOW_MS,
        )
        self.assertEqual(receptive_field_ms(16), 1960)
        self.assertEqual(receptive_field_ms(34), 3400)

    def test_an_unusable_frame_count_falls_back_to_the_window(self):
        for value in (None, 0, -3, "nope"):
            with self.subTest(value=value):
                self.assertEqual(receptive_field_ms(value), EMBEDDING_WINDOW_MS)

    def test_a_selection_uses_its_widest_measured_window(self):
        self.assertEqual(
            selection_receptive_field_ms({"a": 16, "b": 34, "c": 22}), 3400
        )
        self.assertEqual(selection_receptive_field_ms({}), EMBEDDING_WINDOW_MS)


class AttemptPolicyTests(unittest.TestCase):
    def test_the_historical_runtime_policy_name_is_the_attempt_snapshot(self):
        self.assertIs(WakeRuntimePolicy, WakeAttemptPolicy)

    def test_the_snapshot_projection_names_every_wake_value(self):
        payload = policy(
            sensitivity=0.7, min_consecutive_prediction_frames=10,
            detector_gain=1.5, cooldown_ms=250, pre_roll_ms=500,
            settings_revision=4,
        ).to_dict()
        self.assertEqual(payload, {
            "sensitivity": 0.7,
            "minConsecutivePredictionFrames": 10,
            "detectorGain": 1.5,
            "cooldownMs": 250,
            "preRollMs": 500,
            "settingsRevision": 4,
        })

    def test_a_minimum_below_one_is_clamped_to_one(self):
        self.assertEqual(policy(min_consecutive_prediction_frames=0).min_frames, 1)


class HitRegionTests(unittest.TestCase):
    def setUp(self):
        self.tracker = WakeHitTracker(
            policy_supplier=lambda: policy(min_consecutive_prediction_frames=3)
        )

    def test_scores_below_the_threshold_never_start_a_region(self):
        self.assertEqual(drive(self.tracker, [{"a": 0.4}] * 5), [])

    def test_a_run_shorter_than_the_minimum_is_discarded(self):
        hits = drive(self.tracker, [{"a": 0.9}, {"a": 0.9}, {"a": 0.1}])
        self.assertEqual(hits, [])

    def test_a_qualified_run_finalizes_once_at_its_trailing_edge(self):
        hits = drive(self.tracker, [{"a": 0.9}] * 8 + [{"a": 0.1}])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].prediction_frame_count, 8)
        self.assertEqual(hits[0].operational_zero_point_sample, 8 * 1280)

    def test_the_published_score_is_the_peak_of_the_region(self):
        hits = drive(
            self.tracker,
            [{"a": 0.6}, {"a": 0.95}, {"a": 0.7}, {"a": 0.1}],
        )
        self.assertAlmostEqual(hits[0].peak_score, 0.95)
        self.assertAlmostEqual(hits[0].score, 0.95)

    def test_a_wake_word_that_stops_reporting_closes_its_region(self):
        hits = drive(self.tracker, [{"a": 0.9}] * 4 + [{}])
        self.assertEqual(len(hits), 1)


class ArbitrationTests(unittest.TestCase):
    def test_the_first_finalized_region_wins(self):
        tracker = WakeHitTracker(
            policy_supplier=lambda: policy(min_consecutive_prediction_frames=2)
        )
        script = [{"alexa": 0.9, "alexander": 0.9} for _ in range(4)]
        script.append({"alexa": 0.1, "alexander": 0.9})
        script.append({"alexa": 0.1, "alexander": 0.1})
        hits = drive(tracker, script)
        self.assertEqual([hit.canonical_wake_word_id for hit in hits], ["alexa"])

    def test_a_full_tie_is_broken_by_the_smallest_canonical_id(self):
        tracker = WakeHitTracker(
            policy_supplier=lambda: policy(min_consecutive_prediction_frames=2)
        )
        script = [{"zulu": 0.8, "alpha": 0.8} for _ in range(3)]
        script.append({"zulu": 0.1, "alpha": 0.1})
        hits = drive(tracker, script)
        self.assertEqual(hits[0].canonical_wake_word_id, "alpha")

    def test_the_arbitration_is_stable_and_not_order_dependent(self):
        from .test_wakeword_root_findings_c3 import synthetic_hit

        early = synthetic_hit("zulu", start=0, qualification=4, finalization=9)
        late = synthetic_hit("alpha", start=1, qualification=5, finalization=9)
        self.assertEqual(
            arbitrate_finalized([early, late]).canonical_wake_word_id, "zulu"
        )
        self.assertEqual(
            arbitrate_finalized([late, early]).canonical_wake_word_id, "zulu"
        )

    def test_an_empty_decision_has_no_winner(self):
        self.assertIsNone(arbitrate_finalized([]))


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.policy = policy()
        self.evaluator = WakeDetectionEvaluator(
            policy_supplier=lambda: self.policy, clock=self.clock
        )

    def test_a_first_finalized_hit_is_offered(self):
        hits = drive(self.evaluator, [{"hey_jarvis": 0.9}, {"hey_jarvis": 0.1}])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].canonical_wake_word_id, "hey_jarvis")

    def test_a_latched_detector_offers_nothing_more(self):
        hit = drive(self.evaluator, [{"a": 0.9}, {"a": 0.1}])[0]
        self.evaluator.accept(hit, activation_id="act-1")
        self.assertTrue(self.evaluator.latched)
        self.assertEqual(
            drive(self.evaluator, [{"a": 0.99}, {"a": 0.1}] * 5), []
        )

    def test_a_configured_cooldown_blocks_the_next_hit(self):
        evaluator = WakeDetectionEvaluator(
            policy_supplier=lambda: policy(cooldown_ms=500), clock=self.clock
        )
        hit = drive(evaluator, [{"a": 0.9}, {"a": 0.1}])[0]
        evaluator.accept(hit, activation_id="act-1")
        evaluator.release_latch(activation_id="act-1")
        self.assertEqual(drive(evaluator, [{"a": 0.9}, {"a": 0.1}]), [])
        self.clock.advance(0.5)
        self.assertEqual(len(drive(evaluator, [{"a": 0.9}, {"a": 0.1}])), 1)

    def test_a_refused_admission_never_latches(self):
        hit = drive(self.evaluator, [{"a": 0.9}, {"a": 0.1}])[0]
        self.evaluator.refuse(hit)
        self.assertFalse(self.evaluator.latched)
        self.assertEqual(len(drive(self.evaluator, [{"a": 0.9}, {"a": 0.1}])), 1)

    def test_the_latch_is_only_released_for_its_own_activation(self):
        hit = drive(self.evaluator, [{"a": 0.9}, {"a": 0.1}])[0]
        self.evaluator.accept(hit, activation_id="act-1")
        self.assertFalse(self.evaluator.release_latch(activation_id="act-2"))
        self.assertTrue(self.evaluator.latched)
        self.assertTrue(self.evaluator.release_latch(activation_id="act-1"))
        self.assertFalse(self.evaluator.latched)

    def test_a_new_generation_clears_latch_and_regions(self):
        hit = drive(self.evaluator, [{"a": 0.9}, {"a": 0.1}])[0]
        self.evaluator.accept(hit, activation_id="act-1")
        generation = self.evaluator.new_generation()
        self.assertGreater(generation, 0)
        self.assertFalse(self.evaluator.latched)
        self.assertEqual(len(drive(self.evaluator, [{"a": 0.9}, {"a": 0.1}])), 1)

    def test_the_accepted_detection_carries_id_score_and_activation(self):
        hit = drive(self.evaluator, [{"hey_jarvis": 0.87}, {"hey_jarvis": 0.1}])[0]
        detection = self.evaluator.accept(
            hit, activation_id="act-1", boundary="boundary"
        )
        self.assertEqual(detection.event_fields(), {
            "wakeWordId": "hey_jarvis",
            "score": 0.87,
            "activationId": "act-1",
        })
        self.assertEqual(detection.boundary, "boundary")
        self.assertIs(detection.wake_hit, hit)

    def test_diagnostics_expose_raw_scores_without_publishing_them(self):
        drive(self.evaluator, [{"hey_jarvis": 0.9}, {"hey_jarvis": 0.1}])
        diagnostics = self.evaluator.diagnostics()
        self.assertEqual(diagnostics["lastHit"]["peakScore"], 0.9)
        self.assertEqual(diagnostics["cooldownMs"], 0)
        self.assertEqual(diagnostics["minConsecutivePredictionFrames"], 1)
        self.assertEqual(
            diagnostics["tracker"]["lastScores"], {"hey_jarvis": 0.1}
        )


class RawCandidateTests(unittest.TestCase):
    """Raw candidates stay pure diagnostics - never a domain event."""

    def test_a_raw_candidate_projects_its_observation_only(self):
        candidate = RawWakeCandidate(
            canonical_wake_word_id="alexa",
            raw_score=0.42,
            frame_index=7,
            sample_position=8960,
            detector_generation=2,
            model_key="alexa",
        )
        self.assertEqual(candidate.diagnostics(), {
            "wakeWordId": "alexa",
            "rawScore": 0.42,
            "frameIndex": 7,
            "samplePosition": 8960,
            "detectorGeneration": 2,
            "modelKey": "alexa",
        })


if __name__ == "__main__":
    unittest.main()
