# AP-SRV-070 / W4AB-C1 — EMERGENCY FINALIZATION

## Ziel

Den bereits fast fertig implementierten W4AB-C1-WIP **ohne erneuten Projekt-Audit** sauber fertigstellen.

Priorität:
1. keine harten Correctness-/Security-/Deployment-/Release-Fehler übersehen,
2. vorhandenen WIP retten,
3. genau einen finalen Korrekturcommit auf dem vorgeschriebenen Parent erzeugen,
4. Distributed per Fast-Forward aktualisieren,
5. minimale belastbare Abschlussdokumentation erzeugen.

**Keine neue Architekturarbeit. Keine weitere theoretische Härtungsrunde.**

---

## 1. Verbindliche Git-Fakten

Repository/Worktree:

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070
```

Verbindlicher Parent / aktueller Distributed-Stand:

```text
319ce3f29db302795beb767be910fe1aeb8609d6
```

Canonical:

```text
c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

WIP-Handoff-Branch:

```text
handoff/AP-SRV-070-W4AB-C1-dirty-20260901-01a05c77
```

Verbindlicher WIP-Handoff-Commit:

```text
1ef33033453219ce9e56b2ae290405efdec6052d
```

Dieser WIP-Commit hat direkt den richtigen Parent:

```text
319ce3f29db302795beb767be910fe1aeb8609d6
```

Der WIP-Commit ist **nur Transport/Handoff**, nicht der finale Run-Commit.

Verbindlicher Gesamtauftrag:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\AP-SRV-070_W4AB_C1_COMBINED_ROOT_CORRECTION_FINAL.md
```

---

## 2. Start: WIP sicher als uncommitted Final-Arbeitsstand übernehmen

Zuerst:

```powershell
git fetch github
git rev-parse github/feat/einheitliche-triggerarchitektur-distributed
git rev-parse github/feat/einheitliche-triggerarchitektur
git rev-parse github/handoff/AP-SRV-070-W4AB-C1-dirty-20260901-01a05c77
```

Erwartung:

```text
Distributed = 319ce3f29db302795beb767be910fe1aeb8609d6
Canonical   = c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
WIP         = 1ef33033453219ce9e56b2ae290405efdec6052d
```

Wenn das stimmt, einen neuen Final-Branch direkt vom Parent anlegen:

```powershell
git switch -c work/AP-SRV-070-W4AB-C1-final 319ce3f29db302795beb767be910fe1aeb8609d6
git restore --source github/handoff/AP-SRV-070-W4AB-C1-dirty-20260901-01a05c77 --worktree -- .
git status --short
```

Falls der Branchname schon lokal existiert, einen eindeutig neuen Namen verwenden, aber weiterhin direkt vom Parent starten.

Kein Rebase, Amend, Cherry-Pick oder Merge des WIP-Commits.

---

## 3. Vertrauensbasis des WIP

Der WIP enthält laut Session-Handoff bereits die Implementierung für A–J:

```text
A Linux variant tagging
B Linux OpenSSL/toolchain fingerprint
C Free+Pro coexistence
D Retention/GC
E Key != license/runtime authority
F deterministic runtime variant
G resolved-engine options
H secret boundary
I refresh semantics
J cross-platform wheel fixtures
```

Bereits erinnerte/grüne Teilresultate:

```text
Fingerprint + Artifact Store + Linux Installer:
169 passed, 86 subtests passed

Kroko Model Authority + Kroko Engine + STT Model Management:
100 passed, 1 skipped, 32 subtests passed

Scheduler/ASR integration:
8 passed, 1 skipped

central event secret test:
1 passed

compileall:
exit 0
```

**Diese bereits geprüften Bereiche NICHT erneut von Grund auf auditieren.**

Nur die tatsächliche WIP-Diff kurz gegen A–J plausibilisieren und nach offensichtlichen harten Fehlern suchen.

Review-Regel:

Ein Finding blockiert nur, wenn daraus ein realistischer

```text
Correctness
Security/Secret leak
Data-loss
Deployment
Runtime
Release
```

Fehler entstehen kann.

Rein theoretisches Hardening oder „könnte noch schöner reproduzierbar sein“ ist **kein Blocker** und gehört nicht mehr in diesen Lauf.

---

## 4. Minimaler Code-Review

Nur die WIP-Diff und ihre unmittelbar betroffenen Callgraphs ansehen.

Besonders kurz bestätigen:

### A/B
- Linux-Wheel wird wirklich intern + im Dateinamen `1free`/`1pro` getaggt.
- RECORD bleibt konsistent.
- Linux-OpenSSL-Authority geht in den Linux-Fingerprint.
- Windows-Fingerprint wird durch Linux-only-Änderungen nicht unnötig geändert.

### C/D
- Free/Pro bleiben getrennte Store-Namespaces.
- Retention löscht nie aktuellen Slot oder mindestens neuestes verifiziertes LKG.
- keine Löschung über Store-Root hinaus.

### E/F
- Key entscheidet niemals Free/Pro.
- Default Runtime-Variant = `free`.
- `pro` nur explizit.

### G
- Probe/Worker/Recovery/Switch erhalten Options der **resolved Engine**, nicht der ursprünglich konfigurierten falschen Engine.

### H
- Kroko-Credentials werden aus öffentlichen/persistenten Projektionen entfernt/redigiert.
- Exceptiontext redigiert Secrets.

### I
- PATCH persistiert Model-Intent, startet aber keinen großen Download.
- Pending/refreshRequired wird gesetzt.
- expliziter Refresh übernimmt Intent transaktional und behält bei Fehler LKG/alten resolved state.

### J
- Wheel-Testfixtures sind target-aware; Windows/Linux bleiben symmetrisch strikt.

Wenn diese Punkte im vorhandenen Code plausibel umgesetzt sind: **weiter**, nicht weiterforschen.

---

## 5. Teststrategie — nur noch das Final-Gate

Keine erneuten langen Einzelsuiten, solange die Full Unit Regression grün ist.

Zuerst genau **einen** vollständigen seriellen Lauf:

```powershell
python -m pytest -q --basetemp="$env:LOCALAPPDATA\Temp\w4ab-c1-final" tests/unit
```

Keine parallelen pytest-Prozesse.

### Bekannter Windows-Host-Hänger

Falls der Lauf reproduzierbar ausschließlich in:

```text
platform.py -> _wmi_query
```

beim Import von torch/onnxruntime hängt, darf für **den Testprozess בלבד** die bereits dokumentierte Host-Umgehung verwendet werden:

```python
platform.machine = lambda: "AMD64"
platform.system = lambda: "Windows"
```

und anschließend `pytest.main(...)` aufgerufen werden.

Keine Produkt-/Testdatei dafür ändern.

### Ergebnis

- `0 failed`
- `0 errors`

Wenn ein echter Produktfehler auftaucht:
- nur beheben, wenn er klar A–J betrifft;
- keine neue Architektur öffnen;
- danach nur die betroffene Suite + Full Unit erneut.

Wenn nur ein klarer fremder/environmentaler Fehler übrig bleibt und A–J nicht betrifft:
- dokumentieren;
- nicht in fremden Scope refactoren.

Danach:

```powershell
python -m compileall -q VoiceSTT VoiceSTT_server api_fastapi_server tests/unit
git diff --check
```

---

## 6. Minimaler Security-/Scope-Check

Nur final prüfen:

```text
keine echten API keys
keine Tokens
keine Passwörter
keine Private Keys
keine Kroko Runtime-Keys
keine Wheels
keine Modelblobs
keine venv
keine Buildcaches
keine .part-Dateien
keine pytest-Tempdaten
```

im finalen Repo-Diff.

Scope bleibt W4AB-C1.

W4C nicht beginnen.

---

## 7. Abschlussdokumentation — exakt vier kleine Dateien

Erzeuge außerhalb des Repositories:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4AB-C1\Final\
```

### `01_W4AB_C1_REQUIREMENT_MATRIX.md`

Kurze Tabelle:

```text
A Linux variant tagging               IMPLEMENTED / TESTED / PASS
B Linux OpenSSL/toolchain fingerprint IMPLEMENTED / TESTED / PASS
C Free+Pro coexistence                IMPLEMENTED / TESTED / PASS
D Retention/GC                        IMPLEMENTED / TESTED / PASS
E Key != license/runtime authority    IMPLEMENTED / TESTED / PASS
F deterministic runtime variant       IMPLEMENTED / TESTED / PASS
G resolved-engine options             IMPLEMENTED / TESTED / PASS
H secret boundary                     IMPLEMENTED / TESTED / PASS
I refresh semantics                   IMPLEMENTED / TESTED / PASS
J cross-platform wheel fixtures       IMPLEMENTED / TESTED / PASS
```

Je Punkt höchstens 2–4 Sätze mit Datei/Test.

### `02_W4AB_C1_FINAL_TESTS.md`

Nur:
- Full Unit Command + Counts
- ggf. transparenter WMI-Workaround
- compileall
- diff-check
- Secret-/Scope-Check

Keine riesigen Rohlogs.

### `03_HERMES_UBUNTU_REQUALIFICATION.md`

Exakte Befehle für den späteren Ubuntu/Hermes-Lauf auf **dem finalen Commit**:

- Checkout exact SHA
- Linux Development Dependencies
- Fingerprint
- genau ein nativer Free-Build
- `1free` Filename + internes `Build: 1free`
- Store lookup
- zweiter Aufruf = REUSE
- disposable venv install/import
- Free positiv / Pro negativ
- kleiner Kroko/VoiceSTT-Smoke
- relevante Linux-Tests
- Hygiene

Nicht selbst auf Hermes ausführen.

Status:

```text
HERMES_REQUALIFICATION_REQUIRED: YES
```

### `W4AB_C1_FINAL_STATE.md`

Enthält:

```text
START_GATE:
CORRECTION_RESULT:

PARENT_SHA:
COMMIT_SHA:
TREE_SHA:
DISTRIBUTED_SHA:
CANONICAL_SHA:

A_J_MATRIX: PASS|FAIL
FULL_UNIT_REGRESSION:
COMPILEALL:
GIT_DIFF_CHECK:
SECRET_SCAN:
SCOPE_GATE:

HERMES_REQUALIFICATION_REQUIRED: YES
W4C_STARTED: NO
```

Commit-/Push-SHAs nach Abschluss eintragen.

---

## 8. Final-Commit

Nur wenn der finale Gate ausreichend grün ist.

Genau ein Commit mit direktem Parent:

```text
319ce3f29db302795beb767be910fe1aeb8609d6
```

Subject:

```text
AP-SRV-070 W4AB-C1: close Linux qualification and W4B root findings
```

Vor Commit:

```powershell
git diff --check
git status --short
```

Nach Commit:

```powershell
git rev-parse HEAD
git rev-parse "HEAD^{tree}"
git rev-parse HEAD^
```

`HEAD^` muss exakt `319ce3f...` sein.

---

## 9. Distributed Fast-Forward

Vor Push erneut:

```powershell
git fetch github
git rev-parse github/feat/einheitliche-triggerarchitektur-distributed
```

Muss noch:

```text
319ce3f29db302795beb767be910fe1aeb8609d6
```

sein.

Dann:

```powershell
git merge-base --is-ancestor github/feat/einheitliche-triggerarchitektur-distributed HEAD
git push github HEAD:feat/einheitliche-triggerarchitektur-distributed
```

Kein Force.

Danach prüfen:

```text
Distributed = neuer finaler Commit
Canonical   = c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

Handoff-Branch unverändert lassen; später separat löschbar.

---

## 10. Abschlussantwort

Kurz:

```text
W4AB-C1 FINALIZED

PARENT:
COMMIT:
TREE:
DISTRIBUTED:
CANONICAL:

A-J: PASS

FULL UNIT:
COMPILEALL:
DIFF CHECK:
SECRET/SCOPE:

HERMES_REQUALIFICATION_REQUIRED: YES
Evidence:
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4AB-C1\Final\

W4C_STARTED: NO
```

Keine neue Root-Hardening-Runde eröffnen.
