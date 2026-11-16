# V1 zu V2 Client-Migrationsmatrix

**Stand:** korrigiert am 2026-09-28 (Baseline `f7d2b3ccd07757172a45b371829b04bcedffab4b`).
Belege: [`../v2-client-contract-review/FACT_REVIEW_MATRIX.md`](../v2-client-contract-review/FACT_REVIEW_MATRIX.md) (`MIG-*`).

Gegenüberstellung für Entwickler eines Clients, der bisher das Legacy-V1-
Protokoll (`/ws/transcribe`) nutzt. Der vollständige V2-Vertrag steht in
[`docs/client-development/`](../../client-development/README.md), der V1-Vertrag
(nur zur Wartung) in
[`docs/client-development/legacy-v1/`](../../client-development/legacy-v1/README.md).

---

## Migrationsmatrix

| Konzept | Legacy V1 (`/ws/transcribe`) | V2 (`/ws/v2`) | Art | Client-Änderung |
| --- | --- | --- | --- | --- |
| **Endpoint** | `/ws/transcribe` | `/ws/v2` | geändert | URL umstellen. V1 bleibt als Kompatibilitätspfad bestehen. |
| **Sessionkonfiguration** | Queryparameter (`manualTriggerEnabled`, `wakeWordTriggerEnabled`, `wakeWordEnabled`, `wakeWords`, Timings …) | `hello.requestedSession` + `hello.runtimeSuppression`; Timings per `session_settings.patch` | **Breaking** | Queryparameter entfallen (nur `clientId` wird noch gelesen). |
| **Handshake** | Server sendet unaufgefordert `hello`, danach `ready`. | Client sendet `hello`; Server antwortet `hello.accepted` (mit Snapshot), `protocol.incompatible` (4406) oder `session.rejected` (4409). Kein `ready`. | **Breaking** | `hello` binnen 10 s senden (sonst 4408). |
| **Admission-Fehler** | `error` (`where=session_config`/`admission`) + Close 1008/1013 | `session.rejected` + Close 4409 | geändert | Neue Fehlerbehandlung. |
| **IDs** | kompakte 32-Hex-`sessionId`/`activationId`, Integer-`segmentId`, freie `commandId` | kanonische UUIDs für alle IDs; `segmentSequence`/`activationSequence` als Zahlen | **Breaking** | Formate anpassen; V1-IDs sind auf V2 `invalid_payload`. |
| **Audiostart** | `{"type":"start"}` Pflicht vor Audio; `stop` beendet den Stream | Audiopfad öffnet mit `hello.accepted`; kein `start`/`stop` | **Breaking** | `start`/`stop` entfallen. |
| **Activation starten** | `{"type":"trigger","action":"activate","source":"manual","commandId":"…"}` | `{"type":"activation.command","protocolVersion":2,"sessionId":"…","commandId":"<uuid>","action":"activate","source":"manual"}` | geändert | V2-Envelope. |
| **Activation beenden (PTT loslassen)** | `trigger` mit `action:"finish"` | `activation.command` `action:"finish"` + `activationId`, **ohne** `source` | geändert | V2 verbietet `source` bei Controls. |
| **Frist verlängern** | `trigger` mit `action:"refresh"` (`extend` ist auch auf V1 entfernt) | `activation.command` `action:"refresh"` + `activationId` | geändert | – |
| **Abbrechen** | `trigger` mit `action:"cancel"`; zusätzlich `clear` (setzt Turn, Segmente und Timeline zurück) | `activation.command` `action:"cancel"` + `activationId`; kein `clear` | geändert | `clear`-Nutzung ersetzen. |
| **Ping / Metrics** | `ping` → `pong`, `metrics` → `metrics` | nicht vorhanden (unbekannte Typen werden ignoriert) | entfallen | Transport-Keepalive der WS-Bibliothek nutzen; Metriken per HTTP. |
| **Audioverfügbarkeit** | `{"type":"audio_availability","audioAvailable":…,"commandId":…}` → `audio_availability_ack` | `audio_availability.set` → `command.ack` | geändert | – |
| **Trigger-Suppression** | nicht vorhanden | `trigger_suppression.set` | neu | – |
| **Acks** | `trigger_ack`, `audio_availability_ack` (`accepted`, `reason`) | `command.ack` mit 15 Result-Codes, `stateVersion`, `settingsRevision` | **Breaking** | Result-Codes auswerten. |
| **Server-Events** | `status`, `realtime`, `final`, `timeline` (Untertypen), `warning`, `error` | 17 punktgetrennte Events mit `eventId`/`eventSeq`/`stateVersion` | **Breaking** | Neuer Reducer. |
| **Zwischentext** | `realtime` (revidierbar) | **nicht vorhanden** | entfallen | Nur `transcription.completed` anzeigen. |
| **Ordnung / Resync** | keine Sequenz | `eventSeq`, `session.snapshot.request` → `session.snapshot` | neu | Gap-Detection + Resync. |
| **Audio-Framing** | `uint32` LE Metadatenlänge + UTF-8-JSON + PCM `pcm_s16le` | identisch | unverändert | Fehlerhafte Frames: V1 `error(where=audio_packet)`, V2 still verworfen. |
| **Session-Settings** | keine Session-Patches; `PATCH /api/config` ist Admin-Serverkonfiguration | `session_settings.patch` mit `baseSettingsRevision` | neu | Optimistische Revision. |
| **Wake Words** | `wakeWords`-Queryparameter, tolerant (Aliase/Anzeigenamen) | nur kanonische IDs in `requestedSession.wakeWordIds`; Katalog `GET /api/v2/wake-words` | verschärft | IDs clientseitig auflösen. |
| **Log-Zugriff** | `hello.logAccess`-Sessiontoken für `/ws/logs`, `/api/logs/*` | kein `logAccess`; nur Admin-Key | eingeschränkt | – |
