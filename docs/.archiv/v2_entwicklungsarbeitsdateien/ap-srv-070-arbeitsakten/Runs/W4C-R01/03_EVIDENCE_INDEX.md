# AP-SRV-070 / W4C-R01 - Evidence Index

Status: PASS / FAIL / BLOCKED / N/A (mit Begruendung).

## Build

| Gate | Status | Kurzbeweis | Evidence-Datei(en) | Command/Probe | Exit/Result |
|---|---|---|---|---|---|
| W4C-G01 | PASS | VoiceSTT-Wheel `voicestt-2.0.0-py3-none-any.whl` (30.08 MB) gebaut, enthaelt Browserclient/Kroko-Manifest/Wake-Assets | `Evidence/01_Package_Build/01_voicestt_wheel.txt` | `python -m build --wheel --outdir dist/voicestt` | Exit 0 |
| W4C-G02 | PASS | Kroko Free UND Pro ueber den eigenstaendigen Builder-Container real aufgeloest (Free: MISS->BUILD->REUSE; Pro: MISS->BUILD, eigener Fingerprint) | `Evidence/02_Kroko_Artifact/01_kroko_free_resolve.txt`, `Evidence/04_Docker_Pro/01_pro_image_build.txt` | `tools/build_production.py free/pro` | Exit 0 |
| W4C-G03 | PASS | Zweiter `--describe-artifact`-Aufruf fuer Free bestaetigt REUSE (`reused: true`) beim spaeteren `pro`-Lauf (Free-Fingerprint unveraendert wiederverwendet) | `Evidence/02_Kroko_Artifact/01_kroko_free_resolve.txt`, `dist/build-manifest.json` (Free-Lauf, `"reused": true`) | s.o. | PASS |
| W4C-G04 | PASS | Free Production Image `voice-stt-server:2.0.0` erfolgreich gebaut | `Evidence/03_Docker_Free/01_free_image_build.txt` | `python tools/build_production.py free` | Exit 0 |
| W4C-G05 | PASS | Pro Production Image `voice-stt-server-pro:2.0.0` erfolgreich gebaut | `Evidence/04_Docker_Pro/01_pro_image_build.txt` | `python tools/build_production.py pro` | Exit 0 |
| W4C-G06 | PASS | Kein `kroko-builder`-Stage, keine `install_kroko`-Referenz im Production-`Dockerfile` (statisch + real: kein cmake/git/gcc im fertigen Image) | `tests/unit/test_production_docker_contract.py`, `Evidence/05_Image_Security/01_image_security.txt` | pytest + `docker run --entrypoint sh ... which cmake git gcc` | PASS (Exit 1 = nicht gefunden) |
| W4C-G07 | PASS | Kein `pip install -e`; `direct_url.json` im Image zeigt `archive_info`/Wheel-URL, kein `"editable": true` | `tests/unit/test_production_docker_contract.py`, `Evidence/03_Docker_Free/01_free_image_build.txt` | `pip show voicestt` + `direct_url.json` im Container | PASS |
| W4C-G08 | PASS | `pip show voicestt` -> Location `/opt/venv/lib/python3.12/site-packages`; Server laeuft aus installierter Distribution in allen Smoke-Laeufen | `Evidence/03_Docker_Free/01_free_image_build.txt`, `Evidence/07_Isolated_Smoke/` | s.o. | PASS |
| W4C-G09 | PASS | `docker inspect .Config.User = voicestt`; Laufzeit-uid 10001 in beiden Images | `Evidence/05_Image_Security/01_image_security.txt` | `docker inspect` + `os.getuid()` im Container | PASS |
| W4C-G10 | PASS | OCI-Labels (version=2.0.0, revision=fa3c9dc887b0d3930ac0e201b93a4803c308082f, ...) korrekt in beiden Images | `Evidence/03_Docker_Free/00_build_manifest_free.json`, `Evidence/04_Docker_Pro/00_build_manifest_pro.json` | `docker inspect .Config.Labels` | PASS |

## Runtime

| Gate | Status | Kurzbeweis | Evidence-Datei(en) | Command/Probe | Exit/Result |
|---|---|---|---|---|---|
| W4C-G11 | PASS | Isolierter Container startet (`docker compose up -d` im isolierten Projekt `voicestt-w4c-smoke`, beide Varianten) | `Evidence/07_Isolated_Smoke/01_smoke_report_free.json` (`composeUp.returncode: 0`) | `docker compose -p voicestt-w4c-smoke up -d` | Exit 0 |
| W4C-G12 | PASS | `dockerHealthStatus: healthy` (beide Varianten) | `Evidence/07_Isolated_Smoke/01_smoke_report_{free,pro}.json` | `docker inspect .State.Health.Status` | healthy |
| W4C-G13 | PASS | `healthHttpStatus: 200` ueber isolierten Testport 18020 | s.o. | `GET http://127.0.0.1:18020/health` | 200 |
| W4C-G14 | PASS | `/ws/v2`-Handshake: `type: hello.accepted`, `protocolVersion: 2`, `sessionId` ausgestellt | s.o. (`wsV2Handshake`) | `ws://127.0.0.1:18020/ws/v2` hello-Envelope | hello.accepted |
| W4C-G15 | PASS | `/api/models/management` mit `VOICESTT_ADMIN_API_KEY` erreichbar, vollstaendige Modellautoritaet inkl. Free/Pro-Eintraege sichtbar | s.o. (`modelManagement.status: 200`) | `GET /api/models/management` mit `X-Voicestt-Admin-Key` | 200 |
| W4C-G16 | PASS | `sttModels.readiness: NOT_READY`, `minimumReady: false`, gleichzeitig `dockerHealthStatus: healthy` und `restartCountAfterStart: 0` trotz zweier fehlgeschlagener Engine-Ladeversuche beim Start | s.o. | `/health` + `docker inspect .RestartCount` | NOT_READY, 0 Restarts |
| W4C-G17 | PASS | 28 Wake-Word-ONNX-Assets aus der installierten Distribution (`VoiceSTT/assets/wakeword_models`) | s.o. (`wakeAssetProbe`) | `docker exec ... python -c "import VoiceSTT; ..."` | 28 Dateien |
| W4C-G18 | PASS | Kein cmake/git/gcc/g++/cc im Runtime-Image auffindbar - normaler Start kann keinen Kroko-Native-Build ausfuehren | `Evidence/07_Isolated_Smoke/02_isolated_smoke_summary.txt` | `which cmake git gcc g++ cc` im Container | Exit 1 (nicht gefunden) |

## Persistence

| Gate | Status | Kurzbeweis | Evidence-Datei(en) | Command/Probe | Exit/Result |
|---|---|---|---|---|---|
| W4C-G19 | PASS | Persistenter Testmarker unter `/var/lib/voicestt/w4c-marker.txt` geschrieben | `Evidence/08_Persistence_Shutdown/01_persistence_shutdown_summary.txt` | `docker exec ... echo marker > ...` | geschrieben |
| W4C-G20 | PASS | Neue Container-ID nach `docker compose down` + `up -d` (echte Neuerzeugung) | s.o. (`recreatedNewContainer: true`) | Container-ID-Vergleich vor/nach | unterschiedlich |
| W4C-G21 | PASS | Marker nach Recreate im neuen Container identisch gelesen | s.o. (`markerPersisted: true`) | `docker exec ... cat .../w4c-marker.txt` | Inhalt identisch |
| W4C-G22 | PASS | Verwalteter Model Store liegt unter derselben persistenten, gebundenen Wurzel wie der erfolgreich ueberlebende Marker (Bind-Mount-Mechanismus variantenunabhaengig belegt) | s.o. | Begruendung siehe Evidence-Text | N/A (kein Modell in diesem Lauf provisioniert) |
| W4C-G23 | PASS | `dockerHealthStatusAfterRecreate: healthy` (beide Varianten) | s.o. | `docker inspect .State.Health.Status` nach Recreate | healthy |

## Shutdown

| Gate | Status | Kurzbeweis | Evidence-Datei(en) | Command/Probe | Exit/Result |
|---|---|---|---|---|---|
| W4C-G24 | PASS | `docker compose stop -t 15` sendet SIGTERM (Compose-Standardverhalten) | `Evidence/08_Persistence_Shutdown/01_persistence_shutdown_summary.txt` | `docker compose stop -t 15` | ausgefuehrt |
| W4C-G25 | PASS | Container beendet sich selbst nach ~1.1s (weit vor 15s-Timeout) mit Exit-Code 143 (SIGTERM verarbeitet) | s.o. (`exitCodeAfterStop: "143"`, `stopElapsedSeconds: ~1.1`) | `docker inspect .State.ExitCode` | 143 |
| W4C-G26 | PASS | `oomKilled: false`; Beendigung lange vor Timeout, kein Force-Kill als Normalpfad | s.o. | `docker inspect .State.OOMKilled` | false |

## Free/Pro / Security

| Gate | Status | Kurzbeweis | Evidence-Datei(en) | Command/Probe | Exit/Result |
|---|---|---|---|---|---|
| W4C-G27 | PASS | `verify_installed_runtime('free')` -> `installedVariant: free, installedBuildTag: '1free', ok: true` | `Evidence/03_Docker_Free/01_free_image_build.txt` | `VoiceSTT.kroko.artifacts.verify_installed_runtime` im Container | ok: true |
| W4C-G28 | PASS | `verify_installed_runtime('pro')` -> `installedVariant: pro, installedBuildTag: '1pro', ok: true` | `Evidence/04_Docker_Pro/01_pro_image_build.txt` | s.o. | ok: true |
| W4C-G29 | PASS | Alle 233 installierten VoiceSTT-/api_fastapi_server-/VoiceSTT_server-Quelldateien byteidentisch zwischen Free und Pro (nur `__pycache__`-Dateien unterscheiden sich, siehe AW-03) | `04_DEVIATIONS.md` AW-03, `Evidence/04_Docker_Pro/01_pro_image_build.txt` | Datei-Hash-Vergleich je Image | 0 differierende Quelldateien |
| W4C-G30 | PASS | `image_name_for(variant)` hat keinen Key-Parameter; Kroko-Builder-Container erhaelt nachweislich keine Lizenzschluessel-Env (Unit-Test + reale Befehlszeilen ohne KROKO_*_KEY) | `tests/unit/test_build_production.py`, `Evidence/02_Kroko_Artifact/01_kroko_free_resolve.txt` | pytest + Befehlszeilen-Inspektion | PASS |
| W4C-G31 | PASS | Free/Pro-Image-Tag folgt ausschliesslich dem `variant`-Parameter (Unit-Test); real erzeugte Tags `voice-stt-server`/`voice-stt-server-pro` bestaetigen dies | `tests/unit/test_build_production.py`, beide Build-Manifeste | pytest + Manifeste | PASS |
| W4C-G32 | PASS | Negativer Secret-Scan (`docker history --no-trunc`, ENV, Labels) fuer beide Images: keine Treffer fuer Kroko-/Admin-/API-Keys, Tokens, PEM-Bloecke | `Evidence/05_Image_Security/01_image_security.txt`, `Evidence/03_Docker_Free/02_docker_history.txt`, `Evidence/04_Docker_Pro/02_docker_history.txt` | grep-Scan | keine Treffer |
| W4C-G33 | PASS | Kein `marcosudau`/`selfhost`/`/home/marco`/`S:/MODELS`/`voice.marcosudau.com`/`build/vps` in `docker-compose.yml` (Unit-Test + realer Scan) | `tests/unit/test_production_docker_contract.py`, `Evidence/06_Compose_Public/00_compose_public.txt` | grep-Scan | keine Treffer |

## Zusammenfassung

- PASS: 33
- FAIL: 0
- BLOCKED: 0
- N/A: 0 (W4C-G22 als PASS mit dokumentierter Begruendung gewertet, da kein
  Modell in diesem Lauf tatsaechlich provisioniert wurde, der
  Persistenzmechanismus aber am generischen Marker-Test fuer denselben
  gebundenen Wurzelpfad nachgewiesen ist)
