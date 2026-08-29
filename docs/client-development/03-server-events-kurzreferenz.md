# Server-Events – Kurzreferenz

[← WebSocket-Protokoll](02-websocket-protokoll.md) · [Ausführlicher Katalog & Chronologie →](04-server-events-katalog-und-chronologie.md)

Alle Servernachrichten sind JSON-Objekte in WebSocket-Textframes. `type` ist der
primäre Diskriminator. Der produktive Server kann die folgenden **zwölf** Typen
an einen Client senden.

> **Gilt für `/ws/transcribe` (Protokoll v1).** Der seit AP-SRV-040 verfügbare
> Endpunkt `/ws/v2` sendet einen anderen, eingefrorenen Nachrichtensatz
> (`hello.accepted`, `command.ack`, `session.snapshot` und punktgetrennte
> Domain-Events mit `eventId`/`eventSeq`/`stateVersion`). Keiner der hier
> beschriebenen Typen erreicht eine v2-Verbindung. Siehe
> [`docs/einheitliche-triggerarchitektur.md`](../einheitliche-triggerarchitektur.md),
> Abschnitt 12.

## Eventübersicht

| `type` | Scope | Wann | Kernfelder | Empfohlene Clientreaktion |
| --- | --- | --- | --- | --- |
| `hello` | Session | direkt nach Annahme | `sessionId`, `clientId`, `settings`, `limits`, `supportedEngines`, `runtimeSettings`, `logAccess` | Session initialisieren; noch nicht streamen |
| `ready` | Server bzw. Session | Modelle/Service bereit oder bereits bereit | `ok`, `settings`, `limits`, `runtimeSettings`, optional `sessionId`, `models` | Audiostart bei `ok: true` freigeben |
| `status` | Session | Start/Stop, VAD, Aufnahme, Transkription, Wake-Zustand | `state`, `queueDepth`, Drops, Aktivzahlen, Wake-Info, Zeit | UI-/Zustandsanzeige aktualisieren |
| `timeline` | Session | fachlicher Stream-Meilenstein | `event`, Zeit, optional `segmentId`, `segment` und eventspezifische Felder | Historie/Diagnose aktualisieren; nicht als Transkriptquelle verwenden |
| `realtime` | Session | neues Zwischenergebnis | `segmentId`, `text`, reiche Stabilisierungsfelder, Zeit, optional `segment` | Segment vorläufig vollständig ersetzen |
| `final` | Session | finale Transkription abgeschlossen | `segmentId`, `text`, Zeit, optional `segment` | Segment finalisieren |
| `trigger_ack` | Session | Antwort auf jedes `trigger`-Kommando | `commandId`, `accepted`, `reason`, `activationId`, `sessionId` | Pending-Kommando auflösen; erst bei `accepted: true` fachliches Feedback |
| `clear` | Session | Antwort auf Clientbefehl `clear` | `nextSegmentId` | lokale Segmente und Timeline leeren |
| `pong` | Session | Antwort auf `ping` | `serverTime` | lokalen Roundtrip abschließen |
| `metrics` | Session | Antwort auf Befehl `metrics` | `metrics` | Diagnose-/Telemetrieansicht aktualisieren |
| `warning` | Session | behebbares Limit/Überlast/Audioproblem | `message`, meist `sessionId` | anzeigen/loggen; Stream normalerweise fortsetzen |
| `error` | Session oder Server | Protokoll-, Admission-, Engine- oder Transkriptionsfehler | `message`, optional `where`, `sessionId`, `limits`, `requestId` | nach `where` klassifizieren; nicht pauschal reconnecten |

## Gemeinsame Felder

Nicht jedes Event enthält alle gemeinsamen Felder.

| Feld | Typ | Bedeutung |
| --- | --- | --- |
| `type` | String | Eventtyp; immer vorhanden |
| `sessionId` | String | Besitzer-Session; bei Broadcasts/Admission-Fehlern optional |
| `timestamp` | Number | Unix-Sekunden; bei Stream-/Timeline-/Status-Events |
| `timestampIso` | String | derselbe Zeitpunkt als UTC ISO 8601 |
| `segmentId` | Integer | Sessionlokale Äußerungs-ID |
| `segment` | Object | Timeline-Snapshot des Segments |
| `message` | String | menschenlesbare deutsche Warn-/Fehlerbeschreibung |
| `where` | String | Fehlerursprungsbereich |
| `activationId` | String | Activation, zu der ein Recording-/Transkriptionsevent gehört (nur im Controlled-Modus) |
| `primarySource` | String | Quelle des **ersten** Triggers dieser Activation |
| `sources` | Array | alle beteiligten Triggerquellen, jede höchstens einmal |

## Timeline-Untertypen

`timeline` ist ein Container; `event` bestimmt den fachlichen Untertyp.

| `event` | Bedeutung | Zusätzliche Felder |
| --- | --- | --- |
| `wakeword_wait_started` | Wake-Word-Erkennung beginnt/ist aktiv | `wakeWord` |
| `wakeword_wait_ended` | Wake-Word-Wartephase endet | `wakeWord` |
| `activation_started` | eine Activation wurde eröffnet | `activationId`, `generation`, `primarySource`, `sources`, `phase`, `timerRevision` |
| `activation_refreshed` | Follow-up- oder Watchdog-Deadline neu gesetzt | wie oben |
| `activation_closed` | Eingabepfad der Activation ist geschlossen; genau einmal je Activation | wie oben, zusätzlich `reason`, `cause` und `causedByCommandId` |

`activation_closed` wird erst logisch registriert, wenn Gate und Recorder
tatsächlich geschlossen und die Ledgerausgänge registriert sind
(zweiphasiger Input-Close, AP-SRV-030 C3). Diese Registrierung liegt vor der
Foreground-Freigabe nach `idle`; die Transportpublikation kann unmittelbar
danach erfolgen. `causedByCommandId` trägt nur bei einem normalen,
kommandogetriebenen `finish`/`cancel` die
zugehörige `commandId`; Timer-, Watchdog-, Geräte- (`audio_unavailable`) und
Recoveryabschlüsse sind **nicht** kommandokorreliert (`null`), auch wenn die
ursprüngliche Finish-Identität intern bis zum Abschluss erhalten bleibt.
Recoveryabschlüsse kennzeichnet zusätzlich `cause: closing_recovery_timeout`
und `recovered: true`. Ein verspäteter Close mit alter Activation-Identität
wird verworfen und beendet keine neuere Activation.
| `activation_drained` | Hintergrundledger der Activation ist terminal | `activationId`, `activationSequence`, `state`, `reason`, `acceptedSegmentCount`, `terminalSegmentCount` |
| `watchdog_warning` | Vorwarnung vor dem Daueraufnahme-Ablauf | `activationId`, `activationSequence`, `segmentId`, `segmentSequence`, `phase`, `timerRevision`, `remainingSeconds` |
| `wakeword_detected` | Weckwort erkannt; Sprache wird erwartet | `wakeWord` (v1) bzw. `activationId`, `wakeWordId`, `score` (Peak des Trefferbereichs), `primarySource` als `wakeword.detected` (v2); genau ein logisches Event je Wake-Äußerung |
| `wakeword.availability_changed` | jede sichtbare Änderung des Wake-Word-Katalogs, auch reine Metadaten (nur v2) | `catalogRevision`, `availableWakeWordIds` |
| `wakeword_timeout` | Nach erkanntem Weckwort kam nicht rechtzeitig Sprache | `wakeWord` |
| `wakeword_followup_started` | Folgeäußerung ohne erneutes Weckwort möglich | `durationSeconds` |
| `wakeword_followup_timeout` | Follow-up-Fenster ist abgelaufen | keine weiteren Pflichtfelder |
| `recording_started` | Recorder hat ein Segment begonnen | `segmentId`, `segment`, `preRecordingBuffer` |
| `recording_ended` | Recorder hat Segmentaufnahme beendet | `segmentId`, `segment`, `durationSeconds`, `reason` |
| `transcription_started` | finale Transkription startet | `segmentId`, optional `segment` |
| `realtime_transcript` | Spiegel eines Realtime-Meilensteins | `segmentId`, `text`, optional `sequence`, `segment` |
| `final_transcript` | Spiegel des finalen Text-Meilensteins | `segmentId`, `text`, optional `segment` |
| `final_transcript_discarded` | leerer finaler Recordertext beendet das Segment ohne Finaltextframe | `segmentId`, `reason: "empty_final"`, optional `segment` |

## Statuswerte

| `status.state` | Bedeutung |
| --- | --- |
| `idle` | Session streamt nicht |
| `listening` | Stream aktiv, wartet ohne Wake-Word-Gate auf Sprache |
| `voice` | VAD erkennt Sprache |
| `silence` | VAD meldet Stille |
| `wakeword_wait` | wartet auf Weckwort |
| `wakeword_detected` | Weckwort/Folgefenster aktiv, wartet auf Sprache |
| `wakeword_timeout` | Wake-Word-Sprachfenster abgelaufen |
| `recording` | Segment wird aufgenommen |
| `transcribing` | finale Transkription läuft/anläuft |
| `closed` | interner Endzustand; kann bei abruptem Close nicht mehr zugestellt werden |

Statusereignisse sind Zustandsbeobachtungen, keine exakt-einmaligen
Transitionsmeldungen. Derselbe Zustand darf mehrfach eintreffen.

## Segment-Snapshot

Ein `segment` kann folgende Felder enthalten:

| Feld | Typ | Bedeutung |
| --- | --- | --- |
| `segmentId` | Integer | Segment-ID |
| `recordingStartedAt` / `recordingStartedAtIso` | Number / String | Recorderstart |
| `recordingEndedAt` / `recordingEndedAtIso` | Number / String | Recorderende |
| `durationSeconds` | Number | aufgenommene Dauer |
| `endReason` | String | implementierter Recorderpfad typischerweise `recording_stop` |
| `preRecordingBuffer` | Object | konfigurierter/einbezogener Vorlauf und Zeitbereich |
| `wakeWord` | Object | Wake-Kontext, wenn dieses Segment auf eine Erkennung folgt |

`preRecordingBuffer`:

```json
{
  "configuredSeconds": 0.75,
  "includedSeconds": 0.75,
  "startTimestamp": 1784541599.25,
  "startTimestampIso": "2026-07-20T09:59:59.250Z",
  "endTimestamp": 1784541600.0,
  "endTimestampIso": "2026-07-20T10:00:00.000Z",
  "exact": false
}
```

`exact: false` bedeutet, dass der Recordercallback keine gemessene tatsächliche
Vorlaufdauer geliefert hat und der Tracker den konfigurierten Wert verwendet.

## Fehlerorte (`error.where`)

| Wert / Muster | Ursache |
| --- | --- |
| `admission` | Sessionlimit erreicht; danach Close 1013 |
| `session_config` | Sessionparameter mehrdeutig oder kein lokales Fallbackprofil verfügbar; danach Close 1008 |
| `command` | ungültiges JSON, kein Objekt oder unbekannter Befehl |
| `audio_packet` | Binärformat oder Metadaten ungültig |
| `audio` | unerwarteter Fehler bei Audioverarbeitung |
| `recorder` | Session-Textworker/Recorder fehlgeschlagen |
| `scheduler` | finale Queue-/Schedulerablehnung (im alternativen Inlinepfad) |
| `final` / `realtime` | Inferenzfehler im Inlinepfad |
| `main_engine` / `realtime_engine` | Modellworker konnte nicht initialisiert werden |

Neue `where`-Werte sind eine kompatible Erweiterung. Clients sollten unbekannte
Werte anzeigen/loggen und nur bekannte Fälle speziell behandeln.

## Minimale TypeScript-Union

Diese Union bildet die Routing-Ebene ab; die vollständigen Feldtabellen stehen
im [ausführlichen Event-Katalog](04-server-events-katalog-und-chronologie.md).

```ts
type ServerEvent =
  | { type: "hello"; sessionId: string; clientId: string }
  | { type: "ready"; ok: boolean; sessionId?: string }
  | { type: "status"; sessionId: string; state: string }
  | { type: "timeline"; sessionId: string; event: string }
  | { type: "realtime"; sessionId: string; segmentId: number; text: string }
  | { type: "final"; sessionId: string; segmentId: number; text: string }
  | { type: "clear"; sessionId: string; nextSegmentId: number }
  | { type: "pong"; sessionId: string; serverTime: number }
  | { type: "metrics"; sessionId: string; metrics: SessionMetrics }
  | { type: "warning"; sessionId?: string; message: string }
  | { type: "error"; sessionId?: string; message: string; where?: string };
```
