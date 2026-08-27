# HTTP-API und Authentifizierung

[← Client-Zustandsmodell](05-client-zustandsmodell.md) · [Robustheit & Sicherheit →](07-robustheit-grenzen-und-sicherheit.md)

Der Live-Client benötigt primär `WS /ws/transcribe`. Die HTTP-Endpunkte sind
für Readiness, Diagnose, Administration und abgeschlossene Audiodateien
relevant.

## Endpunktmatrix

| Methode | Pfad | Auth im Servercode | Zweck |
| --- | --- | --- | --- |
| `GET` | `/` | keine | integrierte Browseroberfläche |
| `GET` | `/health` | keine | kompakter Readiness-/Health-Snapshot |
| `GET` | `/api/config` | keine | öffentliche Konfiguration und Runtime-Vertrag |
| `PATCH` | `/api/config` | Admin | Runtime-Settings ändern |
| `GET` | `/api/metrics` | keine | vollständige Server-/Session-/Scheduler-Metriken |
| `GET` | `/api/models` | Admin | lokaler Modellkatalog, aktive Lanes, Lifecycle |
| `GET`/`PUT` | `/api/models/active` | Admin | aktive Modellzuordnung lesen/wechseln |
| `GET`/`PUT` | `/api/models/lifecycle` | Admin | Idle-Unload/Memory-Policy lesen/ändern |
| `POST` | `/api/models/load` | Admin | Modelle explizit laden |
| `POST` | `/api/models/unload` | Admin | Modelle explizit entladen |
| `GET`/`PUT` | `/api/language` | Admin | Standardsprache lesen/ändern |
| `GET`/`PUT` | `/api/wake-word` | Admin | Wake-Konfiguration und Modellkatalog |
| `GET`/`PUT` | `/api/logging` | Admin | vier Eventkanäle, Kalender, Transcript-Policy und Live-Zugriff konfigurieren |
| `GET` | `/api/logs/events` | Admin oder Sessiontoken | gefilterte Eventhistorie |
| `GET` | `/api/logs/sessions/{sessionId}` | Admin oder passender Sessiontoken | Historie einer Session |
| `GET` | `/api/logs/transcriptions/{transcriptionId}` | Admin oder passender Sessiontoken | Historie einer Transkription |
| `POST` | `/api/config/validate` | Admin | Kandidatenkonfiguration prüfen |
| `POST` | `/api/config/reload` | Admin | persistierte Runtime-Konfiguration neu anwenden |
| `GET` | `/api/v2/settings/schema` | keine | öffentliches Settingsschema der Control-Plane |
| `GET` | `/api/v2/settings/server` | keine | nicht geheime Serverwerte + Serverrevision |
| `PATCH` | `/api/v2/settings/server` | Admin | Serverdefaults atomar ändern (optimistische Concurrency) |
| `GET` | `/v1/models` | OpenAI-Key* | geladene Modelle/Aliasse |
| `POST` | `/v1/audio/transcriptions` | OpenAI-Key* | abgeschlossene Audiodatei transkribieren |
| `WS` | `/ws/transcribe` | keine im Handler | kontinuierliches Live-Audio |
| `WS` | `/ws/logs` | Admin- oder Sessiontoken in erster Nachricht | Cursor-Replay und strukturierte Live-Events |

\* Wenn kein OpenAI-Key konfiguriert ist, lässt der implementierte Handler die
Anfrage ohne Authentifizierung zu. Im versionierten Deployment werden Keys über
Umgebungs-Secrets vorgesehen.

## Authentifizierungsbereiche

### Admin-API

Bevorzugter Header:

```http
X-VoiceSTT-Admin-Key: <admin-key>
```

Alternativ (derselbe Guard, AP-SRV-050 unterstützt zusätzlich den Frozen
Header):

```http
Authorization: Bearer <admin-key>
X-Admin-Key: <admin-key>
```

Wenn kein Admin-Key konfiguriert ist, erlaubt der Code Adminzugriffe nur von
`127.0.0.1`, `::1`, `localhost` (sowie dem Testclient). Remotezugriffe erhalten
HTTP 403. Bei konfiguriertem Key führt ein falscher/fehlender Key zu 401.

Ein normaler Transkriptionsclient sollte keinen Admin-Key enthalten.

### OpenAI-kompatible API

```http
Authorization: Bearer <openai-api-key>
```

Admin- und OpenAI-Key sind getrennte Vertrauensbereiche. Der OpenAI-Key erlaubt
keinen Modellwechsel und keine Konfigurationsänderung.

### WebSocket

Der Handler für `/ws/transcribe` prüft keine Header, Cookies, Queryparameter oder
erste Auth-Nachricht. Eine Clientimplementierung darf nicht annehmen, dass
`Authorization: Bearer ...` vom Server ausgewertet wird. Browser-WebSockets
können ohnehin keine beliebigen Authorization-Header setzen.

### Strukturierter Logzugriff

`hello.logAccess` des Transkriptions-WebSockets liefert einen zufälligen,
24 Stunden innerhalb des aktuellen Serverprozesses gültigen Sessiontoken. Er
erlaubt ausschließlich die eigene Session und die Channels `audit`,
`transcription` und `performance`; `system` und fremde Sessions bleiben dem
Adminzugriff vorbehalten. `available`, `logProtocolVersion: 2`,
`deliveryMode: "sqlite_first"`, `replayAvailable`, `serverInstanceId`,
`oldestCursor` und `latestCursor` beschreiben den zuverlässigen Logpfad. Bei
nicht verfügbarem Store oder deaktiviertem Livezugriff ist `available: false`
und es wird kein Sessiontoken ausgegeben.

Nach dem Subscribe enthält `log.hello` zusätzlich `retentionCursor`. Dieser
Watermark ist auf die effektiven Channels und die effektive Session des
Abonnements bezogen und kann deshalb oberhalb des globalen `oldestCursor`
liegen.

Für HTTP wird der Token so gesendet:

```http
X-VoiceSTT-Log-Token: <session-token>
```

Für `/ws/logs` gehört er in die erste Nachricht, nicht in die URL:

```json
{
  "type": "subscribe",
  "accessToken": "<session-token>",
  "sessionId": "<session-id>",
  "channels": ["transcription", "performance"],
  "afterCursor": 1200
}
```

Ein Admin kann stattdessen den Admin-Key verwenden. Bei HTTP gehört er in
`X-VoiceSTT-Admin-Key` oder Bearer, beim Log-WebSocket ausschließlich als
`accessToken` in die erste Nachricht. Ohne `sessionId` und Channels ist der
Scope serverweit und umfasst auch `system`. `log.subscribed` bestätigt dies
durch `authorizationScope: "admin"`, `allSessions: true` und
`allChannels: true`. Der Secretvergleich erfolgt konstantzeitlich. Der
Audio-WebSocket erhält dadurch keine Adminrechte.

Replay und Live lesen beide ausschließlich committed SQLite-Events. Der
Protokollablauf und die Fehlercodes sind in
[WebSocket-Protokoll](02-websocket-protokoll.md#zweite-verbindung-zuverlässiger-eventstream)
und [Strukturiertes Logging](../structured-logging.md) beschrieben.

## `GET /health`

Kompakte Form von `service.metrics()`:

```json
{
  "ok": true,
  "ready": true,
  "activeSessions": 2,
  "activeSpeakers": 1,
  "rejectedSessions": 0,
  "scheduler": { "mode": "low-memory-one-model", "queues": {}, "workers": {} },
  "models": { "state": "loaded", "loaded": true, "active": {} },
  "startupErrors": [],
  "eventStore": {
    "state": "ready",
    "available": true,
    "lastErrorType": null,
    "lastTransitionAt": "2026-08-02T10:00:00.000Z",
    "oldestCursor": 1,
    "latestCursor": 18427
  }
}
```

| Feld | Bedeutung |
| --- | --- |
| `ready` | Initialer Ready-Worker ist abgeschlossen |
| `ok` | ready und Scheduler gesund; absichtlich entladene Modelle gelten als ok |
| `activeSessions` | angenommene WebSocket-Sessions |
| `activeSpeakers` | gleichzeitig aktive Aufnahmen |
| `rejectedSessions` | kumulierte Admission-Ablehnungen |
| `scheduler` | Queue-/Worker-Snapshot oder `mode: "unloaded"` |
| `models` | Lifecycle inkl. Aktivität und Idle-Restzeit |
| `startupErrors` | serverweite Engine-/Startfehler |
| `eventStore` | Zustand und committed Cursorgrenzen des kanonischen SQLite-Stores |

Ein Livenessmonitor sollte `ok` prüfen. Ist Live-Logging konfiguriert, wird
`ok` bei degradiertem Eventstore false, während `/ws/transcribe` bewusst
weiterarbeiten kann. Ein UI kann zusätzlich `models.loaded` anzeigen, sollte
„unloaded“ aber nicht automatisch als Ausfall bewerten.

## `GET /api/config`

Antwort:

```json
{
  "settings": {},
  "limits": {},
  "supportedEngines": [],
  "sessionCapabilities": {},
  "runtimeSettings": {
    "activeSessionSafe": [],
    "newSessionOnly": [],
    "startupOnly": []
  },
  "adminAuthRequired": true
}
```

Secrets sowie `transcription_engine_options` und
`realtime_transcription_engine_options` werden aus `settings` entfernt.
`wake_word_enabled` wird als abgeleitetes Feld ergänzt.

## Log-History-API

Die drei History-Routen akzeptieren `channels`, `events`, `sessionId`,
`transcriptionId`, `from`, `to`, `afterCursor` und `limit`. `limit` ist auf
1000 begrenzt. Die Antwort enthält die sortierten Events sowie `nextCursor`,
`oldestCursor`, `latestCursor`, den filterbezogenen `retentionCursor`,
`authorizationScope`, `allSessions` und `deliveryMode`, damit ein Client ohne
Duplikate paginieren und anschließend zum Live-WebSocket wechseln kann.

Ein Sessiontoken wird serverseitig immer auf seine eigene `sessionId`
eingeschränkt, auch wenn der Client einen breiteren Filter anfordert. Nicht
erlaubte Channels liefern keine fremden Daten. Der vollständige Vertrag steht
unter [Strukturiertes Logging](../structured-logging.md).

Admin-History darf `sessionId` weglassen und damit ältere Events aller noch in
Retention vorhandenen Sessions abrufen. Der Browser-Adminbereich lädt solche
Ergebnisse seitenweise mit begrenztem `limit`, optionalen Channel-/Zeitfiltern
und kann danach ab dem aktuellen `latestCursor` in den globalen Live-Modus
wechseln.

## `GET/PUT /api/logging`

Neben den Kalender-/stdout-, Retention-, Transcript- und Audioeinstellungen
liefert `GET /api/logging`:

```json
{
  "liveEnabled": true,
  "logProtocolVersion": 2,
  "deliveryMode": "sqlite_first",
  "replayAvailable": true,
  "eventStore": {
    "enabled": true,
    "state": "ready",
    "available": true,
    "oldestCursor": 1,
    "latestCursor": 18427
  }
}
```

`eventStore.enabled` und der abgeleitete Storepfad sind startup-only.
`liveEnabled` ist laufzeitänderbar, darf aber nur true sein, wenn der Store beim
Start aktiviert wurde. Für Audit, Transkription und System steuern die
Channel-`enabled`-Schalter ihre optionalen Kalender-/stdout-Spiegel. Im
`performance`-Objekt ist `enabled` dagegen der Quellschalter und
`mirrorEnabled` der unabhängige Spiegel-Schalter. `PUT /api/logging` verwendet
dafür `performanceEnabled` und `performanceMirrorEnabled`. Ein bereits
erzeugtes Event wird durch keinen Spiegel-Schalter aus SQLite, Replay oder
Liveausgabe entfernt.

## `PATCH /api/config`

Request:

```json
{
  "settings": {
    "max_sessions": 8,
    "wake_words": "hey_jarvis"
  }
}
```

Alternativ darf das Settings-Objekt direkt der Body sein.

Antwort:

```json
{
  "applied": {
    "max_sessions": { "value": 8, "appliesTo": "active_sessions" },
    "wake_words": { "value": "hey_jarvis", "appliesTo": "new_sessions" }
  },
  "rejected": {},
  "settings": {},
  "runtimeSettings": {}
}
```

Sobald mindestens ein Wert abgelehnt wurde, antwortet der Endpunkt mit HTTP 400,
obwohl andere Werte desselben Requests bereits angewendet worden sein können.
Admin-Clients müssen `applied` und `rejected` daher immer beide auswerten.

## `GET /api/metrics`

Enthält zusätzlich zu `/health`:

- `pendingSessionAdmissions`;
- `sessions`: Map `sessionId → SessionMetrics`;
- `limits`;
- vollständige Queue-/Workerstatistiken.

### Queue-Snapshot

```json
{
  "name": "main",
  "queued": 2,
  "sessions": 2,
  "perSession": {
    "abc": { "final": 1, "realtime": 0 },
    "def": { "final": 0, "realtime": 1 }
  },
  "coalescedRealtime": 12,
  "staleRealtimeDropped": 3,
  "rejectedJobs": 0
}
```

### Worker-Snapshot

```json
{
  "name": "main",
  "ready": true,
  "healthy": true,
  "completedJobs": 120,
  "failedJobs": 1,
  "busyRatio": 0.37,
  "queueDelay": { "count": 120, "avgMs": 42, "maxMs": 300, "p50Ms": 30, "p95Ms": 110 },
  "inferenceDuration": {},
  "totalLatency": {}
}
```

Da `/api/metrics` Session-IDs und Betriebsdetails aller Nutzer offenlegt, sollte
ein Deployment den Zugriff auf Netzwerk-/Proxyebene bewusst einschränken, wenn
diese Informationen nicht öffentlich sein sollen.

## Modellverwaltung

### Aktive Lanes

`GET /api/models/active`:

```json
{
  "final": { "engine": "kroko_onnx", "model": "Kroko-DE-…data" },
  "realtime": {
    "engine": "kroko_onnx",
    "model": "Kroko-DE-…data",
    "sharedWithFinal": true
  }
}
```

`PUT /api/models/active` akzeptiert nur:

```text
model
realtime_model
transcription_engine
realtime_transcription_engine
use_main_model_for_realtime
language
transcription_engine_options
realtime_transcription_engine_options
```

Ein Modellwechsel lädt die Modell-Worker neu. Die neuen Modelle gelten für alle neuen Anfragen und WebSocket-Sitzungen; bestehende Client-Verbindungen übernehmen den Modellwechsel nach einem Reconnect.

### Lifecycle

`GET /api/models/lifecycle` liefert unter anderem:

```text
state, loaded, error, lastActivityAt, idleSeconds,
automaticUnloadEnabled, idleTimeoutSeconds, idleSecondsRemaining,
memoryPolicyEnabled, allowTwoMediumModels, mediumEquivalentLimit, active
```

Ein manuelles Unload antwortet mit 409, solange Audio aktiv ist oder
Transkriptionen ausstehen. Nach erfolgreichem Unload lädt die nächste Realtime-
oder HTTP-Anfrage Modelle automatisch wieder.

## Sprache und Wake Word

`PUT /api/language` gilt für neue Requests und Sessions. Bestehende Sessions
behalten ihre kopierte Recorderkonfiguration.

`GET /api/wake-word` liefert:

```text
enabled, backend, words, sensitivity, timeout, bufferDuration,
followupWindow, openwakewordModelPaths, availableModels, appliesTo
```

`availableModels.openwakeword` enthält die lokal validierten logischen
Modell-IDs aus `models.json` beziehungsweise dem Dateiscan. Der aktuelle
FastAPI-Adminvertrag veröffentlicht kein Porcupine. Änderungen via `PUT`
ändern nur die Baseline für neue Sessions; ein Desktop-Client kann Wake Word
unabhängig davon beim WebSocket-Aufbau sessionlokal konfigurieren.

## OpenAI-kompatible Datei-Transkription

### Abgrenzung zu Live-Audio

`POST /v1/audio/transcriptions` erwartet eine vollständig hochgeladene Datei.
Auch `stream=true` macht daraus keinen bidirektionalen Mikrofonstream: Der Upload
ist zuerst vollständig vorhanden, anschließend streamt der Server Text-/Done-
SSE-Events während der Verarbeitung.

### Multipart-Felder

| Feld | Pflicht | Werte / Bedeutung |
| --- | --- | --- |
| `file` | ja | `.flac`, `.mp3`, `.mp4`, `.mpeg`, `.mpga`, `.m4a`, `.ogg`, `.wav`, `.webm` |
| `model` | ja | z. B. `whisper-1`, geladener Alias oder geladenes Modell |
| `language` | nein | überschreibt Standardsprache für den Request |
| `prompt` | nein | Transkriptionsprompt |
| `response_format` | nein | `json`, `text`, `srt`, `verbose_json`, `vtt`, `diarized_json` |
| `temperature` | nein | 0 bis 1, Standard 0 |
| `timestamp_granularities` | nein | `segment`, `word`; abweichend von nur `segment` nur mit `verbose_json` |
| `stream` | nein | boolesch |
| `include` | nein | derzeit nur `logprobs` |
| `threshold` | nein | 0 bis 1 |
| `known_speaker_names` | nein | maximal 4 |
| `known_speaker_references` | nein | gleich viele wie Namen |
| `voicestt_model` / `model_override` | nein | Lane-/Modelloverride nur bei `model=whisper-1` |

Alternativ zum Multipart-Override wird der Header
`X-VoiceSTT-Model` akzeptiert.

Dateigröße: `openai_max_file_bytes`, im Produktionsprofil 25 MiB.

### Routing-Response-Header

```text
X-Request-ID
X-VoiceSTT-Requested-Model
X-VoiceSTT-Resolved-Model
X-VoiceSTT-Route
X-VoiceSTT-Override-Model        (optional)
X-VoiceSTT-Override-Source       (optional)
```

### JSON-Antwort

Standard:

```json
{
  "text": "Transkript",
  "usage": { "type": "duration", "seconds": 4 }
}
```

`verbose_json` ergänzt `task`, `language`, `duration`, `segments` und optional
`words`. `diarized_json` ist ausdrücklich nur Single-Speaker-Kompatibilität; der
Server besitzt kein Diarisierungsmodell.

### SSE bei `stream=true`

Jede Nachricht ist ein Standard-SSE-`data:`-Block mit JSON:

```json
{"type":"transcript.text.delta","delta":"Teiltext"}
```

Abschluss:

```json
{
  "type": "transcript.text.done",
  "text": "Vollständiges Transkript",
  "usage": { "type": "duration", "seconds": 4 }
}
```

Bei Streamingfehler:

```json
{
  "type": "error",
  "error": {
    "message": "…",
    "type": "invalid_request_error",
    "param": null,
    "code": null
  }
}
```

Für `diarized_json` werden vor `done` einzelne
`transcript.text.segment`-Objekte ausgegeben.

## OpenAI-Fehlerformat

```json
{
  "error": {
    "message": "Beschreibung",
    "type": "invalid_request_error",
    "param": "model",
    "code": "model_not_found"
  }
}
```

Relevante Statuscodes sind 400 (Parameter), 401 (Key), 404 (API deaktiviert
oder Modell nicht gefunden), 409 (lokal vorhanden, aber nicht geladen), 413
(Datei zu groß) und 500 (Transkriptionsfehler).
