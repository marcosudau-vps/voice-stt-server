# AP-SRV-070 — W1B-C1
# Root Correction — Legacy Wake Catalog must honor per-backend health

## Ausgangslage
W1B wurde als einzelner Run-Commit veröffentlicht:

Parent:
24f3a6e0d321fe02ce3b5aef681380b500db1b81

W1B:
a7a37460a1e0997ea7856b96fb766699612a47cf

W1B TREE:
1af193bd93686018330fa0a529acf94f00a93b41

Der Root-Review bestätigt die Migration grundsätzlich, hat aber einen konkreten Backend-Health-Fehler im neuen Legacy-Adapter gefunden.

## Git / Worktree
Weiterverwenden:

P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070

Branch:
work/AP-SRV-070

Vor Mutation:
- HEAD == a7a37460a1e0997ea7856b96fb766699612a47cf
- Remote github/feat/einheitliche-triggerarchitektur-distributed == a7a37460a1e0997ea7856b96fb766699612a47cf
- Worktree clean
- Canonical == c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
- Canonical-Workspace clean

Sonst: STATUS: BLOCKED

Kein neuer Worktree. Kein Amend. Kein Force-Push.

## ROOT FINDING F1 — preferred backend can be advertised although unhealthy

### Defekt
`VoiceSTT_server/operations.py::WakeWordRegistry.openwakeword_models(framework)` filtert derzeit nur auf `entry.available` und ein vorhandenes `entry.artifact_for(preferred)`.

Die kanonische AP-SRV-060-Authority definiert `entry.available` aber als: mindestens ein Backend ist gesund.

Damit ist möglich:
- TFLite gesund
- ONNX ungesund
- entry.available == True

Dann kann `openwakeword_models("onnx")` trotzdem den ONNX-Artefaktpfad ausgeben, obwohl ONNX den realen Loadability-Probe nicht bestanden hat.

`resolve_openwakeword()` prüft den gewünschten Backend bereits korrekt gegen `entry.healthy_backends`; Listing und Resolution sind dadurch inkonsistent.

### Soll
1. `openwakeword_models(framework)` gibt einen Eintrag nur aus, wenn genau der angefragte Backend gesund ist.
2. Deklariertes Artefakt allein reicht nicht.
3. Nur TFLite gesund -> kein Eintrag bei framework="onnx".
4. Derselbe Eintrag darf bei framework="tflite" erscheinen.
5. `availableFormats` enthält nur tatsächlich gesunde Backends.
6. `paths` enthält nur tatsächlich gesunde Backendpfade.
7. `resolve_openwakeword()` und `openwakeword_models()` sind backend-health-konsistent.
8. Keine Änderung des v2-Public-Payloads oder der SRV-060-Authority, sofern nicht zwingend nötig.

Keine neue Wake-Architektur.

## RED-FIRST
Vor Implementierung einen Test gegen den aktuellen W1B-Stand schreiben/ausführen, der den Defekt beweist.

Empfohlen:
Dual-Backend-Bundle:
- ONNX-Prober schlägt deterministisch fehl
- TFLite-Prober besteht

Beweise:
- `openwakeword_models("onnx")` liefert den Eintrag NICHT — dieser Test muss auf a7a3746 RED sein.
- `openwakeword_models("tflite")` liefert ihn.
- `availableFormats` enthält nur gesunde Backends.
- `paths` enthält nur gesunde Backends.
- `resolve_openwakeword(id, "onnx")` meldet missing.
- `resolve_openwakeword(id, "tflite")` löst auf.

Nutze `tests/unit/wake_catalog_support.py`, nicht unnötig eine Fake-Authority.

## ROOT FINDING F2 — direkt betroffene aktive Doku stale
In `docs/fastapi-server.md` beschreibt die Tabelle `--openwakeword-model-paths` weiterhin classifier paths, model directory oder `models.json` path.

W1B hat Directory-/beliebigen Manifest-Scan entfernt.

Korrigiere nur diese unmittelbar betroffene Vertragsstelle auf das reale verbleibende Verhalten:
- explizite `.onnx` / `.tflite` classifier paths als Direktpfad-Override
- ansonsten Katalogauflösung über die kanonische Wake-Word-Authority
- kein Directory-Scan / kein beliebiger `models.json`-Pfad über dieses Setting

Keine W2-Doku-Reorganisation vorziehen.
Docker-/Compose-Referenzen auf `VOICESTT_OPENWAKEWORD_MODEL_ROOT` bleiben W4-Scope.

## Regressionsprüfung
Mindestens:
- neuer RED→GREEN Backend-Health-Test
- tests/unit/test_server_operations.py
- tests/unit/test_wakeword_catalog.py
- tests/unit/test_wakeword_catalog_api.py
- tests/unit/test_wakeword_root_findings_c2.py
- tests/unit/test_wakeword_root_findings_c3.py
- tests/unit/test_fastapi_server_protocol.py
- tests/unit/test_fastapi_server_multi_user.py
- tests/unit/test_wakeword_session_e2e.py

Danach möglichst vollständige Unit-Suite.

Zusätzlich:
- repo-weite Suche nach altem `OpenWakeWordCatalog` / Importpfad
- `git diff --check`
- `git status --porcelain`

W1B-Invarianten bleiben:
- genau eine kanonische Wake-Word-Authority
- kein impliziter Default
- selected-only v2
- kein Runtime-Download
- KEEP_REQUIRED S09-S13 unangetastet
- Calibration `EVIDENCE_BLOCKED / calibration pending`

## Scope
Erlaubt:
- minimale Korrektur im WakeWordRegistry
- direkt zugehörige Tests
- eine unmittelbar stale Doku-Beschreibung

Nicht erlaubt:
- W2-Reorganisation
- Packaging
- Versionssystem
- Docker / Deployment
- Release-Automation
- Client-Code
- fachlich unabhängige Wake-Lifecycle-Seams

## Commit / Distributed
Bei PASS genau EIN neuer Korrektur-Commit.

Parent:
a7a37460a1e0997ea7856b96fb766699612a47cf

Subject:
fix(wakeword): honor backend health in legacy catalog

Danach:
- SHA/TREE erfassen
- Worktree clean
- Canonical unverändert
- Remote Distributed vor Push noch a7a3746...

Distributed nur Fast-Forward:
feat/einheitliche-triggerarchitektur-distributed

Kein Force.
W1B-Originalcommit nicht verändern/amenden.

## Evidence
Unter:

P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W1B-C1\

mindestens:
- 2026-08-30_W1B_C1_CORRECTION_REPORT.md
- 2026-08-30_W1B_C1_TEST_REPORT.md
- 2026-08-30_W1B_C1_STATE.md

STATE:
- Parent a7a3746...
- C1 SHA/TREE
- RED-Nachweis
- per-backend Health-Nachweis
- geänderte Dateien
- Tests
- Distributed before/after
- Canonical unchanged
- Calibration Status
- W2 readiness

## Rückgabe
Schick mir alle Dateien aus diesem Ordner.
