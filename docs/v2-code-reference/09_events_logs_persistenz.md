# 09 – Events, Logs und Persistenz

## 1. Strukturierte Eventkanäle

`StructuredEventHub` (`VoiceSTT_server/event_logging.py:697`) normalisiert ein
Ereignis einmal und verteilt es an die konfigurierten Senken. Im Servercode
werden vier Kanäle verwendet:

| Kanal | Verzeichnis (mit `--data-root`) | aktiv per | Stdout per |
| --- | --- | --- | --- |
| `audit` | `<root>/logs/audit` | `request_logging_enabled` | `request_log_stdout` (Default an) |
| `performance` | `<root>/logs/performance` | `performance_logging_enabled` | `performance_log_stdout` (Default an) |
| `transcription` | `<root>/logs/transcription` | `transcription_logging_enabled` | `transcription_log_stdout` (Default aus) |
| `system` | `<root>/logs/system` | `system_event_logging_enabled` | `system_event_log_stdout` (Default aus) |

Ereignisnamen, die im Servercode vorkommen (Auswahl): `server.starting`,
`server.ready`, `server.stopping`, `session.accepted`, `session.rejected`,
`session.closed`, `authentication.failed`, `config.updated`,
`language.updated`, `models.loaded`, `models.unloaded`, `models.switched`,
`models.load_failed`, `activation.started`, `activation.refreshed`,
`activation.closed`, `activation.drained`, `transcription.started`,
`transcription.recording_started`, `transcription.recording_ended`,
`transcription.accepted`, `transcription.realtime_emitted`,
`transcription.completed`, `transcription.cancelled`,
`transcription.failed`, `transcription.performance_summary`,
`inference.completed`, `stream.first_text`, `stream.final_text`,
`queue.limit_reached`, `scheduler.overloaded`, `worker.failed`,
`recorder.failed`, `wakeword.detected`, `wakeword.timeout`,
`wakeword.wait_started`, `wakeword.wait_ended`,
`wakeword.followup_started`, `wakeword.followup_timeout`,
`watchdog.warning`.

Schweregrad über `ChannelLogManager.event`: Endung `.failed` → `error`;
`.rejected`, `.warning`, `.timeout`, `.dropped` → `warning`; sonst `info`.

Korrelationsfelder (`CONTEXT_FIELDS`): `clientId`, `requestId`, `segmentId`,
`sessionId`, `transcriptionId`, `transport`. Jedes Ereignis trägt zusätzlich
die `server_instance_id` (pro Prozess neu, `uuid4().hex`).

`realtime_log_detail` (`off`, `summary`, `events`) steuert die Menge der
Realtime-Ereignisse.

## 2. Redaktion (Datenschutz)

`sanitize_event_value` (`event_logging.py:116`) entfernt rekursiv:

- Felder mit Secret-Namen (u. a. `accesstoken`, `apikey`, `authorization`,
  `cookie`, `password`, `secret`, `token`, `xvoicesttadminkey`,
  `xvoicesttlogtoken` und alles, was auf `apikey`, `token`, `secret`, …
  endet);
- Rohaudio-Felder (`audio`, `pcm`, `samples`, `waveform`, …) und alle
  Bytewerte;
- Query-Felder (`query`, `querystring`, …);
- Transkripttext-Felder (`text`, `rawText`, `stableText`, …) abhängig von
  `transcript_log_mode`:
  - `none`: nie,
  - `final`: nur im Kanal `transcription` beim Ereignis
    `transcription.completed`,
  - `full`: nur im Kanal `transcription`,
  - im Kanal `performance` nie.

Zusätzlich maskieren Muster `Authorization/api_key/password/secret: …` und
`Bearer …` in Freitexten (`_SECRET_TEXT_PATTERN`, `_BEARER_PATTERN`).

`transcript_log_mode` Default: `final`, wenn `request_log_transcripts` aktiv ist
(Default), sonst `none` (`settings_from_args`).

## 3. Senken

### JSONL-Dateien

`CalendarJsonlSink` schreibt **eine Datei pro Kalendertag und Kanal** in
`<kanal>/<YYYY-MM>/<YYYY-MM-DD>.jsonl`; der Tag wird in
`log_calendar_timezone` (Default `Europe/Berlin`) bestimmt. Bei
`*_max_bytes` > 0 wird auf `<Datum>.<n>.jsonl` fortgesetzt;
`*_backup_count` und `*_retention_days` begrenzen Anzahl und Alter
(Defaults: 10 MiB, 12, 0 = unbegrenzt).

### SQLite-Eventstore

`SQLiteEventStore` (`event_logging.py:438`), Datei
`<root>/logs/voicestt-events.sqlite3`, aktiv mit `event_store_enabled`
(Default an). Tabellen:

```sql
CREATE TABLE IF NOT EXISTS events (
  cursor INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL UNIQUE, timestamp TEXT NOT NULL,
  channel TEXT NOT NULL, event_name TEXT NOT NULL, severity TEXT NOT NULL,
  server_instance_id TEXT NOT NULL, transport TEXT, client_id TEXT,
  session_id TEXT, request_id TEXT, transcription_id TEXT, segment_id TEXT,
  payload_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS retention_watermarks (
  channel TEXT NOT NULL, session_id TEXT NOT NULL, cursor INTEGER NOT NULL,
  PRIMARY KEY (channel, session_id));
```

Der `cursor` ist die Ordnungs- und Replay-Achse für `GET /api/logs/events`
(`afterCursor`, `nextCursor`, `oldestCursor`, `latestCursor`,
`retentionCursor`) und `/ws/logs` (`afterCursor`, `log.gap`,
`log.replay_completed`). Die Auslieferung ist „SQLite-first“
(`deliveryMode: "sqlite_first"`).

Abhängigkeit: `log_live_enabled` erfordert `event_store_enabled`
(`ServerSettings.__post_init__`). `/health.ok` ist bei aktivem Live-Log nur
wahr, wenn der Store verfügbar ist.

Gegendruck: Ereignisse laufen über eine `BoundedPriorityEventQueue` der Größe
`event_log_queue_size` (Default 10000, Minimum 100).

### Audiodateien

Mit `save_audio_files` (Default aus, `VOICESTT_SAVE_AUDIO_FILES`) werden
Aufnahmen unter `<root>/logs/audio` abgelegt (`audio_log_dir`).

## 4. Persistente Laufzeitkonfiguration

`RuntimeConfigStore` (`VoiceSTT_server/operations.py:400`) schreibt
`<root>/config/runtime.json` atomar (Temp-Datei + `os.replace`) unter einem
modulweiten Lock. Das Dokument enthält koexistierend:

```json
{"version": 1, "updatedAt": "...",
 "settings": {"<server-setting>": "..."},
 "settingsControlOverlay": {"<v2-key>": "..."},
 "settingsRevision": 3}
```

Kroko-Credentials werden vor dem Schreiben entfernt
(`redact_kroko_credentials(..., drop=True)`); Admin-/OpenAI-Schlüssel werden
beim Laden ignoriert (`create_app`). Ohne `data_root_path` gibt es keine
Persistenz.

## 5. V2-Protokollereignisse

Die V2-Domänenereignisse (Seite 07) sind **nicht** identisch mit den
Logkanälen: Sie werden pro Verbindung mit `eventSeq`/`stateVersion` nummeriert
und nur an den V2-Client gesendet. Der `EventProjector`
(`protocol_v2/events.py`) leitet sie aus genau einer Domänenquelle ab
(`RecorderBackedRealtimeSession._publish_timeline_event`), wodurch z. B.
`activation.input_closed` genau einmal entsteht.

## Primäre Quellen

- [`VoiceSTT_server/event_logging.py`](../../VoiceSTT_server/event_logging.py) – `sanitize_event_value` (116), `CalendarJsonlSink` (314), `SQLiteEventStore` (438), `StructuredEventHub` (697), `ChannelLogManager` (1322)
- [`VoiceSTT_server/operations.py`](../../VoiceSTT_server/operations.py) – `RuntimeConfigStore`
- [`api_fastapi_server/server.py`](../../api_fastapi_server/server.py) – `ServerSettings.__post_init__`, `_log_events_response`, `websocket_logs`
- Tests: [`tests/unit/test_fastapi_server_multi_user.py`](../../tests/unit/test_fastapi_server_multi_user.py), [`tests/unit/test_protocol_v2_e2e.py`](../../tests/unit/test_protocol_v2_e2e.py), [`tests/unit/test_settings_runtime_persistence.py`](../../tests/unit/test_settings_runtime_persistence.py), [`tests/unit/test_server_operations.py`](../../tests/unit/test_server_operations.py), [`tests/unit/test_server_segment_ledger.py`](../../tests/unit/test_server_segment_ledger.py), [`tests/unit/test_protocol_v2_state_version.py`](../../tests/unit/test_protocol_v2_state_version.py)
