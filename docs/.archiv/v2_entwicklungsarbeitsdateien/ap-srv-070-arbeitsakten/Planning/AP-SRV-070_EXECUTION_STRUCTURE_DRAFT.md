## AP-SRV-070 — EXECUTION STRUCTURE
### Server V2 Finalization, Cleanup, Packaging & Release

**Status:** DRAFT — zur gemeinsamen Abstimmung vor Ausführung
**Basis:** AP-SRV-060 ROOT PASS / Canonical + Distributed bereinigt
**Produktbereich:** Server
**Client-Produktcode:** außerhalb des Scopes

---

## 1. Zweck von AP-SRV-070

AP-SRV-070 ist das abschließende Server-Arbeitspaket der Initiative.

Es soll NICHT noch einmal eine größere neue Architektur einführen.

Der Zweck ist:

```text
bestehende Server-V2-Architektur
        ↓
Legacy-/Altlasten sauber abschneiden
        ↓
Produktoberfläche und Dokumentation finalisieren
        ↓
Package vollständig reproduzierbar bauen/installieren
        ↓
Production-Container herstellen
        ↓
vollständigen Release Candidate prüfen
        ↓
final veröffentlichen
```

AP-SRV-070 ist damit gleichzeitig:

```text
Final Cleanup
Productization
Packaging
Deployment Preparation
Release Qualification
Release
```

---

## 2. Was ausdrücklich NICHT in AP-SRV-070 gehört

Nicht Teil von AP-SRV-070:

```text
neue Client-Funktionalität
Client-Produktcodeänderungen
neue Triggerarchitektur
Neudesign des Activation Lifecycles
Neudesign des Wake-Word-Detektors
neue Settings-Architektur
neues Agent-/Workflow-System
empirische Wake-Word-Kalibrierung ohne reales Positivmaterial erzwingen
```

Wake-Word-Kalibrierung bleibt, falls weiterhin kein reales Material vorliegt:

```text
EVIDENCE_BLOCKED / calibration pending
```

Das ist als bekannte Release-Einschränkung sauber zu dokumentieren, aber nicht
durch erfundene oder synthetisch als "real" ausgegebene Evidence zu schließen.

---

## 3. Organisationsprinzip

AP-SRV-070 wird NICHT in einem Agentenlauf umgesetzt.

Stattdessen:

```text
W0  Delta-Revalidation / Scope Freeze
W1  Runtime & Legacy Hard Cut
W2  Product Surface / Docs / Repo Hygiene
W3  Packaging & Installed-Distribution Proof
W4  Production Docker / Deployment
W5  Release Candidate Audit
W6  Root Review + Canonicalization + External Publication
```

Jeder Block erhält:

```text
eigenen Agentenauftrag
klar abgegrenzten Scope
eigenen kumulativen Commit auf Distributed
eigenes Test-/Evidence-Gate
einen Root-Checkpoint vor dem nächsten Block
```

Kein Block darf "nebenbei" Arbeit aus einem späteren Block vorziehen, außer eine
technische Abhängigkeit macht das zwingend erforderlich und wird ausdrücklich
dokumentiert.

---

## 4. Git-/Review-Modell

Ausgangslage:

```text
Canonical:
feat/einheitliche-triggerarchitektur
c82923fc...

Distributed:
feat/einheitliche-triggerarchitektur-distributed
1e74fec3...

TREE(Canonical) == TREE(Distributed)
```

Für AP-SRV-070 soll erstmals der bereinigte Workflow gelten:

```text
Distributed HEAD
   ↓
W1 Run
   ↓
W2 Run
   ↓
W3 Run
   ↓
W4 Run
   ↓
W5 Run
   ↓
ggf. Root-Korrekturruns
```

Die Produktänderungen bleiben während der Umsetzung ausschließlich auf dieser
kumulativen Distributed-/Arbeitslinie.

Canonical bleibt währenddessen unverändert.

Erst nach finalem AP-SRV-070 ROOT PASS:

```text
Canonical:
c82923f
   ↓
GENAU EIN Aggregate-/Final-Commit AP-SRV-070
```

Der Canonical-Tree muss exakt dem final geprüften Distributed-Source-Tree
entsprechen.

---

## 5. W0 — Delta-Revalidation / Scope Freeze

### Zweck

Die bereits vorhandene AP-SRV-070-Discovery wurde noch vor dem finalen
AP-SRV-060 erstellt.

Sie darf deshalb nicht direkt als Lösch- oder Implementierungsliste benutzt
werden.

W0 gleicht sie gegen den finalen SRV-060-Stand ab.

### Änderungen

```text
KEIN Produktcode
KEIN Git-Worktree erforderlich
KEIN neuer Produktbranch
```

Analyse direkt read-only gegen den sauberen Canonical-Workspace.

Neue PREP-/Planungsberichte ausschließlich unter:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prep\
```

### Kernfragen

Neu beweisen:

```text
welche Legacy-Funde existieren noch?
welche wurden durch SRV-060 bereits ersetzt?
welche alten Remove-Candidates sind wirklich tot?
welche Compatibility-Seams werden noch benötigt?
welche Wake-Word-Altpfade sind noch erreichbar?
welche v1/v2-Grenzen müssen gehärtet werden?
welche Packaging-/Docker-/Doc-Lücken bestehen aktuell?
```

Besondere Prüfpunkte:

```text
ActivationController.finalized()
v1/v2 hard boundary
alte Wake-Word-Pfade
alte Loader / Config-Keys / Runtime-Downloads
Binary Test Fixtures
serverCommit/version metadata
Package Resources
Docker-/Release-Zustand
```

### Ergebnis

W0 endet mit einer verbindlichen Liste:

```text
CONFIRMED_REMOVE
MIGRATE_BEFORE_REMOVE
KEEP_REQUIRED
PROTOCOL_TEST_REQUIRED
PACKAGING_REQUIRED
DOC_REQUIRED
RELEASE_REQUIRED
```

Danach Scope Freeze für W1-W6.

---

## 6. W1 — Runtime & Legacy Hard Cut

### Zweck

Alle durch W0 nachweislich bestätigten runtime-relevanten Altpfade entfernen
oder sauber isolieren.

W1 ist bewusst auf Produktlogik und Protokollgrenzen beschränkt.

### Typischer Scope

Nur soweit W0 bestätigt:

```text
tote Legacy-Adapter
tote Helper / Lifecycle-Seams
alte Wake-Word-Pipeline
alte Loader
alte Runtime-Download-Pfade
alte Config-Keys
alte Triggerpfade
überholte Compatibility-Shims
nicht mehr erreichbare v1/v2-Vermischungen
obsolete Methoden wie ggf. ActivationController.finalized()
```

### Protocol Hard Cut

Explizite negative Tests:

```text
v1 erhält keine v2-Envelopes
v2 erhält keine v1-Messages
Session-ID-Welten werden nicht vermischt
falsche Protocol-Version wird deterministisch abgewiesen
Version/Commit-Metadaten sind eindeutig
```

### Nicht in W1

```text
README-Großumbau
PyPI
Docker Release
GitHub Release
generelle Doku-Neustrukturierung
```

### Gate

Mindestens:

```text
gezielte RED-FIRST Regressionen für entfernte/härtere Pfade
relevante Unit-/Integrationtests
Race-/Lifecycle-Tests, wenn betroffene Seams Nebenläufigkeit berühren
git diff --check
keine neuen Compatibility-Leaks
```

Nach W1:

```text
BLOCK PASS
```

bevor W2 beginnt.

---

## 7. W2 — Product Surface / Documentation / Repository Hygiene

### Zweck

Nach dem Runtime-Cut soll das Repository wie ein fertiges Produkt aussehen und
nicht wie eine laufende Agentenbaustelle.

### Aktive Produktoberfläche

Mindestens sauber organisieren:

```text
README
Getting Started
Installation
Quick Start
Configuration
Environment
API / Protocol v2
Sessions / Activations / Events / Errors
Settings / Apply Policies
Wake Words
Transcription Lifecycle
Architecture
Operations / Logging / Diagnostics
Development
Testing
Deployment
Packaging / Release
```

### README-Ziel

Kurz und produktorientiert:

```text
Was ist Voice STT Server?
Features
Installation
60-second Quick Start
Docker
Minimal Configuration
API Entry Points
Documentation Links
```

### Repository Hygiene

Prüfen/aufräumen:

```text
aktive WIP-Dokumente
veraltete Beispiele
lokale Pfade
temporäre Reports
Debug-/Development-Reste
stale Config-Beispiele
doppelte aktive Dokumentation
nicht archivierte Agenten-/Review-Artefakte
Caches / Buildreste
```

Historische Nachweise bleiben erhalten, aber klar im Archiv isoliert.

### Wake-Word-Dokumentation

Die bereits vorbereitete Wake-Word-Dokumentation wird gegen den finalen
Produktstand aktualisiert und in die aktive Produktdokumentation integriert.

Kalibrierungsstatus ehrlich:

```text
calibration pending
```

wo noch keine reale Evidence vorliegt.

### Gate

```text
keine WIP-Sprache auf aktiver Produktoberfläche
keine widersprüchlichen Settings/API-Angaben
keine Links auf nicht existierende Dateien
README und Detaildoku konsistent
Archivhistorie unangetastet
git diff --check
```

---

## 8. W3 — Packaging & Installed-Distribution Proof

### Zweck

Beweisen, dass nicht nur das Source-Repo funktioniert, sondern das tatsächlich
verteilte Python-Paket.

Noch KEINE externe Veröffentlichung.

### Packaging Authority

Eindeutig festlegen/prüfen:

```text
Package Name
Version Authority
Build Backend
Entry Points
Package Resources
License / Metadata
Dependencies
Python Version Contract
```

Keine doppelte Versionswahrheit.

### Build

Aus sauberem Stand:

```text
wheel
sdist
```

Reproduzierbar und ohne lokale Entwicklungsreste.

### Wake-Word Packaging Hard Gate

Das installierte Package muss enthalten:

```text
models.json
produktive ONNX-Classifier
produktive TFLite-Classifier
Pipeline-/Featureassets
benötigtes VAD-Asset
```

Beweisen:

```text
Package Resources funktionieren nach Installation
Catalog lädt aus installiertem Paket
GET /api/v2/wake-words funktioniert
ausgewähltes Wake Word kann Runtime initialisieren
keine Runtime-Downloads nötig
```

### Installed-Package Smoke

Test nicht gegen den Source-Tree, sondern gegen eine isolierte installierte
Distribution.

Die genaue Isolationsmethode wird vor W3 festgelegt, ohne das bestehende
Entwicklungssetup unnötig zu verändern.

### Noch nicht

```text
kein PyPI Upload
kein Docker Registry Push
kein GitHub Release
```

---

## 9. W4 — Production Docker / Deployment

### Zweck Docker-Deployment

Aus dem Server ein tatsächlich deploybares Production Image machen.

### Docker-Zielbild

```text
Multi-stage soweit sinnvoll
kleines Runtime-Image
kein vollständiges Source-Repo im Runtime-Image soweit vermeidbar
keine Tests / Prompts / Worklogs
keine Secrets
non-root soweit praktikabel
Healthcheck
saubere SIGTERM-/Shutdown-Behandlung
Config über Env / Config / Mount
OCI Metadata
Version / Commit / Source / License
keine Wake-Word-Runtime-Downloads
```

### Wichtige Architekturentscheidung

Der Container soll die installierte Distribution verwenden und nicht
versehentlich wieder einen Source-Checkout als Runtimebasis benutzen.

### Lokaler Proof

Noch kein Registry-Push.

Beweisen:

```text
Image Build
Container Start
Healthcheck
API erreichbar
GET /api/v2/wake-words
Session Admission
Wake-Word Assets im installierten Package
sauberer Shutdown
```

Wenn sinnvoll zusätzlich Compose-Beispiel für Production Deployment.

---

## 10. W5 — Release Candidate Audit

### Zweck

Das ist die umfassende Endprüfung VOR externer Veröffentlichung.

Keine neue Produktfunktion.

### Full Regression

Mindestens:

```text
vollständige Server-Test-Suite
gezielte v2 Boundary Tests
Activation/Session Lifecycle
Settings
Wake Words
Package install smoke
Package resource validation
Container smoke
shutdown/health behavior
git diff --check
Repo-Hygiene
```

### Release-Artefakte

Release Candidate erzeugen und eindeutig hashen:

```text
wheel
sdist
Release Notes
Package metadata
Container build input
```

Noch nicht extern veröffentlichen.

### Version Freeze

Spätestens hier:

```text
exakte Releaseversion fest
alle Artefakte referenzieren dieselbe Version
keine Versionsdrift mehr erlaubt
```

### Root Review

Nach W5 folgt der vollständige adversariale AP-SRV-070 Root Review über den
gesamten kumulativen Stand.

Root prüft unabhängig:

```text
Chain of Custody
gesamten relevanten Diff
Legacy Cut
Protocol Boundary
Docs
Packaging
Assets
Installed Distribution
Docker
Tests
Release Evidence
Scope/Hygiene
```

Ergebnis ausschließlich:

```text
ROOT PASS
```

oder:

```text
ROOT FAIL / RETURN FOR CORRECTION
```

Keine Veröffentlichung bei FAIL.

---

## 11. W6 — Canonicalization & External Publication

W6 beginnt ausschließlich nach ROOT PASS.

### A. Canonicalization

Genau ein AP-SRV-070 Aggregate-/Final-Commit auf:

```text
feat/einheitliche-triggerarchitektur
```

Parent:

```text
c82923fc...
```

Tree:

```text
exakt finaler Root-PASS-Source-Tree
```

### B. Release Tag

Releaseversion auf dem finalen Canonical-Stand taggen.

Kein Tag auf einem ungeprüften Zwischenstand.

### C. PyPI

Veröffentlichen:

```text
wheel
sdist
```

Idealerweise exakt die in W5 qualifizierten Artefakte bzw. reproduzierbar
byteidentische finale Artefakte.

Danach:

```text
frische Installation vom tatsächlich veröffentlichten Index
Import Smoke
Entry Point
API Smoke
Wake-Word Package Resources
```

### D. Production Container

Finales Image aus der veröffentlichten Version bauen.

Dann:

```text
Registry Push
fresh Pull
Smoke Test des frisch gezogenen Images
Digest dokumentieren
```

Bevorzugter Registry-Zielort wird vor W6 explizit festgelegt.

### E. GitHub Release

Enthält mindestens:

```text
Version
Release Notes
Source Tag
Package-Version
Container Tag/Digest
bekannte Einschränkungen
```

### F. Tracking / Archive Closure

AP-SRV-070:

```text
ROOT PASS
RELEASED
COMPLETE
```

Tracking-/Akte finalisieren.

Client darf dabei höchstens etablierte Tracking-/Historienupdates erhalten,
keine Client-Produktänderung.

---

## 12. Review-/Commit-Strategie je Block

Geplante Blöcke sind nicht gleichbedeutend mit C1/C2/C3.

Beispiel:

```text
W1 erster Agentenrun
  ↓
Commit auf Distributed
  ↓
Root-Checkpoint
  ↓
falls Finding:
W1 Correction Run
  ↓
weiterer unveränderlicher Commit
  ↓
Root-Checkpoint
```

Dann erst W2.

Somit bleibt Distributed:

```text
... -> W1 Run -> W1 Fix -> W2 Run -> W3 Run -> ...
```

also weiterhin:

```text
ein Commit pro eingereichtem Agentenrun
```

Canonical erhält dagegen erst am Ende:

```text
genau einen AP-SRV-070 Root-PASS-Commit
```

---

## 13. Warum diese Aufteilung

Die Blöcke trennen unterschiedliche Risikoklassen:

```text
W1 = Produktkorrektheit / Legacy
W2 = Produktoberfläche / Dokumentation
W3 = Distribution / Packaging
W4 = Deployment / Container
W5 = gesamter Release Candidate
W6 = irreversible externe Veröffentlichung
```

Dadurch verhindern wir:

```text
riesigen Agentenlauf
schwer reviewbare Mischdiffs
späte Entdeckung von Runtime-Problemen
Packaging-Fehler erst beim Release
Docker-Debugging zusammen mit Legacy-Cuts
externe Veröffentlichung vor sauberem Root Gate
```

---

## 14. Abhängigkeitskette

```text
W0
 ↓
W1 Runtime Cut
 ↓
W2 Product Surface
 ↓
W3 Packaging
 ↓
W4 Docker
 ↓
W5 RC Audit
 ↓
ROOT PASS
 ↓
W6 Canonicalize + Publish
```

Kein Block überspringt einen vorherigen Hard Gate.

---

## 15. Offene Entscheidungen vor Ausführung

Vor dem jeweiligen Block noch ausdrücklich festzulegen:

### Vor W1

```text
Welche v1-Kompatibilität bleibt bewusst bestehen?
Welche alten Pfade sind CONFIRMED_REMOVE?
```

### Vor W3

```text
exakte Packaging Authority
isolierte Install-Testmethode
```

### Vor W5

```text
exakte Releaseversion
```

### Vor W6

```text
PyPI-Ziel
Container Registry
Tagging-Schema
GitHub-Release-Format
```

Diese Punkte werden nicht ungeprüft vom Agenten selbst entschieden.

---

## 16. Zielzustand nach AP-SRV-070

Server ist:

```text
fachlich finalisiert
Legacy-bereinigt
Protocol-v2-sauber
produktorientiert dokumentiert
als Package reproduzierbar
aus installiertem Package funktionsfähig
als Production Container deploybar
vollständig getestet
extern veröffentlicht
release-seitig nachvollziehbar
```

Git-Historie:

```text
Canonical
  ein Aggregate-/PASS-Commit für AP-SRV-070

Distributed
  vollständige unveränderliche Run-/Correction-Provenienz

temporäre Worktrees/Branches
  nach Abschluss wieder entfernt
```

Danach beginnt erst die eigentliche Client-Finalisierung.
