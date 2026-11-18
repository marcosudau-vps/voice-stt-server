# AP-SRV-070 / W4C-R01 - Implementation Report

## Aenderungstabelle

| Bereich | Datei(en) | Vorher | Aenderung | Warum | Requirement/Gate |
|---|---|---|---|---|---|
| Production Dockerfile | `Dockerfile` | Zwei Stages (`kroko-builder`, `cpu`), Debian `python:3.12-slim-bookworm`, `pip install -e`, Kroko nativ im Build | Zwei Stages `builder`/`runtime`, Ubuntu 24.04, venv, installiert vorgebaute VoiceSTT-/Kroko-Wheels, non-root, korrigierter `HEALTHCHECK` | 7.1/7.2/7.3/7.4/5.1 | W4C-G04,G05,G06,G07,G08,G09,G10 |
| Kroko-Builder-Trennung | `build/kroko-builder.Dockerfile` (neu) | Kroko-Build als Stage im Production-Dockerfile | Eigenstaendiges Linux/AMD64-Builder-Image, ausserhalb des Production-Builds, vom Orchestrator per `docker run` gesteuert | 6, 7.2, Plattformgrenze | W4C-G02,G03,G06,G18 |
| Build-Orchestrator | `tools/build_production.py` (neu) | Kein oeffentlicher Einstiegspunkt | Preflight, Commit/Version, Wheel-Build, Kroko-Resolve (REUSE/BUILD), Image-Build Free/Pro/all, Manifest | 6 | W4C-G01-G05 |
| Docker-Buildkontext | `.dockerignore` | `dist`/`build` vollstaendig ausgeschlossen | `dist/` nicht mehr ausgeschlossen (Wheel-Buildinputs), `build/` bleibt ausgeschlossen | Wheels muessen als Buildinput in den Kontext gelangen | 7.2 |
| Oeffentliche Compose | `docker-compose.yml` | Zwei Services (`server` + `nginx`-`browserclient`), drei Pflicht-Modellmounts, `/data`, `${VAR:?...}` | Ein Service, `/var/lib/voicestt`, optionale Custom-Model-Mounts mit portablen Defaults, korrigierter Healthcheck, kein nginx | 11, 12 | W4C-G33, teilweise G13-G17 |
| Compose-Launcher | `tools/compose.py` | Modellpfade Pflicht (wirft bei Fehlen), Browserport-Injektion | Modellpfade optional (`discover_model_path` gibt `None` statt zu werfen), kein Browserport mehr | Konsistenz mit neuem, optionalen Compose-Vertrag | 11 |
| Projekt-Deploymentdefault | `config.yaml` | `deployment.image: voicestt-cpu:local` | `deployment.image: voice-stt-server:local` (Kommentar erklaert Umbenennung) | eindeutig gebrochene Verlinkung durch die neue Produktidentitaet | 5.2 (Ausnahmeklausel Abschnitt "Nicht Teil dieses Runs") |
| Bestehender Compose-Contract-Test | `tests/unit/test_project_config.py` | Erwartete `KROKO_VARIANT`-Build-Arg und `/data`-Mount mit `:?`-Pflichtwert | Angepasst auf `VOICESTT_KROKO_VARIANT`-Arg und `/var/lib/voicestt`-Mount mit `:-./data`-Default | Test folgt dem bewusst geaenderten, dokumentierten W4C-Vertrag | 16 |
| Neue Tests | `tests/unit/test_build_production.py` (neu) | - | Variantenwahl, Free/Pro-Mapping, Kroko-Reuse/Miss (gestubbt), kein Lizenzschluessel im Buildinput, Image-Tagging | 16 | W4C-G02,G03,G27-G31 |
| Neue Tests | `tests/unit/test_production_docker_contract.py` (neu) | - | Statische Vertragschecks: kein `-e`-Install, keine Kroko-Builder-Stage, Ubuntu 24.04, non-root, OCI-Labels, Healthcheck ohne `ready`/`ok`, Compose ohne private Marker/nginx | 16 | W4C-G06,G07,G09,G10,G33 |
| Public-Doku | `build/BUILD.md` | Beschreibung des alten Zwei-Stage-Kroko-Dockerfiles, `voicestt-cpu`-Tags | Neuer Abschnitt "Oeffentliches Production-Image (W4C)", aktualisierte Buildmatrix, aktualisierter Docker-Build-Abschnitt, korrigierte Pro-Wheel-Upgrade-Referenz | 17 | - |
| Public-Doku | `README.md` | `python tools/compose.py up --build -d` als vollstaendiger Quickstart | Hinweis auf `tools/build_production.py` als Voraussetzung ergaenzt | eindeutig gebrochener Quickstart durch die neue Wheel-Buildinput-Anforderung | Ausnahmeklausel |
| Planung | `docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/2026-09-05_W4C_PLAN.md` (neu) | - | Datierte Gesamtplanung vor Umsetzung (AGENTS.md/Archiv-Pflicht) | AGENTS.md Abschnitt "Groessere Aenderungsaktionen" | - |

## Build-Orchestrator

`tools/build_production.py` implementiert alle in Abschnitt 6 geforderten
Schritte als reine, per Dependency Injection testbare Funktionen
(`CommandRunner`-Parameter): Preflight (`git`/`docker` vorhanden und
funktionsfaehig), exakter Commit (`git rev-parse HEAD`), Version
(`VoiceSTT._version.resolve_version()`), VoiceSTT-Wheel-Build (`python -m
build --wheel`), Kroko-Variantenwahl (`variants_for_target`), Aufloesung des
Linux/AMD64-Kroko-Artefakts ueber den bestehenden W4A-Fingerprint-/
Artifact-Store (per `docker run` gegen `build/kroko-builder.Dockerfile`,
REUSE zuerst per `--describe-artifact`, `--build --skip-install` nur bei
echtem Miss), Kopie des aufgeloesten Wheels in den Docker-Buildkontext,
Production-Image-Build mit vollstaendigen Build-Args/OCI-Labels, `docker
inspect`-Validierung und ein JSON-Manifest (`dist/build-manifest.json`).

## Docker

Zwei Stages, beide `ubuntu:24.04`:

- `builder`: `python3.12-venv`, installiert CPU-Torch, das bereitgestellte
  Kroko-Wheel und das bereitgestellte VoiceSTT-Wheel (Extras
  `faster-whisper,silero-onnx-cpu,server`) in eine venv unter `/opt/venv`.
  Kein `pip install -e`, kein Kroko-Quellcheckout, keine
  `install_kroko`-Referenz.
- `runtime`: kopiert nur `/opt/venv`, legt `voicestt` (UID/GID 10001) und
  `/var/lib/voicestt` (inkl. `models/stt/fasterwhisper`,
  `models/stt/kroko_asr`) an, laeuft als `USER voicestt`, `HEALTHCHECK`
  prueft ausschliesslich `GET /health` -> HTTP 200 (kein `ready`/`ok`).
  OCI-Labels: `org.opencontainers.image.{title,description,version,
  revision,created,source,licenses}` plus `com.voicestt.kroko-variant`.

## Free/Pro

`tools/build_production.py.image_name_for()` ist die einzige Stelle, die
Variante -> Image-Name abbildet (`free` -> `voice-stt-server`, `pro` ->
`voice-stt-server-pro`); sie hat keinen Parameter, ueber den ein Laufzeit-Key
je einfliessen koennte. Der Kroko-Builder-Container erhaelt nie eine der
bekannten Lizenzschluessel-Umgebungsvariablen (siehe
`VoiceSTT.install_kroko.KROKO_LICENSE_KEY_ENV_NAMES`, unveraendert
uebernommen).

## Compose/Persistenz

`docker-compose.yml` hat noch genau einen Service (`server`). Persistenter
Runtime-Root `/var/lib/voicestt` mit portablem Default (`./data`, per
`bind.create_host_path` automatisch angelegt). Zwei optionale, standardmaessig
leere, read-only Custom-Model-Mounts fuer Faster-Whisper/Kroko (`discovery
_roots()` faellt bei leerem Mount auf den verwalteten Store zurueck). Kein
Openwakeword-Mount mehr (Wake-Assets sind Teil des Wheels).
`tools/compose.py` generalisiert genau diese Optionalitaet, ohne Marcos
private Kandidatenwerte in `config.yaml` zu aendern.

## Health

Ausschliesslich die Docker-/Compose-Health**probe** wurde geaendert (siehe
Plan, Entscheidung E); `api_fastapi_server/server.py` und
`VoiceSTT_server/stt_model_management.py` sind unveraendert. Beleg, dass der
bestehende Vertrag "Control Plane healthy trotz fehlendem STT-Modell" bereits
im `/health`-Endpunkt selbst existiert:
`tests/unit/test_stt_model_management.py::test_server_admin_and_health_remain_available_when_stt_is_not_ready`
(unveraendert, besteht weiterhin).

## Source Independence

`api_fastapi_server/static/index.html` ist ein einzelnes, selbstenthaltenes
HTML-Dokument (keine externen Asset-Referenzen) und bereits als
`package_data` im Wheel enthalten (`setup.py`); `api_fastapi_server/server.py`
liest es relativ zum installierten Modul. Die oeffentliche Compose startet
daher nur noch `stt-server`, ohne `nginx`, ohne `docker/nginx.conf`, ohne
Source-Bind-Mount fuer den Browserclient.

## Tests

Neue gezielte Tests: `tests/unit/test_build_production.py` (Orchestrator-
Logik, gestubbte Docker-/Git-Aufrufe), `tests/unit/test_production_docker_
contract.py` (statische Dockerfile-/Compose-Vertragschecks). Bestehender
Test `tests/unit/test_project_config.py::test_root_config_is_valid_for_
server_and_example_app` an den bewusst geaenderten Compose-Vertrag angepasst
(Build-Arg-Name, Mount-Ziel/-Default). Volle Suite und `git diff --check`
siehe `Evidence/09_Tests`.

## Bewusste Nicht-Aenderungen

- `build/vps/*`, `Dockerfile.pro-upgrade`: unveraendert, ausserhalb des Runs.
- `api_fastapi_server/server.py`, `VoiceSTT_server/stt_model_management.py`,
  `VoiceSTT/kroko/*`, `VoiceSTT/install_kroko.py`: keine Codeaenderung,
  nur als Authority gelesen/aufgerufen.
- `config.yaml`s private Kandidatenpfade und `public_url`: unveraendert.
- Legacy-Offline-Flags (`HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`,
  `VOICESTT_OFFLINE_MODELS`): unveraendert beibehalten (siehe Plan,
  Entscheidung F).
