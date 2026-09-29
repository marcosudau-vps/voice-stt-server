# VoiceSTT V2 Desktop Client Technical Contract Reference

**Document Version:** 1.1.0 (korrigiert durch die unabhängige Prüfung vom 2026-09-28)
**Geprüfte Basis:** `feat/einheitliche-triggerarchitektur-distributed`
**Geprüfter Baseline-SHA:** `f7d2b3ccd07757172a45b371829b04bcedffab4b`
**Tree-SHA:** `731c22d872ab3a3897886bcd6bec582e8332be75`
**Status:** Audit-Momentaufnahme dieses SHA, rekonstruiert aus Code, Tests,
Vertragsvektoren und Wire-Traces. Korrekturen der Erstfassung
(`cc7d4996`) sind in
[`../v2-client-contract-review/AUDIT_CORRECTIONS.md`](../v2-client-contract-review/AUDIT_CORRECTIONS.md)
belegt.

> **Kanonische, gepflegte V2-Dokumentation:**
> [`docs/client-development/`](../../client-development/README.md). Dieses
> Dokument ist der auditierte Stand eines bestimmten Commits. Weicht es später
> von der Client-Dokumentation ab, gilt die Client-Dokumentation für den
> jeweils aktuellen Code.

---

## Inhaltsverzeichnis

1. [Verbindung und Handshake](#1-verbindung-und-handshake)
2. [Identitäten](#2-identitäten)
3. [Client → Server Commands](#3-client--server-commands)
4. [Command Acknowledgements](#4-command-acknowledgements-commandack)
5. [Server → Client Events](#5-server--client-events)
6. [Event-Hülle, Reihenfolge, Deduplizierung](#6-event-hülle-reihenfolge-deduplizierung)
7. [Zustandsmodell](#7-zustandsmodell)
8. [Snapshot und Resynchronisierung](#8-snapshot-und-resynchronisierung)
9. [Audio-Transport](#9-audio-transport)
10. [Transkriptionslebenszyklus und Beispielabläufe](#10-transkriptionslebenszyklus-und-beispielabläufe)
11. [Settings-Control-Plane](#11-settings-control-plane)
12. [Triggervertrag](#12-triggervertrag)
13. [Wake Words](#13-wake-words)
14. [HTTP-APIs](#14-http-apis)
15. [Authentifizierung](#15-authentifizierung)
16. [Reconnect](#16-reconnect)
17. [Close-Codes und stille Verwerfungen](#17-close-codes-und-stille-verwerfungen)
18. [Implementierungsregeln](#18-implementierungsregeln)
19. [Golden Examples](#19-golden-examples)
20. [Nachschlagetabellen](#20-nachschlagetabellen)
21. [Compliance-Checkliste](#21-compliance-checkliste)

---

## 1. Verbindung und Handshake

### 1.1 Endpoint

* **Pfad:** `/ws/v2` auf dem HTTP-Port des FastAPI-Servers (`ws://` oder `wss://`).
* **Frames:** Text = ein JSON-Objekt; Binär = Audio (Client → Server). Der Server sendet nur Textframes.
* **Optionale Korrelation:** `?clientId=…` oder Header `X-VoiceSTT-Client-Id` (siehe §2).
* **Handshake-Timeout:** `DEFAULT_HANDSHAKE_TIMEOUT_SECONDS = 10.0`. Bis zur Annahme wartet jede Empfangsoperation höchstens 10 s; danach Close `4408` ohne Nachricht.
* **Vor dem Handshake** existiert keine Session (keine `sessionId`, kein Recorder). Ein Binärframe vor `hello.accepted` → Close `4400` ohne Nachricht.

### 1.2 Client-`hello`

```json
{
  "type": "hello",
  "supportedProtocolVersions": [2],
  "clientVersion": "2.0.0-desktop",
  "clientCommit": "a1b2c3d4",
  "clientRunId": "10000000-0000-4000-8000-000000000001",
  "requestedSession": {
    "trigger": {"manual": true, "wakeWord": true},
    "wakeWordIds": ["hey_jarvis"]
  },
  "runtimeSuppression": {"manual": false, "wakeWord": false}
}
```

Validierung in dieser Reihenfolge (`protocol_v2/handshake.py:parse_hello`):

| Feld | Regel | Verstoß |
| --- | --- | --- |
| `type` | exakt `"hello"`; JSON-Objekt | Close `4400` |
| `supportedProtocolVersions` | nicht leere Liste von Ganzzahlen (keine Bools) | Close `4400` |
| `clientVersion`, `clientCommit` | nicht leere Strings (nicht nur Leerraum) | Close `4400` |
| `clientRunId` | kanonische UUID: 36 Zeichen, klein, mit Bindestrichen. **Version wird nicht geprüft**; UUIDv4 empfohlen | Close `4400` |
| `requestedSession.trigger.manual`/`.wakeWord` | Bool | Close `4400` |
| `requestedSession.wakeWordIds` | Liste nicht leerer Strings (darf leer sein) | Close `4400` |
| `runtimeSuppression.manual`/`.wakeWord` | Bool | Close `4400` |
| gemeinsame Version | `2` muss enthalten sein | `protocol.incompatible` + Close `4406` |
| Sessionadmission | siehe 1.3 C | `session.rejected` + Close `4409` |

### 1.3 Server-Antworten

#### A. `hello.accepted`

`snapshot` ist ein vollständiger `session.snapshot` ohne inneres `type`
(Aufbau §8). Die Settings-Maps sind hier gekürzt; sie enthalten immer alle
16 Session-Schlüssel (§11).

```json
{
  "type": "hello.accepted",
  "protocolVersion": 2,
  "sessionId": "20000000-0000-4000-8000-000000000001",
  "serverVersion": "2.0.0",
  "serverCommit": "unknown",
  "snapshot": {
    "protocolVersion": 2,
    "serverVersion": "2.0.0",
    "serverCommit": "unknown",
    "sessionId": "20000000-0000-4000-8000-000000000001",
    "stateVersion": 0,
    "lastEventSeq": 0,
    "settingsRevision": 0,
    "input": {
      "phase": "idle",
      "activationId": null,
      "primarySource": null,
      "deadlineAtUnixMs": null,
      "remainingMs": null,
      "closeRequested": false
    },
    "pendingActivations": [],
    "trigger": {
      "configured": {"manual": true, "wakeWord": true},
      "suppressed": {"manual": false, "wakeWord": false},
      "effective": {"manual": true, "wakeWord": true}
    },
    "audioAvailable": true,
    "requestedSettings": {
      "activation.closingRecoveryTimeoutMs": 5000,
      "activation.followupTimeoutMs": 3000,
      "activation.initialSpeechTimeoutMs": 15000,
      "activation.segmentWatchdogInitialMs": 600000,
      "activation.segmentWatchdogRefreshMs": 180000,
      "activation.segmentWatchdogWarningMs": 30000,
      "runtimeSuppression.manual": false,
      "runtimeSuppression.wakeWord": false,
      "wakeWord.cooldownMs": 0,
      "wakeWord.detectorGain": 1.0,
      "wakeWord.minConsecutivePredictionFrames": 1,
      "wakeWord.noiseSuppressionEnabled": false,
      "wakeWord.preRollMs": 0,
      "wakeWord.selection": ["hey_jarvis"],
      "wakeWord.sensitivity": 0.5,
      "wakeWord.vadThreshold": 0.0
    },
    "effectiveSettings": {"…": "gleiche 16 Schlüssel"},
    "wakeWordCapabilities": {
      "catalogRevision": 1,
      "availableWakeWordIds": ["alexa", "hey_jarvis"]
    }
  }
}
```

`serverVersion` stammt aus `VoiceSTT._version`; `serverCommit` aus
`VOICESTT_SERVER_COMMIT`, sonst `"unknown"`.

#### B. `protocol.incompatible` (Close `4406`)

```json
{
  "type": "protocol.incompatible",
  "reason": "no_common_protocol_version",
  "serverVersion": "2.0.0",
  "serverCommit": "unknown",
  "supportedProtocolVersions": [2]
}
```

Wird nur gesendet, wenn das `hello` sonst vollständig gültig ist.

#### C. `session.rejected` (Close `4409`)

```json
{
  "type": "session.rejected",
  "reason": "invalid_requested_session",
  "serverVersion": "2.0.0",
  "serverCommit": "unknown",
  "supportedProtocolVersions": [2],
  "errors": [
    {
      "field": "requestedSession.wakeWordIds",
      "code": "wake_word_unavailable",
      "message": "'Hey Jarvis' ist keine kanonische Wake-Word-ID.",
      "reason": "not_canonical",
      "wakeWordId": "Hey Jarvis"
    }
  ]
}
```

| Top-`reason` | `errors[].code` | Ursache |
| --- | --- | --- |
| `invalid_requested_session` | `activation_trigger_required` | beide Trigger `false` |
| `invalid_requested_session` | `wake_word_selection_required` | Wake Word an, `wakeWordIds` leer |
| `invalid_requested_session` | `wake_word_selection_not_allowed` | Wake Word aus, `wakeWordIds` nicht leer |
| `invalid_requested_session` | `wake_word_unavailable` + `reason` (`not_canonical`, `unknown`, `globally_disabled`, `artifact_missing`, `artifact_integrity_mismatch`, `artifact_unloadable`, `pipeline_unavailable`, `runtime_unavailable`, `catalog_unavailable`, `no_common_backend`, `backend_unavailable`) + `wakeWordId` | Katalogadmission |
| `invalid_requested_session` | Code der `SessionConfigurationError` | Sessionaufbau verweigert |
| `session_limit_reached` | `session_limit_reached` | `max_sessions` erreicht |

#### D. Ungültiges `hello` / Nicht-JSON

Keine Nachricht, Close `4400`. Ein unerwarteter Fehler beim Sessionaufbau:
keine Nachricht, Close `1011`.

---

## 2. Identitäten

| ID | Erzeuger | Format | Scope / Lebensdauer | Reconnect |
| --- | --- | --- | --- | --- |
| `clientRunId` | Client | kanonische UUID (v4 empfohlen) | Client-Prozesslauf (Konvention) | Server prüft nur die Syntax; keine Wiederaufnahme |
| `clientId` | Client (optional) / Server | 1–128 Zeichen `[A-Za-z0-9._:-]`, sonst `client-<32 hex>` | nur Transport-/Auditmetadatum; erscheint in keiner V2-Nachricht | frei wählbar |
| `sessionId` | Server | kanonische UUID (uuid4) | eine `/ws/v2`-Verbindung | jede Verbindung neu |
| `commandId` | Client | kanonische UUID | Replay-Schlüssel innerhalb der Session | Cache verfällt mit der Session |
| `activationId` | Server | kanonische UUID (uuid4) | eine Activation, bis zu ihrem Terminal | verfällt |
| `activationSequence` | Server | Ganzzahl ≥ 1 | pro Session monoton | beginnt neu |
| `segmentId` | Server | kanonische UUID (uuid4) | ein Sprachsegment | verfällt |
| `segmentSequence` | Server | Ganzzahl ≥ 1 | pro Session monoton | beginnt neu |
| `eventId` | Server | kanonische UUID (uuid4) | ein logisches Event (Retry = gleiche ID) | – |
| `eventSeq` | Server | Ganzzahl ≥ 1, lückenlos | pro Session | beginnt bei 1 |

Kanonisch heißt: `str(uuid.UUID(value)) == value`. Großbuchstaben, 32-Hex
ohne Bindestriche, Klammern oder Leerraum sind ungültig.

---

## 3. Client → Server Commands

Gemeinsame Pflichtfelder: `type`, `protocolVersion` (exakt Ganzzahl `2`),
`sessionId` (die eigene), `commandId` (kanonische UUID).

Prüfreihenfolge (`protocol_v2/commands.py:parse_command`):

1. Kein JSON-Objekt, nicht parsebar oder unbekannter `type` → **ignoriert** (kein Ack).
2. `commandId` fehlt oder nicht kanonisch → **ignoriert** (kein Ack).
3. `protocolVersion` ≠ `2` oder `sessionId` nicht kanonisch → `invalid_payload`.
4. `sessionId` wohlgeformt, aber fremd → `stale_session`.
5. Typspezifische Felder falsch → `invalid_payload`.

Unbekannte Zusatzfelder werden ansonsten toleriert.

### 3.1 `activation.command`

| `action` | Pflicht | Verboten |
| --- | --- | --- |
| `activate` | `source: "manual"` | Schlüssel `activationId` (auch `null`) |
| `refresh`, `finish`, `cancel` | `activationId` (kanonische UUID) | Schlüssel `source` (auch `null`) |

Andere Aktionen (auch `extend`) → `invalid_payload`.

```json
{"type": "activation.command", "protocolVersion": 2,
 "sessionId": "20000000-0000-4000-8000-000000000001",
 "commandId": "50000000-0000-4000-8000-000000000001",
 "action": "activate", "source": "manual"}
```

Entscheidungsmatrix (`api_fastapi_server/activation.py`, Session in
`server.py`):

| Aktion | Phase / Lage | Ergebnis |
| --- | --- | --- |
| `activate` | `audioAvailable = false` | `audio_unavailable` |
| `activate` | Vordergrund nicht `idle` | `activation_locked` |
| `activate` | Quelle `manual` nicht konfiguriert oder unterdrückt | `trigger_suppressed` + Event `activation.trigger_suppressed` |
| `activate` | sonst | `applied`, Phase `waiting_first_speech` |
| `refresh` / `finish` / `cancel` | `idle` | `not_active` |
| `refresh` / `finish` / `cancel` | andere `activationId` | `stale_activation` |
| `refresh` | `waiting_first_speech` | `invalid_phase` |
| `refresh` | `segment_active` | `applied`; Frist = max(aktuell, jetzt + `segmentWatchdogRefreshMs`); ohne Verschiebung trotzdem `applied`, aber ohne Event und ohne `stateVersion`-Anstieg |
| `refresh` | `followup_wait` | `applied`; Frist = jetzt + `followupTimeoutMs` |
| `refresh` | `closing_input` | `closing_input` |
| `finish` / `cancel` | offene Phase | `applied`, Phase `closing_input` |
| `finish` / `cancel` | `closing_input` | `no_change` |

### 3.2 `trigger_suppression.set`

Pflicht: `manual` (Bool), `wakeWord` (Bool). `applied` bei Änderung,
sonst `no_change`. Wirkt nur auf künftige Admissionen, beendet keine
laufende Activation.

### 3.3 `audio_availability.set`

Pflicht: `audioAvailable` (Bool). `applied`/`no_change`. `false` bricht eine
offene Activation ab (`activation.input_closed.reason = "cancelled"`,
`causedByCommandId = null`) und sperrt neue Activations.

### 3.4 `session_settings.patch`

Pflicht: `baseSettingsRevision` (Ganzzahl ≥ 0), `changes` (nicht leeres
Objekt). Details §11.

### 3.5 `session.snapshot.request`

Keine weiteren Felder. Antwort: `command.ack` (`applied`) **und danach** ein
`session.snapshot`. Auch ein Replay sendet einen neuen Snapshot.

---

## 4. Command Acknowledgements (`command.ack`)

```json
{
  "type": "command.ack",
  "protocolVersion": 2,
  "sessionId": "20000000-0000-4000-8000-000000000001",
  "commandId": "50000000-0000-4000-8000-000000000001",
  "accepted": true,
  "result": "applied",
  "activationId": "30000000-0000-4000-8000-000000000001",
  "inputPhase": "waiting_first_speech",
  "stateVersion": 1,
  "settingsRevision": 0
}
```

* `accepted` ist genau dann `true`, wenn `result` ∈ {`applied`, `no_change`}.
* `activationId`/`inputPhase`: Vordergrund zum Zeitpunkt der Antwort (`null`/`"idle"` wenn keiner).
* `stateVersion`: Version des vom Command bewirkten Zustands. Für `finish`/`cancel` ist das die Version des `closing_input`-Eintritts, die **kleiner** sein kann als die von Events, die bereits vor dem Ack eingetroffen sind.
* `errors[]` nur bei `settings_revision_conflict` und `settings_rejected`.

### 4.1 Result-Codes

| Code | `accepted` | Bedeutung | Client-Reaktion |
| --- | --- | --- | --- |
| `applied` | true | Wirkung eingetreten (auch Snapshot-Anfrage, No-op-`refresh`) | Folgeevents abwarten |
| `no_change` | true | Zustand war bereits so | nichts |
| `activation_locked` | false | Vordergrund-Activation bereits offen | UI am Server-Zustand ausrichten |
| `not_active` | false | Control im `idle` | lokale Activation verwerfen |
| `invalid_phase` | false | `refresh` in `waiting_first_speech` | erst nach Sprechbeginn refreshen |
| `closing_input` | false | `refresh` in `closing_input` | nichts; Schließung läuft |
| `stale_session` | false | fremde `sessionId` im Command | eigene aktuelle `sessionId` verwenden (Clientfehler) |
| `stale_activation` | false | `activationId` ≠ aktuelle | lokale ID korrigieren (Snapshot) |
| `command_id_conflict` | false | `commandId` mit anderem Payload wiederverwendet | neue `commandId` |
| `invalid_payload` | false | Envelope-/Feldfehler | Clientbug beheben, nicht wiederholen |
| `trigger_suppressed` | false | Quelle unterdrückt oder nicht konfiguriert | Trigger-UI sperren |
| `audio_unavailable` | false | `activate` bei `audioAvailable = false` | Mikrofon melden |
| `settings_revision_conflict` | false | veraltete `baseSettingsRevision` | Snapshot lesen, neu basieren |
| `settings_rejected` | false | ungültige Werte | `errors[]` anzeigen |
| `internal_error` | false | unerwarteter Serverzustand | loggen, ggf. neu verbinden |

### 4.2 Replay

Gleiche `commandId` + gleicher Payload → das gespeicherte Original-Ack
(gleiche `stateVersion`/`settingsRevision`), keine zweite Wirkung, kein
zweites Event. Für `activation.command` und `audio_availability.set` ist der
Schlüssel semantisch (unbekannte Zusatzfelder ändern ihn nicht); für alle
anderen Typen und für vom Envelope abgelehnte Commands ist es der gesamte
Payload ohne `commandId`. Anderer Payload → `command_id_conflict`; das
Original bleibt maßgeblich.

---

## 5. Server → Client Events

Siebzehn Eventtypen (`protocol_v2/schema.py:EVENT_TYPES`). Jedes trägt die
Hülle aus §6.1.

| Event | Felder zusätzlich zur Hülle | `stateVersion` |
| --- | --- | --- |
| `activation.started` | `activationId`, `activationSequence`, `primarySource` (`manual`/`wake_word`), `inputPhase` (`waiting_first_speech`), `effectiveSettings` (gelatcht) | +1 |
| `activation.phase_changed` | `activationId`, `previousPhase`, `inputPhase`, `deadlineAtUnixMs`, `remainingMs` (gleiche Phase = verschobene Frist durch `refresh`) | +1 |
| `activation.input_closed` | `activationId`, `reason` (`finished`, `cancelled`, `timed_out`, `segment_watchdog_timeout`, …), `causedByCommandId` (nur bei `finish`/`cancel`, sonst `null`), `acceptedSegmentCount` | +1 |
| `activation.completed` | `activationId`, `acceptedSegmentCount`, `terminalSegmentCount` | +1 |
| `activation.cancelled` / `activation.failed` | wie oben + `reason` | +1 |
| `activation.trigger_suppressed` | `source` (`manual`), `reason` (`trigger_suppressed`) | ±0 |
| `segment.recording_started` | `activationId`, `segmentId`, `segmentSequence` | +1 |
| `segment.recording_ended` | wie oben + `reason` | +1 |
| `transcription.accepted` | `activationId`, `segmentId`, `segmentSequence` | +1 |
| `transcription.completed` | wie oben + `text` | +1 |
| `transcription.discarded` | wie oben + `reason` (z. B. `cancelled`, `empty_final`) | +1 |
| `transcription.failed` | wie oben + `reason` | +1 |
| `watchdog.warning` | `activationId`, `segmentId`, `segmentSequence` (ggf. `null`), `deadlineAtUnixMs`, `remainingMs` | ±0 |
| `wakeword.detected` | `activationId`, `wakeWordId`, `score`, `primarySource: "wake_word"` | +1 |
| `wakeword.availability_changed` | `catalogRevision`, `availableWakeWordIds` (keine `activationId`) | +1 |
| `settings.changed` | `settingsRevision`, `scope: "session"`, `changedKeys`, `applyPolicy` | +1 nur für das erste Event einer Transaktion |

Es gibt **keine** Realtime-/Zwischentranskripte auf V2. Legacy-Ereignisse
ohne Abbildung werden nicht weitergegeben.

---

## 6. Event-Hülle, Reihenfolge, Deduplizierung

### 6.1 Hülle

```json
{
  "type": "activation.started",
  "protocolVersion": 2,
  "sessionId": "20000000-0000-4000-8000-000000000001",
  "eventId": "60000000-0000-4000-8000-000000000001",
  "eventSeq": 1,
  "stateVersion": 1,
  "occurredAtUnixMs": 1787616000000,
  "activationId": "30000000-0000-4000-8000-000000000001",
  "activationSequence": 1,
  "primarySource": "manual",
  "inputPhase": "waiting_first_speech",
  "effectiveSettings": {"activation.followupTimeoutMs": 3000, "…": "…"}
}
```

### 6.2 Garantien

* `eventSeq` beginnt je Session bei 1 und steigt lückenlos um 1.
* Minting und Übergabe an den Writer sind linearisiert; Events werden in `eventSeq`-Reihenfolge gesendet.
* Ein Transportretry desselben logischen Events hat dieselbe `eventId`/`eventSeq`/`stateVersion`.
* `stateVersion` steigt monoton, aber **nicht** lückenlos im Eventstrom: eventlose Änderungen (`closing_input`-Eintritt, Suppression, Audioverfügbarkeit) erhöhen sie ebenfalls.
* Events, die ein Command auslöst, werden **vor** seinem `command.ack` gesendet (Ausnahme: `activation.trigger_suppressed` folgt dem Ack).

### 6.3 Clientregeln

1. `lastSeq` merken; Events mit `eventSeq ≤ lastSeq` verwerfen.
2. `eventSeq > lastSeq + 1` → Lücke: `session.snapshot.request` senden, weitere Events puffern.
3. Nach dem Snapshot: Zustand ersetzen, `lastSeq = snapshot.lastEventSeq`, gepufferte Events mit `eventSeq > lastSeq` in Reihenfolge anwenden. Gepufferte Segment-/Transkriptionsevents mit `eventSeq ≤ lastSeq` trotzdem in die Transkriptliste übernehmen – der Snapshot enthält keine Segmente und keine Texte.
4. Es gibt keinen Replay: in der Lücke verlorene Transkripte sind nicht wiederherstellbar.

---

## 7. Zustandsmodell

```text
idle ──activate / Wake-Treffer──► waiting_first_speech
waiting_first_speech ──Sprache──► segment_active
segment_active ──Segmentende──► followup_wait
followup_wait ──Sprache──► segment_active
waiting_first_speech | segment_active | followup_wait
      ──finish / cancel / Timer / Watchdog / audioAvailable=false──► closing_input
closing_input ──sicherer Eingabeschluss (activation.input_closed)──► idle
```

| Phase | Frist |
| --- | --- |
| `waiting_first_speech` | `activation.initialSpeechTimeoutMs` → `timed_out` |
| `segment_active` | `activation.segmentWatchdogInitialMs` (Warnung `segmentWatchdogWarningMs` davor) → `segment_watchdog_timeout` |
| `followup_wait` | `activation.followupTimeoutMs` → `timed_out` |
| `closing_input` | `activation.closingRecoveryTimeoutMs` (Recovery) |

* Der Eintritt in `closing_input` ist im Ack (`inputPhase`) und im Snapshot sichtbar; ein `activation.phase_changed` dorthin wird nur gesendet, wenn in dieser Phase ein weiteres Domainereignis projiziert wird.
* `activation.input_closed` = Eingabeseite geschlossen; Vordergrund wieder frei. Die Hintergrundarbeit endet mit `activation.completed`/`.cancelled`/`.failed`. Dieses Terminal **kann vor** `activation.input_closed` derselben Activation eintreffen.
* Eine neue Activation kann starten, während ältere noch in `pendingActivations` drainen.
* Der Vordergrund wird intern vor der Publikation von `activation.input_closed` frei. `activation.started` einer neuen Activation kann daher **vor** dem `input_closed` der vorigen eintreffen; `input_closed` setzt den Vordergrund nur zurück, wenn seine `activationId` die aktuelle ist.

---

## 8. Snapshot und Resynchronisierung

```json
{
  "type": "session.snapshot",
  "protocolVersion": 2,
  "serverVersion": "2.0.0",
  "serverCommit": "unknown",
  "sessionId": "20000000-0000-4000-8000-000000000001",
  "stateVersion": 10,
  "lastEventSeq": 9,
  "settingsRevision": 0,
  "input": {"phase": "idle", "activationId": null, "primarySource": null,
            "deadlineAtUnixMs": null, "remainingMs": null, "closeRequested": false},
  "pendingActivations": [
    {"activationId": "30000000-0000-4000-8000-000000000001",
     "activationSequence": 1, "inputClosedReason": "finished",
     "processingState": "draining", "acceptedSegmentCount": 1,
     "terminalSegmentCount": 0}
  ],
  "trigger": {"configured": {"manual": true, "wakeWord": false},
              "suppressed": {"manual": false, "wakeWord": false},
              "effective": {"manual": true, "wakeWord": false}},
  "audioAvailable": true,
  "requestedSettings": {"…": "16 Session-Schlüssel"},
  "effectiveSettings": {"…": "16 Session-Schlüssel"},
  "wakeWordCapabilities": {"catalogRevision": 1, "availableWakeWordIds": []}
}
```

* `input` in offener Phase: `activationId`, `primarySource`, `deadlineAtUnixMs`, `remainingMs`; `closeRequested` ist genau in `closing_input` `true`.
* `pendingActivations`: nur Activations mit geschlossener Eingabe, sortiert nach `activationSequence`.
* Der Snapshot ist ein Lesevorgang (kein Anstieg von `stateVersion`/`settingsRevision`) und autoritativ: Clientzustand vollständig ersetzen.
* Ein `session.snapshot` hat kein `eventSeq`; Events mit `eventSeq ≤ lastEventSeq` sind darin bereits enthalten.

---

## 9. Audio-Transport

### 9.1 Binärframe

```text
Offset 0      : uint32, Little-Endian = N (Länge der Metadaten in Bytes, ≤ 65 536)
Offset 4      : N Bytes UTF-8-JSON, muss ein Objekt sein
Offset 4 + N  : PCM-Nutzdaten, signed 16-bit Little-Endian, interleaved
```

Kein Magic, keine Versionsnummer, keine Flags
(`api_fastapi_server/protocol.py:decode_audio_packet`).

| Metadatum | Pflicht | Regel |
| --- | --- | --- |
| `sampleRate` | ja | positive Ganzzahl (keine Bool); jede Rate, der Server resampelt auf 16 000 Hz |
| `channels` | nein (1) | Ganzzahl 1–8; mehrere Kanäle werden gemittelt |
| `format` | nein (`"pcm_s16le"`) | nur `"pcm_s16le"` |
| `frames` | nein | falls vorhanden: positive Ganzzahl, `frames × channels × 2` = Nutzlastlänge |

* Nutzlastlänge muss ein Vielfaches von `channels × 2` sein.
* Nutzlast ≤ `max_audio_packet_bytes` (Standard 524 288).
* Ein Frame ohne Samples wird akzeptiert und ignoriert.

Beispiel (20 ms, 16 kHz, Mono):

```text
N = len('{"sampleRate":16000,"channels":1,"format":"pcm_s16le","frames":320}') = 67
Frame = 43 00 00 00 | 7B 22 73 61 … 7D | 640 Bytes PCM
```

### 9.2 Annahme

* Vor `hello.accepted`: Close `4400`.
* Danach ist der Audiopfad offen (kein `start`).
* Frames werden **nie quittiert**; fehlerhafte Frames werden still verworfen.
* Audio sollte kontinuierlich fließen, auch außerhalb einer Activation (Wake-Word-Erkennung, VAD). `audioAvailable = false` stoppt die Annahme von Audio **nicht**, sperrt aber Activations.

---

## 10. Transkriptionslebenszyklus und Beispielabläufe

Pro Segment (Schlüssel `segmentId`): `segment.recording_started` →
`segment.recording_ended` → `transcription.accepted` → genau ein Terminal
(`transcription.completed` | `.discarded` | `.failed`). Beim Abbruch kann das
Terminal (`transcription.discarded`, `reason = "cancelled"`) vor
`recording_ended`/`accepted` eintreffen; ein Client behandelt das erste
Terminal als endgültig.

### 10.1 Manuell (beobachtete Trace, IDs gekürzt)

```text
C→S activation.command activate (C1)
S→C activation.started           seq 1  sv 1  A1
S→C command.ack C1 applied               sv 1  inputPhase waiting_first_speech
     (Audio)
S→C activation.phase_changed     seq 2  sv 2  waiting_first_speech → segment_active
S→C segment.recording_started    seq 3  sv 3  S1
S→C activation.phase_changed     seq 4  sv 4  segment_active → followup_wait
S→C segment.recording_ended      seq 5  sv 5  S1 reason recording_stop
S→C transcription.accepted       seq 6  sv 6  S1
S→C transcription.completed      seq 7  sv 7  S1 text "…"
C→S activation.command finish A1 (C2)        (closing_input = sv 8, ohne Event)
S→C activation.completed         seq 8  sv 9  A1
S→C activation.input_closed      seq 9  sv 10 A1 reason finished causedByCommandId C2
S→C command.ack C2 applied               sv 8  inputPhase closing_input
```

### 10.2 Wake Word

```text
     (kontinuierliches Audio, Wake-Treffer)
S→C activation.started   primarySource wake_word   seq n    sv v
S→C wakeword.detected    wakeWordId hey_jarvis     seq n+1  sv v+1
     … Segmente wie oben …
S→C activation.input_closed reason timed_out (Follow-up abgelaufen)
S→C activation.completed
```

### 10.3 Cancel (beobachtete Trace)

```text
S→C activation.phase_changed segment_active → closing_input  seq 4
S→C transcription.discarded  S1 reason cancelled               seq 5
S→C segment.recording_ended  S1                                seq 6
S→C transcription.accepted   S1                                seq 7
S→C activation.cancelled     A1 reason cancelled               seq 8
S→C activation.input_closed  A1 reason cancelled causedByCommandId C4  seq 9
S→C command.ack C4 applied inputPhase closing_input
```

---

## 11. Settings-Control-Plane

Alle Werte stammen aus `api_fastapi_server/settings_control.py`
(`GET /api/v2/settings/schema`).

| Schlüssel | Typ / Grenzen | Standard | Apply-Policy | Session-patchbar |
| --- | --- | --- | --- | --- |
| `activation.initialSpeechTimeoutMs` | int 100–3 600 000 ms | 15 000 | `next_activation` | ja |
| `activation.followupTimeoutMs` | int 100–60 000 ms | 3 000 | `next_activation` | ja |
| `activation.segmentWatchdogInitialMs` | int 60 000–3 600 000 ms | 600 000 | `next_activation` | ja |
| `activation.segmentWatchdogRefreshMs` | int 30 000–600 000 ms | 180 000 | `next_activation` | ja |
| `activation.segmentWatchdogWarningMs` | int ≥ 5 000 ms, < Initial und < Refresh | 30 000 | `next_activation` | ja |
| `activation.closingRecoveryTimeoutMs` | int 1 000–30 000 ms | 5 000 | `next_activation` | ja |
| `wakeWord.sensitivity` | float 0.0–1.0 | 0.5 | `next_activation` | ja |
| `wakeWord.minConsecutivePredictionFrames` | int ≥ 1 | 1 | `next_activation` | ja |
| `wakeWord.cooldownMs` | int ≥ 0 ms | 0 | `next_activation` | ja |
| `wakeWord.preRollMs` | int ≥ 0 ms | 0 | `next_activation` | ja |
| `wakeWord.detectorGain` | float 0.0–3.0 | 1.0 | `next_activation` | ja |
| `wakeWord.noiseSuppressionEnabled` | bool | false | `next_session` | ja |
| `wakeWord.vadThreshold` | float 0.0–1.0 | 0.0 | `next_session` | ja |
| `wakeWord.selection` | string_list | `[]` | `next_session` | ja (siehe 13.1) |
| `runtimeSuppression.manual` / `.wakeWord` | bool | false | `live` | nein → `read_only_runtime_authority` |
| `wakeWord.inferenceBackend` | `auto`/`onnx`/`tflite` | `auto` | `next_session` | nein (Server, Admin) → `wrong_scope` |
| `wakeWord.globalDisabledIds` | string_list | `[]` | `next_session` | nein (Server, Admin) → `wrong_scope` |

Patch-Regeln:

* `baseSettingsRevision` ≠ aktuelle Session-Revision → `settings_revision_conflict` (`errors[].code = stale_settings_revision`).
* Atomar: ein ungültiger Schlüssel verwirft den ganzen Patch (`settings_rejected`, Fehler sortiert nach `field`, Codes `unknown_key`, `invalid_type`, `out_of_range`, `too_few_items`, `value_not_allowed`, `cross_field_conflict`, `wrong_scope`, `read_only_runtime_authority`, `wake_word_selection_required`, `wake_word_unavailable`).
* Nur unveränderte Werte → `no_change`.
* Wirksam: `settingsRevision + 1` (einmal pro Transaktion), je Apply-Policy ein `settings.changed` in der Reihenfolge `live`, `next_activation`, `next_session`, `server_restart`, Schlüssel sortiert; nur das erste erhöht `stateVersion`.
* `next_activation`: gilt ab der nächsten Activation; eine laufende behält ihre gelatchten Werte (im Snapshot: `requestedSettings` neu, `effectiveSettings` alt, bis die Activation endet).
* `next_session`: wird in der laufenden Session nie wirksam; Session-Settings werden nicht persistiert, eine neue Verbindung beginnt mit Serverdefaults. Für eine andere Wake-Word-Auswahl daher mit neuem `hello` verbinden.

---

## 12. Triggervertrag

`effective = configured && !suppressed`. `configured` stammt aus
`requestedSession.trigger`, `suppressed` initial aus `runtimeSuppression` und
danach aus `trigger_suppression.set`. Es gibt höchstens eine
Vordergrund-Activation; ein Trigger bei offenem Vordergrund wird abgewiesen
(`activation_locked` bzw. stiller Wake-Verwurf). Ein unterdrückter oder
gesperrter Wake-Treffer erzeugt kein Event.

---

## 13. Wake Words

### 13.1 IDs

* Katalog-IDs sind kanonisch (`hey_jarvis`); `displayName` und `aliases` sind Anzeige-/Suchhilfen.
* `hello.requestedSession.wakeWordIds`: nur kanonische IDs; ein Alias/Anzeigename, eine unbekannte oder nicht verfügbare ID lehnt die ganze Session ab.
* `session_settings.patch` → `wakeWord.selection`: der Server nutzt hier den toleranten Resolver und akzeptiert Aliase/Anzeigenamen (gespeichert unverändert). Das ist eine Inkonsistenz der Implementierung (Befund `IMPL-01`); Clients senden trotzdem nur kanonische IDs.
* Die Erkennung läuft ausschließlich serverseitig; der Client sendet nie `source = "wake_word"`.

### 13.2 `GET /api/v2/wake-words`

```json
{
  "protocolVersion": 2,
  "catalogRevision": 1,
  "wakeWords": [
    {
      "id": "hey_jarvis",
      "displayName": "Hey Jarvis",
      "aliases": ["jarvis"],
      "artifactVersion": "1",
      "available": true,
      "backends": {
        "onnx": {"available": true},
        "tflite": {"available": false, "unavailableReason": "runtime_unavailable"}
      },
      "catalogRevision": 1
    }
  ]
}
```

`unavailableReason` erscheint nur bei `available: false`. Laufende Sessions
erhalten bei sichtbaren Katalogänderungen `wakeword.availability_changed`.

---

## 14. HTTP-APIs

| Methode | Pfad | Auth | Antwort |
| --- | --- | --- | --- |
| `GET` | `/health` | keine | `ok`, `ready`, `activeSessions`, `sttReady`, `models`, … |
| `GET` | `/api/v2/wake-words` | keine | Katalog §13.2 |
| `POST` | `/api/v2/wake-words/refresh` | Admin | Refresh-Ergebnis (`ok`, `changed`, `catalogRevision`, `availabilityChanged`, `availableWakeWordIds`, `wakeWords`, `protocolVersion`, ggf. `error`); 422 bei Fehler |
| `GET` | `/api/v2/settings/schema` | keine | `protocolVersion`, `serverVersion`, `serverCommit`, `secretsExposed: false`, `settings[]` |
| `GET` | `/api/v2/settings/server` | keine | `protocolVersion`, `serverVersion`, `serverCommit`, `settingsRevision`, `settings` |
| `PATCH` | `/api/v2/settings/server` | Admin | `accepted`, `result`, `settingsRevision`, `changedKeys`, `values`, `effectiveValues`, `applyPolicies`, ggf. `errors`; 409/422/500 |

---

## 15. Authentifizierung

* `/ws/v2` prüft im Anwendungscode keine Credentials.
* Admin-Endpunkte prüfen im Anwendungscode `X-VoiceSTT-Admin-Key`, `Authorization: Bearer …` oder `X-Admin-Key` gegen `admin_api_key`/`VOICESTT_ADMIN_API_KEY`. Ohne konfigurierten Key sind sie nur von Loopback erreichbar (sonst 403); falscher Key → 401.
* Ein vorgeschalteter Proxy ist eine Deploymententscheidung außerhalb dieses Vertrags.
* V2 liefert keinen `logAccess`-Token; `/ws/logs` und `/api/logs/*` sind für V2-Clients nur mit Admin-Key nutzbar.

---

## 16. Reconnect

Es gibt keine Sessionwiederaufnahme. Nach einem Verbindungsabbruch:

1. neue Verbindung zu `/ws/v2`, neues `hello` (gleiche `clientRunId` empfohlen);
2. neue `sessionId`, `stateVersion = 0`, `lastEventSeq = 0`, `settingsRevision = 0`, leerer Replay-Cache, Session-Settings = Serverdefaults;
3. alle lokalen Activations, Segmente und nicht bestätigten Commands der alten Session als verloren behandeln; gewünschte Session-Settings neu patchen.

---

## 17. Close-Codes und stille Verwerfungen

| Code | Anlass |
| --- | --- |
| `4400` | erstes Frame nicht parsebar / kein gültiges `hello` / Binärframe vor der Annahme |
| `4406` | keine gemeinsame Protokollversion (nach `protocol.incompatible`) |
| `4408` | kein Frame binnen 10 s vor der Annahme |
| `4409` | Sessionadmission abgelehnt (nach `session.rejected`) |
| `1011` | unerwarteter Serverfehler (Handshake oder laufende Verbindung), einschließlich terminaler Recovery einer angenommenen Session |

Eine terminale Recovery beendet die Domain-Session irreparabel und schließt
die zugehörige `/ws/v2`-Verbindung mit `1011`, ohne weitere Clientnachricht
und ohne neue Wire-Nachricht. Der Session-Slot wird freigegeben; Weiterarbeit
erfordert ein neues `hello` (neue `sessionId`).

Nach der Annahme führen fehlerhafte Commands und Audioframes **nie** zu einem
Close. Ohne jede Antwort bleiben: nicht parsebares JSON, unbekannter `type`,
fehlende/nicht kanonische `commandId`, ungültige Audioframes, ein zweites
`hello`.

---

## 18. Implementierungsregeln

1. Erst `hello`, dann auf `hello.accepted` warten; vorher nichts anderes senden.
2. Für jeden neuen Command eine neue kanonische UUID; Retries byte-gleich.
3. `activate` nur mit `source: "manual"` ohne `activationId`; Controls nur mit `activationId` ohne `source`.
4. Events streng nach `eventSeq` anwenden; Lücke → Snapshot anfordern, danach puffern und nachziehen.
5. `command.ack` bestätigt das Command, ist aber nicht der neueste Zustand.
6. `activation.input_closed` und das Activation-Terminal unabhängig verarbeiten; Reihenfolge nicht annehmen.
7. Text nur aus `transcription.completed`.
8. Audio im Längenpräfix-Format, kontinuierlich.

---

## 19. Golden Examples

### 19.1 Abgelehntes Ack (`invalid_payload`)

```json
{
  "type": "command.ack",
  "protocolVersion": 2,
  "sessionId": "20000000-0000-4000-8000-000000000001",
  "commandId": "50000000-0000-4000-8000-000000000003",
  "accepted": false,
  "result": "invalid_payload",
  "activationId": null,
  "inputPhase": "idle",
  "stateVersion": 1,
  "settingsRevision": 0
}
```

### 19.2 Abgelehnter Settings-Patch

```json
{
  "type": "command.ack",
  "protocolVersion": 2,
  "sessionId": "20000000-0000-4000-8000-000000000001",
  "commandId": "50000000-0000-4000-8000-000000000005",
  "accepted": false,
  "result": "settings_rejected",
  "activationId": null,
  "inputPhase": "idle",
  "stateVersion": 1,
  "settingsRevision": 0,
  "errors": [
    {"field": "activation.segmentWatchdogWarningMs", "code": "cross_field_conflict",
     "message": "activation.segmentWatchdogWarningMs (200000 ms) muss kleiner sein als die wirksame Frist von activation.segmentWatchdogRefreshMs (180000 ms)."}
  ]
}
```

### 19.3 `settings.changed`

```json
{
  "type": "settings.changed",
  "protocolVersion": 2,
  "sessionId": "20000000-0000-4000-8000-000000000001",
  "eventId": "60000000-0000-4000-8000-000000000002",
  "eventSeq": 2,
  "stateVersion": 2,
  "occurredAtUnixMs": 1787616001000,
  "settingsRevision": 1,
  "scope": "session",
  "changedKeys": ["activation.followupTimeoutMs"],
  "applyPolicy": "next_activation"
}
```

---

## 20. Nachschlagetabellen

**Client → Server (Text):** `hello`, `activation.command`,
`trigger_suppression.set`, `audio_availability.set`,
`session_settings.patch`, `session.snapshot.request`.
**Client → Server (Binär):** Audioframe §9.

**Server → Client:** `hello.accepted`, `protocol.incompatible`,
`session.rejected`, `command.ack`, `session.snapshot` sowie die 17 Events aus §5.

---

## 21. Compliance-Checkliste

- [ ] `hello` als erstes Frame, binnen 10 s; nichts vor `hello.accepted`.
- [ ] Kanonische UUIDs für `clientRunId` und jede `commandId`.
- [ ] Zustand aus `hello.accepted.snapshot` initialisiert.
- [ ] `activate` ohne `activationId`, nur `source: "manual"`; Controls mit `activationId`, ohne `source`.
- [ ] Alle 15 Result-Codes behandelt; `accepted` nur für `applied`/`no_change`.
- [ ] `eventSeq`-Deduplizierung, Lückenerkennung und Snapshot-Resync mit Puffer.
- [ ] Terminal vor `input_closed` toleriert; erstes Segmentterminal endgültig.
- [ ] Audio als `uint32 LE`-Länge + JSON (`sampleRate`) + `pcm_s16le`.
- [ ] Nur kanonische Wake-Word-IDs.
- [ ] Reconnect = neue Session; Settings neu patchen.
