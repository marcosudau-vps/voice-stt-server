# AP-SRV-070 / W4C-R01 - Final Report

## Status

`READY FOR ROOT REVIEW`

## Git

- Start Commit: `fa3c9dc887b0d3930ac0e201b93a4803c308082f`
- Start Tree: `a532f3b493546181c6540a137fec383ee19da4c7`
- Final Commit: `e5f76bf1e4fd28e68624f30140fcf8ec6876db96`
- Final Tree: `f3eb03728dd1d0a4d57855a6154430b7142c8995`
- Zielbranch: `feat/einheitliche-triggerarchitektur-distributed`
- Lokaler Arbeitsbranch: `work/ap-srv-070-w4c-r01`
- Push Status: ausstehend, nur nach expliziter Nutzerbestaetigung (Remote vor
  Push erneut auf Start-SHA `fa3c9dc887b0d3930ac0e201b93a4803c308082f`
  verifiziert - siehe `Evidence/10_Git_Final/01_git_final_pre_push.txt`)
- Remote Final SHA: ausstehend (erst nach Push)
- Working Tree clean: ja

## Workspace / Run

- Modell: Anthropic Sonnet 5
- Workspace: `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w4c`
- Run-Akte: `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4C-R01`
- Prompt SHA256: `661f1515d270ccd9619845294cd6e9b697c60d6b3a1d20932e93beeef29d6811`

## Implementierung

- Neuer, zweistufiger Production-`Dockerfile` (Ubuntu 24.04, `builder`/`runtime`,
  venv-basiert): kein `pip install -e`, kein Kroko-Native-Build, non-root
  Benutzer `voicestt`, vollstaendige OCI-Labels, liveness-only `HEALTHCHECK`.
- Eigenstaendiges `build/kroko-builder.Dockerfile`: fuehrt den bestehenden
  W4A-Linux-Buildpfad standalone fort, nie referenziert vom Production-Image.
- Neuer oeffentlicher Build-Orchestrator `tools/build_production.py`:
  Preflight, Commit/Version, VoiceSTT-Wheel-Build, Kroko-Artefakt-Resolve
  (REUSE/BUILD ueber den Builder-Container), Image-Build Free/Pro/all,
  Validierung, JSON-Build-Manifest.
- Oeffentliches, portables `docker-compose.yml`: ein Service (kein
  nginx-Browserclient mehr - `stt-server` liefert die Browseroberflaeche aus
  der installierten Distribution), persistenter Runtime-Root
  `/var/lib/voicestt`, optionale Custom-Model-Mounts, korrigierter
  Healthcheck, portable Defaults ueberall (kein `${VAR:?...}` mehr).
- `tools/compose.py` generalisiert (optionale Modellpfade, kein
  Browserport), ohne Marcos private Werte in `config.yaml` zu aendern (eine
  einzelne, klar begruendete Ausnahme: der veraltete `deployment.image`-Tag
  wurde umbenannt, siehe `04_DEVIATIONS.md`).
- `.dockerignore`/`.gitignore` angepasst, damit die neuen Wheel-Buildinputs
  bzw. der neue Kroko-Builder-Dockerfile tatsaechlich in Build-Kontext bzw.
  Git-Commit gelangen.
- Gezielte neue Tests (`test_build_production.py`,
  `test_production_docker_contract.py`) plus Anpassung/Erweiterung
  bestehender Compose-Contract-Tests.
- Public-Doku aktualisiert: `build/BUILD.md`, `README.md`,
  `docs/windows-cpu-deployment.md`, `RELEASE_NOTES.md`.

## Build Evidence

### Free

- VoiceSTT Version: 2.0.0
- VoiceSTT Wheel: `voicestt-2.0.0-py3-none-any.whl`, SHA256
  `ebe22ea6ec2d4372597bbcbb638544979d24649e9a2959d56b90e5d7b82e1646`
- Kroko Variant: free
- Kroko Fingerprint: `ab8986fd7fb93756`
- REUSE / BUILD: erster Lauf BUILD (echter Neubau, danach im Store verifiziert), Produktions-Lauf REUSE
- Kroko Artifact SHA256: `df99ecb1def4a9a62cede4f708e76d0e42953f61e17541f0f7ec20641ed74952`
- Image Tag: `voice-stt-server:2.0.0`
- Image ID: `sha256:22c707ec3c5bc200951709988f35a8283f3ad1b74cc923f402af348759333a9f`
- OCI Version: 2.0.0, OCI Revision: `fa3c9dc887b0d3930ac0e201b93a4803c308082f`

### Pro

- VoiceSTT Version: 2.0.0
- VoiceSTT Wheel: `voicestt-2.0.0-py3-none-any.whl`, SHA256
  `a6df1d7a44b8881fe00ab34bfd021d8d1ea5ff1660ac4463bbc63bf5185f1ac0`
  (Quellinhalt byteidentisch zum Free-Wheel; siehe `04_DEVIATIONS.md` AW-03)
- Kroko Variant: pro
- Kroko Fingerprint: `36b440630c0a9475`
- REUSE / BUILD: BUILD (echter Neubau, `proLicenseEnabled: true`, kein
  vorhandenes Pro-Artefakt)
- Kroko Artifact SHA256: `37ae1630cf239f0bbe41abb1b47f90623eb0a8402803af98e27048c382f6ef43`
- Image Tag: `voice-stt-server-pro:2.0.0`
- Image ID: `sha256:f0b699818fef4bfc0b3f1e622b3e391f28a2a53294f024cbd577556986fa43fe`
- OCI Version: 2.0.0, OCI Revision: `fa3c9dc887b0d3930ac0e201b93a4803c308082f`

## Test Summary

| Test/Gate-Gruppe | Ergebnis | Evidence |
|---|---|---|
| Gezielte W4C-Unit-Tests | PASS | `tests/unit/test_build_production.py`, `tests/unit/test_production_docker_contract.py` |
| Volle Unit-Suite | PASS (1547 passed, 14 skipped, 974 subtests) | `Evidence/09_Tests/01_test_results.txt` |
| `git diff --check` | PASS | `Evidence/09_Tests/01_test_results.txt` |
| Docker Build Free/Pro | PASS | `Evidence/03_Docker_Free/`, `Evidence/04_Docker_Pro/` |
| Kroko Artifact Resolve (Free REUSE, Pro BUILD) | PASS | `Evidence/02_Kroko_Artifact/` |
| Image Security Scan | PASS | `Evidence/05_Image_Security/` |
| Compose Public Contract | PASS | `Evidence/06_Compose_Public/` |
| Isolierter Smoke (Free + Pro) | PASS | `Evidence/07_Isolated_Smoke/` |
| Persistenz/Shutdown (Free + Pro) | PASS | `Evidence/08_Persistence_Shutdown/` |

## Isolated Public Smoke

- Compose-Projektname: `voicestt-w4c-smoke`
- Temporaerer Testroot: `%TEMP%\voicestt-w4c-smoke` (Data + zwei leere optionale Custom-Model-Verzeichnisse)
- localhost Testport: 18020
- Health vor/nach Recreate: `healthy` / `healthy` (beide Varianten)
- Protocol v2: `hello.accepted`, `protocolVersion: 2` (beide Varianten)
- Model Management: HTTP 200 mit gesetztem `VOICESTT_ADMIN_API_KEY` (beide Varianten)
- NOT_READY: `sttModels.readiness: NOT_READY`, `minimumReady: false`,
  `restartCountAfterStart: 0` (kein Restart-Loop) (beide Varianten)
- Persistence: Marker uebersteht `down`+`up` mit neuer Container-ID (beide Varianten)
- SIGTERM: `docker compose stop -t 15` beendet den Container selbst nach
  ~1.1s mit Exit-Code 143, `OOMKilled: false` (beide Varianten)

Keine privaten Infrastrukturangaben in dieser Evidence oder im Smoke selbst;
kein Container/Netzwerk/Volume blieb nach dem Smoke zurueck.

## Gate Summary

- PASS: 33
- FAIL: 0
- BLOCKED: 0
- N/A: 0
- Verweis: `03_EVIDENCE_INDEX.md`

## Abweichungen

Drei dokumentierte, nicht-materielle Abweichungen - siehe `04_DEVIATIONS.md`.
Keine schwaecht eine Sicherheits- oder Korrektheitsaussage ab.
