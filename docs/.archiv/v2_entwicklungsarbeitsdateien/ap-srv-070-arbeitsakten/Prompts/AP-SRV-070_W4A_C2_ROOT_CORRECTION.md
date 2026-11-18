# AP-SRV-070 / W4A-C2 — Root-Korrektur: Variant-Isolation, pristine Build-Source, Linux-Toolchain, crash-sicherer Slot-Lock

## Status

**ROOT FAIL nach W4A-C1 → enge C2-Korrektur erforderlich.**

W4A-C1 hat die vier vorherigen Root-Findings fachlich sauber geschlossen. Der unabhängige Root-Review des C1-Endstands hat jedoch vier weitere konkrete Lücken in demselben Build-/Artifact-Vertrag gefunden. Diese C2 ist ausdrücklich **kein neuer Architekturblock** und kein allgemeines Refactoring.

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
17db3b19370ccf27c73c36fd15ef94bf536411aa
```

Erwarteter Parent-Tree:

```text
e6da0b28eb3720cae33c3d80e2b5906697a714d5
```

Distributed muss vor Beginn exakt darauf stehen:

```text
feat/einheitliche-triggerarchitektur-distributed
= 17db3b19370ccf27c73c36fd15ef94bf536411aa
```

Canonical bleibt unverändert:

```text
feat/einheitliche-triggerarchitektur
= c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

Bei Abweichung: **BLOCKED**, keine Mutation.

Evidence ausschließlich nach:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4A-C2\
```

---

# 2. Root Finding E — `free` kann durch geerbtes `KROKO_LICENSE=ON` zu Pro werden

C1 entfernt die vier Runtime-Lizenzkey-Variablen aus der Build-Child-Environment. Der eigentliche **Build-Capability-Schalter**

```text
KROKO_LICENSE
```

wird jedoch weiterhin aus `os.environ` geerbt.

Aktuell gilt sinngemäß:

```python
env = sanitize_build_subprocess_env(os.environ)
...
if variant == "pro":
    env["KROKO_LICENSE"] = "ON"
# bei free wird ein geerbtes KROKO_LICENSE nicht entfernt/überschrieben
```

Damit kann ein Operator, dessen Shell bereits

```text
KROKO_LICENSE=ON
```

enthält, trotz `--variant free` einen lizenzfähigen Buildpfad aktivieren.

Zusätzlich dokumentiert der gepinnte Kroko-Upstream ausdrücklich, dass nach einem Pro-Build die Lizenzkonfiguration im CMake-Cache bestehen bleiben kann und für einen Free-Build entweder der Build-Ordner gelöscht oder `KROKO_LICENSE=OFF` explizit gesetzt werden muss.

Das verletzt die W4A-Hard-Grenze Free/Pro.

## Verbindliche Korrektur

- `KROKO_LICENSE` darf **niemals ambient** aus der Elternumgebung übernommen werden.
- Die Variant-Authority setzt den Wert explizit:
  - `free` → `KROKO_LICENSE=OFF`
  - `pro` → `KROKO_LICENSE=ON`
- Das gilt mindestens für den nativen Linux-Build.
- Die Windows-Child-Environment soll den ambienten Capability-Wert ebenfalls nicht unkontrolliert erben; dort bleibt die vorhandene `--variant`/`BUILD_VARIANT`-Steuerung des gepinnten Builders die Authority.
- Runtime-Lizenzkeys bleiben unverändert Runtime-only.

## RED-/Regression-Proof

Mindestens:

1. Parent-Env `KROKO_LICENSE=ON` + `linux_build_env("free")` → exakt `OFF`.
2. Parent-Env `KROKO_LICENSE=OFF` + `linux_build_env("pro")` → exakt `ON`.
3. Free nach Pro kann keinen Pro-CMake-Zustand übernehmen.
4. Windows-Build-Child-Env übernimmt kein ambientes `KROKO_LICENSE`.
5. Die vier Runtime-Key-Variablen bleiben weiterhin aus allen nativen Build-Child-Environments entfernt.

---

# 3. Root Finding F — tatsächlicher Native-Build startet nicht garantiert aus pristine Source

`prepare_checkout()` prüft den Git-Commit, lässt aber einen bereits existierenden Checkout mit seinen Working-Tree-/Build-Artefakten bestehen.

Das ist für den Fingerprint-Vertrag nicht ausreichend:

- VoiceSTT patcht upstream Dateien absichtlich vor dem Build.
- Ein späterer Patch-/Builder-Revision-Bump muss wieder vom **unveränderten gepinnten Upstream-Tree** ausgehen.
- Ein alter Patch, manuelle Änderung, alter CMake-Cache oder altes Build-Artefakt darf keinen neuen Build unter einem neuen Fingerprint beeinflussen.
- Ein identischer `HEAD` beweist keine pristine Working Tree.

Besonders relevant: einige Patchfunktionen sind absichtlich idempotent und erkennen bereits gepatchte Marker. Eine alte Patchversion im wiederverwendeten Checkout darf daher nicht dazu führen, dass ein neuer Patchvertrag übersprungen wird.

## Verbindliche Korrektur

Jeder **tatsächlich ausgeführte native Build** muss vor Anwendung der VoiceSTT-Patches aus einer pristine Source genau der effektiven Repo-/Revision-Authority starten.

Bevorzugt:

- den ausschließlich unter dem Kroko-Builder-Workroot liegenden Checkout für einen echten Build sicher neu erzeugen/re-materialisieren,

oder ein gleichwertiger Mechanismus, der zuverlässig beweist:

```text
tracked source = exact pinned/effective commit
untracked/generated build state = kann den neuen Build nicht beeinflussen
VoiceSTT patches = werden erst danach angewendet
```

Harte Grenze:

- **keine** destruktiven Reset-/Clean-Befehle auf dem VoiceSTT-Projektworktree;
- nur der eindeutig validierte externe Kroko-Builder-Checkout unter seinem Builder-Root darf verworfen/re-materialisiert werden.

Der normale Artifact-REUSE-Pfad darf weiterhin **keinen Checkout und keinen Build** benötigen.

## RED-/Regression-Proof

Mindestens:

1. Bereits vorhandener Builder-Checkout mit absichtlich veränderter tracked Upstream-Datei → echter Build-Vorbereitungspfad stellt pristine Commit-Inhalt wieder her, bevor Patches wirken.
2. Altes/untracked Build-/CMake-State kann keinen neuen Build beeinflussen.
3. Effektive `repo`/`revision` bleiben dieselben Werte, die der Fingerprint enthält.
4. Reuse-Hit berührt/re-materialisiert den Checkout nicht.
5. Bewegliche/abgekürzte Revisionen dürfen den bestehenden Exact-Commit-Postcheck nicht umgehen.

---

# 4. Root Finding G — Linux-Toolchain-Fingerprint ist noch nicht vollständig für den realen C++-Build

C1 probt `cmake` und den C-Compiler (`cc`/`gcc`/`clang`). Kroko baut jedoch eine native **C++**-Extension / ein C++-Projekt. Nachdem `CXX` bewusst aus dem Ambient-Environment entfernt wird, wählt CMake den Default-C++-Compiler selbst. Dieser tatsächliche C++-Compiler ist damit ein buildwirksamer Host-Input und muss genauso behandelt werden.

Zusätzlich enthält der gepinnte Upstream den Default:

```text
SHERPA_ONNX_USE_PRE_INSTALLED_ONNXRUNTIME_IF_AVAILABLE = ON
```

Damit kann die bloße Anwesenheit einer hostseitig vorinstallierten ONNX-Runtime denselben deklarierten Buildpfad verändern.

## Verbindliche Korrektur

### 4.1 C++-Compiler

Die Linux-Toolchain-Identity muss mindestens zusätzlich die tatsächlich verwendete C++-Compiler-Identity enthalten:

```text
cxxCompilerPath
cxxCompilerVersion
```

Wenn der reale Builder ein hostseitiges Buildtool (`make`/äquivalent) auswählt, muss auch dessen effektive Identität entweder:

- deterministisch festgelegt und deklariert,
- oder in der Toolchain-Identity erfasst

werden.

Nicht blind weitere Hostinformationen hashen; nur den realen Buildpfad korrekt schließen.

### 4.2 Pre-installed ONNX Runtime

Der Linux-Build darf nicht still davon abhängen, ob auf dem Host zufällig bereits eine ONNX-Runtime installiert ist.

Für den VoiceSTT-Kroko-Build daher den upstream Default deterministisch deaktivieren, z. B. über den deklarierten CMake-Vertrag:

```text
-DSHERPA_ONNX_USE_PRE_INSTALLED_ONNXRUNTIME_IF_AVAILABLE=OFF
```

oder eine nachweislich gleichwertige deterministische Lösung.

Da die CMake-Flags bereits Fingerprint-Inputs sind, muss diese Änderung den Linux-Fingerprint korrekt invalidieren.

## RED-/Regression-Proof

Mindestens:

1. anderer effektiver C++-Compiler → anderer Linux-Fingerprint;
2. C- und C++-Compiler werden nicht fälschlich als dieselbe ungeprüfte Identity behandelt;
3. hostseitig gesetztes `CXX` bleibt nicht buildwirksam;
4. der deklarierte Build deaktiviert den opportunistischen pre-installed-ONNXRuntime-Pfad;
5. normale VoiceSTT-/VERSION-Änderungen bleiben weiterhin fingerprint-neutral.

---

# 5. Root Finding H — Slot-Lock ist bei Prozessabbruch nicht crash-recoverable

C1 serialisiert den finalen Slot-Replace korrekt über:

```text
os.open(..., O_CREAT | O_EXCL)
```

und löscht die Lockdatei im normalen `finally`.

Wenn der Prozess jedoch **nach Lock-Acquire hart beendet wird**, läuft dieses `finally` nicht. Die `.lock`-Datei bleibt bestehen.

Der aktuelle nächste Aufrufer:

- erkennt nur `FileExistsError`,
- wartet bis zu 1800 Sekunden,
- besitzt keine Owner-/Lease-/Stale-Recovery,
- kann denselben Slot danach bei jedem Versuch erneut blockiert vorfinden.

Der vorhandene Test „no stale lock left behind“ testet nur einen normalen erfolgreichen Exit, keinen Prozessabbruch.

## Verbindliche Korrektur

Der per-Slot Lock muss bei einem abgebrochenen/gestorbenen Owner **wieder sicher erwerbbar** werden.

Zulässige kleine Lösungen:

- OS-advisory locking, das beim Prozessende automatisch freigegeben wird,
- oder eine robuste Lockfile-Lease/Stale-Recovery mit atomarer Übernahme.

Kein allgemeines Scheduler-/Job-System.

Sicherheitsanforderungen:

- ein **frischer, lebender** Lock darf niemals gestohlen werden;
- ein nachweislich/stabil als stale behandelter Lock darf keinen manuellen Eingriff erfordern;
- zwei gleichzeitige Reclaimer dürfen nicht beide den Slot besitzen;
- bisherige `adopt_existing`-/Force-Rebuild-Semantik bleibt unverändert.

## RED-/Regression-Proof

Mindestens:

1. simuliert/real verwaister Lock → nächster Aufrufer kann den Slot ohne manuellen Dateieingriff wieder erwerben;
2. frischer Lock → zweiter Aufrufer bleibt ausgeschlossen;
3. zwei konkurrierende Store-Aufrufer → weiterhin keine Korruption;
4. `--rebuild-kroko` ersetzt weiterhin wirklich;
5. keine Lock-/Backup-/Staging-Leichen nach erfolgreichem Abschluss.

---

# 6. Guard-/Revision-Vertrag

Da C2 buildwirksame Builder-Funktionen verändert:

- `BUILDER_REVISION` korrekt anheben;
- Builder-Guard-Digest erst **nach finalem Codezustand** aktualisieren;
- Guard erneut negativ verifizieren: simulierte buildwirksame Drift → rot; Restore → grün.

Keine Guard-Abschwächung, kein Entfernen relevanter Funktionen aus der bewachten Fläche.

---

# 7. Real-Artifact-Vertrag

Kein neuer nativer ~30-Minuten-Build nur für C2 erzwingen.

Falls der `BUILDER_REVISION`-Bump den Windows-Free-Fingerprint erneut ändert, darf das bereits real qualifizierte Wheel

```text
kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl
SHA-256 ac26db5d8c063649028924d4b55b14019b2370e8c457841ea278a8e48dd50041
```

erneut unter dem neuen Fingerprint qualifiziert werden, **sofern** die C2-Änderungen seine reale Provenienz nicht verändern.

Dabei sauber unterscheiden:

```text
re-qualified existing real wheel != newly executed native build
```

Wenn diese Provenienzbedingung nicht sicher erfüllt ist: nicht umdeuten, sondern `EVIDENCE_BLOCKED` für genau diesen Real-Artifact-Teil melden.

---

# 8. Scope-Grenzen

Nicht Teil von C2:

- W4B STT Model Registry / Model Discovery / Auto-Download
- W4C Docker-/Deployment-Produktisierung
- Community-Modell-Lizenzentscheidung
- Pro-Modell-Veröffentlichung
- Release/Tags/PyPI/Registries
- Wakeword-Architektur
- allgemeine Refactorings
- neuer absichtlicher nativer Kroko-Build ohne zwingenden Grund

---

# 9. Test-/Evidence-Gate

Vor Commit mindestens:

1. gezielte RED-/Regression-Tests für Findings E–H;
2. bestehende C1-Tests vollständig weiter grün;
3. alle Kroko-Suiten;
4. `git diff --check`;
5. kompletter Regressionstest gegen finalen C2-Stand;
6. Secret-/Capability-Scan;
7. Evidence, die instrumentierte Tests und reale Artifact-Requalification sauber trennt;
8. Scope-/Hygiene-Nachweis.

Falls ein Full-Regression-Lauf ausschließlich an einem nachweisbaren Host-Ressourcenfehler scheitert: keine Endlosschleife; sauber dokumentieren und gemäß bestehendem W4A-Gate verfahren.

---

# 10. Git-Abschluss

Wenn alle im Prompt definierten Implementierungs-, Scope- und Test-Gates erfüllt sind, genau einen Run-Commit erzeugen und Distributed ausschließlich per Fast-Forward aktualisieren.

Das ist noch kein Root-PASS; die abschließende Bewertung erfolgt anschließend separat.

Keine Amendments, kein Rebase, kein Force-Push, kein Rewrite bestehender W4A-/C1-Historie.

---

# 11. Abschlussmeldung

Am Ende nur kurz:

- C2 Commit-SHA
- Tree-SHA
- finaler Full-Regression-Stand
- Distributed-FF bestätigt
- Evidence-Pfad
- ggf. ehrlich verbleibender Blocker

Alle Evidence-Dateien vollständig im angegebenen `Runs\W4A-C2\`-Ordner bereitstellen.
