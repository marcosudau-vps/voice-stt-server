# FastAPI Browser Server

> Für die Implementierung eines neuen Clients gibt es eine aus dem aktuellen
> Code abgeleitete, mehrseitige Dokumentation unter
> [client-development/README.md](client-development/README.md). Sie enthält
> Session-/Server-Scope, Binärprotokoll, alle WebSocket-Events, Chronologien,
> Zustandsmodell, HTTP-API sowie Robustheits- und Sicherheitshinweise.

`api_fastapi_server` is the browser streaming reference app for
VoiceSTT. It serves a local browser UI and exposes a WebSocket endpoint that
streams microphone audio into per-session recorder state machines.

This reference server is intended for source checkouts. It is not installed by
the PyPI wheel; keeping it source-only keeps the wheel lean and avoids adding
web-server dependencies for users who only need the recorder/API library. For
pip-only installs, use the Python recorder/API examples instead. If you want
the FastAPI reference server, clone the repository or install from Git.

## Install

```bash
python -m venv .venv-fastapi
source .venv-fastapi/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install -r api_fastapi_server/requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv-fastapi
.\.venv-fastapi\Scripts\Activate.ps1
python -m pip install -U pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install -r api_fastapi_server\requirements.txt
```

Install the optional engine stack you plan to run. See
[transcription-engines.md](transcription-engines.md).

## Run

```bash
python api_fastapi_server/server.py --host 0.0.0.0 --port 8010
```

Open:

```text
http://localhost:8010
```

## Server Overview

The server accepts multiple browser sessions. Each WebSocket receives a
`sessionId`; audio buffers, VAD state, transcript segment ids, clear/reset
commands, realtime text, final text, warnings, and errors are scoped to that
session.

Heavy ASR engines are shared through final and realtime inference lanes instead
of loading one model per browser. Each accepted session owns lightweight
recorder/VAD state and feeds work into the shared scheduler.

The server exposes:

- `GET /`: browser UI.
- `GET /health`: readiness, active sessions/speakers, startup errors,
  scheduler state, and canonical SQLite event-store state/cursors.
- `GET /api/config`: public settings, limits, and supported engines.
- `GET /api/metrics`: counters, queue depth, latency, coalescing, drops, and
  worker utilization.
- `GET /api/logs/events`, `/api/logs/sessions/{sessionId}`, and
  `/api/logs/transcriptions/{transcriptionId}`: authenticated structured event
  history.
- `WS /ws/transcribe`: browser audio stream and command channel.
- `WS /ws/logs`: SQLite-first, session- or admin-scoped cursor replay and live
  events (log protocol version 2).

## Configuration

Core engine flags:

| Flag | Meaning |
| --- | --- |
| `--engine`, `--transcription-engine` | Final transcription engine. |
| `--model` | Final model name or path. |
| `--realtime-engine`, `--realtime-transcription-engine` | Realtime engine. Defaults to final engine when omitted. |
| `--realtime-model` | Realtime model name or path. |
| `--engine-options` | JSON object passed to final engine. |
| `--realtime-engine-options` | JSON object passed to realtime engine. |
| `--download-root` | Model cache or lookup root. |
| `--device` | `cuda` or `cpu`. |
| `--compute-type` | Engine precision/quantization hint. |
| `--language` | Language code. |
| `--use-main-model-for-realtime` | Use one shared model lane for final and realtime work. |

VAD and transcription timing flags:

| Flag | Meaning |
| --- | --- |
| `--min-length-of-recording` | Minimum recording length in seconds. |
| `--min-gap-between-recordings` | Minimum gap between recordings. |
| `--post-speech-silence-duration` | Silence required before finalizing an utterance. |
| `--silero-sensitivity` | Silero VAD sensitivity. |
| `--webrtc-sensitivity` | WebRTC VAD aggressiveness. |
| `--early-transcription-on-silence` | Starts speculative final transcription during silence. |
| `--pre-recording-buffer-duration` | Per-session pre-roll duration. |
| `--realtime-processing-pause` | Fixed realtime update cadence. |
| `--realtime-use-syllable-boundaries` | Enables acoustic boundary scheduling. |
| `--realtime-boundary-detector-sensitivity` | Boundary detector sensitivity. |
| `--realtime-boundary-followup-delays` | Comma-separated follow-up realtime delays. |

Wake word flags:

| Flag | Meaning |
| --- | --- |
| `--wakeword-backend` | Wake word backend passed to `AudioToTextRecorder`; the current FastAPI contract uses `openwakeword`. |
| `--wake-words` | Comma-separated wake words or model names for the selected backend. |
| `--wake-words-sensitivity` | Wake word detection sensitivity. |
| `--wake-word-activation-delay` | Delay before wake word mode becomes active. |
| `--wake-word-timeout` | Time to wait for speech after wake detection before returning to wake wait mode. |
| `--wake-word-buffer-duration` | Wake-word audio removed from the beginning of the recorded segment. |
| `--wake-word-followup-window` | Optional post-recording grace period that keeps the session in Voice mode so follow-up speech can start without repeating the wake word. |
| `--openwakeword-model-paths` | Comma-separated classifier paths, a model directory, or a `models.json` path. |
| `--openwakeword-inference-framework` | OpenWakeWord inference framework, default `onnx`. |

Capacity and scheduling flags:

| Flag | Meaning |
| --- | --- |
| `--max-sessions` | Maximum accepted browser sessions. |
| `--max-active-speakers` | Maximum concurrent active speakers. |
| `--audio-queue-size` | Per-session input queue size. |
| `--max-audio-packet-bytes` | Maximum binary packet size. |
| `--max-audio-queue-seconds-per-session` | Force-finalizes long continuous recordings. |
| `--max-realtime-queue-age-ms` | Drops stale realtime jobs. |
| `--max-final-queue-depth-per-session` | Limits per-session final backlog. |
| `--max-global-inference-queue-depth` | Global scheduler queue limit. |
| `--realtime-degradation-threshold-ms` | Threshold for degraded realtime scheduling. |
| `--realtime-min-audio-seconds` | Minimum audio duration for realtime jobs. |
| `--realtime-max-audio-seconds` | Maximum audio duration for realtime jobs. |
| `--vad-energy-threshold` | Audio energy gate used by the server. |
| `--no-model-warmup` | Disables model warmup. |
| `--model-idle-unload` / `--no-model-idle-unload` | Enables/disables automatic ASR worker unloading. Enabled by default. |
| `--model-idle-timeout-seconds` | Inactivity period before automatic unloading; default `3600`. |
| `--model-memory-policy` / `--no-model-memory-policy` | Enables/disables the CPU model memory guard. |
| `--allow-two-medium-models` / `--no-allow-two-medium-models` | Allows two medium-equivalent lanes (default) or restores the one-medium limit. Standard `large-v3-turbo` counts as medium. |
| `--data-root` | Single root for generated runtime data. Docker uses `/data`; channel directories, audio, SQLite and `config/runtime.json` are derived internally. |
| `--request-logging` / `--no-request-logging` | Enables/disables the audit/request calendar JSONL mirror. |
| `--request-log-stdout` / `--no-request-log-stdout` | Mirrors audit events to stdout. |
| `--request-log-max-bytes` | Maximum size of one audit daily segment. |
| `--request-log-backup-count` | Legacy compatibility setting; calendar files are not deleted automatically. |
| `--performance-logging` / `--no-performance-logging` | Enables/disables performance-event generation at the source. Disabled events do not enter SQLite, replay, live delivery, JSONL, or stdout. |
| `--performance-log-mirror` / `--no-performance-log-mirror` | Enables/disables the optional performance calendar JSONL/stdout mirror without weakening already generated SQLite/live events. |
| `--performance-log-stdout` / `--no-performance-log-stdout` | Mirrors performance events to stdout for Dozzle. |
| `--performance-log-max-bytes` | Maximum size of one performance log file. |
| `--performance-log-backup-count` | Legacy compatibility setting; calendar files are not deleted automatically. |
| `--performance-log-retention-days` | Deletes older performance calendar files and store entries; `0` disables deletion. |
| `--transcription-logging` / `--no-transcription-logging` | Enables/disables the transport-independent transcription calendar JSONL mirror; canonical SQLite/live events remain uniform. |
| `--transcription-log-stdout` / `--no-transcription-log-stdout` | Mirrors transcription events to stdout. |
| `--transcription-log-max-bytes` | Maximum size of one transcription daily segment. |
| `--transcription-log-backup-count` | Legacy compatibility setting. |
| `--transcription-log-retention-days` | Deletes older transcription calendar files and store entries; `0` disables deletion. |
| `--system-event-logging` / `--no-system-event-logging` | Enables/disables the system calendar JSONL mirror. |
| `--system-event-log-stdout` / `--no-system-event-log-stdout` | Mirrors system events to stdout. |
| `--system-event-log-max-bytes` | Maximum size of one system daily segment. |
| `--system-event-log-backup-count` | Legacy compatibility setting. |
| `--system-event-log-retention-days` | Deletes older system calendar files and store entries; `0` disables deletion. |
| `--transcript-mode` | Transcript policy `none`, `final`, or `full`; text is permitted only in the transcription channel. |
| `--request-log-retention-days` | Deletes older audit calendar files and store entries; `0` disables deletion. |
| `--log-calendar-timezone` | Calendar timezone for `YYYY-MM/YYYY-MM-DD.jsonl` paths; default `Europe/Berlin`. |
| `--realtime-log-detail` | `off`, `summary`, or `events` for realtime cadence measurements. |
| `--event-store` / `--no-event-store` | Enables/disables the indexed SQLite history. |
| `--event-log-queue-size` | Bounded queue capacity for optional JSONL/stdout mirrors and commit/store-state wakeups; SQLite commits are not queued here. |
| `--log-live` / `--no-log-live` | Enables/disables `/ws/logs`; enabling it requires the startup SQLite event store. |
| `--save-audio-files` / `--no-save-audio-files` | Enables/disables optional uploaded-audio archiving below the data root. |

Named tuning profiles are available through `--profile`; explicit flags
override profile defaults.

Runtime settings:

`GET /api/config` includes a `runtimeSettings` contract that separates
`activeSessionSafe`, `newSessionOnly`, and `startupOnly` settings. Runtime
changes are explicit:

```bash
curl -X PATCH http://localhost:8010/api/config \
  -H 'Content-Type: application/json' \
  -d '{"settings":{"max_sessions":8,"wake_words":"jarvis"}}'
```

Active-session-safe capacity settings affect the running service. New-session
settings are copied into future browser sessions; existing sessions keep their
recorder configuration. Startup-only settings, including ASR engines and model
paths, are rejected because shared inference workers are already initialized.

Model memory has dedicated authenticated endpoints: `GET`/`PUT`
`/api/models/lifecycle`, plus `POST /api/models/load` and
`POST /api/models/unload`. Idle unloading defaults to 3600 seconds. Active
audio and pending transcriptions block unloading with HTTP 409; otherwise the
worker engines are stopped and their model references are released. A later
realtime or HTTP transcription loads the configured lanes again. Health checks
stay successful while this intentional unloaded state is active.

Both model selectors use the complete mounted local registry. Kroko ONNX and
Faster-Whisper models can therefore be assigned independently to either the
final or realtime lane. Server-side CPU memory policy remains the only optional
capacity guard.

`GET /api/wake-word` returns `availableModels.openwakeword`. Discovery first
uses `models.json` from `VOICESTT_OPENWAKEWORD_MODEL_ROOT`, a configured model
directory, or a directly configured manifest path. Logical IDs map to local
ONNX/TFLite classifier files, `default_model` defines the fallback, and
`pipeline_models` maps embedding and mel-spectrogram assets. Only files that
exist are exposed; helper models such as embedding, mel-spectrogram, and Silero
VAD are excluded from the selectable catalog. The current server admin and
session contracts do not expose Porcupine.

### Performance measurements

The dedicated performance channel never includes transcript text. It emits:

- model load, switch, and unload duration plus RSS/private/peak process memory;
- queue, inference, and total latency per request;
- audio duration, real-time factor (`inference time / audio duration`) and
  inverse real-time factor/throughput (`audio duration / inference time`);
- time from recording start to first non-empty realtime text;
- time from recording start and detected speech end to the final text;
- active session/speaker counts and success/error state.

Structured audit and performance events retain their stable technical `event`
identifier and include a German human-readable `meldung` field for logs and
Dozzle.

The server also writes transport-independent `transcription` events for HTTP
requests and WebSocket segments. All structured channels share a versioned
  event envelope, optional daily calendar mirrors, and canonical SQLite
  history through
`GET /api/logs/events`, `GET /api/logs/sessions/{sessionId}`, and
  `GET /api/logs/transcriptions/{transcriptionId}`, plus replayable live
  delivery through `/ws/logs`. Every normal live event has already committed
  to SQLite. See
[structured logging](structured-logging.md) for the complete contract.

An RSS delta is an approximate process-level model footprint. It is closest to
a per-model value when both lanes share the same engine/model; if two different
models load together, the delta represents their combined footprint. Compare
cold load and warm inference separately and use latency percentiles (especially
p50, p95, and p99) over repeated runs. Accuracy comparisons require a reference
transcript and should report WER/CER in an offline benchmark; they cannot be
derived safely from production traffic alone.

`GET /api/logging` returns all structured source, mirror, calendar, realtime
and live delivery settings plus `logProtocolVersion`, `deliveryMode`, replay
availability and sanitized store state/cursors. For performance events,
`performance.enabled` controls generation and `performance.mirrorEnabled`
controls the optional JSONL/stdout mirror. Runtime-safe values can be changed
without UI coupling through `PUT /api/logging`; the corresponding request
fields are `performanceEnabled` and `performanceMirrorEnabled`. The response
reports applied and rejected fields. SQLite store activation and its path
remain startup-only.

A normal session receives `hello.logAccess` and can use its token only for its
own `audit`, `transcription`, and `performance` history. Administrators can
query or subscribe across all retained sessions and include `system`; omitting
the session and channel filters explicitly means all sessions/channels. Tokens
are sent through
`X-VoiceSTT-Log-Token` or the first `/ws/logs` subscribe message, never in a
URL. Admin-Key comparison is constant-time. The browser Admin drawer supports
bounded global history pages, channel/time filters, and a distinct global live
mode without persisting the key.

`log.hello` exposes protocol version 2, `deliveryMode: "sqlite_first"`, the
server instance, the committed oldest/latest cursor, and a channel-/session-
specific `retentionCursor`. Replay and live both read SQLite. A deleted event
relevant to the requested scope produces `log.gap(reason=retention)`;
a cursor above the high-watermark produces `log.error(code=cursor_ahead)`.
Store failure closes existing log sockets with `1011`, blocks new log access,
and leaves `/ws/transcribe` operational. An empty final recorder result emits
`transcription.discarded(reason=empty_final)` but no empty `final` frame. Each
result is correlated with the generation and segment captured by its actual
transcription-start callback; duplicate recorder results without another start
cannot claim a new segment. Audit, transcription, and system channel
`*_logging_enabled` switches affect only optional JSONL/stdout mirrors.
`performance_logging_enabled` is the intentional source gate;
`performance_log_mirror_enabled` is its independent mirror switch. Every event
that passes source policy remains canonical in SQLite.

## Engine Recipes

Default faster-whisper:

```bash
python api_fastapi_server/server.py \
  --host 0.0.0.0 \
  --port 8010 \
  --engine faster_whisper \
  --model small.en \
  --realtime-model tiny.en \
  --device cuda \
  --language en
```

whisper.cpp CPU:

```bash
python -m pip install "VoiceSTT[whisper-cpp]"
python api_fastapi_server/server.py \
  --host 0.0.0.0 \
  --port 8010 \
  --engine whisper_cpp \
  --model tiny.en \
  --realtime-engine whisper_cpp \
  --realtime-model tiny.en \
  --device cpu \
  --beam-size 5 \
  --beam-size-realtime 1 \
  --download-root test-model-cache/pywhispercpp \
  --engine-options '{"model":{"n_threads":8,"redirect_whispercpp_logs_to":null}}' \
  --realtime-engine-options '{"model":{"n_threads":8,"redirect_whispercpp_logs_to":null},"transcribe":{"single_segment":true,"no_context":true,"print_timestamps":false}}'
```

sherpa-onnx Moonshine CPU:

```bash
python -m pip install sherpa-onnx
python api_fastapi_server/server.py \
  --engine sherpa_onnx_moonshine \
  --model sherpa-onnx-moonshine-tiny-en-int8 \
  --realtime-engine sherpa_onnx_moonshine \
  --realtime-model sherpa-onnx-moonshine-tiny-en-int8 \
  --device cpu \
  --language en \
  --download-root test-model-cache/sherpa-onnx \
  --engine-options '{"num_threads":2,"provider":"cpu"}' \
  --realtime-engine-options '{"num_threads":2,"provider":"cpu"}' \
  --realtime-processing-pause 0.8 \
  --realtime-use-syllable-boundaries
```

Kroko-ONNX CPU with the same model for final and realtime:

```powershell
$model = "test-model-cache\kroko-onnx\Kroko-EN-Community-64-L-Streaming-001.data"
python api_fastapi_server\server.py `
  --engine kroko_onnx `
  --model $model `
  --realtime-engine kroko_onnx `
  --realtime-model $model `
  --device cpu `
  --language en `
  --engine-options '{"provider":"cpu","num_threads":2}' `
  --realtime-engine-options '{"provider":"cpu","num_threads":1}'
```

Kroko-ONNX final transcription with a lighter realtime engine:

```powershell
$model = "test-model-cache\kroko-onnx\Kroko-EN-Community-64-L-Streaming-001.data"
python api_fastapi_server\server.py `
  --engine kroko_onnx `
  --model $model `
  --realtime-engine whisper_cpp `
  --realtime-model tiny.en `
  --device cpu `
  --language en `
  --engine-options '{"provider":"cpu","num_threads":2}'
```

Parakeet final transcription with a small realtime model:

```bash
python api_fastapi_server/server.py \
  --engine parakeet \
  --model nvidia/parakeet-tdt-0.6b-v3 \
  --realtime-engine faster_whisper \
  --realtime-model tiny.en \
  --device cuda \
  --language en
```

Meta Omnilingual ASR from Linux or WSL2 with Python 3.11.x, using one CTC
model lane for both realtime and final transcription:

```bash
PYTHONPATH=. python api_fastapi_server/server.py \
  --host 0.0.0.0 \
  --port 8010 \
  --engine omnilingual_asr \
  --model omniASR_CTC_1B_v2 \
  --realtime-engine omnilingual_asr \
  --realtime-model omniASR_CTC_1B_v2 \
  --use-main-model-for-realtime \
  --device cuda \
  --compute-type float16 \
  --realtime-processing-pause 0.05 \
  --engine-options '{"batch_size":1,"sample_rate":16000}'
```

Open `http://localhost:8010` from a Windows browser when WSL2 localhost
forwarding is active.

This recipe targets `api_fastapi_server/server.py` from a source checkout,
not the installed `stt-server` console script. Check `stt-server --help`
separately for the installed CLI's supported options.

Wake word mode with OpenWakeWord:

```bash
python api_fastapi_server/server.py \
  --engine faster_whisper \
  --model small.en \
  --realtime-model tiny.en \
  --wakeword-backend openwakeword \
  --openwakeword-model-paths /models/openwakeword/models.json \
  --wake-words hey_jarvis \
  --wake-words-sensitivity 0.7 \
  --wake-word-timeout 5 \
  --wake-word-followup-window 5
```

## WebSocket Protocol

The browser sends binary audio packets to `/ws/transcribe`:

- 4 bytes little-endian unsigned metadata length
- UTF-8 JSON metadata
- 16-bit little-endian mono PCM audio bytes

Metadata example:

```json
{
  "sampleRate": 48000,
  "channels": 1,
  "format": "pcm_s16le",
  "frames": 1920
}
```

Text commands are JSON objects:

```json
{"type": "start"}
```

Supported commands:

- `start`
- `stop`
- `clear`
- `ping`
- `metrics`

Server event types include:

- `hello`: assigns `clientId` and `sessionId`.
- `ready`: model lanes are initialized.
- `timeline`: timing events for wake word state, recording start/end,
  realtime updates, final transcription start, final transcript delivery, and
  discarded empty final results.
- `realtime`: interim text for a session-local `segmentId`.
- `final`: final text for the same session-local `segmentId`.
- `status`: session/server state.
- `warning`: recoverable issue.
- `error`: command, packet, admission, or runtime error.
- `clear`: session transcript reset.
- `pong`: ping response.
- `metrics`: per-session metrics response.

Transcript-bearing events include `sessionId` and are routed only to that
session. `realtime` and `final` events may include a `segment` object with
recording start/end timestamps, duration, pre-recording buffer range, and wake
word timing when available.

### Wake Word build catalog (protocol v2)

```text
GET  /api/v2/wake-words           public, versioned build catalog
POST /api/v2/wake-words/refresh   admin (X-Admin-Key), hot reload
```

The server ships its wake-word models inside the package
(`VoiceSTT/assets/wakeword_models/`) and never downloads them at runtime.
`models.json` in that directory is the canonical catalog authority: it declares
canonical ids, display names, explicit aliases, artifact versions and the shared
pipeline models. `GET /api/v2/wake-words` publishes that catalog with
`catalogRevision`, `available` and an optional `unavailableReason`, and never
exposes a filesystem path.

`POST /api/v2/wake-words/refresh` uses the same admin guard as
`PATCH /api/v2/settings/server`. It rebuilds and fully validates a candidate and
swaps atomically only on total success; a failed refresh answers HTTP 422 and
leaves the running catalog untouched. It affects new session admissions only -
a running session keeps the models it was admitted with. An availability change
emits `wakeword.availability_changed` on every live v2 session.

`VOICESTT_WAKEWORD_ASSET_ROOT` points the server at a bundle outside the
package. See [Wake Words](wake-words.md) for the complete contract.

### Session-local Wake Word profile (legacy v1 endpoint)

Wake Word behavior is resolved before the session recorder is created:

```text
/ws/transcribe?wakeWordEnabled=false
/ws/transcribe?wakeWordEnabled=true
/ws/transcribe?wakeWordEnabled=true&wakeWords=hey_jarvis
```

`wakeWordEnabled` is the decisive tri-state selector: absent, `null`, or
`inherit` copies the server baseline; `false` disables Wake Word for this
session; `true` activates an OpenWakeWord profile. Optional query parameters
are `wakeWordBackend`, `wakeWords`, `wakeWordInferenceFramework`, `wakeWordSensitivity`,
`wakeWordActivationDelay`, `wakeWordTimeout`, `wakeWordBufferDuration`, and
`wakeWordFollowupWindow`.

Invalid optional values fall back to the corresponding server value, active
OpenWakeWord profile, or manifest default and are reported under
`sessionConfig.fallbacks` and `sessionConfig.warnings`. If no local model can
satisfy an enabled profile, the server sends a `session_config` error and
closes with code 1008. `hello` and `ready` contain the same effective
`sessionConfig` and a path-free logical model catalog under
`sessionCapabilities`.

## Metrics And Health

Use `/health` for readiness checks and basic load:

```bash
curl http://localhost:8010/health
```

Use `/api/metrics` for operational detail:

```bash
curl http://localhost:8010/api/metrics
```

Metrics include active session counts, scheduler health, queue depths,
coalesced realtime jobs, dropped stale jobs, p50/p95 queue delay and inference
latency, and worker busy ratios.

## Browser UI Behavior

The UI connects to `/ws/transcribe`, sends browser microphone audio packets, and
keeps session-local realtime and final transcript blocks related by
`segmentId`. Each transcript block shows recording start, recording end,
duration, pre-roll, and wake timing when the server has that data. The left
timeline lists wake wait/detect/timeout events, recording start/end, realtime
updates, and final transcript delivery. Clear/reset affects only the issuing
session.

Admission limits are explicit. When `--max-sessions` is reached, new websocket
clients receive an admission error and close code `1013`. When active speaker
capacity is reached, accepted sessions receive warnings while existing final
work is preserved where possible.

## Tests

Fast fake-scheduler tests:

```bash
python -m unittest -v \
  tests.unit.test_fastapi_server_protocol \
  tests.unit.test_fastapi_server_multi_user
```

Opt-in real-engine load/quality/performance test:

```bash
VOICESTT_RUN_FASTAPI_MULTI_USER_PERF=1 \
python -m unittest -v tests.unit.test_fastapi_server_multi_user_asr_integration
```

Windows `cmd.exe` helper for a sherpa-onnx Moonshine performance run:

```cmd
api_fastapi_server\run_multi_user_perf.cmd
```

More test details are in [testing.md](testing.md).

## Deployment Notes

- Treat [`build/BUILD.md`](../build/BUILD.md) as the canonical image/build
  reference. The concrete Pro-enabled VPS release is documented separately in
  [`build/vps`](../build/vps/README.md).
- Use Linux or WSL2 for CUDA-heavy engines such as Parakeet, Qwen vLLM, and
  larger Transformers models. Omnilingual ASR currently needs Linux/WSL2 with
  Python 3.11.x.
- Install Kroko-ONNX with `VoiceSTT[kroko-builder,silero-onnx-cpu]` and
  `stt-install-kroko --build --variant free` (or the explicitly licensed Pro
  variant) before selecting `kroko_onnx` for recorder-based
  server use. On Windows, use Python 3.12 x64 and start Docker Desktop first.
- Keep model caches on persistent storage so restarts do not redownload models.
- Put the server behind a reverse proxy when exposing it beyond localhost.
- Size `--max-sessions`, `--max-active-speakers`, queue depths, and model lanes
  for the selected engine and hardware.
- Use `/health` for readiness and `/api/metrics` for load/latency monitoring.
