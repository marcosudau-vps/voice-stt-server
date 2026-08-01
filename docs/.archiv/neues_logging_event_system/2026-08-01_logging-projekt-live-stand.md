# Strukturiertes Logging: veröffentlichter Gesamtstand vom 01.08.2026

## Zweck und Geltungsbereich

Dieses Dokument fasst das Gesamtprojekt zur Erneuerung des VoiceSTT-Server-Loggings
ausgehend vom am 01.08.2026 tatsächlich veröffentlichten und laufenden Stand
zusammen. Es vergleicht die frühere Implementierung mit dem Ergebnis der
[ursprünglichen Planung](2026-07-30_LOGGING_EVENT_SYSTEM.md), beschreibt
die neue Architektur und hält fest, welche Teile auf GitHub und auf dem VPS
nachweislich angekommen sind.

Maßgeblicher Veröffentlichungsstand ist:

- Repository: `marcosudau-vps/voice-stt-server` (privat)
- Branch: `main`
- Commit: `48af0d09026275fb30d32d7f0aba49871a4c7467`
- Commit-Titel: `fix(docker): correct persisted data paths after logging rollout`
- GitHub-Push: 01.08.2026, 18:00:53 Uhr MESZ
- laufendes Docker-Image: `sha256:3ccee0b8872765d9c40d0f2626f80f6cebf91174efcee1bb23fb8062b5c08fdd`
- Image gebaut: 01.08.2026, 18:18:44 Uhr MESZ
- Container `stt-voice` gestartet: 01.08.2026, 18:22:04 Uhr MESZ

## Ergebnis der Gegenprüfung

Die gesamte geplante Architektur und alle vorgesehenen Komponenten sind
veröffentlicht. Vier der fünf ursprünglichen Fixgruppen sind vollständig
erfüllt; die transportübergreifende Transkriptionsabdeckung ist weitgehend
erfüllt, besitzt aber noch einen Randfall bei leeren finalen
WebSocket-Ergebnissen. Im ergänzten Gesamtkonzept bleibt außerdem die
sink-spezifische Sichtbarkeit von `log.gap` bei gleichzeitiger Überlast mehrerer
Sinks zeitabhängig. Die Umsetzung ist deshalb als nahezu vollständig, aber
nicht als uneingeschränkt 100-prozentig abzunehmen.

Die Veröffentlichung wurde über vier Ebenen gegengeprüft:

| Ebene | Nachgewiesener Stand | Ergebnis |
| --- | --- | --- |
| GitHub | authentifiziert abgefragter `main`-Head `48af0d0` | stimmt überein |
| lokale Entwicklungsversion | sauberer `main`-Checkout auf `48af0d0` | stimmt überein |
| aktiver VPS-Checkout | sauberer `main`-Checkout auf `48af0d0` | stimmt überein |
| laufender Container | Image nach dem GitHub-Push gebaut; zentrale Laufzeitdateien bytegenau identisch mit dem VPS-Checkout | stimmt überein |

Für den letzten Vergleich wurden `event_logging.py`, `operations.py`,
`server.py`, `initialization.py` und der Browserclient zwischen aktivem
Server-Checkout und laufendem Container per SHA-256 verglichen. Alle fünf
Dateien waren identisch. Abweichende Hashwerte zwischen Windows-Checkout und
Linux-Checkout beruhen auf der Zeilenendendarstellung; beide Checkouts zeigen
auf denselben Git-Commit und sind jeweils sauber.

Auch die Laufzeitfunktion ist sichtbar:

- `/health` meldete den Server als `ok`, `ready` und den Container als gesund.
- Die drei neuen History-Routen werden vom laufenden Server angeboten.
- Ein Aufruf der allgemeinen History ohne Berechtigung wurde korrekt mit HTTP
  `401` abgewiesen.
- Der persistente SQLite-Store enthielt zum Prüfzeitpunkt 66 neue strukturierte
  Events mit lückenlos fortlaufenden Cursorwerten von 1 bis 66.
- In allen vier Channels waren bereits Live-Events vorhanden: `system` 2,
  `audit` 1, `transcription` 19 und `performance` 44.
- Für alle vier Channels existierten die neuen Tagesdateien unter
  `/data/logs/<channel>/2026-08/2026-08-01.jsonl`.

Die Zähler sind nur ein Prüfzeitpunkt und wachsen im laufenden Betrieb weiter.

## Veröffentlichte Commitfolge

Das Logging-Projekt wurde gegenüber dem vorherigen Stand `9a65396` in vier
aufeinander aufbauenden Commits veröffentlicht:

1. `ec9c44e` – Einführung des strukturierten Ereignissystems.
2. `6ccc615` – Korrekturen aus dem technischen Review, insbesondere bei
   Redaction, Queues, Replay, Retention und Zugriffstrennung.
3. `f776bda` – Angleichung der Client- und Serverdokumentation an den realen
   Vertrag.
4. `48af0d0` – Korrektur und Vereinheitlichung der persistenten Docker-Pfade
   unter `/data`.

## Planabgleich

| Planpunkt | Live-Status | Nachweis und Einordnung |
| --- | --- | --- |
| Idempotenter `voicestt`-Logger-Handler | vollständig | Ein markierter Konsolenhandler wird unter Lock wiederverwendet; fremde Handler bleiben bestehen. |
| Laufzeitwirksames `log_level` | vollständig | Validierung und sofortige Anwendung auf Root-, FastAPI-, Uvicorn- und VoiceSTT-Logger. |
| Audit und Performance wirklich auf `stdout` | vollständig | Strukturhandler verwenden bei aktivierter Option explizit `stdout`; normale Fehlerlogs bleiben davon getrennt. |
| Einheitliche HTTP-/WebSocket-Transkriptionsereignisse | weitgehend | Beide Transportwege nutzen `transcription.*`; das Top-Level-Feld `transport` unterscheidet `http` und `websocket`. Ein leeres finales WS-Ergebnis wird derzeit übersprungen und erhält kein terminales strukturiertes Event. |
| Kalenderbasierte Ablage | vollständig | Monatsordner, Tagesdateien, Append nach Neustart, Tagessegmente und konfigurierbare Zeitzone sind implementiert. |
| Vier Channels | vollständig | `system`, `audit`, `transcription` und `performance` sind implementiert und live befüllt. |
| Versionierter Event-Envelope | vollständig | Gemeinsame Pflichtfelder, Korrelationsfelder, `data` und monotoner Cursor werden zentral erzeugt. |
| Asynchroner Fan-out und Verlustsichtbarkeit | teilweise | Emit bleibt nichtblockierend und Verlustzähler funktionieren. Bei gleichzeitiger Überlast kann die auf Queuegröße 1 begrenzte Control-Queue einen sink-spezifischen `log.gap`-Hinweis verdrängen. |
| SQLite-Historie | vollständig | Indexierter WAL-Store ist live aktiv und enthält Events aller vier Channels. |
| History-HTTP-API | vollständig | Allgemeine, sessionbezogene und transkriptionsbezogene Abfragen sind veröffentlicht. |
| Separater Log-WebSocket | weitgehend | Authentifiziertes Replay mit anschließendem Livestream, Keepalive, Ping/Pong und Gap-Meldungen ist implementiert; die sink-spezifische Gap-Garantie besitzt den genannten Überlastrandfall. |
| Sessionbezogene Zugriffstrennung | vollständig | Sessiontokens begrenzen Session und Channels; systemweite Abfragen bleiben Admins vorbehalten. |
| Datenschutz und Redaction | vollständig | Zentrale rekursive Bereinigung findet vor allen Sinks statt; Audit und Performance enthalten keinen Transkripttext. |
| Browser-Anbindung | vollständig | Stabile `clientId`, zweiter WebSocket, Cursor-Replay und Wiederverbindung sind integriert. |
| Persistente Docker-Pfade | vollständig | Logs, SQLite und Laufzeitkonfiguration liegen unter dem auf `/data` gemounteten Datenstamm. |
| Gezielte und vollständige Tests | im veröffentlichten Stand vorhanden und bei der Implementierungsabnahme ausgeführt; aktueller gezielter Lauf nicht vollständig grün | Planungsstand dokumentiert 359 bestandene Tests, 13 übersprungene Tests und 71 bestandene Subtests. Ein aktueller Lauf der drei relevanten Logging-/HTTP-/WS-Gruppen ergab zweimal 68 bestanden und 1 fehlgeschlagen; der isolierte Wiederholungslauf des fehlgeschlagenen Überlasttests bestand. |

## Was sich gegenüber vorher geändert hat

### 1. Von getrennten Logdateien zu einem gemeinsamen Ereignissystem

Vorher existierten im Wesentlichen getrennte Audit-/Request- und
Performance-Logger. Sie besaßen eigene Formate und Aufrufstellen, aber keinen
gemeinsamen Envelope, keinen zentralen Cursor, keinen einheitlichen
Clientzugriff und keine durchgehende transportübergreifende Korrelation.

Jetzt nimmt ein zentraler `StructuredEventHub` alle strukturierten Events an.
Er bereinigt die Daten, erzeugt den gemeinsamen Envelope, vergibt den Cursor
und verteilt das Event anschließend unabhängig an Persistenz, Konsole und
Live-Abonnenten. Bestehende Audit- und Performance-Aufrufstellen bleiben über
Kompatibilitätsfassaden nutzbar.

Der Datenfluss ist damit:

```text
HTTP, WebSocket, Recorder, Scheduler und Server-Lifecycle
                         |
                         v
              StructuredEventHub.emit()
                         |
        Redaction -> Envelope -> Cursorvergabe
                         |
          +--------------+--------------+-------------+
          |              |              |             |
          v              v              v             v
       JSONL          SQLite          stdout       /ws/logs
```

Die zentrale Implementierung liegt in
[`VoiceSTT_server/event_logging.py`](../../../VoiceSTT_server/event_logging.py). Die
Integration in den Dienst erfolgt in
[`api_fastapi_server/server.py`](../../../api_fastapi_server/server.py); die bisherigen
Manager in [`VoiceSTT_server/operations.py`](../../../VoiceSTT_server/operations.py)
sind als kompatible Fassaden erhalten.

### 2. Vier fachlich getrennte Channels

| Channel | Aufgabe | Typische Inhalte | Transkripttext |
| --- | --- | --- | --- |
| `system` | Prozess- und Infrastrukturzustand | Start, Bereitschaft, Shutdown, Worker-, Scheduler-, Recorder- und Speicherfehler | nein |
| `audit` | nachvollziehbare Bedien- und Verwaltungsaktionen | Authentifizierung, Konfiguration, Modelle, Sessions und kompatible HTTP-Audits | nein |
| `transcription` | fachlicher STT- und Wakeword-Lifecycle | Annahme, Start, Aufnahme, Abschluss, Abbruch, Fehler, Wakeword-Zustände | abhängig von `transcript_log_mode` |
| `performance` | numerische Messwerte | Queuezeiten, Inferenzdauer, Latenzen, Speichernutzung und Realtime-Kadenz | nein |

Damit sind operative Zustände, sicherheitsrelevante Aktionen, fachliche
Transkriptionsabläufe und Messdaten voneinander filterbar, ohne ihre gemeinsame
Korrelation zu verlieren.

### 3. Einheitlicher versionierter Event-Envelope

Jedes Event besitzt folgende gemeinsame Pflichtfelder:

- `schemaVersion`
- `eventId`
- `cursor`
- `timestamp`
- `channel`
- `event`
- `severity`
- `serverInstanceId`
- `data`

Soweit vorhanden, stehen die Korrelationsfelder `transport`, `clientId`,
`sessionId`, `requestId`, `transcriptionId` und `segmentId` auf oberster Ebene.
Nicht vorhandene Korrelationsfelder werden weggelassen. Optional kann außerdem
eine menschenlesbare `meldung` enthalten sein.

Der Cursor wird bereits vor dem Fan-out monoton vergeben. Ein späterer
Storefehler führt deshalb weder zu doppelten noch zu rückläufigen Cursorwerten.

### 4. HTTP und WebSocket folgen demselben fachlichen Vertrag

Vorher waren HTTP-Transkriptionen im Audit sichtbar, während bei
WebSocket-Sitzungen vor allem Verbindungsereignisse und Clientnachrichten
vorlagen. Ein finaler WebSocket-Abschnitt war im Logging nicht gleichwertig zu
einer HTTP-Transkription nachvollziehbar.

Jetzt verwenden beide Transportwege unter anderem:

- `transcription.accepted`
- `transcription.started`
- `transcription.completed`
- `transcription.failed`
- `transcription.rejected`

WebSocket-Sitzungen ergänzen die streambezogenen Zustände, beispielsweise
`transcription.recording_started`, `transcription.recording_ended`,
`transcription.cancelled` sowie Wakeword-Warten, Treffer, Timeout und
Follow-up-Zustände. Das Feld `transport` sorgt dafür, dass Clients dieselbe
Taxonomie für beide Wege verwenden können.

Eine bewusst beibehaltene Kompatibilitätsnuance ist, dass einige
HTTP-`transcription.*`-Ereignisse zusätzlich im Auditkanal erscheinen. Bei
gleichzeitigem Abonnement von `audit` und `transcription` können für einen
HTTP-Vorgang deshalb fachlich ähnliche Einträge in zwei Channels sichtbar sein.

### 5. Realtime-Messung ohne Realtime-Text im Performancekanal

Realtime-Aktualisierungen werden nicht als ungebremste Textfolge im
Performancekanal gespeichert. Stattdessen können Kadenz und Laufzeit mit
numerischen Events ausgewertet werden:

- Sequenznummer und Anzahl der Realtime-Ereignisse
- Abstand zum vorherigen Ereignis
- vergangene Zeit seit Segmentbeginn
- Zeichenanzahlen und Stabilisierungsmetadaten
- Zeit bis zum ersten Realtime-Ergebnis
- Zeit bis zum finalen Ergebnis
- Durchschnitt, Minimum, Maximum, P50 und P95

`realtime_log_detail` steuert dies mit `off`, `summary` oder `events`.

### 6. Kalenderbasierte JSONL-Ablage

Die neue persistente Struktur lautet:

```text
<data-root>/logs/
  audit/YYYY-MM/YYYY-MM-DD.jsonl
  performance/YYYY-MM/YYYY-MM-DD.jsonl
  system/YYYY-MM/YYYY-MM-DD.jsonl
  transcription/YYYY-MM/YYYY-MM-DD.jsonl
```

Beim Neustart am selben Tag wird angehängt. Überschreitet eine Tagesdatei die
konfigurierte Maximalgröße, entstehen nummerierte Segmente wie
`2026-08-01.1.jsonl`. Die Kalenderzuordnung folgt der konfigurierten Zeitzone;
die Eventzeitstempel bleiben UTC.

Alte Request- und Performance-Dateien wurden bei der Umstellung absichtlich
nicht gelöscht. Sie können neben der neuen Struktur weiter auf dem Datenvolume
liegen, werden vom neuen Stand aber nicht als neue Channeldateien fortgeführt.

`*_log_retention_days = 0` bedeutet weiterhin: keine automatische Löschung.
Positive Werte löschen ausschließlich passend datierte Dateien des jeweiligen
Channels und die entsprechenden SQLite-Einträge. Die alte Einstellung
`backup_count` bleibt aus Kompatibilitätsgründen akzeptiert, begrenzt die neuen
nummerierten Tagessegmente aber nicht.

### 7. Indexierte Historie in SQLite

Zusätzlich zu JSONL werden dieselben Events in
`<data-root>/logs/voicestt-events.sqlite3` gespeichert. Der Store verwendet
WAL-Modus und indexiert unter anderem Zeit, Channel, Eventname, Session,
Client und Transkription.

Die HTTP-Historie steht über folgende Routen bereit:

- `GET /api/logs/events`
- `GET /api/logs/sessions/{sessionId}`
- `GET /api/logs/transcriptions/{transcriptionId}`

Filter umfassen Channels, Eventnamen, Session, Transkription, Zeitbereich,
`afterCursor` und `limit`. Pro Antwort sind höchstens 1000 Events vorgesehen.
Ist der Store deaktiviert, funktionieren neue Live-Events weiter, Historie und
Cursor-Replay stehen dann jedoch nicht zur Verfügung.

### 8. Separater Live-Log-WebSocket

Logs werden nicht in den Audio-/Transkriptions-WebSocket gemischt. Der eigene
Endpunkt `/ws/logs` übernimmt:

1. Authentifizierung und Subscription.
2. `log.hello` und `log.subscribed`.
3. Cursorbasiertes, bei Bedarf paginiertes Replay.
4. `log.replay_completed`.
5. Fortlaufende `log.event`-Nachrichten.
6. `log.keepalive`, `log.pong`, `log.gap` und `log.error`.

Store, Datei, stdout und Live-Publishing besitzen voneinander unabhängige,
nichtblockierende Queues. Der Audio-/Transkriptionspfad wird dadurch auch bei
Überlast nicht unbegrenzt blockiert. Verlustzähler und Gap-Meldungen machen
Überlast grundsätzlich sichtbar. Wenn mehrere Sinks gleichzeitig ausfallen
und die Control-Queue ebenfalls nur einen Eintrag fasst, kann jedoch ein
sink-spezifischer Gap-Hinweis von einem anderen verdrängt werden. Alle Channels
teilen innerhalb des Dateisinks einen gemeinsamen Dateiworker; die Trennung
erfolgt dort über den Channel-Zielpfad.

### 9. Zugriffstrennung

Eine Transkriptionssession erhält im `hello` einen zufälligen, kurzlebigen
Logzugriffstoken. Er wird nicht in die WebSocket-URL geschrieben, sondern erst
in der Subscription-Nachricht übertragen.

Ein Sessiontoken:

- ist an genau eine Session gebunden;
- darf nur `audit`, `transcription` und `performance` lesen;
- darf nicht den `system`-Channel lesen;
- darf keine fremde Session oder serverweite Historie lesen;
- bleibt für nachträgliche History-Abfragen bis zu 24 Stunden oder bis zum
  Prozessneustart gültig.

Systemweite und sessionübergreifende Abfragen benötigen Adminrechte. Bei HTTP
ist ohne konfigurierten Admin-Key ein administrativer Loopback-Zugriff möglich;
der Log-WebSocket verlangt dagegen immer Admin-Key oder Sessiontoken.

### 10. Datenschutz und zentrale Redaction

Vor allen Sinks läuft dieselbe rekursive Bereinigung. Entfernt oder neutralisiert
werden insbesondere:

- Tokens, API-Keys, Passwörter und allgemeine Secretfelder
- Authorization- und Cookie-Werte
- Querystrings und Querydaten
- Binär- und Audiodaten
- im jeweiligen Channel nicht erlaubte Transkriptfelder

`transcript_log_mode` besitzt drei Stufen:

- `none`: kein Transkripttext
- `final`: Text nur bei `transcription.completed` im Transkriptionskanal
- `full`: erlaubte Transkriptfelder nur im Transkriptionskanal

Audit und Performance bleiben unabhängig von diesem Modus textfrei.
IP-Adressen werden nicht als Clientkennung verwendet.

### 11. Stabile Korrelation im Browser und für API-Clients

Der Browserclient persistiert eine stabile Installations-`clientId` in
`localStorage`, sendet sie an `/ws/transcribe` und öffnet nach dem normalen
`hello` automatisch `/ws/logs`. Innerhalb der laufenden Seite merkt er sich den
letzten Cursor und verbindet sich nach Trennung oder `log.gap` erneut.

API-Clients können dieselbe Korrelation über `X-VoiceSTT-Client-ID` liefern.
`clientId`, `sessionId`, `requestId`, `transcriptionId` und `segmentId` bleiben
getrennte Konzepte und können dadurch gezielt gefiltert werden.

Der Browsercursor wird derzeit nicht über einen Seitenreload hinweg
persistiert. Eine frei filterbare Oberfläche für ältere Logs ist ebenfalls
nicht Bestandteil des Browserclients; der vollständige ältere Zugriff ist
serverseitig über die History-API vorhanden.

### 12. Logger- und Loglevel-Korrekturen

Die Recorderinitialisierung fügt nicht länger für jede Session einen weiteren
globalen Konsolenhandler hinzu. Ein von VoiceSTT markierter Handler wird unter
Lock wiederverwendet. Anwendungsseitige fremde Handler werden weder entfernt
noch verändert. `no_log_file=True` erzeugt weiterhin keine zusätzliche
Recorder-Logdatei.

Änderungen an `log_level` werden validiert und wirken ohne Neustart auf:

- Root-/Anwendungslogger
- relevante Uvicorn-Logger
- den zentralen VoiceSTT-Konsolenhandler

Audit-/Performance-Channelaktivierung und Prozess-Loglevel bleiben getrennte
Einstellungen.

### 13. Einheitlicher persistenter Datenstamm

`data_root_path` ist die Quelle für alle Laufzeitpfade:

- `logs/audit`
- `logs/performance`
- `logs/system`
- `logs/transcription`
- `logs/audio`
- `logs/voicestt-events.sqlite3`
- `config/runtime.json`

Im produktiven Compose-Stack ist `/home/marco/selfhost/data/services/voice/stt-voice`
schreibbar auf `/data` gemountet. Modelle und Serverkonfiguration bleiben
read-only. Dadurch überleben Logs, SQLite-Store und Laufzeitänderungen einen
Containerneubau.

## Aktive Produktionskonfiguration am 01.08.2026

Die effektive Konfiguration wurde über die laufende `/api/config`-Antwort
geprüft. Sie kann wegen persistierter Laufzeitänderungen von der statischen
`stt-config.yaml` abweichen.

| Einstellung | Effektiver Wert |
| --- | --- |
| Datenstamm | `/data` |
| Kalenderzeitzone | `Europe/Berlin` |
| Prozess-Loglevel | `INFO` |
| Queuegröße | 10.000 Events |
| `system` | aktiviert, stdout aus |
| `audit` | aktiviert, stdout aus |
| `transcription` | aktiviert, stdout aus |
| `performance` | aktiviert, stdout an |
| Live-Log-WebSocket | aktiviert |
| Realtime-Detail | `events` |
| Transkriptmodus | `final` |
| Maximalgröße je Tagesdateisegment | 10 MiB |
| Retention aller Channels | `0`, keine automatische Löschung |

Bemerkenswert ist die wirksame Runtime-Übersteuerung für Audit-stdout: In der
statischen Serverdatei steht `request_log_stdout: true`, die persistierte
Laufzeitkonfiguration setzt den effektiven Wert jedoch auf `false`. Die
API-Antwort bildet den tatsächlich laufenden Zustand ab.

## Verifikation und verbleibende Grenzen

Der Live-Check hat Veröffentlichung, Imageinhalt, Health, Routenschutz,
Kalenderdateien, SQLite-Persistenz, Channelbefüllung und effektive Konfiguration
direkt geprüft. Nicht künstlich im Produktionssystem provoziert wurden
Tages-/Monatswechsel, Queueüberlauf, Retention-Löschung, Storeausfall und
autorisierte WebSocket-Replay-Grenzfälle. Dafür existieren gezielte Unit- und
Integrationstests im veröffentlichten Commit.

Die vollständige Suite wurde bei dieser Gegenprüfung nicht erneut ausgeführt.
In der vorhandenen Projekt-`.venv` fehlen `pytest`, `numpy`, `soundfile` und
`PyYAML`, sodass ein Lauf dort bereits beim Import abbrach und keinen
funktionalen Codebefund lieferte. Ein verfügbarer gezielter Lauf der drei
relevanten Logging-/HTTP-/WebSocket-Testgruppen ergab dagegen reproduzierbar
`68 bestanden, 1 fehlgeschlagen`. Betroffen war
`test_event_hub_overload_never_blocks_emit_and_reports_gap`. Der Test bestand
isoliert, scheitert aber im Gruppenlauf zeitabhängig, weil bei Queuegröße 1 ein
anderer Gap-Hinweis den erwarteten `file`-Gap verdrängen kann. Der dokumentierte
Abnahmestand aus der Implementierungsphase lautet weiterhin 359 bestanden,
13 übersprungen und 71 bestandene Subtests; er beschreibt nicht den aktuellen
flaky Gruppenlauf.

Weitere bewusst bekannte Grenzen beziehungsweise Vertragsdetails:

- HTTP kann aus Kompatibilitätsgründen ähnliche Transkriptionsereignisse in
  `audit` und `transcription` erzeugen.
- Leere finale WebSocket-Ergebnisse werden übersprungen und erhalten derzeit
  kein terminales `transcription.completed`, `failed` oder `cancelled`.
- Bei gleichzeitiger Überlast mehrerer Sinks ist ein Gesamtverlust erkennbar,
  aber nicht jeder betroffene Sink wird zuverlässig in einem eigenen
  `log.gap` genannt.
- Sessiontokens werden beim Schließen einer Session nicht sofort widerrufen,
  sondern bleiben für die sessioneigene Historie bis zum Ablauf nutzbar.
- Der Browser merkt sich den Logcursor nicht über einen Seitenreload hinweg.
- Der Browser bietet keine vollständige historische Suchoberfläche; dafür ist
  die History-API vorgesehen.
- Alte Logdateien werden bei der Migration absichtlich weder verschoben noch
  gelöscht.

## Weiterführende technische Dokumentation

Der stabile Protokoll- und Konfigurationsvertrag steht in
[`docs/structured-logging.md`](../../structured-logging.md). Ergänzende Clientdetails
befinden sich unter [`docs/client-development/`](../../client-development/README.md).
Die vorliegende Datei ist der datierte Veröffentlichungs- und Projektbericht;
sie ersetzt nicht die fortlaufend gepflegte Vertragsreferenz.
