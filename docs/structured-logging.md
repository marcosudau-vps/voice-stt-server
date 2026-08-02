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
under `data`. Optional context identifiers are omitted when unavailable; the
`null` values in the example only illustrate their position. `eventId` is
unique. `cursor` is assigned by the canonical SQLite append and therefore
exists only after the transaction has committed. It is strictly increasing,
survives retention deletes and is used for pagination and reconnect. If the
SQLite append fails, the attempted event receives no cursor, is not sent as a
normal `log.event`, and is not mirrored to JSONL or stdout. Failure of an
optional JSONL/stdout mirror never changes the committed cursor or the replay
history.

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
Before deleting SQLite rows, the store persists payload-free retention
watermarks per channel and session. They allow filtered replay to distinguish
a deleted relevant event from a normal gap in the global cursor sequence.

Einzelne Kanalpfade sind nicht konfigurierbar. Dadurch können insbesondere im
Docker-Betrieb keine Kanäle versehentlich außerhalb des `/data`-Mounts landen.

## Transcription lifecycle

The `transcription` channel includes:

- `transcription.accepted`
- `transcription.started`
- `transcription.recording_started`
- `transcription.recording_ended`
- `transcription.completed`
- `transcription.discarded` with `reason: "empty_final"` when the recorder
  returns an empty final result
- `transcription.failed`
- `transcription.rejected`
- `transcription.cancelled`
- wake-word wait, detection, timeout and follow-up events

The system/audit channels also report authentication failures, recorder or
worker failures, scheduler overload, and other operational state changes.

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

An empty final recorder result does not create an empty `final` text frame. It
does terminate the segment exactly once through
`transcription.discarded(reason=empty_final)` and the session timeline event
`final_transcript_discarded`.

## Persistent history

When `event_store_enabled` is true, SQLite is the canonical source for all
structured events. The default database is:

```text
logs/voicestt-events.sqlite3
```

SQLite runs in WAL mode and indexes timestamp, channel, event name, client,
session and transcription identifiers. Sanitization, SQLite append, commit and
cursor assignment happen before optional mirrors or live wakeups. For an event
that has been generated, no mirror setting can suppress SQLite persistence,
replay, or live delivery. `request_logging_enabled`,
`transcription_logging_enabled`, and `system_event_logging_enabled` control
their calendar JSONL/stdout mirrors. Performance is deliberately split:
`performance_logging_enabled` is a source gate and prevents performance events
from being generated, while `performance_log_mirror_enabled` controls only
their optional calendar JSONL/stdout mirror. `realtime_log_detail` remains the
source policy for high-volume realtime performance detail.

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
session and the `audit`, `transcription`, and `performance` channels. An admin
may omit `sessionId` for a global query, include `system`, and filter by all
documented fields. Responses include `authorizationScope`, `allSessions`,
`oldestCursor`, `latestCursor`, scope-specific `retentionCursor`, `nextCursor`, and
`deliveryMode: "sqlite_first"`.

## Live log WebSocket

The transcription WebSocket `hello` response contains:

```json
{
  "logAccess": {
    "available": true,
    "websocketPath": "/ws/logs",
    "historyPath": "/api/logs/events",
    "accessToken": "...",
    "sessionId": "...",
    "expiresAt": "...",
    "logProtocolVersion": 2,
    "deliveryMode": "sqlite_first",
    "replayAvailable": true,
    "serverInstanceId": "...",
    "oldestCursor": 1,
    "latestCursor": 18427
  }
}
```

If live access is disabled or the canonical store is unavailable, `available`
is false, no `accessToken` is issued, and `code` plus `reason` explain the
condition.

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

- `log.hello` with protocol version, delivery mode, server instance, the
  committed oldest/latest cursor, and the scope-specific `retentionCursor`
- `log.subscribed` with `authorizationScope`, effective channels,
  `allChannels`, effective `sessionId`, and `allSessions`
- zero or more replayed `log.event` messages
- `log.replay_completed`
- subsequent live `log.event` messages
- `log.keepalive` during idle periods
- `log.pong` in response to `{"type":"ping"}`
- `log.gap(reason=retention)` when at least one event relevant to the requested
  channel/session scope was deleted after the requested cursor
- `log.error(code=cursor_ahead)` when a cursor is above the committed
  high-watermark
- `log.error(code=event_store_unavailable)` followed by close code `1011` on
  store failure
- `log.error` with close code `1008` for protocol or authorization failures

`/ws/logs` never treats an in-memory payload queue as the event source. A
subscriber first registers for payload-free commit wakeups, captures a SQLite
high-watermark, replays through that watermark, and then repeatedly rescans
SQLite from its own global scan cursor. Wakeups may be coalesced or missed
without data loss. Filtered streams may legitimately skip global cursor
numbers. Only a retention gap represents data no longer present in SQLite.
Because retention is configured per channel, `oldestCursor` remains the global
oldest stored cursor and may be lower than the reported lost range. The server
therefore does not skip directly to `oldestCursor` or `retentionCursor`; it
continues replay from the requested cursor and still delivers every surviving
matching event.

An administrator may use the configured admin key as `accessToken` and can
subscribe across channels and, when omitted, across sessions. Secret
comparison uses constant-time `secrets.compare_digest`. The admin key is never
placed in a URL or serialized event.

The bundled browser client opens this second WebSocket automatically after
`hello`, replays the current session from its last cursor and adds incoming
structured events to its bounded event log. In the Admin drawer, an entered
admin key can load bounded pages of global retained history with channel/time
filters and switch to a clearly labelled server-wide live mode. The key stays
only in the current page's password field; it is not persisted in browser
storage.

The browser persists a random stable client identifier locally and supplies it
as `clientId` when opening `/ws/transcribe`. API clients can supply the same
correlation concept in `X-VoiceSTT-Client-ID`. `clientId`, `sessionId`,
`requestId`, and `transcriptionId` remain separate identifiers. Client IP
addresses and access tokens are not part of session events.

## Configuration

The versioned YAML configuration and `GET /api/logging` expose source and
mirror enablement, stdout mirroring, derived channel directories, daily
segment sizes, calendar timezone, realtime detail and live access. In the
`performance` object, `enabled` is the source gate and `mirrorEnabled` is the
independent optional mirror switch. `PUT /api/logging` changes them through
`performanceEnabled` and `performanceMirrorEnabled`. It rejects individual
file, audio, performance, system, and transcription paths. All generated
locations are derived from the single startup setting `data_root_path`.

The SQLite path, queue size and store enablement are startup settings. File
channel settings, timezone, transcript policy and live access can be changed
at runtime. `log_level` is also applied immediately to the active root,
FastAPI, Uvicorn and managed VoiceSTT console loggers.

`log_live_enabled=true` requires `event_store_enabled=true`; an invalid startup
combination is rejected. The SQLite commit is synchronous and canonical.
Calendar JSONL and stdout remain optional bounded background mirrors. Their
queues preserve audit/errors/terminal events ahead of performance detail and
expose local drop counters, but a mirror overload does not create a client
protocol gap because every committed event remains replayable in SQLite. The
bounded control queue carries only commit/store-state wakeups; missing a normal
commit wakeup is harmless because each handler rescans the committed
high-watermark and performs the same rescan on keepalive.
