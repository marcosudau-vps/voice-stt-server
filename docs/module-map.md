# Module Map

This map records the current repository shape for safe, incremental refactoring.
It complements `docs/ARCHITECTURE.md` with module-level ownership, public
surfaces, side effects, and validation hints. It is descriptive, not a target
architecture mandate.

## System Shape

VoiceSTT is organized around one recorder-centered audio pipeline:

```text
audio input or feed_audio()
  -> AudioToTextRecorder audio queue
  -> wake word, VAD, pre-roll, and recording state
  -> optional realtime ASR and text stabilization
  -> final ASR engine
  -> callbacks, client/server messages, or text() return value
```

The recorder uses 16 kHz mono PCM as its internal audio currency. Optional
engines, wake-word backends, and model runtimes are loaded lazily so importing
`VoiceSTT` stays lightweight.

## Public Entry Points

| Entry point | Current public surface | Compatibility notes |
| --- | --- | --- |
| `VoiceSTT/__init__.py` | Lazy exports for `AudioToTextRecorder`, `AudioToTextRecorderClient`, `AudioInput`, `RealtimeSpeechBoundaryDetector`, `SpeechBoundaryEvent`, and `SpeechBoundaryResult`. | Keep names lazy and backward compatible. Do not import model runtimes from package import. |
| `VoiceSTT/audio_recorder.py` | `AudioToTextRecorder` and recorder constructor options, callbacks, methods, text formatting, and error behavior. | This is the main compatibility boundary. Refactors should delegate internally while preserving constructor parameters and callback behavior. |
| `VoiceSTT/audio_recorder_client.py` | Legacy websocket client `AudioToTextRecorderClient`. | Keep protocol behavior and public methods stable while `VoiceSTT_server` remains supported. |
| `VoiceSTT/transcription_engines/base.py` | `TranscriptionEngineConfig`, `TranscriptionResult`, `TranscriptionInfo`, `BaseTranscriptionEngine`, `StreamingTranscriptionSession`, and engine errors. | Engine adapters should continue normalizing output into this contract. |
| `VoiceSTT/transcription_engines/factory.py` | Engine alias normalization, lazy adapter loading, `create_transcription_engine()`, and `get_supported_transcription_engines()`. | Keep existing aliases and unsupported-engine error text compatible unless intentionally changed. |
| `VoiceSTT_server/stt_server.py` | Legacy dual-websocket server CLI and runtime callbacks. | Compatibility path; avoid mixing legacy server cleanup with recorder refactors. |
| `api_fastapi_server/server.py` | Source-only browser streaming reference server and CLI. | Not packaged as the core wheel, but it is the maintained multi-user browser reference implementation. |
| `api_fastapi_server/protocol.py` | Binary packet encode/decode helpers and protocol validation errors. | Packet shape is a service boundary. Keep serialized formats stable. |
| `VoiceSTT_server/server.py` | Installed production entry point for the maintained FastAPI server. | Keep it aligned with the implementation in `api_fastapi_server/server.py`. |
| `VoiceSTT_server/event_logging.py` | Structured event envelope, redaction, bounded fan-out, calendar JSONL, SQLite history and live subscribers. | Persisted schema and cursor behavior are client-visible contracts. |

## Core Package Modules

| Module | Responsibility | Main side effects | Focused tests |
| --- | --- | --- | --- |
| `VoiceSTT/audio_recorder.py` | Recorder state machine, audio queue consumption, VAD/wake-word gates, recording lifecycle, realtime workers, final transcription dispatch, callbacks, and shutdown. | Threads/processes, queues, callbacks, logging, model worker IPC, microphone coordination. | `tests/unit/test_audio_recorder_preroll_integration.py`, `tests/unit/test_slow_final_transcription_audio_gap.py`, `tests/unit/test_realtime_streaming_transcription.py`. |
| `VoiceSTT/audio_input.py` | PyAudio device selection, microphone stream setup, chunk reads, and resampling helpers for capture. | Device enumeration, microphone I/O, stream lifecycle. | Covered mostly through recorder/client integration and manual scripts. Add characterization tests before moving device logic. |
| `VoiceSTT/core/preroll.py` | Pure pre-recording buffer selection and conservative speech-onset trimming. | None intended; pure helper. | `tests/unit/test_preroll.py`, `tests/unit/test_audio_recorder_preroll_integration.py`. |
| `VoiceSTT/core/realtime_boundary_detector.py` | Low-cost acoustic boundary events for realtime transcription scheduling. | None intended; pure-ish signal analysis state. | `tests/unit/test_realtime_boundary_detector.py`. |
| `VoiceSTT/core/realtime_text_stabilizer.py` | Pure stabilization of partial ASR observations into stable deltas, previews, diagnostics, and final events. | None intended; timestamp/order dependent. | `tests/unit/test_realtime_text_stabilizer.py`. |
| `VoiceSTT/core/silero_vad.py` | Silero backend normalization, model discovery/loading, ONNX/PyTorch wrapper behavior, and callable VAD adaptation. | Optional dependency imports, model file lookup, torch/onnx runtime loading. | `tests/unit/test_silero_vad_backend.py`. |
| `VoiceSTT/core/safepipe.py` | Safer multiprocessing pipe wrapper used by recorder worker communication. | Multiprocessing pipe/process communication. | Covered indirectly by recorder paths; add targeted tests before changing IPC behavior. |
| `VoiceSTT/install_kroko.py` | Kroko-ONNX installer CLI, checkout preparation, patching, build/install helpers. | Filesystem writes, subprocesses, downloads/build tools. | Covered by install-matrix and smoke scripts; treat as tooling, not runtime pipeline code. |

## Transcription Engine Layer

| Module group | Responsibility | Refactor notes |
| --- | --- | --- |
| `base.py` | Shared engine configuration, result types, errors, and optional streaming session interface. | Public contract for every adapter. Move only with compatibility re-exports. |
| `factory.py` | Name normalization, alias table, lazy imports, unsupported-engine diagnostics. | Add aliases deliberately and cover with fast unit tests. |
| `faster_whisper_engine.py`, `openai_whisper_engine.py`, `whisper_cpp_engine.py` | Whisper-family adapters. | Keep optional imports inside loader paths and preserve option mapping. |
| `kroko_onnx_engine.py` | Kroko-ONNX offline/streaming adapter, native-output suppression, model file handling, streaming session. | High-risk because it owns streaming behavior and filesystem/download helpers. Split only after characterization tests. |
| `sherpa_onnx_engine.py` | Sherpa-ONNX parakeet/moonshine adapters and shared offline backend. | Keep path resolution and decoded output conversion stable. |
| `hf_transformers_engines.py`, `cohere_transcribe_engine.py`, `granite_speech_engine.py`, `moonshine_engine.py` | Hugging Face/Transformers-backed engines and compatibility wrapper modules. | Wrapper modules preserve public import paths; do not remove them during cleanup. |
| `parakeet_engine.py`, `qwen3_asr_engine.py`, `omnilingual_asr_engine.py` | Model-specific ASR adapters. | Preserve dependency error messages, language handling, dtype/device option behavior, and result normalization. |
| `openai_api_engine.py` | Placeholder adapter that raises because request handling is not wired. | Documented unsupported behavior; do not silently turn it into a partial implementation. |
| `_model_utils.py` | Small model-output normalization helpers. | Good candidate for pure helper tests if shared behavior grows. |

## Server And Example Modules

| Module | Responsibility | Boundary notes |
| --- | --- | --- |
| `api_fastapi_server/protocol.py` | Binary audio packet format: little-endian metadata length, JSON metadata, then PCM bytes. | Serialized protocol boundary; validate with `tests/unit/test_fastapi_server_protocol.py`. |
| `api_fastapi_server/server.py` | Maintained browser streaming reference server: settings, session store, websocket app, scheduler, fair queue, shared engine workers, recorder-backed sessions, metrics, and runtime settings. | Large multi-responsibility file. Split by server concern only after tests cover packet handling, scheduler behavior, and session lifecycles. |
| `api_fastapi_server/activation.py` | Server-authoritative foreground state machine: the five canonical phases, the command phase matrix, activation-id validation, monotonic deadlines, `timerRevision` and the timer token that makes a stale callback inert. | The only place that creates or invalidates a deadline. Keep transport and ledger concerns out; every timer change must go through the one arming helper. |
| `api_fastapi_server/activation_commands.py` | Command identity around the state machine: payload validation, the deprecated `extend` alias, the semantic payload key and the session-scoped replay cache. | Must stay free of side effects - it only answers "seen / conflict / new". Anything that changes state belongs behind the controller lock. |
| `api_fastapi_server/segment_ledger.py` | Immutable final-job context, activation/segment terminal accounting, and session-wide ordered result drain. | Keep independent from foreground phase/timer policy and cover every loss path with deterministic terminal-cardinality tests. |
| `api_fastapi_server/static/index.html` | Browser UI, stable client ID, transcription socket and separate live-log socket. | Keep websocket, cursor and session-token assumptions aligned with the server contracts. |
| `VoiceSTT_server/server.py` | Packaged production entry point delegating to the maintained FastAPI implementation. | Preserve installed CLI/module compatibility. |
| `VoiceSTT_server/event_logging.py` | Common envelope, redaction, sink queues, calendar files, SQLite history, retention and live fan-out. | Treat channel names, cursor ordering and transcript policy as persisted/public contracts. |
| `VoiceSTT_server/operations.py` | Model registry, runtime persistence and compatibility facades for audit/performance emitters. | Keep existing event names and configuration behavior compatible. |
| `VoiceSTT_server/stt_server.py` | Legacy control/data websocket server around `AudioToTextRecorder`. | Compatibility path. Do not couple new FastAPI restructuring to legacy server cleanup. |
| `VoiceSTT_server/stt_cli_client.py` | CLI client for the legacy server. | Keep command behavior aligned with the legacy protocol. |
| `app_browserclient/*`, `app_webserver/*`, `app_talk_with_llm/*` | Older/manual examples and demos. | Useful for smoke testing and user workflows, but avoid treating examples as the primary architecture source. |

## Test And Documentation Map

| Area | Files | What they protect |
| --- | --- | --- |
| Engine contracts | `tests/unit/test_*_engine.py`, `tests/unit/test_additional_transcription_engines.py` | Optional dependency errors, option mapping, result conversion, factory selection. |
| Realtime behavior | `tests/unit/test_realtime_text_stabilizer.py`, `tests/unit/test_realtime_boundary_detector.py`, `tests/unit/test_realtime_streaming_transcription.py` | Partial text stabilization, boundary scheduling, streaming engine integration. |
| VAD and pre-roll | `tests/unit/test_silero_vad_backend.py`, `tests/unit/test_preroll.py`, `tests/unit/test_audio_recorder_preroll_integration.py` | Backend selection, pure pre-roll trimming, recorder integration. |
| FastAPI server | `tests/unit/test_fastapi_server_protocol.py`, `tests/unit/test_fastapi_server_multi_user.py`, `tests/unit/test_fastapi_server_multi_user_asr_integration.py`, `tests/unit/test_server_segment_ledger.py`, `tests/unit/test_server_controlled_e2e.py` | Packet contract, session handling, immutable final context, ordered drain, fault terminals, scheduler/recorder and controlled-trigger integration. |
| Activation commands and timers | `tests/unit/test_server_activation_controller.py`, `tests/unit/test_server_activation_commands.py`, `tests/unit/test_server_trigger_contract.py`, `tests/unit/test_server_command_timer_e2e.py` | Phase matrix, non-cumulative refresh, segment watchdog (600/180/30 s), `timerRevision` and stale-callback guards, `commandId` replay and conflicts, stale `activationId`, `closing_input` recovery and generic audio availability. |
| Structured logging | `tests/unit/test_server_operations.py`, `tests/unit/test_fastapi_server_multi_user.py`, `tests/unit/test_openai_compatible_endpoint.py`, `tests/unit/test_project_config.py` | Envelope, redaction, queues, calendar/SQLite persistence, history, session scope and `/data` paths. |
| Manual and smoke scripts | `tests/voicestt_*.py`, `tests/*talk*.py`, `tests/feed_audio.py`, `tools/*` when present | Device, model, websocket, and real-audio workflows that are too expensive for fast unit tests. |
| Docs | `docs/*.md`, `docs/engines/*.md` | User-facing setup, configuration, engine selection, troubleshooting, and refactoring guidance. |

## Dependency Direction

Preferred current direction:

```text
examples / servers / clients
  -> VoiceSTT public recorder/client APIs
  -> recorder helpers
  -> transcription engine factory
  -> engine adapters
  -> optional third-party runtimes
```

Pure helpers such as `core/preroll.py`, `core/realtime_boundary_detector.py`, and
`core/realtime_text_stabilizer.py` should not depend on servers, devices, or model
runtimes. Engine adapters should depend on `base.py`, not on recorder internals.
Servers may construct recorders and inject executors; recorders should not depend
on server modules.

## Refactoring Hotspots

| Hotspot | Why it is risky | Safer first move |
| --- | --- | --- |
| `VoiceSTT/audio_recorder.py` | Central state machine with callbacks, worker lifecycle, VAD, wake words, realtime ASR, final ASR, logging, and public constructor behavior. | Extract or harden pure helpers first; keep `AudioToTextRecorder` as facade/orchestrator. |
| `api_fastapi_server/server.py` | Single file owns settings, API app, queues, workers, sessions, metrics, protocol use, and CLI. | Split data-only settings/protocol helpers before session or scheduler behavior. |
| `VoiceSTT/transcription_engines/kroko_onnx_engine.py` | Combines model discovery/download helpers, backend setup, native-output control, batch transcription, and streaming sessions. | Add tests around option parsing and streaming session behavior before extraction. |
| `VoiceSTT/core/silero_vad.py` | Runtime backend fallback logic depends on optional packages and model files. | Keep resolver behavior characterized before changing backend selection. |
| `VoiceSTT_server/stt_server.py` | Legacy protocol, callbacks, recorder thread, websocket handlers, CLI flags, and shutdown live together. | Treat as compatibility surface; isolate only after old protocol tests exist. |

## Suggested Move-Only Milestones

These are possible future milestones, not work already completed.

| Milestone | Scope | Compatibility plan | Minimal validation |
| --- | --- | --- | --- |
| 1 | Keep documenting module ownership and add missing characterization tests for public paths. | No code movement. | Relevant focused `pytest` tests for touched area. |
| 2 | Extract pure helpers from large modules only when they already have tests or can get fast characterization tests. | Keep old public classes/functions in place and delegate internally. | Unit tests for the helper plus existing integration test for the caller. |
| 3 | Split `api_fastapi_server/server.py` by concern, starting with settings/protocol-adjacent data types. | Keep `create_app()`, `settings_from_args()`, CLI flags, packet format, and websocket routes stable. | FastAPI protocol and multi-user tests. |
| 4 | Split engine adapter internals only after preserving dependency error text and option mapping. | Keep module import paths and factory aliases stable; use wrapper modules where paths move. | Engine-specific unit tests and factory tests. |
| 5 | Consider recorder internal decomposition after enough pure helper and characterization coverage exists. | `AudioToTextRecorder` remains the public facade; constructor, callbacks, `text()`, and error behavior remain compatible. | Recorder integration tests plus focused tests for extracted components. |

## Validation Commands

For documentation-only edits:

```powershell
Get-Content docs\module-map.md
git diff -- docs\module-map.md
```

For future code refactors, choose the smallest relevant gate first, then broaden
only when the touched boundary is shared:

```powershell
python -m pytest tests\unit\test_preroll.py
python -m pytest tests\unit\test_realtime_text_stabilizer.py
python -m pytest tests\unit\test_realtime_boundary_detector.py
python -m pytest tests\unit\test_fastapi_server_protocol.py
python -m pytest tests\unit\test_fastapi_server_multi_user.py
python -m pytest tests\unit\test_additional_transcription_engines.py
```

When a public import path moves, add or keep a wrapper/re-export and include a
compatibility test before changing internal imports.
