# AP-CLN-010 / AP-CLN-020 – Move-Entscheidungen und Altlastenprüfung

Datum: 2026-11-05
Branch: `feat/v2-release-cleanup`, Basis `4f30c0f`

## Ergebnis in einem Satz

Die Zielhypothese `engineering/{build,release,tools,deployment/{docker,vps}}`
wurde je Ordner geprüft. **Kein** Verzeichnis ließ sich verschieben, ohne
gleichzeitig mindestens eine der verbindlichen Leitplanken zu verletzen
(unveränderliche Alt-Dokumentation mit funktionsfähigen Pfaden, unveränderte
Release-Gates, unveränderte Kroko-Fingerprint-Autorität, produktives
VPS-Skript, keine doppelten Implementierungen). Statt einer riskanten
Teilmigration wurde ein **Pfadvertragstest** eingeführt, der jede künftige
Verschiebung dieser Flächen deterministisch scheitern lässt, bis alle
Aufrufer mitgezogen sind.

## Alt→Neu-Matrix (final)

| Alt | Ziel (Hypothese) | Status | Begründung (Code-/Konfigurationsbeleg) |
| --- | --- | --- | --- |
| `tools/` | `engineering/tools/` | `NICHT_SICHER` | `release-candidate.yml` ruft `python tools/release_candidate.py` und `python tools/qualify_build_identity.py` direkt auf und importiert `from tools import release_candidate` (Zeilen 112–419). Ein Move ändert damit den Release-Candidate-Workflow selbst. `release_tooling/config.py:33` legt `REPO_ROOT/"tools"` auf `sys.path`; `tools/build_production.py` und `tools.build_production` sind dadurch bereits zwei Modulidentitäten. Tests monkeypatchen `tools.release_candidate` (`tests/unit/test_qualify_build_identity.py:184,191`); eine Fassade per Re-Export würde diese Patches wirkungslos machen. 35 bestehende Markdown-Dateien verweisen auf `tools/...` und dürfen nicht geändert werden. |
| `release_tooling/` | `engineering/release/` | `NICHT_SICHER` | Release-State-Machine; `release.py:30` und ~20 Testmodule importieren `release_tooling.*`; `REPO_ROOT` wird relativ zur Paketlage berechnet (`release_tooling/config.py:31`). Eine Kompatibilitätsfassade bräuchte Modul-Aliasing über `sys.modules` – das wäre eine Änderung der Release-Autorität, nicht nur ein Pfad-Fix. |
| `build/kroko-builder.Dockerfile` | `engineering/build/` | `NICHT_SICHER` | Hash-Guard in `tests/unit/test_kroko_fingerprint.py:1513` und Pfad in `tools/build_production.py:35`; Builder-Revision ist Fingerprint-relevant (`VoiceSTT/kroko/buildinputs.py:164-190`). |
| `build/kroko-redistribution.json` | – | `NICHT_SICHER` (ausdrücklich verboten) | kanonische Freigabequelle, gelesen in `release_tooling/config.py:188`. |
| `build/BUILD.md` | – | bleibt | geschützte Bestandsdokumentation. |
| `build/vps/` | `engineering/deployment/vps/` | `NICHT_SICHER` | `build/vps/release-voice-stt.sh:181` ruft `$CHECKOUT/build/vps/build-area/restore-venv.sh` auf dem Zielserver auf; enthält 4 geschützte `*.md`. |
| `docker/nginx.conf` | `engineering/deployment/docker/` | `NACH_V2` | technisch referenzfrei, aber in 2 unveränderlichen Markdown-Dateien als Pfad genannt; `docker/vps/voice/README.md` muss ohnehin am Ort bleiben → der Ordner `docker/` verschwindet nicht, Gewinn an Ordnung ≈ 0. |

Durchgeführte Moves: **keine**. Durchgeführte technische Absicherung:
`tests/unit/test_engineering_path_contract.py` (14 Tests, 39 Subtests).

## AP-CLN-020 – Beispiele und Altlasten

| Kandidat | Ergebnis | Beleg |
| --- | --- | --- |
| `app_browserclient/` → `examples/` | `NACH_V2` | `.gitignore:2` ignoriert `examples/`; `tests/unit/test_browser_client_contract.py:39` liest den festen Pfad; 11 unveränderliche Markdown-Verweise. |
| `app_talk_with_llm/` → `examples/` | `NACH_V2` | Import in `tests/unit/test_project_config.py:9`; `install_cpu.bat` adressiert `..\install_windows_cpu.ps1` relativ; enthält eigene `README.MD` (geschützt). |
| `app_webserver/` → `examples/` | `NACH_V2` | `.gitignore`-Blocker wie oben; 2 Markdown-Verweise. |
| Getrackte Backup-/Temp-/Bytecode-Dateien | keine gefunden | `git ls-files -ci --exclude-standard` leer; Musterprüfung `bak|tmp|orig|log|pyc|Kopie` leer. |
| `Dockerfile.pro-upgrade`, `activate_venv_install_reqs.ps1`, `install_windows_cpu.ps1`, Root-`__init__.py` | behalten | siehe Baseline Abschnitt 4. |

Gelöschte Dateien: **keine**. Es gab keinen Kandidaten mit vollständigem
Nichtverwendungsnachweis.

## Empfehlung für einen späteren, freigegebenen Strukturschritt (NACH_V2)

Ein Umzug von `tools/` und `release_tooling/` wird erst sinnvoll, wenn
gleichzeitig (a) die Release-Workflows geändert werden dürfen, (b) die
Alt-Dokumentation mitgepflegt werden darf und (c) `tools/` ein echtes Paket
mit nur einer Importidentität wird. Der neue Pfadvertragstest zeigt dabei
alle zu ändernden Stellen an.

---

## Neubewertung im zweiten Lauf (2026-11-05, nach verbindlichem Abschlussauftrag)

Die obige Entscheidung des ersten Laufs (keine Verschiebung) wurde durch den
Abschlussauftrag vom 2026-11-05 ausdrücklich verworfen: Pfadreferenzen, CI
und Importe sind Migrationsaufgaben, alte Doku-Verweise keine pauschalen
Blocker. Der Text oben bleibt als Historie unverändert stehen.

### Tatsächlich umgesetzt (AP-CLN-010)

| Bereich | Alt | Neu | Kompatibilität |
| --- | --- | --- | --- |
| Tools | `tools/*.py`, `tools/verify_session_wakeword.ps1` | `engineering/tools/` | `tools/<name>.py` als Shim (Skript → `main()`, Import → dieselbe Modulidentität via `sys.modules`) |
| Release | `release_tooling/*.py` | `engineering/release/` | `release_tooling/__init__.py` registriert alle Untermodule als Aliase; `release.py` → `engineering.release.cli` |
| Docker | `docker/nginx.conf`, `Dockerfile.pro-upgrade` | `engineering/deployment/docker/` | keine (Datendateien; Alt-Doku-Divergenz dokumentiert) |
| VPS | `build/vps/{docker-compose.yml,profile.yaml,release-voice-stt.sh,service.yaml,stt-config.yaml}`, `build/vps/build-area/{requirements.txt,restore-venv.sh}` | `engineering/deployment/vps/` | `build/vps/release-voice-stt.sh` und `build/vps/build-area/restore-venv.sh` als `exec`-Wrapper |
| Entwürfe | 5 Engine-Dateien aus `VoiceSTT/transcription_engines/` | `engineering/drafts/transcription_engines/` | keine (bewusst nicht importierbar/paketiert) |

**Bewusst nicht verschoben (mit Nachweis):**

- `build/kroko-builder.Dockerfile`: zunächst nach `engineering/build/`
  verschoben, dann zurückgenommen. Die unveränderliche `build/BUILD.md`
  verlinkt die Datei als Nachbardatei, und
  `tests/unit/test_docs_surface.py::MaintainedLinkIntegrityTests` erzwingt
  diesen Link; zusätzlich hasht der Fingerprint-Guard
  (`tests/unit/test_kroko_fingerprint.py`) ihren Inhalt. Ein Symlink wäre auf
  Windows-Checkouts nicht verlässlich. Damit bleibt `engineering/build/`
  derzeit leer und wurde nicht angelegt.
- `build/kroko-redistribution.json`: kanonische Freigabequelle (Auftrag).
- `build_identity_support.py`, `wakeword_package_resources.py`: von
  `setup.py` im PEP-517-Build importiert und per `MANIFEST.in` im sdist
  enthalten; Verschiebung würde den sdist-Rebuild-Vertrag ändern.
- Root-`Dockerfile`, `docker-compose.yml`, `release.py`, `setup.py`,
  `pyproject.toml`, `MANIFEST.in`, `config.yaml`: funktionsnotwendige Root-Einstiege.
- `install_windows_cpu.ps1`, `activate_venv_install_reqs.ps1`: beide setzen das
  Skriptverzeichnis als Projektwurzel voraus.
- Tuning-Profile `parakeet-*` in `api_fastapi_server/server.py`: geprüft und
  behalten. Sie sind engine-neutrale Zeitprofile (Batch, Pausen, VAD-Zeiten),
  wählen keine Engine und sind öffentliche CLI-Choices (`--profile`).

### Tatsächlich umgesetzt (AP-CLN-020)

- `app_browserclient/`, `app_talk_with_llm/`, `app_webserver/` → `examples/`
  (Inhalt inkl. `README.MD` unverändert, R100). `.gitignore`-Regel
  `examples/` entfernt. Angepasst: `example_app_config.PROJECT_ROOT`
  (`APP_DIR.parents[1]`), `ui_openai_voice_interface` (`parents[2]`,
  Import `examples.app_talk_with_llm…`), `install_cpu.bat`
  (`%~dp0..\..\install_windows_cpu.ps1`), `examples/app_webserver/stt_server.py`
  (Import `examples.app_webserver.server`), Tests
  `test_browser_client_contract.py`, `test_project_config.py`.
- `MANIFEST.in`: `prune engineering`, `prune examples`.
- Entfernt als nachweislich obsolet (nur entfernte Engines): manuelle Skripte
  `tests/realtimestt_omnilingual_test.py`, `tests/realtimestt_test_whispercpp.py`;
  `tests/install_extras_matrix.py` auf die verbleibenden Extras umgestellt.

### Vollständige Liste der Umbenennungen (`git diff -M --name-status 4f30c0f..HEAD`, Status R)

| Alt | Neu |
| --- | --- |
| `Dockerfile.pro-upgrade` | `engineering/deployment/docker/Dockerfile.pro-upgrade` |
| `docker/nginx.conf` | `engineering/deployment/docker/nginx.conf` |
| `build/vps/build-area/requirements.txt` | `engineering/deployment/vps/build-area/requirements.txt` |
| `build/vps/docker-compose.yml` | `engineering/deployment/vps/docker-compose.yml` |
| `build/vps/profile.yaml` | `engineering/deployment/vps/profile.yaml` |
| `build/vps/service.yaml` | `engineering/deployment/vps/service.yaml` |
| `build/vps/stt-config.yaml` | `engineering/deployment/vps/stt-config.yaml` |
| `VoiceSTT/transcription_engines/openai_api_engine.py` | `engineering/drafts/transcription_engines/openai_api_engine.py` |
| `VoiceSTT/transcription_engines/openai_whisper_engine.py` | `engineering/drafts/transcription_engines/openai_whisper_engine.py` |
| `VoiceSTT/transcription_engines/parakeet_engine.py` | `engineering/drafts/transcription_engines/parakeet_engine.py` |
| `VoiceSTT/transcription_engines/sherpa_onnx_engine.py` | `engineering/drafts/transcription_engines/sherpa_onnx_engine.py` |
| `VoiceSTT/transcription_engines/whisper_cpp_engine.py` | `engineering/drafts/transcription_engines/whisper_cpp_engine.py` |
| `release_tooling/adapters.py` | `engineering/release/adapters.py` |
| `release_tooling/aliases.py` | `engineering/release/aliases.py` |
| `release_tooling/candidate.py` | `engineering/release/candidate.py` |
| `release_tooling/cli.py` | `engineering/release/cli.py` |
| `release_tooling/config.py` | `engineering/release/config.py` |
| `release_tooling/engine.py` | `engineering/release/engine.py` |
| `release_tooling/errors.py` | `engineering/release/errors.py` |
| `release_tooling/gitinfo.py` | `engineering/release/gitinfo.py` |
| `release_tooling/pipeline.py` | `engineering/release/pipeline.py` |
| `release_tooling/preflight.py` | `engineering/release/preflight.py` |
| `release_tooling/rc_manifest.py` | `engineering/release/rc_manifest.py` |
| `release_tooling/redaction.py` | `engineering/release/redaction.py` |
| `release_tooling/remote_checks.py` | `engineering/release/remote_checks.py` |
| `release_tooling/state.py` | `engineering/release/state.py` |
| `tools/verify_session_wakeword.ps1` | `engineering/tools/verify_session_wakeword.ps1` |
| `app_browserclient/client.js` | `examples/app_browserclient/client.js` |
| `app_browserclient/index.html` | `examples/app_browserclient/index.html` |
| `app_browserclient/server.py` | `examples/app_browserclient/server.py` |
| `app_talk_with_llm/README.MD` | `examples/app_talk_with_llm/README.MD` |
| `app_talk_with_llm/active.wav` | `examples/app_talk_with_llm/active.wav` |
| `app_talk_with_llm/custom_api_chat_endpoint.py` | `examples/app_talk_with_llm/custom_api_chat_endpoint.py` |
| `app_talk_with_llm/example_app_config.py` | `examples/app_talk_with_llm/example_app_config.py` |
| `app_talk_with_llm/inactive.wav` | `examples/app_talk_with_llm/inactive.wav` |
| `app_talk_with_llm/install_cpu.bat` | `examples/app_talk_with_llm/install_cpu.bat` |
| `app_talk_with_llm/ui_openai_voice_interface.py` | `examples/app_talk_with_llm/ui_openai_voice_interface.py` |
| `app_webserver/client.py` | `examples/app_webserver/client.py` |
| `app_webserver/server.py` | `examples/app_webserver/server.py` |
