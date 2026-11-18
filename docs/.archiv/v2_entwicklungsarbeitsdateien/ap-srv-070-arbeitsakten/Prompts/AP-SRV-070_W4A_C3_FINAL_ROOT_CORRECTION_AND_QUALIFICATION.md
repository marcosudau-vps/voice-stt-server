# AP-SRV-070 / W4A-C3 — Final Root Correction + Real Artifact Qualification

## Status

**ROOT FAIL nach W4A-C2 → gezielte finale W4A-Korrektur erforderlich.**

C2 hat die Findings E–H fachlich geschlossen. Der anschließende unabhängige Root-Review des gesamten W4A-Endstands hat noch drei konkrete Vertragslücken gefunden. Zusätzlich ist der für W4A notwendige reale Artifact-Vertrag aktuell nicht mehr qualifiziert, weil die zuvor qualifizierten Wheel-Bytes nicht mehr vorhanden sind.

Diese C3 ist ausdrücklich **kein neuer Architekturblock** und kein W4B-Scope. Ziel ist, W4A vollständig und belastbar abzuschließen.

---

## 1. Git-/Arbeitskontext

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

Verbindlicher Parent:

```text
c8db0f5687dc535e0fe9974fba0445b8fd10f2e1
```

Erwarteter Parent-Tree:

```text
5fc61b069f70ad98565eecb90a7b22858ebe695b
```

Distributed muss vor Beginn exakt darauf stehen:

```text
feat/einheitliche-triggerarchitektur-distributed
= c8db0f5687dc535e0fe9974fba0445b8fd10f2e1
```

Canonical muss unverändert bleiben:

```text
feat/einheitliche-triggerarchitektur
= c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

Bei Abweichung:

```text
STATUS: BLOCKED
```

Keine Mutation.

Evidence ausschließlich nach:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4A-C3\
```

---

# 2. Root Finding I — `--repo`-Override und wiederverwendeter Checkout können auseinanderlaufen

C1 koppelte `args.repo` und `args.revision` korrekt an den Fingerprint.

Der reale Checkoutpfad ist aber noch nicht vollständig source-authoritative:

```python
if not repo_dir.exists():
    git clone ... args.repo ...
else:
    "Using existing Kroko-ONNX checkout"

ensure_pinned_revision(repo_dir, revision)
```

Wenn unter demselben `work_dir` bereits ein Checkout aus Repo A existiert und der Operator anschließend mit

```text
--repo Repo-B --revision <B-commit>
```

arbeitet, bleibt `origin` weiterhin Repo A.

`ensure_pinned_revision()` versucht einen fehlenden Commit anschließend ebenfalls über `origin` zu fetchen — also weiterhin aus Repo A.

Damit können:

```text
Fingerprint-Authority = Repo B
Checkout-/Fetch-Authority = Repo A
```

auseinanderlaufen. Im besten Fall scheitert der Build; im schlechtesten Fall wird ein zufällig bereits vorhandener identischer Commit aus der falschen Source-Authority verwendet. Der C1-Vertrag „Fingerprint / describe / cache / real build verwenden dieselbe Source-Authority“ ist damit noch nicht vollständig erfüllt.

## Verbindliche Korrektur

Vor einem echten Build muss der externe Builder-Checkout nachweislich zur effektiven `args.repo`-Authority gehören.

Bevorzugte kleine Lösung:

- aktuelle `origin`-URL des externen Kroko-Checkouts ermitteln;
- gegen die effektive Repo-Authority vergleichen;
- bei Abweichung den **ausschließlich unter dem validierten Kroko-Builder-Workroot liegenden Checkout** sicher entfernen und aus `args.repo` neu klonen;
- danach exakte `revision` wie bisher pinnen und pristine materialisieren.

Eine gleichwertige Lösung ist erlaubt, solange der reale Fetch/Checkout garantiert aus derselben Repo-Authority stammt, die der Fingerprint dokumentiert.

Keine destruktiven Git-Operationen auf dem VoiceSTT-Projektworktree.

## RED-/Regression-Proof

Mindestens:

1. Lokales Test-Repo A wird zuerst als Builder-Checkout verwendet.
2. Danach werden `--repo Repo-B` + ein ausschließlich in Repo B existierender Full-SHA verwendet.
3. `prepare_checkout()` muss danach erfolgreich Repo B / dessen Commit verwenden.
4. `origin` bzw. die reale Fetch-Authority muss Repo B entsprechen.
5. Fingerprint/describe/real checkout dokumentieren dieselbe Repo-/Revision-Authority.
6. Reuse-Hit benötigt weiterhin überhaupt keinen Checkout.

---

# 3. Root Finding J — Windows-Toolchain ist noch nicht wirklich immutable/fingerprintbar

Der aktuelle Windows-Fingerprint behauptet sinngemäß:

```text
toolchain:
  kind: kroko-docker-windows-crossbuild
  definedBy: upstream-revision+patch-set
```

Das ist für den realen Builder nicht ausreichend.

Der gepinnte/angepasste Windows-Docker-Build verwendet weiterhin mehrere **mutable externe Buildinputs**, unter anderem:

- `FROM ubuntu:24.04` ohne Digest-Pin;
- `apt-get install` ohne immutable Repository-/Package-Resolution;
- ungepinnte Python-Packaging-Tools (`setuptools`, `wheel`, `delvewheel`);
- externe Downloads ohne Content-Hash;
- besonders kritisch: der VoiceSTT-Patch probiert mehrere unterschiedliche OpenSSL-Versionen nacheinander und verwendet **die erste URL, die gerade erreichbar ist**.

Damit kann derselbe:

```text
upstream revision
+ patch revision
+ builder revision
+ variant
+ platform/ABI
```

zu unterschiedlichen realen Toolchains bzw. unterschiedlichen gelinkten/bundled Runtime-Bits führen, ohne dass sich der Fingerprint ändert.

Der bereits beobachtete Slproweb-Ausfall zeigt außerdem praktisch, dass diese Dependency-Auswahl keine belastbare immutable Build-Authority ist.

## Verbindliche Korrektur

Der Windows-Build braucht einen **offline berechenbaren, source-controlled und tatsächlich immutable Toolchain-Vertrag**.

Wichtig:

- Ein normaler Artifact-REUSE-/`--describe-artifact`-Pfad darf **nicht** erst Docker bauen, einen Registry-Lookup brauchen oder Netzwerk benötigen, nur um den Fingerprint zu berechnen.
- Deshalb nicht einfach „aktuelle Docker Image ID“ live als Voraussetzung vor jedem Cache-Lookup ermitteln.

Zulässige robuste Wege sind z. B.:

### Variante A — Buildinputs vollständig pinnen

Die buildwirksamen Windows-Builder-Inputs so pinnen, dass dieselbe source-controlled Declaration tatsächlich dieselbe Toolchain meint, z. B.:

- Base-Image per immutable Digest;
- compiler/linker/toolchain-relevante Paketstände oder immutable Snapshot-Authority;
- Python-/Wheel-Packaging-Tools mit festen Versionen;
- CMake/XWin/Python-target weiterhin exakt versioniert;
- externe Binärdownloads mit konkreter Version **und SHA-256**;
- OpenSSL **eine** bewusst gepinnte Version/Quelle/Hash, kein „erste noch erreichbare Version gewinnt“.

### Variante B — immutable Builder-Image-Authority

Eine bereits immutable Builder-Image-/Toolchain-Identity als source-controlled Buildinput verwenden, sofern sie:
- per Digest unveränderlich ist;
- ohne Neubau/Netzwerk für einen vorhandenen Artifact-Hit als erwartete Authority bekannt ist;
- tatsächlich der Builder ist, der den Artifact erzeugt.

Keine bloße manuelle Versionszahl, die externe mutable Inputs verdeckt.

## Harte Regel für OpenSSL

Nicht mehr:

```text
3_6_3 versuchen
sonst 3_5_7
sonst 3_4_6
...
```

unter demselben Fingerprint.

Stattdessen:

```text
exakt deklarierte Source-Version
+ exakt deklarierter SHA-256
```

Wenn diese Source nicht mehr verfügbar ist:

```text
BUILD ERROR / deliberate buildinput update required
```

und **kein** stiller Wechsel auf andere Bits.

## RED-/Regression-Proof

Mindestens:

1. Windows-Fingerprint enthält eine konkrete immutable Toolchain-Authority, nicht nur `"definedBy": "upstream-revision+patch-set"`.
2. Änderung dieser Authority ändert den Fingerprint.
3. Generierter/gepatchter Windows-Build enthält keine availability-basierte OpenSSL-Versionauswahl.
4. OpenSSL-Content wird vor Verwendung gegen einen source-controlled SHA-256 geprüft.
5. Mutable Base-Image-/Packaging-Tool-Inputs sind gepinnt oder anderweitig durch eine immutable Authority geschlossen.
6. `fingerprint_for()` / `describe_artifact()` bleiben bei einem vorhandenen Artifact offline und benötigen keinen Docker-Build.
7. normale VoiceSTT-/Produktversionsänderungen ändern den Fingerprint weiterhin nicht.

---

# 4. Root Finding K — Force-Rebuild-Swap ist exception-safe, aber nicht crash-atomic

`store()` staged und verifiziert das neue Artifact korrekt.

Beim Replace eines vorhandenen Slots geschieht jedoch:

```text
final
  -> os.replace(final, backup)

staging
  -> os.replace(staging, final)

backup löschen
```

Bei einer Python-Exception wird das Backup wiederhergestellt.

Bei einem **harten Prozessabbruch** zwischen den beiden `os.replace()`-Operationen läuft dieser Recovery-Code jedoch nicht:

```text
final fehlt
backup enthält Last-Known-Good
staging existiert eventuell
OS-Lock wird durch Prozessende freigegeben
```

Der nächste normale `lookup()` kennt den Backup-Zustand nicht und meldet Cache-Miss. Damit ist der deklarierte Vertrag:

```text
failed force rebuild must not destroy the known-good artifact
```

für genau die Crash-Klasse, die C2 beim Lock bereits explizit gehärtet hat, noch nicht vollständig erfüllt.

Zusätzlich kann ein Crash nach erfolgreichem `staging -> final`, aber vor Backup-Cleanup, `.replaced-*`-Leichen hinterlassen.

## Verbindliche Korrektur

Der Slot braucht eine kleine crash-recoverable Replace-State-Logik.

Anforderungen:

- Wenn `final` fehlt, aber unter demselben Slot ein verifiziertes Last-Known-Good-Backup existiert, muss dieses **vor einem unnötigen Native-Rebuild** sicher wiederhergestellt/als gültig erkannt werden.
- Wenn `final` vollständig und verifiziert vorhanden ist, dürfen alte `.replaced-*`-Backups kontrolliert bereinigt werden.
- Recovery-/Cleanup-Entscheidungen unter demselben per-slot OS-Lock treffen.
- Mehrere konkurrierende Recovery-Aufrufer dürfen nie gleichzeitig unterschiedliche Zustände aktivieren.
- Backup immer vollständig gegen dieselben `fingerprint`/`variant`/`inputs` verifizieren, niemals nur nach Dateiname vertrauen.
- Bestehende `adopt_existing`- und `--rebuild-kroko`-Semantik unverändert erhalten.
- Kein großes Journal-/DB-/Scheduler-System.

## RED-/Regression-Proof

Mindestens:

1. Valid final vorhanden → force replace beginnt → simuliert harter Abbruch **nach `final -> backup` und vor `staging -> final`**.
2. Nächster Lookup/Store stellt das bekannte gute Artifact ohne Native-Rebuild wieder bereit.
3. Crash nach `staging -> final` vor Backup-Cleanup → gültiges neues final bleibt aktiv; Backup wird später sicher bereinigt.
4. Korruptes/fremdes Backup wird niemals aktiviert.
5. zwei gleichzeitige Recovery-Aufrufer → keine Korruption / genau ein finaler gültiger Slot.
6. bestehende crash-recoverable Lock-, concurrent-store- und force-rebuild-Tests bleiben grün.

---

# 5. W4A Real-Artifact Gate ist aktuell BLOCKED und muss in C3 wieder hergestellt werden

C2 meldet ehrlich:

```text
previous qualified wheel bytes no longer available
Real-artifact re-qualification = EVIDENCE_BLOCKED
```

Das ist kein bloßer Dokumentationshinweis.

Der ursprüngliche W4A-Vertrag verlangt:

- mindestens einen echten Kroko-Artifact-Build, soweit Toolchain verfügbar;
- realen Store/Verify/Reuse/Install/Import-Nachweis;
- W4B readiness nur bei tatsächlich konsumierbarem qualifiziertem Artifact;
- `STATUS: BLOCKED`, wenn der notwendige reale Artifact-Vertrag nicht qualifizierbar ist.

Damit kann W4A aktuell **nicht** Root-PASS erhalten.

## Verbindliche C3-Qualification

Nach Abschluss und Grünstatus der Findings I–K:

1. einen **frischen echten Free-Native-Build** gegen den finalen C3-Code ausführen;
2. kein Stub/kein synthetisches Wheel/keine fremde gleichnamige Datei;
3. Artifact direkt in einem **persistenten, nicht temporären** Kroko Artifact Store ablegen;
4. Store-Pfad in Evidence dokumentieren;
5. nach erfolgreichem Store:
   - SHA-256
   - Bytes
   - Fingerprint + vollständige Inputs
   - upstream repo/revision
   - target platform/arch
   - Python ABI/tag
   - Toolchain-Authority
   - variant
   dokumentieren;
6. anschließend einen echten normalen Lauf gegen denselben Store:
   ```text
   CACHE HIT -> REUSE
   ```
   und beweisen, dass kein Native-Build gestartet wird;
7. Wheel in wegwerfbarer venv außerhalb des Worktrees installieren;
8. `import kroko_onnx` erfolgreich;
9. `verify_installed_runtime("free") == ok`;
10. Pro-Negativprobe gegen dasselbe installierte Free-Wheel muss ablehnen;
11. disposable venv danach entfernen;
12. Artifact im persistenten Store **nicht** entfernen.

### Bevorzugte Plattform

Da Finding J den Windows-Crossbuild betrifft und Docker inzwischen grundsätzlich funktioniert, ist ein finaler **Windows/free** Build besonders wertvoll, sofern der nun deterministische gepinnte Builder in dieser Umgebung lauffähig ist.

Wenn der finale Code stattdessen aus nachvollziehbarem Grund einen anderen echten W4A-Supported-Artifact-Pfad qualifiziert, muss klar dokumentiert werden, was dadurch real bewiesen und was nur testseitig bewiesen ist.

## Kein blindes Retry

Vor dem teuren Build die neu gepinnten externen Inputs möglichst billig verifizieren.

Wenn ein externer Download **vor** eigentlicher nativer Kompilierung transient scheitert, höchstens einen kontrollierten Retry nach Diagnose.

Keine Schleife mehrfacher 30-Minuten-Builds.

Wenn der echte Build trotz final korrekter Implementierung nicht qualifizierbar ist:

```text
STATUS: BLOCKED
```

kein künstliches PASS und W4B nicht starten.

---

# 6. Guard-/Revision-Vertrag

C3 verändert buildwirksame Builder-/Patchlogik.

Daher:

- `PATCH_SET_REVISION` anheben, **wenn** sich die tatsächliche Windows-Dockerfile-/OpenSSL-Patch-Ausgabe ändert;
- `BUILDER_REVISION` anheben, wenn Builder-/Checkout-/Invocation-Logik verändert wird;
- Guard-Digests erst nach finalem Code aktualisieren;
- beide Guards negativ verifizieren:
  ```text
  simulierte buildwirksame Drift -> RED
  Restore -> GREEN
  ```
- keine Guard-Abschwächung.

Falls neue source-controlled Windows-Toolchain-Konstanten eingeführt werden:
- sie müssen echte Fingerprint-Inputs sein;
- Tests müssen deren Änderung gegen den Fingerprint beweisen.

---

# 7. Scope-Grenzen

Nicht Teil von C3:

- W4B STT Model Registry / Discovery / Auto-Download
- W4C Production Docker
- Community-Modell-Lizenzentscheidung
- Pro-Modell-Publish
- PyPI/Registry/GitHub Release
- Wakeword-Architektur
- allgemeine Server-Refactorings
- Client-Code

Erlaubt:

- ausschließlich Kroko Builder / Fingerprint / Artifact Store;
- zugehörige Buildinput-Authority;
- direkte Tests;
- minimale direkt betroffene Kroko-Builddoku;
- reale W4A-Artifact-Qualification.

---

# 8. Test-Gates

Vor Commit mindestens:

1. gezielte RED-/Regression-Tests für Findings I–K;
2. alle C1-/C2-Kroko-Tests weiterhin grün;
3. Guard-Negativtests;
4. `git diff --check`;
5. kompletter Projekt-Regressionstest gegen finalen C3-Stand;
6. Secret-/Capability-Scan;
7. realer Native-Build + persistenter Artifact-Store + echter Reuse;
8. echte Installation/Import/Variant-Verifikation;
9. Scope-/Hygiene-Nachweis.

Umgebungsbedingte Testfehler nicht still wegwinken; klar diagnostizieren. Keine Wiederholungsschleifen.

---

# 9. Evidence

Unter:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4A-C3\
```

mindestens:

```text
2026-09-01_W4A_C3_ROOT_CORRECTION_REPORT.md
2026-09-01_W4A_C3_TEST_REPORT.md
2026-09-01_W4A_C3_REAL_ARTIFACT_QUALIFICATION.md
2026-09-01_W4A_C3_SECRET_SCAN.txt
2026-09-01_W4A_C3_STATE.md
```

STATE muss explizit enthalten:

- Parent / C3 SHA / TREE
- Distributed before/after
- Canonical unchanged
- Findings I–K Status
- finaler Fingerprint-Vertrag
- Windows Toolchain Authority
- Source-Override Authority
- crash-recoverable Artifact-Swap
- echter Free Artifact-Pfad im persistenten Store
- SHA/Bytes/Fingerprint
- Reuse-Proof
- Install-/Import-/Variant-Proof
- Tests
- Secret scan
- W4A overall readiness
- W4B readiness

---

# 10. Git-Abschluss

**Nur wenn alle Implementierungs-, Test- UND Real-Artifact-Gates erfüllt sind:**

Wenn alle im Prompt definierten Implementierungs-, Scope- und Test-Gates erfüllt sind, genau einen Run-Commit erzeugen und Distributed ausschließlich per Fast-Forward aktualisieren.

Das ist noch kein Root-PASS; die abschließende Bewertung erfolgt anschließend separat.

Keine Amendments.
Kein Rebase.
Kein Force-Push.
Keine Rewrite bestehender W4A-/C1-/C2-Historie.

Wenn das Real-Artifact-Gate nicht erfüllbar ist:

```text
STATUS: BLOCKED
```

Evidence/Handoff schreiben, **kein Erfolgscommit vortäuschen**.

---

# 11. Abschlussmeldung

Bei Erfolg nur kurz:

- C3 Commit-SHA
- Tree-SHA
- Full Regression
- realer Artifact-Fingerprint + SHA-256
- persistenter Artifact-Store
- echter REUSE-Proof
- Distributed-FF
- Evidence-Pfad
- Blocker: keine

Bei Blocker:

- kein PASS behaupten;
- genaue fehlgeschlagene Gate-Stelle;
- bereits sicher abgeschlossene Arbeiten;
- Evidence-Pfad;
- exakter nächster Wiedereinstieg.
