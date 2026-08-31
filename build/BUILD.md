# VoiceSTT bauen und deployen

Diese Datei ist die zentrale Referenz fuer Build, Paketierung und Deployment
von VoiceSTT. Engine-Dokumente beschreiben die Laufzeitnutzung; verbindliche
Buildentscheidungen und Kroko-Varianten werden hier zusammengefuehrt.

Die konkrete Installation auf Marcos VPS ist bewusst getrennt unter
[`build/vps/README.md`](vps/README.md) dokumentiert. Absolute Serverpfade,
Secret-Dateien, produktive Ports und die dortige Release-Automation sind kein
allgemeingueltiger Teil des Projekts.

## Schnellstart

### Lokale Python-Installation

Linux-Voraussetzungen installieren, virtuelle Umgebung anlegen und VoiceSTT
mit der empfohlenen CPU-Ausstattung installieren:

```bash
sudo apt-get update
sudo apt-get install -y python3-dev python3-venv portaudio19-dev git cmake build-essential

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e '.[recommended,server]'
python -m pip check
```

Fuer Kroko Community kommt danach der Runtime-Build hinzu:

```bash
python -m pip install -e '.[kroko-builder,silero-onnx-cpu,server]'
stt-install-kroko --build --variant free
```

Fuer ein lizenziertes Kroko-Pro-Modell muss stattdessen ein Pro-faehiges Wheel
gebaut werden:

```bash
stt-install-kroko --build --variant pro
export KROKO_API_KEY='...nur in der lokalen Secret-Verwaltung...'
```

Der Key ist ein Laufzeit-Secret. Er wird nicht beim Build benoetigt und darf
nicht in Shell-Historien, Images, Compose-Dateien oder Git abgelegt werden.

### Docker mit Community-Kroko

Modellpfade in `config.yaml` pruefen und den portablen Compose-Launcher nutzen:

```bash
python -m pip install PyYAML
python tools/compose.py up --build -d
python tools/compose.py ps
curl -fsS http://127.0.0.1:8010/health
```

`deployment.kroko_variant` ist standardmaessig `free`. Compose baut das
CPU-Image und mountet vorhandene Modellverzeichnisse read-only.

### Docker mit Kroko Pro

Den Pro-Build immer explizit ausloesen und den Lizenz-Key erst beim Start als
Environment-Secret bereitstellen:

```bash
docker build --target cpu --build-arg KROKO_VARIANT=pro -t voicestt-cpu:pro .
docker run --rm -e KROKO_API_KEY --mount type=bind,src=/pfad/kroko,dst=/models/kroko,readonly voicestt-cpu:pro python -c 'import kroko_onnx; print("Kroko runtime importiert")'
```

Fuer Compose kann `deployment.kroko_variant: pro` in einer lokalen
Konfigurationskopie gesetzt werden. Die produktive VPS-Variante ist bereits
unter [`build/vps`](vps/README.md) festgelegt.

### Vor einem Release pruefen

```bash
python -m pytest -q tests/unit
python -m pip check
python -m build
python tools/compose.py config --quiet
```

Reale Engine-Tests benoetigen die jeweilige optionale Runtime und lokale
Modelle. Die vollstaendige Testmatrix steht in
[`docs/testing.md`](../docs/testing.md).

## Grundsaetzliche Trennung

Ein reproduzierbarer VoiceSTT-Build besteht aus mehreren getrennten Ebenen:

| Ebene | Inhalt | Darf in Git/Image liegen? |
| --- | --- | --- |
| Projektquelle | Python-Code, Dockerfile, Setup-Metadaten, Dokumentation | Ja |
| Python-Abhaengigkeiten | Kernpaket und gewaehlte Extras | Im Image ja; lokale venv nein |
| Native Kroko-Runtime | Aus `kroko-onnx` gebautes Wheel, Variante `free` oder `pro` | Im Image ja, Lizenzbedingungen beachten |
| Modelle | Whisper-, Kroko- und Wake-Word-Modelle | Lokal/read-only mounten; nicht in diesem Repo |
| Secrets | API-, Admin-, GitHub- und Kroko-Lizenz-Keys | Nein; nur Secret Store oder lokale env-Datei |
| Laufzeitdaten | Logs, SQLite, Audiodateien, `config/runtime.json` | Nein; persistentes `/data`-Volume |
| Serversteuerung | VPS-Pfade, Ports, Netzwerk, Release-Log | Nur unter `build/vps` als Vorlage; erzeugte Daten extern |

Wichtig fuer Kroko Pro: Ein Pro-Modell wird nicht allein durch einen API-Key
freigeschaltet. Das Image muss ein mit `KROKO_LICENSE=ON` gebautes Pro-Wheel
enthalten, das `.data`-Modell muss vorhanden sein und der passende Key muss der
Runtime uebergeben werden. Eine Free-Runtime kann Pro-Modelle nicht laden.

## Buildmatrix

| Ziel | Befehl | Ergebnis |
| --- | --- | --- |
| Editierbare Entwicklung | `python -m pip install -e '.[recommended,server]'` | Quellcheckout wird direkt importiert |
| Wheel und sdist | `python -m build` | Artefakte unter `dist/` |
| Legacy-Paketbuild | `python setup.py sdist bdist_wheel` | Gleiches Paket ueber `setup.py`; nur noch Kompatibilitaetspfad |
| Kroko Community | `stt-install-kroko --build --variant free` | Community-faehige Kroko-Runtime im aktiven Python |
| Kroko Pro | `stt-install-kroko --build --variant pro` | Lizenzfaehige Kroko-Runtime im aktiven Python |
| Kroko-Wheel ohne Installation | `stt-install-kroko --build --skip-install --work-dir DIR` | Wheel im Kroko-Artefaktverzeichnis |
| Docker CPU/Community | `docker build --target cpu --build-arg KROKO_VARIANT=free -t voicestt-cpu:free .` | Vollstaendiges Offline-CPU-Image |
| Docker CPU/Pro | `docker build --target cpu --build-arg KROKO_VARIANT=pro -t voicestt-cpu:pro .` | Gleiches Image mit Pro-Wheel |
| Nur Kroko-Builder | `docker build --target kroko-builder --build-arg KROKO_VARIANT=pro -t voicestt:kroko-builder-pro .` | Wiederverwendbarer Builder/Cache |
| Pro-Wheel-Upgrade | `docker build -f Dockerfile.pro-upgrade -t voicestt-cpu:pro-upgrade .` | Bestehendes Image plus bereits gebautes Pro-Wheel |

`setup.py` ist aktuell die kanonische Paketmetadatenquelle. Eine spaetere
Migration auf `pyproject.toml` muss Extras, Console-Scripts, den angepassten
`build_py`-Ausschluss und Paketdaten vollstaendig uebernehmen; sie ist nicht
Teil des derzeitigen Buildverfahrens. Setuptools behandelt `build/` als
technischen Ausgabeordner und nimmt diesen Dokumentationsordner daher nicht in
sdist oder Wheel auf. Die Paketbeschreibung verlinkt auf die versionierte
GitHub-Fassung dieser Dokumentation.

## Voraussetzungen

### Unterstuetzte Python- und Betriebssystempfade

- VoiceSTT-Kern: Python 3.11 oder neuer.
- Docker-CPU-Image: Python 3.12 auf Debian Bookworm Slim.
- Kroko Linux-Build: Git, CMake, C/C++-Toolchain, OpenSSL- und zlib-Header.
- Kroko Windows-Build: CPython 3.12 x64, Git und laufendes Docker Desktop mit
  Linux-/WSL2-Engine.
- Omnilingual ASR: Linux/WSL2 mit Python 3.11 und passendem Torch-Stack.
- GPU-Pfade sind engineabhaengig und nicht Bestandteil des CPU-Dockerfiles.

Auf Windows muss `docker version` sowohl Client als auch Server anzeigen.
`docker --version` beweist nur, dass die CLI vorhanden ist.

### Abhaengigkeitsquellen

- `requirements.txt`: gemeinsame Basispins, die `setup.py` einliest.
- `requirements-dev.txt`: Entwicklungs- und Testwerkzeuge.
- `api_fastapi_server/requirements.txt`: Serverabhaengigkeiten.
- `setup.py`: Extras, Paketdaten und Console-Scripts.
- `docker/vps/voice/build-area/requirements.txt`: historischer
  servergebundener venv-Restore; der aktuelle kanonische Stand liegt unter
  [`build/vps/build-area`](vps/build-area/).

Nach jeder Installation ist `python -m pip check` verbindlich. Fuer Torch und
Torchaudio muessen Version und Paketquelle zusammenpassen.

## Weitere Projekt-Buildpfade

### Windows-CPU-Umgebung

`install_windows_cpu.ps1` ist der getestete Komplettweg fuer Windows:

```powershell
.\install_windows_cpu.ps1
```

Das Skript erstellt bei Bedarf `.venv` mit Python 3.12, installiert
CPU-Torch/Torchaudio vom offiziellen CPU-Index und installiert den Checkout
editierbar mit Faster Whisper, Silero ONNX, Wake Words, Kroko-Builder, Server
und Beispiel-App. Kroko-ONNX selbst wird anschliessend mit der gewuenschten
Variante gebaut:

```powershell
.\.venv\Scripts\Activate.ps1
stt-install-kroko --build --variant free
```

Fuer Pro ist `--variant pro` erforderlich. Docker Desktop muss fuer den
Windows-Kroko-Builder laufen. `activate_venv_install_reqs.ps1` ist dagegen nur
ein Legacy-Komfortskript: Es sucht `.venv`, `venv` oder `env`, aktiviert die
Umgebung und aktualisiert ausschließlich `requirements.txt`. Es ersetzt weder
die Extras-Installation noch den Kroko-Build.

### FastAPI-Server und Browseroberflaeche

Der installierte Produktionsstart ist das Console-Script `stt-server`; Docker
startet dasselbe Modul direkt als `python -m VoiceSTT_server.server`. Das Extra
`server` installiert FastAPI, Uvicorn, Multipart-, SSE-, HTTP-, YAML- und
Zeitzonenabhaengigkeiten. `api_fastapi_server/requirements.txt` ist die
zusaetzliche Docker-/Entwicklungsquelle fuer den Server.

Die Browseroberflaeche unter `api_fastapi_server/static/index.html` ist ein
statisches Asset und hat keinen Node-, Bundler- oder Transpiler-Build. Der
Compose-Service `browserclient` mountet sie direkt in `nginx:alpine`; die
Proxyregeln aus `docker/nginx.conf` leiten `/ws`, `/health`, `/config`, `/api`
und `/v1` an den Server weiter. Aenderungen an der statischen Datei erfordern
kein Python-Wheel, aber einen Container-Recreate beziehungsweise ein neues
Image, wenn das Asset nicht als Hostmount genutzt wird.

### Extras- und Installationsmatrix

`tests/install_extras_matrix.py` prueft optionale Installationskombinationen in
isolierten Umgebungen. Diese Matrix ist langsamer und netzwerkabhaengig; sie
gehoert vor Aenderungen an `requirements.txt`, Extras oder Python-Markern in
die Abnahme. Die schnelle Unit-Suite verwendet `requirements-dev.txt`.

## Versions- und Releasepflege

Die Produktversion hat genau eine Authority (AP-SRV-070): die
source-controlled Datei `VERSION` im Repository-Root, aufgeloest ueber
`VoiceSTT/_version.py`. `setup.py`, das importierbare Paket
(`VoiceSTT.__version__`), der laufende Server und der Protocol-v2-Handshake
(`serverVersion`) lesen alle denselben Resolver; keiner dieser Orte pflegt
mehr eine eigene Versionskonstante.

Ein Release-Kandidat kann die Version ueber die validierte Umgebungsvariable
`VOICESTT_BUILD_VERSION` injizieren, ohne `VERSION` vor dem Tag dauerhaft zu
aendern. Ein ungueltiger Override wird hart abgelehnt, nie still verworfen.

Die kuenftige Release-Bedienung (W5/W6) folgt dem Muster
`python release.py` (Patch), `--minor`, `--major` - ohne manuelle
Versionspflege durch den Benutzer. Bis dahin muss ein Projekt-Release
mindestens folgende Stellen konsistent halten:

1. Version in `VERSION` aendern (spaeter automatisiert durch `release.py`).
2. `RELEASE_NOTES.md` von `Unreleased` in einen datierten Versionsabschnitt
   ueberfuehren.
3. Unit-Tests, Paketbuild, `twine check` und relevante Realmodelltests
   ausfuehren.
4. Git-Tag erst auf dem geprueften Commit setzen.
5. Dockerimages mit unveraenderlicher Commit-/Versionsreferenz zusaetzlich zum
   lokalen Betriebs-Tag versehen.

Das Repository besitzt aktuell keinen versionierten GitHub-Actions-Workflow.
Build-, Test- und Releaseabnahme werden daher lokal beziehungsweise ueber die
VPS-Automation ausgefuehrt und muessen im Release-Log nachvollziehbar bleiben.

## Python-Paket bauen

Empfohlen ist der isolierte PEP-517-Build ueber `build`:

```bash
python -m venv .venv-build
. .venv-build/bin/activate
python -m pip install --upgrade pip build twine
python -m build
python -m twine check dist/*
```

Der Projektordner `build/` ist absichtlich Dokumentation. Setuptools kann bei
einem direkten `setup.py build` zusaetzliche Unterordner darin erzeugen. Fuer
einen manuellen Legacy-Build deshalb einen separaten Build-Basisordner nutzen:

```bash
python setup.py build --build-base .build-python
```

Wichtige Paketbesonderheiten:

- `VoiceSTT`, Serverpakete und statische Assets werden explizit gepackt.
- Der angepasste `build_py`-Befehl verhindert doppelte/veraltete Servermodule
  im Wheel.
- `stt-install-kroko` wird als Console-Script aus
  `VoiceSTT.install_kroko:main` registriert.
- Kroko-ONNX selbst ist keine Standardabhaengigkeit und wird separat gebaut.

## Kroko im Detail

### Community und Pro

| Merkmal | Community (`free`) | Pro/Commercial (`pro`) |
| --- | --- | --- |
| Modelllizenz | Laut Kroko CC-BY-SA | Separater Commercial-/OEM-Vertrag oder zugelassener Key |
| Typischer Zweck | Hobby, Forschung, freie Angebote | Professionelle und produktive Nutzung |
| Runtime-Build | Standard, `KROKO_LICENSE=OFF` | Explizit `KROKO_LICENSE=ON` |
| Modellquelle | Oeffentlich bei `Banafo/Kroko-ASR` | Kroko-Portal, nur mit Berechtigung |
| Key | Nicht erforderlich | Erforderlich |
| Netzwerk zur Laufzeit | Fuer lokale Modelle nicht erforderlich | Lizenzserver fuer Validierung/Fingerprint/Nutzungsdauer |

Kroko bietet nach der aktuellen Anbieter-Dokumentation einen dauerhaften,
kostenlosen Key ausschliesslich fuer nicht-kommerzielle Nutzung sowie einen
zeitlich begrenzten Trial-Key. Die Community-Modelllizenz und die Bedingungen
eines Pro-Keys sind getrennte Sachverhalte. Vor kommerzieller Nutzung sind die
konkreten Kroko-Vertragsbedingungen zu pruefen.

Offizielle Quellen:

- [Kroko On-premise und Lizenzen](https://docs.kroko.ai/on-premise/)
- [kroko-onnx Quellprojekt](https://github.com/kroko-ai/kroko-onnx)
- [Community-Modelle](https://huggingface.co/Banafo/Kroko-ASR)

### Kroko-Builder-CLI

Der Befehl `stt-install-kroko --build` wird durch das Extra `kroko-builder`
installiert:

```bash
python -m pip install '.[kroko-builder]'
stt-install-kroko --build
```

Ohne `--build` zeigt der Helfer nur die Nutzungsanforderung und fuehrt keinen
Checkout aus. Mit `--build` laeuft folgender Prozess:

1. Der Build-Fingerprint wird aus den deklarierten Buildinputs berechnet.
2. Existiert im Artifact-Store bereits ein verifiziertes Artefakt fuer genau
   diesen Fingerprint, wird es **wiederverwendet** - es wird nichts kompiliert.
3. Sonst: Git, Schreibrechte und plattformspezifische Werkzeuge pruefen.
4. `kroko-ai/kroko-onnx` wird geklont bzw. wiederverwendet und anschliessend
   auf die **immutable gepinnte Revision** ausgecheckt (nicht auf den
   Branch-Head).
5. VoiceSTT wendet reproduzierbare Patches fuer Windows-Builds und die
   Unterdrueckung asynchroner Lizenzmeldungen an.
6. Linux baut ein CPU-Wheel direkt aus dem Checkout; Windows verwendet den
   vorgelagerten Docker-Workflow.
7. Das Wheel wird verifiziert und atomar im Artifact-Store abgelegt.
8. Das Wheel wird installiert, sofern `--skip-install` nicht gesetzt ist; dabei
   wird geprueft, dass die installierte Runtime wirklich die erwartete Variante
   ist.
9. Bei `--variant pro` setzt der Builder `KROKO_LICENSE=ON`; `free` setzt die
   lizenzierte Runtime nicht frei. Der Pro-**Key** wird zum Bauen nie benoetigt.

### Fingerprint und Artifact-Store (AP-SRV-070 W4A)

Der native Kroko-Build ist vom normalen VoiceSTT-Build entkoppelt. Der
Fingerprint (`VoiceSTT/kroko/fingerprint.py`) umfasst ausschliesslich
buildwirksame Inputs: gepinnte Upstream-Revision, Variante, Zielplattform,
Architektur, Python-ABI, Buildflags, Toolchain-Identitaet sowie die beiden
deklarierten Revisionen fuer VoiceSTTs eigene buildwirksame Logik
(`patchSetRevision`, `builderRevision`).

**Nicht** enthalten sind Serverlogik, Wake-Word-Code, Doku und insbesondere die
Produktversion aus `VERSION`/`VOICESTT_BUILD_VERSION` (W3). Eine reine
Versionserhoehung kompiliert Kroko also nicht neu.

#### Deklarierte Revisionen und ihre Updatepflicht

Der Fingerprint hasht bewusst **deklarierte Werte** statt Quelldateien, damit
ein Edit an unbeteiligtem VoiceSTT-Code keinen 30-Minuten-Build entwertet. Die
Kehrseite: VoiceSTTs eigene buildwirksame Logik muss deklariert werden. Dafuer
gibt es zwei source-controlled Konstanten in `VoiceSTT/kroko/buildinputs.py`:

| Konstante | Deckt ab | Wann erhoehen |
| --- | --- | --- |
| `PATCH_SET_REVISION` | Was VoiceSTT an den Upstream-**Quellen** patcht (WebSocket ON, OpenSSL-Beschaffung, native Lizenzausgabe) | Sobald sich der Inhalt dieser Patches aendert |
| `BUILDER_REVISION` | Wie gebaut wird: welche Revision ausgecheckt wird, welche Patches angewandt werden, wie der Compiler aufgerufen wird, welches erzeugte Wheel als Artefakt genommen wird | Sobald sich diese Builderlogik buildwirksam aendert |

Beide Konstanten sind Fingerprint-Inputs; eine Erhoehung invalidiert gespeicherte
Artefakte also korrekt.

**Die Updatepflicht ist erzwungen, nicht nur dokumentiert:** der Guard-Test
`tests/unit/test_kroko_fingerprint.py::BuildEffectiveLogicGuardTests` hasht den
Quelltext beider Flaechen und schlaegt fehl, sobald sie sich ohne Erhoehung der
zugehoerigen Konstante aendern. Die Fehlermeldung nennt jeweils, welche
Konstante zu erhoehen und welcher Digest nachzuziehen ist.

Der Store liegt ausserhalb des Repositories und ist konfigurierbar:
`--artifact-store` oder `VOICESTT_KROKO_ARTIFACT_STORE`, sonst der
Benutzer-Cache. Free und Pro liegen in strikt getrennten Namespaces.

Alle Optionen:

| Option | Standard | Bedeutung |
| --- | --- | --- |
| `--build` | aus | Build ueberhaupt ausfuehren |
| `--variant free\|pro` | `free` | Community- oder lizenzfaehige Pro-Runtime |
| `--repo URL` | offizielles Kroko-GitHub-Repo | Alternative Source-URL, etwa ein kontrollierter Mirror |
| `--branch NAME` | `cross-platform-builds` | Nur Startpunkt fuer den Clone; gebaut wird die gepinnte Revision |
| `--revision SHA` | gepinnte Revision aus `VoiceSTT/kroko/buildinputs.py` | Immutable Upstream-Commit; Aenderung erzeugt einen neuen Fingerprint |
| `--artifact-store DIR` | `VOICESTT_KROKO_ARTIFACT_STORE` bzw. Benutzer-Cache | Persistenter Artifact-Store |
| `--rebuild-kroko` | aus | Erzwingt echten Neubau trotz vorhandenem Artefakt und ersetzt es atomar |
| `--print-fingerprint` | aus | Fingerprint als JSON ausgeben, nichts bauen |
| `--describe-artifact` | aus | Fingerprint plus Artefakt-Verfuegbarkeit als JSON ausgeben, nichts bauen |
| `--work-dir DIR` | OS-Cache, bei Fehler lokal | Checkout und Buildartefakte dauerhaft ablegen |
| `--force` | aus | Vorhandenen Kroko-*Checkout* im Workdir sicher loeschen und neu klonen |
| `--skip-install` | aus | Wheel bauen, aber nicht in das aktive Python installieren |
| `-h`, `--help` | - | Aktuelle CLI-Hilfe anzeigen |

`--force` und `--rebuild-kroko` sind verschieden: `--force` verwirft den
Quell-Checkout, `--rebuild-kroko` verwirft das Ergebnis-Artefakt.

Beispiele:

```bash
# Normalfall: baut nur, wenn noch kein passendes Artefakt existiert
stt-install-kroko --build --variant pro

# Erzwungener Neubau derselben Konfiguration
stt-install-kroko --build --variant pro --rebuild-kroko

# Nur Artefakt bauen
stt-install-kroko --build --variant pro --skip-install --work-dir /build/kroko

# Maschinenlesbare CI-Schnittstelle
stt-install-kroko --print-fingerprint --variant pro
stt-install-kroko --describe-artifact --variant pro
```

Ein gebautes Wheel wird im Store zusammen mit Fingerprint, Upstream-Revision,
Python-ABI, Plattform, Variante, SHA-256 und Groesse inventarisiert; eine
separate manuelle Inventarisierung ist damit nicht mehr noetig.

### Key und Runtime

Die Engine wertet den Key in dieser Reihenfolge aus:

1. `transcription_engine_options.key`
2. `KROKO_API_KEY`
3. `KROKO_ONNX_KEY`
4. `VOICESTT_KROKO_ONNX_KEY`
5. `KROKO_KEY`

Fuer Server ist `KROKO_API_KEY` in einer nicht versionierten `env_file` die
bevorzugte Form. Ein Key in YAML oder CLI-Argumenten kann ueber Git,
Prozesslisten oder Logs offengelegt werden.

Die Pro-Runtime kontaktiert laut Kroko den Lizenzserver, um Key und erlaubte
Features zu validieren, einen Maschinen-Fingerprint zu uebermitteln und die
verarbeitete Audiodauer zu melden. Audio und Transkripte bleiben lokal. DNS,
HTTPS-Ausgang und korrekte Systemzeit muessen daher funktionieren.

### Modelle und Modell-Sharing

Modelle werden nicht in das Image kopiert. `VOICESTT_KROKO_MODEL_ROOT` zeigt
im Container standardmaessig auf `/models/kroko`; Compose mountet den Hostpfad
read-only. Community-Dateinamen koennen optional automatisch geladen werden,
Produktivdeployments verwenden jedoch lokale, vorab gepruefte Modelle und
`VOICESTT_OFFLINE_MODELS=1`.

Wenn finale und Realtime-Erkennung dasselbe Modell verwenden, setzt
`use_main_model_for_realtime: true` eine gemeinsame physische Modellinstanz
ein. Das reduziert RAM und Lizenzinitialisierungen. Auf dem dokumentierten VPS
ist dieses Sharing fuer Kroko Pro zwingend: Zwei gleichzeitig initialisierte
Pro-Recognizer fuehrten mit dem getesteten nativen Build reproduzierbar zum
Prozessende mit Exit 139. Das ist eine serverseitig beobachtete Einschraenkung,
keine allgemeine Zusage ueber alle Kroko-Versionen.

### Docker-Build

`Dockerfile` hat zwei Stages:

1. `kroko-builder` installiert Buildwerkzeuge und erzeugt das Kroko-Wheel mit
   der Build-Variante aus `ARG KROKO_VARIANT`.
2. `cpu` installiert CPU-Torch, das erzeugte Kroko-Wheel, VoiceSTT mit den
   benoetigten Extras und den FastAPI-Server. Buildwerkzeuge werden danach
   weitgehend entfernt.

Der Build-Arg ist nur waehrend des Builds gueltig:

```bash
docker build --pull --target cpu \
  --build-arg KROKO_VARIANT=pro \
  -t voicestt-cpu:pro .
```

Ein normales `docker compose up --build` ohne gesetzte Variante baut bewusst
Community. `docker-compose.yml` reicht deshalb
`${VOICESTT_KROKO_VARIANT:-free}` als Build-Arg weiter; `tools/compose.py`
setzt den Wert aus `deployment.kroko_variant`.

### Schnelles Pro-Wheel-Upgrade

`Dockerfile.pro-upgrade` ist ein enger Reparaturpfad, kein Ersatz fuer einen
vollstaendigen Release-Build. Es nimmt ein vorhandenes Runtime-Image und
ersetzt nur das Kroko-Wheel durch das Artefakt eines bereits gebauten
Pro-Builder-Images. Vorher muessen die referenzierten Image-Tags existieren.

Beispiel mit den derzeit im Dockerfile erwarteten Tags:

```bash
docker build --target kroko-builder --build-arg KROKO_VARIANT=pro \
  -t selfhost/stt-voice:kroko-builder-pro .
docker build -f Dockerfile.pro-upgrade -t selfhost/stt-voice:pro-candidate .
```

Danach sind mindestens Import, Lizenzinitialisierung, `/health`, eine reale
HTTP-Transkription und Realtime-WebSocket-Teilergebnisse zu pruefen. Der
VPS-Release verwendet fuer regulaere Veroeffentlichungen den vollstaendigen
Build, weil dabei alle Projekt- und Abhaengigkeitsaenderungen enthalten sind.

## Docker Compose und Konfiguration

Der portable Launcher `tools/compose.py` liest ausschließlich den Abschnitt
`deployment` aus `config.yaml`, findet vorhandene Modellordner und setzt die
notwendigen Compose-Variablen. Direkter Aufruf von `docker compose` scheitert
absichtlich, wenn erforderliche Variablen fehlen.

Wichtige Werte:

| Konfiguration | Compose-Variable | Zweck |
| --- | --- | --- |
| `deployment.image` | `VOICESTT_IMAGE` | lokaler Image-Tag |
| `deployment.kroko_variant` | `VOICESTT_KROKO_VARIANT` | `free` oder `pro` beim Build |
| `deployment.server_port` | `VOICESTT_PORT` | FastAPI-Port |
| `deployment.browser_port` | `VOICESTT_BROWSER_PORT` | Browserclient-Port |
| `deployment.cpu_threads` | `VOICESTT_CPU_THREADS` | CPU-Threadlimit |
| `deployment.model_paths.*` | jeweilige Hostpfade | read-only Modellmounts |
| `deployment.runtime_data` | `VOICESTT_DATA_PATH` | persistentes `/data` |

`settings` beschreibt den Serverstart. Persistierte Admin-Aenderungen liegen
unter `/data/config/runtime.json` und koennen YAML-Werte beim Neustart
ueberschreiben. Bei Modellwechseln und Rollbacks sind daher immer beide
Konfigurationsebenen zu pruefen.

## Deployment und Abnahme

Ein produktiver Release ist erst abgeschlossen, wenn folgende Ebenen
uebereinstimmen:

1. Git-Commit und sauberer Checkout.
2. Image-ID und erwartete Kroko-Variante.
3. Compose-/YAML-Konfiguration und persistierte Runtime-Konfiguration.
4. Mounts fuer Modelle, Daten und Secrets.
5. `/health` mit `ok=true`, `ready=true`, erwarteten Engines/Modellen und bei
   geteiltem Kroko `sharedWithFinal=true`.
6. Reale HTTP-Dateitranskription.
7. Realtime-WebSocket mit Partial- und Final-Ergebnis.
8. Unauffaellige Containerlogs und erfolgreicher Neustarttest.

Der generische Build endet am versionierten Image und an portablen
Konfigurationsvorlagen. Reverse Proxy, externe Docker-Netze, konkrete
Hostpfade, Backupnamen und Release-Logs sind servergebunden. Fuer Marcos VPS
gilt [`build/vps/README.md`](vps/README.md).

## Rollback

Vor jedem Imagewechsel das aktuell laufende Image unter einem unveraenderlichen
Rollback-Tag sichern. Zusaetzlich sichern:

- Compose und YAML,
- `/data/config/runtime.json`, falls vorhanden,
- verwendeten Git-Commit und Image-ID,
- aktive Modellnamen aus `/health`.

Ein reines Image-Rollback kann fehlschlagen, wenn die persistierte
Runtime-Konfiguration weiterhin ein Pro-Modell verlangt, das alte Image aber
nur ein Free-Wheel enthaelt. In diesem Fall muss die zum Image passende
Runtime-Konfiguration gemeinsam wiederhergestellt werden.

## Fehlerdiagnose

| Symptom | Wahrscheinliche Ursache | Pruefung/Loesung |
| --- | --- | --- |
| Pro-Modell meldet Payload-/Blockfehler | Free-Wheel im Image | Image explizit mit `KROKO_VARIANT=pro` neu bauen |
| Lizenz fehlt/ungueltig | Key nicht im Container oder falsche Berechtigung | Nur Variablennamen/`docker exec env` pruefen, Key nie ausgeben; Kroko-Portal kontrollieren |
| Lizenzserver nicht erreichbar | DNS, Egress, TLS oder Systemzeit | HTTPS-Ausgang und Uhrzeit des Hosts pruefen |
| Container endet mit 139 beim zweiten Pro-Modell | Zwei native Pro-Recognizer | Dasselbe Pro-Modell teilen und `use_main_model_for_realtime: true` setzen |
| YAML-Aenderung wirkt nicht | `/data/config/runtime.json` ueberschreibt sie | Persistierte Runtime ueber Admin-API anpassen oder kontrolliert entfernen |
| Docker baut trotz Pro-Key Community | Key beeinflusst den Build nicht | `--build-arg KROKO_VARIANT=pro` verwenden |
| `stt-install-kroko` fehlt | `kroko-builder`-Extra nicht installiert | `python -m pip install '.[kroko-builder]'` |
| Windows-Builder findet Docker nicht | Docker Desktop Engine nicht gestartet | `docker version` auf Client und Server pruefen |
| Asynchrone Lizenzmeldungen trotz Quiet-Option | Altes/ungepatchtes Kroko-Wheel | Mit aktuellem VoiceSTT-Installer neu bauen |

## Reproduzierbarkeits-Checkliste

- [ ] Quellcommit dokumentiert und Checkout sauber
- [ ] Python-Version und Plattform dokumentiert
- [ ] Gewaehlte Extras dokumentiert
- [ ] Kroko-Variante explizit `free` oder `pro`
- [ ] Kroko-Quellbranch/-commit nachvollziehbar
- [ ] Keine Secrets oder Modelle im Buildkontext
- [ ] `pip check` erfolgreich
- [ ] Unit-Tests erfolgreich
- [ ] Paketartefakte mit `twine check` geprueft
- [ ] Compose-Konfiguration renderbar
- [ ] Health prueft aktive Modelle, nicht nur den HTTP-Status
- [ ] HTTP- und WebSocket-Smoke-Test erfolgreich
- [ ] Rollback-Image und passende Runtime-Konfiguration gesichert

## Weiterfuehrende Referenzen

- [`docs/installation.md`](../docs/installation.md): Extras und
  plattformspezifische Installation
- [`docs/engines/kroko-onnx.md`](../docs/engines/kroko-onnx.md): Engine-Optionen
  und Recorder-Nutzung
- [`docs/testing.md`](../docs/testing.md): Teststufen und reale Modelltests
- [`docs/fastapi-server.md`](../docs/fastapi-server.md): Serverprotokoll und
  Laufzeitkonfiguration
- [`docs/licenses.md`](../docs/licenses.md): Lizenzhinweise aller Engines
- [`build/vps/README.md`](vps/README.md): konkrete VPS-Automation
