# AP-SRV-070 / W4A-C3 — Real Artifact Qualification

**Datum:** 2026-09-01
**Gegenstand:** frischer echter Free-Native-Build gegen den finalen C3-Code,
persistenter Store, echter REUSE, echte Installation/Import/Variant-Verifikation.

Ergebnis: **qualifiziert.** Kein Stub, kein synthetisches Wheel, keine fremde
gleichnamige Datei.

---

## 1. Gewählte Plattform

**Windows / free** — die vom Prompt bevorzugte Plattform, weil Root Finding J
genau den Windows-Crossbuild betrifft. Der nun deterministische, gepinnte
Builder ist in dieser Umgebung lauffähig, also wurde er auch real qualifiziert.
Es musste nicht auf einen anderen W4A-Supported-Pfad ausgewichen werden.

Host: Windows 11 Pro 26200, CPython 3.12.10 x64, Docker Desktop 4.88.1 /
Engine 29.7.2 (linux/amd64), 4 CPU.

Docker Desktop war zu Beginn der Sitzung *manuell pausiert* („Docker Desktop is
manually paused"). Für den geforderten realen Build wurde die Engine wieder
gestartet; das ist eine reversible lokale Werkzeugzustandsänderung und wird hier
offen dokumentiert.

---

## 2. Vorab-Validierung der neuen externen Buildinputs (vor dem teuren Build)

Der Prompt verlangt, die neu gepinnten externen Inputs zuerst *billig* zu
verifizieren. Genau so wurde vorgegangen — die SHA-256-Werte in
`VoiceSTT/kroko/buildinputs.py` sind **nicht geraten**, sondern jeweils aus
einem echten Download berechnet, bevor irgendein nativer Build lief:

| Input | Vorab-Validierung |
| --- | --- |
| Base-Image-Digest | Docker-Registry-Manifest-Abfrage (ohne laufenden Build) |
| apt-Snapshot | `dists/{noble,noble-updates,noble-security}/Release` einzeln auf HTTP 200 geprüft, `Valid-Until` nicht gesetzt ⇒ keine Ablaufprobleme |
| CMake 3.30.5 | heruntergeladen, SHA-256 berechnet **und** gegen Kitwares publizierte `cmake-3.30.5-SHA-256.txt` gegengeprüft |
| xwin 0.6.5 | heruntergeladen, SHA-256 berechnet |
| Windows-CPython 3.12.7 (NuGet) | heruntergeladen, SHA-256 berechnet |
| VC++ Redistributable | rollierender `aka.ms`-Alias aufgelöst, die immutable Ziel-URL heruntergeladen, SHA-256 berechnet (stimmt mit dem in der URL enthaltenen Hash überein) |
| OpenSSL 3.6.4 (conda-forge) | heruntergeladen, SHA-256 berechnet und gegen `repodata.json` gegengeprüft; Paket entpackt und das Dateilayout (`Library/{bin,lib,include}`) gegen das geprüft, was CMakes `FindOpenSSL` erwartet |
| openfst-Tag-Archiv | heruntergeladen, SHA-256 berechnet |
| Packaging-Pins | Existenz jeder exakten Version auf PyPI per API geprüft |

Anschließend wurde das Builder-Image **allein** gebaut (also ohne den ~30-minütigen
nativen Compile), um alle Pins in situ zu validieren, bevor Build-Zeit investiert
wurde.

### Dabei gefundene und behobene reale Fehler (keine Blindwiederholungen)

1. **`apt` scheiterte am Snapshot.** Das Base-Image bringt kein CA-Bundle mit,
   `snapshot.ubuntu.com` ist HTTPS-only (`http://` redirectet auf `https://`).
   Diagnose aus dem Log: *„No system certificates available."* Behoben durch
   einen dokumentierten `ca-certificates`-Bootstrap aus den bildeigenen
   Default-Quellen, **bevor** die Quellen auf den Snapshot umgestellt werden.
   Ein Trust Store ist kein Build-Input; jedes Paket, das die erzeugten Bytes
   beeinflussen kann, kommt weiterhin ausschließlich aus dem Snapshot.
2. **Die Packaging-Pins ließen sich nicht installieren.** Diagnose aus dem Log:
   *„Cannot uninstall wheel 0.42.0, RECORD file not found. Hint: The package was
   installed by debian."* Ubuntus `python3-wheel`/`python3-setuptools` sind
   dpkg-verwaltet und für pip nicht deinstallierbar. Behoben mit
   `--ignore-installed` plus einer **In-Image-Assertion**, die beweist, dass der
   Interpreter tatsächlich die gepinnten Versionen auflöst — statt die
   `sys.path`-Reihenfolge nur anzunehmen. Der Schritt bekam außerdem eine eigene
   Layer, damit eine Korrektur an den Pins nicht die minutenlange
   apt-Snapshot-Auflösung wiederholen muss.

   Nebenbefund, der den Pin rechtfertigt: die *ursprüngliche* ungepinnte Zeile
   `pip3 install setuptools wheel delvewheel` hat gar nichts installiert — pip
   betrachtet eine Anforderung ohne Version als bereits erfüllt. Die
   Wheel-Erzeugung hing damit faktisch am Base-Image, nicht an etwas Deklariertem.

Beide Fehler wurden je **einmal** kontrolliert nach Diagnose korrigiert. Es gab
keine Wiederholungsschleife langer nativer Builds: der native Compile lief
genau **einmal**.

---

## 3. Der gepinnte Builder

Alle Content-Gates haben im realen Image-Build gefeuert und bestanden:

```text
/tmp/cmake.tar.gz: OK
xwin.tar.gz: OK
/opt/vc_redist/vc_redist.x64.exe: OK
python.nupkg: OK
/tmp/openssl.conda: OK
```

und im Container-Lauf zusätzlich:

```text
/tmp/openfst.tgz: OK
```

Image-Identität nach dem Bau:
`sha256:174f3e7338a4726cb15fc1b6ccfa53a6280c903cdd63f8eae5be270a54b1b916`
(erstellt 2026-09-01).

Live im Image verifiziert (nicht nur im Dockerfile behauptet):

```text
setuptools 75.8.2
wheel 0.45.1
delvewheel 1.10.1
wheel.bdist_wheel OK
```

Im realen Build tatsächlich verwendete Toolchain (aus dem Container-Log):

```text
CMake: cmake version 3.30.5
clang: Ubuntu clang version 19.1.1 (1ubuntu1~24.04.2)
Variant: free (KROKO_LICENSE=OFF)
```

---

## 4. Der reale Build

```text
Kroko build fingerprint: b2483a5a5c488f59 (variant free,
    upstream https://github.com/kroko-ai/kroko-onnx.git @ 8657e655192623b98d7708e742a72987f953d3a2)
No reusable Kroko artifact: no stored artifact for this variant/fingerprint
...
Unrepaired wheel: /tmp/wheel-build/kroko_onnx-1.12.9-cp312-cp312-win_amd64.whl
  _sherpa_onnx.cpython-312-x86_64-linux-gnu.so -> _sherpa_onnx.cp312-win_amd64.pyd
=== Repaired + slimmed wheel ===
Built Kroko-ONNX wheel: ...\release_artifacts\windows\kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl
Stored verified Kroko artifact: ...\kroko-artifacts\free\b2483a5a5c488f59\kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl
exit=0
```

Dass das Wheel die korrekten `cp312-cp312-win_amd64`-Tags trägt, ist der direkte
Beleg, dass der `wheel<0.46`-Pin greift: upstream `cmake/cmake_extension.py`
importiert `wheel.bdist_wheel` und fällt bei ImportError still auf
`bdist_wheel = None` zurück, was das Tagging verändert hätte.

### Eine erklärungsbedürftige Log-Auffälligkeit (kein Build-Fehler)

Im Log stehen mehrere Zeilen der Form
`find: '/C/$Recycle.Bin/...': Permission denied`.

Ursache, vollständig diagnostiziert: `build_windows.bat` zählt die gestageten
Dateien mit `dir /B "%STAGING%" | find /C /V ""`. In der Shell-Umgebung dieses
Laufs stand Gits GNU-`find.exe` im `PATH` **vor**
`C:\Windows\System32\find.exe` (`where find` bestätigt beide, GNU zuerst).
GNU-`find` interpretiert `/C /V ""` als Pfadargumente und durchsucht daher das
gesamte Laufwerk `C:`. Sichtbare Folge im Log:

```text
    Staged /C/Meine files in ...\release_artifacts\windows\bin-free
```

— also ein Müllwert in genau der Variablen, die ausschließlich in dieses eine
`echo` fließt. Der Wert wird nirgends geprüft, und `errorlevel` wird für diesen
Befehl nicht ausgewertet. Er kann das Wheel, den Fingerprint, die Verifikation
und den Store nicht berühren; das direkt darauf folgende Wheel-Retag lieferte
korrekt `kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl (11M)`.

Das ist ein Artefakt der **Aufrufumgebung** dieses Laufs, kein Produktfehler und
keines der Findings I–K. Der Laufwerksscan wurde beendet, nachdem seine
Wirkungslosigkeit belegt war; der Batch lief danach unverändert weiter
(Retag → NSIS → Store, `exit=0`). Sauberer Umgang künftig: den Build aus einer
reinen cmd-/PowerShell-Umgebung starten. Den Batch auf
`%SystemRoot%\System32\find.exe` festzunageln wäre eine Änderung der
Patch-Ausgabe und damit ein `PATCH_SET_REVISION`-Bump samt neuem Pflichtbuild —
für eine reine Anzeigezeile unverhältnismäßig und außerhalb des C3-Scopes.

---

## 5. Persistenter Artifact-Store

```text
C:\Users\user\AppData\Local\VoiceSTT\kroko-artifacts
```

Das ist der reguläre, **nicht temporäre** Per-User-Store aus
`default_store_root()` — außerhalb des Repositories, sodass ein `git clean` ihn
nicht zerstören kann. Kein `--artifact-store`-Override, kein Temp-Verzeichnis.

Slot:

```text
...\kroko-artifacts\free\b2483a5a5c488f59\
    artifact.json
    kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl
```

| Feld | Wert |
| --- | --- |
| Wheel | `kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl` |
| SHA-256 | `cdaa28193366c21d21b6f59e73cd0733fd59ba3eba6a471d540ba11a34f48f38` |
| Bytes | `12549999` |
| Fingerprint | `b2483a5a5c488f59` |
| Toolchain-Authority | `5c93d37146d3dd23` |
| Upstream Repo | `https://github.com/kroko-ai/kroko-onnx.git` |
| Upstream Revision | `8657e655192623b98d7708e742a72987f953d3a2` |
| Target Platform / Arch | `windows` / `amd64` |
| Python Tag / ABI | `cp312` / `cp312` |
| Variant | `free` |
| Patch-Set / Builder Revision | `2` / `4` |

Die vollständigen Fingerprint-Inputs liegen als
`evidence_artifacts/2026-09-01_W4A_C3_stored_artifact_metadata.json` und
`…_describe_artifact.json` bei.

---

## 6. Echter REUSE-Proof

Zweiter ganz normaler Lauf gegen denselben Store:

```text
command : python -m VoiceSTT.install_kroko --build --variant free --skip-install
exit    : 0
elapsed : 0.34s
Kroko build fingerprint: b2483a5a5c488f59 (...)
Reusing verified Kroko artifact: ...\kroko-artifacts\free\b2483a5a5c488f59\kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl
Kroko-ONNX is ready in this Python environment.

docker containers unchanged: True
docker images unchanged    : True
RESULT: CACHE HIT -> REUSE, no native build started
```

Dass kein Native-Build startet, ist dreifach belegt: kein Build-Pfad-Schritt im
Output (weder Checkout, noch Build, noch Store), 0,34 s statt Build-Zeit, und
Docker sieht **keinen** neuen Container und **kein** neues Image.

---

## 7. Installation / Import / Variant-Verifikation

Wegwerfbare venv **außerhalb** des Worktrees
(`…\scratchpad\qualify-venv`, kein neues persistentes venv angelegt):

```json
{
  "distributionVersion": "1.12.9",
  "importedFrom": "...\\qualify-venv\\Lib\\site-packages\\kroko_onnx\\__init__.py",
  "free": {
    "expectedVariant": "free", "importable": true,
    "installedBuildTag": "1free", "installedVariant": "free", "ok": true
  },
  "pro": {
    "expectedVariant": "pro", "importable": true,
    "installedBuildTag": "1free", "installedVariant": "free", "ok": false,
    "problem": "installed Kroko runtime variant 'free' does not match the expected 'pro'"
  }
}
```

| Gate | Ergebnis |
| --- | --- |
| Wheel in wegwerfbarer venv außerhalb des Worktrees installiert | OK |
| `import kroko_onnx` erfolgreich | OK (aus der venv, nicht aus dem äußeren Interpreter) |
| `verify_installed_runtime("free") == ok` | OK |
| Pro-Negativprobe gegen dasselbe Free-Wheel lehnt ab | OK — abgelehnt mit begründetem `problem` |
| disposable venv danach entfernt | OK (verifiziert: Pfad existiert nicht mehr) |
| Artifact im persistenten Store **nicht** entfernt | OK (verifiziert: Datei vorhanden, SHA-256 unverändert) |

---

## 8. Was real bewiesen ist — und was nur testseitig

**Real bewiesen (echte Bytes, echte Toolchain):**
der gepinnte Windows-Builder ist lauffähig; jedes gepinnte externe Input wurde
gegen seinen deklarierten SHA-256 geprüft; die pinned OpenSSL-Quelle ersetzt die
Verfügbarkeitsschleife tatsächlich im gebauten Image; ein echtes Free-Wheel wurde
kompiliert, verifiziert, im persistenten Store abgelegt, aus dem Store
wiederverwendet ohne Neubau, installiert, importiert und als `free` verifiziert,
während die Pro-Probe abgelehnt wurde.

**Nur testseitig bewiesen (bewusst, kein realer Lauf):**
das Repo-A→Repo-B-Verhalten aus Finding I (gegen echte lokale Test-Repos, aber
nicht gegen zwei reale Kroko-Upstreams); die Crash-Klasse aus Finding K (der
harte Prozessabbruch wird durch exakt denselben On-Disk-Zustand simuliert, den
ein Kill hinterlässt — ein echter Kill mitten im Swap ist nicht deterministisch
herstellbar); der Pro-Variant-Build (nur der Free-Pfad wurde real gebaut, wie
vom Prompt vorgesehen); und dass eine Änderung eines gepinnten Toolchain-Inputs
den Fingerprint bewegt (per Subtest, nicht durch einen zweiten 30-Minuten-Build —
ein solcher Nachweis wäre reine Verschwendung und der Prompt untersagt
unnötige Wiederholungen langer Builds ausdrücklich).
