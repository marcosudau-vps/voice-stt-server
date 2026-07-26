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
- structured stdout/rotating-file request logs and optional audio archiving;
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

The startup policy permits one model up to `medium` together with one model
strictly smaller than `medium`. Reusing the same model consumes one model lane.
Larger or ambiguous two-model combinations fail before any model is loaded.

Clients that must send `model=whisper-1` can choose a loaded local lane with
the `X-VoiceSTT-Model` header or the multipart field `voicestt_model`.
`GET /v1/models` reports available local models. The browser **Settings** drawer
uses the typed `/api/language`, `/api/wake-word`, `/api/logging`, and
`/api/models/active` endpoints. Remote administration requires the configured
admin key; persisted runtime JSON never contains secrets.

See [the complete Windows CPU deployment guide](../docs/windows-cpu-deployment.md).
