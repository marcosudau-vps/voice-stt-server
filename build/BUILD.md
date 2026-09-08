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

### Oeffentliches Production-Image (AP-SRV-070 W4C)

Der Production-Docker-Pfad kompiliert Kroko nie selbst und installiert
VoiceSTT nie editable: `tools/build_production.py` baut zuerst das
VoiceSTT-Wheel (`python -m build`), loest danach ueber den vorhandenen
Kroko-Fingerprint-/Artifact-Store (W4A) ein verifiziertes Linux/AMD64-Wheel
auf (REUSE, sonst einmaliger Build im eigenstaendigen
[`build/kroko-builder.Dockerfile`](kroko-builder.Dockerfile)) und baut dann
erst das eigentliche Production-Image aus dem neuen zweistufigen
`Dockerfile` (Ubuntu 24.04, `builder`/`runtime`, non-root, kein
Kroko-Builder-Stage):

```bash
python tools/build_production.py free
python tools/build_production.py pro
python tools/build_production.py all
```

Jeder Lauf schreibt `dist/build-manifest.json` mit Git-Commit, VoiceSTT- und
Kroko-Artefaktidentitaet, Image-Tags und Image-ID. Die beiden oeffentlichen
Produktidentitaeten sind `voice-stt-server` (Free) und `voice-stt-server-pro`
(Pro) - beide mit demselben VoiceSTT-Stand, nur mit unterschiedlichem
Kroko-Build-Input. Ein vorhandener Kroko-Runtime-Key ist niemals Build-Input
und kann eine Free-Variante nie zu Pro machen.

Danach mit dem oeffentlichen, portablen `docker-compose.yml` starten:

```bash
VOICESTT_IMAGE=voice-stt-server:local docker compose up -d
curl -fsS http://127.0.0.1:8010/health
```

`docker-compose.yml` hat portable Defaults fuer Port, Datenverzeichnis und
optionale Custom-Model-Pfade; kein Wert ist an Marcos Infrastruktur
gebunden. Fuer Pro `VOICESTT_IMAGE=voice-stt-server-pro:local` setzen und den
Lizenz-Key erst zur Laufzeit als Secret bereitstellen (`VOICESTT_API_KEY`
bzw. `KROKO_API_KEY` ueber `env_file`, nie im Compose-File selbst):

```bash
docker run --rm -e KROKO_API_KEY voice-stt-server-pro:local \
  /opt/venv/bin/python -c 'import kroko_onnx; print("Kroko runtime importiert")'
```

Marcos bestehende lokale/VPS-nahe Komfortschicht (`tools/compose.py` +
`config.yaml`'s `deployment`-Abschnitt) bleibt fuer sein eigenes Environment
nutzbar; Custom-Model-Pfade daraus sind jetzt optional statt Pflichtwerte.
Die produktive VPS-Variante bleibt unter [`build/vps`](vps/README.md)
festgelegt und ist nicht Teil des oeffentlichen Pfads.

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
| Production-Image Free | `python tools/build_production.py free` | `voice-stt-server:<version>` (Ubuntu 24.04, non-root) |
| Production-Image Pro | `python tools/build_production.py pro` | `voice-stt-server-pro:<version>`, gleicher VoiceSTT-Stand |
| Production-Image beide | `python tools/build_production.py all` | Beide Images plus `dist/build-manifest.json` |
| Nur Kroko-Builder-Image | `docker build -f build/kroko-builder.Dockerfile -t voicestt-kroko-builder .` | Eigenstaendiges Linux/AMD64-Builder-Image (W4A-Pfad, ausserhalb des Production-Images) |
| Pro-Wheel-Upgrade | `docker build -f Dockerfile.pro-upgrade -t voicestt-cpu:pro-upgrade .` | Marcos enger `selfhost/stt-voice`-Reparaturpfad; nicht Teil des oeffentlichen W4C-Pfads |

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
einzelnes, selbstenthaltenes statisches Asset ohne Node-, Bundler- oder
Transpiler-Build und ohne externe Asset-Referenzen; `setup.py` paketiert sie
als `package_data`. `api_fastapi_server/server.py` liest sie relativ zum
installierten Modul und liefert sie unter `/` aus - seit AP-SRV-070 W4C
braucht die oeffentliche Production Compose dafuer keinen separaten
`nginx`/Browserclient-Container und keinen Source-Bind-Mount mehr; `stt-server`
liefert API, WebSocket und Browseroberflaeche aus einem Container. Der
historische `nginx:alpine`-Compose-Service und `docker/nginx.conf` bleiben im
Repository liegen, sind aber nicht mehr Teil des Production-Compose-Pfads.
Aenderungen an der statischen Datei erfordern ein neues VoiceSTT-Wheel plus
Imagebuild, da sie nicht mehr als Hostmount genutzt wird.

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

### Der Release-Orchestrator (AP-SRV-070 W5)

`release.py` im Repository-Root ist die eine kanonische Release-Bedienung;
es gibt keine zweite, konkurrierende Release-Authority. Die eigentliche
Implementierung liegt in `release_tooling/` (Preflight, Dry-Run,
resumable State, RC-Manifest); `release.py` selbst delegiert nur dorthin.

```bash
python release.py --help
python release.py preflight
python release.py dry-run
python release.py status
python release.py manifest validate <pfad>
```

`preflight` ist rein lesend und prueft unter anderem VERSION, den
`RELEASE_NOTES.md`-Abschnitt, sauberen/exakten Git-Zustand, Tag-Abwesenheit
bzw. -Kompatibilitaet, Tool-Verfuegbarkeit sowie Registry-Konfiguration und
Credential-*Praesenz* (nie den Wert selbst).

### GitHub-nativer Build und Release (AP-SRV-070 W5-R04)

Seit W5-R04 wird ein Release-Kandidat vollstaendig auf einem frischen,
GitHub-gehosteten Linux-Runner aus einem exakten Quellcommit erzeugt. Kein
Operator-Rechner, kein lokaler Kroko-Artefaktspeicher, kein vorgebautes Wheel,
kein lokales Image und keine lokalen Registry-Zugangsdaten sind Teil der
Release-Autoritaet.

Zwei Workflows, beide ausschliesslich per `workflow_dispatch`:

| Workflow | Zweck | Schreibrechte |
| --- | --- | --- |
| `.github/workflows/release-candidate.yml` | Kandidat bauen und qualifizieren | nur `packages: write` fuer **private** GHCR-Staging-Pakete |
| `.github/workflows/release-publish.yml` | Kandidat veroeffentlichen | pro Job nur das noetige Recht, alles in der geschuetzten Umgebung `release` |

Die gewoehnliche CI (`.github/workflows/ci.yml`) ist durchgehend
`contents: read` und kann strukturell nichts veroeffentlichen.

Zwei vollstaendige, alternative Distributionen werden dabei gebaut:

```text
exakter Commit/Tree
  ├── Kroko Free  -> voice-stt-server      -> Image voice-stt-server
  └── Kroko Pro   -> voice-stt-server-pro  -> Image voice-stt-server-pro
```

Jedes Distributions-Wheel enthaelt die passende native Kroko-Laufzeit bereits
(`tools/build_distribution.py` fuegt das qualifizierte Kroko-Wheel byteweise
ein und taggt das Ergebnis auf die reale Plattform um). Ein Endanwender baut
Kroko also nie selbst. Es gibt bewusst **kein** separates oeffentliches
Kroko-Paket und **keinen** sdist fuer diese beiden Distributionen - ein sdist
koennte die native Laufzeit nicht transportieren und wuerde die
Vollstaendigkeitsgarantie brechen.

Kroko-Artefakte werden ueber den GitHub-Actions-Cache wiederverwendet, mit dem
**autoritativen Fingerprint** als Schluessel, der im Buildcontainer aufgeloest
wird. Free und Pro haben getrennte Schluessel und getrennte Namensraeume. Der
Cache ist immer nur Optimierung: jedes wiederverwendete Artefakt wird gegen die
bestehende Fingerprint-/Artefakt-Autoritaet revalidiert, und ein Cache-Miss
baut aus der Quelle.

Der lokale Orchestrator dafuer ist `tools/release_candidate.py`:

```bash
# Nur die autoritativen Fingerprints ausgeben (Cache-Schluessel)
python tools/release_candidate.py --print-fingerprints

# Vollstaendigen Kandidaten lokal bauen, ohne Staging-Push
python tools/release_candidate.py --out-dir candidate --no-manifest
```

Vollstaendige Prozessbeschreibung, Zustandsreihenfolge, Resume-Semantik und die
komplette Operator-Einrichtung (eine Repository-Variable, ein Repository-Secret,
zwei PyPI Trusted Publisher, eine geschuetzte Umgebung):
[`docs/release-process.md`](../docs/release-process.md).

### Eine Engine fuer Dry-Run und echte Publikation (AP-SRV-070 W5-R01-C1)

`release_tooling/engine.py` ist die eine Stelle, an der die feste
W6-Publikationsreihenfolge als Daten kodiert ist (`STEP_DEFINITIONS`), nicht
als verstreute Fallunterscheidung:

```text
PREPARED -> TAGGED -> PyPI (Free + Pro) -> Docker Hub -> GHCR
  -> externe Verifikation -> bewegliche Aliase -> GitHub Release
  -> finale Verifikation -> COMPLETE
```

> **AP-SRV-070 W5-R04** hat diese Reihenfolge geaendert. Der Git-Tag entsteht
> jetzt **zuerst**, nicht zuletzt: sobald `2.0.0` auf PyPI oder in einer
> Registry existiert, ist die Version oeffentlich belegt, also muss der
> unveraenderliche Quellanker bereits vorher existieren. Docker Hub steht vor
> GHCR, weil GHCR dasselbe Manifest per Digest uebernimmt statt es erneut zu
> bauen. Bewegliche Aliase (`2.0`, `2`, `latest`) bewegen sich erst nach
> verifizierten exakten Artefakten in beiden Registries. Vollstaendige
> Beschreibung und Operator-Einrichtung:
> [`docs/release-process.md`](../docs/release-process.md).

`python release.py dry-run` und `python release.py publish` rufen beide
dieselbe Funktion `engine.run_engine()` mit demselben Adapter-Bundle auf -
der einzige Unterschied ist `ExecutionMode.DRY_RUN` gegenueber
`ExecutionMode.REAL`. Jeder Schritt prueft zuerst rein lesend den
Remote-Zustand (`adapter.verify()` - sicher in beiden Modi); nur im
REAL-Modus und nur wenn dabei "noch nicht vorhanden" herauskommt, wird
`adapter.publish()` ueberhaupt aufgerufen. Im DRY_RUN-Modus ist es
strukturell unmoeglich, dass `publish()` jemals aufgerufen wird - das ist
keine Konvention, sondern eine Eigenschaft der Engine-Schleife selbst
(siehe `tests/unit/test_release_engine.py::DryRunNeverWritesTests`).

`release_tooling/adapters.py` implementiert die echten Publikationsadapter
(PyPI fuer **beide** Distributionen - auf dem GitHub-Weg ueber PyPI Trusted
Publishing, lokal ueber Twine; Docker Hub und GHCR ueber
`docker buildx imagetools create`, also Manifest-Promotion per Digest statt
eines zweiten Builds; bewegliche Aliase; Git-Tag ueber `git tag`/`git push`;
GitHub Release ueber `gh release create`) sowie zwei rein lesende
Verifikationsadapter (externe/finale Verifikation, die verlangen, dass
alle darunterliegenden Adapter `MATCH` melden). Kein Adapter liest, loggt
oder speichert jemals einen Credential-Wert - jedes Werkzeug liest seinen
eigenen etablierten Zugangsdatenvertrag direkt aus der Prozessumgebung
(Twines `TWINE_USERNAME`/`TWINE_PASSWORD`/`TWINE_API_KEY`, `docker login`,
gits Credential-Helper, `gh`s `GH_TOKEN`/`GITHUB_TOKEN`) - dieser Code fasst
den Wert nie an.

Der Git-Tag entsteht bewusst **frueh** (W5-R04): sowohl die feste
Schrittreihenfolge als auch `GitTagAdapter.publish()` selbst
(`state.assert_tag_allowed()`) verhindern eine Tag-Erstellung, sobald bereits
ein oeffentliches Artefakt existiert. Umgekehrt verlangt jeder unumkehrbare
oeffentliche Schreibvorgang (PyPI, Docker Hub, GHCR, Aliase) ueber
`state.assert_public_publication_allowed()`, dass der Tag bereits existiert.
`state.assert_aliases_allowed()` verlangt zusaetzlich verifizierte exakte
Artefakte in beiden Registries, und `assert_github_release_allowed()`
verlangt gesetzte Aliase - das GitHub Release bleibt der letzte oeffentliche
Erfolgsmarker. Ein Versuch, diese Reihenfolge zu umgehen, ist ein harter
Fehler (`OrderError`), keine stille Ausnahme.

Der Release-State (`release_state/<version>.json`, git-ignoriert, niemals
Secrets) bindet die exakte Quell-Commit-/Tree-Identitaet, beide
Distributions-Wheels, beide Image-Manifest-Digests und die Identitaet des
qualifizierten Kandidaten an eine Version und laesst sich nach einem
Teilausfall wieder aufnehmen - ohne die Version automatisch zu wechseln
(Abschnitt "Kein verschwendeter oeffentlicher Versionsstand" weiter unten).
Ein bereits vorhandenes, abweichendes Remote-Artefakt (PyPI-Release,
GHCR-/Docker-Hub-Tag, Git-Tag, GitHub Release) fuehrt zu einem harten Stopp
(`ConflictError`), nie zu einem stillen Ausweichen auf eine neue Version.
Selbst wenn der lokale State nach einem Absturz nicht mitgeschrieben wurde,
aber die externe Operation tatsaechlich erfolgreich war, erkennt die Engine
das beim naechsten Lauf automatisch (derselbe lesende
`verify()`-vor-`publish()`-Schritt reconciled den State, statt ihn erneut
auszufuehren).

`python release.py publish --manifest <RC-Manifest> --yes` fuehrt die echte
Engine im `ExecutionMode.REAL` aus. Ohne `--manifest` oder ohne `--yes`
verweigert der Befehl sofort, ohne irgendetwas zu lesen oder zu schreiben;
mit beidem laeuft zuerst ein vollstaendiger Preflight, und erst bei
`passed: true` wird ueberhaupt ein Adapter konstruiert. AP-SRV-070 W5-R01-C1
implementiert und qualifiziert diese Engine vollstaendig mit injizierten
Fake-Adaptern (`tests/unit/test_release_engine.py`,
`tests/unit/test_release_adapters.py`) - sie fuehrt selbst keinen echten
oeffentlichen Schreibvorgang aus, weil dafuer echte Zugangsdaten und eine
echte Zielregistry noetig sind. W6 ruft dieselbe, hier bereits qualifizierte
Engine mit echten Zugangsdaten auf, statt neue kritische Publikationslogik
nach der RC-Qualifikation einzufuehren.

`python release.py prepare-next-version [--minor|--major] [--apply]` ist die
**zukuenftige** Versionsvorbereitung (`--minor`/`--major` wie im bisherigen
Konzept) und bewusst vom aktuellen Publikationspfad getrennt: ohne `--apply`
berechnet der Befehl nur die naechste Version, ohne `VERSION` zu schreiben.

### RC-Manifest (AP-SRV-070 W5/W6)

`release_tooling.rc_manifest` definiert das eine kanonische Format fuer
einen Release-Kandidaten (`W5-RC1`, `W5-RC2`, ...): Produktversion,
Quell-Commit/-Tree, Wheel-/Sdist-Datei plus SHA-256, Kroko-Free-/Pro-
Fingerprint plus Artefakt-SHA-256, Free-/Pro-Image-Tag plus Image-ID,
OCI-Version/-Revision, Qualifizierungszeitpunkt/-kontext und
Freigabestatus - ohne jegliches Secret. W5-R02 friert genau ein solches
Manifest ein; W6 darf nichts veroeffentlichen, das von den darin gebundenen
Identitaeten abweicht.

### Kein verschwendeter oeffentlicher Versionsstand

Ein teilweiser Veroeffentlichungsfehler darf niemals automatisch eine neue
Produktversion erzeugen. Gelingt W6 zum Beispiel PyPI, aber nicht GHCR, nimmt
ein erneuter Lauf **dieselbe** Version wieder auf - niemals automatisch
`2.0.1`. Nur eine bewusste menschliche Entscheidung vor Beginn der
Veroeffentlichung darf die Version wechseln.

### Freigabeprozess bis zum echten W6-Publish

1. Version in `VERSION` aendern (`release.py prepare-next-version --apply`
   fuer die naechste Version; der aktuelle Publikationspfad selbst aendert
   `VERSION` nie).
2. `RELEASE_NOTES.md` von `Unreleased` in einen Versionsabschnitt
   ueberfuehren.
3. `python release.py preflight` und `python release.py dry-run` pruefen.
4. Unit-Tests, Paketbuild, `twine check` und relevante Realmodelltests
   ausfuehren.
5. W5-R02 friert das RC-Manifest fuer exakt diesen Commit ein.
6. W6 fuehrt `python release.py publish --manifest <RC-Manifest> --yes`
   gegen das eingefrorene Manifest aus; der Git-Tag entsteht erst nach
   externer Verifikation. Vor diesem Lauf muessen
   `VOICESTT_RELEASE_GHCR_REPO`/`VOICESTT_RELEASE_DOCKERHUB_REPO` gesetzt
   und die Zugangsdaten der jeweiligen Werkzeuge (Twine, `docker login`,
   Git-Credential-Helper, `gh auth login`) bereits vorhanden sein - keiner
   dieser Werte wird von `release_tooling` selbst verwaltet oder gelesen.

### GitHub Actions CI (AP-SRV-070 W5)

`.github/workflows/ci.yml` ist der oeffentliche CI-Workflow: Checkout,
Paketbuild (Wheel + Sdist), `twine check`, Installation aus dem gebauten
Wheel (nie editable) samt `pip check`/Import-/Versions-/Console-Script-/
Asset-Pruefung, sowie die schnelle Unit-/Guard-/Release-Tool-Suite
(`python -m pytest -q tests/unit`) auf Windows und Ubuntu 24.04 mit
Python 3.12. Der Workflow triggert auf Pull Requests, Pushes auf
`main`/`feat/**`/`work/**` und `workflow_dispatch`; er verlangt kein
Kroko-Pro-Runtime-Secret, baut kein natives Kroko und veroeffentlicht,
taggt oder released nichts.

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
(`patchSetRevision`, `builderRevision`). Auf Linux gehoert ausserdem die
effektive OpenSSL-Development-Identitaet (Quelle, Version, Header und
Bibliotheken samt Inhalts-Hashes) zum Fingerprint. zlib wird nicht separat
aufgenommen, solange der aktuelle Buildpfad keine eigenstaendig ausgewaehlte
zlib-Development-Authority konsumiert.

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
| `WINDOWS_BUILDER_REVISION` | Wie der Windows-Dockerpfad baut und das Wheel auswaehlt | Sobald sich diese Windows-Builderlogik buildwirksam aendert |
| `LINUX_BUILDER_REVISION` | Wie der native Linuxpfad baut, Toolchaininputs aufloest und das Wheel retaggt | Sobald sich diese Linux-Builderlogik buildwirksam aendert |

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
| `--artifact-retention-days N` | `30` bzw. `VOICESTT_KROKO_ARTIFACT_RETENTION_DAYS` | Alter fuer best-effort Cleanup; `0` deaktiviert |
| `--openssl-root-dir DIR` | `OPENSSL_ROOT_DIR` oder System-Development-Stack | Autoritative OpenSSL-Header/Bibliotheken fuer Linux |
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

Linux-Wheels tragen den Build-Tag `1free` beziehungsweise `1pro` sowohl im
Dateinamen als auch in `.dist-info/WHEEL`; der RECORD-Eintrag wird dabei neu
gehasht. Free und Pro bleiben in getrennten Namespaces parallel erhalten.
Retention-Cleanup ist best-effort und schuetzt immer den aktuellen
Fingerprint, den neuesten verifizierten LKG-Slot, die jeweils andere Variante
und gesperrte Slots.

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

### Docker-Build (AP-SRV-070 W4C)

`Dockerfile` hat seit W4C zwei Stages, beide `ubuntu:24.04`, und keine davon
kompiliert Kroko:

1. `builder` installiert eine venv unter `/opt/venv` und installiert darin
   CPU-Torch, das bereits aufgeloeste Kroko-Wheel (`dist/kroko/*.whl`) und
   das bereits gebaute VoiceSTT-Wheel (`dist/voicestt/*.whl`) mit den
   benoetigten Extras.
2. `runtime` kopiert nur `/opt/venv` in ein schlankes Ubuntu-24.04-Image,
   legt den nicht-root Benutzer `voicestt` und `/var/lib/voicestt` an und
   setzt den korrigierten liveness-only `HEALTHCHECK`.

Beide Wheels sind Pflicht-Build-Context-Eingaben; sie werden von
`tools/build_production.py` erzeugt (siehe oben), nicht vom Dockerfile
selbst. Der eigenstaendige Kroko-Builder lebt in
[`build/kroko-builder.Dockerfile`](kroko-builder.Dockerfile) und wird nie vom
Production-`Dockerfile` referenziert:

```bash
docker build -f build/kroko-builder.Dockerfile -t voicestt-kroko-builder .
docker run --rm -v "$PWD/.kroko-artifacts:/artifact-store" \
  -e VOICESTT_KROKO_ARTIFACT_STORE=/artifact-store \
  voicestt-kroko-builder --describe-artifact --variant pro
```

`tools/build_production.py` orchestriert genau diese beiden Schritte
(Kroko-Wheel aufloesen, dann Production-Image bauen) fuer `free`, `pro` oder
`all`.

### Schnelles Pro-Wheel-Upgrade

`Dockerfile.pro-upgrade` bleibt Marcos enger `selfhost/stt-voice`-
Reparaturpfad und ist nicht Teil des oeffentlichen W4C-Production-Pfads. Es
erwartet ein bereits gebautes `selfhost/stt-voice:kroko-builder-pro`-Image mit
dem fertigen Wheel unter `/build/kroko-work/kroko-onnx/release_artifacts/linux/`.
Das bis W4C dafuer genutzte `kroko-builder`-Target existiert im
Production-`Dockerfile` nicht mehr; wer diesen Reparaturpfad weiter nutzen
will, muss das erwartete Builder-Image ausserhalb des W4C-Pfads selbst
bereitstellen (z. B. mit einer eigenen, build/vps-gebundenen Variante, die den
Kroko-Build wie zuvor als `RUN`-Schritt in das Image backt statt ihn - wie
`build/kroko-builder.Dockerfile` - erst beim `docker run` auszufuehren). Das
ist Marcos Betreiberpfad und bewusst nicht Teil dieses Runs.

Danach sind mindestens Import, Lizenzinitialisierung, `/health`, eine reale
HTTP-Transkription und Realtime-WebSocket-Teilergebnisse zu pruefen. Der
VPS-Release verwendet fuer regulaere Veroeffentlichungen den vollstaendigen
Build, weil dabei alle Projekt- und Abhaengigkeitsaenderungen enthalten sind.

## Docker Compose und Konfiguration

Der portable Launcher `tools/compose.py` liest ausschließlich den Abschnitt
`deployment` aus `config.yaml` und setzt die entsprechenden Compose-Variablen;
seit AP-SRV-070 W4C hat `docker-compose.yml` selbst fuer alle diese Variablen
bereits portable Defaults, `tools/compose.py` ist also Komfort, keine
Voraussetzung. Ein direkter `docker compose up` ohne `tools/compose.py`
funktioniert; ohne konfigurierte Custom-Model-Pfade nutzt der Server einfach
den persistenten verwalteten Store unter `/var/lib/voicestt`.

Wichtige Werte:

| Konfiguration | Compose-Variable | Zweck |
| --- | --- | --- |
| `deployment.image` | `VOICESTT_IMAGE` | lokaler Image-Tag |
| `deployment.kroko_variant` | `VOICESTT_KROKO_VARIANT` | Label-Wert des Builds (Variantenwahl selbst passiert vor dem Imagebuild, siehe `tools/build_production.py`) |
| `deployment.server_port` | `VOICESTT_PORT` | FastAPI-/Browserclient-Port (ein Container) |
| `deployment.cpu_threads` | `VOICESTT_CPU_THREADS` | CPU-Threadlimit |
| `deployment.model_paths.faster_whisper`/`.kroko` | jeweilige Hostpfade | optionale read-only Custom-Model-Mounts; fehlend/nicht gefunden bleibt unmontiert |
| `deployment.runtime_data` | `VOICESTT_DATA_PATH` | persistentes `/var/lib/voicestt` |

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

- [`docs/release-process.md`](../docs/release-process.md): GitHub-nativer
  Releaseprozess, Zustandsreihenfolge und vollstaendige Operator-Einrichtung
- [`docs/installation.md`](../docs/installation.md): Extras und
  plattformspezifische Installation
- [`docs/kroko-onnx.md`](../docs/kroko-onnx.md): Engine-Optionen
  und Recorder-Nutzung
- [`docs/testing.md`](../docs/testing.md): Teststufen und reale Modelltests
- [`docs/fastapi-server.md`](../docs/fastapi-server.md): Serverprotokoll und
  Laufzeitkonfiguration
- [`docs/licenses.md`](../docs/licenses.md): Lizenzhinweise aller Engines
- [`build/vps/README.md`](vps/README.md): konkrete VPS-Automation
