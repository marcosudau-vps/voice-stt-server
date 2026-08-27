"""AP-SRV-060: the wake admission coordinator, the latch and its races.

The latch deliberately lives here and not in the ``ActivationController``:
AP-SRV-010/030 stay the one source-neutral activation authority. These tests
therefore drive the real ``ActivationController`` and only fake the detector.

Every concurrency case is synchronised with ``threading.Barrier`` /
``threading.Event`` - never with sleeps.
"""

import threading
import unittest

from api_fastapi_server.activation import ActivationController
from api_fastapi_server.wake_admission import WakeAdmissionCoordinator
from VoiceSTT.core.wake_detection import RawWakeCandidate, WakeDetectionEvaluator


def candidate(identifier="hey_jarvis", score=0.9, generation=0,
              sample_position=32000):
    return RawWakeCandidate(
        canonical_wake_word_id=identifier,
        raw_score=score,
        frame_index=1,
        sample_position=sample_position,
        detector_generation=generation,
        model_key=identifier,
    )


class CoordinatorHarness:
    """One evaluator, one real controller, one coordinator."""

    def __init__(self, *, manual=True, wake_word=True, rearm_ms=0.0):
        self.controller = ActivationController(
            manual_trigger_enabled=manual,
            wake_word_trigger_enabled=wake_word,
        )
        self.evaluator = WakeDetectionEvaluator(threshold=0.5, rearm_ms=rearm_ms)
        self.published = []
        self.coordinator = WakeAdmissionCoordinator(
            evaluator=self.evaluator,
            activate=self._activate,
            publish=self.published.append,
        )

    def _activate(self, _candidate, _boundary):
        decision = self.controller.activate("wake_word")
        if not decision.accepted:
            return None
        return decision.snapshot.get("activationId")

    def offer_and_admit(self, item=None):
        item = item or candidate()
        offered = self.evaluator.offer([item])
        if offered is None:
            return None
        return self.coordinator.admit(offered)


class AcceptedDetectionTests(unittest.TestCase):
    def test_an_accepted_hit_publishes_exactly_one_detection(self):
        harness = CoordinatorHarness()
        detection = harness.offer_and_admit()

        self.assertIsNotNone(detection)
        self.assertEqual(len(harness.published), 1)
        fields = harness.published[0].event_fields()
        self.assertEqual(fields["wakeWordId"], "hey_jarvis")
        self.assertEqual(fields["score"], 0.9)
        self.assertEqual(
            fields["activationId"], harness.controller.snapshot()["activationId"]
        )

    def test_the_same_utterance_never_produces_a_second_event(self):
        harness = CoordinatorHarness()
        harness.offer_and_admit()
        for _ in range(20):
            self.assertIsNone(harness.offer_and_admit())
        self.assertEqual(len(harness.published), 1)

    def test_the_wire_source_is_wake_word(self):
        harness = CoordinatorHarness()
        harness.offer_and_admit()
        self.assertEqual(
            harness.controller.snapshot()["primarySource"], "wake_word"
        )


class RefusedAdmissionTests(unittest.TestCase):
    def test_activation_locked_publishes_nothing_and_does_not_latch(self):
        harness = CoordinatorHarness()
        harness.controller.activate("manual")
        locked_id = harness.controller.snapshot()["activationId"]

        detection = harness.offer_and_admit()

        self.assertIsNone(detection)
        self.assertEqual(harness.published, [])
        self.assertFalse(harness.evaluator.latched)
        # No second activation and no source merge.
        self.assertEqual(
            harness.controller.snapshot()["activationId"], locked_id
        )
        self.assertEqual(
            harness.controller.snapshot()["primarySource"], "manual"
        )

    def test_a_suppressed_wake_source_publishes_nothing(self):
        harness = CoordinatorHarness()
        harness.controller.set_runtime_suppression(wake_word=True)
        self.assertIsNone(harness.offer_and_admit())
        self.assertEqual(harness.published, [])
        self.assertFalse(harness.evaluator.latched)

    def test_a_refused_admission_still_rearms_the_detector(self):
        harness = CoordinatorHarness(rearm_ms=60000)
        harness.controller.activate("manual")
        harness.offer_and_admit()
        # Same utterance is not offered again while the re-arm window is open.
        self.assertIsNone(harness.evaluator.offer([candidate()]))

    def test_a_failing_activation_is_treated_as_a_refusal(self):
        harness = CoordinatorHarness()

        def boom(_candidate, _boundary):
            raise RuntimeError("controller unavailable")

        coordinator = WakeAdmissionCoordinator(
            evaluator=harness.evaluator,
            activate=boom,
            publish=harness.published.append,
        )
        self.assertIsNone(coordinator.admit(candidate()))
        self.assertEqual(harness.published, [])
        self.assertFalse(harness.evaluator.latched)


class LatchLifecycleTests(unittest.TestCase):
    def test_the_latch_survives_until_the_input_close_of_its_activation(self):
        harness = CoordinatorHarness()
        detection = harness.offer_and_admit()
        activation_id = detection.activation_id

        # Neither a segment nor its end releases the latch.
        harness.controller.recording_started()
        self.assertTrue(harness.evaluator.latched)
        harness.controller.recording_ended()
        self.assertTrue(harness.evaluator.latched)

        # A foreign activation id must not release it either.
        self.assertFalse(harness.coordinator.release("other-activation"))
        self.assertTrue(harness.evaluator.latched)

        self.assertTrue(harness.coordinator.release(activation_id))
        self.assertFalse(harness.evaluator.latched)

    def test_after_release_a_new_utterance_is_admitted_again(self):
        harness = CoordinatorHarness()
        detection = harness.offer_and_admit()
        harness.coordinator.release(detection.activation_id)
        harness.controller.finish(activation_id=detection.activation_id)
        harness.controller.input_closed(
            activation_id=detection.activation_id,
            activation_sequence=harness.controller.snapshot().get(
                "activationSequence", 1
            ),
        )

        second = harness.offer_and_admit()
        self.assertIsNotNone(second)
        self.assertEqual(len(harness.published), 2)
        self.assertNotEqual(second.activation_id, detection.activation_id)

    def test_reset_starts_a_new_generation_and_drops_the_latch(self):
        harness = CoordinatorHarness()
        harness.offer_and_admit()
        generation = harness.coordinator.reset()
        self.assertFalse(harness.evaluator.latched)
        self.assertIsNone(harness.coordinator.accepted_detection)
        # A callback from the previous generation is inert.
        self.assertIsNone(
            harness.evaluator.offer([candidate(generation=generation - 1)])
        )


class WakeRaceTests(unittest.TestCase):
    REPEATS = 30

    def test_two_concurrent_wake_candidates_open_exactly_one_activation(self):
        for iteration in range(self.REPEATS):
            with self.subTest(iteration=iteration):
                harness = CoordinatorHarness()
                barrier = threading.Barrier(2)
                results = []
                lock = threading.Lock()

                def worker(identifier):
                    barrier.wait()
                    detection = harness.offer_and_admit(
                        candidate(identifier=identifier)
                    )
                    with lock:
                        results.append(detection)

                threads = [
                    threading.Thread(target=worker, args=("hey_jarvis",)),
                    threading.Thread(target=worker, args=("alexa",)),
                ]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=5)
                    self.assertFalse(thread.is_alive())

                accepted = [item for item in results if item is not None]
                self.assertEqual(len(accepted), 1)
                self.assertEqual(len(harness.published), 1)
                self.assertEqual(harness.controller.snapshot()["phase"],
                                 "waiting_first_speech")

    def test_manual_and_wake_race_produces_one_activation_and_one_source(self):
        for iteration in range(self.REPEATS):
            with self.subTest(iteration=iteration):
                harness = CoordinatorHarness()
                barrier = threading.Barrier(2)
                outcomes = {}
                lock = threading.Lock()

                def manual():
                    barrier.wait()
                    decision = harness.controller.activate("manual")
                    with lock:
                        outcomes["manual"] = decision.accepted

                def wake():
                    barrier.wait()
                    detection = harness.offer_and_admit()
                    with lock:
                        outcomes["wake"] = detection is not None

                threads = [
                    threading.Thread(target=manual),
                    threading.Thread(target=wake),
                ]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=5)
                    self.assertFalse(thread.is_alive())

                self.assertEqual(
                    sum(1 for value in outcomes.values() if value), 1
                )
                snapshot = harness.controller.snapshot()
                self.assertIn(snapshot["primarySource"], ("manual", "wake_word"))
                if snapshot["primarySource"] == "manual":
                    self.assertEqual(harness.published, [])
                else:
                    self.assertEqual(len(harness.published), 1)

    def test_a_duplicate_raw_candidate_burst_yields_one_detection(self):
        for iteration in range(self.REPEATS):
            with self.subTest(iteration=iteration):
                harness = CoordinatorHarness()
                start = threading.Event()
                results = []
                lock = threading.Lock()

                def worker():
                    start.wait(timeout=5)
                    detection = harness.offer_and_admit()
                    with lock:
                        results.append(detection)

                threads = [threading.Thread(target=worker) for _ in range(6)]
                for thread in threads:
                    thread.start()
                start.set()
                for thread in threads:
                    thread.join(timeout=5)
                    self.assertFalse(thread.is_alive())

                self.assertEqual(
                    len([item for item in results if item is not None]), 1
                )
                self.assertEqual(len(harness.published), 1)


if __name__ == "__main__":
    unittest.main()
