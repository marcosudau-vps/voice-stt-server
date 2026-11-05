# 07 – WebSocket-Protokolle

Der Server bietet drei WebSocket-Endpunkte (`api_fastapi_server/server.py`):

| Pfad | Zweck | Handler |
| --- | --- | --- |
| `/ws/transcribe` | Protokoll V1 (Kompatibilitätspfad) | `websocket_transcribe` (9914) |
| `/ws/v2` | Protokoll V2 (eingefrorener Vertrag) | `websocket_protocol_v2` (10123) |
| `/ws/logs` | Live-Logstream | `websocket_logs` (9562) |

Der V2-Docstring hält fest, dass V1 und V2 bewusst getrennte Routen sind:
V1 nimmt die Sitzung aus Query-Parametern **vor** der ersten Nachricht an und
sendet ein **Server**-`hello`; V2 nimmt nichts an, bevor das **Client**-`hello`
validiert ist. V2-Verbindungen werden nicht im `ConnectionManager` registriert,
damit keine V1-Nutzlast eine V2-Verbindung erreicht.

Client-Kennung (beide Protokolle): Query `clientId` oder Header
`X-VoiceSTT-Client-Id`, normalisiert durch `normalized_client_id`.

Audioframes: identisches Binärformat, siehe Seite 05.

---

## 1. Protokoll V1 – `/ws/transcribe`

### Verbindungsaufbau

1. Query-Parameter werden gelesen: Wake-Word-Felder
   (`wakeWordEnabled`, `wakeWordBackend`, `wakeWords`, …) und
   Aktivierungsfelder (`manualTriggerEnabled`, `wakeWordTriggerEnabled`,
   Timer). Ungültig → Accept, `{"type": "error", "where": "session_config",
   "code": ...}`, Close `1008`.
2. Admission (`service.admit_session`). Sitzungslimit erreicht → Accept,
   `{"type": "error", "where": "admission", "limits": {...}}`, Close `1013`.
   Unerwarteter Fehler → `code: "session_initialization_failed"`, Close `1011`.
3. Server sendet `hello`:

```json
{"type":"hello","clientId":"...","sessionId":"<32 hex>","settings":{...},
 "sessionConfig":{...},"activationConfig":{"version":2,"mode":"legacy|controlled", "...":"..."},
 "sessionCapabilities":{...},"limits":{...},"supportedEngines":[...],
 "runtimeSettings":{...},"logAccess":{...}}
```

4. Ist der Dienst bereit, folgen `ready` und ggf. gespeicherte
   Startfehler-Nachrichten.

V1-`sessionId` ist kompakt (32 Hex-Zeichen, `uuid.uuid4().hex`).

### Client → Server (Text-JSON, Feld `type`)

| `type` | Wirkung | Antwort |
| --- | --- | --- |
| `start` | `session.start_streaming()` | – |
| `stop` | `session.stop_streaming()` | – |
| `clear` | `session.clear()` | – |
| `ping` | – | `{"type":"pong","sessionId","serverTime"}` |
| `metrics` | – | `{"type":"metrics","sessionId","metrics":{...}}` |
| `trigger` | Aktivierungsbefehl (`action`, `source`, `commandId`, `activationId`) | `trigger_ack` |
| `audio_availability` | `audioAvailable: bool`, `commandId` | `audio_availability_ack` |
| sonst | – | `{"type":"error","where":"command","message":"Unbekannter Befehl: ..."}` |

Nicht-JSON oder Nicht-Objekt → `error` mit `where: "command"`.

`trigger_ack`:

```json
{"type":"trigger_ack","commandId":"c-1","accepted":true,"reason":"activated",
 "activationId":"...","phase":"waiting_first_speech","sessionId":"..."}
```

Ablehnungsgründe stammen aus `prepare_activation_command` und dem Controller,
z. B. `missing_command_id`, `invalid_command_id`, `invalid_action`,
`invalid_source`, `invalid_payload`, `command_id_conflict`, `invalid_phase`,
`not_active`, `stale_activation`, `activation_locked`, `trigger_suppressed`,
`audio_unavailable`.

### Server → Client (Auswahl der im Code erzeugten `type`-Werte)

`hello`, `ready`, `status`, `realtime`, `final`, `timeline`, `clear`,
`warning`, `error`, `pong`, `metrics`, `trigger_ack`,
`audio_availability_ack`.

`final` trägt u. a. `sessionId`, `segmentId`, `text`, `timestamp`,
`timestampIso`, `requestId`, `activationId`, `activationSequence`,
`segmentSequence` und ggf. `segment`. `realtime` trägt `segmentId`, `text`,
Zeitstempel und – bei Stabilisierung – `recordingId`, `sequence`, `rawText`,
`displayText`, `stableText`, `stableDelta`, `unstableText`,
`committedStableText`, `visualStableText`, `visualUnstableText` u. a.
(`server.py:4845`, `4983`, `5084`).

Bei Verbindungsende: Sitzung entfernt, Audit-Event `session.closed`.

---

## 2. Protokoll V2 – `/ws/v2`

Vokabular: `api_fastapi_server/protocol_v2/schema.py` (reine Daten).
Version `PROTOCOL_VERSION = 2`; unterstützt `(2,)`.

### Handshake

Die Verbindung wird technisch akzeptiert; die **erste** Textnachricht muss
`hello` sein, sonst schließt der Server. Zeitlimit
`DEFAULT_HANDSHAKE_TIMEOUT_SECONDS = 10.0` → Close `4408`.

```json
{"type":"hello",
 "supportedProtocolVersions":[2],
 "clientVersion":"1.0.0","clientCommit":"abc123",
 "clientRunId":"7f8e0c1a-3c55-4b55-9a51-1d1f6f0a2b10",
 "requestedSession":{"trigger":{"manual":true,"wakeWord":false},"wakeWordIds":[]},
 "runtimeSuppression":{"manual":false,"wakeWord":false}}
```

Validierung (`protocol_v2/handshake.py:parse_hello`) in drei Stufen:

| Stufe | Bedingung | Reaktion |
| --- | --- | --- |
| Envelope | kein JSON, `type != hello`, `supportedProtocolVersions` keine nicht-leere Int-Liste, `clientVersion`/`clientCommit` leer, `clientRunId` kein kanonischer UUID-String, `requestedSession`/`trigger`/`wakeWordIds`/`runtimeSuppression` falsch typisiert | Close `4400`, keine Nachricht |
| Version | keine gemeinsame Version | `protocol.incompatible` (mit `serverVersion`, `serverCommit`, `supportedProtocolVersions`), Close `4406` |
| Session | kein Trigger aktiv (`activation_trigger_required`), Wake-Word ohne IDs (`wake_word_selection_required`), IDs ohne Wake-Word (`wake_word_selection_not_allowed`), unbekannte/nicht verfügbare IDs, Sitzungslimit (`session_limit_reached`) | `session.rejected` mit `errors[]` (`field`, `code`, `message`), Close `4409` |

Kanonische IDs: Bindestrich-UUID in Kleinbuchstaben (`is_canonical_uuid`);
kompakte 32-Hex-Form und Großschreibung werden abgelehnt.

Erfolg:

```json
{"type":"hello.accepted","protocolVersion":2,"sessionId":"<uuid>",
 "serverVersion":"2.0.0","serverCommit":"...","snapshot":{...},"logAccess":{...}}
```

Mit der Annahme wird der Audiopfad sofort geöffnet (es gibt kein
`start`-Kommando in V2) und die Laufzeit-Unterdrückung aus dem `hello`
angewendet (`ProtocolV2Connection._activate_session`).

### Kommandos

Gemeinsamer Envelope (`protocol_v2/commands.py:parse_command`):

```json
{"type":"activation.command","protocolVersion":2,"sessionId":"<uuid>",
 "commandId":"<uuid>","action":"activate","source":"manual"}
```

| `type` | Pflichtfelder neben dem Envelope |
| --- | --- |
| `activation.command` | `action` ∈ `activate|refresh|finish|cancel`; `activate`: `source: "manual"`, **keine** `activationId`; sonst: `activationId` (UUID), **kein** `source` |
| `trigger_suppression.set` | `manual: bool`, `wakeWord: bool` |
| `audio_availability.set` | `audioAvailable: bool` |
| `session_settings.patch` | `baseSettingsRevision: int ≥ 0`, `changes`: nicht-leeres Objekt |
| `session.snapshot.request` | – |

Regeln:

- Unbekannter/fehlender `type` → wird **ignoriert** (keine Antwort).
- Keine verwertbare kanonische `commandId` → keine Antwort möglich (kein Ack).
- Falsche `protocolVersion` oder `sessionId` keine UUID → `invalid_payload`;
  fremde `sessionId` → `stale_session`.
- Ein abgelehntes Kommando schließt die Sitzung nie.
- Replay: gleiche `commandId` und gleiche Nutzlast → identisches, gemerktes Ack;
  abweichende Nutzlast → `command_id_conflict`.

### `command.ack`

```json
{"type":"command.ack","protocolVersion":2,"sessionId":"<uuid>","commandId":"<uuid>",
 "accepted":true,"result":"applied","activationId":"<uuid>","inputPhase":"waiting_first_speech",
 "stateVersion":3,"settingsRevision":0}
```

`result` ist genau einer von 15 Codes: `applied`, `no_change`,
`activation_locked`, `not_active`, `invalid_phase`, `closing_input`,
`stale_session`, `stale_activation`, `command_id_conflict`,
`invalid_payload`, `trigger_suppressed`, `audio_unavailable`,
`settings_revision_conflict`, `settings_rejected`, `internal_error`.
`accepted` ist nur bei `applied` und `no_change` wahr. Die Abbildung der
Domänengründe auf diese Codes ist erschöpfend; ein unbekannter Grund wirft
`UnmappedDomainReason` (`DOMAIN_REASON_RESULTS`).

### Ereignisse

Envelope (`protocol_v2/session.py:mint_event`):

```json
{"type":"transcription.completed","protocolVersion":2,"sessionId":"<uuid>",
 "eventId":"<uuid>","eventSeq":17,"stateVersion":9,"occurredAtUnixMs":1762300000000, "...":"..."}
```

- `eventSeq` steigt bei **jedem** Ereignis um 1.
- `stateVersion` steigt bei jedem Ereignis außer den Diagnoseereignissen
  `watchdog.warning`, `activation.trigger_suppressed`, `transcription.interim`
  (`NON_STATE_EVENTS`).
- Gleicher logischer Schlüssel → identischer Envelope (Transport-Retry
  erzeugt kein neues Ereignis).

Ereignistypen (`schema.EVENT_TYPES`) und belegte Zusatzfelder
(`protocol_v2/events.py`):

| Ereignis | Zusatzfelder |
| --- | --- |
| `activation.started` | `activationId`, `activationSequence`, `primarySource`, `inputPhase`, `effectiveSettings` |
| `activation.phase_changed` | `activationId`, `previousPhase`, `inputPhase`, `deadlineAtUnixMs`, `remainingMs` |
| `activation.input_closed` | `activationId`, `reason`, `causedByCommandId`, `acceptedSegmentCount` |
| `activation.completed` / `activation.cancelled` / `activation.failed` | `activationId`, `acceptedSegmentCount`, `terminalSegmentCount` |
| `activation.trigger_suppressed` | `source`, `reason` |
| `segment.recording_started` / `segment.recording_ended` | `activationId`, `segmentId`, `segmentSequence` |
| `transcription.accepted` | Segmentfelder |
| `transcription.interim` | Segmentfelder, `text`, optional Stabilisierungsfelder (`rawText`, `stableText`, `stableDelta`, `unstableText`, `committedStableText`, `consensusText`, `timing`, …) |
| `transcription.completed` | Segmentfelder, `text` |
| `transcription.discarded` / `transcription.failed` | Segmentfelder, `reason` |
| `watchdog.warning` | `activationId` |
| `wakeword.detected` | `activationId`, `wakeWordId`, `score`, `primarySource: "wake_word"` |
| `wakeword.availability_changed` | `catalogRevision`, `availableWakeWordIds` |
| `settings.changed` | `settingsRevision`, `scope`, `changedKeys`, `applyPolicy` |

### Snapshot und Resync

`session.snapshot.request` beantwortet der Server mit `session.snapshot`
(`protocol_v2/snapshot.py`):

```json
{"type":"session.snapshot","protocolVersion":2,"serverVersion":"...","serverCommit":"...",
 "sessionId":"<uuid>","stateVersion":9,"lastEventSeq":17,"settingsRevision":0,
 "input":{"phase":"idle","activationId":null,"primarySource":null,
          "deadlineAtUnixMs":null,"remainingMs":null,"closeRequested":false},
 "pendingActivations":[{"activationId":"...","activationSequence":1,"inputClosedReason":"...",
                        "processingState":"draining","acceptedSegmentCount":1,"terminalSegmentCount":0}],
 "trigger":{"configured":{"manual":true,"wakeWord":false},"suppressed":{...},"effective":{...}},
 "audioAvailable":true,"requestedSettings":{...},"effectiveSettings":{...},
 "wakeWordCapabilities":{...}}
```

Ein Client kann damit nach Verlust von Ereignissen anhand von `stateVersion`
und `lastEventSeq` resynchronisieren. `logAccess` steht nur im
`hello.accepted`, nicht in späteren Snapshots.

### Close-Codes

| Code | Bedeutung |
| --- | --- |
| `4400` | ungültiger Handshake bzw. Binärdaten vor `hello.accepted` |
| `4406` | keine gemeinsame Protokollversion |
| `4408` | Handshake-Timeout |
| `4409` | Sitzung abgelehnt |
| `1011` | interner Fehler (auch bei fehlgeschlagenem Senden) |

---

## 3. Live-Logs – `/ws/logs`

1. Server akzeptiert. Ist `log_live_enabled` aus → `{"type":"log.error",
   "code":"log_live_disabled"}`, Close `1008`. Eventstore nicht verfügbar →
   `event_store_unavailable`, Close `1011`.
2. Erste Client-Nachricht muss `{"type":"subscribe", "accessToken": "...",
   "sessionId": "...", "channels": [...], "afterCursor": 0}` sein.
3. Autorisierung (`LogGate.websocket_scope`): Admin-Schlüssel als
   `accessToken` → Admin-Scope; sonst gültiges Log-Token → Session-Scope.
   **Anders als HTTP** gibt es hier keinen impliziten Loopback-Admin. Fehlschlag
   → `log.error` `not_authorized`, Close `1008`.
4. Session-Scope darf nur `audit`, `performance`, `transcription` abonnieren.

Weitere Nachrichtentypen im Code: `log.hello`, `log.subscribed`, `log.event`,
`log.gap`, `log.replay_completed`, `log.keepalive` (Intervall
`LOG_STREAM_KEEPALIVE_SECONDS = 30.0`), `log.pong`.

Das Log-Token liefert das `logAccess`-Objekt aus V1-`hello` bzw.
V2-`hello.accepted` (`accessToken`, `expiresAt`, `websocketPath: "/ws/logs"`,
`historyPath: "/api/logs/events"`, `logProtocolVersion: 2`,
`deliveryMode: "sqlite_first"`). Gültigkeit 24 h, nur im Prozessspeicher
(`security/logs.py:TOKEN_LIFETIME_SECONDS`).

## Primäre Quellen

- [`api_fastapi_server/server.py`](../../api_fastapi_server/server.py) – `websocket_transcribe` (9914), `websocket_protocol_v2` (10123), `websocket_logs` (9562), `create_log_access`
- [`api_fastapi_server/protocol_v2/schema.py`](../../api_fastapi_server/protocol_v2/schema.py), [`handshake.py`](../../api_fastapi_server/protocol_v2/handshake.py), [`commands.py`](../../api_fastapi_server/protocol_v2/commands.py), [`connection.py`](../../api_fastapi_server/protocol_v2/connection.py), [`events.py`](../../api_fastapi_server/protocol_v2/events.py), [`session.py`](../../api_fastapi_server/protocol_v2/session.py), [`snapshot.py`](../../api_fastapi_server/protocol_v2/snapshot.py)
- Tests: [`tests/unit/test_protocol_v2_contract.py`](../../tests/unit/test_protocol_v2_contract.py), [`tests/unit/test_protocol_v2_e2e.py`](../../tests/unit/test_protocol_v2_e2e.py), [`tests/unit/test_protocol_v2_races.py`](../../tests/unit/test_protocol_v2_races.py), [`tests/unit/test_protocol_v2_state_version.py`](../../tests/unit/test_protocol_v2_state_version.py), [`tests/unit/test_protocol_v2_terminal_recovery.py`](../../tests/unit/test_protocol_v2_terminal_recovery.py), [`tests/unit/test_protocol_v1_v2_boundary.py`](../../tests/unit/test_protocol_v1_v2_boundary.py), [`tests/unit/test_server_trigger_contract.py`](../../tests/unit/test_server_trigger_contract.py), [`tests/unit/test_browser_client_contract.py`](../../tests/unit/test_browser_client_contract.py)
