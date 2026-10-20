---
goal: Windows-Candidate unter Linux bauen und auf Windows qualifizieren
version: 1
date_created: 2026-10-20
last_updated: 2026-10-20
owner: Issue 9
status: Planned
tags: [bug, infrastructure, build]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Datierter Nachtragsplan vor Implementierung auf Ausgangscommit
`354567a08993226f996a533026c4f8a6173e91ad`. Benutzerbeauftragter Fix im
bestehenden Issue-9-Branch/PR; kein neuer Releasepfad. Ablage gemaess
Repositoryregel im bestehenden Aktionsarchiv statt in einem parallelen
Planverzeichnis. Historische A-/B-Berichte bleiben unveraendert.

## 1. Requirements & Constraints

- **REQ-001**: Windows-AMD64-Kroko- und Produktwheels auf Ubuntu 24.04
  mit den aktuellen V2-Buildinputs erzeugen; genau diese Bytes auf
  windows-latest unter CPython 3.12 x64 installieren.
- **REQ-002**: Free und Pro in getrennten frischen Umgebungen mit pip check,
  nativem Import, installierter Produktidentitaet und HTTP-/Refusalidentitaet
  qualifizieren; SHA-256 und Quellprovenienz vor und nach Transfer vergleichen.
- **CON-001**: V2-Fingerprintschema, Windows-Fingerprints, gepinnte Toolchain,
  Upstreamrevision, Patchset und ArtifactStore-Verifikation unveraendert lassen.
- **CON-002**: Keine V1-Skripte oder historischen V1-Abhaengigkeitspins kopieren.
  Keine Wiederholung des nachweislich ungeeigneten Windows-Dockerbuilds.
- **SEC-001**: Kein Merge, Release, Deployment oder Git-Tagging; bestehende
  private Kandidatenstaging-Grenze und Least-Privilege-Rechte erhalten.
- **PAT-001**: Bestehende V2-Kandidaten-/Paketierungs-/Qualifikationshelfer
  wiederverwenden; RC-Manifest, Promotion und Resume nicht aendern.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Uebertragbarkeit und Ausgangslage vor Produktaenderung belegen.

| Task | Description | Completed | Date |
| --- | --- | --- | --- |
| TASK-001 | V1-Release, referenzierten erfolgreichen Run, Workflow und beide V1-Skripte lesen. Tatsaechliche Ubuntu-/Windows-Runnerlabels verifizieren. | yes | 2026-10-20 |
| TASK-002 | Aktuellen V2-Workflow, Windows-Toolchain/Fingerprint, Installerpatches, Store, Paketierung und Qualifikation pruefen. Ergebnis: Zielplattform ist von der Hostplattform trennbar; kompilierende Containerinputs muessen nicht geaendert werden. | yes | 2026-10-20 |

### Implementation Phase 2

- **GOAL-002**: Nach TASK-002 gezielten Build-/Transfer-/Installationspfad
  implementieren; Regressionen muessen vor Remoteversuch bestehen.

| Task | Description | Completed | Date |
| --- | --- | --- | --- |
| TASK-003 | tools/release_candidate.py um Linux-Cross-Orchestrierung des bestehenden gepatchten Dockerfile.windows/in_windows_container.sh erweitern. Fingerprint explizit windows/amd64/cp312/cp312 ueber bestehenden Rechner bestimmen. Store.lookup/store und bestehenden Produktwheelmerger verwenden. | no | |
| TASK-004 | .github/workflows/release-candidate.yml: separaten Ubuntu-Windows-Buildjob mit bestehenden variantengetrennten Fingerprintcaches, statischem Provenienzegate und Zwischenartefakt einfuegen; candidate-windows ausschliesslich Download, native frische Installationen und Reportupload ausfuehren lassen. Assemblyvertrag erhalten. Abhaengigkeit: TASK-003. | no | |
| TASK-005 | tests/unit/test_release_candidate.py und test_release_workflows.py um Buildhost-/Zieltrennung, gleiche Fingerprints, echten Store-/Tagcheck, Cache-/Integritaets-/Fehlerfaelle und no-Docker-on-Windows erweitern. Betroffene Build-, Fingerprint-, Store-, Qualifikations- und Release-Regressionen gemeinsam ausfuehren. Abhaengigkeiten: TASK-003, TASK-004. | no | |
| TASK-006 | build/BUILD.md als einzige allgemeine Buildauthority aktualisieren. Implementierung committen/pushen und genau den neuen Ref ueber vorhandenen gezielten RC-Workflow ausfuehren. Nur andersartige neue Fehler gezielt untersuchen, keine ungeeignete Hostkonfiguration erneut versuchen. Abhaengigkeit: TASK-005. | no | |

### Implementation Phase 3

- **GOAL-003**: Nach TASK-006 den tatsaechlich veroeffentlichten Branchstand
  und die echten Resultate ohne Gesamtfreigabe dokumentieren.

| Task | Description | Completed | Date |
| --- | --- | --- | --- |
| TASK-007 | Neue datierte WINDOWS_RC_UMSETZUNGSVERGLEICH-Datei mit Ursache, V1-/V2-Entscheidung, exaktem Commit, Befehlen, Runlinks, vier Wheel-/Nativehashen und tatsaechlichen Installations-/RC-Ergebnissen erstellen. Fehlende Faelle NOT_RUN/NOT_PROVEN nennen; historische Berichte nicht umschreiben. | no | |
| TASK-008 | Materielle neue Abweichungen gesondert dokumentieren; Archivregister und bestehenden PR #10 nach Livepruefung aktualisieren. Kein weiterer PR, keine automatische Freigabe. Abhaengigkeit: TASK-007. | no | |

## 3. Alternatives

- **ALT-001**: Windows-Dockerengine umschalten oder gleiche Hosted-Builds
  wiederholen: verworfen; falscher Buildhost und vom Benutzer ausgeschlossen.
- **ALT-002**: V1-Buildskripte/Pins uebernehmen: verworfen; wuerde die
  staerkere aktuelle V2-Toolchain-/Fingerprintautoritaet ersetzen.
- **ALT-003**: Hostplattform im laufenden Installer monkeypatchen:
  verworfen; wuerde Checkout-, Toolchain- und Artefaktsemantik verschleiern.

## 4. Dependencies

- **DEP-001**: Vorhandene gepinnte V2-Docker- und Microsoft-/OpenSSL-Inputs
  muessen auf dem isolierten Ubuntu-Runner erreichbar sein; kein Fallback.
- **DEP-002**: GitHub-Artefakttransfer innerhalb desselben Runs und echter
  Windows-Runner fuer beide frischen Installationen.

## 5. Files

- **FILE-001**: tools/release_candidate.py, .github/workflows/release-candidate.yml.
- **FILE-002**: tests/unit/test_release_candidate.py, tests/unit/test_release_workflows.py.
- **FILE-003**: build/BUILD.md, docs/.archiv/README.md und neue datierte
  Nachtragsdateien im bestehenden Issue-9-Aktionsordner.

## 6. Testing

- **TEST-001**: Gleiche Windows-Fingerprintdokumente und bestehender Goldenwert
  Free 28594e6d201fc4a7; vorhandene Patch-/Builder-/Toolchain-Digestguards bestehen.
- **TEST-002**: Verifizierter Cachereuse ohne Kompilation; echter Store lehnt
  falsche native Plattform/Variante/Hash ab; Builds scheitern sichtbar.
- **TEST-003**: Workflow-DAG erzwingt Ubuntu-Crossbuild vor Windows-Installation
  und beide Plattformberichte vor bestehender RC-Abnahme; Windowsjob ohne Docker.
- **TEST-004**: Tatsaechlicher neuer RC mit getrennten Free-/Pro-Venvs auf
  Windows und Linux sowie gemeinsamer Vier-Wheel-Integritaetspruefung.

## 7. Risks & Assumptions

- **RISK-001**: Erst der echte V2-Crossbuild beweist die Erreichbarkeit der
  strengeren V2-Pins; V1-Erfolg beweist keine V2-Binaerkompatibilitaet.
- **RISK-002**: Containerdateien koennen root gehoeren. Nur den eigenen
  temporaeren Ausgabeordner auf die aufrufende UID/GID zurueckuebertragen;
  keine ungesicherte Upstream-NSIS-/Temp-Cleanup-Orchestrierung uebernehmen.
- **ASSUMPTION-001**: Gleicher gepinnter V2-Compilercontainer, gleiche gepatchte
  Quellen, gleiche explizite Variante und gleiche native Retaggingtools
  erlauben unveraenderte Windows-Fingerprints trotz anderem Orchestrierungshost.

## 8. Related Specifications / Further Reading

- [Issue 9](https://github.com/marcosudau-vps/voice-stt-server/issues/9)
- [V1-Release](https://github.com/marcosudau-vps/voice-stt-server/releases/tag/v1.0.0)
- [Erfolgreiche V1-Validierung](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/36253196730)
- [V1-Workflow](https://github.com/marcosudau-vps/voice-stt-server/blob/v1.0.0/.github/workflows/release-candidate.yml)
- [V1-Crossbuild](https://github.com/marcosudau-vps/voice-stt-server/blob/v1.0.0/tools/v1_kroko_release.py)
- [V1-Wheelmerger](https://github.com/marcosudau-vps/voice-stt-server/blob/v1.0.0/tools/v1_product_wheel.py)
- [Aktuelle Buildauthority](../../../build/BUILD.md)
