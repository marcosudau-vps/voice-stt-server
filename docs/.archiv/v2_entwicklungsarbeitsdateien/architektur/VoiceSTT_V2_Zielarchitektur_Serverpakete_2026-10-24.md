# VoiceSTT V2 – Zielarchitektur und Ist→Soll-Migrationskarte

**Stand:** 24.10.2026 · **Status:** verbindliche Zielrichtung für den überarbeiteten Implementierungsauftrag; konkrete Extraktionsgrenzen werden vor Code anhand der dann aktuellen HEADs überprüft.
**Repository:** https://github.com/marcosudau-vps/voice-stt-server
**Untersuchte Stände:** `feat/v2-unified-kroko` (`acdffc7042357cb8ae5e47961e42b78a25bd902c`) und `work/ap-kr-020-restintegration` (`03b813f27b4f707758ca14bdd1cf5d7d59edeb88`). PR #12 (`454e497...`) und PR #13 (`58a85b7...`) liegen auf eigenen Branches. Der ausführende Agent muss Branch-/PR-HEADs, Dateien und Tests vor Beginn erneut verifizieren.

> **Zweck:** Ein nachvollziehbares Ziel für die **moderne serverseitige Python-Architektur** schaffen, ohne vorhandene Wire-, Import-, Packaging-, Sicherheits-, Lizenz- oder Recovery-Verträge zu brechen. Diese Datei ist eine **Planung**, kein Bericht über bereits umgesetzte Moves. Wo ein Pfad mit `→` angegeben ist, handelt es sich um eine **beabsichtigte** Zuordnung, nicht um eine bereits erfolgte Änderung.

## 1. Befund: vier Namen, unterschiedliche Funktionen

| Ist-Paket | Reale Funktion | Konsequenz |
|---|---|---|
| `api_fastapi_server/` | **Implementierung** des modernen FastAPI-Multiuser-Servers samt HTTP, `/ws/transcribe`, `/ws/v2`, Scheduler, Sessions und Adminoberfläche | Fachlich aufteilen und zur modernen Serverimplementierung im kanonischen Paket machen; bisherigen Import-/Skriptpfad zunächst erhalten |
| `VoiceSTT_server/` | Moderner CLI-**Wrapper** (`server.py`), serverseitige Hilfen (Logging, Modellmanager, Persistenz, OpenAI-Kompatibilität), **eigenständiger alter Zwei-Port-Server** (`stt_server.py`) und dessen CLI-Client | Moderne Hilfen verlagern; Legacyserver ausdrücklich isolieren und kompatibel halten |
| `voice_stt_server/` | Bereits eingeführter **öffentlicher Python-Paketname** beider Distributionen; gegenwärtig hauptsächlich Lazy-Re-Exports auf `VoiceSTT` sowie `_embedded.py` für native Provenienz | **Zielheimat der modernen Serverimplementierung**. Bestehende `__init__.py`-Exports und `_embedded.py` unverändert kompatibel halten; Import weiterhin leichtgewichtig |
| `VoiceSTT/` | Recorder-, Audio-, VAD-, Wake-Word- und Transkriptions-Engine-**Kernbibliothek**, außerdem Kroko-Laufzeit- und Buildhilfen | Kernbibliothek **nicht** in den Server verschieben; getrenntes späteres Strukturrefactoring möglich |

**Präzisierung von „V1“:** Der moderne FastAPI-Server enthält den älteren WebSocket-Endpunkt `/ws/transcribe` **und** das eingefrorene `/ws/v2`. Daneben besitzt `VoiceSTT_server/stt_server.py` einen anderen, eigenständigen **Control-/Data-Zwei-Port-Server**, erreichbar als `stt-server-legacy`. Diese drei Wirepfade nicht verwechseln und nicht beim Umräumen miteinander fusionieren.

**Startkette aktuell:** `voice-stt-server` und `stt-server` → `VoiceSTT_server.server:main` (27-zeiliger Forwarder) → `api_fastapi_server.server:main` (moderne Implementierung); das Dockerfile startet derzeit `python3.12 -m VoiceSTT_server.server`. Die beiden öffentlichen Distributionen heißen `voice-stt-server`/`voice-stt-server-pro`, exponieren aber **denselben** Python-Importnamen `voice_stt_server`. `VoiceSTT` bleibt die bestehende Implementierung der Recorder-API.

**Größen/Hotspots zum geprüften Stand:** `api_fastapi_server/server.py` ~10.634 Zeilen, `api_fastapi_server/settings_control.py` ~1.420, `VoiceSTT_server/event_logging.py` ~1.363, `VoiceSTT_server/stt_model_management.py` ~1.184, `VoiceSTT/core/realtime.py` ~1.049, `VoiceSTT_server/stt_server.py` ~917. Die **wichtigste** Entflechtung ist die moderne `server.py`, nicht nur ein Umbenennen der Ordner.

## 2. Architekturprinzipien und beschlossene Grenzen

1. **Ein modularer moderner Server, keine zweite Implementierung.** `voice_stt_server` wird Ziel für moderne Server- und Managementlogik. `api_fastapi_server` und `VoiceSTT_server` behalten bei Bedarf dünne, explizite **Kompatibilitätsfassaden**, aber keine parallel gepflegten Laufzeitautoritäten.
2. **Klare Abhängigkeitsrichtung:** Transport/HTTP/WebSocket → Anwendung/Koordinatoren → fachliche Serverkomponenten → `VoiceSTT`-Recorder-/Engine-/Kroko-Autoritäten. `VoiceSTT` importiert nicht `voice_stt_server`; niedrigere Module importieren nicht FastAPI-App-Erzeugung oder Transportadapter. Dependency Injection/Ports statt Importzyklen.
3. **Genau eine maßgebliche Autorität je Zustand:** Sessionaktivierung, Segmentledger, Runtime-Scheduler, Server-Settings-Revision, Modellinventar, Kroko-Lizenzstatus, Downloadjobs und Eventstore sind unterschiedliche Zuständigkeiten. Nur Projektionen dürfen sie zusammenführen; keine replizierten Wahrheiten.
4. **Bestehende Verträge erhalten:** öffentliche Lazy-Exports (`voice_stt_server`, `VoiceSTT`), die konsolidierten `voice-stt-server`/`stt-server`-CLI-Aliasse, `stt-server-legacy`, V1/V2-Wire, bestehende HTTP-APIs, Settings-Control-Plane (AP-SRV-050), Activation/Segmentledger, Replay, LKG/Recovery und Kroko-Owner/License-Semantik.
5. **Struktur zuerst, Verhalten später:** Move-only-/Charakterisierungsschritte von Featureänderungen und Sicherheits-/Runtimekorrekturen in getrennten Commits und Evidenz absichern. Große 10k-Zeilen-Datei in nachvollziehbaren Schritten zerlegen; nicht per blindem Bulk-Move oder dynamischer Modulalias-Manipulation.
6. **Kompatibilität ist konkret zu testen:** Re-Export reicht bei `monkeypatch`/`mock.patch` des alten Modulnamens, direkten Skriptstarts, importseitigen Singleton-Objekten oder Seiteneffekten **nicht automatisch**. Prüfe jeden tatsächlich genutzten Import-/Patch-/Startpfad.
7. **Kein künstliches Dateiwachstum:** Das nachfolgende Baumziel ist eine **fachliche Zuordnung**. Nur Dateien erzeugen, wenn sie tatsächlich eigene zusammenhängende Verantwortung tragen. Kein dogmatisches 1-Klasse-pro-Datei und keine neuen leeren Platzhalter.

## 3. Zielstruktur – moderne Serverseite

```text
voice_stt_server/                        # kanonisches modernes Server-Pythonpaket
├── __init__.py                         # BESTEHENDE leichte Lazy-Re-Exports
├── _embedded.py                        # BESTEHENDE Kroko-Wheel-Provenienz
├── application.py                      # create_app, Composition Root, Lifespan/DI
├── cli.py                              # parse_args, settings_from_args, main
├── api/
│   ├── http/                           # modular registrierte FastAPI-Router
│   │   ├── status.py                   # /health, /api/v2/info, /api/v2/server/status
│   │   ├── settings.py                 # /api/config, /api/v2/settings/*
│   │   ├── models.py                   # Legacy-Modellendpunkte + /api/v2/stt/*
│   │   ├── sessions.py                 # session-/language-/wake-word-Routen
│   │   ├── logs.py                     # /api/logs/* und übrige operative Routen
│   │   └── openai.py                   # /v1/models und Transkriptions-Endpunkte
│   ├── websocket/
│   │   ├── legacy_v1.py                # /ws/transcribe; identischer Legacy-Wire
│   │   ├── v2/                         # aus api_fastapi_server/protocol_v2/
│   │   │   ├── commands.py
│   │   │   ├── connection.py
│   │   │   ├── events.py
│   │   │   ├── handshake.py
│   │   │   ├── identity.py
│   │   │   ├── ports.py
│   │   │   ├── schema.py                # eingefroren, KEIN Vokabular-Redesign
│   │   │   ├── session.py
│   │   │   └── snapshot.py
│   │   └── logs.py                     # /ws/logs; bestehender Hub
│   ├── protocol.py                     # Binärpacketformat und Parser
│   └── openai_compat.py                # pure REST/OpenAI-Payload-Helfer
├── sessions/
│   ├── activation.py                   # BESTEHENDE ActivationController-Autorität
│   ├── commands.py                     # Befehls-/Replay-Identitäten
│   ├── segment_ledger.py               # BESTEHENDE SegmentLedger-Autorität
│   ├── wake_admission.py               # Wake→Activation-Grenze
│   ├── store.py                        # SessionStore/Admission
│   └── runtime.py                      # RecorderBackedRealtimeSession etc.; schrittweise
├── inference/
│   ├── contracts.py                    # InferenceJob/Result/QueueSubmitResult
│   ├── queue.py                        # FairInferenceQueue
│   ├── workers.py                      # SharedEngineWorker
│   └── scheduler.py                    # InferenceScheduler/Executor
├── models/
│   ├── contracts.py                    # Produkt/Kandidat/Installation/Snapshot
│   ├── inventory.py                    # Discovery, Integrität, externe Leseablagen
│   ├── storage.py                      # serververwaltete Installationen/Löschung
│   ├── downloads.py                    # ein Jobmanager für beide Engines
│   ├── runtime.py                      # Modell-Runtime-/Recovery-Steuerung
│   └── manager.py                      # STTModelManager / einheitliche Fassade
├── settings/
│   ├── definitions.py                  # ServerSettings, öffentliche Feldverträge
│   ├── control.py                      # AP-SRV-050-Registry und Patchlogik
│   ├── persistence.py                  # RuntimeConfigStore
│   └── cli_config.py                   # YAML/CLI-/ENV-Adaptierung, sofern nötig
├── observability/
│   ├── events.py                       # StructuredEventHub/SQLite/JSONL
│   ├── metrics.py                      # Performance-/Runtime-Messwerte
│   └── status.py                       # read-only Statusprojektionen
├── security/
│   ├── admin_auth.py                   # bereits bestehende Admin-Guards, nur Extraktion
│   └── redaction.py                    # Credential-Redaktion
└── web/
    └── index.html                      # bisher api_fastapi_server/static/index.html

VoiceSTT/                                # KERNBIBLIOTHEK: bleibt getrennt
├── audio_recorder.py
├── core/...
├── transcription_engines/...
└── kroko/...

api_fastapi_server/                     # übergangsweise schlanke Kompatibilität
├── server.py                           # ältere Imports, create_app/CLI-Skriptstart
├── protocol_v2/...                     # falls alte vollständige Imports gebraucht
└── ...                                 # nur nach nachgewiesener Verwendung

VoiceSTT_server/                        # übergangsweise CLI-/Legacy-Kompatibilität
├── server.py                           # moderne CLI-Fassade
├── stt_server.py                       # echter alter Zwei-Port-Server
├── stt_cli_client.py                   # dazugehöriger Client
└── ...                                 # weiter benötigte Re-Exports
```

**Nicht jede Route braucht sofort eine eigene Datei.** Bei einer großen `application.py`-Extraktion ist wichtig, dass die Router tatsächlich **aus einem Service-/Settings-Context** arbeiten, statt jeden Tag neue `from ...server import service`-Zyklen zu erzeugen. `application.py` baut die eine App, konfiguriert Lifespan, zentralen Service und registriert Router; Transportmodule besitzen keine unabhängigen Worker/Settings.

**Transitional vs. endgültig:** Vollständige fachliche Extraktion ist das Ziel. Wenn ein Legacyimport wegen seiner Seiteneffekte nicht in diesem Lauf risikofrei migriert werden kann, verbleibt eine **schmale und dokumentierte** Fassade – keine zweite funktionsfähige Implementierung. Vorhandene Kompatibilitätspfade dürfen nicht voreilig gelöscht werden.

## 4. Konkrete Ist→Soll-Zuordnung: moderne Serverkomponenten

| Quelle | Gegenwärtige Rolle / konkrete Typen | Zielbereich | Migrationsregel |
|---|---|---|---|
| `api_fastapi_server/server.py` `ServerSettings`, `runtime_settings_contract`, `coerce_setting_value` | Runtime-Felder, Schema-/Validierungshilfen | `settings/definitions.py` | Identische Defaults und Feldnamen; keine zweite Autorität |
| `api_fastapi_server/server.py` `load_yaml_config_defaults`, `parse_args`, `settings_from_args`, `main` | Konfig-/CLI-Start | `settings/cli_config.py`, `cli.py` | Argumente, ENV, Exitcodes, Startkommandos und Konfigurationsprecedence erhalten |
| `api_fastapi_server/settings_control.py` `SettingDefinition`, `SettingsRegistry`, `ServerSettingsState`, `SessionSettingsState` | AP-SRV-050-Control-Plane | `settings/control.py` | Atomare Revision/Persistenz/Session-Latching unverändert; altes Modul als Importadapter |
| `VoiceSTT_server/operations.py` `RuntimeConfigStore` | persistierte Runtimekonfig | `settings/persistence.py` | Genau ein Store; `settingsRevision` und Secretgrenzen bleiben |
| `api_fastapi_server/server.py` `SessionConfigurationError`, `SessionWakeWordRequest`, `ResolvedSessionWakeWordConfig`, `SessionActivationRequest` | Handshake-/Sessionkonfiguration | `sessions/` bzw. `api/websocket/` | Transportvalidierung von reiner Sessionkonfiguration trennen |
| `api_fastapi_server/activation.py`, `activation_commands.py`, `segment_ledger.py`, `wake_admission.py` | autoritative Session-Activation, Befehle, Ledger, Wake-Admisson | `sessions/activation.py`, `commands.py`, `segment_ledger.py`, `wake_admission.py` | **Move-only**; bei Paketnamenkonflikt präzise benennen. Kein Replay-/Phasen-/Timer-Redesign |
| `api_fastapi_server/server.py` `SegmentState`, `SegmentTimelineTracker`, `RecorderBackedRealtimeSession`, `InputClosePlan` | pro-Session-Recorder-Lifecycle und Timeline | `sessions/runtime.py` plus geeignete schmale Unterkomponenten | erst nach Charakterisierung; starke Kopplung an Callback/Lock/Worker beachten |
| `api_fastapi_server/server.py` `SessionStore` | Sessionregistrierung/Admission | `sessions/store.py` | unveränderte Sperren, Kapazität, Sessionidentitäten |
| `api_fastapi_server/server.py` `ConnectionManager` | Session-Sockets/Serverloop/Fan-out | `api/websocket/` oder Transport-Abstraktion | Eventloop-Bindung erhalten, nie im Domainlayer |
| `api_fastapi_server/server.py` `InferenceJob`, `InferenceResult`, `QueueSubmitResult`, `FairInferenceQueue` | Inferenzaufträge und Fairness | `inference/contracts.py`, `queue.py` | FIFO/Fairness/Cancellation/Per-Session-Semantik unverändert |
| `api_fastapi_server/server.py` `SharedEngineWorker`, `InferenceScheduler`, `SchedulerTranscriptionExecutor` | Engine-Erstellung, Worker-/Job-Lifecycle | `inference/workers.py`, `scheduler.py` | eine Schedulerinstanz, CPU-Regeln, Loaded-/Idle-/Sessionraces charakterisieren |
| `VoiceSTT_server/stt_model_management.py` `ProductModel`, `OperatorIntent`, `ModelCandidate`, `ModelSnapshot`, Discoveryadapter, `AtomicModelProvisioner`, `STTModelManager`, `ManagedModelRegistryView` | gemischte Modellautorität | `models/contracts.py`, `inventory.py`, `storage.py`, `downloads.py`, `runtime.py`, `manager.py` | echte Invarianten erhalten; `VoiceSTT_server.stt_model_management` als dünner Re-Export während Migration |
| `api_fastapi_server/server.py` `_probe_stt_model`, `refresh_stt_models`, `ensure_models_loaded`, `unload_models`, `_switch_models_locked`, `_model_idle_worker` | Modelllifecycle/Recovery in `VoiceSTTService` | `models/runtime.py` (mit injizierten Scheduler-/Owner-Ports), koordinierender Service | nicht einfach Methods kopieren: Locks, LKG, Kroko-Prozesswechsel und Sessions müssen gleich bleiben |
| `VoiceSTT_server/operations.py` `LocalModelRegistry`, `WakeWordRegistry` | historische Modell-/Wake-Word-Views | möglichst eine `models`-View bzw. bestehende Wake-Word-Autorität | alte `LocalModelRegistry` nur nach Aufruferprüfung ersetzen/entfernen; Wake-Word-Autorität NICHT neu bauen |
| `VoiceSTT_server/operations.py` `AuditLogManager`, `PerformanceLogManager` | Fassade für vorhandene Eventkanäle | `observability/events.py`/Adapter | weiterhin **ein** Eventstore/Hub |
| `VoiceSTT_server/event_logging.py` `StructuredEventHub`, `SQLiteEventStore`, `CalendarJsonlSink` | kanonische Telemetrie/Auditlogs | `observability/events.py` oder kleines Unterpaket | alten Eventstream/SQLite-Schema/Cursor beibehalten |
| `VoiceSTT_server/credential_redaction.py` | redigierte Logs/Status/Errors | `security/redaction.py` | keine Secrets bei neuen Importpfaden oder Fehlern |
| `VoiceSTT_server/openai_compat.py` | Datenvalidierung/Formatierung/SSE | `api/openai_compat.py` | OpenAI-REST-Kompatibilität inklusive Streaming unverändert |
| `api_fastapi_server/protocol.py` | Binary Packet Parser | `api/protocol.py` | Wire-Bytes unverändert |
| `api_fastapi_server/protocol_v2/*` | `ProtocolV2Connection`, Handshake, Session-Wire, Ports/Events, `schema.py` | `api/websocket/v2/*` | **Frozen schema** unverändert, Projektionen importieren Autoritäten statt Kopien |
| `api_fastapi_server/server.py` `create_app`, `lifespan`, Routen | Appbildung plus REST-/WS-Handler | `application.py` + `api/http/*`, `api/websocket/*` | App-/Request-/Dependencies einmalig verdrahten; erhaltene Endpointpfade/OpenAPI-Kennwerte testen |
| `api_fastapi_server/server.py` `RunningStats`, `metrics`, `process_memory_snapshot` | Metriken und Serviceprojektionen | `observability/metrics.py`, Statusprojektion | keine neuen Messwertspeicher |
| `api_fastapi_server/server.py` `VoiceSTTService` | Monolithischer Koordinator für alles | schrittweise **schlanker Anwendungsservice** in `application.py` bzw. `service.py` und Fachkomponenten | nicht duplizieren, keine unerlaubte mutable Facade; saubere Ports/DI, gemeinsame Locks |
| `api_fastapi_server/static/index.html` | aktuelle moderne Browser-/Admin-Konsole | `web/index.html` | `setup.py`-package_data, `INDEX_PATH`, Docker, direkte URL `/` und statische Tests anpassen |

Für `api_fastapi_server/server.py` sollten **Migrations-Charakterisierungstests** pro extrahierter Domäne vorliegen: Modell-/Servicezustand, Serversettings, Sessionstate, Worker/Queues, FastAPI-Router und V1/V2-Handshake. Die tabellarische Einteilung ist ein **semantischer Plan**, kein Versprechen, dass jede Methode ohne zusätzliche Port-/Dependency-Injection-Arbeit verschoben werden kann.

## 5. Kompatibilitätsschichten und übrige Dateien

| Aktueller Pfad | Einordnung und Soll |
|---|---|
| `VoiceSTT_server/server.py` | **Beibehalten** als schlanker dokumentierter CLI- und API-Forwarder zur neuen `voice_stt_server`-App; `python -m VoiceSTT_server.server` weiterhin unterstützen |
| `api_fastapi_server/server.py` | **Beibehalten** als minimale Import-/Skriptkompatibilität, solange benutzt. `create_app`, `ServerSettings`, `parse_args`, `settings_from_args`, `main` sowie direkt getestete Symbole nach Bedarf delegieren. Patchpunkte nicht unbemerkt entkoppeln |
| `api_fastapi_server/protocol_v2/*`, `activation.py`, `settings_control.py` usw. | Nach Migration nur die tatsächlich benötigten fachlich schlanken Kompatibilitätsmodule; Importtests für alle erhaltenen Pfade, keine duplizierte Session-Autorität |
| `VoiceSTT_server/stt_server.py` | **Echter Legacy-Zwei-Port-Server**. Vorerst separat mit `stt-server-legacy` erhalten; später ggf. verschieben nach `voice_stt_server/legacy/`, aber nur in eigenem getesteten Schritt. **Nicht** mit `/ws/transcribe` gleichsetzen |
| `VoiceSTT_server/stt_cli_client.py`, `install_packages.py`, `index.html` | Aufrufe und Nutzung des Legacyservers prüfen. `install_packages.py` wird im Legacy-Server bei Import verwendet – nicht blind entfernen. `index.html` ist eine ältere Zwei-WebSocket-Oberfläche, nicht die moderne `web/index.html` |
| `VoiceSTT_server/README.md`, `api_fastapi_server/README.md`, `api_fastapi_server/requirements.txt`, `run_multi_user_perf.cmd` | Technische Dokumentation/Requirements/Benchmarks aktualisieren und ggf. in `docs/`/`tools/` überführen, nachdem echte CLI-/CI-/Installationsverweise geprüft sind |
| `voice_stt_server/__init__.py`, `_embedded.py` | **Beibehalten und intern nicht schwerer machen.** `__version__`, `get_version`, Lazy-Reexports und Free-/Pro-Provenienz bleiben wahrheitsgemäß |
| `setup.py` | `find_packages`-Inklusion, Console-Scripts und Package-Data **gezielt** aktualisieren; `stt-server-legacy`, `stt`, `stt-server`, `voice-stt-server` bleiben vorerst verfügbar |
| `Dockerfile`, `docker-compose.yml`, `tools/build_distribution.py`, `tools/build_production.py`, `tools/release_candidate.py` | Entrypoint-/Pfad-/Resource-Abgleich, ohne native Buildidentitäten oder Releasevertrag leichtfertig umzubauen |

**Kernbibliothek `VoiceSTT/` – bewusst außerhalb dieses Server-Refactorings:**

- `audio_recorder.py` bleibt öffentliche Recorder-Fassade; `core/` ist intern bereits nach `initialization`, `lifecycle`, `recording`, `realtime`, `wakeword`, `voice_activity`, `transcription` usw. aufgeteilt. Unterpakete wie `core/recording/`, `core/realtime/`, `core/wakeword/` wären später sinnvoll, sind **nicht Voraussetzung** des aktuellen Serverauftrags. `VoiceSTT/core/wakeword_catalog.py` bleibt Wake-Word-Autorität.
- `transcription_engines/base.py`, `factory.py`, Engines und **`_model_utils.py`** bleiben Enginebereich. `_model_utils.py` verarbeitet primär Transkriptionsausgaben/Tensorwerte und ist **kein** Modellinventar. `model_resolver.py` bleibt lokale **downloadfreie** Modellpfadauflösung; Server gibt bevorzugt bereits autoritativ aufgelöste Pfade hinein.
- In `VoiceSTT/kroko/` bleiben `models.py`, `catalog.py`, `license_runtime.py`, `bootstrap.py`, `native_status.py`, `owner_process.py`, `supervisor.py` produkt-/native-spezifische Runtimeautoritäten. `artifacts.py`, `buildinputs.py`, `fingerprint.py` und `install_kroko.py` sind Build-/Packagingkandidaten; **nicht** zusammen mit dem Runtimeordner verschieben. Ein späteres gezieltes Buildtooling-Refactoring ist möglich, muss die Native-Fingerprintguards respektieren.
- `VoiceSTT/assets/*` bleibt an der über `setup.py` qualifizierten Paketressourcenautorität. **Keine** Wake-Word-, Kroko- oder Build-Assets pauschal in neue Verzeichnisse ziehen.
- Noch registrierte Engines wie `cohere`, `funasr`, `granite`, `moonshine`, `omnilingual`, `sherpa` entfernen wir **nicht** in diesem Agentenauftrag. Das wäre eine eigene **Produkt-/API-Reduktion** einschließlich Factory-Aliasse, optionaler Dependencies, Tests und Dokumentation; „nicht im Deployment genutzt“ genügt als Löschbeleg nicht.

**Beispielanwendungen:** `app_browserclient/server.py` und `app_webserver/server.py` sind nur Launcher für den modernen Server mit unterschiedlichen Defaults; `app_webserver/client.py` kommuniziert noch in einem anderen Legacy-Dialekt, dessen heutige Kompatibilität zu prüfen ist. Sie können später gesammelt unter `examples/` (oder `apps_extra/`) liegen; die Zusammenlegung ist **nicht Bestandteil des kritischen Server-Refactoring-Gates**. Links, Importpfade und Browserressourcen müssen vorher inventarisiert werden. Die alte `VoiceSTT_server/index.html` ist nicht mit der modernen Live-Konsole zu verwechseln.

## 6. Umsetzung in nachprüfbaren Strukturphasen

**S0 – Ausgangsschnitt und Vertragsinventar:** PR #12, Restintegration und PR #13 getrennt gegen aktuelles HEAD untersuchen, vorhandene Tests/CI lesen. Ein präzises `Import → Export → Monkeypatch → Laufzeitsymbol`-Inventar erstellen, inklusive `setup.py`, Docker, CLI, Docs und Tests; Datei-/Symbol-Move-Matrix dokumentieren. Vor jedem produktiven Code die in `AGENTS.md`/`docs/.archiv/README.md` verlangten Akten anlegen.

**S1 – Kanonisches Serverpaket vorbereiten:** bestehende `voice_stt_server/__init__.py`/`_embedded.py` erhalten; `application.py`/`cli.py`/Paketunterstruktur nur entsprechend tatsächlicher Extraktion einführen; Alteinstiege und Script-Aufrufe charakterisieren. Erst reine Hilfen (Redaktion, Statusdaten, OpenAI-Formate), dann Settings-Persistenz und reine Typen verschieben.

**S2 – Isolierte AP-Module übernehmen:** `activation`, `activation_commands`, `segment_ledger`, `wake_admission`, `settings_control`, Wire-/Protokolladapter unter korrekten Importgrenzen in `sessions`, `settings` und `api` überführen. **Keine** Änderungen an V2-Schema, Zeit-/Revisions-/Replaysemantik. Alte Test- und Importpfade sichern.

**S3 – Inferenz- und Sessionverantwortung herauslösen:** `InferenceScheduler`, Worker, Queue, SessionStore/Sessionruntime mit expliziter Kontextinjektion; erst charakterisieren und separat regressionsprüfen. Tatsächliche Lifecycleschreibrechte bleiben eindeutig; nie zwei Scheduler oder konkurrierende Queuezustände erzeugen.

**S4 – API-Router und Composition Root:** HTTP-/WS-Routen an bereits existierende Services binden, `create_app`/Lifespan/CLI in neue Module verlagern. Frische App-Instanzen in Paralleltests müssen isoliert sein. Alter Serverimport, Browserroute, OpenAPI-Schema, Requestauth, V1-/V2-/Logging-Wire müssen unverändert funktionieren.

**S5 – Neue Modellfeatures auf der neuen Heimat:** `voice_stt_server/models/` für Katalog, Inventar, sichere Ablage, Downloadjobs, Recovery/Runtime und Management; Settings/API-/Statusintegration entsprechend der Beschlussdatei. **Nicht** zuerst ein neues Modellpaket unter `VoiceSTT_server/stt_models/` bauen, das danach wieder migriert wird.

**S6 – Cleanup und Abschluss:** Nur nach Beleg alte doppelte Registries und verwaiste Imports entfernen, Dokumentation auf einen modernen Einstiegspunkt ausrichten, vollständige Tests/Builds/CI und Soll-Ist, verbleibende Legacywrapper explizit nachweisen. **Kein** automatischer Merge, Release oder Deployment.

**Reihenfolge mit PRs:** PR #12/Restintegration und #13 zunächst auf einen separaten, frischen Arbeitsbranch integrieren und **vor** strukturellen Moves Baseline-/Konflikttests ausführen. Danach S1–S5; beide ursprünglichen PRs nicht ungefragt mergen/schließen. Das neue Ergebnis landet in einem eigenen Review-PR gegen `feat/v2-unified-kroko`.

**Transaktions- und Beobachtbarkeitsschnittstellen:** Die moderne App hält weiterhin eine einzige `VoiceSTTService`-Autorität beziehungsweise einen schmalen Servicekoordinator. Die intern delegierten Fachobjekte dürfen **nur in der Appkomposition** erzeugt werden, nicht jeweils in einzelnen Routern. Bestehender Event-Hub, Settings-Revision, Recovery-LKG und Kroko-native Besitzerprozesse werden einmalig referenziert, nicht kopiert.

## 7. Migrations- und Regressionstore

| Gate | Geforderter Beleg |
|---|---|
| Import/CLI | `voice_stt_server` Lazy-Import, `VoiceSTT` Recorder, `VoiceSTT_server.server:main`, `api_fastapi_server.server:create_app`, direkte Skriptaufrufe, `stt-server-legacy`, `stt` |
| FastAPI | `/health`, `/api/v2/info`, `/api/config`, `/api/models/*`, `/api/v2/settings/*`, `/api/v2/wake-words`, `/api/logs/*`, `/v1/models`, `/v1/audio/transcriptions`, `/`, OpenAPI/Payloads |
| WebSockets | `/ws/transcribe`, **frozen** `/ws/v2`-Handshake, Events, Replay/Sessionstate, `/ws/logs` und berechtigte Zugriffssichten |
| Settings | `baseSettingsRevision`, persist-before-commit, atomare Fehlerbehandlung, alte Konfigurationsquellen/CLI/ENV, latched Sessionpolicy, Credential-Redaktion |
| Inferenz | Fairness, Cancellation, Workerwarmup, Final/Realtime-Status, Parallelclients, Schedulerstart/-stop, CPU-Regeln, keine zweite Workerinstanz |
| Modelle | LKG/Recovery, MINIMUM_READY, Load/Unload/Idle-3600/Lazy-Reload, Kroko-Owner-/Lizenzgrenzen, keine versteckten Downloads, neue Jobs/Security/APIs |
| Verpackung | `setup.py` find_packages/Entry Points/Package Data, `python -m build`, Wheel-Import/CLI/Browserressource aus sauberer Installation, Free-/Pro-Provenienz, Docker-Entrypoint; Heavy RC/Native-Gates gesondert korrekt melden |
| Dokumentation | `docs/module-map.md`, Konfiguration, API-Referenzen, Build-/Release-Dokumentation, Beispiele, alle relativen Links, kein historisches AP umschreiben |
| Arbeitsakte | Originalprompt wörtlich, datierter Plan vor Umsetzung, Ist-Matrix, Commitjournal, Test-/Security-Evidenz, gesonderte Soll-/Ist- und Abweichungsakte, Abschlussbericht, neuer Review-PR |

Gezielte bestehende Tests u. a.: `tests/unit/test_fastapi_server_protocol.py`, `tests/unit/test_fastapi_server_multi_user.py`, `tests/unit/test_fastapi_server_multi_user_asr_integration.py`, `tests/unit/test_settings_control_plane.py`, `tests/unit/test_settings_runtime_persistence.py`, `tests/unit/test_stt_model_management.py`, `tests/unit/test_kroko_unified_runtime.py`, `tests/unit/test_kroko_restintegration.py`, `tests/unit/test_kroko_catalog.py`, `tests/unit/test_local_model_resolver.py` sowie V2-Connection-/Replay-/Handshake- und Eventloggingtests. Der Agent muss tatsächliche vorhandene Dateinamen auf dem finalen HEAD prüfen. Das **mindeste** Hauptgate ist `python -m pytest -q tests/unit` in sauberer, dokumentierter Umgebung; zusätzlich Python-Compile, Packaging- und zielgerichtete realitätsnahe Integrationstests.

## 8. Abgrenzung und Evidenzstatus

- **Heute festgehalten:** ein gemeinsames modernes Serverpaket `voice_stt_server`, fachliche Abhängigkeits- und Authority-Grenzen, schrittweise sichere Integration, Modellpaket `voice_stt_server/models/`, Beibehaltung von Legacy-/Kernbibliotheksverträgen.
- **Vorschlags-/Implementierungsdetails:** konkrete Dateinamen jenseits dieser Paketgrenzen, wie weit sich `VoiceSTTService` innerhalb eines sicheren Agentenlaufs reduzieren lässt, Zahl der Router/Helpermodule. Diese Varianten sind nur nach dokumentierter Prüfung zulässig; sie dürfen die Architekturprinzipien nicht umkehren.
- **Bewusst nicht beauftragt:** tiefes `VoiceSTT/core`-Refactoring, Löschung ungenutzter Transkriptionsengines, pauschaler Kroko-Buildmodulumzug, Bereinigung aller `examples`-Launcher, neue V2-Wire-Nachrichten, Release/Deployment, Merges der bestehenden PRs.
- **Kroko-Blocker:** Katalogmetadaten sind keine Lizenz-/Downloadberechtigung; externe Modell-/Pro-Rechte- und API-Schnittstellen dürfen bis zum echten Nachweis nur `BLOCKED`/`CONDITIONAL` sein. Kein „grün“ durch reine Mocktests.

### Hauptquellen (unveränderte Repo-Pfade und Commitbasis)

- `AGENTS.md`, `docs/.archiv/README.md`, `docs/module-map.md`, `build/BUILD.md`
- `setup.py`, `Dockerfile`, `VoiceSTT_server/server.py`, `VoiceSTT_server/stt_server.py`, `voice_stt_server/__init__.py`, `voice_stt_server/_embedded.py`
- `api_fastapi_server/server.py`, `api_fastapi_server/settings_control.py`, `api_fastapi_server/protocol_v2/*`
- `VoiceSTT_server/stt_model_management.py`, `VoiceSTT_server/operations.py`, `VoiceSTT_server/event_logging.py`
- `VoiceSTT/kroko/{models,artifacts,buildinputs,fingerprint,license_runtime,owner_process,supervisor}.py`
- `VoiceSTT/transcription_engines/{factory,model_resolver,_model_utils}.py`
- `VoiceSTT_V2_Modellverwaltung_Beschlussstand_2026-10-24.md` (separate zuvor erstellte Beschlussakte)

Die vorgeschlagene Paketstruktur ersetzt **nicht** die funktionalen und sicherheitsrelevanten Festlegungen der bestehenden Beschlussdatei, sondern **konkretisiert deren internen Architektur- und Ablageort**.
