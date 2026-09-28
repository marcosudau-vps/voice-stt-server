# Server-Nachrichten V2 – Referenz

[← WebSocket-Protokoll](02-websocket-protokoll.md) · [Lebenszyklen & Chronologie →](04-server-events-katalog-und-chronologie.md) · [Übersicht](README.md)

## 1. Nachrichtentypen

| `type` | Art | `eventSeq` | Beschreibung |
| --- | --- | --- | --- |
| `hello.accepted` | Handshake | – | Session angenommen, enthält Snapshot |
| `protocol.incompatible` | Handshake | – | vor Close `4406` |
| `session.rejected` | Handshake | – | vor Close `4409` |
| `command.ack` | Antwort | – | genau eine je empfangenem Command mit kanonischer `commandId` |
| `session.snapshot` | Antwort | – | nach `session.snapshot.request` |
| 17 Domain-Events (unten) | Event | ja | geordneter Zustandsstrom |

Unbekannte `type`-Werte und unbekannte Felder muss ein Client ignorieren.

## 2. Gemeinsame Event-Hülle

```json
{
  "type": "segment.recording_started",
  "protocolVersion": 2,
  "sessionId": "20000000-0000-4000-8000-000000000001",
  "eventId": "60000000-0000-4000-8000-000000000001",
  "eventSeq": 3,
  "stateVersion": 3,
  "occurredAtUnixMs": 1787616000000,
  "activationId": "30000000-0000-4000-8000-000000000001",
  "segmentId": "40000000-0000-4000-8000-000000000001",
  "segmentSequence": 1
}
```

| Feld | Regel |
| --- | --- |
| `eventId` | kanonische UUID; bei Transport-Retry desselben logischen Events unverändert |
| `eventSeq` | ab 1, lückenlos um 1 steigend; Events werden in dieser Reihenfolge gesendet |
| `stateVersion` | monoton; steigt bei sichtbaren Zustandsänderungen (auch eventlosen), nicht bei diagnostischen Events |
| `occurredAtUnixMs` | Wall-Clock des Servers in ms (Anzeige/Diagnose, nicht zur Ordnung) |

## 3. Eventkatalog

„±0“ = erhöht `stateVersion` nicht; das Event trägt die aktuelle Version.

### Activation

| Event | Zusatzfelder | `stateVersion` |
| --- | --- | --- |
| `activation.started` | `activationId`, `activationSequence`, `primarySource` (`manual` \| `wake_word`), `inputPhase` = `waiting_first_speech`, `effectiveSettings` (für diese Activation gelatcht) | +1 |
| `activation.phase_changed` | `activationId`, `previousPhase`, `inputPhase`, `deadlineAtUnixMs`, `remainingMs` | +1 |
| `activation.input_closed` | `activationId`, `reason`, `causedByCommandId`, `acceptedSegmentCount` | +1 |
| `activation.completed` | `activationId`, `acceptedSegmentCount`, `terminalSegmentCount` | +1 |
| `activation.cancelled` | wie `completed` + `reason` | +1 |
| `activation.failed` | wie `completed` + `reason` | +1 |
| `activation.trigger_suppressed` | `source` (`manual`), `reason` = `trigger_suppressed` | ±0 |

* `activation.phase_changed` mit `previousPhase == inputPhase` bedeutet: neue Frist nach `refresh`.
* `activation.input_closed.reason`: `finished` (`finish`), `cancelled` (`cancel` oder `audio_availability.set false`), `timed_out` (Initial- oder Follow-up-Frist), `segment_watchdog_timeout`; bei Sessionende weitere interne Gründe. `causedByCommandId` ist nur bei `finish`/`cancel` gesetzt, sonst `null`.
* `activation.completed` = alle Segmente erfolgreich oder verworfen; `.failed` = mindestens ein Segment fehlgeschlagen; `.cancelled` = abgebrochen.

### Segment und Transkription

Alle tragen `activationId`, `segmentId`, `segmentSequence`.

| Event | Zusatzfelder | `stateVersion` |
| --- | --- | --- |
| `segment.recording_started` | – | +1 |
| `segment.recording_ended` | `reason` (z. B. `recording_stop`) | +1 |
| `transcription.accepted` | – | +1 |
| `transcription.completed` | `text` (finaler Text, kann leer sein) | +1 |
| `transcription.discarded` | `reason` (z. B. `cancelled`, `empty_final`) | +1 |
| `transcription.failed` | `reason` | +1 |

Je `segmentId` gibt es genau ein Terminal (`completed` | `discarded` |
`failed`). **Es gibt keine Zwischen-/Realtime-Transkripte auf V2.**

### Watchdog, Wake Word, Settings

| Event | Zusatzfelder | `stateVersion` |
| --- | --- | --- |
| `watchdog.warning` | `activationId`, `segmentId`/`segmentSequence` (ggf. `null`), `deadlineAtUnixMs`, `remainingMs` | ±0 |
| `wakeword.detected` | `activationId` (die durch den Treffer geöffnete Activation), `wakeWordId` (kanonisch), `score`, `primarySource` = `wake_word` | +1 |
| `wakeword.availability_changed` | `catalogRevision`, `availableWakeWordIds` | +1 |
| `settings.changed` | `settingsRevision`, `scope` = `session`, `changedKeys` (sortiert), `applyPolicy` | +1 für das erste Event einer Transaktion, ±0 für weitere |

## 4. Snapshot-Felder

Vollständig beschrieben in
[05 – `session.snapshot`](05-client-zustandsmodell.md#2-sessionsnapshot).

## 5. TypeScript-Skizze

```ts
type Phase = "idle" | "waiting_first_speech" | "segment_active" | "followup_wait" | "closing_input";
type Source = "manual" | "wake_word";

interface Envelope {
  protocolVersion: 2; sessionId: string;
  eventId: string; eventSeq: number; stateVersion: number; occurredAtUnixMs: number;
}
interface SegmentRef { activationId: string; segmentId: string; segmentSequence: number; }

type V2Event =
  | Envelope & { type: "activation.started"; activationId: string; activationSequence: number;
                 primarySource: Source; inputPhase: "waiting_first_speech"; effectiveSettings: Record<string, unknown> }
  | Envelope & { type: "activation.phase_changed"; activationId: string | null; previousPhase: Phase;
                 inputPhase: Phase; deadlineAtUnixMs: number | null; remainingMs: number | null }
  | Envelope & { type: "activation.input_closed"; activationId: string; reason: string;
                 causedByCommandId: string | null; acceptedSegmentCount: number }
  | Envelope & { type: "activation.completed"; activationId: string; acceptedSegmentCount: number; terminalSegmentCount: number }
  | Envelope & { type: "activation.cancelled" | "activation.failed"; activationId: string;
                 acceptedSegmentCount: number; terminalSegmentCount: number; reason: string }
  | Envelope & { type: "activation.trigger_suppressed"; source: Source; reason: "trigger_suppressed" }
  | Envelope & SegmentRef & { type: "segment.recording_started" | "transcription.accepted" }
  | Envelope & SegmentRef & { type: "segment.recording_ended" | "transcription.discarded" | "transcription.failed"; reason: string }
  | Envelope & SegmentRef & { type: "transcription.completed"; text: string }
  | Envelope & { type: "watchdog.warning"; activationId: string | null; segmentId: string | null;
                 segmentSequence: number | null; deadlineAtUnixMs: number | null; remainingMs: number | null }
  | Envelope & { type: "wakeword.detected"; activationId: string; wakeWordId: string; score: number | null; primarySource: "wake_word" }
  | Envelope & { type: "wakeword.availability_changed"; catalogRevision: number; availableWakeWordIds: string[] }
  | Envelope & { type: "settings.changed"; settingsRevision: number; scope: "session";
                 changedKeys: string[]; applyPolicy: "live" | "next_activation" | "next_session" | "server_restart" };
```
