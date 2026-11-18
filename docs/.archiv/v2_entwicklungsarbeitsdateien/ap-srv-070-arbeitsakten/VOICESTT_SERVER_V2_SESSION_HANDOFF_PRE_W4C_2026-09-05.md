# VoiceSTT Server V2 — ausführliche Übergabe / Session Cut

## Stand nach W4AB + Ubuntu-Requalification, vor W4C

**Datum:** 2026-09-05
**Projekt:** `marcosudau-vps/voice-stt-server`
**Scope:** ausschließlich **Server V2**
**Zweck:** Vollständige Übergabe an eine neue Koordinationssession, damit ohne Verlust des Projektkontexts direkt mit der letzten technischen Implementierungsphase weitergearbeitet werden kann.

---

## 1. Executive Summary

Der eigentliche fachliche Server-V2-Umbau ist praktisch abgeschlossen.

Abgeschlossen sind insbesondere:

- Trigger-/Activation-Architektur
- Commands / Timer
- Protocol v2
- Settings Control
- Wake-Word-Architektur
- Packaging / zentrale Versionsautorität
- Kroko Artifact Authority / Free-Pro-Trennung
- Windows- und Ubuntu-Qualification des Kroko-Build-/Reuse-Pfads
- STT Model Management / Discovery / Recovery / Provisioning
- Secret Boundary
- transaktionale Model-Refresh-Semantik
- Linux-Test-Portabilität

Aktueller maßgeblicher Git-Stand:

```text
DISTRIBUTED:
fa3c9dc887b0d3930ac0e201b93a4803c308082f

TREE:
a532f3b493546181c6540a137fec383ee19da4c7

CANONICAL:
c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

Canonical bleibt absichtlich noch auf AP-SRV-060, bis AP-SRV-070 vollständig Root-PASS ist.

Der finale Hermes-/Ubuntu-Rerun ist **PASS**:

```text
TARGETED_LINUX_TESTS:
169 passed
86 subtests passed
0 failed
0 errors

ARTIFACT_REUSE:
PASS

IMPORT:
PASS

REPO_HYGIENE:
PASS

NATIVE_BUILD_STARTED:
NO
```

Der erste reale Ubuntu-Build war davor bereits erfolgreich:

```text
Linux fingerprint:
98793851d8632294

Artifact:
kroko_onnx-1.12.9-1free-cp312-cp312-linux_x86_64.whl

SHA256:
7355732a01c62844b7e68bc2b1b17d978d48dc201c62fdd9650adb5cdbb6ed67

Bytes:
8286712

Native Free Build:
PASS

Second-run REUSE:
PASS
```

**Nächste Phase: W4C — Production Docker / Deployment.**

W4C ist der letzte geplante echte technische Implementierungsblock.

Danach:

```text
W5 Release Candidate Qualification
→ Final Root-PASS AP-SRV-070
→ Canonical Close
→ W6 Release Automation / Publication
→ Fresh External Verification
→ Server V2 fertig
```

---

## 2. Git- und Branch-Strategie

### Distributed

Branch:

```text
feat/einheitliche-triggerarchitektur-distributed
```

Zweck:

- vollständige Agenten-/Run-/Korrekturprovenienz
- ein Commit pro abgeschlossenem Lauf
- lineare Historie
- keine History-Rewrites

Aktuell:

```text
fa3c9dc887b0d3930ac0e201b93a4803c308082f
```

### Canonical

Branch:

```text
feat/einheitliche-triggerarchitektur
```

Zweck:

- genau ein kanonischer Commit pro vollständig Root-abgenommenem AP
- keine Zwischenstände
- keine Agentenrun-Provenienz

Aktuell:

```text
c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

### Bis zum finalen AP-SRV-070 Root-PASS verboten

- Canonical vorzeitig aktualisieren
- Rebase/Amend veröffentlichter Distributed-Commits
- Force-Push
- Release-Tag erzeugen
- PyPI veröffentlichen
- GHCR veröffentlichen
- Docker Hub veröffentlichen
- GitHub Release erzeugen

---

## 3. Arbeitsweise / Orchestrierung

Die Hauptsession arbeitet als Koordinator und Root-Reviewer.

Typischer Ablauf:

```text
Koordination
→ Agentenauftrag
→ Implementierung
→ Evidence
→ Root Review
→ ggf. kleine Korrekturrunde
→ Distributed Commit
→ später Canonical Close
```

Die Koordination:

- definiert den Scope
- friert Contracts ein
- formuliert Agentenprompts
- entscheidet PASS/FAIL
- verhindert unnötige Neuentwürfe
- hält Git-Governance ein
- hält den Gesamtplan zusammen

Agents sollen **nicht** selbständig die gesamte Architektur neu bewerten.

### Review-Regel

Ein Finding blockiert nur bei realistischem:

```text
Correctness
Security / Secret leakage
Data loss
Runtime
Deployment
Release
klare Contract-Verletzung
```

Nicht blockierend:

- theoretische zusätzliche Reproduzierbarkeit
- „man könnte noch einen SHA mehr pinnen“
- kosmetische Refactorings
- alternative Architekturen ohne echten Defekt
- zusätzliche Hardening-Ideen ohne reproduzierbares Risiko

### Kein Repo-weites Re-Audit

Neue Agents bekommen:

```text
1. exakten Start-Commit
2. engen Scope
3. bereits geschlossene Contracts
4. konkrete Acceptance Gates
5. relevante Dateien / Tests
6. Stop-Regel
```

Sie sollen nicht:

- die komplette AP-SRV-010..070-Historie lesen
- alle Root-Berichte neu auditieren
- W4A/W4B neu entwerfen
- vorsorglich alle Dependencies neu untersuchen

### Bevorzugter Rhythmus

```text
1 Implementierungsrun
→ 1 Root Review
→ maximal 1 eng begrenzte Correction bei echtem Blocker
```

Keine erneuten Phase1/Phase2/Phase2R/Phase2S-Ketten ohne realen Produktfehler.

### Token-/Context-Limit-Notfallregel

Wenn ein Agent oder Chat an Limits läuft, sofort Handoff erzeugen mit:

```text
CURRENT_BRANCH
CURRENT_HEAD
PARENT
REMOTE DISTRIBUTED
CANONICAL
git status --short
geänderte Dateien
erledigte Requirements
gelaufene Tests
offene Tests
offene TODOs
exakter nächster Schritt
bekannte Blocker
```

Wenn nötig einen separaten WIP-Handoff-Branch erzeugen, aber Distributed und Canonical nicht verändern.

---

## 4. Geschlossene fachliche Bereiche

Ohne konkreten reproduzierbaren Defekt nicht neu öffnen:

### Trigger / Activation / Protocol

- serverautoritativer Trigger-Lifecycle
- Activation-Lifecycle
- Commands
- Timer
- Protocol v2
- v1/v2 Boundary
- negative Boundary-Tests

### Settings / Control Plane

- Settings Control
- Runtime-/Session-/Startup-Semantik
- administrative Control Plane
- Event-/Logging-Grundlagen

### Wake Word

- Wake Word Catalog
- Detection
- Runtime Authority
- Assets
- Generatoren
- Packaging
- Legacy-Migration

### W3 Packaging

- zentrale Versionsautorität
- Wheel / sdist
- Packaging Authority
- Wake-Assets im Package
- Install-Smokes

### W4A Kroko Artifact Authority

- persistenter Artifact Store
- Free/Pro getrennt
- Build Fingerprint
- Toolchain Authority
- Windows/Linux Plattformprüfung
- Runtime ABI/Platform-Gates
- Secret-freier Buildpfad
- Reuse-by-default
- expliziter Rebuild
- Race-/Crash-Sicherheit
- Retention / GC
- Linux Wheel `1free` / `1pro`
- OpenSSL Development Identity im Linux-Fingerprint

### W4B STT Model Management

- Model Authority
- Operator Intent
- Discovery
- Recovery
- Provisioning
- Auto-download-Hierarchie
- Last-Known-Good
- administrative NOT_READY-Semantik
- resolved-engine Options
- transaktionaler Model Refresh
- Secret Boundary
- deterministische Kroko Runtime-Variante

---

## 5. W4AB-C1 und Ubuntu — finaler Status

Findings A–J:

```text
A Linux variant tagging               PASS
B Linux OpenSSL/toolchain fingerprint PASS
C Free+Pro coexistence                PASS
D Retention/GC                        PASS
E Key != license/runtime authority    PASS
F deterministic runtime variant       PASS
G resolved-engine options             PASS
H secret boundary                     PASS
I refresh semantics                   PASS
J cross-platform wheel fixtures       PASS
```

Windows Full Unit auf dem finalen Produktstand vor dem Test-only Linux-Portability-Commit:

```text
1513 passed
14 skipped
974 subtests passed
0 failed
0 errors
```

Linux-Test-Portability-Fix:

```text
COMMIT:
fa3c9dc887b0d3930ac0e201b93a4803c308082f

CHANGED:
tests/unit/test_kroko_artifact_store.py

PRODUCT_CODE_CHANGED:
NO
```

Hermes final:

```text
OVERALL: PASS
TARGETED_LINUX_TESTS: 169 passed + 86 subtests
ARTIFACT_REUSE: PASS
IMPORT: PASS
REPO_HYGIENE: PASS
NATIVE_BUILD_STARTED: NO
```

Damit:

```text
W4A: CLOSED
W4B: CLOSED
W4AB UBUNTU QUALIFICATION: CLOSED
```

---

## 6. Nächste Arbeitsphase: W4C — Production Docker / Deployment

### Ziel

Bis jetzt ist der Server als **Software** weitgehend fertig.

W4C macht daraus ein **deploybares Production-Produkt**.

Zielbild:

```text
VoiceSTT Source
      ↓
Python Wheel
      ↓
qualifiziertes Kroko Artifact
      ↓
Production Docker Image
      ↓
Production Compose
      ↓
isolierter realer Deployment-Smoke
```

W4C ist der letzte geplante echte technische Implementierungsblock.

### Was W4C ausdrücklich nicht mehr macht

Nicht erneut öffnen:

- Triggerarchitektur
- Protocol v2
- Wake Word
- Model Registry
- Auto-download-Semantik
- Kroko Artifact Authority
- Free/Pro Authority
- Secret-Redaction-Architektur
- Fingerprinting
- Release-Versionierung

W4C verdrahtet diese Authorities nur noch für Production.

---

## 7. W4C — Funktionsumfang

### 7.1 Production Dockerfile

Ziel:

```text
Source
→ Builder Stage
→ VoiceSTT Wheel
→ Runtime Stage
→ pip install Wheel
→ Production Runtime
```

Anforderungen:

- Multi-stage
- kein `pip install -e`
- kein Source-Mount als Runtime-Abhängigkeit
- Runtime konsumiert gebautes Wheel
- unprivilegierter User
- Healthcheck
- sauberer SIGTERM
- OCI Metadata
- Version / Commit nachvollziehbar
- keine Build-Secrets in Layern
- Kroko-Key nicht im Build
- keine unnötigen Buildtools im finalen Image

### 7.2 Kroko in Production

Normaler Containerstart darf Kroko niemals kompilieren.

Ziel:

```text
qualifiziertes Kroko Artifact
→ Docker Build
→ Runtime Image
```

Free/Pro bleiben getrennt.

Ein Key entscheidet niemals über die Variante.

### 7.3 Große STT-Modelle

Faster-Whisper- und Kroko-ASR-Modelle gehören nicht ins Image.

Persistenter Runtime Model Store:

```text
<runtime>/models/stt/fasterwhisper
<runtime>/models/stt/kroko_asr
```

Custom Model Paths bleiben primäre Discovery-Quellen.

Read-only Custom Paths bleiben zulässig.

Provisioning:

- bevorzugtes writable Ziel verwenden
- sonst Default Runtime Model Store
- `.part` / staging im Zielverzeichnis
- Verify
- Atomic Rename

Kein separates permanentes Download-Cache-System.

### 7.4 Compose

Production Compose soll verdrahten:

- Image / Build
- Ports
- Runtime Data Root
- Model Store
- Kroko Artifact
- Secrets
- Restart Policy
- Healthcheck
- Runtime-Konfiguration
- Persistenz

### 7.5 Realer Deployment-Smoke

Nicht nur:

```text
docker build → exit 0
```

sondern:

```text
Image bauen
→ Container starten
→ Health grün
→ Server erreichbar
→ Protocol-v2 Handshake
→ Model Management erreichbar
→ Persistenz
→ Recreate
→ Health wieder grün
→ SIGTERM
→ sauber beendet
```

Bestehende produktive Installation möglichst nicht anfassen.

---

## 8. Offene W4C-Entscheidungen

Die neue Session soll **zuerst diese Entscheidungen mit dem Nutzer abschließen**. Vorher nicht implementieren.

### Frage 1 — Container-Varianten

#### A — getrennte Free/Pro Targets

```text
VoiceSTT Free
VoiceSTT Pro
```

Selbes Buildsystem, jeweilig passendes Kroko-Wheel.

*Empfehlung: A**

#### B — zunächst nur Free

Pro vorbereitet, erstes Release aber nur Free.

#### C — ein Image mit Laufzeitwechsel Free/Pro

Nicht empfohlen.

---

### Frage 2 — Linux-Basisimage

#### A — Ubuntu 24.04

Vorteile:

- real qualifizierte Umgebung
- geringeres ABI-/OpenSSL-Risiko

*Empfehlung: A**

#### B — Python 3.12 slim / Debian

Kleiner, aber neue Runtime-Kombination.

---

### Frage 3 — CPU / GPU

#### A — V2 CPU-only

*Empfehlung: A**

#### B — sofort CUDA/NVIDIA zusätzlich

Erhöht Scope deutlich.

---

### Frage 4 — Default Auto-Download

#### A — standardmäßig OFF

```text
auto_download = false
```

Server bleibt administrierbar, STT kann `NOT_READY` sein, keine überraschenden GB-Downloads.

*Empfehlung: A**

#### B — Defaultmodelle beim ersten Start automatisch provisionieren

---

### Frage 5 — interner persistenter Data Root

Empfehlung:

```text
/var/lib/voicestt
```

Beispiel:

```text
/var/lib/voicestt/
├─ data/
└─ models/
   └─ stt/
      ├─ fasterwhisper/
      └─ kroko_asr/
```

---

### Frage 6 — Host-Persistenz

#### A — Bind Mounts

Vorteile:

- transparent
- einfach zu sichern
- einfach zu migrieren
- passt zur bestehenden Selfhost-Struktur

*Empfehlung: A**

#### B — Docker Named Volumes

---

### Frage 7 — Runtime Secrets

#### A — externes `.env`

Einfach und schnell.

#### B — Docker Secrets only

Dafür ggf. `_FILE`-Support ergänzen.

#### C — ENV + `_FILE`

Kompatibel und production-tauglich.

*Empfehlung: C**

Wenn Scope maximal klein bleiben soll: A.

---

### Frage 8 — realer W4C Deployment-Test

#### A — isoliert auf VPS

Eigenes Compose-Projekt, eigene Verzeichnisse, freier High-Port, kein Caddy.

*Empfehlung: A**

#### B — nur Windows Docker Desktop

Weniger aussagekräftig.

#### C — bestehende Production-Instanz ersetzen

Nicht empfohlen.

---

### Frage 9 — Caddy / öffentliche Domain

#### A — W4C bleibt localhost / High-Port

Caddy erst nach Final Qualification / Release.

*Empfehlung: A**

#### B — Staging-Subdomain

#### C — echte Domain sofort umschalten

Nicht empfohlen.

---

### Frage 10 — Kroko Build-Verhalten im Docker-Build

#### A — Release-Build verlangt qualifiziertes Artifact

Fehlt es:

```text
BUILD FAIL
```

#### B — Docker-Build darf Kroko bei Cache-Miss selbst bauen

#### C — beides

Development:

```text
build-if-missing erlaubt
```

Release:

```text
qualified artifact required
```

*Empfehlung: C**

---

### Frage 11 — Architektur

#### A — `linux/amd64` für V2

*Empfehlung: A**

#### B — sofort zusätzlich ARM64

Würde eigenen Build-/Qualification-Pfad erzeugen.

---

## 9. Empfohlene Default-Konfiguration

Wenn der Nutzer sagt „nimm deine Empfehlungen“:

```text
1  A  getrennte Free + Pro Targets
2  A  Ubuntu 24.04
3  A  CPU-only
4  A  Auto-download default OFF
5     /var/lib/voicestt
6  A  Bind Mounts
7  C  ENV + optional _FILE secrets
8  A  isolierter VPS-Smoke
9  A  kein Caddy in W4C
10 C  Development build-if-missing möglich,
      Release verlangt qualifiziertes Artifact
11 A  linux/amd64
```

---

## 10. Zwei W4C-Entscheidungen gelten bereits als geschlossen

Sofern der Nutzer nicht ausdrücklich widerspricht:

### Health

Fehlendes STT-Modell darf Docker-Liveness nicht zerstören.

```text
Process / Control Plane alive
→ container healthy
```

STT-Modell fehlt:

```text
STT NOT_READY
```

Nicht:

```text
unhealthy
→ restart loop
```

### Große Modelle

Keine Faster-Whisper-/Kroko-ASR-Gigabyte-Modelle ins Image backen.

Modelle bleiben persistent extern.

---

## 11. W4C Acceptance Gates

Der spätere W4C-Prompt soll mindestens prüfen:

1. Docker Build erfolgreich
2. Runtime nutzt gebautes VoiceSTT-Wheel
3. kein Editable Install
4. non-root
5. OCI Version + Commit korrekt
6. Healthcheck grün
7. Server startet
8. Health-Endpunkt grün
9. `/ws/v2` Handshake möglich
10. Wake-Word-Assets vorhanden
11. Model Management startet
12. fehlendes Modell → administrierbares `NOT_READY`
13. persistente Daten über Recreate erhalten
14. persistente Modelle über Recreate erhalten
15. SIGTERM sauber
16. keine Secrets in Image/Layer/Logs/Metadata
17. Kroko startet ohne Native-Build im normalen Production-Start
18. Free/Pro sauber getrennt

---

## 12. Agentenstrategie für W4C

Empfohlen: ein starker Agent mit engem Scope.

Der Agent soll nur lesen:

- finalen aktuellen Commit
- W4C-Prompt
- relevante Docker-/Compose-Dateien
- Packaging Authority
- Kroko Runtime/Artifact Schnittstellen
- STT Model Management Schnittstellen
- Health-/Startup-/Shutdown-Pfade
- unmittelbar relevante Tests

Nicht lesen:

- komplette AP-Historie
- alte W4A-C1/C2/C3/C4-Forensik
- alte Trigger-/Wakeword-Root-Berichte
- gesamten Docs-Baum

Ziel:

```text
ein großer W4C Implementierungsrun
→ ein Review
→ maximal eine kleine echte Correction
```

---

## 13. Nach W4C

Nach W4C soll keine neue geplante Produktfunktion mehr kommen.

Dann:

### W5 — Release Candidate Qualification

Gesamtsystem prüfen:

```text
Unit
Packaging
Wheel / sdist
Kroko
Ubuntu
Docker
Health
Protocol v2
Wake Word
Model Management
Persistenz
Shutdown
Security
```

Keine Veröffentlichung in W5.

### Final Root-PASS

Nur reale Produkt-/Releasefehler blockieren.

### Canonical Close

Canonical erhält genau einen AP-SRV-070-Gesamtabschluss.

Tree-Invariante:

```text
TREE(Canonical AP-SRV-070)
==
TREE(finaler Root-PASS Distributed Stand)
```

### W6 — Release

Ziel:

```text
Preflight
→ automatische Version
→ immutable Tag
→ PyPI
→ GHCR
→ Docker Hub
→ GitHub Release zuletzt
→ Fresh External Verification
```

---

## 14. Release-Grundsätze

### Versionierung

Version nicht manuell erraten.

Eine zentrale Versionsautorität existiert bereits.

W6 soll daraus automatische konsistente Release-Versionierung machen.

### Preflight vor Tag

Wichtigster Vertrag:

```text
alles Prüfbare zuerst
→ erst dann immutable Tag
```

Nicht:

```text
Tag erzeugen
→ dann feststellen, dass Build kaputt ist
```

### Publish-Reihenfolge

```text
1. Preflight
2. Version Freeze
3. Git Tag
4. PyPI
5. GHCR
6. Docker Hub
7. GitHub Release zuletzt
8. Fresh External Verification
```

### Resume / Recovery

Wenn Publish teilweise scheitert, keine neue Version und keinen neuen Tag erfinden.

Mögliche Release-State-Machine:

```text
PRECHECKED
TAGGED
PYPI_PUBLISHED
GHCR_PUBLISHED
DOCKERHUB_PUBLISHED
GITHUB_RELEASED
EXTERNAL_VERIFIED
COMPLETE
```

---

## 15. Definition „Server V2 fertig“

```text
[x] W4A geschlossen
[x] W4B geschlossen
[x] Ubuntu Kroko Qualification PASS
[x] Linux Test-Portability PASS

[ ] W4C Production Deployment PASS
[ ] W5 RC Qualification PASS
[ ] AP-SRV-070 Root PASS
[ ] Canonical AP-SRV-070 Close
[ ] Release-Version automatisiert/konsistent
[ ] Preflight PASS
[ ] Git Tag
[ ] PyPI
[ ] GHCR
[ ] Docker Hub
[ ] GitHub Release
[ ] Fresh PyPI Install PASS
[ ] Fresh GHCR Pull/Run PASS
[ ] Fresh Docker Hub Pull/Run PASS
[ ] Archive Close
```

---

## 16. Wichtige Pfade

Windows-Arbeitsbereich:

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w4b
```

Workflow-/Evidence:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\
```

Masterplan:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\VOICESTT_SERVER_V2_ABSCHLUSS_MASTERPLAN_2026-09-05.md
```

W4AB Windows Evidence:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4AB-C1\Final\
```

Linux Test-Fix Evidence:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4AB-LINUX-TESTFIX\
```

Hermes Qualification:

```text
/home/marco/workspace/hermes/projekte/voice-stt-server-projekt/ubuntu_qualification_02/W4AB-C1-Ubuntu-Requalification/
```

Hermes finaler Rerun:

```text
/home/marco/workspace/hermes/projekte/voice-stt-server-projekt/ubuntu_qualification_02/W4AB-C1-Ubuntu-Requalification/evidence-rerun/
```

---

## 17. Was die neue Session als Erstes tun soll

Noch nicht implementieren.

Zuerst:

1. Diese Übergabe vollständig lesen.
2. Den Nutzer durch die 11 offenen W4C-Entscheidungen führen.
3. Entscheidungen verbindlich festhalten.
4. Daraus einen einzigen vollständigen W4C-Implementierungsprompt erstellen.
5. Passendes Agentenmodell empfehlen.
6. Erst nach Freigabe Agentenarbeit starten.

W4A/W4B nicht erneut prüfen.

---

## 18. Bootstrap-Text für die neue Session

```text
Wir setzen VoiceSTT Server V2 fort.

Lies bitte zuerst vollständig die beigefügte Übergabe.

Wichtig:
- nur Server
- W4A/W4B/Ubuntu Qualification sind geschlossen
- kein erneuter Repo-/Architektur-Audit
- blockierend sind nur echte Correctness-, Security-, Data-Loss-, Runtime-, Deployment- oder Release-Probleme
- Distributed und Canonical haben getrennte Rollen
- Canonical bleibt bis zum finalen AP-SRV-070 Root-PASS unverändert

Aktueller Stand:
Distributed fa3c9dc887b0d3930ac0e201b93a4803c308082f
Tree a532f3b493546181c6540a137fec383ee19da4c7
Canonical c82923fc6ce889b4dfbbde1f9877b8b76481a1e8

Unmittelbar nächste Phase:
W4C Production Docker / Deployment

Bitte führe mich zuerst durch die noch offenen W4C-Entscheidungen aus der Übergabe.
Noch keinen Agenten starten und noch keinen Code ändern.
```

---

## 19. Schlussstatus

```text
SERVER V2 FUNCTIONAL ARCHITECTURE:
praktisch abgeschlossen

W4A:
CLOSED

W4B:
CLOSED

UBUNTU / HERMES:
PASS

LINUX TEST PORTABILITY:
PASS

NEXT:
W4C Production Docker / Deployment

AFTER W4C:
Qualification + Root + Release
```

**Diese Übergabe ist ab jetzt die Startgrundlage der nächsten Koordinationssession.**
