# Verbindliche Gliederung

Quelle: [Spezifikation V0.2](../SPEZIFIKATION_v0.2.md). Inhaltliche Beschreibungen sind Rechercheaufträge, keine technische Implementierungsbestätigung.

## 01 – Einstieg und Systemverständnis

- **01.01 Produktüberblick:** Ziel, Einsatzbereiche, Produktfunktionen.
  [Entwurf](../docs/v2-handbuch/01-grundlagen/01.01-produktueberblick.md) · [Eigene Hinweise](../workflow/notes/01.01.md)
- **01.02 Architekturübersicht:** Gesamtarchitektur und Verantwortlichkeiten.
  [Entwurf](../docs/v2-handbuch/01-grundlagen/01.02-architekturuebersicht.md) · [Eigene Hinweise](../workflow/notes/01.02.md) · [Diagrammideen](../workflow/diagram-notes/01.02.md)
- **01.03 Komponenten und Schichten:** FastAPI, Session-Verwaltung, Recorder, Activation Controller, Inferenz, Modelle, Speicherung.
  [Entwurf](../docs/v2-handbuch/01-grundlagen/01.03-komponenten-und-schichten.md) · [Eigene Hinweise](../workflow/notes/01.03.md) · [Diagrammideen](../workflow/diagram-notes/01.03.md)
- **01.04 Gesamter Datenfluss:** Vom Audioeingang bis zum fertigen Transkript.
  [Entwurf](../docs/v2-handbuch/01-grundlagen/01.04-gesamter-datenfluss.md) · [Eigene Hinweise](../workflow/notes/01.04.md) · [Diagrammideen](../workflow/diagram-notes/01.04.md)
- **01.05 Betriebs- und Funktionsmodi:** Manuell, Wake-Word, kombinierte Trigger, Realtime/Final.
  [Entwurf](../docs/v2-handbuch/01-grundlagen/01.05-betriebs-und-funktionsmodi.md) · [Eigene Hinweise](../workflow/notes/01.05.md) · [Diagrammideen](../workflow/diagram-notes/01.05.md)
- **01.06 Serverweite und sitzungsbezogene Ressourcen:** Shared vs. isoliert.
  [Entwurf](../docs/v2-handbuch/01-grundlagen/01.06-serverweite-und-sitzungsbezogene-ressourcen.md) · [Eigene Hinweise](../workflow/notes/01.06.md) · [Diagrammideen](../workflow/diagram-notes/01.06.md)
- **01.07 Identitäten:** Server, Client, Connection, Session, Activation, Segment, Command.
  [Entwurf](../docs/v2-handbuch/01-grundlagen/01.07-identitaeten.md) · [Eigene Hinweise](../workflow/notes/01.07.md) · [Diagrammideen](../workflow/diagram-notes/01.07.md)
- **01.08 Technische Grenzen:** CPU-only, Plattformen, Engines, V1/V2.
  [Entwurf](../docs/v2-handbuch/01-grundlagen/01.08-technische-grenzen.md) · [Eigene Hinweise](../workflow/notes/01.08.md)
- **01.09 Architekturdiagramme:** Systemübersicht, Komponenten- und Datenflussdiagramme.
  [Entwurf](../docs/v2-handbuch/01-grundlagen/01.09-architekturdiagramme.md) · [Eigene Hinweise](../workflow/notes/01.09.md) · [Diagrammideen](../workflow/diagram-notes/01.09.md)

## 02 – Funktionsweise und interne Abläufe

- **02.01 Session-Management:** Erstellung, Initialisierung, Lebenszyklus, Identitäten, Verbindungen, konkurrierende Sessions, serverweite/sitzungsbezogene Zustände, Verbindungsabbruch, Reconnect, Cleanup.
  [Entwurf](../docs/v2-handbuch/02-funktionsweise/02.01-session-management.md) · [Eigene Hinweise](../workflow/notes/02.01.md) · [Diagrammideen](../workflow/diagram-notes/02.01.md)
- **02.02 Audioverarbeitung:** Mikrofon, externe Zuführung, WebSocket, PCM/Format/Sample-Rate, Audioframes/Chunks/Puffer, Resampling, Normalisierung, VAD, Pre-Roll/Audiogrenzen, Audioverfügbarkeit, Transkriptionsübergabe.
  [Entwurf](../docs/v2-handbuch/02-funktionsweise/02.02-audioverarbeitung.md) · [Eigene Hinweise](../workflow/notes/02.02.md) · [Diagrammideen](../workflow/diagram-notes/02.02.md)
- **02.03 Activation:** Controller, Triggerquellen und Prioritäten, Phasen/Zustandsübergänge, Aktivieren/Deaktivieren/Abbrechen, Triggerannahme/-ablehnung, Locks/Konkurrenz, Timings/Watchdogs/Timeouts, Follow-up, Audiofreigabe, Idempotenz/Races/Recovery, Zustands- und Sequenzdiagramme.
  [Entwurf](../docs/v2-handbuch/02-funktionsweise/02.03-activation.md) · [Eigene Hinweise](../workflow/notes/02.03.md) · [Diagrammideen](../workflow/diagram-notes/02.03.md)
- **02.04 Wake-Word:** Backends, Erkennungspipeline, Modell-/Build-Katalog, IDs/Aliase, Session-Auswahl, Prediction Frames/Score/Schwellen, Qualifikation/Arbitration, Latch/Suppression/Rearm/Reset, Audioübernahme, Activation-/Follow-up-Integration, Diagnose.
  [Entwurf](../docs/v2-handbuch/02-funktionsweise/02.04-wake-word.md) · [Eigene Hinweise](../workflow/notes/02.04.md) · [Diagrammideen](../workflow/diagram-notes/02.04.md)
- **02.05 Transcription:** Gesamtpipeline, Realtime/Interim, Final, Segmente/Transkripte, Korrelation/Ersetzung/Stabilisierung, IDs, Inferenzaufträge/Queues/Prioritäten, Cancellation/verspätete Ergebnisse, Fehler/Timing.
  [Entwurf](../docs/v2-handbuch/02-funktionsweise/02.05-transcription.md) · [Eigene Hinweise](../workflow/notes/02.05.md) · [Diagrammideen](../workflow/diagram-notes/02.05.md)
- **02.06 Engines:** Abstraktion/Factory, zulässige Engines und Fähigkeiten, Faster-Whisper, Kroko-ONNX Community/Pro, Initialisierung/CPU-Nutzung, Engine-/Modellwechsel, Optionen, Grenzen/Fehler.
  [Entwurf](../docs/v2-handbuch/02-funktionsweise/02.06-engines.md) · [Eigene Hinweise](../workflow/notes/02.06.md) · [Diagrammideen](../workflow/diagram-notes/02.06.md)
- **02.07 Modelle und Modellverwaltung:** Katalog/Identitäten/Metadaten, Discovery/Dateipfade, Provisionierung/Downloads, Final-/Realtime-Auswahl, Lifecycle/Laden/Warm-up/Unload, aktiver Wechsel, Operator-Intent, Idle-/Speicherpolitik, Kroko-Entitlements, Recovery.
  [Entwurf](../docs/v2-handbuch/02-funktionsweise/02.07-modelle-und-modellverwaltung.md) · [Eigene Hinweise](../workflow/notes/02.07.md) · [Diagrammideen](../workflow/diagram-notes/02.07.md)
- **02.08 Scheduler und Nebenläufigkeit:** Inferenz-Lanes/Worker, Shared Resources/Session-Isolation, Fairness/Backpressure, Queue-Limits/Prioritäten, Staleness/Cancel/Timeout, Multiuser-Verhalten.
  [Entwurf](../docs/v2-handbuch/02-funktionsweise/02.08-scheduler-und-nebenlaeufigkeit.md) · [Eigene Hinweise](../workflow/notes/02.08.md) · [Diagrammideen](../workflow/diagram-notes/02.08.md)

## 03 – Einstellungen und Konfigurationssystem

- **03.01 Konfigurationsarchitektur:** Verschiedene Konfigurationsebenen und Zuständigkeiten.
  [Entwurf](../docs/v2-handbuch/03-konfiguration/03.01-konfigurationsarchitektur.md) · [Eigene Hinweise](../workflow/notes/03.01.md) · [Diagrammideen](../workflow/diagram-notes/03.01.md)
- **03.02 Scopes:** Server, Session und alle weiteren tatsächlich implementierten Gültigkeitsbereiche.
  [Entwurf](../docs/v2-handbuch/03-konfiguration/03.02-scopes.md) · [Eigene Hinweise](../workflow/notes/03.02.md) · [Diagrammideen](../workflow/diagram-notes/03.02.md)
- **03.03 Benennungskonventionen:** Code-/Wire-/CLI-/YAML-/Env-Namen und Zuordnung.
  [Entwurf](../docs/v2-handbuch/03-konfiguration/03.03-benennungskonventionen.md) · [Eigene Hinweise](../workflow/notes/03.03.md)
- **03.04 Datentypen und Validierung:** Defaults, Pflicht/Optional, Wertebereiche und Regeln.
  [Entwurf](../docs/v2-handbuch/03-konfiguration/03.04-datentypen-und-validierung.md) · [Eigene Hinweise](../workflow/notes/03.04.md)
- **03.05 Quellen und Prioritäten:** Defaults, Dateien, Env, CLI, gespeicherte Werte, API.
  [Entwurf](../docs/v2-handbuch/03-konfiguration/03.05-quellen-und-prioritaeten.md) · [Eigene Hinweise](../workflow/notes/03.05.md) · [Diagrammideen](../workflow/diagram-notes/03.05.md)
- **03.06 Server-Einstellungen:** Gültigkeit und Auswirkungen.
  [Entwurf](../docs/v2-handbuch/03-konfiguration/03.06-server-einstellungen.md) · [Eigene Hinweise](../workflow/notes/03.06.md)
- **03.07 Session-Einstellungen:** Overrides, Isolation und Schranken.
  [Entwurf](../docs/v2-handbuch/03-konfiguration/03.07-session-einstellungen.md) · [Eigene Hinweise](../workflow/notes/03.07.md)
- **03.08 Runtime-Änderungen:** Patch, Validate, Reload, Revisionen und Acknowledgements.
  [Entwurf](../docs/v2-handbuch/03-konfiguration/03.08-runtime-aenderungen.md) · [Eigene Hinweise](../workflow/notes/03.08.md) · [Diagrammideen](../workflow/diagram-notes/03.08.md)
- **03.09 Wirksamkeitszeitpunkt:** Sofort, nächster Trigger/Session, Modellwechsel, Neustart – nur wie implementiert.
  [Entwurf](../docs/v2-handbuch/03-konfiguration/03.09-wirksamkeitszeitpunkt.md) · [Eigene Hinweise](../workflow/notes/03.09.md) · [Diagrammideen](../workflow/diagram-notes/03.09.md)
- **03.10 Persistenz:** Ort, Laden, Speichern, Konflikte, Fehlerbehandlung.
  [Entwurf](../docs/v2-handbuch/03-konfiguration/03.10-persistenz.md) · [Eigene Hinweise](../workflow/notes/03.10.md)
- **03.11 Secrets:** Trennung von normalen Settings und Zugangsdaten.
  [Entwurf](../docs/v2-handbuch/03-konfiguration/03.11-secrets.md) · [Eigene Hinweise](../workflow/notes/03.11.md)
- **03.12 Abhängigkeiten:** Interdependenzen, Ausschlüsse und Auswirkungen.
  [Entwurf](../docs/v2-handbuch/03-konfiguration/03.12-abhaengigkeiten.md) · [Eigene Hinweise](../workflow/notes/03.12.md)
- **03.13 Konfigurationsbeispiele:** Realtime, Wake-Word, Multiuser, CPU-Performance.
  [Entwurf](../docs/v2-handbuch/03-konfiguration/03.13-konfigurationsbeispiele.md) · [Eigene Hinweise](../workflow/notes/03.13.md)

## 04 – Schnittstellen und Client-Integration

- **04.01 Schnittstellenübersicht:** HTTP/REST, WS V2, Legacy V1, OpenAI, Logs.
  [Entwurf](../docs/v2-handbuch/04-schnittstellen/04.01-schnittstellenuebersicht.md) · [Eigene Hinweise](../workflow/notes/04.01.md)
- **04.02 HTTP-Grundlagen:** Adressierung, Versionierung, Requests, Responses, Fehler.
  [Entwurf](../docs/v2-handbuch/04-schnittstellen/04.02-http-grundlagen.md) · [Eigene Hinweise](../workflow/notes/04.02.md)
- **04.03 WebSocket V2:** Verbindung, `hello`, Aushandlung und Sessions.
  [Entwurf](../docs/v2-handbuch/04-schnittstellen/04.03-websocket-v2.md) · [Eigene Hinweise](../workflow/notes/04.03.md) · [Diagrammideen](../workflow/diagram-notes/04.03.md)
- **04.04 Commands/Acknowledgements:** IDs, `command.ack`, Replay, Konflikte.
  [Entwurf](../docs/v2-handbuch/04-schnittstellen/04.04-commands-acknowledgements.md) · [Eigene Hinweise](../workflow/notes/04.04.md) · [Diagrammideen](../workflow/diagram-notes/04.04.md)
- **04.05 Audiotransport:** Binärframes, Formate, Reihenfolge, Grenzen.
  [Entwurf](../docs/v2-handbuch/04-schnittstellen/04.05-audiotransport.md) · [Eigene Hinweise](../workflow/notes/04.05.md)
- **04.06 Eventtransport:** Hülle, `eventSeq`, Zustellung/Reihenfolge.
  [Entwurf](../docs/v2-handbuch/04-schnittstellen/04.06-eventtransport.md) · [Eigene Hinweise](../workflow/notes/04.06.md) · [Diagrammideen](../workflow/diagram-notes/04.06.md)
- **04.07 Snapshot/Synchronisierung:** Event-Reducer, Resync, Konsistenz.
  [Entwurf](../docs/v2-handbuch/04-schnittstellen/04.07-snapshot-synchronisierung.md) · [Eigene Hinweise](../workflow/notes/04.07.md) · [Diagrammideen](../workflow/diagram-notes/04.07.md)
- **04.08 Reconnect:** Verbindungswechsel, Identitäten, Lücken, Wiederanlauf.
  [Entwurf](../docs/v2-handbuch/04-schnittstellen/04.08-reconnect.md) · [Eigene Hinweise](../workflow/notes/04.08.md) · [Diagrammideen](../workflow/diagram-notes/04.08.md)
- **04.09 Client-Zustandsmodell:** UI-State und konsistenter Reducer.
  [Entwurf](../docs/v2-handbuch/04-schnittstellen/04.09-client-zustandsmodell.md) · [Eigene Hinweise](../workflow/notes/04.09.md) · [Diagrammideen](../workflow/diagram-notes/04.09.md)
- **04.10 OpenAI-kompatible API:** Datei-Transkription, Modelle, Formate, Streaming, Auth.
  [Entwurf](../docs/v2-handbuch/04-schnittstellen/04.10-openai-kompatible-api.md) · [Eigene Hinweise](../workflow/notes/04.10.md) · [Diagrammideen](../workflow/diagram-notes/04.10.md)
- **04.11 Logzugriff:** Historie und Live-Logstream.
  [Entwurf](../docs/v2-handbuch/04-schnittstellen/04.11-logzugriff.md) · [Eigene Hinweise](../workflow/notes/04.11.md)
- **04.12 Legacy V1:** Unterstützter Altvertrag und saubere V2-Abgrenzung.
  [Entwurf](../docs/v2-handbuch/04-schnittstellen/04.12-legacy-v1.md) · [Eigene Hinweise](../workflow/notes/04.12.md)
- **04.13 Integrationsbeispiele:** End-to-End V2-Client, inklusive Fehler/Reconnect.
  [Entwurf](../docs/v2-handbuch/04-schnittstellen/04.13-integrationsbeispiele.md) · [Eigene Hinweise](../workflow/notes/04.13.md)

## 05 – Administration, Sicherheit und Berechtigungen

- **05.01 Sicherheitsarchitektur:** Vertrauensgrenzen und geschützte Bereiche.
  [Entwurf](../docs/v2-handbuch/05-administration/05.01-sicherheitsarchitektur.md) · [Eigene Hinweise](../workflow/notes/05.01.md) · [Diagrammideen](../workflow/diagram-notes/05.01.md)
- **05.02 Serverzugriff:** Bind-Adresse, Netzwerk, HTTP/WS, Deployment-Sicherheit.
  [Entwurf](../docs/v2-handbuch/05-administration/05.02-serverzugriff.md) · [Eigene Hinweise](../workflow/notes/05.02.md)
- **05.03 Admin-Authentifizierung:** API-Key, Berechtigungen, Validierung und Fehler.
  [Entwurf](../docs/v2-handbuch/05-administration/05.03-admin-authentifizierung.md) · [Eigene Hinweise](../workflow/notes/05.03.md) · [Diagrammideen](../workflow/diagram-notes/05.03.md)
- **05.04 Session-Zugriff:** Session-Rechte und Admin-Abgrenzung.
  [Entwurf](../docs/v2-handbuch/05-administration/05.04-session-zugriff.md) · [Eigene Hinweise](../workflow/notes/05.04.md)
- **05.05 Log-Authentifizierung:** Tokens, Scope, Gültigkeit, Widerruf.
  [Entwurf](../docs/v2-handbuch/05-administration/05.05-log-authentifizierung.md) · [Eigene Hinweise](../workflow/notes/05.05.md) · [Diagrammideen](../workflow/diagram-notes/05.05.md)
- **05.06 OpenAI-API-Authentifizierung:** Separater Schlüssel und Gate.
  [Entwurf](../docs/v2-handbuch/05-administration/05.06-openai-api-authentifizierung.md) · [Eigene Hinweise](../workflow/notes/05.06.md)
- **05.07 Kroko-Lizenzierung:** Key, Gültigkeit, Community/Pro, Force Community.
  [Entwurf](../docs/v2-handbuch/05-administration/05.07-kroko-lizenzierung.md) · [Eigene Hinweise](../workflow/notes/05.07.md) · [Diagrammideen](../workflow/diagram-notes/05.07.md)
- **05.08 Native-Guard:** Runtime-Berechtigung, Lizenzkontext, nötige Neustarts.
  [Entwurf](../docs/v2-handbuch/05-administration/05.08-native-guard.md) · [Eigene Hinweise](../workflow/notes/05.08.md) · [Diagrammideen](../workflow/diagram-notes/05.08.md)
- **05.09 Schutz von Daten/Secrets:** Environment, Redaktion, Logs, Dateien.
  [Entwurf](../docs/v2-handbuch/05-administration/05.09-schutz-von-daten-secrets.md) · [Eigene Hinweise](../workflow/notes/05.09.md)
- **05.10 Fehler-/Zugriffsantworten:** HTTP-/WS-Verweigerungen und Formate.
  [Entwurf](../docs/v2-handbuch/05-administration/05.10-fehler-zugriffsantworten.md) · [Eigene Hinweise](../workflow/notes/05.10.md)
- **05.11 Sicherheitsrelevante Betriebsregeln:** LAN/externer Zugang, sichere Konfiguration.
  [Entwurf](../docs/v2-handbuch/05-administration/05.11-sicherheitsrelevante-betriebsregeln.md) · [Eigene Hinweise](../workflow/notes/05.11.md)

## 06 – Installation, Betrieb und Diagnose

- **06.01 Systemvoraussetzungen:** Plattformen, Python, Architektur, Ressourcen.
  [Entwurf](../docs/v2-handbuch/06-betrieb/06.01-systemvoraussetzungen.md) · [Eigene Hinweise](../workflow/notes/06.01.md)
- **06.02 Installationskonzept:** Ein Produkt, Native-Runtime, CPU-only.
  [Entwurf](../docs/v2-handbuch/06-betrieb/06.02-installationskonzept.md) · [Eigene Hinweise](../workflow/notes/06.02.md)
- **06.03 Windows-Installation:** Unterstützter CPU-Installationsweg.
  [Entwurf](../docs/v2-handbuch/06-betrieb/06.03-windows-installation.md) · [Eigene Hinweise](../workflow/notes/06.03.md)
- **06.04 Linux-Installation:** CPU-Torch, Constraints, Installationsprüfung.
  [Entwurf](../docs/v2-handbuch/06-betrieb/06.04-linux-installation.md) · [Eigene Hinweise](../workflow/notes/06.04.md)
- **06.05 Docker-Betrieb:** Images/Compose, Ports, Volumes, Konfiguration.
  [Entwurf](../docs/v2-handbuch/06-betrieb/06.05-docker-betrieb.md) · [Eigene Hinweise](../workflow/notes/06.05.md) · [Diagrammideen](../workflow/diagram-notes/06.05.md)
- **06.06 Ersteinrichtung:** Datenverzeichnisse, Schlüssel, Modelle, Defaults.
  [Entwurf](../docs/v2-handbuch/06-betrieb/06.06-ersteinrichtung.md) · [Eigene Hinweise](../workflow/notes/06.06.md)
- **06.07 Serverstart/-stopp:** CLI, Env, Startup, Shutdown.
  [Entwurf](../docs/v2-handbuch/06-betrieb/06.07-serverstart-stopp.md) · [Eigene Hinweise](../workflow/notes/06.07.md) · [Diagrammideen](../workflow/diagram-notes/06.07.md)
- **06.08 Datenhaltung:** Persistente Pfade, SQLite, JSON, Logs, Audio.
  [Entwurf](../docs/v2-handbuch/06-betrieb/06.08-datenhaltung.md) · [Eigene Hinweise](../workflow/notes/06.08.md)
- **06.09 Logging:** Kanäle, Level, Datenschutz, Aufbewahrung.
  [Entwurf](../docs/v2-handbuch/06-betrieb/06.09-logging.md) · [Eigene Hinweise](../workflow/notes/06.09.md)
- **06.10 Monitoring und Metriken:** Health, Queues, Worker, Betriebsstatus.
  [Entwurf](../docs/v2-handbuch/06-betrieb/06.10-monitoring-und-metriken.md) · [Eigene Hinweise](../workflow/notes/06.10.md) · [Diagrammideen](../workflow/diagram-notes/06.10.md)
- **06.11 Performance/Ressourcen:** Threads, Latenz, Modellgröße, Multiuser.
  [Entwurf](../docs/v2-handbuch/06-betrieb/06.11-performance-ressourcen.md) · [Eigene Hinweise](../workflow/notes/06.11.md)
- **06.12 Fehlerdiagnose:** Install, Audio, Model, Auth, Inferenz.
  [Entwurf](../docs/v2-handbuch/06-betrieb/06.12-fehlerdiagnose.md) · [Eigene Hinweise](../workflow/notes/06.12.md)
- **06.13 Wartung:** Neustart, Modellwechsel, Updates, Cleanup.
  [Entwurf](../docs/v2-handbuch/06-betrieb/06.13-wartung.md) · [Eigene Hinweise](../workflow/notes/06.13.md)
- **06.14 Datensicherung:** Welche Daten sichern und wie wiederherstellen.
  [Entwurf](../docs/v2-handbuch/06-betrieb/06.14-datensicherung.md) · [Eigene Hinweise](../workflow/notes/06.14.md)
- **06.15 Betriebsszenarien:** Einzelbenutzer, Multiuser, lokal, Container.
  [Entwurf](../docs/v2-handbuch/06-betrieb/06.15-betriebsszenarien.md) · [Eigene Hinweise](../workflow/notes/06.15.md)

## 07 – Entwicklung, Tests, Build und Release

- **07.01 Entwicklungsumgebung:** Source-Checkout, venv, Werkzeuge, Abhängigkeiten.
  [Entwurf](../docs/v2-handbuch/07-entwicklung/07.01-entwicklungsumgebung.md) · [Eigene Hinweise](../workflow/notes/07.01.md)
- **07.02 Repository-Architektur:** Pakete, Module, Engineering-Verzeichnisse.
  [Entwurf](../docs/v2-handbuch/07-entwicklung/07.02-repository-architektur.md) · [Eigene Hinweise](../workflow/notes/07.02.md)
- **07.03 Technische Schnittstellen:** Recorder, Engine, Session, Server.
  [Entwurf](../docs/v2-handbuch/07-entwicklung/07.03-technische-schnittstellen.md) · [Eigene Hinweise](../workflow/notes/07.03.md)
- **07.04 Erweiterungspunkte:** Verträge und sichere Integration neuer Funktionen.
  [Entwurf](../docs/v2-handbuch/07-entwicklung/07.04-erweiterungspunkte.md) · [Eigene Hinweise](../workflow/notes/07.04.md)
- **07.05 Testarchitektur:** Unit, Contract, Integration, Packaging, Plattform.
  [Entwurf](../docs/v2-handbuch/07-entwicklung/07.05-testarchitektur.md) · [Eigene Hinweise](../workflow/notes/07.05.md)
- **07.06 Testverfahren:** Mit/ohne Modelle, Last, Regression.
  [Entwurf](../docs/v2-handbuch/07-entwicklung/07.06-testverfahren.md) · [Eigene Hinweise](../workflow/notes/07.06.md)
- **07.07 Packaging:** `setup.py`, Wheel, sdist, Extras, Daten.
  [Entwurf](../docs/v2-handbuch/07-entwicklung/07.07-packaging.md) · [Eigene Hinweise](../workflow/notes/07.07.md)
- **07.08 Native-Kroko-Build:** Buildinputs, Fingerprints, Provenienz, Plattformen.
  [Entwurf](../docs/v2-handbuch/07-entwicklung/07.08-native-kroko-build.md) · [Eigene Hinweise](../workflow/notes/07.08.md) · [Diagrammideen](../workflow/diagram-notes/07.08.md)
- **07.09 CI:** Workflows, Matrix, CPU-only-Prüfung.
  [Entwurf](../docs/v2-handbuch/07-entwicklung/07.09-ci.md) · [Eigene Hinweise](../workflow/notes/07.09.md)
- **07.10 Release Candidate:** Manifest, Staging, Qualifikation.
  [Entwurf](../docs/v2-handbuch/07-entwicklung/07.10-release-candidate.md) · [Eigene Hinweise](../workflow/notes/07.10.md) · [Diagrammideen](../workflow/diagram-notes/07.10.md)
- **07.11 Veröffentlichung:** Registries, Freigaben, Release-State-Machine.
  [Entwurf](../docs/v2-handbuch/07-entwicklung/07.11-veroeffentlichung.md) · [Eigene Hinweise](../workflow/notes/07.11.md) · [Diagrammideen](../workflow/diagram-notes/07.11.md)
- **07.12 Buildketten-Sicherheit:** Identitäten, Redistribution und Gates.
  [Entwurf](../docs/v2-handbuch/07-entwicklung/07.12-buildketten-sicherheit.md) · [Eigene Hinweise](../workflow/notes/07.12.md)
- **07.13 Änderungs-/Kompatibilitätsregeln:** Versionierung, Migration, Dokumentationsvalidierung.
  [Entwurf](../docs/v2-handbuch/07-entwicklung/07.13-aenderungs-kompatibilitaetsregeln.md) · [Eigene Hinweise](../workflow/notes/07.13.md)

## 08 – Kataloge und technische Referenzen

- **08.01 Event-Katalog:** Alle Events, Felder, Typen, Trigger, Reihenfolge, Beispiele.
  [Entwurf](../docs/v2-handbuch/08-referenzen/08.01-event-katalog.md) · [Eigene Hinweise](../workflow/notes/08.01.md)
- **08.02 Command-Katalog:** Alle Commands, Payloads, Zustände, Acks und Fehler.
  [Entwurf](../docs/v2-handbuch/08-referenzen/08.02-command-katalog.md) · [Eigene Hinweise](../workflow/notes/08.02.md)
- **08.03 Settings-Katalog:** Alle Settings, Scope, Typ, Default, Validierung, Änderung, Wirkung, Persistenz.
  [Entwurf](../docs/v2-handbuch/08-referenzen/08.03-settings-katalog.md) · [Eigene Hinweise](../workflow/notes/08.03.md)
- **08.04 API-Endpunkt-Katalog:** Alle Routen, Methoden, Auth, Parameter, Rückgaben, Fehler.
  [Entwurf](../docs/v2-handbuch/08-referenzen/08.04-api-endpunkt-katalog.md) · [Eigene Hinweise](../workflow/notes/08.04.md)
- **08.05 Zustands-/Phasenkatalog:** Session, Activation, Modell und andere State Machines.
  [Entwurf](../docs/v2-handbuch/08-referenzen/08.05-zustands-phasenkatalog.md) · [Eigene Hinweise](../workflow/notes/08.05.md) · [Diagrammideen](../workflow/diagram-notes/08.05.md)
- **08.06 Timing-Katalog:** Timer, Fristen, Defaults, Zeitursprünge, gegenseitige Beziehungen.
  [Entwurf](../docs/v2-handbuch/08-referenzen/08.06-timing-katalog.md) · [Eigene Hinweise](../workflow/notes/08.06.md) · [Diagrammideen](../workflow/diagram-notes/08.06.md)
- **08.07 Modell-Katalog-Referenz:** Schemata, IDs, Metadaten, Fähigkeiten, Lizenzklassen.
  [Entwurf](../docs/v2-handbuch/08-referenzen/08.07-modell-katalog-referenz.md) · [Eigene Hinweise](../workflow/notes/08.07.md)
- **08.08 Engine-Referenz:** Zwei unterstützte Engines mit belegten Optionen.
  [Entwurf](../docs/v2-handbuch/08-referenzen/08.08-engine-referenz.md) · [Eigene Hinweise](../workflow/notes/08.08.md)
- **08.09 Fehlerkatalog:** Alle Fehler-/Ablehnungs-/Close-Codes, Ursachen, Umgang.
  [Entwurf](../docs/v2-handbuch/08-referenzen/08.09-fehlerkatalog.md) · [Eigene Hinweise](../workflow/notes/08.09.md)
- **08.10 WebSocket-Schema-Referenz:** Handshake, Nachrichten, Binärframe, Event, Snapshot, Close.
  [Entwurf](../docs/v2-handbuch/08-referenzen/08.10-websocket-schema-referenz.md) · [Eigene Hinweise](../workflow/notes/08.10.md)
- **08.11 Logging-Katalog:** Ereignisse, Felder, Level, Kanäle, Redaktion.
  [Entwurf](../docs/v2-handbuch/08-referenzen/08.11-logging-katalog.md) · [Eigene Hinweise](../workflow/notes/08.11.md)
- **08.12 CLI-/Env-Katalog:** Parameter, Umgebungsvariablen, Defaults, Prioritäten.
  [Entwurf](../docs/v2-handbuch/08-referenzen/08.12-cli-env-katalog.md) · [Eigene Hinweise](../workflow/notes/08.12.md)
- **08.13 Daten-/Persistenzschema:** SQLite, JSON, Pfade, Lebensdauer.
  [Entwurf](../docs/v2-handbuch/08-referenzen/08.13-daten-persistenzschema.md) · [Eigene Hinweise](../workflow/notes/08.13.md)
- **08.14 Metrik-Katalog:** Alle Metriken, Einheiten, Bedeutungen und Grenzen.
  [Entwurf](../docs/v2-handbuch/08-referenzen/08.14-metrik-katalog.md) · [Eigene Hinweise](../workflow/notes/08.14.md)

## 09 – Anhänge und Kompatibilität

- **09.01 Glossar:** Kanonische Fachbegriffe und Begriffsbeziehungen.
  [Entwurf](../docs/v2-handbuch/09-anhaenge/09.01-glossar.md) · [Eigene Hinweise](../workflow/notes/09.01.md)
- **09.02 Abkürzungen:** STT, ASR, VAD, PCM usw.
  [Entwurf](../docs/v2-handbuch/09-anhaenge/09.02-abkuerzungen.md) · [Eigene Hinweise](../workflow/notes/09.02.md)
- **09.03 V1-/V2-Unterschiede:** Technische/protokollarische Abgrenzung.
  [Entwurf](../docs/v2-handbuch/09-anhaenge/09.03-v1-v2-unterschiede.md) · [Eigene Hinweise](../workflow/notes/09.03.md) · [Diagrammideen](../workflow/diagram-notes/09.03.md)
- **09.04 Client-Migration:** V1 auf V2 einschließlich Bruchstellen.
  [Entwurf](../docs/v2-handbuch/09-anhaenge/09.04-client-migration.md) · [Eigene Hinweise](../workflow/notes/09.04.md) · [Diagrammideen](../workflow/diagram-notes/09.04.md)
- **09.05 Kompatibilitätsverträge:** Bewusst erhaltene öffentliche APIs.
  [Entwurf](../docs/v2-handbuch/09-anhaenge/09.05-kompatibilitaetsvertraege.md) · [Eigene Hinweise](../workflow/notes/09.05.md)
- **09.06 Beispielszenarien:** Zusammenhängende End-to-End-Abläufe.
  [Entwurf](../docs/v2-handbuch/09-anhaenge/09.06-beispielszenarien.md) · [Eigene Hinweise](../workflow/notes/09.06.md) · [Diagrammideen](../workflow/diagram-notes/09.06.md)
- **09.07 Quellen/Verifikation:** Zuordnung Kapitel ↔ Code/Schemas/Tests.
  [Entwurf](../docs/v2-handbuch/09-anhaenge/09.07-quellen-verifikation.md) · [Eigene Hinweise](../workflow/notes/09.07.md)
- **09.08 Dokumentationsstand:** Commit, Geltungsbereich, Unsicherheiten, Grenzen.
  [Entwurf](../docs/v2-handbuch/09-anhaenge/09.08-dokumentationsstand.md) · [Eigene Hinweise](../workflow/notes/09.08.md)
