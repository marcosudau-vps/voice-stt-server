"""AP-SRV-050 - protocol-v2 settings wire, revision, event and timer proofs.

The frozen wire contract is exercised end-to-end through ``/ws/v2`` where the
behaviour is transport-level (patch -> ack -> settings.changed -> snapshot),
and at the deterministic controller/timer level where the *real* timer binding
of ``next_activation`` values is proven with exact expected deadlines.
"""

import json
import queue
import threading
import time
import unittest
import uuid

from api_fastapi_server import activation as activation_module
from api_fastapi_server.activation import ActivationController, ActivationTimingPolicy
from api_fastapi_server.protocol_v2 import commands as command_layer
from api_fastapi_server.protocol_v2 import events as event_layer
from api_fastapi_server.protocol_v2 import ports, schema
from api_fastapi_server.protocol_v2.connection import ProtocolV2Connection
from api_fastapi_server.protocol_v2.session import ProtocolSessionState
from api_fastapi_server import settings_control as sc

from tests.unit.test_server_controlled_e2e import (
    AutoScheduler,
    GateAwareRecorder,
    TestClient,
    build_app,
    speech_packet,
)
from tests.unit.test_protocol_v2_e2e import V2Session, hello_message


class FakeWakeRegistry:
    """A minimal in-memory wake catalog for admission-based C2 tests."""

    def resolve_openwakeword(self, model_ids, configured_paths=None,
                             framework="onnx"):
        if model_ids:
            return [
                {"id": identifier, "path": f"/fake/{identifier}"}
                for identifier in model_ids
            ], []
        return [], []

    def openwakeword_models(self, configured_paths=None, framework="onnx"):
        return [{
            "id": "hey_jarvis", "label": "Hey Jarvis",
            "availableFormats": ["onnx"], "default": True,
        }]

    def default_openwakeword(self, configured_paths=None, framework="onnx"):
        return ({"id": "hey_jarvis", "path": "/fake/hey_jarvis"}, [])


def _patch_payload(base, changes):
    return {
        "type": schema.SESSION_SETTINGS_PATCH,
        "baseSettingsRevision": base,
        "changes": changes,
    }


def build_admin_app():
    from api_fastapi_server.server import ServerSettings, create_app

    settings = ServerSettings(
        admin_api_key="test-admin-secret",
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
    )
    return create_app(
        settings,
        scheduler_factory=AutoScheduler,
        recorder_factory=GateAwareRecorder,
    )


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def make_policy(**overrides):
    base = dict(
        initial_speech_timeout=1.5,
        followup_timeout=3.0,
        segment_watchdog_initial=600.0,
        segment_watchdog_refresh=180.0,
        segment_watchdog_warning=30.0,
        closing_recovery_timeout=5.0,
    )
    base.update(overrides)
    return ActivationTimingPolicy(**base)


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class SessionSettingsPatchWireTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def test_single_key_patch_revision_event_state(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                snapshot0 = session.snapshot()
                before_version = snapshot0["stateVersion"]
                before_revision = snapshot0["settingsRevision"]

                sent = session.command(_patch_payload(
                    before_revision,
                    {sc.ACTIVATION_FOLLOWUP: 8000},
                ))
                ack = session.ack(sent["commandId"])
                self.assertTrue(ack["accepted"])
                self.assertEqual(ack["result"], schema.RESULT_APPLIED)
                self.assertEqual(ack["settingsRevision"], before_revision + 1)
                self.assertEqual(ack["stateVersion"], before_version + 1)

                changed = session.event(schema.EVENT_SETTINGS_CHANGED)
                self.assertEqual(changed["settingsRevision"], before_revision + 1)
                self.assertEqual(changed["changedKeys"],
                                 [sc.ACTIVATION_FOLLOWUP])
                self.assertEqual(changed["applyPolicy"], "next_activation")
                self.assertEqual(changed["scope"], "session")

                # exactly one settings.changed for this transaction
                self.assertEqual(
                    len([m for m in session.messages
                         if m.get("type") == schema.EVENT_SETTINGS_CHANGED]),
                    1,
                )

                snapshot = session.snapshot()
                self.assertEqual(snapshot["settingsRevision"], before_revision + 1)
                self.assertEqual(
                    snapshot["effectiveSettings"][sc.ACTIVATION_FOLLOWUP], 8000
                )

    def test_multi_key_same_policy_one_revision_one_event(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                sent = session.command(_patch_payload(0, {
                    sc.ACTIVATION_FOLLOWUP: 8000,
                    sc.ACTIVATION_INITIAL_SPEECH: 22000,
                }))
                ack = session.ack(sent["commandId"])
                self.assertTrue(ack["accepted"])
                self.assertEqual(ack["settingsRevision"], 1)
                changed = session.event(schema.EVENT_SETTINGS_CHANGED)
                # changedKeys are lexicographically sorted per the contract.
                self.assertEqual(changed["changedKeys"], [
                    sc.ACTIVATION_FOLLOWUP,
                    sc.ACTIVATION_INITIAL_SPEECH,
                ])
                self.assertEqual(
                    len([m for m in session.messages
                         if m.get("type") == schema.EVENT_SETTINGS_CHANGED]),
                    1,
                )

    def test_multi_policy_patch_groups_deterministically(self):
        # fail-closed wake selection needs a catalog for the next_session key
        self.app.state.voicestt_service.wakeword_registry = FakeWakeRegistry()
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                snapshot = session.snapshot()
                version0 = snapshot["stateVersion"]
                sent = session.command(_patch_payload(
                    snapshot["settingsRevision"],
                    {
                        sc.ACTIVATION_FOLLOWUP: 8000,               # next_activation
                        sc.WAKE_WORD_SELECTION: ["hey_jarvis"],     # next_session
                    },
                ))
                ack = session.ack(sent["commandId"])
                self.assertTrue(ack["accepted"])
                self.assertEqual(ack["settingsRevision"], 1)
                # stateVersion rises exactly once for the whole transaction.
                self.assertEqual(ack["stateVersion"], version0 + 1)

                events = [m for m in session.messages
                          if m.get("type") == schema.EVENT_SETTINGS_CHANGED]
                self.assertEqual(len(events), 2)
                # deterministic group order: next_activation before next_session
                self.assertEqual(events[0]["applyPolicy"], "next_activation")
                self.assertEqual(events[0]["changedKeys"],
                                 [sc.ACTIVATION_FOLLOWUP])
                self.assertEqual(events[1]["applyPolicy"], "next_session")
                self.assertEqual(events[1]["changedKeys"],
                                 [sc.WAKE_WORD_SELECTION])
                # all events carry the same new revision
                self.assertEqual({ev["settingsRevision"] for ev in events}, {1})
                # exactly one visible change: the second event does not raise
                # the version again.
                self.assertEqual(events[0]["stateVersion"], version0 + 1)
                self.assertEqual(events[1]["stateVersion"], version0 + 1)
                # eventSeq is strictly monotonic within the block
                self.assertEqual(events[0]["eventSeq"] + 1,
                                 events[1]["eventSeq"])

    def test_invalid_field_alongside_valid_field_is_atomic(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                snapshot = session.snapshot()
                sent = session.command(_patch_payload(
                    snapshot["settingsRevision"],
                    {sc.ACTIVATION_FOLLOWUP: 8000,
                     sc.ACTIVATION_WATCHDOG_INITIAL: -5},
                ))
                ack = session.ack(sent["commandId"])
                self.assertFalse(ack["accepted"])
                self.assertEqual(ack["result"], schema.RESULT_SETTINGS_REJECTED)
                self.assertTrue(ack["errors"])
                # no partial write, no events, no revision bump
                self.assertEqual(ack["settingsRevision"],
                                 snapshot["settingsRevision"])
                self.assertEqual(
                    len([m for m in session.messages
                         if m.get("type") == schema.EVENT_SETTINGS_CHANGED]),
                    0,
                )
                after = session.snapshot()
                self.assertEqual(after["settingsRevision"],
                                 snapshot["settingsRevision"])
                self.assertEqual(
                    after["effectiveSettings"][sc.ACTIVATION_FOLLOWUP], 3000
                )

    def test_stale_base_revision_conflicts_without_effect(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                session.command(_patch_payload(0, {sc.ACTIVATION_FOLLOWUP: 8000}))
                session.event(schema.EVENT_SETTINGS_CHANGED)
                sent = session.command(_patch_payload(0, {sc.ACTIVATION_FOLLOWUP: 9000}))
                ack = session.ack(sent["commandId"])
                self.assertEqual(
                    ack["result"], schema.RESULT_SETTINGS_REVISION_CONFLICT
                )
                self.assertFalse(ack["accepted"])
                self.assertEqual(ack["settingsRevision"], 1)
                self.assertEqual(
                    session.snapshot()["effectiveSettings"][
                        sc.ACTIVATION_FOLLOWUP
                    ],
                    8000,
                )

    def test_no_change_does_not_bump_anything(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                before = session.snapshot()
                sent = session.command(_patch_payload(
                    before["settingsRevision"],
                    {sc.ACTIVATION_FOLLOWUP: 3000},
                ))
                ack = session.ack(sent["commandId"])
                self.assertTrue(ack["accepted"])
                self.assertEqual(ack["result"], schema.RESULT_NO_CHANGE)
                self.assertEqual(ack["settingsRevision"],
                                 before["settingsRevision"])
                self.assertEqual(ack["stateVersion"], before["stateVersion"])
                after = session.snapshot()
                self.assertEqual(after["settingsRevision"],
                                 before["settingsRevision"])
                self.assertEqual(after["stateVersion"], before["stateVersion"])
                self.assertEqual(
                    len([m for m in session.messages
                         if m.get("type") == schema.EVENT_SETTINGS_CHANGED]),
                    0,
                )

    def test_replay_returns_identical_ack_without_second_effect(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                sent = session.command(_patch_payload(0, {sc.ACTIVATION_FOLLOWUP: 8000}))
                first = session.ack(sent["commandId"])
                session.event(schema.EVENT_SETTINGS_CHANGED)

                session.send_raw({**sent, "commandId": sent["commandId"]})
                second = session.ack(sent["commandId"])
                self.assertEqual(first, second)
                # no second settings.changed
                self.assertEqual(
                    len([m for m in session.messages
                         if m.get("type") == schema.EVENT_SETTINGS_CHANGED]),
                    1,
                )

    def test_command_id_conflict_has_no_effect(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                command_id = str(uuid.uuid4())
                session.send_raw({
                    "type": schema.SESSION_SETTINGS_PATCH,
                    "protocolVersion": schema.PROTOCOL_VERSION,
                    "sessionId": session.session_id,
                    "commandId": command_id,
                    "baseSettingsRevision": 0,
                    "changes": {sc.ACTIVATION_FOLLOWUP: 8000},
                })
                first = session.ack(command_id)
                session.event(schema.EVENT_SETTINGS_CHANGED)
                session.send_raw({
                    "type": schema.SESSION_SETTINGS_PATCH,
                    "protocolVersion": schema.PROTOCOL_VERSION,
                    "sessionId": session.session_id,
                    "commandId": command_id,
                    "baseSettingsRevision": 0,
                    "changes": {sc.ACTIVATION_INITIAL_SPEECH: 22000},
                })
                conflict = session.ack(command_id)
                self.assertEqual(
                    conflict["result"], schema.RESULT_COMMAND_ID_CONFLICT
                )
                # no second effect
                self.assertEqual(
                    session.snapshot()["effectiveSettings"][
                        sc.ACTIVATION_FOLLOWUP
                    ],
                    8000,
                )

    def test_concurrent_same_base_patches_one_wins_20x(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                server_session = session.server_session(self.app)
                for _ in range(20):
                    barrier = threading.Barrier(2)
                    results = []
                    lock = threading.Lock()
                    base = server_session.settings_state.settings_revision
                    current = server_session.settings_state.effective_values()[
                        sc.ACTIVATION_FOLLOWUP
                    ]

                    def patch_one(value):
                        try:
                            barrier.wait(timeout=10)
                        except threading.BrokenBarrierError:
                            pass
                        result = server_session.apply_settings_patch(
                            base, {sc.ACTIVATION_FOLLOWUP: value}
                        )
                        with lock:
                            results.append(result)

                    # Both candidates differ from the current value, so neither
                    # can collapse into a no_change.
                    value_1, value_2 = current + 1000, current + 2000
                    a = threading.Thread(target=patch_one, args=(value_1,))
                    b = threading.Thread(target=patch_one, args=(value_2,))
                    a.start()
                    b.start()
                    a.join(timeout=15)
                    b.join(timeout=15)
                    self.assertEqual(
                        len([r for r in results
                             if r.result == sc.RESULT_APPLIED]), 1
                    )
                    self.assertEqual(
                        len([r for r in results
                             if r.result == sc.RESULT_REVISION_CONFLICT]),
                        1,
                    )
                    # one revision bump and no lost change
                    self.assertEqual(
                        server_session.settings_state.settings_revision,
                        base + 1,
                    )
                    self.assertIn(
                        server_session.settings_state.effective_values()[
                            sc.ACTIVATION_FOLLOWUP
                        ],
                        (value_1, value_2),
                    )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class SettingsChangedOrderingTests(unittest.TestCase):
    """``settings.changed`` shares the AP-SRV-040 event dispatch linearization."""

    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def test_parallel_domain_and_settings_events_keep_a_gapless_sequence(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                server_session = session.server_session(self.app)
                connection = self._connection_of(server_session, session.session_id)
                self.addCleanup(server_session.service.remove_session,
                                server_session.session_id)
                self.run_scenario(connection, server_session)

    def _connection_of(self, server_session, session_id):
        """Rebuilds the wire layer around the running session."""
        connection = ProtocolV2Connection(server_session.service)
        connection.session = server_session
        connection.hello = None
        connection.state = ProtocolSessionState(
            session_id,
            protocol_version=schema.PROTOCOL_VERSION,
            settings_revision=server_session.settings_state.settings_revision,
        )
        connection.projector = event_layer.EventProjector(connection.state)
        connection.settings_port = ports.SettingsPort(server_session)
        return connection

    def run_scenario(self, connection, server_session):
        for _ in range(20):
            barrier = threading.Barrier(3)
            errors = []

            def settings_thread():
                try:
                    barrier.wait(timeout=10)
                except threading.BrokenBarrierError:
                    pass
                try:
                    for i in range(10):
                        patch = server_session.apply_settings_patch(
                            server_session.settings_state.settings_revision,
                            {sc.ACTIVATION_FOLLOWUP: 3000 + i},
                        )
                        connection._bind_settings_patch(patch)
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

            def domain_thread():
                try:
                    barrier.wait(timeout=10)
                except threading.BrokenBarrierError:
                    pass
                try:
                    controller = server_session.activation_controller()
                    for i in range(10):
                        if controller is not None and controller.snapshot()["phase"] == activation_module.IDLE:
                            controller.activate(activation_module.MANUAL_SOURCE, {})
                        legacy = self._domain_event(i)
                        connection._on_domain_event(legacy[0], legacy[1])
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

            def release():
                try:
                    barrier.wait(timeout=10)
                except threading.BrokenBarrierError:
                    pass

            starter = threading.Thread(target=release)
            threads = [
                threading.Thread(target=settings_thread),
                threading.Thread(target=domain_thread),
            ]
            for thread in threads:
                thread.start()
            starter.start()
            for thread in threads + [starter]:
                thread.join(timeout=30)
            self.assertEqual(errors, [])

            payloads = connection.drain()
            events = [m for m in payloads
                      if m.get("type") in schema.EVENT_TYPES]
            self.assertTrue(events, "no events were dispatched")
            sequences = [event["eventSeq"] for event in events]
            identifiers = [event["eventId"] for event in events]
            # strictly monotonic, gapless and unique within the block
            self.assertEqual(
                sequences,
                list(range(sequences[0], sequences[0] + len(sequences))),
            )
            self.assertEqual(len(set(identifiers)), len(identifiers))

    @staticmethod
    def _domain_event(i):
        activation_id = f"activation-{i}"
        return ("activation_started", {
            "activationId": activation_id,
            "activationSequence": i + 1,
            "primarySource": "manual",
            "timestamp": time.time(),
        })


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class NextActivationTimerBindingTests(unittest.TestCase):
    """The hard root gate: ``next_activation`` must retime the next activation."""

    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    # -- controller-level exact proof for all six timings ---------------------

    def test_all_six_timings_latch_the_new_value_real(self):
        low = make_policy(
            initial_speech_timeout=1.5, followup_timeout=3.0,
            segment_watchdog_initial=600.0, segment_watchdog_refresh=180.0,
            segment_watchdog_warning=30.0, closing_recovery_timeout=5.0,
        )
        high = make_policy(
            initial_speech_timeout=4.0, followup_timeout=8.0,
            segment_watchdog_initial=900.0, segment_watchdog_refresh=240.0,
            segment_watchdog_warning=45.0, closing_recovery_timeout=9.0,
        )

        def new_controller(now):
            clock = FakeClock()
            clock.t = now
            return clock, ActivationController(
                manual_trigger_enabled=True,
                wake_word_trigger_enabled=False,
                clock=clock,
                id_factory=lambda: uuid.uuid4().hex,
            )

        # --- initial speech ---------------------------------------------
        clock, controller = new_controller(10.0)
        opened = controller.activate("manual", {}, timing_policy=low)
        self.assertTrue(opened.accepted)
        self.assertEqual(opened.snapshot["deadline"], 10.0 + 1.5)
        controller.reset()
        opened = controller.activate("manual", {}, timing_policy=high)
        self.assertEqual(opened.snapshot["deadline"], 10.0 + 4.0)

        # --- followup (regular segment end) -----------------------------
        clock, controller = new_controller(20.0)
        controller.activate("manual", {}, timing_policy=low)
        controller.recording_started()
        controller.recording_ended()
        self.assertEqual(controller.snapshot()["deadline"], 20.0 + 3.0)
        controller.reset()
        controller.activate("manual", {}, timing_policy=high)
        controller.recording_started()
        controller.recording_ended()
        self.assertEqual(controller.snapshot()["deadline"], 20.0 + 8.0)

        # --- segment watchdog initial + its warning ---------------------
        clock, controller = new_controller(30.0)
        controller.activate("manual", {}, timing_policy=low)
        controller.recording_started()
        self.assertEqual(controller.snapshot()["deadline"], 30.0 + 600.0)
        self.assertEqual(controller.snapshot()["warningDeadline"],
                         30.0 + 600.0 - 30.0)
        controller.reset()
        controller.activate("manual", {}, timing_policy=high)
        controller.recording_started()
        self.assertEqual(controller.snapshot()["deadline"], 30.0 + 900.0)
        self.assertEqual(controller.snapshot()["warningDeadline"],
                         30.0 + 900.0 - 45.0)

        # --- segment watchdog refresh -----------------------------------
        # The refresh deadline is ``max(current, now + refresh)``, so the
        # refresh value only becomes observable when the initial watchdog is
        # shorter than the refresh window.
        low_refresh = make_policy(
            segment_watchdog_initial=100.0, segment_watchdog_refresh=180.0,
            segment_watchdog_warning=30.0,
        )
        high_refresh = make_policy(
            segment_watchdog_initial=200.0, segment_watchdog_refresh=240.0,
            segment_watchdog_warning=45.0,
        )
        clock, controller = new_controller(40.0)
        controller.activate("manual", {}, timing_policy=low_refresh)
        controller.recording_started()
        self.assertEqual(controller.snapshot()["deadline"], 40.0 + 100.0)
        clock.t = 50.0
        refreshed = controller.refresh(
            activation_id=controller.snapshot()["activationId"]
        )
        self.assertTrue(refreshed.accepted)
        self.assertEqual(controller.snapshot()["deadline"], 50.0 + 180.0)
        controller.reset()
        controller.activate("manual", {}, timing_policy=high_refresh)
        controller.recording_started()
        clock.t = 50.0
        controller.refresh(activation_id=controller.snapshot()["activationId"])
        self.assertEqual(controller.snapshot()["deadline"], 50.0 + 240.0)

        # --- closing recovery ------------------------------------------
        clock, controller = new_controller(70.0)
        controller.activate("manual", {}, timing_policy=low)
        closed = controller.finish(
            activation_id=controller.snapshot()["activationId"]
        )
        self.assertTrue(closed.accepted)
        self.assertEqual(controller.snapshot()["deadline"], 70.0 + 5.0)
        controller.reset()
        controller.activate("manual", {}, timing_policy=high)
        closed = controller.finish(
            activation_id=controller.snapshot()["activationId"]
        )
        self.assertEqual(controller.snapshot()["deadline"], 70.0 + 9.0)

    # -- the §28 follow-up wire example with real timers ----------------------

    def _to_followup(self, session, server_session):
        """Drives the open activation into ``followup_wait``."""
        session.send_bytes(speech_packet())
        session.event(schema.EVENT_SEGMENT_RECORDING_STARTED)
        session.recorder().flush_buffered_audio()
        session.event(schema.EVENT_SEGMENT_RECORDING_ENDED)
        controller = server_session.activation_controller()
        snap = controller.snapshot()
        self.assertEqual(snap["phase"], activation_module.FOLLOWUP_WAIT)
        return controller, snap

    def test_followup_patch_leaves_current_activation_then_retimes_next(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                server_session = session.server_session(self.app)

                # Activation A with the default 3000 ms follow-up.
                _command_id, ack_a = session.activate()
                started_a = session.event(schema.EVENT_ACTIVATION_STARTED)
                self.assertEqual(
                    started_a["effectiveSettings"][sc.ACTIVATION_FOLLOWUP], 3000
                )
                controller, snap_a = self._to_followup(session, server_session)
                deadline_a = snap_a["deadline"]
                self.assertEqual(snap_a["deadlineKind"], "followup")
                self.assertAlmostEqual(
                    deadline_a - time.monotonic(), 3.0, delta=0.9
                )

                # Patch while A is open -> 8000 ms.
                sent = session.command(_patch_payload(
                    server_session.settings_state.settings_revision,
                    {sc.ACTIVATION_FOLLOWUP: 8000},
                ))
                ack = session.ack(sent["commandId"])
                self.assertTrue(ack["accepted"])
                self.assertEqual(ack["result"], schema.RESULT_APPLIED)
                self.assertEqual(
                    ack["settingsRevision"],
                    server_session.settings_state.settings_revision,
                )
                session.event(schema.EVENT_SETTINGS_CHANGED)

                # The running activation keeps its latch and its real timer.
                snap_a_after = server_session.activation_controller().snapshot()
                self.assertEqual(snap_a_after["deadline"], deadline_a)
                self.assertEqual(
                    server_session.settings_effective_for_wire()[
                        sc.ACTIVATION_FOLLOWUP
                    ],
                    3000,
                )

                # Close A safely, then start B.
                finish = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": schema.FINISH,
                    "activationId": ack_a["activationId"],
                })
                session.ack(finish["commandId"])
                session.event(schema.EVENT_ACTIVATION_INPUT_CLOSED)

                _command_id, ack_b = session.activate()
                started_b = session.event(schema.EVENT_ACTIVATION_STARTED)
                self.assertEqual(
                    started_b["effectiveSettings"][sc.ACTIVATION_FOLLOWUP], 8000
                )
                _controller, snap_b = self._to_followup(session, server_session)
                self.assertEqual(snap_b["deadlineKind"], "followup")
                # B's follow-up deadline is really built with 8.0 s.
                self.assertAlmostEqual(
                    snap_b["deadline"] - time.monotonic(), 8.0, delta=0.9
                )
                self.assertEqual(
                    server_session.settings_effective_for_wire()[
                        sc.ACTIVATION_FOLLOWUP
                    ],
                    8000,
                )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class SessionSnapshotConsistencyTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def test_every_revision_projection_matches_after_a_patch(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                server_session = session.server_session(self.app)
                sent = session.command(_patch_payload(0, {sc.ACTIVATION_FOLLOWUP: 8000}))
                ack = session.ack(sent["commandId"])
                changed = session.event(schema.EVENT_SETTINGS_CHANGED)
                snapshot = session.snapshot()

                port_revision = ports.SettingsPort(server_session).revision
                values = (
                    ack["settingsRevision"],
                    changed["settingsRevision"],
                    snapshot["settingsRevision"],
                    server_session.settings_state.settings_revision,
                    port_revision,
                )
                self.assertEqual(len(set(values)), 1, values)
                # wire flat effectiveSettings equals the control-plane view
                self.assertEqual(
                    snapshot["effectiveSettings"][sc.ACTIVATION_FOLLOWUP], 8000
                )
                self.assertEqual(
                    server_session.settings_effective_for_wire()[
                        sc.ACTIVATION_FOLLOWUP
                    ],
                    8000,
                )
                self.assertEqual(
                    server_session.settings_state.effective_values()[
                        sc.ACTIVATION_FOLLOWUP
                    ],
                    8000,
                )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class RestSettingsV2Tests(unittest.TestCase):
    """``/api/v2/settings`` REST surface, auth guard reuse and secrets."""

    SECRET_VALUES = ("test-admin-secret",)
    SECRET_FIELDS = ("admin_api_key", "openai_api_key", "apiKey", "x-admin-key")

    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_admin_app()

    def assert_no_secrets(self, *payloads):
        for payload in payloads:
            text = str(payload)
            for secret in self.SECRET_VALUES:
                self.assertNotIn(secret, text, payload)
            for field in self.SECRET_FIELDS:
                self.assertNotIn(field + '":', text, payload)

    def test_public_reads_need_no_key(self):
        with TestClient(self.app) as client:
            schema_r = client.get("/api/v2/settings/schema")
            self.assertEqual(schema_r.status_code, 200)
            self.assertEqual(schema_r.json()["secretsExposed"], False)
            server_r = client.get("/api/v2/settings/server")
            self.assertEqual(server_r.status_code, 200)
            self.assert_no_secrets(schema_r.text, server_r.text)
        # The existing wake endpoint remains functional; it is admin-guarded
        # and belongs to the wake catalog domain (AP-SRV-060), not to this AP.
        with TestClient(self.app) as client:
            wake_r = client.get(
                "/api/wake-word",
                headers={"x-admin-key": "test-admin-secret"},
            )
            self.assertEqual(wake_r.status_code, 200)
            self.assert_no_secrets(wake_r.text)

    def test_schema_is_deterministic_and_complete(self):
        with TestClient(self.app) as client:
            payload = client.get("/api/v2/settings/schema").json()
            settings = payload["settings"]
            keys = [entry["key"] for entry in settings]
            self.assertEqual(keys, sorted(keys))
            required = (
                "key", "scope", "auth", "type", "constraints",
                "defaultValue", "applyPolicy",
            )
            for entry in settings:
                for field in required:
                    self.assertIn(field, entry)
            self.assertEqual(
                set(keys),
                {"activation.initialSpeechTimeoutMs",
                 "activation.followupTimeoutMs",
                 "activation.segmentWatchdogInitialMs",
                 "activation.segmentWatchdogRefreshMs",
                 "activation.segmentWatchdogWarningMs",
                 "activation.closingRecoveryTimeoutMs",
                 "wakeWord.sensitivity",
                 "wakeWord.selection",
                 "wakeWord.globalDisabledIds",
                 # AP-SRV-060 calibration keys.
                 "wakeWord.cooldownMs",
                 "wakeWord.preRollMs",
                 # AP-SRV-060 C3 detection, gain, VAD and backend keys.
                 "wakeWord.minConsecutivePredictionFrames",
                 "wakeWord.detectorGain",
                 "wakeWord.noiseSuppressionEnabled",
                 "wakeWord.vadThreshold",
                 "wakeWord.inferenceBackend",
                 "runtimeSuppression.manual",
                 "runtimeSuppression.wakeWord"},
            )

    def test_server_read_exposes_requested_effective_and_revision(self):
        with TestClient(self.app) as client:
            payload = client.get("/api/v2/settings/server").json()
            self.assertEqual(payload["settingsRevision"], 0)
            entries = {entry["key"]: entry for entry in payload["settings"]}
            self.assertIn("requestedValue", entries[sc.ACTIVATION_FOLLOWUP])
            self.assertIn("effectiveValue", entries[sc.ACTIVATION_FOLLOWUP])
            # session-only keys are absent from the server surface
            self.assertNotIn(sc.WAKE_WORD_SELECTION, entries)
            self.assert_no_secrets(payload)

    def test_patch_without_key_is_refused(self):
        with TestClient(self.app) as client:
            response = client.patch("/api/v2/settings/server", json={
                "baseSettingsRevision": 0,
                "changes": {sc.ACTIVATION_FOLLOWUP: 8000},
            })
            self.assertEqual(response.status_code, 401)

    def test_patch_with_wrong_key_is_refused(self):
        with TestClient(self.app) as client:
            response = client.patch(
                "/api/v2/settings/server",
                json={"baseSettingsRevision": 0,
                      "changes": {sc.ACTIVATION_FOLLOWUP: 8000}},
                headers={"x-voicestt-admin-key": "wrong-key"},
            )
            self.assertEqual(response.status_code, 401)

    def test_patch_with_existing_admin_header_path_is_accepted(self):
        with TestClient(self.app) as client:
            response = client.patch(
                "/api/v2/settings/server",
                json={"baseSettingsRevision": 0,
                      "changes": {sc.ACTIVATION_FOLLOWUP: 8000}},
                headers={"x-voicestt-admin-key": "test-admin-secret"},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["accepted"])
            self.assertEqual(payload["settingsRevision"], 1)
            self.assert_no_secrets(payload)

    def test_patch_with_x_admin_key_alias_is_accepted(self):
        with TestClient(self.app) as client:
            response = client.patch(
                "/api/v2/settings/server",
                json={"baseSettingsRevision": 0,
                      "changes": {sc.ACTIVATION_FOLLOWUP: 8000}},
                headers={"x-admin-key": "test-admin-secret"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["accepted"])

    def test_patch_with_bearer_authorization_path_is_accepted(self):
        with TestClient(self.app) as client:
            response = client.patch(
                "/api/v2/settings/server",
                json={"baseSettingsRevision": 0,
                      "changes": {sc.ACTIVATION_FOLLOWUP: 8000}},
                headers={"authorization": "Bearer test-admin-secret"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["accepted"])

    def test_stale_server_revision_conflicts_409(self):
        with TestClient(self.app) as client:
            response = client.patch(
                "/api/v2/settings/server",
                json={"baseSettingsRevision": 5,
                      "changes": {sc.ACTIVATION_FOLLOWUP: 8000}},
                headers={"x-admin-key": "test-admin-secret"},
            )
            self.assertEqual(response.status_code, 409)
            payload = response.json()
            self.assertEqual(payload["result"],
                             schema.RESULT_SETTINGS_REVISION_CONFLICT)
            self.assert_no_secrets(payload)

    def test_invalid_value_is_atomically_rejected(self):
        with TestClient(self.app) as client:
            response = client.patch(
                "/api/v2/settings/server",
                json={"baseSettingsRevision": 0,
                      "changes": {sc.ACTIVATION_FOLLOWUP: -1}},
                headers={"x-admin-key": "test-admin-secret"},
            )
            self.assertEqual(response.status_code, 422)
            payload = response.json()
            self.assertEqual(payload["result"], schema.RESULT_SETTINGS_REJECTED)
            self.assertTrue(payload["errors"])
            # the server surface is unchanged
            server = client.get("/api/v2/settings/server").json()
            self.assertEqual(server["settingsRevision"], 0)
            self.assert_no_secrets(payload)

    def test_session_scope_key_over_server_patch_is_rejected(self):
        with TestClient(self.app) as client:
            response = client.patch(
                "/api/v2/settings/server",
                json={"baseSettingsRevision": 0,
                      "changes": {sc.WAKE_WORD_SELECTION: ["x"]}},
                headers={"x-admin-key": "test-admin-secret"},
            )
            self.assertEqual(response.status_code, 422)
            codes = {entry["code"] for entry in response.json()["errors"]}
            self.assertIn(sc.CODE_WRONG_SCOPE, codes)

    def test_server_patch_is_persisted_and_loaded(self):
        with TestClient(self.app) as client:
            client.patch(
                "/api/v2/settings/server",
                json={"baseSettingsRevision": 0,
                      "changes": {sc.ACTIVATION_FOLLOWUP: 8000}},
                headers={"x-admin-key": "test-admin-secret"},
            )
            server = client.get("/api/v2/settings/server").json()
            entry = {e["key"]: e for e in server["settings"]}[
                sc.ACTIVATION_FOLLOWUP
            ]
            self.assertEqual(entry["requestedValue"], 8000)
            self.assertEqual(entry["effectiveValue"], 8000)
            service = self.app.state.voicestt_service
            # the in-memory server control reflects the confirmed patch; the
            # atomic disk persistence is proven in test_settings_runtime_persistence.
            self.assertEqual(service.settings_control.settings_revision, 1)
            self.assertEqual(
                service.settings_control.server_effective()[
                    sc.ACTIVATION_FOLLOWUP
                ],
                8000,
            )
            self.assert_no_secrets(server)


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class AtomicAdmissionTests(unittest.TestCase):
    """F3 - one atomic settings/timing bundle per activation admission."""

    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def _to_followup(self, session, server_session):
        session.send_bytes(speech_packet())
        session.event(schema.EVENT_SEGMENT_RECORDING_STARTED)
        session.recorder().flush_buffered_audio()
        session.event(schema.EVENT_SEGMENT_RECORDING_ENDED)
        snap = server_session.activation_controller().snapshot()
        self.assertEqual(snap["phase"], activation_module.FOLLOWUP_WAIT)
        return snap

    def test_admission_inputs_use_only_the_atomic_bundle_seam(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                server_session = session.server_session(self.app)
                state = server_session.settings_state

                def boom(*args, **kwargs):
                    raise AssertionError("a second settings read was used")

                state.activation_timings_seconds = boom
                server_session.settings_effective_for_wire = boom

                def stub_bundle():
                    return sc.ActivationAdmissionSettings(
                        settings_revision=1,
                        effective_settings={
                            sc.ACTIVATION_FOLLOWUP: 4000,
                            sc.ACTIVATION_INITIAL_SPEECH: 15000,
                            "wakeWord.selection": [],
                            "wakeWord.sensitivity": 0.5,
                            "runtimeSuppression.manual": False,
                            "runtimeSuppression.wakeWord": False,
                        },
                        timing_seconds={
                            sc.ACTIVATION_FOLLOWUP: 4.0,
                            sc.ACTIVATION_INITIAL_SPEECH: 15.0,
                        },
                    )

                state.activation_admission_settings = stub_bundle
                wire_settings, policy = server_session._new_activation_inputs()
                self.assertEqual(
                    wire_settings[sc.ACTIVATION_FOLLOWUP], 4000
                )
                self.assertEqual(policy.followup_timeout, 4.0)
                self.assertEqual(policy.initial_speech_timeout, 15.0)

    def test_manual_admission_effective_timing_and_real_deadline_are_same_revision(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                server_session = session.server_session(self.app)
                sent = session.command(_patch_payload(
                    0, {sc.ACTIVATION_FOLLOWUP: 4000}
                ))
                ack = session.ack(sent["commandId"])
                self.assertTrue(ack["accepted"])
                session.event(schema.EVENT_SETTINGS_CHANGED)

                _command_id, ack_a = session.activate()
                started = session.event(schema.EVENT_ACTIVATION_STARTED)
                # the wire effective settings of the admission
                self.assertEqual(
                    started["effectiveSettings"][sc.ACTIVATION_FOLLOWUP], 4000
                )
                snap = self._to_followup(session, server_session)
                # the real follow-up deadline was built from the SAME value
                self.assertEqual(snap["deadlineKind"], "followup")
                self.assertAlmostEqual(
                    snap["deadline"] - time.monotonic(), 4.0, delta=0.9
                )

    def test_wake_admission_effective_timing_and_real_deadline_are_same_revision(self):
        app = build_app()
        GateAwareRecorder.instances = []
        service = app.state.voicestt_service
        service.wakeword_registry = FakeWakeRegistry()
        with TestClient(app) as client:
            with V2Session(
                client,
                hello=hello_message(
                    manual=True, wake_word=True,
                    wake_word_ids=("hey_jarvis",),
                ),
            ) as session:
                server_session = session.server_session(app)
                sent = session.command(_patch_payload(
                    0, {sc.ACTIVATION_FOLLOWUP: 4000}
                ))
                session.ack(sent["commandId"])
                session.event(schema.EVENT_SETTINGS_CHANGED)

                session.recorder().simulate_wake_word()
                started = session.event(schema.EVENT_ACTIVATION_STARTED)
                self.assertEqual(started["primarySource"], "wake_word")
                self.assertEqual(
                    started["effectiveSettings"][sc.ACTIVATION_FOLLOWUP], 4000
                )
                snap = self._to_followup(session, server_session)
                self.assertEqual(snap["deadlineKind"], "followup")
                self.assertAlmostEqual(
                    snap["deadline"] - time.monotonic(), 4.0, delta=0.9
                )

    def test_patch_between_admissions_changes_only_the_next_bundle(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                server_session = session.server_session(self.app)
                _cid, ack_a = session.activate()
                started_a = session.event(schema.EVENT_ACTIVATION_STARTED)
                self.assertEqual(
                    started_a["effectiveSettings"][sc.ACTIVATION_FOLLOWUP],
                    3000,
                )
                # A's armed timer, captured before the patch
                deadline_a = server_session.activation_controller().snapshot()[
                    "deadline"
                ]

                # patch while A is open
                sent = session.command(_patch_payload(
                    0, {sc.ACTIVATION_FOLLOWUP: 8000}
                ))
                session.ack(sent["commandId"])
                session.event(schema.EVENT_SETTINGS_CHANGED)

                # A itself keeps its latched value AND its real timer unchanged
                self.assertEqual(
                    server_session.settings_effective_for_wire()[
                        sc.ACTIVATION_FOLLOWUP
                    ],
                    3000,
                )
                self.assertEqual(
                    server_session.activation_controller().snapshot()["deadline"],
                    deadline_a,
                )

                finish = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": schema.FINISH,
                    "activationId": ack_a["activationId"],
                })
                session.ack(finish["commandId"])
                session.event(schema.EVENT_ACTIVATION_INPUT_CLOSED)

                _cid, ack_b = session.activate()
                started_b = session.event(schema.EVENT_ACTIVATION_STARTED)
                self.assertEqual(
                    started_b["effectiveSettings"][sc.ACTIVATION_FOLLOWUP],
                    8000,
                )
                # B latches the new timing really
                self._to_followup(session, server_session)
                snap_b = server_session.activation_controller().snapshot()
                self.assertEqual(snap_b["deadlineKind"], "followup")
                self.assertAlmostEqual(
                    snap_b["deadline"] - time.monotonic(), 8.0, delta=0.9
                )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class RequestedSettingsWireTests(unittest.TestCase):
    """F6 - session.snapshot exposes requested/effective differences additively."""

    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def test_snapshot_exposes_requested_settings(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                snapshot = session.snapshot()
                self.assertIn("requestedSettings", snapshot)
                self.assertIn("effectiveSettings", snapshot)
                self.assertEqual(
                    set(snapshot["requestedSettings"]),
                    set(snapshot["effectiveSettings"]),
                )

    def test_initial_requested_and_effective_settings_match(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                snapshot = session.snapshot()
                requested = snapshot["requestedSettings"]
                effective = snapshot["effectiveSettings"]
                for key in (sc.ACTIVATION_FOLLOWUP,
                            sc.ACTIVATION_WATCHDOG_INITIAL,
                            sc.WAKE_WORD_SELECTION):
                    self.assertEqual(requested[key], effective[key])

    def test_next_activation_patch_during_open_activation_shows_requested_new_effective_old(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                _cid, _ack = session.activate()
                session.event(schema.EVENT_ACTIVATION_STARTED)
                sent = session.command(_patch_payload(
                    0, {sc.ACTIVATION_FOLLOWUP: 8000}
                ))
                session.ack(sent["commandId"])
                session.event(schema.EVENT_SETTINGS_CHANGED)
                snapshot = session.snapshot()
                self.assertEqual(
                    snapshot["requestedSettings"][sc.ACTIVATION_FOLLOWUP], 8000
                )
                self.assertEqual(
                    snapshot["effectiveSettings"][sc.ACTIVATION_FOLLOWUP], 3000
                )

    def test_next_activation_after_close_uses_new_requested_and_effective(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                sent = session.command(_patch_payload(
                    0, {sc.ACTIVATION_FOLLOWUP: 8000}
                ))
                session.ack(sent["commandId"])
                session.event(schema.EVENT_SETTINGS_CHANGED)
                snapshot = session.snapshot()
                self.assertEqual(
                    snapshot["requestedSettings"][sc.ACTIVATION_FOLLOWUP], 8000
                )
                self.assertEqual(
                    snapshot["effectiveSettings"][sc.ACTIVATION_FOLLOWUP], 8000
                )

    def test_next_session_patch_shows_requested_new_effective_current_session_value(self):
        self.app.state.voicestt_service.wakeword_registry = FakeWakeRegistry()
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                sent = session.command(_patch_payload(
                    0, {sc.WAKE_WORD_SELECTION: ["hey_jarvis"]}
                ))
                ack = session.ack(sent["commandId"])
                self.assertTrue(ack["accepted"])
                session.event(schema.EVENT_SETTINGS_CHANGED)
                snapshot = session.snapshot()
                self.assertEqual(
                    snapshot["requestedSettings"][sc.WAKE_WORD_SELECTION],
                    ["hey_jarvis"],
                )
                # effectiveValue stays the current session selection
                self.assertEqual(
                    snapshot["effectiveSettings"][sc.WAKE_WORD_SELECTION], []
                )

    def test_snapshot_request_resync_preserves_requested_effective_difference(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                _cid, _ack = session.activate()
                session.event(schema.EVENT_ACTIVATION_STARTED)
                sent = session.command(_patch_payload(
                    0, {sc.ACTIVATION_FOLLOWUP: 8000}
                ))
                session.ack(sent["commandId"])
                session.event(schema.EVENT_SETTINGS_CHANGED)
                first = session.snapshot()
                second = session.snapshot()
                self.assertEqual(
                    first["requestedSettings"], second["requestedSettings"]
                )
                self.assertEqual(
                    first["effectiveSettings"], second["effectiveSettings"]
                )
                self.assertEqual(
                    first["requestedSettings"][sc.ACTIVATION_FOLLOWUP], 8000
                )
                self.assertEqual(
                    first["effectiveSettings"][sc.ACTIVATION_FOLLOWUP], 3000
                )

    def test_runtime_suppression_requested_and_effective_follow_live_authority(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                sent = session.command({
                    "type": schema.TRIGGER_SUPPRESSION_SET,
                    "manual": True,
                    "wakeWord": False,
                })
                session.ack(sent["commandId"])
                snapshot = session.snapshot()
                self.assertTrue(
                    snapshot["requestedSettings"][
                        sc.RUNTIME_SUPPRESSION_MANUAL
                    ]
                )
                self.assertTrue(
                    snapshot["effectiveSettings"][
                        sc.RUNTIME_SUPPRESSION_MANUAL
                    ]
                )
                self.assertFalse(
                    snapshot["requestedSettings"][
                        sc.RUNTIME_SUPPRESSION_WAKE_WORD
                    ]
                )

    def test_requested_settings_read_does_not_bump_state_or_settings_revision(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                first = session.snapshot()
                second = session.snapshot()
                third = session.snapshot()
                self.assertEqual(first["stateVersion"],
                                 second["stateVersion"])
                self.assertEqual(second["stateVersion"],
                                 third["stateVersion"])
                self.assertEqual(first["settingsRevision"],
                                 second["settingsRevision"])


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class PersistenceFailureRestTests(unittest.TestCase):
    """F5 - persistent server patch failure surfaces as a clean 500."""

    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_admin_app()

    def test_rest_server_patch_persistence_failure_returns_500_internal_error(self):
        service = self.app.state.voicestt_service

        def boom(overlay, revision):
            raise OSError("disk full")

        service.config_store.save_settings_control = boom
        with TestClient(self.app) as client:
            response = client.patch(
                "/api/v2/settings/server",
                json={"baseSettingsRevision": 0,
                      "changes": {sc.ACTIVATION_FOLLOWUP: 8000}},
                headers={"x-admin-key": "test-admin-secret"},
            )
            self.assertEqual(response.status_code, 500)
            payload = response.json()
            self.assertEqual(payload["result"], "internal_error")
            self.assertFalse(payload["accepted"])
            codes = {entry["code"] for entry in payload["errors"]}
            self.assertIn("persistence_failed", codes)
            # machine readable, non-secret, no exception details
            self.assertNotIn("disk full", response.text)
            self.assertNotIn("test-admin-secret", response.text)

    def test_rest_persistence_failure_does_not_advance_settings_revision(self):
        service = self.app.state.voicestt_service

        def boom(overlay, revision):
            raise OSError("disk full")

        service.config_store.save_settings_control = boom
        with TestClient(self.app) as client:
            client.patch(
                "/api/v2/settings/server",
                json={"baseSettingsRevision": 0,
                      "changes": {sc.ACTIVATION_FOLLOWUP: 8000}},
                headers={"x-admin-key": "test-admin-secret"},
            )
            server = client.get("/api/v2/settings/server")
            self.assertEqual(server.json()["settingsRevision"], 0)


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class WireLinearizationTests(unittest.TestCase):
    """AP-SRV-050 C3 - wire atomicity on the shared ``_event_dispatch_lock``.

    Test A  - a ``session.snapshot`` must never observe the window between a
              settings domain commit (session state N+1) and the wire mirror /
              ``settings.changed`` (still N).
    Test B  - ``settings.changed`` for N+1 must precede every domain event that
              already uses settings N+1; eventSeq stays strictly monotonic,
              gapless and duplicate-free.

    Both open the window deterministically via a controlled mirror seam
    (an ``Event`` pausing ``ProtocolSessionState.set_settings_revision``) -
    no ``sleep()`` anywhere.
    """

    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def _rebuilt_connection(self, server_session, session_id):
        connection = ProtocolV2Connection(server_session.service)
        connection.session = server_session
        connection.hello = None
        connection.state = ProtocolSessionState(
            session_id,
            protocol_version=schema.PROTOCOL_VERSION,
            settings_revision=server_session.settings_state.settings_revision,
        )
        connection.projector = event_layer.EventProjector(connection.state)
        connection.settings_port = ports.SettingsPort(server_session)
        return connection

    @staticmethod
    def _patch_parsed(base, changes):
        return command_layer.ParsedCommand(
            type=schema.SESSION_SETTINGS_PATCH,
            command_id=schema.new_canonical_id(),
            payload_key=("raw",),
            payload={"baseSettingsRevision": base, "changes": changes},
        )

    def _pause_mirror(self, connection):
        mirrored = threading.Event()
        release = threading.Event()
        original = connection.state.set_settings_revision

        def blocking_mirror(revision):
            mirrored.set()
            release.wait(timeout=10)
            return original(revision)

        connection.state.set_settings_revision = blocking_mirror
        return mirrored, release

    def test_snapshot_never_observes_the_mutation_mirror_gap(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                server_session = session.server_session(self.app)
                connection = self._rebuilt_connection(
                    server_session, session.session_id
                )
                self.addCleanup(server_session.service.remove_session,
                                server_session.session_id)
                mirrored, release = self._pause_mirror(connection)
                errors = []

                def patcher():
                    try:
                        connection._apply_settings_patch(
                            self._patch_parsed(
                                0, {sc.ACTIVATION_FOLLOWUP: 8000}
                            )
                        )
                    except Exception as exc:  # noqa: BLE001
                        errors.append(exc)

                patcher_thread = threading.Thread(target=patcher)
                patcher_thread.start()
                self.assertTrue(mirrored.wait(timeout=10),
                                "wire mirror was not paused")

                box = {}
                launched = threading.Event()

                def snapshotter():
                    launched.set()
                    box["payload"] = connection._snapshot_payload()

                snap_thread = threading.Thread(target=snapshotter)
                snap_thread.start()
                self.assertTrue(launched.wait(timeout=10))
                release.set()
                patcher_thread.join(timeout=15)
                snap_thread.join(timeout=15)
                self.assertEqual(errors, [])
                snapshot = box["payload"]
                # never a revision-mixed snapshot
                self.assertEqual(snapshot["settingsRevision"], 1)
                self.assertEqual(
                    snapshot["requestedSettings"][sc.ACTIVATION_FOLLOWUP], 8000
                )
                self.assertEqual(
                    snapshot["effectiveSettings"][sc.ACTIVATION_FOLLOWUP], 8000
                )

    def test_settings_changed_precedes_domain_events_that_use_new_settings(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                server_session = session.server_session(self.app)
                connection = self._rebuilt_connection(
                    server_session, session.session_id
                )
                self.addCleanup(server_session.service.remove_session,
                                server_session.session_id)
                mirrored, release = self._pause_mirror(connection)
                errors = []

                def patcher():
                    try:
                        connection._apply_settings_patch(
                            self._patch_parsed(
                                0, {sc.ACTIVATION_FOLLOWUP: 8000}
                            )
                        )
                    except Exception as exc:  # noqa: BLE001
                        errors.append(exc)

                patcher_thread = threading.Thread(target=patcher)
                patcher_thread.start()
                self.assertTrue(mirrored.wait(timeout=10),
                                "wire mirror was not paused")

                launched = threading.Event()

                def domainer():
                    launched.set()
                    connection._on_domain_event(
                        "activation_started",
                        {
                            "activationId": "act-1",
                            "activationSequence": 1,
                            "primarySource": "manual",
                            "timestamp": time.time(),
                        },
                    )

                domain_thread = threading.Thread(target=domainer)
                domain_thread.start()
                self.assertTrue(launched.wait(timeout=10))
                release.set()
                patcher_thread.join(timeout=15)
                domain_thread.join(timeout=15)
                self.assertEqual(errors, [])

                events = [m for m in connection.drain()
                          if m.get("type") in schema.EVENT_TYPES]
                changed = [e for e in events
                           if e.get("type") == schema.EVENT_SETTINGS_CHANGED]
                domain = [e for e in events
                          if e.get("type") == schema.EVENT_ACTIVATION_STARTED]
                self.assertEqual(len(changed), 1)
                self.assertEqual(len(domain), 1)
                self.assertEqual(changed[0]["settingsRevision"], 1)
                # the domain event indeed carries the NEW settings value
                self.assertEqual(
                    domain[0]["effectiveSettings"][sc.ACTIVATION_FOLLOWUP], 8000
                )
                # settings.changed (revision 1) must precede that domain event
                self.assertLess(changed[0]["eventSeq"], domain[0]["eventSeq"])
                # strictly monotonic and unique
                sequences = [event["eventSeq"] for event in events]
                self.assertEqual(sequences, sorted(sequences))
                self.assertEqual(len(set(sequences)), len(sequences))


if __name__ == "__main__":  # pragma: no cover
    import pytest
    raise SystemExit(pytest.main([__file__]))