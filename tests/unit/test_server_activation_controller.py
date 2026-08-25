import itertools
import threading
import time
import unittest
from unittest import mock

from api_fastapi_server.activation import (
    ActivationController,
    CLOSING_INPUT,
    CLOSING_RECOVERY_DEADLINE,
    FOLLOWUP_DEADLINE,
    FOLLOWUP_WAIT,
    IDLE,
    INITIAL_SPEECH_DEADLINE,
    SEGMENT_ACTIVE,
    SEGMENT_WATCHDOG_DEADLINE,
    WAITING_FIRST_SPEECH,
)


class MonotonicFakeClock:
    def __init__(self, start=1000.0):
        self.monotonic_now = start

    def __call__(self):
        return self.monotonic_now


def build_controller(clock, ids=None, **overrides):
    """One controller with the frozen contract defaults, in seconds."""
    options = {
        "manual_trigger_enabled": True,
        "wake_word_trigger_enabled": True,
        "initial_speech_timeout": 15.0,
        "followup_timeout": 3.0,
        "segment_watchdog_initial": 600.0,
        "segment_watchdog_refresh": 180.0,
        "segment_watchdog_warning": 30.0,
        "closing_recovery_timeout": 5.0,
        "clock": clock,
    }
    options.update(overrides)
    if ids is not None:
        options["id_factory"] = lambda: next(ids)
    return ActivationController(**options)


class ServerActivationControllerTests(unittest.TestCase):
    def setUp(self):
        self.clock = MonotonicFakeClock()
        self.ids = iter(f"activation-{index}" for index in range(1, 20))
        self.controller = build_controller(self.clock, self.ids)

    # -- helpers for the source-neutral C2 signatures -----------------------

    def _activation_id(self):
        return self.controller.snapshot()["activationId"]

    def _activation_sequence(self):
        return self.controller.snapshot()["activationSequence"]

    def _refresh(self, **kwargs):
        return self.controller.refresh(
            activation_id=self._activation_id(), **kwargs
        )

    def _finish(self, **kwargs):
        return self.controller.finish(
            activation_id=self._activation_id(), **kwargs
        )

    def _cancel(self, **kwargs):
        return self.controller.cancel(
            activation_id=self._activation_id(), **kwargs
        )

    def _close(self):
        return self.controller.input_closed(
            activation_id=self._activation_id(),
            activation_sequence=self._activation_sequence(),
        )

    def test_canonical_foreground_uses_exactly_five_phase_values(self):
        observed = {self.controller.snapshot()["phase"]}
        self.controller.activate("manual")
        observed.add(self.controller.snapshot()["phase"])
        self.controller.recording_started()
        observed.add(self.controller.snapshot()["phase"])
        self.controller.recording_ended()
        observed.add(self.controller.snapshot()["phase"])
        self._finish()
        observed.add(self.controller.snapshot()["phase"])
        self._close()
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
            (CLOSING_INPUT, lambda: self._finish()),
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
            self.controller.recording_started,
            self.controller.recording_ended,
            lambda: self._refresh(),
            lambda: self._finish(),
            self._close,
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
        closing = self._finish()

        self.assertTrue(closing.accepted)
        self.assertEqual(closing.snapshot["phase"], CLOSING_INPUT)
        self.assertFalse(closing.snapshot["windowOpen"])
        self.assertEqual(
            closing.snapshot["activationId"], opened.snapshot["activationId"]
        )
        self.assertEqual(closing.snapshot["closeReason"], "finished")

        idle = self._close()
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
        closing = self._finish()
        self.assertEqual(closing.snapshot["phase"], CLOSING_INPUT)
        self.assertEqual(closing.snapshot["activationId"], opened.snapshot["activationId"])
        idle = self._close()
        self.assertEqual(idle.snapshot["phase"], IDLE)
        self.assertEqual(idle.snapshot["closedSegments"], 0)
        self.assertEqual(idle.snapshot["closeReason"], "finished")

    def test_cancel_uses_the_same_close_barrier_and_preserves_its_reason(self):
        opened = self.controller.activate("manual")
        closing = self._cancel()
        self.assertEqual(closing.snapshot["phase"], CLOSING_INPUT)
        self.assertEqual(closing.snapshot["activationId"], opened.snapshot["activationId"])
        idle = self._close()
        self.assertEqual(idle.snapshot["phase"], IDLE)
        self.assertEqual(idle.snapshot["closeReason"], "cancelled")

    def test_repeated_finish_and_cancel_do_not_repeat_the_close_transition(self):
        """AP-SRV-030 replaces the former ``not_active`` answer.

        The contract phase matrix answers ``finish``/``cancel`` in
        ``closing_input`` with an idempotent state answer, not with a
        rejection. What must not change is the effect: no second transition,
        no second close reason and no second timer.
        """
        for first_action in ("finish", "cancel"):
            with self.subTest(first_action=first_action):
                self.controller.reset()
                opened = self.controller.activate("manual")
                first = getattr(self.controller, first_action)(
                    activation_id=opened.snapshot["activationId"]
                )
                before = self.controller.snapshot()

                self.assertTrue(first.accepted)
                self.assertEqual(first.snapshot["phase"], CLOSING_INPUT)
                for repeated_action in ("finish", "cancel"):
                    repeated = getattr(self.controller, repeated_action)(
                        activation_id=opened.snapshot["activationId"]
                    )
                    self.assertTrue(repeated.accepted)
                    self.assertEqual(repeated.reason, "no_change")
                    self.assertFalse(repeated.changed)
                    self.assertEqual(
                        repeated.snapshot["phase"], CLOSING_INPUT
                    )
                    self.assertEqual(
                        repeated.snapshot["closeReason"],
                        first.snapshot["closeReason"],
                    )
                    self.assertEqual(
                        repeated.snapshot["timerRevision"],
                        before["timerRevision"],
                    )
                    self.assertEqual(
                        repeated.snapshot["activationId"],
                        opened.snapshot["activationId"],
                    )

    def test_new_activation_after_close_gets_new_id_and_sequence(self):
        first = self.controller.activate("manual")
        self._cancel()
        self.assertEqual(
            self.controller.activate("wake_word").reason, "activation_locked"
        )
        self._close()
        second = self.controller.activate("wake_word")

        self.assertEqual(second.snapshot["activationSequence"], 2)
        self.assertGreater(
            second.snapshot["activationSequence"],
            first.snapshot["activationSequence"],
        )
        self.assertNotEqual(
            second.snapshot["activationId"], first.snapshot["activationId"]
        )

    def test_initial_speech_timeout_enters_close_barrier(self):
        opened = self.controller.activate("manual")
        self.assertEqual(
            opened.snapshot["deadlineKind"], INITIAL_SPEECH_DEADLINE
        )
        token = opened.snapshot["timerToken"]

        self.clock.monotonic_now = 2000.0
        expired = self.controller.tick(token)
        self.assertTrue(expired.accepted)
        self.assertEqual(expired.reason, "timed_out")
        self.assertEqual(expired.snapshot["phase"], CLOSING_INPUT)
        self.assertEqual(expired.snapshot["closeReason"], "timed_out")
        self.assertEqual(
            expired.snapshot["closeCause"], "initial_speech_timeout"
        )

    def test_a_timer_of_a_superseded_deadline_is_inert(self):
        opened = self.controller.activate("manual")
        stale_token = opened.snapshot["timerToken"]
        # Speech starts, so the initial-speech deadline is replaced by the
        # segment watchdog and the old callback is no longer responsible.
        self.controller.recording_started()

        self.clock.monotonic_now = 2000.0
        stale = self.controller.tick(stale_token)
        self.assertFalse(stale.accepted)
        self.assertEqual(stale.reason, "stale_timer")
        self.assertEqual(stale.snapshot["phase"], SEGMENT_ACTIVE)

    def test_only_the_timer_revision_has_to_differ_for_a_callback_to_be_inert(self):
        """The same activation, the same phase, only a newer deadline."""
        self.controller.activate("manual")
        self.controller.recording_started()
        followup = self.controller.recording_ended()
        stale_token = followup.snapshot["timerToken"]

        self.clock.monotonic_now = 1001.0
        refreshed = self._refresh()
        fresh_token = refreshed.snapshot["timerToken"]
        self.assertEqual(stale_token.activation_id, fresh_token.activation_id)
        self.assertEqual(stale_token.phase, fresh_token.phase)
        self.assertEqual(stale_token.kind, fresh_token.kind)
        self.assertNotEqual(
            stale_token.timer_revision, fresh_token.timer_revision
        )

        self.clock.monotonic_now = 1003.5
        stale = self.controller.tick(stale_token)
        self.assertFalse(stale.accepted)
        self.assertEqual(stale.reason, "stale_timer")
        self.assertEqual(stale.snapshot["phase"], FOLLOWUP_WAIT)
        self.assertEqual(stale.snapshot["deadline"], 1004.0)

    def test_tick_without_an_armed_deadline_is_effect_free(self):
        idle_before = self.controller.snapshot()
        idle_tick = self.controller.tick(idle_before["timerToken"])
        self.assertFalse(idle_tick.accepted)
        self.assertEqual(idle_tick.reason, "not_expirable")
        self.assertEqual(idle_tick.snapshot, idle_before)

        self.assertFalse(self.controller.tick(None).accepted)
        self.assertEqual(self.controller.tick("nonsense").reason, "stale_timer")

    def test_wallclock_jumps_do_not_change_monotonic_deadline_or_expiry(self):
        with mock.patch(
            "api_fastapi_server.activation.time.time", return_value=10**12
        ):
            opened = self.controller.activate("manual")
        token = opened.snapshot["timerToken"]
        self.assertEqual(opened.snapshot["deadline"], 1015.0)

        self.clock.monotonic_now = 1010.0
        with mock.patch(
            "api_fastapi_server.activation.time.time", return_value=-10**12
        ):
            early = self.controller.tick(token)
        self.assertFalse(early.accepted)
        self.assertEqual(early.reason, "not_due")
        self.assertEqual(early.snapshot["deadline"], 1015.0)

        self.clock.monotonic_now = 1016.0
        expired = self.controller.tick(token)
        self.assertTrue(expired.accepted)
        self.assertEqual(expired.snapshot["phase"], CLOSING_INPUT)

    # -- AP-SRV-030: the contract refresh replaces the additive extend -------
    #
    # The AP-SRV-010 baseline banked ``extensionSeconds`` on every ``extend``
    # (FIND-010, HK-04). Those expectations are gone; the tests below hold the
    # frozen semantics instead.

    def test_the_additive_extend_semantics_is_gone_from_the_controller(self):
        """FIND-010/HK-04: no ``extensionSeconds``, no banked time, no credit."""
        self.assertFalse(hasattr(self.controller, "extend"))
        self.assertFalse(hasattr(self.controller, "extension_seconds"))
        self.assertFalse(hasattr(self.controller, "_pending_extension"))
        self.assertNotIn("pendingExtensionSeconds", self.controller.snapshot())
        with self.assertRaises(TypeError):
            ActivationController(
                manual_trigger_enabled=True,
                wake_word_trigger_enabled=True,
                extension_seconds=5.0,
                clock=self.clock,
            )

    def test_refresh_is_invalid_while_waiting_for_the_first_speech(self):
        """PHASE-03: the initial-speech window is not refreshable."""
        opened = self.controller.activate("manual")
        before = self.controller.snapshot()
        rejected = self.controller.refresh(
            activation_id=opened.snapshot["activationId"]
        )
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.reason, "invalid_phase")
        self.assertFalse(rejected.changed)
        self.assertEqual(rejected.snapshot, before)
        self.assertEqual(
            rejected.snapshot["deadline"], opened.snapshot["deadline"]
        )

    def test_followup_refresh_restarts_the_window_and_never_accumulates(self):
        """TIME-02/TIME-03: three refreshes are three restarts, not three credits."""
        self.controller.activate("manual")
        self.controller.recording_started()
        followup = self.controller.recording_ended()
        self.assertEqual(followup.snapshot["deadline"], 1003.0)
        self.assertEqual(followup.snapshot["deadlineKind"], FOLLOWUP_DEADLINE)

        self.clock.monotonic_now = 1002.0
        first = self._refresh()
        second = self._refresh()
        third = self._refresh()

        for result in (first, second, third):
            self.assertTrue(result.accepted)
            self.assertEqual(result.reason, "refreshed")
            self.assertEqual(result.snapshot["phase"], FOLLOWUP_WAIT)
            # now + followupTimeout, no matter how often it is pressed.
            self.assertEqual(result.snapshot["deadline"], 1005.0)

        self.clock.monotonic_now = 1004.0
        fourth = self._refresh()
        self.assertEqual(fourth.snapshot["deadline"], 1007.0)

    def test_every_effective_refresh_raises_the_timer_revision(self):
        """TIME-07: an effective timer change is never silent."""
        self.controller.activate("manual")
        self.controller.recording_started()
        followup = self.controller.recording_ended()
        revisions = [followup.snapshot["timerRevision"]]
        for offset in (1.0, 2.0, 3.0):
            self.clock.monotonic_now = 1000.0 + offset
            refreshed = self._refresh()
            self.assertGreater(
                refreshed.snapshot["timerRevision"], revisions[-1]
            )
            revisions.append(refreshed.snapshot["timerRevision"])

    def test_refresh_does_not_depend_on_the_trigger_source(self):
        """F6: a control works for either latched source without a source arg."""
        for source in ("manual", "wake_word"):
            with self.subTest(source=source):
                self.controller.reset()
                self.clock.monotonic_now = 1000.0
                opened = self.controller.activate(source)
                self.controller.recording_started()
                self.controller.recording_ended()
                self.clock.monotonic_now = 1001.0
                refreshed = self.controller.refresh(
                    activation_id=opened.snapshot["activationId"]
                )
                self.assertTrue(refreshed.accepted)
                self.assertEqual(refreshed.reason, "refreshed")
                self.assertEqual(
                    refreshed.snapshot["activationId"],
                    opened.snapshot["activationId"],
                )
                self.assertEqual(refreshed.snapshot["primarySource"], source)
                self.assertEqual(refreshed.snapshot["sources"], [source])
                self.assertEqual(refreshed.snapshot["deadline"], 1004.0)

    def test_control_does_not_change_the_latched_source(self):
        self.controller.activate("manual")
        self.controller.recording_started()
        self.controller.recording_ended()
        refreshed = self._refresh()
        self.assertTrue(refreshed.accepted)
        self.assertEqual(refreshed.reason, "refreshed")
        self.assertEqual(refreshed.snapshot["primarySource"], "manual")
        self.assertEqual(refreshed.snapshot["sources"], ["manual"])

    def test_refresh_in_closing_input_has_no_effect(self):
        self.controller.activate("manual")
        self._finish()
        before = self.controller.snapshot()
        rejected = self.controller.refresh(
            activation_id=self._activation_id()
        )
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.reason, "closing_input")
        self.assertFalse(rejected.changed)
        self.assertEqual(rejected.snapshot, before)

    # -- AP-SRV-030: segment watchdog ---------------------------------------

    def test_segment_start_arms_the_ten_minute_watchdog(self):
        """TIME-04: 600 s by default, warning 30 s before the deadline."""
        self.controller.activate("manual")
        started = self.controller.recording_started()
        self.assertEqual(
            started.snapshot["deadlineKind"], SEGMENT_WATCHDOG_DEADLINE
        )
        self.assertEqual(started.snapshot["deadline"], 1600.0)
        self.assertEqual(started.snapshot["warningDeadline"], 1570.0)

    def test_an_early_watchdog_refresh_never_shortens_the_remaining_time(self):
        """TIME-05: ``max(currentDeadline, now + 180 s)``."""
        self.controller.activate("manual")
        started = self.controller.recording_started()

        self.clock.monotonic_now = 1060.0
        early = self._refresh()
        self.assertTrue(early.accepted)
        self.assertEqual(early.reason, "refreshed")
        self.assertFalse(
            early.changed, "an early refresh must not churn the timer"
        )
        self.assertEqual(early.snapshot["deadline"], 1600.0)
        self.assertEqual(
            early.snapshot["timerRevision"], started.snapshot["timerRevision"]
        )

    def test_a_late_watchdog_refresh_secures_at_least_three_minutes(self):
        self.controller.activate("manual")
        self.controller.recording_started()

        self.clock.monotonic_now = 1500.0
        late = self._refresh()
        self.assertTrue(late.changed)
        self.assertEqual(late.snapshot["deadline"], 1680.0)
        self.assertEqual(late.snapshot["warningDeadline"], 1650.0)

    def test_repeated_watchdog_refreshes_do_not_accumulate(self):
        self.controller.activate("manual")
        self.controller.recording_started()
        self.clock.monotonic_now = 1500.0
        for _ in range(3):
            refreshed = self._refresh()
            self.assertEqual(refreshed.snapshot["deadline"], 1680.0)

    def test_vad_activity_does_not_reset_the_watchdog(self):
        """TIME-06: continued speech is not an interaction."""
        self.controller.activate("manual")
        started = self.controller.recording_started()
        for offset in (10.0, 120.0, 400.0):
            self.clock.monotonic_now = 1000.0 + offset
            repeated = self.controller.recording_started()
            self.assertTrue(repeated.accepted)
            self.assertEqual(repeated.reason, "already_recording")
            self.assertFalse(repeated.changed)
            self.assertEqual(repeated.snapshot["deadline"], 1600.0)
            self.assertEqual(
                repeated.snapshot["timerRevision"],
                started.snapshot["timerRevision"],
            )

    def test_the_watchdog_warns_once_and_then_expires_without_followup(self):
        """TIME-08: the audio is processed, the whole activation closes."""
        self.controller.activate("manual")
        started = self.controller.recording_started()
        token = started.snapshot["timerToken"]

        self.clock.monotonic_now = 1569.0
        self.assertEqual(self.controller.tick(token).reason, "not_due")

        self.clock.monotonic_now = 1570.0
        warning = self.controller.tick(token)
        self.assertTrue(warning.accepted)
        self.assertEqual(warning.reason, "watchdog_warning")
        self.assertEqual(warning.snapshot["phase"], SEGMENT_ACTIVE)
        self.assertTrue(warning.snapshot["warningFired"])
        # The warning moves no deadline, so the same token stays responsible.
        self.assertEqual(warning.snapshot["timerToken"], token)

        self.clock.monotonic_now = 1580.0
        self.assertEqual(self.controller.tick(token).reason, "not_due")

        self.clock.monotonic_now = 1600.0
        expired = self.controller.tick(token)
        self.assertTrue(expired.accepted)
        self.assertEqual(expired.reason, "segment_watchdog_timeout")
        self.assertEqual(expired.snapshot["phase"], CLOSING_INPUT)
        self.assertNotEqual(expired.snapshot["phase"], FOLLOWUP_WAIT)
        self.assertEqual(
            expired.snapshot["closeCause"], "segment_watchdog_timeout"
        )

    def test_a_watchdog_timer_of_an_ended_segment_is_inert(self):
        self.controller.activate("manual")
        first = self.controller.recording_started()
        stale_token = first.snapshot["timerToken"]
        self.controller.recording_ended()
        self.controller.recording_started()

        self.clock.monotonic_now = 5000.0
        stale = self.controller.tick(stale_token)
        self.assertFalse(stale.accepted)
        self.assertEqual(stale.reason, "stale_timer")
        self.assertEqual(stale.snapshot["phase"], SEGMENT_ACTIVE)

    # -- AP-SRV-030: closing recovery ---------------------------------------

    def test_closing_input_arms_a_recovery_deadline(self):
        self.controller.activate("manual")
        closing = self._finish()
        self.assertEqual(
            closing.snapshot["deadlineKind"], CLOSING_RECOVERY_DEADLINE
        )
        self.assertEqual(closing.snapshot["deadline"], 1005.0)

    def test_recovery_due_stays_in_closing_input(self):
        """F1: recovery must not claim idle - only input_closed() may."""
        opened = self.controller.activate("manual")
        activation_id = opened.snapshot["activationId"]
        closing = self._finish(command_id="cmd-r")
        token = closing.snapshot["timerToken"]
        self.assertEqual(closing.snapshot["phase"], CLOSING_INPUT)

        self.clock.monotonic_now = 1005.0
        recovered = self.controller.tick(token)
        self.assertTrue(recovered.accepted)
        self.assertEqual(recovered.reason, "closing_recovery_due")
        self.assertEqual(recovered.snapshot["phase"], CLOSING_INPUT)
        self.assertTrue(recovered.snapshot["recoveryRequested"])
        # The deadline is consumed; the phase is *not* idle (F1).
        self.assertIsNone(recovered.snapshot["deadline"])
        # The close identity survives the recovery deadline (F2).
        self.assertEqual(
            recovered.snapshot["closeRequestedByCommandId"], "cmd-r"
        )
        # The same close can still complete through identity-bound input_closed.
        completed = self.controller.input_closed(
            activation_id=activation_id,
            activation_sequence=opened.snapshot["activationSequence"],
        )
        self.assertTrue(completed.accepted)
        self.assertEqual(completed.snapshot["phase"], IDLE)
        self.assertFalse(completed.snapshot["recoveryRequested"])

    def test_a_recovery_timer_cannot_touch_a_newer_activation(self):
        first = self.controller.activate("manual")
        activation_id = first.snapshot["activationId"]
        activation_sequence = first.snapshot["activationSequence"]
        closing = self.controller.finish(activation_id=activation_id)
        stale_token = closing.snapshot["timerToken"]
        self.controller.input_closed(
            activation_id=activation_id,
            activation_sequence=activation_sequence,
        )
        second = self.controller.activate("wake_word")

        self.clock.monotonic_now = 9000.0
        stale = self.controller.tick(stale_token)
        self.assertFalse(stale.accepted)
        self.assertEqual(stale.reason, "stale_timer")
        self.assertEqual(
            self.controller.snapshot()["activationId"],
            second.snapshot["activationId"],
        )
        self.assertEqual(
            self.controller.snapshot()["phase"], WAITING_FIRST_SPEECH
        )

    # -- AP-SRV-030: observed activation id ---------------------------------

    def test_a_control_command_with_a_stale_activation_id_has_no_effect(self):
        """CMD-02/CMD-07: an old id never acts on the newer activation."""
        first = self.controller.activate("manual")
        stale_id = first.snapshot["activationId"]
        self.controller.finish(activation_id=stale_id)
        self.controller.input_closed(
            activation_id=stale_id,
            activation_sequence=first.snapshot["activationSequence"],
        )
        second = self.controller.activate("wake_word")
        self.controller.recording_started()
        self.controller.recording_ended()
        before = self.controller.snapshot()

        for action in ("refresh", "finish", "cancel"):
            with self.subTest(action=action):
                result = getattr(self.controller, action)(
                    activation_id=stale_id
                )
                self.assertFalse(result.accepted)
                self.assertEqual(result.reason, "stale_activation")
                self.assertFalse(result.changed)
                self.assertEqual(result.snapshot, before)
                self.assertEqual(
                    result.snapshot["activationId"],
                    second.snapshot["activationId"],
                )

    def test_the_observed_activation_id_admits_the_current_activation(self):
        opened = self.controller.activate("manual")
        activation_id = opened.snapshot["activationId"]
        self.controller.recording_started()
        self.controller.recording_ended()

        refreshed = self.controller.refresh(activation_id=activation_id)
        self.assertTrue(refreshed.accepted)
        finished = self.controller.finish(activation_id=activation_id)
        self.assertTrue(finished.accepted)
        self.assertEqual(finished.reason, "finished")

    def test_activate_must_not_address_an_existing_activation(self):
        rejected = self.controller.activate("manual", activation_id="a-1")
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.reason, "invalid_payload")
        self.assertEqual(self.controller.snapshot()["phase"], IDLE)

    # -- AP-SRV-030 C2: identity-bound input closed --------------------------

    def test_input_closed_requires_the_closing_activation_identity(self):
        opened = self.controller.activate("manual")
        activation_id = opened.snapshot["activationId"]
        activation_sequence = opened.snapshot["activationSequence"]
        self.controller.finish(activation_id=activation_id)

        # A matching identity completes the close.
        completed = self.controller.input_closed(
            activation_id=activation_id,
            activation_sequence=activation_sequence,
        )
        self.assertTrue(completed.accepted)

    def test_stale_input_closed_cannot_clear_a_newer_activation(self):
        """A stale close follow-up must never end the newer activation."""
        first = self.controller.activate("manual")
        first_id = first.snapshot["activationId"]
        first_seq = first.snapshot["activationSequence"]
        self.controller.finish(activation_id=first_id)
        self.controller.input_closed(
            activation_id=first_id, activation_sequence=first_seq
        )
        second = self.controller.activate("wake_word")
        second_id = second.snapshot["activationId"]

        # The old close identity is gone; its follow-up cannot open B at all.
        stale = self.controller.input_closed(
            activation_id=first_id, activation_sequence=first_seq
        )
        self.assertFalse(stale.accepted)
        self.assertEqual(
            self.controller.snapshot()["activationId"], second_id
        )
        self.assertEqual(
            self.controller.snapshot()["phase"], WAITING_FIRST_SPEECH
        )

        # While B is mid-close, a mismatched close identity is also inert.
        self.controller.finish(activation_id=second_id)
        before = self.controller.snapshot()
        mismatched = self.controller.input_closed(
            activation_id=second_id, activation_sequence=first_seq
        )
        self.assertFalse(mismatched.accepted)
        self.assertEqual(mismatched.reason, "stale_activation")
        self.assertEqual(mismatched.snapshot, before)
        self.assertEqual(
            self.controller.snapshot()["activationId"], second_id
        )
        self.assertEqual(
            self.controller.snapshot()["phase"], CLOSING_INPUT
        )

    def test_close_context_survives_until_input_closed(self):
        opened = self.controller.activate("manual")
        activation_id = opened.snapshot["activationId"]
        closing = self.controller.finish(
            activation_id=activation_id, command_id="cmd-7"
        )
        self.assertEqual(closing.snapshot["phase"], CLOSING_INPUT)
        self.assertEqual(closing.snapshot["closeReason"], "finished")
        self.assertEqual(
            closing.snapshot["closeRequestedByCommandId"], "cmd-7"
        )
        self.assertEqual(
            closing.snapshot["closeRequestedByAction"], "finish"
        )

        # The internal identity survives an idempotent repeated close.
        repeated = self.controller.cancel(activation_id=activation_id)
        self.assertEqual(repeated.reason, "no_change")
        self.assertEqual(
            repeated.snapshot["closeRequestedByCommandId"], "cmd-7"
        )
        self.assertEqual(
            repeated.snapshot["closeRequestedByAction"], "finish"
        )

        # And it is transported through the identity-bound close completion.
        completed = self.controller.input_closed(
            activation_id=activation_id,
            activation_sequence=opened.snapshot["activationSequence"],
        )
        self.assertTrue(completed.accepted)
        self.assertEqual(completed.snapshot["closeReason"], "finished")
        self.assertEqual(
            completed.snapshot["closeRequestedByCommandId"], "cmd-7"
        )
        # The live controller no longer holds the context.
        self.assertIsNone(
            self.controller.snapshot().get("closeRequestedByCommandId")
        )

    # -- AP-SRV-030: generic audio availability ------------------------------

    def test_audio_loss_cancels_the_open_activation_in_every_phase(self):
        """DEVICE-03: cancel the activation, keep the session."""
        phase_setups = (
            (WAITING_FIRST_SPEECH, ()),
            (SEGMENT_ACTIVE, ("recording_started",)),
            (FOLLOWUP_WAIT, ("recording_started", "recording_ended")),
        )
        for expected_phase, transitions in phase_setups:
            with self.subTest(phase=expected_phase):
                self.controller.reset()
                self.controller.activate("manual")
                for transition in transitions:
                    getattr(self.controller, transition)()
                self.assertEqual(
                    self.controller.snapshot()["phase"], expected_phase
                )

                lost = self.controller.audio_unavailable()
                self.assertTrue(lost.accepted)
                self.assertTrue(lost.changed)
                self.assertEqual(lost.snapshot["phase"], CLOSING_INPUT)
                self.assertEqual(lost.snapshot["closeReason"], "cancelled")
                self.assertEqual(
                    lost.snapshot["closeCause"], "audio_unavailable"
                )
                # F7: an audio loss is never command correlated.
                self.assertIsNone(
                    lost.snapshot.get("closeRequestedByCommandId")
                )
                self.assertIsNone(lost.snapshot.get("closeRequestedByAction"))

    def test_audio_loss_is_idempotent_and_needs_an_open_activation(self):
        self.assertEqual(
            self.controller.audio_unavailable().reason, "not_active"
        )
        self.controller.activate("manual")
        self.controller.audio_unavailable()
        repeated = self.controller.audio_unavailable()
        self.assertTrue(repeated.accepted)
        self.assertEqual(repeated.reason, "no_change")
        self.assertFalse(repeated.changed)

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

    def test_control_is_independent_of_trigger_source_enablement(self):
        """F6: controls must work for a wake activation even with manual off."""
        controller = ActivationController(
            manual_trigger_enabled=False,
            wake_word_trigger_enabled=True,
            clock=self.clock,
        )
        opened = controller.activate("wake_word")
        activation_id = opened.snapshot["activationId"]
        controller.recording_started()
        controller.recording_ended()

        refreshed = controller.refresh(activation_id=activation_id)
        self.assertTrue(refreshed.accepted)
        self.assertEqual(refreshed.reason, "refreshed")
        self.assertEqual(refreshed.snapshot["primarySource"], "wake_word")

        finished = controller.finish(activation_id=activation_id)
        self.assertTrue(finished.accepted)
        self.assertEqual(finished.reason, "finished")

    def test_control_methods_require_matching_activation_identity(self):
        opened = self.controller.activate("manual")
        activation_id = opened.snapshot["activationId"]
        self.controller.recording_started()
        self.controller.recording_ended()
        before = self.controller.snapshot()

        for action in ("refresh", "finish", "cancel"):
            with self.subTest(action=action):
                stale = getattr(self.controller, action)(
                    activation_id="someone-else"
                )
                self.assertFalse(stale.accepted)
                self.assertEqual(stale.reason, "stale_activation")
                self.assertEqual(stale.snapshot, before)
                missing = getattr(self.controller, action)(activation_id="")
                self.assertFalse(missing.accepted)
                self.assertEqual(missing.reason, "invalid_payload")

        self.assertTrue(
            self.controller.refresh(activation_id=activation_id).accepted
        )
        self.assertTrue(
            self.controller.finish(activation_id=activation_id).accepted
        )

    def test_invalid_transitions_are_refused(self):
        for call, reason in (
            (lambda: self.controller.refresh(activation_id="x"), "not_active"),
            (self.controller.recording_started, "not_active"),
            (self.controller.recording_ended, "not_active"),
            (lambda: self.controller.finish(activation_id="x"), "not_active"),
            (lambda: self.controller.cancel(activation_id="x"), "not_active"),
            (
                lambda: self.controller.input_closed(
                    activation_id="x", activation_sequence=1
                ),
                "not_closing_input",
            ),
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
                    if transition == "finish":
                        controller.finish(
                            activation_id=opened.snapshot["activationId"]
                        )
                    else:
                        getattr(controller, transition)()
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
                activation_id = controller.snapshot()["activationId"]
                activation_sequence = controller.snapshot()["activationSequence"]
                controller.finish(activation_id=activation_id)
                controller.input_closed(
                    activation_id=activation_id,
                    activation_sequence=activation_sequence,
                )
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
                closing = controller.finish(
                    activation_id=controller.snapshot()["activationId"]
                )
                self.assertEqual(closing.snapshot["phase"], CLOSING_INPUT)
                closing_ready.set()
                release_close.wait(timeout=10)
                controller.input_closed(
                    activation_id=controller.snapshot()["activationId"],
                    activation_sequence=controller.snapshot()[
                        "activationSequence"
                    ],
                )

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