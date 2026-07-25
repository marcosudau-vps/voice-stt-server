# Server-Events – Kurzreferenz

[← WebSocket-Protokoll](02-websocket-protokoll.md) · [Ausführlicher Katalog & Chronologie →](04-server-events-katalog-und-chronologie.md)

Alle Servernachrichten sind JSON-Objekte in WebSocket-Textframes. `type` ist der
primäre Diskriminator. Der produktive Server kann die folgenden **elf** Typen an
einen Client senden.

## Eventübersicht

| `type` | Scope | Wann | Kernfelder | Empfohlene Clientreaktion |
| --- | --- | --- | --- | --- |
| `hello` | Session | direkt nach Annahme | `sessionId`, `clientId`, `settings`, `limits`, `supportedEngines`, `runtimeSettings` | Session initialisieren; noch nicht streamen |
| `ready` | Server bzw. Session | Modelle/Service bereit oder bereits bereit | `ok`, `settings`, `limits`, `runtimeSettings`, optional `sessionId`, `models` | Audiostart bei `ok: true` freigeben |
| `status` | Session | Start/Stop, VAD, Aufnahme, Transkription, Wake-Zustand | `state`, `queueDepth`, Drops, Aktivzahlen, Wake-Info, Zeit | UI-/Zustandsanzeige aktualisieren |
| `timeline` | Session | fachlicher Stream-Meilenstein | `event`, Zeit, optional `segmentId`, `segment` und eventspezifische Felder | Historie/Diagnose aktualisieren; nicht als Transkriptquelle verwenden |
| `realtime` | Session | neues Zwischenergebnis | `segmentId`, `text`, reiche Stabilisierungsfelder, Zeit, optional `segment` | Segment vorläufig vollständig ersetzen |
| `final` | Session | finale Transkription abgeschlossen | `segmentId`, `text`, Zeit, optional `segment` | Segment finalisieren |
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

## Timeline-Untertypen

`timeline` ist ein Container; `event` bestimmt den fachlichen Untertyp.

| `event` | Bedeutung | Zusätzliche Felder |
| --- | --- | --- |
| `wakeword_wait_started` | Wake-Word-Erkennung beginnt/ist aktiv | `wakeWord` |
| `wakeword_wait_ended` | Wake-Word-Wartephase endet | `wakeWord` |
| `wakeword_detected` | Weckwort erkannt; Sprache wird erwartet | `wakeWord` |
| `wakeword_timeout` | Nach erkanntem Weckwort kam nicht rechtzeitig Sprache | `wakeWord` |
| `wakeword_followup_started` | Folgeäußerung ohne erneutes Weckwort möglich | `durationSeconds` |
| `wakeword_followup_timeout` | Follow-up-Fenster ist abgelaufen | keine weiteren Pflichtfelder |
| `recording_started` | Recorder hat ein Segment begonnen | `segmentId`, `segment`, `preRecordingBuffer` |
| `recording_ended` | Recorder hat Segmentaufnahme beendet | `segmentId`, `segment`, `durationSeconds`, `reason` |
| `transcription_started` | finale Transkription startet | `segmentId`, optional `segment` |
| `realtime_transcript` | Spiegel eines Realtime-Meilensteins | `segmentId`, `text`, optional `sequence`, `segment` |
| `final_transcript` | Spiegel des finalen Text-Meilensteins | `segmentId`, `text`, optional `segment` |

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
