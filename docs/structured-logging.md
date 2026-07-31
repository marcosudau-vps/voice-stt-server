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
under `data`. `eventId` is unique; `cursor` is a monotonically increasing
position from the persistent event store and is used for pagination and live
reconnect.

HTTP and WebSocket transcription events use the same `transcription.*` event
names. `transport` records the protocol difference. One HTTP request owns one
transcription ID. A WebSocket session can own multiple transcription IDs, one
per final segment.

Final transcript text is written only when `request_log_transcripts` is
enabled. Realtime text is never written to the performance channel.

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
```

An existing file is appended after a same-day restart. When a daily file
reaches its configured size, numbered daily segments are created, for example
`2026-07-30.1.jsonl`. Event timestamps remain UTC. Calendar paths use
`log_calendar_timezone`, which defaults to `Europe/Berlin`.

The legacy `*BackupCount` settings remain accepted for configuration
compatibility, but do not delete calendar files. Numbered segments continue as
needed so the configured size limit is not silently abandoned. Retention will
only be introduced with a separately confirmed age-based policy.

Legacy values ending in `.jsonl` are accepted as channel-root hints. For
example `/data/logs/voicestt-requests.jsonl` writes below
`/data/logs/voicestt-requests/YYYY-MM/`.

## Transcription lifecycle

The `transcription` channel includes:

- `transcription.started`
- `transcription.recording_started`
- `transcription.recording_ended`
- `transcription.completed`
- `transcription.failed`
- `transcription.rejected`
- wake-word wait, detection, timeout and follow-up events

The system lifecycle currently uses `server.starting`, `server.ready`,
`server.stopping`, and `server.component_failed`.

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
- zero or more replayed `log.event` messages
- `log.replay_completed`
- subsequent live `log.event` messages
- `log.keepalive` during idle periods
- `log.gap` if the subscriber was too slow and its bounded queue dropped data
- `log.error` for protocol or authorization failures

After `log.gap`, a client should reconnect with the cursor of its last
successfully processed `log.event`; the persistent replay then fills the
subscriber-local gap. The bundled browser client does this automatically.

An administrator may use the configured admin key as `accessToken` and can
subscribe across channels and, when omitted, across sessions.

The bundled browser client opens this second WebSocket automatically after
`hello`, replays the current session from its last cursor and adds incoming
structured events to its event log. Older or broader history remains available
through the HTTP endpoint.

## Configuration

The versioned YAML configuration and `GET`/`PUT /api/logging` expose channel
enablement, stdout mirroring, channel directories, daily segment sizes,
calendar timezone, realtime detail and live access.

The SQLite path, queue size and store enablement are startup settings. File
channel settings, timezone, transcript policy and live access can be changed
at runtime. `log_level` is also applied immediately to the active root,
FastAPI, Uvicorn and managed VoiceSTT console loggers.

The structured writer uses a bounded background queue so logging does not
normally block transcription. Audit and transcription events get a short
last-chance enqueue window when the queue is full; lower-priority performance
events may be dropped. Live subscribers have independent bounded queues.
