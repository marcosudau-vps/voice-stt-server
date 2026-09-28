# Auswirkungen auf die Repository-Dokumentation (Phase B)

**Datum:** 2026-09-28 · Basis: verifizierter Vertrag aus
[`INDEPENDENT_REVIEW.md`](INDEPENDENT_REVIEW.md).

## 1. Ergebnis

* **Kanonischer Einstieg für V2:** [`docs/client-development/README.md`](../../client-development/README.md).
  Normative Seiten: `02` (Wire), `03` (Events), `05` (Snapshot/Resync).
* **Legacy V1** getrennt unter [`docs/client-development/legacy-v1/`](../../client-development/legacy-v1/README.md), jede Seite mit Banner „Legacy V1 – nicht für neue Clients“ und Link auf V2.
* **Audit** (`docs/audits/v2-client-contract/`) = belegte Momentaufnahme; verweist auf die kanonische Doku.
* **Architektur** (`docs/einheitliche-triggerarchitektur.md` §12) = Servermodell hinter dem Protokoll; verweist für Felder und Beispiele auf die Client-Doku.

## 2. Veraltete Dateien und Änderungen

| Datei | Befund vorher | Änderung |
| --- | --- | --- |
| `docs/client-development/README.md` | Primärschnittstelle `/ws/transcribe`, Regeln „`ready` abwarten“, „`start` senden“, Queryparameter | Neu als V2-Einstieg: Paketübersicht, Minimalablauf, 10 Regeln, Codequellen, Legacy-Hinweis |
| `…/02-websocket-protokoll.md` | V1-Protokoll | **V1-Inhalt verschoben** nach `legacy-v1/v1-websocket-protokoll.md`; neu: V2-Wire (Handshake, IDs, Commands, Acks, Replay, stille Verwerfungen, Audioframe, Close-Codes) |
| `…/03-server-events-kurzreferenz.md` | V1-Events | **verschoben** nach `legacy-v1/v1-server-events-kurzreferenz.md`; neu: V2-Nachrichten, Hülle, 17 Events, TypeScript-Union |
| `…/04-server-events-katalog-und-chronologie.md` | V1-Chronologie | **verschoben** nach `legacy-v1/v1-server-events-katalog-und-chronologie.md`; neu: Phasen, Fristen, Segmentlebenszyklus, Reihenfolge-Garantien, Traces, Trigger |
| `…/05-client-zustandsmodell.md` | V1-Reducer (Realtime/Final, start/stop/clear) | **verschoben** nach `legacy-v1/v1-client-zustandsmodell.md`; neu: Snapshot, Reducer mit Lückenpuffer, Reconnect |
| `…/09-betriebsmodi-und-serverkonfiguration.md` | V1-Queryparameter, Legacy-Modus | **verschoben** nach `legacy-v1/v1-triggerquellen-und-queryparameter.md`; neu: Triggerquellen, Katalog, Admission, Session-Settings |
| `…/01-session-und-server-scope.md` | Lebenszyklus mit `start`/`stop`/`clear`, „Settings in `hello`“ | V2-Lebenszyklus; V1-Befehle als Legacy markiert; Abschnitt Session-Settings |
| `…/06-http-api-und-authentifizierung.md` | „Live-Client benötigt `/ws/transcribe`“; Logtoken ohne V2-Hinweis; Link auf entfallenen Anchor | `/ws/v2` als Live-Schnittstelle, `/ws/transcribe` als Legacy; V2 ohne `logAccess`; `ready` → `/health`; Links angepasst |
| `…/07-robustheit-grenzen-und-sicherheit.md` | Limits/Fehler/Checkliste V1 (`1013`, `warning`, `start`) | V2-Limits, Fehlerstrategie, Timeouts, Race Conditions, V2-Checkliste, V2-Referenztests; Datenschutz/Secrets übernommen |
| `…/08-protokollabgrenzung.md` | `/ws/transcribe` als „primäre Transkriptionsschnittstelle“, Produktionshost-URL auf V1 | V2 aktuell, V1 Legacy, Vergleichstabelle, Zwei-Port-Server, `/ws/logs` |
| `docs/client-development/legacy-v1/README.md` | – | neu: Zweck, Umfang, Seitenindex |
| `docs/audits/v2-client-contract/*` (4 Dateien) | siehe [`AUDIT_CORRECTIONS.md`](AUDIT_CORRECTIONS.md) | korrigiert |
| `docs/einheitliche-triggerarchitektur.md` | §0: v2 lehne `session_settings.patch` ab; §12.5: Zustellreihenfolge „kann abweichen“, Tabelle ohne 3 Events; §12.7 ohne `requestedSettings`; §6–9 V1 ohne Kennzeichnung | §0 berichtigt; §12 Link auf Client-Doku; gültiges `hello`-Beispiel (§12.2); Linearisierung; fehlende Events + „keine Realtime-Texte“; `requestedSettings`; 10-s-Timeout; §6–9 als Legacy V1/Observability markiert |
| `docs/fastapi-server.md` | V2-Abschnitt: `hello.accepted` mit `supportedProtocolVersions`; Reconnect fordert Snapshot an; Logtoken ohne V2-Hinweis | berichtigt (Felder, Close-Codes, Audioformat, Reconnect, keine Realtime-Texte, Log-Zugriff, V2-Admission-Limit) |
| `docs/structured-logging.md` | Logtoken aus „dem“ `hello` | als V1 gekennzeichnet; V2 nur Admin-Key |
| `docs/wake-words.md` | Legacy-Abschnitt verlinkte „vollständigen Vertrag“ auf die nun V2-Seite `09`; defekter Anchor `#models-json-is-the-authority` | Link auf Legacy-Seite + V2-Seite; Anchor repariert |
| `docs/module-map.md` | „the deprecated `extend` alias“ | als entfernt beschrieben |
| `docs/README.md` | „`trigger`/`trigger_ack`-Vertrag“ als aktueller Stand; Cliententwicklung ohne V1/V2-Trennung | V2 als aktueller Vertrag, Legacy-Verweis, Audit-Links |
| `README.md` | ok, aber kein Hinweis auf Legacy-Trennung | kanonischer Einstieg + Legacy-Hinweis |
| `api_fastapi_server/README.md` | Abschnitt „Protocol“ beschreibt unmarkiert V1 | als Legacy V1 markiert, V2-Verweis, Audioformat präzisiert |
| `VoiceSTT_server/README.md` | nur `/ws/transcribe` | `/ws/v2` ergänzt, V1 als Legacy |

Keine Datei wurde gelöscht; die fünf V1-Seiten wurden verschoben.

## 3. Bewusst unverändert

| Fundstelle | Einordnung |
| --- | --- |
| `docs/.archiv/**` | Historie; laut `AGENTS.md` nicht umzuschreiben |
| `RELEASE_NOTES.md` | historische Releasebeschreibung (V1-Wake-Word-Vertrag in 1.0.0) |
| `api_fastapi_server/static/index.html`, `app_browserclient/client.js` | V1-Kompatibilitätsimplementierung (Browserclient) |
| `tools/validate_parallel_realtime.py`, `tools/verify_session_wakeword.ps1` | V1-Diagnosewerkzeuge |
| `tests/**` | Testfixtures für V1 und V2 |
| `api_fastapi_server/server.py`, `activation_commands.py` | Produktcode (inkl. veraltetem Docstring, Befund `IMPL-04`) |
| `build/vps/VOICE_STT_SERVER_RELEASE_ANLEITUNG.md` | `ready` bezieht sich auf das `/health`-Feld, nicht auf die V1-Nachricht |
| `docs/configuration.md` | verweist bereits auf kanonische IDs im `hello` |

## 4. Abschließende Konsistenzsuche

Suche über alle gepflegten Dateien (ohne `docs/.archiv/`) nach `/ws/transcribe`,
`"type": "start"`, `trigger_ack`, `extend`, `ready`, `activationConfig`,
`manualTriggerEnabled`, `VSTT`, `0x56535454`, `api/v2/health`,
`hello.logAccess`. Jedes verbleibende Vorkommen ist einer der Klassen
*Legacy V1 (markiert)*, *Historie*, *Kompatibilitätsimplementierung*,
*Testfixture* oder *Korrekturbericht (zitierter Fehler)* zugeordnet; es
verbleibt keine unmarkierte V1-Anleitung in aktueller Dokumentation.
