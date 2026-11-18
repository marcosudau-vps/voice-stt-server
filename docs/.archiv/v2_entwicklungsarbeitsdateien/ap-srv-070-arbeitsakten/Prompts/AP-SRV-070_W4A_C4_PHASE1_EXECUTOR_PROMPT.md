# AP-SRV-070 / W4A-C4 — Phase 1 Executor Prompt
## Bestandsaufnahme / Evidence-only / keine Implementierung

Du arbeitest als **streng geführter Executor** für `AP-SRV-070 / W4A-C4`.

Du triffst **keine eigenen Architekturentscheidungen**.
Du erweiterst **keinen Scope**.
Du implementierst in dieser Phase **nichts**.

Wenn etwas nicht eindeutig vorgegeben ist, dokumentierst du den Sachverhalt und stoppst an dieser Stelle. **Nicht raten.**

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

Erwarteter HEAD / Parent:

```text
16662698997b5e32980663ccb82176508d1d23dd
```

Erwarteter Tree:

```text
9433ca78334c5906b60b1ca48f2e3ac92cb6358b
```

Erwarteter Distributed-Stand:

```text
feat/einheitliche-triggerarchitektur-distributed
= 16662698997b5e32980663ccb82176508d1d23dd
```

Canonical muss unverändert sein:

```text
feat/einheitliche-triggerarchitektur
= c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

Verbindlicher Gesamtauftrag:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\AP-SRV-070_W4A_C4_FINAL_REPRODUCIBILITY_AND_GREEN_GATE.md
```

**Diesen Gesamtauftrag vollständig lesen, aber in dieser Phase noch nicht implementieren.**

Evidence-Ordner:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4A-C4\
```

---

# 2. Phase 1 — ausschließlich Analyse und Evidence

## 2.1 Git-Gates prüfen

Prüfe und dokumentiere mindestens:

```text
git rev-parse HEAD
git rev-parse HEAD^{tree}
git status --short
git branch --show-current
```

Zusätzlich die relevanten lokalen und Remote-Refs für:

```text
feat/einheitliche-triggerarchitektur-distributed
feat/einheitliche-triggerarchitektur
```

Erwartungen:

```text
HEAD:
16662698997b5e32980663ccb82176508d1d23dd

TREE:
9433ca78334c5906b60b1ca48f2e3ac92cb6358b

Distributed:
16662698997b5e32980663ccb82176508d1d23dd

Canonical:
c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

Bei irgendeiner Abweichung:

```text
STATUS: BLOCKED
```

und **sofort stoppen**.

Keine Mutation.

---

## 2.2 Aktuellen C3-xwin-Vertrag exakt aufnehmen

Lies ausschließlich die unmittelbar relevanten aktuellen Dateien:

```text
VoiceSTT/kroko/buildinputs.py
VoiceSTT/kroko/fingerprint.py
VoiceSTT/install_kroko.py
tests/unit/test_kroko_fingerprint.py
```

Ermittle exakt:

- xwin-Version
- xwin-Binary-SHA256
- generierten xwin-Aufruf
- welche xwin-/Windows-Toolchain-Werte aktuell in `windows_toolchain_declaration()` enthalten sind
- welche davon tatsächlich den Fingerprint beeinflussen
- ob ein konkretes Microsoft Top-Level-Manifest technisch festgelegt ist
- ob eine konkrete Windows-SDK-Version technisch festgelegt ist
- ob eine konkrete CRT/MSVC-Version technisch festgelegt ist
- ob xwin derzeit implizit `latest` aus einem Microsoft-Manifest auswählen kann

**Noch nichts ändern.**

---

## 2.3 Vorhandenen C3-Builderzustand untersuchen

Ziel:

Feststellen, ob die **tatsächlich beim C3-Build verwendete Microsoft/xwin-Authority** noch aus dem vorhandenen Maschinenzustand rekonstruiert werden kann.

Untersuche ohne Änderungen:

- vorhandene Docker-Images des C3-Builders
- vorhandene Container, soweit relevant
- vorhandene xwin-Caches
- vorhandene xwin-Sysroots
- `/opt/xwin`
- `.xwin-cache`, falls vorhanden
- Manifestdateien
- xwin-Metadaten
- SDK-Metadaten
- CRT/MSVC-Metadaten
- erkennbare konkrete Windows-SDK-Version
- erkennbare konkrete CRT/MSVC-Version
- andere Dateien, die eindeutig die beim C3-Build verwendete xwin-Authority belegen

**Verboten:**

```text
kein neues xwin splat
kein Download
kein Docker-Build
kein nativer Kroko-Build
```

Wenn relevante Dateien gefunden werden:

- Pfad
- Dateigröße
- SHA-256, soweit sinnvoll
- enthaltene Versions-/Authority-Angaben

erfassen.

Wichtig:

Nicht behaupten, dass eine C3-Authority beweisbar ist, solange die konkrete Manifest-/SDK-/CRT-Identität nicht aus real vorhandenem Zustand oder vorhandener Build-Evidence belegt werden kann.

---

## 2.4 Windows-Dependency-Closure-Inventar erstellen

Verwende:

1. den vorhandenen C3-Buildlog,
2. den gepinnten Kroko-Upstream-Stand,
3. die von VoiceSTT in C3 eingeführten Buildinput-Definitionen.

Mindestens untersuchen:

```text
kaldi-native-fbank
kissfft
kaldi-decoder
kaldifst
openfst
eigen
onnxruntime
simple-sentencepiece
websocketpp
asio
cppjieba
hclust_cpp
```

Für jede Dependency ausschließlich Fakten erfassen:

| Feld | Inhalt |
|---|---|
| Dependency | Name |
| Upstream-Datei | CMake-/Script-Datei |
| Source | URL / Repo |
| Version/Tag/Commit | vorhandener Wert |
| Content-Hash | vorhandener SHA/Hash oder `NONE` |
| Technische Verifikation | z. B. `URL_HASH`, `sha256sum`, Commit-Checkout, `NONE` |
| VoiceSTT-Override vorhanden | ja/nein + Stelle |
| Beobachtung | kurze sachliche Beschreibung |

**Noch keine eigene Bewertung**, ob die Absicherung ausreichend ist.

Insbesondere nicht:

```text
keine neuen Pins
keine CMake-Patches
keine Hash-Ergänzungen
keine Refactorings
```

---

## 2.5 Artifact-Store-Lookup-Race exakt kartieren

Lies:

```text
VoiceSTT/kroko/artifacts.py
```

Dokumentiere die aktuelle Reihenfolge und Interaktion von mindestens:

```text
lookup()
_verify_slot_dir()
replaced_backups()
recover_slot()
_recover_slot_locked()
store()
```

Kartiere anschließend exakt das im C4-Auftrag beschriebene Interleaving:

```text
Writer:
final -> backup

Reader:
prüft final
=> MISS

Writer:
staging -> final
backup cleanup

Reader:
prüft backups
=> keine

Reader:
kann alten MISS zurückgeben
```

Nenne die konkreten Funktionen und Codebereiche, zwischen denen dieser Race möglich ist.

**Keine Lösung implementieren.**
**Keinen Lösungsvorschlag in den Code schreiben.**

---

## 2.6 Kalenderabhängigen Retention-Test kartieren

Finde:

```text
test_admin_replay_reports_retention_gap
```

Dokumentiere:

- Testdatei
- Testklasse
- relevante absolute Fixture-Zeitstempel
- verwendete Store-/Test-Uhr
- Retention-Fenster
- welcher Timestamp ausdrücklich ein Ereignis **innerhalb** des Retention-Fensters darstellen soll
- welcher Timestamp ein Ereignis **außerhalb** darstellen soll
- unmittelbar benachbarte Tests/Fixtures derselben kleinen Retention-Testgruppe mit vergleichbaren absoluten Zeitstempeln

Noch nichts ändern.

Insbesondere:

```text
kein Produktcode
keine Retention-Logik
keine Testdatei
```

ändern.

---

# 3. Exakt zu erzeugende Evidence-Dateien

Alle Dateien nach:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4A-C4\
```

## 3.1 `01_START_STATE.md`

Enthält:

- Datum/Zeit
- Repository
- Worktree
- Branch
- HEAD
- Tree
- Distributed
- Canonical
- `git status --short`
- verwendeter Remote für GitHub-Authority
- Ergebnis:

```text
START_GATE: PASS
```

oder:

```text
START_GATE: BLOCKED
```

---

## 3.2 `02_XWIN_C3_STATE.md`

Enthält:

- xwin-Version
- xwin-Binary-SHA256
- real generierten xwin-Aufruf
- aktuell fingerprintete xwin-/Windows-Toolchain-Eingaben
- Manifest-Status
- SDK-Status
- CRT/MSVC-Status
- Stellen im Code, an denen diese Werte entstehen
- ausschließlich Fakten
- keine Lösung

---

## 3.3 `03_EXISTING_BUILDER_STATE.md`

Enthält:

- relevante Docker-Images
- relevante Container, falls vorhanden
- untersuchte Pfade
- gefundene xwin-/Manifest-/SDK-/CRT-Artefakte
- Pfade / Größen / Hashes
- konkrete Versionen, soweit nachweisbar
- klar getrennte Aussage:

```text
C3_MANIFEST_AUTHORITY_RECONSTRUCTABLE: YES|NO|PARTIAL
C3_SDK_AUTHORITY_RECONSTRUCTABLE: YES|NO|PARTIAL
C3_CRT_AUTHORITY_RECONSTRUCTABLE: YES|NO|PARTIAL
```

Bei `YES` exakt angeben, wodurch.

Bei `PARTIAL` exakt angeben, was fehlt.

Kein Neubau.

---

## 3.4 `04_WINDOWS_DEPENDENCY_INVENTORY.md`

Enthält die vollständige Tabelle:

| Dependency | Upstream-Datei | Source | Version/Tag/Commit | Content-Hash | technische Verifikation | VoiceSTT-Override | Beobachtung |
|---|---|---|---|---|---|---|---|

Mindestens für alle in Abschnitt 2.4 genannten Dependencies.

Noch **keine** CLOSED/OPEN-Entscheidung treffen.

---

## 3.5 `05_ARTIFACT_LOOKUP_RACE_MAP.md`

Enthält:

- relevante Funktionen
- aktuelle Aufrufreihenfolge
- konkretes Reader/Writer-Interleaving
- betroffene Codebereiche
- warum ein gültiger final-Slot trotzdem als Miss zurückgegeben werden könnte
- keine Implementierung
- keine Architekturentscheidung

---

## 3.6 `06_RETENTION_FIXTURE_MAP.md`

Enthält:

- Datei
- Testname
- Testklasse
- absolute Zeitwerte
- Retention-Fenster
- verwendete Uhr
- beabsichtigte Semantik jedes relevanten Zeitwerts
- unmittelbar benachbarte verdächtige Fixtures
- keine Änderungen

---

## 3.7 `PHASE1_STATE.md`

Exakt dieses Statusschema verwenden:

```text
START_GATE: PASS|BLOCKED
XWIN_STATE_CAPTURED: YES|NO
C3_BUILDER_STATE_CAPTURED: YES|NO
DEPENDENCY_INVENTORY_COMPLETE: YES|NO
LOOKUP_RACE_MAPPED: YES|NO
RETENTION_FIXTURE_MAPPED: YES|NO

C3_MANIFEST_AUTHORITY_RECONSTRUCTABLE: YES|NO|PARTIAL
C3_SDK_AUTHORITY_RECONSTRUCTABLE: YES|NO|PARTIAL
C3_CRT_AUTHORITY_RECONSTRUCTABLE: YES|NO|PARTIAL

SOURCE_FILES_CHANGED: NO
TEST_FILES_CHANGED: NO
NATIVE_BUILD_STARTED: NO
DOCKER_BUILD_STARTED: NO
DOWNLOAD_STARTED: NO
GIT_COMMIT_CREATED: NO
GIT_PUSH_PERFORMED: NO
```

Darunter höchstens eine kurze Liste tatsächlicher Blocker oder offener Fakten.

---

# 4. Harte Stop-Regel

Nach Fertigstellung der Evidence-Dateien:

```text
STOP
```

Danach ausdrücklich:

- keine Implementierung
- keine Testsuite
- kein Commit
- kein Push
- kein Docker-Build
- kein nativer Build
- kein xwin-Download
- keine neuen Dependencies
- keine Änderungen an Source- oder Testdateien

Die Architektur- und Implementierungsentscheidung erfolgt danach extern.

---

# 5. Abschlussantwort

Antworte ausschließlich kurz mit:

```text
PHASE 1 COMPLETE

START_GATE: <PASS|BLOCKED>

Evidence:
- 01_START_STATE.md
- 02_XWIN_C3_STATE.md
- 03_EXISTING_BUILDER_STATE.md
- 04_WINDOWS_DEPENDENCY_INVENTORY.md
- 05_ARTIFACT_LOOKUP_RACE_MAP.md
- 06_RETENTION_FIXTURE_MAP.md
- PHASE1_STATE.md

Blocker:
- <keine oder kurze Liste>
```

Keine zusätzliche Implementierungsplanung anhängen.
