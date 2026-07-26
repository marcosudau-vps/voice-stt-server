# Prüf- und Implementierungsbericht – konfigurierbare Sessionprofile

> **Bezug:** `SERVER_SESSION_PROFILE_SPECIFICATION.md`, Version 1.0 vom 25. Juli 2026  
> **Prüfstand:** aktueller Workspace am 25. Juli 2026  
> **Repository-Basis:** Branch `master`, Commit `a89fabb`; bewertet wurde ausdrücklich der darüber hinaus stark geänderte, nicht eingecheckte Arbeitsstand  
> **Ergebnis:** technisch gut machbar, aber nicht als bloße Ergänzung eines Queryparameters. Für eine produktionsreife Version 1 sind ein eigener Profilresolver, strikte Validierung, eine Korrektur der öffentlichen Settings und neue Isolations-/Protokolltests erforderlich.

## 1. Kurzfazit

Die bestehende Serverarchitektur ist eine gute Basis für Sessionprofile:

- Jede angenommene WebSocket-Verbindung erhält bereits einen eigenen `AudioToTextRecorder`.
- VAD-, Wake-Word-, Follow-up-, Aufnahme-, Puffer-, Timeline- und Segmentzustände liegen bereits in der Session.
- Finale und Realtime-ASR-Modelle sowie deren Scheduler bleiben serverweit geteilt.
- Die Session kopiert bei ihrer Erzeugung bereits `ServerSettings`.
- `start`, `stop`, `clear`, Disconnect und Reconnect besitzen schon weitgehend die in der Spezifikation geforderte Sessionsemantik.

Damit ist **kein grundlegender Architekturumbau** nötig. Der Kernbedarf lässt sich als kontrollierte Auswahl einer effektiven `ServerSettings`-Kopie vor der Recordererzeugung umsetzen.

Die Funktion ist im aktuellen Server jedoch noch **gar nicht implementiert**:

- `sessionProfile` wird nicht gelesen oder validiert.
- Es gibt keine Profildefinitionen und keinen Profilkatalog.
- `hello`, `ready`, `status`, `metrics` und Logs kennen kein angewendetes Profil.
- Jede neue Session kopiert ausschließlich den jeweils aktuellen globalen Serverzustand.
- Unbekannte Queryparameter werden derzeit ignoriert.

Die größten fachlichen Stolpersteine sind:

1. Mehrere laut Spezifikation mögliche Profilfelder wirken im produktiven Recorderpfad derzeit nicht sessionlokal.
2. `realtime_callback` besitzt im Server einen anderen Typ als in der Spezifikation.
3. Das aktuelle VPS-Deployment verwendet global Wake Word; ein Defaultwechsel auf `direct_hotkey` würde bestehende Clients ohne Queryparameter verändern.
4. `settings.public_dict()` veröffentlicht derzeit unter anderem lokale Wake-Word-Modellpfade und Prompts.
5. Die vorhandene Konfigurationsvalidierung prüft überwiegend Typen, nicht die von der Spezifikation geforderten Wertebereiche, Querbedingungen und Ressourcenobergrenzen.

### Aufwand in drei sinnvollen Ausbaustufen

| Umfang | Inhalt | Grobe Größenordnung |
| --- | --- | ---: |
| Minimaler Funktionsnachweis | Nur `direct_hotkey`/`wake_word`, Profilwahl, `hello`, Fehlerfälle und Fake-Recorder-Tests | 3–5 Personentage |
| Empfohlene produktionsreife Version 1 | Strikter Profilkatalog, sichere Modell-ID-Auflösung, Defaultmigration, Protokoll/Status/Metriken/Logs, Datenschutzkorrekturen, umfassende Unit-/WebSocket-/Isolations- und Deploymenttests | **6–9 Personentage** |
| Vollständiger Feldumfang einschließlich heute geteilter oder wirkungsloser Werte | Zusätzlich Umbau von Prompts/ASR-Optionen zu Jobparametern, Engine-Fähigkeitsmatrix, produktive Verdrahtung der Realtime-Min/Max-Werte und erweiterte E2E-Matrix | **10–16 Personentage insgesamt** |

Die Schätzungen setzen eine vorhandene funktionierende Entwicklungs-/Dockerumgebung und verfügbare Wake-Word-Testmodelle voraus. Ein belastbarer Real-Audio-Wake-Word-E2E-Test kann je nach Testmaterial und Backend weitere 1–2 Tage beanspruchen.

## 2. Geprüfter Ist-Zustand

### 2.1 Maßgeblicher Serverpfad

Der produktive Einstiegspunkt `VoiceSTT_server/server.py` delegiert vollständig an `api_fastapi_server/server.py`. Die zu ändernde Hauptimplementierung ist daher eindeutig:

- `api_fastapi_server/server.py`
- ergänzend `VoiceSTT_server/operations.py` für den Wake-Word-Modellkatalog
- Konfiguration unter `docker/vps/voice/stt-config.yaml`

Der ältere Server unter `VoiceSTT_server/stt_server.py` ist für den aktuellen FastAPI-/Desktop-Client-Vertrag nicht der maßgebliche Pfad.

### 2.2 Session- und Ressourcenmodell

Relevante Implementierungspunkte:

- `RecorderBackedRealtimeSession` erzeugt pro Session einen Recorder und eine Text-Worker-Threadinstanz.
- `self.settings = replace(service.settings)` kopiert die Settings bei Sessionerzeugung.
- `_create_recorder()` übergibt VAD-, Segmentierungs-, Wake-Word- und Realtime-Taktungswerte an den sessioneigenen Recorder.
- `InferenceScheduler` und `SharedEngineWorker` laden die teuren finalen und Realtime-ASR-Engines nur serverweit.
- `SchedulerTranscriptionExecutor` reicht Sessionjobs an diese gemeinsamen Worker weiter.
- `SessionStore` reserviert den Sessionplatz vor der Recordererzeugung und verwaltet aktive Sprecher getrennt.

Das deckt den entscheidenden Architekturwunsch der Spezifikation bereits ab:

```text
WebSocket-Session
  └─ eigener Recorder/VAD/Wake-/Pufferzustand
       └─ Inferenzjobs
            └─ gemeinsame faire ASR-Lanes
```

### 2.3 Aktueller WebSocket-Ablauf

Der Handler unter `/ws/transcribe` führt derzeit aus:

1. neue zufällige `sessionId` erzeugen;
2. über `service.admit_session(session_id)` sofort einen Recorder erzeugen;
3. WebSocket annehmen;
4. globales `settings.public_dict()` in `hello` senden;
5. bei bereits bereitem Server ein direktes `ready` senden;
6. `start`, `stop`, `clear`, `ping`, `metrics` und Audiopakete verarbeiten.

Es gibt vor Schritt 2 aktuell keine profilbezogene Verarbeitung. Genau dort muss die neue Auflösung eingeschoben werden.

### 2.4 Bestehende Wake-Word-Unterstützung

Die nötige Recorderfunktion ist bereits vorhanden:

- OpenWakeWord und Porcupine werden unterstützt.
- Backend, Wörter/Modellbezeichner, Sensitivität, Aktivierungsverzögerung, Timeout, Puffer und Framework werden an jeden Recorder übergeben.
- Wake-Wait, Detection, Timeout und Follow-up sind bereits in der Session gekapselt.
- Die Timeline- und Statuscallbacks publizieren die relevanten Zustandswechsel.
- `clear()` setzt Wake- und Follow-up-Zustand der Session zurück.
- `stop()` und ein späteres erneutes `start()` behalten die Settingskopie der Verbindung.

Für die beiden primären Betriebsarten fehlt somit vor allem die Auswahl:

- `direct_hotkey` muss in der effektiven Sessionkopie Backend und Wake Words deaktivieren.
- `wake_word` muss eine vollständig validierte, verfügbare Wake-Konfiguration erhalten.

Wichtig: `wake_word_enabled` ist heute **kein gespeichertes Settingsfeld**, sondern wird durch `ServerSettings.wake_word_enabled()` aus `wakeword_backend` und `wake_words` abgeleitet. Ein Profil darf daher nicht nur ein neues Boolean setzen; es muss die zugrunde liegenden Recorderwerte konsistent normalisieren.

## 3. Soll-/Ist-Abgleich nach Anforderungsbereich

### 3.1 Profilauswahl

| Anforderung | Ist-Zustand | Bewertung |
| --- | --- | --- |
| `sessionProfile` einmalig als Queryparameter | nicht implementiert | neu erforderlich |
| Syntax `^[a-z][a-z0-9_-]{0,63}$` | nicht implementiert | einfach, aber exakt und ohne implizites Trim/Casefold umsetzen |
| fehlender Parameter nutzt Default | nicht implementiert | neue Serverkonfiguration nötig |
| Auswahl vor Recordererzeugung | derzeit keine Auswahl | gut integrierbar, muss vor `admit_session()` geschehen |
| ungültig/unbekannt ohne Sessionplatz | aktuell unbekannte Querywerte werden ignoriert | Validator muss vor `SessionStore.reserve()` laufen |
| Profilkopie bei Reconnect | Session wird ohnehin neu erzeugt | nach Profilresolver automatisch erfüllt |
| kein Wechsel in derselben Verbindung | kein entsprechender Befehl vorhanden | automatisch erfüllt, sofern kein Profilmutationsbefehl eingeführt wird |

Starlette/FastAPI stellt Queryparameter als Multivalue-Struktur bereit. Für die Duplikatregel muss ausdrücklich `getlist("sessionProfile")` beziehungsweise eine gleichwertige Multivalue-Auswertung verwendet werden; ein einfaches `.get()` würde doppelte Parameter stillschweigend verschlucken.

### 3.2 `hello` und `ready`

Aktuell enthalten `hello` und das direkte `ready` jeweils **globale** `settings.public_dict()`. Die bereits im Recorder liegende Sessionkopie wird nicht verwendet.

Für die Spezifikation sind nötig:

- eine unveränderliche `sessionConfig` an der Session;
- `hello.settings` aus der effektiven Sessionkopie, mindestens für sessionrelevante Werte;
- `hello.sessionConfig` exakt gemäß Vertrag;
- Wiederholung derselben `sessionConfig` im direkten, sessionbezogenen `ready`;
- kein `sessionConfig` im serverweiten `ready`-Broadcast;
- ein gemeinsamer Serializer, damit `hello`, `ready`, `status` und `metrics` nicht auseinanderlaufen.

Die aktuelle Trennung hilft dabei:

- Das direkte `ready` besitzt eine `sessionId`.
- Der spätere serverweite Ready-Broadcast besitzt keine `sessionId`.

Clients, die sich während des Modellstarts verbinden, erhalten daher `sessionConfig` sicher im `hello`, später aber nur einen globalen `ready`. Das sollte in der aktualisierten Clientdokumentation ausdrücklich festgehalten werden.

### 3.3 Fehlervertrag

Die geforderten Profilfehler existieren noch nicht. Empfohlen ist eine interne, typisierte Fehlerklasse mit:

- öffentlichem `code`;
- sicherer öffentlicher Standardmeldung;
- optional internem Diagnosegrund;
- `requestedProfile` nur in begrenzter/validierter Form;
- Zuordnung zu Close-Code `1008`.

Für einen Fehler vor Admission ist folgender Ablauf nötig:

1. WebSocket explizit annehmen;
2. genau ein `error(where="session_config")` senden;
3. mit `1008` schließen;
4. weder `ConnectionManager.connect()` noch `SessionStore.reserve()` noch Recordererzeugung aufrufen.

Die Fehlerklassen sollten sauber getrennt werden:

| Code | Serverseitige Ursache |
| --- | --- |
| `invalid_session_profile` | leer, zu lang, falsche Zeichen, mehrfacher Parameter |
| `unknown_session_profile` | gültige ID nicht im Katalog |
| `session_profile_unavailable` | bekannte Definition, aber fehlendes Backend, fehlendes Modell oder nicht erfüllte Betriebsabhängigkeit |
| `session_profile_misconfigured` | Definition verletzt Schema, Querbedingungen oder erlaubten Feldumfang |

Strukturell fehlerhafte Pflichtprofile sollten vorzugsweise den Serverstart abbrechen. Operativ nicht verfügbare optionale Profile können im Katalog als `unavailable` markiert werden, sodass beispielsweise `direct_hotkey` trotz fehlendem OpenWakeWord weiter nutzbar bleibt.

### 3.4 Lebenszyklus und Isolation

Die vorhandene Implementierung erfüllt bereits einen großen Teil:

| Anforderung | Bestehende Basis |
| --- | --- |
| Sessioneigener Recorder | vorhanden |
| Wake-/Follow-up-Isolation | vorhanden |
| `clear` ändert Profil nicht | vorhandene Settingskopie bleibt bestehen |
| `stop` ändert Profil nicht | vorhandene Settingskopie bleibt bestehen |
| erneutes `start` nutzt dasselbe Profil | Verbindung und Recorder bleiben bestehen |
| Reconnect erzeugt neue Kopie | neue `sessionId` und neuer Recorder |
| globale ASR-Modelle bleiben geteilt | vorhanden |
| globale Session-/Speakerlimits bleiben wirksam | vorhanden |

Die aktuelle Kopie erfolgt allerdings mit `dataclasses.replace()` und ist damit nur flach. Diktate und andere mutable Werte bleiben referenziell geteilt. Die Spezifikation verlangt zu Recht eine tiefe Kopie. Für den neuen Resolver sollte `copy.deepcopy()` oder ein explizit unveränderliches Settingsmodell verwendet werden.

Außerdem existiert zwar `VoiceSTTService._settings_lock`, der aktuelle Updatepfad nutzt ihn jedoch nicht für eine atomare Kombination aus globalem Snapshot und Profilauflösung. Ohne Korrektur kann eine zeitgleiche Adminänderung theoretisch eine gemischte Sessionkonfiguration erzeugen. Profilauflösung und Runtimeupdates sollten unter demselben Lock konsistent gemacht werden.

## 4. Feldgenauer Wirkungsnachweis

Die folgende Matrix bezieht sich auf den **produktiven `RecorderBackedRealtimeSession`-Pfad**, nicht auf die ältere Inlineklasse `RealtimeSession`.

### 4.1 Neu einzuführende Felder

| Feld | Aktuelle Wirkung | Empfehlung |
| --- | --- | --- |
| `activation_mode` | nicht vorhanden | als führende, unveränderliche Profilmetadaten einführen |
| `wake_word_enabled` | nur abgeleitete Methode aus Backend + Wörtern | nicht unabhängig speichern; aus validiertem Aktivierungsmodus ableiten und rückmelden |
| `language` | wird pro Recorder an den Executor und anschließend pro Job an den Shared Worker gereicht | nur mit Engine-Fähigkeitsprüfung freigeben; beim aktuell eingesetzten Kroko-Modell ändert der Sprachwert nicht das sprachspezifische Modell |

Für das aktuelle Kroko-DE-Produktionsmodell sollte ein Profil daher nicht den Eindruck erwecken, durch `language: en` werde ein englisches Modell aktiviert. Ein Engine-/Modellwechsel bleibt zu Recht global und startupbezogen.

### 4.2 Audio und Recorder

| Feld | Produktiver Pfad | Freigabe |
| --- | --- | --- |
| `audio_queue_size` | wird als `allowed_latency_limit` an den Recorder übergeben | sessionlokal, aber semantisch Chunk-Rückstaugrenze und keine echte `Queue(maxsize=...)` |
| `max_audio_queue_seconds_per_session` | begrenzt im Recorderpfad die Dauer einer laufenden Aufnahme und erzwingt Finalisierung | sessionlokal, Name/Beschreibung als „Backloggrenze“ ist missverständlich |
| `pre_recording_buffer_duration` | direkt am Recorder und in der Timeline | sessionlokal |
| `vad_energy_threshold` | nur in der älteren Inline-Session verwendet | im Produktionspfad derzeit wirkungslos; nicht freigeben, bevor es bewusst verdrahtet wird |
| `vad_filter` | Shared ASR-Engine wird damit beim Workerstart gebaut; Recorderwert greift wegen externer Executors nicht auf die Engine durch | nicht sessionlokal; aus Version 1 ausschließen |

### 4.3 Segmentierung und VAD

| Feld | Produktiver Pfad | Freigabe |
| --- | --- | --- |
| `min_length_of_recording` | Recorderinstanz | sessionlokal |
| `min_gap_between_recordings` | Recorderinstanz | sessionlokal |
| `post_speech_silence_duration` | Recorderinstanz | sessionlokal |
| `early_transcription_on_silence` | Recorderinstanz | sessionlokal |
| `silero_sensitivity` | sessioneigener VAD | sessionlokal |
| `webrtc_sensitivity` | sessioneigene WebRTC-VAD-Instanz | sessionlokal |

Zu `early_transcription_on_silence` besteht eine Dokumentationsunschärfe: Die Bibliotheksdokumentation bezeichnet den Wert teilweise als Millisekunden, der aktuelle Code vergleicht ihn aber direkt mit `time.time()`-Differenzen in Sekunden; auch der Serverdefault `0.2` spricht für Sekunden. Vor öffentlicher Profilfreigabe sollte die Einheit verbindlich als Sekunden dokumentiert und mit einem Regressionstest abgesichert werden.

### 4.4 Realtime-Verhalten

| Feld | Produktiver Pfad | Freigabe |
| --- | --- | --- |
| `realtime_callback` | String-Enum `"update"` oder `"stabilized"` bestimmt den publizierten Callback/Textpfad | sessionlokal, **Spezifikationstyp Boolean ist falsch** |
| `realtime_processing_pause` | steuert die Realtime-Taktung des Recorders | sessionlokal |
| `realtime_min_audio_seconds` | nur in der älteren Inline-Session verwendet | produktiv derzeit wirkungslos |
| `realtime_max_audio_seconds` | nur in der älteren Inline-Session verwendet | produktiv derzeit wirkungslos |
| `realtime_batch_size` | wird beim Erzeugen des gemeinsamen Realtime-ASR-Workers fest eingebaut | nicht sessionlokal; Recorderwert ist bei externem Executor praktisch ohne Wirkung |
| `realtime_transcription_use_syllable_boundaries` | Recorderinstanz | sessionlokal |
| `realtime_boundary_detector_sensitivity` | Recorderinstanz | sessionlokal |
| `realtime_boundary_followup_delays` | Recorderinstanz | sessionlokal |

`realtime_min_audio_seconds` könnte künftig bewusst auf `init_realtime_after_seconds` abgebildet werden, die Semantik ist jedoch nicht exakt identisch. `realtime_max_audio_seconds` benötigt im produktiven Recorderpfad eine neue, getestete Begrenzung. Beide Werte sollten bis dahin nicht als angewendet zurückgemeldet werden.

### 4.5 Prompts

| Feld | Produktiver Pfad | Freigabe |
| --- | --- | --- |
| `initial_prompt` | Shared Final-Engine erhält den Prompt beim Workerstart; Sessionexecutor überträgt nur `use_prompt` | nicht sessionlokal |
| `initial_prompt_realtime` | Shared Realtime-Engine erhält den Prompt beim Workerstart | nicht sessionlokal |

Eine Sessionkopie dieser Strings ändert den tatsächlich verwendeten Prompt nicht. Für echte Sessionprompts wäre nötig:

1. Prompt als validierte Joboption in `InferenceJob` aufnehmen;
2. `SchedulerTranscriptionExecutor` und `transcribe_for_recorder()` erweitern;
3. jeden Engineadapter auf per-Request-Promptfähigkeit prüfen;
4. nicht unterstützte Engines/Modelle eindeutig ablehnen;
5. Prompts in Events, Audit- und Fehlerlogs konsequent redigieren.

Das ist ein eigener, deutlich größerer Teilumfang und sollte nicht still in die Aktivierungsprofil-Funktion hineingezogen werden.

### 4.6 Wake Word

| Feld | Produktiver Pfad | Freigabe |
| --- | --- | --- |
| `wakeword_backend` | pro Recorder | sessionlokal |
| `wake_words` | pro Recorder | sessionlokal |
| `wake_words_sensitivity` | pro Recorder | sessionlokal |
| `wake_word_activation_delay` | pro Recorder | sessionlokal, aber siehe Vertragswiderspruch unten |
| `wake_word_timeout` | pro Recorder | sessionlokal |
| `wake_word_buffer_duration` | pro Recorder | sessionlokal |
| `wake_word_followup_window` | explizite Sessionlogik im FastAPI-Server | sessionlokal |
| `openwakeword_model_paths` | pro Recorder, lädt die Wake-Word-Instanz | nur intern nach Auflösung einer Modell-ID |
| `openwakeword_inference_framework` | pro Recorder | sessionlokal |

Der vorhandene `WakeWordRegistry` kann bereits OpenWakeWord-Dateien und Porcupine-Keywords katalogisieren. Er muss für Profile zu einem eindeutigen, validierten ID-zu-Pfad-Resolver erweitert werden.

Die Profildefinition sollte keinen frei formulierten Pfad im `overrides`-Block benötigen. Besser ist ein profilinternes Feld wie `wakeword_model_id: hey_jarvis`; daraus löst der Server anhand seines vertrauenswürdigen Katalogs den absoluten Pfad für die effektive Recorderkonfiguration auf.

### 4.7 Konservativ zulässiger Feldumfang für Version 1

Für eine risikoarme erste Version sollten nur folgende Felder profilierbar sein:

- `activation_mode`
- abgeleitetes `wake_word_enabled`
- optional `language`, zunächst nur wenn identisch zum Serverdefault oder von der aktiven Engine nachweislich unterstützt
- `audio_queue_size`
- `max_audio_queue_seconds_per_session`
- `pre_recording_buffer_duration`
- `min_length_of_recording`
- `min_gap_between_recordings`
- `post_speech_silence_duration`
- `early_transcription_on_silence`
- `silero_sensitivity`
- `webrtc_sensitivity`
- `realtime_callback` als Enum
- `realtime_processing_pause`
- `realtime_transcription_use_syllable_boundaries`
- `realtime_boundary_detector_sensitivity`
- `realtime_boundary_followup_delays`
- die oben als sessionlokal bestätigten Wake-Word-Werte

Zunächst auszuschließen:

- `vad_energy_threshold`
- `vad_filter`
- `realtime_min_audio_seconds`
- `realtime_max_audio_seconds`
- `realtime_batch_size`
- `initial_prompt`
- `initial_prompt_realtime`

Ein ausgeschlossener Wert muss beim Serverstart als Profilfehlkonfiguration auffallen. Er darf weder still ignoriert noch im `sessionConfig` als angewendet gespiegelt werden.

## 5. Widersprüche und notwendige Präzisierungen der Spezifikation

### 5.1 Defaultprofil versus Rückwärtskompatibilität

Die Beispielkonfiguration setzt:

```yaml
default_session_profile: direct_hotkey
```

Das aktuelle produktionsnahe VPS-Config setzt jedoch global:

```yaml
wakeword_backend: openwakeword
wake_words: hey_jarvis
wake_word_followup_window: 7.0
```

Bestehende Browser- und Desktopclients verbinden sich ohne `sessionProfile`. Würde das Deployment beim Rollout den Beispieldefault `direct_hotkey` übernehmen, würden diese Clients plötzlich ohne Wake-Word-Gate arbeiten. Das widerspricht der Regressionsforderung „bestehende Clients ohne `sessionProfile` funktionieren unverändert“.

**Empfehlung für den ersten Produktionsrollout:**

```yaml
default_session_profile: wake_word
```

Der neue Desktop-Client fordert `direct_hotkey` explizit an. Erst nach Migration aller Altclients kann der Default bewusst geändert werden.

Alternativ müsste die Spezifikation den Defaultwechsel als absichtliche Breaking Change ausweisen.

### 5.2 `realtime_callback`

Die Spezifikation nennt einen Boolean. Der Server verwendet:

```text
"update" | "stabilized"
```

Empfehlung: Spezifikation auf dieses Enum korrigieren. Falls eigentlich „Realtime komplett aktiv/inaktiv“ gemeint war, wäre ein neues separates Feld nötig.

### 5.3 `wake_word_activation_delay`

Die Spezifikation erlaubt Werte `>= 0`, fordert für `wake_word` aber unmittelbar:

```text
start → wakeword_wait
```

Der aktuelle Server liefert bei positiver Aktivierungsverzögerung zunächst `listening`. Für das verbindliche Profil `wake_word` sollte daher `wake_word_activation_delay == 0` gelten. Andere Wake-Profile mit verzögertem Gate wären ein späterer eigener Aktivierungsmodus oder müssten abweichend dokumentiert werden.

### 5.4 Wake-Word-Aktivierungsableitung

Der Recorder betrachtet OpenWakeWord bereits anhand des Backends als aktiv; `ServerSettings.wake_word_enabled()` verlangt derzeit zusätzlich nichtleere `wake_words`. Die Spezifikation verlangt für das verbindliche Profil beides, dennoch sollte die Serverableitung vereinheitlicht werden, damit Status und realer Recorderzustand niemals auseinanderlaufen.

### 5.5 Profiländerungen zur Laufzeit

Die Spezifikation sagt, Änderungen an Profildefinitionen wirkten nur auf neue Sessions, benennt aber keinen Admin-Endpunkt oder Reloadmechanismus dafür.

Für Version 1 sollte festgelegt werden:

- Profile werden nur beim Serverstart aus der read-only YAML geladen; oder
- `/api/config/reload` lädt auch Profildefinitionen atomar neu; oder
- es gibt eine eigene authentifizierte Profilverwaltung.

Empfohlen für die erste Version ist **startup-/YAML-only**. Das reduziert Race-, Persistenz- und Sicherheitskomplexität. Ein späterer atomarer Reload kann ergänzt werden.

### 5.6 Pfadverweis in der Spezifikation

Die Spezifikation verweist auf `server-docs-for-client-development/`. Im aktuellen Repository liegt die maßgebliche Dokumentation unter:

```text
docs/client-development/
```

Der Verweis sollte korrigiert werden.

## 6. Empfohlene Zielarchitektur

### 6.1 Eigener Profilkatalog

Statt weitere Logik in die bereits sehr große `server.py` einzubauen, empfiehlt sich ein Modul:

```text
api_fastapi_server/session_profiles.py
```

Mögliche interne Typen:

```python
SessionProfileDefinition
SessionProfileStatus
ResolvedSessionProfile
SessionProfileRegistry
SessionProfileError
```

`ResolvedSessionProfile` sollte mindestens tragen:

- `requested_profile: str | None`
- `applied_profile: str`
- `activation_mode`
- `wake_word_enabled`
- tief kopierte effektive `ServerSettings`
- sichere öffentliche `sessionConfig`

### 6.2 Auflösungsablauf

Empfohlene Reihenfolge:

1. alle Vorkommen von `sessionProfile` lesen;
2. Multiplizität und Syntax validieren;
3. bei Fehlen Default-ID einsetzen;
4. Profildefinition aus ausschließlich serverseitigem Katalog laden;
5. Verfügbarkeit prüfen;
6. unter Settingslock einen tiefen Snapshot der aktuellen Serverdefaults erstellen;
7. nur erlaubte Profilfelder anwenden;
8. Wake-Word-Modell-ID intern in Pfad auflösen;
9. Querbedingungen und globale Hard Caps prüfen;
10. unveränderliches `ResolvedSessionProfile` erzeugen;
11. erst jetzt Sessionplatz reservieren und Recorder mit genau diesem Snapshot erzeugen.

`VoiceSTTService.admit_session()` sollte daher künftig nicht selbst unkontrolliert globale Settings kopieren, sondern den bereits aufgelösten Snapshot erhalten.

### 6.3 Harte globale Obergrenzen

Mehrere Profilfelder benötigen laut Spezifikation serverseitige Obergrenzen. Derzeit sind Default und Grenze teilweise dasselbe Feld. Empfohlen ist eine klare Regel:

- Der globale Basiswert ist gleichzeitig der maximale zulässige Profilwert; Profile dürfen ihn nur absenken.
- Wo eine Erhöhung fachlich nötig ist, wird ein getrenntes startup-only Hard-Cap-Feld eingeführt.

Beispiele:

- `audio_queue_size <= global audio_queue_size`
- `max_audio_queue_seconds_per_session <= global max_audio_queue_seconds_per_session`
- `pre_recording_buffer_duration <= global configured cap`
- begrenzte Anzahl und Gesamtdauer der Follow-up-Delays
- separate feste Zeichen-/Bytegrenzen für Prompts, falls diese später freigegeben werden

So bleiben globale Ressourcen- und Sicherheitsentscheidungen tatsächlich strenger als Profile.

### 6.4 Verfügbarkeitsprüfung

Beim Start:

- Profil-ID und Schema validieren;
- unbekannte/gesperrte Felder ablehnen;
- Backendname normalisieren und allowlisten;
- Pythonpaket des Backends prüfen;
- Wake-Word-Modell-ID eindeutig auflösen;
- Modell- und Featuredateien auf Existenz prüfen;
- Framework und Dateiformat abgleichen;
- Pflichtprofile auf Vorhandensein prüfen.

Eine reine Dateiexistenzprüfung kann ein korruptes Modell nicht erkennen. Tritt trotz Preflight ein Fehler bei der Recordererzeugung auf, muss:

- die Reservierung sicher freigegeben werden;
- kein Sessionobjekt im Store bleiben;
- der Client eine sanitisierte Profilfehlermeldung erhalten;
- der interne Fehler mit Profil-ID und ohne Secret-/Promptinhalt protokolliert werden.

### 6.5 Öffentliche Settings und Datenschutz

`ServerSettings.public_dict()` entfernt derzeit Engine-Options und API-Keys, lässt aber unter anderem folgende Werte stehen:

- `openwakeword_model_paths`
- `download_root`
- `initial_prompt`
- `initial_prompt_realtime`
- Log-/Runtimepfade

Damit widerspricht schon der aktuelle `hello`-Payload teilweise dem neuen Sicherheitsziel. Vor Einführung von Sessionprofilen sollte ein expliziter Public-Serializer entstehen, der nur wirklich öffentliche Betriebsinformationen enthält.

Mindestens zu entfernen oder zu redigieren:

- sämtliche lokalen Modell- und Datenpfade;
- Prompts;
- Secretwerte;
- interne Runtime-/Logpfade;
- vollständige Profildefinitionen.

Das betrifft auch `/api/config`, denn dieser GET-Endpunkt ist aktuell ohne Adminauthentifizierung erreichbar.

Zudem protokolliert `update_settings()` im Auditereignis aktuell die angewendeten Werte. Sobald Prompts beteiligt sind, müssen diese dort redigiert werden.

## 7. Auswirkungen auf vorhandene APIs und Bedienoberflächen

### 7.1 Admin-Wake-Word-API

`PUT /api/wake-word` ändert derzeit die globalen Wake-Werte für neue Sessions. Mit expliziten Profil-Overrides kann eine solche Änderung wirkungslos erscheinen:

- Das Profil `wake_word` überschreibt möglicherweise Backend/Wort/Sensitivität.
- Die Admin-API ändert nur die Baseline.
- Neue Sessions mit diesem Profil verwenden trotzdem dessen Override.

Für Version 1 muss dokumentiert werden, dass die API nur geerbte Defaults ändert, oder sie muss gezielt das Wake-Profil verwalten. Ohne Klärung ist die Browser-Adminoberfläche irreführend.

### 7.2 Eingebaute Browseroberfläche

Die Browseroberfläche verbindet sich aktuell ohne Queryparameter. Sie wird daher vom `default_session_profile` gesteuert.

Mindestens erforderlich:

- Default beim Rollout auf das bisherige Wake-Verhalten setzen;
- effektives Profil aus `hello.sessionConfig` anzeigen oder wenigstens diagnostisch speichern;
- `ready` ohne `sessionConfig` weiterhin tolerieren;
- die Admin-Wake-Konfiguration nicht fälschlich als direktes Umschalten der laufenden Session darstellen.

### 7.3 Reverse Proxy

Die vorhandene Nginx-Konfiguration leitet `/ws/` ohne feste Ziel-URI an den Server weiter. Queryparameter werden dabei grundsätzlich mitgereicht. Trotzdem sollte ein Produktions-Smoke-Test mit der realen WSS-URL beide Profile und einen doppelten Parameter abdecken.

## 8. Risiken

### 8.1 Hohe Priorität

| Risiko | Auswirkung | Gegenmaßnahme |
| --- | --- | --- |
| falscher Default beim Rollout | bestehende Clients verhalten sich anders, eventuell unbeabsichtigte Dauertranskription ohne Wake Gate | zunächst `wake_word` als Default |
| wirkungslose Felder werden als angewendet gemeldet | gefährlicher Scheinerfolg, schwer diagnostizierbare Clientfehler | konservative Allowlist und Feldtests bis zum realen Worker |
| lokale Pfade/Prompts in `hello` oder `/api/config` | Informationsabfluss | expliziter Public-Serializer |
| unbekanntes Profil wird erst nach Admission erkannt | Slot-/Recorderverbrauch durch ungültige Anfrage | Resolver vollständig vor `reserve()` |
| Backend-/Modellfehler propagiert ungefiltert | interne Pfade/Details gelangen zum Client | typisierte öffentliche Fehler plus interne Logs |
| nicht atomare Runtimeänderung und Profilauflösung | gemischte Sessionkonfiguration | gemeinsamer Settingslock und Snapshot |

### 8.2 Mittlere Priorität

| Risiko | Auswirkung | Gegenmaßnahme |
| --- | --- | --- |
| OpenWakeWord wird pro Wake-Session geladen | zusätzlicher RAM/CPU, Verbindungsaufbau blockiert | Kapazität messen, optional separates Wake-Session-Limit oder später Lazy Recorder Creation |
| unauthentifizierter Client kann teureres Wake-Profil wählen | Ressourcen-DoS innerhalb des Sessionlimits | kleine feste Profilmenge, Hard Caps, Rate-/Connection-Limits am Proxy, Monitoring |
| Profildefinition und Admin-Baseline überlagern sich | unerwartete Wirkung von `/api/wake-word` und PATCH | klare Vererbungs- und API-Regeln |
| positiver `wake_word_activation_delay` | `start` meldet entgegen Vertrag zunächst `listening` | im Pflichtprofil auf 0 festlegen |
| flache Settingskopie | mutable Konfigurationsobjekte könnten geteilt bleiben | Deep Copy/frozen Typen |

### 8.3 Niedrigere, aber zu dokumentierende Risiken

- Profil-IDs sind nicht geheim und erscheinen in URL-/Proxylogs.
- URL-Encoding muss nur dekodiert und anschließend gegen die ASCII-Allowlist geprüft werden; keine automatische Normalisierung.
- Ein korruptes Wake-Modell kann trotz Startup-Dateiprüfung erst bei Recordererzeugung auffallen.
- Realtime-/Final-Ereignisse laufen nebenläufig; Profilmetadaten sollten nicht bei jedem Textevent dupliziert werden, sofern nicht nötig.
- Der stark geänderte, nicht eingecheckte Workspace erschwert spätere Diff-/Regressionseinordnung. Vor Implementierungsbeginn ist ein sauberer Baseline-Commit sinnvoll.

## 9. Empfohlener Implementierungsplan

### Phase 0 – Vertrag präzisieren

1. Produktionsdefault für Altclients festlegen, empfohlen `wake_word`.
2. `realtime_callback` als Enum korrigieren.
3. Einheit von `early_transcription_on_silence` als Sekunden festschreiben.
4. `wake_word_activation_delay == 0` für das Pflichtprofil festschreiben.
5. konservative Feldallowlist aus Abschnitt 4.7 bestätigen.
6. YAML-only versus Runtimeprofilverwaltung entscheiden.

### Phase 1 – Profilmodell und Startupvalidierung

1. eigenes Profilmodul anlegen;
2. YAML-Loader um `default_session_profile` und `session_profiles` erweitern;
3. Profil-IDs, Feldtypen, Bereiche und Querbedingungen validieren;
4. Pflichtprofile prüfen;
5. Wake-Modell-ID über `WakeWordRegistry` sicher auflösen;
6. interne Profilstatus `available`, `unavailable`, `misconfigured` modellieren;
7. keine Profildefinition in Runtime-JSON oder öffentliche Settings persistieren.

### Phase 2 – Admission und Sessionkopie

1. Queryparameter vor Admission lesen;
2. doppelte/ungültige/unbekannte Werte vor Recordererzeugung ablehnen;
3. effektiven Settingssnapshot atomar und tief kopieren;
4. `admit_session(session_id, resolved_profile)` einführen;
5. Sessionprofil unveränderlich an `RecorderBackedRealtimeSession` binden;
6. Recorderkonstruktionsfehler sauber aufräumen und klassifizieren.

### Phase 3 – Protokoll und Beobachtbarkeit

1. `hello.sessionConfig` ergänzen;
2. direkte `ready`-Antwort ergänzen;
3. `settings` aus der effektiven Sessionkonfiguration senden;
4. `status` und Sessionmetriken um Profil/Activation/Wake ergänzen;
5. Audit-/Performance-Logs um Profil-ID und Aktivierungsmodus ergänzen;
6. Public-Serializer und Redaction korrigieren;
7. serverweiten Ready-Broadcast unverändert profilneutral halten.

### Phase 4 – Tests

Siehe Abschnitt 10. Erst wenn alle neuen und bestehenden Tests grün sind, sollte die VPS-Konfiguration angepasst werden.

### Phase 5 – Dokumentation und Rollout

1. `docs/client-development/` auf neuen Vertrag aktualisieren;
2. `docs/fastapi-server.md`, `api_fastapi_server/README.md` und Konfigurationsdoku ergänzen;
3. VPS-YAML um Profile erweitern;
4. Default zunächst auf `wake_word`;
5. Server deployen und mit alten Clients ohne Parameter testen;
6. Desktop-Client mit explizitem `direct_hotkey` freischalten;
7. nach Stabilitätsphase optional Defaultmigration bewerten.

## 10. Erforderliche Teststrategie

### 10.1 Unit-Tests des Profilresolvers

- fehlender Parameter;
- genau ein gültiger Parameter;
- doppelter identischer und doppelter unterschiedlicher Parameter;
- leerer Wert;
- Großbuchstaben, Leerzeichen, Unicode, Pfadzeichen, Punktsegmente;
- 64 Zeichen gültig, 65 Zeichen ungültig;
- unbekannte gültige ID;
- strukturell fehlerhaftes Profil;
- fehlendes Backend;
- fehlendes/mehrdeutiges Modell;
- ungültiges Framework;
- NaN/Infinity bei jedem Floatfeld;
- Bereichs- und Querbedingungen;
- verbotene globale/shared Felder;
- Deep-Copy-Nachweis;
- Profiländerung beeinflusst bereits aufgelöste Session nicht.

### 10.2 Recorderkonfigurations-Tests

Mit `FakeRecorder`:

- `direct_hotkey` erhält leeres Backend/leere Wake Words;
- `wake_word` erhält nur intern aufgelösten Modellpfad;
- beide Recorder parallel besitzen unterschiedliche effektive Settings;
- Startstatus ist `listening` beziehungsweise `wakeword_wait`;
- `clear`, `stop` und erneutes `start` behalten das Profil;
- Follow-up-Timer und Recorderattribute bleiben auf der Wake-Session;
- globale Settings bleiben unverändert.

### 10.3 WebSocket-Protokolltests

- `hello.sessionConfig` vollständig und konsistent;
- direkte `ready`-Antwort wiederholt dieselbe Struktur;
- globales `ready` darf sie auslassen;
- Defaultprofil bei fehlendem Parameter;
- Fehlerpayload und Close-Code `1008`;
- kein `hello` nach Profilfehler;
- `activeSessions`, Pending-Reservations und Recorderinstanzen bleiben bei ungültigem Profil unverändert;
- Reconnect erzeugt neue Session-ID und frische Profilkopie;
- bestehende Befehle und Binäraudio bleiben kompatibel.

### 10.4 Echte Isolationstests

Mindestens zwei gleichzeitige Sessions:

```text
Session A: direct_hotkey
Session B: wake_word
```

Zu beweisen:

- A transkribiert Sprache ohne Wake Word.
- B transkribiert dieselbe Sprache vor Wake-Erkennung nicht.
- B akzeptiert während `wakeword_wait` kontinuierlich Audio.
- Wake-Erkennung öffnet nur B.
- Follow-up und Timeout von B ändern Status/Recorder von A nicht.
- beide nutzen weiterhin dieselben ASR-Lanes.

Der reine Callbacktest mit `FakeRecorder` ist wichtig, aber kein vollständiger Nachweis der realen Wake-Word-Audioerkennung. Dafür sollte ein opt-in Integrationstest mit dem tatsächlich deployten OpenWakeWord-Modell und einem rechtlich nutzbaren Wake-/Sprach-Audiofixture vorgesehen werden.

### 10.5 Regression und Deployment

- vorhandene FastAPI-Protokoll- und Multi-User-Tests;
- gesamte Unit-Test-Suite;
- OpenAI-kompatibler Endpoint;
- Parallel-Realtime-Validator;
- Containerstart mit der echten VPS-YAML;
- Healthcheck und Modell-Lifecycle;
- WSS-Smoke-Test über den realen Reverse Proxy;
- alte Browser-/Desktopclients ohne Queryparameter;
- neuer Desktopclient mit beiden Profilen.

### 10.6 Aktuell geprüfte Baseline

Mit der vorhandenen Projekt-Venv:

```powershell
.\.venv\Scripts\python.exe -m unittest -v `
  tests.unit.test_fastapi_server_protocol `
  tests.unit.test_fastapi_server_multi_user
```

Ergebnis am Prüfdatum:

```text
Ran 50 tests
OK
```

Damit ist der relevante aktuelle FastAPI-/Session-Baselinezustand grün. Die neuen Profiltests existieren naturgemäß noch nicht.

## 11. Erwartete Dateiauswirkungen

### Sicher betroffen

- `api_fastapi_server/server.py`
- neues `api_fastapi_server/session_profiles.py`
- `VoiceSTT_server/operations.py`
- `tests/unit/test_fastapi_server_protocol.py`
- `tests/unit/test_fastapi_server_multi_user.py`
- `docker/vps/voice/stt-config.yaml`
- `docs/client-development/01-session-und-server-scope.md`
- `docs/client-development/02-websocket-protokoll.md`
- `docs/client-development/03-server-events-kurzreferenz.md`
- `docs/client-development/04-server-events-katalog-und-chronologie.md`
- `docs/client-development/05-client-zustandsmodell.md`
- `docs/client-development/07-robustheit-grenzen-und-sicherheit.md`
- `docs/fastapi-server.md`
- `api_fastapi_server/README.md`

### Optional betroffen

- `api_fastapi_server/static/index.html`, falls Profilanzeige/-wahl in der eingebauten UI gewünscht ist;
- `VoiceSTT/core/*` und Engineadapter nur dann, wenn heute wirkungslose/geteilte Felder wie Prompts, `vad_filter`, Realtime-Min/Max oder `realtime_batch_size` wirklich sessionlokal gemacht werden sollen;
- Docker-/Nginx-Tests, nicht zwingend die Proxykonfiguration selbst.

## 12. Konkrete Empfehlung

Die Spezifikation sollte umgesetzt werden, aber in einer konservativen Version 1:

1. Fokus auf die beiden Aktivierungsprofile und bereits nachweislich sessionlokale Recorderwerte.
2. Shared-Worker-Werte und heute wirkungslose Felder explizit ablehnen.
3. Profilauflösung vollständig vor Admission/Recordererzeugung.
4. Wake-Modell ausschließlich über serverseitige Modell-ID auflösen.
5. Effektive Sessionkonfiguration tief kopieren und unveränderlich halten.
6. Öffentliche Settings vor dem Rollout auf Pfad-/Promptlecks bereinigen.
7. Im ersten VPS-Rollout `wake_word` als Default verwenden, um Altclients nicht zu verändern.
8. Erst nach grünen Unit-, WebSocket-, Isolation-, Real-Wake- und Proxytests den Desktop-Client auf explizite Profilauswahl umstellen.

Unter diesen Bedingungen ist das Vorhaben überschaubar und risikoarm genug für eine gezielte Servererweiterung. Der kritische Erfolgsfaktor ist nicht die Profilauswahl selbst, sondern die ehrliche Trennung zwischen tatsächlich sessionlokalen Recorderparametern und den weiterhin geteilten ASR-Workerparametern.
