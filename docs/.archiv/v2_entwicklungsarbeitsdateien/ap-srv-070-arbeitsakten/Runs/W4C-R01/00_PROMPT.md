# AP-SRV-070 / W4C — Public Production Docker / Deployment
## Implementation Run 01 — Sonnet 5

### Run-Metadaten

- **Projekt:** AP-SRV-070
- **Work Package:** W4C — Public Production Docker / Deployment
- **Run:** W4C-R01
- **Modell:** Anthropic Sonnet 5
- **Session:** NEUE Session
- **Repository:** `marcosudau-vps/voice-stt-server`
- **Zielbranch:** `feat/einheitliche-triggerarchitektur-distributed`
- **Verbindlicher Start-Commit:** `fa3c9dc887b0d3930ac0e201b93a4803c308082f`
- **Verbindlicher Start-Tree:** `a532f3b493546181c6540a137fec383ee19da4c7`
- **Session-Startordner:** `P:\GithubRepos\marcosudau-vps\voice-stt-server`
- **Neuer Workspace / Git-Worktree:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w4c`
- **Prompt-Quelle:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\2026-09-05_AP-SRV-070_W4C_RUN01_SONNET5.md`
- **Run-Arbeitsakte:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4C-R01`

Dieser Run implementiert und qualifiziert ausschließlich den **allgemeinen, öffentlich releasbaren Production-Docker-/Compose-Pfad** des Projekts.

Private oder betreiberspezifische Infrastruktur ist **nicht Teil von W4C**.

Insbesondere nicht Teil dieses Runs:

- Marcos VPS-/Selfhost-Struktur
- private Serverpfade
- private Domains
- Caddy-Konfiguration
- bestehende produktive Container
- private Ports
- private Model-Verzeichnisse
- private Secrets-Dateipfade
- private Release-/Rollback-Automation
- `build/vps/*` als Implementierungsziel

Falls solche Dateien im Repository historisch existieren, sind sie für diesen Run **außer Scope und nicht zu verändern**, außer eine rein öffentliche Referenz muss aufgrund einer eindeutig gebrochenen Verlinkung minimal angepasst werden.

Du führst **nicht selbst den Root Review durch** und vergibst **keinen Root PASS**.

Wenn alle Run-Gates erfüllt sind:

`READY FOR ROOT REVIEW`

---

# 1. Run-Akte und Workspace einrichten

## 1.1 Run-Akte

Lege an:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4C-R01`

mit der in Abschnitt 18 definierten Struktur.

Kopiere die Prompt-Datei byteidentisch aus:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\2026-09-05_AP-SRV-070_W4C_RUN01_SONNET5.md`

nach:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4C-R01\00_PROMPT.md`

Prüfe die Byteidentität per SHA256 und dokumentiere Quelle/Kopie in `01_RUN_CONTEXT.md`.

Die externe Run-Akte dient ausschließlich Arbeitsnachweisen, Reports und Evidence.

Keine Secrets und keine Binärartefakte hinein kopieren.

## 1.2 Remote-Stand verifizieren

Aus:

`P:\GithubRepos\marcosudau-vps\voice-stt-server`

Remote-Fetch durchführen.

`origin/feat/einheitliche-triggerarchitektur-distributed`

muss exakt auf:

`fa3c9dc887b0d3930ac0e201b93a4803c308082f`

zeigen.

Tree muss exakt sein:

`a532f3b493546181c6540a137fec383ee19da4c7`

Bei Abweichung:

**STOP — keine Implementierung beginnen.**

## 1.3 Dedizierten Worktree anlegen

Ziel:

`P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w4c`

Lokaler Arbeitsbranch z. B.:

`work/ap-srv-070-w4c-r01`

Der Worktree muss exakt vom verbindlichen Start-Commit erzeugt werden.

Falls der Pfad bereits existiert:

- nicht blind löschen;
- Identität, Git-Worktree-Zuordnung, HEAD und Cleanliness prüfen;
- nur wiederverwenden, wenn er eindeutig genau diesem Run entspricht;
- sonst STOP.

Danach dokumentieren:

- `git status --porcelain`
- `git branch --show-current`
- `git rev-parse HEAD`
- `git rev-parse HEAD^{tree}`
- `git worktree list --porcelain`

Ab dann ausschließlich im neuen Workspace implementieren.

---

# 2. Vor Änderungen: öffentliche Authorities lesen

Mindestens lesen:

- `AGENTS.md`
- gegebenenfalls spezifischere `AGENTS.md`
- `build/BUILD.md`
- `docs/.archiv/README.md`
- vorhandene AP-SRV-070-Dokumente
- `Dockerfile`
- `.dockerignore`
- `docker-compose.yml`
- `tools/compose.py`
- `setup.py`
- `MANIFEST.in`
- `VERSION`
- `VoiceSTT/_version.py`
- `VoiceSTT/install_kroko.py`
- `VoiceSTT/kroko/*`
- STT-Model-Management-Implementierung und relevante Tests
- Health-/Server-Implementierung
- Browserclient-/Static-Asset-Pfad

**Nicht als W4C-Authority verwenden oder verändern:**

`build/vps/*`

W4C erzeugt einen **allgemein nutzbaren öffentlichen Releasepfad**, keine Deploymentkonfiguration für einen einzelnen Betreiber.

---

# 3. Gesamtziel

W4C stellt aus dem bereits abgeschlossenen Server-V2-, Packaging-, Kroko-Artifact- und Model-Management-Stand einen öffentlich releasbaren Productionpfad her:

```text
VoiceSTT Source
       ↓
VoiceSTT Package/Wheel Build
       ↓
Kroko Artifact Resolve
       ↓
passendes qualifiziertes Artifact vorhanden → REUSE
Artifact fehlt → vorhandener W4A-Kroko-Build außerhalb Production-Docker-Build
       ↓
Production Docker Image Build
       ↓
voice-stt-server / voice-stt-server-pro
       ↓
portable Production Compose
       ↓
isolierter, disposabler Docker/Compose Smoke
```

Der normale Buildworkflow soll einen übergeordneten Einstiegspunkt bieten, der die Buildphasen orchestriert.

**Der Production-Docker-Build selbst kompiliert Kroko niemals nativ.**

---

# 4. Geschlossene Authorities — nicht redesignen

Nicht neu entwerfen:

- Trigger / Activation
- Commands / Timer
- Protocol v2
- Settings-Control-Plane
- Wake-Word-Architektur / Detection
- Model Registry
- STT Model Management / Discovery / Recovery / Provisioning
- Kroko Artifact Authority
- Kroko Fingerprinting
- Kroko Free/Pro Authority
- Kroko Secret Boundary
- Packaging-/Version-Authority
- Transactional Refresh / LKG
- qualifizierte Windows-/Ubuntu-Kroko-Mechanik

Änderungen dort nur bei konkret reproduzierbarem W4C-Blocker und dann minimal mit Regression + Dokumentation.

Kein opportunistisches Refactoring.

---

# 5. Fest entschiedene W4C-Verträge

## 5.1 Zielplattform

Production Target:

- Ubuntu 24.04
- Linux
- `amd64`
- CPU-only
- kein CUDA/NVIDIA
- kein ARM64

Das finale Runtime-Image basiert auf Ubuntu 24.04.

## 5.2 Free / Pro

Öffentliche Production-Produktidentitäten:

```text
voice-stt-server
voice-stt-server-pro
```

Beide enthalten denselben VoiceSTT-Softwarestand.

Unterschied:

```text
voice-stt-server
→ qualifiziertes Kroko Free Artifact

voice-stt-server-pro
→ qualifiziertes Kroko Pro Artifact
```

Free/Pro ist Build-Time Product Authority.

Ein vorhandener Kroko Runtime-Key darf niemals die Buildvariante bestimmen.

Der Pro-Key ist ausschließlich Runtime-Secret.

Gemeinsame Dockerfile-/Buildlogik bevorzugen.

## 5.3 Persistenter Runtime Root

Kanonischer Containerpfad:

`/var/lib/voicestt`

Bestehende W4B-Unterstruktur weiterverwenden, insbesondere:

```text
/var/lib/voicestt/models/stt/fasterwhisper
/var/lib/voicestt/models/stt/kroko_asr
```

## 5.4 Secrets

Öffentlicher Compose-/Runtimepfad:

- ENV
- `env_file`

Kein neuer `_FILE`-Scope in W4C.

Keine realen Secret-Dateien oder Secret-Werte ins Repo.

## 5.5 Auto-Download

Standard bleibt OFF.

Fehlende große Modelle dürfen nicht ungefragt beim Serverstart geladen werden.

Explizite autorisierte Provisionierung nach bestehender W4B-Policy muss weiterhin möglich bleiben.

---

# 6. Kanonischer Production-Build-Orchestrator

Implementiere einen klaren öffentlichen Production-Build-Einstiegspunkt.

Die konkrete Dateistruktur soll sich sinnvoll in das Repository einfügen.

`build/BUILD.md` bleibt allgemeine Build-Authority.

Mindestens:

- Free Build
- Pro Build

Eine `all`-Variante ist sinnvoll, sofern sauber.

Der Orchestrator muss mindestens:

1. Preflight ausführen.
2. exakten Git-Commit bestimmen.
3. VoiceSTT-Version bestimmen.
4. VoiceSTT-Python-Wheel reproduzierbar bauen.
5. Kroko-Variante explizit bestimmen.
6. vorhandene W4A-Fingerprint-/Artifact-Store-Authority verwenden.
7. passendes verifiziertes Kroko-Artifact wiederverwenden.
8. bei echtem Artifact-Miss den bestehenden W4A-Buildpfad orchestrieren.
9. das korrekte Linux/AMD64-Kroko-Wheel als Docker-Buildinput bereitstellen.
10. Production-Image bauen.
11. Image-Metadaten und Installation validieren.
12. nachvollziehbares Buildresultat/Manifest erzeugen.

## Plattformgrenze

Production Target ist Linux/AMD64.

Keine neue Cross-Compilation-/Fingerprint-Authority erfinden.

Kann der aktuelle Host das benötigte Linux/AMD64-Kroko-Artifact nach bestehendem Vertrag nicht erzeugen:

- vorhandenes verifiziertes Linux/AMD64-Artifact verwenden;
- oder bestehenden autorisierten Linux-Buildpfad verwenden;
- oder kontrolliert abbrechen.

Nie Kroko-Kompilierung zurück in den Production-Docker-Build verlagern.

---

# 7. Production Dockerfile

## 7.1 VoiceSTT Runtime

- kein `pip install -e`;
- kein Editable Install;
- kein Source-Checkout als Runtimebasis;
- zuvor gebautes VoiceSTT-Wheel installieren;
- Package-Assets aus installierter Distribution verwenden.

## 7.2 Kroko

Production-Docker-Build:

- kein Kroko-Builder-Stage;
- keine native Kroko-Kompilierung;
- fertiges verifiziertes Kroko-Wheel als Buildinput;
- exakt dieses Artifact installieren;
- Free/Pro-Zuordnung mit bestehender Authority validieren;
- kein Kroko-Key als Buildinput.

## 7.3 Runtime-Basis

- Ubuntu 24.04;
- Python 3.12;
- saubere venv-basierte Runtime bevorzugen;
- kein unnötiges `--break-system-packages`;
- keine unnötigen Buildtools im finalen Image;
- nur Runtime Libraries.

## 7.4 Non-root

Server als unprivilegierter Benutzer.

Real prüfen:

- `/var/lib/voicestt` schreibbar;
- Bind-Mount-Nutzung praktikabel;
- kein `chmod 777`.

## 7.5 Signal Handling

- exec-fähiger Prozesspfad;
- SIGTERM erreicht Server;
- keine Shell, die Signale verschluckt;
- `init: true` in Compose zulässig.

## 7.6 OCI / Provenance

Mindestens:

- VoiceSTT-Version
- exakter Git-Commit
- Build-Zeitpunkt
- OCI Version
- OCI Revision
- Source Repository

Keine Secrets in Labels, ARGs, ENV oder History.

---

# 8. Image-Inhalt / Modelle

Nicht ins Image:

- Faster-Whisper-Modelle
- Kroko-ASR-Modelle

Wake-Word-Produktassets aus dem Python-Package sind Teil des Produkts.

Custom Model Paths bleiben primäre Discovery-Quellen und dürfen read-only sein.

Verwalteter Store unter `/var/lib/voicestt` ist persistent und beschreibbar.

Bestehende Regeln lediglich korrekt verdrahten:

- Custom Paths zuerst
- vorhandene Target Authority
- sonst Runtime Store
- Staging im Zielbereich
- Verify
- atomarer Rename
- kein zusätzlicher permanenter Downloadcache

---

# 9. Auto-Download / Offline-Flags

Legacy-Defaults wie:

```text
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
VOICESTT_OFFLINE_MODELS=1
```

nicht blind übernehmen, falls sie explizite Provisionierung blockieren.

Ziel:

```text
normaler Start
→ kein unerwarteter großer Download

expliziter autorisierter Provisioning-Vorgang
→ Netzwerk nach bestehender Policy möglich
```

Keine neue Downloadpolicy.

---

# 10. Health vs. Readiness

Geschlossener Vertrag:

```text
Process / Control Plane alive
+
STT model missing
=
Container healthy
STT NOT_READY
```

Fehlendes Modell darf keinen Restart-Loop erzeugen.

Legacy `ready && ok` als Docker Health ist dafür nicht ausreichend.

Tests müssen unterscheiden:

- Control Plane healthy
- STT ready
- STT NOT_READY wegen Modell
- echter Server-/Healthfehler

---

# 11. Öffentliche Production Compose

Erstelle/härte den allgemeinen Composepfad so, dass er ohne betreiberspezifische Annahmen nutzbar ist.

Mindestens:

- Free/Pro eindeutig auswählbar
- Image/Build
- dokumentierbarer Port
- `init`
- Restart Policy
- Runtime Config
- optionales `env_file`
- `/var/lib/voicestt`
- persistente verwaltete Modelle
- optionale Custom Model Paths
- Healthcheck
- CPU Runtimeparameter

Keine fest verdrahteten:

- privaten Hostpfade
- privaten Domains
- privaten Netzwerke
- privaten Ports
- privaten Secretpfade
- privaten Modelpfade
- betreiberspezifischen Resource-Limits

Sinnvolle portable Defaults und dokumentierte Overrides verwenden.

---

# 12. Source-unabhängige Production Runtime

Nach Image-Build darf das Deployment keinen Git-Checkout benötigen.

Das gilt auch für den Browserclient.

Aktuelle Source-Mounts für Static Assets/nginx dürfen im Productionpfad nicht notwendig bleiben.

Löse das minimal produktionsgeeignet:

- gebautes Browserclient-Image oder
- gleichwertige image-/package-basierte Lösung.

Kein Browserclient-Redesign.

Externe Runtime-Konfiguration und persistente Betreiberverzeichnisse sind zulässige Mounts.

---

# 13. Isolierter öffentlicher Deployment-Smoke

W4C muss einen realen, aber **infrastrukturunabhängigen und disposablen** Docker/Compose-Smoke durchführen.

Er darf keine Annahmen über Marcos Serverinfrastruktur enthalten.

Smoke-Setup:

- eigenes temporäres Compose-Projekt;
- temporärer isolierter Runtime/Data Root;
- temporärer isolierter Model Store;
- freier lokaler High-Port;
- keine öffentliche Domain;
- kein Reverse Proxy;
- kein vorhandenes produktives Deployment;
- keine privaten Hostpfade;
- keine privaten Netzwerke.

Der Smoke darf auf jedem geeigneten Dockerhost durchgeführt werden, der Linux/AMD64-Container ausführen kann.

Die Evidence nennt den tatsächlich verwendeten Hosttyp/OS/Dockerstand, aber keine privaten Infrastrukturdetails, die für das öffentliche Produkt irrelevant sind.

---

# 14. Realer Deployment-Smoke — Acceptance Gates

## Build

- **W4C-G01** VoiceSTT-Wheel erfolgreich gebaut.
- **W4C-G02** Kroko-Artifact korrekt aufgelöst.
- **W4C-G03** vorhandener passender Fingerprint kann verifiziert REUSED werden.
- **W4C-G04** Free Production Image erfolgreich gebaut.
- **W4C-G05** Pro Production Image erfolgreich gebaut.
- **W4C-G06** Production Docker Build führt keinen nativen Kroko-Build aus.
- **W4C-G07** kein Editable Install.
- **W4C-G08** Runtime verwendet installierte VoiceSTT-Distribution.
- **W4C-G09** Image läuft non-root.
- **W4C-G10** OCI Version/Revision stimmen.

## Runtime

- **W4C-G11** isolierter Container startet.
- **W4C-G12** Container Health wird grün.
- **W4C-G13** Server über isolierten Testport erreichbar.
- **W4C-G14** `/ws/v2` Protocol-v2-Handshake erfolgreich.
- **W4C-G15** Model Management / Admin Control Plane erreichbar.
- **W4C-G16** fehlendes STT-Modell ergibt administrierbares NOT_READY ohne unhealthy/restart loop.
- **W4C-G17** Wake Assets aus installierter Distribution verfügbar.
- **W4C-G18** normaler Containerstart führt keinen Kroko Native Build aus.

## Persistence

- **W4C-G19** persistente Runtime-Daten geschrieben.
- **W4C-G20** Container recreated.
- **W4C-G21** Runtime-Daten bleiben erhalten.
- **W4C-G22** verwalteter Model Store bleibt erhalten.
- **W4C-G23** Container danach wieder healthy.

## Shutdown

- **W4C-G24** SIGTERM wird gesendet.
- **W4C-G25** sauberer Shutdown nachgewiesen.
- **W4C-G26** kein erzwungener Kill als normaler Shutdownpfad.

## Free/Pro / Security

- **W4C-G27** Free enthält Free Kroko Runtime.
- **W4C-G28** Pro enthält Pro Kroko Runtime.
- **W4C-G29** gleicher VoiceSTT-Produktstand.
- **W4C-G30** Kroko Runtime-Key ist kein Buildinput.
- **W4C-G31** Runtime-Key kann Free-Build nicht in Pro verwandeln.
- **W4C-G32** keine Secret-Werte in Image, Labels, History, Logs oder Evidence.
- **W4C-G33** Public Compose/Images enthalten keine betreiberspezifischen Marcos-/VPS-Abhängigkeiten.

---

# 15. Secret-/Image-Audit

Für beide Images geeignete Inspect-/History-Prüfungen.

Mindestens ausschließen:

- Kroko API Keys
- VoiceSTT API Keys
- Admin API Keys
- GitHub Tokens
- andere Secret-Werte

in:

- Image ENV
- OCI Labels
- Docker History
- Build Metadata
- committed Compose
- Build-/Smoke-Logs
- Run-Evidence

Keine Secret-Werte als Evidence speichern.

---

# 16. Tests

Gezielte W4C-Tests mindestens für:

- Build-Orchestrator Variantenselektion
- Free/Pro Mapping
- Kroko Artifact Reuse/Miss soweit unit-testbar
- kein nativer Kroko-Build im Production-Dockerpfad
- Version/Revision Propagation
- Health/Liveness
- portable Production Compose Contracts
- kein Editable Install
- keine Source-Runtime-Abhängigkeit
- Data-/Model-Root Wiring
- keine betreiberspezifischen absoluten Pfade/Netzwerke/Domains im öffentlichen Productionpfad

Danach:

```text
python -m pytest -q tests/unit
git diff --check
```

Null Testfehler.

Geschlossene Contract-Assertions nicht abschwächen.

---

# 17. Repo-Dokumentation / Archiv

Gemäß `AGENTS.md` / `docs/.archiv/README.md`:

Vor Implementierung:

- datierte W4C-Planung im bestehenden AP-SRV-070-Archiv.

Nach Umsetzung:

- datierter Soll-/Ist-Vergleich;
- materielle Abweichungen separat;
- `build/BUILD.md` aktualisieren;
- öffentliche Docker-/Compose-Dokumentation aktualisieren;
- relevante README-/Deploymenthinweise konsistent halten.

Historische Dokumente nicht rückwirkend umschreiben.

`build/vps/*` ist nicht Teil dieses Runs und bleibt unangetastet.

Terminologie klar trennen:

```text
VoiceSTT Package/Wheel Build
Kroko Native Artifact Build
Production Docker Image Build
Registry Publish
```

Registry Publish ist nicht Teil von W4C.

---

# 18. Verbindliche Evidence-Struktur

Externe Run-Akte:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4C-R01`

```text
W4C-R01\
│
├── 00_PROMPT.md
├── 01_RUN_CONTEXT.md
├── 02_IMPLEMENTATION_REPORT.md
├── 03_EVIDENCE_INDEX.md
├── 04_DEVIATIONS.md
├── 05_FINAL_REPORT.md
│
└── Evidence\
    ├── 00_Preflight\
    ├── 01_Package_Build\
    ├── 02_Kroko_Artifact\
    ├── 03_Docker_Free\
    ├── 04_Docker_Pro\
    ├── 05_Image_Security\
    ├── 06_Compose_Public\
    ├── 07_Isolated_Smoke\
    ├── 08_Persistence_Shutdown\
    ├── 09_Tests\
    └── 10_Git_Final\
```

## `01_RUN_CONTEXT.md`

Mindestens:

- Run-ID
- Modell
- Startzeit
- Session-Startordner
- Workspace
- Zielbranch
- erwarteter und tatsächlicher Start SHA/Tree
- lokaler Arbeitsbranch
- Python/Git/Docker/Compose-Version
- Host OS
- bindende W4C-Authorities
- Entscheidungen A–G in Kurzform, wobei G jetzt ausdrücklich **isolierter öffentlicher Docker-Smoke ohne private Infrastruktur** bedeutet
- Prompt SHA256 Quelle/Kopie

## `02_IMPLEMENTATION_REPORT.md`

Tabelle:

| Bereich | Datei(en) | Vorher | Änderung | Warum | Requirement/Gate |
|---|---|---|---|---|---|

Danach technische Kurzabschnitte:

- Build-Orchestrator
- Docker
- Free/Pro
- Compose/Persistenz
- Health
- Source Independence
- Tests
- bewusste Nicht-Änderungen

## `03_EVIDENCE_INDEX.md`

Für jedes Gate G01–G33:

| Gate | Status | Kurzbeweis | Evidence-Datei(en) | Command/Probe | Exit/Result |
|---|---|---|---|---|---|

Status:

- PASS
- FAIL
- BLOCKED
- N/A nur mit echter Begründung

Jeder PASS braucht konkrete Evidence.

## `04_DEVIATIONS.md`

Wenn keine:

`Keine bekannten W4C-Abweichungen.`

Sonst pro Abweichung:

- ID
- Soll
- Ist
- Ursache
- Auswirkung
- Security-/Release-Relevanz
- Entscheidung
- Follow-up
- Gate-Auswirkung

## `05_FINAL_REPORT.md`

Siehe Abschnitt 22.

---

# 19. Evidence-Dateien — allgemeines Format

Jede relevante textuelle Roh-Evidence beginnt:

```text
Evidence-ID:
Gate(s):
Timestamp UTC:
Host:
Working Directory:
Command / Probe:
Expected:
Exit Code:
Result:
```

Danach relevante vollständige Ausgabe.

Regeln:

- Exit Code dokumentieren.
- Logs nicht sinnverändernd kürzen.
- sehr lange Logs separat als `.log`/`.txt`.
- keine Secrets.
- keine Binärartefakte.
- Wheels: nur Dateiname, Pfad, Größe, SHA256.
- Images: Tag, ID/Digest, Labels.
- textuelle maschinenlesbare Evidence bevorzugen.

---

# 20. Mindestnachweise je Evidence-Ordner

## `00_Preflight`

- Remote SHA/Tree
- Worktree-Anlage
- Workspace SHA/Tree
- Clean Start
- Tool-Versionen
- Prompt Hashvergleich

## `01_Package_Build`

- Build Command
- VoiceSTT Wheel Name
- Größe
- SHA256
- Version
- wesentliche Package Assets
- kein Editable-Production-Artefakt

## `02_Kroko_Artifact`

Free und Pro getrennt:

- Variant
- Fingerprint
- Artifact Store Location
- REUSE oder BUILD
- Wheel Name
- SHA256
- Größe
- Plattform/ABI
- Verification Result
- Runtime-Key nicht Buildinput

Bei neuem Build:
- bestehender autorisierter W4A-Pfad
- Buildhost/Plattform
- Exit
- anschließende Verifikation

## `03_Docker_Free`

- exakter Build Command
- Exit
- Image Tag
- Image ID
- OCI Labels
- Runtime User/UID
- installierte VoiceSTT-Version
- installierte Kroko-Variante
- kein Editable Install
- kein Kroko Native Build im Docker-Build

## `04_Docker_Pro`

Wie Free plus Pro-Nachweis.

## `05_Image_Security`

Beide Images:

- sichere relevante `docker inspect` Felder
- History-Prüfung
- negativer Secret-Scan
- non-root
- keine großen STT-Modelle
- keine Source-Abhängigkeit
- keine unnötige Compiler-/Buildtoolchain im finalen Image soweit prüfbar

## `06_Compose_Public`

- öffentliche Production Compose Config
- Free/Pro Auswahl
- Port Override
- Data Root
- Model Store
- Custom read-only Model Path Support
- Healthcheck
- optionales `env_file`
- Browserclient source-unabhängig
- negativer Scan auf private/betreiberspezifische Marcos-/Selfhost-/Domain-/absolute Hostpfad-Annahmen

## `07_Isolated_Smoke`

- isolierter Projektname
- temporärer Testroot
- lokaler High-Port
- `compose up`
- Container Status
- Health
- HTTP Probe
- `/ws/v2` Handshake
- Model Management
- NOT_READY
- Restart Count
- Wake Asset Probe
- kein Kroko Build beim Start

## `08_Persistence_Shutdown`

- persistenter Testmarker
- Recreate
- Marker bleibt
- Model-Store-Persistenz
- Health danach
- SIGTERM/Stop mit Zeitstempeln
- Exit State
- kein forced kill als Normalpfad

## `09_Tests`

- gezielte W4C Tests
- vollständige Unit Suite
- `git diff --check`
- Counts + Exit Codes

## `10_Git_Final`

Vor Commit:
- status
- diff stat
- adversarial Diff Review

Nach Commit:
- final SHA
- Tree SHA
- Commit Message
- Clean Status

Vor Push:
- Fetch
- Remote Distributed muss noch Start-SHA sein

Push:
- genau ein Fast-Forward Run-Commit
- kein Force Push

Nach Push:
- Remote SHA
- Remote Tree
- Clean Workspace

---

# 21. Git-Governance

Distributed erhält genau einen dauerhaften finalen Run-Commit.

Keine WIP-/Debug-Commits dauerhaft auf Distributed.

Zwischenzustände nur lokal oder temporärer Dirty-Branch.

Final:

1. alle Gates ausführen;
2. adversarial Diff Review;
3. genau einen finalen Commit;
4. Remote Distributed erneut prüfen;
5. nur Fast-Forward Push;
6. kein Force Push;
7. Canonical nicht anfassen;
8. `main` nicht anfassen.

Empfohlene Commit Message:

`AP-SRV-070 W4C: production Docker and deployment`

---

# 22. Abschlussbericht

`05_FINAL_REPORT.md`:

## Status

`READY FOR ROOT REVIEW`

oder

`NOT READY FOR ROOT REVIEW`

Nie `ROOT PASS`.

## Git

- Start Commit
- Start Tree
- Final Commit
- Final Tree
- Zielbranch
- lokaler Arbeitsbranch
- Push Status
- Remote Final SHA
- Working Tree clean

## Workspace / Run

- Modell
- Workspace
- Run-Akte
- Prompt SHA256

## Implementierung

Kurze Liste der öffentlichen Produkt-/Deploymentänderungen.

## Build Evidence

Free und Pro:

- VoiceSTT Version
- VoiceSTT Wheel + SHA256
- Kroko Variant
- Kroko Fingerprint
- REUSE / BUILD
- Kroko Artifact SHA256
- Image Tag
- Image ID
- OCI Version
- OCI Revision

## Test Summary

| Test/Gate-Gruppe | Ergebnis | Evidence |
|---|---|---|

## Isolated Public Smoke

- Compose-Projektname
- temporärer Testroot
- localhost Testport
- Health vor/nach Recreate
- Protocol v2
- Model Management
- NOT_READY
- Persistence
- SIGTERM

Keine privaten Infrastrukturangaben.

## Gate Summary

- PASS count
- FAIL count
- BLOCKED count
- N/A count
- Verweis auf `03_EVIDENCE_INDEX.md`

## Abweichungen

Verweis auf `04_DEVIATIONS.md`.

---

# 23. Stop-Regel

Nicht wegen kleiner Details stoppen.

STOP wenn:

- Start SHA/Tree nicht stimmen;
- Workspace nicht sicher eingerichtet werden kann;
- geschlossene Authority gebrochen werden müsste;
- Linux/AMD64-Kroko-Artifact weder autoritativ auflösbar noch über bestehenden qualifizierten Pfad erzeugbar ist;
- Smoke nicht isoliert/disposabel möglich ist;
- Secret offengelegt werden müsste;
- externe Publikation nötig wäre;
- Remote Distributed vor Push nicht mehr Start-SHA ist.

Bei STOP:

- keine spekulative Großarchitektur;
- `NOT READY FOR ROOT REVIEW`;
- Blocker + Evidence dokumentieren.

---

# 24. Nicht Teil dieses Runs

Nicht durchführen:

- PyPI Publish
- GHCR Push
- Docker Hub Push
- GitHub Release
- Release Tag
- Canonical Update
- Merge nach `main`
- betreiberspezifische VPS-/Selfhost-Arbeiten
- Caddy-/Domain-Arbeiten
- private Deploymentmigration
- GPU
- ARM64
- Client-Neuentwicklung
- Trigger-/Protocol-/Wake-/Settings-Redesign
- W5/W6 vollständig vorwegnehmen

---

# 25. Erfolgszustand

```text
Source
→ VoiceSTT Wheel
→ autoritatives Kroko Artifact
→ Ubuntu-24.04 Production Image
→ Free / Pro Images
→ non-root Runtime
→ persistenter Data/Model Store
→ korrektes Health/NOT_READY
→ portables source-unabhängiges Production Compose
→ isolierter disposabler Docker/Compose Smoke
→ vollständige Gate-Evidence
→ genau ein sauberer Distributed-Commit
→ READY FOR ROOT REVIEW
```

W4C qualifiziert das **öffentliche Produkt**, nicht eine bestimmte Betreiberinstallation.
