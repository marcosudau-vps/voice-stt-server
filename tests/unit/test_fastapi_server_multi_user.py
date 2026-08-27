import collections
import json
import os
import queue
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from starlette.websockets import WebSocketDisconnect

from api_fastapi_server.protocol import decode_audio_packet, encode_audio_packet
from api_fastapi_server.server import (
    create_app,
    InferenceJob,
    InferenceResult,
    QueueSubmitResult,
    RecorderBackedRealtimeSession,
    SessionWakeWordRequest,
    VoiceSTTService,
    SegmentState,
    ServerSettings,
    WARMUP_AUDIO_PATH,
    read_wav_float32,
)
from VoiceSTT.core.realtime_text_stabilizer import (
    RealtimeTextEvidenceDiagnostics,
    RealtimeTextObservationTiming,
    RealtimeTextStabilizationEvent,
)


class CollectingManager:
    def __init__(self):
        self.messages = collections.defaultdict(list)
        self.global_messages = []

    def bind_loop(self, loop):
        pass

    def publish_session(self, session_id, message):
        self.messages[session_id].append(message)

    def publish_all(self, message):
        self.global_messages.append(message)


class WarmupAudioPathTests(unittest.TestCase):
    def test_packaged_warmup_audio_exists_and_is_readable(self):
        self.assertEqual(WARMUP_AUDIO_PATH.parent.name, "assets")
        self.assertTrue(WARMUP_AUDIO_PATH.is_file(), WARMUP_AUDIO_PATH)
        audio = read_wav_float32(WARMUP_AUDIO_PATH)
        self.assertEqual(audio.sample_rate, 16000)
        self.assertGreater(audio.samples.size, 0)


class RecorderRealtimeStabilizationPayloadTests(unittest.TestCase):
    def test_structured_stabilization_event_publishes_split_realtime_fields(self):
        manager = CollectingManager()
        service = type("Service", (), {})()
        service.manager = manager
        service.settings = ServerSettings(realtime_callback="update")

        session = RecorderBackedRealtimeSession.__new__(RecorderBackedRealtimeSession)
        session.service = service
        session.settings = service.settings
        session.session_id = "session-a"
        session.segment_state = SegmentState()
        session.lock = threading.RLock()
        session.reject_current_recording = False

        event = RealtimeTextStabilizationEvent(
            recording_id=3,
            segment_id=7,
            sequence=11,
            accepted=True,
            ignored_reason=None,
            publish_allowed=True,
            should_publish=True,
            raw_observation_text="Hello world",
            stable_text="Hello",
            stable_delta="Hello",
            unstable_text=" world",
            display_text="Hello world",
            stable_normalized_offset=5,
            stable_raw_end_offset=5,
            stable_audio_end_sample_exclusive=None,
            has_new_stable_text=True,
            is_outlier=False,
            stable_prefix_conflict=False,
            commit_reason="evidence-threshold",
            evidence=RealtimeTextEvidenceDiagnostics(),
            timing=RealtimeTextObservationTiming(
                created_at_monotonic=1.0,
                completed_at_monotonic=1.2,
            ),
            trigger_reason="timer",
        )

        session._on_realtime_stabilization_event(event)

        [message] = manager.messages["session-a"]
        self.assertEqual(message["type"], "realtime")
        self.assertEqual(message["segmentId"], 7)
        self.assertEqual(message["recordingId"], 3)
        self.assertEqual(message["sequence"], 11)
        self.assertEqual(message["text"], "Hello world")
        self.assertEqual(message["rawText"], "Hello world")
        self.assertEqual(message["displayText"], "Hello world")
        self.assertEqual(message["stableText"], "Hello")
        self.assertEqual(message["stableDelta"], "Hello")
        self.assertEqual(message["unstableText"], " world")
        self.assertEqual(message["committedStableText"], "Hello")
        self.assertEqual(message["visualStableText"], "Hello")
        self.assertEqual(message["visualUnstableText"], " world")
        self.assertTrue(message["publicConsensusAligned"])
        self.assertFalse(message["isOutlier"])
        self.assertEqual(message["timing"]["completed_at_monotonic"], 1.2)

    def test_structured_stabilization_event_keeps_committed_stable_visible(self):
        manager = CollectingManager()
        service = type("Service", (), {})()
        service.manager = manager
        service.settings = ServerSettings(realtime_callback="update")

        session = RecorderBackedRealtimeSession.__new__(RecorderBackedRealtimeSession)
        session.service = service
        session.settings = service.settings
        session.session_id = "session-a"
        session.segment_state = SegmentState()
        session.lock = threading.RLock()
        session.reject_current_recording = False

        event = RealtimeTextStabilizationEvent(
            recording_id=3,
            segment_id=7,
            sequence=12,
            accepted=True,
            ignored_reason=None,
            publish_allowed=True,
            should_publish=True,
            raw_observation_text="I would think that the current approach",
            stable_text="I would think that the card",
            stable_delta="",
            unstable_text=" ... current approach",
            display_text="I would think that the card ... current approach",
            stable_normalized_offset=27,
            stable_raw_end_offset=27,
            stable_audio_end_sample_exclusive=None,
            has_new_stable_text=False,
            is_outlier=False,
            stable_prefix_conflict=True,
            commit_reason="none",
            evidence=RealtimeTextEvidenceDiagnostics(),
            timing=RealtimeTextObservationTiming(),
            trigger_reason="timer",
            consensus_text="I would think that the current approach",
            consensus_unstable_text="",
            consensus_display_text="I would think that the current approach",
            consensus_normalized_offset=39,
            public_consensus_aligned=False,
            internal_revision=True,
        )

        session._on_realtime_stabilization_event(event)

        [message] = manager.messages["session-a"]
        self.assertEqual(message["stableText"], "I would think that the card")
        self.assertEqual(
            message["visualStableText"],
            "I would think that the card",
        )
        self.assertEqual(message["committedStableText"], "I would think that the card")
        self.assertEqual(message["stableDelta"], "")
        self.assertEqual(
            message["unstableText"],
            " ... current approach",
        )
        self.assertEqual(
            message["displayText"],
            "I would think that the card ... current approach",
        )
        self.assertEqual(
            message["consensusDisplayText"],
            "I would think that the current approach",
        )
        self.assertFalse(message["publicConsensusAligned"])
        self.assertTrue(message["internalRevision"])


class ManualScheduler:
    def __init__(self, settings, result_callback, drop_callback=None, error_callback=None):
        self.settings = settings
        self.result_callback = result_callback
        self.drop_callback = drop_callback
        self.error_callback = error_callback
        self.jobs = []
        self.cancelled_sessions = []

    def start(self):
        pass

    def stop(self):
        pass

    def wait_ready(self, timeout=None):
        return True

    def healthy(self):
        return True

    def submit(self, job):
        self.jobs.append(job)
        return QueueSubmitResult(True)

    def cancel_session(self, session_id):
        self.cancelled_sessions.append(session_id)

    def snapshot(self):
        return {"jobs": len(self.jobs)}

    def complete(self, job, text=None, error=None, delay=0.001):
        started_at = job.created_at + delay
        completed_at = started_at + delay
        self.result_callback(
            InferenceResult(
                request_id=job.request_id,
                session_id=job.session_id,
                kind=job.kind,
                segment_id=job.segment_id,
                sequence=job.sequence,
                generation=job.generation,
                text=text if text is not None else f"{job.kind}-{job.session_id}",
                error=error,
                created_at=job.created_at,
                started_at=started_at,
                completed_at=completed_at,
                queue_delay=max(0.0, started_at - job.created_at),
                inference_duration=max(0.0, completed_at - started_at),
                total_latency=max(0.0, completed_at - job.created_at),
            )
        )


class AutoScheduler(ManualScheduler):
    def submit(self, job):
        result = super().submit(job)
        threading.Thread(
            target=self.complete,
            args=(job, f"{job.kind}-{job.session_id}"),
            daemon=True,
        ).start()
        return result


class FakeRecorder:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        FakeRecorder.instances.append(self)
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
        self.realtime_callback = (
            kwargs.get("on_realtime_transcription_update")
            or kwargs.get("on_realtime_transcription_stabilized")
        )
        self.transcription_executor = kwargs["transcription_executor"]
        self.realtime_transcription_executor = kwargs["realtime_transcription_executor"]
        self.audio_queue = queue.Queue()
        self.recorded_audio_queue = queue.Queue()
        self.final_text = queue.Queue()
        self.wake_word_timeout = kwargs.get("wake_word_timeout", 5.0)
        self.wakeword_detected = False
        self.wake_word_detect_time = 0
        self.start_recording_on_voice_activity = False
        self.stop_recording_on_voice_deactivity = False
        self.is_recording = False
        self.is_shut_down = False
        self.has_audio = False

    def feed_audio(self, samples, original_sample_rate=16000):
        self.audio_queue.put(samples)
        self.has_audio = True
        if not self.is_recording:
            self.is_recording = True
            if self.on_recording_start:
                self.on_recording_start()

        def run_realtime():
            try:
                result = self.realtime_transcription_executor.transcribe(samples, language="en", use_prompt=True)
            except RuntimeError:
                return
            if self.realtime_callback and result.text:
                self.realtime_callback(result.text)

        threading.Thread(target=run_realtime, daemon=True).start()

    def flush_buffered_audio(self):
        if not self.has_audio:
            return False
        self.has_audio = False
        self.is_recording = False
        if self.on_recording_stop:
            self.on_recording_stop()

        def run_final():
            abort = self.on_transcription_start(None) if self.on_transcription_start else False
            if abort:
                self.final_text.put("")
                return
            try:
                result = self.transcription_executor.transcribe(np.ones(32, dtype=np.float32), language="en", use_prompt=True)
            except RuntimeError:
                self.final_text.put("")
                return
            self.final_text.put(result.text)

        threading.Thread(target=run_final, daemon=True).start()
        return True

    def text(self):
        item = self.final_text.get()
        if item is None:
            return ""
        return item

    def abort(self):
        self.final_text.put("")

    def stop(self):
        return self.flush_buffered_audio()

    def shutdown(self):
        self.is_shut_down = True
        self.final_text.put(None)


def make_service(**overrides):
    model_warmup = overrides.pop("model_warmup", False)
    overrides.setdefault("request_logging_enabled", False)
    overrides.setdefault("performance_logging_enabled", False)
    overrides.setdefault("performance_log_mirror_enabled", False)
    overrides.setdefault("transcription_logging_enabled", False)
    overrides.setdefault("system_event_logging_enabled", False)
    overrides.setdefault("event_store_enabled", False)
    overrides.setdefault("log_live_enabled", False)
    settings = ServerSettings(
        model_warmup=model_warmup,
        realtime_processing_pause=0.0,
        realtime_min_audio_seconds=0.01,
        min_length_of_recording=0.0,
        post_speech_silence_duration=60.0,
        vad_energy_threshold=1.0,
        webrtc_sensitivity=99,
        **overrides,
    )
    manager = CollectingManager()
    service = VoiceSTTService(
        settings,
        manager,
        scheduler_factory=ManualScheduler,
        recorder_factory=FakeRecorder,
    )
    return service, manager


def audio_packet(level=2000, frames=640, sample_rate=16000):
    samples = np.full(frames, level, dtype=np.int16)
    return decode_audio_packet(encode_audio_packet(
        {"sampleRate": sample_rate, "channels": 1, "format": "pcm_s16le", "frames": frames},
        samples.tobytes(),
    ))


class FastAPIMultiUserSessionTests(unittest.TestCase):
    def setUp(self):
        FakeRecorder.instances.clear()

    def test_live_log_configuration_requires_sqlite_but_not_jsonl_mirrors(self):
        with self.assertRaisesRegex(ValueError, "event_store_enabled"):
            ServerSettings(event_store_enabled=False, log_live_enabled=True)
        settings = ServerSettings(
            event_store_enabled=True,
            transcription_logging_enabled=False,
            log_live_enabled=True,
        )
        self.assertTrue(settings.log_live_enabled)

        service, _ = make_service()
        result = service.update_settings({"log_live_enabled": True})
        self.assertNotIn("log_live_enabled", result["applied"])
        self.assertEqual(
            result["rejected"]["log_live_enabled"]["reason"],
            "invalid_dependency",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            persisted_settings = ServerSettings(
                model_warmup=False,
                data_root_path=temp_dir,
            )
            runtime_path = Path(persisted_settings.runtime_config_path)
            runtime_path.parent.mkdir(parents=True, exist_ok=True)
            runtime_path.write_text(
                json.dumps({
                    "event_store_enabled": False,
                    "log_live_enabled": True,
                }),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "event_store_enabled"):
                create_app(
                    persisted_settings,
                    scheduler_factory=AutoScheduler,
                    recorder_factory=FakeRecorder,
                )

        for mode in ("off", "summary", "events"):
            self.assertEqual(
                ServerSettings(realtime_log_detail=mode.upper()).realtime_log_detail,
                mode,
            )
        with self.assertRaisesRegex(ValueError, "off, summary oder events"):
            ServerSettings(realtime_log_detail="verbose")

    def test_performance_source_switch_controls_service_generation_and_runtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service, _ = make_service(
                data_root_path=temp_dir,
                event_store_enabled=True,
                performance_logging_enabled=False,
                performance_log_mirror_enabled=False,
            )

            self.assertIsNone(service.performance.event(
                "source.disabled_test",
                model="small",
            ))
            service.events.flush()
            self.assertEqual(
                service.events.query(channels={"performance"}),
                [],
            )

            result = service.update_settings({
                "performance_logging_enabled": True,
            })
            self.assertTrue(
                result["applied"]["performance_logging_enabled"]["value"]
            )
            self.assertIsNotNone(service.performance.event(
                "source.enabled_test",
                model="small",
            ))
            service.events.flush()
            self.assertEqual(
                [
                    event["event"]
                    for event in service.events.query(
                        channels={"performance"},
                    )
                ],
                ["source.enabled_test"],
            )
            service.stop()

    def test_sessions_receive_only_their_own_final_transcripts(self):
        service, manager = make_service()
        first = service.admit_session("first")
        second = service.admit_session("second")

        first.start_streaming()
        second.start_streaming()
        self.assertTrue(first.ingest_audio_packet(audio_packet(level=2000))[0])
        self.assertTrue(second.ingest_audio_packet(audio_packet(level=3000))[0])
        first.stop_streaming()
        second.stop_streaming()

        self._wait_for(lambda: len([job for job in service.scheduler.jobs if job.kind == "final"]) >= 2)
        final_jobs = [job for job in service.scheduler.jobs if job.kind == "final"]
        self.assertEqual({job.session_id for job in final_jobs}, {"first", "second"})

        for job in final_jobs:
            service.scheduler.complete(job, text=f"private-{job.session_id}")

        self._wait_for(lambda: any(msg.get("type") == "final" for msg in manager.messages["first"]))
        self._wait_for(lambda: any(msg.get("type") == "final" for msg in manager.messages["second"]))

        first_finals = [msg for msg in manager.messages["first"] if msg.get("type") == "final"]
        second_finals = [msg for msg in manager.messages["second"] if msg.get("type") == "final"]

        self.assertEqual([msg["text"] for msg in first_finals], ["private-first"])
        self.assertEqual([msg["text"] for msg in second_finals], ["private-second"])
        self.assertNotIn("private-second", [msg.get("text") for msg in manager.messages["first"]])
        self.assertNotIn("private-first", [msg.get("text") for msg in manager.messages["second"]])

    def test_clear_resets_only_one_session_and_discards_old_results(self):
        service, manager = make_service()
        first = service.admit_session("first")
        second = service.admit_session("second")

        for session in (first, second):
            session.start_streaming()
            session.ingest_audio_packet(audio_packet())
            session.stop_streaming()

        self._wait_for(lambda: len([job for job in service.scheduler.jobs if job.kind == "final"]) >= 2)
        first_final = next(job for job in service.scheduler.jobs if job.kind == "final" and job.session_id == "first")
        second_final = next(job for job in service.scheduler.jobs if job.kind == "final" and job.session_id == "second")

        first.clear()
        service.scheduler.complete(first_final, text="old-first")
        service.scheduler.complete(second_final, text="still-second")
        self._wait_for(lambda: any(msg.get("text") == "still-second" for msg in manager.messages["second"]))

        self.assertTrue(any(msg.get("type") == "clear" for msg in manager.messages["first"]))
        self.assertFalse(any(msg.get("type") == "clear" for msg in manager.messages["second"]))
        self.assertFalse(any(msg.get("text") == "old-first" for msg in manager.messages["first"]))
        self.assertTrue(any(msg.get("text") == "still-second" for msg in manager.messages["second"]))

    def test_stale_final_text_from_previous_generation_is_not_published(self):
        service, manager = make_service()
        session = service.admit_session("first")
        stale_generation = session.generation

        session.clear()
        published = session._publish_final_text("old-final", stale_generation)

        self.assertFalse(published)
        self.assertFalse(any(msg.get("text") == "old-final" for msg in manager.messages["first"]))

    def test_empty_final_text_emits_one_discard_terminal_without_final_frame(self):
        service, manager = make_service()
        session = service.admit_session("first")
        emitted = []
        session._emit_realtime_summary = lambda *args, **kwargs: None
        session._emit_structured_event = (
            lambda channel, event, **fields: emitted.append(
                {"channel": channel, "event": event, **fields}
            )
        )

        segment_id = session.segment_state.current()
        published = session._publish_discarded_empty_final(
            session.generation,
            expected_segment_id=segment_id,
        )

        self.assertTrue(published)
        self.assertEqual(
            [event["event"] for event in emitted],
            ["transcription.discarded", "activation.drained"],
        )
        self.assertEqual(emitted[0]["reason"], "empty_final")
        self.assertEqual(emitted[0]["segment_id"], 1)
        self.assertFalse(any(
            message.get("type") == "final"
            for message in manager.messages["first"]
        ))
        discarded = [
            message
            for message in manager.messages["first"]
            if message.get("type") == "timeline"
            and message.get("event") == "final_transcript_discarded"
        ]
        self.assertEqual(len(discarded), 1)
        self.assertEqual(discarded[0]["reason"], "empty_final")

        self.assertFalse(session._publish_discarded_empty_final(
            session.generation,
            expected_segment_id=segment_id,
        ))
        self.assertEqual(len(emitted), 2)
        self.assertEqual(len([
            message
            for message in manager.messages["first"]
            if message.get("event") == "final_transcript_discarded"
        ]), 1)

        stale_generation = session.generation
        session.clear()
        self.assertFalse(
            session._publish_discarded_empty_final(stale_generation)
        )
        self.assertEqual(len(emitted), 2)

    def test_session_publishes_cross_activation_finals_by_segment_sequence(self):
        service, manager = make_service()
        session = service.admit_session("ordered")
        ledger = session.segment_ledger
        ledger.open_activation("activation-1", 1, {"language": "en"})
        first = ledger.accept_segment("activation-1", 11)
        ledger.close_activation("activation-1", "finished")
        ledger.open_activation("activation-2", 2, {"language": "de"})
        second = ledger.accept_segment("activation-2", 12)
        ledger.close_activation("activation-2", "finished")

        self.assertTrue(session._publish_final_text("second", context=second))
        self.assertEqual(
            [item for item in manager.messages["ordered"] if item.get("type") == "final"],
            [],
        )
        self.assertTrue(session._publish_final_text("first", context=first))

        finals = [
            item for item in manager.messages["ordered"]
            if item.get("type") == "final"
        ]
        self.assertEqual([item["text"] for item in finals], ["first", "second"])
        self.assertEqual([item["segmentSequence"] for item in finals], [1, 2])
        self.assertEqual(
            [item["activationId"] for item in finals],
            ["activation-1", "activation-2"],
        )
        self.assertEqual(session.segment_ledger.snapshot()["pendingSegmentCount"], 0)

    def test_parallel_ledger_updates_dispatch_finals_and_terminals_in_order(self):
        service, manager = make_service()
        session = service.admit_session("parallel-order")
        ledger = session.segment_ledger
        ledger.open_activation("activation-1", 1)
        first = ledger.accept_segment("activation-1", 1)
        ledger.close_activation("activation-1", "finished")
        ledger.open_activation("activation-2", 2)
        second = ledger.accept_segment("activation-2", 2)
        ledger.close_activation("activation-2", "finished")

        first_apply_entered = threading.Event()
        release_first_apply = threading.Event()
        second_started = threading.Event()
        original_apply = session._apply_ledger_update
        apply_calls = 0
        apply_lock = threading.Lock()

        def block_first_apply(update):
            nonlocal apply_calls
            with apply_lock:
                apply_calls += 1
                call_number = apply_calls
            if call_number == 1:
                first_apply_entered.set()
                self.assertTrue(release_first_apply.wait(timeout=5.0))
            original_apply(update)

        session._apply_ledger_update = block_first_apply
        outcomes = []

        def publish(context, text):
            if context is second:
                second_started.set()
            outcomes.append(session._publish_final_text(text, context=context))

        first_thread = threading.Thread(target=publish, args=(first, "first"))
        second_thread = threading.Thread(target=publish, args=(second, "second"))
        first_thread.start()
        self.assertTrue(first_apply_entered.wait(timeout=5.0))
        second_thread.start()
        self.assertTrue(second_started.wait(timeout=5.0))

        try:
            # At the old boundary thread 2 could now publish before thread 1.
            # The dispatch lock keeps both its ledger mutation and output pending.
            time.sleep(0.05)
            self.assertEqual(manager.messages["parallel-order"], [])
        finally:
            release_first_apply.set()
            first_thread.join(timeout=5.0)
            second_thread.join(timeout=5.0)

        self.assertFalse(first_thread.is_alive())
        self.assertFalse(second_thread.is_alive())
        self.assertEqual(outcomes, [True, True])
        messages = manager.messages["parallel-order"]
        finals = [item for item in messages if item.get("type") == "final"]
        self.assertEqual([item["text"] for item in finals], ["first", "second"])
        self.assertEqual(
            [item["segmentSequence"] for item in finals],
            [1, 2],
        )
        observable = [
            (item.get("type"), item.get("event"), item.get("segmentSequence"))
            for item in messages
            if item.get("type") == "final"
            or item.get("event") == "activation_drained"
        ]
        self.assertEqual(
            observable,
            [
                ("final", None, 1),
                ("timeline", "activation_drained", None),
                ("final", None, 2),
                ("timeline", "activation_drained", None),
            ],
        )

    def test_recorded_audio_queue_trim_terminalizes_its_exact_context(self):
        service, manager = make_service(max_final_queue_depth_per_session=0)
        session = service.admit_session("trimmed")
        ledger = session.segment_ledger
        ledger.open_activation("activation", 1)
        context = ledger.accept_segment("activation", 4)
        ledger.close_activation("activation", "finished")
        session.recorder.recorded_audio_queue.put({
            "frames": [b"audio"],
            "segment_context": context,
        })

        self.assertEqual(session._trim_recorded_audio_queue(), 1)

        snapshot = ledger.snapshot()
        self.assertEqual(snapshot["pendingSegmentCount"], 0)
        self.assertEqual(snapshot["terminalSegmentCount"], 1)
        terminals = [
            item for item in manager.messages["trimmed"]
            if item.get("event") == "final_transcript_discarded"
        ]
        self.assertEqual(len(terminals), 1)
        self.assertEqual(terminals[0]["requestId"], context.request_id)

    def test_scheduler_reject_and_duplicate_drop_terminalize_once(self):
        service, manager = make_service()
        session = service.admit_session("rejected")
        ledger = session.segment_ledger
        ledger.open_activation("activation", 1)
        context = ledger.accept_segment("activation", 3)
        ledger.close_activation("activation", "finished")
        job = InferenceJob(
            request_id=context.request_id,
            session_id="rejected",
            kind="final",
            audio=np.ones(4, dtype=np.float32),
            language="en",
            use_prompt=True,
            segment_id=context.segment_id,
            sequence=0,
            generation=0,
            created_at=time.monotonic(),
            segment_context=context,
        )

        session.on_submit_result(job, QueueSubmitResult(False, "final queue full"))
        session.on_job_dropped(job, "cancelled")

        failed = [
            item for item in manager.messages["rejected"]
            if item.get("event") == "final_transcript_failed"
        ]
        cancelled = [
            item for item in manager.messages["rejected"]
            if item.get("event") == "final_transcript_cancelled"
        ]
        self.assertEqual(len(failed), 1)
        self.assertEqual(cancelled, [])
        self.assertEqual(ledger.snapshot()["pendingSegmentCount"], 0)

    def test_worker_exception_terminalizes_the_submitted_segment_once(self):
        service, manager = make_service()
        session = service.admit_session("worker-error")
        session.start_streaming()
        session.ingest_audio_packet(audio_packet())
        session.recorder.flush_buffered_audio()
        self._wait_for(
            lambda: any(job.kind == "final" for job in service.scheduler.jobs)
        )
        job = next(job for job in service.scheduler.jobs if job.kind == "final")

        service.scheduler.complete(job, text="", error="engine exploded")
        self._wait_for(lambda: any(
            item.get("event") == "final_transcript_failed"
            for item in manager.messages["worker-error"]
        ))

        failed = [
            item for item in manager.messages["worker-error"]
            if item.get("event") == "final_transcript_failed"
        ]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["requestId"], job.request_id)
        self.assertEqual(session.segment_ledger.snapshot()["pendingSegmentCount"], 0)

    def test_session_close_cancels_every_pending_segment_without_leaks(self):
        service, manager = make_service()
        session = service.admit_session("closing")
        ledger = session.segment_ledger
        ledger.open_activation("first", 1)
        first = ledger.accept_segment("first", 1)
        ledger.close_activation("first", "finished")
        ledger.open_activation("second", 2)
        second = ledger.accept_segment("second", 2)

        session.close()

        cancelled = [
            item for item in manager.messages["closing"]
            if item.get("event") == "final_transcript_cancelled"
        ]
        self.assertEqual(
            {item["requestId"] for item in cancelled},
            {first.request_id, second.request_id},
        )
        snapshot = ledger.snapshot()
        self.assertEqual(snapshot["pendingSegmentCount"], 0)
        self.assertEqual(snapshot["pendingActivationCount"], 0)

    def test_duplicate_empty_recorder_results_terminalize_started_segment_once(self):
        service, manager = make_service()
        session = service.admit_session("first")
        emitted = []
        session._emit_realtime_summary = lambda *args, **kwargs: None
        session._emit_structured_event = (
            lambda channel, event, **fields: emitted.append(
                {"channel": channel, "event": event, **fields}
            )
        )

        self.assertFalse(session._on_transcription_start(None))
        session.recorder.final_text.put("")
        session.recorder.final_text.put("")

        self._wait_for(lambda: len([
            event
            for event in emitted
            if event["event"] == "transcription.discarded"
        ]) >= 1)
        time.sleep(0.05)

        discarded = [
            event
            for event in emitted
            if event["event"] == "transcription.discarded"
        ]
        timeline_terminals = [
            message
            for message in manager.messages["first"]
            if message.get("type") == "timeline"
            and message.get("event") == "final_transcript_discarded"
        ]
        self.assertEqual(
            [(event["event"], event["segment_id"]) for event in discarded],
            [("transcription.discarded", 1)],
        )
        self.assertEqual(
            [(event["event"], event["segmentId"]) for event in timeline_terminals],
            [("final_transcript_discarded", 1)],
        )
        self.assertEqual(session.segment_state.current(), 2)
        session.close()

    def test_empty_final_result_loses_disconnect_race_without_terminal_event(self):
        service, manager = make_service()
        session = service.admit_session("first")
        emitted = []
        session._emit_structured_event = (
            lambda channel, event, **fields: emitted.append(event)
        )
        generation = session.generation
        segment_id = session.segment_state.current()

        session.close()

        self.assertFalse(session._publish_discarded_empty_final(
            generation,
            expected_segment_id=segment_id,
        ))
        self.assertEqual(emitted, [])
        self.assertFalse(any(
            message.get("event") == "final_transcript_discarded"
            for message in manager.messages["first"]
        ))

    def test_realtime_log_detail_modes_control_generation_before_event_hub(self):
        expected = {
            "off": set(),
            "summary": {"transcription.performance_summary"},
            "events": {
                "transcription.realtime_emitted",
                "transcription.performance_summary",
            },
        }

        for mode, expected_detail_events in expected.items():
            with self.subTest(mode=mode):
                service, _ = make_service(realtime_log_detail=mode)
                session = service.admit_session(f"session-{mode}")
                recorded = []
                service.performance = type(
                    "PerformanceCollector",
                    (),
                    {"event": lambda self, event, **fields: recorded.append(event)},
                )()

                timestamp = time.time()
                session._record_realtime_performance(
                    1,
                    timestamp,
                    {},
                    "realtime text",
                )
                session._emit_realtime_summary(1, timestamp, {})

                detail_events = {
                    event
                    for event in recorded
                    if event in {
                        "transcription.realtime_emitted",
                        "transcription.performance_summary",
                    }
                }
                self.assertEqual(detail_events, expected_detail_events)
                session.close()

    def test_active_speaker_limit_rejects_only_new_speaker(self):
        service, manager = make_service(max_active_speakers=1)
        first = service.admit_session("first")
        second = service.admit_session("second")

        first.start_streaming()
        second.start_streaming()

        self.assertTrue(first.ingest_audio_packet(audio_packet())[0])
        accepted, warning = second.ingest_audio_packet(audio_packet())

        self.assertTrue(accepted)
        self.assertIsNone(warning)
        self.assertTrue(any("maximale Anzahl gleichzeitig sprechender Personen" in msg.get("message", "") for msg in manager.messages["second"]))
        self.assertEqual(service.active_speaker_count(), 1)

    def test_session_admission_limit_is_explicit(self):
        service, _ = make_service(max_sessions=1)

        self.assertIsNotNone(service.admit_session("first"))
        self.assertIsNone(service.admit_session("second"))

        metrics = service.metrics()
        self.assertEqual(metrics["activeSessions"], 1)
        self.assertEqual(metrics["rejectedSessions"], 1)

    def test_recorder_sessions_receive_realtime_boundary_configuration(self):
        service, _ = make_service(
            realtime_transcription_use_syllable_boundaries=True,
            realtime_boundary_detector_sensitivity=0.7,
            realtime_boundary_followup_delays=(0.1, 0.2, 0.4),
        )

        self.assertIsNotNone(service.admit_session("first"))

        config = FakeRecorder.instances[-1].kwargs
        self.assertTrue(config["realtime_transcription_use_syllable_boundaries"])
        self.assertEqual(config["realtime_boundary_detector_sensitivity"], 0.7)
        self.assertEqual(config["realtime_boundary_followup_delays"], (0.1, 0.2, 0.4))
        self.assertFalse(config["warmup_vad"])

    def test_recorder_sessions_enable_vad_warmup_with_model_warmup(self):
        service, _ = make_service(model_warmup=True)

        self.assertIsNotNone(service.admit_session("first"))

        config = FakeRecorder.instances[-1].kwargs
        self.assertTrue(config["warmup_vad"])

    def test_recorder_sessions_receive_wake_word_configuration(self):
        service, _ = make_service(
            wakeword_backend="pvporcupine",
            wake_words="jarvis",
            wake_words_sensitivity=0.72,
            wake_word_timeout=3.5,
            wake_word_buffer_duration=0.25,
        )

        self.assertIsNotNone(service.admit_session("first"))

        config = FakeRecorder.instances[-1].kwargs
        self.assertEqual(config["wakeword_backend"], "pvporcupine")
        self.assertEqual(config["wake_words"], "jarvis")
        self.assertEqual(config["wake_words_sensitivity"], 0.72)
        self.assertEqual(config["wake_word_timeout"], 3.5)
        self.assertEqual(config["wake_word_buffer_duration"], 0.25)
        self.assertTrue(callable(config["on_wakeword_detected"]))
        self.assertTrue(callable(config["on_wakeword_timeout"]))

    def test_disabled_session_is_isolated_from_inherited_wake_word_session(self):
        service, _ = make_service(
            wakeword_backend="openwakeword",
            wake_words="hey_jarvis",
            openwakeword_model_paths="C:/models/hey_jarvis.onnx",
        )

        inherited = service.admit_session("inherited")
        disabled = service.admit_session(
            "disabled",
            wake_word_request=SessionWakeWordRequest(enabled=False),
        )

        self.assertTrue(inherited.settings.wake_word_enabled())
        self.assertFalse(disabled.settings.wake_word_enabled())
        self.assertTrue(service.settings.wake_word_enabled())
        self.assertEqual(
            FakeRecorder.instances[-2].kwargs["wakeword_backend"],
            "openwakeword",
        )
        self.assertEqual(
            FakeRecorder.instances[-1].kwargs["wakeword_backend"],
            "",
        )
        self.assertFalse(
            disabled.session_config_dict()["effectiveWakeWordEnabled"]
        )

    def test_wake_word_callbacks_publish_status_and_timeline_events(self):
        service, manager = make_service(
            wakeword_backend="pvporcupine",
            wake_words="jarvis",
        )
        session = service.admit_session("first")
        self.assertIsNotNone(session)
        # Wake-word callbacks are lifecycle-bound (C2/F9): only a running
        # stream arms them, exactly like the production recorder thread.
        session.start_streaming()
        recorder = FakeRecorder.instances[-1]

        recorder.on_wakeword_detection_start()
        recorder.on_wakeword_detected()
        recorder.on_wakeword_timeout()

        timeline_events = [
            message.get("event")
            for message in manager.messages["first"]
            if message.get("type") == "timeline"
        ]
        statuses = [
            message.get("state")
            for message in manager.messages["first"]
            if message.get("type") == "status"
        ]

        self.assertIn("wakeword_wait_started", timeline_events)
        self.assertIn("wakeword_detected", timeline_events)
        self.assertIn("wakeword_timeout", timeline_events)
        self.assertIn("wakeword_wait", statuses)
        self.assertIn("wakeword_detected", statuses)
        self.assertIn("wakeword_timeout", statuses)

    def test_wake_word_session_returns_to_wake_wait_after_recording_and_final(self):
        service, manager = make_service(
            wakeword_backend="pvporcupine",
            wake_words="jarvis",
        )
        session = service.admit_session("first")
        self.assertIsNotNone(session)
        session.start_streaming()

        session._on_wakeword_detected()
        session._on_recording_start()
        session._on_recording_stop()

        statuses = [
            message.get("state")
            for message in manager.messages["first"]
            if message.get("type") == "status"
        ]
        self.assertEqual(statuses[-1], "wakeword_wait")

        self.assertTrue(session._publish_final_text("done", session.generation))
        statuses = [
            message.get("state")
            for message in manager.messages["first"]
            if message.get("type") == "status"
        ]
        self.assertEqual(statuses[-1], "wakeword_wait")

    def test_wake_word_followup_window_stays_in_voice_mode_after_recording(self):
        service, manager = make_service(
            wakeword_backend="pvporcupine",
            wake_words="jarvis",
            wake_word_timeout=3.0,
            wake_word_followup_window=5.0,
        )
        session = service.admit_session("first")
        self.assertIsNotNone(session)
        session.start_streaming()
        recorder = FakeRecorder.instances[-1]

        session._on_wakeword_detected()
        session._on_recording_start()
        session._on_recording_stop()

        statuses = [
            message.get("state")
            for message in manager.messages["first"]
            if message.get("type") == "status"
        ]
        self.assertEqual(statuses[-1], "wakeword_detected")
        self.assertTrue(recorder.wakeword_detected)
        self.assertEqual(recorder.wake_word_timeout, 5.0)
        self.assertTrue(recorder.start_recording_on_voice_activity)
        self.assertTrue(recorder.stop_recording_on_voice_deactivity)
        self.assertTrue(any(
            message.get("event") == "wakeword_followup_started"
            for message in manager.messages["first"]
            if message.get("type") == "timeline"
        ))

        self.assertTrue(session._publish_final_text("done", session.generation))
        statuses = [
            message.get("state")
            for message in manager.messages["first"]
            if message.get("type") == "status"
        ]
        self.assertEqual(statuses[-1], "wakeword_detected")

        generation = session._wakeword_followup_generation
        self.assertTrue(session._finish_wakeword_followup(generation))
        statuses = [
            message.get("state")
            for message in manager.messages["first"]
            if message.get("type") == "status"
        ]
        self.assertEqual(statuses[-1], "wakeword_wait")
        self.assertFalse(recorder.wakeword_detected)
        self.assertEqual(recorder.wake_word_timeout, 3.0)
        self.assertFalse(recorder.start_recording_on_voice_activity)
        self.assertFalse(recorder.stop_recording_on_voice_deactivity)
        self.assertTrue(any(
            message.get("event") == "wakeword_followup_timeout"
            for message in manager.messages["first"]
            if message.get("type") == "timeline"
        ))

    def test_wake_word_session_ignores_late_vad_detect_start_after_reset(self):
        service, manager = make_service(
            wakeword_backend="pvporcupine",
            wake_words="jarvis",
        )
        session = service.admit_session("first")
        self.assertIsNotNone(session)
        session.start_streaming()
        recorder = FakeRecorder.instances[-1]

        # Lifecycle-bound detection: arm the wake epoch first (C2/F9).
        recorder.on_wakeword_detection_start()
        recorder.on_wakeword_detected()
        recorder.on_vad_detect_start()
        recorder.on_recording_start()
        recorder.on_recording_stop()
        recorder.on_vad_detect_start()

        statuses = [
            message.get("state")
            for message in manager.messages["first"]
            if message.get("type") == "status"
        ]
        self.assertIn("voice", statuses)
        self.assertEqual(statuses[-1], "wakeword_wait")

    def test_recording_timeline_metadata_is_attached_to_final_segment(self):
        service, manager = make_service(pre_recording_buffer_duration=0.4)
        session = service.admit_session("first")
        session.start_streaming()

        self.assertTrue(session.ingest_audio_packet(audio_packet())[0])
        session.stop_streaming()

        self._wait_for(lambda: any(job.kind == "final" for job in service.scheduler.jobs))
        final_job = next(job for job in service.scheduler.jobs if job.kind == "final")
        service.scheduler.complete(final_job, text="private-final")
        self._wait_for(lambda: any(msg.get("type") == "final" for msg in manager.messages["first"]))

        final = next(msg for msg in manager.messages["first"] if msg.get("type") == "final")
        segment = final["segment"]
        self.assertEqual(final["segmentId"], segment["segmentId"])
        self.assertIn("recordingStartedAt", segment)
        self.assertIn("recordingEndedAt", segment)
        self.assertIn("durationSeconds", segment)
        self.assertIn("preRecordingBuffer", segment)
        self.assertEqual(segment["preRecordingBuffer"]["configuredSeconds"], 0.4)
        self.assertTrue(any(
            msg.get("type") == "timeline" and msg.get("event") == "recording_started"
            for msg in manager.messages["first"]
        ))
        self.assertTrue(any(
            msg.get("type") == "timeline" and msg.get("event") == "final_transcript"
            for msg in manager.messages["first"]
        ))

    def test_sessions_use_separate_recorder_vad_state_with_shared_executors(self):
        service, _ = make_service(audio_queue_size=7)

        first = service.admit_session("first")
        second = service.admit_session("second")

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(len(FakeRecorder.instances), 2)
        self.assertIsNot(FakeRecorder.instances[0], FakeRecorder.instances[1])
        for recorder in FakeRecorder.instances:
            self.assertIs(recorder.transcription_executor.service, service)
            self.assertIs(recorder.realtime_transcription_executor.service, service)
            self.assertEqual(recorder.kwargs["allowed_latency_limit"], 7)
            self.assertTrue(recorder.kwargs["handle_buffer_overflow"])
            self.assertTrue(callable(recorder.kwargs["on_recorded_chunk"]))

    def test_audio_packets_are_rejected_until_session_is_started(self):
        service, _ = make_service()
        session = service.admit_session("first")

        accepted, warning = session.ingest_audio_packet(audio_packet())

        self.assertFalse(accepted)
        self.assertIn("Startbefehl", warning)
        self.assertEqual(service.scheduler.jobs, [])
        self.assertEqual(session.snapshot()["rejectedAudioChunks"], 1)

    def test_max_recording_duration_forces_recorder_finalization(self):
        service, manager = make_service(max_audio_queue_seconds_per_session=0.01)
        session = service.admit_session("first")
        session.start_streaming()

        accepted, warning = session.ingest_audio_packet(audio_packet(frames=640))

        self.assertTrue(accepted)
        self.assertIsNone(warning)
        self._wait_for(lambda: any(job.kind == "final" for job in service.scheduler.jobs))
        self.assertEqual(session.snapshot()["forcedFinalizations"], 1)
        self.assertTrue(any(
            "Maximaler Audiopuffer der Sitzung" in msg.get("message", "")
            for msg in manager.messages["first"]
        ))

    def test_processed_recorded_chunks_enforce_max_recording_duration(self):
        service, manager = make_service(max_audio_queue_seconds_per_session=0.01)
        session = service.admit_session("first")
        session.start_streaming()
        session.recorder.is_recording = True
        session.recorder.has_audio = True

        session._on_recorded_chunk(np.zeros(640, dtype=np.int16).tobytes())

        self._wait_for(lambda: session.snapshot()["forcedFinalizations"] == 1)
        self.assertTrue(any(
            "Maximaler Audiopuffer der Sitzung" in msg.get("message", "")
            for msg in manager.messages["first"]
        ))

    def test_recorded_audio_backlog_is_trimmed_to_final_queue_limit(self):
        service, manager = make_service(max_final_queue_depth_per_session=1)
        session = service.admit_session("first")
        queue_obj = session.recorder.recorded_audio_queue
        queue_obj.put({"frames": [b"a"]})
        queue_obj.put({"frames": [b"b"]})
        queue_obj.put({"frames": [b"c"]})

        dropped = session._trim_recorded_audio_queue()

        self.assertEqual(dropped, 2)
        self.assertEqual(queue_obj.qsize(), 1)
        snapshot = session.snapshot()
        self.assertEqual(snapshot["droppedRecordedSegments"], 2)
        self.assertEqual(snapshot["finalRejected"], 2)
        self.assertTrue(any(
            "Rückstau finaler Transkriptionen" in msg.get("message", "")
            for msg in manager.messages["first"]
        ))

    def test_service_stop_closes_active_sessions(self):
        service, _ = make_service()
        session = service.admit_session("first")

        service.stop()

        self.assertEqual(service.session_count(), 0)
        self.assertTrue(session.recorder.is_shut_down)

    def test_session_reservation_prevents_recorder_construction_over_capacity(self):
        class SlowRecorder(FakeRecorder):
            created = 0
            entered = threading.Event()
            release = threading.Event()

            def __init__(self, **kwargs):
                SlowRecorder.created += 1
                SlowRecorder.entered.set()
                SlowRecorder.release.wait(timeout=2.0)
                super().__init__(**kwargs)

        settings = ServerSettings(
            model_warmup=False,
            realtime_processing_pause=0.0,
            realtime_min_audio_seconds=0.01,
            min_length_of_recording=0.0,
            post_speech_silence_duration=60.0,
            vad_energy_threshold=1.0,
            webrtc_sensitivity=99,
            max_sessions=1,
        )
        manager = CollectingManager()
        service = VoiceSTTService(
            settings,
            manager,
            scheduler_factory=ManualScheduler,
            recorder_factory=SlowRecorder,
        )
        admitted = []

        first_thread = threading.Thread(
            target=lambda: admitted.append(service.admit_session("first")),
            daemon=True,
        )
        first_thread.start()
        self.assertTrue(SlowRecorder.entered.wait(timeout=1.0))

        second = service.admit_session("second")
        self.assertIsNone(second)
        self.assertEqual(SlowRecorder.created, 1)

        SlowRecorder.release.set()
        first_thread.join(timeout=2.0)
        self.assertEqual(len(admitted), 1)
        self.assertIsNotNone(admitted[0])
        self.assertEqual(service.session_count(), 1)

    def test_realtime_results_are_routed_to_owner(self):
        service, manager = make_service()
        first = service.admit_session("first")
        second = service.admit_session("second")
        first.start_streaming()
        second.start_streaming()

        first.ingest_audio_packet(audio_packet(level=2000))
        second.ingest_audio_packet(audio_packet(level=2200))

        self._wait_for(lambda: len([job for job in service.scheduler.jobs if job.kind == "realtime"]) >= 2)
        realtime_jobs = [job for job in service.scheduler.jobs if job.kind == "realtime"]
        self.assertEqual({job.session_id for job in realtime_jobs}, {"first", "second"})
        for job in realtime_jobs:
            service.scheduler.complete(job, text=f"rt-{job.session_id}")

        self._wait_for(lambda: any(msg.get("type") == "realtime" for msg in manager.messages["first"]))
        self._wait_for(lambda: any(msg.get("type") == "realtime" for msg in manager.messages["second"]))

        self.assertTrue(any(msg.get("text") == "rt-first" for msg in manager.messages["first"]))
        self.assertTrue(any(msg.get("text") == "rt-second" for msg in manager.messages["second"]))
        self.assertFalse(any(msg.get("text") == "rt-second" for msg in manager.messages["first"]))
        self.assertFalse(any(msg.get("text") == "rt-first" for msg in manager.messages["second"]))

    def _wait_for(self, predicate, timeout=2.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.01)
        self.fail("Timed out waiting for condition")


try:
    from fastapi.testclient import TestClient
except Exception as exc:  # pragma: no cover - optional dependency
    TestClient = None
    FASTAPI_IMPORT_ERROR = exc
else:
    FASTAPI_IMPORT_ERROR = None


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class FastAPIMultiUserWebSocketTests(unittest.TestCase):
    def test_configured_admin_key_grants_global_history_replay_and_live(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = ServerSettings(
                model_warmup=False,
                data_root_path=temp_dir,
                admin_api_key="test-admin-secret",
                request_log_stdout=False,
                performance_log_stdout=False,
            )
            app = create_app(
                settings,
                scheduler_factory=AutoScheduler,
                recorder_factory=FakeRecorder,
            )

            with TestClient(app) as client:
                events = app.state.voicestt_service.events
                events.emit("audit", "admin.test_a", sessionId="session-a")
                events.emit(
                    "transcription",
                    "admin.test_b",
                    sessionId="session-b",
                )
                events.emit("system", "admin.test_system")
                events.flush()

                self.assertEqual(
                    client.get("/api/logs/events").status_code,
                    401,
                )
                self.assertEqual(
                    client.get(
                        "/api/logs/events",
                        headers={"X-VoiceSTT-Admin-Key": "wrong"},
                    ).status_code,
                    401,
                )
                history = client.get(
                    "/api/logs/events",
                    headers={
                        "X-VoiceSTT-Admin-Key": "test-admin-secret",
                    },
                    params={"limit": 1000},
                )
                self.assertEqual(history.status_code, 200)
                history_body = history.json()
                self.assertEqual(history_body["authorizationScope"], "admin")
                self.assertTrue(history_body["allSessions"])
                self.assertEqual(history_body["deliveryMode"], "sqlite_first")
                names = {event["event"] for event in history_body["data"]}
                self.assertTrue({
                    "admin.test_a",
                    "admin.test_b",
                    "admin.test_system",
                }.issubset(names))
                self.assertNotIn("test-admin-secret", history.text)

                with client.websocket_connect("/ws/logs") as denied:
                    denied.send_json({
                        "type": "subscribe",
                        "accessToken": "wrong",
                    })
                    denied_message = denied.receive_json()
                    self.assertEqual(denied_message["type"], "log.error")
                    self.assertEqual(denied_message["code"], "not_authorized")

                with client.websocket_connect("/ws/logs") as logs:
                    logs.send_json({
                        "type": "subscribe",
                        "accessToken": "test-admin-secret",
                        "channels": [],
                        "afterCursor": 0,
                    })
                    hello = logs.receive_json()
                    self.assertEqual(hello["type"], "log.hello")
                    self.assertEqual(hello["logProtocolVersion"], 2)
                    self.assertEqual(hello["deliveryMode"], "sqlite_first")
                    subscribed = logs.receive_json()
                    self.assertEqual(subscribed["authorizationScope"], "admin")
                    self.assertTrue(subscribed["allChannels"])
                    self.assertTrue(subscribed["allSessions"])
                    replayed = set()
                    while True:
                        message = logs.receive_json()
                        if message["type"] == "log.event":
                            replayed.add(message["event"]["event"])
                        elif message["type"] == "log.replay_completed":
                            break
                    self.assertTrue({
                        "admin.test_a",
                        "admin.test_b",
                        "admin.test_system",
                    }.issubset(replayed))

                    events.emit(
                        "system",
                        "admin.test_live",
                        sessionId="session-c",
                    )
                    while True:
                        message = logs.receive_json()
                        if (
                            message["type"] == "log.event"
                            and message["event"]["event"] == "admin.test_live"
                        ):
                            self.assertFalse(message["replay"])
                            break

                with client.websocket_connect("/ws/logs") as ahead:
                    ahead.send_json({
                        "type": "subscribe",
                        "accessToken": "test-admin-secret",
                        "afterCursor": events.latest_cursor() + 1,
                    })
                    error = ahead.receive_json()
                    self.assertEqual(error["type"], "log.error")
                    self.assertEqual(error["code"], "cursor_ahead")
                    with self.assertRaises(WebSocketDisconnect) as closed:
                        ahead.receive_json()
                    self.assertEqual(closed.exception.code, 1008)

                with client.websocket_connect("/ws/logs") as negative:
                    negative.send_json({
                        "type": "subscribe",
                        "accessToken": "test-admin-secret",
                        "afterCursor": -1,
                    })
                    error = negative.receive_json()
                    self.assertEqual(error["type"], "log.error")
                    self.assertEqual(error["code"], "invalid_cursor")
                    with self.assertRaises(WebSocketDisconnect) as closed:
                        negative.receive_json()
                    self.assertEqual(closed.exception.code, 1008)

                health = client.get("/health").json()
                self.assertTrue(health["eventStore"]["available"])

    def test_admin_live_rescans_sqlite_after_coalesced_commit_wakeup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = ServerSettings(
                model_warmup=False,
                data_root_path=temp_dir,
                admin_api_key="test-admin-secret",
                request_log_stdout=False,
                performance_log_stdout=False,
            )
            app = create_app(
                settings,
                scheduler_factory=AutoScheduler,
                recorder_factory=FakeRecorder,
            )
            with TestClient(app) as client:
                events = app.state.voicestt_service.events
                with client.websocket_connect("/ws/logs") as logs:
                    logs.send_json({
                        "type": "subscribe",
                        "accessToken": "test-admin-secret",
                        "channels": ["system"],
                        "afterCursor": events.latest_cursor(),
                    })
                    self.assertEqual(logs.receive_json()["type"], "log.hello")
                    self.assertEqual(logs.receive_json()["type"], "log.subscribed")
                    self.assertEqual(
                        logs.receive_json()["type"],
                        "log.replay_completed",
                    )

                    original_enqueue = events._enqueue_control
                    with patch.object(
                        events,
                        "_enqueue_control",
                        return_value=False,
                    ):
                        for sequence in range(3):
                            events.emit(
                                "system",
                                "coalesced.test",
                                sequence=sequence,
                            )
                    original_enqueue({
                        "_logControl": "commit",
                        "cursor": events.latest_cursor(),
                    })

                    received = []
                    while len(received) < 3:
                        message = logs.receive_json()
                        if (
                            message["type"] == "log.event"
                            and message["event"]["event"] == "coalesced.test"
                        ):
                            received.append(message["event"])
                    self.assertEqual(
                        [event["data"]["sequence"] for event in received],
                        [0, 1, 2],
                    )
                    self.assertEqual(
                        [event["cursor"] for event in received],
                        sorted(event["cursor"] for event in received),
                    )

    def test_admin_live_keepalive_rescans_without_commit_wakeup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = ServerSettings(
                model_warmup=False,
                data_root_path=temp_dir,
                admin_api_key="test-admin-secret",
                request_log_stdout=False,
                performance_log_stdout=False,
            )
            app = create_app(
                settings,
                scheduler_factory=AutoScheduler,
                recorder_factory=FakeRecorder,
            )
            with TestClient(app) as client, patch(
                "api_fastapi_server.server.LOG_STREAM_KEEPALIVE_SECONDS",
                0.01,
            ):
                events = app.state.voicestt_service.events
                with client.websocket_connect("/ws/logs") as logs:
                    logs.send_json({
                        "type": "subscribe",
                        "accessToken": "test-admin-secret",
                        "channels": ["system"],
                        "afterCursor": events.latest_cursor(),
                    })
                    self.assertEqual(logs.receive_json()["type"], "log.hello")
                    self.assertEqual(logs.receive_json()["type"], "log.subscribed")
                    self.assertEqual(
                        logs.receive_json()["type"],
                        "log.replay_completed",
                    )

                    with patch.object(
                        events,
                        "_enqueue_control",
                        return_value=False,
                    ):
                        events.emit("system", "keepalive.rescan_test")

                    event = None
                    for _ in range(10):
                        message = logs.receive_json()
                        if message["type"] == "log.event":
                            event = message
                            break
                        self.assertEqual(message["type"], "log.keepalive")
                    self.assertIsNotNone(event)
                    self.assertEqual(
                        event["event"]["event"],
                        "keepalive.rescan_test",
                    )
                    keepalive = logs.receive_json()
                    self.assertEqual(keepalive["type"], "log.keepalive")
                    self.assertEqual(keepalive["eventsSent"], 1)

    def test_admin_replay_can_resume_after_disconnect_at_multiple_positions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = ServerSettings(
                model_warmup=False,
                data_root_path=temp_dir,
                admin_api_key="test-admin-secret",
                request_log_stdout=False,
                performance_log_stdout=False,
            )
            app = create_app(
                settings,
                scheduler_factory=AutoScheduler,
                recorder_factory=FakeRecorder,
            )
            with TestClient(app) as client:
                events = app.state.voicestt_service.events
                start_cursor = events.latest_cursor()
                for sequence in range(8):
                    events.emit(
                        "system",
                        "resume.replay_test",
                        sequence=sequence,
                    )
                expected = list(range(8))

                for disconnect_after in (1, 4, 7):
                    with self.subTest(disconnect_after=disconnect_after):
                        received = []
                        resume_cursor = start_cursor
                        with client.websocket_connect("/ws/logs") as logs:
                            logs.send_json({
                                "type": "subscribe",
                                "accessToken": "test-admin-secret",
                                "channels": ["system"],
                                "afterCursor": start_cursor,
                            })
                            self.assertEqual(
                                logs.receive_json()["type"],
                                "log.hello",
                            )
                            self.assertEqual(
                                logs.receive_json()["type"],
                                "log.subscribed",
                            )
                            while len(received) < disconnect_after:
                                message = logs.receive_json()
                                if (
                                    message["type"] == "log.event"
                                    and message["event"]["event"]
                                    == "resume.replay_test"
                                ):
                                    received.append(
                                        message["event"]["data"]["sequence"]
                                    )
                                    resume_cursor = message["event"]["cursor"]

                        with client.websocket_connect("/ws/logs") as resumed:
                            resumed.send_json({
                                "type": "subscribe",
                                "accessToken": "test-admin-secret",
                                "channels": ["system"],
                                "afterCursor": resume_cursor,
                            })
                            self.assertEqual(
                                resumed.receive_json()["type"],
                                "log.hello",
                            )
                            self.assertEqual(
                                resumed.receive_json()["type"],
                                "log.subscribed",
                            )
                            while True:
                                message = resumed.receive_json()
                                if message["type"] == "log.event":
                                    if (
                                        message["event"]["event"]
                                        == "resume.replay_test"
                                    ):
                                        received.append(
                                            message["event"]["data"]["sequence"]
                                        )
                                elif message["type"] == "log.replay_completed":
                                    break
                        self.assertEqual(received, expected)

    def test_store_outage_closes_live_stream_and_recovery_allows_new_stream(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = ServerSettings(
                model_warmup=False,
                data_root_path=temp_dir,
                admin_api_key="test-admin-secret",
                request_log_stdout=False,
                performance_log_stdout=False,
            )
            app = create_app(
                settings,
                scheduler_factory=AutoScheduler,
                recorder_factory=FakeRecorder,
            )
            with TestClient(app) as client:
                events = app.state.voicestt_service.events
                original_append = events._store.append
                with client.websocket_connect("/ws/logs") as logs:
                    logs.send_json({
                        "type": "subscribe",
                        "accessToken": "test-admin-secret",
                        "afterCursor": events.latest_cursor(),
                    })
                    self.assertEqual(logs.receive_json()["type"], "log.hello")
                    self.assertEqual(logs.receive_json()["type"], "log.subscribed")
                    self.assertEqual(
                        logs.receive_json()["type"],
                        "log.replay_completed",
                    )

                    events._store.append = lambda event: (_ for _ in ()).throw(
                        OSError("simulated outage")
                    )
                    self.assertIsNone(
                        events.emit("system", "outage.not_committed")
                    )
                    error = logs.receive_json()
                    self.assertEqual(error["type"], "log.error")
                    self.assertEqual(error["code"], "event_store_unavailable")
                    with self.assertRaises(WebSocketDisconnect) as closed:
                        logs.receive_json()
                    self.assertEqual(closed.exception.code, 1011)

                with client.websocket_connect("/ws/logs") as unavailable:
                    error = unavailable.receive_json()
                    self.assertEqual(error["type"], "log.error")
                    self.assertEqual(error["code"], "event_store_unavailable")
                    with self.assertRaises(WebSocketDisconnect) as closed:
                        unavailable.receive_json()
                    self.assertEqual(closed.exception.code, 1011)

                events._store.append = original_append
                self.assertIsNotNone(events.emit("system", "outage.recovered"))
                self.assertTrue(events.store_available())
                self.assertNotIn(
                    "outage.not_committed",
                    {event["event"] for event in events.query(limit=1000)},
                )

                with client.websocket_connect("/ws/logs") as recovered:
                    recovered.send_json({
                        "type": "subscribe",
                        "accessToken": "test-admin-secret",
                        "channels": ["system"],
                        "afterCursor": 0,
                    })
                    self.assertEqual(
                        recovered.receive_json()["type"],
                        "log.hello",
                    )
                    self.assertEqual(
                        recovered.receive_json()["type"],
                        "log.subscribed",
                    )
                    replayed = []
                    while True:
                        message = recovered.receive_json()
                        if message["type"] == "log.event":
                            replayed.append(message["event"]["event"])
                        elif message["type"] == "log.replay_completed":
                            break
                    self.assertIn("outage.recovered", replayed)
                    self.assertNotIn("outage.not_committed", replayed)

    def test_audio_transcription_continues_while_event_store_is_degraded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = ServerSettings(
                model_warmup=False,
                data_root_path=temp_dir,
                request_log_stdout=False,
                performance_log_stdout=False,
                realtime_processing_pause=0.0,
                realtime_min_audio_seconds=0.01,
                min_length_of_recording=0.0,
                post_speech_silence_duration=60.0,
            )
            app = create_app(
                settings,
                scheduler_factory=AutoScheduler,
                recorder_factory=FakeRecorder,
            )
            with TestClient(app) as client:
                events = app.state.voicestt_service.events
                original_append = events._store.append
                with client.websocket_connect("/ws/transcribe") as transcribe:
                    self.assertEqual(
                        transcribe.receive_json()["type"],
                        "hello",
                    )
                    events._store.append = (
                        lambda event: (_ for _ in ()).throw(
                            OSError("simulated outage")
                        )
                    )
                    try:
                        self.assertIsNone(
                            events.emit("system", "outage.trigger")
                        )
                        self.assertFalse(events.store_available())

                        transcribe.send_text('{"type":"start"}')
                        transcribe.send_bytes(encode_audio_packet(
                            {
                                "sampleRate": 16000,
                                "channels": 1,
                                "format": "pcm_s16le",
                                "frames": 640,
                            },
                            np.full(640, 2000, dtype=np.int16).tobytes(),
                        ))
                        transcribe.send_text('{"type":"stop"}')
                        final = self._receive_type(transcribe, "final")
                        self.assertTrue(final["text"])
                    finally:
                        events._store.append = original_append

                self.assertIsNotNone(
                    events.emit("system", "outage.audio_recovered")
                )
                self.assertTrue(events.store_available())

    def test_admin_replay_reports_retention_gap(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = ServerSettings(
                model_warmup=False,
                data_root_path=temp_dir,
                admin_api_key="test-admin-secret",
                request_log_stdout=False,
                performance_log_stdout=False,
            )
            app = create_app(
                settings,
                scheduler_factory=AutoScheduler,
                recorder_factory=FakeRecorder,
            )
            with TestClient(app) as client:
                events = app.state.voicestt_service.events
                common = {
                    "schemaVersion": 1,
                    "severity": "info",
                    "serverInstanceId": events.server_instance_id,
                    "data": {},
                }
                system_cursor = events._store.append({
                    **common,
                    "eventId": "retention-system-old",
                    "timestamp": "2020-01-01T00:00:00.000Z",
                    "channel": "system",
                    "event": "retention.system_old",
                    "sessionId": "session-a",
                })
                removed_cursor = events._store.append({
                    **common,
                    "eventId": "retention-transcription-old",
                    "timestamp": "2020-01-01T00:00:00.000Z",
                    "channel": "transcription",
                    "event": "retention.transcription_old",
                    "sessionId": "session-a",
                })
                session_b_cursor = events._store.append({
                    **common,
                    "eventId": "retention-transcription-session-b",
                    "timestamp": "2026-08-02T00:00:00.000Z",
                    "channel": "transcription",
                    "event": "retention.session_b",
                    "sessionId": "session-b",
                })
                events._store.set_retention({"transcription": 30})
                events.emit(
                    "transcription",
                    "retention.transcription_new",
                    sessionId="session-a",
                )
                self.assertLess(events.oldest_cursor(), removed_cursor)
                self.assertNotIn(
                    removed_cursor,
                    [event["cursor"] for event in events.query(limit=1000)],
                )

                with client.websocket_connect("/ws/logs") as logs:
                    logs.send_json({
                        "type": "subscribe",
                        "accessToken": "test-admin-secret",
                        "channels": ["system"],
                        "sessionId": "session-a",
                        "afterCursor": system_cursor,
                    })
                    hello = logs.receive_json()
                    self.assertLess(hello["oldestCursor"], removed_cursor)
                    self.assertEqual(hello["retentionCursor"], 0)
                    self.assertEqual(logs.receive_json()["type"], "log.subscribed")
                    self.assertEqual(
                        logs.receive_json()["type"],
                        "log.replay_completed",
                    )

                with client.websocket_connect("/ws/logs") as logs:
                    logs.send_json({
                        "type": "subscribe",
                        "accessToken": "test-admin-secret",
                        "channels": ["transcription"],
                        "sessionId": "session-a",
                        "afterCursor": system_cursor,
                    })
                    hello = logs.receive_json()
                    self.assertLess(hello["oldestCursor"], removed_cursor)
                    self.assertEqual(
                        hello["retentionCursor"],
                        removed_cursor,
                    )
                    self.assertEqual(logs.receive_json()["type"], "log.subscribed")
                    gap = logs.receive_json()
                    self.assertEqual(gap["type"], "log.gap")
                    self.assertEqual(gap["reason"], "retention")
                    self.assertEqual(
                        gap["lostFromCursor"],
                        system_cursor + 1,
                    )
                    self.assertEqual(gap["lostToCursor"], removed_cursor)
                    replay = logs.receive_json()
                    self.assertEqual(replay["type"], "log.event")
                    self.assertEqual(
                        replay["event"]["event"],
                        "retention.transcription_new",
                    )

                with client.websocket_connect("/ws/logs") as logs:
                    logs.send_json({
                        "type": "subscribe",
                        "accessToken": "test-admin-secret",
                        "channels": ["transcription"],
                        "sessionId": "session-b",
                        "afterCursor": system_cursor,
                    })
                    hello = logs.receive_json()
                    self.assertEqual(hello["retentionCursor"], 0)
                    self.assertEqual(logs.receive_json()["type"], "log.subscribed")
                    replay = logs.receive_json()
                    self.assertEqual(replay["type"], "log.event")
                    self.assertEqual(replay["event"]["cursor"], session_b_cursor)

    def test_session_log_websocket_replays_more_than_one_page(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = ServerSettings(
                model_warmup=False,
                data_root_path=str(root),
                request_log_stdout=False,
                performance_log_stdout=False,
            )
            app = create_app(
                settings,
                scheduler_factory=AutoScheduler,
                recorder_factory=FakeRecorder,
            )

            with TestClient(app) as client:
                with client.websocket_connect(
                    "/ws/transcribe?clientId=browser-client-42"
                ) as transcribe:
                    hello = transcribe.receive_json()
                    session_id = hello["sessionId"]
                    access = hello["logAccess"]
                    self.assertEqual(hello["clientId"], "browser-client-42")
                    for sequence in range(1005):
                        app.state.voicestt_service.events.emit(
                            "transcription",
                            "transcription.realtime_test",
                            sessionId=session_id,
                            transcriptionId=f"{session_id}:test",
                            sequence=sequence,
                        )
                    app.state.voicestt_service.events.flush()

                    with client.websocket_connect("/ws/logs") as logs:
                        logs.send_json({
                            "type": "subscribe",
                            "accessToken": access["accessToken"],
                            "sessionId": session_id,
                            "channels": ["transcription"],
                            "afterCursor": 0,
                        })
                        self.assertEqual(logs.receive_json()["type"], "log.hello")
                        replayed = 0
                        while True:
                            message = logs.receive_json()
                            if message["type"] == "log.event":
                                replayed += 1
                            elif message["type"] == "log.replay_completed":
                                self.assertEqual(message["count"], 1005)
                                break
                        self.assertEqual(replayed, 1005)

    def test_session_log_websocket_replays_and_streams_only_own_events(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = ServerSettings(
                model_warmup=False,
                data_root_path=str(root),
                realtime_processing_pause=0.0,
                realtime_min_audio_seconds=0.01,
                min_length_of_recording=0.0,
                post_speech_silence_duration=60.0,
                request_log_stdout=False,
                performance_log_stdout=False,
            )
            app = create_app(
                settings,
                scheduler_factory=AutoScheduler,
                recorder_factory=FakeRecorder,
            )

            with TestClient(app) as client:
                with client.websocket_connect(
                    "/ws/transcribe?clientId=browser-client-42"
                ) as transcribe:
                    hello = transcribe.receive_json()
                    session_id = hello["sessionId"]
                    access = hello["logAccess"]
                    self.assertEqual(hello["clientId"], "browser-client-42")
                    forbidden_history = client.get(
                        "/api/logs/events",
                        params={
                            "sessionId": session_id,
                            "channels": "system",
                        },
                        headers={
                            "X-VoiceSTT-Log-Token": access["accessToken"],
                        },
                    )
                    self.assertEqual(forbidden_history.status_code, 200)
                    self.assertEqual(forbidden_history.json()["data"], [])

                    with client.websocket_connect("/ws/logs") as forbidden_logs:
                        forbidden_logs.send_json({
                            "type": "subscribe",
                            "accessToken": access["accessToken"],
                            "sessionId": session_id,
                            "channels": ["system"],
                            "afterCursor": 0,
                        })
                        self.assertEqual(
                            forbidden_logs.receive_json()["type"],
                            "log.hello",
                        )
                        self.assertEqual(
                            forbidden_logs.receive_json()["type"],
                            "log.subscribed",
                        )
                        forbidden_replay = forbidden_logs.receive_json()
                        self.assertEqual(
                            forbidden_replay["type"],
                            "log.replay_completed",
                        )
                        self.assertEqual(forbidden_replay["count"], 0)

                    with client.websocket_connect("/ws/logs") as logs:
                        logs.send_json({
                            "type": "subscribe",
                            "accessToken": access["accessToken"],
                            "sessionId": session_id,
                            "channels": ["audit", "transcription", "performance"],
                            "afterCursor": 0,
                        })
                        self.assertEqual(logs.receive_json()["type"], "log.hello")
                        subscribed = logs.receive_json()
                        self.assertEqual(subscribed["type"], "log.subscribed")
                        self.assertEqual(
                            subscribed["sessionId"],
                            session_id,
                        )
                        while True:
                            replay_message = logs.receive_json()
                            if replay_message["type"] == "log.replay_completed":
                                break
                        logs.send_json({"type": "ping"})
                        pong = logs.receive_json()
                        self.assertEqual(pong["type"], "log.pong")
                        self.assertIn("serverTime", pong)

                        transcribe.send_text('{"type":"start"}')
                        transcribe.send_bytes(encode_audio_packet(
                            {
                                "sampleRate": 16000,
                                "channels": 1,
                                "format": "pcm_s16le",
                                "frames": 640,
                            },
                            np.full(640, 2000, dtype=np.int16).tobytes(),
                        ))
                        transcribe.send_text('{"type":"stop"}')
                        self._receive_type(transcribe, "final")

                        received = []
                        while "transcription.completed" not in {
                            event["event"] for event in received
                        }:
                            message = logs.receive_json()
                            if message["type"] == "log.event":
                                received.append(message["event"])

                        self.assertTrue(received)
                        self.assertTrue(all(
                            event.get("sessionId") == session_id
                            for event in received
                        ))
                        missing_client_ids = [
                            (event["event"], event.get("clientId"))
                            for event in received
                            if event.get("clientId") != "browser-client-42"
                        ]
                        self.assertEqual(missing_client_ids, [])
                        self.assertIn(
                            "transcription.completed",
                            {event["event"] for event in received},
                        )
                        self.assertIn(
                            "transcription.accepted",
                            {event["event"] for event in received},
                        )

    def test_config_endpoint_exposes_and_updates_runtime_settings(self):
        settings = ServerSettings(model_warmup=False, max_sessions=1)
        app = create_app(settings, scheduler_factory=AutoScheduler, recorder_factory=FakeRecorder)

        with TestClient(app) as client:
            config = client.get("/api/config")
            self.assertEqual(config.status_code, 200)
            config_body = config.json()
            self.assertIn("runtimeSettings", config_body)
            self.assertIn("kroko_onnx", config_body["supportedEngines"])

            update = client.patch(
                "/api/config",
                json={"settings": {"max_sessions": 3, "wake_words": "jarvis"}},
            )

            self.assertEqual(update.status_code, 200)
            body = update.json()
            self.assertEqual(body["applied"]["max_sessions"]["appliesTo"], "active_sessions")
            self.assertEqual(body["applied"]["wake_words"]["appliesTo"], "new_sessions")
            self.assertEqual(body["settings"]["max_sessions"], 3)

    def test_two_websocket_clients_get_isolated_transcripts(self):
        settings = ServerSettings(
            model_warmup=False,
            realtime_processing_pause=0.0,
            realtime_min_audio_seconds=0.01,
            min_length_of_recording=0.0,
            post_speech_silence_duration=60.0,
            vad_energy_threshold=1.0,
            webrtc_sensitivity=99,
            max_sessions=2,
        )
        app = create_app(settings, scheduler_factory=AutoScheduler, recorder_factory=FakeRecorder)

        with TestClient(app) as client:
            with client.websocket_connect("/ws/transcribe") as first:
                with client.websocket_connect("/ws/transcribe") as second:
                    first_hello = first.receive_json()
                    second_hello = second.receive_json()
                    self.assertEqual(first_hello["type"], "hello")
                    self.assertEqual(second_hello["type"], "hello")
                    first_session = first_hello["sessionId"]
                    second_session = second_hello["sessionId"]
                    self.assertNotEqual(first_session, second_session)

                    first.send_text('{"type":"start"}')
                    second.send_text('{"type":"start"}')
                    first.send_bytes(encode_audio_packet(
                        {"sampleRate": 16000, "channels": 1, "format": "pcm_s16le", "frames": 640},
                        np.full(640, 2000, dtype=np.int16).tobytes(),
                    ))
                    second.send_bytes(encode_audio_packet(
                        {"sampleRate": 16000, "channels": 1, "format": "pcm_s16le", "frames": 640},
                        np.full(640, 3000, dtype=np.int16).tobytes(),
                    ))
                    first.send_text('{"type":"stop"}')
                    second.send_text('{"type":"stop"}')

                    first_final = self._receive_type(first, "final")
                    second_final = self._receive_type(second, "final")

                    self.assertEqual(first_final["sessionId"], first_session)
                    self.assertEqual(second_final["sessionId"], second_session)
                    self.assertIn(first_session, first_final["text"])
                    self.assertIn(second_session, second_final["text"])
                    self.assertNotIn(second_session, first_final["text"])
                    self.assertNotIn(first_session, second_final["text"])

    def test_websocket_disabled_wake_word_contract_is_confirmed(self):
        settings = ServerSettings(
            model_warmup=False,
            wakeword_backend="openwakeword",
            wake_words="hey_jarvis",
            openwakeword_model_paths="C:/models/hey_jarvis.onnx",
        )
        app = create_app(
            settings,
            scheduler_factory=AutoScheduler,
            recorder_factory=FakeRecorder,
        )

        with TestClient(app) as client:
            with client.websocket_connect(
                "/ws/transcribe?wakeWordEnabled=false"
                "&wakeWordBackend=ignored"
                "&wakeWordSensitivity=invalid"
            ) as websocket:
                hello = websocket.receive_json()
                ready = websocket.receive_json()

        self.assertEqual(hello["type"], "hello")
        self.assertFalse(
            hello["sessionConfig"]["effectiveWakeWordEnabled"]
        )
        self.assertEqual(
            hello["sessionConfig"]["ignoredFields"],
            ["wakeWordBackend", "wakeWordSensitivity"],
        )
        self.assertNotIn(
            "openwakeword_model_paths",
            hello["settings"],
        )
        self.assertFalse(ready["sessionConfig"]["effectiveWakeWordEnabled"])
        self.assertFalse(ready["settings"]["wake_word_enabled"])

    def test_websocket_falls_back_for_invalid_wake_word_control(self):
        settings = ServerSettings(model_warmup=False)
        app = create_app(
            settings,
            scheduler_factory=AutoScheduler,
            recorder_factory=FakeRecorder,
        )

        with TestClient(app) as client:
            with client.websocket_connect(
                "/ws/transcribe?wakeWordEnabled=flase"
            ) as websocket:
                hello = websocket.receive_json()
                ready = websocket.receive_json()
            metrics = client.get("/api/metrics").json()

        self.assertEqual(hello["type"], "hello")
        self.assertFalse(
            hello["sessionConfig"]["effectiveWakeWordEnabled"]
        )
        self.assertEqual(
            hello["sessionConfig"]["fallbacks"][0]["field"],
            "wakeWordEnabled",
        )
        self.assertEqual(
            ready["sessionConfig"],
            hello["sessionConfig"],
        )
        self.assertEqual(metrics["activeSessions"], 0)

    def test_websocket_enables_manifest_default_and_reports_fallback(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            models = root / "all_models"
            models.mkdir()
            for filename in (
                "alexa.onnx",
                "embedding_model.onnx",
                "melspectrogram.onnx",
            ):
                (models / filename).write_bytes(b"model")
            (root / "models.json").write_text(json.dumps({
                "openwakeword_models": {
                    "path": str(models),
                    "default_model": "alexa",
                    "pipeline_models": {
                        "embedding_model_onnx": "embedding_model.onnx",
                        "melspectrogram_onnx": "melspectrogram.onnx",
                    },
                    "onnx_models": {"alexa": "alexa.onnx"},
                    "tflite_models": {},
                }
            }), encoding="utf-8")
            with patch.dict(
                os.environ,
                {"VOICESTT_OPENWAKEWORD_MODEL_ROOT": str(root)},
            ):
                settings = ServerSettings(
                    model_warmup=False,
                    wake_words_sensitivity=0.37,
                )
                app = create_app(
                    settings,
                    scheduler_factory=AutoScheduler,
                    recorder_factory=FakeRecorder,
                )
                with TestClient(app) as client:
                    with client.websocket_connect(
                        "/ws/transcribe?wakeWordEnabled=true"
                        "&wakeWordBackend=openwakeword"
                        "&wakeWordSensitivity=invalid"
                    ) as websocket:
                        hello = websocket.receive_json()
                        ready = websocket.receive_json()

        config = hello["sessionConfig"]
        self.assertTrue(config["effectiveWakeWordEnabled"])
        self.assertEqual(config["effectiveWakeWords"], ["alexa"])
        self.assertEqual(config["fallbacks"][0]["value"], 0.37)
        self.assertEqual(
            hello["sessionCapabilities"]["wakeWord"][
                "availableWakeWords"
            ][0]["id"],
            "alexa",
        )
        self.assertEqual(
            FakeRecorder.instances[-1].kwargs["wake_words"],
            "alexa",
        )
        self.assertTrue(
            FakeRecorder.instances[-1].kwargs[
                "openwakeword_model_paths"
            ].endswith("alexa.onnx")
        )
        self.assertEqual(
            ready["sessionConfig"],
            hello["sessionConfig"],
        )

    def test_admission_limit_rejects_extra_websocket(self):
        settings = ServerSettings(model_warmup=False, max_sessions=1)
        app = create_app(settings, scheduler_factory=AutoScheduler, recorder_factory=FakeRecorder)

        with TestClient(app) as client:
            with client.websocket_connect("/ws/transcribe") as first:
                self.assertEqual(first.receive_json()["type"], "hello")
                with client.websocket_connect("/ws/transcribe") as second:
                    error = second.receive_json()
                    self.assertEqual(error["type"], "error")
                    self.assertEqual(error["where"], "admission")

    def _receive_type(self, websocket, event_type, limit=20):
        for _ in range(limit):
            message = websocket.receive_json()
            if message.get("type") == event_type:
                return message
        self.fail(f"Did not receive {event_type!r} event")


if __name__ == "__main__":
    unittest.main()
