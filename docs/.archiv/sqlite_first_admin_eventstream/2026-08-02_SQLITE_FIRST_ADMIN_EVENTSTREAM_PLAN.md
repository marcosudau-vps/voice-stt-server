# Gesamtplanung – SQLite-first Eventstream und vollständiger Admin-Logvertrag

> **Status:** abgeschlossen
> **Datum:** 2. August 2026
> **Branch:** `feature/sqlite-first-admin-eventstream`
> **Ausgangscommit:** `33bde82fbce14e30d95b88f0936a4ce33e6bdf18`
> **Veröffentlichung:** ausdrücklich nicht Bestandteil dieser Aktion; kein Push,
> Merge nach `main` und kein Deployment ohne separate Benutzerfreigabe

## 1. Auftrag

Der bestehende strukturierte Servereventstrom wird so gehärtet, dass jedes
normal über `/ws/logs` ausgelieferte Event zuvor erfolgreich in SQLite
committed wurde. Replay und Liveauslieferung lesen aus derselben kanonischen
Storequelle.

Gleichzeitig wird der vorhandene Adminvertrag zu einem vollständig getesteten
und dokumentierten serverweiten Logzugriff ausgebaut. Der Browser-Adminbereich
soll nach Eingabe des Admin-Keys sowohl ältere, noch in Retention vorhandene
Events als auch einen serverweiten Liveeventstrom über alle Sessions und
berechtigten Channels anzeigen können.

Die Umsetzung wird lokal vollständig getestet und veröffentlichungsreif
vorbereitet. Anschließend wird die aktive Server-Client-Dokumentation
vollständig in das Clientprojekt synchronisiert. Vor einer Veröffentlichung
prüft der Benutzer den lokalen Feature-Branch.

## 2. Ausgangslage

Der Server besitzt bereits:

- strukturierte Event-Envelopes mit globalem Cursor,
- SQLite-Store, JSONL/stdout-Spiegel und Live-Publisher,
- `/ws/logs` mit Replay, Livephase, Filterung, Keepalive und Ping/Pong,
- Sessiontokens aus `hello.logAccess`,
- Admin-Key-Authentifizierung für HTTP-Verwaltungsendpunkte,
- Admin-Key als `accessToken` für serverweite `/ws/logs`-Subscriptions,
- Historyendpunkte für Events, Sessions und Transkriptionen,
- einen Browser-Adminbereich für Modelle, Sprache, Wake Word und Logging.

Bekannte Vertragslücken:

- Store und Live-Publisher werden unabhängig bedient; Live kann vor oder ohne
  erfolgreichen Storecommit sichtbar werden.
- flüchtige Subscriberqueues transportieren Eventpayloads und können droppen.
- Storeausfall kann ein nur live existierendes Event erzeugen.
- Cursormetadaten unterscheiden Retention, Cursor-ahead und gefilterte Sprünge
  nicht vollständig.
- ein leerer finaler STT-Text erhält kein terminales fachliches Event.
- der Browserlogbereich verwendet ausschließlich den Token der aktuellen
  Transkriptionssession und stellt keinen globalen Admin-History-/Livepfad dar.
- der globale Logzugriff mit tatsächlich konfiguriertem Admin-Key besitzt noch
  keine vollständige automatisierte Vertragsmatrix.
- Admin-Key-Vergleiche verwenden einfache Stringgleichheit.

## 3. Verbindliche Entscheidungen

### 3.1 SQLite ist kanonisch

Für jedes tatsächlich erzeugte strukturierte Event gilt:

```text
erzeugen → sanitizen/validieren → SQLite-Commit → finaler Cursor
         → Commit-Wakeup → /ws/logs liest aus SQLite
         → optionale JSONL-/stdout-Spiegel
```

Kein normales `log.event` wird ohne erfolgreichen Commit ausgeliefert.

### 3.2 Einheitliche Zuverlässigkeit

Alle erzeugten strukturierten Events folgen demselben Storevertrag. Last wird
durch die vorhandenen Erzeugungsschalter begrenzt, nicht durch eine zweite
Best-Effort-Klasse im Clientprotokoll.

### 3.3 Commit-Wakeup statt Payloadqueue

Subscriber erhalten nur die Information, dass ein neuer committed Wasserstand
vorliegen kann. Jeder `/ws/logs`-Handler liest ab seinem eigenen globalen
Scan-Cursor aus SQLite nach. Mehrere Commits dürfen zu einem Wakeup
zusammenfallen.

### 3.4 Storeausfall ist sichtbar

Bei Storeausfall:

- kein normales Liveevent,
- Storezustand `degraded`,
- bestehende Logverbindungen erhalten einen maschinenlesbaren Fehler und
  werden mit 1011 beendet,
- neue Logverbindungen werden abgewiesen,
- `hello.logAccess.available=false` mit Grund,
- Audio-/Textbetrieb auf `/ws/transcribe` bleibt erhalten,
- Recovery wird sichtbar und neue committed Events funktionieren wieder.

### 3.5 Adminprivileg bleibt getrennt vom Audio-WebSocket

`/ws/transcribe` wird nicht zu einem privilegierten Admin-WebSocket. Der
Admin-Key authentifiziert:

- HTTP-Adminaufrufe über `X-VoiceSTT-Admin-Key` beziehungsweise Bearer,
- `/ws/logs` im ersten `subscribe`-Frame als `accessToken`.

Adminprivilegien werden nicht an eine normale Transkriptionssession vererbt.

### 3.6 Admin-History und Admin-Live

Ein authentifizierter Admin kann:

- Events aller noch vorhandenen Sessions abfragen,
- den `system`-Channel und alle weiteren aktivierten Channels lesen,
- nach Channel, Eventname, Session, Transkription und Zeit filtern,
- cursorbasiert paginieren,
- serverweit replayen und anschließend live folgen.

Antworten kennzeichnen den wirksamen Scope ausdrücklich als `admin` oder
`session`, einschließlich All-Session-/All-Channel-Semantik.

### 3.7 Browser-Adminbereich

Der vorhandene Admin-Key bleibt nur im Arbeitsspeicher der Seite. Er wird nicht
in URL oder persistenten Browserspeicher geschrieben. Nach erfolgreicher
Adminauthentifizierung kann der Benutzer:

- serverweite History seitenweise laden,
- Filter und einen begrenzten Zeitraum wählen,
- danach serverweit live folgen,
- zwischen aktuellem Sessionlog und Adminlog unterscheiden.

Die Anzeige verwendet begrenzte Datenstrukturen und lädt nicht unkontrolliert
die gesamte Retention in den DOM.

### 3.8 Terminalität

Ein leerer finaler Text erzeugt genau einmal
`transcription.discarded(reason=empty_final)`, aber kein leeres Finaltextframe.

## 4. Sicherheitsvertrag

- Admin-Key und Sessiontokens nie in URLs, Events, Logs oder Fehlertexte.
- Admin-Key nicht in YAML oder Runtimepersistenz.
- Geheimnisvergleich über `secrets.compare_digest` mit normalisierten Strings.
- Fehlender/falscher Key liefert definierte 401/1008-Semantik ohne Detailleck.
- Sessiontokens bleiben auf eigene Session und erlaubte Channels begrenzt.
- Adminantworten enthalten keine internen Dateipfade oder Secrets, soweit der
  bestehende öffentliche Vertrag sie nicht ausdrücklich vorsieht.
- CORS/Browseränderungen erweitern nicht unnötig den Vertrauensbereich.

## 5. Protokollziel

`hello.logAccess` und `log.hello` veröffentlichen mindestens:

- `logProtocolVersion: 2`,
- `deliveryMode: "sqlite_first"`,
- `replayAvailable`,
- `serverInstanceId`,
- `oldestCursor`,
- `latestCursor`,
- Storeverfügbarkeit und bei Nichtverfügbarkeit einen Code.

`log.subscribed` veröffentlicht mindestens:

- `authorizationScope: "session" | "admin"`,
- wirksame Channels,
- `allChannels`,
- wirksame Session oder `null`,
- `allSessions`,
- `afterCursor`.

Cursorregeln:

- globaler Cursor; Sprünge in gefilterten Streams sind normal,
- negativer Cursor wird einheitlich abgelehnt oder normalisiert und
  dokumentiert,
- Cursor vor Retention erzeugt `log.gap(reason=retention)`,
- Cursor über dem High-Watermark erzeugt `log.error(code=cursor_ahead)`,
- Live- und Replaycursor sind ausschließlich committed Cursor.

## 6. Betroffene Produktivbereiche

Mindestens zu prüfen beziehungsweise zu ändern:

- `VoiceSTT_server/event_logging.py`
- `api_fastapi_server/server.py`
- `api_fastapi_server/static/index.html`
- `VoiceSTT_server/operations.py` bei betroffenen Fassaden
- `config.yaml` bei notwendigen Default-/Validierungsänderungen

Keine fachfremden Engine-, VAD- oder Schedulerrefactorings.

## 7. Tests

### Store und Hub

- Commit vor Live-Sichtbarkeit.
- Commitfehler: kein Publish, Cursor unverändert, Store degradiert.
- Recovery und eindeutige Cursor bei Parallelität.
- langsamer/defekter optionaler Spiegel beschädigt den Store nicht.
- High-Watermark und ältester Cursor nach Retention/Neustart.

### Logprotokoll

- leerer und mehrseitiger Replay.
- lückenloser Übergang Replay → Live.
- coalesced Wakeups.
- Disconnect während Replay und erneute Fortsetzung.
- Retention, Cursor-ahead und gefilterte globale Cursorsprünge.
- Storeausfall beendet bestehende und blockiert neue Logverbindungen.

### Authentifizierung und Scope

- korrekter Admin-Key: globale HTTP-History und globaler WS-Replay/Live.
- Admin sieht Events mehrerer Sessions einschließlich `system`.
- falscher/fehlender Admin-Key: HTTP und WS abgewiesen.
- normaler Sessiontoken sieht ausschließlich eigene Session und erlaubte
  Channels.
- Adminfilter auf einzelne Session/Channels funktioniert.
- Admin-Key und Tokens erscheinen nicht in serialisierten Events/Antwortlogs.
- Bearer- und bevorzugter Adminheader sind konsistent.

### Adminoberfläche

- Key bleibt nur im Speicher und wird korrekt an HTTP/WS gegeben.
- Historypagination, Filter, Begrenzung und Liveübergang.
- klare Trennung Session-/Adminmodus.
- Fehler, Retentiongap und Reconnect sichtbar.

### Transkription

- leerer Finaltext terminiert genau einmal mit `discarded`.
- keine Doppelterminalität bei Generation-/Disconnectrennen.
- normale Realtime-/Finalpfade bleiben unverändert.

### Gesamtprüfung

- fokussierte Tests,
- vollständige Pytest-Suite,
- `compileall`,
- lokaler Docker-Build,
- lokaler App-/Contract-Smoke ohne produktives Deployment.

## 8. Aktive Dokumentation

Mindestens abzugleichen:

- `README.md`
- `RELEASE_NOTES.md`
- `docs/structured-logging.md`
- `docs/configuration.md`
- `docs/fastapi-server.md`
- vollständiger Ordner `docs/client-development/`
- Archivregister und Soll-/Ist-Vergleich

Nach Abschluss wird `docs/client-development/` vollständig nach
`P:\DockerProjekte\voice-stt-client\server-docs-for-client-development\`
synchronisiert. Einzelne Seiten werden nicht manuell gemischt.

## 9. Nicht-Ziele

- kein Push zu GitHub,
- kein Merge nach `main`,
- kein Deployment oder Eingriff in den Livecontainer,
- keine Client-Codeänderung,
- kein neues Cookie-/Login-System,
- keine Adminprivilegien auf `/ws/transcribe`,
- keine unbegrenzte lokale Kopie aller Events im Browser,
- keine Änderung an Retention ohne ausdrückliche Konfiguration.

## 10. Abnahme und Übergabe

Die Aktion ist lokal veröffentlichungsreif, wenn:

1. alle Planpunkte umgesetzt oder als materielle Abweichung dokumentiert sind,
2. fokussierte und vollständige Tests grün sind,
3. `compileall`, Build und lokale Smokes grün sind,
4. aktive Serverdokumentation dem Code entspricht,
5. Clientkopie der Serverdocs identisch synchronisiert ist,
6. Soll-/Ist-Vergleich und gegebenenfalls Abweichungsdatei vorliegen,
7. Arbeitsbaum und Branch eindeutig berichtet werden,
8. keinerlei Push, Merge oder Deployment erfolgt ist.
