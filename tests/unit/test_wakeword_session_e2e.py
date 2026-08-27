"""AP-SRV-060 end to end: admission, snapshot, wake event and refresh races.

These tests drive a real ``/ws/v2`` session against the real catalog authority
and the real activation authority. Only the audio hardware and the
transcription model are faked.
"""

import threading
import unittest

from api_fastapi_server.protocol_v2 import schema

from .test_protocol_v2_e2e import V2Session, hello_message
from .test_server_controlled_e2e import GateAwareRecorder, TestClient, build_app


BUNDLED_WAKE_WORD = "hey_jarvis"


def wake_hello(ids=(BUNDLED_WAKE_WORD,), **kwargs):
    return hello_message(manual=True, wake_word=True, wake_word_ids=ids, **kwargs)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()
        service = self.app.state.voicestt_service
        if service.wakeword_catalog.snapshot() is None:
            self.skipTest(
                f"no bundled catalog: {service.wakeword_catalog.load_error}"
            )

    def test_a_bundled_wake_word_is_admitted_and_mirrored_in_the_snapshot(self):
        with TestClient(self.app) as client:
            with V2Session(client, hello=wake_hello()) as session:
                capabilities = session.accepted["snapshot"]["wakeWordCapabilities"]
        service = self.app.state.voicestt_service
        self.assertEqual(
            capabilities["catalogRevision"],
            service.wakeword_catalog.catalog_revision,
        )
        self.assertIn(BUNDLED_WAKE_WORD, capabilities["availableWakeWordIds"])

    def test_an_alias_is_admitted_through_the_one_resolver(self):
        with TestClient(self.app) as client:
            with V2Session(client, hello=wake_hello(("jarvis",))) as session:
                self.assertIsNotNone(session.session_id)

    def test_a_human_written_display_name_is_admitted(self):
        with TestClient(self.app) as client:
            with V2Session(client, hello=wake_hello(("Hey Jarvis",))) as session:
                self.assertIsNotNone(session.session_id)

    def test_one_unknown_id_rejects_the_whole_selection(self):
        with TestClient(self.app) as client:
            with V2Session(
                client,
                hello=wake_hello((BUNDLED_WAKE_WORD, "does_not_exist")),
                expect_accept=False,
            ) as session:
                payload = session.drain(schema.SESSION_REJECTED, timeout=15.0)

        self.assertEqual(payload["type"], schema.SESSION_REJECTED)
        errors = payload["errors"]
        self.assertEqual(
            {error["code"] for error in errors}, {"wake_word_unavailable"}
        )
        self.assertEqual(
            [error["wakeWordId"] for error in errors], ["does_not_exist"]
        )
        self.assertEqual([error["reason"] for error in errors], ["unknown"])

    def test_every_problematic_id_is_named_machine_readably(self):
        with TestClient(self.app) as client:
            with V2Session(
                client,
                hello=wake_hello(("nope_one", "nope_two")),
                expect_accept=False,
            ) as session:
                payload = session.drain(schema.SESSION_REJECTED, timeout=15.0)

        self.assertEqual(
            sorted(error["wakeWordId"] for error in payload["errors"]),
            ["nope_one", "nope_two"],
        )

    def test_an_empty_selection_with_wake_enabled_is_rejected(self):
        with TestClient(self.app) as client:
            with V2Session(
                client, hello=wake_hello(()), expect_accept=False
            ) as session:
                payload = session.drain(schema.SESSION_REJECTED, timeout=15.0)
        self.assertIn(
            "wake_word_selection_required",
            {error["code"] for error in payload["errors"]},
        )

    def test_only_the_admitted_models_are_configured_for_the_session(self):
        with TestClient(self.app) as client:
            with V2Session(client, hello=wake_hello()):
                recorder = GateAwareRecorder.instances[-1]
                selection = recorder.kwargs.get("wake_word_selection")

        self.assertIsNotNone(selection)
        self.assertEqual(selection.wake_word_ids, (BUNDLED_WAKE_WORD,))
        self.assertEqual(len(selection.model_paths), 1)


class WakeEventTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()
        service = self.app.state.voicestt_service
        if service.wakeword_catalog.snapshot() is None:
            self.skipTest("no bundled catalog")

    def _session_object(self):
        service = self.app.state.voicestt_service
        sessions = service.sessions.all()
        self.assertEqual(len(sessions), 1)
        return sessions[0]

    @staticmethod
    def _candidate(identifier=BUNDLED_WAKE_WORD, score=0.91):
        from VoiceSTT.core.wake_detection import RawWakeCandidate

        return RawWakeCandidate(
            canonical_wake_word_id=identifier,
            raw_score=score,
            frame_index=1,
            sample_position=32000,
            detector_generation=0,
            model_key=identifier,
        )

    def test_an_accepted_hit_publishes_exactly_one_wakeword_detected(self):
        with TestClient(self.app) as client:
            with V2Session(client, hello=wake_hello()) as session:
                domain = self._session_object()
                domain._wake_detection_epoch = domain._lifecycle_epoch
                detection = domain._on_wakeword_detected(self._candidate())
                self.assertIsNotNone(detection)
                event = session.drain(
                    schema.EVENT_WAKEWORD_DETECTED, timeout=15.0
                )

        self.assertEqual(event["wakeWordId"], BUNDLED_WAKE_WORD)
        self.assertEqual(event["score"], 0.91)
        self.assertEqual(event["primarySource"], schema.WAKE_WORD_SOURCE)
        self.assertEqual(event["activationId"], detection.activation_id)

    def test_a_repeated_hit_of_the_same_utterance_publishes_nothing(self):
        with TestClient(self.app) as client:
            with V2Session(client, hello=wake_hello()) as session:
                domain = self._session_object()
                domain._wake_detection_epoch = domain._lifecycle_epoch
                first = domain._on_wakeword_detected(self._candidate())
                self.assertIsNotNone(first)
                for _ in range(5):
                    self.assertIsNone(
                        domain._on_wakeword_detected(self._candidate())
                    )
                session.drain(schema.EVENT_WAKEWORD_DETECTED, timeout=15.0)
                events = [
                    message for message in session.messages
                    if message.get("type") == schema.EVENT_WAKEWORD_DETECTED
                ]
        self.assertEqual(len(events), 1)

    def test_a_wake_word_during_an_open_activation_has_no_effect(self):
        with TestClient(self.app) as client:
            with V2Session(client, hello=wake_hello()) as session:
                domain = self._session_object()
                domain._wake_detection_epoch = domain._lifecycle_epoch
                _command_id, ack = session.activate()
                self.assertTrue(ack["accepted"], ack)
                manual_activation = ack["activationId"]

                self.assertIsNone(
                    domain._on_wakeword_detected(self._candidate())
                )
                snapshot = session.snapshot()

        self.assertEqual(snapshot["input"]["activationId"], manual_activation)
        self.assertEqual(snapshot["input"]["primarySource"], "manual")
        wake_events = [
            message for message in session.messages
            if message.get("type") == schema.EVENT_WAKEWORD_DETECTED
        ]
        self.assertEqual(wake_events, [])

    def test_the_latch_is_released_at_the_safe_input_close(self):
        with TestClient(self.app) as client:
            with V2Session(client, hello=wake_hello()) as session:
                domain = self._session_object()
                domain._wake_detection_epoch = domain._lifecycle_epoch
                first = domain._on_wakeword_detected(self._candidate())
                self.assertIsNotNone(first)
                session.drain(schema.EVENT_WAKEWORD_DETECTED, timeout=15.0)

                sent = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": schema.FINISH,
                    "activationId": first.activation_id,
                })
                session.ack(sent["commandId"])
                session.drain(
                    schema.EVENT_ACTIVATION_INPUT_CLOSED, timeout=15.0
                )

                # Only now may a new utterance be admitted again.
                second = domain._on_wakeword_detected(self._candidate())
                self.assertIsNotNone(second)
                self.assertNotEqual(
                    second.activation_id, first.activation_id
                )
                second_event = session.drain(
                    schema.EVENT_WAKEWORD_DETECTED, timeout=15.0
                )
                events = session.collected(schema.EVENT_WAKEWORD_DETECTED)

        # One event per accepted utterance - two utterances, two events.
        self.assertEqual(len(events), 2)
        self.assertEqual(
            second_event["activationId"], second.activation_id
        )

    def test_a_stale_detector_callback_is_inert(self):
        with TestClient(self.app) as client:
            with V2Session(client, hello=wake_hello()) as session:
                domain = self._session_object()
                # No matching detection epoch: the callback belongs to an
                # earlier stream and must not open anything.
                domain._wake_detection_epoch = domain._lifecycle_epoch - 1
                self.assertIsNone(
                    domain._on_wakeword_detected(self._candidate())
                )
                snapshot = session.snapshot()
        self.assertEqual(snapshot["input"]["phase"], schema.IDLE)


class CatalogRefreshRaceTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()
        service = self.app.state.voicestt_service
        if service.wakeword_catalog.snapshot() is None:
            self.skipTest("no bundled catalog")

    def test_a_refresh_does_not_disturb_an_already_admitted_session(self):
        service = self.app.state.voicestt_service
        with TestClient(self.app) as client:
            with V2Session(client, hello=wake_hello()) as session:
                before = GateAwareRecorder.instances[-1].kwargs[
                    "wake_word_selection"
                ]
                result = service.refresh_wake_word_catalog()
                self.assertTrue(result.ok)
                after = GateAwareRecorder.instances[-1].kwargs[
                    "wake_word_selection"
                ]
                snapshot = session.snapshot()

        # The running session keeps exactly the models it was admitted with.
        self.assertIs(before, after)
        self.assertEqual(snapshot["input"]["phase"], schema.IDLE)

    def test_concurrent_refresh_and_admission_stay_consistent(self):
        service = self.app.state.voicestt_service
        for iteration in range(10):
            with self.subTest(iteration=iteration):
                barrier = threading.Barrier(2)
                outcome = {}

                def refresher():
                    barrier.wait(timeout=10)
                    outcome["refresh"] = service.refresh_wake_word_catalog()

                def admitter():
                    barrier.wait(timeout=10)
                    selection, errors = service.wakeword_catalog.resolve_selection(
                        [BUNDLED_WAKE_WORD]
                    )
                    outcome["selection"] = selection
                    outcome["errors"] = errors

                threads = [
                    threading.Thread(target=refresher),
                    threading.Thread(target=admitter),
                ]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=10)
                    self.assertFalse(thread.is_alive())

                self.assertTrue(outcome["refresh"].ok)
                self.assertEqual(outcome["errors"], ())
                self.assertEqual(
                    outcome["selection"].wake_word_ids, (BUNDLED_WAKE_WORD,)
                )

    def test_an_availability_change_reaches_live_sessions_as_an_event(self):
        service = self.app.state.voicestt_service
        with TestClient(self.app) as client:
            with V2Session(client, hello=wake_hello()) as session:
                result = service.wakeword_catalog.set_global_disabled(["alexa"])
                self.assertTrue(result.availability_changed)
                event = session.drain(
                    schema.EVENT_WAKEWORD_AVAILABILITY_CHANGED, timeout=15.0
                )

        self.assertEqual(event["catalogRevision"], result.catalog_revision)
        self.assertNotIn("alexa", event["availableWakeWordIds"])
        self.assertIn(BUNDLED_WAKE_WORD, event["availableWakeWordIds"])


if __name__ == "__main__":
    unittest.main()
