"""AP-SRV-070 W1A - the hard boundary between protocol v1 and protocol v2.

The two transports share one server process, one service object and one
session store, but they are two different wire worlds:

* ``/ws/transcribe`` is the v1 transport. It admits by query parameter, has no
  handshake, and its session ids are compact 32 character hex strings.
* ``/ws/v2`` is the v2 transport. It admits by ``hello`` handshake, and its
  session ids are canonical hyphenated UUIDs.

Every test here is a *negative* one: it proves that a message, an identifier
or a protocol version of one world has no effect in the other. A leak in
either direction would let a client drive state through a contract the server
never validated for it, so these are boundary regressions rather than feature
tests.

The v1 alias cut of W1A is asserted here as well: after AP-SRV-070 both
transports answer to exactly the same four canonical actions, so the advertised
v1 vocabulary may no longer carry a deprecated spelling the v2 parser rejects.
"""

import json
import unittest
import uuid

from api_fastapi_server.protocol_v2 import identity, schema

try:
    from starlette.websockets import WebSocketDisconnect
except Exception:  # pragma: no cover - optional dependency
    class WebSocketDisconnect(Exception):
        code = None

from tests.unit.test_protocol_v2_e2e import V2Session, hello_message
from tests.unit.test_server_controlled_e2e import (
    ControlledSessionHarness,
    GateAwareRecorder,
    TestClient,
    build_app,
)


CONTROLLED = "manualTriggerEnabled=true&wakeWordTriggerEnabled=false"

#: A well formed v2 command envelope for every command type v2 accepts. None
#: of them may ever mean anything on the v1 wire.
def v2_envelopes():
    session_id = str(uuid.uuid4())
    common = {
        "protocolVersion": schema.PROTOCOL_VERSION,
        "sessionId": session_id,
    }
    return (
        dict(common, type=schema.ACTIVATION_COMMAND, commandId=str(uuid.uuid4()),
             action=schema.ACTIVATE, source=schema.MANUAL_SOURCE),
        dict(common, type=schema.TRIGGER_SUPPRESSION_SET,
             commandId=str(uuid.uuid4()), manual=True, wakeWord=False),
        dict(common, type=schema.AUDIO_AVAILABILITY_SET,
             commandId=str(uuid.uuid4()), audioAvailable=False),
        dict(common, type=schema.SESSION_SETTINGS_PATCH,
             commandId=str(uuid.uuid4()), settings={}),
        dict(common, type=schema.SESSION_SNAPSHOT_REQUEST,
             commandId=str(uuid.uuid4())),
    )


#: v1 wire messages that the v1 transport really implements. On v2 they are
#: unknown message types and must stay unanswered.
V1_WIRE_MESSAGES = (
    {"type": "trigger", "action": "activate", "source": "manual",
     "commandId": "v1-c-1"},
    {"type": "audio_availability", "audioAvailable": False,
     "commandId": "v1-c-2"},
    {"type": "start"},
    {"type": "stop"},
    {"type": "clear"},
    {"type": "ping"},
    {"type": "metrics"},
)


class BoundaryTestCase(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class V1RefusesV2EnvelopesTests(BoundaryTestCase):
    """Invariant 1: a v2 envelope is an unknown command on the v1 wire."""

    def test_every_v2_command_type_is_an_unknown_v1_command(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, CONTROLLED) as session:
                session.send({"type": "start"})
                for envelope in v2_envelopes():
                    with self.subTest(type=envelope["type"]):
                        session.send(envelope)
                        answer = session.drain("error")
                        self.assertEqual(answer["where"], "command")
                        self.assertEqual(
                            answer["message"],
                            f"Unbekannter Befehl: {envelope['type']}",
                        )
                        # The refusal is answered in the v1 session, never in
                        # the session the v2 envelope claimed.
                        self.assertEqual(
                            answer["sessionId"], session.hello["sessionId"]
                        )
                        self.assertNotEqual(
                            answer["sessionId"], envelope["sessionId"]
                        )

    def test_a_v2_activation_command_never_becomes_a_v1_activation(self):
        """The refusal must not be a state change with an error attached."""
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, CONTROLLED) as session:
                session.send({"type": "start"})
                envelope = v2_envelopes()[0]
                session.send(envelope)
                session.drain("error")
                # A round trip through a command the v1 wire *does* implement
                # flushes everything the server would still have to say.
                session.settle()
                self.assertEqual(
                    [m for m in session.messages
                     if m.get("type") == "trigger_ack"],
                    [],
                )
                self.assertEqual(
                    session.timeline_events("activation.started"), []
                )

    def test_a_v2_envelope_does_not_occupy_a_v1_command_id(self):
        """A refused foreign envelope must not eat a v1 replay slot."""
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, CONTROLLED) as session:
                session.send({"type": "start"})
                envelope = dict(v2_envelopes()[0], commandId="shared-id")
                session.send(envelope)
                session.drain("error")
                session.send({
                    "type": "trigger",
                    "action": "activate",
                    "source": "manual",
                    "commandId": "shared-id",
                })
                ack = session.drain("trigger_ack")
                self.assertEqual(ack["commandId"], "shared-id")
                self.assertTrue(
                    ack["accepted"],
                    "the v1 command id was consumed by a foreign envelope",
                )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class V2IgnoresV1WireMessagesTests(BoundaryTestCase):
    """Invariant 2: a v1 message is an unknown type on the v2 wire.

    The frozen wire schema forbids treating an unknown message type as a known
    state change, so the correct answer is *no* answer: no ack, no event, no
    version bump.
    """

    def test_v1_messages_are_neither_acknowledged_nor_effective(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                before = session.snapshot()
                for message in V1_WIRE_MESSAGES:
                    with self.subTest(type=message["type"]):
                        session.send_raw(dict(
                            message,
                            protocolVersion=schema.PROTOCOL_VERSION,
                            sessionId=session.session_id,
                        ))
                after = session.snapshot()
                for message_type in ("trigger_ack", "pong", "metrics",
                                     "audio_availability_ack", "error"):
                    self.assertEqual(
                        session.seen(message_type), [],
                        f"v2 answered a v1 message with {message_type}",
                    )
                for command_id in ("v1-c-1", "v1-c-2"):
                    self.assertEqual(
                        [
                            m for m in session.seen(schema.COMMAND_ACK)
                            if m.get("commandId") == command_id
                        ],
                        [],
                        "a v1 commandId was acknowledged on v2",
                    )
                self.assertEqual(
                    after["input"]["phase"], before["input"]["phase"]
                )
                self.assertEqual(
                    after["stateVersion"], before["stateVersion"],
                    "a v1 message moved the v2 state version",
                )

    def test_the_deprecated_v1_extend_spelling_is_unknown_on_both_wires(self):
        """W1A: after the alias cut neither transport knows ``extend``."""
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                _command_id, activate_ack = session.activate()
                sent = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": "extend",
                    "activationId": activate_ack["activationId"],
                })
                ack = session.ack(sent["commandId"])
                self.assertEqual(ack["result"], schema.RESULT_INVALID_PAYLOAD)
            with ControlledSessionHarness(client, CONTROLLED) as v1:
                v1.send({"type": "start"})
                v1.send({
                    "type": "trigger",
                    "action": "extend",
                    "source": "manual",
                    "commandId": "x-1",
                })
                v1_ack = v1.drain("trigger_ack")
                self.assertFalse(v1_ack["accepted"])
                self.assertEqual(v1_ack["reason"], "invalid_action")


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class SessionIdentityIsolationTests(BoundaryTestCase):
    """Invariant 3: the two id spellings are never mixed."""

    def test_the_two_transports_mint_different_id_shapes(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, CONTROLLED) as v1:
                v1_id = v1.hello["sessionId"]
            with V2Session(client) as v2:
                v2_id = v2.session_id
        self.assertEqual(len(v1_id), 32)
        self.assertFalse(schema.is_canonical_uuid(v1_id))
        self.assertTrue(schema.is_canonical_uuid(v2_id))
        self.assertNotEqual(v1_id, v2_id)

    def test_a_compact_v1_session_id_is_invalid_payload_on_v2(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, CONTROLLED) as v1:
                v1_id = v1.hello["sessionId"]
                with V2Session(client) as v2:
                    sent = v2.command({
                        "type": schema.ACTIVATION_COMMAND,
                        "sessionId": v1_id,
                        "action": schema.ACTIVATE,
                        "source": schema.MANUAL_SOURCE,
                    })
                    ack = v2.ack(sent["commandId"])
                    self.assertEqual(
                        ack["result"], schema.RESULT_INVALID_PAYLOAD
                    )
                    self.assertFalse(ack["accepted"])
                    # The ack answers in the v2 session, not the borrowed one.
                    self.assertEqual(ack["sessionId"], v2.session_id)
                    self.assertEqual(
                        v2.snapshot()["input"]["phase"], schema.IDLE
                    )

    def test_the_hyphenated_form_of_a_v1_id_is_still_a_foreign_session(self):
        """Reformatting at the boundary must not create a second identity."""
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, CONTROLLED) as v1:
                hyphenated = str(uuid.UUID(v1.hello["sessionId"]))
                with V2Session(client) as v2:
                    sent = v2.command({
                        "type": schema.ACTIVATION_COMMAND,
                        "sessionId": hyphenated,
                        "action": schema.ACTIVATE,
                        "source": schema.MANUAL_SOURCE,
                    })
                    ack = v2.ack(sent["commandId"])
                    self.assertEqual(
                        ack["result"], schema.RESULT_STALE_SESSION
                    )
                    self.assertFalse(ack["accepted"])

    def test_a_canonical_v2_session_id_does_not_steer_a_v1_command(self):
        with TestClient(self.app) as client:
            with V2Session(client) as v2:
                with ControlledSessionHarness(client, CONTROLLED) as v1:
                    v1.send({"type": "start"})
                    v1.send({
                        "type": "trigger",
                        "action": "activate",
                        "source": "manual",
                        "commandId": "c-1",
                        "sessionId": v2.session_id,
                    })
                    ack = v1.drain("trigger_ack")
                    self.assertEqual(ack["sessionId"], v1.hello["sessionId"])
                    self.assertNotEqual(ack["sessionId"], v2.session_id)
                # The v2 session never saw the v1 activation.
                self.assertEqual(v2.snapshot()["input"]["phase"], schema.IDLE)


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class ProtocolVersionBoundaryTests(BoundaryTestCase):
    """Invariant 4: an incompatible protocol version is deterministic."""

    def test_the_v2_endpoint_advertises_exactly_one_version(self):
        self.assertEqual(schema.SUPPORTED_PROTOCOL_VERSIONS, (2,))

    def test_a_v1_only_client_is_refused_with_protocol_incompatible(self):
        messages, close_code = self._handshake(hello_message(versions=(1,)))
        self.assertEqual(close_code, schema.CLOSE_PROTOCOL_INCOMPATIBLE)
        self.assertEqual(len(messages), 1)
        refusal = messages[0]
        self.assertEqual(refusal["type"], schema.PROTOCOL_INCOMPATIBLE)
        self.assertEqual(refusal["reason"], "no_common_protocol_version")
        self.assertEqual(refusal["supportedProtocolVersions"], [2])
        # A refused handshake must not leave a session behind.
        self.assertEqual(len(self.app.state.voicestt_service.sessions.all()), 0)

    def test_a_v1_protocol_version_on_a_v2_command_is_invalid_payload(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                sent = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "protocolVersion": 1,
                    "action": schema.ACTIVATE,
                    "source": schema.MANUAL_SOURCE,
                })
                ack = session.ack(sent["commandId"])
                self.assertEqual(ack["result"], schema.RESULT_INVALID_PAYLOAD)
                self.assertFalse(ack["accepted"])
                self.assertEqual(
                    session.snapshot()["input"]["phase"], schema.IDLE
                )

    def _handshake(self, first_message):
        messages = []
        close_code = None
        with TestClient(self.app) as client:
            with client.websocket_connect("/ws/v2") as socket:
                socket.send_text(json.dumps(first_message))
                try:
                    while True:
                        messages.append(socket.receive_json())
                except WebSocketDisconnect as disconnect:
                    close_code = disconnect.code
                except Exception:
                    pass
        return messages, close_code


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class ServerIdentityConsistencyTests(BoundaryTestCase):
    """Invariant 5: version, commit and protocol metadata never disagree."""

    def _identity_of(self, payload):
        return (payload["serverVersion"], payload["serverCommit"])

    def test_every_v2_wire_surface_publishes_the_same_identity(self):
        expected = (identity.server_version(), identity.server_commit())
        seen = {}
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                seen["hello.accepted"] = self._identity_of(session.accepted)
                seen["session.snapshot"] = self._identity_of(
                    session.snapshot()
                )
            incompatible, _ = ProtocolVersionBoundaryTests._handshake(
                self, hello_message(versions=(1,))
            )
            seen["protocol.incompatible"] = self._identity_of(incompatible[0])
            rejected, _ = ProtocolVersionBoundaryTests._handshake(
                self, hello_message(manual=False, wake_word=False)
            )
            seen["session.rejected"] = self._identity_of(rejected[0])
        for surface, published in seen.items():
            with self.subTest(surface=surface):
                self.assertEqual(published, expected)

    def test_the_rest_metadata_agrees_with_the_wire(self):
        expected = (identity.server_version(), identity.server_commit())
        with TestClient(self.app) as client:
            schema_payload = client.get("/api/v2/settings/schema").json()
            server_payload = client.get("/api/v2/settings/server").json()
        self.assertEqual(self._identity_of(schema_payload), expected)
        self.assertEqual(self._identity_of(server_payload), expected)
        self.assertEqual(
            schema_payload["protocolVersion"], schema.PROTOCOL_VERSION
        )
        self.assertIn(
            schema_payload["protocolVersion"],
            schema.SUPPORTED_PROTOCOL_VERSIONS,
        )

    def test_both_transports_advertise_the_same_activation_vocabulary(self):
        """W1A: the v1 capability surface has no vocabulary v2 rejects."""
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, CONTROLLED) as session:
                triggers = (
                    session.hello["sessionCapabilities"]["activationTriggers"]
                )
        self.assertEqual(
            tuple(triggers["actions"]), schema.ACTIVATION_ACTIONS
        )
        self.assertNotIn("deprecatedActionAliases", triggers)
        self.assertNotIn("retiredQueryParameters", triggers)
        self.assertNotIn(
            "extensionSeconds", triggers["queryParameters"]
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
