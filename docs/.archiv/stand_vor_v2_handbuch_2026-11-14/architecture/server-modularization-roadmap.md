# Voice-STT-Server: Modularisierungsfahrplan

**Stand:** 25.10.2026 · **Basis:** `feat/v2-unified-kroko` ·
**Arbeits-PR:** [#15](https://github.com/marcosudau-vps/voice-stt-server/pull/15)

## Zielbild

Die umfangreiche `api_fastapi_server/server.py` soll langfristig **Kompositionswurzel**
sein: App erzeugen, abhängige Dienste verdrahten, Router registrieren, starten und
stoppen. Fachlogik, Zustandsmaschinen, Transport, Authentifizierung und
Modellverwaltung sollen in ausdrücklich zuständigen Modulen leben.

**Leitprinzip:** in kleinen PR-fähigen Schnitten extrahieren, bestehenden Vertrag
erst einmal unverändert lassen, Schnittstellen und Tests stabilisieren. Eine
Dateiverschiebung allein ist keine Verbesserung, wenn dabei Zyklen, globale
Zustände oder eine neue riesige `utils.py` entstehen.

## Komponentenmatrix / „Schlachtplan“

Der Stand bezieht sich auf die Quellstruktur im Arbeitsbranch von PR #15;
**keine** Aussage über schon gemergte oder produktiv ausgerollte Versionen.

| Bereich / Komponente | Heutige Situation / Verantwortung | Zielmodul und notwendige Grenze | Empfehlung / Zeitpunkt |
| --- | --- | --- | --- |
| **OpenAI-HTTP-Routen** | `GET /v1/models`, `POST /v1/audio/transcriptions`, Upload, SSE, Formate und HTTP-Telemetrie lagen zusammen in `server.py` | `api_fastapi_server/openai_routes.py`, `create_openai_router(...)` mit expliziter Service-/Codec-/Auth-Injektion | **JETZT – im PR #15 extrahiert.** Nach Linux-/Windows-CI und unabhängiger Prüfung abschließen |
| **OpenAI-Format-/Formularlogik** | Bereits in `VoiceSTT_server/openai_compat.py` | Bestehende Modulgrenze unverändert weiterverwenden; später allenfalls mit Routen in Fachpaket umordnen | **BELASSEN.** Kein zweites Parsing-/Response-Modul erfinden |
| **Security / Gatekeeper** | Admin-, OpenAI- und Log-Zugriff waren über ASGI-Routen und `VoiceSTTService` verteilt | `api_fastapi_server/security/`: `SecurityService` als einheitliche Schnittstelle mit spezialisierten Admin-, OpenAI-, Log- und Kroko-Adaptern | **JETZT – im PR #15 extrahiert.** Unveränderte Zugriffsscope-/401-/403-Verträge ausführlich testen |
| **Kroko-Lizenz** | Eff. Key, WebSocket-Probe und flüchtiger Modell-Lizenzstatus liegen separat unter `VoiceSTT/kroko/`; der Security-Adapter wertet die Policy automatisch aus (Init, Refresh/Switch, Force-Änderung, expliziter Recheck) und der `STTModelManager` erzwingt sie als lesende `license_policy` vor jeder Admission | **JETZT – in PR #15 integriert.** UUID aus `.data`-Header, Community auch unter Pro-Runtime, Pro nur mit frischem modellgebundenem Nachweis; echte Pro-Lizenztests Opt-in, Anbieter-Limits/Widerruf weiter offen |
| **Logtoken-Lebenszyklus** | 24h-Token-Ausgabe und Scopeprüfung waren im Service und den Log-Routen gemischt | `security/logs.py`: Tokens, Sessionbindung, Ablauf und getrennte HTTP-/WS-Policy | **JETZT – im PR #15 extrahiert.** Nie Logtoken mit Admin-Key verwechseln |
| **Log-HTTP- und -WebSocket-Routen** | Historie, SQLite-Replay, Subscriptions, Filter, Kanalrechte und Streaming bleiben in `server.py` | `api_fastapi_server/log_routes.py`; Event-Hub über Schnittstelle statt Rückimport der Serverdatei | **ALS NÄCHSTES.** Hoher Nutzen, gut abgrenzbar, aber WS-Replay-/Cursor-Contract absichern |
| **Admin-/Konfigurationsrouten** | REST für Konfiguration, Laufzeitparameter, Settings-Registry, Reload, Logging, Sprache | `routes/admin.py`, `routes/settings.py`, `routes/logging_config.py` mit Service-API | **ALS NÄCHSTES.** In 2–3 thematischen Schnitten; Sicherheit aus PR #15 vorher festigen |
| **Modell-Adminrouten** | `/api/models/*`, Load/Unload, Refresh, aktive Modelle und Last-Known-Good-Switch | `routes/models.py`; STTModelManager bleibt fachliche Authority | **BALD.** Relativ klare HTTP-Grenze, keine neuen Modell-Semantiken einbauen |
| **OpenAI-Inferenzkoordination** | `transcribe_openai`, `complete_pending_api_transcription`, Pending-Result-Map im `VoiceSTTService` und Scheduler-Callbacks | Eigener `OpenAIInferenceAdapter` **oder** verallgemeinerter Request-Korrelator; Scheduler akzeptiert weiterhin Jobs, liefert Resultate | **SPÄTER.** Erst nach HTTP-Extraktion; Race-, Timeout-, Cancel- und Pending-Result-Tests festigen |
| **Modellkatalog/Aliasse** | `model_catalog`, `resolve_openai_model`, Registry und Zwei-Lane-Modellwechsel | Gemeinsamer Modellkatalog/Resolver außerhalb von HTTP, OpenAI-spezifisches Alias-Mapping als Adapter | **BALD–SPÄTER.** `model_catalog` wird auch von Adminrouten genutzt, nicht exklusiv nach OpenAI verschieben |
| **Runtime-Settings/ServerSettings** | große Dataclass, Defaults, Coercion, Runtimekonfig, persistierte Overlay-Regeln | `settings/` für Definition, Validator, Projektion; bestehendes `settings_control.py` nicht duplizieren | **BALD.** Erst Definitionen und Hilfsfunktionen extrahieren; Persistenzvertrag unverändert |
| **Inferenz-Scheduler** | `InferenceJob`, `InferenceResult`, `FairInferenceQueue`, `SharedEngineWorker`, `InferenceScheduler` in `server.py` | `inference/` mit eigenständigen Datentypen, Queue, Worker, Scheduler; Service injiziert Scheduler | **GUTER FOLGESCHRITT**, aber **nach** Router-/Security-Schnittstellen. Hoher Gewinn, hohe Parallelitäts-/Fairness-Risiken |
| **Recorder-/Session-Runtime** | `RecorderBackedRealtimeSession` ist ein sehr großer Zustandsblock mit Audio, Wake Word, Aktivierung und Events | Stückweise Delegation an vorhandene `activation.py`, `wake_admission.py`, `segment_ledger.py`; später `session/` | **BEWUSST SPÄTER.** Hohe Race-/Wire-/Lebenszyklus-Risiken, keine Komplettverschiebung in einem PR |
| **SessionStore und ConnectionManager** | Session-Zulassung, Reservierungen, Speaker-Limits, WebSocket-Ausgabe | `sessions/store.py` und `transport/connections.py` mit kleinen Ports | **BALD.** Kleine überschaubare Klassen; vor Session-Runtime abspalten |
| **V1-/V2-WebSocket-Routen** | `/ws/transcribe` und `/ws/v2` registrieren und transportieren Sitzungen | `transport/ws_v1.py`, `transport/ws_v2.py`; vorhandenes `protocol_v2/` ist weiterhin Vertragseigentümer | **SPÄTER.** Versioniertes Protokoll strikt unverändert lassen; Client-Paartest und Race-Tests nötig |
| **Wake Word / Detection** | Teile bereits in `wake_admission.py`, `VoiceSTT/core/wake_detection.py`, Katalog authority; viel Sitzungsverhalten noch inline | Vorhandene Authority beibehalten und nur fehlende Adapter/Orchestrierung auslagern | **NACH SESSIONSCHNITT.** Keine zweite Zustandsmaschine schaffen |
| **Audio-Konvertierung und Upload-Codecs** | `decode_audio_float32`, WAV-Hilfen, Resampling in `server.py` | `audio/decoding.py` und `audio/resampling.py` mit stabilen Datentypen | **BALD.** Reine Funktionen zuerst; Audioformat-/Rundungsäquivalenz testen |
| **Logging/Metriken** | Event-Hub und `operations.py` bereits vorhanden, aber HTTP/SSE-/Sessionaufrufe verteilt | Instrumentierung in Fachadaptern, zentrale Sink-/Schema-Authority behalten | **FORTLAUFEND.** Events, Feldnamen, IDs und Reihenfolge dürfen nicht durch Extraktion driften |
| **Service-Orchestrierung** | `VoiceSTTService` verkettet Scheduler, Modelle, Settings, Sessions, Events, Lifecycle | Schmales Application-Service mit klaren Ports; Fachautoritäten bei ihren Komponenten | **ZULETZT sukzessive.** Erst andere Module schaffen, dann nur verbleibende Orchestrierung belassen |
| **App-Factory / Startup** | `create_app`, Lifespan, Uvicorn-CLI und globale Imports in `server.py` | Kleine `server.py` als Kompositionswurzel, optional `app_factory.py` / `cli.py` | **ZULETZT.** Nicht vor fachlicher Zerlegung neue Aufrufketten und Importzyklen schaffen |

## Empfohlene Durchführung in Etappen

| Phase | Arbeitsergebnis / Test-Fokus | Weiter erst, wenn ... |
| --- | --- | --- |
| **A – PR #15** | OpenAI-Router, vier Security-Gates inkl. automatischem Kroko-Lizenz-Lifecycle mit Manager-Integration, gezielte Unit-/HTTP-/WS-/Live-Tests, unveränderte bestehende V2-Semantik | Windows-/Linux-CI grün, unabhängiger PR-Review |
| **B – kleinere API-Fachmodule** | Log-Router, Admin-/Settings- und Modell-Router, getrennt pro Schnitt | API-Vertrag und Audit-/Cursor-Snapshots stabil |
| **C – technische Kerne** | Audiocodecs, SessionStore, ConnectionManager, danach Queue/Worker/Scheduler | Last-/Race-/Abbruch-/Parallelitäts-Tests belastbar |
| **D – komplexe Sitzungslogik** | RecorderBackedRealtimeSession in kleine Verantwortlichkeiten zerlegen | V1-/V2-Client-Paartests, Wake-/Activation-Regressionssuite bestanden |
| **E – Aufräum-/Release-Schnitt** | `VoiceSTTService` verschlanken, App-Factory finalisieren, Doppelimporte/Altcode entfernen | End-to-End-, Release- und Build-Identitätstests bestanden |
| **Separat: Kroko Pro** | Betreiberlizenz vs. Modellrechte, Widerruf/Monitoring, Nutzungsreports | Anbieter-Limits/Reporting/Widerruf und echte autorisierte Positiv-/Negativtests je Release vorliegen |

## Nicht verhandelbare Architekturregeln

1. **Keine Zyklen:** Fachmodule importieren niemals `api_fastapi_server.server`.
2. **Eine Authority pro Zustand:** Eventstore, Modellverwaltung, Settings, Wake-
   und Activation-State nicht bei jeder Extraktion duplizieren.
3. **Security bleibt fachlich getrennt:** Admin-Authentifizierung, Log-Zugriff,
   OpenAI-API-Zugang und externe Kroko-Lizenz sind keine austauschbaren Tokens.
4. **Transporte ≠ Fachlogik:** HTTP-/WS-Adapter autorisieren und übersetzen;
   Inferenz und Modellverwaltung arbeiten über stabile Dienstschnittstellen.
5. **Verhaltensgleiche erste Stufe:** Änderungen am Wire, Persistenzschema oder
   Berechtigungsumfang gehören in eigene, klar begründete Folgepakete.
6. **Messbare Fortschritte:** entfernte Zeilen, ersetzte Abhängigkeiten,
   Tests und Restschulden dokumentieren; nicht nur Dateien zählen.
7. **Keine Secrets im Code, Repo, CI-Log oder Telemetrie.**
8. **PR-Grenzen klein halten:** Architektur-Schnitt und neue Fachfunktion nicht
   im selben Arbeitspaket vermischen.

## Stand und ausstehende Qualifikation

Dieser Fahrplan ist ein technisches Arbeitsdokument und keine
Releasefreigabe. Die Extraktion in PR #15 wird gegen vorhandene Tests
geprüft; der Korrekturlauf integriert zusätzlich den automatischen
Kroko-Lizenz-Lifecycle mit Opt-in-Echtlizenztests. Anbieter-Connection-Limits,
Nutzungsreports, Widerrufssemantik und produktive Runtimewechsel gehören
ausdrücklich **nicht** zur vorliegenden Abnahme. Die kommenden
Etappen sind Vorschläge, keine bereits umgesetzten Änderungen.
