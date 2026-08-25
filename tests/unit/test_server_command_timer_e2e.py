"""AP-SRV-030 - commands, timers, watchdog and recovery over the real path.

Everything here goes through the production entry point that AP-SRV-010 and
AP-SRV-020 established: a real WebSocket, the real query parsing and session
admission, the real recorder gate and the real segment ledger. Only the audio
hardware and the transcription model are faked.

The test classes follow the mandatory proof classes of the package:

``CommandPhaseMatrixTests``     the 5 x 4 phase matrix (CMD-03/CMD-04)
``CommandReplayEndToEndTests``  ``commandId`` replay and payload conflict
``StaleActivationEndToEndTests``  an old ``activationId`` is inert
``SegmentWatchdogEndToEndTests``  600/180/30 s semantics and the close
``ClosingRecoveryEndToEndTests``  gate/recorder faults and the way back to idle
``AudioAvailabilityEndToEndTests``  ``audioAvailable=false``
``LedgerRegressionEndToEndTests``  the AP-SRV-020 invariants under the new paths
"""

import threading
import time
import unittest

from tests.unit.test_server_controlled_e2e import (
    ControlledSessionHarness,
    GateAwareRecorder,
    TestClient,
    build_app,
    speech_packet,
)


#: A session whose deadlines are long enough that no timer interferes with a
#: command-matrix assertion.
QUIET = (
    "manualTriggerEnabled=true&wakeWordTriggerEnabled=true"
    "&initialSpeechTimeout=60&followupTimeout=60"
    "&segmentWatchdogInitialSeconds=60&segmentWatchdogRefreshSeconds=45"
    "&segmentWatchdogWarningSeconds=20&closingRecoveryTimeoutSeconds=60"
)


class FaultyGateRecorder(GateAwareRecorder):
    """Injects exactly the two closing faults the contract names.

    ``fail_gate_close`` makes the controlled gate refuse to close, and
    ``fail_recorder_close`` makes stopping the recorder raise. Both leave the
    foreground in ``closing_input``, which is precisely the situation the
    recovery deadline exists for.
    """

    fail_gate_close = False
    fail_recorder_close = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.gate_close_failures = 0
        self.recorder_close_failures = 0

    @classmethod
    def reset(cls):
        cls.fail_gate_close = False
        cls.fail_recorder_close = False
        GateAwareRecorder.instances = []

    def close_controlled_activation(self, activation_id=None, generation=None):
        if type(self).fail_gate_close:
            self.gate_close_failures += 1
            raise RuntimeError("controlled gate refused to close")
        return super().close_controlled_activation(
            activation_id, generation=generation
        )

    def flush_buffered_audio(self, min_abs_level=50):
        if type(self).fail_recorder_close:
            self.recorder_close_failures += 1
            raise RuntimeError("recorder refused to stop")
        return super().flush_buffered_audio(min_abs_level)


class ControlledCommandTestCase(unittest.TestCase):
    """Shared driving helpers: one session, one phase, one command."""

    QUERY = QUIET
    RECORDER_FACTORY = None

    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app(recorder_factory=self.RECORDER_FACTORY)

    def _trigger(self, session, **payload):
        payload.setdefault("type", "trigger")
        session.send(payload)
        return session.drain("trigger_ack")

    def _activate(self, session, command_id="open"):
        session.send({"type": "start"})
        return self._trigger(
            session, action="activate", source="manual", commandId=command_id
        )

    def _start_segment(self, session):
        session.socket.send_bytes(speech_packet())
        session.timeline("recording_started")

    def _end_segment(self, session):
        session.recorder().flush_buffered_audio()
        session.timeline("recording_ended")

    def _phase(self, session):
        return session.server_session(self.app).activation_snapshot()["phase"]

    def _drive_to(self, session, phase):
        """Brings a fresh streaming session into one foreground phase."""
        if phase == "idle":
            session.send({"type": "start"})
            session.settle()
            return None
        ack = self._activate(session)
        if phase == "waiting_first_speech":
            pass
        elif phase == "segment_active":
            self._start_segment(session)
        elif phase == "followup_wait":
            self._start_segment(session)
            self._end_segment(session)
        else:  # pragma: no cover - guarded by the callers
            raise AssertionError(f"unsupported phase: {phase}")
        self.assertEqual(self._phase(session), phase)
        return ack


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class CommandPhaseMatrixTests(ControlledCommandTestCase):
    """CMD-03/CMD-04 plus the refresh column of the frozen phase matrix."""

    #: ``phase -> action -> (accepted, reason)``
    MATRIX = {
        "idle": {
            "activate": (True, "activated"),
            "refresh": (False, "not_active"),
            "finish": (False, "not_active"),
            "cancel": (False, "not_active"),
        },
        "waiting_first_speech": {
            "activate": (False, "activation_locked"),
            "refresh": (False, "invalid_phase"),
            "finish": (True, "finished"),
            "cancel": (True, "cancelled"),
        },
        "segment_active": {
            "activate": (False, "activation_locked"),
            "refresh": (True, "refreshed"),
            "finish": (True, "finished"),
            "cancel": (True, "cancelled"),
        },
        "followup_wait": {
            "activate": (False, "activation_locked"),
            "refresh": (True, "refreshed"),
            "finish": (True, "finished"),
            "cancel": (True, "cancelled"),
        },
    }

    def test_every_open_phase_answers_every_action_as_the_contract_says(self):
        for phase, expectations in self.MATRIX.items():
            for action, (accepted, reason) in expectations.items():
                with self.subTest(phase=phase, action=action):
                    with TestClient(self.app) as client:
                        with ControlledSessionHarness(
                            client, self.QUERY
                        ) as session:
                            opened = self._drive_to(session, phase)
                            before = self._phase(session)
                            payload = {
                                "action": action,
                                "source": "manual",
                                "commandId": f"{phase}-{action}",
                            }
                            if action != "activate" and opened is not None:
                                payload["activationId"] = opened["activationId"]
                            ack = self._trigger(session, **payload)

                            self.assertEqual(ack["accepted"], accepted, ack)
                            self.assertEqual(ack["reason"], reason, ack)
                            if not accepted:
                                self.assertEqual(
                                    self._phase(session),
                                    before,
                                    "a rejected command must not change the phase",
                                )
                            if opened is not None and action != "activate":
                                self.assertEqual(
                                    ack["activationId"],
                                    opened["activationId"],
                                    "even a rejection stays correlated",
                                )

    def test_a_rejected_command_leaves_the_gate_and_timers_untouched(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                opened = self._drive_to(session, "waiting_first_speech")
                server = session.server_session(self.app)
                before = server.activation_snapshot()

                rejected = self._trigger(
                    session,
                    action="refresh",
                    source="manual",
                    commandId="reject-1",
                    activationId=opened["activationId"],
                )
                self.assertEqual(rejected["reason"], "invalid_phase")

                after = server.activation_snapshot()
                self.assertEqual(after["deadline"], before["deadline"])
                self.assertEqual(
                    after["timerRevision"], before["timerRevision"]
                )
                self.assertEqual(after["version"], before["version"])
                self.assertTrue(
                    session.recorder().controlled_activation_state()["active"]
                )

    def test_a_refresh_in_followup_wait_resets_the_deadline_from_now(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                opened = self._drive_to(session, "followup_wait")
                server = session.server_session(self.app)
                first = server.activation_snapshot()

                time.sleep(0.05)
                self._trigger(
                    session,
                    action="refresh",
                    source="manual",
                    commandId="fw-1",
                    activationId=opened["activationId"],
                )
                second = server.activation_snapshot()
                self._trigger(
                    session,
                    action="refresh",
                    source="manual",
                    commandId="fw-2",
                    activationId=opened["activationId"],
                )
                third = server.activation_snapshot()

                self.assertGreater(second["deadline"], first["deadline"])
                # Non cumulative: the window never grows beyond one timeout.
                span = third["deadline"] - second["deadline"]
                self.assertLess(
                    span, 1.0, "a second refresh must not bank another 60 s"
                )
                self.assertGreater(
                    third["timerRevision"], second["timerRevision"]
                )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class CommandReplayEndToEndTests(ControlledCommandTestCase):
    """CMD-05/CMD-06: one effect per ``commandId``, conflicts are refused."""

    def test_a_triple_replay_of_activate_opens_exactly_one_activation(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                command = {
                    "action": "activate",
                    "source": "manual",
                    "commandId": "replay-activate",
                }
                session.send({"type": "start"})
                first = self._trigger(session, **command)
                answers = [self._trigger(session, **command) for _ in range(3)]

                for answer in answers:
                    self.assertEqual(answer, first)
                snapshot = session.server_session(self.app).activation_snapshot()
                self.assertEqual(snapshot["activationSequence"], 1)
                self.assertEqual(
                    session.recorder().controlled_activation_state()[
                        "activationId"
                    ],
                    first["activationId"],
                )
                self.assertEqual(
                    len(session.timeline_events("activation_started")), 1
                )

    def test_a_refresh_replay_does_not_move_the_deadline_twice(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                opened = self._drive_to(session, "followup_wait")
                server = session.server_session(self.app)
                command = {
                    "action": "refresh",
                    "source": "manual",
                    "commandId": "replay-refresh",
                    "activationId": opened["activationId"],
                }
                first = self._trigger(session, **command)
                after_first = server.activation_snapshot()

                time.sleep(0.05)
                replay = self._trigger(session, **command)
                after_replay = server.activation_snapshot()

                self.assertEqual(replay, first)
                self.assertEqual(
                    after_replay["deadline"], after_first["deadline"]
                )
                self.assertEqual(
                    after_replay["timerRevision"], after_first["timerRevision"]
                )
                self.assertEqual(
                    len(session.timeline_events("activation_refreshed")), 1
                )

    def test_a_finish_replay_produces_no_second_lifecycle_or_ledger_event(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                opened = self._drive_to(session, "segment_active")
                command = {
                    "action": "finish",
                    "source": "manual",
                    "commandId": "replay-finish",
                    "activationId": opened["activationId"],
                }
                first = self._trigger(session, **command)
                self.assertTrue(first["accepted"])
                session.drain("final")

                for _ in range(3):
                    self.assertEqual(self._trigger(session, **command), first)
                session.settle()

                self.assertEqual(
                    len(session.timeline_events("activation_closed")), 1
                )
                self.assertEqual(
                    len(session.timeline_events("activation_drained")), 1
                )
                ledger = session.server_session(self.app).snapshot()[
                    "segmentLedger"
                ]
                self.assertEqual(ledger["pendingSegmentCount"], 0)
                self.assertEqual(
                    ledger["acceptedSegmentCount"],
                    ledger["terminalSegmentCount"],
                )

    def test_a_cancel_replay_cancels_exactly_once(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                opened = self._drive_to(session, "segment_active")
                command = {
                    "action": "cancel",
                    "source": "manual",
                    "commandId": "replay-cancel",
                    "activationId": opened["activationId"],
                }
                first = self._trigger(session, **command)
                self.assertTrue(first["accepted"])
                for _ in range(3):
                    self.assertEqual(self._trigger(session, **command), first)
                session.settle()

                drained = session.timeline_events("activation_drained")
                self.assertEqual(len(drained), 1)
                self.assertEqual(drained[0]["state"], "cancelled")
                self.assertEqual(
                    len(session.timeline_events("activation_closed")), 1
                )

    def test_the_same_command_id_with_another_payload_is_a_conflict(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                opened = self._drive_to(session, "followup_wait")
                first = self._trigger(
                    session,
                    action="refresh",
                    source="manual",
                    commandId="conflict-1",
                    activationId=opened["activationId"],
                )
                self.assertTrue(first["accepted"])

                for changed in (
                    {"action": "cancel", "source": "manual"},
                    {"action": "refresh", "source": "wake_word"},
                    {"action": "refresh", "source": "manual",
                     "activationId": "someone-else"},
                ):
                    with self.subTest(changed=changed):
                        payload = {
                            "commandId": "conflict-1",
                            "activationId": opened["activationId"],
                        }
                        payload.update(changed)
                        conflicting = self._trigger(session, **payload)
                        self.assertFalse(conflicting["accepted"])
                        self.assertEqual(
                            conflicting["reason"], "command_id_conflict"
                        )
                        self.assertEqual(
                            self._phase(session),
                            "followup_wait",
                            "a conflict must not change the foreground",
                        )

                # The original entry stays authoritative.
                self.assertEqual(
                    self._trigger(
                        session,
                        action="refresh",
                        source="manual",
                        commandId="conflict-1",
                        activationId=opened["activationId"],
                    ),
                    first,
                )

    def test_the_replay_cache_holds_for_the_whole_session(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                opened = self._drive_to(session, "waiting_first_speech")
                first = self._trigger(
                    session,
                    action="refresh",
                    source="manual",
                    commandId="ancient",
                    activationId=opened["activationId"],
                )
                for index in range(400):
                    self._trigger(
                        session,
                        action="refresh",
                        source="manual",
                        commandId=f"filler-{index}",
                        activationId=opened["activationId"],
                    )
                self.assertEqual(
                    self._trigger(
                        session,
                        action="refresh",
                        source="manual",
                        commandId="ancient",
                        activationId=opened["activationId"],
                    ),
                    first,
                )

    def test_a_malformed_command_never_occupies_its_command_id(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                session.send({"type": "start"})
                broken = self._trigger(
                    session, action="teleport", source="manual", commandId="m-1"
                )
                self.assertEqual(broken["reason"], "invalid_action")

                accepted = self._trigger(
                    session, action="activate", source="manual", commandId="m-1"
                )
                self.assertTrue(accepted["accepted"])
                self.assertEqual(accepted["reason"], "activated")


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class StaleActivationEndToEndTests(ControlledCommandTestCase):
    """CMD-02/CMD-07: a command aimed at an old activation is inert."""

    def _open_two_activations(self, session):
        first = self._activate(session, "stale-first")
        self._trigger(
            session,
            action="finish",
            source="manual",
            commandId="stale-close",
            activationId=first["activationId"],
        )
        second = self._trigger(
            session, action="activate", source="manual", commandId="stale-second"
        )
        self.assertNotEqual(first["activationId"], second["activationId"])
        return first, second

    def test_an_old_activation_id_cannot_touch_the_new_activation(self):
        for action in ("refresh", "finish", "cancel"):
            with self.subTest(action=action):
                with TestClient(self.app) as client:
                    with ControlledSessionHarness(
                        client, self.QUERY
                    ) as session:
                        first, second = self._open_two_activations(session)
                        server = session.server_session(self.app)
                        before = server.activation_snapshot()

                        ack = self._trigger(
                            session,
                            action=action,
                            source="manual",
                            commandId=f"stale-{action}",
                            activationId=first["activationId"],
                        )
                        self.assertFalse(ack["accepted"])
                        self.assertEqual(ack["reason"], "stale_activation")
                        self.assertEqual(
                            ack["activationId"], second["activationId"]
                        )

                        after = server.activation_snapshot()
                        self.assertEqual(after["phase"], before["phase"])
                        self.assertEqual(
                            after["timerRevision"], before["timerRevision"]
                        )
                        self.assertEqual(after["version"], before["version"])
                        self.assertTrue(
                            session.recorder().controlled_activation_state()[
                                "active"
                            ]
                        )

    def test_a_stale_command_racing_a_new_activation_is_deterministic(self):
        """The old command may win the race to the lock and must still lose.

        Both directions are exercised: the stale ``cancel`` is sent while the
        new ``activate`` is in flight, and either order has to end with the new
        activation open and untouched.
        """
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                first = self._activate(session, "race-first")
                self._trigger(
                    session,
                    action="finish",
                    source="manual",
                    commandId="race-close",
                    activationId=first["activationId"],
                )
                server = session.server_session(self.app)

                barrier = threading.Barrier(2)
                results = {}

                def stale_cancel():
                    barrier.wait(timeout=10)
                    results["cancel"] = server.handle_trigger_command({
                        "commandId": "race-cancel",
                        "action": "cancel",
                        "source": "manual",
                        "activationId": first["activationId"],
                    })

                def new_activate():
                    barrier.wait(timeout=10)
                    results["activate"] = server.handle_trigger_command({
                        "commandId": "race-activate",
                        "action": "activate",
                        "source": "manual",
                    })

                threads = [
                    threading.Thread(target=stale_cancel),
                    threading.Thread(target=new_activate),
                ]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=30)

                self.assertTrue(results["activate"]["accepted"])
                self.assertFalse(results["cancel"]["accepted"])
                self.assertIn(
                    results["cancel"]["reason"],
                    {"stale_activation", "not_active"},
                )
                snapshot = server.activation_snapshot()
                self.assertEqual(
                    snapshot["activationId"],
                    results["activate"]["activationId"],
                )
                self.assertEqual(snapshot["phase"], "waiting_first_speech")


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class SegmentWatchdogEndToEndTests(ControlledCommandTestCase):
    """SAFE-01/TIME-04/TIME-08 through the real recorder and ledger."""

    WATCHDOG = (
        "manualTriggerEnabled=true&wakeWordTriggerEnabled=false"
        "&initialSpeechTimeout=30&followupTimeout=30"
        "&segmentWatchdogInitialSeconds=0.8"
        "&segmentWatchdogRefreshSeconds=30"
        "&segmentWatchdogWarningSeconds=0.4"
        "&closingRecoveryTimeoutSeconds=5"
    )

    def test_the_watchdog_warns_then_closes_and_still_delivers_the_audio(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.WATCHDOG) as session:
                opened = self._activate(session, "wd-1")
                self._start_segment(session)

                warning = session.timeline("watchdog_warning", timeout=20.0)
                self.assertEqual(
                    warning["activationId"], opened["activationId"]
                )
                self.assertEqual(warning["phase"], "segment_active")
                self.assertEqual(warning["segmentSequence"], 1)

                closed = session.timeline("activation_closed", timeout=20.0)
                self.assertEqual(closed["reason"], "segment_watchdog_timeout")
                self.assertEqual(closed["cause"], "segment_watchdog_timeout")
                self.assertEqual(closed["phase"], "idle")

                # The recorded audio is processed like a regular finish.
                final = session.drain("final", timeout=20.0)
                self.assertEqual(final["activationId"], opened["activationId"])
                self.assertTrue(final["text"])

                session.settle()
                self.assertFalse(
                    session.recorder().controlled_activation_state()["active"],
                    "the watchdog must close the recorder gate",
                )

    def test_the_watchdog_opens_no_followup_window(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.WATCHDOG) as session:
                self._activate(session, "wd-2")
                self._start_segment(session)
                session.timeline("activation_closed", timeout=20.0)
                session.settle()

                snapshot = session.server_session(self.app).activation_snapshot()
                self.assertEqual(snapshot["phase"], "idle")
                self.assertIsNone(snapshot["deadline"])
                self.assertEqual(
                    len(session.timeline_events("activation_closed")), 1
                )
                # And speech after the watchdog no longer records.
                before = session.recorder().recording_starts
                session.socket.send_bytes(speech_packet())
                session.settle()
                self.assertEqual(
                    session.recorder().recording_starts, before
                )

    def test_only_one_warning_is_emitted_per_segment_deadline(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.WATCHDOG) as session:
                self._activate(session, "wd-3")
                self._start_segment(session)
                session.timeline("activation_closed", timeout=20.0)
                session.settle()
                self.assertEqual(
                    len(session.timeline_events("watchdog_warning")), 1
                )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class ClosingRecoveryEndToEndTests(ControlledCommandTestCase):
    """PHASE-05/SAFE-02: ``closing_input`` always finds its way back to idle."""

    RECORDER_FACTORY = FaultyGateRecorder
    RECOVERY = (
        "manualTriggerEnabled=true&wakeWordTriggerEnabled=false"
        "&initialSpeechTimeout=30&followupTimeout=30"
        "&segmentWatchdogInitialSeconds=30&segmentWatchdogRefreshSeconds=30"
        "&segmentWatchdogWarningSeconds=10"
        "&closingRecoveryTimeoutSeconds=0.5"
    )
    PARKED = RECOVERY.replace(
        "closingRecoveryTimeoutSeconds=0.5",
        "closingRecoveryTimeoutSeconds=30",
    )

    def setUp(self):
        FaultyGateRecorder.reset()
        super().setUp()

    def tearDown(self):
        FaultyGateRecorder.reset()

    def _park_in_closing_input(self, session, fault, command_id="stuck"):
        opened = self._activate(session, "recovery-open")
        self._start_segment(session)
        setattr(FaultyGateRecorder, fault, True)
        ack = self._trigger(
            session,
            action="finish",
            source="manual",
            commandId=command_id,
            activationId=opened["activationId"],
        )
        self.assertTrue(ack["accepted"])
        self.assertEqual(ack["reason"], "finished")
        self.assertEqual(self._phase(session), "closing_input")
        return opened

    def test_the_closing_input_row_of_the_phase_matrix(self):
        """The fifth phase of the matrix, reachable only through a fault.

        ``activate`` stays locked, ``refresh`` answers ``closing_input`` and
        ``finish``/``cancel`` give the idempotent state answer without a second
        transition, a second close event or a second ledger operation.
        """
        expectations = {
            "activate": (False, "activation_locked"),
            "refresh": (False, "closing_input"),
            "finish": (True, "no_change"),
            "cancel": (True, "no_change"),
        }
        for action, (accepted, reason) in expectations.items():
            with self.subTest(action=action):
                FaultyGateRecorder.reset()
                self.app = build_app(recorder_factory=FaultyGateRecorder)
                with TestClient(self.app) as client:
                    with ControlledSessionHarness(client, self.PARKED) as session:
                        opened = self._park_in_closing_input(
                            session, "fail_gate_close", command_id=f"park-{action}"
                        )
                        payload = {
                            "action": action,
                            "source": "manual",
                            "commandId": f"closing-{action}",
                        }
                        if action != "activate":
                            payload["activationId"] = opened["activationId"]
                        ack = self._trigger(session, **payload)

                        self.assertEqual(ack["accepted"], accepted, ack)
                        self.assertEqual(ack["reason"], reason, ack)
                        self.assertEqual(ack["phase"], "closing_input")
                        self.assertEqual(
                            ack["activationId"], opened["activationId"]
                        )
                        self.assertEqual(self._phase(session), "closing_input")
                        session.settle()
                        self.assertEqual(
                            session.timeline_events("activation_closed"),
                            [],
                            "no close event before the input is really closed",
                        )
                        self.assertEqual(
                            session.timeline_events("activation_drained"), []
                        )
                        FaultyGateRecorder.fail_gate_close = False

    def test_a_gate_close_fault_is_recovered_into_idle(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.RECOVERY) as session:
                opened = self._park_in_closing_input(session, "fail_gate_close")
                self.assertGreater(
                    session.recorder().gate_close_failures, 0
                )

                closed = session.timeline("activation_closed", timeout=20.0)
                self.assertEqual(closed["activationId"], opened["activationId"])
                self.assertEqual(closed["cause"], "closing_recovery_timeout")
                self.assertTrue(closed["recovered"])
                self.assertEqual(closed["phase"], "idle")
                self.assertFalse(
                    session.recorder().controlled_activation_state()["active"],
                    "recovery must close the gate defensively",
                )
                self.assertEqual(self._phase(session), "idle")

    def test_a_recorder_close_fault_is_recovered_into_idle(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.RECOVERY) as session:
                self._park_in_closing_input(session, "fail_recorder_close")
                self.assertGreater(
                    session.recorder().recorder_close_failures, 0
                )

                closed = session.timeline("activation_closed", timeout=20.0)
                self.assertEqual(closed["cause"], "closing_recovery_timeout")
                self.assertEqual(self._phase(session), "idle")

    def test_recovery_keeps_the_ledger_cardinality_consistent(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.RECOVERY) as session:
                self._park_in_closing_input(session, "fail_recorder_close")
                # The recovery resolves the orphaned segment and the ledger
                # before it publishes the single close event, so waiting for
                # that event is enough to have seen all of them.
                session.timeline("activation_closed", timeout=20.0)
                session.settle()

                ledger = session.server_session(self.app).snapshot()[
                    "segmentLedger"
                ]
                self.assertEqual(ledger["pendingSegmentCount"], 0)
                self.assertEqual(ledger["pendingActivationCount"], 0)
                self.assertEqual(
                    ledger["acceptedSegmentCount"],
                    ledger["terminalSegmentCount"],
                )
                self.assertEqual(ledger["terminalActivationCount"], 1)
                # The audio that never reached the pipeline is accounted for
                # instead of vanishing (SAFE-02).
                failed = session.timeline_events("final_transcript_failed")
                self.assertEqual(len(failed), 1)
                self.assertEqual(
                    failed[0]["reason"], "closing_recovery_timeout"
                )
                self.assertEqual(
                    len(session.timeline_events("activation_drained")), 1
                )

    def test_the_foreground_is_free_again_after_a_recovery(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.RECOVERY) as session:
                first = self._park_in_closing_input(
                    session, "fail_recorder_close"
                )
                session.timeline("activation_closed", timeout=20.0)
                FaultyGateRecorder.fail_recorder_close = False

                second = self._trigger(
                    session,
                    action="activate",
                    source="manual",
                    commandId="after-recovery",
                )
                self.assertTrue(second["accepted"])
                self.assertNotEqual(
                    second["activationId"], first["activationId"]
                )

    def test_a_stale_recovery_timer_cannot_end_a_newer_activation(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.PARKED) as session:
                first = self._park_in_closing_input(
                    session, "fail_gate_close", command_id="parked"
                )
                self.assertEqual(self._phase(session), "closing_input")

                # Stop tears the parked activation down and drops its timer.
                FaultyGateRecorder.fail_gate_close = False
                session.send({"type": "stop"})
                session.settle()
                self.assertEqual(self._phase(session), "idle")

                second = self._activate(session, "after-parked")
                self.assertTrue(second["accepted"])
                self.assertNotEqual(
                    second["activationId"], first["activationId"]
                )

                # Well past the parked activation's recovery deadline would be
                # 30 s, but its timer was dropped: nothing may fire at all.
                time.sleep(1.0)
                session.settle()
                snapshot = session.server_session(self.app).activation_snapshot()
                self.assertEqual(snapshot["phase"], "waiting_first_speech")
                self.assertEqual(
                    snapshot["activationId"], second["activationId"]
                )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class AudioAvailabilityEndToEndTests(ControlledCommandTestCase):
    """DEVICE-03/CORE-12: losing the device cancels the activation only."""

    def _availability(self, session, available, command_id):
        session.send({
            "type": "audio_availability",
            "commandId": command_id,
            "audioAvailable": available,
        })
        return session.drain("audio_availability_ack")

    def test_audio_loss_cancels_the_open_activation_and_keeps_the_session(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                opened = self._drive_to(session, "segment_active")
                ack = self._availability(session, False, "audio-1")

                self.assertTrue(ack["accepted"])
                self.assertEqual(ack["reason"], "applied")
                self.assertFalse(ack["audioAvailable"])

                closed = session.timeline("activation_closed", timeout=20.0)
                self.assertEqual(closed["activationId"], opened["activationId"])
                self.assertEqual(closed["reason"], "cancelled")
                self.assertEqual(closed["cause"], "audio_unavailable")
                self.assertEqual(self._phase(session), "idle")

                # The session itself is still usable.
                metrics = session.settle()
                self.assertEqual(metrics["type"], "metrics")

    def test_a_lost_device_refuses_a_new_activation_until_it_returns(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                session.send({"type": "start"})
                self._availability(session, False, "audio-2")

                blocked = self._trigger(
                    session, action="activate", source="manual",
                    commandId="blocked-1",
                )
                self.assertFalse(blocked["accepted"])
                self.assertEqual(blocked["reason"], "audio_unavailable")

                restored = self._availability(session, True, "audio-3")
                self.assertTrue(restored["accepted"])
                self.assertTrue(restored["audioAvailable"])

                accepted = self._trigger(
                    session, action="activate", source="manual",
                    commandId="restored-1",
                )
                self.assertTrue(accepted["accepted"])

    def test_audio_loss_never_withdraws_already_published_text(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                first = self._drive_to(session, "segment_active")
                self._trigger(
                    session,
                    action="finish",
                    source="manual",
                    commandId="publish-1",
                    activationId=first["activationId"],
                )
                published = session.drain("final", timeout=20.0)
                self.assertTrue(published["text"])

                second = self._trigger(
                    session, action="activate", source="manual",
                    commandId="publish-2",
                )
                self._start_segment(session)
                self._availability(session, False, "audio-4")
                session.timeline("activation_closed", timeout=20.0)
                session.settle()

                self.assertEqual(
                    [
                        message["text"]
                        for message in session.messages
                        if message.get("type") == "final"
                    ],
                    [published["text"]],
                    "the published result must survive the device loss",
                )
                cancelled = session.timeline_events("final_transcript_cancelled")
                self.assertEqual(len(cancelled), 1)
                self.assertEqual(
                    cancelled[0]["activationId"], second["activationId"]
                )

    def test_the_availability_command_is_idempotent_and_conflict_safe(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                session.send({"type": "start"})
                first = self._availability(session, False, "audio-5")
                for _ in range(3):
                    self.assertEqual(
                        self._availability(session, False, "audio-5"), first
                    )
                conflicting = self._availability(session, True, "audio-5")
                self.assertFalse(conflicting["accepted"])
                self.assertEqual(conflicting["reason"], "command_id_conflict")
                self.assertFalse(conflicting["audioAvailable"])


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class LedgerRegressionEndToEndTests(ControlledCommandTestCase):
    """The AP-SRV-020 invariants have to survive the new command/timer paths."""

    def test_segment_sequence_and_order_hold_across_the_new_close_paths(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                finals = []
                for index in range(3):
                    opened = self._trigger(
                        session,
                        action="activate",
                        source="manual",
                        commandId=f"seq-open-{index}",
                    ) if index else self._activate(session, "seq-open-0")
                    self._start_segment(session)
                    self._trigger(
                        session,
                        action="finish",
                        source="manual",
                        commandId=f"seq-close-{index}",
                        activationId=opened["activationId"],
                    )
                    final = session.drain("final", timeout=20.0)
                    finals.append(final)
                    self.assertEqual(
                        final["activationId"], opened["activationId"]
                    )
                    drained = session.timeline("activation_drained", timeout=20.0)
                    self.assertEqual(
                        drained["activationId"], opened["activationId"]
                    )

                self.assertEqual(
                    [final["segmentSequence"] for final in finals], [1, 2, 3]
                )
                self.assertEqual(
                    len(session.timeline_events("activation_drained")), 3
                )
                ledger = session.server_session(self.app).snapshot()[
                    "segmentLedger"
                ]
                self.assertEqual(ledger["pendingSegmentCount"], 0)
                self.assertEqual(ledger["pendingActivationCount"], 0)
                self.assertEqual(
                    ledger["acceptedSegmentCount"],
                    ledger["terminalSegmentCount"],
                )

    def test_two_serial_segments_keep_one_activation_and_two_sequences(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                opened = self._activate(session, "serial-open")
                self._start_segment(session)
                self._end_segment(session)
                first = session.drain("final", timeout=20.0)

                self._start_segment(session)
                self._trigger(
                    session,
                    action="finish",
                    source="manual",
                    commandId="serial-close",
                    activationId=opened["activationId"],
                )
                second = session.drain("final", timeout=20.0)
                session.timeline("activation_drained", timeout=20.0)

                self.assertEqual(first["activationId"], opened["activationId"])
                self.assertEqual(second["activationId"], opened["activationId"])
                self.assertEqual(first["segmentSequence"], 1)
                self.assertEqual(second["segmentSequence"], 2)
                drained = session.timeline_events("activation_drained")
                self.assertEqual(len(drained), 1)
                self.assertEqual(drained[0]["acceptedSegmentCount"], 2)
                self.assertEqual(drained[0]["terminalSegmentCount"], 2)


if __name__ == "__main__":
    unittest.main()
