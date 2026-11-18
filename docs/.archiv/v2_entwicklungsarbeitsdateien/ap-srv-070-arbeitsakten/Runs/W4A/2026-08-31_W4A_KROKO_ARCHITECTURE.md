# AP-SRV-070 — W4A — Kroko Architecture Report

**Datum:** 2026-08-31
**Teilblock:** W4A-01 / W4A-02 / W4A-03 / W4A-10 / W4A-11

---

## 1. Ausgangszustand (vor W4A ermittelt)

| Aspekt | Zustand vor W4A |
|---|---|
| Upstream-Bezug | `DEFAULT_BRANCH = "cross-platform-builds"` in `VoiceSTT/install_kroko.py` — loser Branchbezug, kein Commit-Pin |
| Reproduzierbarkeit | Ein Build zog implizit den jeweiligen Branch-Head; zwei Builds zu verschiedenen Zeitpunkten konnten unterschiedliche Binaries erzeugen, ohne dass irgendetwas das anzeigte |
| Artefakt-Wiederverwendung | Keine. Jeder `stt-install-kroko --build` kompilierte neu (Windows: Docker-Crossbuild, ~30 min) |
| Free/Pro-Trennung | Nur als Build-Flag (`KROKO_LICENSE=ON`); keine getrennte Artefaktablage, keine Prüfung, ob ein vorhandenes Wheel wirklich die erwartete Variante ist |
| Modellauthority | `resolve_kroko_model()` akzeptierte jede Datei, die namentlich passte, aus `VOICESTT_KROKO_MODEL_ROOT` o. ä. — ohne Hash, Lizenzklasse oder Variantenbezug |
| Runtime-Downloads | `auto_download_model` defaultete auf `not offline_models_enabled(...)`, d. h. ein normaler Serverstart lud Modelle selbsttätig von Hugging Face |

## 2. Ermittelte Upstream-Realität (W4A-02, Schritte 1–5)

Der tatsächlich verwendete und bereits qualifizierte Kroko-Checkout liegt unter
`%LOCALAPPDATA%\VoiceSTT\kroko-builder\kroko-onnx`:

| Feld | Wert |
|---|---|
| Remote | `https://github.com/kroko-ai/kroko-onnx.git` |
| Branch | `cross-platform-builds` |
| **Qualifizierter Commit** | **`8657e655192623b98d7708e742a72987f953d3a2`** (2026-05-28, „Merge remote-tracking branch 'origin/master' into cross-platform-builds") |
| Submodule | keine (`.gitmodules` nicht vorhanden) |
| Git LFS | nicht verwendet |
| Lokale Modifikationen | genau 3 Dateien — `build_windows.bat`, `Dockerfile.windows`, `sherpa-onnx/csrc/license.h` — exakt die von `install_kroko.py` gepatchten Dateien |

`git ls-remote` zum Prüfzeitpunkt: `refs/heads/cross-platform-builds` steht
aktuell ebenfalls auf `8657e655…`, `refs/heads/master` auf `f572b3b9…`. Dass
Branch-Head und qualifizierter Commit hier zufällig übereinstimmen, ändert
nichts am Befund: ein Branchname ist keine reproduzierbare Authority, weil er
sich jederzeit bewegen kann, ohne dass ein Build das bemerkt.

**Buildweg Free/Pro:** Windows baut über Kroko's eigenen Docker-Workflow
(`build_windows.bat` → `Dockerfile.windows` → `in_windows_container.sh`,
delvewheel-Repair); Linux baut nativ über `pip wheel` mit den
`SHERPA_ONNX_*`-CMake-Flags. `--variant pro` setzt ausschließlich
`KROKO_LICENSE=ON` — **kein Key im Buildpfad** (siehe §6).

## 3. Immutable Pin (W4A-02)

`VoiceSTT/kroko/buildinputs.py` ist die neue, source-controlled Authority:

```python
KROKO_UPSTREAM_REPO     = "https://github.com/kroko-ai/kroko-onnx.git"
KROKO_UPSTREAM_REVISION = "8657e655192623b98d7708e742a72987f953d3a2"
KROKO_UPSTREAM_BRANCH_HINT = "cross-platform-builds"   # nur Clone-Startpunkt
```

`install_kroko.prepare_checkout()` ruft jetzt `ensure_pinned_revision()` auf:
Es checkt den gepinnten Commit explizit aus (`git checkout --detach <sha>`,
bei Bedarf mit vorherigem `git fetch origin <sha>`) und **verifiziert danach
per `git rev-parse HEAD`**, dass der Checkout wirklich dort steht — sonst
harter Fehler. Ein Build kann damit nicht mehr versehentlich „latest branch
head" verwenden.

Ein bewusstes Upstream-Upgrade ist eine Änderung von `KROKO_UPSTREAM_REVISION`
und erzeugt dadurch automatisch einen neuen Fingerprint (Test:
`test_upstream_revision_changes_the_fingerprint`).

## 4. Build-Fingerprint (W4A-03)

`VoiceSTT/kroko/fingerprint.py`. Deterministische Serialisierung über
`json.dumps(sort_keys=True, separators=(",",":"))`, Hash = SHA-256, ID = erste
16 Hex-Zeichen.

### Enthaltene Inputs

| Input | Begründung |
|---|---|
| `upstream.repo` + `upstream.revision` | die Quelle des kompilierten Codes |
| `variant` (`free`/`pro`) | unterschiedliche Runtime-Fähigkeiten, unterschiedliche Binaries |
| `target.platform`, `target.architecture` | Zielplattform des Wheels |
| `python.tag`, `python.abi` | native Extension ist ABI-gebunden |
| `build.cmakeFlags`, `build.makeArgs` | ändern die Kompilierung direkt |
| `build.proLicenseEnabled` | Free-/Pro-Schalter |
| `build.patchSetRevision` | VoiceSTT-eigene Patches am Upstream (siehe §5) |
| `build.builderRevision` | VoiceSTT-eigene Builderlogik: Checkout, Patchanwendung, Build-Aufruf, Wheel-Auswahl (siehe §5) |
| `toolchain` | buildwirksame Toolchain-Identität (siehe unten) |
| `schemaVersion` | Bedeutungsänderung der Inputs invalidiert bewusst alles |

### Bewusst NICHT enthalten

FastAPI-/Serverlogik, Wake-Word-Code, Docs, README, sonstige VoiceSTT-Dateien
und insbesondere die Produktversion aus `VERSION` / `VOICESTT_BUILD_VERSION`
(W3). Das ist strukturell garantiert, nicht nur per Konvention: der Fingerprint
liest **keine einzige Datei**. Der Test
`test_computing_a_fingerprint_reads_no_source_file` patcht `builtins.open` und
belegt, dass beim Berechnen kein Dateizugriff stattfindet — damit kann kein
Quelltext-Edit den Fingerprint beeinflussen.

### Toolchain-Identität — eine bewusste Designentscheidung

Für `target.platform == "windows"` ist die Toolchain **hostunabhängig**
(`{"kind": "kroko-docker-windows-crossbuild", "definedBy": "upstream-revision+patch-set"}`).
Grund: das Windows-Wheel wird in Kroko's eigenem Docker-Image cross-gebaut;
Compiler, CMake und OpenSSL kommen also aus dem gepinnten Upstream plus
Patch-Set, nicht vom Host. Würde man dort Host-Toolversionen aufnehmen, hätten
zwei Maschinen unterschiedliche Fingerprints für byte-gleichwertige Wheels und
die Wiederverwendung wäre praktisch wertlos.

Für Linux (nativer Build gegen Host-Tools) ist die Toolchain ein echter
Buildinput; sie wird als expliziter Parameter übergeben, damit der Fingerprint
deterministisch und testbar bleibt statt still von der Testumgebung abzuhängen.

### Gemessene Werte in dieser Umgebung

| Variante | Fingerprint |
|---|---|
| `free` (windows/amd64/cp312) | `32c947609a9be925` |
| `pro` (windows/amd64/cp312) | `1a447cbd22b3cf0b` |

### Vollständige Abdeckungsprüfung buildwirksamer Inputs (Root-Check)

Der Umstand, dass der Fingerprint **keine Dateien liest**, ist die Abgrenzung
gegen normalen VoiceSTT-Code — er darf aber nicht dazu führen, dass
VoiceSTT-spezifische Kroko-Buildinputs aus dem Fingerprint herausfallen. Diese
Richtung wird deshalb explizit und geschlossen nachgewiesen durch
`BuildInputCoverageTests::test_every_build_effective_input_changes_the_fingerprint`.
Der Test mutiert je genau einen Input und verlangt eine Fingerprint-Änderung:

| # | Buildwirksamer Input | Mutation im Test | Fingerprint ändert sich |
|---|---|---|---|
| 1 | Kroko-Upstream-Revision | `KROKO_UPSTREAM_REVISION` → `000…0` | ja |
| 2 | Kroko-Upstream-Repo | `KROKO_UPSTREAM_REPO` → Fork-URL | ja |
| 3 | `free\|pro` | `variant` → `pro` | ja |
| 4 | Zielplattform | `linux` → `windows` | ja |
| 5 | Architektur | `amd64` → `arm64` | ja |
| 6 | Python-Tag | `cp312` → `cp311` | ja |
| 7 | Python-ABI allein | `abi` → `cp312d` | ja |
| 8 | CMake-Flags | `LINUX_CMAKE_FLAGS` → GPU=ON | ja |
| 9 | Make-Args | `LINUX_MAKE_ARGS` → `-j99` | ja |
| 10 | Compiler-/Toolchain-Identität | `cmake 3.28` → `3.31` | ja |
| 11 | VoiceSTT-Kroko-Patches | `PATCH_SET_REVISION` → 42 | ja |
| 12 | VoiceSTT-Builderlogik | `BUILDER_REVISION` → 42 | ja |
| 13 | Fingerprint-Schema | `FINGERPRINT_SCHEMA_VERSION` → 99 | ja |

**Gegenbeweis** (`test_ordinary_voicestt_changes_leave_the_fingerprint_identical`):
Ein Produktversions-Bump über `VOICESTT_BUILD_VERSION` (`resolve_version()`
liefert nachweislich `77.66.55`) lässt den Fingerprint **identisch**; zusätzlich
wird im selben Test belegt, dass die Berechnung keine einzige Datei öffnet —
Server-, Wake-, Docs- und README-Quellen können ihn also gar nicht erreichen.

## 5. VoiceSTT-eigene buildwirksame Logik: zwei deklarierte Revisionen

VoiceSTT beeinflusst das erzeugte Binary auf zwei Wegen, die beide Buildinputs
sind und beide als **deklarierte Revision** im Fingerprint stehen:

| Konstante | Deckt ab | Guard-Fläche |
|---|---|---|
| `PATCH_SET_REVISION` | Was an den Upstream-**Quellen** gepatcht wird: `SHERPA_ONNX_ENABLE_WEBSOCKET=ON`, ersetzte OpenSSL-Beschaffung, gekapselte native Lizenzausgabe | `patch_windows_bat`, `patch_windows_dockerfile`, `patch_windows_container_script`, `patch_license_quiet_env`, `_wrap_license_output_line`, `_insert_after_line` |
| `BUILDER_REVISION` | **Wie** gebaut wird: welche Revision ausgecheckt wird, welche Patches angewandt werden, wie der Compiler aufgerufen wird, welches erzeugte Wheel zum Artefakt wird | `prepare_checkout`, `ensure_pinned_revision`, `prepare_windows_checkout`, `linux_build_env`, `build_linux_wheel`, `build_windows_wheel`, `build_wheel`, `find_linux_wheel`, `find_windows_wheel` |

### Warum deklarierte Werte statt Content-Hash der Dateien

Ein Content-Hash über `install_kroko.py` würde bei jedem Kommentar, jeder
Logzeile und jeder CLI-Hilfetext-Änderung einen 30-Minuten-Build entwerten.
Deklarierte Revisionen invalidieren dagegen genau dann, wenn es fachlich nötig
ist. Der Preis dieser Wahl ist eine Updatepflicht — und die ist **erzwungen,
nicht erhofft**.

### Erzwungene Updatepflicht (Guard)

`BuildEffectiveLogicGuardTests` hasht den Quelltext beider Flächen getrennt und
vergleicht gegen je einen gepinnten Digest:

- Patch-Fläche: `0d716f36…` ↔ `PATCH_SET_REVISION = 1`
- Builder-Fläche: `cdb72891…` ↔ `BUILDER_REVISION = 1`

Ändert sich eine Fläche ohne Bump, schlägt der Test fehl und nennt im
Fehlertext exakt die zu erhöhende Konstante und den nachzuziehenden Digest.

**Der Guard wurde in diesem Lauf negativ verifiziert**, nicht nur „grün
gesehen": eine simulierte buildwirksame Änderung in `linux_build_env`
(zusätzliche `SHERPA_ONNX_EXTRA`-Env-Variable) ließ
`test_builder_surface_matches_its_declared_revision` erwartungsgemäß fehlschlagen
(`1d379e05…` ≠ `cdb72891…`); nach Rücknahme der Änderung war der Test wieder
grün. Ein Guard, der nur jemals besteht, würde nichts beweisen.

Dieses Muster entspricht der `CATALOG_REVISION`-Konstante aus W2-C2.

### Herleitung der Builder-Fläche

Die neun Builder-Funktionen wurden nicht geraten, sondern über die Frage
ausgewählt: *Kann eine Änderung hier die Bytes der erzeugten Runtime oder die
Auswahl des erzeugten Artefakts verändern?* Reine Vorbedingungsprüfungen
(`ensure_windows_host`, `ensure_work_dir_writable`) sind bewusst **nicht** Teil
der Fläche — sie können einen Build verhindern, aber sein Ergebnis nicht
verändern.

Diese Lücke wurde erst durch den Root-Check dieses Laufs geschlossen: die erste
Implementierung guardete ausschließlich die Patch-Funktionen, sodass eine
Änderung an Checkout, Build-Aufruf oder Wheel-Auswahl den Fingerprint
unverändert gelassen hätte und ein veraltetes Artefakt wiederverwendet worden
wäre.

## 6. Free-/Pro-Lizenzgrenze (W4A-01)

- **Build:** `--variant pro` setzt nur `KROKO_LICENSE=ON`. Der Pro-**Key** wird
  zum Bauen nicht benötigt und nie in die Buildumgebung gelegt (Test:
  `test_pro_build_environment_carries_no_key`). Die im Prompt vorgesehene
  `STATUS: BLOCKED`-Eskalation für den Fall, dass das Kroko-Buildsystem
  überraschend doch einen Key verlangt, war nicht nötig.
- **Runtime:** Der Key wird ausschließlich zur Laufzeit aus
  `transcription_engine_options.key` bzw. `KROKO_API_KEY` / `KROKO_ONNX_KEY` /
  `VOICESTT_KROKO_ONNX_KEY` / `KROKO_KEY` gelesen — unverändert gegenüber vor
  W4A.
- **Ein Key macht keine Free-Runtime zu Pro:** Die Variante wird aus dem
  Artefakt selbst gelesen (Wheel-`Build:`-Tag `1free`/`1pro`), nicht aus der
  Anwesenheit eines Keys. `verify_installed_runtime("pro")` gegen die real
  installierte Free-Runtime meldet korrekt
  `installed Kroko runtime variant 'free' does not match the expected 'pro'`.

## 7. W3-Integration (W4A-10)

| W3-Vertrag | Status nach W4A |
|---|---|
| Produktversion kommt aus `VERSION`/`VoiceSTT._version` | unverändert; W4A fasst weder Datei noch Resolver an |
| `VOICESTT_BUILD_VERSION` darf Kroko nicht neu kompilieren | belegt durch `test_product_version_is_not_part_of_the_fingerprint`: bei gesetztem Override liefert `resolve_version()` `99.98.97`, der Fingerprint bleibt identisch und enthält den String nicht |
| Wheel/Sdist enthalten nur freigegebene Ressourcen | W4A fügt genau **eine** Datei hinzu: `VoiceSTT/assets/kroko/models.json` (reine Metadaten). Kein Modell, kein Kroko-Binary im VoiceSTT-Wheel |
| Kein PyPI-Publish / kein Tag | eingehalten |
| Kroko-Identität getrennt von Produktversion | Fingerprint ist eine eigene technische Identität ohne jeden Bezug zur SemVer-Produktversion |

## 8. CI-/Release-Schnittstelle (W4A-11)

Maschinenlesbar, ohne Checkout und ohne Kompilierung:

| Bedarf | Schnittstelle |
|---|---|
| Fingerprint berechnen | `stt-install-kroko --print-fingerprint [--variant …]` → JSON; programmatisch `VoiceSTT.kroko.fingerprint.compute_fingerprint()` |
| Artifact-Existenz prüfen | `stt-install-kroko --describe-artifact` → JSON mit `artifactPresent` |
| Artifact verifizieren | `KrokoArtifactStore.lookup()` verifiziert vollständig, bevor es einen Treffer meldet |
| Free/Pro wählen | `--variant free|pro` |
| Cache-/Artifact-Pfad konfigurieren | `--artifact-store` oder `VOICESTT_KROKO_ARTIFACT_STORE` |
| Bei Miss Builder ausführen | Standardverhalten von `--build` |
| Force-Rebuild | `--rebuild-kroko` |
| Ergebnis maschinenlesbar | `ArtifactRecord.public_dict()`, identisch im `--describe-artifact`-JSON |

Der Store ist ein Dateisystem-Root außerhalb des Repos und damit für einen
GitHub-Actions-Artifact-/Registry-Store oder ein VPS-Verzeichnis geeignet — kein
ephemerer Layercache.

## 9. Neue/Geänderte Dateien

**Neu:**
`VoiceSTT/kroko/__init__.py`, `buildinputs.py`, `fingerprint.py`,
`artifacts.py`, `models.py`; `VoiceSTT/assets/kroko/models.json`;
`tests/unit/test_kroko_fingerprint.py`, `test_kroko_artifact_store.py`,
`test_kroko_model_authority.py`.

**Geändert:**
`VoiceSTT/install_kroko.py` (Pin, Reuse, Force, Store, CI-Interfaces),
`VoiceSTT/transcription_engines/kroko_onnx_engine.py` (Download-Gate,
Fehlermeldung), `setup.py` (Manifest als package_data), `build/BUILD.md`,
`docs/engines/kroko-onnx.md`, `RELEASE_NOTES.md`,
`tests/unit/test_kroko_onnx_engine.py` (neuer Download-Vertrag).
