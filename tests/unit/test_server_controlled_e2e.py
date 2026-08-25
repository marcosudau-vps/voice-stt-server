"""AP4 – end-to-end proof that the controlled trigger path is really wired.

The previous version of this file called itself E2E but never touched a
WebSocket, never went through query parsing or session admission, and drove the
gate with a recorder mock whose ``open_controlled_activation`` unconditionally
set an event. Its timeout test even closed the gate from inside the test and
then asserted that the gate was closed.

This version goes through the real production entry point:

    websocket_connect("/ws/transcribe?manualTriggerEnabled=…")
        -> parse_session_activation_query
        -> resolve_session_activation_config
        -> VoiceSTTService.admit_session
        -> RecorderBackedRealtimeSession
        -> handle_trigger_command
        -> ActivationController
        -> the real recorder gate module
        -> recorder callbacks back into the controller

The recorder is a fake, because a real one would need a microphone and models -
but it is a fake that uses the **real** gate functions from
``VoiceSTT.core.activation_control`` and asks the **real** VAD start condition
before it starts a recording. If the gate were not wired, speech would start a
recording without a trigger and these tests would fail.
"""

import json
import queue
import threading
import time
import unittest
import uuid
from unittest import mock

import numpy as np

from api_fastapi_server.protocol import encode_audio_packet
from api_fastapi_server.server import (
    ServerSettings,
    create_app,
)
from VoiceSTT.core.activation_control import (
    abort_controlled_activation_gate,
    close_controlled_activation_gate,
    configure_activation_policy,
    controlled_activation_snapshot,
    initialize_activation_control,
    open_controlled_activation_gate,
    recording_activation_gate_is_open,
    shutdown_controlled_activation_gate,
)

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - optional dependency
    TestClient = None

from tests.unit.test_fastapi_server_multi_user import AutoScheduler


SAMPLE_RATE = 16000


class GateAwareRecorder:
    """A recorder fake that obeys the real controlled activation gate.

    Only the audio hardware and the transcription model are faked. The gate
    itself is the production module, and ``feed_audio`` asks exactly the
    condition that ``run_recording_worker`` asks before it starts a segment.
    """

    instances = []

    def __init__(self, **kwargs):
        GateAwareRecorder.instances.append(self)
        self.kwargs = kwargs
        self.on_recording_start = kwargs.get("on_recording_start")
        self.on_recording_stop = kwargs.get("on_recording_stop")
        self.on_transcription_start = kwargs.get("on_transcription_start")
        self.on_wakeword_detected = kwargs.get("on_wakeword_detected")
        self.on_wakeword_timeout = kwargs.get("on_wakeword_timeout")
        self.on_wakeword_detection_start = kwargs.get("on_wakeword_detection_start")
        self.on_wakeword_detection_end = kwargs.get("on_wakeword_detection_end")
        self.on_vad_start = kwargs.get("on_vad_start")
        self.on_vad_stop = kwargs.get("on_vad_stop")
        self.on_vad_detect_start = kwargs.get("on_vad_detect_start")
        self.on_vad_detect_stop = kwargs.get("on_vad_detect_stop")
        self.transcription_executor = kwargs["transcription_executor"]
        self.realtime_transcription_executor = kwargs[
            "realtime_transcription_executor"
        ]

        self.audio_queue = queue.Queue()
        self.recorded_audio_queue = queue.Queue()
        self.final_text = queue.Queue()

        # Real gate state on a fake recorder.
        initialize_activation_control(self)

        self.use_wake_words = bool(kwargs.get("wake_words"))
        self.wake_word_timeout = kwargs.get("wake_word_timeout", 5.0)
        self.wakeword_detected = False
        self.wake_word_detect_time = 0
        # Legacy VAD authority is armed, so a missing gate would be visible:
        # without the controlled policy this recorder records on any speech.
        self.start_recording_on_voice_activity = True
        self.stop_recording_on_voice_deactivity = True
        self.is_recording = False
        self.is_shut_down = False
        self.has_audio = False

        self.recording_starts = 0
        self.recording_stops = 0

    # -- the production gate API --------------------------------------------

    def set_activation_policy(self, policy):
        return configure_activation_policy(self, policy)

    def open_controlled_activation(self, activation_id, replace=False, generation=None):
        return open_controlled_activation_gate(
            self, activation_id, replace=replace, generation=generation
        )

    def close_controlled_activation(self, activation_id=None, generation=None):
        return close_controlled_activation_gate(
            self, activation_id, generation=generation
        )

    def abort_controlled_activation(self):
        return abort_controlled_activation_gate(self)

    def controlled_activation_state(self):
        return controlled_activation_snapshot(self)

    # -- audio ---------------------------------------------------------------

    def feed_audio(self, samples, original_sample_rate=SAMPLE_RATE):
        """Speech arrives. Whether it may start a segment is the gate's call."""
        self.audio_queue.put(samples)
        self.has_audio = True
        if self.is_recording:
            return
        may_record = recording_activation_gate_is_open(
            self, wake_word_activation_delay_passed=True
        )
        if not may_record:
            return
        self.is_recording = True
        self.recording_starts += 1
        if self.on_recording_start:
            self.on_recording_start()

    def simulate_wake_word(self):
        """What the wake-word engine does: report a detection, nothing more."""
        self.wakeword_detected = True
        self.wake_word_detect_time = time.time()
        if self.on_wakeword_detected:
            self.on_wakeword_detected()

    def flush_buffered_audio(self, min_abs_level=50):
        if not self.is_recording:
            return False
        self.has_audio = False
        self.is_recording = False
        self.recording_stops += 1
        if self.on_recording_stop:
            self.on_recording_stop()

        def run_final():
            abort = (
                self.on_transcription_start(None)
                if self.on_transcription_start
                else False
            )
            if abort:
                self.final_text.put("")
                return
            try:
                result = self.transcription_executor.transcribe(
                    np.ones(32, dtype=np.float32), language="en", use_prompt=True
                )
            except RuntimeError:
                self.final_text.put("")
                return
            self.final_text.put(result.text)

        threading.Thread(target=run_final, daemon=True).start()
        return True

    def text(self):
        item = self.final_text.get()
        return "" if item is None else item

    def stop(self, *args, **kwargs):
        return self.flush_buffered_audio()

    def abort(self):
        abort_controlled_activation_gate(self)
        self.final_text.put("")

    def shutdown(self):
        shutdown_controlled_activation_gate(self)
        self.is_shut_down = True
        self.final_text.put(None)


class CountingScheduler(AutoScheduler):
    """Records every scheduler allocation so the invariant can be counted.

    ``ManualScheduler`` already keeps every submitted job in ``self.jobs``;
    this subclass only makes the instances reachable from a test, so that
    "Scheduler allocations = 1" can be asserted for real instead of inferred.
    """

    instances: list = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        CountingScheduler.instances.append(self)

    @classmethod
    def reset(cls):
        cls.instances = []

    @classmethod
    def jobs_for(cls, session_id, kind=None):
        found = []
        for scheduler in cls.instances:
            for job in scheduler.jobs:
                if job.session_id != session_id:
                    continue
                if kind is not None and job.kind != kind:
                    continue
                found.append(job)
        return found


def build_app(scheduler_factory=AutoScheduler):
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
    )
    return create_app(
        settings,
        scheduler_factory=scheduler_factory,
        recorder_factory=GateAwareRecorder,
    )


def speech_packet(seconds=0.2):
    frames = int(SAMPLE_RATE * seconds)
    samples = (
        np.sin(np.linspace(0, 40 * np.pi, frames)).astype(np.float32) * 0.5
    )
    pcm = (samples * 32767).astype("<i2")
    return encode_audio_packet(
        {
            "sampleRate": SAMPLE_RATE,
            "channels": 1,
            "format": "pcm_s16le",
            "frames": frames,
        },
        pcm.tobytes(),
    )


class ControlledSessionHarness:
    """Drives one real WebSocket session and collects what the server sends.

    Incoming messages are pulled by a background reader into a queue, so every
    wait in a test is bounded. A blocking ``receive_json`` would turn a missing
    server message into a hanging test instead of a failing one - which matters
    especially when these tests are checked by mutation.
    """

    def __init__(self, client, query):
        self.client = client
        self.query = query
        self.messages = []
        self._inbox = queue.Queue()
        self._reader = None
        self._closed = threading.Event()

    def __enter__(self):
        self._context = self.client.websocket_connect(
            f"/ws/transcribe?{self.query}"
        )
        self.socket = self._context.__enter__()
        self._reader = threading.Thread(target=self._read_forever, daemon=True)
        self._reader.start()
        self.hello = self.expect(timeout=10.0)
        return self

    def _read_forever(self):
        try:
            while not self._closed.is_set():
                self._inbox.put(self.socket.receive_json())
        except Exception:
            self._inbox.put(None)

    def __exit__(self, *exc):
        self._closed.set()
        return self._context.__exit__(*exc)

    def send(self, payload):
        self.socket.send_text(json.dumps(payload))

    def expect(self, timeout=15.0):
        try:
            message = self._inbox.get(timeout=timeout)
        except queue.Empty:
            raise AssertionError(f"no server message within {timeout}s")
        if message is None:
            raise AssertionError("the server closed the connection")
        self.messages.append(message)
        return message

    def drain(self, expected_type=None, timeout=15.0):
        """Reads until a message of ``expected_type`` arrives (or times out)."""
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(
                    f"no {expected_type} within {timeout}s; "
                    f"saw {[m.get('type') for m in self.messages[-8:]]}"
                )
            message = self.expect(timeout=remaining)
            if expected_type is None or message.get("type") == expected_type:
                return message

    def timeline(self, event, timeout=15.0):
        """Waits for one specific timeline event by name."""
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(
                    f"no timeline event {event!r} within {timeout}s; saw "
                    f"{[m.get('event') for m in self.timeline_events()]}"
                )
            message = self.drain("timeline", timeout=remaining)
            if message.get("event") == event:
                return message

    def settle(self, timeout=15.0):
        """Round-trips a cheap command so pending messages are all delivered."""
        self.send({"type": "metrics"})
        return self.drain("metrics", timeout=timeout)

    def timeline_events(self, name=None):
        return [
            message
            for message in self.messages
            if message.get("type") == "timeline"
            and (name is None or message.get("event") == name)
        ]

    def recorder(self):
        assert GateAwareRecorder.instances, "no recorder was created"
        return GateAwareRecorder.instances[-1]

    def server_session(self, app):
        """The live session object the server built for this connection."""
        session = app.state.voicestt_service.sessions.get(
            self.hello["sessionId"]
        )
        assert session is not None, "the server session is gone"
        return session


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class ControlledActivationEndToEndTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    # -- admission ----------------------------------------------------------

    def test_query_parameters_reach_the_session_and_announce_the_capability(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(
                client, "manualTriggerEnabled=true&wakeWordTriggerEnabled=false"
            ) as session:
                hello = session.hello
                self.assertEqual(hello["type"], "hello")
                activation = hello["activationConfig"]
                self.assertEqual(activation["mode"], "controlled")
                self.assertTrue(activation["manualTriggerEnabled"])
                self.assertFalse(activation["wakeWordTriggerEnabled"])

                capability = hello["sessionCapabilities"]["activationTriggers"]
                self.assertTrue(capability["supported"])
                self.assertEqual(capability["commandType"], "trigger")
                self.assertEqual(capability["ackType"], "trigger_ack")
                self.assertTrue(capability["commandIdIdempotent"])

    def test_a_session_without_trigger_parameters_stays_legacy(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, "clientId=legacy") as session:
                self.assertEqual(session.hello["activationConfig"]["mode"], "legacy")
                # A legacy client never sends `trigger`; if it did, it is told
                # that the controlled path is not active for this session.
                session.send({"type": "start"})
                session.send({
                    "type": "trigger",
                    "action": "activate",
                    "source": "manual",
                    "commandId": "legacy-1",
                })
                ack = session.drain("trigger_ack")
                self.assertFalse(ack["accepted"])
                self.assertEqual(ack["reason"], "controlled_activation_disabled")

    def test_both_triggers_disabled_is_rejected_at_admission(self):
        with TestClient(self.app) as client:
            with client.websocket_connect(
                "/ws/transcribe?manualTriggerEnabled=false&wakeWordTriggerEnabled=false"
            ) as socket:
                error = socket.receive_json()
                self.assertEqual(error["type"], "error")
                self.assertEqual(error["where"], "session_config")
                self.assertEqual(error["code"], "activation_trigger_required")

    def test_an_unparsable_trigger_flag_is_rejected_instead_of_silently_false(self):
        with TestClient(self.app) as client:
            with client.websocket_connect(
                "/ws/transcribe?manualTriggerEnabled=perhaps"
            ) as socket:
                error = socket.receive_json()
                self.assertEqual(error["code"], "invalid_activation_flag")
                self.assertEqual(error["field"], "manualTriggerEnabled")

    # -- the gate really gates ----------------------------------------------

    def test_speech_without_a_trigger_never_starts_a_recording(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(
                client, "manualTriggerEnabled=true&wakeWordTriggerEnabled=false"
            ) as session:
                session.send({"type": "start"})
                for _ in range(5):
                    session.socket.send_bytes(speech_packet())
                session.settle()

                recorder = session.recorder()
                self.assertEqual(
                    recorder.recording_starts,
                    0,
                    "the closed gate must block speech from starting a segment",
                )
                self.assertEqual(session.timeline_events("recording_started"), [])

    def test_manual_trigger_opens_the_gate_and_speech_then_records(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(
                client, "manualTriggerEnabled=true&wakeWordTriggerEnabled=false"
            ) as session:
                session.send({"type": "start"})
                session.send({
                    "type": "trigger",
                    "action": "activate",
                    "source": "manual",
                    "commandId": "cmd-1",
                })
                ack = session.drain("trigger_ack")
                self.assertTrue(ack["accepted"])
                self.assertEqual(ack["reason"], "activated")
                self.assertTrue(ack["activationId"])
                activation_id = ack["activationId"]

                recorder = session.recorder()
                gate = recorder.controlled_activation_state()
                self.assertEqual(gate["policy"], "controlled")
                self.assertTrue(gate["active"])
                self.assertEqual(gate["activationId"], activation_id)

                session.socket.send_bytes(speech_packet())
                started = session.timeline("recording_started")

                self.assertEqual(recorder.recording_starts, 1)
                self.assertEqual(started["activationId"], activation_id)
                self.assertEqual(started["primarySource"], "manual")
                self.assertEqual(started["sources"], ["manual"])

    def test_wake_word_reaches_the_recorder_only_through_the_controller(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(
                client,
                "manualTriggerEnabled=true&wakeWordTriggerEnabled=true",
            ) as session:
                session.send({"type": "start"})
                recorder = session.recorder()

                recorder.simulate_wake_word()
                detected = session.timeline("wakeword_detected")

                gate = recorder.controlled_activation_state()
                self.assertTrue(
                    gate["active"], "the wake word must open the shared gate"
                )
                self.assertTrue(gate["activationId"])

                session.socket.send_bytes(speech_packet())
                started = session.timeline("recording_started")
                self.assertEqual(started["primarySource"], "wake_word")
                self.assertEqual(recorder.recording_starts, 1)

    def test_wake_word_is_ignored_when_the_wake_word_trigger_is_disabled(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(
                client, "manualTriggerEnabled=true&wakeWordTriggerEnabled=false"
            ) as session:
                session.send({"type": "start"})
                recorder = session.recorder()
                recorder.simulate_wake_word()
                session.settle()

                self.assertFalse(
                    recorder.controlled_activation_state()["active"],
                    "a disabled wake word must not open the gate",
                )
                session.socket.send_bytes(speech_packet())
                session.settle()
                self.assertEqual(recorder.recording_starts, 0)


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class SingleFollowUpAuthorityTests(unittest.TestCase):
    """Only the ActivationController may own the follow-up window.

    ``_start_wakeword_followup_window`` is the legacy mechanism: it writes
    ``wakeword_detected`` and the VAD flags straight onto the recorder and
    starts a timer thread of its own. Running it next to the controller would
    give one session two follow-up authorities and two timers, which the
    specification forbids. So in the controlled mode it must not be reached at
    all - and this test pins the call site rather than the (environment
    dependent) effect, because the legacy function also has internal guards
    that could mask the mistake.
    """

    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def _record_a_segment(self, query):
        calls = []
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, query) as session:
                server_session = session.server_session(self.app)
                original = server_session._start_wakeword_followup_window

                def spy():
                    calls.append(True)
                    return original()

                server_session._start_wakeword_followup_window = spy

                session.send({"type": "start"})
                if "manualTriggerEnabled" in query:
                    session.send({
                        "type": "trigger",
                        "action": "activate",
                        "source": "manual",
                        "commandId": "follow-1",
                    })
                    self.assertTrue(session.drain("trigger_ack")["accepted"])

                session.socket.send_bytes(speech_packet())
                session.timeline("recording_started")

                recorder = session.recorder()
                recorder.flush_buffered_audio()
                session.timeline("recording_ended")
                session.settle()
        return calls

    def test_controlled_mode_never_starts_the_legacy_followup_window(self):
        calls = self._record_a_segment(
            "manualTriggerEnabled=true&wakeWordTriggerEnabled=false"
        )
        self.assertEqual(
            calls,
            [],
            "the legacy wake-word follow-up must not run beside the controller",
        )

    def test_legacy_mode_still_starts_the_legacy_followup_window(self):
        calls = self._record_a_segment("clientId=legacy-followup")
        self.assertEqual(
            len(calls),
            1,
            "legacy sessions must keep their existing follow-up behaviour",
        )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class TriggerCollisionEndToEndTests(unittest.TestCase):
    """GATE 4: for every collision, exactly one activation and one segment."""

    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    QUERY = "manualTriggerEnabled=true&wakeWordTriggerEnabled=true"

    def _collision(self, first, second):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                session.send({"type": "start"})
                recorder = session.recorder()

                acks = []
                for index, source in enumerate((first, second)):
                    if source == "manual":
                        session.send({
                            "type": "trigger",
                            "action": "activate",
                            "source": "manual",
                            "commandId": f"cmd-{index}",
                        })
                        acks.append(session.drain("trigger_ack"))
                    else:
                        recorder.simulate_wake_word()

                session.socket.send_bytes(speech_packet())
                started = session.timeline("recording_started")

                session.settle()

                activation_ids = {
                    message["activationId"]
                    for message in session.timeline_events()
                    if message.get("activationId")
                }
                starts = session.timeline_events("recording_started")

                self.assertEqual(
                    len(activation_ids),
                    1,
                    f"exactly one activation expected, got {activation_ids}",
                )
                self.assertEqual(
                    recorder.recording_starts,
                    1,
                    "a colliding trigger must not start a second recording",
                )
                self.assertEqual(len(starts), 1, "exactly one recording_started")
                self.assertEqual(started["primarySource"], first)
                self.assertEqual(
                    sorted(started["sources"]), sorted({first, second})
                )
                for ack in acks:
                    self.assertTrue(ack["accepted"])
                return session

    def test_manual_then_wake_word_stays_one_activation(self):
        self._collision("manual", "wake_word")

    def test_wake_word_then_manual_stays_one_activation(self):
        self._collision("wake_word", "manual")

    def test_repeated_manual_triggers_stay_one_activation(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                session.send({"type": "start"})
                ids = set()
                for index in range(5):
                    session.send({
                        "type": "trigger",
                        "action": "activate",
                        "source": "manual",
                        "commandId": f"repeat-{index}",
                    })
                    ack = session.drain("trigger_ack")
                    self.assertTrue(ack["accepted"])
                    ids.add(ack["activationId"])
                self.assertEqual(len(ids), 1, ids)

                session.socket.send_bytes(speech_packet())
                started = session.timeline("recording_started")
                self.assertEqual(session.recorder().recording_starts, 1)


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class CollisionMatrixEndToEndTests(unittest.TestCase):
    """GATE 4 – the full collision matrix, one separate E2E case each.

    For every case the four invariants of the specification are counted, not
    inferred:

    ```text
    Activations = 1
    Segments = 1
    Finals = 1
    Scheduler allocations = 1
    ```

    Double segments, double finals and double scheduler allocations are the
    central risks of this architecture, so each is measured on its own:
    activations from the distinct ``activationId`` values in the timeline,
    segments from the distinct ``segmentId`` values, finals from the published
    ``final`` messages, and scheduler allocations from the jobs the session
    actually handed to the scheduler.
    """

    QUERY = "manualTriggerEnabled=true&wakeWordTriggerEnabled=true"

    def setUp(self):
        GateAwareRecorder.instances = []
        CountingScheduler.reset()
        self.app = build_app(scheduler_factory=CountingScheduler)

    # -- helpers ------------------------------------------------------------

    def _fire(self, session, source, command_id):
        if source == "manual":
            session.send({
                "type": "trigger",
                "action": "activate",
                "source": "manual",
                "commandId": command_id,
            })
            return session.drain("trigger_ack")
        session.recorder().simulate_wake_word()
        return None

    def _run_turn(self, session):
        """One complete turn: speech, recording, stop, final."""
        session.socket.send_bytes(speech_packet())
        started = session.timeline("recording_started")
        session.recorder().flush_buffered_audio()
        session.timeline("recording_ended")
        final = session.drain("final", timeout=20.0)
        return started, final

    def _evidence(self, session, started, final):
        timeline = session.timeline_events()
        activation_ids = sorted(
            {m["activationId"] for m in timeline if m.get("activationId")}
        )
        segment_ids = sorted(
            {m["segmentId"] for m in session.messages if m.get("segmentId") is not None}
        )
        finals = [m for m in session.messages if m.get("type") == "final"]
        recording_starts = session.timeline_events("recording_started")
        session_id = session.hello["sessionId"]
        allocations = CountingScheduler.jobs_for(session_id, kind="final")
        return {
            "activationId": activation_ids,
            "primarySource": started.get("primarySource"),
            "sources": started.get("sources"),
            "segmentId": segment_ids,
            "recordingStarts": len(recording_starts),
            "recorderRecordingStarts": session.recorder().recording_starts,
            "finals": len(finals),
            "schedulerAllocations": len(allocations),
            "finalText": final.get("text"),
        }

    def _assert_invariants(self, evidence, first, second):
        self.assertEqual(
            len(evidence["activationId"]), 1,
            f"Activations must be 1, got {evidence['activationId']}",
        )
        self.assertEqual(
            len(evidence["segmentId"]), 1,
            f"Segments must be 1, got {evidence['segmentId']}",
        )
        self.assertEqual(
            evidence["finals"], 1,
            f"Finals must be 1, got {evidence['finals']}",
        )
        self.assertEqual(
            evidence["schedulerAllocations"], 1,
            "Scheduler allocations must be 1, got "
            f"{evidence['schedulerAllocations']}",
        )
        self.assertEqual(evidence["recordingStarts"], 1)
        self.assertEqual(evidence["recorderRecordingStarts"], 1)
        self.assertEqual(evidence["primarySource"], first)
        self.assertEqual(
            sorted(evidence["sources"] or []), sorted({first, second})
        )

    def _report(self, name, evidence):
        print(f"\n[GATE4 collision] {name}: {json.dumps(evidence, sort_keys=True)}")

    # -- the three mandatory cases -----------------------------------------

    def test_case_1_manual_then_wake_word(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                session.send({"type": "start"})
                self._fire(session, "manual", "c1-manual")
                self._fire(session, "wake_word", None)
                started, final = self._run_turn(session)
                evidence = self._evidence(session, started, final)
                self._report("manual -> wake_word", evidence)
                self._assert_invariants(evidence, "manual", "wake_word")

    def test_case_2_wake_word_then_manual(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                session.send({"type": "start"})
                self._fire(session, "wake_word", None)
                session.timeline("wakeword_detected")
                ack = self._fire(session, "manual", "c2-manual")
                self.assertTrue(ack["accepted"])
                self.assertEqual(
                    ack["reason"], "merged",
                    "the manual trigger must merge into the running activation",
                )
                started, final = self._run_turn(session)
                evidence = self._evidence(session, started, final)
                self._report("wake_word -> manual", evidence)
                self._assert_invariants(evidence, "wake_word", "manual")

    def test_case_3_near_simultaneous(self):
        """Both sources reach the server at the same time, for real.

        A plain "send both quickly" would almost never interleave inside the
        critical section. ``uuid4`` is called *inside* it when a new activation
        opens, so patching it to sleep widens the window: without correct
        serialisation both sources would open their own activation and the
        invariants below would fail.

        This is an E2E case over the real WebSocket, not a controller unit
        test: the manual trigger travels through the server's receive loop
        while the wake word arrives through the recorder callback.
        """
        real_uuid4 = uuid.uuid4

        def slow_uuid4():
            time.sleep(0.02)
            return real_uuid4()

        with mock.patch(
            "api_fastapi_server.activation.uuid.uuid4", side_effect=slow_uuid4
        ):
            with TestClient(self.app) as client:
                with ControlledSessionHarness(client, self.QUERY) as session:
                    session.send({"type": "start"})
                    session.settle()
                    recorder = session.recorder()

                    start = threading.Barrier(2)
                    errors = []

                    def wake_word():
                        try:
                            start.wait(timeout=10)
                            recorder.simulate_wake_word()
                        except Exception as exc:  # pragma: no cover
                            errors.append(exc)

                    thread = threading.Thread(target=wake_word)
                    thread.start()
                    start.wait(timeout=10)
                    session.send({
                        "type": "trigger",
                        "action": "activate",
                        "source": "manual",
                        "commandId": "c3-manual",
                    })
                    ack = session.drain("trigger_ack")
                    thread.join(timeout=10)
                    self.assertEqual(errors, [])
                    self.assertTrue(ack["accepted"])

                    started, final = self._run_turn(session)
                    evidence = self._evidence(session, started, final)
                    self._report("near simultaneous", evidence)

                    # Either source may win the race, so primarySource is not
                    # pinned here - but there must be exactly one activation
                    # and both sources must be recorded in it.
                    self.assertEqual(
                        len(evidence["activationId"]), 1,
                        f"Activations must be 1, got {evidence['activationId']}",
                    )
                    self.assertEqual(
                        len(evidence["segmentId"]), 1,
                        f"Segments must be 1, got {evidence['segmentId']}",
                    )
                    self.assertEqual(evidence["finals"], 1)
                    self.assertEqual(evidence["schedulerAllocations"], 1)
                    self.assertEqual(evidence["recordingStarts"], 1)
                    self.assertEqual(evidence["recorderRecordingStarts"], 1)
                    self.assertIn(
                        evidence["primarySource"], ("manual", "wake_word")
                    )
                    self.assertEqual(
                        sorted(evidence["sources"] or []),
                        ["manual", "wake_word"],
                        "both sources must be recorded in the one activation",
                    )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class ActivationTimeoutEndToEndTests(unittest.TestCase):
    """The timeout has to fire on its own - no help from the test."""

    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def test_the_server_closes_the_gate_on_its_own_after_the_timeout(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(
                client,
                "manualTriggerEnabled=true&wakeWordTriggerEnabled=false"
                "&initialSpeechTimeout=0.3",
            ) as session:
                session.send({"type": "start"})
                session.send({
                    "type": "trigger",
                    "action": "activate",
                    "source": "manual",
                    "commandId": "timeout-1",
                })
                ack = session.drain("trigger_ack")
                self.assertTrue(ack["accepted"])
                recorder = session.recorder()
                self.assertTrue(recorder.controlled_activation_state()["active"])

                closed = session.timeline("activation_closed", timeout=20.0)

                # Nothing in this test closed the gate; the server's own timer
                # did. That is the difference to the previous version.
                self.assertEqual(closed["reason"], "timed_out")
                self.assertFalse(
                    recorder.controlled_activation_state()["active"],
                    "the activation timeout must close the recorder gate",
                )

                # And afterwards speech must no longer record.
                session.socket.send_bytes(speech_packet())
                session.settle()
                self.assertEqual(recorder.recording_starts, 0)

    def test_a_timeout_does_not_end_an_activation_that_was_extended(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(
                client,
                "manualTriggerEnabled=true&wakeWordTriggerEnabled=false"
                "&initialSpeechTimeout=0.4&extensionSeconds=5",
            ) as session:
                session.send({"type": "start"})
                session.send({
                    "type": "trigger",
                    "action": "activate",
                    "source": "manual",
                    "commandId": "ext-1",
                })
                first = session.drain("trigger_ack")
                session.send({
                    "type": "trigger",
                    "action": "extend",
                    "source": "manual",
                    "commandId": "ext-2",
                })
                extended = session.drain("trigger_ack")
                self.assertTrue(extended["accepted"])
                self.assertEqual(extended["activationId"], first["activationId"])

                # Wait past the *original* deadline. The stale timer must not
                # end the extended activation.
                time.sleep(1.0)
                recorder = session.recorder()
                self.assertTrue(
                    recorder.controlled_activation_state()["active"],
                    "the extension must survive the original deadline",
                )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class ActivationLifecycleEndToEndTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    QUERY = "manualTriggerEnabled=true&wakeWordTriggerEnabled=false"

    def _activate(self, session, command_id="start-1"):
        session.send({"type": "start"})
        session.send({
            "type": "trigger",
            "action": "activate",
            "source": "manual",
            "commandId": command_id,
        })
        return session.drain("trigger_ack")

    def test_finish_closes_the_gate(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                self._activate(session)
                session.send({
                    "type": "trigger",
                    "action": "finish",
                    "source": "manual",
                    "commandId": "fin-1",
                })
                ack = session.drain("trigger_ack")
                self.assertTrue(ack["accepted"])
                self.assertEqual(ack["reason"], "finished")
                self.assertFalse(
                    session.recorder().controlled_activation_state()["active"]
                )

    def test_cancel_closes_the_gate(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                self._activate(session)
                session.send({
                    "type": "trigger",
                    "action": "cancel",
                    "source": "manual",
                    "commandId": "can-1",
                })
                ack = session.drain("trigger_ack")
                self.assertTrue(ack["accepted"])
                self.assertEqual(ack["reason"], "cancelled")
                self.assertFalse(
                    session.recorder().controlled_activation_state()["active"]
                )

    def test_stopping_the_stream_ends_the_activation(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as session:
                self._activate(session)
                recorder = session.recorder()
                self.assertTrue(recorder.controlled_activation_state()["active"])

                session.send({"type": "stop"})
                session.settle()

                self.assertFalse(
                    recorder.controlled_activation_state()["active"],
                    "an activation must not outlive its audio stream",
                )

    def test_a_reconnect_does_not_revive_the_previous_activation(self):
        with TestClient(self.app) as client:
            with ControlledSessionHarness(client, self.QUERY) as first:
                ack = self._activate(first, "recon-1")
                self.assertTrue(ack["accepted"])
                old_activation = ack["activationId"]
                old_recorder = first.recorder()

            # The socket is closed; the session is torn down.
            with ControlledSessionHarness(client, self.QUERY) as second:
                self.assertFalse(
                    old_recorder.controlled_activation_state()["active"],
                    "closing the session must close its gate",
                )
                second.send({"type": "start"})
                second.settle()
                new_recorder = second.recorder()
                self.assertIsNot(new_recorder, old_recorder)
                self.assertFalse(
                    new_recorder.controlled_activation_state()["active"],
                    "a fresh session must start without an activation",
                )

                ack = self._activate(second, "recon-2")
                self.assertNotEqual(ack["activationId"], old_activation)


if __name__ == "__main__":
    unittest.main()
