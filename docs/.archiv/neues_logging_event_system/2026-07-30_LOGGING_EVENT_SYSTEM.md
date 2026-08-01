---
type: Note
---
# 2026-07-30_LOGGING_EVENT_SYSTEM

Mein Vorschlag wäre tatsächlich, einen dritten strukturierten Kanal für Transkriptionsvorgänge einzuführen. Insgesamt würde ich vier klar getrennte Channels vorsehen. Dadurch können HTTP und WebSocket fachlich einheitlich behandelt werden, ohne Audit- und Performancelogs zu vermischen.

## 1. Vorgeschlagene Channels

| Channel | Zweck | Beispiele | Typische Sichtbarkeit |
|---|---|---|---|
| `system` | Technischer Serverbetrieb und Fehlerdiagnose | Workerstart, unerwartete Exception, Fallback, Shutdown | Administrator |
| `audit` | Nachvollziehbare administrative und sicherheitsrelevante Vorgänge | Konfigurationsänderung, Modellwechsel, Session angenommen/abgelehnt | Administrator |
| `transcription` | Fachlicher Lebenszyklus einzelner Transkriptionen | Aufnahme gestartet, Transkription abgeschlossen, Wakeword erkannt | Session-Client und Administrator |
| `performance` | Messwerte ohne eigentliche Inhalte | Latenzen, Queuezeiten, Realtime-Abstände, Speichernutzung | Session-Client und Administrator |

Damit hätten wir eine saubere Trennung:

- `audit` beantwortet: Wer oder was hat den Serverzustand verändert?
- `transcription` beantwortet: Was geschah bei einer konkreten Transkription?
- `performance` beantwortet: Wie schnell und ressourcenschonend lief sie?
- `system` beantwortet: Was geschah intern im Serverprozess?

Normale Python- und Bibliothekslogs würde ich nicht ungefiltert an Clients weiterreichen. Stattdessen sollten alle clientrelevanten Informationen als strukturierte Ereignisse über diese Channels laufen.

---

# 2. Einheitliches Ereignismodell

Alle strukturierten Channels sollten denselben äußeren Envelope verwenden:

```json
{
  "schemaVersion": 1,
  "eventId": "01K...",
  "cursor": 18427,
  "timestamp": "2026-07-30T14:26:41.537Z",
  "channel": "transcription",
  "event": "transcription.completed",
  "severity": "info",
  "serverInstanceId": "server-20260730-01",

  "transport": "websocket",
  "clientId": "client-123",
  "sessionId": "session-456",
  "requestId": null,
  "transcriptionId": "tr-789",
  "segmentId": 3,

  "data": {
    "language": "de",
    "engine": "faster_whisper",
    "model": "medium",
    "audioDurationMs": 2840,
    "totalLatencyMs": 912
  }
}
```

## Identifikatoren

Die wichtigsten Einheiten sollten klar getrennt werden:

- `clientId`: dauerhafte oder zumindest pro Clientinstallation stabile Identität.
- `sessionId`: eine WebSocket-Verbindung beziehungsweise ein logischer HTTP-Vorgang.
- `requestId`: technische HTTP-Anfrage oder Scheduler-Anfrage.
- `transcriptionId`: transportübergreifend eindeutige ID einer konkreten Transkription.
- `segmentId`: Segment innerhalb einer längeren WebSocket-Sitzung.
- `eventId`: weltweit eindeutiges Ereignis.
- `cursor`: fortlaufende Position für History und WebSocket-Reconnect.

Die fachliche Gleichbehandlung von HTTP und WebSocket würde über `transcriptionId` erfolgen:

- HTTP: normalerweise genau eine Transkription pro Request.
- WebSocket: mehrere Transkriptionen beziehungsweise Segmente innerhalb einer Session.

HTTP muss also nicht künstlich exakt dieselbe Sessionstruktur wie WebSocket erhalten. Entscheidend ist, dass für beide derselbe Transkriptionslebenszyklus protokolliert wird.

---

# 3. Vorgeschlagene Ereignisse

## 3.1 System-Channel

Nur wichtige technische Betriebsereignisse sollten strukturiert werden:

- `server.starting`
- `server.ready`
- `server.stopping`
- `server.error`
- `worker.starting`
- `worker.ready`
- `worker.failed`
- `scheduler.overloaded`
- `recorder.failed`
- `storage.failed`
- `log.subscriber.dropped`

Detailreiche Debugmeldungen können weiterhin normale Prozesslogs bleiben.

## 3.2 Audit-Channel

- `config.updated`
- `language.updated`
- `models.loaded`
- `models.load_failed`
- `models.switched`
- `models.unloaded`
- `session.accepted`
- `session.rejected`
- `session.closed`
- `authentication.failed`
- `logging.config_updated`

Die bisherigen `websocket.connected`-Ereignisse würde ich perspektivisch auf allgemeine `session.*`-Ereignisse umstellen und `transport: "websocket"` ergänzen. HTTP kann dieselben Ereignisse verwenden, wenn eine fachliche Session gebildet wird.

Für die Übergangszeit können die bestehenden Namen kompatibel weitergeschrieben oder auf das neue Modell abgebildet werden.

## 3.3 Transcription-Channel

Hier würde ich HTTP und WebSocket vollständig vereinheitlichen:

- `transcription.accepted`
- `transcription.started`
- `transcription.recording_started`
- `transcription.recording_ended`
- `transcription.completed`
- `transcription.failed`
- `transcription.rejected`
- `transcription.cancelled`

Wakewordbezogene Ereignisse gehören ebenfalls hierher:

- `wakeword.wait_started`
- `wakeword.wait_ended`
- `wakeword.detected`
- `wakeword.timeout`
- `wakeword.followup_started`
- `wakeword.followup_timeout`

Realtime-Ausgaben könnten optional ebenfalls fachlich protokolliert werden:

- `transcription.realtime_emitted`

Ich würde dabei aber standardmäßig keinen Realtime-Text speichern. Das Ereignis dient vor allem als zeitliche Markierung.

Ein erfolgreiches Abschlussereignis könnte enthalten:

```json
{
  "channel": "transcription",
  "event": "transcription.completed",
  "transport": "websocket",
  "sessionId": "...",
  "transcriptionId": "...",
  "segmentId": 4,
  "data": {
    "language": "de",
    "engine": "faster_whisper",
    "model": "medium",
    "audioDurationMs": 3120,
    "realtimeEventCount": 7,
    "text": "Optionaler finaler Text"
  }
}
```

Ob `text` enthalten ist, sollte über eine zentrale Datenschutzoption gesteuert werden.

## 3.4 Performance-Channel

- `models.load_completed`
- `models.unload_completed`
- `inference.completed`
- `transcription.first_text`
- `transcription.realtime_emitted`
- `transcription.completed`
- `transcription.performance_summary`
- `queue.limit_reached`
- `audio.buffer_limit_reached`

Performanceereignisse enthalten niemals Transkripttext oder Audio.

---

# 4. Realtime-Ereignisse

Ich halte es für sinnvoll, jeden tatsächlich an den Client ausgegebenen Realtime-Stand zumindest als leichtgewichtiges Performanceereignis zu erfassen.

Beispiel:

```json
{
  "channel": "performance",
  "event": "transcription.realtime_emitted",
  "timestamp": "2026-07-30T14:26:40.221Z",
  "sessionId": "...",
  "transcriptionId": "...",
  "segmentId": 3,
  "data": {
    "sequence": 5,
    "sincePreviousMs": 284,
    "sinceRecordingStartMs": 1341,
    "characterCount": 42,
    "stableCharacterCount": 31,
    "unstableCharacterCount": 11,
    "queueDelayMs": 18,
    "inferenceMs": 173,
    "isOutlier": false
  }
}
```

Beim finalen Ergebnis sollte zusätzlich eine Zusammenfassung erzeugt werden:

```json
{
  "event": "transcription.performance_summary",
  "data": {
    "realtimeEventCount": 8,
    "timeToFirstRealtimeMs": 476,
    "averageRealtimeIntervalMs": 291,
    "minRealtimeIntervalMs": 182,
    "maxRealtimeIntervalMs": 517,
    "p95RealtimeIntervalMs": 498,
    "timeToFinalMs": 3710
  }
}
```

Damit erhält man:

- Anzahl der Realtime-Ausgaben,
- Zeit bis zum ersten Text,
- zeitliche Verteilung der Aktualisierungen,
- Ausreißer,
- Abschlusslatenz.

Nicht geloggt werden sollten:

- jedes Audiopaket,
- jeder VAD-Frame,
- unveränderte Realtime-Wiederholungen,
- vollständige Realtime-Texte im Performancekanal.

Optional könnte es drei Detailstufen geben:

- `off`: keine einzelnen Realtime-Performanceereignisse.
- `summary`: nur Abschlusszusammenfassung.
- `events`: einzelne Zeitpunkte plus Zusammenfassung.

Meine Empfehlung wäre `events`, allerdings ohne Text und mit einer konfigurierbaren Aufbewahrungsdauer.

---

# 5. Zentrale Architektur

Statt Audit- und Performancemanager direkt Dateien schreiben zu lassen, würde ich einen zentralen `StructuredEventHub` einführen:

```text
HTTP-Route / WebSocket-Session / Scheduler / Modellverwaltung
                    │
                    ▼
             StructuredEventHub
                    │
       ┌────────────┼───────────────┐
       ▼            ▼               ▼
  Konsolen-Sink  Datei-Sink   PersistentEventStore
                                    │
                       ┌────────────┴────────────┐
                       ▼                         ▼
                 History-HTTP-API         Log-WebSocket
```

Der EventHub übernimmt:

- Schemaergänzung,
- Zeitstempel,
- `eventId` und Cursor,
- Validierung,
- Zuordnung von Session und Transkription,
- Redaction sensibler Felder,
- Verteilung an alle aktivierten Ziele.

Wichtig: Das Schreiben und Versenden von Logs darf die Transkription niemals blockieren. Deshalb braucht jeder Sink eine begrenzte asynchrone Queue.

Bei Überlastung:

- Debug- und detaillierte Performanceereignisse dürfen verworfen werden.
- Audit- und Abschlussereignisse haben höhere Priorität.
- Der Client erhält ein `log.gap`-Ereignis mit der Zahl verworfener Meldungen.

---

# 6. Speicherung und historische Abfrage

Rotierende JSONL-Dateien sind gut für Docker, Dozzle und manuelle Analyse. Für gezielte historische Abfragen nach Session, Zeitraum oder Channel sind sie aber ungeeignet.

Ich würde deshalb beides behalten:

## JSONL

- `logs/voicestt-audit.jsonl`
- `logs/voicestt-transcriptions.jsonl`
- `logs/voicestt-performance.jsonl`

Das normale Systemlog kann weiterhin hauptsächlich über Container-Logging laufen.

## Persistenter Event Store

Für den aktuellen Einzelserver wäre SQLite mit WAL-Modus ausreichend:

```text
logs/voicestt-events.sqlite3
```

Wichtige Indizes:

- Cursor
- Timestamp
- Channel
- Session-ID
- Client-ID
- Transkriptions-ID
- Eventname

Vorgeschlagene History-Endpunkte:

```text
GET /api/logs/events
GET /api/logs/sessions/{sessionId}
GET /api/logs/transcriptions/{transcriptionId}
```

Filter:

- `channels`
- `events`
- `from`
- `to`
- `afterCursor`
- `limit`
- `sessionId`
- `transcriptionId`

Antworten sollten cursorbasiert paginiert werden.

Aufbewahrungszeiten sollten pro Channel einstellbar sein, beispielsweise:

- Audit: 90 Tage
- Transcription: 30 Tage
- Performance-Details: 7–14 Tage
- Performance-Zusammenfassungen: 30 Tage

---

# 7. Eigener Log-WebSocket

Die neue Verbindung könnte unter `/ws/logs` laufen.

Ablauf:

1. Client verbindet sich.
2. Client sendet eine `subscribe`-Nachricht mit Berechtigung und Filtern.
3. Optional werden Ereignisse ab einem Cursor nachgeliefert.
4. Danach wechselt die Verbindung lückenlos auf Live-Ereignisse.

Beispiel:

```json
{
  "type": "subscribe",
  "accessToken": "...",
  "sessionId": "...",
  "channels": ["transcription", "performance"],
  "afterCursor": 18300
}
```

Live-Ereignis:

```json
{
  "type": "log.event",
  "event": {
    "schemaVersion": 1,
    "cursor": 18427,
    "channel": "transcription",
    "event": "transcription.completed"
  }
}
```

Zusätzliche Protokollnachrichten:

- `log.hello`
- `log.subscribed`
- `log.event`
- `log.replay_completed`
- `log.gap`
- `log.error`
- `log.pong`

Die Cursorlösung ermöglicht Reconnects ohne Ereignislücke.

---

# 8. Berechtigungen

Hier ist eine klare Trennung wichtig:

## Normaler Session-Client

Darf standardmäßig sehen:

- `transcription` der eigenen Session,
- `performance` der eigenen Session,
- ausgewählte eigene Session-Auditereignisse.

Darf nicht sehen:

- andere Sessions,
- globale Konfigurationsänderungen,
- Client-IP-Adressen,
- interne Stacktraces,
- globale System- und Modellinformationen, sofern nicht ausdrücklich freigegeben.

## Administrator

Darf alle Channels und Sessions abonnieren und historische Ereignisse abrufen.

Für die laufende Session könnte der Server beim `hello` einen kurzlebigen, sessiongebundenen Logzugang ausgeben. Das eigentliche Token sollte anschließend in der ersten WebSocket-Nachricht und nicht als URL-Query übertragen werden.

Für ältere Sessions brauchen wir eine weitere Entscheidung:

- Nur Administratoren dürfen alte Sessions abrufen.
- Ein Sessiontoken darf die eigene Session noch für eine bestimmte Zeit abrufen.
- Oder es wird eine dauerhafte Clientidentität mit eigenem Schlüssel eingeführt, über die ein Client alle seine früheren Sessions sehen darf.

Meine Empfehlung für den ersten Ausbau:

- Sessiontoken für aktuelle und dieselbe kürzlich beendete Session.
- Adminschlüssel für globale Historie.
- Dauerhafte Clientidentität erst ergänzen, wenn sie wirklich benötigt wird.

---

# 9. Datenschutzkonzept

Ich würde eine zentrale Einstellung vorsehen:

```text
transcriptMode = none | final | full
```

- `none`: kein Text in gespeicherten Logs.
- `final`: nur finaler Text im Transcription-Channel.
- `full`: auch Realtime-Texte; nur für gezieltes Debugging.

Meine Empfehlung als Standard wäre `final` oder bei besonders sensibler Nutzung `none`.

Unabhängig davon sollten niemals protokolliert werden:

- Audio-Rohdaten,
- API-Schlüssel,
- Logzugangstoken,
- Authorization-Header,
- vollständige URL-Querys mit sensiblen Parametern.

Das optionale Audioarchiv bleibt eine eigene, ausdrücklich zu aktivierende Funktion.

---

# 10. Was ich gegenüber dem aktuellen Stand ändern würde

## Technische Korrekturen

- Akkumulierende Recorder-Logger-Handler beheben.
- `log_level` tatsächlich live anwenden.
- Audit-/Performance-Konsolenhandler wirklich auf stdout legen.

## Neues Loggingfundament

- `StructuredEventHub` als zentrale Verteilstelle einführen.
- Gemeinsamen Event-Envelope und stabile IDs definieren.
- Audit und Performance auf den EventHub umstellen.
- Neuen `transcription`-Channel ergänzen.
- Normale Systemlogs nur für ausgewählte Ereignisse strukturieren.

## Einheitliche HTTP-/WebSocket-Behandlung

- Gemeinsame `transcriptionId` einführen.
- Gleiche Ereignisse für angenommen, gestartet, abgeschlossen, abgelehnt und fehlgeschlagen verwenden.
- Unterschiede nur über `transport: "http" | "websocket"` ausdrücken.
- WebSocket-Segmente als einzelne Transkriptionen behandeln.

## Realtime-Messungen

- Zeitpunkt und Sequenz jeder tatsächlichen Realtime-Ausgabe erfassen.
- Abstand zur vorherigen Ausgabe berechnen.
- Keine Texte im Performancekanal speichern.
- Am Ende eine kompakte Performancezusammenfassung erzeugen.

## Speicherung und Zugriff

- JSONL-Dateien weiterhin anbieten.
- Zusätzlich indexierten persistenten Event Store einführen.
- History-API mit Filtern und Cursorpagination ergänzen.
- Eigenen `/ws/logs` für Replay und Liveabonnement ergänzen.
- Session- und Administratorberechtigungen trennen.
- Retention und Datenschutz pro Channel konfigurierbar machen.

## Empfohlene Umsetzungsetappen

1. Ereignisschema, Channelnamen und Datenschutzoptionen verbindlich festlegen.
2. Bestehende technische Loggingfehler beheben.
3. EventHub und Sinks einführen.
4. HTTP und WebSocket auf den gemeinsamen Transkriptionslebenszyklus umstellen.
5. Realtime-Performanceereignisse und Zusammenfassung ergänzen.
6. Persistenten Store und History-API implementieren.
7. Log-WebSocket ergänzen.
8. Browser-/API-Client an History und Liveabonnement anbinden.

Das wäre meine vorläufige Gesamtkonzeption. Sie ist deutlich größer als die ursprünglich vier Logging-Fixes; deshalb würde ich sie als eigenes Architekturvorhaben in den bestehenden Plan aufnehmen und in klar abgegrenzten Etappen implementieren.