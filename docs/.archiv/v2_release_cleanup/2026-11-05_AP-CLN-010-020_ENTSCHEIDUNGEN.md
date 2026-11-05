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
