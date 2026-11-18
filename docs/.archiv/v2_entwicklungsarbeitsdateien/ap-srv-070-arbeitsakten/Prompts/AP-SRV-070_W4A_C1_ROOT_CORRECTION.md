# AP-SRV-070 / W4A-C1 — Root-Korrektur: Build-Fingerprint, Secret Boundary, Artifact-Verifikation

## Status

**ROOT FAIL → gezielte C1-Korrektur erforderlich.**

W4A ist fachlich weitgehend gelungen, aber der Root-Review hat mehrere konkrete Lücken gefunden, die den zentralen Cache-/Reuse-Vertrag verletzen. Keine neue Architektur und kein allgemeines Refactoring: nur die unten beschriebenen Punkte korrigieren, testen und evidenzieren.

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

Verbindlicher Parent für C1:

```text
0b7b608c5709e7448f46ae66e30896ecdc167d54
```

Erwarteter Parent-Tree:

```text
be6ad9db512c50d3d1360a0b3569b77d140d0c5d
```

Distributed muss vor Beginn auf demselben Commit stehen:

```text
feat/einheitliche-triggerarchitektur-distributed
= 0b7b608c5709e7448f46ae66e30896ecdc167d54
```

Canonical bleibt unverändert:

```text
feat/einheitliche-triggerarchitektur
= c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

Bei Abweichung: **BLOCKED**, keine Mutation.

Evidence ausschließlich nach:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4A-C1\
```

---

## 2. Root Finding A — tatsächlich verwendete Source-Overrides sind nicht im Fingerprint

Aktuell akzeptiert `stt-install-kroko` die CLI-Optionen `--repo` und `--revision`. `prepare_checkout()` verwendet diese Werte tatsächlich für Clone/Checkout. `fingerprint_for(args)` berechnet den Fingerprint jedoch nur aus `variant=args.variant` und verwendet damit weiterhin die statischen Werte aus `buildinputs.py`.

Damit können unterschiedliche Quellen bzw. Revisionen unter **demselben Cache-Key** gebaut und gespeichert werden.

### Verbindliche Korrektur

Es muss genau einer der folgenden sauberen Verträge umgesetzt werden:

1. **Overrides bleiben unterstützt:** Dann müssen der effektiv verwendete Repository-Wert und die effektiv verwendete Revision exakt in den Fingerprint eingehen und Metadata/Describe-Ausgaben dieselben effektiven Werte zeigen.

oder

2. **Produktionsbuild ist ausschließlich auf den Pin festgelegt:** Dann müssen abweichende `--repo`-/`--revision`-Werte vor Cache-Lookup und Build hart abgelehnt werden. Keine scheinbar unterstützten Overrides, die den Fingerprint umgehen.

Keine dritte Variante.

### RED-/Regression-Proof

Mindestens beweisen:

- Default und abweichende Revision können niemals denselben effektiven Fingerprint verwenden.
- Default und abweichendes Repo können niemals denselben effektiven Fingerprint verwenden.
- `describe-artifact`, Cache-Lookup und realer Build verwenden dieselbe Source-Authority.

---

## 3. Root Finding B — Linux-Build hat nicht deklarierte buildwirksame Eingaben

Aktuell:

- `fingerprint_for(args)` übergibt keinen konkreten Linux-Toolchain-Fingerprint.
- `toolchain_identity("linux")` fällt dadurch auf lediglich `{"kind": "host-native"}` zurück.
- `linux_build_env()` übernimmt die komplette Host-Umgebung.
- Ein bereits gesetztes `SHERPA_ONNX_CMAKE_ARGS` wird an die deklarierten Flags angehängt.
- Ein bereits gesetztes `SHERPA_ONNX_MAKE_ARGS` kann den deklarierten Wert per `setdefault()` überschreiben.
- Weitere übliche Build-Variablen wie `CC`, `CXX`, `CFLAGS`, `CXXFLAGS`, `LDFLAGS`, `CMAKE_GENERATOR` usw. können ebenfalls aus der Host-Umgebung in den Build gelangen.

Damit können zwei Builds mit demselben Fingerprint unterschiedliche effektive Build-Eingaben verwenden.

### Verbindliche Korrektur

Der Buildvertrag muss geschlossen werden:

- Entweder buildwirksame Ambient-Overrides **deterministisch entfernen/normalisieren**, sodass nur deklarierte Werte wirksam sind,
- oder jeden unterstützten buildwirksamen Wert in kanonischer Form in den Fingerprint aufnehmen.

Für Linux muss die tatsächlich buildwirksame Toolchain-Identität repräsentiert werden. Mindestens die für den realen Pfad relevanten Compiler/CMake-/Buildtool-Identitäten dürfen nicht pauschal als nur `"host-native"` kollabieren.

Die Lösung darf nicht bei einem Unit-Test stehen bleiben; `fingerprint_for(args)` und der reale Buildpfad müssen dieselbe effektive Eingabe-Autorität benutzen.

### RED-/Regression-Proof

Mindestens beweisen:

- Eine tatsächlich buildwirksame CMake-/Compiler-/Toolchain-Änderung ändert den Fingerprint **oder wird vor dem Build neutralisiert**.
- Nicht buildwirksame normale VoiceSTT-/VERSION-Änderungen ändern ihn weiterhin nicht.
- Der reale `linux_build_env()` kann keine nicht deklarierte buildwirksame Abweichung einschleusen.
- `BUILDER_REVISION` und Guard-Digest werden bei notwendiger Builder-Codeänderung korrekt angehoben.

---

## 4. Root Finding C — Kroko-Lizenzkeys gelangen aktuell in die Build-Umgebung

Der W4A-Vertrag lautet: **Lizenzkey ist ausschließlich Runtime-Secret und kein Build-Input.**

Aktuell kopiert `linux_build_env()` jedoch `os.environ` vollständig. Damit werden gesetzte Variablen wie

```text
KROKO_API_KEY
KROKO_ONNX_KEY
VOICESTT_KROKO_ONNX_KEY
KROKO_KEY
```

in die Umgebung des Build-Subprozesses übernommen.

Der bestehende Test prüft nur, dass der Secret-Wert nicht in CMake-/Make-Argumentstrings auftaucht; er beweist nicht, dass die Key-Variablen aus der Build-Umgebung entfernt sind.

Der Windows-Pfad startet `cmd.exe` ohne explizit bereinigte Umgebung und erbt damit ebenfalls die Prozessumgebung.

### Verbindliche Korrektur

- Alle bekannten Kroko-Lizenzkey-Variablen müssen vor **jedem nativen Build-Subprozess** aus dessen Umgebung entfernt werden.
- Parent-/Runtime-Environment nicht global zerstören; nur die Build-Child-Environment sanitizen.
- Free und Pro verwenden denselben Secret-Boundary-Vertrag.
- Pro wird ausschließlich durch den Capability-Switch (`KROKO_LICENSE=ON`) gebaut, niemals durch einen Key.
- Kein Key in Fingerprint, Build-Metadata, Logs oder Commands.

### RED-/Regression-Proof

Mit gesetzten Sentinel-Secrets beweisen:

- Linux-Build-Child-Env enthält keinen der Keys.
- Windows-Build-Child-Env enthält keinen der Keys.
- Capability-Switch bei Pro bleibt vorhanden.
- Runtime-Key-Verhalten außerhalb des Builders bleibt unverändert.

---

## 5. Root Finding D — Wheel-Plattform wird nicht gegen den Ziel-Fingerprint verifiziert

`verify_artifact()` prüft aktuell u. a. Fingerprint, Variant, SHA-256, Bytezahl und Python/ABI-Präfix. Die `targetPlatform`-/`architecture`-Werte werden aber nur gegen die ebenfalls aus den erwarteten Inputs erzeugten Metadata-Felder verglichen.

Der tatsächliche Wheel-Tag wird nur auf das Präfix `pythonTag-abiTag` geprüft. Dadurch kann beispielsweise ein strukturell gültiges

```text
cp312-cp312-win_amd64
```

Wheel bei passenden Metadaten prinzipiell unter einem Linux-Fingerprint akzeptiert werden, weil die Plattformkomponente des Wheel-Tags nicht gegen den erwarteten Target-Contract geprüft wird.

### Verbindliche Korrektur

Die Wheel-Kompatibilitätsprüfung muss den tatsächlichen Wheel-Tag gegen den erwarteten Target-Contract prüfen:

- Python-Tag
- ABI
- Plattform
- Architektur, soweit im Wheel-Platform-Tag abbildbar

Keine bloße Metadata-Selbstauskunft.

### RED-/Regression-Proof

Mindestens:

- Windows-Wheel unter Linux-Inputs → **REJECT**
- Linux-Wheel unter Windows-Inputs → **REJECT**
- amd64/arm64-Mismatch → **REJECT**
- korrekter Tag → **PASS**

---

## 6. Root Hardening — gleichzeitiger Zugriff auf denselben Artifact-Slot

Der Store staged und ersetzt atomar, besitzt aber derzeit keinen sichtbaren Interprozess-/Same-Fingerprint-Lock. Zwei parallele Prozesse können denselben Cache-Miss sehen und gleichzeitig bauen bzw. denselben Slot ersetzen.

Für W4B/CI ist mindestens zu klären und zu beweisen:

- derselbe Variant+Fingerprint-Slot kann nicht korrumpiert werden;
- ein paralleler Prozess darf einen bereits fertig qualifizierten Artifact-Hit wiederverwenden;
- keine zerstörerischen Backup-/Replace-Races.

Eine kleine per-slot Lock-Lösung ist zulässig. Kein allgemeines Job-/Scheduler-System bauen.

Wenn die bestehende Implementierung ohne neuen Lock nachweislich sicher ist, genügt ein reproduzierbarer Concurrency-Test plus Dokumentation. Bloße Behauptung genügt nicht.

---

## 7. Scope-Grenzen

Nicht Teil von C1:

- W4B STT Model Registry implementieren
- W4C Docker/Deployment implementieren
- Community-Modell-Lizenzpolitik neu entscheiden
- Pro-Modelle veröffentlichen
- Release/Tag/Registry/PyPI
- Wakeword-Architektur verändern
- allgemeine Refactorings
- neuer nativer 30-Minuten-Build ohne zwingenden Grund

Die neue STT-Model-Registry wird erst nach W4A Root PASS begonnen.

---

## 8. Tests / Gate

Vor Commit mindestens:

1. gezielte RED-FIRST-Tests für Findings A–D;
2. Kroko-Fingerprint-/Artifact-/Model-/Engine-Suites;
3. `git diff --check`;
4. kompletter Regressionstest gegen finalen C1-Stand;
5. Secret-Scan über Diff/Evidence auf verwendete Sentinel-Keys;
6. Evidence mit klarer Trennung zwischen instrumentiertem Buildtest und real qualifiziertem vorhandenen Wheel.

Falls durch `BUILDER_REVISION`/Fingerprint-Änderung ein neuer Artifact-Fingerprint entsteht, darf der bereits real gebaute qualifizierte Wheel erneut in den Store aufgenommen und verifiziert werden, sofern seine reale Provenienz weiterhin exakt zu den deklarierten Build-Eingaben passt. Das nicht als neuen nativen Build darstellen.

---

## 9. Git-Abschluss

Wenn alle im Prompt definierten Implementierungs-, Scope- und Test-Gates erfüllt sind, genau einen Run-Commit erzeugen und Distributed ausschließlich per Fast-Forward aktualisieren.

Das ist noch kein Root-PASS; die abschließende Bewertung erfolgt anschließend separat.

Keine Amendments, kein Rebase, kein Force-Push, kein Rewrite bestehender W4A-Historie.

---

## 10. Abschlussmeldung

Am Ende nur kurz:

- C1 Commit-SHA
- Tree-SHA
- finaler Full-Regression-Stand
- Distributed-FF bestätigt
- Evidence-Pfad
- ggf. ehrlich verbleibender Blocker

Alle Evidence-Dateien im angegebenen `Runs\W4A-C1\`-Ordner vollständig bereitstellen.
