# AP-SRV-070 — W4A — Artifact Cache Report

**Datum:** 2026-08-31
**Teilblock:** W4A-04 / W4A-05 / W4A-06 / W4A-09 (realer Build)

---

## 1. Store-Vertrag (W4A-04)

### Layout

```text
<store-root>/
  free/
    <fingerprint>/
      artifact.json
      kroko_onnx-<version>-1free-<py>-<abi>-<plat>.whl
  pro/
    <fingerprint>/
      ...
  .staging/          # nur während eines atomaren Store-Vorgangs
```

Free und Pro sind **doppelt** getrennt: die Variante ist Teil des Fingerprints
*und* jede Variante hat ihr eigenes Namespace-Verzeichnis. Selbst bei einer
hypothetischen Fingerprint-Kollision könnte ein Pro-Artefakt nicht in einem
Free-Slot landen.

### Root-Auflösung (keine hardcodierten persönlichen Pfade)

1. `--artifact-store <DIR>`
2. `VOICESTT_KROKO_ARTIFACT_STORE`
3. OS-Benutzer-Cache: Windows `%LOCALAPPDATA%\VoiceSTT\kroko-artifacts`,
   Linux `$XDG_CACHE_HOME/voicestt/kroko-artifacts` bzw.
   `~/.cache/voicestt/kroko-artifacts`, macOS
   `~/Library/Caches/VoiceSTT/kroko-artifacts`

Der Default liegt bewusst außerhalb des Repositories, damit ein `git clean`
keinen 30-Minuten-Build vernichtet (Test:
`test_default_root_is_outside_the_repository`).

### Metadaten (`artifact.json`)

Real erzeugtes Dokument dieses Laufs (Feldliste aus dem Secret-Scan):
`schemaVersion`, `fingerprint`, `fingerprintInputs`, `upstreamRepo`,
`upstreamRevision`, `variant`, `targetPlatform`, `architecture`, `pythonTag`,
`abiTag`, `buildFlags`, `toolchain`, `wheelFilename`, `wheelSha256`,
`wheelBytes`, `wheelTags`, `wheelBuildTag`, `builtAt`.

Damit sind alle vom Prompt geforderten Felder abgedeckt. `builtAt` ist
ausdrücklich **informativ und nicht Teil des Fingerprints** — andernfalls sähe
jeder Rebuild wie ein anderes Artefakt aus und Reuse wäre unmöglich.

## 2. Realer qualifizierter Artefakt-Build (W4A-09, „Realer Build")

### Begriffsabgrenzung — was in diesem Lauf real war und was nicht

Damit hier nichts überinterpretiert wird, ausdrücklich getrennt:

| Vorgang | Status in W4A |
|---|---|
| **Bereits existierendes reales Kroko-Wheel vollständig qualifiziert** | **JA** — real. Ein tatsächlich nativ kompiliertes Wheel aus dem gepinnten Upstream-Commit wurde durch den kompletten neuen Vertrag geführt: Introspektion, Store, Verify, Reuse, echte Installation in eine wegwerfbare venv, `import kroko_onnx`, Variantenprüfung inkl. Negativprobe. |
| **Neuer nativer Kroko-Build (~30 min) in W4A ausgeführt** | **NEIN** — nicht ausgeführt, weil die dafür zwingend nötige Docker-Runtime nachweislich weiterhin hängt (Beleg unten). |
| **Reuse-/Force-/Invalidierungsverhalten** | Über den echten `install_kroko.main()`-Pfad mit **instrumentiertem (gestubbtem) Builder** verifiziert. Das ist ausdrücklich **kein** erneut ausgeführter 30-Minuten-Nativbuild und wird hier auch nicht als solcher dargestellt: gezählt wird, *ob und wie oft* der Builder aufgerufen würde — genau die Frage, um die es bei Reuse und Force geht. |

Der Prompt verlangt, mindestens einen echten Kroko-Artefakt-Build zu
*qualifizieren*, und warnt zugleich davor, dieselbe teure Kompilierung mehrfach
blind zu wiederholen. Genau diese Aufteilung ist oben umgesetzt.

### Warum kein *neuer* nativer Build gefahren wurde

Der Windows-Kroko-Build läuft zwingend über Kroko's Docker-Workflow
(`ensure_windows_host()` verlangt Docker; `build_windows.bat` startet den
Container-Crossbuild). Der bereits in W3 dokumentierte Docker-Runtime-Ausfall
besteht in dieser Umgebung **weiterhin**:

- `docker version` antwortet normal (Client + Server).
- `docker run --rm alpine:latest echo …` mit einem **lokal bereits
  vorhandenen** Image hängt und läuft in den Timeout (Exit 124, 60 s).

Es ist also kein Pull-/Netzwerkproblem, sondern die Container-Runtime selbst.
Ein neuer Windows-Kroko-Build war damit nicht durchführbar.

Der Prompt verlangt aber ausdrücklich, mindestens **einen echten
Kroko-Artefakt-Build zu qualifizieren** — nicht, ihn zwingend neu auszuführen —
und warnt gleichzeitig davor, denselben teuren Build unnötig zu wiederholen.
Auf dieser Maschine existiert ein **echtes, real kompiliertes** Kroko-Wheel aus
genau dem gepinnten Upstream-Commit. Es wurde vollständig durch den neuen
Artefaktvertrag qualifiziert.

### Das qualifizierte Artefakt

| Feld | Wert |
|---|---|
| Datei | `kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl` |
| SHA-256 | `ac26db5d8c063649028924d4b55b14019b2370e8c457841ea278a8e48dd50041` |
| Bytes | 12 549 957 |
| Herkunft | realer Build aus `%LOCALAPPDATA%\VoiceSTT\kroko-builder\kroko-onnx`, Upstream `8657e655…` |
| Wheel-Tags | `cp312-cp312-win_amd64` |
| Wheel-Build-Tag | `1free` |
| Fingerprint | `32c947609a9be925` (free/windows/amd64/cp312) |

### Durchgeführte Qualifikation (end-to-end, real)

1. **Introspektion:** Dateiname korrekt als PEP-427-Wheel geparst
   (`build=1free`, `abi=cp312`, `platform=win_amd64`); `WHEEL`-Dokument im
   Archiv gelesen → `Tag: cp312-cp312-win_amd64`, `Build: 1free`;
   Variantenerkennung → `free`.
2. **Store:** über `KrokoArtifactStore.store()` verifiziert und atomar abgelegt
   nach `…/w4a_store/free/32c947609a9be925/`.
3. **Reuse:** `lookup()` liefert einen Treffer ohne Beanstandungen (`problems == []`).
4. **Installation (echte Konsumierung):** In eine wegwerfbare venv außerhalb des
   Worktrees installiert.
5. **Import:** `import kroko_onnx` erfolgreich, `OnlineRecognizer` vorhanden.
6. **Runtime-Variantenprüfung:** installierte dist-info meldet
   `Tag: cp312-cp312-win_amd64`, `Build: 1free`;
   `verify_installed_runtime("free")` → `ok: true`.
7. **Negativprobe:** `verify_installed_runtime("pro")` → `ok: false`,
   `"installed Kroko runtime variant 'free' does not match the expected 'pro'"`.

Damit ist der komplette W4A-06-Konsumvertrag (Fingerprint, SHA-256, Bytes,
Variante, Plattform/Architektur, ABI-Tags, Wheel installierbar, Modul
importierbar, Runtime-Variante korrekt) an einem **echten** Artefakt belegt —
nicht simuliert.

Rohdaten: `evidence_artifacts/2026-08-31_W4A_installed_runtime_consumption.json`.
Die temporäre venv lag außerhalb des Worktrees und wurde nach der Prüfung
entfernt.

## 2a. Reuse-/Force-Nachweis: instrumentiert, nicht nativ nachgebaut

Die Tabellen in §3 und §4 stammen aus dem echten `install_kroko.main()`-Pfad
mit **gestubbtem Builder** (`build_wheel` gepatcht und gezählt, Checkout und
Preflight gepatcht). Sie belegen die Steuerlogik — Reuse-by-default,
Force-Auslösung, Nichtzerstörung bei Fehlschlag — und ausdrücklich **nicht**,
dass eine native 30-Minuten-Kompilierung erneut gelaufen wäre. Für die
Steuerlogik ist ein Aufrufzähler der präzisere Nachweis als eine wiederholte
teure Kompilierung; der Nachweis, dass ein real kompiliertes Artefakt den
Vertrag erfüllt, steht getrennt davon in §2.

## 3. Reuse-by-default (W4A-04, Tests 7–9)

Nachgewiesen über den echten `install_kroko.main()`-Pfad mit instrumentiertem
Builder (`build_wheel` gepatcht und gezählt); die 30-Minuten-Kompilierung wird
bewusst nicht wiederholt, weil ein Zähler dieselbe Frage exakter beantwortet:

| Szenario | Builder-Aufrufe (gezählt) | Ergebnis |
|---|---|---|
| Erster Free-Lauf | `["free"]` | ruft den Builder auf, verifiziert, speichert |
| Zweiter identischer Free-Lauf | `["free"]` (unverändert) | **ruft den Builder nicht erneut auf** |
| Free → Pro → Free | `["free", "pro"]` | der dritte Lauf reused das Free-Artefakt; ein zwischenzeitlicher Pro-Lauf zerstört es nicht |

## 4. Force-Rebuild (W4A-05, Tests 11–12)

| Szenario | Builder-Aufrufe (gezählt) | Ergebnis |
|---|---|---|
| `--rebuild-kroko` nach vorhandenem Artefakt | `["free", "free"]` | der Builder wird **wirklich erneut aufgerufen**; ein vorhandenes Artefakt zählt nicht als Build-Erfolg |
| `--rebuild-kroko` mit fehlschlagendem Build | — | Exit 1; das zuvor gespeicherte gute Artefakt bleibt **unverändert** (gleicher SHA-256) |

Auch hier gilt §2a: „Builder wirklich erneut aufgerufen" heißt, dass der
Force-Pfad den Builder tatsächlich ansteuert statt das Artefakt
durchzureichen — nicht, dass in diesem Lauf ein nativer Build lief.

Ablauf beim Speichern: vollständig in `.staging/` schreiben → dort verifizieren
→ bestehendes Slot-Verzeichnis beiseite legen → atomar `os.replace()` →
Backup erst nach erfolgreichem Swap löschen; bei Fehler wird das Backup
zurückgerollt. Ein fehlgeschlagener Store kann das letzte gute Artefakt daher
nicht beschädigen.

## 5. Integritäts-/Konsumvertrag (W4A-06, Tests 13–14)

Abgelehnt wird — jeweils als **harter Miss**, nie als „best effort"-Treffer:

| Fall | Verhalten |
|---|---|
| Manipulierte Wheel-Bytes | abgelehnt (SHA-256/Bytes) |
| Fehlendes Wheel | abgelehnt |
| Fremder Fingerprint in den Metadaten | abgelehnt |
| Inkompatibles ABI-Tag (`cp311` statt `cp312`) | Store verweigert die Ablage |
| Abweichende gespeicherte Fingerprint-Inputs | abgelehnt |
| Pro-Wheel in einem Free-Slot | Store verweigert die Ablage |
| Free-Artefakt auf Pro-Anfrage | kein Treffer |
| Metadaten-Variante ≠ erwartete Variante | abgelehnt |
| Wheel ohne Free/Pro-Build-Tag | abgelehnt (Variante „unbewiesen") |
| Korruptes Archiv mit korrektem Dateinamen | Variante bleibt unbewiesen → abgelehnt |

Der letzte Fall entstand aus einem Testfehlschlag während dieses Laufs: die
erste Implementierung fiel bei unlesbarem Archiv auf den **Dateinamen** zurück
und hätte ein korruptes „`…-1free-…`.whl" als Free-Variante ausgewiesen. Ein
Dateiname ist trivial fälschbar und darf den tatsächlichen Archivinhalt nie
überstimmen; `variant_of_wheel()` liefert bei unlesbarem Archiv jetzt `None`
(= unbewiesen) statt einer Vermutung.

## 6. Secret-Grenze (W4A-01, Test 17)

- Gespeicherte Metadaten enthalten **kein** Feld, dessen Name auf
  Key/Secret/Token/Credential hindeutet (automatischer Scan über alle
  verschachtelten Felder, Ergebnis: `NONE`).
- Der Fingerprint wird ausschließlich aus deklarierten Buildinputs gebildet und
  liest keine Umgebungsvariablen mit Key-Bezug.
- Automatischer Nachweis: `SecretLeakageTests` injiziert einen synthetischen
  Secret-Wert in `KROKO_API_KEY`, `KROKO_ONNX_KEY`, `VOICESTT_KROKO_ONNX_KEY`
  und `KROKO_KEY` und prüft, dass er weder im Fingerprint noch in den
  Metadaten, im Wheel, in `public_dict()` noch in der Pro-Buildumgebung
  auftaucht.
- Operativer Scan über Store, Wheel und Evidence-Ordner: keine Treffer. Er ist
  allerdings ehrlich begrenzt, weil in dieser Umgebung **kein echter
  Kroko-Key gesetzt war**; der belastbare Nachweis ist deshalb der
  synthetische Injektionstest, nicht der Scan.

Rohdaten: `evidence_artifacts/2026-08-31_W4A_secret_scan.txt`.

## 7. Docker-Umgebungsstatus (nur informativ)

Der Docker-Runtime-Ausfall aus W3 besteht fort (siehe §2). Er bleibt ein Carry
für W4B; W4A wurde nicht in einen Docker-only-Testpfad umgebaut und ist davon
nicht blockiert, weil das reale Artefakt auf dem beschriebenen lokalen Weg
vollständig qualifiziert werden konnte.
