# Structured logging and client log access

The FastAPI server exposes four structured event channels in addition to its
normal Python/Uvicorn process log:

| Channel | Purpose |
| --- | --- |
| `system` | Server lifecycle and selected operational failures. |
| `audit` | Configuration, model lifecycle, authentication and session actions. |
| `transcription` | Transport-independent transcription and wake-word lifecycle. |
| `performance` | Numeric model, queue, inference and realtime cadence measurements. |

## Common event envelope

Every structured event uses the same versioned outer schema:

```json
{
  "schemaVersion": 1,
  "eventId": "b8c...",
  "cursor": 18427,
  "timestamp": "2026-07-30T14:26:41.537Z",
  "channel": "transcription",
  "event": "transcription.completed",
  "severity": "info",
  "serverInstanceId": "c25...",
  "transport": "websocket",
  "clientId": null,
  "sessionId": "session-456",
  "requestId": null,
  "transcriptionId": "session-456:0:3",
  "segmentId": 3,
  "data": {
    "language": "de",
    "engine": "faster_whisper",
    "model": "medium"
  }
}
```

Context identifiers remain at the top level. Event-specific values are stored
under `data`. `eventId` is unique; `cursor` is assigned centrally before fan-out
and is strictly increasing even if an individual sink temporarily fails. It is
used for pagination and live reconnect. A sink failure creates an explicit gap
rather than reusing a cursor.

HTTP and WebSocket transcription events use the same `transcription.*` event
names. `transport` records the protocol difference. One HTTP request owns one
transcription ID. A WebSocket session can own multiple transcription IDs, one
per final segment.

`transcript_log_mode` controls transcript content:

- `none`: no transcript text in structured events;
- `final`: final text only in `transcription.completed` on the
  `transcription` channel;
- `full`: transcript fields are permitted on the `transcription` channel.

The legacy `request_log_transcripts` Boolean remains compatible with
`none`/`final`. Audit and performance events never contain transcript text.
The central sanitizer recursively removes credentials, authorization values,
cookies, query strings, binary/audio fields, and disallowed transcript fields
before an event reaches any file, SQLite, stdout, or live subscriber sink.

## Calendar file layout

Each enabled channel writes to a channel root, then a `YYYY-MM` directory and
one `YYYY-MM-DD.jsonl` file:

```text
/data/logs/
  audit/
    2026-07/
      2026-07-30.jsonl
  transcription/
    2026-07/
      2026-07-30.jsonl
  performance/
    2026-07/
      2026-07-30.jsonl
  system/
    2026-07/
      2026-07-30.jsonl
  audio/
  voicestt-events.sqlite3
/data/config/
  runtime.json
```

`data_root_path` beziehungsweise `--data-root` ist der einzige konfigurierbare
Pfad für erzeugte Laufzeitdaten. Die Kanalordner, das Audioarchiv, die
SQLite-Datenbank und `config/runtime.json` werden intern daraus abgeleitet.

An existing file is appended after a same-day restart. When a daily file
reaches its configured size, numbered daily segments are created, for example
`2026-07-30.1.jsonl`. Event timestamps remain UTC. Calendar paths use
`log_calendar_timezone`, which defaults to `Europe/Berlin`.

The legacy `*BackupCount` settings remain accepted for configuration
compatibility, but do not delete calendar files. Numbered segments continue as
needed so the configured size limit is not silently abandoned. Each channel
has an independent `*_log_retention_days` setting. The default `0` disables
automatic deletion. A positive value prunes only dated JSONL files below that
channel's configured root and applies the same channel policy to SQLite.

Einzelne Kanalpfade sind nicht konfigurierbar. Dadurch können insbesondere im
Docker-Betrieb keine Kanäle versehentlich außerhalb des `/data`-Mounts landen.

## Transcription lifecycle

The `transcription` channel includes:

- `transcription.accepted`
- `transcription.started`
- `transcription.recording_started`
- `transcription.recording_ended`
- `transcription.completed`
- `transcription.failed`
- `transcription.rejected`
- `transcription.cancelled`
- wake-word wait, detection, timeout and follow-up events

The system/audit channels also report authentication failures, recorder or
worker failures, scheduler overload, storage failures, and recovered
subscriber drops where applicable.

WebSocket realtime outputs are measured in the performance channel:

- `transcription.realtime_emitted`
- `transcription.performance_summary`
- existing first-text, final-text and inference events

`realtime_log_detail` controls the detail:

- `off`: no realtime detail or summary;
- `summary`: final cadence summary only;
- `events`: every emitted realtime timestamp plus the final summary.

The per-event measurement contains sequence, interval from the previous
realtime output, elapsed time, character counts and stabilization metadata but
no transcript text.

## Persistent history

When `event_store_enabled` is true, all structured events are also stored in
SQLite. The default database is:

```text
logs/voicestt-events.sqlite3
```

SQLite runs in WAL mode and indexes timestamp, channel, event name, client,
session and transcription identifiers.

History is available at:

```http
GET /api/logs/events
GET /api/logs/sessions/{sessionId}
GET /api/logs/transcriptions/{transcriptionId}
```

Supported query parameters:

- `channels`
- `events`
- `sessionId`
- `transcriptionId`
- `from`
- `to`
- `afterCursor`
- `limit` (maximum 1000)

Administrators authenticate like the other admin endpoints. A normal session
client sends its token through `X-VoiceSTT-Log-Token`; it can only read its own
session and the `audit`, `transcription`, and `performance` channels.

## Live log WebSocket

The transcription WebSocket `hello` response contains:

```json
{
  "logAccess": {
    "websocketPath": "/ws/logs",
    "historyPath": "/api/logs/events",
    "accessToken": "...",
    "sessionId": "...",
    "expiresAt": "..."
  }
}
```

The access token is scoped to that session and is valid for 24 hours within
the current server process. It is sent in the first WebSocket message rather
than in the URL:

```json
{
  "type": "subscribe",
  "accessToken": "...",
  "sessionId": "...",
  "channels": ["transcription", "performance"],
  "afterCursor": 18000
}
```

The server responds with:

- `log.hello`
- `log.subscribed`
- zero or more replayed `log.event` messages
- `log.replay_completed`
- subsequent live `log.event` messages
- `log.keepalive` during idle periods
- `log.pong` in response to `{"type":"ping"}`
- `log.gap` if a sink or subscriber queue dropped data
- `log.error` for protocol or authorization failures

After a subscriber-local `log.gap`, a client should reconnect with the cursor
of its last successfully processed `log.event`; the persistent replay then
fills the gap. A store-related gap cannot be replayed from that store and must
remain visible as an operational data-loss signal. The bundled browser client
reconnects automatically.

An administrator may use the configured admin key as `accessToken` and can
subscribe across channels and, when omitted, across sessions.

The bundled browser client opens this second WebSocket automatically after
`hello`, replays the current session from its last cursor and adds incoming
structured events to its event log. Older or broader history remains available
through the HTTP endpoint.

The browser persists a random stable client identifier locally and supplies it
as `clientId` when opening `/ws/transcribe`. API clients can supply the same
correlation concept in `X-VoiceSTT-Client-ID`. `clientId`, `sessionId`,
`requestId`, and `transcriptionId` remain separate identifiers. Client IP
addresses and access tokens are not part of session events.

## Configuration

The versioned YAML configuration and `GET`/`PUT /api/logging` expose channel
enablement, stdout mirroring, channel directories, daily segment sizes,
calendar timezone, realtime detail and live access.

The SQLite path, queue size and store enablement are startup settings. File
channel settings, timezone, transcript policy and live access can be changed
at runtime. `log_level` is also applied immediately to the active root,
FastAPI, Uvicorn and managed VoiceSTT console loggers.

Store, channel files, stdout, and live publishing each use an independent
bounded background queue. Emission is non-blocking. On saturation, audit,
errors, and terminal transcription events have higher preservation priority
than performance detail. Every eviction or failed write increments a per-sink
counter and emits a `log.gap`; storage failures additionally create a throttled
`storage.failed` event. Live subscribers have their own bounded queues and
report recovered drops through `log.subscriber.dropped`.
