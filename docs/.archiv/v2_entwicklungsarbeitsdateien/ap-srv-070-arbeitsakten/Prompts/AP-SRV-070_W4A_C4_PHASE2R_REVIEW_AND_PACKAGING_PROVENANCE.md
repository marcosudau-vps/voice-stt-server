# AP-SRV-070 / W4A-C4 — Phase 2R Executor Prompt
## Externer Review-Capture + Python Packaging Tool Provenance Audit
## KEINE Source-/Teständerungen, KEIN Build, KEIN Commit, KEIN Push

Du arbeitest weiterhin als **streng geführter Executor** für `AP-SRV-070 / W4A-C4`.

Phase 2 ist implementiert und targeted grün. Vor Artifact-Requalification und Full Regression erfolgt jetzt ein externer Root-Review der **tatsächlichen uncommitted Diff** sowie ein letzter Closure-Audit der buildwirksamen Python-Packaging-Tools des Windows-Builders.

Diese Phase ist **Evidence-only**. Du änderst keinerlei Source- oder Testdateien.

---

# 1. Arbeitskontext

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

Unveränderter Parent:

```text
16662698997b5e32980663ccb82176508d1d23dd
```

Parent-Tree:

```text
9433ca78334c5906b60b1ca48f2e3ac92cb6358b
```

Distributed remote authority:

```text
github/feat/einheitliche-triggerarchitektur-distributed
= 16662698997b5e32980663ccb82176508d1d23dd
```

Canonical:

```text
feat/einheitliche-triggerarchitektur
= c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

Evidence:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4A-C4\
```

---

# 2. Start-Gate für den absichtlich dirty Phase-2-Worktree

Prüfe:

```text
git rev-parse HEAD
git rev-parse "HEAD^{tree}"
git branch --show-current
git rev-parse github/feat/einheitliche-triggerarchitektur-distributed
git rev-parse feat/einheitliche-triggerarchitektur
git status --short
```

HEAD/Tree/Refs müssen exakt den Werten aus §1 entsprechen.

Der Worktree soll jetzt **absichtlich dirty** sein.

Es sind ausschließlich Änderungen an diesen sechs Dateien erlaubt:

```text
VoiceSTT/install_kroko.py
VoiceSTT/kroko/artifacts.py
VoiceSTT/kroko/buildinputs.py
tests/unit/test_fastapi_server_multi_user.py
tests/unit/test_kroko_artifact_store.py
tests/unit/test_kroko_fingerprint.py
```

Keine weiteren tracked oder untracked Repo-Dateien.

Bei einer anderen Repo-Änderung:

```text
STATUS: BLOCKED
```

und stoppen.

---

# 3. Vollständige Phase-2-Diff als Review-Evidence exportieren

Erzeuge exakt:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4A-C4\10_PHASE2_WORKTREE.patch
```

Inhalt muss die vollständige uncommitted Diff gegen Parent sein:

```powershell
git diff --full-index --binary 16662698997b5e32980663ccb82176508d1d23dd -- `
  VoiceSTT/install_kroko.py `
  VoiceSTT/kroko/artifacts.py `
  VoiceSTT/kroko/buildinputs.py `
  tests/unit/test_fastapi_server_multi_user.py `
  tests/unit/test_kroko_artifact_store.py `
  tests/unit/test_kroko_fingerprint.py
```

Die Ausgabe **bytegetreu** in `10_PHASE2_WORKTREE.patch` schreiben.

Zusätzlich in Evidence dokumentieren:

```text
git diff --stat 16662698997b5e32980663ccb82176508d1d23dd
git diff --check
```

Keine Source-Datei anfassen.

---

# 4. Residual Audit: Python Packaging Tools sind buildwirksam

Der reale C3-Windows-Builder installierte:

```text
setuptools==75.8.2
wheel==0.45.1
delvewheel==1.10.1
pefile==2024.8.26
```

mit:

```text
pip3 install --break-system-packages --no-cache-dir --ignore-installed ...
```

Diese Tools sind buildwirksam:

- `setuptools` / `wheel` steuern Wheel-Erzeugung und Tags;
- `delvewheel` verändert das fertige Windows-Wheel;
- `pefile` wird durch `delvewheel` für PE/DLL-Arbeit verwendet;
- aktive transitive Python-Abhängigkeiten dieser Tools können ebenfalls buildwirksam sein.

Version-Pins allein sind für diesen Audit **noch nicht automatisch** als Content-Identity zu behandeln.

Du sollst jetzt ausschließlich die reale C3-Provenienz erfassen.

---

# 5. C3 Builder Image unverändert untersuchen

Verbindliches vorhandenes Image:

```text
kroko-onnx-windows-builder:latest
```

Erwartete C3 Image-ID aus Phase 1:

```text
b57c9ef6855e
```

Zuerst prüfen:

```text
docker image inspect kroko-onnx-windows-builder:latest
```

Wenn die Image-ID nicht mehr zum C3-Image gehört:

```text
C3_PACKAGING_IMAGE_AVAILABLE: NO
```

und diesen Teil als BLOCKED dokumentieren. Kein neues Builder-Image erzeugen.

Wenn vorhanden:

## 5.1 Python-/pip-Identity

Im Image erfassen:

```text
python3 --version
python3 -m pip --version
```

## 5.2 Direkte Distributionen

Für:

```text
setuptools
wheel
delvewheel
pefile
```

per `importlib.metadata` erfassen:

- Name
- Version
- Location / dist-info path
- `Requires-Dist`
- Entry points
- Anzahl der in `importlib.metadata.files()` bekannten Dateien

## 5.3 Aktive transitive Dependency-Closure

Schreibe ein kleines **temporäres Audit-Skript außerhalb des Repositories** oder führe es inline aus.

Ausgehend von den vier direkten Distributionen:

1. `Requires-Dist` lesen.
2. Environment Marker **im C3 Builder Container** auswerten.
3. Nur für dieses Builder-Environment aktive Requirements verfolgen.
4. Rekursiv deren installierte Distributionen/Versionen erfassen.
5. Standardbibliothek ignorieren.
6. Keine Dev-/Test-Extras aktivieren, die der reale pip-Aufruf nicht aktiviert hat.

Ergebnis ist die **tatsächlich aktive Python-Packaging-Dependency-Closure**.

Für jeden Eintrag:

```text
name
installed version
direct/transitive
required by
active marker
distribution path
```

Wenn z. B. `packaging` aktiv transitiv installiert/verwendet wird, muss es ausdrücklich erscheinen.

Nicht raten.

---

# 6. Kandidaten-Artefakte aus dem Package Index herunterladen — nur Audit

Dies ist ein **kleiner Evidence-Download**, kein Build.

Erzeuge einen disposable Ordner außerhalb des Repositories, z. B.:

```text
C:\Users\user\AppData\Local\Temp\w4a-c4-packaging-audit\
```

Für **jede Distribution in der aktiven Closure** soll im Linux-C3-Builder-Kontext das exakte Binary-Wheel für die installierte Version heruntergeladen werden.

Bevorzugt in einem ephemeren Container des vorhandenen C3-Builder-Images mit Bind-Mount auf den disposable Ordner.

Semantik:

```text
python3 -m pip download
  --only-binary=:all:
  --no-deps
  --dest /audit
  <name>==<installed-version>
```

Ein Paket nach dem anderen oder als vollständig exakt versionierte Liste.

Wichtig:

- keine Installation;
- kein `docker build`;
- kein Native-Build;
- keine Änderung des C3-Images;
- kein Repo-Download-Verzeichnis;
- keine persistenten venvs.

Für jedes heruntergeladene Wheel erfassen:

```text
filename
bytes
SHA-256
wheel tags
```

Wenn für eine installierte Distribution kein Binary-Wheel für den C3-Builder-Kontext verfügbar ist:

```text
BINARY_WHEEL_AVAILABLE: NO
```

dokumentieren; nicht automatisch sdist bauen.

---

# 7. C3 Installed-Content-Provenienz gegen heruntergeladene Wheels vergleichen

Ziel:

Nicht bloß beweisen, dass dieselbe Version existiert, sondern ob das C3-Image tatsächlich **inhaltlich** zu den jetzt identifizierten Wheel-Artefakten passt.

## 7.1 Vergleichsmethode

Für jedes heruntergeladene Wheel:

1. Wheel nur in disposable Audit-Ordner entpacken.
2. Die im Wheel enthaltene `.dist-info/RECORD` auswerten.
3. Für alle regulären, gehashten Wheel-Dateien, die als Python-Package-/Metadata-Dateien in `site-packages` landen:
   - relativen Zielpfad bestimmen;
   - SHA-256 der Wheel-Datei bestimmen;
   - SHA-256 der entsprechenden installierten Datei im C3-Image bestimmen;
   - vergleichen.
4. Nicht als Herkunftsbeweis verwenden:
   - `.pyc`
   - Cache-Dateien
   - `RECORD` selbst, wenn dessen eigener Hash leer ist
   - rein durch pip generierte State-Dateien wie `INSTALLER`/`REQUESTED`, sofern sie nicht Teil des Wheel-Artefakts sind.
5. Wenn das Wheel `.data`-Bereiche oder Entry-Point-Skripte enthält:
   - separat dokumentieren, wie pip sie installiert hat;
   - relevante installierte Zielinhalte soweit deterministisch vergleichbar ebenfalls vergleichen.

Der Vergleich darf mit einem disposable Python-Skript automatisiert werden.

## 7.2 Einstufung pro Distribution

Nur diese Werte:

```text
C3_INSTALLED_CONTENT_MATCHES_WHEEL: YES
C3_INSTALLED_CONTENT_MATCHES_WHEEL: NO
C3_INSTALLED_CONTENT_MATCHES_WHEEL: PARTIAL
```

`YES` nur, wenn alle für den Build relevanten und deterministisch vergleichbaren Package-Dateien übereinstimmen und keine gegenteilige Evidence existiert.

`PARTIAL` bei nicht vollständig auflösbarer Mapping-/Script-Situation.

---

# 8. Keine Source-Korrektur in dieser Phase

Auch wenn sich hier eine Restlücke bestätigt:

**nicht** sofort `buildinputs.py` oder `install_kroko.py` ändern.

Wir benötigen zuerst die exakten:

- Dependency-Namen,
- Versionen,
- Wheel-Dateinamen,
- SHA-256,
- C3-Inhaltsvergleichsdaten.

Die anschließende Korrektur wird extern exakt vorgegeben.

---

# 9. Zu erzeugende Evidence

## `10_PHASE2_WORKTREE.patch`

Vollständige uncommitted Diff gemäß §3.

## `11_PHASE2_DIFF_STATE.md`

Enthält:

```text
HEAD:
TREE:
BRANCH:
DISTRIBUTED:
CANONICAL:

EXPECTED_CHANGED_FILES:
ACTUAL_CHANGED_FILES:

UNEXPECTED_REPO_CHANGES: YES|NO
GIT_DIFF_CHECK: PASS|FAIL

PATCH_FILE:
10_PHASE2_WORKTREE.patch
```

plus `git diff --stat`.

## `12_C3_PACKAGING_TOOL_PROVENANCE.md`

Enthält:

### A. C3 Image

```text
image tag
image id
python version
pip version
```

### B. Dependency Closure

Tabelle:

| Name | Installed Version | Direct/Transitive | Required By | Active Marker/Reason | Installed Location |
|---|---|---|---|---|---|

### C. Downloaded Candidate Wheels

| Name | Version | Wheel Filename | Bytes | SHA-256 | Tags |
|---|---|---|---:|---|---|

### D. Installed-vs-Wheel Content Comparison

| Name | Compared Files | Matches | Mismatches | Unresolved | Result |
|---|---:|---:|---:|---:|---|

Für jeden `NO` oder `PARTIAL` genaue Ursache nennen.

### E. Gesamtstatus

```text
C3_PACKAGING_IMAGE_AVAILABLE: YES|NO
ACTIVE_PACKAGING_DEPENDENCY_CLOSURE_COMPLETE: YES|NO
ALL_CANDIDATE_WHEELS_IDENTIFIED: YES|NO
ALL_CANDIDATE_WHEEL_HASHES_CAPTURED: YES|NO
C3_PACKAGING_PROVENANCE_RECONSTRUCTABLE: YES|NO|PARTIAL
```

## `PHASE2R_STATE.md`

Exakt:

```text
START_GATE: PASS|BLOCKED

PHASE2_DIFF_EXPORTED: YES|NO
UNEXPECTED_REPO_CHANGES: 0|<count>
GIT_DIFF_CHECK: PASS|FAIL

C3_PACKAGING_IMAGE_AVAILABLE: YES|NO
ACTIVE_PACKAGING_DEPENDENCY_CLOSURE_COMPLETE: YES|NO
ACTIVE_PACKAGING_DEPENDENCY_COUNT: <number>

ALL_CANDIDATE_WHEELS_IDENTIFIED: YES|NO
ALL_CANDIDATE_WHEEL_HASHES_CAPTURED: YES|NO
C3_PACKAGING_PROVENANCE_RECONSTRUCTABLE: YES|NO|PARTIAL

SOURCE_FILES_CHANGED_DURING_PHASE2R: NO
TEST_FILES_CHANGED_DURING_PHASE2R: NO
DOCKER_BUILD_STARTED: NO
NATIVE_BUILD_STARTED: NO
ARTIFACT_REQUALIFICATION_STARTED: NO
FULL_REGRESSION_STARTED: NO
GIT_COMMIT_CREATED: NO
GIT_PUSH_PERFORMED: NO
```

---

# 10. Cleanup

Disposable Wheel-/Unpack-/Audit-Dateien unter:

```text
C:\Users\user\AppData\Local\Temp\w4a-c4-packaging-audit\
```

dürfen nach vollständiger Evidence-Erzeugung gelöscht werden.

Evidence-Dateien nicht löschen.

Vorhandenes C3-Builder-Image nicht löschen.

Vorhandenes Kroko-Artifact nicht verändern.

---

# 11. Harte Stop-Regel

Nach Evidence:

```text
STOP
```

Kein Source-/Test-Patch.
Kein Docker-Build.
Kein Native-Build.
Keine Artifact-Requalification.
Keine Full Regression.
Kein Commit.
Kein Push.

---

# 12. Abschlussantwort

Nur:

```text
PHASE 2R COMPLETE

START_GATE: <PASS|BLOCKED>
PHASE2_DIFF_EXPORTED: <YES|NO>
UNEXPECTED_REPO_CHANGES: <count>

ACTIVE_PACKAGING_DEPENDENCY_COUNT: <number>
ALL_CANDIDATE_WHEELS_IDENTIFIED: <YES|NO>
ALL_CANDIDATE_WHEEL_HASHES_CAPTURED: <YES|NO>
C3_PACKAGING_PROVENANCE_RECONSTRUCTABLE: <YES|NO|PARTIAL>

Evidence:
- 10_PHASE2_WORKTREE.patch
- 11_PHASE2_DIFF_STATE.md
- 12_C3_PACKAGING_TOOL_PROVENANCE.md
- PHASE2R_STATE.md

Blocker:
- <keine oder kurze Liste>

STOPPED BEFORE:
- source/test correction
- docker/native build
- artifact requalification
- full regression
- commit
- push
```
