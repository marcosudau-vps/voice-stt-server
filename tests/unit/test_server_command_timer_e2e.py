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

from api_fastapi_server.segment_ledger import SegmentLedger
from api_fastapi_server.server import ServerSettings, create_app as _create_app
from tests.unit.test_fastapi_server_multi_user import AutoScheduler as _AutoScheduler
from tests.unit.test_server_controlled_e2e import (
    BlockingScheduler,
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
                            if action != "activate":
                                # Controls carry the observed activation id;
                                # in idle no activation exists, so any id is
                                # stale and the answer is ``not_active``.
                                payload["activationId"] = (
                                    opened["activationId"]
                                    if opened is not None
                                    else "no-such-activation"
                                )
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

    def test_a_control_source_change_is_no_semantic_conflict(self):
        """F6: for controls the ignored legacy source field is not semantic.

        The C1 behaviour treated ``source`` changes of a control as a payload
        conflict; per the frozen contract source is not semantic for controls,
        so a pure source change stays a replay.
        """
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                opened = self._drive_to(session, "followup_wait")
                first = self._trigger(
                    session,
                    action="refresh",
                    source="manual",
                    commandId="source-neutral-1",
                    activationId=opened["activationId"],
                )
                self.assertTrue(first["accepted"])

                replay = self._trigger(
                    session,
                    action="refresh",
                    source="wake_word",
                    commandId="source-neutral-1",
                    activationId=opened["activationId"],
                )
                self.assertEqual(replay, first)

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

    def test_rejected_command_with_valid_id_is_replayed_and_conflicts_on_reuse(self):
        """T4/F3: a usable commandId stays occupied even when fachlich rejected.

        The C1 behaviour "a malformed command never occupies its command id"
        was fachlich wrong: an invalid action must be replay/idempotent and a
        later valid reuse of the same id must be a conflict.
        """
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                session.send({"type": "start"})
                broken = self._trigger(
                    session, action="teleport", source="manual", commandId="m-1"
                )
                self.assertEqual(broken["reason"], "invalid_action")

                repeat = self._trigger(
                    session, action="teleport", source="manual", commandId="m-1"
                )
                self.assertEqual(repeat, broken)

                conflict = self._trigger(
                    session, action="activate", source="manual", commandId="m-1"
                )
                self.assertFalse(conflict["accepted"])
                self.assertEqual(conflict["reason"], "command_id_conflict")

    def test_a_keyless_rejection_does_not_occupy_the_cache(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                session.send({"type": "start"})
                keyless = self._trigger(
                    session, action="teleport", source="manual"
                )
                self.assertEqual(keyless["reason"], "missing_command_id")

                accepted = self._trigger(
                    session, action="activate", source="manual",
                    commandId="fresh-1",
                )
                self.assertTrue(accepted["accepted"])


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


# -- AP-SRV-030 C2 regression tests -----------------------------------------
#
# These tests pin the C2 root findings on the real production wiring: the real
# websocket session, the real controller, the real ledger and the real
# recorder gate. Only *timing points* are blocked with events/barriers; no
# controller or ledger decision is rebuilt by a fake.


class BlockingGateCloseRecorder(GateAwareRecorder):
    """Gate-aware recorder whose gate close can be paused deterministically.

    Used for T5 (no new activation between Phase A and the registered input
    close) and T10 (the input close must not wait for the dispatch boundary
    while holding the session lock).
    """

    instances_list = []

    #: Module-level barrier refreshed per test.
    gate_entered = None
    gate_release = None
    gate_blocking = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        BlockingGateCloseRecorder.instances_list.append(self)

    @classmethod
    def reset(cls):
        cls.instances_list = []
        cls.gate_entered = threading.Event()
        cls.gate_release = threading.Event()
        cls.gate_blocking = False

    def close_controlled_activation(self, activation_id=None, generation=None):
        if type(self).gate_blocking:
            type(self).gate_entered.set()
            type(self).gate_release.wait(timeout=30)
        return super().close_controlled_activation(
            activation_id, generation=generation
        )


class BlockingRecoveryRecorder(GateAwareRecorder):
    """Gate-aware recorder whose recovery abort can be paused (T6).

    ``fail_gate_close`` keeps the foreground stuck in ``closing_input`` (the
    fault that makes recovery necessary); ``recovery_blocking`` then pauses
    the recovery worker inside the defensive abort so the test can prove no
    new activation is admitted while the cleanup runs.
    """

    instances_list = []

    recovery_entered = None
    recovery_release = None
    recovery_blocking = False
    fail_gate_close = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        BlockingRecoveryRecorder.instances_list.append(self)

    @classmethod
    def reset(cls):
        cls.instances_list = []
        cls.recovery_entered = threading.Event()
        cls.recovery_release = threading.Event()
        cls.recovery_blocking = False
        cls.fail_gate_close = False

    def close_controlled_activation(self, activation_id=None, generation=None):
        if type(self).fail_gate_close:
            raise RuntimeError("controlled gate refused to close")
        return super().close_controlled_activation(
            activation_id, generation=generation
        )

    def abort_controlled_activation(self):
        if type(self).recovery_blocking:
            type(self).recovery_entered.set()
            type(self).recovery_release.wait(timeout=30)
        return super().abort_controlled_activation()


class HardFailRecorder(BlockingGateCloseRecorder):
    """Recorder where every close/abort/flush path fails (T16)."""

    instances_list = []

    fail_gate_close = False
    fail_abort = False
    fail_flush = False
    fail_hard_abort = False

    @classmethod
    def reset(cls):
        cls.instances_list = []
        cls.fail_gate_close = False
        cls.fail_abort = False
        cls.fail_flush = False
        cls.fail_hard_abort = False

    def close_controlled_activation(self, activation_id=None, generation=None):
        if type(self).fail_gate_close:
            raise RuntimeError("gate close failed")
        return super().close_controlled_activation(
            activation_id, generation=generation
        )

    def abort_controlled_activation(self):
        if type(self).fail_abort:
            raise RuntimeError("gate abort failed")
        return super().abort_controlled_activation()

    def abort(self):
        if type(self).fail_hard_abort:
            raise RuntimeError("recorder hard abort failed")
        return super().abort()

    def flush_buffered_audio(self, min_abs_level=50):
        if type(self).fail_flush:
            raise RuntimeError("recorder flush failed")
        return super().flush_buffered_audio(min_abs_level)


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class ControlSourceNeutralEndToEndTests(ControlledCommandTestCase):
    """T2/T3: controls are source-neutral and need an observed activation id."""

    def test_control_without_activation_id_cannot_touch_a_newer_activation(self):
        """T2: A opens/closes, B opens. A control without id never touches B."""
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                first = self._activate(session, "t2-open-a")
                self._trigger(
                    session,
                    action="finish",
                    source="manual",
                    commandId="t2-close-a",
                    activationId=first["activationId"],
                )
                second = self._trigger(
                    session, action="activate", source="manual", commandId="t2-open-b"
                )
                self.assertNotEqual(
                    first["activationId"], second["activationId"]
                )
                server = session.server_session(self.app)
                before = server.activation_snapshot()

                for action in ("refresh", "finish", "cancel"):
                    with self.subTest(action=action):
                        ack = self._trigger(
                            session,
                            action=action,
                            source="manual",
                            commandId=f"t2-no-id-{action}",
                        )
                        self.assertFalse(ack["accepted"])
                        self.assertEqual(ack["reason"], "invalid_payload")
                        after = server.activation_snapshot()
                        self.assertEqual(
                            after["activationId"],
                            second["activationId"],
                        )
                        self.assertEqual(after["phase"], before["phase"])
                        self.assertEqual(
                            after["timerRevision"], before["timerRevision"]
                        )
                        self.assertTrue(
                            session.recorder().controlled_activation_state()[
                                "active"
                            ]
                        )

    def test_manual_disabled_does_not_disable_control_of_wake_activation(self):
        """T3: controls of a wake activation work with manual disabled.

        ``manualTriggerEnabled=false`` + ``wakeWordTriggerEnabled=true`` with
        an active wake-word profile: the wake word opens the activation, and a
        control without a source must be accepted - never ``trigger_disabled``.
        """
        from api_fastapi_server.server import create_app as _create_app

        settings = ServerSettings(
            model_warmup=False,
            request_logging_enabled=False,
            performance_logging_enabled=False,
            performance_log_mirror_enabled=False,
            transcription_logging_enabled=False,
            system_event_logging_enabled=False,
            event_store_enabled=False,
            log_live_enabled=False,
            realtime_processing_pause=0.0,
            realtime_min_audio_seconds=0.01,
            min_length_of_recording=0.0,
            post_speech_silence_duration=60.0,
            wakeword_backend="openwakeword",
            wake_words="hey_jarvis",
            openwakeword_model_paths="C:/models/hey_jarvis.onnx",
        )
        app = _create_app(
            settings,
            scheduler_factory=_AutoScheduler,
            recorder_factory=GateAwareRecorder,
        )
        query = (
            "manualTriggerEnabled=false&wakeWordTriggerEnabled=true"
            "&wakeWordBackend=openwakeword&wakeWords=hey_jarvis"
            "&initialSpeechTimeout=60&followupTimeout=60"
        )
        with TestClient(app) as client:
            with ControlledSessionHarness(client, query) as session:
                hello = session.hello
                self.assertEqual(
                    hello["activationConfig"]["mode"], "controlled"
                )
                self.assertFalse(
                    hello["activationConfig"]["manualTriggerEnabled"]
                )
                self.assertTrue(
                    hello["activationConfig"]["wakeWordTriggerEnabled"]
                )
                session.send({"type": "start"})
                session.settle()

                # The wake word is the only trigger; it goes through the same
                # controlled admission.
                recorder = session.recorder()
                recorder.simulate_wake_word()
                detected = session.timeline("wakeword_detected")
                activation_id = detected.get("activationId")
                self.assertTrue(activation_id)
                snapshot = session.server_session(app).activation_snapshot()
                self.assertEqual(snapshot["primarySource"], "wake_word")

                session.socket.send_bytes(speech_packet())
                started = session.timeline("recording_started")
                self.assertEqual(started["activationId"], activation_id)
                session.recorder().flush_buffered_audio()
                session.timeline("recording_ended")
                session.drain("final")

                # Control without any source field: accepted, source-neutral.
                session.send({
                    "type": "trigger",
                    "action": "refresh",
                    "commandId": "t3-refresh",
                    "activationId": activation_id,
                })
                refreshed = session.drain("trigger_ack")
                self.assertTrue(refreshed["accepted"])
                self.assertEqual(refreshed["reason"], "refreshed")
                self.assertEqual(
                    refreshed["activationId"], activation_id
                )
                refreshed_snapshot = session.server_session(
                    app
                ).activation_snapshot()
                self.assertEqual(
                    refreshed_snapshot["primarySource"], "wake_word"
                )
                self.assertEqual(
                    refreshed_snapshot["sources"], ["wake_word"]
                )

                session.send({
                    "type": "trigger",
                    "action": "finish",
                    "commandId": "t3-finish",
                    "activationId": activation_id,
                })
                finished = session.drain("trigger_ack")
                self.assertTrue(finished["accepted"])
                self.assertEqual(finished["reason"], "finished")


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class CloseAdmissionRaceEndToEndTests(ControlledCommandTestCase):
    """T5/T6: no new activation while the input close is being registered."""

    def setUp(self):
        BlockingGateCloseRecorder.reset()
        BlockingRecoveryRecorder.reset()
        super().setUp()

    def test_new_activation_stays_locked_until_normal_input_close_is_registered(self):
        """T5: during a blocked normal input close, activate B is locked.

        The finish is driven through the production session entry point
        (``RecorderBackedRealtimeSession.handle_trigger_command``) exactly like
        the stale-command race test, while the gate close is paused. Because
        ``activate`` needs the session lock and the controller stays in
        ``closing_input`` until the input close is registered, a new
        activation must be refused as ``activation_locked``.
        """
        app = build_app(recorder_factory=BlockingGateCloseRecorder)
        with TestClient(app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                session.send({"type": "start"})
                session.settle()
                server = session.server_session(app)
                opened = server.handle_trigger_command({
                    "type": "trigger",
                    "action": "activate",
                    "source": "manual",
                    "commandId": "t5-open-a",
                })
                self.assertTrue(opened["accepted"])

                BlockingGateCloseRecorder.gate_blocking = True
                close_result = {}

                def do_finish():
                    close_result["ack"] = server.handle_trigger_command({
                        "type": "trigger",
                        "action": "finish",
                        "source": "manual",
                        "commandId": "t5-finish",
                        "activationId": opened["activationId"],
                    })

                thread = threading.Thread(target=do_finish)
                thread.start()
                self.assertTrue(
                    BlockingGateCloseRecorder.gate_entered.wait(timeout=20)
                )

                locked = server.handle_trigger_command({
                    "type": "trigger",
                    "action": "activate",
                    "source": "manual",
                    "commandId": "t5-locked-b",
                })
                self.assertFalse(locked["accepted"])
                self.assertEqual(locked["reason"], "activation_locked")
                self.assertEqual(
                    locked["activationId"], opened["activationId"]
                )
                self.assertEqual(
                    server.activation_snapshot()["phase"], "closing_input"
                )

                BlockingGateCloseRecorder.gate_release.set()
                thread.join(timeout=30)
                self.assertTrue(close_result["ack"]["accepted"])

                second = server.handle_trigger_command({
                    "type": "trigger",
                    "action": "activate",
                    "source": "manual",
                    "commandId": "t5-open-b",
                })
                self.assertTrue(second["accepted"])
                self.assertNotEqual(
                    second["activationId"], opened["activationId"]
                )
                self.assertEqual(
                    server.activation_snapshot()["activationId"],
                    second["activationId"],
                )
                session.settle()
                self.assertTrue(
                    session.recorder().controlled_activation_state()["active"]
                )

    def test_new_activation_stays_locked_during_recovery_cleanup(self):
        """T6: while recovery cleanup is running, activate is locked.

        A fault parks the activation in ``closing_input``; the recovery worker
        then pauses inside the defensive abort. During that pause a new
        activation must be refused (the foreground is not idle yet and the
        session is not admitting), and it must stay the gate owner afterwards.
        """
        app = build_app(recorder_factory=BlockingRecoveryRecorder)
        BlockingRecoveryRecorder.fail_gate_close = True
        query = self.QUERY.replace(
            "closingRecoveryTimeoutSeconds=60",
            "closingRecoveryTimeoutSeconds=0.5",
        )
        with TestClient(app) as client:
            with ControlledSessionHarness(client, query) as session:
                session.send({"type": "start"})
                session.settle()
                server = session.server_session(app)
                opened = server.handle_trigger_command({
                    "type": "trigger",
                    "action": "activate",
                    "source": "manual",
                    "commandId": "t6-open-a",
                })
                self.assertTrue(opened["accepted"])

                # Let a recording start so there is real input to recover.
                session.socket.send_bytes(speech_packet())
                session.timeline("recording_started")

                # Cancel with a fault: gate close fails, phase stays closing.
                ack = server.handle_trigger_command({
                    "type": "trigger",
                    "action": "cancel",
                    "source": "manual",
                    "commandId": "t6-cancel",
                    "activationId": opened["activationId"],
                })
                self.assertTrue(ack["accepted"])
                self.assertEqual(
                    server.activation_snapshot()["phase"], "closing_input"
                )

                # The recovery worker parks in the abort gate.
                BlockingRecoveryRecorder.recovery_blocking = True
                self.assertTrue(
                    BlockingRecoveryRecorder.recovery_entered.wait(timeout=20)
                )
                locked = server.handle_trigger_command({
                    "type": "trigger",
                    "action": "activate",
                    "source": "manual",
                    "commandId": "t6-locked-b",
                })
                self.assertFalse(locked["accepted"])
                self.assertEqual(locked["reason"], "activation_locked")
                self.assertEqual(
                    server.activation_snapshot()["phase"], "closing_input"
                )

                BlockingRecoveryRecorder.recovery_release.set()
                deadline = time.monotonic() + 20
                while (
                    server.activation_snapshot()["phase"] != "idle"
                    and time.monotonic() < deadline
                ):
                    time.sleep(0.01)
                self.assertEqual(
                    server.activation_snapshot()["phase"], "idle"
                )
                session.settle()

                second = server.handle_trigger_command({
                    "type": "trigger",
                    "action": "activate",
                    "source": "manual",
                    "commandId": "t6-open-b",
                })
                self.assertTrue(second["accepted"])
                self.assertEqual(
                    server.activation_snapshot()["activationId"],
                    second["activationId"],
                )
                session.socket.send_bytes(speech_packet())
                started = session.timeline("recording_started")
                self.assertEqual(
                    started["activationId"], second["activationId"]
                )
                self.assertTrue(
                    session.recorder().controlled_activation_state()["active"]
                )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class CloseEventRegistrationEndToEndTests(ControlledCommandTestCase):
    """C3/PHASE-04: event registration precedes foreground release."""

    def test_new_activation_remains_locked_until_input_close_event_is_registered(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                opened = self._activate(session, command_id="c3-event-open")
                server = session.server_session(self.app)

                event_registered = threading.Event()
                release_after_registration = threading.Event()
                original_reserve = server._reserve_input_close_event

                def blocking_reserve(plan, *, recovery=False):
                    key = original_reserve(plan, recovery=recovery)
                    self.assertIsNotNone(key)
                    with server.lock:
                        self.assertIn(
                            key, server._registered_input_close_events
                        )
                    event_registered.set()
                    release_after_registration.wait(timeout=30)
                    return key

                server._reserve_input_close_event = blocking_reserve
                finish_result = {}

                def finish_a():
                    finish_result["ack"] = server.handle_trigger_command({
                        "type": "trigger",
                        "action": "finish",
                        "source": "manual",
                        "commandId": "c3-event-finish",
                        "activationId": opened["activationId"],
                    })

                thread = threading.Thread(target=finish_a)
                thread.start()
                self.assertTrue(event_registered.wait(timeout=20))

                self.assertEqual(
                    server.activation_snapshot()["phase"], "closing_input"
                )
                blocked = server.handle_trigger_command({
                    "type": "trigger",
                    "action": "activate",
                    "source": "manual",
                    "commandId": "c3-event-blocked-b",
                })
                self.assertFalse(blocked["accepted"])
                self.assertEqual(blocked["reason"], "activation_locked")
                self.assertEqual(
                    blocked["activationId"], opened["activationId"]
                )

                release_after_registration.set()
                thread.join(timeout=30)
                self.assertFalse(thread.is_alive())
                self.assertTrue(finish_result["ack"]["accepted"])
                self.assertEqual(
                    server.activation_snapshot()["phase"], "idle"
                )

                session.settle()
                close_events = [
                    event
                    for event in session.timeline_events("activation_closed")
                    if event.get("activationId") == opened["activationId"]
                ]
                self.assertEqual(len(close_events), 1)

                second = server.handle_trigger_command({
                    "type": "trigger",
                    "action": "activate",
                    "source": "manual",
                    "commandId": "c3-event-open-b",
                })
                self.assertTrue(second["accepted"])
                self.assertNotEqual(
                    second["activationId"], opened["activationId"]
                )

@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class RecoveryIdentityEndToEndTests(ClosingRecoveryEndToEndTests):
    """T7: recovery keeps the internal command identity but not the wire link."""

    def test_recovery_preserves_internal_command_identity_without_wrong_wire_correlation(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.RECOVERY) as session:
                opened = self._park_in_closing_input(
                    session, "fail_recorder_close", command_id="known-finish-id"
                )
                server = session.server_session(self.app)
                while server.activation_snapshot()["phase"] == "closing_input":
                    closed = session.timeline("activation_closed", timeout=20.0)
                    break
                self.assertEqual(closed["cause"], "closing_recovery_timeout")
                # The wire correlation must be null for a recovery completion.
                self.assertIsNone(closed.get("causedByCommandId"))
                self.assertNotIn(closed.get("causedByCommandId"), {"known-finish-id"})

                # Normal finish (no recovery) stays correlated.
                FaultyGateRecorder.fail_recorder_close = False
                second = self._trigger(
                    session,
                    action="activate",
                    source="manual",
                    commandId="t7-open-b",
                )
                self._start_segment(session)
                self._trigger(
                    session,
                    action="finish",
                    source="manual",
                    commandId="t7-finish",
                    activationId=second["activationId"],
                )
                final = session.drain("final", timeout=20.0)
                self.assertTrue(final["text"])
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    server_events = session.timeline_events("activation_closed")
                    if len(server_events) >= 2:
                        break
                    time.sleep(0.01)
                closed = session.timeline_events("activation_closed")[-1]
                self.assertEqual(closed["reason"], "finished")
                self.assertEqual(
                    closed.get("causedByCommandId"),
                    "t7-finish",
                    "a normal finish without recovery must stay correlated",
                )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class AudioAvailabilityCorrelationTests(ControlledCommandTestCase):
    """T8: the audio-availability command id is not a close correlation."""

    def test_audio_unavailable_command_id_is_not_a_finish_cancel_correlation(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                opened = self._drive_to(session, "segment_active")
                session.send({
                    "type": "audio_availability",
                    "commandId": "avail-id-1",
                    "audioAvailable": False,
                })
                ack = session.drain("audio_availability_ack")
                self.assertTrue(ack["accepted"])
                self.assertEqual(ack["commandId"], "avail-id-1")

                closed = session.timeline("activation_closed", timeout=20.0)
                self.assertEqual(closed["reason"], "cancelled")
                self.assertEqual(closed["cause"], "audio_unavailable")
                self.assertNotIn(
                    closed.get("causedByCommandId"), {"avail-id-1"}
                )
                self.assertIsNone(closed.get("causedByCommandId"))

                # The availability id remains replayable.
                session.send({
                    "type": "audio_availability",
                    "commandId": "avail-id-1",
                    "audioAvailable": False,
                })
                replay = session.drain("audio_availability_ack")
                self.assertEqual(replay, ack)


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class LedgerCancelTotalOrderTests(ControlledCommandTestCase):
    """T9: cancel/final total order over the real session-ledger wiring.

    Only the timing point is controlled (an event pauses the visible
    publication); the decisions and the ledger are entirely real.
    """

    def _start(self, app):
        self.client = TestClient(app)
        self.stream = ControlledSessionHarness(
            self.client, self.QUERY
        )
        self.stream.__enter__()
        self.stream.send({"type": "start"})
        server = self.stream.server_session(app)
        opened = server.handle_trigger_command({
            "action": "activate",
            "source": "manual",
            "commandId": "to-open",
        })
        self.assertTrue(opened["accepted"])
        return opened

    def _finish_stream(self):
        self.stream.__exit__(None, None, None)
        self.client.__exit__(None, None, None)

    def test_final_already_inside_dispatch_is_visible_before_cancel_can_be_accepted(self):
        """T9a/Fall A: a final that holds the dispatch boundary publishes first."""
        BlockingScheduler.instances = []
        app = build_app(scheduler_factory=BlockingScheduler)
        with TestClient(app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                session.send({"type": "start"})
                session.settle()
                server = session.server_session(app)
                opened = server.handle_trigger_command({
                    "action": "activate",
                    "source": "manual",
                    "commandId": "t9a-open",
                })
                self.assertTrue(opened["accepted"])
                session.socket.send_bytes(speech_packet())
                session.timeline("recording_started")
                # End the recording so a final job is submitted and *held* by
                # the blocking scheduler. The activation stays open (follow-up).
                session.recorder().flush_buffered_audio()
                session.timeline("recording_ended")
                server = session.server_session(app)
                scheduler = BlockingScheduler.instances[0]
                deadline = time.monotonic() + 10
                while not scheduler.jobs:
                    if time.monotonic() >= deadline:
                        self.fail("the final job was not submitted")
                    time.sleep(0.01)

                # A final result arrives. Pause its *visible publication* after
                # the ledger resolved it (inside ``_apply_ledger_update``),
                # while ``_ledger_dispatch_lock`` is still held.
                entered = threading.Event()
                release = threading.Event()
                original_apply = server._apply_ledger_update
                publication_visible = []

                def blocking_apply(update):
                    if update.publications and not release.is_set():
                        entered.set()
                        release.wait(timeout=30)
                    original_apply(update)
                    if update.publications:
                        publication_visible.append(update.publications)

                server._apply_ledger_update = blocking_apply

                # Drive the actual final resolution through the real scheduler
                # submission while the publication is paused. The scheduler
                # keeps the job pending, so the resolve runs inside the real
                # dispatch boundary.
                final_thread = threading.Thread(
                    target=scheduler.complete,
                    args=(scheduler.jobs[0], "visible-before-cancel"),
                )
                final_thread.start()
                self.assertTrue(entered.wait(timeout=20))

                # While the final holds the dispatch boundary, a cancel command
                # must not have been fachlich accepted yet.
                cancel_result = {}
                cancel_thread = threading.Thread(
                    target=lambda: cancel_result.update(
                        server.handle_trigger_command({
                            "action": "cancel",
                            "source": "manual",
                            "commandId": "t9a-cancel",
                            "activationId": opened["activationId"],
                        })
                    )
                )
                cancel_thread.start()
                time.sleep(0.1)
                self.assertNotIn("accepted", cancel_result)
                server._apply_ledger_update = original_apply
                release.set()
                final_thread.join(timeout=30)
                cancel_thread.join(timeout=30)

                self.assertEqual(len(publication_visible), 1)
                visible = publication_visible[0][0]
                self.assertEqual(
                    visible.text, "visible-before-cancel"
                )
                self.assertTrue(cancel_result["accepted"])
                self.assertEqual(
                    len(session.timeline_events("final_transcript_cancelled")),
                    0,
                    "the final was visible before cancel acceptance and stays",
                )

    def test_cancel_acceptance_blocks_every_later_final_publication(self):
        """T9b/Fall B: once cancel holds the barrier, no later final publishes."""
        BlockingScheduler.instances = []
        app = build_app(scheduler_factory=BlockingScheduler)
        with TestClient(app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                session.send({"type": "start"})
                session.settle()
                server = session.server_session(app)
                opened = server.handle_trigger_command({
                    "action": "activate",
                    "source": "manual",
                    "commandId": "t9b-open",
                })
                self.assertTrue(opened["accepted"])
                session.socket.send_bytes(speech_packet())
                session.timeline("recording_started")
                # A recording exists and its final job is held. Transfer it to
                # the blocking scheduler so the later resolve runs against the
                # cancel barrier.
                session.recorder().flush_buffered_audio()
                session.timeline("recording_ended")
                server = session.server_session(app)

                # Pause the cancel right after its barrier is set (still under
                # the dispatch boundary).
                barrier_set = threading.Event()
                release = threading.Event()
                server._test_cancel_after_barrier = lambda: (
                    barrier_set.set(), release.wait(timeout=30)
                )

                cancel_thread = threading.Thread(
                    target=lambda: server.handle_trigger_command({
                        "action": "cancel",
                        "source": "manual",
                        "commandId": "t9b-cancel",
                        "activationId": opened["activationId"],
                    })
                )
                cancel_thread.start()
                self.assertTrue(barrier_set.wait(timeout=20))

                # The final for the accepted segment must go through the real
                # dispatch boundary. Cancel already holds it, so the resolve
                # waits and - after the release - sees the cancel barrier.
                with server.segment_ledger._lock:
                    ctx = next(
                        record.context
                        for record in server.segment_ledger._segments.values()
                    )

                final_publication = {}
                final_thread = threading.Thread(
                    target=lambda: final_publication.update(
                        server._dispatch_ledger_operation(
                            server.segment_ledger.resolve_completed,
                            ctx,
                            "must-not-publish",
                        ).publications
                    )
                )
                final_thread.start()
                time.sleep(0.1)
                # The final is waiting on the dispatch boundary held by cancel.
                self.assertTrue(final_thread.is_alive())
                self.assertEqual(final_publication, {})

                server._test_cancel_after_barrier = None
                release.set()
                cancel_thread.join(timeout=30)
                final_thread.join(timeout=30)
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    server_ledger = session.server_session(app).snapshot()[
                        "segmentLedger"
                    ]
                    if server_ledger["pendingSegmentCount"] == 0:
                        break
                    time.sleep(0.01)
                session.settle()

                self.assertFalse(any(
                    message.get("type") == "final"
                    and message.get("text") == "must-not-publish"
                    for message in session.messages
                ))
                cancelled = session.timeline_events("final_transcript_cancelled")
                self.assertEqual(len(cancelled), 1)
                drained = session.timeline_events("activation_drained")
                self.assertEqual(len(drained), 1)
                self.assertEqual(drained[0]["state"], "cancelled")
                ledger = session.server_session(app).snapshot()["segmentLedger"]
                self.assertEqual(ledger["pendingSegmentCount"], 0)
                self.assertEqual(
                    ledger["acceptedSegmentCount"],
                    ledger["terminalSegmentCount"],
                )

    def test_cancel_removes_prepared_but_not_yet_published_text(self):
        """T9c: text already computed but blocked by a sequence hole is gone."""
        BlockingScheduler.instances = []
        app = build_app(scheduler_factory=BlockingScheduler)
        with TestClient(app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                session.send({"type": "start"})
                session.settle()
                server = session.server_session(app)
                opened = server.handle_trigger_command({
                    "action": "activate",
                    "source": "manual",
                    "commandId": "t9c-open",
                })
                self.assertTrue(opened["accepted"])

                # Segment 1 (hole) and segment 2 (prepared, unseen).
                session.socket.send_bytes(speech_packet())
                session.timeline("recording_started")
                session.recorder().flush_buffered_audio()
                session.timeline("recording_ended")
                session.socket.send_bytes(speech_packet())
                session.timeline("recording_started")

                ledger = server.segment_ledger
                # Reconstruct the two contexts from the ledger directly.
                with server.segment_ledger._lock:
                    ctxs = [
                        record.context
                        for record in server.segment_ledger._segments.values()
                    ]
                self.assertEqual(len(ctxs), 2)
                seg1, seg2 = ctxs

                # Segment 2 finishes while segment 1 is still an open hole.
                update = server._dispatch_ledger_operation(
                    ledger.resolve_completed, seg2, "hole-waiting"
                )
                self.assertEqual(update.publications, ())

                ack = server.handle_trigger_command({
                    "action": "cancel",
                    "source": "manual",
                    "commandId": "t9c-cancel",
                    "activationId": opened["activationId"],
                })
                self.assertTrue(ack["accepted"])
                session.settle()

                # Resolving the hole now must not publish the prepared text.
                update = server._dispatch_ledger_operation(
                    ledger.resolve_terminal, seg1, "discarded", "empty_final"
                )
                self.assertEqual(update.publications, ())
                session.settle()
                self.assertFalse(any(
                    message.get("type") == "final"
                    and message.get("text") == "hole-waiting"
                    for message in session.messages
                ))
                cancelled = session.timeline_events("final_transcript_cancelled")
                self.assertEqual(len(cancelled), 2)
                ledger_snapshot = ledger.snapshot()
                self.assertEqual(ledger_snapshot["pendingSegmentCount"], 0)
                self.assertEqual(
                    ledger_snapshot["acceptedSegmentCount"],
                    ledger_snapshot["terminalSegmentCount"],
                )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class LockOrderEndToEndTests(ControlledCommandTestCase):
    """T10: session lock is never held while waiting for the dispatch boundary."""

    def setUp(self):
        BlockingGateCloseRecorder.reset()
        super().setUp()

    def test_input_close_never_waits_for_dispatch_while_holding_session_lock(self):
        """A pinned dispatch lock cannot deadlock a normal input close."""
        BlockingGateCloseRecorder.reset()
        app = build_app(recorder_factory=BlockingGateCloseRecorder)
        with TestClient(app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                session.send({"type": "start"})
                session.settle()
                server = session.server_session(app)
                opened = server.handle_trigger_command({
                    "action": "activate",
                    "source": "manual",
                    "commandId": "t10-open",
                })
                self.assertTrue(opened["accepted"])

                # Another thread parks inside the dispatch boundary.
                dispatch_in = threading.Event()
                dispatch_free = threading.Event()
                dispatching = []

                def hold_dispatch():
                    with server._ledger_dispatch_lock:
                        dispatch_in.set()
                        dispatch_free.wait(timeout=30)
                        dispatching.append(True)

                holder = threading.Thread(target=hold_dispatch)
                holder.start()
                self.assertTrue(dispatch_in.wait(timeout=20))

                # A normal close accepts and runs Phase B. The gate close is
                # paused, which proves the close released self.lock before any
                # dispatch/recorder operation.
                BlockingGateCloseRecorder.gate_blocking = True
                close_result = {}

                def do_close():
                    close_result["ack"] = server.handle_trigger_command({
                        "action": "finish",
                        "source": "manual",
                        "commandId": "t10-finish",
                        "activationId": opened["activationId"],
                    })

                closer = threading.Thread(target=do_close)
                closer.start()
                self.assertTrue(
                    BlockingGateCloseRecorder.gate_entered.wait(timeout=20)
                )

                # While the close is parked in the gate close, the session lock
                # must be acquirable: the close is NOT holding it.
                acquired = server.lock.acquire(timeout=5)
                self.assertTrue(acquired, "close must release self.lock")
                server.lock.release()

                BlockingGateCloseRecorder.gate_release.set()
                dispatch_free.set()
                closer.join(timeout=30)
                holder.join(timeout=30)
                self.assertTrue(close_result["ack"]["accepted"])

    def test_cancel_uses_dispatch_then_session_lock_order(self):
        """Cancel acquires the dispatch boundary before the session lock.

        The instrumentation wraps both locks with delegating trackers that
        record the *nesting*: acquiring the dispatch boundary while the
        session lock is already held is the forbidden ``self.lock -> dispatch``
        and must never happen for a cancel.
        """
        app = build_app(recorder_factory=GateAwareRecorder)
        with TestClient(app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                session.send({"type": "start"})
                session.settle()
                server = session.server_session(app)
                opened = server.handle_trigger_command({
                    "action": "activate",
                    "source": "manual",
                    "commandId": "t10b-open",
                })
                self.assertTrue(opened["accepted"])

                state = {
                    "first": None,
                    "violations": [],
                    "depths": {},
                    "cancel_thread": None,
                }
                real_dispatch = server._ledger_dispatch_lock
                real_session = server.lock

                class TrackingLock:
                    def __init__(self, delegate, name, on_enter, on_exit):
                        self._delegate = delegate
                        self._name = name
                        self._on_enter = on_enter
                        self._on_exit = on_exit

                    def __enter__(self):
                        self._on_enter(self._name)
                        self._delegate.acquire()
                        return self

                    def __exit__(self, *exc):
                        self._on_exit(self._name)
                        self._delegate.release()
                        return False

                    def acquire(self, *a, **kw):
                        self._on_enter(self._name)
                        result = self._delegate.acquire(*a, **kw)
                        return result

                    def release(self):
                        self._on_exit(self._name)
                        return self._delegate.release()

                def thread_depth():
                    tid = threading.get_ident()
                    return state["depths"].setdefault(tid, {"dispatch": 0, "session": 0})

                def on_enter(name):
                    depth = thread_depth()
                    if state["first"] is None:
                        state["first"] = name
                    if name == "dispatch":
                        if depth["session"] > 0:
                            state["violations"].append(
                                f"dispatch-while-session(tid={threading.get_ident()})"
                            )
                        depth["dispatch"] += 1
                    else:
                        depth["session"] += 1

                def on_exit(name):
                    depth = thread_depth()
                    if name == "dispatch":
                        depth["dispatch"] -= 1
                    else:
                        depth["session"] -= 1

                dispatch_tracker = TrackingLock(
                    real_dispatch, "dispatch", on_enter, on_exit
                )
                session_tracker = TrackingLock(
                    real_session, "session", on_enter, on_exit
                )
                server._ledger_dispatch_lock = dispatch_tracker
                server.lock = session_tracker
                try:
                    ack = server.handle_trigger_command({
                        "action": "cancel",
                        "source": "manual",
                        "commandId": "t10b-cancel",
                        "activationId": opened["activationId"],
                    })
                finally:
                    server._ledger_dispatch_lock = real_dispatch
                    server.lock = real_session

                self.assertTrue(ack["accepted"])
                self.assertEqual(
                    state["violations"],
                    [],
                    "cancel must never acquire dispatch while holding the session lock",
                )
                self.assertEqual(
                    state["first"],
                    "dispatch",
                    "cancel must acquire the dispatch boundary first",
                )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class RecoveryFailClosedEndToEndTests(ControlledCommandTestCase):
    """T16: catastrophic recovery failure must fail closed, never fake idle."""

    def setUp(self):
        HardFailRecorder.reset()
        super().setUp()

    def test_recovery_cleanup_failure_never_publishes_idle_or_admits_new_activation(self):
        """Unrecoverable input cleanup terminates the session instead of hanging."""
        HardFailRecorder.fail_gate_close = True
        HardFailRecorder.fail_abort = True
        HardFailRecorder.fail_flush = True
        HardFailRecorder.fail_hard_abort = True
        query = self.QUERY.replace(
            "closingRecoveryTimeoutSeconds=60",
            "closingRecoveryTimeoutSeconds=0.5",
        )
        app = build_app(recorder_factory=HardFailRecorder)
        with TestClient(app) as client:
            with ControlledSessionHarness(client, query) as session:
                session.send({"type": "start"})
                session.settle()
                server = session.server_session(app)

                terminated = threading.Event()
                original_close = server.close

                def observed_close():
                    try:
                        return original_close()
                    finally:
                        terminated.set()

                server.close = observed_close

                stale_waiting_publish_attempted = threading.Event()
                original_publish_status = server.publish_status

                def observed_publish_status(state=None):
                    if (
                        terminated.is_set()
                        and state in {"listening", "wakeword_wait"}
                    ):
                        stale_waiting_publish_attempted.set()
                    return original_publish_status(state)

                server.publish_status = observed_publish_status

                opened = server.handle_trigger_command({
                    "action": "activate",
                    "source": "manual",
                    "commandId": "t16-open",
                })
                self.assertTrue(opened["accepted"])
                session.socket.send_bytes(speech_packet())
                session.timeline("recording_started")

                ack = server.handle_trigger_command({
                    "action": "cancel",
                    "source": "manual",
                    "commandId": "t16-cancel",
                    "activationId": opened["activationId"],
                })
                self.assertTrue(ack["accepted"])
                self.assertEqual(
                    server.activation_snapshot()["phase"], "closing_input"
                )

                self.assertTrue(terminated.wait(timeout=20))
                # Wait until the recovery timer worker has resumed and
                # attempted to publish the waiting state it calculated
                # before fail_closed_for_recovery(). The terminal guard
                # must make that stale publication inert.
                self.assertTrue(
                    stale_waiting_publish_attempted.wait(timeout=20)
                )
                self.assertEqual(server.status, "closed")
                self.assertFalse(server.streaming)
                self.assertFalse(server._audio_available)

                activation = server.activation_snapshot()
                self.assertEqual(activation["phase"], "idle")
                self.assertIsNone(activation["activationId"])

                ledger = server.segment_ledger.snapshot()
                self.assertEqual(ledger["pendingSegmentCount"], 0)
                self.assertEqual(ledger["pendingActivationCount"], 0)
                self.assertEqual(
                    ledger["acceptedSegmentCount"],
                    ledger["terminalSegmentCount"],
                )

                blocked = server.handle_trigger_command({
                    "action": "activate",
                    "source": "manual",
                    "commandId": "t16-blocked",
                })
                self.assertFalse(blocked["accepted"])
                self.assertEqual(blocked["reason"], "session_closed")

                close_event = session.timeline("activation_closed", timeout=20)
                self.assertEqual(close_event.get("reason"), "session_closed")
