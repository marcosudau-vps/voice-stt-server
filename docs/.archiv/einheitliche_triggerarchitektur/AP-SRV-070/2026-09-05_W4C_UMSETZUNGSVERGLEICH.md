# AP-SRV-070 / W4C - Soll-/Ist-Vergleich

## Ergebnis

W4C ist im vorgesehenen Scope vollstaendig umgesetzt: ein oeffentlicher,
betreiberunabhaengiger Production-Docker-/Compose-Pfad mit Wheel-basiertem
Imagebuild, getrenntem Kroko-Builder, korrigiertem Health-Vertrag, portablem
Compose ohne nginx-Abhaengigkeit und einem realen, isolierten Docker-Smoke
inklusive Persistenz- und Shutdown-Nachweis fuer Free und Pro. `build/vps/*`
und `Dockerfile.pro-upgrade` blieben unveraendert ausserhalb des
Arbeitspakets.

## Plan gegen verifizierten Stand

| Planpunkt | Ist-Stand | Nachweis |
| --- | --- | --- |
| Getrennter Kroko-Builder statt Multi-Stage-Kompilierung | Vollstaendig. `build/kroko-builder.Dockerfile` fuehrt den W4A-Linux-Buildpfad standalone fort; der Orchestrator ruft ihn per `docker run` auf. Das Production-`Dockerfile` hat keine `kroko-builder`-Stage, keine `install_kroko`-Referenz und im fertigen Image keine cmake/git/gcc-Binaries. | `Evidence/02_Kroko_Artifact/`, `Evidence/05_Image_Security/01_image_security.txt`, `tests/unit/test_production_docker_contract.py` |
| Produktionswheel statt Editable Install | Vollstaendig. `python -m build --wheel` erzeugt das Wheel; beide Images installieren exakt dieses Wheel (`pip show` zeigt Wheel-Install, `direct_url.json` ohne `editable`). | `Evidence/01_Package_Build/`, `Evidence/03_Docker_Free/01_free_image_build.txt` |
| Ubuntu 24.04 + venv, zweistufig | Vollstaendig. `builder`/`runtime`-Stages, beide `ubuntu:24.04`; `runtime` enthaelt nur Laufzeitbibliotheken. | `Dockerfile`, `Evidence/05_Image_Security/01_image_security.txt` |
| Free/Pro bleibt Build-Time-Authority | Vollstaendig. `voice-stt-server`/`voice-stt-server-pro` real gebaut, `verify_installed_runtime` bestaetigt `1free`/`1pro`; kein Lizenzschluessel als Buildinput (Unit-Test + reale Befehlszeilen). | `Evidence/03_Docker_Free/`, `Evidence/04_Docker_Pro/`, `tests/unit/test_build_production.py` |
| Health-Vertrag: Liveness ungleich Readiness | Vollstaendig. Docker-/Compose-`HEALTHCHECK` prueft ausschliesslich `GET /health` -> HTTP 200; realer Smoke zeigt `dockerHealthStatus: healthy` bei gleichzeitigem `sttModels.readiness: NOT_READY` und `restartCountAfterStart: 0`. `/health` selbst unveraendert. | `Evidence/07_Isolated_Smoke/`, `tests/unit/test_production_docker_contract.py` |
| Offline-Flags bleiben | Vollstaendig. Codepruefung bestaetigt, dass die drei Flags nur die alten Engine-Konstruktoren betreffen, nicht den W4B-Provisionierungspfad; unveraendert im Image gesetzt. | Plan Entscheidung F; `Dockerfile` |
| Browserclient ohne nginx/Source-Mount | Vollstaendig. Ein Service, `stt-server` liefert `/` aus der installierten Distribution; realer Smoke bestaetigt `/ws/v2` und Browserclient-Verfuegbarkeit ohne Source-Mount. | `docker-compose.yml`, `Evidence/07_Isolated_Smoke/`, `tests/unit/test_production_docker_contract.py` |
| Persistenter Runtime-Root und optionale Custom-Model-Mounts | Vollstaendig. `/var/lib/voicestt` einziger persistenter Root; Custom-Model-Pfade optional (leere Default-Mounts, `discover_model_path` gibt `None` statt zu werfen). | `docker-compose.yml`, `tools/compose.py`, `tests/unit/test_project_config.py` |
| `tools/compose.py`/`config.yaml` als Komfortschicht angepasst | Vollstaendig. Marcos private Kandidatenwerte unveraendert; nur Struktur generalisiert (optionale Modellpfade, kein Browserport). Der isolierte Smoke laeuft nachweislich unabhaengig davon direkt mit `docker compose -p ...`. | `tools/compose.py`-Diff, `Evidence/07_Isolated_Smoke/00_smoke_script.py` |
| Realer isolierter Docker/Compose-Smoke | Vollstaendig. Eigenes Compose-Projekt, temporaerer Testroot, freier lokaler Port 18020, kein Reverse Proxy, keine privaten Pfade/Netzwerke; Health/`/ws/v2`/Model-Management/NOT_READY/Persistenz/Recreate/SIGTERM fuer Free UND Pro real durchgefuehrt und disposabel wieder entfernt (keine Container/Netzwerke/Volumes danach). | `Evidence/07_Isolated_Smoke/`, `Evidence/08_Persistence_Shutdown/` |

## Verifikation

- Gezielte W4C-Tests (`tests/unit/test_build_production.py`,
  `tests/unit/test_production_docker_contract.py`, ergaenzte
  `tests/unit/test_project_config.py`-Faelle): bestanden.
- Finale Full Unit Regression: siehe `Evidence/09_Tests/`.
- `git diff --check`: bestanden.
- Reale Docker-Builds Free und Pro, Kroko-Artefakt-Resolve (REUSE und echter
  Build), Image-Security-Scan, isolierter Smoke inkl. Persistenz und
  Shutdown: alle in `Evidence/` mit konkreten Befehlen/Ergebnissen belegt.

## Abweichungen

Drei dokumentierte, nicht-materielle Abweichungen (Testanpassung an den
bewusst geaenderten Compose-Vertrag, Umbenennung eines gebrochenen
Image-Tag-Verweises in `config.yaml`, nicht-byteidentisches aber
inhaltsgleiches VoiceSTT-Wheel zwischen zwei getrennten Free-/Pro-Laeufen) -
siehe `04_DEVIATIONS.md` im Run-Verzeichnis
(`_workflow-tools/AP-SRV-070/Runs/W4C-R01/04_DEVIATIONS.md`). Keine davon
schwaecht eine Sicherheits- oder Korrektheitsaussage ab.
