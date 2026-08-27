"""AP-SRV-040 – frozen contract vectors and protocol-layer unit proofs.

Two kinds of test live here:

1. **Contract vectors.** ``tests/contracts/protocol-v2-vectors.json`` is the
   frozen cross-repository vector file. The tests load it - they never restate
   a message inline - so AP-SRV-040 and AP-CLI-010 cannot drift apart. When
   ``VOICESTT_PROTOCOL_V2_VECTORS`` points at the planning original, the copy
   is compared against it and any drift fails.

2. **Protocol-layer proofs.** Strict envelope rules, the exhaustive result
   mapping, event identity and versioning, the deadline projection and the
   pending-activation projection - each against the module that owns it, so a
   failure names the responsible component instead of a whole socket.
"""

import json
import os
import pathlib
import threading
import unittest
import uuid

from api_fastapi_server import activation as activation_module
from api_fastapi_server.protocol_v2 import (
    commands,
    events,
    handshake,
    identity,
    ports,
    schema,
    snapshot as snapshot_layer,
)
from api_fastapi_server.protocol_v2.session import ProtocolSessionState

from tests.unit.test_server_controlled_e2e import (
    GateAwareRecorder,
    TestClient,
    build_app,
)
from tests.unit.test_protocol_v2_e2e import V2Session, hello_message


VECTOR_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / "contracts"
    / "protocol-v2-vectors.json"
)


def load_vectors():
    return json.loads(VECTOR_PATH.read_text(encoding="utf-8"))


def vector(name):
    data = load_vectors()
    for group in ("validMessages", "invalidMessages"):
        for entry in data.get(group, []):
            if entry.get("name") == name:
                return entry
    raise AssertionError(f"unknown contract vector: {name}")


class ContractVectorFileTests(unittest.TestCase):
    def test_the_vendored_copy_matches_the_planning_original(self):
        original = os.environ.get("VOICESTT_PROTOCOL_V2_VECTORS")
        if not original:
            self.skipTest(
                "set VOICESTT_PROTOCOL_V2_VECTORS to compare against the "
                "planning original"
            )
        source = pathlib.Path(original)
        if not source.is_file():
            self.skipTest(f"{original} is not a readable file")
        self.assertEqual(
            source.read_bytes(),
            VECTOR_PATH.read_bytes(),
            "the vendored contract vectors drifted from the planning original",
        )

    def test_the_vector_file_targets_this_protocol_version(self):
        data = load_vectors()
        self.assertEqual(data["protocolVersion"], schema.PROTOCOL_VERSION)

    def test_every_expected_vector_is_present(self):
        data = load_vectors()
        names = {
            entry["name"]
            for group in ("validMessages", "invalidMessages")
            for entry in data[group]
        }
        self.assertGreaterEqual(names, {
            "hello_v2",
            "manual_activate",
            "manual_activate_replay",
            "refresh_active_activation",
            "activation_started_event",
            "idle_snapshot",
            "wake_enabled_without_selection",
            "client_claims_wake_word",
            "activate_with_activation_id",
            "refresh_without_activation_id",
            "command_id_conflict",
        })


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class ContractVectorBehaviourTests(unittest.TestCase):
    """Each vector run against the real parser and the real projection."""

    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def _bind(self, session, message):
        """Vector ids are placeholders; bind them to this live session."""
        bound = dict(message)
        if "sessionId" in bound:
            bound["sessionId"] = session.session_id
        return bound

    def test_hello_v2_is_accepted(self):
        entry = vector("hello_v2")
        message = dict(entry["message"])
        # The vector selects a wake word from the frozen catalog; the trigger
        # part is what this server can admit today, so the wake word source is
        # exercised separately by the negative vector below.
        message["requestedSession"] = {
            "trigger": {"manual": True, "wakeWord": False},
            "wakeWordIds": [],
        }
        with TestClient(self.app) as client:
            with V2Session(client, hello=message) as session:
                self.assertEqual(
                    session.accepted["type"], entry["expected"]
                )
                self.assertEqual(session.accepted["protocolVersion"], 2)

    def test_hello_v2_envelope_passes_the_frozen_parser(self):
        entry = vector("hello_v2")
        result = handshake.parse_hello(
            entry["message"],
            server_version="test",
            server_commit="test",
        )
        self.assertTrue(result.accepted, result.refusal)
        self.assertEqual(result.protocol_version, 2)
        self.assertEqual(result.hello.wake_word_ids, ("hey_jarvis",))

    def test_manual_activate_and_replay(self):
        activate = vector("manual_activate")
        replay = vector("manual_activate_replay")
        self.assertEqual(
            replay["sameLogicalMessageAs"], activate["name"]
        )
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                first_payload = self._bind(session, activate["message"])
                session.send_raw(first_payload)
                first = session.ack(first_payload["commandId"])
                self.assertEqual(
                    first["accepted"], activate["expectedAck"]["accepted"]
                )
                self.assertEqual(
                    first["result"], activate["expectedAck"]["result"]
                )
                session.event(schema.EVENT_ACTIVATION_STARTED)

                session.send_raw(self._bind(session, replay["message"]))
                second = session.ack(first_payload["commandId"])
                # identical_ack_and_single_effect
                self.assertEqual(first, second)
                session.snapshot()
                self.assertEqual(
                    len(session.collected(schema.EVENT_ACTIVATION_STARTED)), 1
                )

    def test_refresh_active_activation(self):
        entry = vector("refresh_active_activation")
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                _command_id, activate_ack = session.activate()
                session.event(schema.EVENT_ACTIVATION_STARTED)
                # A refresh is only meaningful once a segment or the follow-up
                # window is running; drive the real recorder to get there.
                from tests.unit.test_server_controlled_e2e import speech_packet

                session.send_bytes(speech_packet())
                session.event(schema.EVENT_SEGMENT_RECORDING_STARTED)

                payload = self._bind(session, entry["message"])
                payload["activationId"] = activate_ack["activationId"]
                session.send_raw(payload)
                ack = session.ack(payload["commandId"])
                self.assertEqual(
                    ack["accepted"], entry["expectedAck"]["accepted"]
                )
                self.assertEqual(
                    ack["result"], entry["expectedAck"]["result"]
                )

    def test_activation_started_event_uses_the_frozen_field_names(self):
        expected_fields = set(vector("activation_started_event")["message"])
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                session.activate()
                started = session.event(schema.EVENT_ACTIVATION_STARTED)
                missing = expected_fields - set(started)
                self.assertEqual(missing, set(), started)
                self.assertEqual(started["type"], "activation.started")

    def test_idle_snapshot_uses_the_frozen_field_names(self):
        message = vector("idle_snapshot")["message"]
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                produced = session.snapshot()
                self.assertEqual(set(message) - set(produced), set(), produced)
                self.assertEqual(
                    set(message["input"]) - set(produced["input"]), set()
                )
                self.assertEqual(
                    set(message["trigger"]) - set(produced["trigger"]), set()
                )
                self.assertEqual(
                    set(message["wakeWordCapabilities"])
                    - set(produced["wakeWordCapabilities"]),
                    set(),
                )
                self.assertEqual(produced["input"], message["input"])

    def test_wake_enabled_without_selection_is_rejected(self):
        entry = vector("wake_enabled_without_selection")
        with TestClient(self.app) as client:
            with client.websocket_connect("/ws/v2") as socket:
                socket.send_text(json.dumps(entry["message"]))
                payload = socket.receive_json()
        self.assertEqual(payload["type"], entry["expected"])
        codes = {error["code"] for error in payload["errors"]}
        self.assertIn(entry["expectedErrorCode"], codes)

    def test_negative_command_vectors(self):
        for name in (
            "client_claims_wake_word",
            "activate_with_activation_id",
            "refresh_without_activation_id",
        ):
            with self.subTest(vector=name):
                app = build_app()
                GateAwareRecorder.instances = []
                entry = vector(name)
                with TestClient(app) as client:
                    with V2Session(client) as session:
                        payload = self._bind(session, entry["message"])
                        session.send_raw(payload)
                        ack = session.ack(payload["commandId"])
                        self.assertEqual(
                            ack["accepted"], entry["expectedAck"]["accepted"]
                        )
                        self.assertEqual(
                            ack["result"], entry["expectedAck"]["result"]
                        )

    def test_command_id_conflict_vector(self):
        activate = vector("manual_activate")
        conflict = vector("command_id_conflict")
        self.assertEqual(
            activate["message"]["commandId"], conflict["message"]["commandId"]
        )
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                first_payload = self._bind(session, activate["message"])
                session.send_raw(first_payload)
                first = session.ack(first_payload["commandId"])

                conflicting = self._bind(session, conflict["message"])
                conflicting["activationId"] = first["activationId"]
                session.send_raw(conflicting)
                ack = session.ack(conflicting["commandId"])
                self.assertEqual(
                    ack["accepted"], conflict["expectedAck"]["accepted"]
                )
                self.assertEqual(
                    ack["result"], conflict["expectedAck"]["result"]
                )
                # No effect: the activation is still open.
                self.assertEqual(
                    session.snapshot()["input"]["phase"],
                    schema.WAITING_FIRST_SPEECH,
                )


class CanonicalIdentityTests(unittest.TestCase):
    def test_canonical_uuids_are_accepted(self):
        for _ in range(20):
            self.assertTrue(
                schema.is_canonical_uuid(schema.new_canonical_id())
            )

    def test_compact_and_upper_case_forms_are_refused(self):
        value = uuid.uuid4()
        self.assertFalse(schema.is_canonical_uuid(value.hex))
        self.assertFalse(schema.is_canonical_uuid(str(value).upper()))
        self.assertFalse(schema.is_canonical_uuid(f" {value} "))
        self.assertFalse(schema.is_canonical_uuid(None))
        self.assertFalse(schema.is_canonical_uuid(1))
        self.assertFalse(schema.is_canonical_uuid("not-a-uuid"))

    def test_normalize_command_id_never_rewrites(self):
        canonical = schema.new_canonical_id()
        self.assertEqual(schema.normalize_command_id(canonical), canonical)
        self.assertIsNone(schema.normalize_command_id(canonical.replace("-", "")))


class StrictEnvelopeTests(unittest.TestCase):
    SESSION = "20000000-0000-4000-8000-000000000001"
    COMMAND = "50000000-0000-4000-8000-000000000001"
    ACTIVATION = "30000000-0000-4000-8000-000000000001"

    def parse(self, **overrides):
        payload = {
            "type": schema.ACTIVATION_COMMAND,
            "protocolVersion": 2,
            "sessionId": self.SESSION,
            "commandId": self.COMMAND,
        }
        payload.update(overrides)
        return commands.parse_command(payload, session_id=self.SESSION)

    def test_activate_requires_manual_source_and_no_activation_id(self):
        self.assertIsNone(
            self.parse(action="activate", source="manual").rejection
        )
        self.assertEqual(
            self.parse(action="activate", source="wake_word").rejection,
            schema.RESULT_INVALID_PAYLOAD,
        )
        self.assertEqual(
            self.parse(action="activate").rejection,
            schema.RESULT_INVALID_PAYLOAD,
        )
        self.assertEqual(
            self.parse(
                action="activate", source="manual", activationId=self.ACTIVATION
            ).rejection,
            schema.RESULT_INVALID_PAYLOAD,
        )

    def test_controls_require_activation_id_and_forbid_source(self):
        for action in ("refresh", "finish", "cancel"):
            with self.subTest(action=action):
                self.assertIsNone(
                    self.parse(
                        action=action, activationId=self.ACTIVATION
                    ).rejection
                )
                self.assertEqual(
                    self.parse(action=action).rejection,
                    schema.RESULT_INVALID_PAYLOAD,
                )
                self.assertEqual(
                    self.parse(
                        action=action,
                        activationId=self.ACTIVATION,
                        source="manual",
                    ).rejection,
                    schema.RESULT_INVALID_PAYLOAD,
                )

    def test_extend_alias_does_not_exist_in_v2(self):
        self.assertEqual(
            self.parse(action="extend", activationId=self.ACTIVATION).rejection,
            schema.RESULT_INVALID_PAYLOAD,
        )

    def test_foreign_session_id_is_stale_session(self):
        parsed = self.parse(
            action="activate",
            source="manual",
            sessionId="20000000-0000-4000-8000-0000000000ff",
        )
        self.assertEqual(parsed.rejection, schema.RESULT_STALE_SESSION)

    def test_malformed_session_id_is_invalid_payload(self):
        parsed = self.parse(
            action="activate", source="manual", sessionId="nope"
        )
        self.assertEqual(parsed.rejection, schema.RESULT_INVALID_PAYLOAD)

    def test_unknown_message_type_is_not_a_command(self):
        self.assertIsNone(
            commands.parse_command(
                {"type": "future.thing", "commandId": self.COMMAND},
                session_id=self.SESSION,
            )
        )
        self.assertIsNone(
            commands.parse_command("not a dict", session_id=self.SESSION)
        )

    def test_forbidden_control_source_changes_the_replay_key(self):
        """The legacy v1 tolerance must not hide a forbidden v2 field."""
        without = self.parse(action="refresh", activationId=self.ACTIVATION)
        with_source = self.parse(
            action="refresh", activationId=self.ACTIVATION, source="manual"
        )
        self.assertNotEqual(without.payload_key, with_source.payload_key)

    def test_additive_unknown_fields_do_not_change_the_frozen_verdict(self):
        parsed = self.parse(
            action="activate", source="manual", futureField=[1, {"a": True}]
        )
        self.assertIsNone(parsed.rejection)

    def test_other_command_types_validate_their_frozen_fields(self):
        session = self.SESSION

        def parse(payload):
            base = {
                "protocolVersion": 2,
                "sessionId": session,
                "commandId": self.COMMAND,
            }
            base.update(payload)
            return commands.parse_command(base, session_id=session)

        self.assertIsNone(parse({
            "type": schema.TRIGGER_SUPPRESSION_SET,
            "manual": True,
            "wakeWord": False,
        }).rejection)
        self.assertEqual(parse({
            "type": schema.TRIGGER_SUPPRESSION_SET, "manual": True,
        }).rejection, schema.RESULT_INVALID_PAYLOAD)
        self.assertIsNone(parse({
            "type": schema.AUDIO_AVAILABILITY_SET, "audioAvailable": False,
        }).rejection)
        self.assertEqual(parse({
            "type": schema.AUDIO_AVAILABILITY_SET, "audioAvailable": "false",
        }).rejection, schema.RESULT_INVALID_PAYLOAD)
        self.assertIsNone(parse({
            "type": schema.SESSION_SETTINGS_PATCH,
            "baseSettingsRevision": 0,
            "changes": {"a": 1},
        }).rejection)
        self.assertEqual(parse({
            "type": schema.SESSION_SETTINGS_PATCH,
            "baseSettingsRevision": -1,
            "changes": {"a": 1},
        }).rejection, schema.RESULT_INVALID_PAYLOAD)
        self.assertIsNone(parse({
            "type": schema.SESSION_SNAPSHOT_REQUEST,
        }).rejection)


class ResultMappingTests(unittest.TestCase):
    """K4 - one explicit, exhaustive projection onto the frozen codes."""

    def test_every_mapped_value_is_a_frozen_result_code(self):
        for reason, result in commands.DOMAIN_REASON_RESULTS.items():
            with self.subTest(reason=reason):
                self.assertIn(result, schema.RESULT_CODES)

    def test_accepted_is_true_for_exactly_two_results(self):
        accepted = {
            result for result in schema.RESULT_CODES
            if commands.is_accepted(result)
        }
        self.assertEqual(accepted, {"applied", "no_change"})

    def test_an_unmapped_reason_fails_loudly(self):
        with self.assertRaises(commands.UnmappedDomainReason):
            commands.map_domain_reason("a_reason_nobody_mapped")

    def test_every_domain_reason_is_mapped_or_declared_non_command(self):
        """Reads the reasons out of the AP-SRV-030 source itself.

        A new decision reason therefore fails this test until it has been
        classified, instead of silently degrading to ``internal_error``.
        """
        source = pathlib.Path(activation_module.__file__).read_text(
            encoding="utf-8"
        )
        found = set()
        for marker in ('ActivationDecision(\n', 'ActivationDecision('):
            del marker
        import re

        for match in re.finditer(
            r'ActivationDecision\(\s*(?:True|False),\s*"([a-z_]+)"', source
        ):
            found.add(match.group(1))
        # The close barrier returns the close reason itself.
        found.update({"finished", "cancelled"})
        self.assertTrue(found, "no domain reasons were discovered")

        unclassified = found - set(commands.DOMAIN_REASON_RESULTS) - (
            commands.NON_COMMAND_REASONS
        )
        self.assertEqual(unclassified, set(), f"unclassified reasons: {unclassified}")

    def test_declared_non_command_reasons_are_not_also_mapped(self):
        overlap = commands.NON_COMMAND_REASONS & set(
            commands.DOMAIN_REASON_RESULTS
        )
        self.assertEqual(overlap, set())


class ProtocolSessionStateTests(unittest.TestCase):
    def state(self, **kwargs):
        return ProtocolSessionState(schema.new_canonical_id(), **kwargs)

    def test_a_non_canonical_session_id_is_refused(self):
        with self.assertRaises(ValueError):
            ProtocolSessionState(uuid.uuid4().hex)

    def test_event_seq_is_strictly_monotonic(self):
        state = self.state()
        sequences = [
            state.mint_event(schema.EVENT_ACTIVATION_STARTED)["eventSeq"]
            for _ in range(25)
        ]
        self.assertEqual(sequences, list(range(1, 26)))
        self.assertEqual(state.last_event_seq, 25)

    def test_state_version_advances_only_for_visible_changes(self):
        state = self.state()
        state.mint_event(schema.EVENT_ACTIVATION_STARTED)
        self.assertEqual(state.state_version, 1)
        warning = state.mint_event(schema.EVENT_WATCHDOG_WARNING)
        self.assertEqual(state.state_version, 1)
        self.assertEqual(warning["stateVersion"], 1)
        suppressed = state.mint_event(
            schema.EVENT_ACTIVATION_TRIGGER_SUPPRESSED
        )
        self.assertEqual(state.state_version, 1)
        self.assertEqual(suppressed["eventSeq"], 3)

    def test_a_retry_of_one_logical_event_mints_no_new_identity(self):
        state = self.state()
        key = ("activation.input_closed", "a")
        first = state.mint_event(
            schema.EVENT_ACTIVATION_INPUT_CLOSED, logical_key=key
        )
        second = state.mint_event(
            schema.EVENT_ACTIVATION_INPUT_CLOSED, logical_key=key
        )
        self.assertEqual(first, second)
        self.assertEqual(state.last_event_seq, 1)
        self.assertEqual(state.state_version, 1)

    def test_event_ids_are_canonical_and_unique(self):
        state = self.state()
        identifiers = [
            state.mint_event(schema.EVENT_ACTIVATION_STARTED)["eventId"]
            for _ in range(50)
        ]
        self.assertEqual(len(set(identifiers)), 50)
        for value in identifiers:
            self.assertTrue(schema.is_canonical_uuid(value))

    def test_concurrent_minting_keeps_the_sequence_gapless(self):
        state = self.state()
        start = threading.Barrier(8)
        results = []
        lock = threading.Lock()

        def mint():
            start.wait(timeout=10)
            for _ in range(20):
                envelope = state.mint_event(schema.EVENT_ACTIVATION_STARTED)
                with lock:
                    results.append(envelope["eventSeq"])

        threads = [threading.Thread(target=mint) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertEqual(sorted(results), list(range(1, 161)))
        self.assertEqual(state.state_version, 160)

    def test_settings_revision_mirrors_only_real_changes(self):
        state = self.state(settings_revision=3)
        self.assertEqual(state.settings_revision, 3)
        self.assertFalse(state.set_settings_revision(3))
        self.assertTrue(state.set_settings_revision(4))
        self.assertEqual(state.settings_revision, 4)


class EventProjectionTests(unittest.TestCase):
    def setUp(self):
        self.state = ProtocolSessionState(schema.new_canonical_id())
        self.projector = events.EventProjector(self.state)
        self.activation = schema.new_canonical_id()

    def context(self, phase=schema.WAITING_FIRST_SPEECH, **kwargs):
        base = {
            "phase": phase,
            "activation_id": self.activation,
            "activation_sequence": 1,
            "primary_source": schema.MANUAL_SOURCE,
        }
        base.update(kwargs)
        return events.ProjectionContext(**base)

    def test_unknown_legacy_events_are_dropped(self):
        for legacy in (
            "realtime_transcript", "idle", "wakeword_wait_started",
            "wakeword_followup_timeout", "transcription_started_unknown",
        ):
            with self.subTest(legacy=legacy):
                self.assertEqual(
                    self.projector.project(legacy, {}, self.context()), []
                )
        self.assertEqual(self.state.last_event_seq, 0)

    def test_input_closed_keeps_a_null_correlation_for_timer_closes(self):
        produced = self.projector.project(
            "activation_closed",
            {
                "activationId": self.activation,
                "reason": "initial_speech_timeout",
                "acceptedSegmentCount": 0,
            },
            self.context(phase=schema.IDLE),
        )
        self.assertEqual(len(produced), 1)
        event = produced[0]
        self.assertEqual(event["type"], schema.EVENT_ACTIVATION_INPUT_CLOSED)
        self.assertIsNone(event["causedByCommandId"])
        self.assertEqual(event["reason"], "initial_speech_timeout")

    def test_input_closed_keeps_the_command_correlation_for_finish(self):
        command_id = schema.new_canonical_id()
        produced = self.projector.project(
            "activation_closed",
            {
                "activationId": self.activation,
                "reason": "finished",
                "causedByCommandId": command_id,
                "acceptedSegmentCount": 2,
            },
            self.context(phase=schema.IDLE),
        )
        self.assertEqual(produced[0]["causedByCommandId"], command_id)
        self.assertEqual(produced[0]["acceptedSegmentCount"], 2)

    def test_a_republished_close_reuses_the_same_logical_identity(self):
        payload = {
            "activationId": self.activation,
            "reason": "finished",
            "acceptedSegmentCount": 0,
        }
        first = self.projector.project(
            "activation_closed", payload, self.context(phase=schema.IDLE)
        )[0]
        second = self.projector.project(
            "activation_closed", payload, self.context(phase=schema.IDLE)
        )[0]
        self.assertEqual(first["eventId"], second["eventId"])
        self.assertEqual(first["eventSeq"], second["eventSeq"])
        self.assertEqual(first["stateVersion"], second["stateVersion"])
        self.assertEqual(self.state.last_event_seq, 1)

    def test_activation_terminals_fan_out_by_state(self):
        for state, expected in (
            ("completed", schema.EVENT_ACTIVATION_COMPLETED),
            ("cancelled", schema.EVENT_ACTIVATION_CANCELLED),
            ("failed", schema.EVENT_ACTIVATION_FAILED),
        ):
            with self.subTest(state=state):
                projector = events.EventProjector(
                    ProtocolSessionState(schema.new_canonical_id())
                )
                produced = projector.project(
                    "activation_drained",
                    {
                        "activationId": self.activation,
                        "state": state,
                        "reason": "reason",
                        "acceptedSegmentCount": 2,
                        "terminalSegmentCount": 2,
                    },
                    self.context(phase=schema.IDLE),
                )
                self.assertEqual(produced[0]["type"], expected)
                self.assertEqual(produced[0]["acceptedSegmentCount"], 2)
                self.assertEqual(produced[0]["terminalSegmentCount"], 2)
                if expected != schema.EVENT_ACTIVATION_COMPLETED:
                    self.assertIn("reason", produced[0])

    def test_a_cancelled_segment_terminal_is_a_discard_with_its_reason(self):
        self.projector.project(
            "recording_started",
            {"segmentId": "s1", "segmentSequence": 1,
             "activationId": self.activation},
            self.context(phase=schema.SEGMENT_ACTIVE),
        )
        produced = self.projector.project(
            "final_transcript_cancelled",
            {"segmentId": "s1", "reason": "cancelled"},
            self.context(phase=schema.IDLE),
        )
        self.assertEqual(
            produced[-1]["type"], schema.EVENT_TRANSCRIPTION_DISCARDED
        )
        self.assertEqual(produced[-1]["reason"], "cancelled")
        self.assertEqual(produced[-1]["segmentSequence"], 1)

    def test_segment_sequence_survives_the_released_context(self):
        self.projector.project(
            "recording_started",
            {"segmentId": "s7", "activationId": self.activation},
            self.context(
                phase=schema.SEGMENT_ACTIVE,
                active_segment_id="s7",
                active_segment_sequence=4,
            ),
        )
        produced = self.projector.project(
            "recording_ended",
            {"segmentId": "s7", "reason": "recording_stop"},
            self.context(phase=schema.FOLLOWUP_WAIT),
        )
        ended = produced[-1]
        self.assertEqual(ended["type"], schema.EVENT_SEGMENT_RECORDING_ENDED)
        self.assertEqual(ended["segmentSequence"], 4)
        self.assertEqual(ended["segmentId"], "s7")

    def test_every_projected_event_name_is_frozen(self):
        for name in events.LEGACY_EVENT_TYPES.values():
            if name is None:
                continue
            self.assertIn(name, schema.EVENT_TYPES)
        for name in events.ACTIVATION_TERMINAL_TYPES.values():
            self.assertIn(name, schema.EVENT_TYPES)


class DeadlineProjectionTests(unittest.TestCase):
    def test_a_monotonic_deadline_becomes_a_wall_clock_projection(self):
        deadline_at, remaining = snapshot_layer.project_deadline(
            1_000.0,
            monotonic=lambda: 995.0,
            wall_clock=lambda: 1_700_000_000.0,
        )
        self.assertEqual(remaining, 5_000)
        self.assertEqual(deadline_at, 1_700_000_000_000 + 5_000)

    def test_an_expired_deadline_never_goes_negative(self):
        deadline_at, remaining = snapshot_layer.project_deadline(
            1_000.0,
            monotonic=lambda: 1_500.0,
            wall_clock=lambda: 1_700_000_000.0,
        )
        self.assertEqual(remaining, 0)
        self.assertEqual(deadline_at, 1_700_000_000_000)

    def test_no_deadline_projects_to_null(self):
        self.assertEqual(snapshot_layer.project_deadline(None), (None, None))

    def test_idle_input_nulls_every_optional_value(self):
        produced = snapshot_layer.build_input({"phase": schema.IDLE})
        self.assertEqual(produced, {
            "phase": schema.IDLE,
            "activationId": None,
            "primarySource": None,
            "deadlineAtUnixMs": None,
            "remainingMs": None,
            "closeRequested": False,
        })

    def test_closing_input_sets_close_requested(self):
        produced = snapshot_layer.build_input({
            "phase": schema.CLOSING_INPUT,
            "activationId": "a",
            "primarySource": schema.MANUAL_SOURCE,
            "deadline": None,
        })
        self.assertTrue(produced["closeRequested"])
        self.assertEqual(produced["activationId"], "a")


class FakeController:
    """A controller stand-in for pure snapshot projection tests."""

    def __init__(self, snapshot, trigger=None):
        self._snapshot = snapshot
        self._trigger = trigger or {
            "configured": {"manual": True, "wake_word": False},
            "suppressed": {"manual": False, "wake_word": False},
            "effective": {"manual": True, "wake_word": False},
        }

    def snapshot(self):
        return dict(self._snapshot)

    def trigger_state(self):
        return self._trigger


class FakeLedger:
    def __init__(self, activations):
        self._activations = activations

    def snapshot(self):
        return {"activations": [dict(item) for item in self._activations]}


def pending_record(sequence, *, activation_id=None, closed=True, state="draining"):
    return {
        "activationId": activation_id or f"activation-{sequence}",
        "activationSequence": sequence,
        "inputClosed": closed,
        "inputClosedReason": "finished" if closed else None,
        "state": state,
        "acceptedSegmentCount": 1,
        "terminalSegmentCount": 0,
    }


class SnapshotCombinationTests(unittest.TestCase):
    """Every foreground/background combination the frozen contract requires."""

    def build(self, controller_snapshot, activations):
        state = ProtocolSessionState(schema.new_canonical_id())

        class FakeSettings:
            def effective_settings(self):
                return {"activation.followupTimeoutMs": 3000}

        class FakeWake:
            def capabilities(self):
                return {"catalogRevision": 1, "availableWakeWordIds": []}

        return snapshot_layer.build_snapshot(
            state=state,
            controller=FakeController(controller_snapshot),
            ledger=FakeLedger(activations),
            audio_available=True,
            settings_port=FakeSettings(),
            wake_word_port=FakeWake(),
            server_version="2.0.0-test",
            server_commit="test",
        )

    def test_idle_without_pending_activations(self):
        produced = self.build({"phase": schema.IDLE}, [])
        self.assertEqual(produced["input"]["phase"], schema.IDLE)
        self.assertEqual(produced["pendingActivations"], [])

    def test_idle_with_one_pending_activation(self):
        produced = self.build({"phase": schema.IDLE}, [pending_record(1)])
        self.assertEqual(produced["input"]["phase"], schema.IDLE)
        self.assertEqual(len(produced["pendingActivations"]), 1)
        entry = produced["pendingActivations"][0]
        self.assertEqual(entry["activationSequence"], 1)
        self.assertEqual(entry["inputClosedReason"], "finished")
        self.assertEqual(entry["processingState"], "draining")

    def test_idle_with_several_pending_activations_stays_sorted(self):
        produced = self.build(
            {"phase": schema.IDLE},
            [pending_record(3), pending_record(1), pending_record(2)],
        )
        self.assertEqual(
            [entry["activationSequence"] for entry in produced["pendingActivations"]],
            [1, 2, 3],
        )

    def test_an_open_activation_with_older_pending_activations(self):
        produced = self.build(
            {
                "phase": schema.SEGMENT_ACTIVE,
                "activationId": "activation-4",
                "primarySource": schema.MANUAL_SOURCE,
                "deadline": None,
            },
            [
                pending_record(1),
                pending_record(2),
                pending_record(4, activation_id="activation-4", closed=False),
            ],
        )
        self.assertEqual(produced["input"]["phase"], schema.SEGMENT_ACTIVE)
        self.assertEqual(produced["input"]["activationId"], "activation-4")
        # The open foreground activation is reported by ``input`` only.
        self.assertEqual(
            [entry["activationSequence"] for entry in produced["pendingActivations"]],
            [1, 2],
        )

    def test_every_frozen_snapshot_field_is_present(self):
        produced = self.build({"phase": schema.IDLE}, [])
        for field in (
            "type", "protocolVersion", "serverVersion", "serverCommit",
            "sessionId", "stateVersion", "lastEventSeq", "settingsRevision",
            "input", "pendingActivations", "trigger", "audioAvailable",
            "effectiveSettings", "wakeWordCapabilities",
        ):
            self.assertIn(field, produced)
        self.assertEqual(
            snapshot_layer.embedded_snapshot(produced).get("type"), None
        )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class InputCloseSeamTests(unittest.TestCase):
    """AP-SRV-040 binds the AP-SRV-030 close seam; it never replaces it."""

    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()
        self.service = self.app.state.voicestt_service

    def _session(self):
        from api_fastapi_server.server import SessionActivationRequest

        session = self.service.admit_session(
            schema.new_canonical_id(),
            activation_request=SessionActivationRequest(
                manual_enabled=True, wake_word_enabled=False
            ),
            canonical_ids=True,
        )
        self.addCleanup(self.service.remove_session, session.session_id)
        return session

    def _closing_plan(self, session, *, command_id, recovery):
        controller = session.activation_controller()
        decision = controller.activate(schema.MANUAL_SOURCE, {})
        self.assertTrue(decision.accepted)
        activation_id = decision.snapshot["activationId"]
        closed = controller.finish(
            activation_id=activation_id, command_id=command_id
        )
        self.assertTrue(closed.accepted)
        with session.lock:
            plan = session._build_close_plan_locked(
                controller.snapshot(),
                requested_by_command_id=command_id,
                recovery=recovery,
            )
        return activation_id, plan

    def test_a_command_driven_close_keeps_its_correlation(self):
        session = self._session()
        command_id = schema.new_canonical_id()
        activation_id, plan = self._closing_plan(
            session, command_id=command_id, recovery=False
        )
        key = session._reserve_input_close_event(plan, recovery=False)
        self.assertIsNotNone(key)
        fields = session._registered_input_close_events[key]
        self.assertEqual(fields["causedByCommandId"], command_id)
        self.assertEqual(fields["activationId"], activation_id)

    def test_a_recovery_close_reports_a_null_correlation_on_the_wire(self):
        session = self._session()
        command_id = schema.new_canonical_id()
        _activation_id, plan = self._closing_plan(
            session, command_id=command_id, recovery=True
        )
        # The internal close context may keep the original command identity …
        self.assertEqual(plan.requested_by_command_id, command_id)
        key = session._reserve_input_close_event(plan, recovery=True)
        self.assertIsNotNone(key)
        fields = session._registered_input_close_events[key]
        # … but the wire completion of a recovery is never command correlated.
        self.assertIsNone(fields["causedByCommandId"])
        self.assertTrue(fields.get("recovered"))

        projector = events.EventProjector(
            ProtocolSessionState(schema.new_canonical_id())
        )
        produced = projector.project(
            "activation_closed",
            dict(fields),
            events.ProjectionContext(phase=schema.IDLE),
        )
        self.assertEqual(
            produced[0]["type"], schema.EVENT_ACTIVATION_INPUT_CLOSED
        )
        self.assertIsNone(produced[0]["causedByCommandId"])

    def test_the_registration_is_idempotent_for_one_activation(self):
        session = self._session()
        _activation_id, plan = self._closing_plan(
            session, command_id=schema.new_canonical_id(), recovery=False
        )
        first = session._reserve_input_close_event(plan, recovery=False)
        second = session._reserve_input_close_event(plan, recovery=False)
        self.assertEqual(first, second)
        self.assertEqual(len(session._registered_input_close_events), 1)


class PortTests(unittest.TestCase):
    def test_the_settings_port_declares_its_binding(self):
        self.assertEqual(
            ports.SettingsPort.binding, "REQUIRES_AP_SRV_050_BINDING"
        )
        self.assertEqual(
            ports.WakeWordPort.binding, "REQUIRES_AP_SRV_060_BINDING"
        )

    def test_a_patch_is_applied_and_a_stale_revision_conflicts(self):
        from api_fastapi_server.settings_control import (
            SessionSettingsState,
            build_default_registry,
        )

        class FakeSettingsSession:
            def __init__(self, state):
                self.settings_state = state

            def apply_settings_patch(self, base, changes):
                return self.settings_state.apply_patch(base, changes)

            def settings_effective_for_wire(self):
                return dict(self.settings_state.effective_values())

        session = FakeSettingsSession(
            SessionSettingsState(build_default_registry())
        )
        port = ports.SettingsPort(session)
        result = port.patch(0, {"activation.followupTimeoutMs": 4000})
        self.assertEqual(result.result, "applied")
        self.assertTrue(result.accepted)
        self.assertEqual(result.settings_revision, 1)
        self.assertEqual(port.revision, 1)
        # ``effectiveSettings`` reflects the session resolution.
        self.assertEqual(
            port.effective_settings()["activation.followupTimeoutMs"], 4000
        )
        stale = port.patch(0, {"activation.followupTimeoutMs": 5000})
        self.assertEqual(stale.result, "settings_revision_conflict")
        self.assertEqual(stale.errors[0].code, "stale_settings_revision")

    def test_wake_word_selection_is_atomic(self):
        class FakeService:
            def session_capabilities(self):
                return {"wakeWord": {"availableWakeWords": [
                    {"id": "hey_jarvis"}, {"id": "alexa"},
                ]}}

        port = ports.WakeWordPort(FakeService())
        self.assertEqual(port.available_ids(), ["alexa", "hey_jarvis"])
        self.assertEqual(port.validate_selection(["hey_jarvis"]), [])
        errors = port.validate_selection(["hey_jarvis", "nope"])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], "wake_word_unavailable")

    def test_capabilities_carry_a_catalog_revision(self):
        class EmptyService:
            def session_capabilities(self):
                return {}

        capabilities = ports.WakeWordPort(EmptyService()).capabilities()
        self.assertIn("catalogRevision", capabilities)
        self.assertEqual(capabilities["availableWakeWordIds"], [])


class HandshakeUnitTests(unittest.TestCase):
    def test_negotiation_picks_the_highest_shared_version(self):
        self.assertEqual(handshake.negotiate([1, 2, 3]), 2)
        self.assertEqual(handshake.negotiate([2]), 2)
        self.assertIsNone(handshake.negotiate([1]))
        self.assertIsNone(handshake.negotiate([]))

    def test_refusal_messages_carry_the_server_identity(self):
        payload = handshake.protocol_incompatible(
            "no_common_protocol_version",
            server_version="1.2.3",
            server_commit="abc",
        )
        self.assertEqual(payload["serverVersion"], "1.2.3")
        self.assertEqual(payload["serverCommit"], "abc")
        self.assertEqual(payload["supportedProtocolVersions"], [2])
        self.assertNotIn("sessionId", payload)

    def test_a_wake_selection_without_the_wake_trigger_is_refused(self):
        result = handshake.parse_hello(
            hello_message(
                manual=True, wake_word=False, wake_word_ids=("hey_jarvis",)
            ),
            server_version="t",
            server_commit="t",
        )
        self.assertTrue(result.accepted)

        class FakePort:
            def validate_selection(self, ids):
                return []

        errors = handshake.validate_requested_session(
            result.hello, FakePort()
        )
        codes = {error["code"] for error in errors}
        self.assertIn("wake_word_selection_not_allowed", codes)

    def test_suppression_does_not_replace_the_wake_selection(self):
        result = handshake.parse_hello(
            hello_message(
                manual=True, wake_word=True, wake_word_ids=(),
                suppress_wake_word=True,
            ),
            server_version="t",
            server_commit="t",
        )

        class FakePort:
            def validate_selection(self, ids):
                return []

        errors = handshake.validate_requested_session(result.hello, FakePort())
        codes = {error["code"] for error in errors}
        self.assertIn("wake_word_selection_required", codes)


class ServerIdentityTests(unittest.TestCase):
    def test_the_commit_falls_back_to_unknown(self):
        previous = os.environ.pop("VOICESTT_SERVER_COMMIT", None)
        try:
            self.assertEqual(identity.server_commit(), "unknown")
            os.environ["VOICESTT_SERVER_COMMIT"] = "  deadbeef "
            self.assertEqual(identity.server_commit(), "deadbeef")
            os.environ["VOICESTT_SERVER_COMMIT"] = "   "
            self.assertEqual(identity.server_commit(), "unknown")
        finally:
            os.environ.pop("VOICESTT_SERVER_COMMIT", None)
            if previous is not None:
                os.environ["VOICESTT_SERVER_COMMIT"] = previous

    def test_the_version_is_published(self):
        self.assertTrue(identity.server_version())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
