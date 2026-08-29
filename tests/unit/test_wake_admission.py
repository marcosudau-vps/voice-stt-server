"""AP-SRV-060: the wake admission coordinator, the latch and its races.

The latch deliberately lives here and not in the ``ActivationController``:
AP-SRV-010/030 stay the one source-neutral activation authority. These tests
therefore drive the real ``ActivationController`` and only fake the detector.

Since AP-SRV-060 C3 the unit that reaches the admission is a finalized
:class:`~VoiceSTT.core.wake_detection.WakeHit` - one contiguous region of
prediction frames - and no longer a per-chunk raw candidate. The exactly-once
mint of the logical ``wakeword.detected`` is covered in
``test_wakeword_root_findings_c3.py``.

Every concurrency case is synchronised with ``threading.Barrier`` /
``threading.Event`` - never with sleeps.
"""

import threading
import unittest

from api_fastapi_server.activation import ActivationController
from api_fastapi_server.wake_admission import WakeAdmissionCoordinator
from VoiceSTT.core.wake_detection import (
    WakeAttemptPolicy,
    WakeDetectionEvaluator,
    WakeHit,
)


FRAME = 1280


def hit(identifier="hey_jarvis", score=0.9, *, cooldown_ms=0):
    """A finalized hit region, as the tracker would hand it over."""
    return WakeHit(
        canonical_wake_word_id=identifier,
        peak_score=score,
        start_frame_index=0,
        start_sample=FRAME,
        qualification_frame_index=0,
        qualification_sample=FRAME,
        finalization_frame_index=1,
        operational_zero_point_sample=FRAME,
        prediction_frame_count=1,
        policy=WakeAttemptPolicy(sensitivity=0.5, cooldown_ms=cooldown_ms),
    )


class CoordinatorHarness:
    """One evaluator, one real controller, one coordinator."""

    def __init__(self, *, manual=True, wake_word=True, cooldown_ms=0):
        self.controller = ActivationController(
            manual_trigger_enabled=manual,
            wake_word_trigger_enabled=wake_word,
        )
        self.policy = WakeAttemptPolicy(
            sensitivity=0.5,
            min_consecutive_prediction_frames=1,
            cooldown_ms=cooldown_ms,
        )
        self.evaluator = WakeDetectionEvaluator(
            policy_supplier=lambda: self.policy
        )
        self.published = []
        self.coordinator = WakeAdmissionCoordinator(
            evaluator=self.evaluator,
            activate=self._activate,
            publish=self.published.append,
        )
        self._end_sample = 0

    def _activate(self, _hit, _boundary):
        decision = self.controller.activate("wake_word")
        if not decision.accepted:
            return None
        return decision.snapshot.get("activationId")

    def detect(self, identifier="hey_jarvis", score=0.9):
        """One spoken wake word: a run above the threshold, then below it."""
        finalized = None
        for value in (score, 0.0):
            self._end_sample += FRAME
            offered = self.evaluator.observe_scores(
                {identifier: value}, end_sample=self._end_sample
            )
            if offered is not None:
                finalized = offered
        return finalized

    def offer_and_admit(self, identifier="hey_jarvis", score=0.9):
        offered = self.detect(identifier, score)
        if offered is None:
            return None
        return self.coordinator.admit(offered)

    def admit_hit(self, identifier="hey_jarvis"):
        """Admits a finalized hit directly, bypassing the detector gate."""
        return self.coordinator.admit(hit(identifier))


class AcceptedDetectionTests(unittest.TestCase):
    def test_an_accepted_hit_publishes_exactly_one_detection(self):
        harness = CoordinatorHarness()
        detection = harness.offer_and_admit()

        self.assertIsNotNone(detection)
        self.assertEqual(len(harness.published), 1)
        self.assertEqual(harness.coordinator.logical_event_count(), 1)
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
        self.assertEqual(harness.coordinator.logical_event_count(), 1)

    def test_a_sustained_score_stays_one_logical_hit(self):
        """Many prediction frames of one utterance are one hit, not many."""
        harness = CoordinatorHarness()
        end_sample = 0
        offered = []
        for value in [0.9] * 40 + [0.0]:
            end_sample += FRAME
            result = harness.evaluator.observe_scores(
                {"hey_jarvis": value}, end_sample=end_sample
            )
            if result is not None:
                offered.append(result)
        self.assertEqual(len(offered), 1)
        self.assertEqual(offered[0].prediction_frame_count, 40)
        harness.coordinator.admit(offered[0])
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
        self.assertEqual(harness.coordinator.logical_event_count(), 0)
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

    def test_a_refused_admission_arms_the_configured_cooldown(self):
        harness = CoordinatorHarness(cooldown_ms=60000)
        harness.controller.activate("manual")
        harness.offer_and_admit()
        # The operator's cooldown blocks the next hit; there is no implicit
        # window beyond it (AP-SRV-060 C3, section 9.1).
        self.assertIsNone(harness.detect())

    def test_a_failing_activation_is_treated_as_a_refusal(self):
        harness = CoordinatorHarness()

        def boom(_hit, _boundary):
            raise RuntimeError("controller unavailable")

        coordinator = WakeAdmissionCoordinator(
            evaluator=harness.evaluator,
            activate=boom,
            publish=harness.published.append,
        )
        self.assertIsNone(coordinator.admit(hit()))
        self.assertEqual(harness.published, [])
        self.assertEqual(coordinator.logical_event_count(), 0)
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
        self.assertEqual(harness.coordinator.logical_event_count(), 2)
        self.assertNotEqual(second.activation_id, detection.activation_id)

    def test_reset_starts_a_new_generation_and_drops_the_latch(self):
        harness = CoordinatorHarness()
        harness.offer_and_admit()
        generation = harness.coordinator.reset()
        self.assertGreater(generation, 0)
        self.assertFalse(harness.evaluator.latched)
        self.assertIsNone(harness.coordinator.accepted_detection)
        # The tracker starts over: no half-finished region survives the reset.
        self.assertFalse(harness.evaluator.tracker.active)
        # The already minted logical events are history and stay in the ledger.
        self.assertEqual(harness.coordinator.logical_event_count(), 1)


class WakeRaceTests(unittest.TestCase):
    REPEATS = 30

    def test_two_concurrent_wake_hits_open_exactly_one_activation(self):
        for iteration in range(self.REPEATS):
            with self.subTest(iteration=iteration):
                harness = CoordinatorHarness()
                barrier = threading.Barrier(2)
                results = []
                lock = threading.Lock()

                def worker(identifier):
                    barrier.wait()
                    detection = harness.admit_hit(identifier)
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
                self.assertEqual(harness.coordinator.logical_event_count(), 1)
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
                    detection = harness.admit_hit()
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
                    self.assertEqual(
                        harness.coordinator.logical_event_count(), 0
                    )
                else:
                    self.assertEqual(len(harness.published), 1)
                    self.assertEqual(
                        harness.coordinator.logical_event_count(), 1
                    )

    def test_a_duplicate_hit_burst_yields_one_detection(self):
        for iteration in range(self.REPEATS):
            with self.subTest(iteration=iteration):
                harness = CoordinatorHarness()
                start = threading.Event()
                results = []
                lock = threading.Lock()

                def worker():
                    start.wait(timeout=5)
                    detection = harness.admit_hit()
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
                self.assertEqual(harness.coordinator.logical_event_count(), 1)


if __name__ == "__main__":
    unittest.main()
