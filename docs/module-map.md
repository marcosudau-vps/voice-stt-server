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
| `api_fastapi_server/protocol_v2/` | Frozen protocol v2 wire contract on `/ws/v2`: handshake, strict command envelope, `ProtocolSessionState`, event projection and `session.snapshot`. | Public wire contract. It projects the existing authorities and must never grow a second activation, timer, ledger or close authority. |
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
| `api_fastapi_server/server.py` | Maintained browser streaming reference server: settings, session store, websocket app, scheduler, fair queue, shared engine workers, recorder-backed sessions, metrics, and runtime settings. Since C2 it also owns the two-phase input-close orchestrator (`InputClosePlan`, `_run_input_close`/`_run_recovery_close`), the cancel-accept total order (`_ledger_dispatch_lock -> self.lock`) and the lifecycle epoch that gates late wake/recording callbacks. | Large multi-responsibility file. Split by server concern only after tests cover packet handling, scheduler behavior, and session lifecycles. |
| `api_fastapi_server/activation.py` | Server-authoritative foreground state machine: the five canonical phases, the command phase matrix, activation-id validation, monotonic deadlines, `timerRevision` and the timer token that makes a stale callback inert. Since AP-SRV-030 C2 it also owns the persistent `CloseContext` (reason/cause/command identity) that survives the whole `closing_input` and the identity-bound `input_closed()`. Since AP-SRV-050 it latches an immutable `ActivationTimingPolicy` per activation so a later settings patch can never retarget an armed activation. | The only place that creates or invalidates a deadline. Keep transport and ledger concerns out; every timer change must go through the one arming helper. |
| `api_fastapi_server/activation_commands.py` | Command identity around the state machine: payload validation, the deprecated `extend` alias, the semantic payload key, a two-level replay-capable envelope (`PreparedActivationCommand`) and the session-scoped replay cache. `source` is not semantic for controls; rejected commands with a usable `commandId` still occupy their replay identity. | Must stay free of side effects - it only answers "seen / conflict / new". Anything that changes state belongs behind the controller lock. |
| `api_fastapi_server/segment_ledger.py` | Immutable final-job context, activation/segment terminal accounting, and session-wide ordered result drain. Since C2 it also implements the per-activation cancel publication barrier (`mark_cancel_requested`) and refuses segment acceptance / completion behind that barrier. | Keep independent from foreground phase/timer policy and cover every loss path with deterministic terminal-cardinality tests. |
| `api_fastapi_server/protocol_v2/schema.py` | Frozen v2 vocabulary: message names, phases, the fifteen result codes, the canonical event names, the close codes and the canonical UUID helpers. | Data only. A value that is not in the frozen contract does not belong here. |
| `api_fastapi_server/protocol_v2/handshake.py` | `hello` validation, version negotiation, `protocol.incompatible`/`session.rejected` and the requested-session admission rules. | Refuses before any session exists; never builds a partial session. |
| `api_fastapi_server/protocol_v2/commands.py` | Strict v2 envelope validation and the exhaustive projection of AP-SRV-030 reasons onto the frozen result codes. | Stricter than the v1 parser on purpose. An unmapped known reason raises instead of degrading to `internal_error`. |
| `api_fastapi_server/protocol_v2/session.py` | `ProtocolSessionState`: `stateVersion`, `eventSeq`/`eventId`, the registry that makes a transport retry re-send one logical event, and `advance_state()` for a visible change that has no event of its own. | Owns wire versioning only - never a phase, a deadline, a trigger lock or ledger state. One logical visible change advances the version exactly once. |
| `api_fastapi_server/protocol_v2/events.py` | Projection of the one AP-SRV-030 lifecycle funnel onto the canonical v2 event names, including the derived `activation.phase_changed`. | Reads authoritative values; holds no authority. Legacy names without a v2 equivalent are dropped, not forwarded. |
| `api_fastapi_server/protocol_v2/snapshot.py` | `session.snapshot` from controller, ledger, trigger state and ports, plus the monotonic-to-wall-clock deadline projection. | Pure projection. `pendingActivations` comes from the ledger, never from a current-activation pointer. |
| `api_fastapi_server/protocol_v2/connection.py` | The `/ws/v2` driver: handshake sequencing, admission, ack projection, replay routing and the outbound queue. | Transport agnostic so the protocol is testable without a socket. Uses the session's one replay cache. |
| `api_fastapi_server/protocol_v2/ports.py` | Settings and wake-word adapters: the settings port proxies the AP-SRV-050 session settings control (revision, effective settings, patch result); the wake-word port reports the catalog capabilities and validates a requested selection. | Adapter only. No value storage, no second registry and no second wake engine. |
| `api_fastapi_server/settings_control.py` | AP-SRV-050 settings domain: registry (key/scope/auth/type/constraints/default/applyPolicy), the per-session `SessionSettingsState` (one revision stream per session; since C2 also the atomic `activation_admission_settings()` bundle), the admin-managed `ServerSettingsState` (own revision + persistence overlay, strict startup validation, prepare→persist→commit), atomic patch validation, requested/effective policy resolution and the final-candidate watchdog cross-field rule. | The one settings authority. It never talks to the wire directly; `session_settings.patch`/`settings.changed` are projected by `protocol_v2/connection.py`, and persistence reuses the `RuntimeConfigStore` document. |
| `api_fastapi_server/protocol_v2/identity.py` | `serverVersion` and `serverCommit` for the v2 wire; the commit comes from `VOICESTT_SERVER_COMMIT` and falls back to `unknown`. | Build input, not a runtime lookup. No git subprocess may delay a handshake. |
| `api_fastapi_server/static/index.html` | Browser UI, stable client ID, transcription socket and separate live-log socket. | Keep websocket, cursor and session-token assumptions aligned with the server contracts. |
| `VoiceSTT_server/server.py` | Packaged production entry point delegating to the maintained FastAPI implementation. | Preserve installed CLI/module compatibility. |
| `VoiceSTT_server/event_logging.py` | Common envelope, redaction, sink queues, calendar files, SQLite history, retention and live fan-out. | Treat channel names, cursor ordering and transcript policy as persisted/public contracts. |
| VoiceSTT_server/operations.py` | Model registry, runtime persistence and compatibility facades for audit/performance emitters. Since AP-SRV-050 the `RuntimeConfigStore` preserves the `settingsControlOverlay`/`settingsRevision` sections and unknown top-level fields in both write directions. | Keep existing event names and configuration behavior compatible. |
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
| Protocol v2 wire contract | `tests/unit/test_protocol_v2_contract.py`, `tests/unit/test_protocol_v2_e2e.py`, `tests/unit/test_protocol_v2_races.py`, `tests/unit/test_protocol_v2_state_version.py`, `tests/unit/test_protocol_v2_settings.py` | Frozen contract vectors from `tests/contracts/protocol-v2-vectors.json`, handshake refusals and close codes, strict envelope, replay/conflict, `eventId`/`eventSeq`/`stateVersion`, exactly-once `activation.input_closed`, snapshot combinations, `stateVersion` against visible state (suppression, audio availability, the `closing_input` entry), repeated ordering proofs and the AP-SRV-050 settings wire (patch→ack→settings.changed→snapshot, multi-policy groups, real next-activation timer binding, REST v2 auth). |
| AP-SRV-050 settings domain | `tests/unit/test_settings_control_plane.py`, `tests/unit/test_settings_runtime_persistence.py` | Registry contract, atomic patch/revision rules, requested/effective per apply policy, watchdog cross-field validation, per-session revision isolation, server overlay and concurrency (20x); runtime config coexistence format both directions, restart restore and parallel writes. |
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
