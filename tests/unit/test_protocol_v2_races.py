"""AP-SRV-040 – deterministic ordering proofs for the v2 wire layer.

Ordering is forced with :class:`threading.Barrier` and :class:`threading.Event`
hook points. A sleep is never an ordering mechanism here; the only timeouts are
failsafes that turn a deadlock into a failing test instead of a hanging one.

The critical invariants are repeated ``REPETITIONS`` times, because a race that
only shows up once in a while is exactly the kind this file exists to catch.

Two levels are covered on purpose. The projector and the protocol session
state are hit by real parallel threads, because that is where AP-SRV-040 owns
the identity. The socket-level tests race the *submission* of commands; a
single WebSocket then serialises the frames, so what they prove is that the
wire layer keeps its guarantees whatever order the domain ends up seeing -
the domain's own thread races are proven by the AP-SRV-030 suite.
"""

import threading
import unittest
import uuid

from api_fastapi_server.protocol_v2 import schema
from api_fastapi_server.protocol_v2.connection import ProtocolV2Connection
from api_fastapi_server.protocol_v2.events import (
    EventProjector,
    ProjectionContext,
)
from api_fastapi_server.protocol_v2.session import ProtocolSessionState

from tests.unit.test_server_controlled_e2e import (
    GateAwareRecorder,
    TestClient,
    build_app,
    speech_packet,
)
from tests.unit.test_protocol_v2_e2e import V2Session


#: How often each race-sensitive invariant is repeated.
REPETITIONS = 20

#: Failsafe only - never an ordering mechanism.
JOIN_TIMEOUT = 30.0


class EventDispatchOrderingTests(unittest.TestCase):
    def test_mint_to_sink_is_linearized_across_domain_threads(self):
        first_activation = schema.new_canonical_id()
        second_activation = schema.new_canonical_id()
        first_minted = threading.Event()
        contender_waiting = threading.Event()
        received = []

        class ObservedRLock:
            def __init__(self):
                self._lock = threading.RLock()
                self._owned = threading.Event()

            def __enter__(self):
                if self._owned.is_set():
                    contender_waiting.set()
                self._lock.acquire()
                self._owned.set()
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                self._owned.clear()
                self._lock.release()

        connection = ProtocolV2Connection(object())
        connection._event_dispatch_lock = ObservedRLock()
        connection.session = type(
            "SessionStub",
            (),
            {"INPUT_CLOSING_NOTIFICATION": "__input_closing__"},
        )()
        connection.state = ProtocolSessionState(schema.new_canonical_id())
        delegate = EventProjector(connection.state)

        class GatedProjector:
            def project(self, legacy_event, payload, context):
                events = delegate.project(legacy_event, payload, context)
                if payload["activationId"] == first_activation:
                    first_minted.set()
                    if not contender_waiting.wait(timeout=JOIN_TIMEOUT):
                        raise AssertionError("second publisher never reached dispatch")
                return events

        connection.projector = GatedProjector()
        connection._projection_context = lambda: ProjectionContext(
            phase=schema.SEGMENT_ACTIVE,
            activation_id=first_activation,
        )

        connection.set_sink(
            lambda payload: received.append(payload["eventSeq"])
        )

        def publish(legacy_event, activation_id):
            payload = {
                "activationId": activation_id,
            }
            if legacy_event == "activation_drained":
                payload.update({
                    "state": "completed",
                    "acceptedSegmentCount": 0,
                    "terminalSegmentCount": 0,
                })
            connection._on_domain_event(legacy_event, payload)

        # watchdog.warning also derives activation.phase_changed here, so the
        # first projection is a two-event block that must stay contiguous.
        first = threading.Thread(
            target=publish, args=("watchdog_warning", first_activation)
        )
        second = threading.Thread(
            target=publish, args=("activation_drained", second_activation)
        )
        first.start()
        self.assertTrue(first_minted.wait(timeout=JOIN_TIMEOUT))
        second.start()
        for thread in (first, second):
            thread.join(timeout=JOIN_TIMEOUT)
            self.assertFalse(thread.is_alive())

        self.assertEqual(received, [1, 2, 3])

    def test_many_mixed_domain_and_diagnostic_events_reach_sink_in_mint_order(self):
        connection = ProtocolV2Connection(object())
        connection.session = type(
            "SessionStub",
            (),
            {"INPUT_CLOSING_NOTIFICATION": "__input_closing__"},
        )()
        connection.state = ProtocolSessionState(schema.new_canonical_id())
        connection.projector = EventProjector(connection.state)
        connection._projection_context = ProjectionContext
        received = []
        connection.set_sink(received.append)

        workers = 6
        per_worker = 15
        start = threading.Barrier(workers)

        def publish(index):
            start.wait(timeout=JOIN_TIMEOUT)
            for step in range(per_worker):
                event_kind = (index + step) % 3
                if event_kind == 0:
                    parsed = type(
                        "ParsedStub",
                        (),
                        {"payload": {"source": schema.MANUAL_SOURCE}},
                    )()
                    connection._emit_trigger_suppressed(parsed)
                elif event_kind == 1:
                    connection._on_domain_event("activation_drained", {
                        "activationId": schema.new_canonical_id(),
                        "state": "completed",
                        "acceptedSegmentCount": 0,
                        "terminalSegmentCount": 0,
                    })
                else:
                    connection._on_domain_event("activation_started", {
                        "activationId": schema.new_canonical_id(),
                        "activationSequence": index * per_worker + step + 1,
                        "primarySource": schema.MANUAL_SOURCE,
                    })

        threads = [
            threading.Thread(target=publish, args=(index,))
            for index in range(workers)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=JOIN_TIMEOUT)
            self.assertFalse(thread.is_alive())

        total = workers * per_worker
        sequences = [event["eventSeq"] for event in received]
        versions = [event["stateVersion"] for event in received]
        self.assertEqual(sequences, list(range(1, total + 1)))
        self.assertEqual(versions, sorted(versions))
        self.assertEqual(
            len({event["eventId"] for event in received}), total
        )
        self.assertEqual(
            {event["type"] for event in received},
            {
                schema.EVENT_ACTIVATION_COMPLETED,
                schema.EVENT_ACTIVATION_STARTED,
                schema.EVENT_ACTIVATION_TRIGGER_SUPPRESSED,
            },
        )

    def test_connection_close_around_sink_handoff_does_not_deadlock(self):
        connection = ProtocolV2Connection(object())
        connection.session = type(
            "SessionStub",
            (),
            {"INPUT_CLOSING_NOTIFICATION": "__input_closing__"},
        )()
        connection.state = ProtocolSessionState(schema.new_canonical_id())
        connection.projector = EventProjector(connection.state)
        connection._projection_context = ProjectionContext
        event_at_sink = threading.Event()
        close_at_sink = threading.Event()
        received = []

        def sink(payload):
            if payload is None:
                close_at_sink.set()
                return
            event_at_sink.set()
            if not close_at_sink.wait(timeout=JOIN_TIMEOUT):
                raise AssertionError("close never reached the sink")
            received.append(payload["eventSeq"])

        connection.set_sink(sink)

        def publish():
            connection._on_domain_event("activation_drained", {
                "activationId": schema.new_canonical_id(),
                "state": "completed",
                "acceptedSegmentCount": 0,
                "terminalSegmentCount": 0,
            })

        def close():
            if not event_at_sink.wait(timeout=JOIN_TIMEOUT):
                raise AssertionError("event never reached the sink")
            connection.request_close(1000)

        threads = [
            threading.Thread(target=publish),
            threading.Thread(target=close),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=JOIN_TIMEOUT)
            self.assertFalse(thread.is_alive())

        self.assertTrue(connection.closed)
        self.assertEqual(received, [1])


class EventIdentityRaceTests(unittest.TestCase):
    def test_concurrent_retries_of_one_logical_event_mint_one_identity(self):
        for repetition in range(REPETITIONS):
            with self.subTest(repetition=repetition):
                state = ProtocolSessionState(schema.new_canonical_id())
                projector = EventProjector(state)
                activation = schema.new_canonical_id()
                payload = {
                    "activationId": activation,
                    "reason": "finished",
                    "acceptedSegmentCount": 0,
                }
                context = ProjectionContext(
                    phase=schema.IDLE, activation_id=activation
                )

                workers = 8
                start = threading.Barrier(workers)
                produced = []
                lock = threading.Lock()

                def publish():
                    start.wait(timeout=JOIN_TIMEOUT)
                    events = projector.project(
                        "activation_closed", dict(payload), context
                    )
                    with lock:
                        produced.extend(events)

                threads = [
                    threading.Thread(target=publish) for _ in range(workers)
                ]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=JOIN_TIMEOUT)
                    self.assertFalse(thread.is_alive())

                self.assertEqual(len(produced), workers)
                identifiers = {event["eventId"] for event in produced}
                sequences = {event["eventSeq"] for event in produced}
                versions = {event["stateVersion"] for event in produced}
                self.assertEqual(len(identifiers), 1)
                self.assertEqual(len(sequences), 1)
                self.assertEqual(len(versions), 1)
                self.assertEqual(state.last_event_seq, 1)
                self.assertEqual(state.state_version, 1)

    def test_event_seq_stays_gapless_under_competing_domain_events(self):
        for repetition in range(REPETITIONS):
            with self.subTest(repetition=repetition):
                state = ProtocolSessionState(schema.new_canonical_id())
                workers = 6
                per_worker = 15
                start = threading.Barrier(workers)
                seen = []
                lock = threading.Lock()

                def mint(index):
                    start.wait(timeout=JOIN_TIMEOUT)
                    for step in range(per_worker):
                        event_type = (
                            schema.EVENT_WATCHDOG_WARNING
                            if (index + step) % 3 == 0
                            else schema.EVENT_ACTIVATION_STARTED
                        )
                        envelope = state.mint_event(event_type)
                        with lock:
                            seen.append(
                                (envelope["eventSeq"], envelope["stateVersion"])
                            )

                threads = [
                    threading.Thread(target=mint, args=(index,))
                    for index in range(workers)
                ]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=JOIN_TIMEOUT)
                    self.assertFalse(thread.is_alive())

                total = workers * per_worker
                sequences = sorted(entry[0] for entry in seen)
                self.assertEqual(sequences, list(range(1, total + 1)))
                # stateVersion never runs ahead of the number of events.
                self.assertLessEqual(state.state_version, total)
                by_sequence = dict(seen)
                versions = [by_sequence[key] for key in sorted(by_sequence)]
                self.assertEqual(versions, sorted(versions))


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class ReplayRaceTests(unittest.TestCase):
    def test_concurrent_replays_produce_one_effect_and_one_ack(self):
        for repetition in range(REPETITIONS):
            with self.subTest(repetition=repetition):
                GateAwareRecorder.instances = []
                app = build_app()
                with TestClient(app) as client:
                    with V2Session(client) as session:
                        command_id = str(uuid.uuid4())
                        payload = {
                            "type": schema.ACTIVATION_COMMAND,
                            "protocolVersion": 2,
                            "sessionId": session.session_id,
                            "commandId": command_id,
                            "action": schema.ACTIVATE,
                            "source": schema.MANUAL_SOURCE,
                        }
                        senders = 5
                        start = threading.Barrier(senders)

                        def send():
                            start.wait(timeout=JOIN_TIMEOUT)
                            session.send_raw(dict(payload))

                        threads = [
                            threading.Thread(target=send)
                            for _ in range(senders)
                        ]
                        for thread in threads:
                            thread.start()
                        for thread in threads:
                            thread.join(timeout=JOIN_TIMEOUT)
                            self.assertFalse(thread.is_alive())

                        acks = [
                            session.ack(command_id) for _ in range(senders)
                        ]
                        for ack in acks[1:]:
                            self.assertEqual(ack, acks[0])
                        self.assertEqual(acks[0]["result"], schema.RESULT_APPLIED)

                        snapshot = session.snapshot()
                        started = session.collected(
                            schema.EVENT_ACTIVATION_STARTED
                        )
                        self.assertEqual(len(started), 1)
                        self.assertEqual(
                            snapshot["stateVersion"], acks[0]["stateVersion"]
                        )
                        self.assertEqual(
                            snapshot["input"]["phase"],
                            schema.WAITING_FIRST_SPEECH,
                        )

    def test_competing_finish_and_cancel_close_the_input_exactly_once(self):
        for repetition in range(REPETITIONS):
            with self.subTest(repetition=repetition):
                GateAwareRecorder.instances = []
                app = build_app()
                with TestClient(app) as client:
                    with V2Session(client) as session:
                        _command_id, ack = session.activate()
                        session.event(schema.EVENT_ACTIVATION_STARTED)
                        activation_id = ack["activationId"]

                        start = threading.Barrier(2)
                        ids = {}

                        def control(action):
                            command_id = str(uuid.uuid4())
                            ids[action] = command_id
                            start.wait(timeout=JOIN_TIMEOUT)
                            session.send_raw({
                                "type": schema.ACTIVATION_COMMAND,
                                "protocolVersion": 2,
                                "sessionId": session.session_id,
                                "commandId": command_id,
                                "action": action,
                                "activationId": activation_id,
                            })

                        threads = [
                            threading.Thread(target=control, args=(action,))
                            for action in (schema.FINISH, schema.CANCEL)
                        ]
                        for thread in threads:
                            thread.start()
                        for thread in threads:
                            thread.join(timeout=JOIN_TIMEOUT)
                            self.assertFalse(thread.is_alive())

                        results = {
                            action: session.ack(ids[action])["result"]
                            for action in (schema.FINISH, schema.CANCEL)
                        }
                        # Exactly one of them performs the close. The loser
                        # gets the idempotent ``no_change`` while the close is
                        # still running, or ``not_active`` once the foreground
                        # slot has already been released - both are correct
                        # frozen answers, and neither closes anything again.
                        applied = [
                            action for action, result in results.items()
                            if result == schema.RESULT_APPLIED
                        ]
                        self.assertEqual(len(applied), 1, results)
                        loser = [
                            result for action, result in results.items()
                            if action != applied[0]
                        ][0]
                        self.assertIn(
                            loser,
                            {schema.RESULT_NO_CHANGE, schema.RESULT_NOT_ACTIVE},
                            results,
                        )

                        closed = session.event(
                            schema.EVENT_ACTIVATION_INPUT_CLOSED
                        )
                        session.snapshot()
                        closes = session.collected(
                            schema.EVENT_ACTIVATION_INPUT_CLOSED
                        )
                        self.assertEqual(len(closes), 1)
                        self.assertEqual(
                            closed["causedByCommandId"], ids[applied[0]]
                        )

    def test_snapshot_during_background_drain_stays_consistent(self):
        for repetition in range(REPETITIONS):
            with self.subTest(repetition=repetition):
                GateAwareRecorder.instances = []
                app = build_app()
                with TestClient(app) as client:
                    with V2Session(client) as session:
                        _command_id, ack = session.activate()
                        session.event(schema.EVENT_ACTIVATION_STARTED)
                        session.send_bytes(speech_packet())
                        session.event(schema.EVENT_SEGMENT_RECORDING_STARTED)

                        start = threading.Barrier(2)
                        finish_id = str(uuid.uuid4())

                        def finish():
                            start.wait(timeout=JOIN_TIMEOUT)
                            session.send_raw({
                                "type": schema.ACTIVATION_COMMAND,
                                "protocolVersion": 2,
                                "sessionId": session.session_id,
                                "commandId": finish_id,
                                "action": schema.FINISH,
                                "activationId": ack["activationId"],
                            })

                        def resync():
                            start.wait(timeout=JOIN_TIMEOUT)
                            session.send_raw({
                                "type": schema.SESSION_SNAPSHOT_REQUEST,
                                "protocolVersion": 2,
                                "sessionId": session.session_id,
                                "commandId": str(uuid.uuid4()),
                            })

                        threads = [
                            threading.Thread(target=finish),
                            threading.Thread(target=resync),
                        ]
                        for thread in threads:
                            thread.start()
                        for thread in threads:
                            thread.join(timeout=JOIN_TIMEOUT)
                            self.assertFalse(thread.is_alive())

                        session.ack(finish_id)
                        session.event(schema.EVENT_ACTIVATION_INPUT_CLOSED)
                        final = session.snapshot()

                        # Whatever the interleaving was, the snapshot is
                        # internally consistent and never invents an idle that
                        # loses a pending activation.
                        self.assertIn(
                            final["input"]["phase"], schema.INPUT_PHASES
                        )
                        sequences = [
                            entry["activationSequence"]
                            for entry in final["pendingActivations"]
                        ]
                        self.assertEqual(sequences, sorted(sequences))
                        self.assertGreaterEqual(final["lastEventSeq"], 1)
                        self.assertGreaterEqual(final["stateVersion"], 1)
                        if final["input"]["phase"] == schema.IDLE:
                            self.assertIsNone(final["input"]["activationId"])


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class SessionCloseRaceTests(unittest.TestCase):
    def test_no_v2_mutation_survives_the_session_close(self):
        for repetition in range(REPETITIONS):
            with self.subTest(repetition=repetition):
                GateAwareRecorder.instances = []
                app = build_app()
                service = app.state.voicestt_service
                with TestClient(app) as client:
                    with V2Session(client) as session:
                        session_id = session.session_id
                        _command_id, ack = session.activate()
                        session.event(schema.EVENT_ACTIVATION_STARTED)
                        server_session = session.server_session(app)
                        controller = server_session.activation_controller()
                        token = controller.timer_token()

                    # The connection is gone; the service tears the session
                    # down. A late timer callback must not resurrect anything.
                    service.remove_session(session_id)
                    self.assertIsNone(service.sessions.get(session_id))
                    late = controller.tick(token)
                    self.assertFalse(
                        late.accepted and late.reason == "activated"
                    )
                    self.assertIsNone(service.sessions.get(session_id))
                    del ack


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
