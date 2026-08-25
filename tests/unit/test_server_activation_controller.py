import itertools
import threading
import time
import unittest
from unittest import mock

from api_fastapi_server.activation import (
    ActivationController,
    CLOSING_INPUT,
    FOLLOWUP_WAIT,
    IDLE,
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
        self.ids = iter(f"activation-{index}" for index in range(1, 20))
        self.controller = ActivationController(
            manual_trigger_enabled=True,
            wake_word_trigger_enabled=True,
            initial_speech_timeout=15.0,
            followup_timeout=3.0,
            extension_seconds=5.0,
            clock=self.clock,
            id_factory=lambda: next(self.ids),
        )

    def test_canonical_foreground_uses_exactly_five_phase_values(self):
        observed = {self.controller.snapshot()["phase"]}
        self.controller.activate("manual")
        observed.add(self.controller.snapshot()["phase"])
        self.controller.recording_started()
        observed.add(self.controller.snapshot()["phase"])
        self.controller.recording_ended()
        observed.add(self.controller.snapshot()["phase"])
        self.controller.finish("manual")
        observed.add(self.controller.snapshot()["phase"])
        self.controller.input_closed()
        observed.add(self.controller.snapshot()["phase"])

        self.assertEqual(
            observed,
            {
                IDLE,
                WAITING_FIRST_SPEECH,
                SEGMENT_ACTIVE,
                FOLLOWUP_WAIT,
                CLOSING_INPUT,
            },
        )
        self.assertNotIn("finalizing", observed)
        self.assertNotIn("inactive", observed)

    def test_first_trigger_latches_identity_sequence_source_and_settings(self):
        settings = {
            "language": "de",
            "nested": {"models": ["small", "large"]},
        }
        opened = self.controller.activate("manual", settings)

        self.assertTrue(opened.accepted)
        self.assertEqual(opened.reason, "activated")
        self.assertEqual(opened.snapshot["activationId"], "activation-1")
        self.assertEqual(opened.snapshot["activationSequence"], 1)
        self.assertEqual(opened.snapshot["generation"], 1)
        self.assertEqual(opened.snapshot["primarySource"], "manual")
        self.assertEqual(opened.snapshot["sources"], ["manual"])
        self.assertEqual(opened.snapshot["effectiveSettings"], settings)
        self.assertEqual(opened.snapshot["phase"], WAITING_FIRST_SPEECH)
        self.assertEqual(opened.snapshot["deadline"], 1015.0)

    def test_effective_settings_are_deeply_detached_and_snapshot_is_defensive(self):
        settings = {"language": "de", "nested": {"models": ["small"]}}
        self.controller.activate("manual", settings)
        settings["language"] = "en"
        settings["nested"]["models"].append("large")

        first = self.controller.snapshot()
        first["effectiveSettings"]["nested"]["models"].append("mutated")
        second = self.controller.snapshot()

        self.assertEqual(second["effectiveSettings"]["language"], "de")
        self.assertEqual(
            second["effectiveSettings"]["nested"]["models"], ["small"]
        )

    def test_new_activation_is_locked_in_every_non_idle_phase(self):
        phase_setups = (
            (WAITING_FIRST_SPEECH, lambda: None),
            (SEGMENT_ACTIVE, self.controller.recording_started),
            (
                FOLLOWUP_WAIT,
                lambda: (
                    self.controller.recording_started(),
                    self.controller.recording_ended(),
                ),
            ),
            (CLOSING_INPUT, lambda: self.controller.finish("manual")),
        )
        for expected_phase, prepare in phase_setups:
            with self.subTest(phase=expected_phase):
                self.controller.reset()
                opened = self.controller.activate(
                    "manual", {"owner": expected_phase}
                )
                prepare()
                before = self.controller.snapshot()
                rejected = self.controller.activate(
                    "wake_word", {"owner": "replacement"}
                )

                self.assertFalse(rejected.accepted)
                self.assertEqual(rejected.reason, "activation_locked")
                self.assertFalse(rejected.changed)
                self.assertEqual(rejected.snapshot, before)
                self.assertEqual(
                    rejected.snapshot["activationId"],
                    opened.snapshot["activationId"],
                )
                self.assertEqual(rejected.snapshot["primarySource"], "manual")
                self.assertEqual(rejected.snapshot["sources"], ["manual"])
                self.assertEqual(
                    rejected.snapshot["effectiveSettings"],
                    {"owner": expected_phase},
                )

    def _assert_first_trigger_order(self, first_source, second_source):
        opened = self.controller.activate(
            first_source, {"latchedFor": first_source}
        )
        before = self.controller.snapshot()
        locked = self.controller.activate(
            second_source, {"latchedFor": second_source}
        )

        self.assertFalse(locked.accepted)
        self.assertEqual(locked.reason, "activation_locked")
        self.assertEqual(locked.snapshot, before)
        self.assertEqual(
            locked.snapshot["activationId"], opened.snapshot["activationId"]
        )
        self.assertEqual(locked.snapshot["activationSequence"], 1)
        self.assertEqual(locked.snapshot["primarySource"], first_source)
        self.assertEqual(locked.snapshot["sources"], [first_source])
        self.assertEqual(
            locked.snapshot["effectiveSettings"],
            {"latchedFor": first_source},
        )

    def test_manual_then_wake_word_latches_manual_and_locks_wake_word(self):
        self._assert_first_trigger_order("manual", "wake_word")

    def test_wake_word_then_manual_latches_wake_word_and_locks_manual(self):
        self._assert_first_trigger_order("wake_word", "manual")

    def test_sequence_is_stable_and_version_tracks_only_effective_changes(self):
        opened = self.controller.activate("manual")
        sequence = opened.snapshot["activationSequence"]
        versions = [opened.snapshot["version"]]

        locked = self.controller.activate("wake_word")
        self.assertEqual(locked.snapshot["version"], versions[-1])
        self.assertEqual(locked.snapshot["activationSequence"], sequence)

        for transition in (
            lambda: self.controller.extend("manual"),
            self.controller.recording_started,
            self.controller.recording_ended,
            lambda: self.controller.finish("manual"),
            self.controller.input_closed,
        ):
            changed = transition()
            self.assertTrue(changed.changed)
            self.assertGreater(changed.snapshot["version"], versions[-1])
            versions.append(changed.snapshot["version"])
            self.assertEqual(
                changed.snapshot["activationSequence"], sequence
            )

        second = self.controller.activate("wake_word")
        self.assertEqual(second.snapshot["activationSequence"], sequence + 1)

    def test_recording_transitions_support_multiple_serial_segments(self):
        opened = self.controller.activate("wake_word")
        first_start = self.controller.recording_started()
        first_end = self.controller.recording_ended()
        second_start = self.controller.recording_started()
        second_end = self.controller.recording_ended()

        self.assertEqual(first_start.snapshot["phase"], SEGMENT_ACTIVE)
        self.assertEqual(first_end.snapshot["phase"], FOLLOWUP_WAIT)
        self.assertEqual(second_start.snapshot["segments"], 2)
        self.assertEqual(second_end.snapshot["segments"], 2)
        self.assertEqual(
            second_end.snapshot["activationId"], opened.snapshot["activationId"]
        )
        self.assertEqual(second_end.snapshot["activationSequence"], 1)
        self.assertEqual(second_end.snapshot["primarySource"], "wake_word")

    def test_duplicate_recording_start_is_idempotent_and_counts_one_segment(self):
        self.controller.activate("manual")
        first = self.controller.recording_started()
        second = self.controller.recording_started()

        self.assertTrue(second.accepted)
        self.assertEqual(first.reason, "recording_started")
        self.assertEqual(second.reason, "already_recording")
        self.assertFalse(second.changed)
        self.assertEqual(second.snapshot["version"], first.snapshot["version"])
        self.assertEqual(second.snapshot["phase"], SEGMENT_ACTIVE)
        self.assertEqual(second.snapshot["segments"], 1)

    def test_recording_end_requires_an_active_segment(self):
        opened = self.controller.activate("manual")
        ended = self.controller.recording_ended()
        self.assertFalse(ended.accepted)
        self.assertEqual(ended.reason, "not_active")
        self.assertEqual(ended.snapshot, opened.snapshot)

    def test_finish_has_explicit_close_barrier_then_idle(self):
        opened = self.controller.activate("manual", {"language": "de"})
        self.controller.recording_started()
        closing = self.controller.finish("manual")

        self.assertTrue(closing.accepted)
        self.assertEqual(closing.snapshot["phase"], CLOSING_INPUT)
        self.assertFalse(closing.snapshot["windowOpen"])
        self.assertEqual(
            closing.snapshot["activationId"], opened.snapshot["activationId"]
        )
        self.assertEqual(closing.snapshot["closeReason"], "finished")

        idle = self.controller.input_closed()
        self.assertTrue(idle.accepted)
        self.assertEqual(idle.snapshot["phase"], IDLE)
        self.assertIsNone(idle.snapshot["activationId"])
        self.assertEqual(
            idle.snapshot["closedActivationId"], opened.snapshot["activationId"]
        )
        self.assertEqual(idle.snapshot["closedSegments"], 1)
        self.assertEqual(idle.snapshot["closeReason"], "finished")

    def test_finish_without_segment_still_uses_the_close_barrier(self):
        opened = self.controller.activate("manual")
        closing = self.controller.finish("manual")
        self.assertEqual(closing.snapshot["phase"], CLOSING_INPUT)
        self.assertEqual(closing.snapshot["activationId"], opened.snapshot["activationId"])
        idle = self.controller.input_closed()
        self.assertEqual(idle.snapshot["phase"], IDLE)
        self.assertEqual(idle.snapshot["closedSegments"], 0)
        self.assertEqual(idle.snapshot["closeReason"], "finished")

    def test_cancel_uses_the_same_close_barrier_and_preserves_its_reason(self):
        opened = self.controller.activate("manual")
        closing = self.controller.cancel("manual")
        self.assertEqual(closing.snapshot["phase"], CLOSING_INPUT)
        self.assertEqual(closing.snapshot["activationId"], opened.snapshot["activationId"])
        idle = self.controller.input_closed()
        self.assertEqual(idle.snapshot["phase"], IDLE)
        self.assertEqual(idle.snapshot["closeReason"], "cancelled")

    def test_repeated_finish_and_cancel_do_not_repeat_the_close_transition(self):
        for first_action in ("finish", "cancel"):
            with self.subTest(first_action=first_action):
                self.controller.reset()
                opened = self.controller.activate("manual")
                first = getattr(self.controller, first_action)("manual")
                before = self.controller.snapshot()

                self.assertTrue(first.accepted)
                self.assertEqual(first.snapshot["phase"], CLOSING_INPUT)
                for repeated_action in ("finish", "cancel"):
                    repeated = getattr(
                        self.controller, repeated_action
                    )("manual")
                    self.assertFalse(repeated.accepted)
                    self.assertEqual(repeated.reason, "not_active")
                    self.assertFalse(repeated.changed)
                    self.assertEqual(repeated.snapshot, before)
                    self.assertEqual(
                        repeated.snapshot["activationId"],
                        opened.snapshot["activationId"],
                    )

    def test_new_activation_after_close_gets_new_id_and_sequence(self):
        first = self.controller.activate("manual")
        self.controller.cancel("manual")
        self.assertEqual(
            self.controller.activate("wake_word").reason, "activation_locked"
        )
        self.controller.input_closed()
        second = self.controller.activate("wake_word")

        self.assertEqual(second.snapshot["activationSequence"], 2)
        self.assertGreater(
            second.snapshot["activationSequence"],
            first.snapshot["activationSequence"],
        )
        self.assertNotEqual(
            second.snapshot["activationId"], first.snapshot["activationId"]
        )

    def test_timeout_enters_close_barrier_and_stale_timer_is_rejected(self):
        opened = self.controller.activate("manual")
        old_version = opened.snapshot["version"]
        self.controller.extend("manual")
        self.clock.monotonic_now = 2000.0
        stale = self.controller.expire(old_version)
        self.assertFalse(stale.accepted)
        self.assertEqual(stale.reason, "stale_timer")

        current_version = self.controller.snapshot()["version"]
        expired = self.controller.expire(current_version)
        self.assertTrue(expired.accepted)
        self.assertEqual(expired.reason, "timed_out")
        self.assertEqual(expired.snapshot["phase"], CLOSING_INPUT)
        self.assertEqual(expired.snapshot["closeReason"], "timed_out")

    def test_expire_without_active_deadline_is_effect_free(self):
        idle_before = self.controller.snapshot()
        idle_expire = self.controller.expire(idle_before["version"])
        self.assertFalse(idle_expire.accepted)
        self.assertEqual(idle_expire.reason, "not_expirable")
        self.assertEqual(idle_expire.snapshot, idle_before)

        self.controller.activate("manual")
        recording = self.controller.recording_started()
        segment_expire = self.controller.expire(recording.snapshot["version"])
        self.assertFalse(segment_expire.accepted)
        self.assertEqual(segment_expire.reason, "not_expirable")
        self.assertEqual(segment_expire.snapshot, recording.snapshot)

    def test_wallclock_jumps_do_not_change_monotonic_deadline_or_expiry(self):
        with mock.patch(
            "api_fastapi_server.activation.time.time", return_value=10**12
        ):
            opened = self.controller.activate("manual")
        version = opened.snapshot["version"]
        self.assertEqual(opened.snapshot["deadline"], 1015.0)

        self.clock.monotonic_now = 1010.0
        with mock.patch(
            "api_fastapi_server.activation.time.time", return_value=-10**12
        ):
            early = self.controller.expire(version)
        self.assertFalse(early.accepted)
        self.assertEqual(early.reason, "not_due")
        self.assertEqual(early.snapshot["deadline"], 1015.0)

        self.clock.monotonic_now = 1016.0
        expired = self.controller.expire(version)
        self.assertTrue(expired.accepted)
        self.assertEqual(expired.snapshot["phase"], CLOSING_INPUT)

    def test_extension_semantics_remain_out_of_scope_for_ap_srv_010(self):
        opened = self.controller.activate("manual")
        first = self.controller.extend("manual")
        second = self.controller.extend("manual")
        self.assertEqual(opened.snapshot["deadline"], 1015.0)
        self.assertEqual(first.snapshot["deadline"], 1020.0)
        self.assertEqual(second.snapshot["deadline"], 1025.0)

    def test_each_source_can_open_and_extend_its_own_activation(self):
        for source in ("manual", "wake_word"):
            with self.subTest(source=source):
                self.controller.reset()
                opened = self.controller.activate(source)
                extended = self.controller.extend(source)
                self.assertTrue(extended.accepted)
                self.assertEqual(extended.reason, "extended")
                self.assertEqual(
                    extended.snapshot["activationId"],
                    opened.snapshot["activationId"],
                )
                self.assertEqual(extended.snapshot["primarySource"], source)
                self.assertEqual(extended.snapshot["sources"], [source])
                self.assertEqual(extended.snapshot["deadline"], 1020.0)

    def test_followup_extensions_keep_the_inherited_additive_baseline(self):
        self.controller.activate("manual")
        self.controller.recording_started()
        followup = self.controller.recording_ended()
        self.clock.monotonic_now = 1002.0
        first = self.controller.extend("manual")
        second = self.controller.extend("manual")

        self.assertEqual(followup.snapshot["deadline"], 1003.0)
        self.assertEqual(first.snapshot["deadline"], 1008.0)
        self.assertEqual(second.snapshot["deadline"], 1013.0)
        self.assertEqual(second.snapshot["phase"], FOLLOWUP_WAIT)

    def test_each_enabled_source_can_extend_without_changing_first_source(self):
        self.controller.activate("manual")
        extended = self.controller.extend("wake_word")
        self.assertTrue(extended.accepted)
        self.assertEqual(extended.reason, "extended")
        self.assertEqual(extended.snapshot["primarySource"], "manual")
        self.assertEqual(extended.snapshot["sources"], ["manual"])

    def test_disabled_and_unknown_sources_are_rejected_without_mutation(self):
        controller = ActivationController(
            manual_trigger_enabled=False,
            wake_word_trigger_enabled=True,
            clock=self.clock,
        )
        before = controller.snapshot()
        for source in ("manual", "telepathy", None):
            result = controller.activate(source)
            self.assertFalse(result.accepted)
            self.assertEqual(result.reason, "trigger_disabled")
            self.assertEqual(result.snapshot, before)

    def test_non_idle_lock_precedes_recognized_source_enablement(self):
        controller = ActivationController(
            manual_trigger_enabled=True,
            wake_word_trigger_enabled=False,
            clock=self.clock,
        )
        opened = controller.activate("manual")
        locked = controller.activate("wake_word")
        self.assertFalse(locked.accepted)
        self.assertEqual(locked.reason, "activation_locked")
        self.assertEqual(
            locked.snapshot["activationId"], opened.snapshot["activationId"]
        )

    def test_unknown_source_is_rejected_by_every_source_command(self):
        self.controller.activate("manual")
        before = self.controller.snapshot()
        for operation in ("extend", "finish", "cancel"):
            with self.subTest(operation=operation):
                result = getattr(self.controller, operation)("telepathy")
                self.assertFalse(result.accepted)
                self.assertEqual(result.reason, "trigger_disabled")
                self.assertEqual(result.snapshot, before)

    def test_invalid_transitions_are_refused(self):
        for call, reason in (
            (lambda: self.controller.extend("manual"), "not_active"),
            (self.controller.recording_started, "not_active"),
            (self.controller.recording_ended, "not_active"),
            (lambda: self.controller.finish("manual"), "not_active"),
            (lambda: self.controller.cancel("manual"), "not_active"),
            (self.controller.input_closed, "not_closing_input"),
        ):
            result = call()
            self.assertFalse(result.accepted)
            self.assertEqual(result.reason, reason)
            self.assertEqual(result.snapshot["phase"], IDLE)

    def test_reset_clears_foreground_but_not_session_sequence(self):
        first = self.controller.activate("manual")
        reset = self.controller.reset()
        second = self.controller.activate("wake_word")
        self.assertEqual(reset.snapshot["phase"], IDLE)
        self.assertEqual(second.snapshot["activationSequence"], 2)
        self.assertGreater(
            second.snapshot["activationSequence"],
            first.snapshot["activationSequence"],
        )

    def test_reset_clears_each_non_idle_phase_and_preserves_session_sequence(self):
        phase_setups = (
            (WAITING_FIRST_SPEECH, ()),
            (SEGMENT_ACTIVE, ("recording_started",)),
            (
                FOLLOWUP_WAIT,
                ("recording_started", "recording_ended"),
            ),
            (CLOSING_INPUT, ("finish",)),
        )
        for expected_phase, transitions in phase_setups:
            with self.subTest(phase=expected_phase):
                ids = iter(("first", "second"))
                controller = ActivationController(
                    manual_trigger_enabled=True,
                    wake_word_trigger_enabled=True,
                    clock=self.clock,
                    id_factory=lambda: next(ids),
                )
                opened = controller.activate("manual")
                for transition in transitions:
                    method = getattr(controller, transition)
                    method("manual") if transition == "finish" else method()
                self.assertEqual(controller.snapshot()["phase"], expected_phase)

                reset = controller.reset()
                self.assertTrue(reset.accepted)
                self.assertEqual(reset.snapshot["phase"], IDLE)
                self.assertIsNone(reset.snapshot["activationId"])
                self.assertEqual(
                    reset.snapshot["closedActivationId"],
                    opened.snapshot["activationId"],
                )
                self.assertEqual(reset.snapshot["activationSequence"], 1)

                reopened = controller.activate("wake_word")
                self.assertEqual(reopened.snapshot["activationSequence"], 2)

    def test_both_disabled_is_invalid(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            ActivationController(
                manual_trigger_enabled=False,
                wake_word_trigger_enabled=False,
            )


class ConcurrentTriggerTests(unittest.TestCase):
    REPEATS = 16
    HOLD_SECONDS = 0.01

    @staticmethod
    def _slow_id_factory():
        counter = itertools.count(1)

        def factory():
            time.sleep(ConcurrentTriggerTests.HOLD_SECONDS)
            return f"act-{next(counter)}"

        return factory

    def test_parallel_sources_admit_exactly_one_latched_activation(self):
        for _ in range(self.REPEATS):
            controller = ActivationController(
                manual_trigger_enabled=True,
                wake_word_trigger_enabled=True,
                id_factory=self._slow_id_factory(),
            )
            start = threading.Barrier(8)
            results = []
            result_lock = threading.Lock()

            def trigger(index, source):
                start.wait(timeout=10)
                result = controller.activate(
                    source, {"request": index, "source": source}
                )
                with result_lock:
                    results.append((index, source, result))

            threads = [
                threading.Thread(
                    target=trigger,
                    args=(index, "manual" if index % 2 == 0 else "wake_word"),
                )
                for index in range(8)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=30)

            accepted = [item for item in results if item[2].accepted]
            rejected = [item for item in results if not item[2].accepted]
            self.assertEqual(len(accepted), 1)
            self.assertEqual(len(rejected), 7)
            self.assertTrue(
                all(item[2].reason == "activation_locked" for item in rejected)
            )
            winner_index, winner_source, _ = accepted[0]
            snapshot = controller.snapshot()
            self.assertEqual(snapshot["activationSequence"], 1)
            self.assertEqual(snapshot["primarySource"], winner_source)
            self.assertEqual(snapshot["sources"], [winner_source])
            self.assertEqual(
                snapshot["effectiveSettings"],
                {"request": winner_index, "source": winner_source},
            )

    def test_parallel_snapshot_readers_never_observe_half_built_state(self):
        for _ in range(self.REPEATS):
            controller = ActivationController(
                manual_trigger_enabled=True,
                wake_word_trigger_enabled=True,
                id_factory=self._slow_id_factory(),
            )
            inconsistent = []
            stop = threading.Event()

            def reader():
                while not stop.is_set():
                    snapshot = controller.snapshot()
                    phase = snapshot["phase"]
                    if phase == IDLE:
                        if any(
                            (
                                snapshot["activationId"],
                                snapshot["primarySource"],
                                snapshot["sources"],
                                snapshot["windowOpen"],
                            )
                        ):
                            inconsistent.append(snapshot)
                    elif not (
                        snapshot["activationId"]
                        and snapshot["primarySource"]
                        and snapshot["sources"]
                    ):
                        inconsistent.append(snapshot)

            readers = [threading.Thread(target=reader) for _ in range(3)]
            for thread in readers:
                thread.start()
            try:
                controller.activate("manual")
                controller.recording_started()
                controller.recording_ended()
                controller.finish("manual")
                controller.input_closed()
                controller.activate("wake_word")
            finally:
                stop.set()
                for thread in readers:
                    thread.join(timeout=10)

            self.assertEqual(
                inconsistent,
                [],
                f"observed inconsistent snapshots: {inconsistent[:2]}",
            )

    def test_real_close_activate_race_never_admits_inside_close_barrier(self):
        for _ in range(self.REPEATS):
            controller = ActivationController(
                manual_trigger_enabled=True,
                wake_word_trigger_enabled=True,
                id_factory=self._slow_id_factory(),
            )
            first = controller.activate("manual")
            controller.recording_started()
            closing_ready = threading.Event()
            release_close = threading.Event()

            def close_input():
                closing = controller.finish("manual")
                self.assertEqual(closing.snapshot["phase"], CLOSING_INPUT)
                closing_ready.set()
                release_close.wait(timeout=10)
                controller.input_closed()

            thread = threading.Thread(target=close_input)
            thread.start()
            self.assertTrue(closing_ready.wait(timeout=10))
            blocked = controller.activate("wake_word")
            self.assertFalse(blocked.accepted)
            self.assertEqual(blocked.reason, "activation_locked")
            self.assertEqual(
                blocked.snapshot["activationId"], first.snapshot["activationId"]
            )
            release_close.set()
            thread.join(timeout=10)

            admitted = controller.activate("wake_word")
            self.assertTrue(admitted.accepted)
            self.assertEqual(admitted.snapshot["activationSequence"], 2)


if __name__ == "__main__":
    unittest.main()
