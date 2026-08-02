# Soll-/Ist-Vergleich – SQLite-first Eventstream und Admin-Logvertrag

> **Status:** abgeschlossen
> **Datum:** 2. August 2026
> **Branch:** `feature/sqlite-first-admin-eventstream`
> **Ausgangscommit:** `33bde82fbce14e30d95b88f0936a4ce33e6bdf18`
> **Veröffentlichung:** nicht erfolgt; kein Push, kein Merge nach `main`, kein
> Deployment und keine Änderung am Live-System

## 1. Gesamtergebnis

Die Gesamtplanung wurde vollständig umgesetzt. SQLite ist die kanonische
Quelle jedes erzeugten strukturierten Events. Ein normales `log.event` wird
erst nach erfolgreichem Commit sichtbar. Replay und Livephase lesen aus
demselben Store. Der Admin-Key erlaubt getrennt vom Audio-WebSocket globale
History sowie Replay/Live über alle Sessions und Channels. Der Browserbereich
stellt diesen Scope bedienbar bereit.

Es besteht keine materielle Abweichung, die eine separate Abweichungsdatei
erfordert. Die bei der Detailprüfung vorgenommene Klarstellung, dass
`transcription_logging_enabled` nur den optionalen Kalender-/stdout-Spiegel
steuert und nicht den zuverlässigen SQLite-/Livevertrag, folgt unmittelbar der
geplanten einheitlichen Zuverlässigkeit aller strukturierten Events.

## 2. Vergleich der Architekturziele

| Planpunkt | Ist-Stand | Bewertung |
| --- | --- | --- |
| SQLite-Commit vor Cursor und Sichtbarkeit | `SQLiteEventStore.append()` weist den nächsten Cursor in der Committransaktion zu; `emit()` bricht bei Fehler ohne Mirror-/Liveausgabe ab | vollständig |
| Einheitliche Zuverlässigkeit | alle erzeugten strukturierten Channels folgen demselben Storepfad; keine Best-Effort-Eventklasse im Clientprotokoll | vollständig |
| Commit-Wakeup statt Payloadqueue | Subscriber erhalten nur Commit-/Storezustands-Wakeups; `/ws/logs` liest committed Bereiche ab eigenem Scan-Cursor nach | vollständig |
| Optionaler Spiegel darf droppen | JSONL/stdout bleiben priorisierte bounded Queues; Drops verändern SQLite und Client-Replay nicht | vollständig |
| Storeausfall sichtbar | Zustand `degraded`, `hello.logAccess.available=false`, HTTP 503, bestehende Logsockets `1011`, neue Logsockets abgewiesen, Recovery durch nächsten erfolgreichen Commit | vollständig |
| Audio bleibt unabhängig | `/ws/transcribe` erhält keine Adminrechte und wird bei Storeausfall nicht beendet | vollständig |
| Leerer Finaltext terminal | genau ein `transcription.discarded(reason=empty_final)` plus `final_transcript_discarded`, kein leeres `final`-Frame | vollständig |

## 3. Protokoll und Cursor

Implementiert sind:

- `logProtocolVersion: 2` und `deliveryMode: "sqlite_first"` in
  `hello.logAccess`, `log.hello` und der Admin-Konfigurationssicht;
- `replayAvailable`, `serverInstanceId`, `oldestCursor` und `latestCursor`;
- expliziter `authorizationScope`, `allSessions` und `allChannels`;
- mehrseitiges Replay bis zu einem vorab aufgenommenen committed Watermark;
- lückenloser Übergang in die Livephase durch Registrierung vor dem Watermark
  und anschließenden SQLite-Rescan;
- `log.gap(reason=retention)` mit verlorener Cursorspanne;
- `log.error(code=cursor_ahead)` bei Cursor oberhalb des High-Watermarks;
- globale Cursorsemantik, bei der gefilterte Sprünge kein Gap bedeuten;
- Keepalive-Rescan und Ping/Pong;
- definierte Fehlercodes und Closecodes `1008` beziehungsweise `1011`.

## 4. Authentifizierung und Admin-Scope

Der konfigurierte Admin-Key wird für HTTP über
`X-VoiceSTT-Admin-Key`/Bearer und für `/ws/logs` als `accessToken` im ersten
Subscribe-Frame ausgewertet. Vergleiche verwenden `secrets.compare_digest`.

Ein Admin kann ohne `sessionId` und Channelangabe global lesen, einschließlich
`system` und älterer Sessions innerhalb der Retention. Sessiontokens bleiben
auf ihre eigene Session sowie `audit`, `transcription` und `performance`
beschränkt. Schlüssel und Tokens erscheinen weder in Eventpayloads noch URLs.

## 5. Browser-Adminbereich

Der vorhandene Settings-Drawer enthält jetzt:

- Channel- und optionale Zeitfilter;
- begrenzte Seitengröße und getrennte Historypagination;
- einen ausdrücklich serverweiten Admin-Livemodus;
- sichtbaren Scope-/Verbindungsstatus;
- Rückkehr zum normalen Sessionlog;
- eine weiterhin auf 30 DOM-Einträge begrenzte Ereignisanzeige.

Der Admin-Key bleibt im Passwortfeld der laufenden Seite und wird nicht in
Local Storage, Session Storage oder einer URL gespeichert.

## 6. Tests und technische Verifikation

### Automatisiert

- fokussierte Eventstore-/FastAPI-Vertragssuite: **56 bestanden**;
- vollständige Pytest-Suite: **366 bestanden, 13 übersprungen**;
- zusätzliche unittest-Subtests: **72 bestanden**;
- bekannte, nicht durch diese Änderung verursachte Warnung: FastAPI/
  Starlette-Testclient weist auf eine künftige `httpx2`-Migration hin;
- `python -m compileall -q VoiceSTT VoiceSTT_server api_fastapi_server tests`:
  erfolgreich;
- JavaScript der eingebetteten Browserseite über Node geparst: erfolgreich;
- aktive lokale Markdownlinks: erfolgreich geprüft.

Die ergänzten Tests decken insbesondere Commit-vor-Wakeup, Commitfehler,
Recovery, eindeutige parallele Cursor, Mirrorüberlast, coalesced Wakeups,
mehrseitiges Replay, Cursor-ahead, Retentiongap, Storeausfall, Sessionisolation,
globalen Admin-History-/Replay-/Livezugriff, Secret-Nichtoffenlegung und
Empty-Final-Terminalität ab. Eine zuvor nur unter der Gesamtsuite sichtbare
WebSocket-Abbruchrace wurde behoben und der betroffene Test anschließend fünf
Mal hintereinander erfolgreich wiederholt.

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
  `sha256:98e177826bdcaea989bf63c5644c9c084c9e7a252266bc368a1c4ad35e2af59c`;
- Compileall und SQLite-first-Contract-Smoke im gebauten Image: erfolgreich;
- kein Image-Push und kein Containerdeployment.

## 7. Dokumentationsabgleich

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

## 8. Noch bewusst ausstehend

Die technische Aktion ist abgeschlossen. Bewusst nicht erfolgt sind nur die
vom Auftrag ausgeschlossenen Veröffentlichungsschritte:

- kein Push des Feature-Branches;
- kein Pull Request oder Merge nach `main`;
- kein Deployment auf den Live-Server.

Der Benutzer prüft den lokalen Feature-Branch vor jeder separaten
Veröffentlichungsfreigabe.
