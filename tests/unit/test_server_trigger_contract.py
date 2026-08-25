"""AP3 – the WebSocket trigger contract, driven over a real WebSocket.

Every mandatory negative case of the specification is exercised through the
production entry point, not by assigning ``session._activation`` from the test.
The rule under test is: every syntactically valid command gets exactly one
deterministic, correlated answer - rejections included.
"""

import contextlib
import json
import unittest

from tests.unit.test_server_controlled_e2e import (
    ControlledSessionHarness,
    GateAwareRecorder,
    TestClient,
    build_app,
)


CONTROLLED = "manualTriggerEnabled=true&wakeWordTriggerEnabled=false"
BOTH = "manualTriggerEnabled=true&wakeWordTriggerEnabled=true"


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class TriggerAckContractTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    @contextlib.contextmanager
    def _streaming_session(self, client, query=CONTROLLED):
        """A connected session with the audio stream started.

        Deliberately a context manager rather than ``addCleanup``: cleanups run
        after the enclosing ``TestClient`` block has already shut down, and
        closing a WebSocket whose portal is gone blocks forever.
        """
        with ControlledSessionHarness(client, query) as session:
            session.send({"type": "start"})
            yield session

    def _trigger(self, session, **payload):
        payload.setdefault("type", "trigger")
        session.send(payload)
        return session.drain("trigger_ack")

    # -- the positive contract ----------------------------------------------

    def test_every_ack_carries_the_command_id_and_the_session_id(self):
        with TestClient(self.app) as client:
            with self._streaming_session(client) as session:
                ack = self._trigger(
                    session, action="activate", source="manual", commandId="c-1"
                )
                self.assertEqual(ack["type"], "trigger_ack")
                self.assertEqual(ack["commandId"], "c-1")
                self.assertEqual(ack["sessionId"], session.hello["sessionId"])
                self.assertTrue(ack["accepted"])
                self.assertTrue(ack["activationId"])

    def test_all_four_actions_are_answered(self):
        """AP-SRV-030 replaces the accepted ``extend`` of the AP-SRV-010 baseline.

        The former version pressed ``extend`` in ``waiting_first_speech`` and
        expected ``extended``. The frozen phase matrix answers ``refresh``
        there with ``invalid_phase`` (PHASE-03), so the positive refresh case
        moved to :class:`CommandPhaseMatrixTests`.
        """
        with TestClient(self.app) as client:
            with self._streaming_session(client) as session:
                first = self._trigger(
                    session, action="activate", source="manual", commandId="a-1"
                )
                refreshed = self._trigger(
                    session, action="refresh", source="manual", commandId="a-2"
                )
                self.assertFalse(refreshed["accepted"])
                self.assertEqual(refreshed["reason"], "invalid_phase")
                self.assertEqual(
                    refreshed["activationId"], first["activationId"]
                )

                finished = self._trigger(
                    session, action="finish", source="manual", commandId="a-3"
                )
                self.assertTrue(finished["accepted"])
                self.assertEqual(finished["reason"], "finished")

                cancelled = self._trigger(
                    session, action="cancel", source="manual", commandId="a-4"
                )
                self.assertFalse(cancelled["accepted"])
                self.assertEqual(cancelled["reason"], "not_active")

    # -- idempotency ---------------------------------------------------------

    def test_the_same_command_id_never_takes_effect_twice(self):
        with TestClient(self.app) as client:
            with self._streaming_session(client) as session:
                command = {
                    "action": "activate",
                    "source": "manual",
                    "commandId": "dup-1",
                }
                first = self._trigger(session, **command)
                repeated = self._trigger(session, **command)

                self.assertEqual(first, repeated, "the repeat ack must be identical")
                self.assertEqual(
                    repeated["activationId"],
                    first["activationId"],
                    "a repeat must not open a second activation",
                )
                # No second recording either: the gate still holds the first id.
                gate = session.recorder().controlled_activation_state()
                self.assertEqual(gate["activationId"], first["activationId"])

    def test_the_same_command_id_with_another_payload_is_rejected(self):
        with TestClient(self.app) as client:
            with self._streaming_session(client) as session:
                first = self._trigger(
                    session, action="activate", source="manual", commandId="conf-1"
                )
                conflicting = self._trigger(
                    session, action="cancel", source="manual", commandId="conf-1"
                )
                self.assertFalse(conflicting["accepted"])
                self.assertEqual(conflicting["reason"], "command_id_conflict")
                # The rejection is still correlated to the running activation.
                self.assertEqual(conflicting["activationId"], first["activationId"])
                self.assertTrue(
                    session.recorder().controlled_activation_state()["active"],
                    "a conflicting repeat must not cancel the activation",
                )

    # -- mandatory negative cases -------------------------------------------

    def test_a_missing_command_id_is_rejected(self):
        with TestClient(self.app) as client:
            with self._streaming_session(client) as session:
                ack = self._trigger(session, action="activate", source="manual")
                self.assertFalse(ack["accepted"])
                self.assertEqual(ack["reason"], "missing_command_id")

    def test_a_wrongly_typed_command_id_is_rejected(self):
        with TestClient(self.app) as client:
            with self._streaming_session(client) as session:
                ack = self._trigger(
                    session, action="activate", source="manual", commandId=17
                )
                self.assertFalse(ack["accepted"])
                self.assertEqual(ack["reason"], "invalid_command_id")

    def test_an_unknown_action_is_rejected(self):
        with TestClient(self.app) as client:
            with self._streaming_session(client) as session:
                ack = self._trigger(
                    session, action="teleport", source="manual", commandId="n-1"
                )
                self.assertFalse(ack["accepted"])
                self.assertEqual(ack["reason"], "invalid_action")
                self.assertEqual(ack["commandId"], "n-1")

    def test_a_wrongly_typed_action_is_rejected(self):
        with TestClient(self.app) as client:
            with self._streaming_session(client) as session:
                ack = self._trigger(
                    session, action=["activate"], source="manual", commandId="n-2"
                )
                self.assertFalse(ack["accepted"])
                self.assertEqual(ack["reason"], "invalid_action")

    def test_an_invalid_source_is_rejected(self):
        with TestClient(self.app) as client:
            with self._streaming_session(client) as session:
                ack = self._trigger(
                    session, action="activate", source="telepathy", commandId="n-3"
                )
                self.assertFalse(ack["accepted"])
                self.assertEqual(ack["reason"], "invalid_source")

    def test_a_disabled_source_is_rejected_with_its_own_reason(self):
        with TestClient(self.app) as client:
            # wake_word trigger is off in this session
            with self._streaming_session(client) as session:
                ack = self._trigger(
                    session, action="activate", source="wake_word", commandId="n-4"
                )
                self.assertFalse(ack["accepted"])
                self.assertEqual(ack["reason"], "trigger_disabled")

    def test_a_trigger_before_stream_start_is_rejected(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, CONTROLLED) as session:
                # deliberately no {"type": "start"}
                ack = self._trigger(
                    session, action="activate", source="manual", commandId="pre-1"
                )
                self.assertFalse(ack["accepted"])
                self.assertEqual(ack["reason"], "stream_not_started")
                self.assertFalse(
                    session.recorder().controlled_activation_state()["active"]
                )

    def test_a_trigger_after_stream_stop_is_rejected(self):
        with TestClient(self.app) as client:
            with self._streaming_session(client) as session:
                accepted = self._trigger(
                    session, action="activate", source="manual", commandId="post-1"
                )
                self.assertTrue(accepted["accepted"])

                session.send({"type": "stop"})
                session.settle()

                ack = self._trigger(
                    session, action="activate", source="manual", commandId="post-2"
                )
                self.assertFalse(ack["accepted"])
                self.assertEqual(ack["reason"], "stream_not_started")

    def test_malformed_json_is_answered_with_a_command_error(self):
        with TestClient(self.app) as client:
            with self._streaming_session(client) as session:
                session.socket.send_text("{not json")
                error = session.drain("error")
                self.assertEqual(error["where"], "command")

    def test_a_trigger_that_is_not_an_object_is_rejected(self):
        with TestClient(self.app) as client:
            with self._streaming_session(client) as session:
                session.socket.send_text(json.dumps(["trigger"]))
                error = session.drain("error")
                self.assertEqual(error["where"], "command")

    # -- legacy compatibility ------------------------------------------------

    def test_a_legacy_client_never_sends_a_trigger_and_keeps_working(self):
        """`start`/`stop` stay stream commands and are unaffected."""
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, "clientId=legacy-1") as session:
                self.assertEqual(
                    session.hello["activationConfig"]["mode"], "legacy"
                )
                session.send({"type": "start"})
                status = session.drain("status")
                self.assertEqual(status["state"], "listening")

                session.send({"type": "stop"})
                session.settle()

                # The legacy session has no controller at all.
                self.assertEqual(
                    session.recorder().controlled_activation_state()["policy"],
                    "legacy",
                )

    def test_an_unknown_command_still_reports_an_error(self):
        with TestClient(self.app) as client:
            with self._streaming_session(client) as session:
                session.send({"type": "teleport"})
                error = session.drain("error")
                self.assertEqual(error["where"], "command")


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class TriggerSourceMatrixTests(unittest.TestCase):
    """Both sources may drive the same activation when both are enabled."""

    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def test_wake_word_source_is_accepted_as_a_command_when_enabled(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, BOTH) as session:
                session.send({"type": "start"})
                session.send({
                    "type": "trigger",
                    "action": "activate",
                    "source": "wake_word",
                    "commandId": "ww-1",
                })
                ack = session.drain("trigger_ack")
                self.assertTrue(ack["accepted"])
                self.assertEqual(ack["reason"], "activated")

    def test_a_second_source_is_locked_to_the_first_activation(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, BOTH) as session:
                session.send({"type": "start"})
                session.send({
                    "type": "trigger",
                    "action": "activate",
                    "source": "manual",
                    "commandId": "m-1",
                })
                first = session.drain("trigger_ack")
                session.send({
                    "type": "trigger",
                    "action": "activate",
                    "source": "wake_word",
                    "commandId": "w-1",
                })
                locked = session.drain("trigger_ack")

                self.assertFalse(locked["accepted"])
                self.assertEqual(locked["reason"], "activation_locked")
                self.assertEqual(locked["activationId"], first["activationId"])


if __name__ == "__main__":
    unittest.main()
