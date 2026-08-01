# Server-Anforderung – konfigurierbare Sessionprofile

> **Status:** verbindliche Client-Anforderung an eine noch nicht implementierte Servererweiterung  
> **Version:** 1.0  
> **Stand:** 25. Juli 2026  
> **Wichtig:** Dieses Dokument beschreibt den gewünschten zukünftigen Vertrag. Der aktuell implementierte Serververtrag unter `server-docs-for-client-development/` bleibt bis zur tatsächlichen Serveränderung maßgeblich.

## 1. Ziel

Jede neue WebSocket-Session soll beim Verbindungsaufbau ein benanntes, serverseitig definiertes Sessionprofil auswählen können. Dadurch müssen mindestens diese beiden Sitzungen gleichzeitig und ohne globale Umschaltung möglich sein:

- `direct_hotkey`: Nach `start` wird Sprache sofort erkannt; kein Wake Word erforderlich.
- `wake_word`: Nach `start` läuft die Audioübertragung dauerhaft, der Recorder bleibt jedoch bis zur Wake-Word-Erkennung gesperrt.

Die Profilauswahl darf keine globale Serverkonfiguration verändern und keine bereits laufende Session beeinflussen.

## 2. Sicherheits- und Architekturentscheidung

Der WebSocket-Endpunkt ist derzeit nicht mit einem Admin-Token geschützt. Deshalb darf ein normaler Client **keine beliebigen Recorder-, Modell-, Pfad-, Logging- oder Ressourcenparameter** senden.

Version 1 verwendet ausschließlich:

```text
Client wählt eine Profil-ID
→ Server validiert die ID
→ Server lädt eine vertrauenswürdige serverseitige Profildefinition
→ Server kopiert die effektiven Werte in genau diese neue Session
```

Nicht zulässig:

- Admin-API-Key im Desktop-Client,
- freie JSON-Overrides aus dem WebSocket-Client,
- Dateisystempfade oder Modellpfade vom Client,
- Modell-/Enginewechsel durch die Profilauswahl,
- Änderung globaler Limits, Logs oder Speicherregeln,
- nachträgliche Mutation eines Profils innerhalb einer laufenden Session.

## 3. Client-Konfiguration

Der Client besitzt ab sofort:

```yaml
session:
  mode: direct_hotkey
```

Zulässige Werte:

| Wert | Bedeutung |
|---|---|
| `direct_hotkey` | Aufnahme nach `start` ohne Wake-Word-Gate |
| `wake_word` | kontinuierliche Audioübertragung, Freigabe durch Wake Word |

Bis der Server diesen Vertrag implementiert, wird der Wert noch nicht an den Server gesendet. Der Client vergleicht ihn lediglich mit `hello.settings.wake_word_enabled` und warnt bei einer Abweichung.

Nach der Serverimplementierung wird `session.mode` eins zu eins auf die gleichnamige Serverprofil-ID abgebildet.

## 4. Verbindungs- und Protokollvertrag

### 4.1 Profilauswahl

Der Client verbindet sich künftig mit:

```text
wss://stt.voice.marcosudau.com/ws/transcribe?sessionProfile=direct_hotkey
```

beziehungsweise:

```text
wss://stt.voice.marcosudau.com/ws/transcribe?sessionProfile=wake_word
```

Regeln:

- Queryparametername: `sessionProfile`
- Kodierung: UTF-8 und reguläres URL-Encoding
- zulässige Profil-ID: `^[a-z][a-z0-9_-]{0,63}$`
- der Parameter darf höchstens einmal vorkommen
- fehlt er, verwendet der Server `default_session_profile`
- die Auswahl muss **vor Erzeugung des sessioneigenen Recorders** erfolgen
- bei Reconnect sendet der Client das konfigurierte Profil erneut; die neue `sessionId` erhält eine frische Profilkopie

Ein Queryparameter ist hier nur ein Profilselektor. Er ist kein Secret und kein Authentifizierungsersatz.

### 4.2 Erfolgreiches `hello`

`hello` erhält zusätzlich:

```json
{
  "type": "hello",
  "sessionId": "…",
  "settings": {
    "language": "de",
    "wake_word_enabled": false
  },
  "sessionConfig": {
    "version": 1,
    "requestedProfile": "direct_hotkey",
    "appliedProfile": "direct_hotkey",
    "activationMode": "direct_hotkey",
    "wakeWordEnabled": false
  }
}
```

Pflichtfelder in `sessionConfig`:

| Feld | Typ | Bedeutung |
|---|---|---|
| `version` | Integer | Protokollversion, zunächst `1` |
| `requestedProfile` | String oder `null` | Querywert; `null`, wenn keiner gesendet wurde |
| `appliedProfile` | String | tatsächlich verwendete Profil-ID |
| `activationMode` | `"direct_hotkey"` oder `"wake_word"` | normalisierte Aktivierungssemantik |
| `wakeWordEnabled` | Boolean | effektiver Recorderzustand |

Die direkte, sessionbezogene `ready`-Variante soll dasselbe `sessionConfig` wiederholen. Ein serverweiter `ready`-Broadcast darf es wie bisher auslassen.

`settings.wake_word_enabled`, `sessionConfig.activationMode` und `sessionConfig.wakeWordEnabled` dürfen sich nicht widersprechen.

### 4.3 Ungültiges oder nicht verfügbares Profil

Vor Recordererzeugung:

```json
{
  "type": "error",
  "where": "session_config",
  "code": "unknown_session_profile",
  "message": "Unknown session profile.",
  "requestedProfile": "invalid"
}
```

Danach:

- WebSocket-Close-Code `1008` (Policy Violation),
- kein Recorder,
- kein belegter aktiver Session-/Speaker-Slot,
- kein Modell-Ladevorgang allein aufgrund des ungültigen Profils.

Weitere Fehlercodes:

| Code | Fall |
|---|---|
| `invalid_session_profile` | Syntax, Länge oder mehrfacher Parameter ungültig |
| `unknown_session_profile` | syntaktisch gültige, aber unbekannte ID |
| `session_profile_unavailable` | Profil vorhanden, aber wegen fehlendem Backend/Modell nicht verwendbar |
| `session_profile_misconfigured` | serverseitige Profildefinition ist intern widersprüchlich |

Interne Pfade, Secrets und vollständige Serverkonfiguration dürfen nicht in der Fehlermeldung erscheinen.

## 5. Verbindliche Profile

### 5.1 `direct_hotkey`

Mindestwirkung:

```yaml
activation_mode: direct_hotkey
wake_word_enabled: false
```

Verhalten:

1. `hello.sessionConfig.activationMode == "direct_hotkey"`
2. `hello.settings.wake_word_enabled == false`
3. `start` führt in `listening`, `voice` oder einen anderen normalen VAD-Zustand, niemals zuerst in `wakeword_wait`
4. gültige Sprache kann ohne vorheriges Wake Word `realtime` und `final` erzeugen
5. serverweite Wake-Word-Defaults werden nicht verändert

### 5.2 `wake_word`

Mindestwirkung:

```yaml
activation_mode: wake_word
wake_word_enabled: true
wakeword_backend: openwakeword
wake_words: hey_jarvis
```

Verhalten:

1. `hello.sessionConfig.activationMode == "wake_word"`
2. `hello.settings.wake_word_enabled == true`
3. `start` führt in `wakeword_wait`
4. Audio wird während `wakeword_wait` kontinuierlich angenommen
5. erst Wake-Word-Erkennung oder ein aktives Follow-up-Fenster gibt die Sprachaufnahme frei
6. Wake-Timeout und Follow-up bleiben ausschließlich in dieser Session

## 6. Vollständiger Profilumfang

Die folgende Liste basiert auf den aktuellen `newSessionOnly`-Werten des Servers. Der Server-Agent muss für jedes Feld nachweisen, ob es wirklich sessionlokal wirkt. Ein Feld darf nur als effektiv pro Session veröffentlicht werden, wenn es nicht stillschweigend einen bereits gemeinsam geladenen Worker oder andere Sessions beeinflusst.

### 6.1 Neu einzuführende Profilfelder

| Feld | Typ | Regel |
|---|---|---|
| `activation_mode` | Enum | exakt `direct_hotkey` oder `wake_word` |
| `wake_word_enabled` | Boolean | muss zu `activation_mode` passen |
| `language` | String | serverseitige Allowlist; nur sessionlokal ausweisen, wenn die Engine dies tatsächlich pro Job/Recorder unterstützt |

`activation_mode` ist die führende Semantik. `wake_word_enabled` ist der daraus abgeleitete, ausdrücklich zurückgemeldete Effektivwert.

### 6.2 Audio und Recorder

| Bestehender Serverwert | Validierung | Profilwirkung |
|---|---|---|
| `audio_queue_size` | positive Ganzzahl; serverseitige Obergrenze | Queue dieser Session |
| `max_audio_queue_seconds_per_session` | positive Zahl; serverseitige Obergrenze | Latenz-/Backloggrenze dieser Session |
| `pre_recording_buffer_duration` | Zahl `>= 0`; serverseitige Obergrenze | Prebuffer dieser Session |
| `vad_energy_threshold` | endliche Zahl `>= 0` | nur freigeben, wenn produktiver Recorderpfad sie tatsächlich nutzt |
| `vad_filter` | Boolean | nur als sessionlokal ausweisen, wenn kein Shared Worker dadurch mutiert wird |

### 6.3 Segmentierung und VAD

| Bestehender Serverwert | Validierung |
|---|---|
| `min_length_of_recording` | endliche Zahl `>= 0` |
| `min_gap_between_recordings` | endliche Zahl `>= 0` |
| `post_speech_silence_duration` | endliche Zahl `>= 0` |
| `early_transcription_on_silence` | endliche Zahl `>= 0`; vorhandene Serversemantik und Einheit beibehalten |
| `silero_sensitivity` | endliche Zahl im vom Backend unterstützten Bereich; bevorzugt `0..1` |
| `webrtc_sensitivity` | Ganzzahl aus der tatsächlich unterstützten WebRTC-VAD-Enum |

### 6.4 Realtime-Verhalten

| Bestehender Serverwert | Validierung |
|---|---|
| `realtime_callback` | Boolean |
| `realtime_processing_pause` | endliche Zahl `>= 0` |
| `realtime_min_audio_seconds` | endliche Zahl `>= 0` |
| `realtime_max_audio_seconds` | endliche Zahl `> 0` und `>= realtime_min_audio_seconds` |
| `realtime_batch_size` | positive Ganzzahl; Shared-Worker-Auswirkung prüfen |
| `realtime_transcription_use_syllable_boundaries` | Boolean |
| `realtime_boundary_detector_sensitivity` | endliche Zahl im unterstützten Bereich |
| `realtime_boundary_followup_delays` | Liste endlicher Zahlen `>= 0`; maximale Länge serverseitig begrenzen |

### 6.5 Prompts

| Bestehender Serverwert | Validierung |
|---|---|
| `initial_prompt` | String; serverseitiges Zeichen-/Bytelimit; nicht in Logs ausgeben |
| `initial_prompt_realtime` | String; serverseitiges Zeichen-/Bytelimit; nicht in Logs ausgeben |

Prompts dürfen nur als sessionlokal beworben werden, wenn sie pro Recorder beziehungsweise Inferenzjob übergeben werden. Eine Profiländerung darf keinen bereits von anderen Sessions verwendeten Shared Worker mutieren.

### 6.6 Wake Word

| Bestehender Serverwert | Validierung und Sicherheitsregel |
|---|---|
| `wakeword_backend` | Allowlist installierter Backends |
| `wake_words` | normalisierte serverseitige Wort-/Modell-ID; im Wake-Modus nicht leer |
| `wake_words_sensitivity` | endliche Zahl im Backendbereich, bevorzugt `0..1` |
| `wake_word_activation_delay` | endliche Zahl `>= 0` |
| `wake_word_timeout` | endliche Zahl `> 0` |
| `wake_word_buffer_duration` | endliche Zahl `>= 0`; serverseitige Obergrenze |
| `wake_word_followup_window` | endliche Zahl `>= 0` |
| `openwakeword_model_paths` | **kein Clientwert**; aus vertrauenswürdiger serverseitiger Modell-ID auflösen |
| `openwakeword_inference_framework` | Allowlist installierter Frameworks |

Ein Profil darf Modell-IDs referenzieren. Der Server löst sie über seinen Modellkatalog in lokale Pfade auf. Lokale Pfade werden weder vom Client angenommen noch in öffentlichen Events ausgegeben.

## 7. Werte, die nicht durch Sessionprofile geändert werden dürfen

### 7.1 Globale Betriebs- und Sicherheitswerte

Unter anderem:

- `host`, `port`,
- `admin_api_key`, `openai_api_key`,
- `max_sessions`, `max_active_speakers`,
- `max_audio_packet_bytes`,
- globale Scheduler-/Queue-Limits,
- Modell-Idle- und Memory-Policy,
- Request-/Performance-Logging,
- Audioarchivierung und Logpfade,
- `runtime_config_path`.

### 7.2 Geteilte Modell- und Enginewerte

Solange die Serverarchitektur gemeinsame Lanes verwendet:

- `transcription_engine`, `model`, `transcription_engine_options`,
- `realtime_transcription_engine`, `realtime_model`,
- `realtime_transcription_engine_options`,
- `beam_size`, `beam_size_realtime`, `batch_size`,
- `use_main_model_for_realtime`,
- `device`, `compute_type`, `download_root`,
- `normalize_audio`, `model_warmup`,
- `tuning_profile`, `tuning_description`.

Falls `language`, Prompts, `realtime_batch_size` oder andere Werte gegenwärtig in einen Shared Worker eingebaut werden, muss der Server-Agent entweder:

1. sie pro Job/sessionlokal machen,
2. sie aus dem Profilvertrag ausschließen,
3. oder eine Profilwahl mit abweichendem Wert eindeutig ablehnen.

Ein bloßes Echo als „angewendet“, obwohl der laufende Worker einen anderen Wert nutzt, ist nicht zulässig.

## 8. Serverseitige Konfiguration

Empfohlene Struktur:

```yaml
default_session_profile: direct_hotkey

session_profiles:
  direct_hotkey:
    description: Direkte Diktieraufnahme per Desktop-Hotkey
    activation_mode: direct_hotkey
    wake_word_enabled: false
    overrides:
      post_speech_silence_duration: 0.7
      pre_recording_buffer_duration: 0.2

  wake_word:
    description: Dauerhafte Hintergrundsession mit Hey Jarvis
    activation_mode: wake_word
    wake_word_enabled: true
    overrides:
      wakeword_backend: openwakeword
      wake_words: hey_jarvis
      wake_words_sensitivity: 0.5
      wake_word_timeout: 7.0
      wake_word_buffer_duration: 0.1
      wake_word_followup_window: 7.0
```

Die Zahlen im Beispiel sind keine neuen verbindlichen Tuningwerte. Nicht überschriebene Felder erben die bestehenden Serverdefaults. Beim Start muss der Server alle Profile vollständig validieren; ungültige Profile werden als nicht verfügbar markiert oder führen zu einem klaren Startfehler.

## 9. Isolation und Lebenszyklus

- Die effektive Profilkonfiguration wird beim Sessionaufbau tief kopiert.
- Zwei parallele Sessions dürfen unterschiedliche Profile verwenden.
- `clear` setzt Segment-, Recorder- und Wake-Zustand zurück, ändert aber nicht das Profil.
- `stop` beendet Streaming, ändert aber nicht das Profil.
- Ein erneutes `start` derselben Verbindung verwendet dasselbe Profil.
- Ein Profilwechsel innerhalb derselben WebSocket-Verbindung ist in Version 1 nicht erlaubt.
- Reconnect erzeugt eine neue Session und erfordert erneute Profilauswahl.
- Runtime-Änderungen an einer Profildefinition gelten nur für danach erzeugte Sessions.
- Der Server darf globale Sicherheitslimits weiterhin strenger anwenden als ein Profil.

## 10. Beobachtbarkeit

Sessionbezogene `status`- und `metrics`-Daten sollen zusätzlich enthalten:

```json
{
  "sessionProfile": "direct_hotkey",
  "activationMode": "direct_hotkey",
  "wakeWordEnabled": false
}
```

Logs dürfen Profil-ID, Session-ID und Aktivierungsmodus enthalten. Prompts, Transkripttext, lokale Modellpfade und Secrets bleiben gemäß bestehender Datenschutzkonfiguration geschützt.

## 11. Mindestabnahme für den Server-Agenten

### Protokoll

- [ ] fehlender Queryparameter verwendet den dokumentierten Default
- [ ] `direct_hotkey` und `wake_word` werden vor Recordererzeugung ausgewählt
- [ ] `hello` und direkte `ready`-Antwort melden das effektive Profil widerspruchsfrei
- [ ] ungültige/unbekannte Profile liefern `error(where=session_config)` und Close `1008`
- [ ] Querywert wird nicht als Pfad, Code oder freier Konfigurationswert interpretiert

### Verhalten

- [ ] `direct_hotkey`: `start` → kein `wakeword_wait`; Sprache erzeugt ohne Wake Word einen Finaltext
- [ ] `wake_word`: `start` → `wakeword_wait`; Audio läuft weiter; Wake Word → Aufnahme → Finaltext
- [ ] Follow-up und Timeout einer Wake-Session beeinflussen keine andere Session
- [ ] parallele Direct- und Wake-Session funktionieren gleichzeitig
- [ ] Profilauswahl ändert keine globalen Serverdefaults
- [ ] Reconnect übernimmt nur durch erneute Queryauswahl dasselbe Profil

### Ressourcen und Fehler

- [ ] unbekanntes Profil erzeugt keinen Recorder und belegt keinen Session-/Speaker-Slot
- [ ] fehlendes Wake-Backend/Modell ergibt `session_profile_unavailable`
- [ ] Profilwerte werden vollständig validiert und gegen Serverobergrenzen begrenzt
- [ ] globale Kapazitätsgrenzen bleiben wirksam
- [ ] keine Pfade, Secrets oder Prompts erscheinen in öffentlichen Fehlern

### Regression

- [ ] bestehende Clients ohne `sessionProfile` funktionieren unverändert
- [ ] bestehende `start`, `stop`, `clear`, `ping`, `metrics` und Audiopakete bleiben kompatibel
- [ ] bestehende Serverprotokolltests bestehen
- [ ] neue Tests beweisen echte Sessionisolation mit mindestens zwei gleichzeitigen Profilen

## 12. Nach erfolgreicher Serverimplementierung im Client

Dann sind im Client noch gezielt umzusetzen:

1. `session.mode` URL-sicher als `sessionProfile` an den WebSocket-Endpunkt anhängen.
2. `hello.sessionConfig` parsen und speichern.
3. Verbindungsaufnahme abbrechen, wenn `appliedProfile` oder `activationMode` nicht der Clientkonfiguration entsprechen.
4. Bei Reconnect dasselbe konfigurierte Profil erneut anfordern.
5. Betriebsmodus und effektiven Serverzustand in Controller, Tray und Diagnose anzeigen.
6. direkte und Wake-Word-End-to-End-Tests getrennt ausführen.

Bis dahin gilt: Die lokale Option dokumentiert die gewünschte Betriebsart und erkennt über `wake_word_enabled` eine Abweichung, sie konfiguriert den Server noch nicht.
