# 02 – Installation und Betrieb

## 1. Distributionen und Python-Versionen

`setup.py` baut aus demselben Quellbaum zwei Distributionsnamen. Welche
entsteht, entscheidet die Umgebungsvariable `VOICESTT_DISTRIBUTION_VARIANT`
(`resolve_distribution_variant`, `setup.py:44ff.`):

| Variante | Auslöser | Distributionsname | `python_requires` | `install_requires` |
| --- | --- | --- | --- | --- |
| Entwickler-/Legacy-Build | Variable leer und keine geerbte Build-Identität | `voicestt` | `>=3.11` | `base_requirements` |
| Öffentliche V2-Distribution | `VOICESTT_DISTRIBUTION_VARIANT=pro` | `voice-stt-server` | `>=3.12,<3.13` | `public_install_requires` (Basis + faster-whisper + Silero-ONNX + Server) |

Andere Werte als `pro` brechen den Build mit `SystemExit` ab. Der Kommentar in
`setup.py` begründet die 3.12-Beschränkung damit, dass das eingebettete
Kroko-Native-Wheel nur für `cp312` (`linux_x86_64`, `win_amd64`) gebaut wird.

**Plattformen:** CI baut und testet auf `ubuntu-24.04` und `windows-latest`
mit Python 3.12 (`.github/workflows/ci.yml`, Matrix `os`). Andere Plattformen
sind im Code nicht qualifiziert.

### Extras (vollständig, `extras_require` in `setup.py`)

| Extra | Inhalt |
| --- | --- |
| `minimal` | leer |
| `faster-whisper` | `faster-whisper==1.2.1`, `av>=11,<19` |
| `silero-vad`, `silero` | `silero-vad>=6.2.1` |
| `silero-onnx`, `silero-onnx-cpu`, `vad-onnx` | `silero-vad[onnx-cpu]>=6.2.1` |
| `kroko-builder` | `huggingface_hub` (nur Build-Werkzeug) |
| `porcupine`, `pvporcupine`, `pvp` | `pvporcupine==1.9.5` |
| `openwakeword`, `oww` | `openwakeword>=0.6.0` |
| `wakewords`, `wake-words` | beide Wake-Word-Backends |
| `server` | `fastapi>=0.115`, `uvicorn[standard]>=0.30`, `python-multipart`, `sse-starlette`, `httpx`, `PyYAML>=6.0`, `tzdata` |
| `recommended`, `default` | faster-whisper + Silero-ONNX-CPU |
| `example-app` | Abhängigkeiten von `examples/app_talk_with_llm` |
| `all` | faster-whisper, Silero-ONNX, kroko-builder, Wake-Word, server, example-app |

Für nicht unterstützte Engines gibt es **keine** Extras mehr;
`tests/packaging/test_v2_distribution_contents.py` prüft das an den
`Provides-Extra`-Metadaten des gebauten Wheels.

### Laufzeitabhängigkeiten (Basis, `base_requirements`)

`packaging`, `PyAudio`, `webrtcvad-wheels`, `halo`, `torch`, `scipy`,
`websockets`, `websocket-client`, `soundfile`. `torchaudio` ist entfallen:
`silero-vad[onnx-cpu]` verlangt nur `torch` (lokal geprüft mit
`importlib.metadata.requires("silero-vad")`), und keine der beiden
unterstützten Engines importiert `torchaudio`.

### CPU-only-Vertrag

V2 läuft ausschließlich auf der CPU. `torch` bleibt nötig
(`VoiceSTT/core/initialization.py` und `runtime.py` nutzen
`torch.multiprocessing`, `VoiceSTT/core/silero_vad.py` den PyTorch-Fallback,
`silero-vad` hängt von `torch` ab). Eine normale PyPI-Auflösung von `torch`
installiert unter Linux jedoch die CUDA-Variante samt `nvidia-*`/`triton`.
Weil `install_requires` keinen anderen Paketindex vorschreiben kann, gilt:

Der offizielle Installationsweg beginnt in einer **neuen, isolierten Python-3.12-
Umgebung ohne vorhandenes Torch**. Die Hilfsskripte werden aus dem Repository
aufgerufen; sie gehören nicht zum installierten Produkt-Wheel. Ein bloßer
Indexwechsel ersetzt eine bereits installierte CUDA-/ROCm-Version nicht:
Pip kann sie als erfüllt behandeln. Für solche Bestandsumgebungen deshalb eine
neue venv verwenden, statt deren Torch-Version als CPU-Constraint zu übernehmen.

1. Im Repository-Root eine neue Umgebung anlegen und aktivieren (Linux).
   `.venv-v2` muss ein neuer Verzeichnispfad sein:

```bash
python3.12 -m venv .venv-v2
source .venv-v2/bin/activate
python -m pip install --upgrade pip "packaging>=24.0"
```

2. CPU-Torch aus `https://download.pytorch.org/whl/cpu` installieren,
   die Version per absolutem pip-Constraint festhalten und sofort prüfen:

`packaging` muss bereits vor dieser ersten Prüfung vorhanden sein: Der Prüfer
verwendet es zur Auswertung von `Requires-Dist`-Umgebungsmarkern. Andernfalls
wertet er konservativ auch GPU-Requirements für andere Plattformen als aktiv;
ein korrektes Windows-CPU-Wheel mit Linux-only-Metadaten könnte dadurch
abgelehnt werden. `packaging` gehört ohnehin zu den Produktabhängigkeiten.

```bash
python engineering/tools/cpu_only.py install-torch --constraint-out "$VIRTUAL_ENV/cpu-constraints.txt"
python engineering/tools/cpu_only.py check
```

3. Nur bei erfolgreicher Prüfung die öffentliche V2-Distribution installieren
   (nach deren Veröffentlichung; alternativ den qualifizierten Wheel-Pfad
   anstelle des Paketnamens angeben):

```bash
PIP_CONSTRAINT="$VIRTUAL_ENV/cpu-constraints.txt" python -m pip install voice-stt-server
```

4. Die fertige Installation prüfen. Bei einem Fehler die Installation nicht
   als CPU-only freigeben:

```bash
python -m pip check
python engineering/tools/cpu_only.py check
```

Jede spätere Installation beziehungsweise Aktualisierung in dieser Umgebung
muss denselben `PIP_CONSTRAINT` verwenden. Unter PowerShell lautet der
entsprechende Ablauf (ebenfalls mit einem neuen `.venv-v2`-Verzeichnis):

```powershell
py -3.12 -m venv .venv-v2
.\.venv-v2\Scripts\Activate.ps1
python -m pip install --upgrade pip "packaging>=24.0"
$cpuConstraint = Join-Path $env:VIRTUAL_ENV "cpu-constraints.txt"
python engineering/tools/cpu_only.py install-torch --constraint-out $cpuConstraint
python engineering/tools/cpu_only.py check
# Nur bei erfolgreicher Prüfung fortfahren; Constraint existiert jetzt.
$env:PIP_CONSTRAINT = $cpuConstraint
python -m pip install voice-stt-server
python -m pip check
python engineering/tools/cpu_only.py check
```

`check` schlägt fehl, wenn `torch.version.cuda` oder `torch.version.hip`
gesetzt ist, eine `nvidia-*`/`cuda-*`/`triton`/`onnxruntime-gpu`-Distribution
installiert ist, die `torch`-Metadaten GPU-Laufzeiten verlangen oder eine
CPU-Tensoroperation scheitert. `torch.cuda.is_available()` wird bewusst
nicht verwendet.

Verdrahtet ist das in CI (Wheel-Smoke- und Dev-Umgebung), in
`engineering/tools/qualify_build_identity.qualify_installed_wheel` (frische
venv der Release-Candidate-Qualifikation), im Produktions-`Dockerfile`
(CPU-Index, `PIP_CONSTRAINT`, CUDA-/NVIDIA-Prüfung) und in
`install_windows_cpu.ps1` (CPU-Index).

**Verbleibende Einschränkung:** Ein schlichtes `pip install voice-stt-server`
ohne vorherige CPU-Torch-Installation kann unter Linux weiterhin die
CUDA-Variante von PyPI ziehen; das lässt sich über Paketmetadaten nicht
verhindern. Unter Windows liefert PyPI bereits CPU-Wheels. Unterstützt ist
der oben beschriebene Weg.

## 2. Kommandozeilen-Einstiege

`entry_points["console_scripts"]` in `setup.py:464ff.`:

| Befehl | Ziel | Zweck |
| --- | --- | --- |
| `voice-stt-server` | `VoiceSTT_server.server:main` | Kanonischer FastAPI-Server |
| `stt-server` | `VoiceSTT_server.server:main` | Kompatibilitätsalias, identisch |
| `stt-server-legacy` | `VoiceSTT_server.stt_server:main` | Eigenständiger Alt-Server mit Control-Port `8011` und Data-Port `8012` (argparse-Defaults in `stt_server.py:417,420`) |
| `stt` | `VoiceSTT_server.stt_cli_client:main` | CLI-Client für den Alt-Server |
| `stt-install-kroko` | `VoiceSTT.install_kroko:main` | Entwickler-/Release-Helfer zum Bauen der Kroko-Native-Laufzeit |

Gleichwertig: `python -m VoiceSTT_server.server` (so startet auch das
Container-Image, siehe unten).

## 3. Lokaler Start (Entwicklungs-Checkout)

Zuerst die neue Umgebung und CPU-Torch wie oben vorbereiten und prüfen.
Die Entwicklungsinstallation verwendet danach denselben Constraint wie die
CI-Entwicklungsumgebung:

```bash
PIP_CONSTRAINT="$VIRTUAL_ENV/cpu-constraints.txt" python -m pip install -e ".[recommended,server]"
```

```bash
PIP_CONSTRAINT="$VIRTUAL_ENV/cpu-constraints.txt" python -m pip install -r requirements-dev.txt
python -m pip check
python engineering/tools/cpu_only.py check
```

Start auf Loopback mit eigenem Datenverzeichnis:

```bash
voice-stt-server --host 127.0.0.1 --port 8010 --data-root ./data
```

**Beobachtetes Verhalten ohne lokale Modelle** (2026-11-05): Der Prozess
startet, `GET /api/v2/info` antwortet sofort, `GET /health` meldet
`"ok": false, "ready": false`. Im Log steht die Ursache
(`TranscriptionEngineError`): der Modellmanager konnte das lokale
faster-whisper-Modell `small` nicht auflösen; „engine libraries are not allowed
to download models implicitly“ (`VoiceSTT/transcription_engines/model_resolver.py:104`).
Modelle müssen also lokal bereitliegen oder über die Modellverwaltung
(Seite 04) bereitgestellt werden.

### Host, Port, Pfade

- Defaults: `--host 0.0.0.0`, `--port 8010` (`parse_args`, `server.py:10392ff.`;
  `ServerSettings.host/port`).
- `--data-root` / `VOICESTT_DATA_ROOT` setzt `data_root_path`. Daraus werden
  abgeleitet (`ServerSettings.__post_init__`, `server.py:543ff.`):
  - `<root>/logs/audit`, `<root>/logs/performance`, `<root>/logs/transcription`,
    `<root>/logs/system`, `<root>/logs/audio`
  - `<root>/logs/voicestt-events.sqlite3` (Eventstore)
  - `<root>/config/runtime.json` (persistierte Laufzeitwerte)
  - Modellwurzeln `<root>/models/stt/fasterwhisper` und
    `<root>/models/stt/kroko_asr` (`STTModelManager.default_root`)
- Ohne `--data-root`: Logs relativ unter `logs/`, **keine** Laufzeit-
  Persistenz (`runtime_config_path = None`), Modellwurzel relativ unter
  `data/` (`STTModelManager(runtime_root=settings.data_root_path or "data")`,
  `server.py:6319`).

## 4. Container

### Image (`Dockerfile`)

- Zweistufig auf `ubuntu:24.04`, per Digest gepinnt.
- **Builder:** installiert Python 3.12, erstellt `/opt/venv`, installiert
  `torch` aus dem CPU-Index und pinnt diese Version in
  `/build/cpu-constraints.txt` (`PIP_CONSTRAINT`), dann **das vorab gebaute
  Wheel** aus `dist/voicestt/*.whl` mit Extras
  `[faster-whisper,silero-onnx-cpu,server]` sowie `openwakeword==0.6.0` ohne
  Abhängigkeiten (der `tflite-runtime`-Eintrag wird aus den Metadaten
  entfernt), abschließend `pip check`, eine Prüfung
  `torch.version.cuda is None` / `hip is None` und ein Abbruch, falls
  `nvidia-*`/`cuda-*`/`triton`-Pakete installiert sind. Der Docker-Build
  selbst baut **kein** Wheel. (Ein lokaler Docker-Build wurde in dieser
  Cloud-Umgebung nicht ausgeführt.)
- **Runtime:** Nutzer `voicestt` (UID/GID 10001), `WORKDIR` und `VOLUME`
  `/var/lib/voicestt`, `EXPOSE 8010`, `HEALTHCHECK` gegen
  `http://127.0.0.1:8010/health`.
- Gesetzte Umgebung: `VOICESTT_CPU_ONLY=1`, `VOICESTT_OFFLINE_MODELS=1`,
  `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`,
  `VOICESTT_DATA_ROOT=/var/lib/voicestt`, `VOICESTT_SERVER_COMMIT` aus
  Build-Arg.
- `ENTRYPOINT ["python3.12", "-m", "VoiceSTT_server.server"]`, `CMD` mit
  `--device cpu --compute-type int8` und `{"local_files_only":true}` für beide
  Engines.

### Compose (`docker-compose.yml`)

Ein Dienst `server` (Build-Kontext `.`, Target `runtime`, Image
`${VOICESTT_IMAGE:-voice-stt-server:local}`):

| Aspekt | Wert |
| --- | --- |
| Port | `${VOICESTT_PORT:-8010}:8010` |
| Datenvolume | `${VOICESTT_DATA_PATH:-./data}` → `/var/lib/voicestt` |
| Modellvolumes (read-only) | `${VOICESTT_FASTER_WHISPER_HOST_PATH:-./models/custom/faster-whisper}` → `/models/custom/faster-whisper`, `${VOICESTT_KROKO_HOST_PATH:-./models/custom/kroko}` → `/models/custom/kroko` |
| Modellwurzeln im Container | `VOICESTT_FASTER_WHISPER_MODEL_ROOT`, `VOICESTT_KROKO_MODEL_ROOT` |
| Secrets | `VOICESTT_API_KEY`, `VOICESTT_ADMIN_API_KEY` aus der Host-Umgebung; optional `env_file` `${VOICESTT_ENV_FILE:-./voicestt.env}` (`required: false`) |
| Threads | `OMP_NUM_THREADS=${VOICESTT_CPU_THREADS:-4}` |

Weil das Dockerfile `dist/voicestt/*.whl` kopiert, muss vor
`docker compose build` ein Wheel dort liegen; `engineering/tools/build_production.py`
erzeugt es (Seite 10). Alternativ setzt man `VOICESTT_IMAGE` auf ein bereits
gebautes Image.

`engineering/tools/compose.py` ist ein optionaler Wrapper, der aus dem Abschnitt
`deployment` der Root-`config.yaml` Umgebungsvariablen für
`docker compose` ableitet (`build_compose_environment`) und danach
`docker compose -p <compose_project> ...` aufruft.

## 5. Windows

Belegt sind: CI-Läufe auf `windows-latest` (Build, Wheel-Installation,
Unit-Tests), das Native-Wheel-Ziel `win_amd64` für die öffentliche
Distribution und die PowerShell-Skripte `install_windows_cpu.ps1` /
`activate_venv_install_reqs.ps1` im Root. Eine Windows-Container-Variante des
Servers ist im Code nicht nachweisbar.

## Primäre Quellen

- [`setup.py`](../../setup.py) – `resolve_distribution_variant`, `extras_require`, `entry_points`
- [`Dockerfile`](../../Dockerfile), [`docker-compose.yml`](../../docker-compose.yml), [`engineering/tools/compose.py`](../../engineering/tools/compose.py)
- [`api_fastapi_server/server.py`](../../api_fastapi_server/server.py) – `parse_args`, `ServerSettings.__post_init__`, `main`
- [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)
- Tests: [`tests/unit/test_production_docker_contract.py`](../../tests/unit/test_production_docker_contract.py), [`tests/unit/test_project_config.py`](../../tests/unit/test_project_config.py), [`tests/packaging/test_identity_installation.py`](../../tests/packaging/test_identity_installation.py), [`tests/unit/test_engineering_path_contract.py`](../../tests/unit/test_engineering_path_contract.py)
