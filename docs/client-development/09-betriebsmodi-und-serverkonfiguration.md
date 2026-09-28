# Triggerquellen, Wake Words und Settings (V2)

[← Protokollabgrenzung](08-protokollabgrenzung.md) · [Übersicht](README.md)

Diese Seite beschreibt, wie ein V2-Client Triggerquellen wählt, Wake Words
auswählt und Session-Settings ändert. Serverbetrieb und Admin-Konfiguration:
[`docs/wake-words.md`](../wake-words.md),
[`docs/configuration.md`](../configuration.md),
[`docs/einheitliche-triggerarchitektur.md`](../einheitliche-triggerarchitektur.md) §13–14.

## Triggerquellen

Eine Session hat zwei unabhängig wählbare Quellen, festgelegt im `hello`:

| `trigger.manual` | `trigger.wakeWord` | zulässig |
| --- | --- | --- |
| `true` | `false` | ja – nur Push-to-Talk/Toggle |
| `false` | `true` | ja – nur Wake Word |
| `true` | `true` | ja – beide |
| `false` | `false` | nein → `session.rejected` (`activation_trigger_required`) |

Die Quellen sind für die Session fest. Zur Laufzeit lassen sie sich nur
**unterdrücken** (`trigger_suppression.set`), nicht hinzufügen; für eine andere
Kombination neu verbinden. Beispiel: Wake Word während eines Telefonats
stummschalten, ohne die Session zu verlieren.

| Quelle | Auslöser | Client sendet |
| --- | --- | --- |
| `manual` | Nutzeraktion (Hotkey, Button) | `activation.command` `activate`, später `finish`/`cancel`/`refresh` |
| `wake_word` | serverseitige Erkennung im Audiostrom | nichts – nur kontinuierliches Audio; Steuerung der entstandenen Activation wie bei `manual` |

## Wake-Word-Katalog

Vor dem `hello` lädt der Client den Katalog:

```http
GET /api/v2/wake-words
```

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

* `id` ist die **kanonische ID** und das Einzige, was auf den Wire gehört.
* `displayName`/`aliases` dienen der Anzeige und der clientseitigen Suche.
* Nicht verfügbare Einträge bleiben gelistet (`available: false`, `unavailableReason`: `globally_disabled`, `artifact_missing`, `artifact_integrity_mismatch`, `artifact_unloadable`, `pipeline_unavailable`, `runtime_unavailable`).
* Der gebündelte Build enthält 25 IDs (`alexa`, `alice`, `computer`, `hey_alfred` … `hey_rocky`, `ivy`, `pico`, `stop`, `timer`, `weather`); maßgeblich ist immer die Antwort des Servers.
* Die verfügbaren IDs stehen zusätzlich in `snapshot.wakeWordCapabilities`; Änderungen während der Session meldet `wakeword.availability_changed`.

## Wake-Word-Admission

`requestedSession.wakeWordIds` wird atomar geprüft; ein einziger Fehler
lehnt die ganze Session ab (`session.rejected`, Close `4409`):

| `errors[].code` | `errors[].reason` | Ursache |
| --- | --- | --- |
| `wake_word_selection_required` | – | `wakeWord: true`, aber leere Liste |
| `wake_word_selection_not_allowed` | – | `wakeWord: false`, aber IDs |
| `wake_word_unavailable` | `not_canonical` | Alias oder Anzeigename statt `id` |
| `wake_word_unavailable` | `unknown` | ID nicht im Katalog |
| `wake_word_unavailable` | `globally_disabled`, `artifact_*`, `pipeline_unavailable`, `runtime_unavailable` | Eintrag nicht verfügbar |
| `wake_word_unavailable` | `no_common_backend`, `backend_unavailable` | kein gemeinsames Inference-Backend für die ganze Auswahl |
| `wake_word_unavailable` | `catalog_unavailable` | Server ohne Katalog |

Doppelte IDs werden zusammengefasst. Nach der Annahme erkennt die Session
genau die gewählten Wake Words.

## Session-Settings

### Schlüssel

Die Session kennt 16 Schlüssel; sie stehen vollständig in
`requestedSettings`/`effectiveSettings` des Snapshots. Metadaten liefert
`GET /api/v2/settings/schema`, die aktuellen Serverdefaults
`GET /api/v2/settings/server`.

| Schlüssel | Typ / Grenzen | Default | Apply-Policy | per Session-Patch |
| --- | --- | --- | --- | --- |
| `activation.initialSpeechTimeoutMs` | int 100–3 600 000 ms | 15 000 | `next_activation` | ja |
| `activation.followupTimeoutMs` | int 100–60 000 ms | 3 000 | `next_activation` | ja |
| `activation.segmentWatchdogInitialMs` | int 60 000–3 600 000 ms | 600 000 | `next_activation` | ja |
| `activation.segmentWatchdogRefreshMs` | int 30 000–600 000 ms | 180 000 | `next_activation` | ja |
| `activation.segmentWatchdogWarningMs` | int ≥ 5 000 ms, **<** Initial **und** < Refresh | 30 000 | `next_activation` | ja |
| `activation.closingRecoveryTimeoutMs` | int 1 000–30 000 ms | 5 000 | `next_activation` | ja |
| `wakeWord.sensitivity` | float 0–1 | 0.5 | `next_activation` | ja |
| `wakeWord.minConsecutivePredictionFrames` | int ≥ 1 | 1 | `next_activation` | ja |
| `wakeWord.cooldownMs` | int ≥ 0 ms | 0 | `next_activation` | ja |
| `wakeWord.preRollMs` | int ≥ 0 ms | 0 | `next_activation` | ja |
| `wakeWord.detectorGain` | float 0–3 | 1.0 | `next_activation` | ja |
| `wakeWord.noiseSuppressionEnabled` | bool | false | `next_session` | ja (siehe unten) |
| `wakeWord.vadThreshold` | float 0–1 | 0.0 | `next_session` | ja (siehe unten) |
| `wakeWord.selection` | Liste | aus `hello` | `next_session` | ja (siehe unten) |
| `runtimeSuppression.manual` / `.wakeWord` | bool | aus `hello` | `live` | **nein** → `read_only_runtime_authority`; `trigger_suppression.set` verwenden |

Zusätzlich gibt es Server-Schlüssel (`wakeWord.inferenceBackend`,
`wakeWord.globalDisabledIds`), die nur Admins per
`PATCH /api/v2/settings/server` ändern; im Session-Patch → `wrong_scope`.
Mit `calibration: "pending"` markierte Werte sind Leitplanken, keine
empfohlenen Betriebswerte.

### Patch-Ablauf

```json
{"type": "session_settings.patch", "protocolVersion": 2,
 "sessionId": "…", "commandId": "…",
 "baseSettingsRevision": 0,
 "changes": {"activation.followupTimeoutMs": 4000, "wakeWord.sensitivity": 0.6}}
```

1. `baseSettingsRevision` muss der aktuellen Session-Revision entsprechen (anfangs `0`, danach aus Ack/Snapshot/`settings.changed`). Sonst `settings_revision_conflict`, `errors[0].code = stale_settings_revision`.
2. Der Patch ist atomar: ein Fehler verwirft alle Änderungen (`settings_rejected`, `errors[]` nach `field` sortiert).
3. Nur unveränderte Werte → `no_change`.
4. Wirksam → `applied`, Revision +1, dann je betroffener Apply-Policy ein `settings.changed` (Reihenfolge `live`, `next_activation`, `next_session`, `server_restart`; nur das erste erhöht `stateVersion`). Die Events kommen vor dem Ack.

| Fehlercode | Ursache |
| --- | --- |
| `unknown_key` | Schlüssel existiert nicht |
| `invalid_type` | falscher Typ (Bool ist nie eine Zahl) |
| `out_of_range` | außerhalb `min`/`max` |
| `too_few_items` | Liste zu kurz |
| `value_not_allowed` | nicht in `allowedValues` |
| `cross_field_conflict` | Watchdog-Warnung ≥ Initial- oder Refresh-Frist (gegen den finalen Kandidaten geprüft) |
| `wrong_scope` | Server-Schlüssel |
| `read_only_runtime_authority` | `runtimeSuppression.*` |
| `wake_word_selection_required` / `wake_word_unavailable` | ungültige `wakeWord.selection` |

### Wann ein Wert wirkt

* **`next_activation`:** ab der nächsten Activation. Eine laufende Activation behält die Werte, mit denen sie gestartet ist (`activation.started.effectiveSettings`). Im Snapshot zeigt `requestedSettings` sofort den neuen Wert, `effectiveSettings` bis zum Ende der laufenden Activation den alten.
* **`next_session`:** wird in der laufenden Session **nie** wirksam (`effectiveSettings` bleibt). Session-Settings werden nicht gespeichert; eine neue Verbindung beginnt wieder mit Serverdefaults. Eine andere Wake-Word-Auswahl oder Rauschunterdrückung erreicht der Client daher nur durch eine neue Verbindung mit passendem `hello` (Auswahl) bzw. – für `noiseSuppressionEnabled`/`vadThreshold` – derzeit nur über die Serverdefaults.
* **`live`:** nur die Suppression; sie wird über `trigger_suppression.set` geändert.

> **Bekannte Inkonsistenz (`IMPL-01`):** Im Session-Patch akzeptiert der
> Server für `wakeWord.selection` auch Aliase/Anzeigenamen und speichert sie
> unverändert, obwohl der Handshake nur kanonische IDs zulässt. Clients senden
> ausschließlich kanonische IDs. Siehe
> [`INDEPENDENT_REVIEW.md`](../audits/v2-client-contract-review/INDEPENDENT_REVIEW.md#implementierungsbefunde).

## Empfohlene Clientstruktur

```text
Settings-UI ──► lokales Profil (Trigger, Wake-Word-IDs, Timings)
                    │
                    ├─ beim Verbinden: hello.requestedSession / runtimeSuppression
                    ├─ nach hello.accepted: session_settings.patch (Timings, Sensitivität)
                    └─ Laufzeit: trigger_suppression.set, audio_availability.set
Katalog-Cache ◄── GET /api/v2/wake-words (+ wakeword.availability_changed)
```

* Wake-Word-Auswahl im UI über `displayName`, gespeichert als `id`.
* Nicht mehr verfügbare IDs vor dem `hello` aus der Auswahl entfernen oder den Nutzer fragen – sonst lehnt der Server die Session ab.
* Nach jedem Reconnect Timings erneut patchen.
