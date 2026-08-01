# Betriebsmodi und sessionlokale Wake-Word-Konfiguration

[← Protokollabgrenzung](08-protokollabgrenzung.md) · [Zur Übersicht](README.md)

## Zweck und aktueller Stand

Der Server unterstützt zwei typische Desktop-Betriebsarten über denselben
WebSocket-Endpunkt:

- einen durch Hotkey oder UI gesteuerten Aufnahmemodus ohne Wake Word;
- eine länger laufende Verbindung, in der OpenWakeWord serverseitig auf ein
  Wake Word wartet.

Der gewünschte Wake-Word-Modus kann beim Aufbau von `WS /ws/transcribe`
sessionlokal ausgewählt werden. Diese Auswahl verändert weder die globale
Serverkonfiguration noch andere bestehende oder später aufgebaute Sessions.
Die Admin-API bleibt für die serverweite Baseline zuständig.

Version 1 des sessionlokalen Contracts unterstützt ausschließlich
OpenWakeWord. Clients übergeben logische Modell-IDs, niemals Serverpfade.
Porcupine ist weder auswählbarer Session-Backend noch Teil des veröffentlichten
Wake-Word-Katalogs.

## Lebenszyklen

Eine WebSocket-Verbindung entspricht genau einer Session. `start` und `stop`
öffnen oder schließen nur eine Streamingphase innerhalb dieser Session.

```mermaid
flowchart TD
    A["WebSocket-Session<br/>connect → hello → ready → disconnect"]
    B["Streamingphase<br/>start → Audiopakete → stop"]
    C["Sprachsegment<br/>Wake Word/VAD → recording → final"]
    A --> B
    B --> C
    C -->|"weitere Äußerung"| C
```

Sessioneinstellungen werden vor dem Erzeugen des Recorders aus einem atomaren
Snapshot der Serverkonfiguration aufgelöst. Sie bleiben anschließend für die
gesamte Verbindung unverändert. Ein Moduswechsel benötigt daher einen
Reconnect; `start` oder `stop` lösen keine neue Konfigurationsauflösung aus.

## Die zwei empfohlenen Betriebsmodi

| Merkmal | Hotkey-Modus | Wake-Word-Modus |
| --- | --- | --- |
| Sessionparameter | `wakeWordEnabled=false` | `wakeWordEnabled=true` |
| WebSocket | vorzugsweise dauerhaft offen | dauerhaft offen |
| Mikrofon | nur während der Hotkeyphase | kontinuierlich |
| `start` | bei Aktivierung | einmal beim Aktivieren des Modus |
| `stop` | bei Ende der Hotkeyphase | nur beim Pausieren/Beenden |
| Trigger | Desktop-Client | OpenWakeWord, danach VAD |
| typischer Serverstatus | `idle` / `listening` | `wakeword_wait` |

### Hotkey-Modus

Empfohlener Verbindungsaufbau:

```text
wss://SERVER/ws/transcribe?wakeWordEnabled=false
```

Nach `hello` und einem erfolgreichen `ready` sendet der Client bei
Hotkeyaktivierung zuerst `{"type":"start"}` und erst danach PCM-Pakete. Beim
Loslassen stoppt er die Audioquelle, sendet das letzte vollständige Paket und
anschließend `{"type":"stop"}`. Nachlaufende `final`-Events müssen weiterhin
angenommen werden.

### Wake-Word-Modus

Mit dem serverweiten Standardmodell:

```text
wss://SERVER/ws/transcribe?wakeWordEnabled=true
```

Mit explizitem logischen Modell:

```text
wss://SERVER/ws/transcribe?wakeWordEnabled=true&wakeWords=hey_jarvis
```

Der Client sendet nach `ready` einmal `start` und anschließend kontinuierlich
Audio. Der Server übernimmt Wake-Word-Gate, VAD, Timeout und Follow-up. `stop`
ist für Pause oder Modusende vorgesehen, nicht für jedes Sprachsegment.

## Session-Create-Contract

Alle Werte werden als Queryparameter am WebSocket-Upgrade übergeben. Der
Contract ist versioniert und wird in `hello.sessionCapabilities` sowie
`ready.sessionCapabilities` beschrieben.

| Queryparameter | Typ/Werte | Bedeutung |
| --- | --- | --- |
| `wakeWordEnabled` | `true`, `false`, `null`, `inherit` | entscheidender Tri-State-Schalter |
| `wakeWordBackend` | `openwakeword` | optionaler Backendwunsch |
| `wakeWords` | kommaseparierte Modell-IDs | gewünschte Wake Words aus dem Serverkatalog |
| `wakeWordInferenceFramework` | `onnx`, `tflite` | gewünschtes lokal verfügbares Modellformat |
| `wakeWordSensitivity` | `0.0`–`1.0` | Erkennungsschwelle |
| `wakeWordActivationDelay` | `0.0`–`3600.0` s | Verzögerung bis zum Wake-Word-Gate |
| `wakeWordTimeout` | `0.0`–`3600.0` s | Sprach-Timeout nach Erkennung |
| `wakeWordBufferDuration` | `0.0`–`60.0` s | Wake-Word-Puffer |
| `wakeWordFollowupWindow` | `0.0`–`3600.0` s | Follow-up-Fenster |

Querywerte müssen URL-kodiert werden. `wakeWordEnabled` darf unabhängig vom
Modus höchstens einmal vorkommen. Bei `wakeWordEnabled=true` dürfen auch die
übrigen Wake-Word-Felder nicht mehrfach vorkommen; mehrdeutige Angaben führen
vor der Sessionaufnahme zu einem Konfigurationsfehler. Im Modus `inherit` oder
`false` werden zusätzliche Wake-Word-Felder nicht angewendet und als ignoriert
bestätigt.

### `wakeWordEnabled` fehlt, ist `null` oder `inherit`

Die vollständige Wake-Word-Konfiguration wird aus der Serverbaseline kopiert.
Mitgesendete Wake-Word-Felder werden absichtlich ignoriert und erscheinen in
`sessionConfig.ignoredFields`.

Ein ungültiger Wert wie `flase` wird sicherheitshalber ebenfalls als
„Baseline übernehmen“ behandelt. Der Handshake meldet dafür einen sichtbaren
Fallback und eine Warnung, damit ein Clientfehler nicht unbemerkt bleibt.

### `wakeWordEnabled=false`

Wake Word wird nur für diese Session deaktiviert. Backend, Wörter und interne
Modellpfade werden in der Sessionkopie geleert. Weitere Wake-Word-Parameter
werden ohne Fehler ignoriert und in `ignoredFields` zurückgemeldet.

### `wakeWordEnabled=true`

Die Auflösung folgt diesen Regeln:

1. Ohne weitere Angaben wird ein bereits vollständiges serverweites
   OpenWakeWord-Profil übernommen.
2. Ist keine verwendbare Baseline aktiv, wird `default_model` aus
   `models.json` verwendet.
3. Bei `wakeWordBackend=openwakeword` ohne `wakeWords` wird ebenfalls das
   Manifest-Standardmodell verwendet.
4. Angegebene Modell-IDs werden ohne Beachtung der Groß-/Kleinschreibung gegen
   den serverseitigen Katalog aufgelöst.
5. Gültige Tuningwerte überschreiben die entsprechenden Baselinewerte.

Ungültige optionale Werte erzeugen keinen Abbruch, solange ein vollständiges
Fallback-Profil gebildet werden kann:

- ungültiges Backend: OpenWakeWord bzw. Baseline;
- unbekanntes Wake Word: aktives OpenWakeWord-Baselineprofil, sonst
  Manifest-Standardmodell;
- ungültiger Tuningwert: entsprechender Wert der Serverbaseline.

Jeder Fallback wird in `sessionConfig.fallbacks` und
`sessionConfig.warnings` offengelegt. Kann `wakeWordEnabled=true` auch nach
Fallback nicht mit einem lokalen Modell erfüllt werden, sendet der Server
`error` mit `where: "session_config"` und schließt mit Code `1008`.

## Effektive Konfiguration im Handshake

`hello` und `ready` liefern dieselbe effektive Sessionkonfiguration:

```json
{
  "type": "hello",
  "sessionId": "…",
  "settings": {
    "wake_word_enabled": true,
    "wakeword_backend": "openwakeword",
    "wake_words": "hey_jarvis",
    "wake_words_sensitivity": 0.42
  },
  "sessionConfig": {
    "version": 1,
    "requestedWakeWordEnabled": true,
    "effectiveWakeWordEnabled": true,
    "effectiveWakeWordBackend": "openwakeword",
    "effectiveWakeWords": ["hey_jarvis"],
    "source": "session",
    "fallbacks": [],
    "ignoredFields": [],
    "warnings": [],
    "requestedFields": ["wakeWords"]
  },
  "sessionCapabilities": {
    "version": 1,
    "wakeWord": {
      "supported": true,
      "backends": ["openwakeword"],
      "availableWakeWords": [
        {
          "id": "hey_jarvis",
          "label": "Hey Jarvis",
          "availableFormats": ["onnx"],
          "default": false
        }
      ]
    }
  }
}
```

`settings` enthält keine lokalen Modellpfade. Auch
`sessionCapabilities.availableWakeWords` veröffentlicht nur logische IDs,
Formate und Anzeigenamen. Pfade bleiben ein internes Serverdetail.

Der Client muss seinen gewünschten Modus immer gegen
`sessionConfig.effectiveWakeWordEnabled` prüfen. Nicht die lokal konstruierte
URL, sondern der Handshake ist die maßgebliche Bestätigung.

## `models.json` als Modellkatalog

Beim Start beziehungsweise bei der Sessionauflösung sucht der Server zuerst
nach `models.json`:

- in `VOICESTT_OPENWAKEWORD_MODEL_ROOT`;
- im Verzeichnis eines konfigurierten Modellpfads;
- oder direkt unter einem als `openwakeword_model_paths` angegebenen
  Manifestpfad.

Eine Verzeichnisangabe ist ebenfalls zulässig. Fehlt ein verwendbares
Manifest, bleibt als Kompatibilitätsfallback der lokale Scan nach `.onnx`- und
`.tflite`-Dateien bestehen.

Relevanter Ausschnitt:

```json
{
  "openwakeword_models": {
    "path": "/models/openwakeword/all_models",
    "default_model": "alexa",
    "pipeline_models": {
      "embedding_model_onnx": "embedding_model.onnx",
      "melspectrogram_onnx": "melspectrogram.onnx"
    },
    "onnx_models": {
      "alexa": "alexa.onnx",
      "hey_jarvis": "jarvis_v2.onnx"
    },
    "tflite_models": {
      "alexa": "alexa.tflite"
    }
  }
}
```

Nur Einträge, deren Dateien tatsächlich existieren, werden veröffentlicht.
Pipeline- und Supportmodelle wie `embedding_model`, `melspectrogram` und
`silero_vad` erscheinen nicht als auswählbare Wake Words. Relative Pfade
werden relativ zum Manifest aufgelöst; ein im Manifest deklarierter, aber in
der aktuellen Umgebung nicht erreichbarer Basispfad fällt auf den
konfigurierten Modellordner beziehungsweise den Manifestordner zurück.

`default_model` muss auf eine vorhandene logische ID zeigen. Das Manifest wird
zur Laufzeit ausschließlich gelesen; VoiceSTT lädt keine Modelle aus dem Netz.

## Serverbaseline und Admin-API

Die folgenden Endpunkte benötigen bei konfiguriertem Adminschlüssel
`X-VoiceSTT-Admin-Key`:

| Endpunkt | Zweck | Wirkung |
| --- | --- | --- |
| `GET /api/wake-word` | Baseline und verfügbaren Katalog lesen | keine |
| `PUT /api/wake-word` | Baseline aktivieren/deaktivieren und abstimmen | nur neue Sessions |
| `PATCH /api/config` | generische Laufzeitkonfiguration | gemäß `appliesTo` |

`PUT /api/wake-word` akzeptiert für Aktivierung nur OpenWakeWord. `words`
enthält logische IDs; leer bedeutet Manifest-Standardmodell. Optional kann
`openwakewordModelPaths` als Suchquelle einen Modellpfad, einen Modellordner
oder `models.json` angeben. Persistiert werden die aufgelösten lokalen
Klassifikatorpfade.

Sessionlokale Queryparameter ändern die Baseline nicht und benötigen im
aktuellen Protokoll keinen Admin-Key. Der WebSocket-Endpunkt selbst besitzt
derzeit keine eingebaute Authentifizierung. Bei externer Erreichbarkeit müssen
TLS, Zugriffsschutz, Connection-/Rate-Limits und gegebenenfalls Authentisierung
am Reverse Proxy umgesetzt werden.

## Empfohlene Clientstruktur

Der Desktop-Client sollte drei getrennte Bereiche führen:

1. **Aufnahmemodus:** Hotkey oder Wake Word; erzeugt ausschließlich
   sessionlokale Queryparameter.
2. **Wake-Word-Profil:** Modell-ID und optionale Tuningwerte aus
   `sessionCapabilities`.
3. **Serveradministration:** Baseline und andere Adminwerte; getrennt,
   ausdrücklich global und mit Admin-Key.

Der Admin-Key gehört in den Secret Store des Betriebssystems, nicht in
Konfigurationsdateien, Logs, URLs oder Telemetrie. Für den normalen
Moduswechsel wird er nicht benötigt.

Minimaler Verbindungsalgorithmus:

1. Modus und optionale Wake-Werte lokal festlegen.
2. WebSocket-URL mit `URLSearchParams` erzeugen.
3. Verbindung öffnen und `hello` abwarten.
4. `fallbacks`, `warnings` und `ignoredFields` auswerten.
5. Effektiven Modus und Modell-IDs gegen die Benutzerwahl prüfen.
6. `ready.ok === true` abwarten.
7. Im Hotkeymodus ereignisgesteuert, im Wake-Word-Modus einmalig `start`
   senden.
8. Bei Modusänderung alte Session sauber stoppen und eine neue Verbindung
   aufbauen.

## Fehler- und Reconnect-Regeln

| Situation | Serververhalten | Clientreaktion |
| --- | --- | --- |
| kein lokales Fallbackmodell | `error`, `where=session_config`, Close `1008` | Konfiguration anzeigen, nicht blind wiederholen |
| doppelter Queryparameter | `error`, Close `1008` | URL-Erzeugung korrigieren |
| Sessionlimit | `error`, `where=admission`, Close `1013` | begrenztes Backoff |
| Warnung/Fallback | normale Session mit `hello` | effektiv aufgelösten Wert anzeigen |
| Verbindungsabbruch | Session wird verworfen | neue Session mit denselben gewünschten Parametern |

Ein Client darf bei einem deterministischen `1008`-Fehler keine schnelle
Reconnectschleife starten. Fallbacks sollten in der UI mindestens als
Statushinweis sichtbar sein, weil die Session zwar verwendbar ist, aber nicht
exakt der angeforderten Konfiguration entspricht.

## Abnahmecheckliste

- Hotkey- und Wake-Word-Session können gleichzeitig mit unterschiedlichen
  effektiven Profilen laufen.
- Das Öffnen oder Schließen einer Session verändert `GET /api/wake-word`
  nicht.
- `false` deaktiviert Wake Word auch bei aktivierter Serverbaseline.
- fehlend/`null`/`inherit` übernimmt die Baseline unverändert.
- `true` ohne weitere Werte nutzt Baseline oder `default_model`.
- logische Modell-IDs werden case-insensitiv aufgelöst.
- unbekannte IDs und ungültige Tuningwerte erzeugen sichtbare Fallbacks.
- ein fehlendes Fallbackmodell wird vor der eigentlichen Session abgelehnt.
- `hello` und `ready` melden identische Sessionkonfiguration.
- keine Modellpfade erscheinen im öffentlichen WebSocket-Handshake.
- parallele Adminänderungen erzeugen keinen gemischten Settings-Snapshot.
- Reconnect und Moduswechsel hinterlassen keine alte aktive Session.

## Zusammenfassung

Der Desktop-Client muss für einen Moduswechsel keine serverweite Einstellung
mehr umschalten. `wakeWordEnabled` ist der verbindliche sessionlokale
Schalter, alle weiteren Wake-Word-Werte sind optionale Overrides. Die
Serverbaseline bleibt Default und Fallback, `models.json` liefert die sicheren
logischen Modell-IDs und internen Pfade, und der Handshake bestätigt stets die
tatsächlich wirksame Konfiguration.
