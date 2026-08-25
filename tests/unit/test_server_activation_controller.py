import itertools
import threading
import time
import unittest

from api_fastapi_server.activation import (
    ActivationController,
    FINALIZING,
    FOLLOWUP_WAIT,
    INACTIVE,
    SEGMENT_ACTIVE,
    WAITING_FIRST_SPEECH,
)


class MonotonicFakeClock:
    def __init__(self, start=1000.0):
        self.monotonic_now = start

    def __call__(self):
        return self.monotonic_now


class ServerActivationControllerTests(unittest.TestCase):
    def setUp(self):
        self.clock = MonotonicFakeClock()
        self.controller = ActivationController(
            manual_trigger_enabled=True,
            wake_word_trigger_enabled=True,
            initial_speech_timeout=15.0,
            followup_timeout=3.0,
            extension_seconds=5.0,
            clock=self.clock,
            id_factory=lambda: "activation-42",
        )

    # Mandatory Test 1: Manual aktiviert aus inactive
    def test_01_manual_activates_from_inactive(self):
        res = self.controller.activate("manual")
        self.assertTrue(res.accepted)
        self.assertEqual(res.reason, "activated")
        self.assertEqual(res.snapshot["primarySource"], "manual")
        self.assertEqual(res.snapshot["sources"], ["manual"])
        self.assertEqual(res.snapshot["phase"], WAITING_FIRST_SPEECH)
        self.assertEqual(res.snapshot["deadline"], 1015.0)

    # Mandatory Test 2: Wake Word aktiviert aus inactive
    def test_02_wake_word_activates_from_inactive(self):
        res = self.controller.activate("wake_word")
        self.assertTrue(res.accepted)
        self.assertEqual(res.reason, "activated")
        self.assertEqual(res.snapshot["primarySource"], "wake_word")
        self.assertEqual(res.snapshot["sources"], ["wake_word"])
        self.assertEqual(res.snapshot["phase"], WAITING_FIRST_SPEECH)

    # Mandatory Test 3: Manual -> Manual verlängert
    def test_03_manual_manual_extends(self):
        self.controller.activate("manual")
        res = self.controller.extend("manual")
        self.assertTrue(res.accepted)
        self.assertEqual(res.reason, "extended")
        self.assertEqual(res.snapshot["primarySource"], "manual")
        self.assertEqual(res.snapshot["sources"], ["manual"])
        self.assertEqual(res.snapshot["deadline"], 1020.0)

    # Mandatory Test 4: Wake Word -> Wake Word verlängert
    def test_04_wake_word_wake_word_extends(self):
        self.controller.activate("wake_word")
        res = self.controller.extend("wake_word")
        self.assertTrue(res.accepted)
        self.assertEqual(res.snapshot["primarySource"], "wake_word")
        self.assertEqual(res.snapshot["sources"], ["wake_word"])
        self.assertEqual(res.snapshot["deadline"], 1020.0)

    # Mandatory Test 5: Manual -> Wake Word bleibt gleiche Activation
    def test_05_manual_then_wake_word_merges(self):
        act1 = self.controller.activate("manual")
        act2 = self.controller.activate("wake_word")

        self.assertTrue(act2.accepted)
        self.assertEqual(act2.reason, "merged")
        self.assertEqual(act2.snapshot["activationId"], act1.snapshot["activationId"])
        self.assertEqual(act2.snapshot["primarySource"], "manual")  # primarySource unchanged
        self.assertEqual(act2.snapshot["sources"], ["manual", "wake_word"])

    # Mandatory Test 6: Wake Word -> Manual bleibt gleiche Activation
    def test_06_wake_word_then_manual_merges(self):
        act1 = self.controller.activate("wake_word")
        act2 = self.controller.activate("manual")

        self.assertTrue(act2.accepted)
        self.assertEqual(act2.reason, "merged")
        self.assertEqual(act2.snapshot["activationId"], act1.snapshot["activationId"])
        self.assertEqual(act2.snapshot["primarySource"], "wake_word")  # primarySource unchanged
        self.assertEqual(act2.snapshot["sources"], ["wake_word", "manual"])

    # Mandatory Test 7: Nahezu simultane Trigger -> genau eine Activation
    def test_07_simultaneous_triggers_yield_single_activation(self):
        res1 = self.controller.activate("manual")
        res2 = self.controller.activate("wake_word")
        res3 = self.controller.activate("manual")

        self.assertEqual(res1.snapshot["activationId"], "activation-42")
        self.assertEqual(res2.snapshot["activationId"], "activation-42")
        self.assertEqual(res3.snapshot["activationId"], "activation-42")

    # Mandatory Test 8: primarySource bleibt stabil
    def test_08_primary_source_remains_stable_across_lifecycle(self):
        self.controller.activate("manual")
        self.controller.activate("wake_word")
        self.controller.recording_started()
        self.controller.extend("wake_word")

        snap = self.controller.snapshot()
        self.assertEqual(snap["primarySource"], "manual")
        self.assertEqual(snap["sources"], ["manual", "wake_word"])

    # Mandatory Test 9: sources enthält beide Trigger maximal einmal
    def test_09_sources_contains_triggers_without_duplicates(self):
        self.controller.activate("manual")
        self.controller.activate("manual")
        self.controller.extend("manual")
        self.controller.activate("wake_word")
        self.controller.extend("wake_word")
        self.controller.extend("manual")

        self.assertEqual(self.controller.snapshot()["sources"], ["manual", "wake_word"])

    # Mandatory Test 10: Recording Start Transition
    def test_10_recording_started_transition(self):
        self.controller.activate("manual")
        res = self.controller.recording_started()
        self.assertTrue(res.accepted)
        self.assertEqual(res.snapshot["phase"], SEGMENT_ACTIVE)
        self.assertIsNone(res.snapshot["deadline"])

    # Mandatory Test 11: Recording End Transition
    def test_11_recording_ended_transition(self):
        self.controller.activate("manual")
        self.controller.recording_started()
        res = self.controller.recording_ended()
        self.assertTrue(res.accepted)
        self.assertEqual(res.snapshot["phase"], FOLLOWUP_WAIT)
        self.assertEqual(res.snapshot["deadline"], 1003.0)  # 1000 + 3.0 followup

    # Mandatory Test 12: Erneuter Trigger während Follow-up -> Verlängerung
    def test_12_trigger_during_followup_extends_deadline(self):
        self.controller.activate("manual")
        self.controller.recording_started()
        self.controller.recording_ended()
        self.clock.monotonic_now = 1002.0

        res = self.controller.extend("manual")
        self.assertTrue(res.accepted)
        # deadline is max(1002, 1003) + 5.0 = 1008.0
        self.assertEqual(res.snapshot["deadline"], 1008.0)

    def test_baseline_repeated_extensions_accumulate(self):
        """Characterizes the inherited additive extension semantics.

        This is deliberately an Ist test, not the later refresh-style target:
        each call adds ``extension_seconds`` to the current deadline.
        """
        opened = self.controller.activate("manual")
        first = self.controller.extend("manual")
        second = self.controller.extend("manual")

        self.assertEqual(opened.snapshot["deadline"], 1015.0)
        self.assertEqual(first.snapshot["deadline"], 1020.0)
        self.assertEqual(second.snapshot["deadline"], 1025.0)

    def test_baseline_multiple_segments_share_one_activation(self):
        """Pins the current multi-segment controller path without a ledger."""
        opened = self.controller.activate("manual")

        self.controller.recording_started()
        first_end = self.controller.recording_ended()
        self.controller.recording_started()
        second_end = self.controller.recording_ended()

        self.assertEqual(first_end.snapshot["segments"], 1)
        self.assertEqual(second_end.snapshot["segments"], 2)
        self.assertEqual(
            second_end.snapshot["activationId"], opened.snapshot["activationId"]
        )
        self.assertEqual(second_end.snapshot["phase"], FOLLOWUP_WAIT)

    # Mandatory Test 13: Timeout -> Abschluss
    def test_13_timeout_expires_activation(self):
        opened = self.controller.activate("manual")
        version = opened.snapshot["version"]
        self.clock.monotonic_now = 1016.0

        expired = self.controller.expire(version)
        self.assertTrue(expired.accepted)
        self.assertEqual(expired.reason, "timed_out")
        self.assertFalse(expired.snapshot["active"])
        self.assertEqual(expired.snapshot["closedPrimarySource"], "manual")

    # Mandatory Test 14: Finish
    def test_14_finish_closes_activation(self):
        self.controller.activate("manual")
        res = self.controller.finish("manual")
        self.assertTrue(res.accepted)
        self.assertEqual(res.reason, "finished")
        self.assertFalse(res.snapshot["active"])

    # Mandatory Test 15: Cancel
    def test_15_cancel_closes_activation(self):
        self.controller.activate("manual")
        res = self.controller.cancel("manual")
        self.assertTrue(res.accepted)
        self.assertEqual(res.reason, "cancelled")
        self.assertFalse(res.snapshot["active"])

    # Mandatory Test 16: Doppelte Finish-/Cancel-Aufrufe
    def test_16_double_finish_or_cancel_is_idempotent(self):
        self.controller.activate("manual")
        res1 = self.controller.finish("manual")
        res2 = self.controller.finish("manual")
        self.assertTrue(res1.accepted)
        self.assertFalse(res2.accepted)
        self.assertEqual(res2.reason, "not_active")

        self.controller.activate("manual")
        c1 = self.controller.cancel("manual")
        c2 = self.controller.cancel("manual")
        self.assertTrue(c1.accepted)
        self.assertFalse(c2.accepted)

    # Mandatory Test 17: Alter Timer einer alten Generation
    def test_17_stale_timer_from_old_generation_ignored(self):
        opened = self.controller.activate("manual")
        old_ver = opened.snapshot["version"]
        self.controller.extend("manual")  # increments version
        self.clock.monotonic_now = 2000.0

        stale = self.controller.expire(old_ver)
        self.assertFalse(stale.accepted)
        self.assertEqual(stale.reason, "stale_timer")
        self.assertTrue(stale.snapshot["active"])

    # Mandatory Test 18: Systemzeitänderung darf monotone Deadlines nicht stören
    def test_18_system_clock_jump_does_not_affect_monotonic_deadlines(self):
        # Even if wallclock changes dramatically, monotonic clock drives expiry
        opened = self.controller.activate("manual")
        ver = opened.snapshot["version"]
        # Monotonic time advances by 10s (deadline is 15s)
        self.clock.monotonic_now = 1010.0
        stale = self.controller.expire(ver)
        self.assertFalse(stale.accepted)
        self.assertEqual(stale.reason, "not_due")

        # Monotonic time advances past deadline (1015.0)
        self.clock.monotonic_now = 1016.0
        exp = self.controller.expire(ver)
        self.assertTrue(exp.accepted)

    # Mandatory Test 19: Reset
    def test_19_reset_clears_activation(self):
        self.controller.activate("manual")
        res = self.controller.reset()
        self.assertTrue(res.accepted)
        self.assertEqual(res.reason, "reset")
        self.assertFalse(res.snapshot["active"])

    # Mandatory Test 20: Reconnect / Session Close Semantik
    def test_20_session_close_and_reconnect_clears_activation(self):
        self.controller.activate("manual")
        self.controller.recording_started()
        reset_res = self.controller.reset()
        self.assertTrue(reset_res.accepted)
        self.assertEqual(self.controller.snapshot()["phase"], INACTIVE)
        self.assertIsNone(self.controller.snapshot()["activationId"])

    def test_disabled_source_rejected(self):
        c = ActivationController(
            manual_trigger_enabled=False,
            wake_word_trigger_enabled=True,
            clock=self.clock,
        )
        self.assertEqual(c.activate("manual").reason, "trigger_disabled")

    def test_both_disabled_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            ActivationController(
                manual_trigger_enabled=False,
                wake_word_trigger_enabled=False,
            )


class GenerationAndVersionTests(unittest.TestCase):
    """GATE 2: generation identifies an activation, version invalidates timers."""

    def setUp(self):
        self.clock = MonotonicFakeClock()
        self.ids = iter(f"act-{index}" for index in range(1, 50))
        self.controller = ActivationController(
            manual_trigger_enabled=True,
            wake_word_trigger_enabled=True,
            clock=self.clock,
            id_factory=lambda: next(self.ids),
        )

    def test_generation_is_stable_for_one_activation(self):
        opened = self.controller.activate("manual")
        generation = opened.snapshot["generation"]

        for step in (
            lambda: self.controller.activate("wake_word"),
            lambda: self.controller.extend("manual"),
            lambda: self.controller.recording_started(),
            lambda: self.controller.recording_ended(),
        ):
            result = step()
            self.assertEqual(
                result.snapshot["generation"],
                generation,
                "generation must not move inside one activation",
            )

    def test_version_moves_on_every_state_change(self):
        seen = []
        seen.append(self.controller.activate("manual").snapshot["version"])
        seen.append(self.controller.activate("wake_word").snapshot["version"])
        seen.append(self.controller.extend("manual").snapshot["version"])
        seen.append(self.controller.recording_started().snapshot["version"])
        seen.append(self.controller.recording_ended().snapshot["version"])
        self.assertEqual(seen, sorted(set(seen)), f"version must increase: {seen}")

    def test_a_new_activation_raises_the_generation(self):
        first = self.controller.activate("manual")
        self.controller.cancel("manual")
        second = self.controller.activate("wake_word")
        self.assertGreater(
            second.snapshot["generation"], first.snapshot["generation"]
        )
        self.assertNotEqual(
            second.snapshot["activationId"], first.snapshot["activationId"]
        )

    def test_a_merge_does_not_raise_the_generation(self):
        first = self.controller.activate("manual")
        merged = self.controller.activate("wake_word")
        self.assertEqual(merged.reason, "merged")
        self.assertEqual(
            merged.snapshot["generation"], first.snapshot["generation"]
        )
        self.assertEqual(
            merged.snapshot["activationId"], first.snapshot["activationId"]
        )


class FinalizingPhaseTests(unittest.TestCase):
    """The lifecycle of the specification ends via ``finalizing``."""

    def setUp(self):
        self.clock = MonotonicFakeClock()
        self.controller = ActivationController(
            manual_trigger_enabled=True,
            wake_word_trigger_enabled=True,
            clock=self.clock,
            id_factory=lambda: "act-final",
        )

    def test_finish_after_a_segment_enters_finalizing_and_keeps_the_id(self):
        self.controller.activate("manual")
        self.controller.recording_started()
        self.controller.recording_ended()
        closed = self.controller.finish("manual")

        self.assertTrue(closed.accepted)
        self.assertEqual(closed.snapshot["phase"], FINALIZING)
        # The window is shut - the recorder gate must close with it ...
        self.assertFalse(closed.snapshot["windowOpen"])
        # ... but the id survives so the trailing final can be correlated.
        self.assertEqual(closed.snapshot["activationId"], "act-final")
        self.assertEqual(closed.snapshot["closedActivationId"], "act-final")

        done = self.controller.finalized()
        self.assertTrue(done.accepted)
        self.assertEqual(done.snapshot["phase"], INACTIVE)
        self.assertIsNone(done.snapshot["activationId"])

    def test_finish_without_a_segment_goes_straight_to_inactive(self):
        self.controller.activate("manual")
        closed = self.controller.finish("manual")
        self.assertEqual(closed.snapshot["phase"], INACTIVE)
        self.assertIsNone(closed.snapshot["activationId"])

    def test_cancel_discards_the_turn_without_finalizing(self):
        self.controller.activate("manual")
        self.controller.recording_started()
        closed = self.controller.cancel("manual")
        self.assertEqual(closed.snapshot["phase"], INACTIVE)
        self.assertIsNone(closed.snapshot["activationId"])

    def test_a_trigger_during_finalizing_opens_a_new_activation(self):
        self.controller.activate("manual")
        self.controller.recording_started()
        first = self.controller.finish("manual")
        self.assertEqual(first.snapshot["phase"], FINALIZING)

        reopened = self.controller.activate("manual")
        self.assertEqual(reopened.reason, "activated")
        self.assertGreater(
            reopened.snapshot["generation"], first.snapshot["generation"]
        )
        self.assertEqual(reopened.snapshot["phase"], WAITING_FIRST_SPEECH)

    def test_reset_also_clears_a_finalizing_activation(self):
        self.controller.activate("manual")
        self.controller.recording_started()
        self.controller.finish("manual")
        cleared = self.controller.reset()
        self.assertTrue(cleared.accepted)
        self.assertEqual(cleared.snapshot["phase"], INACTIVE)
        self.assertIsNone(cleared.snapshot["activationId"])


class InvalidTransitionTests(unittest.TestCase):
    """GATE 2 requires invalid transitions to be tested explicitly."""

    def setUp(self):
        self.clock = MonotonicFakeClock()
        self.controller = ActivationController(
            manual_trigger_enabled=True,
            wake_word_trigger_enabled=True,
            clock=self.clock,
            id_factory=lambda: "act-invalid",
        )

    def test_operations_on_an_inactive_controller_are_refused(self):
        for name, call in (
            ("extend", lambda: self.controller.extend("manual")),
            ("recording_started", self.controller.recording_started),
            ("recording_ended", self.controller.recording_ended),
            ("finish", lambda: self.controller.finish("manual")),
            ("cancel", lambda: self.controller.cancel("manual")),
        ):
            with self.subTest(operation=name):
                result = call()
                self.assertFalse(result.accepted)
                self.assertEqual(result.reason, "not_active")
                self.assertEqual(result.snapshot["phase"], INACTIVE)

    def test_finalized_outside_finalizing_is_refused(self):
        self.assertEqual(self.controller.finalized().reason, "not_finalizing")
        self.controller.activate("manual")
        self.assertEqual(self.controller.finalized().reason, "not_finalizing")

    def test_unknown_source_is_refused_everywhere(self):
        self.controller.activate("manual")
        for name, call in (
            ("activate", lambda: self.controller.activate("telepathy")),
            ("extend", lambda: self.controller.extend("telepathy")),
            ("finish", lambda: self.controller.finish("")),
            ("cancel", lambda: self.controller.cancel(None)),
        ):
            with self.subTest(operation=name):
                result = call()
                self.assertFalse(result.accepted)
                self.assertEqual(result.reason, "trigger_disabled")
        # The running activation is untouched by all of that.
        self.assertEqual(self.controller.snapshot()["activationId"], "act-invalid")

    def test_recording_started_twice_does_not_count_a_second_segment(self):
        self.controller.activate("manual")
        first = self.controller.recording_started()
        second = self.controller.recording_started()
        self.assertEqual(first.reason, "recording_started")
        self.assertEqual(second.reason, "already_recording")
        self.assertEqual(second.snapshot["segments"], 1)

    def test_expire_is_refused_when_no_deadline_is_armed(self):
        self.controller.activate("manual")
        started = self.controller.recording_started()
        # While recording there is no deadline; a timeout must not fire.
        result = self.controller.expire(started.snapshot["version"])
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "not_expirable")

    def test_expire_on_an_inactive_controller_is_refused(self):
        result = self.controller.expire(self.controller.snapshot()["version"])
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "not_expirable")


class ConcurrentTriggerTests(unittest.TestCase):
    """Case 7 with real threads: near-simultaneous triggers yield one activation.

    The state machine is reached from the WebSocket coroutine, from recorder
    callback threads and from the timeout thread, so it has to serialise
    itself.

    A plain barrier is not enough to prove that: the critical section of
    ``activate`` is so short that the threads practically never interleave
    inside it, and the test then stays green even without a lock. That was
    verified by mutation - replacing the lock with a no-op did not turn the
    naive version red.

    These tests therefore widen the window on purpose. ``id_factory`` is called
    *inside* the critical section, so an injected factory that sleeps holds the
    section open long enough for every other thread to reach it. Without a lock
    all threads would pass the "is a window already open?" check and each would
    open its own activation.
    """

    REPEATS = 12
    HOLD_SECONDS = 0.01

    def _slow_id_factory(self):
        counter = itertools.count(1)

        def factory():
            # Widen the critical section so a missing lock becomes observable.
            time.sleep(self.HOLD_SECONDS)
            return f"act-{next(counter)}"

        return factory

    def _run_once(self):
        created = []
        created_lock = threading.Lock()
        controller = ActivationController(
            manual_trigger_enabled=True,
            wake_word_trigger_enabled=True,
            id_factory=self._slow_id_factory(),
        )
        start = threading.Barrier(8)

        def trigger(source):
            start.wait()
            result = controller.activate(source)
            if result.reason == "activated":
                with created_lock:
                    created.append(result.snapshot["activationId"])

        threads = [
            threading.Thread(target=trigger, args=("manual",))
            for _ in range(4)
        ] + [
            threading.Thread(target=trigger, args=("wake_word",))
            for _ in range(4)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        snapshot = controller.snapshot()
        self.assertEqual(
            len(created), 1, f"exactly one activation must open, got {created}"
        )
        self.assertEqual(snapshot["generation"], 1)
        self.assertEqual(sorted(snapshot["sources"]), ["manual", "wake_word"])
        self.assertIn(snapshot["primarySource"], ("manual", "wake_word"))
        # sources must never contain a duplicate
        self.assertEqual(len(snapshot["sources"]), len(set(snapshot["sources"])))

    def test_near_simultaneous_triggers_yield_exactly_one_activation(self):
        for _ in range(self.REPEATS):
            self._run_once()

    def test_a_reader_never_observes_a_half_built_activation(self):
        """A snapshot taken while ``activate`` runs must never be half applied.

        The slow id factory keeps the controller inside ``activate`` for a
        while; readers hammer ``snapshot()`` throughout. Without the lock a
        reader can see a phase that no longer matches the activation id.
        """
        for _ in range(self.REPEATS):
            controller = ActivationController(
                manual_trigger_enabled=True,
                wake_word_trigger_enabled=True,
                id_factory=self._slow_id_factory(),
            )
            torn = []
            stop = threading.Event()

            def reader():
                while not stop.is_set():
                    state = controller.snapshot()
                    open_window = state["windowOpen"]
                    has_id = state["activationId"] is not None
                    has_primary = state["primarySource"] is not None
                    if open_window and not (has_id and has_primary):
                        torn.append(state)
                    if state["phase"] == INACTIVE and state["sources"]:
                        torn.append(state)

            readers = [threading.Thread(target=reader) for _ in range(3)]
            for thread in readers:
                thread.start()
            try:
                controller.activate("manual")
                controller.recording_started()
                controller.recording_ended()
                controller.cancel("manual")
                controller.activate("wake_word")
            finally:
                stop.set()
                for thread in readers:
                    thread.join(timeout=10)
            self.assertEqual(torn, [], f"observed an inconsistent snapshot: {torn[:2]}")


if __name__ == "__main__":
    unittest.main()
