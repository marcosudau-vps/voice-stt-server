# AP-SRV-070 / W4AB — Linux Test-Portability Correction
## Enger Test-Harness-Fix nach erfolgreicher realer Ubuntu-Kroko-Qualification

### Zweck

Die reale Ubuntu-Qualification des Produktcodes auf Commit

```text
b2ec1657d40b4015cf8cf92c17eef1371b127b78
```

war in allen Produkt-/Runtime-Gates erfolgreich:

```text
Linux fingerprint: 98793851d8632294
Native Free Build: PASS
Wheel filename 1free: PASS
WHEEL Build: 1free: PASS
Artifact Store Lookup: PASS
Second-run REUSE: PASS
Import: PASS
Free variant: PASS
Pro negative: PASS
Repo hygiene: PASS
```

Einziger Blocker sind 10 Linux-Fehlschläge in:

```text
tests/unit/test_kroko_artifact_store.py
```

Die Evidence zeigt Test-Harness-/Portabilitätsprobleme, nicht einen realen Produktcodefehler.

Dieser Auftrag behebt **ausschließlich diese Test-Portabilität**.

Keine Produktarchitektur. Kein W4C. Keine Kroko-Produktcode-Härtung.

---

# 1. Arbeitsort

Arbeite im bestehenden lokalen Windows-Workspace:

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w4b
```

Zu Beginn:

```powershell
git fetch github
git status --short
git branch --show-current
git rev-parse HEAD
git rev-parse github/feat/einheitliche-triggerarchitektur-distributed
git rev-parse github/feat/einheitliche-triggerarchitektur
```

Erwartung:

```text
HEAD:
b2ec1657d40b4015cf8cf92c17eef1371b127b78

Distributed:
b2ec1657d40b4015cf8cf92c17eef1371b127b78

Canonical:
c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

Bei unerwarteten Source-Änderungen stoppen.

---

# 2. Autorisierte Mutation

Produktcode ist **read-only**.

Erlaubt ist ausschließlich:

```text
tests/unit/test_kroko_artifact_store.py
```

Nur falls technisch zwingend notwendig darf eine unmittelbar zugehörige Testhelper-Datei geändert werden. Das muss dann explizit begründet werden.

Nicht ändern:

```text
VoiceSTT/**
VoiceSTT_server/**
api_fastapi_server/**
config.yaml
requirements.txt
docs/**
build/**
```

---

# 3. Die 10 Linux-Failures nicht als 10 unabhängige Produktfindings behandeln

Die Ubuntu-Evidence zeigt drei wahrscheinliche Test-Harness-Ursachen.

## Ursache A — hardcodierte Windows-Erwartung

Fail:

```text
StoreAndReuseTests::test_storing_a_wheel_produces_a_verified_artifact
```

Der Test erzeugt bereits target-aware Wheels, erwartet danach aber weiterhin hart:

```text
cp312-cp312-win_amd64
```

Auf Linux muss die Erwartung aus dem tatsächlich erzeugten Wheel/Target abgeleitet werden.

Kein OS-spezifischer Skip. Der Test soll auf Windows und Linux denselben Vertrag prüfen.

---

## Ursache B — Test-Lookups verwenden nicht dieselbe effektive Fingerprint-Erzeugung wie der reale Builderpfad

Betroffen:

```text
BuilderReuseFlowTests::test_free_and_pro_rebuilds_never_modify_the_other_variant
BuilderReuseContinuationTests::test_failed_force_rebuild_keeps_the_existing_artifact
BuilderReuseContinuationTests::test_force_rebuild_actually_replaces_the_stored_artifact
```

Die Tests führen den Builder über:

```text
install_kroko.main(...)
```

aus, berechnen für spätere Lookups aber separat:

```python
fingerprint.compute_fingerprint(variant=...)
```

Nach der Linux-OpenSSL-/Toolchain-Authority kann das auf Linux vom effektiven CLI-/Builder-Fingerprint abweichen.

Korrigiere den Test-Harness so, dass er für Lookup/Assertions **denselben effektiven Fingerprintpfad wie der reale install_kroko-Aufruf** benutzt, z.B. über:

```text
install_kroko.parse_args(...)
install_kroko.fingerprint_for(...)
```

oder einen äquivalenten vorhandenen kanonischen Helper.

Keine Produktcodeänderung.

Die zwei gemeldeten MagicMock-Fehler:

```text
RootFindingISourceAuthorityTests::test_reuse_hit_needs_no_checkout_at_all_regression
RootFindingKCrashAtomicSwapTests::test_a_run_after_the_crash_reuses_instead_of_rebuilding
```

zunächst als mögliche **Folgefehler desselben unerwarteten Cache-Miss/Fingerprint-Mismatch** behandeln.

Nicht blind neue Mock-Sonderlogik hinzufügen, bevor geprüft wurde, ob sie nach dem Fingerprint-Harness-Fix bereits verschwinden.

---

## Ursache C — Test-Fixture hängt von globalem Git Default Branch ab

Betroffen:

```text
RootFindingISourceAuthorityTests::
  test_a_checkout_without_a_readable_origin_is_never_trusted
  test_fingerprint_describe_and_checkout_agree_on_the_same_authority
  test_matching_authority_still_reuses_the_existing_checkout
  test_reused_checkout_from_another_repo_is_reclaimed_for_the_requested_one
```

Die Fixture erzeugt lokale Repositories über:

```text
git init
```

übergibt später aber hart:

```text
branch="main"
```

Auf Ubuntu kann `git init` standardmäßig `master` erzeugen.

Mache die Test-Fixture deterministisch und unabhängig von globaler Git-Konfiguration.

Bevorzugt:

```text
git init -b main
```

oder eine gleichwertige explizite Fixture-Initialisierung.

Nicht die Produktlogik auf `master`/`main` tolerant machen; das Problem liegt in der Test-Fixture.

---

# 4. Review-Schwelle

Nur wenn du beim tatsächlichen Debugging beweisen kannst, dass einer der 10 Fehler doch einen realen Produktcodefehler offenlegt:

```text
STOP / BLOCKED
```

und dokumentieren.

Produktcode in diesem Run nicht korrigieren.

Wenn die Fehler wie erwartet Test-Harness-Probleme sind, nur die Tests portabel machen.

Keine neue Dependency-Jagd.
Keine theoretische Härtung.
Kein Repository-weites Audit.

---

# 5. Tests lokal auf Windows

Nach Korrektur zuerst:

```powershell
python -m pytest -q --basetemp="$env:LOCALAPPDATA\Temp\w4ab-linux-testfix" tests/unit/test_kroko_artifact_store.py
```

Dann zusätzlich:

```powershell
python -m pytest -q --basetemp="$env:LOCALAPPDATA\Temp\w4ab-linux-testfix-related" `
  tests/unit/test_install_kroko_cpu.py `
  tests/unit/test_kroko_artifact_store.py `
  tests/unit/test_kroko_fingerprint.py
```

Hard Gate:

```text
0 failed
0 errors
```

Da ausschließlich Test-Harness-Code geändert wird und der Parent bereits eine vollständige Regression von

```text
1513 passed / 14 skipped / 974 subtests / 0 failed
```

hat, ist in diesem Korrekturlauf **keine erneute komplette tests/unit Regression erforderlich**.

Die nächste vollständige Gesamtregression kommt in W5.

---

# 6. Diff-/Scope-Gate

```powershell
git diff --check
git status --short
git diff --name-only
```

Erwartung:

```text
nur tests/unit/test_kroko_artifact_store.py
```

Keine Produktdatei.

---

# 7. Commit / Distributed

Erzeuge genau einen neuen Test-Portabilitätscommit auf Parent:

```text
b2ec1657d40b4015cf8cf92c17eef1371b127b78
```

Vorgeschlagener Subject:

```text
AP-SRV-070 W4AB: make Kroko artifact tests Linux-portable
```

Kein Amend des bestehenden W4AB-C1-Commits.

Kein Rebase.
Kein Force.

Vor Push:

```powershell
git fetch github
git rev-parse github/feat/einheitliche-triggerarchitektur-distributed
```

Muss weiterhin:

```text
b2ec1657d40b4015cf8cf92c17eef1371b127b78
```

sein.

Dann:

```powershell
git merge-base --is-ancestor github/feat/einheitliche-triggerarchitektur-distributed HEAD
git push github HEAD:feat/einheitliche-triggerarchitektur-distributed
```

Canonical bleibt:

```text
c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

---

# 8. Evidence

Erzeuge ausschließlich außerhalb des Repositories:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4AB-LINUX-TESTFIX\
```

Genau zwei Dateien reichen:

## `01_LINUX_TEST_PORTABILITY_FIX.md`

Enthält:

- die 10 Hermes-Failures;
- tatsächliche Root Causes;
- welche Teständerungen vorgenommen wurden;
- Bestätigung `PRODUCT_CODE_CHANGED: NO`;
- lokale Testcounts.

## `W4AB_LINUX_TESTFIX_STATE.md`

```text
PARENT:
COMMIT:
TREE:
DISTRIBUTED:
CANONICAL:

CHANGED_FILES:
PRODUCT_CODE_CHANGED: NO

ROOT_CAUSE_A: FIXED|NOT_APPLICABLE
ROOT_CAUSE_B: FIXED|NOT_APPLICABLE
ROOT_CAUSE_C: FIXED|NOT_APPLICABLE
MOCK_FAILURES_WERE_CASCADE: YES|NO

WINDOWS_ARTIFACT_STORE_TESTS:
WINDOWS_RELATED_KROKO_TESTS:
GIT_DIFF_CHECK:
SCOPE_GATE:

HERMES_RERUN_REQUIRED: YES
W4C_STARTED: NO
```

---

# 9. Abschluss

Melde:

```text
W4AB LINUX TEST PORTABILITY FIX COMPLETE

PARENT:
COMMIT:
TREE:
DISTRIBUTED:
CANONICAL:

PRODUCT_CODE_CHANGED: NO
CHANGED_FILES:

WINDOWS_ARTIFACT_STORE_TESTS:
WINDOWS_RELATED_KROKO_TESTS:

HERMES_RERUN_REQUIRED: YES
W4C_STARTED: NO

Evidence:
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4AB-LINUX-TESTFIX\
```

Danach STOP.
