# AP-SRV-070 — W3 — Packaging Report

**Datum:** 2026-08-30
**Teilblock:** W3-03 / W3-04 / W3-07 / W3-09 — wheel/sdist, Wake-Asset-Gate, Kandidaten-Build, PyPI-Preflight

---

## 0. Build-Umgebung — Docker-Ausfall und Fallback

Der Prompt bevorzugt einen disposable Python-Container für die isolierten
Install-Smokes. Docker war in dieser Umgebung während des gesamten Laufs
**nicht nutzbar**, unabhängig vom Image:

- `docker pull hello-world` (kleinstmögliches Image) hing > 60 s ohne jede
  Ausgabe (Timeout).
- `docker run --rm <bereits lokal vorhandenes Image ohne Pull-Bedarf> echo ...`
  hing ebenfalls > 30 s ohne Ausgabe (Timeout).
- `docker info` / `docker images` funktionierten normal — nur die
  Container-Runtime selbst (Pull **und** Run) hing.

Damit ist es kein Problem des `python:3.12-slim`-Images, sondern ein
Ausfall der Docker-Runtime in dieser Sitzung. Gemäß der im Prompt selbst
vorgesehenen Ausweichoption:

> „... oder eine andere vollständig temporäre, nach dem Test verworfene
> Umgebung."

wurden Build und Installed-Artifact-Smoke stattdessen in **temporären,
außerhalb des Worktrees liegenden venvs** durchgeführt (`build_venv` für
Build-Tooling, `install_venv` für den Install-Smoke), beide nach Abschluss
des Laufs vollständig gelöscht. Keine dieser venvs ist Teil des Repos oder
persistent.

Eine Konsequenz dieses Fallbacks: der "keine Runtime-Downloads"-Nachweis
(Punkt 14 des Installed-Artifact-Smokes) konnte nicht operational über
`docker run --network none` erzwungen werden. Siehe
`2026-08-30_W3_INSTALLED_ARTIFACT_REPORT.md` für den kompensierenden
Nachweis (statische Prüfung + Erfolg aller Asset-/Katalog-Checks rein aus
lokalen Dateien).

## 1. Build-Fix: PEP 517 sys.path (während dieses Laufs gefunden und behoben)

Der erste Build-Versuch schlug fehl:

```
ModuleNotFoundError: No module named 'VoiceSTT'
```

Ursache: ein PEP-517-Build-Backend (`python -m build`) execut `setup.py`
nicht wie ein direkter `python setup.py ...`-Aufruf — das Projektverzeichnis
landet dabei nicht automatisch auf `sys.path`. `setup.py` importiert aber
die zwei Repository-Root-Hilfsmodule (`VoiceSTT._version`,
`wakeword_package_resources`) als Sibling-Module. Fix: `setup.py` fügt sein
eigenes Verzeichnis explizit vorne an `sys.path` an, bevor es diese Module
importiert (siehe `setup.py`, Kommentar "A PEP 517 in-process build backend
..."). Nach dem Fix bauen Wheel und Sdist ohne Workaround.

## 2. PEP 440 vs. SemVer beim Override (Konstruktionsdetail, dokumentiert)

`VOICESTT_BUILD_VERSION` wird gegen die volle SemVer-2.0.0-Grammatik
validiert (inkl. Bindestrich-Prerelease, z. B. `9.9.9-candidate.1`).
`setuptools`/`packaging.version.Version` normalisiert Versionen jedoch nach
**PEP 440**, das eine SemVer-Bindestrich-Prerelease-Syntax **nicht**
akzeptiert (`InvalidVersion: '9.9.9-candidate.1'`). Ein solcher Override
lässt sich also validieren, aber nicht tatsächlich in ein Wheel/Sdist
einbetten.

Für den W3-07-Kandidaten-Nachweis wurde daher ein PEP-440-kompatibler,
gültiger SemVer-Override verwendet: **`9.9.9`** (reine Release-Form, kein
Prerelease-Suffix) — genau die Form, die der spätere `release.py`
(`patch`/`--minor`/`--major`) ohnehin ausschließlich erzeugt. Kein
Scope-Problem für W3/W5/W6, aber als bewusste Randbedingung für einen
künftigen, expliziten Prerelease-Kandidaten-Workflow dokumentiert.

## 3. Baseline-Build (`VERSION`-Authority, `2.0.0`)

| Datei | SHA-256 | Bytes |
|---|---|---|
| `voicestt-2.0.0-py3-none-any.whl` | `3bff4ec39fec38566ce13ea9533ee91f829d7b4a8957fcee8cbc6a4df40167a6` | 30 016 076 |
| `voicestt-2.0.0.tar.gz` | `9ea617574544ab826eb567772fc43a5c1dcb3f8abb651f91cebd1e7858307d96` | 29 799 960 |

- `twine check`: **PASSED** (beide Dateien).
- `METADATA`/`PKG-INFO` Version: `2.0.0` — identisch zur Authority.
- Wake-Asset-Dateien in Wheel **und** Sdist: **56** (`models.json` + 50
  Classifier-Artefakte [25 × onnx/tflite] + 4 Pipeline-Artefakte + 1
  Auxiliary-Asset), exakte Übereinstimmung mit
  `wakeword_package_resources.bundled_package_data_files()` (`wakeAssetsMatchAuthority: true`
  für Wheel und Sdist, siehe `evidence_artifacts/2026-08-30_W3_dist_inspection.json`).
- Console Entry Points im Wheel (`entry_points.txt`): `stt`,
  `stt-install-kroko`, `stt-server`, `stt-server-legacy` — vollständig,
  unverändert zum Quellcode.
- Sdist enthält `VERSION` und `wakeword_package_resources.py` — eigenständig
  aus dem Sdist heraus wieder baubar (`hasVersionFile: true`,
  `hasWakewordPackageResourcesHelper: true`).

## 4. Kandidaten-Build (`VOICESTT_BUILD_VERSION=9.9.9`, W3-07-Nachweis)

| Datei | SHA-256 | Bytes |
|---|---|---|
| `voicestt-9.9.9-py3-none-any.whl` | `1eaf630321637814aba740b057d52cb4210597ca3a33717932f277a28f45fa6f` | 30 016 076 |
| `voicestt-9.9.9.tar.gz` | `1361d39dd7f73664a8a57b3353f5345ff3d389325cad433d4188ef7ff30a542b` | 29 799 952 |

- `twine check`: **PASSED**.
- `METADATA`/`PKG-INFO` Version: `9.9.9` — exakt der injizierte Override,
  identisch in Wheel und Sdist.
- **`VERSION`-Datei im Source-Baum vor und nach dem Kandidaten-Build
  bytegenau identisch** (`diff` ohne Ausgabe) — kein dauerhafter
  Versionsverbrauch durch einen Kandidaten-Build.
- Kein Git-Tag, kein Release erzeugt.

## 5. Reproduktions-Build (`baseline-repeat`, gleiche Eingabe)

| Datei | SHA-256 | Bytes |
|---|---|---|
| `voicestt-2.0.0-py3-none-any.whl` | `5a16da029449a857c9161e9801086efee268123d8205dcc200111fa8ee9ece83` | 30 016 076 (identisch) |
| `voicestt-2.0.0.tar.gz` | `d904cbb039e217aed18d2a4c2f840b6550321320b575e29b97c510b4dd413cbe` | 29 800 040 |

`twine check`: PASSED. Gleiche Version, gleiche Dateiliste, gleiche
Byte-Größe (Wheel) — die SHA-256-Werte selbst unterscheiden sich zwischen
den zwei Baseline-Builds (zip/tar betten Zeitstempel ein; kein
`SOURCE_DATE_EPOCH` gesetzt). Das ist **kein** W3-Gate-Verstoß: der Prompt
verlangt Determinismus für die **Versionsberechnung** (`resolve_version()`
— siehe Test `test_repeated_resolution_without_a_release_in_between_is_deterministic`),
nicht bytegenaue Archiv-Reproduzierbarkeit. Inhalt (Version, Dateiliste,
Wake-Asset-Auswahl) ist über alle drei Builds hinweg identisch.

## 6. Wake-Asset-Gate (W3-04)

`python tools/sync_wakeword_assets.py --source ... --check` wurde für W3
**nicht** erneut ausgeführt: die externe Maintenance-Source
(`S:\MODELS\openwakeword\resources\models\all_models`) ist auf dieser
Maschine in dieser Sitzung nicht referenziert worden, und W2-C2 hat den
`--check`-Nachweis bereits gegen den unveränderten committeten
Bundle-Stand mit Exit 0 erbracht (siehe `Runs/W2-C2`). Da W3 den Bundle
selbst nicht verändert (nur die *Packaging-Auswahl* dieses Bundles), bleibt
dieser Nachweis gültig.

Der W3-eigene Beitrag ist das **Packaging-Gate**: `setup.py` wählt
Package-Data nicht mehr über `assets/wakeword_models/*.onnx` /
`*.tflite`-Globs, sondern über `wakeword_package_resources.bundled_package_data_files()`,
das ausschließlich aus dem committeten `models.json` plus der bekannten
Auxiliary-Liste (`silero_vad.onnx`) ableitet. Nachweis, dass die drei
physisch vorhandenen, nicht manifestierten historischen Varianten
(`Jarvis.onnx`, `jarvis_v1.onnx`, `hey_jarvis_v0.1.onnx`, je mit
`.tflite`-Pendant) **nicht** im Wheel/Sdist enthalten sind:

- Statisch: `tests/unit/test_wakeword_package_resources.py::BundledPackageDataFilesTests::test_excludes_every_known_unmanifested_historical_variant` (PASSED).
- Am gebauten Artefakt: `evidence_artifacts/2026-08-30_W3_dist_inspection.json`
  — `wakeAssetFileCount: 56` für Wheel und Sdist beider Builds, kein
  Eintrag der sechs verbotenen Dateinamen.
- Installiert: siehe `2026-08-30_W3_INSTALLED_ARTIFACT_REPORT.md`,
  `no_unmanifested_historical_variants_leaked`.

Die sechs historischen Dateien bleiben unverändert im Source-Repository
(bewusst nicht gelöscht, siehe Prompt: „Diese Dateien müssen nicht aus dem
Source-Repository gelöscht werden") — sie sind nur nicht mehr Teil der
öffentlichen Package-Data-Auswahl.

## 7. PyPI-Preflight (W3-09, kein Publish)

| Prüfung | Ergebnis |
|---|---|
| Distributionsname `voicestt` auf PyPI | `GET https://pypi.org/pypi/voicestt/json` → **HTTP 404** (Name frei, nicht reserviert). Rein lesend, kein Claim/Reservierung. |
| `twine check` | PASSED für alle drei Builds (Wheel + Sdist je) |
| README/`long_description` renderbar | Bestanden über `twine check` (Markdown-Rendering-Gate von `readme_renderer`) |
| Wheel-/Sdist-Dateinamen | `voicestt-<version>-py3-none-any.whl`, `voicestt-<version>.tar.gz` — korrektes PEP 427/PEP 625-Namensschema |
| Version korrekt | Baseline `2.0.0`, Kandidat `9.9.9` — je exakt in `METADATA`/`PKG-INFO` |
| Keine lokalen Pfade | Gescannt (`C:\Users`, `P:\GithubRepos`, `/p/GithubRepos`) — **keine Treffer** in Wheel oder Sdist |
| Keine Secrets | Gescannt (`api_key`, `apikey`, `secret`, private-key-Marker) — nur Quellcode-Identifier/Feldnamen (z. B. `admin_api_key`-Handling, Secret-Redaction-Code), keine tatsächlichen Credential-Werte |
| Keine Build-/Test-/Agent-Evidence im Artefakt | Sdist-Dateiliste geprüft (`evidence_artifacts/2026-08-30_W3_dist_inspection.json`) — keine `tests/`, `Runs/`, `docs/.archiv/` o. ä. enthalten (MANIFEST.in `prune`-Regeln und `find_packages`-Scope schließen das aus) |
| Keine unerwartet großen Source-Dateien | Sdist-Scan: keine Datei > 3 MB außerhalb der manifestierten Wake-Assets |
| Keine unmanifestierten historischen Wake-Artefakte | Siehe §6 |

Kein Netzwerk-Publish, kein `twine upload`, kein Tag.

## 8. Scope-Einhaltung

Kein PyPI-Publish, kein Git-Tag, kein GitHub Release, kein
GHCR/Docker-Hub-Publish, keine Docker-Produktisierung, keine vollständige
Release-State-Machine. Die 9.9.9-Kandidaten-Artefakte existieren nur lokal
im (inzwischen verworfenen) `dist_out/candidate`-Scratch-Verzeichnis; sie
wurden nirgendwo veröffentlicht oder committet.
