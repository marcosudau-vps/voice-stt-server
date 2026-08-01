# Sitzungslokale Wake-Word-Konfiguration

## Zweck und aktueller Stand

Diese Dokumentation beschreibt die mit dem Branch
`codex/session-wakeword-config` eingeführte Erweiterung des
VoiceSTT-Multi-User-Servers. Die Erweiterung ist in `main` integriert und
ermöglicht jedem WebSocket-Client, beim Verbindungsaufbau einen eigenen
Wake-Word-Modus anzufordern.

Der Implementierungsstand ist vollständig:

- Der WebSocket-Handshake besitzt einen versionierten Session-Contract.
- Wake Word kann pro Sitzung geerbt, aktiviert oder deaktiviert werden.
- Session-Änderungen verändern nicht die globale Serverkonfiguration.
- OpenWakeWord-Modelle werden über logische IDs aus `models.json` aufgelöst.
- Ungültige optionale Angaben erzeugen sichtbare Fallbacks und Warnungen.
- Nicht erfüllbare Aktivierungswünsche werden vor der Audioverarbeitung
  eindeutig abgelehnt.
- `hello` und `ready` bestätigen die tatsächlich wirksame Konfiguration.
- Der Vertrag und die Isolation mehrerer Sessions sind durch automatisierte
  Tests abgedeckt.

Die FastAPI-Anwendung meldet derzeit API-Version `2.0.0`. Der neue
Session-Wake-Word-Contract hat unabhängig davon die Contract-Version `1`.

Die unveränderten ursprünglichen Planungsunterlagen bleiben separat erhalten:

- [ursprünglicher Prüf- und Implementierungsbericht](archive/session-wakeword-planung/SERVER_SESSION_PROFILE_IMPLEMENTATION_REPORT.md)
- [ursprüngliche Anforderungsspezifikation](archive/session-wakeword-planung/SERVER_SESSION_PROFILE_SPECIFICATION.md)
- [Archivhinweise und SHA-256-Prüfsummen](archive/session-wakeword-planung/README.md)

## Ausgangslage

Vor der Erweiterung war die Wake-Word-Konfiguration im Wesentlichen eine
serverweite Baseline. Alle neu verbundenen Clients übernahmen Backend, Modell,
Empfindlichkeit und Timeout aus derselben Serverkonfiguration.

Das war für einen einzelnen Client ausreichend, führte bei mehreren
unterschiedlichen Clients aber zu einem grundsätzlichen Problem:

- Ein Hotkey-Client möchte Audio sofort über VAD verarbeiten.
- Ein dauerhaft lauschender Client möchte zuerst auf „Hey Jarvis“ warten.
- Ein Testclient möchte eine abweichende Empfindlichkeit verwenden.
- Eine Änderung für einen Client darf andere aktive Sessions nicht verändern.

Eine globale Umschaltung über `PUT /api/wake-word` kann diese Anforderungen
nicht sicher erfüllen. Sie ist weiterhin für die Baseline neuer Sessions
zuständig, aber nicht mehr der einzige mögliche Betriebsmodus.

## Zielbild

Jede WebSocket-Verbindung erhält beim Aufbau eine private Kopie der relevanten
Servereinstellungen. Der Client kann ausschließlich für diese Kopie einen
Wake-Word-Wunsch angeben.

```text
Server-Baseline
      |
      +-- Session A: Baseline erben
      |
      +-- Session B: Wake Word deaktivieren
      |
      +-- Session C: OpenWakeWord mit eigener Empfindlichkeit
```

Die globale Baseline bleibt unverändert. Neue oder bereits aktive Sessions
beeinflussen sich nicht gegenseitig.

## Konfigurationsebenen

### Versionierte Startkonfiguration

Die Root-Datei `config.yaml` enthält die eingecheckte Serverbaseline. Dazu
gehören beispielsweise:

- Wake-Word-Backend und Standardmodell;
- Empfindlichkeit und Timeout;
- Follow-up-Fenster;
- Modellpfad beziehungsweise logische Modell-ID;
- Server-, Modell- und Kapazitätseinstellungen.

Secrets stehen ausschließlich in der nicht versionierten Root-Datei `.env`.

### Persistierte Runtime-Konfiguration

Administrative Endpunkte können die Baseline für zukünftige Sessions ändern.
Wenn `data_root_path` gesetzt ist, werden erlaubte Runtime-Werte ohne Secrets
unter `<data_root_path>/config/runtime.json` persistiert.

### Sitzungslokale Konfiguration

Die WebSocket-Queryparameter werden genau einmal beim Verbindungsaufbau
ausgewertet. Das Ergebnis gilt nur für die neue Session und wird nicht in die
globale Runtime-Konfiguration zurückgeschrieben.

## WebSocket-Endpunkt

```text
WS /ws/transcribe
```

Beispiele:

```text
# Serverbaseline übernehmen
wss://SERVER/ws/transcribe

# Wake Word ausschließlich für diese Session deaktivieren
wss://SERVER/ws/transcribe?wakeWordEnabled=false

# Wake Word aktivieren und logisches Modell auswählen
wss://SERVER/ws/transcribe?wakeWordEnabled=true&wakeWords=hey_jarvis

# Modell und Empfindlichkeit sitzungslokal festlegen
wss://SERVER/ws/transcribe?wakeWordEnabled=true&wakeWords=hey_jarvis&wakeWordSensitivity=0.42
```

Querywerte müssen URL-kodiert werden.

## Session-Create-Contract

| Queryparameter | Wertebereich | Bedeutung |
| --- | --- | --- |
| `wakeWordEnabled` | `true`, `false`, `null`, `inherit` | Tri-State-Schalter für den Sessionmodus |
| `wakeWordBackend` | `openwakeword` | gewünschtes Wake-Word-Backend |
| `wakeWords` | kommaseparierte IDs | logische Modelle aus dem Serverkatalog |
| `wakeWordInferenceFramework` | `onnx`, `tflite` | gewünschtes Modellformat |
| `wakeWordSensitivity` | `0.0`–`1.0` | Erkennungsschwelle |
| `wakeWordActivationDelay` | `0.0`–`3600.0` Sekunden | Verzögerung bis zum Wake-Word-Gate |
| `wakeWordTimeout` | `0.0`–`3600.0` Sekunden | Zeit für Sprache nach Erkennung |
| `wakeWordBufferDuration` | `0.0`–`60.0` Sekunden | Puffer um das erkannte Wake Word |
| `wakeWordFollowupWindow` | `0.0`–`3600.0` Sekunden | Zeitfenster für direkte Folgeäußerungen |

`wakeWordEnabled` darf höchstens einmal vorkommen. Bei expliziter Aktivierung
dürfen auch die übrigen Sessionfelder nicht mehrfach vorkommen. Mehrdeutige
Angaben werden mit einem Session-Konfigurationsfehler und WebSocket-Code `1008`
abgelehnt.

## Tri-State-Verhalten

### Baseline erben

Wenn `wakeWordEnabled` fehlt, `null` oder `inherit` ist, übernimmt die Session
die vollständige Serverbaseline.

Zusätzlich übergebene Wake-Word-Felder werden in diesem Modus nicht heimlich
angewendet. Sie erscheinen in `sessionConfig.ignoredFields`.

Ein Tippfehler wie `wakeWordEnabled=flase` wird aus Sicherheitsgründen wie
„Baseline übernehmen“ behandelt. Der Handshake enthält dann einen Fallback und
eine Warnung, sodass der Fehler für den Client sichtbar bleibt.

### Wake Word deaktivieren

Mit `wakeWordEnabled=false` werden Backend, Wörter und interne Modellpfade nur
in der Sessionkopie geleert. Die Serverbaseline und andere Sessions bleiben
unverändert.

Weitere Wake-Word-Parameter sind in diesem Modus wirkungslos und werden in
`ignoredFields` bestätigt.

### Wake Word aktivieren

Mit `wakeWordEnabled=true` versucht der Server, ein vollständiges lokales
OpenWakeWord-Profil zu bilden:

1. Ein vollständiges OpenWakeWord-Baselineprofil wird übernommen.
2. Ohne verwendbare Baseline wird das `default_model` aus `models.json`
   verwendet.
3. Eine angegebene logische Modell-ID wird gegen den lokalen Katalog
   aufgelöst.
4. Gültige Tuningwerte überschreiben die geerbten Werte.
5. Ungültige optionale Werte fallen sichtbar auf Baseline oder Standardmodell
   zurück.

Ist trotz Fallback kein lokales Modell verfügbar, sendet der Server ein
`error`-Ereignis mit `where: "session_config"` und schließt die Verbindung mit
Code `1008`.

## Verbindlicher Handshake

Der Client darf nicht allein aus seiner angeforderten URL ableiten, welcher
Modus tatsächlich aktiv ist. Maßgeblich ist ausschließlich die Antwort des
Servers.

Ein `hello` der neuen Version enthält:

```json
{
  "type": "hello",
  "sessionId": "…",
  "settings": {
    "wake_word_enabled": false,
    "wakeword_backend": "",
    "wake_words": ""
  },
  "sessionConfig": {
    "version": 1,
    "requestedWakeWordEnabled": false,
    "effectiveWakeWordEnabled": false,
    "effectiveWakeWordBackend": "",
    "effectiveWakeWords": [],
    "source": "session",
    "fallbacks": [],
    "ignoredFields": ["wakeWords"],
    "warnings": [],
    "requestedFields": ["wakeWords"]
  },
  "sessionCapabilities": {
    "version": 1,
    "wakeWord": {
      "supported": true,
      "backends": ["openwakeword"],
      "queryParameters": [
        "wakeWordEnabled",
        "wakeWordBackend",
        "wakeWords"
      ]
    }
  }
}
```

`ready` enthält dieselbe `sessionConfig` und dieselben
`sessionCapabilities`. Ready-Nachrichten werden sitzungsspezifisch erzeugt und
können dadurch nicht versehentlich das Profil einer anderen Session enthalten.

## Bedeutung der Antwortfelder

| Feld | Bedeutung |
| --- | --- |
| `requestedWakeWordEnabled` | vom Client angeforderter Tri-State-Wert |
| `effectiveWakeWordEnabled` | tatsächlich wirksamer Sessionmodus |
| `effectiveWakeWordBackend` | tatsächlich verwendetes Backend |
| `effectiveWakeWords` | aufgelöste logische Modell-IDs |
| `source` | `server` bei Vererbung oder `session` bei expliziter Wahl |
| `fallbacks` | maschinenlesbare ersetzte Eingaben |
| `ignoredFields` | bewusst nicht angewendete Queryfelder |
| `warnings` | für Benutzer oder Logs geeignete Warnungen |
| `requestedFields` | ausdrücklich mitgesendete Tuning-/Modellfelder |

Ein Client sollte mindestens prüfen:

1. `sessionConfig.version`;
2. `sessionConfig.effectiveWakeWordEnabled`;
3. `fallbacks` und `warnings`;
4. bei Aktivierung `effectiveWakeWords`;
5. `sessionCapabilities.wakeWord.supported`.

## OpenWakeWord-Modellkatalog

Die Erweiterung trennt öffentliche Modell-IDs von internen Dateipfaden.

Der Server sucht `models.json`:

- im konfigurierten OpenWakeWord-Modellroot;
- im Verzeichnis eines angegebenen Modells;
- direkt über einen als `openwakeword_model_paths` gesetzten Manifestpfad.

Ein Manifest kann Modelle, Formate, Pipeline-Abhängigkeiten und ein
Standardmodell beschreiben. Nach außen veröffentlicht der Server nur:

- logische ID;
- Anzeigename;
- verfügbare Formate;
- Kennzeichnung des Standardmodells.

Interne Host- oder Containerpfade werden weder in `settings` noch in
`sessionCapabilities` veröffentlicht.

Fehlt ein verwendbares Manifest, bleibt aus Kompatibilitätsgründen der lokale
Scan nach `.onnx`- und `.tflite`-Dateien möglich.

## Globale Administration

`GET /api/wake-word` zeigt die aktuelle Baseline und den lokal verfügbaren
Modellkatalog.

`PUT /api/wake-word` ändert die Baseline für neue Sessions. Bereits aktive
Sessions behalten ihre eigene Kopie.

`GET /api/config` enthält zusätzlich den neuen öffentlichen
`sessionCapabilities`-Vertrag. Dieser Endpunkt eignet sich für eine schnelle
Feature-Erkennung ohne WebSocket-Verbindung.

## Sitzungsisolation

Die Auflösung findet vor der Aufnahme der Session in den Connection Manager
statt. Jede Session besitzt danach eigene `ServerSettings` und eine eigene
`ResolvedSessionWakeWordConfig`.

Dadurch gelten folgende Garantien:

- Deaktivieren in Session A deaktiviert Wake Word nicht in Session B.
- Tuningwerte einer Session verändern keine globalen Werte.
- Das Schließen einer Session verändert den Modellkatalog nicht.
- `hello` und `ready` werden aus derselben Sessionkonfiguration erzeugt.
- Ein ungültiger Sessionwunsch wird abgelehnt, bevor Audio verarbeitet wird.

Die ASR-Modelle und Scheduler-Ressourcen bleiben weiterhin serverweit geteilt.
Sitzungslokal ist die Steuerung des Aufnahme- und Wake-Word-Verhaltens, nicht
eine vollständige private Kopie aller geladenen Modelle.

## Zustandsablauf

Eine aktivierte Wake-Word-Session läuft typischerweise durch:

```text
hello
  -> ready
  -> start
  -> wakeword_wait
  -> wakeword_detected
  -> voice / recording
  -> transcribing
  -> final
  -> wakeword_wait oder Follow-up-Fenster
```

Auch in `wakeword_wait` muss der Client kontinuierlich PCM-Audio senden. Das
Wake Word wird serverseitig im eingehenden Audiostrom erkannt.

Mit einem positiven `wakeWordFollowupWindow` kann der Server nach einer
erfolgreichen Äußerung vorübergehend weitere Sprache ohne neues Wake Word
zulassen. Der Ablauf wird durch Timeline-Ereignisse wie
`wakeword_followup_started` und `wakeword_followup_timeout` sichtbar.

## Fehler- und Fallbackmodell

### Harte Fehler

Harte Fehler verhindern eine eindeutige oder erfüllbare Session:

- mehrfach angegebene eindeutige Parameter;
- keine lokale Wake-Word-Implementierung trotz expliziter Aktivierung;
- keine auflösbare Baseline und kein Standardmodell;
- interner Initialisierungsfehler.

### Weiche Fallbacks

Weiche Fehler werden ersetzt und im Handshake offengelegt:

- ungültiger Tri-State-Wert;
- unbekanntes optionales Backend;
- unbekannte Modell-ID bei vorhandener Baseline oder Standardmodell;
- Tuningwert außerhalb des zulässigen Bereichs.

Clients sollten Fallbacks protokollieren. Bei sicherheits- oder
bedienkritischen Anwendungen kann der Client die Session selbst schließen,
wenn der effektive Modus nicht exakt dem gewünschten Modus entspricht.

## PowerShell-Nachweis

### Schneller HTTP-Nachweis

Dieser Test prüft, ob der laufende Server den neuen Vertrag veröffentlicht:

```powershell
$BaseUrl = "http://localhost:8010"
$OpenApi = Invoke-RestMethod "$BaseUrl/openapi.json"
$Config = Invoke-RestMethod "$BaseUrl/api/config"

$HasSessionContract =
    $Config.sessionCapabilities.version -ge 1 -and
    $Config.sessionCapabilities.wakeWord.queryParameters -contains "wakeWordEnabled"

[pscustomobject]@{
    ApiVersion = $OpenApi.info.version
    SessionContractVersion = $Config.sessionCapabilities.version
    WakeWordSessionContract = $HasSessionContract
    Backends = $Config.sessionCapabilities.wakeWord.backends -join ", "
}

if (-not $HasSessionContract) {
    throw "Der neue Session-Wake-Word-Contract ist nicht aktiv."
}
```

Erwartet werden mindestens:

```text
ApiVersion              2.0.0
SessionContractVersion  1
WakeWordSessionContract True
Backends                openwakeword
```

Dieser Nachweis bestätigt, dass der laufende Prozess die neue Erweiterung
kennt. Er prüft noch nicht, ob die sitzungslokale Auflösung korrekt antwortet.

### Vollständiger WebSocket-Nachweis

Das Repository enthält dafür:

```powershell
.\tools\verify_session_wakeword.ps1 -BaseUrl "http://localhost:8010"
```

Für den VPS:

```powershell
.\tools\verify_session_wakeword.ps1 `
  -BaseUrl "https://voice.marcosudau.com"
```

Das Skript:

1. prüft die FastAPI-Version;
2. prüft `GET /api/config`;
3. öffnet eine echte WebSocket-Session;
4. fordert `wakeWordEnabled=false` an;
5. sendet zusätzlich ein absichtlich wirkungsloses `wakeWords`;
6. prüft `hello.sessionConfig`;
7. erwartet `effectiveWakeWordEnabled=false`;
8. erwartet `wakeWords` in `ignoredFields`.

Damit wird nicht nur eine Versionsnummer, sondern das tatsächliche Verhalten
der neuen Sessionauflösung nachgewiesen.

## Deployment-Nachweis

Nach einem Update sollte der Container neu gebaut und ersetzt werden:

```powershell
git switch main
git pull
python .\tools\compose.py up --build --force-recreate -d
python .\tools\compose.py ps
```

Danach folgt der PowerShell-Nachweis:

```powershell
.\tools\verify_session_wakeword.ps1 -BaseUrl "http://localhost:8010"
```

Ein vorhandenes Image allein beweist nicht, dass der Container bereits daraus
neu erstellt wurde. Der API-/WebSocket-Test fragt den tatsächlich laufenden
Prozess ab und ist deshalb der bessere Nachweis.

## Automatisierte Testabdeckung

Die Implementierung wird unter anderem geprüft auf:

- Parsing und Validierung der Queryparameter;
- Tri-State-Verhalten;
- Aktivierung, Deaktivierung und Vererbung;
- Sessionisolation bei unterschiedlichen Clients;
- Fallbacks für Backend, Modell und Tuning;
- unbekannte beziehungsweise nicht verfügbare Modelle;
- identische Sessionkonfiguration in `hello` und `ready`;
- sitzungsspezifische Ready-Nachrichten;
- OpenWakeWord-Katalog und `models.json`;
- Wake-Word-Status- und Timeline-Ereignisse;
- Follow-up-Fenster;
- unveränderte globale Baseline.

Die maßgeblichen Tests liegen in:

- `tests/unit/test_fastapi_server_protocol.py`;
- `tests/unit/test_fastapi_server_multi_user.py`;
- `tests/unit/test_server_operations.py`;
- `tests/unit/test_wakeword.py`.

## Grenzen

- Der Session-Create-Contract wird nur beim WebSocket-Aufbau ausgewertet. Für
  einen Moduswechsel wird eine neue Session empfohlen.
- Der Sessionvertrag unterstützt derzeit OpenWakeWord. Porcupine wird nicht im
  öffentlichen Sessionkatalog angeboten.
- Ein Client muss Audio auch während des Wartens kontinuierlich senden.
- API-Version und Session-Contract-Version sind getrennt zu betrachten.
- `/openapi.json` allein beweist nur die API-Version. Für den eindeutigen
  Feature-Nachweis müssen `sessionCapabilities` oder der WebSocket-Handshake
  geprüft werden.

## Weiterführende Dokumentation

- [Betriebsmodi und Serverkonfiguration](client-development/09-betriebsmodi-und-serverkonfiguration.md)
- [WebSocket-Protokoll](client-development/02-websocket-protokoll.md)
- [Serverereignisse](client-development/04-server-events-katalog-und-chronologie.md)
- [HTTP-API und Authentifizierung](client-development/06-http-api-und-authentifizierung.md)
- [Wake Words](wake-words.md)
- [FastAPI-Server](fastapi-server.md)
