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
