# Abgrenzung der Serverprotokolle

[← Robustheit & Sicherheit](07-robustheit-grenzen-und-sicherheit.md) · [Triggerquellen, Wake Words & Settings →](09-betriebsmodi-und-serverkonfiguration.md) · [Übersicht](README.md)

## Entscheidung für neue Clients

**Neue Clients implementieren Protokoll V2 auf `/ws/v2`.**

```text
VoiceSTT_server.server  ──re-exportiert──►  api_fastapi_server.server
                                               │
                     ┌─────────────────────────┼──────────────────────────┐
                     ▼                         ▼                          ▼
             WS /ws/v2 (V2, aktuell)   WS /ws/transcribe (Legacy V1)   WS /ws/logs (Logstream)
```

Alle drei Endpunkte liegen auf demselben HTTP-/HTTPS-Port.

| Endpunkt | Status | Zweck | Dokumentation |
| --- | --- | --- | --- |
| `/ws/v2` | **aktuell** | Audio + Steuerung für neue Clients (Desktop-Client V2) | diese Dokumentation |
| `/ws/transcribe` | **Legacy V1**, dauerhaft als Kompatibilitätspfad betrieben | integrierter Browserclient, bestehende Clients, Diagnose-Tools | [legacy-v1/](legacy-v1/README.md) |
| `/ws/logs` | unabhängig vom Audioprotokoll | replaybarer, SQLite-basierter Eventstream | [06 – Log-Zugriff](06-http-api-und-authentifizierung.md#strukturierter-logzugriff), [`docs/structured-logging.md`](../structured-logging.md) |

## V2 und V1 im Vergleich

| Merkmal | V2 `/ws/v2` | Legacy V1 `/ws/transcribe` |
| --- | --- | --- |
| Erste Nachricht | Client `hello` | Server `hello`, dann `ready` |
| Sessionkonfiguration | im `hello` | Queryparameter |
| Audiostart | implizit mit `hello.accepted` | `{"type":"start"}` |
| Activation-Steuerung | `activation.command` (`activate`/`refresh`/`finish`/`cancel`) | `trigger` (gleiche Aktionen) |
| Antworten | `command.ack` mit 15 Result-Codes | `trigger_ack`, `audio_availability_ack` |
| Events | 17 Typen, `eventSeq`, `stateVersion` | `status`, `realtime`, `final`, `timeline`, … |
| Zwischentext | keiner | `realtime` |
| Resync | `session.snapshot` | – |
| IDs | kanonische UUIDs | kompakte Hex-IDs, Integer-`segmentId` |
| Audioframe | Längenpräfix + JSON + PCM | identisch |
| Session-Settings | `session_settings.patch` | – |
| Log-Token | – | `hello.logAccess` |

Die beiden Protokolle teilen alle Serverautoritäten (Activation-Controller,
Segmentledger, Recorder, Scheduler), sind aber strikt getrennt: Ein V2-Client
erhält nie eine V1-Nachricht, V2-Commands sind auf V1 unbekannt und umgekehrt,
und es gibt keinen Fallback innerhalb einer Verbindung. Belegt durch
`tests/unit/test_protocol_v1_v2_boundary.py`.

Migrationsdetails: [V1 → V2 Migrationsmatrix](../audits/v2-client-contract/V1_TO_V2_CLIENT_MIGRATION_MATRIX.md).

## Separate Zwei-Port-Implementierung

`VoiceSTT_server/stt_server.py` ist eine davon unabhängige
WebSocket-Serverimplementierung (Control-Port 8011, Data-Port 8012, Befehle
`set_parameter`/`get_parameter`/`call_method`, Recorder-Callbacks wie
`fullSentence`). Sie ist mit keinem der FastAPI-Protokolle kompatibel, hat
keine HTTP-API und ist nicht Gegenstand dieser Dokumentation. Erkennung: Ein
FastAPI-Server antwortet auf `/ws/v2` erst nach dem Client-`hello`; die
Zwei-Port-Implementierung hat keinen solchen Pfad.

## Keine automatische Aushandlung zwischen Endpunkten

Ein Client wählt den Endpunkt explizit. Die Versionsaushandlung von V2
(`supportedProtocolVersions`) gilt nur innerhalb von `/ws/v2`; ein Server, der
V2 nicht kennt, beantwortet `/ws/v2` nicht als WebSocket.
