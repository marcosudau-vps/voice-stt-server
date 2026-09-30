# Client-Zustandsmodell, Snapshot und Reconnect (V2)

[← Lebenszyklen & Chronologie](04-server-events-katalog-und-chronologie.md) · [HTTP-API →](06-http-api-und-authentifizierung.md) · [Übersicht](README.md)

## 1. Grundsatz

Der Server ist autoritativ. Der Client spiegelt den Serverzustand aus genau
zwei Quellen:

1. **Snapshots** (`hello.accepted.snapshot`, `session.snapshot`) – ersetzen den Spiegel vollständig;
2. **Events** in `eventSeq`-Reihenfolge – aktualisieren ihn inkrementell.

`command.ack` bestätigt nur ein Command (Erfolg/Fehler). Optimistische
UI-Zustände (z. B. „PTT gedrückt“) werden bei `accepted: false` zurückgerollt.
Bei `accepted: true` gilt je Command:

| Command | Bestätigung des neuen Zustands |
| --- | --- |
| `activate`, wirksamer `refresh`/`finish`/`cancel` | zugehörige Events (`activation.started`, `activation.phase_changed`, …) kommen **vor** dem Ack; der Eintritt in `closing_input` ist nur im Ack (`inputPhase`) sichtbar |
| `refresh` ohne Fristverschiebung | kein Event – das Ack (`applied`) ist die Bestätigung |
| `trigger_suppression.set`, `audio_availability.set` | kein Event – Spiegel nach dem Ack lokal setzen (oder Snapshot anfordern) |
| `session_settings.patch` | `settings.changed` vor dem Ack |
| `session.snapshot.request` | `session.snapshot` **nach** dem Ack |
| `no_change` | nichts zu tun |

Nie nach einem `applied`-Ack auf ein Event warten, das es für dieses Command
nicht gibt.

## 2. `session.snapshot`

```json
{
  "type": "session.snapshot",
  "protocolVersion": 2,
  "serverVersion": "2.0.0",
  "serverCommit": "unknown",
  "sessionId": "20000000-0000-4000-8000-000000000001",
  "stateVersion": 8,
  "lastEventSeq": 12,
  "settingsRevision": 3,
  "input": {
    "phase": "segment_active",
    "activationId": "30000000-0000-4000-8000-000000000002",
    "primarySource": "manual",
    "deadlineAtUnixMs": 1787616600000,
    "remainingMs": 598000,
    "closeRequested": false
  },
  "pendingActivations": [
    {
      "activationId": "30000000-0000-4000-8000-000000000001",
      "activationSequence": 1,
      "inputClosedReason": "finished",
      "processingState": "draining",
      "acceptedSegmentCount": 2,
      "terminalSegmentCount": 1
    }
  ],
  "trigger": {
    "configured": {"manual": true, "wakeWord": true},
    "suppressed": {"manual": false, "wakeWord": true},
    "effective": {"manual": true, "wakeWord": false}
  },
  "audioAvailable": true,
  "requestedSettings": {"activation.followupTimeoutMs": 4000, "…": "alle 16 Session-Schlüssel"},
  "effectiveSettings": {"activation.followupTimeoutMs": 3000, "…": "alle 16 Session-Schlüssel"},
  "wakeWordCapabilities": {"catalogRevision": 1, "availableWakeWordIds": ["alexa", "hey_jarvis"]}
}
```

| Feld | Bedeutung |
| --- | --- |
| `stateVersion` | Version des abgebildeten Zustands |
| `lastEventSeq` | letztes bereits enthaltene Event (0 = noch keins) |
| `settingsRevision` | aktuelle Session-Settingsrevision (Basis für den nächsten Patch) |
| `input` | Vordergrund. In `idle` sind `activationId`, `primarySource`, `deadlineAtUnixMs`, `remainingMs` `null`, `closeRequested` `false`; `closeRequested` ist genau in `closing_input` `true` |
| `pendingActivations` | Activations mit geschlossener Eingabe, deren Segmente noch nicht alle terminal sind; aufsteigend nach `activationSequence`; enthält nie die offene Vordergrund-Activation |
| `trigger` | `configured`/`suppressed`/`effective` je Quelle |
| `audioAvailable` | zuletzt gemeldete Geräteverfügbarkeit |
| `requestedSettings` / `effectiveSettings` | angeforderte bzw. wirksame Werte aller 16 Session-Schlüssel; während einer offenen Activation zeigt `effectiveSettings` deren gelatchte Werte ([09](09-betriebsmodi-und-serverkonfiguration.md#session-settings)) |
| `wakeWordCapabilities` | aktuelle Katalogrevision und verfügbare IDs |

`deadlineAtUnixMs` ist aus der monotonen Serverfrist abgeleitet; für
Countdown-Anzeigen `remainingMs` relativ zum Empfangszeitpunkt verwenden,
nicht die Uhren vergleichen.

Ein Snapshot ist ein reiner Lesevorgang und trägt kein `eventSeq`.

## 3. Empfohlenes Zustandsschema

```ts
interface V2Mirror {
  sessionId: string;
  lastEventSeq: number;
  stateVersion: number;
  settingsRevision: number;
  input: { phase: Phase; activationId: string | null; primarySource: Source | null;
           deadlineAtUnixMs: number | null; remainingMs: number | null; closeRequested: boolean };
  activations: Map<string, {           // activationId → Zustand
    sequence: number; source: Source; inputClosed: boolean;
    terminal: null | "completed" | "cancelled" | "failed";
  }>;
  segments: Map<string, {              // segmentId → Zustand
    activationId: string; sequence: number;
    stage: "recording" | "recorded" | "accepted" | "interim" | "completed" | "discarded" | "failed";
    interimText?: string; text?: string; reason?: string;
  }>;
  trigger: { configured: Flags; suppressed: Flags; effective: Flags };
  audioAvailable: boolean;
  requestedSettings: Record<string, unknown>;
  effectiveSettings: Record<string, unknown>;
  wakeWords: { catalogRevision: number; available: string[] };
  resync: { pending: boolean; buffer: V2Event[] };
}
```

## 4. Event-Reducer

```ts
// Events mit Nutzlast, die ein Snapshot NICHT enthält (Segmente, Texte).
const PAYLOAD = (e: V2Event) =>
  e.type.startsWith("segment.") || e.type.startsWith("transcription.");

function onEvent(m: V2Mirror, e: V2Event) {
  if (m.resync.pending) { m.resync.buffer.push(e); return; }
  if (e.eventSeq <= m.lastEventSeq) return;                // Duplikat
  if (e.eventSeq > m.lastEventSeq + 1) {                    // Lücke
    m.resync.pending = true; m.resync.buffer.push(e);
    send(snapshotRequest()); return;
  }
  apply(m, e);
  m.lastEventSeq = e.eventSeq;
  m.stateVersion = Math.max(m.stateVersion, e.stateVersion);
}

function onSnapshot(m: V2Mirror, s: Snapshot) {
  replaceMirrorFrom(m, s);          // Zustand ersetzen; segments/Texte BEHALTEN
  m.lastEventSeq = s.lastEventSeq;
  const buffer = m.resync.buffer.sort((a, b) => a.eventSeq - b.eventSeq);
  m.resync = { pending: false, buffer: [] };
  for (const e of buffer) {
    if (e.eventSeq <= s.lastEventSeq) {
      if (PAYLOAD(e)) applySegment(m, e);  // Snapshot kennt keine Texte
      continue;                            // Zustand steckt bereits im Snapshot
    }
    onEvent(m, e);                         // kann erneut Lücke erkennen
  }
}
```

`replaceMirrorFrom` ersetzt `input`, `trigger`, `audioAvailable`, Settings,
`wakeWords` und den Activation-Status aus `pendingActivations`, lässt aber
die Segment-/Transkriptliste stehen: Der Snapshot enthält nur Zähler
(`acceptedSegmentCount`/`terminalSegmentCount`), keine `segmentId` und keinen
Text. `applySegment` ist idempotent (erstes Terminal gewinnt).

> **Grenze des Protokolls:** Es gibt keinen Replay. Ein Segment- oder
> Transkriptionsevent, das in der Lücke selbst verloren ging, ist nicht
> wiederherstellbar; der Snapshot zeigt nur, dass eine Activation terminal ist.
> Ein Client sollte solche Activations als „Ergebnis unvollständig“ markieren.
> Da der Server Events linearisiert über eine TCP-Verbindung sendet, entstehen
> Lücken praktisch nur durch Clientfehler (verworfene Nachrichten).

Regeln für `apply`:

| Event | Wirkung im Spiegel |
| --- | --- |
| `activation.started` | `input` = neue Activation, Phase `waiting_first_speech`; Activation anlegen |
| `activation.phase_changed` | `input.phase`/Frist aktualisieren |
| `activation.input_closed` | Activation `inputClosed = true`; `input` nur dann auf `idle` setzen, wenn `input.activationId === e.activationId` – eine neue Activation kann ihr `activation.started` **vor** dem `input_closed` der vorigen senden |
| `activation.completed`/`.cancelled`/`.failed` | Activation `terminal` setzen; darf **vor** `input_closed` kommen – dann `input` erst bei `input_closed` zurücksetzen |
| `segment.*`, `transcription.accepted` | Segment anlegen/Stufe erhöhen, falls noch nicht terminal |
| `transcription.interim` | falls noch nicht terminal: `interimText` desselben Segments ersetzen; optionale Stabilisierungsfelder nur als Vorschau behandeln (der Server sendet nach einem Terminal kein weiteres Interim; die Regel bleibt clientseitig als Verteidigung bestehen) |
| `transcription.completed`/`.discarded`/`.failed` | `interimText` entfernen und Segment terminal setzen (erstes Terminal gewinnt) |
| `settings.changed` | `settingsRevision` übernehmen; Werte per Snapshot nachladen, falls benötigt |
| `wakeword.availability_changed` | `wakeWords.available`/`catalogRevision` ersetzen; bei geänderter Revision den Katalog (`GET /api/v2/wake-words`) neu laden – das Event trägt keine Metadaten (Anzeigenamen, Aliase, Backends) und kommt auch bei reinen Metadatenänderungen |
| `wakeword.detected` | UI-Hinweis (Activation kam bereits mit `activation.started`) |
| `watchdog.warning`, `activation.trigger_suppressed` | nur Anzeige/Diagnose |

Zustände **ohne Event** (Suppression, `audioAvailable`) ändern sich durch
eigene Commands; nach deren `applied`-Ack den Spiegel lokal setzen oder einen
Snapshot anfordern.

## 5. Reconnect

Es gibt keine Wiederaufnahme einer Session.

1. Verbindung weg → alle nicht bestätigten Commands als verloren betrachten; offene Activations und nicht terminale Segmente der alten Session als abgebrochen darstellen (ihre Ergebnisse kommen nie an).
2. Neu verbinden mit Backoff und Jitter, neues `hello` (gleiche `clientRunId`, gleiche gewünschte Trigger/Wake Words).
3. Aus `hello.accepted.snapshot` einen frischen Spiegel bauen: neue `sessionId`, `lastEventSeq = 0`, `stateVersion = 0`, `settingsRevision = 0`.
4. Session-Settings stehen wieder auf Serverdefaults → gewünschte Werte erneut per `session_settings.patch` (Basis `0`) setzen; Suppression und Audioverfügbarkeit erneut melden, falls sie vom `hello` abweichen.
5. Keine `commandId` der alten Session wiederverwenden.

Ein beim Disconnect verlorenes Interim ist nur eine verlorene Vorschau. Ein
verlorenes Terminal bleibt wegen des fehlenden Domain-Event-Replays dagegen
eine unvollständige fachliche Ausgabe. `hello.accepted.logAccess` der neuen
Session ersetzt den Bootstrap-Logzugriff für die neue Session; ein noch
gültiges Token der alten Session bleibt ausschließlich auf deren Historie
begrenzt.

| Ereignis | Automatischer Reconnect? |
| --- | --- |
| Netzwerkabbruch, `1011`, Serverneustart | ja, Backoff + Jitter |
| `4409` mit `session_limit_reached` | ja, langer Backoff |
| `4409` sonst, `4406`, `4400` | nein – Konfiguration/Clientbug beheben |
| `4408` | einmal sofort; wiederholt → Clientbug |

## 6. Zeit

* Ordnung ausschließlich über `eventSeq`, nie über `occurredAtUnixMs`.
* `occurredAtUnixMs`/`deadlineAtUnixMs` sind Server-Wall-Clock-Werte in ms.
* Countdown aus `remainingMs` + lokalem monotonem Zeitpunkt des Empfangs.
