# Legacy V1 – Protokoll `/ws/transcribe`

> **Nicht für neue Clients.** Das aktuelle Protokoll ist **V2 auf `/ws/v2`**.
> Einstieg: [**V2-Client-Dokumentation**](../README.md).
> Migration: [V1 → V2 Migrationsmatrix](../../audits/v2-client-contract/V1_TO_V2_CLIENT_MIGRATION_MATRIX.md).

## Warum diese Seiten noch existieren

Der Server betreibt `/ws/transcribe` weiterhin als erforderlichen
Kompatibilitätspfad (AP-SRV-070: `KEEP_REQUIRED`). Ihn nutzen der integrierte
Browserclient (`api_fastapi_server/static/index.html`,
`app_browserclient/client.js`), Diagnose-Skripte unter `tools/` und bestehende
Clients. Wer diese Clients wartet, braucht die V1-Beschreibung; für alles
andere gilt V2.

Die Seiten wurden unverändert aus `docs/client-development/` hierher
verschoben (Stand vor der V2-Umstellung, 2. August 2026 mit späteren
Ergänzungen) und nur mit diesem Legacy-Rahmen versehen. Sie waren nicht
Gegenstand der V2-Vertragsprüfung vom 2026-09-28; bestätigt wurde dabei nur,
dass V1 weiterhin `hello`/`ready` serverseitig sendet, `start`/`stop`/`clear`/
`ping`/`metrics`/`trigger`/`audio_availability` versteht, `extend` mit
`invalid_action` ablehnt und dasselbe Audioformat wie V2 verwendet.

## Seiten

| Seite | Inhalt |
| --- | --- |
| [V1 WebSocket-Protokoll](v1-websocket-protokoll.md) | Queryparameter-Admission, Server-`hello`/`ready`, `start`/`stop`/`clear`, `trigger`/`trigger_ack`, Audioformat, `/ws/logs` mit Sessiontoken |
| [V1 Event-Kurzreferenz](v1-server-events-kurzreferenz.md) | `status`, `realtime`, `final`, `timeline`, `warning`, `error`, … |
| [V1 Event-Katalog & Chronologie](v1-server-events-katalog-und-chronologie.md) | Semantik und Abläufe der V1-Events |
| [V1 Client-Zustandsmodell](v1-client-zustandsmodell.md) | Reducer für Realtime/Final, Start/Stop/Clear, Reconnect |
| [V1 Triggerquellen & Queryparameter](v1-triggerquellen-und-queryparameter.md) | `manualTriggerEnabled`, `wakeWordTriggerEnabled`, `wakeWordEnabled`, Legacy-Modus |

Protokollneutrale Themen (HTTP-API, Server-Scope, Limits, Logging) stehen in
der gemeinsamen Dokumentation eine Ebene höher.
