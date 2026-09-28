# V1 zu V2 Client Migrationsmatrix

Dieses Dokument bietet Entwicklern eines bestehenden Desktop-Clients, der bisher das V1-Protokoll (`/ws/transcribe`) verwendet hat, eine exakte technische Gegenüberstellung für die Migration auf das V2-Protokoll (`/ws/v2`).

---

## Migrationsmatrix

| V1-Konzept | V1-Vertrag (`/ws/transcribe`) | V2-Entsprechung (`/ws/v2`) | Art der Änderung | Konkrete Client-Änderung | Kompatibilitätshinweis |
| --- | --- | --- | --- | --- | --- |
| **Endpoint URL** | `/ws/transcribe` | `/ws/v2` | Geändert | WebSocket-Verbindungs-URL auf `/ws/v2` umstellen | V1 bleibt als Abwärtskompatibilitätspfad auf `/ws/transcribe` bestehen, V2 ist der neue Zielvertrag. |
| **Handshake** | Nach WS-Connect unaufgefordert `hello` oder `ready` vom Server. | Client **muss** zuerst Textnachricht `hello` senden. | **Breaking Change** | Client muss aktiv `hello` senden und auf `hello.accepted` warten. | Sendet der Client nicht innerhalb von 10s `hello`, schließt der Server mit Close `4408`. |
| **Session ID** | `sessionId` (String) | `sessionId` (Kanonische UUIDv4) | Format verschärft | Formatprüfungen anpassen (36 Chars, Hyphens). | V2 akzeptiert keine kompakten 32-Char Hex-Strings. |
| **Command Envelope** | Freie JSON-Befehle (`start`, `stop`, `clear`) | Strict Envelope mit `protocolVersion: 2`, `sessionId`, `commandId` | **Breaking Change** | Jeden Command in das V2-Envelope verpacken + frische `commandId` generieren. | Commands ohne valide `commandId` erhalten kein Ack. |
| **Manual Start/PTT** | `{"type": "start"}` oder `{"type": "trigger", "action": "start"}` | `{"type": "activation.command", "action": "activate", "source": "manual"}` | Geändert | Nachrichtenformat anpassen. | `source="wake_word"` darf vom Client NIEMALS gesendet werden. |
| **Manual Stop/PTT Release** | `{"type": "stop"}` oder `{"type": "trigger", "action": "stop"}` | `{"type": "activation.command", "action": "finish", "activationId": "..."}` | Geändert | Nachrichtenformat anpassen, `activationId` mitsenden. | `action="finish"` erfordert die `activationId` der laufenden Activation. |
| **Verlängerung/Extend** | `{"type": "trigger", "action": "extend"}` | `{"type": "activation.command", "action": "refresh", "activationId": "..."}` | Umbenannt | Alias `extend` durch `refresh` ersetzen. | `extend` wird auf V2 als `invalid_payload` abgelehnt! |
| **Abbruch/Cancel** | `{"type": "clear"}` | `{"type": "activation.command", "action": "cancel", "activationId": "..."}` | Geändert | `action="cancel"` mit `activationId` senden. | `clear` existiert auf V2 nicht mehr. |
| **Command Ack** | `trigger_ack` / `status` | `command.ack` mit schlossenem Result-Code Set | Geändert | Auf `command.ack` hören und `accepted: true/false` sowie `result` auswerten. | Exactly-once Replay-Semantik per `commandId`. |
| **Server Events** | Heterogene Events (`realtime_transcript`, `final_transcript`, `status`) | Strukturierte, punktgetrennte Events (`activation.started`, `transcription.completed` etc.) | **Breaking Change** | Event-Handler auf V2-Eventnamen umstellen. | Jedes Event enthält `eventSeq` und `stateVersion`. |
| **Event Sequence & Ordering** | Keine globale Sequenznummer | `eventSeq` (1, 2, 3...) und `stateVersion` | **Neu in V2** | In-Order Event-Queue und Gap-Detection implementieren. | Bei Lücke `session.snapshot.request` senden. |
| **Resynchronisierung** | Nicht vorhanden | `session.snapshot.request` -> `session.snapshot` | **Neu in V2** | Snapshot-Resync-Logik implementieren. | Autoritatives Serverbild ersetzt lokalen Mirror. |
| **Audio Framing** | Binary Frames mit 8-Byte VSTT Header + PCM 16kHz | Identisch (8-Byte VSTT Header + PCM 16kHz) | Unverändert | Der binäre Audio-Transport ist auf V1 und V2 identisch. | Audio erst nach `hello.accepted` senden! |
| **Settings Patch** | `config` / `/api/config` | `session_settings.patch` mit `baseSettingsRevision` | Geändert | Optimistisches Patching mit Revisionszählung implementieren. | Bei Konflikt `settings_revision_conflict` verarbeiten. |
| **Wake Words** | Teils Freitext / Aliase | Kanonische IDs über `requestedSession.wakeWordIds` | Verschärft | Nur kanonische IDs senden, Katalog via `GET /api/v2/wake-words` beziehen. | Ungültige IDs führen zu `session.rejected`. |
| **Audio Availability** | Nicht explizit im Protokoll | `audio_availability.set` Command | **Neu in V2** | Mikrofon-Status explizit an Server melden. | |
