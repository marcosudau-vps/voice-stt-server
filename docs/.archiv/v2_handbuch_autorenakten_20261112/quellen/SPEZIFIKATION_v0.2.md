# Voice-STT-Server V2 – Dokumentations-Orchestrierung

**Planungsstand:** Version 0.2 · 06.11.2026
**Status:** Verbindlicher Entwurf für die spätere OpenCode-/OpenChamber-Einrichtung; noch nicht implementiert.
**Repository:** `marcosudau-vps/voice-stt-server`
**Arbeitsbranch:** `feat/v2-release-cleanup`
**Ziel:** Eine vollständig eigenständige, technisch belegte, verständliche und praxisorientierte Voice-STT-V2-Dokumentation. Keine Neuauflage der alten Legacy-STT-Dateien.

## A. Unverrückbare Grundsätze

1. **Ein Gesamtauftrag.** Ein Orchestrator führt die Dokumentationsarbeit über alle neun Hauptbereiche selbstständig aus, teilt intern in Arbeitspakete auf und verwaltet Belege, Reviews, Korrekturen und Integration.
2. **Die komplette Gliederung aus Abschnitt C ist verbindlich.** Jedes nummerierte Unterkapitel ist als eigener nachverfolgbarer Coverage-Eintrag zu behandeln. Kein stillschweigendes Weglassen, Zusammenlegen oder Umbenennen. Sinnvolle weitere Themen dürfen ergänzend aufgenommen werden. Inhaltlich nachweislich nicht vorhandene Funktionen werden als solche gekennzeichnet, nicht erfunden.
3. **Recherche ausschließlich aus der aktuellen technischen Implementierung.** Researcher dürfen keine bestehenden Markdown-/Dokumentationstexte als Informationsquelle verwenden oder daraus paraphrasieren. Primärquellen sind ausführbarer Produktcode, Schemas, registrierte Routen, Tests, Packaging-/Build-/CI-Konfigurationen und tatsächliche Konfigurationsdefinitionen. Tests sind Evidenz für erwartetes Verhalten, nicht automatisch Beweis für tatsächliches Laufzeitverhalten; bei Widerspruch entscheidet die Implementierung, und der Widerspruch wird dokumentiert. Kommentare/Docstrings allein sind keine hinreichende Verifikation.
4. **Der alte Dokumentationsbestand ist weder Schreibvorlage noch Wahrheitsquelle.** `docs/`, `README.md`, alte Legacy-STT-Texte, historische Agentenberichte und die bestehende `docs/v2-code-reference/` dürfen bei der technischen Faktenrecherche nicht als Primärbelege dienen. Die hier festgelegte Gliederung ist eine redaktionelle Strukturvorgabe, keine Tatsachenquelle. Gegebenenfalls darf der Orchestrator später einen separaten, ausdrücklich abgegrenzten Migrations-/Link-Audit der Alttexte ansetzen; dessen Inhalte dürfen nicht unbestätigt in das neue Handbuch einfließen.
5. **Anschaulich statt Telefonbuch.** Die Autoren schaffen Erklärungen, Einstiegsszenarien, Ursache/Wirkung, nachvollziehbare praxisnahe Beispiele, tabellarische Übersichten und korrekte Diagramme (vorzugsweise Mermaid), wenn diese einen realen Erkenntnisgewinn bringen. Tabellen und Aufzählungen allein reichen für Fachkapitel nicht aus.
6. **Belegte Beispiele.** Beispielbefehle, APIs, JSON-Felder und Sequenzen stimmen mit nachgewiesenen Verträgen überein. Illustrative/pseudocodehafte Darstellungen sind sichtbar als schematisch gekennzeichnet; nicht verifizierte Befehle dürfen nicht als ausführbar dargestellt werden.
7. **Unabhängige Abnahme.** Reviewer prüfen gegen Originalcode und Schema, nicht nur gegen die Faktenakte. Writer dürfen ihre Kapitel nicht selbst freigeben. Jede schwerwiegende Abweichung erzeugt ein konkret benanntes Korrekturticket mit erneutem Review.
8. **Schutz des Produktcodes und der bisherigen Dokumentation.** Agenten ändern nur ihre zugewiesenen Arbeitsakten und neue Dokumentation unter `docs/v2-handbuch/`. Keine Änderungen an Runtime, Tests oder bestehender Dokumentation während der Inhaltserstellung ohne eigene Freigabe. Alte aktive Dokumente erst nach einer separat abgenommenen Migration entfernen.
9. **Nachvollziehbare Identität.** Jede Faktenakte und jede Freigabe benennt den exakten Git-Commit/Quellstand. Ändert sich die Implementation, werden betroffene Kapitel neu geprüft.
10. **Keine verdeckte Fertigmeldung.** `COMPLETE` nur bei dokumentierter Vollabdeckung, bestandenen mechanischen Checks, unabhängiger Review-Freigabe aller Kapitel und bestandener globaler Integrationsprüfung. Externe Release-/Native-Freigaben sind nicht Teil einer Dokumentationsabnahme.

## B. Agentenrollen und Übergabeverträge

### B.1 Orchestrator (primärer Agent)
- Legt aus **jedem** Unterkapitel in Abschnitt C einen Registry-Eintrag an; prüft, dass die Summe der Einträge vollständig ist.
- Verwaltet Prioritäten, Kapitelabhängigkeiten, Quellenstand, Schreibrechte, Revisionen, Korrekturschleifen und Integration.
- Delegiert Recherche, Autorenarbeit und unabhängigen Review an getrennte Subagenten.
- Prüft Belegketten, erkennt Konflikte zwischen Kapiteln und veranlasst erneute Recherche.
- Führt den Pilot **02.03 Activation** mit dem vollständigen Workflow aus, einschließlich mindestens einer kontrollierten Review-Runde, bevor der Rest skaliert wird.
- Speichert Zustand im Repository, sodass die Arbeit nach Kontextkomprimierung/Sessionfortsetzung nachvollziehbar weiterläuft.

### B.2 Researcher (lesender Quellcode-Agent)
**Erlaubte Quellen:** aktuelle `*.py`-Produktdateien, tatsächlich verwendete JSON/YAML-Konfigurationen, Schemas, Tests, CI-/Packaging-/Builddefinitionen, ggf. überprüfbare generierte Metadaten oder Testausgaben.
**Verbotene Wahrheitsquellen:** bestehende `docs/**`, Root-README, Release-Notes, andere freie Dokumentation, historische Untersuchungen, alte Legacy-STT-Quellen. Der Researcher soll nicht zuerst diese Dokumente lesen oder Begriffe aus ihnen übernehmen. Die verbindliche Kapitelgliederung gilt nur als Suchauftrag.

**Ausgabe je Kapitel: `research/<ID>.json` oder `.md`**
- exakter Commit und untersuchte Quellenliste;
- für jeden behaupteten Mechanismus eine Fakten-ID mit Pfad, Symbol, möglichst stabiler Positionsangabe, beobachtetem Ablauf und Evidenzgrad;
- API-/Events-/Settings-Definitionen inklusive Datentypen, Defaults, Gültigkeit, Fehlern und Scopes aus tatsächlichen Schemas;
- Sequenzen, Zustandsübergänge, Zeitparameter und ihre Vorbedingungen;
- nachvollziehbare, technisch zulässige Beispielabläufe;
- explizite `NOT_IMPLEMENTED`, `UNKNOWN` oder `CONFLICT`-Befunde;
- mögliche Diagrammbeziehungen als Fakten, **keine erfundenen Übergänge**.

Bei Unklarheit erweitern Researcher die Codesuche und dürfen keine naheliegenden Defaults, APIs oder Zeitwerte schätzen.

### B.3 Writer (didaktischer Fachautor)
- Nutzt ausschließlich abgenommene Faktenakte und bei Bedarf den darin referenzierten aktuellen Code, nicht die alte Dokumentation.
- **Schreibt für Menschen:** beginnt bei Bedarf mit „Wozu dient das?“, zeigt dann „Wie funktioniert es?“, anschließend „Wie benutze/erkenne/diagnostiziere ich es?“.
- Nutzt verständliche Absätze, kurze praxisnahe Abläufe, relevante Beispiele, erklärende Tabellen sowie Diagramme, deren Pfeile und Zustände nachgewiesen sind.
- Verwende **Mermaid** nach Möglichkeit für Zustandsautomaten, Sequenzdiagramme, Datenfluss und Entscheidungsbäume. Diagramme nicht als bloße Dekoration einsetzen und keine unrealistischen Ablaufdarstellungen erzeugen.
- Trennt Konzept, Produktionsverhalten, Konfiguration, Beispiel und Referenz. Erklärt Fachbegriffe vor ihrer Verwendung oder verlinkt auf Glossar.
- Verlinkt auf die zuständige kanonische Referenz statt dieselbe vollständige Tabelle mehrfach zu kopieren.
- Trennt nachvollziehbar normale Abläufe von Grenzfällen, Ablehnungen, Recovery, Timeouts und Race Conditions.
- Fügt nach Möglichkeit pro größerem Thema mindestens ein **End-to-End-Szenario** ein, ohne künstliche Beispiele zu erfinden.
- Erzeugt eine Kapiteldatei mit Fakten-ID-Verweisen und einem kurzen Nachweis der Gliederungsabdeckung.

**Redaktioneller Qualitätsmaßstab:** Das Kapitel muss ohne Kenntnis des Quellcodes grundsätzlich verständlich sein. Ein bloßes Ausschreiben der Researcher-Faktenakte, ein reines Datenblatt oder eine lose Liste von Methoden erfüllt den Auftrag nicht.

### B.4 Reviewer (unabhängige technische + redaktionelle Prüfung)
- Darf Kapitel und Faktenakte lesen, prüft aber **jede relevante Aussage eigenständig anhand des aktuellen Quellcodes**. Keine bestehenden Dokumentationsdateien als Wahrheitsbeweis.
- Prüft ausdrücklich, ob Diagrammübergänge, Beispiele, Konfigurationsdefaults, Fehlercodes, Nebenläufigkeit und Zeitverhalten real belegt sind.
- Prüft Korrektheit, Vollständigkeit gegen Gliederung und Coderegistrierungen, Widersprüche, Terminologie, Zugänglichkeit/Lesbarkeit, Praxisnutzen und funktionierende Links.
- Gibt `PASS`, `CHANGES_REQUESTED` oder `ESCALATE` mit nachvollziehbaren Befunden und Quellen ab.
- **Ändert nie selbst das zu prüfende Kapitel** und bewertet einen eigenen Text niemals als unabhängig freigegeben.

### B.5 Integrator (zentral beim Orchestrator)
- Bindet nur `ACCEPTED`-Kapitel ein, vereinheitlicht Navigation, Querverweise und Glossarbegriffe.
- Verifiziert die neun Hauptbereiche und jedes Unterkapitel; überprüft die mechanische Katalogabdeckung.
- Sucht identische/konfligierende fachliche Aussagen, kaputte Links, fehlende Diagrammreferenzen, alte relative Pfade und unzulässige Altprojekteinträge.
- Führt finale Gesamt-Review durch und dokumentiert Abweichungen/Blocker transparent.

### B.6 Workflow, Rückgabe und Begrenzung
`PLANNED → RESEARCHED → DRAFTED → IN_REVIEW → ACCEPTED → INTEGRATED`

Bei Fehlern `CHANGES_REQUESTED → RESEARCHED` oder `→ DRAFTED`, danach erneut `IN_REVIEW`. Nach drei fehlgeschlagenen Korrekturen desselben Mangels `ESCALATE` an Orchestrator: Ursache analysieren, Auftrag zerlegen oder einen anderen Bearbeiter wählen. Kein Endlosloop.

Parallele **Recherche** ist sinnvoll, aber unterschiedliche Agenten schreiben nicht gleichzeitig dieselbe Zieldatei. Höchstens ca. drei Recherche- und zwei Autorenaufträge gleichzeitig als konservativer Startwert; genaue Parallelitätsgrenzen nach Leistung und Kontextbudget konfigurieren. Modelle sind Vorschläge (z. B. Muse Spark 1.3 Contributor für Recherche/Autoren, DeepSeek V4.1 für Orchestrierung/Review); die echten IDs müssen in der OpenCode-Installation verifiziert werden.

## C. Verbindliche Gesamtkapitelgliederung

**Alle folgenden nummerierten Unterkapitel sind Pflicht-Coverage-Einträge, unabhängig davon, ob sie am Ende je eine Datei oder sinnvolle Teilabschnitte innerhalb einer Datei bilden. Die Titel sind als Plan fest; fachliche Details können nach Codeprüfung präzisiert werden.**

### 01 – Einstieg und Systemverständnis
- **01.01 Produktüberblick:** Ziel, Einsatzbereiche, Produktfunktionen.
- **01.02 Architekturübersicht:** Gesamtarchitektur und Verantwortlichkeiten.
- **01.03 Komponenten und Schichten:** FastAPI, Session-Verwaltung, Recorder, Activation Controller, Inferenz, Modelle, Speicherung.
- **01.04 Gesamter Datenfluss:** Vom Audioeingang bis zum fertigen Transkript.
- **01.05 Betriebs- und Funktionsmodi:** Manuell, Wake-Word, kombinierte Trigger, Realtime/Final.
- **01.06 Serverweite und sitzungsbezogene Ressourcen:** Shared vs. isoliert.
- **01.07 Identitäten:** Server, Client, Connection, Session, Activation, Segment, Command.
- **01.08 Technische Grenzen:** CPU-only, Plattformen, Engines, V1/V2.
- **01.09 Architekturdiagramme:** Systemübersicht, Komponenten- und Datenflussdiagramme.

### 02 – Funktionsweise und interne Abläufe
- **02.01 Session-Management:** Erstellung, Initialisierung, Lebenszyklus, Identitäten, Verbindungen, konkurrierende Sessions, serverweite/sitzungsbezogene Zustände, Verbindungsabbruch, Reconnect, Cleanup.
- **02.02 Audioverarbeitung:** Mikrofon, externe Zuführung, WebSocket, PCM/Format/Sample-Rate, Audioframes/Chunks/Puffer, Resampling, Normalisierung, VAD, Pre-Roll/Audiogrenzen, Audioverfügbarkeit, Transkriptionsübergabe.
- **02.03 Activation:** Controller, Triggerquellen und Prioritäten, Phasen/Zustandsübergänge, Aktivieren/Deaktivieren/Abbrechen, Triggerannahme/-ablehnung, Locks/Konkurrenz, Timings/Watchdogs/Timeouts, Follow-up, Audiofreigabe, Idempotenz/Races/Recovery, Zustands- und Sequenzdiagramme.
- **02.04 Wake-Word:** Backends, Erkennungspipeline, Modell-/Build-Katalog, IDs/Aliase, Session-Auswahl, Prediction Frames/Score/Schwellen, Qualifikation/Arbitration, Latch/Suppression/Rearm/Reset, Audioübernahme, Activation-/Follow-up-Integration, Diagnose.
- **02.05 Transcription:** Gesamtpipeline, Realtime/Interim, Final, Segmente/Transkripte, Korrelation/Ersetzung/Stabilisierung, IDs, Inferenzaufträge/Queues/Prioritäten, Cancellation/verspätete Ergebnisse, Fehler/Timing.
- **02.06 Engines:** Abstraktion/Factory, zulässige Engines und Fähigkeiten, Faster-Whisper, Kroko-ONNX Community/Pro, Initialisierung/CPU-Nutzung, Engine-/Modellwechsel, Optionen, Grenzen/Fehler.
- **02.07 Modelle und Modellverwaltung:** Katalog/Identitäten/Metadaten, Discovery/Dateipfade, Provisionierung/Downloads, Final-/Realtime-Auswahl, Lifecycle/Laden/Warm-up/Unload, aktiver Wechsel, Operator-Intent, Idle-/Speicherpolitik, Kroko-Entitlements, Recovery.
- **02.08 Scheduler und Nebenläufigkeit:** Inferenz-Lanes/Worker, Shared Resources/Session-Isolation, Fairness/Backpressure, Queue-Limits/Prioritäten, Staleness/Cancel/Timeout, Multiuser-Verhalten.

### 03 – Einstellungen und Konfigurationssystem
- **03.01 Konfigurationsarchitektur:** Verschiedene Konfigurationsebenen und Zuständigkeiten.
- **03.02 Scopes:** Server, Session und alle weiteren tatsächlich implementierten Gültigkeitsbereiche.
- **03.03 Benennungskonventionen:** Code-/Wire-/CLI-/YAML-/Env-Namen und Zuordnung.
- **03.04 Datentypen und Validierung:** Defaults, Pflicht/Optional, Wertebereiche und Regeln.
- **03.05 Quellen und Prioritäten:** Defaults, Dateien, Env, CLI, gespeicherte Werte, API.
- **03.06 Server-Einstellungen:** Gültigkeit und Auswirkungen.
- **03.07 Session-Einstellungen:** Overrides, Isolation und Schranken.
- **03.08 Runtime-Änderungen:** Patch, Validate, Reload, Revisionen und Acknowledgements.
- **03.09 Wirksamkeitszeitpunkt:** Sofort, nächster Trigger/Session, Modellwechsel, Neustart – nur wie implementiert.
- **03.10 Persistenz:** Ort, Laden, Speichern, Konflikte, Fehlerbehandlung.
- **03.11 Secrets:** Trennung von normalen Settings und Zugangsdaten.
- **03.12 Abhängigkeiten:** Interdependenzen, Ausschlüsse und Auswirkungen.
- **03.13 Konfigurationsbeispiele:** Realtime, Wake-Word, Multiuser, CPU-Performance.

### 04 – Schnittstellen und Client-Integration
- **04.01 Schnittstellenübersicht:** HTTP/REST, WS V2, Legacy V1, OpenAI, Logs.
- **04.02 HTTP-Grundlagen:** Adressierung, Versionierung, Requests, Responses, Fehler.
- **04.03 WebSocket V2:** Verbindung, `hello`, Aushandlung und Sessions.
- **04.04 Commands/Acknowledgements:** IDs, `command.ack`, Replay, Konflikte.
- **04.05 Audiotransport:** Binärframes, Formate, Reihenfolge, Grenzen.
- **04.06 Eventtransport:** Hülle, `eventSeq`, Zustellung/Reihenfolge.
- **04.07 Snapshot/Synchronisierung:** Event-Reducer, Resync, Konsistenz.
- **04.08 Reconnect:** Verbindungswechsel, Identitäten, Lücken, Wiederanlauf.
- **04.09 Client-Zustandsmodell:** UI-State und konsistenter Reducer.
- **04.10 OpenAI-kompatible API:** Datei-Transkription, Modelle, Formate, Streaming, Auth.
- **04.11 Logzugriff:** Historie und Live-Logstream.
- **04.12 Legacy V1:** Unterstützter Altvertrag und saubere V2-Abgrenzung.
- **04.13 Integrationsbeispiele:** End-to-End V2-Client, inklusive Fehler/Reconnect.

### 05 – Administration, Sicherheit und Berechtigungen
- **05.01 Sicherheitsarchitektur:** Vertrauensgrenzen und geschützte Bereiche.
- **05.02 Serverzugriff:** Bind-Adresse, Netzwerk, HTTP/WS, Deployment-Sicherheit.
- **05.03 Admin-Authentifizierung:** API-Key, Berechtigungen, Validierung und Fehler.
- **05.04 Session-Zugriff:** Session-Rechte und Admin-Abgrenzung.
- **05.05 Log-Authentifizierung:** Tokens, Scope, Gültigkeit, Widerruf.
- **05.06 OpenAI-API-Authentifizierung:** Separater Schlüssel und Gate.
- **05.07 Kroko-Lizenzierung:** Key, Gültigkeit, Community/Pro, Force Community.
- **05.08 Native-Guard:** Runtime-Berechtigung, Lizenzkontext, nötige Neustarts.
- **05.09 Schutz von Daten/Secrets:** Environment, Redaktion, Logs, Dateien.
- **05.10 Fehler-/Zugriffsantworten:** HTTP-/WS-Verweigerungen und Formate.
- **05.11 Sicherheitsrelevante Betriebsregeln:** LAN/externer Zugang, sichere Konfiguration.

### 06 – Installation, Betrieb und Diagnose
- **06.01 Systemvoraussetzungen:** Plattformen, Python, Architektur, Ressourcen.
- **06.02 Installationskonzept:** Ein Produkt, Native-Runtime, CPU-only.
- **06.03 Windows-Installation:** Unterstützter CPU-Installationsweg.
- **06.04 Linux-Installation:** CPU-Torch, Constraints, Installationsprüfung.
- **06.05 Docker-Betrieb:** Images/Compose, Ports, Volumes, Konfiguration.
- **06.06 Ersteinrichtung:** Datenverzeichnisse, Schlüssel, Modelle, Defaults.
- **06.07 Serverstart/-stopp:** CLI, Env, Startup, Shutdown.
- **06.08 Datenhaltung:** Persistente Pfade, SQLite, JSON, Logs, Audio.
- **06.09 Logging:** Kanäle, Level, Datenschutz, Aufbewahrung.
- **06.10 Monitoring und Metriken:** Health, Queues, Worker, Betriebsstatus.
- **06.11 Performance/Ressourcen:** Threads, Latenz, Modellgröße, Multiuser.
- **06.12 Fehlerdiagnose:** Install, Audio, Model, Auth, Inferenz.
- **06.13 Wartung:** Neustart, Modellwechsel, Updates, Cleanup.
- **06.14 Datensicherung:** Welche Daten sichern und wie wiederherstellen.
- **06.15 Betriebsszenarien:** Einzelbenutzer, Multiuser, lokal, Container.

### 07 – Entwicklung, Tests, Build und Release
- **07.01 Entwicklungsumgebung:** Source-Checkout, venv, Werkzeuge, Abhängigkeiten.
- **07.02 Repository-Architektur:** Pakete, Module, Engineering-Verzeichnisse.
- **07.03 Technische Schnittstellen:** Recorder, Engine, Session, Server.
- **07.04 Erweiterungspunkte:** Verträge und sichere Integration neuer Funktionen.
- **07.05 Testarchitektur:** Unit, Contract, Integration, Packaging, Plattform.
- **07.06 Testverfahren:** Mit/ohne Modelle, Last, Regression.
- **07.07 Packaging:** `setup.py`, Wheel, sdist, Extras, Daten.
- **07.08 Native-Kroko-Build:** Buildinputs, Fingerprints, Provenienz, Plattformen.
- **07.09 CI:** Workflows, Matrix, CPU-only-Prüfung.
- **07.10 Release Candidate:** Manifest, Staging, Qualifikation.
- **07.11 Veröffentlichung:** Registries, Freigaben, Release-State-Machine.
- **07.12 Buildketten-Sicherheit:** Identitäten, Redistribution und Gates.
- **07.13 Änderungs-/Kompatibilitätsregeln:** Versionierung, Migration, Dokumentationsvalidierung.

### 08 – Kataloge und technische Referenzen
- **08.01 Event-Katalog:** Alle Events, Felder, Typen, Trigger, Reihenfolge, Beispiele.
- **08.02 Command-Katalog:** Alle Commands, Payloads, Zustände, Acks und Fehler.
- **08.03 Settings-Katalog:** Alle Settings, Scope, Typ, Default, Validierung, Änderung, Wirkung, Persistenz.
- **08.04 API-Endpunkt-Katalog:** Alle Routen, Methoden, Auth, Parameter, Rückgaben, Fehler.
- **08.05 Zustands-/Phasenkatalog:** Session, Activation, Modell und andere State Machines.
- **08.06 Timing-Katalog:** Timer, Fristen, Defaults, Zeitursprünge, gegenseitige Beziehungen.
- **08.07 Modell-Katalog-Referenz:** Schemata, IDs, Metadaten, Fähigkeiten, Lizenzklassen.
- **08.08 Engine-Referenz:** Zwei unterstützte Engines mit belegten Optionen.
- **08.09 Fehlerkatalog:** Alle Fehler-/Ablehnungs-/Close-Codes, Ursachen, Umgang.
- **08.10 WebSocket-Schema-Referenz:** Handshake, Nachrichten, Binärframe, Event, Snapshot, Close.
- **08.11 Logging-Katalog:** Ereignisse, Felder, Level, Kanäle, Redaktion.
- **08.12 CLI-/Env-Katalog:** Parameter, Umgebungsvariablen, Defaults, Prioritäten.
- **08.13 Daten-/Persistenzschema:** SQLite, JSON, Pfade, Lebensdauer.
- **08.14 Metrik-Katalog:** Alle Metriken, Einheiten, Bedeutungen und Grenzen.

### 09 – Anhänge und Kompatibilität
- **09.01 Glossar:** Kanonische Fachbegriffe und Begriffsbeziehungen.
- **09.02 Abkürzungen:** STT, ASR, VAD, PCM usw.
- **09.03 V1-/V2-Unterschiede:** Technische/protokollarische Abgrenzung.
- **09.04 Client-Migration:** V1 auf V2 einschließlich Bruchstellen.
- **09.05 Kompatibilitätsverträge:** Bewusst erhaltene öffentliche APIs.
- **09.06 Beispielszenarien:** Zusammenhängende End-to-End-Abläufe.
- **09.07 Quellen/Verifikation:** Zuordnung Kapitel ↔ Code/Schemas/Tests.
- **09.08 Dokumentationsstand:** Commit, Geltungsbereich, Unsicherheiten, Grenzen.

## D. Redaktionelle Gestaltungskriterien

### D.1 Standardaufbau erklärender Kapitel
1. **Worum geht es?** Einfache Einordnung und Bedeutung für Anwender/Client-/Serverentwicklung.
2. **Das Wesentliche auf einen Blick.** Kurze Erklärung und ggf. Mini-Diagramm.
3. **So funktioniert es.** Fachlicher Mechanismus mit korrekten Begriffen, Zuständen und Datenflüssen.
4. **Konkreter Ablauf.** Ein praxisnahes, vollständiges Beispiel; bei relevanten Timings ein Sequenzdiagramm.
5. **Konfiguration und Schnittstellen.** Welche Werte und Operationen steuern den Ablauf (Kataloglinks statt Copy-Paste großer Tabellen).
6. **Grenzfälle und Fehler.** Ablehnung, Retry, Timeout, Parallelität, Neustart, Diagnose.
7. **Siehe auch / Nachweise.** Kanonische Referenzen und geprüfte Codefundstellen.

Nicht jedes Kapitel benötigt jede Unterüberschrift; rein tabellarische Kataloge haben ihr eigenes Format. Inhaltliche Vollständigkeit und Lesbarkeit sind verbindlich, nicht ein starrer Textbaukasten.

### D.2 Diagrammvertrag
- Bevorzugt **Mermaid** (versionierbar, Markdown-kompatibel, ohne externe Dienste).
- Diagramme bevorzugt bei komplexen Abläufen: Activation-Phasen/Zeitachsen, Trigger/Wake-Arbitration, Audio/Transcription-Pipeline, Realtime/Final-Korrelation, Session/Client-Reconnect, Settings-Scopes und Patch-Wirkung, Modell-Lifecycle, Auth-Gates, Release-Gates.
- **Jede Diagrammkante ist durch eine konkrete Fakten-ID belegbar.** Keine erfundenen Schritte, Pseudo-Events oder vermeintliche Garantien.
- Diagramme haben aussagekräftigen Titel/Beschreibung und werden im Fließtext erläutert. Kein Diagramm ohne Mehrwert.
- Textliche Alternative/kurze Ablaufbeschreibung für Situationen, in denen Mermaid nicht gerendert wird.
- Verzicht auf beliebig generierte Screenshots oder Illustrationen, wenn sie technische Genauigkeit nicht verbessern.

### D.3 Stil und Praxisorientierung
- Deutsch, sachlich, freundlich, gut lesbar; kurze Absätze und verständliche Begriffe, ohne die technische Präzision zu verlieren.
- Erst die Motivation und das beobachtbare Verhalten, dann die Implementierungsdetails.
- Keine unvermittelten, riesigen Listen von Klassen- oder Variablennamen.
- Benutze Beispiele zu realistischen Einsatzfällen: Push-to-Talk, Wake-Word-Sitzung, Realtime/Final, Reconnect, Modellwechsel, Admin-Settings, Loganalyse.
- Kennzeichne CPU-only und vorhandene Plattform-/Lizenzgrenzen korrekt; keine GPU-Anleitung für V2.
- Identische Fachinformationen nur an einem autoritativen Ort; Querverweise statt widersprüchlicher Duplikate.

## E. Abnahme und maschinelle Prüfschritte

### E.1 Pro Kapitel
- Kapitel- und Unterkapitelabdeckung vollständig dokumentiert.
- Faktenakte gegen aktuellen Commit verifiziert.
- Mindestens jeder technische Mechanismus, Default, Timing, Zustandsübergang, API-Feld und Beispielbefehl durch Code-/Schema-Evidenz überprüft.
- Diagrammkanten und Beispiele überprüft.
- Verständlicher Einstieg + konkrete Anwendung, soweit fachlich sinnvoll.
- Review unabhängig und ohne unbelegte Alttextübernahme.
- Keine offenen kritischen oder erheblichen Findings.
- Links und Mermaid-Syntax gültig.

### E.2 Globale Integrationsgates
- **Vollständige Coverage:** alle neun Hauptkapitel und sämtliche **104** nummerierten Unterkapitel besitzen eindeutigen Status und geprüfte Zieladresse.
- API-Routen systematisch gegen Handler-/Router-Registrierungen abgeglichen; HTTP-Methoden und Auth-Scopes enthalten.
- V2-Kommandos, Events und Felder gegen registrierte Protokollschemata abgeglichen; V1 gesondert.
- Settings/CLI/Env gegen reale Registrierungen und Defaultquellen abgeglichen; keine bloß geschätzten Werte.
- Engine-Produktgrenze: nur `faster_whisper` und `kroko_onnx` als produktiv unterstützt; Drafts nicht als Produktfunktionen anpreisen.
- Timing-/State-Definitionen aus Implementierung nachvollzogen, inklusive Geltungsbereich und Wirksamkeitszeitpunkt.
- Keine unaufgelösten kritischen Widersprüche zwischen Kapiteln/Katalogen.
- Markdown-Links, Mermaid-Syntax, Codebeispiele (soweit isoliert ausführbar) und bestehende Dokutests erfolgreich.
- Altdokumentation und Produktcode während der Erstgenerierung unverändert.
- Ergebnisbericht und nachvollziehbare Freigabe im Repository, mit konkreten bekannten Grenzen.

### E.3 Statusfelder in der Aufgabenregistry
Für jede ID mindestens: `id`, `title`, `source_commit`, `owner_role`, `state`, `research_path`, `draft_path`, `review_path`, `findings`, `correction_round`, `dependencies`, `acceptance_evidence`, `integrated_path`.

## F. Vorgesehene Dateistruktur

```text
.opencode/agents/
    doc-orchestrator.md
    doc-researcher.md
    doc-writer.md
    doc-reviewer.md
engineering/documentation-workflow/
    master-plan.md
    task-registry.json
    coverage-matrix.json
    terminology.json
    decisions.md
    research/
    reviews/
    reports/
docs/v2-handbuch/
    README.md
    01-grundlagen/
    02-funktionsweise/
    03-konfiguration/
    04-schnittstellen/
    05-administration/
    06-betrieb/
    07-entwicklung/
    08-referenzen/
    09-anhaenge/
```

Die oben genannte Struktur ist ein Zielentwurf; vor Umsetzung bestehende `.opencode`-Konfiguration lesen und ergänzen, **niemals blind überschreiben**. Das `.opencode`-Tooling und die exakten Modell-IDs erst anhand der tatsächlich installierten OpenCode-/OpenChamber-Version überprüfen.

## G. Abschluss und Übergabe

1. Pilot 02.03 Activation mit kompletter Recherche, Autorenarbeit, unabhängigen Reviews und überprüfbaren Mermaid-Diagrammen.
2. Bei Pilot-PASS restliche Kapitel automatisiert bearbeiten; Abhängigkeiten beachten und keine Dateien mehrfach parallel beschreiben.
3. Globale Katalogabdeckungs- und Linkprüfung durchführen.
4. Dokumentations-Neubaseline mit `REVIEW_READY` zur unabhängigen Abnahme stellen.
5. **Keine automatische Entfernung alter Dokumente, kein Merge und keine Veröffentlichung.** Die Ablösung alter Legacy-STT-Dokumente erfolgt erst als ausdrücklich freigegebener, separater Migrationsschritt nach erfolgreicher Abnahme.
