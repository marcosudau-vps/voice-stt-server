# VoiceSTT multi-user server (CPU only)

`stt-server` launches the same FastAPI application as
`api_fastapi_server/server.py`. Server and clients are independent
processes and may run on different hosts. One server instance provides:

- isolated WebSocket sessions at `/ws/transcribe`;
- concurrent realtime and final jobs through a fair shared scheduler;
- Faster Whisper and Kroko ONNX model routing;
- OpenAI-compatible `POST /v1/audio/transcriptions`, including SSE streaming;
- health, configuration, session and metrics endpoints;
- a local model registry, transactional model switching and typed admin endpoints;
- four structured event channels (`system`, `audit`, `transcription`, and
  `performance`) with calendar JSONL files, indexed SQLite history, optional
  stdout mirroring, session-scoped live delivery at `/ws/logs`, and optional
  audio archiving;
- CPU-only execution with no device-driver probing;
- local-only model resolution when `VOICESTT_OFFLINE_MODELS=1`.

Portable Docker example (Windows and VPS):

```powershell
python .\tools\compose.py up --build -d
```

All non-secret defaults and path candidates are defined once in the root
`config.yaml`. API keys are read only from the ignored root `.env`.

Open `http://localhost:8010` for the browser client. Use
`stt-server --help` for the complete configuration reference. The old two-port
protocol remains available as `stt-server-legacy`, but the modern server is the
supported multi-user path.

The startup memory policy validates the requested model lanes before loading.
The current versioned default permits two medium-equivalent lanes through
`allow_two_medium_models`; deployments can restore the stricter one-medium
limit. Reusing the same engine and model consumes one shared lane.

Clients that must send `model=whisper-1` can choose a loaded local lane with
the `X-VoiceSTT-Model` header or the multipart field `voicestt_model`.
`GET /v1/models` reports available local models. The browser **Settings** drawer
uses the typed `/api/language`, `/api/wake-word`, `/api/logging`, and
`/api/models/active` endpoints. Remote administration requires the configured
admin key; persisted runtime JSON never contains secrets.

Each `/ws/transcribe` connection can inherit, disable, or explicitly enable
OpenWakeWord for only that session. The effective profile and logical model
catalog are returned in `hello.sessionConfig` and `sessionCapabilities`.
`hello.logAccess` supplies the session-scoped token used for the separate log
WebSocket and history endpoints. See the
[FastAPI server guide](../docs/fastapi-server.md),
[session-local Wake Word reference](../docs/session-wakeword-erweiterung.md),
and [structured logging contract](../docs/structured-logging.md).

See [the complete Windows CPU deployment guide](../docs/windows-cpu-deployment.md).
