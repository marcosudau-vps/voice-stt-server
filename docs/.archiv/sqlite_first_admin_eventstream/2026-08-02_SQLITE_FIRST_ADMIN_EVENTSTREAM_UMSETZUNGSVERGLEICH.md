# Soll-/Ist-Vergleich – SQLite-first Eventstream und Admin-Logvertrag

> **Status:** nach externer Prüfung nachgebessert; Liveabnahme ausstehend
> **Datum:** 2. August 2026
> **Branch:** `feature/sqlite-first-admin-eventstream`
> **Ausgangscommit:** `33bde82fbce14e30d95b88f0936a4ce33e6bdf18`
> **Veröffentlichung:** nicht erfolgt; kein Push, kein Merge nach `main`, kein
> Deployment und keine Änderung am Live-System

## 1. Gesamtergebnis

Der lokal beauftragte Implementierungsumfang ist nach einer unabhängigen
Prüfung und anschließender Nachbesserung umgesetzt. SQLite ist die kanonische
Quelle jedes erzeugten strukturierten Events. Ein normales `log.event` wird
erst nach erfolgreichem Commit sichtbar. Replay und Livephase lesen aus
demselben Store. Der Admin-Key erlaubt getrennt vom Audio-WebSocket globale
History sowie Replay/Live über alle Sessions und Channels.

AP07-S1 ist lokal implementiert und automatisiert nachgewiesen. Von AP07-S2
sind die Abschnitte 5.1 bis 5.5 lokal implementiert und getestet. Abschnitt
5.6, Deployment und Liveabnahme, wurde auf ausdrücklichen Auftrag nicht
ausgeführt. AP07-S2 als Gesamtmeilenstein ist daher noch nicht abgeschlossen
und dieser Branch allein stellt keine Freigabe zur Liveübernahme dar.

Eine frühere Fassung dieses Berichts bewertete die lokale Testabdeckung zu
weitgehend. Der externe Prüfbericht wies zwei Funktionsfehler sowie fehlende
Pflichtnachweise nach. Diese Fassung ersetzt jene Bewertung und dokumentiert
die Korrekturen ausdrücklich.

## 2. Vergleich der Architekturziele

| Planpunkt | Ist-Stand | Bewertung |
| --- | --- | --- |
| SQLite-Commit vor Cursor und Sichtbarkeit | `SQLiteEventStore.append()` weist den nächsten Cursor in der Committransaktion zu; `emit()` bricht bei Fehler ohne Mirror-/Liveausgabe ab | vollständig |
| Einheitliche Zuverlässigkeit | alle erzeugten strukturierten Channels folgen demselben Storepfad; keine Best-Effort-Eventklasse im Clientprotokoll | vollständig |
| Channel-Schalter | `*_logging_enabled=false` deaktiviert nur JSONL/stdout; das Event wird weiterhin committed und replay-/livefähig | vollständig nachgebessert |
| Commit-Wakeup statt Payloadqueue | Subscriber erhalten nur Commit-/Storezustands-Wakeups; `/ws/logs` liest committed Bereiche ab eigenem Scan-Cursor nach | vollständig |
| Optionaler Spiegel darf droppen | JSONL/stdout bleiben priorisierte bounded Queues; Drops verändern SQLite und Client-Replay nicht | vollständig |
| Storeausfall sichtbar | Zustand `degraded`, `hello.logAccess.available=false`, HTTP 503, bestehende Logsockets `1011`, neue Logsockets abgewiesen, Recovery durch nächsten erfolgreichen Commit | vollständig |
| Audio bleibt unabhängig | `/ws/transcribe` erhält keine Adminrechte und wird bei Storeausfall nicht beendet | vollständig |
| Leerer Finaltext terminal | genau ein `transcription.discarded(reason=empty_final)` plus `final_transcript_discarded`, kein leeres `final`-Frame | vollständig |
| Kanalbezogene Retention | persistente payloadfreie Watermarks pro Channel/Session unterscheiden gelöschte relevante Events von normalen globalen Filtersprüngen | vollständig nachgebessert |

## 3. Nachbesserung aufgrund des Prüfberichts

Der Prüfbericht wurde reproduziert und führte zu folgenden Änderungen:

1. Die vorzeitige Rückgabe aus `StructuredEventHub.emit()` bei deaktiviertem
   Channel-Spiegel wurde entfernt. JSONL und stdout bleiben deaktiviert, SQLite,
   Replay und Liveausgabe bleiben vollständig.
2. `retention_watermarks` speichert beim kanalbezogenen Löschen den höchsten
   entfernten Cursor pro Channel und Session ohne Eventpayload. `/ws/logs`
   wertet den Watermark gegen den effektiven Abonnementscope aus.
3. Der Server springt nach einem Retention-Gap nicht über möglicherweise noch
   vorhandene Events hinweg, sondern replayt weiterhin ab dem angeforderten
   Cursor.
4. Empty-Final-Ergebnisse beanspruchen ihren erwarteten Segment-/Generations-
   Abschluss genau einmal; Duplikat- und Disconnectrennen werden verworfen.
5. Die zuvor fehlenden Vertragsfälle wurden automatisiert ergänzt.

## 4. Protokoll und Cursor

Implementiert sind:

- `logProtocolVersion: 2` und `deliveryMode: "sqlite_first"` in
  `hello.logAccess`, `log.hello` und der Admin-Konfigurationssicht;
- `replayAvailable`, `serverInstanceId`, `oldestCursor`, `latestCursor` und der
  Scope-spezifische `retentionCursor`;
- expliziter `authorizationScope`, `allSessions` und `allChannels`;
- mehrseitiges Replay bis zu einem vorab aufgenommenen committed Watermark;
- lückenloser Übergang in die Livephase durch Registrierung vor dem Watermark
  und anschließenden SQLite-Rescan;
- `log.gap(reason=retention)` bei einem nachweislich gelöschten, für Channel
  und Session relevanten Event;
- `log.error(code=cursor_ahead)` bei Cursor oberhalb des High-Watermarks;
- globale Cursorsemantik, bei der gefilterte Sprünge kein Gap bedeuten;
- Keepalive-Rescan und Ping/Pong;
- definierte Fehlercodes und Closecodes `1008` beziehungsweise `1011`.

## 5. Authentifizierung und Admin-Scope

Der konfigurierte Admin-Key wird für HTTP über
`X-VoiceSTT-Admin-Key`/Bearer und für `/ws/logs` als `accessToken` im ersten
Subscribe-Frame ausgewertet. Vergleiche verwenden `secrets.compare_digest`.

Ein Admin kann ohne `sessionId` und Channelangabe global lesen, einschließlich
`system` und älterer Sessions innerhalb der Retention. Sessiontokens bleiben
auf ihre eigene Session sowie `audit`, `transcription` und `performance`
beschränkt. Schlüssel und Tokens erscheinen weder in Eventpayloads noch URLs.

## 6. Browser-Adminbereich

Der vorhandene Settings-Drawer enthält jetzt:

- Channel- und optionale Zeitfilter;
- begrenzte Seitengröße und getrennte Historypagination;
- einen ausdrücklich serverweiten Admin-Livemodus;
- sichtbaren Scope-/Verbindungsstatus;
- Rückkehr zum normalen Sessionlog;
- eine weiterhin auf 30 DOM-Einträge begrenzte Ereignisanzeige.

Der Admin-Key bleibt im Passwortfeld der laufenden Seite und wird nicht in
Local Storage, Session Storage oder einer URL gespeichert.

## 7. Tests und technische Verifikation

### Automatisiert

- fokussierte Eventstore-/FastAPI-Vertragssuite: **64 bestanden**, zusätzlich
  **6 Subtests bestanden**;
- vollständige Pytest-Suite: **374 bestanden, 13 übersprungen**;
- zusätzliche unittest-Subtests im Gesamtlauf: **78 bestanden**;
- direkter unittest-Discovery-Lauf: **340 bestanden, 13 übersprungen**;
- bekannte, nicht durch diese Änderung verursachte Warnung: FastAPI/
  Starlette-Testclient weist auf eine künftige `httpx2`-Migration hin;
- `python -m compileall -q VoiceSTT VoiceSTT_server api_fastapi_server tests`:
  erfolgreich;
- JavaScript der eingebetteten Browserseite über Node geparst: erfolgreich;
- aktive lokale Markdownlinks: erfolgreich geprüft.

Die ergänzten Tests decken insbesondere Commit-vor-Wakeup, Commitfehler,
Recovery samt vollständigem Neu-Replay, eindeutige parallele Cursor,
deaktivierte und tatsächlich fehlschlagende Spiegel, die Modusmatrix
`off|summary|events`, coalesced sowie vollständig ausbleibende Wakeups,
Keepalive-Rescan, mehrseitiges Replay, Fortsetzung nach Abbruch an drei
Replaypositionen, negative und vorausliegende Cursor, kanal-/sessionspezifische
Retention, echte Closecodes `1008`/`1011`, Audiofortsetzung bei Storeausfall,
Sessionisolation, globalen Adminzugriff, Secret-Nichtoffenlegung sowie
Empty-Final-Duplikat-/Disconnectrennen ab.

### Realer lokaler Browser-Smoke

Mit Playwright wurden auf einer lokalen Testinstanz erfolgreich ausgeführt:

1. Audio-/Session-WebSocket verbinden;
2. Admin-Drawer öffnen und Key nur im Passwortfeld eingeben;
3. Admin-Settings authentifiziert laden;
4. globale Historie laden;
5. globalen Admin-Livemodus starten;
6. per authentifiziertem `PATCH /api/config` ein `config.updated` erzeugen;
7. das committed Event sichtbar als `Admin-Live` im DOM empfangen.

### Container

- finaler lokaler Build:
  `docker build --target cpu -t voicestt-server:feature-sqlite-first .`;
- Image-ID:
  `sha256:3f47765f5ceac9536129f4fe067698bfb349938be1b454c37c78dd33ecea8477`;
- Compileall sowie SQLite-first-, Channel-Schalter- und Retention-Watermark-
  Contract-Smoke im gebauten Image: erfolgreich;
- kein Image-Push und kein Containerdeployment.

## 8. Dokumentationsabgleich

Aktualisiert wurden insbesondere:

- `README.md`, `RELEASE_NOTES.md`, `docs/README.md`;
- `docs/structured-logging.md`;
- `docs/fastapi-server.md`;
- der vollständige Ordner `docs/client-development/`.

`docs/configuration.md` wurde geprüft; die Datei dokumentiert den
Recorder-Konstruktor und enthält keinen betroffenen Server-Eventvertrag, daher
war dort keine inhaltliche Änderung erforderlich.

Die zehn Dateien aus `docs/client-development/` und die weiterhin benötigte
Referenz `docs/session-wakeword-erweiterung.md` wurden nach
`P:\DockerProjekte\voice-stt-client\server-docs-for-client-development\`
kopiert. Alle **11 Dateien** sind zwischen Quelle und Ziel SHA-256-identisch.

## 9. Noch bewusst ausstehend

Der lokale Implementierungs- und Testumfang ist abgeschlossen. Bewusst nicht
erfolgt und für den formalen Abschluss von AP07-S2 weiterhin erforderlich sind:

- kein Push des Feature-Branches;
- kein Pull Request oder Merge nach `main`;
- kein Deployment auf den Live-Server.

Damit fehlen weiterhin die produktiven Nachweise aus AP07-S2 Abschnitt 5.6,
insbesondere Health-/Handshakeprüfung, Korrelation eines echten
Transkriptionsereignisses mit SQLite/Liveausgabe, produktives Replay und der
Mehrsessionsnachweis.

Der Benutzer prüft den lokalen Feature-Branch vor jeder separaten
Veröffentlichungsfreigabe.
