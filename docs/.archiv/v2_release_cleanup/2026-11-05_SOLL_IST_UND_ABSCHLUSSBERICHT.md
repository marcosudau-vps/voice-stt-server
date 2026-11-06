# Soll/Ist-Prüfung und Abschlussbericht – V2 Pre-Release-Cleanup + V2-Code-Referenz

Datum: 2026-11-05
Repository: `marcosudau-vps/voice-stt-server`
Basis: `feat/einheitliche-triggerarchitektur-distributed` @ `4f30c0fda9da6470333cad996c13865c31e6474e` (beim Start per `git fetch` verifiziert, keine Abweichung zum Auftrag)
Arbeitsbranch: `feat/v2-release-cleanup`
Geprüfter Code-/Doku-Stand erster Lauf: `c2b2d7d`. **Finaler Stand nach dem
Abschlussauftrag (zweiter Lauf): siehe „Teil 2“ am Ende dieser Datei.** Die
Abschnitte 1–6 dokumentieren den ersten Lauf und bleiben als Historie stehen.
Draft-PR: https://github.com/marcosudau-vps/voice-stt-server/pull/18
Review-Status: `REVIEW_READY` (eingereicht). **Kein** `ROOT_PASS`, **keine** Freigabe, **kein** Merge, **keine** Veröffentlichung.

## 1. Soll/Ist je Arbeitspaket

| AP | Soll | Ist | Status |
| --- | --- | --- | --- |
| CLN-000 | Baseline, Cross-References, Risiko, Mapping, Testmatrix, geschützte Doku | `2026-11-04_AP-CLN-000_BASELINE_UND_MATRIX.md`, Blob-Liste `2026-11-04_GESCHUETZTE_DOKUMENTATION_BASELINE.tsv` (259 Dateien) | COMPLETE |
| CLN-010 | Engineering-Konsolidierung unter `engineering/`, nur wo Verträge erhalten bleiben | Alle Kandidaten geprüft; **kein** Move sicher möglich (Begründung je Ordner in `2026-11-05_AP-CLN-010-020_ENTSCHEIDUNGEN.md`). Stattdessen Regressionsnetz `tests/unit/test_engineering_path_contract.py` (14 Tests / 39 Subtests) für Workflow-Skriptpfade, Root-Einstiege, Console-Scripts, Release-Autoritätspfade, Dockerfile-`COPY`, Compose-Kontext, `MANIFEST.in` | PARTIAL – Zielstruktur nicht erreicht, bewusst `NICHT_SICHER`/`NACH_V2` |
| CLN-020 | Beispiele nach `examples/`, Altlasten mit Beleg entfernen | `examples/` ist in `.gitignore` ausgeschlossen; alle `app_*` haben Test-/Packaging-/Doku-Bindungen → `NACH_V2`. Keine getrackten Altlasten gefunden → nichts gelöscht | PARTIAL – geprüft, keine sichere Maßnahme |
| CLN-030 | Alt-Doku unverändert, technische Pfade funktionsfähig | Da nichts verschoben wurde, entstehen **keine** neuen Pfad-/Doku-Divergenzen. Alle 259 geschützten Dateien Blob-identisch (Abschnitt 3) | COMPLETE |
| DOC-V2-100 | Eigenständige, code-abgeleitete V2-Referenz (13 Seiten) | `docs/v2-code-reference/` mit README + 12 Fachseiten, jede mit „Primäre Quellen“; mechanischer Abdeckungstest `tests/unit/test_v2_code_reference.py` | COMPLETE (mit dokumentierten Teil-Lücken, Seite 12) |
| CLN-040 | Regression, Sicherheitsprüfung, Bericht, PR | dieser Bericht, Tests Abschnitt 4, PR #18 | COMPLETE (Restpunkte Abschnitt 6) |

## 2. Alt→Neu-Matrix (final)

Keine Verschiebung durchgeführt. Vollständige Matrix mit Begründung:
`2026-11-05_AP-CLN-010-020_ENTSCHEIDUNGEN.md`.

Hinzugefügte Dateien (`git diff --name-status 4f30c0f..c2b2d7d`, ausschließlich `A`):

- `docs/.archiv/v2_release_cleanup/` – 4 Dateien (+ dieser Bericht)
- `docs/v2-code-reference/` – 13 Dateien
- `tests/unit/test_engineering_path_contract.py`
- `tests/unit/test_v2_code_reference.py`

Laufzeit-/Build-/CI-Dateien geändert: **keine**.

## 3. Nachweis unveränderter Alt-Dokumentation

Befehl (Ergebnis `protected_fail=0 count=259`):

```bash
while IFS=$'\t' read -r blob path; do
  [ "$(git rev-parse "HEAD:$path")" = "$blob" ] || echo "CHANGED $path"
done < docs/.archiv/v2_release_cleanup/2026-11-04_GESCHUETZTE_DOKUMENTATION_BASELINE.tsv
```

Zusätzlich: `git diff --name-status 4f30c0f..HEAD -- '*.md' '*.MD' '*.rst'`
zeigt ausschließlich `A`-Einträge unter `docs/v2-code-reference/` und
`docs/.archiv/v2_release_cleanup/`. `AGENTS.md`,
`docs/.archiv/README.md`, `build/BUILD.md`, `build/vps/*.md` sowie die drei
HTML-Dateien (`VoiceSTT_server/index.html`,
`api_fastapi_server/static/index.html`, `app_browserclient/index.html`) sind
unverändert.

Alt-Dokumentation nachweislich unverändert: **JA**.

## 4. Tests und Prüfungen

Umgebung lokal: Linux, Python 3.12 (venv), CPU-Torch, `portaudio19-dev`,
keine Modelldateien, kein Netzwerkzugriff auf Produktionssysteme.

| Prüfung | Befehl | SHA | Ergebnis |
| --- | --- | --- | --- |
| Gesamtsuite (Basis + Pfadtest) | `python -m pytest -q -p no:cacheprovider tests/unit tests/compatibility` | `0a15520` + Pfadtest | PASS – 2341 passed, 24 skipped, 1362 subtests, 9:31 min |
| Gesamtsuite final | wie oben | `c2b2d7d` | siehe Abschnitt 4a |
| Packaging | `python -m pytest -q -p no:cacheprovider tests/packaging` | `c2b2d7d` | siehe Abschnitt 4a |
| Neue Tests + Doku-Oberfläche | `pytest tests/unit/test_v2_code_reference.py tests/unit/test_docs_surface.py tests/unit/test_engineering_path_contract.py` | `c2b2d7d` | PASS – 53 passed, 121 subtests |
| Server-Smoke ohne Modelle | `voice-stt-server --host 127.0.0.1 --port 8765 --data-root <tmp> --no-model-warmup` | `0a15520` (Code identisch zu `c2b2d7d`) | PASS – `/api/v2/info`, `/health` (`ready:false`), `/api/v2/wake-words`, `/api/v2/settings/server`, `/v1/models` antworten; `PATCH /api/config` von Loopback `200` |
| CLI | `voice-stt-server --help`, `python release.py --help`, `python tools/build_production.py --help` | – | PASS |
| Release-Preflight | `python release.py preflight` | `0a15520` | erwartetes FAIL (Exit 1): `git_clean_tree` (damals unversionierte Testdatei) und `dockerhub_repo_configured` (lokal nicht konfiguriert); keine Schreiboperation. Siehe 4a für den Lauf auf sauberem Baum |
| Release-`dry-run` | – | – | NOT_RUN – Standard-Adapter fragen externe Registries/PyPI lesend ab; ausgelassen gemäß Auftrag (keine externen Calls). Abgedeckt durch `tests/unit/test_release_pipeline.py`/`test_release_engine.py` mit Fake-Adaptern (in der Gesamtsuite PASS) |
| Docker-Build | – | – | NOT_RUN – benötigt vorab gebautes Wheel + Kroko-Artefakt; nur Vertragstests (`test_production_docker_contract.py`, PASS) |
| GitHub-CI Linux | Workflow `CI` | `721c13b` | alle Schritte `success` inkl. Unit-, Packaging-Tests und `git diff --check` (Job am Ende durch Concurrency als `cancelled` markiert) – Run https://github.com/marcosudau-vps/voice-stt-server/actions/runs/41938928706 |
| GitHub-CI final | Workflow `CI` | `c2b2d7d` / Bericht-Commit | siehe Abschnitt 4a |

### 4a. Abschlussläufe (erster Lauf, Stand `c2b2d7d`)

| Prüfung | Ergebnis |
| --- | --- |
| `pytest tests/unit tests/compatibility` | PASS – 2350 passed, 24 skipped, 1402 subtests (9:31 min) |
| `pytest tests/packaging` (erster Versuch) | FAIL – 32 failed: lokale venv ohne Modul `build` (Umgebungsfehler, keine Codeursache) |
| `pytest tests/packaging` (nach `pip install build wheel`) | PASS – 33 passed (5:22 min) |
| `python release.py preflight` (sauberer Baum) | Exit 1 – einziges FAIL `dockerhub_repo_configured` (lokal nicht konfiguriert), übrige Checks PASS/WARN |
| GitHub-CI `e423028` PR-Lauf 41940581684 | Ubuntu und Windows SUCCESS |
| GitHub-CI `e423028` Push-Lauf 41940574543 | Ubuntu FAILURE (`No space left on device` beim Installieren der CUDA-Torch-Abhängigkeiten), Windows SUCCESS – Ursache und Behebung siehe Teil 2 |

## 5. Feature-/Quellenmatrix und Abdeckung

Siehe `docs/v2-code-reference/12_feature_und_quellenmatrix.md` (42 Features,
Status getestet/beobachtet/experimentell/blockiert). Mechanisch geprüft:
alle Routen, alle V2-Kommandotypen/Result-Codes/Ereignistypen, alle 19
V2-Settings-Schlüssel, alle registrierten Engine-Namen. Bewusst nicht
vollständig: Feldlisten einzelner V1-Nachrichten (`status`, `timeline`,
`ready`) und die vollständige Parameterliste von `AudioToTextRecorder`.

Während der Code-Analyse festgestellte, **nicht** behobene Auffälligkeiten
(Behebung wäre Verhaltensänderung, außerhalb des Auftrags):

1. `PUT /api/models/active` mappt `RuntimeError` mit dem Text
   „keine WebSocket-Sitzungen“ auf `409`; dieser Text wird im
   Produktionscode nirgends erzeugt → faktisch immer `500`.
2. Kommentar in `docker-compose.yml` nennt `tools/build_production.py
   <free|pro|all>`; die CLI akzeptiert nur `pro|all`.
3. Mit dem ausgelieferten Manifest ist für keines der 23 bekannten Modelle
   Provisionierung erlaubt; `stt_auto_download_enabled` hat derzeit keine
   installierende Wirkung.

## 6. Offene Punkte

| Punkt | Status | Konsequenz |
| --- | --- | --- |
| Engineering-Konsolidierung `engineering/` | NACH_V2 / NICHT_SICHER | benötigt Freigabe für Workflow- und Alt-Doku-Änderungen |
| `app_*` → `examples/` | NACH_V2 | benötigt `.gitignore`-Anpassung und Doku-Pflege |
| Registereintrag `docs/.archiv/README.md` | bewusst nicht erfolgt | siehe `2026-11-04_AUSNAHME_REGISTER_UND_PROZESS.md` |
| Release-`dry-run`, Docker-Build, Release-Candidate-Workflow | NOT_RUN | keine externen Seiteneffekte erlaubt |
| Windows-CI auf finalem SHA | siehe 4a | – |
| Unabhängige Abnahme / Merge | NICHT ERFOLGT | ausstehend |
| V2-Publikation | NICHT ERFOLGT | zusätzlich blockiert durch `build/kroko-redistribution.json: BLOCKED` |

---

# Teil 2 – Abschlussauftrag (zweiter Lauf, 2026-11-05)

Auftrag: verbindliche Engine-Bereinigung, CPU-only-Packaging, Behebung des
CI-Speicherfehlers, tatsächliche Umsetzung von AP-CLN-010/020,
Qualifikation, Aktualisierung von Doku, Akten und PR #18.
Commits dieses Laufs: `f6cadb7` (Engines + CPU-only), `b534e0b`
(Engineering/Beispiele + Doku), `d1fd24a` (Marker-Fix CPU-Check), danach
`7270dde` und dieser Aktenstand (reine Akten-Commits; finaler SHA steht in der PR-Beschreibung, weil ein Commit seinen eigenen SHA nicht enthalten kann).

## T2-1. Status je Arbeitspaket (final)

| AP | Status | Kurzbeleg |
| --- | --- | --- |
| Engine-Produktgrenze | COMPLETE | Factory = `faster_whisper`, `kroko_onnx`; 5 Entwürfe isoliert, 7 entfernt; `tests/unit/test_v2_engine_boundary.py`, Wheel/sdist-Test |
| Packaging/Abhängigkeiten | COMPLETE | Engine-Extras und -Abhängigkeiten entfernt, `torchaudio` entfernt, `prune engineering/examples`; `tests/packaging/test_v2_distribution_contents.py` auf echten Archiven |
| CPU-only | COMPLETE (mit dokumentierter Einschränkung) | `engineering/tools/cpu_only.py`; CI Ubuntu+Windows grün (Lauf 41953317447), RC-Qualifikation, Dockerfile; Einschränkung für schlichtes `pip install` unter Linux (T2-4) |
| CI-Speicherfehler | COMPLETE | Ursache CUDA-Torch-Auflösung entfernt; Ubuntu-Dev-Installation 28 s statt Abbruch |
| AP-CLN-000 | COMPLETE | unverändert (erster Lauf) |
| AP-CLN-010 | COMPLETE (eine begründete Ausnahme) | `engineering/{tools,release,deployment/{docker,vps},drafts}` umgesetzt; `build/kroko-builder.Dockerfile` bleibt (Link-Integritätstest + Fingerprint), daher kein `engineering/build/` |
| AP-CLN-020 | COMPLETE | `examples/` mit allen drei Apps, `.gitignore` korrigiert, Pfade/Importe angepasst |
| AP-CLN-030 | COMPLETE | Alt-Doku inhaltlich unverändert (T2-6); Pfaddivergenzen dokumentiert |
| AP-DOC-V2-100 | COMPLETE | Referenz aktualisiert (Seiten 01, 02, 04, 10, 11, 12) + neue Seite 13 (86 Recorder-Parameter, V1-Nachrichtenfelder, maschinell erzeugt) |
| AP-CLN-040 | COMPLETE | Tests/CI T2-5; Review-Status `REVIEW_READY`, keine Abnahme |

## T2-2. Engines

- **Unterstützt:** `VoiceSTT/transcription_engines/faster_whisper_engine.py`
  (`faster_whisper`), `VoiceSTT/transcription_engines/kroko_onnx_engine.py`
  (`kroko_onnx`).
- **Isolierte Entwürfe** (`engineering/drafts/transcription_engines/`, kein
  `__init__.py`, nicht in `find_packages`, `prune engineering`, kein
  Produktimport – AST-geprüft): `parakeet_engine.py`, `whisper_cpp_engine.py`,
  `openai_api_engine.py`, `openai_whisper_engine.py`, `sherpa_onnx_engine.py`.
- **Entfernt:** `cohere_transcribe_engine.py`, `funasr_engine.py`,
  `granite_speech_engine.py`, `hf_transformers_engines.py`,
  `moonshine_engine.py`, `omnilingual_asr_engine.py`, `qwen3_asr_engine.py`.
- **Registrierung:** `ENGINE_CLASS_PATHS` nur noch zwei Einträge; Aliase
  `kroko`, `banafo_kroko` und alle übrigen Namen entfernt (auch aus
  `stt_model_management.normalize_engine` und `model_size_rank`).
- **Kontrollierte Ablehnung:** `enforce_supported_engines` (in
  `enforce_cpu_model_policy`) vor jedem Import; beobachtet:
  `POST /api/config/validate {"transcription_engine":"whisper_cpp"}` → 400,
  `PUT /api/models/active {"realtime_transcription_engine":"parakeet"}` → 400,
  Fabrik → `UnsupportedTranscriptionEngineError` mit Liste der unterstützten.
- **Öffentliche Capabilities:** beobachtet `GET /api/config` →
  `supportedEngines: ["faster_whisper","kroko_onnx"]`.
- **Hilfsmodule:** `_model_utils.py` auf `attr_or_key`, `first_item`,
  `text_from_output` reduziert (einzige Nutzung: Kroko); `model_resolver.py`
  unverändert (Faster-Whisper + Kroko).
- **Entfallene Tests (nur entfernte/isolierte Engines):**
  `test_additional_transcription_engines.py`, `test_cohere_transcribe_engine.py`,
  `test_granite_speech_engine.py`, `test_moonshine_engine.py`,
  `test_omnilingual_asr_engine.py`, `test_openai_whisper_engine.py`,
  `test_sherpa_onnx_engine.py`, `test_whisper_cpp_engine.py`. Ersetzt durch
  Negativtests in `test_v2_engine_boundary.py`. Gemeinsame Audio-Hilfen für
  den Kroko-Test nach `tests/unit/audio_engine_fixtures.py` extrahiert. Zwei
  Alias-Tests (`test_kroko_onnx_engine.py`, `test_fastapi_server_protocol.py`)
  wurden auf die neue Grenze umgestellt (sie prüfen jetzt die Abwesenheit der
  Aliase).

## T2-3. Packaging und Abhängigkeiten

- Entfernte Extras: `whisper-cpp`, `whispercpp`, `openai-whisper`,
  `sherpa-onnx`, `sherpa`, `transformers`, `moonshine`, `granite`, `cohere`,
  `omnilingual-asr`, `omnilingual`, `meta-omnilingual-asr`, `qwen`,
  `qwen3-asr` (sowie die unbenutzten Listen `parakeet_requirements`,
  `qwen_vllm_requirements`, `all_optional_requirements`).
- Entfernte Abhängigkeiten: `torchaudio` (Basis, `requirements.txt`,
  Dockerfile, `install_windows_cpu.ps1`, VPS-`build-area/requirements.txt`);
  engine-exklusiv `pywhispercpp`, `openai-whisper`, `sherpa-onnx`,
  `transformers`, `nemo_toolkit[asr]`, `omnilingual-asr` (+ gepinntes
  torch/torchaudio 2.8.0), `qwen-asr`.
- Begründung `torchaudio`: `importlib.metadata.requires("silero-vad")`
  verlangt nur `torch` (torchaudio nur in den Extras `all`/`audio`/`test`);
  kein Produktmodul importiert torchaudio; volle Testsuite grün ohne Nutzung.
- Verbleibende CPU-Abhängigkeiten: `torch` (für `torch.multiprocessing` in
  `VoiceSTT/core/initialization.py`/`runtime.py`, PyTorch-Fallback in
  `silero_vad.py`, Abhängigkeit von `silero-vad`), `onnxruntime` (über
  `silero-vad[onnx-cpu]`), `faster-whisper`/`ctranslate2`, `av`, `scipy`,
  `numpy` u. a.
- `setup.py`-Installationstext bereinigt (keine entfernten Engines, Hinweis
  auf CPU-Torch).
- Echte Archive geprüft (`python -m build`): Wheel enthält genau
  `faster_whisper_engine.py` und `kroko_onnx_engine.py`, kein `engineering/`,
  keine `.pyc`; sdist ohne Entwürfe/entfernte Engines; `Provides-Extra` ohne
  Engine-Extras; `Requires-Dist` ohne engine-exklusive Pakete und ohne
  `torchaudio`.
- Release-Candidate-Smoketest prüft zusätzlich je Plattform-Wheel die
  Engine-Dateiliste und das Fehlen von `engineering/`.

## T2-4. CPU-only-Vertrag und CI-Speicherfehler

- **Ursache des Fehlers** (Lauf 41940574543): `pip install -e
  ".[recommended,server]"` löste `torch` von PyPI auf; unter Linux ist das
  die CUDA-Variante mit `nvidia-*`, `cuda-*`, `triton` (lokal reproduziert:
  dieselbe Auflösung ergab `torch 2.15.0+cu132`).
- **Behebung:** `engineering/tools/cpu_only.py install-torch` installiert
  `torch` aus `https://download.pytorch.org/whl/cpu` und schreibt einen
  pip-Constraint; alle Folgeinstallationen laufen mit `PIP_CONSTRAINT`.
  `cpu_only.py check` prüft `torch.version.cuda is None`,
  `torch.version.hip is None`, keine installierten GPU-Laufzeit-Distributionen,
  keine für die aktuelle Plattform aktiven GPU-`Requires-Dist` von `torch`
  und eine CPU-Tensoroperation.
- **Verdrahtung:** CI (Wheel-Smoke + Dev-Umgebung, Ubuntu + Windows),
  `qualify_installed_wheel` (frische venv der RC-Qualifikation), Produktions-
  `Dockerfile` (CPU-Index, Constraint, CUDA-/NVIDIA-Abbruch),
  `install_windows_cpu.ps1` (CPU-Index, ohne torchaudio).
- **Korrektur im Lauf:** Erste Fassung wertete Umgebungsmarker nicht aus und
  scheiterte unter Windows an Linux-only-Einträgen des CPU-Wheels
  (`platform_system == "Linux"`); `d1fd24a` wertet Marker aus
  (Regressionstest ergänzt).
- **Nachweise:** CI Ubuntu (`f6cadb7`, Lauf 41950693576): beide
  CPU-only-Schritte SUCCESS, Dev-Installation 28 s. CI Ubuntu + Windows
  (`7270dde`, Läufe 41953313619/41953317447): beide CPU-only-Schritte je
  Plattform SUCCESS (Windows: `torch 2.15.0+cpu`).
  Lokal: `cpu_only.py check` meldet die (wegen gesperrtem
  `download.pytorch.org`) lokal installierte CUDA-Variante korrekt als
  Verstoß (Negativnachweis); ein positiver lokaler CPU-only-Nachweis ist
  `BLOCKED` durch die Netzwerkrichtlinie dieser Cloud-Umgebung.
- **Verbleibende Einschränkung:** Ein schlichtes `pip install voice-stt-server`
  ohne vorherige CPU-Torch-Installation kann unter Linux weiterhin CUDA-Torch
  ziehen; `install_requires` kann keinen Paketindex vorschreiben. Unterstützte
  Wege: CPU-Torch vorab + Constraint (dokumentiert in Seite 02 der
  V2-Referenz), Container-Image, Windows (PyPI liefert CPU-Wheels).

## T2-5. Tests und CI (final)

| Prüfung | Stand | Ergebnis |
| --- | --- | --- |
| `pytest tests/unit tests/compatibility` | `b534e0b`-Baum | PASS – 2302 passed, 15 skipped, 1506 subtests (8:51 min) |
| gezielte Tests nach Marker-Fix (`test_cpu_only_contract.py`) | `d1fd24a` | PASS – 10 passed |
| `pytest tests/packaging` (inkl. Wheel/sdist-Inhalt) | `b534e0b`-Baum | PASS – 37 passed |
| Server-Smoke ohne Modelle | `b534e0b` | PASS – siehe T2-2; `/v1/models` 200, `/v1/audio/transcriptions` Formatfehler 400, echte Transkription 500 mangels Modell (erwartet, NOT_RUN für echte Inferenz) |
| `python release.py preflight` | `b534e0b`, sauberer Baum | Exit 1 – einziges FAIL `dockerhub_repo_configured` (Umgebung), 13 PASS |
| Alte CLI-Pfade (`python tools/release_candidate.py --help`, `tools/build_production.py --help`, `release.py --help`) | `b534e0b` | PASS |
| Modulidentität `release_tooling.cli is engineering.release.cli` | `b534e0b` | PASS (True) |
| GitHub-CI | `d1fd24a` | PASS – Code-Stand `d1fd24a` = `7270dde` (nur Akten dazwischen): Läufe 41953313619 (push) und 41953317447 (pull_request), je `build-and-test (ubuntu-24.04)` und `build-and-test (windows-latest)` SUCCESS, inkl. Wheel-Build, `twine check`, CPU-only-Prüfung (Smoke + Dev), Unit-/Contract-Suite, `tests/packaging`, `git diff --check`. Frühere Fehlschläge: `f6cadb7`/`b534e0b` Windows (Marker, behoben in `d1fd24a`) |
| Echte Faster-Whisper-/Kroko-Inferenz, Kroko Pro nativ | – | NOT_RUN – keine Modelle/Native-Artefakte in der Cloud-Umgebung; durch Unit-/Integrationstests mit Fakes abgedeckt |
| Docker-Build, Release-Candidate-Workflow, `release.py dry-run` | – | NOT_RUN – keine externen Seiteneffekte; Vertragstests PASS |

## T2-6. Dokumentationsschutz

`git diff -M --name-status 4f30c0f..HEAD -- '*.md' '*.MD' '*.rst'` außerhalb
der beiden genehmigten neuen Ordner: nur
`R100 app_talk_with_llm/README.MD → examples/app_talk_with_llm/README.MD`
(inhaltlich identisch, mit dem Beispielordner verschoben). Alle übrigen 258
geschützten Dateien sind Blob-identisch am alten Ort. Unvermeidliche
historische Pfaddivergenzen (Alt-Doku nennt alte Orte):
`tools/*.py` (funktionsfähig über Shims), `release_tooling` (Alias-Paket),
`build/vps/release-voice-stt.sh` (Wrapper), `build/vps/*.yaml`,
`build/vps/build-area/requirements.txt`, `docker/nginx.conf`,
`Dockerfile.pro-upgrade`, `app_*`-Pfade (jetzt `examples/…`).

## T2-7. Offene Punkte

| Punkt | Status |
| --- | --- |
| Positiver CPU-only-Nachweis lokal | BLOCKED (Netzwerkrichtlinie: `download.pytorch.org` gesperrt); in CI erbracht |
| CPU-only-Garantie für schlichtes `pip install` unter Linux | technisch nicht über Metadaten erreichbar; dokumentiert |
| Echte Inferenz / Kroko Pro nativ / Docker-Build / RC-Workflow | NOT_RUN |
| `engineering/build/` | nicht angelegt (einzige Kandidatendatei aus Integritätsgründen am Root-Ort) |
| Registereintrag `docs/.archiv/README.md` | weiterhin bewusst nicht erfolgt (Ausnahmeakte) |
| Unabhängige Abnahme, Merge, Veröffentlichung | NICHT ERFOLGT; Redistribution weiterhin `BLOCKED` (unverändert) |


---

# Teil 3 – Finale Nachkorrektur vor unabhängiger Abnahme (2026-11-06)

Ausgangsstand: `f03fa5e95041d265175c00c669c2e21b3aa4b8bc`.
Fortsetzung ausschließlich auf `feat/v2-release-cleanup` im bestehenden
Draft-PR #18 gegen `feat/einheitliche-triggerarchitektur-distributed`.
Die Abschnitte der beiden vorherigen Läufe bleiben historische Nachweise.

## T3-1. Tatsächliche Restkorrekturen

- Die drei bisherigen Parakeet-Tuning-Profile aus `TUNING_PROFILES` entfernt.
  Öffentlich bleibt nur `custom` (beide CLI-Aliase erhalten). Allgemeine
  Beam-/Batch-/Timing-/VAD-Werte bleiben einzeln konfigurierbar.
- Den CLI-Hilfetext bereinigt. Unbekannte Profilnamen werden durch argparse
  beziehungsweise die YAML-Prüfung kontrolliert abgelehnt. Ein alter Profilname
  in persistierten Laufzeitsettings verhindert den Start mit einer klaren
  Meldung: `custom` verwenden und allgemeine Tuning-Werte explizit setzen.
  Eine gespeicherte alte Profilbeschreibung wird aus dem gültigen Profil neu
  abgeleitet. Keine automatische Umdeutung alter Profile.
- Den Parakeet-Sonderzweig in `applySettings` entfernt. Engine-/Modellnamen,
  CPU-/Compute-Type, Beam, beide Batch-Größen, Timing, VAD und Wake-Word bleiben
  sichtbar; gemeinsame Modelle behalten die Anzeige „wie final“.
- Den ausführbaren `api_fastapi_server/run_multi_user_perf.cmd` von nicht mehr
  unterstützten Moonshine-Defaults auf Faster-Whisper (`small`/`tiny`, CPU)
  samt passenden Engine-Optionen und Cachepfad umgestellt.
- Alte Profil-Positivtests durch Tests für V2-Defaults, explizite allgemeine
  Tuning-Parameter, CLI-/YAML-/persistierte Profilablehnung, API-Capabilities,
  negative Engine-Auswahl und UI-Parameter ersetzt beziehungsweise erweitert.
  Factory-Regressionsnachweis: kompatible GPU-Argumente werden weiterhin
  angenommen, jedoch vor Engine-Erzeugung auf CPU/Index 0 gesetzt.
- Die zusätzliche Leerzeile am Ende von `audio_engine_fixtures.py` entfernt;
  Whitespace-Prüfung umfasst auch den gesamten PR-Diff gegen `4f30c0f`.

## T3-2. Erhaltene Verträge und gezielte Bestandsprüfung

Die Factory bleibt exakt auf `faster_whisper` und `kroko_onnx` begrenzt.
Die fünf isolierten Engine-Entwürfe, Kroko Community/Pro, Lizenzprüfung,
Modellverwaltung, Recorder, Scheduler, HTTP/WebSocket V1/V2, `/v1/*`,
Authentisierung, Logging und Wake-Word wurden nicht neu organisiert.
Native Fingerprints, Release-State-Machine und Redistribution-Gates bleiben
unverändert. Die öffentliche Redistribution bleibt `BLOCKED`.

Die ausführbaren Dateien unter `VoiceSTT/`, `VoiceSTT_server/`,
`api_fastapi_server/`, `voice_stt_server/` sowie `config.yaml`, `setup.py` und
`requirements.txt` wurden gezielt auf aktive Legacy-Auswahl, Profile,
Sonderbehandlungen und Abhängigkeiten geprüft. Nach der Bereinigung keine
weiteren aktiven Legacy-Engine-Referenzen gefunden. `openai_api_*` bezeichnet
weiterhin die erhaltene OpenAI-kompatible HTTP-Schnittstelle.

GPU-Felder der öffentlichen Recorder-API bleiben kompatibel. Recorder und
Engine-Factory erzwingen CPU; Kroko lehnt GPU-Provider ab; explizite
CUDA-Silero-Auswahl wird vor einem GPU-Ladevorgang abgelehnt. Keine GPU-Pakete
hinzugefügt, keine CPU-only-Prüfung abgeschwächt.

Historische Dokumentation: alle 259 geschützten Dokumente weiterhin
blob-identisch (eins davon unverändert unter dem bereits verschobenen
Beispielpfad). Nur die betroffenen Seiten der neuen V2-Code-Referenz angepasst;
diese bestehende Abschlussakte ausschließlich um Teil 3 ergänzt.

## T3-3. Verbindlicher CPU-only-Installationsweg

Der vorhandene Mechanismus in `engineering/tools/cpu_only.py` und seine
CI-/RC-/Docker-/Windows-Anbindungen bleiben erhalten. Keine Torch-Versions-
experimente und kein Packaging-Umbau.

Die aktuelle Installationsreferenz verlangt jetzt ausdrücklich eine **neue
Python-3.12-venv ohne vorhandenes Torch**, CPU-Torch vom offiziellen CPU-Index,
einen absoluten Constraintpfad, Prüfung vor der Produktinstallation sowie
`pip check` und CPU-only-Prüfung danach. Alle späteren Installationen müssen
denselben Constraint verwenden. Linux- und PowerShell-Ablauf sowie die
Entwicklungsinstallation sind entsprechend beschrieben.

Ein Indexwechsel repariert eine bestehende CUDA-/ROCm-Installation nicht
zuverlässig (`Requirement already satisfied`); dafür ist eine neue venv
vorgesehen. Ein schlichtes Linux-`pip install voice-stt-server` ohne diese
Vorbereitung kann weiterhin CUDA-Abhängigkeiten beziehen. Diese Einschränkung
ist ausdrücklich dokumentiert und kein Freigabenachweis für CPU-only.

## T3-4. Prüfungen der Nachkorrektur

Bestehende Windows-Testumgebung, Python 3.12, CPU-Torch `2.13.0+cpu`.
Keine Tests deaktiviert oder Erwartungen zur Umgehung eines Fehlers gelockert.
Der erste neue API-Test benötigte korrektes Schließen der Service-/SQLite-
Ressourcen unter Windows; dies wurde im Test über `ExitStack` ergänzt.

| Prüfung | Ergebnis |
| --- | --- |
| Syntax/Import | `compileall` für alle vier Produktpakete PASS; Import-/CLI-Prüfungen in der gezielten Suite PASS |
| Gezielte Server-/Engine-/CPU-/Engineering-/Doku-/Silero-Tests | 132 passed, 1 skipped, 297 subtests passed |
| Webinterface | Gesamte Inline-JavaScript-Syntax PASS; tatsächliche Ausführung von `applySettings` mit Node/VM: 8 V2-Konfigurationen (beide Engine-Anordnungen, gemeinsame/getrennte Modelle, Wake-Word an/aus) PASS |
| CPU-only-Nachweis lokal | PASS: keine GPU-Distributionen, `cuda=null`, `hip=null`, keine aktiven GPU-Requirements, CPU-Tensoroperation erfolgreich |
| Vollständige Unit-/Contractsuite | PASS: `python -m pytest -q tests/unit tests/compatibility` – 2309 passed, 16 skipped, 1547 subtests passed, 1 bestehende Starlette/httpx-DeprecationWarning (17:42 min) |
| Packaging | PASS: `python -m pytest -q tests/packaging` – 37 passed (25:28 min) |
| `git diff --check` gegen die PR-Basis | PASS |
| GitHub-CI / Code-Commit | Lokale Qualifikation vollständig PASS; nach Push folgt der versionierte CI-Nachtrag. Der tatsächliche finale PR-HEAD und seine CI werden zusätzlich in PR #18 dokumentiert. |

Echte Modellinferenz, native Pro-Qualifikation, Docker-/RC-Build und
Release-Dry-Run werden durch diesen begrenzten Korrekturlauf nicht neu
qualifiziert. Keine Veröffentlichung, kein Deployment, kein VPS-Zugriff,
kein Merge und keine unabhängige Abnahme erteilt.


## T3-5. GitHub-Nachweis und abschließender Abgabezustand

Fachlicher Code-/Test-/Dokumentationscommit der Nachkorrektur:
`37594b385481ee61f888d3dd3fd1ac1cd3991931`
(`fix(v2): remove active legacy profiles and clarify CPU-only installation`).
Dieser Commit wurde nach vollständiger lokaler Qualifikation normal auf den
bestehenden Branch gepusht. Kein neuer Branch/PR, kein Force-Push.

Die tatsächlich zu diesem SHA gehörenden Läufe sind abgeschlossen:

| Lauf | Ubuntu | Windows |
| --- | --- | --- |
| [Push-CI 42156941999](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/42156941999) | SUCCESS | SUCCESS |
| [PR-CI 42156946996](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/42156946996) | SUCCESS | SUCCESS |

Alle vier Jobs sind grün, einschließlich Wheel/sdist, `twine check`,
Installation des gebauten Wheels, `pip check`, CPU-only-Prüfungen der
Installations- und Entwicklungsumgebung, Unit-/Contracttests,
Packaging-Installationen und CI-`git diff --check`.
Die PR-Joblogs bestätigen auf Ubuntu **2310 passed, 15 skipped, 1547 subtests**
und auf Windows **2309 passed, 16 skipped, 1547 subtests**; auf jeder Plattform
zusätzlich **37 Packaging-Tests bestanden**. Jeweils nur die bestehende
Starlette/httpx-DeprecationWarning. Keine CI-Nachkorrektur am Code erforderlich.

Dieser nachträgliche CI-Nachweis ist eine reine Akten-Ergänzung nach dem
geprüften Code-Commit. Auch die vollständige CI dieses abschließenden
Aktencommits muss vor Abgabe erfolgreich abgeschlossen sein. Der genaue
**finale PR-HEAD** (einschließlich dieser Akten-Ergänzung) und die genau dazu
gehörenden finalen Push-/PR-CI-Links werden in der aktuellen Beschreibung von
[PR #18](https://github.com/marcosudau-vps/voice-stt-server/pull/18) festgehalten;
der Commit dieser Ergänzung ist außerdem unmittelbar über die Git-Historie
dieser Datei nachvollziehbar. Dadurch bleiben die obigen Code-Commit-Nachweise
prüfbar, ohne einem Commit seinen erst nach Erstellung entstehenden SHA
rückwirkend einzutragen.

Abgabeziel nach dieser letzten CI-Prüfung: **REVIEW_READY** für die unabhängige
technische Abnahme. Der PR bleibt **Draft**. Kein `ROOT_PASS`, keine erteilte
unabhängige Abnahme, kein Merge, kein Release und kein Deployment.
Redistribution weiterhin `BLOCKED`; die in T3-4 abgegrenzten ausstehenden
Release-/Inferenzqualifikationen bleiben unverändert.


## T3-6. Präzisierung der frischen Installationsumgebung

Bei der abschließenden Prüfung der Installationsreihenfolge wurde die neue
Anleitung um `packaging>=24.0` vor dem **ersten** CPU-only-Check ergänzt
(Linux und PowerShell). `packaging` ist bereits eine Basisabhängigkeit des
Produkts, fehlt aber in einer frisch angelegten venv vor der Produktinstallation.
Ohne diesen Marker-Parser arbeitet `cpu_only.py` absichtlich konservativ und
kann Linux-only-GPU-Requirements im Windows-CPU-Wheel als aktiv behandeln.
Die GitHub-Logs bestätigen, dass die reine CPU-Torch-Installation `packaging`
nicht mitinstalliert; die bestehenden CI-Prüfungen erfolgen hingegen erst nach
der Produktinstallation und verfügen dann bereits über diesen Parser.

Dies korrigiert ausschließlich die zuvor neu beschriebene Vorabprüfung der
Installation. Keine Änderung des CPU-only-Werkzeugs, der Abhängigkeiten des
Produkts, der Torch-Version, des Packaging-Verfahrens oder des Produktcodes.
Die Dokumentations-/Oberflächenprüfung wurde danach erneut erfolgreich
abgeschlossen (39 passed, 85 subtests passed). Die finale CI wird auch auf
dem Commit dieser reinen Dokumentationspräzisierung geprüft; genauer SHA und
vollständige endgültige Run-Links stehen in der aktuellen PR-Beschreibung.
Alle bisherigen Ergebnisse und Nachweise in dieser Akte bleiben erhalten.
