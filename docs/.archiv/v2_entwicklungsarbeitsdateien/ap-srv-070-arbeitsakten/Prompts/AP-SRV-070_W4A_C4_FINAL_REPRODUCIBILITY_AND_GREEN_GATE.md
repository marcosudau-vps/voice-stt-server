# AP-SRV-070 / W4A-C4 — Final Reproducibility Closure + Green Qualification Gate

## Status

**ROOT FAIL nach W4A-C3 → gezielte finale Korrektur erforderlich.**

C3 hat Findings I–K und den realen Free-Artifact-Gate weitgehend geschlossen. Der unabhängige Root-Review gegen veröffentlichten C3-Code und reale Build-Evidence hat jedoch noch zwei technische Restlücken sowie einen formalen Qualification-Blocker gefunden. Kein W4B, kein allgemeines Refactoring.

## 1. Git-/Arbeitskontext

```text
Repository: P:\GithubRepos\marcosudau-vps\voice-stt-server
Worktree:   P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070
Branch:     work/AP-SRV-070

Parent:
16662698997b5e32980663ccb82176508d1d23dd

Parent-Tree:
9433ca78334c5906b60b1ca48f2e3ac92cb6358b

Distributed vor Beginn:
feat/einheitliche-triggerarchitektur-distributed
= 16662698997b5e32980663ccb82176508d1d23dd

Canonical unverändert:
feat/einheitliche-triggerarchitektur
= c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

Bei Abweichung: `STATUS: BLOCKED`, keine Mutation.

Evidence ausschließlich:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4A-C4\
```

---

## 2. Root Finding L — xwin ist gepinnt, Microsoft SDK/CRT dahinter aber nicht

C3 pinnt das xwin-Executable (0.6.5 + SHA-256). Der reale Builder führt jedoch aus:

```text
xwin --accept-license --arch x86_64 splat --output /opt/xwin
```

Damit ist nur das Downloader-Programm immutable. xwin 0.6.5 dokumentiert selbst:

- ohne `--manifest` wird das Top-Level-Manifest von Microsoft geladen;
- `--manifest` kann verwendet werden, um reproduzierbaren Output sicherzustellen;
- ohne `--sdk-version` wird die neueste SDK-Version des Manifests verwendet;
- ohne `--crt-version` wird die neueste CRT-Version des Manifests verwendet;
- `splat` lädt und entpackt die Pakete automatisch.

Der C3-Fingerprint enthält derzeit keine Microsoft-Manifest-/SDK-/CRT-Authority. Derselbe Fingerprint kann daher später andere SDK-/CRT-Bytes erhalten.

### Verbindliche Korrektur

Die tatsächliche xwin/MSVC-Sysroot-Authority source-controlled und offline fingerprintbar schließen:

1. konkrete Top-Level-Manifest-Content-Identity ermitteln;
2. Manifest selbst oder immutable URL + SHA-256/equivalente Content-Identity deklarieren;
3. konkrete Windows-SDK-Version deklarieren;
4. konkrete CRT-Version deklarieren;
5. xwin technisch zwingen, genau diese Authority zu verwenden, sinngemäß:

```text
xwin \
  --manifest <verified-manifest> \
  --sdk-version <declared-sdk> \
  --crt-version <declared-crt> \
  --accept-license \
  --arch x86_64 \
  splat --output /opt/xwin
```

Syntax passend zur gepinnten xwin-Version 0.6.5 umsetzen.

Harte Gates:

- Manifest/SDK/CRT sind Teil der Windows Toolchain Declaration und damit des Fingerprints.
- `fingerprint_for()` / `--describe-artifact` bleiben offline; kein Docker-/Microsoft-/Netzwerk-Lookup.
- falscher Manifest-Hash oder fehlende Authority → harter Buildfehler, kein `latest`-Fallback.
- keine bloße Dokumentation ohne technische Erzwingung.

### RED-/Regression-Proof

Mindestens:

1. generierter Builder enthält keinen nackten xwin-`splat`, der SDK/CRT implizit `latest` wählen kann;
2. SDK-Version ändern → Toolchain Authority/Fingerprint ändern;
3. CRT-Version ändern → Authority/Fingerprint ändern;
4. Manifest-Identity ändern → Authority/Fingerprint ändern;
5. realer Builder verwendet exakt die deklarierten Werte;
6. falscher Hash/fehlende Authority → Buildfehler;
7. Fingerprint/Describe bleiben offline.

---

## 3. Root Finding M — tatsächliche Windows-Build-Downloads vollständig auditieren

Der reale C3-Buildlog zeigt weitere FetchContent-/Download-Schritte, u. a.:

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
...
```

**Nicht blind alles neu pinnen.** Einige Dependencies sind im gepinnten Kroko-Upstream bereits per `URL_HASH` oder gleichwertiger Content-Identity geschlossen.

Für jede buildwirksame externe Download-Dependency eine Matrix erstellen:

```text
Dependency
Source/Version Authority
Content Identity
Verification Mechanism
Status:
  CLOSED_BY_PINNED_UPSTREAM
  CLOSED_BY_VOICESTT_AUTHORITY
  OPEN
```

Nur `OPEN` technisch schließen.

Besonders prüfen: ONNX Runtime, kaldi-native-fbank, kaldi-decoder/kaldifst, kissfft, eigen, simple-sentencepiece, websocketpp, asio, cppjieba, hclust_cpp und openfst.

Ein Tagname allein genügt nicht, wenn der tatsächliche Inhalt nicht gegen Hash/Commit-Content-Identity verifiziert wird. Keine pauschale Behauptung „upstream revision pins everything“; die konkrete FetchContent-Definition entscheidet.

**Gate:** Nach dem Audit darf kein buildwirksamer externer Download verbleiben, dessen Bytes sich unter identischem W4A-Fingerprint unbemerkt ändern können.

Wenn außer xwin bereits alles sauber gehasht ist: nicht refactoren, nur beweisen.

---

## 4. Root Finding N — Lookup-TOCTOU während Force-Swap

C3 macht den Swap crash-recoverable. Ein enger Race bleibt:

```text
Writer: final -> backup
Reader: final prüfen -> MISS
Writer: staging -> final
Writer: backup löschen
Reader: backups prüfen -> keine
Reader: gibt alten MISS zurück, obwohl final inzwischen gültig ist
```

Keine Store-Korruption, aber unnötiger Native-Build möglich.

### Verbindliche Korrektur

Ein initialer Miss muss vor Rückgabe gegen eine gleichzeitige Slot-Transition stabilisiert werden, z. B. durch erneute konsistente Verifikation oder eine kleine lock-geschützte Miss-Entscheidung. Gesunder Cache-Hit soll weiterhin cheap/lock-arm bleiben.

### RED-/Regression-Proof

Mit Barriers/Synchronisationspunkten:

1. Reader sieht exakt das `final -> backup`-Fenster;
2. Writer beendet Swap + Cleanup vor Reader-Entscheidung;
3. Reader liefert gültigen Hit, keinen Miss;
4. kein Builder-Aufruf;
5. C1–C3 Crash-/Concurrency-/Force-Tests bleiben grün;
6. normaler Hit bleibt cheap.

---

## 5. Qualification Blocker Q — Full Regression ist rot

C3:

```text
1 failed, 1431 passed, 14 skipped, 934 subtests passed
```

Fehler:

```text
test_admin_replay_reports_retention_gap
```

Evidence zeigt kalenderabhängige Fixture:

```text
Fixture timestamp: 2026-08-02T00:00:00Z
Retention: 30 Tage

Store clock 2026-08-31 -> PASS
Store clock 2026-09-01 -> FAIL
```

Die Ursache ist C3-fremd und der grüne C2-Lauf war korrekt. Der finale W4A-Gate darf trotzdem nicht mit roter Full Regression geschlossen werden.

### Verbindliche Korrektur — nur Test-Fixture

Kein Produktcode und keine Retention-Semantik ändern.

Die „innerhalb Retention“ gedachte Fixture relativ zur kontrollierten Test-/Store-Uhr erzeugen oder die Testuhr explizit einfrieren. Die Testaussage muss identisch bleiben.

Unmittelbar benachbarte Retention-Fixtures derselben kleinen Testgruppe auf denselben absoluten-Zeitstempel-Fehler prüfen; nur eindeutig gleiche Fälle korrigieren.

### Proof

1. bisher roter Test am 2026-09-01 grün;
2. derselbe Test bei deutlich später simulierter Uhr grün;
3. Retention-Gap-Semantik bleibt geprüft;
4. kein Produktcode dafür geändert;
5. Kroko-Fingerprint durch diese Test-only-Korrektur unverändert.

---

## 6. Guard-/Revision-Vertrag

Wenn L/M buildwirksame Patch-/Builder-Logik ändern:

- `PATCH_SET_REVISION` und/oder `BUILDER_REVISION` passend anheben;
- Guard-Surfaces um neue buildwirksame Funktionen erweitern;
- Digests erst nach finalem Codezustand setzen;
- negativ verifizieren: Drift → RED, Restore → GREEN.

Keine Guard-Abschwächung.

---

## 7. Real-Artifact-Gate

C3 Artifact:

```text
Fingerprint: b2483a5a5c488f59
Wheel: kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl
SHA-256: cdaa28193366c21d21b6f59e73cd0733fd59ba3eba6a471d540ba11a34f48f38
Bytes: 12549999
Store: C:\Users\user\AppData\Local\VoiceSTT\kroko-artifacts
```

L wird voraussichtlich die Toolchain Authority/Fingerprint ändern.

**Vor neuem teuren Build** prüfen, ob die für C3 tatsächlich verwendete Microsoft-Manifest-/SDK-/CRT-Identity und alle M-Dependency-Identities aus vorhandenem C3 Builder-Image, Sysroot/Cache, Logs oder unveränderten Build-Artefakten exakt beweisbar sind.

Requalification des vorhandenen C3-Wheels nur, wenn:

```text
neu deklarierte C4-Buildinputs
==
nachweislich exakt die realen Inputs des C3-Wheels
```

Evidence, keine Annahme.

Falls vollständig beweisbar: vorhandenes echtes Wheel requalifizieren.

Falls nicht: genau **einen** neuen Windows/free Native-Build gegen finalen C4-Code; keine Schleife.

Danach erneut zwingend:

- persistenter Store;
- SHA/Bytes/Fingerprint/vollständige Inputs;
- echter `CACHE HIT -> REUSE`;
- kein Native-Build beim Reuse;
- disposable venv außerhalb Worktree;
- `import kroko_onnx`;
- `verify_installed_runtime("free") == ok`;
- Pro-Negativprobe;
- venv entfernen;
- Artifact persistent behalten.

---

## 8. Scope

Erlaubt:

- Kroko Windows Buildinput-/Fingerprint-/Builder-Authority;
- notwendige Windows-Build-Patches;
- Artifact-Store-Lookup-Race;
- direkte Tests und minimale Kroko-Builddoku;
- ausschließlich die kleine kalenderabhängige Retention-Test-Fixture;
- Real-Artifact-Qualification.

Nicht erlaubt:

- W4B;
- W4C Production Docker;
- Retention-/Event-Store-Produktlogik;
- allgemeine Server-Refactorings;
- Client;
- Release/Tag/PyPI/Registry;
- Wakeword-Architektur;
- Modell-Lizenzentscheidungen.

---

## 9. Test-/Evidence-Gates

Vor Commit mindestens:

1. RED-/Regression-Tests L und N;
2. Dependency-Closure-Matrix M;
3. alle bestehenden W4A/C1/C2/C3 Kroko-Suiten;
4. xwin Manifest/SDK/CRT Authority technisch verifiziert;
5. Guard-Negativtests;
6. Retention-Fixture gegen aktuelle und spätere simulierte Uhr;
7. `git diff --check`;
8. Secret-/Capability-Scan;
9. Real-Artifact-Gate gemäß §7;
10. **vollständige Projekt-Regression: 0 failures**.

Der letzte Punkt ist hart. Bei neuer objektiver Infrastrukturblockade: `STATUS: BLOCKED`, kein Erfolgscommit.

---

## 10. Evidence

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4A-C4\
```

Mindestens:

```text
2026-09-01_W4A_C4_ROOT_CORRECTION_REPORT.md
2026-09-01_W4A_C4_TEST_REPORT.md
2026-09-01_W4A_C4_WINDOWS_DEPENDENCY_CLOSURE.md
2026-09-01_W4A_C4_REAL_ARTIFACT_QUALIFICATION.md
2026-09-01_W4A_C4_SECRET_SCAN.txt
2026-09-01_W4A_C4_STATE.md
```

STATE: Parent/C4 SHA/TREE, Distributed before/after, Canonical unchanged, L/M/N/Q, finale Toolchain Authority, xwin Manifest/SDK/CRT, Artifact Fingerprint/SHA/Bytes/Store, Reuse/Install/Variant, Full Regression 0 failures, W4A/W4B readiness.

---

## 11. Git-Abschluss

Nur wenn **alle** Implementierungs-, Scope-, Test- und Real-Artifact-Gates erfüllt sind:

**Wenn alle im Prompt definierten Implementierungs-, Scope- und Test-Gates erfüllt sind, genau einen Run-Commit erzeugen und Distributed ausschließlich per Fast-Forward aktualisieren.**

Das ist noch kein Root-PASS; die abschließende Bewertung erfolgt anschließend separat.

Keine Amendments, kein Rebase, kein Force-Push, kein History-Rewrite.

Bei offenem harten Gate: `STATUS: BLOCKED`, Evidence/Handoff, kein künstliches PASS.

## 12. Abschlussmeldung

Bei Erfolg:

- C4 Commit-SHA
- Tree-SHA
- finale Windows Toolchain Authority
- xwin Manifest/SDK/CRT Authority
- Full Regression (0 failures)
- Artifact-Fingerprint + SHA-256
- persistenter Artifact-Store
- echter REUSE-Proof
- Distributed-FF
- Evidence-Pfad
- Blocker: keine

Bei Blocker: genaue Gate-Stelle, abgeschlossene Arbeiten, Evidence-Pfad, exakter Wiedereinstieg.
