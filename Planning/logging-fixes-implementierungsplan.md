# Implementierungsplan: Logging-Fixes

Status: Implementiert, nach Abnahmebericht nachgebessert und verifiziert
Betroffene Basis: lokale Entwicklungsversion des VoiceSTT-Servers
Produktivsystem/VPS: nicht Teil der Planung oder Umsetzung, sofern nicht später ausdrücklich festgelegt

## 1. Ziel

Die erkannten technischen Schwächen des Server-Loggings werden behoben und zu
einem einheitlichen, transportübergreifenden Ereignissystem ausgebaut.
Bestehende Audit-/Performance-Aufrufstellen bleiben über eine
Kompatibilitätsfassade nutzbar; das persistierte Schema wird bewusst als
versionierter Event-Envelope vereinheitlicht.

## 2. Allgemeine Leitlinien

- Änderungen auf die betroffenen Logging- und Konfigurationsstellen begrenzen.
- Keine beiläufigen Refactorings außerhalb des vereinbarten Umfangs.
- Bestehende Audit- und Performance-Ereignisnamen kompatibel halten.
- Keine zusätzlichen Transkript- oder Audiodaten protokollieren, ohne dies ausdrücklich festzulegen.
- Mehrere parallele und nacheinander aufgebaute WebSocket-Sitzungen berücksichtigen.
- Nach der Umsetzung gezielte Regressionstests und anschließend die vollständige Testsuite ausführen.
- Fehler aus den Tests iterativ beheben, bis alle relevanten Prüfungen erfolgreich sind.

## 3. Aufgenommene Fixes

### 3.1 Akkumulierende `voicestt`-Logger-Handler verhindern

Priorität: hoch
Status: umgesetzt

#### Problem

Jeder neu erzeugte `AudioToTextRecorder` fügt dem globalen Logger `voicestt` einen weiteren Konsolenhandler hinzu. Beim Schließen einer Sitzung wird dieser Handler nicht entfernt. Dadurch können Logmeldungen nach mehreren Sitzungen mehrfach ausgegeben werden.

#### Geplante Lösung

- Die Einrichtung des gemeinsamen Recorder-Loggers idempotent machen.
- Einen bestehenden VoiceSTT-Konsolenhandler wiederverwenden, statt pro Recorder einen neuen Handler anzuhängen.
- Den von VoiceSTT verwalteten Handler eindeutig kennzeichnen, damit fremde beziehungsweise anwendungsseitig konfigurierte Handler nicht entfernt oder verändert werden.
- Das bestehende Logformat und das aktuelle Standardlevel zunächst beibehalten.
- Sicherstellen, dass mehrere gleichzeitig aktive Recorder denselben zentralen Handler gefahrlos verwenden.
- Die bisherige Option `no_log_file=True` des FastAPI-Servers unverändert lassen; der Recorder soll weiterhin keine zusätzliche Datei `realtimesst.log` anlegen.

#### Voraussichtlich betroffene Stellen

- `VoiceSTT/core/initialization.py`
- gegebenenfalls Logger-Hilfsfunktionen beziehungsweise Recorder-Shutdown, falls für eine saubere Kapselung erforderlich
- Unit-Tests für Recorder-/Loggerinitialisierung

#### Abnahmekriterien

- Nach dem Erzeugen mehrerer Recorder existiert höchstens ein von VoiceSTT verwalteter Konsolenhandler.
- Eine einzelne Logmeldung wird unabhängig von der Anzahl zuvor erzeugter Recorder nur einmal über diesen Handler ausgegeben.
- Extern konfigurierte Handler bleiben erhalten.
- Parallele Recorder beeinflussen sich beim Schließen nicht gegenseitig.
- `no_log_file=True` erzeugt weiterhin keine Recorder-Logdatei.

### 3.2 Laufzeitverhalten von `log_level` korrigieren

Priorität: mittel
Status: bevorzugte Live-Variante umgesetzt

#### Problem

Eine Änderung von `log_level` über die Laufzeitkonfiguration wird als erfolgreich angewendet gemeldet, verändert aber weder das Level des bereits laufenden Root-/FastAPI-Loggers noch die Uvicorn- oder Recorder-Handler zuverlässig.

#### Bevorzugte Lösung

- Eine zentrale Funktion zum Anwenden des Prozess-Loglevels einführen.
- Bei einer erfolgreichen Laufzeitänderung mindestens folgende aktive Logger beziehungsweise Handler aktualisieren:
  - Root-Logger beziehungsweise FastAPI-Anwendungslogger
  - relevante Uvicorn-Logger
  - den zentralen VoiceSTT-Recorder-Konsolenhandler
- Den normalisierten Levelnamen validieren und nur gültige Python-Logging-Level akzeptieren.
- Die Konfigurationsantwort erst dann als erfolgreich ausgeben, wenn das Level tatsächlich angewendet wurde.
- Das Startverhalten und die Kommandozeilenoption `--log-level` weiterhin über dieselbe Logik führen, damit Start- und Laufzeitkonfiguration nicht auseinanderlaufen.

#### Alternative, falls kein Live-Wechsel gewünscht ist

`log_level` aus den laufzeitänderbaren Einstellungen entfernen und als neustartpflichtige Einstellung ausweisen. Die API müsste eine Laufzeitänderung dann ausdrücklich ablehnen.

#### Voraussichtlich betroffene Stellen

- `api_fastapi_server/server.py`
- gegebenenfalls eine kleine zentrale Logging-Hilfsfunktion
- Tests der Laufzeitkonfiguration und Logger-Level

#### Abnahmekriterien für die bevorzugte Lösung

- Ein Wechsel von `INFO` auf `DEBUG` wirkt ohne Serverneustart.
- Ein Wechsel zurück auf `WARNING` unterdrückt anschließend niedrigere Level.
- API-Antwort und tatsächlicher Loggerzustand stimmen überein.
- Ungültige Level werden mit einer verständlichen Validierungsantwort abgelehnt.
- Audit- und Performance-JSONL-Kanäle bleiben aktiviert beziehungsweise deaktiviert wie separat konfiguriert.

### 3.3 Audit- und Performance-Konsolenausgabe tatsächlich auf `stdout` schreiben

Priorität: niedrig
Status: umgesetzt

#### Problem

Die Einstellungen und Dokumentation sprechen von `request_log_stdout` und `performance_log_stdout`. Die verwendeten `logging.StreamHandler()` schreiben ohne expliziten Stream jedoch standardmäßig nach `stderr`.

#### Geplante Lösung

- Für Audit- und Performance-Konsolenhandler explizit `sys.stdout` verwenden.
- Kalenderdatei-Sinks und JSONL-Format unverändert nutzen.
- Normale Prozess- und Fehlermeldungen nicht pauschal auf stdout umleiten.

#### Voraussichtlich betroffene Stellen

- `VoiceSTT_server/operations.py`
- Tests für die Handlerkonfiguration

#### Abnahmekriterien

- Auditereignisse mit aktivierter stdout-Option werden über stdout ausgegeben.
- Performanceereignisse mit aktivierter stdout-Option werden über stdout ausgegeben.
- Bei deaktivierter stdout-Option erfolgt keine Konsolenausgabe des jeweiligen strukturierten Kanals.
- Rotierende Audit- und Performancedateien funktionieren unverändert.

### 3.4 Auditabdeckung für WebSocket-Transkriptionen ergänzen

Priorität: mittel
Status: als transportübergreifender Transkriptionskanal umgesetzt

#### Problem

Das Auditlog dokumentiert WebSocket-Verbindungen, aber nicht die einzelnen final abgeschlossenen beziehungsweise fehlgeschlagenen WebSocket-Transkriptionen. Die vorhandenen `transcription.*`-Audits gehören im Wesentlichen zur HTTP-API.

#### Empfohlener minimaler Umfang

- Keine Auditereignisse für jedes Realtime-Zwischenergebnis erzeugen.
- Pro finalem WebSocket-Segment höchstens ein zusammenfassendes Erfolgs- oder Fehlerereignis protokollieren.
- Vorgeschlagene neue Ereignisnamen:
  - `stream.transcription.completed`
  - `stream.transcription.failed`
- Ein zusätzliches `stream.transcription.started` nur aufnehmen, falls Beginn und Ende ausdrücklich getrennt nachvollziehbar sein sollen.

#### Vorgeschlagene Felder

- `sessionId`
- `segmentId`
- Engine und Modell
- Sprache
- Audio-/Aufnahmedauer
- relevante Latenzen, soweit an dieser Stelle zuverlässig verfügbar
- Erfolg beziehungsweise Fehler
- optional `text`, ausschließlich im Transkriptionskanal und abhängig von
  `transcript_log_mode` (`none`, `final`, `full`)

#### Zu klärende Fragen

- Soll eine erfolgreiche finale WebSocket-Transkription grundsätzlich im Auditlog erscheinen?
- Reicht ein zusammenfassendes Abschlussereignis?
- Soll der Transkripttext entsprechend der bestehenden Auditoption aufgenommen werden?
- Soll ein leeres finales Ergebnis als erfolgreich, verworfen oder fehlgeschlagen gelten?
- Sind neue Event-IDs gewünscht oder sollen die bestehenden `transcription.completed`/`failed` mit einem Feld wie `transport: "websocket"` wiederverwendet werden?

#### Voraussichtlich betroffene Stellen

- `VoiceSTT_server/operations.py` für deutsche Ereignisbeschreibungen
- `api_fastapi_server/server.py` in der finalen Streamausgabe und in Fehlerpfaden
- Audit-Tests sowie WebSocket-Sitzungstests
- gegebenenfalls Logging-Dokumentation

#### Umgesetzte Entscheidung

HTTP und WebSocket verwenden dieselben `transcription.*`-Ereignisnamen. Das
Top-Level-Feld `transport` unterscheidet `http` und `websocket`. Dadurch können
Clients beide Transportwege identisch auswerten, ohne zwei Taxonomien
zusammenführen zu müssen.

### 3.5 Kalenderbasierte Logablage mit Monatsordnern und Tagesdateien

Priorität: mittel
Status: umgesetzt

#### Problem

Audit- und Performancelogs werden derzeit jeweils in eine langfristig fortgeschriebene Datei geschrieben und nur anhand der Dateigröße rotiert. Dadurch sind einzelne Tage schwer auffindbar und die Dateien lassen sich für Archivierung, Übertragung und manuelle Kontrolle nur umständlich abgrenzen.

#### Zielstruktur

Jeder strukturierte Channel erhält ein eigenes Stammverzeichnis. Darunter wird ein Monatsordner im Format `YYYY-MM` und darin eine Tagesdatei im Format `YYYY-MM-DD.jsonl` angelegt.

Beispiel:

```text
logs/
  audit/
    2026-07/
      2026-07-29.jsonl
      2026-07-30.jsonl
  transcription/
    2026-07/
      2026-07-30.jsonl
  performance/
    2026-07/
      2026-07-30.jsonl
```

Der neue `transcription`-Channel wird in diese Struktur aufgenommen, sobald das übergeordnete Channelkonzept umgesetzt wird.

#### Geplante Lösung

- Einen kalenderbasierten JSONL-Handler beziehungsweise Datei-Sink verwenden, der den Zielpfad aus Channel, Kalenderdatum und konfigurierter Logging-Zeitzone bildet.
- Beim ersten Ereignis eines neuen Tages automatisch den Monatsordner und die Tagesdatei anlegen.
- Bei einem Serverneustart am selben Tag an die vorhandene Tagesdatei anhängen.
- Den Dateiwechsel threadsicher durchführen, damit parallele Audit-, Transkriptions- und Performanceereignisse nicht verloren gehen.
- Die Kalender-Zeitzone explizit konfigurierbar machen; vorgesehener Standard für diese Installation ist `Europe/Berlin`.
- Ereigniszeitstempel weiterhin in UTC speichern. Nur die Zuordnung zu Monatsordner und Tagesdatei richtet sich nach der konfigurierten Kalender-Zeitzone.
- Einen Tageswechsel und einen Monatswechsel ohne Serverneustart erkennen.
- Bestehende alte Logdateien nicht automatisch löschen oder stillschweigend verschieben.

#### Größenbegrenzung innerhalb eines Tages

Der tägliche Dateiwechsel ersetzt nicht zwingend den Schutz vor außergewöhnlich großen Dateien. Falls eine Tagesdatei die konfigurierte Maximalgröße erreicht, darf sie innerhalb desselben Tages in nummerierte Segmente aufgeteilt werden:

```text
2026-07-30.jsonl
2026-07-30.1.jsonl
2026-07-30.2.jsonl
```

Die genaue Benennung und Reihenfolge wird vor der Implementierung verbindlich festgelegt. Ohne Überschreitung der Maximalgröße existiert pro Channel und Tag genau eine Datei.

#### Aufbewahrung

Die bisherige ausschließlich dateianzahlbasierte Option `backup_count` passt nur eingeschränkt zu Tagesdateien. Für die neue Struktur soll eine zeitbasierte Aufbewahrung pro Channel vorgesehen werden, beispielsweise `retention_days`.

Die Aufbewahrung ist pro Channel über `*_log_retention_days` konfigurierbar.
Der sichere Standardwert `0` löscht nichts. Positive Werte berücksichtigen
ausschließlich datierte JSONL-Dateien im jeweiligen konfigurierten
Channel-Stammverzeichnis und die Einträge dieses Channels im SQLite-Store.

#### Voraussichtlich betroffene Stellen

- `VoiceSTT_server/operations.py`
- zukünftiger zentraler Event-/Datei-Sink des Loggingkonzepts
- Servereinstellungen, Kommandozeilenargumente und Konfigurationsvertrag
- `/api/logging`
- Logging-Dokumentation
- Tests für Dateiablage, Tageswechsel, Monatswechsel und Größenrotation

#### Abnahmekriterien

- Für jeden aktivierten strukturierten Channel wird in der richtigen Zeitzone der korrekte Monatsordner verwendet.
- Ereignisse eines Kalendertags landen in der zugehörigen Tagesdatei.
- Der Wechsel von Monatsende auf den ersten Tag des Folgemonats legt automatisch den neuen Monatsordner an.
- Ein Neustart am selben Tag überschreibt die bestehende Datei nicht.
- Gleichzeitige Schreibvorgänge führen weder zu verlorenen noch zu unvollständigen JSONL-Zeilen.
- Eine optionale Größenrotation bleibt auf den aktuellen Tag begrenzt.
- Bestehende historische Logdateien bleiben bei der Umstellung unangetastet.

## 4. Ergänztes Gesamtkonzept

### 4.1 Channels

- `system`: Server-Lifecycle und operative Systemereignisse
- `audit`: Konfigurations-, Modell-, Authentifizierungs- und Sessionaktionen
- `transcription`: fachlicher, transportübergreifender Transkriptions- und
  Wake-Word-Lifecycle
- `performance`: numerische Queue-, Inferenz-, Latenz- und
  Realtime-Kadenzmessungen ohne Realtime-Text

### 4.2 Gemeinsamer Event-Envelope

Jedes strukturierte Ereignis enthält `schemaVersion`, `eventId`, `cursor`,
`timestamp`, `channel`, `event`, `severity` und `serverInstanceId`.
Korrelationsfelder wie `transport`, `sessionId`, `requestId`,
`transcriptionId` und `segmentId` stehen auf oberster Ebene;
ereignisspezifische Daten liegen unter `data`.

### 4.3 Persistenz und Clientzugriff

- Alle aktivierten Channels schreiben asynchron in die kalenderbasierte
  JSONL-Struktur.
- Ein optionaler SQLite-Store hält dieselben Events indiziert. Der zentrale Hub
  vergibt strikt monotone Cursor bereits vor dem Fan-out, sodass auch ein
  temporärer Storefehler keine Cursor dupliziert.
- `GET /api/logs/events`, `GET /api/logs/sessions/{sessionId}` und
  `GET /api/logs/transcriptions/{transcriptionId}` bieten gefilterten
  Historienzugriff.
- `/ws/logs` bestätigt mit `log.subscribed`, liefert Cursor-Replay und
  anschließend Live-Events und beantwortet Client-Pings mit `log.pong`.
- Store, Dateien, stdout und Live-Publishing besitzen unabhängige,
  nichtblockierende Queues. Sink- und Subscriberverluste werden als `log.gap`
  sichtbar; Store-/Dateifehler zusätzlich als `storage.failed`.
- Normale Sessiontokens dürfen nur die eigene Session und die Channels
  `audit`, `transcription` und `performance` lesen. System- und
  sessionübergreifender Zugriff bleiben Admins vorbehalten.

Der vollständige Vertrag steht in `docs/structured-logging.md`.

### 4.4 Datenschutz und Korrelation

- Eine zentrale rekursive Bereinigung läuft vor allen Sinks und entfernt
  Credentials, Authorization-/Cookie-Werte, Querystrings, Binär-/Audiodaten
  sowie im jeweiligen Channel unzulässige Transkriptfelder.
- Performance- und Auditkanal enthalten grundsätzlich keinen Transkripttext.
- IP-Adressen werden nicht als Clientkennung protokolliert.
- Browserclients persistieren eine stabile `clientId`; API-Clients können sie
  über `X-VoiceSTT-Client-ID` liefern. `clientId`, `sessionId`, `requestId` und
  `transcriptionId` bleiben strukturell getrennt.

## 5. Vorgesehene Umsetzungsreihenfolge

1. Logging-Grundlage, Schema, Channel-Sinks und SQLite-Store umsetzen. – erledigt
2. HTTP- und WebSocket-Transkriptionsereignisse vereinheitlichen. – erledigt
3. Historien-API und separaten Live-Log-WebSocket ergänzen. – erledigt
4. Logger-Handler und Live-`log_level` korrigieren. – erledigt
5. Konfiguration und Dokumentation abgleichen. – erledigt
6. Gezielte Tests ausführen. – erledigt
7. Vollständige Testsuite ausführen und Seiteneffekte beheben. – erledigt

## 6. Geplanter Testumfang

### 6.1 Gezielte Tests

- Mehrfachinitialisierung des Recorder-Loggers ohne Handlerduplikate.
- Gleichzeitige Recorder und Sitzungsabbau ohne gegenseitige Loggerbeeinflussung.
- Erhalt fremder Logger-Handler.
- Laufzeitwechsel des Loglevels beziehungsweise korrekte Ablehnung, abhängig von der endgültigen Entscheidung.
- stdout-/Datei-Verhalten von Audit- und Performancekanal.
- Tages- und Monatswechsel in der konfigurierten Logging-Zeitzone.
- Wiederaufnahme derselben Tagesdatei nach einem Serverneustart.
- Größenrotation innerhalb eines Tages und bestehendes JSONL-Schema.
- Transkriptunterdrückung bei `request_log_transcripts=False`.
- Alle drei Varianten von `transcript_log_mode`.
- Rekursive Redaction in Datei, Store und Live-Ausgabe.
- SQLite-Ausfall ohne doppelte oder rückläufige Cursor.
- Langsamer Dateisink und Queue-Sättigung ohne Blockade des Emit-Pfads,
  einschließlich `log.gap`.
- Opt-in-Retention für Kalenderdateien und SQLite.
- History-Routen für Session und Transkription.
- `log.subscribed`, `log.pong` und stabile transportübergreifende `clientId`.
- Falls umgesetzt: genau ein WebSocket-Auditabschluss pro finalem Segment und korrekte Fehlerereignisse.

### 6.2 Regression

- Bestehende Unit- und Integrationstests des Servers.
- Vollständige im Projekt vorhandene Testsuite.
- Keine Tests gegen den produktiven VPS, sofern dies nicht später ausdrücklich beauftragt wird.

### 6.3 Ergebnis

- Gezielte Logging-, HTTP- und WebSocket-Tests: 69 bestanden.
- Vollständige Projektsuite: 359 bestanden, 13 übersprungen und 71 Subtests
  bestanden.
- Inline-JavaScript des Browserclients: Syntaxprüfung bestanden.

## 7. Nicht Bestandteil dieses Planstands

- Änderungen am Wakeword-Verhalten.
- Automatische Aufbewahrung ohne explizit positiven Retention-Wert; der
  Standardwert `0` löscht nichts.
- Ungefilterte Weiterleitung beliebiger Python-/Uvicorn-Textlogzeilen an
  Clients; der Clientzugriff gilt ausschließlich für strukturierte Events.
- Änderungen an ASR-Modellen, Schedulerlogik oder Audiopipeline außerhalb der für die Logging-Fixes zwingend notwendigen Stellen.
- Deployment oder Änderungen auf dem produktiven VPS.
