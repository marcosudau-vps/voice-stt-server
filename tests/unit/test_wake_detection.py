"""AP-SRV-060: raw candidates, the stable multi-model rule, latch and re-arm."""

import unittest

from VoiceSTT.core.wake_detection import (
    EMBEDDING_FRAME_STEP_MS,
    EMBEDDING_WINDOW_MS,
    RawWakeCandidate,
    WakeDetectionEvaluator,
    receptive_field_ms,
    select_candidate,
    selection_receptive_field_ms,
)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def candidate(identifier, score, *, generation=0, sample_position=1600,
              frame_index=1, model_key=None):
    return RawWakeCandidate(
        canonical_wake_word_id=identifier,
        raw_score=score,
        frame_index=frame_index,
        sample_position=sample_position,
        detector_generation=generation,
        model_key=model_key or identifier,
    )


class ReceptiveFieldTests(unittest.TestCase):
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


class SelectCandidateTests(unittest.TestCase):
    def test_scores_below_the_threshold_are_not_candidates(self):
        self.assertIsNone(select_candidate([candidate("a", 0.4)], 0.5))

    def test_the_highest_valid_score_wins(self):
        best = select_candidate(
            [candidate("a", 0.6), candidate("b", 0.9), candidate("c", 0.7)], 0.5
        )
        self.assertEqual(best.canonical_wake_word_id, "b")

    def test_an_exact_tie_is_broken_by_the_smallest_canonical_id(self):
        best = select_candidate(
            [candidate("zulu", 0.8), candidate("alpha", 0.8)], 0.5
        )
        self.assertEqual(best.canonical_wake_word_id, "alpha")
        # The rule is stable, not order dependent.
        best = select_candidate(
            [candidate("alpha", 0.8), candidate("zulu", 0.8)], 0.5
        )
        self.assertEqual(best.canonical_wake_word_id, "alpha")


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.evaluator = WakeDetectionEvaluator(
            threshold=0.5, rearm_ms=1960, cooldown_ms=0, clock=self.clock
        )

    def test_a_first_hit_is_offered(self):
        offered = self.evaluator.offer([candidate("hey_jarvis", 0.9)])
        self.assertIsNotNone(offered)
        self.assertEqual(offered.canonical_wake_word_id, "hey_jarvis")

    def test_a_latched_detector_offers_nothing_more(self):
        first = self.evaluator.offer([candidate("hey_jarvis", 0.9)])
        self.evaluator.accept(first, activation_id="act-1")
        self.assertTrue(self.evaluator.latched)
        for _ in range(10):
            self.assertIsNone(
                self.evaluator.offer([candidate("hey_jarvis", 0.99)])
            )

    def test_a_refused_admission_arms_rearm_but_never_the_latch(self):
        first = self.evaluator.offer([candidate("hey_jarvis", 0.9)])
        self.evaluator.refuse(first)
        self.assertFalse(self.evaluator.latched)
        self.assertIsNone(self.evaluator.offer([candidate("hey_jarvis", 0.9)]))
        self.clock.advance(self.evaluator.rearm_ms / 1000.0)
        self.assertIsNotNone(self.evaluator.offer([candidate("hey_jarvis", 0.9)]))

    def test_the_configured_cooldown_extends_the_measured_window(self):
        evaluator = WakeDetectionEvaluator(
            threshold=0.5, rearm_ms=1000, cooldown_ms=500, clock=self.clock
        )
        self.assertEqual(evaluator.rearm_ms, 1500)

    def test_the_latch_is_only_released_for_its_own_activation(self):
        first = self.evaluator.offer([candidate("hey_jarvis", 0.9)])
        self.evaluator.accept(first, activation_id="act-1")
        self.assertFalse(self.evaluator.release_latch(activation_id="act-2"))
        self.assertTrue(self.evaluator.latched)
        self.assertTrue(self.evaluator.release_latch(activation_id="act-1"))
        self.assertFalse(self.evaluator.latched)

    def test_a_stale_generation_candidate_is_ignored(self):
        generation = self.evaluator.new_generation()
        self.assertIsNone(
            self.evaluator.offer([candidate("hey_jarvis", 0.9, generation=generation - 1)])
        )
        self.assertIsNotNone(
            self.evaluator.offer([candidate("hey_jarvis", 0.9, generation=generation)])
        )

    def test_a_new_generation_clears_latch_and_rearm(self):
        first = self.evaluator.offer([candidate("hey_jarvis", 0.9)])
        self.evaluator.accept(first, activation_id="act-1")
        generation = self.evaluator.new_generation()
        self.assertFalse(self.evaluator.latched)
        self.assertIsNotNone(
            self.evaluator.offer([candidate("hey_jarvis", 0.9, generation=generation)])
        )

    def test_the_accepted_detection_carries_id_score_and_activation(self):
        first = self.evaluator.offer([candidate("hey_jarvis", 0.87)])
        detection = self.evaluator.accept(
            first, activation_id="act-1", boundary="boundary"
        )
        self.assertEqual(detection.event_fields(), {
            "wakeWordId": "hey_jarvis",
            "score": 0.87,
            "activationId": "act-1",
        })
        self.assertEqual(detection.boundary, "boundary")

    def test_diagnostics_expose_raw_scores_without_publishing_them(self):
        self.evaluator.offer([candidate("hey_jarvis", 0.9)])
        diagnostics = self.evaluator.diagnostics()
        self.assertEqual(diagnostics["lastCandidate"]["rawScore"], 0.9)
        self.assertEqual(diagnostics["effectiveRearmMs"], 1960)


if __name__ == "__main__":
    unittest.main()
