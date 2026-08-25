"""AP1 – the controlled activation gate is the recorder's only authority.

These tests deliberately do **not** use throwaway ``SimpleNamespace`` objects
for the gate itself. They build a real ``AudioToTextRecorder`` instance without
running its constructor (which would start worker processes and load models)
and then drive the **real public methods** of that class:

``set_activation_policy`` / ``open_controlled_activation`` /
``close_controlled_activation`` / ``abort_controlled_activation`` /
``controlled_activation_state`` / ``abort`` / ``shutdown``

The VAD start decision is taken with the very function that
``VoiceSTT/core/recording.py::run_recording_worker`` calls, so a regression in
the production decision would fail here too.
"""

import threading
import unittest
from unittest import mock

from VoiceSTT.audio_recorder import AudioToTextRecorder
from VoiceSTT.core.activation_control import (
    CONTROLLED_ACTIVATION_POLICY,
    LEGACY_ACTIVATION_POLICY,
    initialize_activation_control,
    recording_activation_gate_is_open,
)


def make_recorder(
    *,
    use_wake_words=False,
    start_recording_on_voice_activity=True,
    wakeword_detected=False,
):
    """A real recorder object with only the attributes the gate path reads.

    ``__init__`` is skipped on purpose: it spawns worker processes and loads
    models. Everything the tests exercise afterwards is genuine class code.
    """
    recorder = object.__new__(AudioToTextRecorder)
    initialize_activation_control(recorder)
    recorder.use_wake_words = use_wake_words
    recorder.start_recording_on_voice_activity = start_recording_on_voice_activity
    recorder.wakeword_detected = wakeword_detected
    recorder.is_recording = False
    return recorder


def gate_open(recorder, *, delay_passed=True):
    """Exactly the call ``run_recording_worker`` makes before starting VAD."""
    return recording_activation_gate_is_open(
        recorder,
        wake_word_activation_delay_passed=delay_passed,
    )


class ControlledGateAuthorityTests(unittest.TestCase):
    """Cases 1–4: the gate decides, and only the gate."""

    def test_01_controlled_closed_gate_blocks_recording_despite_speech(self):
        recorder = make_recorder()
        recorder.set_activation_policy("controlled")
        # Speech would be present; the gate is the only thing that matters.
        self.assertFalse(gate_open(recorder))

    def test_02_controlled_open_gate_allows_recording(self):
        recorder = make_recorder()
        recorder.set_activation_policy("controlled")
        self.assertTrue(recorder.open_controlled_activation("A1", generation=1))
        self.assertTrue(gate_open(recorder))

    def test_03_legacy_policy_behaviour_is_unchanged(self):
        # Legacy without wake words: VAD may start when armed.
        recorder = make_recorder(use_wake_words=False)
        self.assertEqual(recorder.activation_policy, LEGACY_ACTIVATION_POLICY)
        self.assertTrue(gate_open(recorder))

        recorder.start_recording_on_voice_activity = False
        self.assertFalse(gate_open(recorder))

        # Legacy with wake words: a detected wake word still opens directly.
        legacy_ww = make_recorder(
            use_wake_words=True,
            start_recording_on_voice_activity=False,
            wakeword_detected=True,
        )
        self.assertTrue(gate_open(legacy_ww, delay_passed=True))

        # ... and before the activation delay passes, VAD may arm as before.
        legacy_delay = make_recorder(
            use_wake_words=True,
            start_recording_on_voice_activity=True,
            wakeword_detected=False,
        )
        self.assertTrue(gate_open(legacy_delay, delay_passed=False))
        self.assertFalse(gate_open(legacy_delay, delay_passed=True))

    def test_04_wake_word_cannot_bypass_a_closed_controlled_gate(self):
        recorder = make_recorder(
            use_wake_words=True,
            start_recording_on_voice_activity=True,
        )
        recorder.set_activation_policy("controlled")
        # The legacy bypass flag is set, exactly as the wake-word detector
        # would set it. In the controlled policy it must have no effect.
        recorder.wakeword_detected = True
        self.assertFalse(gate_open(recorder))
        self.assertFalse(gate_open(recorder, delay_passed=False))


class ActivationReplacementTests(unittest.TestCase):
    """Cases 5–7: generation binding protects a newer activation."""

    def setUp(self):
        self.recorder = make_recorder()
        self.recorder.set_activation_policy("controlled")

    def test_05_gate_a_is_open(self):
        self.assertTrue(self.recorder.open_controlled_activation("A", generation=1))
        state = self.recorder.controlled_activation_state()
        self.assertTrue(state["active"])
        self.assertEqual(state["activationId"], "A")
        self.assertEqual(state["generation"], 1)

    def test_06_activation_b_replaces_a(self):
        self.recorder.open_controlled_activation("A", generation=1)
        # Without replace the running activation wins.
        self.assertFalse(self.recorder.open_controlled_activation("B", generation=2))
        self.assertEqual(
            self.recorder.controlled_activation_state()["activationId"], "A"
        )
        # With replace and a newer generation, B takes over.
        self.assertTrue(
            self.recorder.open_controlled_activation("B", replace=True, generation=2)
        )
        state = self.recorder.controlled_activation_state()
        self.assertEqual(state["activationId"], "B")
        self.assertEqual(state["generation"], 2)

    def test_07_late_close_of_a_must_not_close_b(self):
        self.recorder.open_controlled_activation("A", generation=1)
        self.recorder.open_controlled_activation("B", replace=True, generation=2)

        # The late close carries the old id ...
        self.assertFalse(self.recorder.close_controlled_activation("A"))
        self.assertTrue(self.recorder.controlled_activation_state()["active"])

        # ... and even an unqualified close from the old generation is refused.
        self.assertFalse(self.recorder.close_controlled_activation(generation=1))
        self.assertTrue(self.recorder.controlled_activation_state()["active"])
        self.assertEqual(
            self.recorder.controlled_activation_state()["activationId"], "B"
        )

        # The owner may close.
        self.assertTrue(self.recorder.close_controlled_activation("B", generation=2))
        self.assertFalse(self.recorder.controlled_activation_state()["active"])

    def test_07b_stale_open_cannot_replace_a_newer_activation(self):
        self.recorder.open_controlled_activation("B", generation=5)
        self.assertFalse(
            self.recorder.open_controlled_activation("A", replace=True, generation=4)
        )
        self.assertEqual(
            self.recorder.controlled_activation_state()["activationId"], "B"
        )


class GateClosingTests(unittest.TestCase):
    """Cases 8–11 and 15: cancel, finish, abort, shutdown, idempotence."""

    def setUp(self):
        self.recorder = make_recorder()
        self.recorder.set_activation_policy("controlled")
        self.recorder.open_controlled_activation("A", generation=1)

    def test_08_cancel_closes_the_gate(self):
        self.assertTrue(self.recorder.close_controlled_activation("A", generation=1))
        self.assertFalse(gate_open(self.recorder))

    def test_09_finish_closes_the_gate(self):
        # finish and cancel both reach the recorder as "close this activation".
        self.assertTrue(self.recorder.close_controlled_activation("A"))
        self.assertFalse(gate_open(self.recorder))

    def test_10_abort_forces_a_deterministic_closed_state(self):
        with mock.patch("VoiceSTT.audio_recorder.abort_recording") as aborted:
            self.recorder.abort()
        aborted.assert_called_once_with(self.recorder)
        state = self.recorder.controlled_activation_state()
        self.assertFalse(state["active"])
        self.assertIsNone(state["activationId"])
        self.assertFalse(gate_open(self.recorder))

    def test_11_shutdown_during_an_open_gate_closes_it_permanently(self):
        with mock.patch("VoiceSTT.audio_recorder.shutdown_recorder") as stopped:
            self.recorder.shutdown()
        stopped.assert_called_once_with(self.recorder)
        state = self.recorder.controlled_activation_state()
        self.assertFalse(state["active"])
        self.assertTrue(state["shutdown"])
        # A trigger arriving during teardown must not re-open the gate.
        self.assertFalse(self.recorder.open_controlled_activation("C", generation=9))
        self.assertFalse(gate_open(self.recorder))

    def test_15_multiple_close_calls_are_idempotent(self):
        self.assertTrue(self.recorder.close_controlled_activation("A"))
        for _ in range(5):
            self.assertFalse(self.recorder.close_controlled_activation("A"))
            self.assertFalse(self.recorder.close_controlled_activation())
        self.assertFalse(gate_open(self.recorder))
        self.assertIsNone(
            self.recorder.controlled_activation_state()["activationId"]
        )


class DuplicateTriggerTests(unittest.TestCase):
    """Case 12: a second trigger must not duplicate anything."""

    def test_12_repeated_open_for_the_same_activation_is_a_no_op(self):
        recorder = make_recorder()
        recorder.set_activation_policy("controlled")
        self.assertTrue(recorder.open_controlled_activation("A", generation=1))
        before = recorder.controlled_activation_state()
        for _ in range(4):
            self.assertTrue(recorder.open_controlled_activation("A", generation=1))
        self.assertEqual(recorder.controlled_activation_state(), before)

    def test_12b_gate_is_only_consulted_while_not_recording(self):
        """The production loop reads the gate inside its ``not is_recording``
        branch, so an extra trigger during a running segment cannot start a
        second one. This test pins that structural property of the worker."""
        import inspect

        from VoiceSTT.core import recording

        source = inspect.getsource(recording.run_recording_worker)
        gate_at = source.index("recording_activation_gate_is_open(")
        guard_at = source.index("if not self.is_recording:")
        self.assertLess(
            guard_at,
            gate_at,
            "the gate check must stay inside the 'not recording' branch",
        )


class GateRaceTests(unittest.TestCase):
    """Cases 13–14: toggling the gate concurrently with VAD reads.

    A single green run of a race test is not evidence, so each case is
    repeated. The invariant checked is that a read never observes a torn state
    (event set but no activation id, or vice versa).
    """

    REPEATS = 25

    def _run_race(self, closer):
        recorder = make_recorder()
        recorder.set_activation_policy("controlled")
        torn = []
        stop = threading.Event()

        def reader():
            while not stop.is_set():
                state = recorder.controlled_activation_state()
                if state["active"] != (state["activationId"] is not None):
                    torn.append(state)
                gate_open(recorder)

        threads = [threading.Thread(target=reader) for _ in range(3)]
        for thread in threads:
            thread.start()
        try:
            for index in range(200):
                recorder.open_controlled_activation(
                    f"A{index}", replace=True, generation=index + 1
                )
                closer(recorder, index)
        finally:
            stop.set()
            for thread in threads:
                thread.join(timeout=5)
        self.assertEqual(torn, [], "observed a torn gate state")

    def test_13_gate_opening_concurrent_with_vad_reads(self):
        for _ in range(self.REPEATS):
            self._run_race(lambda recorder, index: None)

    def test_14_gate_closing_concurrent_with_vad_reads(self):
        for _ in range(self.REPEATS):
            self._run_race(
                lambda recorder, index: recorder.close_controlled_activation(
                    f"A{index}", generation=index + 1
                )
            )


class PolicyValidationTests(unittest.TestCase):
    def test_unknown_policy_is_rejected(self):
        recorder = make_recorder()
        with self.assertRaises(ValueError):
            recorder.set_activation_policy("hybrid")

    def test_opening_the_gate_requires_the_controlled_policy(self):
        recorder = make_recorder()
        with self.assertRaises(RuntimeError):
            recorder.open_controlled_activation("A")

    def test_empty_activation_id_is_rejected(self):
        recorder = make_recorder()
        recorder.set_activation_policy("controlled")
        with self.assertRaises(ValueError):
            recorder.open_controlled_activation("   ")

    def test_leaving_controlled_policy_clears_the_gate(self):
        recorder = make_recorder()
        recorder.set_activation_policy("controlled")
        recorder.open_controlled_activation("A", generation=1)
        recorder.set_activation_policy(LEGACY_ACTIVATION_POLICY)
        state = recorder.controlled_activation_state()
        self.assertFalse(state["active"])
        self.assertIsNone(state["activationId"])
        self.assertEqual(recorder.activation_policy, LEGACY_ACTIVATION_POLICY)

    def test_controlled_policy_constant_is_used(self):
        recorder = make_recorder()
        recorder.set_activation_policy(CONTROLLED_ACTIVATION_POLICY)
        self.assertEqual(
            recorder.activation_policy, CONTROLLED_ACTIVATION_POLICY
        )


if __name__ == "__main__":
    unittest.main()
