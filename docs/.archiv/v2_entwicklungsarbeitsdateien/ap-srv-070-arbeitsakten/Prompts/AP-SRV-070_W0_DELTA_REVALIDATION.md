# AP-SRV-070 — W0 DELTA-REVALIDATION / SCOPE FREEZE

## Ziel
Erzeuge eine belastbare READ-ONLY Delta-Revalidation für AP-SRV-070. Die frühere 070-Discovery entstand vor dem finalen AP-SRV-060-Stand und darf nicht ungeprüft als Implementierungs- oder Löschliste verwendet werden.

## Baseline
Canonical Workspace:
P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\einheitliche-triggerarchitektur

Canonical:
feat/einheitliche-triggerarchitektur
c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
TREE de6fe364545b508a47a87ead67a01c5732477e71

Distributed:
feat/einheitliche-triggerarchitektur-distributed
1e74fec3096778d78c4f91e3916ef272c762ebd3

## Arbeitsweise
READ-ONLY gegen das Produktrepository.

Nicht:
- Produktcode ändern
- Branch/Worktree anlegen
- committen/pushen/mergen/rebasen
- reset/clean/prune
- Dateien im Produktrepo erzeugen
- AP-SRV-070 implementieren

Neue Analyseunterlagen ausschließlich unter:
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prep\W0\

## Quellen
1. Finaler Canonical-Stand AP-SRV-060.
2. Historische AP-SRV-070-Discovery unter P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prep\
3. Relevante historische Akten/Tracking-Unterlagen.
4. Aktueller Repositoryzustand.

Falls die historische Discovery nicht eindeutig auffindbar ist: STATUS: BLOCKED. Nicht aus Erinnerung rekonstruieren.

## Prüffelder

### A. Runtime / Legacy
Jeden alten Remove-/Migration-Candidate neu beweisen: Existenz, Erreichbarkeit, direkte/indirekte Caller, dynamische Registrierung, Import-Side-Effects, Tests/Doku/Packaging-Abhängigkeiten, Compatibility-/Lifecycle-Verantwortung.

Klassifikation:
CONFIRMED_REMOVE
MIGRATE_BEFORE_REMOVE
KEEP_REQUIRED
SUPERSEDED_ALREADY
NEEDS_RUNTIME_PROOF
OUT_OF_SCOPE

Besonders prüfen:
- ActivationController.finalized()
- alte Trigger-/Activation-Seams
- tote Adapter/Helper
- alte Wake-Word-Pfade/Loader
- Runtime-Downloads
- alte Config-Keys
- temporäre Compatibility-Shims

### B. Protocol v1/v2 Boundary
Prüfen und konkrete negative Tests für W1 formulieren:
- v1 bekommt keine v2-Envelopes
- v2 bekommt keine v1-Messages
- Session-ID-Welten werden nicht vermischt
- Protocol-Versionen deterministisch
- serverCommit / Server-Version / Protocol-Version eindeutig

### C. Wake Words nach SRV-060
Prüfen:
- parallele alte Detection-/Triggerpfade
- externe Assetpfade
- Runtime-Downloadannahmen
- obsolete Loader/Config
- Package-Resource-Annahmen
- verbleibende Legacyspiegel
- Dev-/Fallback-Seams

SRV-060 nicht neu designen.

### D. Product Surface / Docs
Ermitteln, was W2 wirklich überarbeiten/ordnen muss:
README, Getting Started, Installation, Quick Start, Configuration, Environment, API/Protocol v2, Sessions/Activations/Events/Errors, Settings, Wake Words, Transcription Lifecycle, Architecture, Operations/Logging/Diagnostics, Development/Testing, Deployment/Packaging/Release.

### E. Packaging
Ist-Zustand prüfen:
Package-/Version-Authority, Build-Backend, Entry Points, Dependencies, Package Resources, wheel/sdist, Wake-Word-Assets, installierte Distribution, Build-/Release-Automation.

W3-Hard-Gates formulieren für:
models.json, ONNX/TFLite-Classifier, Pipeline-/Featureassets, VAD-Asset, Catalog aus installiertem Package, GET /api/v2/wake-words, Wake-Word-Initialisierung, keine Runtime-Downloads.

### F. Docker / Deployment
Ist-Zustand prüfen:
Dockerfile(s), Compose, Entry Point, Healthcheck, Shutdown, User/root, Source-Checkout vs installierte Distribution, Secrets, Dev-/Test-Dateien, OCI-Metadaten, Version/Commit-Traceability, Wake-Word-Assets.

### G. Release Candidate / Publication
Nur planen, nicht veröffentlichen:
Full Regression, Package Build, Installed-Package Smoke, Container Smoke, Version Freeze, Artefakt-Hashes, PyPI, frischer Install, Registry Push, Fresh Pull Smoke, GitHub Release, Tracking/Archive Closure.

## Ergebnisdateien
Unter:
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prep\W0\

Erzeuge mindestens:
2026-08-29_W0_DELTA_REVALIDATION.md
2026-08-29_W0_SCOPE_MATRIX.md
2026-08-29_W0_EXECUTION_BACKLOG.md

SCOPE_MATRIX mit:
ID | Bereich | Klassifikation | Dateien/Symbole | Begründung | Abhängigkeiten | Risiko | Zielblock W1-W6

EXECUTION_BACKLOG nach W1-W6. Je Aufgabe:
ID | Scope | Dateien/Symbole | Akzeptanzkriterium | Tests/Evidence | Abhängigkeiten | Priorität P0/P1/P2

## Rückgabe
STATUS
BASELINE
HISTORICAL DISCOVERY
DELTA
BACKLOG COUNTS W1-W6
CRITICAL DECISIONS
FILES
NEXT — W1 planbar JA/NEIN

Kein Produktcode wurde verändert.
