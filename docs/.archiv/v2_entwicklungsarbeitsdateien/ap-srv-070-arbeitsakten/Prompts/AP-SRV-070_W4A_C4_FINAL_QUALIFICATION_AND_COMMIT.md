# AP-SRV-070 / W4A-C4 — Final Qualification + Commit/Distributed-FF
## Vorhandenes C3-Artifact requalifizieren, Full Regression grün, genau ein Run-Commit

Du arbeitest weiterhin als **streng geführter Executor** für `AP-SRV-070 / W4A-C4`.

Die Implementierungsarbeit aus Phase 2 ist abgeschlossen und targeted grün.
Phase 2R hat die reale C3-Provenienz zusätzlich bestätigt.

**Ab jetzt keine neue Dependency-Jagd, keine weitere allgemeine Reproduzierbarkeits-Härtung und keine Refactorings.**

Ziel dieser Phase ist ausschließlich:

1. aktuellen C4-Stand unverändert qualifizieren,
2. vorhandenes reales C3-Wheel ohne Native-Rebuild unter dem aktuellen C4-Fingerprint requalifizieren, sofern der vorhandene Provenienzbeweis vollständig hält,
3. echten REUSE nachweisen,
4. install/import/runtime proof durchführen,
5. Full Regression mit 0 Failures,
6. genau einen Run-Commit erzeugen,
7. Distributed ausschließlich per Fast-Forward aktualisieren.

W4B ist weiterhin verboten.

---

# 1. Arbeitsumgebung

Repository:

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server
```

Worktree:

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070
```

Branch:

```text
work/AP-SRV-070
```

Verbindlicher Parent / C3:

```text
16662698997b5e32980663ccb82176508d1d23dd
```

Parent-Tree:

```text
9433ca78334c5906b60b1ca48f2e3ac92cb6358b
```

Remote-Distributed vor diesem Run:

```text
github/feat/einheitliche-triggerarchitektur-distributed
= 16662698997b5e32980663ccb82176508d1d23dd
```

Canonical bleibt unverändert:

```text
feat/einheitliche-triggerarchitektur
= c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

Gesamtauftrag:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\AP-SRV-070_W4A_C4_FINAL_REPRODUCIBILITY_AND_GREEN_GATE.md
```

Bestehende Evidence:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4A-C4\
```

Neue Qualification-Evidence ausschließlich nach:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4A-C4\Qualification\
```

Ordner bei Bedarf anlegen.

---

# 2. Start-Gate

Vor jeder weiteren Aktion:

```text
git rev-parse HEAD
git rev-parse "HEAD^{tree}"
git branch --show-current
git rev-parse github/feat/einheitliche-triggerarchitektur-distributed
git rev-parse feat/einheitliche-triggerarchitektur
git status --short
```

Erwartung:

```text
HEAD:
16662698997b5e32980663ccb82176508d1d23dd

TREE:
9433ca78334c5906b60b1ca48f2e3ac92cb6358b

BRANCH:
work/AP-SRV-070

REMOTE DISTRIBUTED:
16662698997b5e32980663ccb82176508d1d23dd

CANONICAL:
c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

Der Worktree ist absichtlich dirty.

Es dürfen ausschließlich diese sechs Repo-Dateien geändert sein:

```text
VoiceSTT/install_kroko.py
VoiceSTT/kroko/artifacts.py
VoiceSTT/kroko/buildinputs.py
tests/unit/test_fastapi_server_multi_user.py
tests/unit/test_kroko_artifact_store.py
tests/unit/test_kroko_fingerprint.py
```

Keine weiteren tracked/untracked Repo-Dateien.

Bei Abweichung:

```text
STATUS: BLOCKED
```

und stoppen.

---

# 3. Keine weitere Source-Härtung

Der aktuelle Phase-2-Stand ist die zu qualifizierende Implementierung.

Insbesondere jetzt NICHT:

- Packaging-Wheel-SHAs zusätzlich in Source pinnen,
- weitere Downloads inventarisieren,
- neue Buildinputs ergänzen,
- neue Architektur einführen,
- neue allgemeine Reproducibility-Härtung,
- Refactorings,
- W4B beginnen.

Wenn ein Qualification-Gate objektiv fehlschlägt:

```text
STATUS: BLOCKED
```

Fehler + Evidence dokumentieren und stoppen.

Nicht eigenmächtig einen neuen Korrektur-Scope eröffnen.

---

# 4. Verbindliche C3-Artifact-Identity

Das vorhandene reale C3-Free-Artifact:

```text
C3 fingerprint:
b2483a5a5c488f59

Filename:
kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl

SHA-256:
cdaa28193366c21d21b6f59e73cd0733fd59ba3eba6a471d540ba11a34f48f38

Bytes:
12549999
```

Persistenter Store:

```text
C:\Users\user\AppData\Local\VoiceSTT\kroko-artifacts
```

Erwarteter alter C3-Slot:

```text
C:\Users\user\AppData\Local\VoiceSTT\kroko-artifacts\free\b2483a5a5c488f59\
```

Den C3-Slot **nicht löschen, nicht überschreiben, nicht verschieben**.

---

# 5. C3-Provenienz vor Requalification bestätigen

Nutze die bereits vorhandene Evidence aus Phase 1/2R.

Für Requalification müssen mindestens weiterhin exakt belegt sein:

```text
Kroko upstream revision:
8657e655192623b98d7708e742a72987f953d3a2

xwin:
0.6.5
SHA-256 9fd53950b064d067f42428a69453b927656cae68dbd7f8d3f86dcb81c80dd22d

Channel manifest:
manifest_17.json
Bytes 91833
SHA-256 4c81e902fb7fe2acea779b828e6dc548fe0bbb693df50eda0224263c16686bdd

Package manifest:
pkg_manifest_bd98dd01efa4195cb1c11030da63b9e4a3bcec7bc406799a9db80339d6dabd79.vsman
Bytes 17955171
SHA-256 3891c3018a07338b3880cbb28088bb22ef7762eb9206523655b2e3972b9d527e

Windows SDK:
10.0.26100

CRT:
14.44.17.14
```

Zusätzlicher Phase-2R-Proof:

```text
setuptools 75.8.2: 460/460 files match
wheel 0.45.1:       36/36 files match
delvewheel 1.10.1:  11/11 files match
pefile 2024.8.26:   10/10 files match
```

Wenn diese C3-Provenienz nicht mehr aus Evidence/Builderzustand nachvollziehbar ist:

```text
REQUALIFICATION_PROVENANCE: BLOCKED
```

und stoppen.

**Kein Native-Build als automatischer Fallback in diesem Run.**

---

# 6. Aktuellen C4-Fingerprint bestimmen

Mit aktuellem uncommitted C4-Code den Free-Windows-Fingerprint und die vollständige Toolchain-Authority bestimmen.

Verwende die vorhandene CLI/API des Projekts, z. B.:

```text
python VoiceSTT\install_kroko.py --print-fingerprint --variant free
```

und:

```text
python VoiceSTT\install_kroko.py --describe-artifact --variant free
```

bzw. exakt die vorhandene korrekte CLI-Syntax.

Erfassen:

```text
C4_WINDOWS_FREE_FINGERPRINT
C4_WINDOWS_TOOLCHAIN_AUTHORITY
PATCH_SET_REVISION
BUILDER_REVISION
```

Vor Requalification soll der aktuelle C4-Slot erwartungsgemäß noch fehlen.

Falls bereits ein aktuelles gültiges C4-Artifact vorhanden ist:
- nichts löschen;
- dessen SHA/Bytes/Metadata erfassen;
- nur weiterarbeiten, wenn es byte-identisch zum verbindlichen C3-Artifact ist;
- sonst `STATUS: BLOCKED`.

---

# 7. Vorhandenes C3-Wheel ohne Native-Build requalifizieren

Requalification ist erlaubt, weil die neu deklarierten C4-Toolchain-Eingaben nach Phase-1-Evidence exakt den realen C3-Build-Eingaben entsprechen.

Vor Requalification das alte Wheel erneut prüfen:

```text
Filename exakt
SHA-256 exakt
Bytes exakt
Wheel tag cp312-cp312-win_amd64
Variant free
```

Dann das **identische Wheel** mit den aktuellen C4-Fingerprint-Inputs in einen neuen C4-Slot des persistenten Stores aufnehmen.

Bevorzugt die vorhandene Artifact-Store-API verwenden:

```text
KrokoArtifactStore.store(...)
```

mit:

```text
wheel_path = altes reales C3-Wheel
fingerprint = aktueller C4-Fingerprint
inputs = aktuelles C4-Fingerprint-Dokument
variant = free
```

Keine manuellen Metadaten erfinden.

Nicht den alten C3-Slot umbenennen.

Nicht dessen `artifact.json` verändern.

Erwartung:

```text
alter C3-Slot bleibt vorhanden
+
neuer C4-Slot enthält dieselben Wheel-Bytes
+
neue Metadata beschreibt aktuellen C4-Fingerprint
```

Nach Store:

- SHA erneut prüfen,
- Bytes erneut prüfen,
- Metadata vollständig gegen aktuellen Fingerprint/Inputs prüfen.

---

# 8. Echten normalen REUSE-Pfad beweisen

Danach einen normalen Build-Aufruf ausführen, der bei vorhandenem validem C4-Artifact **nur reusen** darf.

Sinngemäß:

```text
python VoiceSTT\install_kroko.py --build --skip-install --variant free --artifact-store "C:\Users\user\AppData\Local\VoiceSTT\kroko-artifacts"
```

Exakte bestehende CLI-Syntax verwenden.

Vorher:

```text
docker ps -a
docker images
```

relevanten Zustand erfassen.

Nachher erneut.

Erwartung:

```text
Reusing verified Kroko artifact
```

und:

```text
NATIVE_BUILD_INVOKED: NO
DOCKER_BUILD_INVOKED: NO
NEW_BUILD_CONTAINER_CREATED: NO
```

Der Lauf soll schnell sein.

Wenn der normale Pfad trotzdem einen Build starten will:

```text
STATUS: BLOCKED
```

Build abbrechen, Evidence sichern, stoppen.

---

# 9. Disposable Install / Import / Variant Proof

Erzeuge eine disposable venv **außerhalb des Worktrees**, z. B.:

```text
C:\Users\user\AppData\Local\Temp\w4a-c4-qualification-venv
```

Keine persistente neue Projekt-venv.

Darin:

1. das requalifizierte C4-Wheel installieren;
2. `import kroko_onnx` erfolgreich;
3. vorhandenen Runtime-Variant-Check ausführen;
4. Free-Erwartung muss positiv sein;
5. Pro-Erwartung muss negativ sein.

Erwartung:

```text
IMPORT: PASS
VERIFY_FREE: PASS
VERIFY_PRO_AS_FREE_WHEEL: FAIL_AS_EXPECTED
```

Danach disposable venv löschen.

---

# 10. C4 Focused Gate erneut

Vor Full Regression mindestens:

```text
python -m pytest -q tests/unit/test_kroko_fingerprint.py
python -m pytest -q tests/unit/test_kroko_artifact_store.py
python -m pytest -q tests/unit/test_fastapi_server_multi_user.py -k "retention_gap or retention"
```

und die gesamte Kroko-W4A-Gruppe:

```text
python -m pytest -q \
  tests/unit/test_kroko_fingerprint.py \
  tests/unit/test_kroko_artifact_store.py \
  tests/unit/test_kroko_onnx_engine.py \
  tests/unit/test_kroko_model_authority.py \
  tests/unit/test_install_kroko_cpu.py
```

Unter PowerShell Syntax entsprechend korrekt anpassen.

Eigenen `--basetemp` außerhalb des Worktrees verwenden, falls nötig.

Alle Gates müssen grün sein.

---

# 11. Full Regression — 0 Failures zwingend

Danach vollständige Server-Unit-Regression:

```text
python -m pytest -q tests/unit
```

mit geeignetem `--basetemp`, falls nötig.

Harter Gate:

```text
FAILED: 0
```

Skips nur, wenn bereits erwartbar/erklärt.

Der bisher kalenderabhängige:

```text
test_admin_replay_reports_retention_gap
```

muss jetzt grün sein.

Bei irgendeinem Failure:

```text
STATUS: BLOCKED
```

Keine Source-Reparatur in diesem Run.
Evidence sichern.
Stoppen.

---

# 12. Finaler Hygiene-/Scope-Gate

Prüfe:

```text
git diff --check
git status --short
git diff --stat 16662698997b5e32980663ccb82176508d1d23dd
```

Es dürfen weiterhin ausschließlich die sechs autorisierten Repo-Dateien geändert sein.

Keine:

- temporären Dateien,
- Evidence,
- Wheels,
- Logs,
- venvs,
- Build-Verzeichnisse

im Repo.

Zusätzlich den finalen Diff auf offensichtliche Secrets prüfen:

```text
API keys
tokens
passwords
private keys
license keys
```

Öffentliche Hashes/URLs sind keine Secrets.

---

# 13. Finaler Commit

Nur wenn **alle** vorigen Gates erfüllt sind.

Verbindliche Implementierungsregel:

**Wenn alle im Prompt definierten Implementierungs-, Scope- und Test-Gates erfüllt sind, genau einen Run-Commit erzeugen und Distributed ausschließlich per Fast-Forward aktualisieren.**

Commit-Parent muss exakt sein:

```text
16662698997b5e32980663ccb82176508d1d23dd
```

Empfohlener Commit-Subject:

```text
AP-SRV-070 W4A-C4: close reproducibility and qualification
```

Nach Commit prüfen:

```text
git rev-parse HEAD
git rev-parse "HEAD^{tree}"
git rev-parse HEAD^
git status --short
```

Erwartung:

```text
HEAD^ = 16662698997b5e32980663ccb82176508d1d23dd
status clean
```

Exakt ein neuer Commit.

Kein Amend.
Kein Rebase.
Kein Squash.
Kein Force-Push.

---

# 14. Distributed ausschließlich Fast-Forward

Vor Push Remote erneut lesen:

```text
git fetch github
git rev-parse github/feat/einheitliche-triggerarchitektur-distributed
```

Muss weiterhin exakt C3 sein:

```text
16662698997b5e32980663ccb82176508d1d23dd
```

Dann beweisen:

```text
git merge-base --is-ancestor \
  github/feat/einheitliche-triggerarchitektur-distributed \
  HEAD
```

Exit 0.

Dann ausschließlich Fast-Forward-Push:

```text
git push github HEAD:feat/einheitliche-triggerarchitektur-distributed
```

Danach verifizieren:

```text
github/feat/einheitliche-triggerarchitektur-distributed
= neuer C4-Commit
```

Canonical **nicht** verändern.

Canonical muss weiterhin:

```text
c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

sein.

---

# 15. Evidence

Ausschließlich:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4A-C4\Qualification\
```

Erzeuge mindestens:

## `17_REQUALIFICATION_PROOF.md`

- C3 Wheel Identity
- C4 Fingerprint
- C4 Toolchain Authority
- Provenienz-Mapping C3 → C4
- alter C3-Slot erhalten
- neuer C4-Slot
- SHA/Bytes vorher/nachher
- `REQUALIFICATION_PROVENANCE: PASS`

## `18_REUSE_AND_RUNTIME_PROOF.md`

- normaler CLI-REUSE-Command
- Laufzeit
- kein Docker-/Native-Build
- disposable venv
- Import
- Free positiv
- Pro negativ

## `19_FINAL_TEST_REPORT.md`

- Focused Tests
- Kroko-W4A-Gruppe
- Full Regression
- exakte Counts
- 0 Failures
- `git diff --check`

## `20_FINAL_GIT_AND_SCOPE.md`

- Parent
- neuer Commit
- Tree
- exakt sechs geänderte Dateien
- Secret Scan
- Distributed vorher/nachher
- Fast-Forward-Proof
- Canonical unverändert

## `W4A_C4_STATE.md`

Exakt:

```text
START_GATE: PASS|BLOCKED

REQUALIFICATION_PROVENANCE: PASS|BLOCKED
C3_ARTIFACT_SHA256: cdaa28193366c21d21b6f59e73cd0733fd59ba3eba6a471d540ba11a34f48f38
C3_ARTIFACT_BYTES: 12549999

C4_WINDOWS_FREE_FINGERPRINT: <value>
C4_WINDOWS_TOOLCHAIN_AUTHORITY: <value>

C4_ARTIFACT_REQUALIFIED: YES|NO
C4_ARTIFACT_SHA256: <value>
C4_ARTIFACT_BYTES: <value>

NORMAL_REUSE: PASS|FAIL
NATIVE_BUILD_INVOKED: NO
DOCKER_BUILD_INVOKED: NO

DISPOSABLE_INSTALL: PASS|FAIL
IMPORT_KROKO_ONNX: PASS|FAIL
FREE_VARIANT_VERIFY: PASS|FAIL
PRO_NEGATIVE_VERIFY: PASS|FAIL

FOCUSED_TESTS: PASS|FAIL
KROKO_W4A_TEST_GROUP: PASS|FAIL
FULL_REGRESSION: PASS|FAIL
FULL_REGRESSION_FAILURES: 0|<count>

GIT_DIFF_CHECK: PASS|FAIL
SECRET_SCAN: PASS|FAIL
SCOPE_GATE: PASS|FAIL

RUN_COMMIT_CREATED: YES|NO
RUN_COMMIT_SHA: <sha>
RUN_TREE_SHA: <sha>
RUN_PARENT_SHA: 16662698997b5e32980663ccb82176508d1d23dd

DISTRIBUTED_FAST_FORWARD: PASS|FAIL
DISTRIBUTED_SHA: <sha>
CANONICAL_UNCHANGED: YES|NO
CANONICAL_SHA: c82923fc6ce889b4dfbbde1f9877b8b76481a1e8

W4B_STARTED: NO
```

---

# 16. Stop-Regel

Nach erfolgreichem Commit + Distributed-FF:

```text
STOP
```

Nicht:

- Canonical aktualisieren,
- W4B beginnen,
- Tag erzeugen,
- Release veröffentlichen,
- weitere Hardening-Runde starten.

Das ist noch kein Root-PASS; die abschließende Bewertung erfolgt anschließend separat.

---

# 17. Abschlussantwort

Nur:

```text
W4A-C4 QUALIFICATION COMPLETE

C4_WINDOWS_FREE_FINGERPRINT: <value>
C4_WINDOWS_TOOLCHAIN_AUTHORITY: <value>

ARTIFACT:
- filename: <filename>
- sha256: <sha>
- bytes: <bytes>
- store: <path>

REQUALIFICATION: <PASS|BLOCKED>
NORMAL_REUSE: <PASS|FAIL>
NATIVE_BUILD_INVOKED: NO
DOCKER_BUILD_INVOKED: NO

FOCUSED_TESTS: <PASS|FAIL>
KROKO_W4A_TEST_GROUP: <PASS|FAIL>
FULL_REGRESSION: <PASS|FAIL>
FULL_REGRESSION_FAILURES: <count>

COMMIT:
- sha: <sha>
- tree: <sha>
- parent: 16662698997b5e32980663ccb82176508d1d23dd

DISTRIBUTED_FAST_FORWARD: <PASS|FAIL>
DISTRIBUTED_SHA: <sha>
CANONICAL_UNCHANGED: <YES|NO>

Evidence:
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4A-C4\Qualification\

Blocker:
- <keine oder kurze Liste>

STOPPED BEFORE:
- canonicalization
- W4B
- release
```
