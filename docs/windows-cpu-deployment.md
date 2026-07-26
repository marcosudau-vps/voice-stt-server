# Windows CPU-only deployment

This is the supported setup for this checkout. It does not enumerate or probe
graphics devices, has no accelerator install scripts, and exposes only `cpu` in
the server CLI. Faster Whisper uses `int8`; Silero, Kroko and OpenWakeWord use
ONNX CPU execution.

## Install the venv

Use 64-bit Python 3.12 and run from the repository root:

```powershell
.\install_windows_cpu.ps1
```

The script creates `.venv`, installs the PyTorch CPU wheel first, and installs
only the requested STT, wake-word, server and voice-interface components. The
Kroko Windows wheel is built separately upstream; install the local wheel into
this same venv if `import kroko_onnx` is not yet available.

Verify the environment:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.version.cuda)"
```

The second value must be `None`.

## External models

The Compose launcher reads `deployment.model_paths` from the root
`config.yaml` and selects the first directory that exists. Windows and VPS
locations are already listed. For another machine, add only one candidate in
that section.

Faster Whisper resolves both direct CTranslate2 directories and Hugging Face
`models--owner--name/snapshots/...` layouts. Kroko resolves `.data` filenames
inside its root. OpenWakeWord requires the selected classifier plus
`melspectrogram.onnx` and `embedding_model.onnx`. Missing files cause a clear
startup error; runtime model downloads are not attempted.

## Start the shared server

```powershell
.\.venv\Scripts\stt-server.exe `
  --host 0.0.0.0 --port 8010 `
  --engine faster_whisper --model small `
  --realtime-engine kroko_onnx `
  --realtime-model Kroko-DE-Community-64-L-Streaming-001.data `
  --language de --device cpu --compute-type int8 `
  --admin-api-key "replace-this-admin-key" `
  --runtime-config ".\data\config\runtime.json" `
  --request-log-path ".\data\logs\voicestt-requests.jsonl" `
  --max-sessions 8 --max-active-speakers 4
```

The root page is the browser client. Every WebSocket connection owns its audio,
VAD and transcript state, while loaded engines and inference workers are
shared. Final jobs cannot be starved by realtime previews. The same scheduler
also accepts normal HTTP transcription requests, so browser realtime, final
transcription and file uploads can run together.

The model-memory guard permits two medium-equivalent model lanes. The original
Faster Whisper `large-v3-turbo` is classified as medium-equivalent; ordinary
Large models and specially named Large/Turbo variants are not. Two requests
routed to the same model reuse the same lane. Use
`--no-allow-two-medium-models` for the former one-medium limit, or
`--no-model-memory-policy` only when you intentionally accept the additional
CPU/RAM risk.

ASR workers unload automatically after one hour without transcription activity.
Idle browser/WebSocket connections do not pin those workers in RAM. Configure
this with `--model-idle-timeout-seconds`, disable it with
`--no-model-idle-unload`, or use the authenticated controls in the settings UI.
The API equivalents are `GET`/`PUT /api/models/lifecycle`,
`POST /api/models/load`, and `POST /api/models/unload`.

Unloading never interrupts active audio or pending requests; those attempts
return HTTP 409. The next realtime or normal transcription lazily reloads the
configured models. `/health` remains healthy while models are intentionally
unloaded and exposes their lifecycle state separately.

## OpenAI-compatible endpoint

Send multipart requests to `POST /v1/audio/transcriptions`. Supported request
fields are `file`, `model`, `language`, `prompt`, `response_format`,
`temperature`, `timestamp_granularities[]`, `include[]`, `stream`, `threshold`,
`known_speaker_names[]`, and `known_speaker_references[]`.

Formats are `json`, `text`, `srt`, `verbose_json`, `vtt`, and
`diarized_json`. `stream=true` returns SSE delta and done events. The configured
models do not contain a diarization model, so diarized output is explicitly
reported as single-speaker compatibility output instead of inventing speakers.
Likewise, local segment probabilities are exposed as compatibility log-probability
data where exact hosted token logprobs do not exist.

Set `VOICESTT_API_KEY` to require `Authorization: Bearer ...`. Model aliases
are supplied with `--openai-model-aliases`, for example:

```powershell
--openai-model-aliases '{"whisper-1":"final","fast":"realtime"}'
```

Some clients insist on sending the literal model name `whisper-1`. Those clients
can select one of the two loaded local lanes without breaking compatibility:

```powershell
$headers = @{ "X-VoiceSTT-Model" = "Kroko-DE-Community-64-L-Streaming-001.data" }
curl.exe -X POST http://127.0.0.1:8010/v1/audio/transcriptions `
  -H "X-VoiceSTT-Model: small" `
  -F "model=whisper-1" -F "file=@sample.wav"
```

The equivalent multipart fields are `voicestt_model` and `model_override`.
The field takes precedence over the header. Overrides are deliberately accepted
only together with `model=whisper-1`; otherwise the server returns an explicit
400 response. Response headers show the requested model, effective local model,
route, override source, and request ID. `GET /v1/models` lists every mounted
model and marks currently loaded lanes.

## Administration and logging

The browser client's **Settings** drawer exposes the common operations without
requiring the large generic JSON document. On a remote address all modifying
and detailed configuration endpoints require `X-VoiceSTT-Admin-Key` (or a
Bearer token) and remote administration stays disabled if no admin key is set.

- `GET/PUT /api/language`
- `GET/PUT /api/wake-word`
- `GET/PUT /api/logging`
- `GET /api/models` and `GET/PUT /api/models/active`
- `POST /api/config/validate` and `POST /api/config/reload`
- `GET/PATCH /api/config` for the complete existing configuration surface

Model changes are transactional: they are only allowed with zero WebSocket
sessions, only resolve files in the mounted registries, and restore the previous
workers if the replacement fails. The UI closes its own idle socket before a
switch. Other connected clients must be disconnected first. Runtime changes are
atomically persisted when `--runtime-config` is configured; API and admin keys
are never written to that file.

Request events are one-line JSON, suitable for both stdout/Dozzle and rotating
files. They include request ID, chosen model/lane, timings, language, status and,
when enabled, transcript text. Uploaded audio archiving is opt-in. Configure it
with `--request-logging`, `--request-log-stdout`, `--request-log-path`,
`--request-log-transcripts`, `--save-audio-files`, and `--audio-log-dir` or use
`PUT /api/logging`.

Performance measurements use their own transcript-free JSONL channel. Enable
and route it with `--performance-logging`, `--performance-log-stdout`, and
`--performance-log-path` (or the matching `VOICESTT_PERFORMANCE_*`
variables). The Docker default writes `/data/logs/voicestt-performance.jsonl`
and mirrors the same events to stdout for Dozzle. These events contain model
load/unload RAM deltas, queue/inference/total latency, realtime factor, time to
first realtime text, and finalization latency.

## Wake-word smoke test

Start the server with the German model pair and:

```powershell
--wakeword-backend openwakeword `
--wake-words hey_jarvis `
--openwakeword-model-paths "S:\MODELS\stt\openwakeword\hey_jarvis_v0.1.onnx" `
--openwakeword-inference-framework onnx
```

Open the UI, press **Start stream**, say “Hey Jarvis”, then speak German. The
state rail and event log must move from wake-word wait to recording, realtime
updates, and a final transcript. Backend, word/model, sensitivity, timeout and
follow-up window can then be changed in **Settings**. Porcupine uses backend
`pvporcupine`, a Porcupine keyword, and requires `PICOVOICE_ACCESS_KEY`.

## Docker on Windows

The image has one stage named `cpu`, installs PyTorch from the CPU wheel index,
and declares no host devices or accelerator runtime. Models are read-only bind
mounts. Start it through the portable configuration launcher:

```powershell
python .\tools\compose.py config
python .\tools\compose.py up --build -d
```

- API/server: `http://localhost:8010`
- proxied standalone browser client: `http://localhost:8081`

The browser container proxies `/ws`, `/health`, `/config`, `/api`, and `/v1` to the
server, so it remains an independent container without hard-coded localhost
assumptions.

The Linux image installs OpenWakeWord's ONNX runtime dependencies explicitly.
Its Python 3.12 package metadata still declares `tflite-runtime`, although that
wheel is unavailable for this interpreter and the configured ONNX path never
imports it. The Docker build therefore removes only that stale metadata line;
the OpenWakeWord source and ONNX dependencies remain unchanged, and `pip check`
must still pass.

## CPU-only compatibility boundary

The old GPU installer batch files and GPU requirement files were removed. All
shipped launchers, Docker services, recorder construction, model factories,
Kroko providers, Silero selection and the documented test commands enforce
CPU execution. Historical accelerator-related names remain only where removing
them would break the upstream Python public API or the unit tests for optional,
uninstalled engines. In this checkout those recorder compatibility arguments
are inert, and configured engine creation overwrites the device with `cpu`
before importing an engine.

## Examples

- `api_fastapi_server/server.py`: full server directly.
- `app_browserclient/server.py`: full server on historical port 9001.
- `app_webserver/server.py`: full server on historical port 5025.
- `app_talk_with_llm/ui_openai_voice_interface.py --check`: dependency check without
  starting audio or loading models.

The browser and web launchers intentionally replaced their old singleton
recorders. That change is required for independent clients, current WebSocket
compatibility, and bounded shared-model concurrency; no server configuration
was removed from the modern implementation.
