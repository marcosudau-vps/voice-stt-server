"""AP-SRV-040 C2 – ``stateVersion`` is bound to visible state, not to events.

The frozen contract says ``stateVersion`` rises on **every visible state
change**. Several visible changes have no canonical event of their own:

* ``trigger.suppressed``/``trigger.effective`` after ``trigger_suppression.set``
  - ``activation.trigger_suppressed`` is diagnostic and only appears when a
  later trigger is refused;
* ``audioAvailable`` after ``audio_availability.set`` - the frozen event
  catalogue has no availability event at all;
* the entry into ``closing_input`` - one of the five canonical foreground
  phases, which an accepted ``finish``/``cancel`` reaches immediately while
  ``activation.input_closed`` only describes the *completed* close.

These tests pin the rule "one logical visible change, one advance" in both
directions: the change is versioned, and nothing that is not a visible change
- a replay, a refusal, a repeated no-op, a diagnostic event or a snapshot
request - advances anything.
"""

import threading
import unittest
import uuid

from api_fastapi_server.protocol_v2 import schema
from api_fastapi_server.protocol_v2.events import EventProjector, ProjectionContext
from api_fastapi_server.protocol_v2.session import ProtocolSessionState

from tests.unit.test_server_controlled_e2e import (
    GateAwareRecorder,
    TestClient,
    build_app,
    speech_packet,
)
from tests.unit.test_protocol_v2_e2e import V2Session


#: How often the replay- and race-sensitive versioning proofs are repeated.
REPETITIONS = 20

JOIN_TIMEOUT = 30.0


class StateVersionUnitTests(unittest.TestCase):
    def state(self):
        return ProtocolSessionState(schema.new_canonical_id())

    def test_advance_state_moves_the_version_by_exactly_one(self):
        state = self.state()
        self.assertEqual(state.advance_state(), 1)
        self.assertEqual(state.advance_state(), 2)
        self.assertEqual(state.state_version, 2)
        # It is a state advance, not an event: the sequence stays untouched.
        self.assertEqual(state.last_event_seq, 0)

    def test_concurrent_advances_never_collide(self):
        for repetition in range(REPETITIONS):
            with self.subTest(repetition=repetition):
                state = self.state()
                workers = 8
                per_worker = 10
                start = threading.Barrier(workers)
                seen = []
                lock = threading.Lock()

                def advance():
                    start.wait(timeout=JOIN_TIMEOUT)
                    for _ in range(per_worker):
                        version = state.advance_state()
                        with lock:
                            seen.append(version)

                threads = [
                    threading.Thread(target=advance) for _ in range(workers)
                ]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=JOIN_TIMEOUT)
                    self.assertFalse(thread.is_alive())

                total = workers * per_worker
                self.assertEqual(sorted(seen), list(range(1, total + 1)))
                self.assertEqual(state.state_version, total)

    def test_a_diagnostic_event_never_advances_the_version(self):
        state = self.state()
        projector = EventProjector(state)
        activation = schema.new_canonical_id()
        context = ProjectionContext(
            phase=schema.SEGMENT_ACTIVE, activation_id=activation
        )
        projector.project(
            "recording_started",
            {"segmentId": "s1", "segmentSequence": 1,
             "activationId": activation},
            context,
        )
        before = state.state_version
        produced = projector.project(
            "watchdog_warning",
            {"segmentId": "s1", "activationId": activation},
            context,
        )
        self.assertEqual(produced[-1]["type"], schema.EVENT_WATCHDOG_WARNING)
        self.assertEqual(produced[-1]["stateVersion"], before)
        self.assertEqual(state.state_version, before)


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class TriggerSuppressionVersionTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def test_an_applied_suppression_advances_ack_and_snapshot(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                before = session.snapshot()
                sent = session.command({
                    "type": schema.TRIGGER_SUPPRESSION_SET,
                    "manual": True,
                    "wakeWord": False,
                })
                ack = session.ack(sent["commandId"])
                after = session.snapshot()

                self.assertEqual(ack["result"], schema.RESULT_APPLIED)
                self.assertEqual(
                    ack["stateVersion"], before["stateVersion"] + 1
                )
                self.assertEqual(after["stateVersion"], ack["stateVersion"])
                # The change really is visible in the snapshot.
                self.assertTrue(after["trigger"]["suppressed"]["manual"])
                self.assertFalse(after["trigger"]["effective"]["manual"])
                self.assertFalse(before["trigger"]["suppressed"]["manual"])

    def test_a_no_change_suppression_advances_nothing(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                first = session.command({
                    "type": schema.TRIGGER_SUPPRESSION_SET,
                    "manual": True,
                    "wakeWord": True,
                })
                applied = session.ack(first["commandId"])
                self.assertEqual(applied["result"], schema.RESULT_APPLIED)

                second = session.command({
                    "type": schema.TRIGGER_SUPPRESSION_SET,
                    "manual": True,
                    "wakeWord": True,
                })
                ack = session.ack(second["commandId"])
                self.assertEqual(ack["result"], schema.RESULT_NO_CHANGE)
                self.assertEqual(
                    ack["stateVersion"], applied["stateVersion"]
                )
                self.assertEqual(
                    session.snapshot()["stateVersion"], applied["stateVersion"]
                )

    def test_a_suppression_replay_returns_the_original_version(self):
        for repetition in range(REPETITIONS):
            with self.subTest(repetition=repetition):
                GateAwareRecorder.instances = []
                app = build_app()
                with TestClient(app) as client:
                    with V2Session(client) as session:
                        payload = {
                            "type": schema.TRIGGER_SUPPRESSION_SET,
                            "protocolVersion": 2,
                            "sessionId": session.session_id,
                            "commandId": str(uuid.uuid4()),
                            "manual": True,
                            "wakeWord": False,
                        }
                        session.send_raw(dict(payload))
                        first = session.ack(payload["commandId"])
                        session.send_raw(dict(payload))
                        replay = session.ack(payload["commandId"])

                        self.assertEqual(first, replay)
                        self.assertEqual(
                            session.snapshot()["stateVersion"],
                            first["stateVersion"],
                        )

    def test_a_refused_trigger_diagnostic_advances_nothing(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                sent = session.command({
                    "type": schema.TRIGGER_SUPPRESSION_SET,
                    "manual": True,
                    "wakeWord": False,
                })
                suppression_ack = session.ack(sent["commandId"])

                _command_id, activate_ack = session.activate()
                self.assertEqual(
                    activate_ack["result"], schema.RESULT_TRIGGER_SUPPRESSED
                )
                diagnostic = session.event(
                    schema.EVENT_ACTIVATION_TRIGGER_SUPPRESSED
                )
                self.assertEqual(
                    diagnostic["stateVersion"], suppression_ack["stateVersion"]
                )
                self.assertEqual(
                    activate_ack["stateVersion"],
                    suppression_ack["stateVersion"],
                )
                self.assertEqual(
                    session.snapshot()["stateVersion"],
                    suppression_ack["stateVersion"],
                )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class AudioAvailabilityVersionTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def test_losing_the_device_in_idle_advances_the_version(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                before = session.snapshot()
                self.assertEqual(before["input"]["phase"], schema.IDLE)
                self.assertTrue(before["audioAvailable"])

                sent = session.command({
                    "type": schema.AUDIO_AVAILABILITY_SET,
                    "audioAvailable": False,
                })
                ack = session.ack(sent["commandId"])
                after = session.snapshot()

                self.assertEqual(ack["result"], schema.RESULT_APPLIED)
                self.assertEqual(
                    ack["stateVersion"], before["stateVersion"] + 1
                )
                self.assertEqual(after["stateVersion"], ack["stateVersion"])
                self.assertFalse(after["audioAvailable"])

    def test_a_repeated_availability_value_advances_nothing(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                first = session.command({
                    "type": schema.AUDIO_AVAILABILITY_SET,
                    "audioAvailable": False,
                })
                applied = session.ack(first["commandId"])
                self.assertEqual(applied["result"], schema.RESULT_APPLIED)

                second = session.command({
                    "type": schema.AUDIO_AVAILABILITY_SET,
                    "audioAvailable": False,
                })
                ack = session.ack(second["commandId"])
                self.assertEqual(ack["result"], schema.RESULT_NO_CHANGE)
                self.assertEqual(ack["stateVersion"], applied["stateVersion"])
                self.assertEqual(
                    session.snapshot()["stateVersion"], applied["stateVersion"]
                )

    def test_an_availability_replay_returns_the_original_version(self):
        for repetition in range(REPETITIONS):
            with self.subTest(repetition=repetition):
                GateAwareRecorder.instances = []
                app = build_app()
                with TestClient(app) as client:
                    with V2Session(client) as session:
                        payload = {
                            "type": schema.AUDIO_AVAILABILITY_SET,
                            "protocolVersion": 2,
                            "sessionId": session.session_id,
                            "commandId": str(uuid.uuid4()),
                            "audioAvailable": False,
                        }
                        session.send_raw(dict(payload))
                        first = session.ack(payload["commandId"])
                        session.send_raw(dict(payload))
                        replay = session.ack(payload["commandId"])

                        self.assertEqual(first, replay)
                        self.assertEqual(
                            session.snapshot()["stateVersion"],
                            first["stateVersion"],
                        )

    def test_a_device_close_versions_one_logical_change_once(self):
        """Availability *and* phase change in one accepted command.

        The frozen contract wants one advance per logical visible change, so
        the single accepted command reports one new version - not two - and the
        later completed close reports the next one. No version is skipped and
        none is used twice.
        """
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                _command_id, activate_ack = session.activate()
                started = session.event(schema.EVENT_ACTIVATION_STARTED)
                session.send_bytes(speech_packet())
                session.event(schema.EVENT_SEGMENT_RECORDING_STARTED)
                before = session.snapshot()["stateVersion"]

                sent = session.command({
                    "type": schema.AUDIO_AVAILABILITY_SET,
                    "audioAvailable": False,
                })
                ack = session.ack(sent["commandId"])
                closed = session.event(schema.EVENT_ACTIVATION_INPUT_CLOSED)
                after = session.snapshot()

                self.assertEqual(ack["result"], schema.RESULT_APPLIED)
                self.assertEqual(ack["inputPhase"], schema.CLOSING_INPUT)
                self.assertGreater(ack["stateVersion"], before)
                self.assertGreater(started["stateVersion"], 0)
                # The completed close is a second visible change.
                self.assertGreater(closed["stateVersion"], ack["stateVersion"])
                self.assertEqual(
                    closed["activationId"], activate_ack["activationId"]
                )
                self.assertIsNone(closed["causedByCommandId"])

                self.assertFalse(after["audioAvailable"])
                self.assertEqual(after["input"]["phase"], schema.IDLE)
                self.assertGreaterEqual(
                    after["stateVersion"], closed["stateVersion"]
                )
                self.assertEqual(
                    len(session.collected(
                        schema.EVENT_ACTIVATION_INPUT_CLOSED
                    )),
                    1,
                )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class ClosingInputVersionTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def _assert_close_versioning(self, action):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                _command_id, activate_ack = session.activate()
                started = session.event(schema.EVENT_ACTIVATION_STARTED)

                sent = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": action,
                    "activationId": activate_ack["activationId"],
                })
                ack = session.ack(sent["commandId"])
                closed = session.event(schema.EVENT_ACTIVATION_INPUT_CLOSED)
                after = session.snapshot()

                self.assertEqual(ack["result"], schema.RESULT_APPLIED)
                # The ack already reports the visible closing phase …
                self.assertEqual(ack["inputPhase"], schema.CLOSING_INPUT)
                # … so it must not still carry the version of the open phase.
                self.assertGreater(
                    ack["stateVersion"], started["stateVersion"]
                )
                # … and it must not borrow the version of the completed close.
                self.assertGreater(
                    closed["stateVersion"], ack["stateVersion"]
                )
                self.assertEqual(
                    closed["causedByCommandId"], sent["commandId"]
                )
                self.assertEqual(after["input"]["phase"], schema.IDLE)
                self.assertGreaterEqual(
                    after["stateVersion"], closed["stateVersion"]
                )
                return started, ack, closed

    def test_finish_versions_the_closing_entry_and_the_close(self):
        self._assert_close_versioning(schema.FINISH)

    def test_cancel_versions_the_closing_entry_and_the_close(self):
        self._assert_close_versioning(schema.CANCEL)

    def test_a_repeated_control_in_closing_input_advances_nothing(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                _command_id, activate_ack = session.activate()
                session.event(schema.EVENT_ACTIVATION_STARTED)
                first = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": schema.FINISH,
                    "activationId": activate_ack["activationId"],
                })
                session.ack(first["commandId"])
                session.event(schema.EVENT_ACTIVATION_INPUT_CLOSED)
                settled = session.snapshot()["stateVersion"]

                repeat = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": schema.FINISH,
                    "activationId": activate_ack["activationId"],
                })
                ack = session.ack(repeat["commandId"])
                self.assertIn(
                    ack["result"],
                    {schema.RESULT_NO_CHANGE, schema.RESULT_NOT_ACTIVE},
                )
                self.assertEqual(ack["stateVersion"], settled)
                self.assertEqual(
                    session.snapshot()["stateVersion"], settled
                )

    def test_a_finish_replay_returns_the_original_version(self):
        for repetition in range(REPETITIONS):
            with self.subTest(repetition=repetition):
                GateAwareRecorder.instances = []
                app = build_app()
                with TestClient(app) as client:
                    with V2Session(client) as session:
                        _command_id, activate_ack = session.activate()
                        session.event(schema.EVENT_ACTIVATION_STARTED)
                        payload = {
                            "type": schema.ACTIVATION_COMMAND,
                            "protocolVersion": 2,
                            "sessionId": session.session_id,
                            "commandId": str(uuid.uuid4()),
                            "action": schema.FINISH,
                            "activationId": activate_ack["activationId"],
                        }
                        session.send_raw(dict(payload))
                        first = session.ack(payload["commandId"])
                        session.event(
                            schema.EVENT_ACTIVATION_INPUT_CLOSED
                        )
                        settled = session.snapshot()["stateVersion"]

                        session.send_raw(dict(payload))
                        replay = session.ack(payload["commandId"])
                        self.assertEqual(first, replay)
                        self.assertEqual(
                            session.snapshot()["stateVersion"], settled
                        )
                        self.assertEqual(
                            len(session.collected(
                                schema.EVENT_ACTIVATION_INPUT_CLOSED
                            )),
                            1,
                        )

    def test_a_retried_close_versions_the_entry_only_once(self):
        """A failed close that the recovery repeats is one logical entry."""
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                connection_state = session.accepted
                del connection_state
                service = self.app.state.voicestt_service
                server_session = service.sessions.get(session.session_id)
                self.assertIsNotNone(server_session)

                _command_id, activate_ack = session.activate()
                session.event(schema.EVENT_ACTIVATION_STARTED)
                sent = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": schema.FINISH,
                    "activationId": activate_ack["activationId"],
                })
                ack = session.ack(sent["commandId"])
                session.event(schema.EVENT_ACTIVATION_INPUT_CLOSED)
                settled = session.snapshot()["stateVersion"]

                # Replay the very same closing notification the recovery would
                # send for the same activation.
                server_session._notify_protocol_observer(
                    server_session.INPUT_CLOSING_NOTIFICATION,
                    {
                        "activationId": activate_ack["activationId"],
                        "activationSequence": 1,
                        "reason": "finished",
                        "recovery": True,
                    },
                )
                self.assertEqual(
                    session.snapshot()["stateVersion"], settled
                )
                self.assertGreater(settled, ack["stateVersion"])


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class NonMutatingCommandVersionTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def test_a_snapshot_request_advances_nothing(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                first = session.snapshot()
                second = session.snapshot()
                third = session.snapshot()
                self.assertEqual(first["stateVersion"], second["stateVersion"])
                self.assertEqual(second["stateVersion"], third["stateVersion"])

    def test_no_refusal_advances_the_version(self):
        refusals = (
            ("client claims wake word", {
                "type": schema.ACTIVATION_COMMAND,
                "action": schema.ACTIVATE,
                "source": schema.WAKE_WORD_SOURCE,
            }),
            ("control without activationId", {
                "type": schema.ACTIVATION_COMMAND,
                "action": schema.REFRESH,
            }),
            ("stale session", {
                "type": schema.ACTIVATION_COMMAND,
                "sessionId": "20000000-0000-4000-8000-0000000000ff",
                "action": schema.ACTIVATE,
                "source": schema.MANUAL_SOURCE,
            }),
            ("stale activation", {
                "type": schema.ACTIVATION_COMMAND,
                "action": schema.FINISH,
                "activationId": "30000000-0000-4000-8000-0000000000ff",
            }),
            ("settings patch", {
                "type": schema.SESSION_SETTINGS_PATCH,
                "baseSettingsRevision": 0,
                "changes": {"activation.followupTimeoutMs": 4000},
            }),
        )
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                baseline = session.snapshot()["stateVersion"]
                for label, payload in refusals:
                    with self.subTest(case=label):
                        sent = session.command(payload)
                        ack = session.ack(sent["commandId"])
                        self.assertFalse(ack["accepted"], ack)
                        self.assertEqual(ack["stateVersion"], baseline)
                        self.assertEqual(
                            session.snapshot()["stateVersion"], baseline
                        )

    def test_a_command_id_conflict_advances_nothing(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                command_id = str(uuid.uuid4())
                session.send_raw({
                    "type": schema.TRIGGER_SUPPRESSION_SET,
                    "protocolVersion": 2,
                    "sessionId": session.session_id,
                    "commandId": command_id,
                    "manual": True,
                    "wakeWord": False,
                })
                applied = session.ack(command_id)
                self.assertEqual(applied["result"], schema.RESULT_APPLIED)

                session.send_raw({
                    "type": schema.TRIGGER_SUPPRESSION_SET,
                    "protocolVersion": 2,
                    "sessionId": session.session_id,
                    "commandId": command_id,
                    "manual": False,
                    "wakeWord": True,
                })
                conflict = session.ack(command_id)
                self.assertEqual(
                    conflict["result"], schema.RESULT_COMMAND_ID_CONFLICT
                )
                self.assertEqual(
                    conflict["stateVersion"], applied["stateVersion"]
                )
                snapshot = session.snapshot()
                self.assertEqual(
                    snapshot["stateVersion"], applied["stateVersion"]
                )
                # The conflicting payload had no effect either.
                self.assertTrue(snapshot["trigger"]["suppressed"]["manual"])
                self.assertFalse(snapshot["trigger"]["suppressed"]["wakeWord"])

    def test_a_no_op_refresh_advances_nothing(self):
        """``refreshed`` without a moved deadline is not a visible change."""
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                _command_id, activate_ack = session.activate()
                session.event(schema.EVENT_ACTIVATION_STARTED)
                session.send_bytes(speech_packet())
                session.event(schema.EVENT_SEGMENT_RECORDING_STARTED)
                before = session.snapshot()["stateVersion"]

                # The segment watchdog deadline is far beyond the refresh
                # window, so ``max(current, now + refresh)`` cannot move it.
                sent = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": schema.REFRESH,
                    "activationId": activate_ack["activationId"],
                })
                ack = session.ack(sent["commandId"])
                self.assertEqual(ack["result"], schema.RESULT_APPLIED)
                self.assertEqual(ack["stateVersion"], before)
                self.assertEqual(
                    session.snapshot()["stateVersion"], before
                )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class StateVersionMonotonicityTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def test_a_full_activation_cycle_never_reuses_or_skips_a_version(self):
        for repetition in range(REPETITIONS):
            with self.subTest(repetition=repetition):
                GateAwareRecorder.instances = []
                app = build_app()
                with TestClient(app) as client:
                    with V2Session(client) as session:
                        _command_id, activate_ack = session.activate()
                        session.event(schema.EVENT_ACTIVATION_STARTED)
                        session.send_bytes(speech_packet())
                        session.event(
                            schema.EVENT_SEGMENT_RECORDING_STARTED
                        )
                        session.recorder().flush_buffered_audio()
                        session.event(schema.EVENT_SEGMENT_RECORDING_ENDED)
                        sent = session.command({
                            "type": schema.ACTIVATION_COMMAND,
                            "action": schema.FINISH,
                            "activationId": activate_ack["activationId"],
                        })
                        session.ack(sent["commandId"])
                        session.event(
                            schema.EVENT_ACTIVATION_INPUT_CLOSED
                        )
                        final = session.snapshot()

                        received = [
                            message for message in session.messages
                            if message.get("type") in schema.EVENT_TYPES
                        ]
                        # The dispatch boundary preserves mint order on the
                        # wire, so the client observes the version invariants
                        # directly without reconstructing a reordered stream.
                        events = received
                        versions = [
                            event["stateVersion"] for event in events
                        ]
                        self.assertEqual(versions, sorted(versions))
                        self.assertEqual(
                            len(set(event["eventId"] for event in events)),
                            len(events),
                        )
                        self.assertLessEqual(
                            max(versions), final["stateVersion"]
                        )
                        # Every event of this cycle is a state event and there
                        # is exactly one eventless visible change - the entry
                        # into ``closing_input``. So the version is ahead of
                        # the sequence by exactly one: neither a missing nor a
                        # double advance can hide in here.
                        self.assertEqual(
                            final["stateVersion"], final["lastEventSeq"] + 1
                        )
                        sequences = [event["eventSeq"] for event in events]
                        self.assertEqual(
                            sequences, list(range(1, len(sequences) + 1))
                        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
