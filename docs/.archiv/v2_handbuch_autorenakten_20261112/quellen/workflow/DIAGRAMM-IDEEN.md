# Diagrammideen – editierbarer Index

**Unbestätigte Vorschläge.** Mermaid-Diagramme erst nach belegter Code-Recherche erstellen.

## 01.02 – Architekturübersicht
**Status:** VERIFIED · [Notizen](diagram-notes/01.02.md) · [Kapitel](../docs/v2-handbuch/01-grundlagen/01.02-architekturuebersicht.md)
- **Komponentenübersicht** (flowchart): Welche Hauptkomponenten kommunizieren direkt miteinander?

## 01.03 – Komponenten und Schichten
**Status:** VERIFIED · [Notizen](diagram-notes/01.03.md) · [Kapitel](../docs/v2-handbuch/01-grundlagen/01.03-komponenten-und-schichten.md)
- **Schichten und Zuständigkeiten** (flowchart): Welche Komponente besitzt welche Verantwortung?

## 01.04 – Gesamter Datenfluss
**Status:** VERIFIED · [Notizen](diagram-notes/01.04.md) · [Kapitel](../docs/v2-handbuch/01-grundlagen/01.04-gesamter-datenfluss.md)
- **Audio-zu-Text-Datenfluss** (flowchart): Welche nachgewiesenen Datenübergaben führen zum Ergebnis?

## 01.05 – Betriebs- und Funktionsmodi
**Status:** VERIFIED · [Notizen](diagram-notes/01.05.md) · [Kapitel](../docs/v2-handbuch/01-grundlagen/01.05-betriebs-und-funktionsmodi.md)
- **Betriebsmodi im Vergleich** (flowchart): Welche Modi und Triggerkombinationen existieren tatsächlich?

## 01.06 – Serverweite und sitzungsbezogene Ressourcen
**Status:** VERIFIED · [Notizen](diagram-notes/01.06.md) · [Kapitel](../docs/v2-handbuch/01-grundlagen/01.06-serverweite-und-sitzungsbezogene-ressourcen.md)
- **Shared vs. Session** (flowchart): Welche Ressourcen sind serverweit, welche sitzungsgebunden?

## 01.07 – Identitäten
**Status:** VERIFIED · [Notizen](diagram-notes/01.07.md) · [Kapitel](../docs/v2-handbuch/01-grundlagen/01.07-identitaeten.md)
- **Identitäten und Lebensdauer** (flowchart): Wie sind Client, Connection, Session und Segment verknüpft?

## 01.09 – Architekturdiagramme
**Status:** VERIFIED · [Notizen](diagram-notes/01.09.md) · [Kapitel](../docs/v2-handbuch/01-grundlagen/01.09-architekturdiagramme.md)
- **Gesamtarchitektur** (flowchart): Welche Systeme und Grenzen sind architektonisch sichtbar?

## 02.01 – Session-Management
**Status:** VERIFIED · [Notizen](diagram-notes/02.01.md) · [Kapitel](../docs/v2-handbuch/02-funktionsweise/02.01-session-management.md)
- **Session-Lebenszyklus** (stateDiagram-v2): Welche Sessionzustände und Übergänge existieren?

## 02.02 – Audioverarbeitung
**Status:** VERIFIED · [Notizen](diagram-notes/02.02.md) · [Kapitel](../docs/v2-handbuch/02-funktionsweise/02.02-audioverarbeitung.md)
- **Audio-Pipeline** (flowchart): Wie durchläuft Audio Eingang, Puffer, VAD und ASR?

## 02.03 – Activation
**Status:** VERIFIED · [Notizen](diagram-notes/02.03.md) · [Kapitel](../docs/v2-handbuch/02-funktionsweise/02.03-activation.md)
- **Activation-Phasen** (stateDiagram-v2): Welche Phasen und erlaubten Übergänge sind im Code definiert?
- **Activation-Zeitablauf** (sequenceDiagram): Wie wirken Trigger, Timer, Audiofreigabe und Events zeitlich zusammen?

## 02.04 – Wake-Word
**Status:** VERIFIED · [Notizen](diagram-notes/02.04.md) · [Kapitel](../docs/v2-handbuch/02-funktionsweise/02.04-wake-word.md)
- **Wake-Word-Detektion und Rearm** (sequenceDiagram): Welche Schritte von Treffer über Admission bis Rearm sind belegt?

## 02.05 – Transcription
**Status:** VERIFIED · [Notizen](diagram-notes/02.05.md) · [Kapitel](../docs/v2-handbuch/02-funktionsweise/02.05-transcription.md)
- **Realtime-/Final-Korrelation** (sequenceDiagram): Wie werden vorläufige und finale Ergebnisse tatsächlich zugeordnet?

## 02.06 – Engines
**Status:** VERIFIED · [Notizen](diagram-notes/02.06.md) · [Kapitel](../docs/v2-handbuch/02-funktionsweise/02.06-engines.md)
- **Engine-Auswahl** (flowchart): Wie werden ausschließlich die zwei freigegebenen Engines ausgewählt?

## 02.07 – Modelle und Modellverwaltung
**Status:** VERIFIED · [Notizen](diagram-notes/02.07.md) · [Kapitel](../docs/v2-handbuch/02-funktionsweise/02.07-modelle-und-modellverwaltung.md)
- **Modell-Lifecycle** (stateDiagram-v2): Welche Modellzustände und Übergänge sind implementiert?

## 02.08 – Scheduler und Nebenläufigkeit
**Status:** VERIFIED · [Notizen](diagram-notes/02.08.md) · [Kapitel](../docs/v2-handbuch/02-funktionsweise/02.08-scheduler-und-nebenlaeufigkeit.md)
- **Inference-Queues** (flowchart): Wie werden Lanes, Worker und Sessions in der Inferenz koordiniert?

## 03.01 – Konfigurationsarchitektur
**Status:** VERIFIED · [Notizen](diagram-notes/03.01.md) · [Kapitel](../docs/v2-handbuch/03-konfiguration/03.01-konfigurationsarchitektur.md)
- **Konfigurationsebenen** (flowchart): Welche Konfigurationsinstanzen existieren tatsächlich?

## 03.02 – Scopes
**Status:** VERIFIED · [Notizen](diagram-notes/03.02.md) · [Kapitel](../docs/v2-handbuch/03-konfiguration/03.02-scopes.md)
- **Setting-Scopes** (flowchart): Welche Scopes gelten und wie beeinflussen sie sich?

## 03.05 – Quellen und Prioritäten
**Status:** VERIFIED · [Notizen](diagram-notes/03.05.md) · [Kapitel](../docs/v2-handbuch/03-konfiguration/03.05-quellen-und-prioritaeten.md)
- **Konfigurationspriorität** (flowchart): Welche wirksame Prioritätsreihenfolge definiert der Code?

## 03.08 – Runtime-Änderungen
**Status:** VERIFIED · [Notizen](diagram-notes/03.08.md) · [Kapitel](../docs/v2-handbuch/03-konfiguration/03.08-runtime-aenderungen.md)
- **Settings-Patch** (sequenceDiagram): Wie laufen Validierung, Anwendung, Revision und Quittierung?

## 03.09 – Wirksamkeitszeitpunkt
**Status:** VERIFIED · [Notizen](diagram-notes/03.09.md) · [Kapitel](../docs/v2-handbuch/03-konfiguration/03.09-wirksamkeitszeitpunkt.md)
- **Wirksamkeitszeitpunkt** (sequenceDiagram): Wann greifen Änderungen und welche Grenzen sind relevant?

## 04.03 – WebSocket V2
**Status:** VERIFIED · [Notizen](diagram-notes/04.03.md) · [Kapitel](../docs/v2-handbuch/04-schnittstellen/04.03-websocket-v2.md)
- **V2-Handshake** (sequenceDiagram): Wie läuft der reale hello-Handshake ab?

## 04.04 – Commands/Acknowledgements
**Status:** VERIFIED · [Notizen](diagram-notes/04.04.md) · [Kapitel](../docs/v2-handbuch/04-schnittstellen/04.04-commands-acknowledgements.md)
- **Command und ACK** (sequenceDiagram): Wie werden Kommando, Ack, Replay und Konflikt gehandhabt?

## 04.06 – Eventtransport
**Status:** VERIFIED · [Notizen](diagram-notes/04.06.md) · [Kapitel](../docs/v2-handbuch/04-schnittstellen/04.06-eventtransport.md)
- **Eventzustellung** (sequenceDiagram): Was ist hinsichtlich Reihenfolge und eventSeq garantiert?

## 04.07 – Snapshot/Synchronisierung
**Status:** VERIFIED · [Notizen](diagram-notes/04.07.md) · [Kapitel](../docs/v2-handbuch/04-schnittstellen/04.07-snapshot-synchronisierung.md)
- **Snapshot/Resync** (sequenceDiagram): Wie wird der Zustand nach Lücken synchronisiert?

## 04.08 – Reconnect
**Status:** VERIFIED · [Notizen](diagram-notes/04.08.md) · [Kapitel](../docs/v2-handbuch/04-schnittstellen/04.08-reconnect.md)
- **Reconnect** (sequenceDiagram): Wie erfolgt der real implementierte Wiederanlauf?

## 04.09 – Client-Zustandsmodell
**Status:** VERIFIED · [Notizen](diagram-notes/04.09.md) · [Kapitel](../docs/v2-handbuch/04-schnittstellen/04.09-client-zustandsmodell.md)
- **Client-State-Reducer** (flowchart): Welche State-Inputs und Aktualisierungsregeln gelten?

## 04.10 – OpenAI-kompatible API
**Status:** VERIFIED · [Notizen](diagram-notes/04.10.md) · [Kapitel](../docs/v2-handbuch/04-schnittstellen/04.10-openai-kompatible-api.md)
- **OpenAI-HTTP-Transkription** (sequenceDiagram): Wie laufen Upload, Modellauflösung, ASR und Antwort ab?

## 05.01 – Sicherheitsarchitektur
**Status:** VERIFIED · [Notizen](diagram-notes/05.01.md) · [Kapitel](../docs/v2-handbuch/05-administration/05.01-sicherheitsarchitektur.md)
- **Vertrauenszonen** (flowchart): Welche Schnittstellen sind öffentlich und welche geschützt?

## 05.03 – Admin-Authentifizierung
**Status:** VERIFIED · [Notizen](diagram-notes/05.03.md) · [Kapitel](../docs/v2-handbuch/05-administration/05.03-admin-authentifizierung.md)
- **Admin-Gate** (flowchart): Welche Admin-Requests passieren welche Prüfung?

## 05.05 – Log-Authentifizierung
**Status:** VERIFIED · [Notizen](diagram-notes/05.05.md) · [Kapitel](../docs/v2-handbuch/05-administration/05.05-log-authentifizierung.md)
- **Logtoken-Lebensdauer** (sequenceDiagram): Wie werden Logrechte und Tokens ausgegeben und validiert?

## 05.07 – Kroko-Lizenzierung
**Status:** VERIFIED · [Notizen](diagram-notes/05.07.md) · [Kapitel](../docs/v2-handbuch/05-administration/05.07-kroko-lizenzierung.md)
- **Community/Pro-Entscheidung** (flowchart): Wie wird der Kroko-Modellzugriff entschieden?

## 05.08 – Native-Guard
**Status:** VERIFIED · [Notizen](diagram-notes/05.08.md) · [Kapitel](../docs/v2-handbuch/05-administration/05.08-native-guard.md)
- **Native-Guard-Lifecycle** (stateDiagram-v2): Welche Native-Lifecycle-Grenzen sind tatsächlich implementiert?

## 06.05 – Docker-Betrieb
**Status:** VERIFIED · [Notizen](diagram-notes/06.05.md) · [Kapitel](../docs/v2-handbuch/06-betrieb/06.05-docker-betrieb.md)
- **Container-Aufbau** (flowchart): Wie hängen Image, Container, Netz und Volumes zusammen?

## 06.07 – Serverstart/-stopp
**Status:** VERIFIED · [Notizen](diagram-notes/06.07.md) · [Kapitel](../docs/v2-handbuch/06-betrieb/06.07-serverstart-stopp.md)
- **Serverstart und Shutdown** (sequenceDiagram): Welche Start-/Stopphasen sind beobachtbar?

## 06.10 – Monitoring und Metriken
**Status:** VERIFIED · [Notizen](diagram-notes/06.10.md) · [Kapitel](../docs/v2-handbuch/06-betrieb/06.10-monitoring-und-metriken.md)
- **Monitoring-Datenfluss** (flowchart): Woher kommen Metriken, Health-Daten und Logs?

## 07.08 – Native-Kroko-Build
**Status:** VERIFIED · [Notizen](diagram-notes/07.08.md) · [Kapitel](../docs/v2-handbuch/07-entwicklung/07.08-native-kroko-build.md)
- **Kroko-Buildkette** (flowchart): Welche verifizierbaren Eingänge und Artefakte umfasst der Native-Build?

## 07.10 – Release Candidate
**Status:** VERIFIED · [Notizen](diagram-notes/07.10.md) · [Kapitel](../docs/v2-handbuch/07-entwicklung/07.10-release-candidate.md)
- **RC-Qualifikation** (flowchart): Welche Gates bestehen auf dem Release-Candidate-Pfad?

## 07.11 – Veröffentlichung
**Status:** VERIFIED · [Notizen](diagram-notes/07.11.md) · [Kapitel](../docs/v2-handbuch/07-entwicklung/07.11-veroeffentlichung.md)
- **Release-State-Machine** (stateDiagram-v2): Welche Release-Zustände und Freigabegates sind implementiert?

## 08.05 – Zustands-/Phasenkatalog
**Status:** VERIFIED · [Notizen](diagram-notes/08.05.md) · [Kapitel](../docs/v2-handbuch/08-referenzen/08.05-zustands-phasenkatalog.md)
- **Zustandsautomaten-Übersicht** (stateDiagram-v2): Welche echten State-Machines gibt es?

## 08.06 – Timing-Katalog
**Status:** VERIFIED · [Notizen](diagram-notes/08.06.md) · [Kapitel](../docs/v2-handbuch/08-referenzen/08.06-timing-katalog.md)
- **Zeitlinien und Fristen** (sequenceDiagram): Welche Timer beeinflussen welchen fachlichen Ablauf?

## 09.03 – V1-/V2-Unterschiede
**Status:** VERIFIED · [Notizen](diagram-notes/09.03.md) · [Kapitel](../docs/v2-handbuch/09-anhaenge/09.03-v1-v2-unterschiede.md)
- **V1-/V2-Abgrenzung** (flowchart): Welche Endpunkte und Vertragsgrenzen sind jeweils gültig?

## 09.04 – Client-Migration
**Status:** VERIFIED · [Notizen](diagram-notes/09.04.md) · [Kapitel](../docs/v2-handbuch/09-anhaenge/09.04-client-migration.md)
- **Client-Migrationspfad** (flowchart): Welche nachweisbaren Schritte sind für die Umstellung erforderlich?

## 09.06 – Beispielszenarien
**Status:** VERIFIED · [Notizen](diagram-notes/09.06.md) · [Kapitel](../docs/v2-handbuch/09-anhaenge/09.06-beispielszenarien.md)
- **End-to-End-Szenario** (sequenceDiagram): Welcher vollständige Praxisablauf lässt sich sicher belegen?
