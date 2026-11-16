# AP-CLN-000 – Baseline, Abhängigkeitsinventar und Testmatrix

Datum: 2026-11-04
Arbeitsbranch: `feat/v2-release-cleanup`
Basisbranch: `feat/einheitliche-triggerarchitektur-distributed`
Ausgangs-SHA (Remote-HEAD beim Abzweigen, per `git fetch` verifiziert):
`4f30c0fda9da6470333cad996c13865c31e6474e` – identisch mit dem im Auftrag
genannten SHA, keine Abweichung.

Working Tree beim Start: sauber (`git status --short` leer). Der Branch
`feat/v2-release-cleanup` existierte remote nicht (`git ls-remote` leer) und
wurde vor jeder Schreiboperation lokal vom Remote-HEAD erzeugt.

## 1. Inventar der Engineering-Flächen

| Ordner | Getrackte Dateien |
| --- | --- |
| `build/` | `BUILD.md`, `kroko-builder.Dockerfile`, `kroko-redistribution.json`, `vps/` |
| `build/vps/` | `README.md`, `VOICE_STT_SERVER_RELEASE_ANLEITUNG.md`, `docker-compose.yml`, `profile.yaml`, `release-voice-stt.sh`, `service.yaml`, `stt-config.yaml`, `build-area/{backup-ignore.md,backup-keep.md,requirements.txt,restore-venv.sh}` |
| `release_tooling/` | 15 Python-Module (`cli`, `config`, `engine`, `pipeline`, `preflight`, `state`, `rc_manifest`, `candidate`, `adapters`, `aliases`, `gitinfo`, `redaction`, `remote_checks`, `errors`, `__init__`) |
| `tools/` | 11 Python-Skripte + `verify_session_wakeword.ps1`, **kein** `__init__.py` (Namespace-Paket) |
| `docker/` | `nginx.conf`, `vps/voice/README.md` |

## 2. Cross-References (Code, CI, Container – ohne Markdown)

| Ziel | Referenziert von (Belege) |
| --- | --- |
| `tools/release_candidate.py` | `.github/workflows/release-candidate.yml:112,134,213,226,419` (Aufruf + `from tools import release_candidate`) |
| `tools/qualify_build_identity.py` | `.github/workflows/release-candidate.yml:147,234,284,402`; Import in `tools/build_production.py:32`, `tools/release_candidate.py:60` |
| `tools/build_production.py` | `release_tooling/config.py:33-37` (über `sys.path`-Einschub `REPO_ROOT/"tools"`), Kommentarverweise in `Dockerfile:5`, `docker-compose.yml:5,11`, `build/kroko-builder.Dockerfile:9` |
| `tools/build_distribution.py` | `release_tooling/config.py:38`, `tools/build_production.py:724`, `tools/qualify_build_identity.py:24` |
| `tools/sync_wakeword_assets.py` | `VoiceSTT/assets/wakeword_models/models.json:4` (`generatedBy`, Teil der Assetbeschreibung) |
| `tools/*` (Tests) | `tests/unit/test_build_production.py`, `test_build_distribution.py`, `test_production_docker_contract.py`, `test_project_config.py`, `test_qualify_build_identity.py` (monkeypatcht `tools.release_candidate`), `test_kroko_catalog.py` (Subprozess `tools/kroko_catalog_cli.py`), `test_sync_wakeword_assets.py`, `test_realtime_text_stabilizer_eval.py`, `test_release_candidate.py`, `test_unified_product.py`, `tests/packaging/test_identity_installation.py` |
| `release_tooling` | `release.py:30` (`from release_tooling.cli import main`), `tools/release_candidate.py:53-55`, rund 20 Testmodule; `release_tooling/config.py:31` berechnet `REPO_ROOT = Path(__file__).resolve().parent.parent` |
| `build/kroko-redistribution.json` | `release_tooling/config.py:188`, `.gitignore:256` (Whitelist) – kanonische Freigabequelle |
| `build/kroko-builder.Dockerfile` | `tools/build_production.py:35`, `tests/unit/test_kroko_fingerprint.py:1513` (Hash-Guard zusammen mit `VoiceSTT/kroko/buildinputs.py`), `tests/unit/test_production_docker_contract.py:23,102,114`, `.gitignore:68` |
| `build/vps/build-area/restore-venv.sh` | `build/vps/release-voice-stt.sh:181` (absoluter Checkout-Pfad auf dem Server) |
| `build/vps` | `tests/unit/test_production_docker_contract.py:34`, `.gitignore:69-70` |
| `docker/nginx.conf` | keine Code-/CI-Referenz; nur Markdown |
| Root `build_identity_support.py`, `wakeword_package_resources.py` | `setup.py:20,22`, `MANIFEST.in:10,12`, `tools/*.py`, Packaging-Tests |
| `release.py` | `.github/workflows/release-candidate.yml:353,364,407,414`, `release-publish.yml:80,87,140,163,227,288` |

Markdown-Referenzen (nur technisch gezählt, Inhalt nicht als Quelle genutzt;
`git grep -l <pfad> -- '*.md' '*.MD'`): `tools/` 35 Dateien,
`release_tooling` 12, `build/vps` 19, `kroko-builder.Dockerfile` 6,
`docker/vps` 5, `docker/nginx.conf` 2, `app_browserclient` 11,
`app_webserver` 2, `app_talk_with_llm` 3, `Dockerfile.pro-upgrade` 3,
`install_windows_cpu` 5, `activate_venv_install_reqs` 1.

## 3. Risikoeinstufung und Alt→Neu-Mapping (Zielhypothese `engineering/`)

| Alt | Neu (Hypothese) | Risiko | Entscheidung |
| --- | --- | --- | --- |
| `tools/` | `engineering/tools/` | HOCH: Release-Candidate-Workflow-Gates, `sys.path`-Doppelidentität (`build_production` und `tools.build_production`), Monkeypatch-Ziele in Tests, `models.json`-`generatedBy`, 35 unveränderliche Markdown-Verweise auf `python tools/...` | `NICHT_SICHER` – siehe Akte CLN-010 |
| `release_tooling/` | `engineering/release/` | HOCH: Release-State-Machine, `REPO_ROOT`-Berechnung, ~20 Testimporte, Monkeypatching | `NICHT_SICHER` |
| `build/` (ohne `*.md`) | `engineering/build/` | HOCH: Kroko-Fingerprint-Guard über `build/kroko-builder.Dockerfile`, kanonische Freigabequelle `kroko-redistribution.json` | `NICHT_SICHER` |
| `build/vps/` | `engineering/deployment/vps/` | HOCH: produktives Serverskript nutzt `$CHECKOUT/build/vps/...`; enthält geschützte `*.md` | `NICHT_SICHER` |
| `docker/` | `engineering/deployment/docker/` | MITTEL: `docker/vps/voice/README.md` muss bleiben; einzig bewegbare Datei `nginx.conf` ist in 2 Markdown-Dateien referenziert | `NACH_V2` |

## 4. Beispielordner und Altlastenkandidaten

| Kandidat | Nutzungsevidenz | Einstufung |
| --- | --- | --- |
| `app_browserclient/` | `tests/unit/test_browser_client_contract.py:39` liest `app_browserclient/client.js`; 11 Markdown-Verweise | behalten, `NACH_V2` |
| `app_webserver/` | 2 Markdown-Verweise, keine Code-Referenz | behalten, `NACH_V2` |
| `app_talk_with_llm/` | `tests/unit/test_project_config.py:9` importiert `app_talk_with_llm.example_app_config`; `setup.py:297,356` (Extra `example-app`); `README.MD` im Ordner | behalten, `NACH_V2` |
| Ziel `examples/` | `.gitignore:2` ignoriert `examples/` – ein Move dorthin wäre ohne `.gitignore`-Änderung nicht trackbar | Blocker dokumentiert |
| `Dockerfile.pro-upgrade` | Kommentar Zeile 1 und 3 Markdown-Dateien verweisen darauf | behalten |
| `activate_venv_install_reqs.ps1` | Skript setzt `$PSScriptRoot` als Projektwurzel voraus | behalten |
| `install_windows_cpu.ps1` | `app_talk_with_llm/install_cpu.bat:3` (`%~dp0..\install_windows_cpu.ps1`) | behalten |
| Root-`__init__.py` | Lazy-Exporte der VoiceSTT-Objekte; Nutzung bei Checkout als Paketordner nicht ausschließbar | behalten, `NACH_V2` |
| Getrackte, aber ignorierte Dateien | `git ls-files -ci --exclude-standard` → leer | keine |
| Backup-/Temp-Reste | `git ls-files | grep -Ei '\.(bak|tmp|orig|log|pyc)$|Kopie'` → leer | keine |

## 5. Testmatrix der betroffenen Verträge

| Vertrag | Prüfung |
| --- | --- |
| Root-Einstieg `python release.py` | `tests/unit/test_release_cli.py`, `test_release_root_corrections.py`, `python release.py --help` |
| Build-/Distributionspfade | `tests/unit/test_build_production.py`, `test_build_distribution.py`, `test_production_docker_contract.py`, `test_project_config.py`, `test_unified_product.py` |
| Release-State-Machine | `tests/unit/test_release_*.py` |
| Workflows | `tests/unit/test_release_workflows.py` |
| Kroko-Fingerprint | `tests/unit/test_kroko_fingerprint.py` |
| Packaging | `tests/packaging/` |
| Doku-Oberfläche | `tests/unit/test_docs_surface.py` (prüft u. a. alle nicht archivierten `*.md`) |
| Neu: Pfadverträge | `tests/unit/test_engineering_path_contract.py` (dieser Branch) |
| Neu: V2-Code-Referenz | `tests/unit/test_v2_code_reference.py` (dieser Branch) |

## 6. Geschützte Dokumentation

Alle 259 zum Ausgangs-SHA getrackten `*.md`/`*.MD`/`*.rst`-Dateien sind mit
Git-Blob-ID in
[`2026-11-04_GESCHUETZTE_DOKUMENTATION_BASELINE.tsv`](2026-11-04_GESCHUETZTE_DOKUMENTATION_BASELINE.tsv)
erfasst. Zusätzlich unverändert zu erhaltende HTML-Dateien (Programmbestandteile,
keine Doku-Quellen): `VoiceSTT_server/index.html`,
`api_fastapi_server/static/index.html`, `app_browserclient/index.html`.
