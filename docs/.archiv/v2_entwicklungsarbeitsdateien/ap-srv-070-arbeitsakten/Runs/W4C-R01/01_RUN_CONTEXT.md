# AP-SRV-070 / W4C-R01 - Run Context

- **Run-ID:** W4C-R01
- **Modell:** Anthropic Sonnet 5 (claude-sonnet-5)
- **Startzeit (UTC):** 2026-09-05T12:00Z (ca.)
- **Session-Startordner:** `P:\GithubRepos\marcosudau-vps\voice-stt-server`
- **Workspace:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w4c`
- **Zielbranch (Distributed):** `feat/einheitliche-triggerarchitektur-distributed`
- **Lokaler Arbeitsbranch:** `work/ap-srv-070-w4c-r01`

## Start SHA/Tree

| | Erwartet | Tatsaechlich |
|---|---|---|
| Commit | `fa3c9dc887b0d3930ac0e201b93a4803c308082f` | `fa3c9dc887b0d3930ac0e201b93a4803c308082f` |
| Tree | `a532f3b493546181c6540a137fec383ee19da4c7` | `a532f3b493546181c6540a137fec383ee19da4c7` |

Remote-Fetch aus `P:\GithubRepos\marcosudau-vps\voice-stt-server\main` bestaetigt exakte
Uebereinstimmung (siehe `Evidence/00_Preflight/01_remote_fetch_verify.txt`).
Der Worktree wurde mit `git worktree add -b work/ap-srv-070-w4c-r01 <pfad>
fa3c9dc887b0d3930ac0e201b93a4803c308082f` direkt vom verbindlichen Start-Commit
erzeugt (siehe `Evidence/00_Preflight/02_worktree_identity.txt`).

## Tool-Versionen (Host)

- Python 3.12.10
- Git 2.53.0.windows.1
- Docker 29.7.2 (Docker Desktop, Server OSType=linux, Architecture=x86_64)
- Docker Compose v5.4.0
- Host-OS: Windows 11 Pro 10.0.26200

Siehe `Evidence/00_Preflight/03_tool_versions.txt`.

## Bindende W4C-Authorities

- `AGENTS.md`
- `build/BUILD.md`
- `docs/.archiv/README.md`
- `docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/2026-09-01_W4B_PLAN.md`
  und `..._W4B_UMSETZUNGSVERGLEICH.md`
- `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `tools/compose.py`
- `setup.py`, `MANIFEST.in`, `VERSION`, `VoiceSTT/_version.py`
- `VoiceSTT/install_kroko.py`, `VoiceSTT/kroko/*`
  (`fingerprint.py`, `artifacts.py`, `buildinputs.py`, `models.py`)
- `VoiceSTT_server/stt_model_management.py`
- `api_fastapi_server/server.py` (Health-/Server-Implementierung)
- `api_fastapi_server/static/index.html`, `setup.py` package_data (Browserclient)

Ausdruecklich **nicht** als W4C-Authority verwendet oder veraendert:
`build/vps/*`, `Dockerfile.pro-upgrade`, private Werte in `config.yaml`
(`deployment.model_paths.*.candidates`, `deployment.runtime_data.candidates`,
`deployment.public_url`).

## Entscheidungen A-G (Kurzform)

Vollstaendige Begruendung in
`docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/2026-09-05_W4C_PLAN.md`
(Entscheidungen A-I dort).

- **A. Getrennter Kroko-Builder:** `build/kroko-builder.Dockerfile` fuehrt den
  bestehenden W4A-autorisierten Linux-Buildpfad standalone fort; der
  Orchestrator ruft ihn als Container auf, nie das Production-Dockerfile.
- **B. Produktionswheel statt Editable Install:** `python -m build --wheel`
  erzeugt das VoiceSTT-Wheel, das Production-Image installiert exakt dieses
  Wheel.
- **C. Ubuntu 24.04 + venv:** zweistufiges `Dockerfile` (`builder`/`runtime`),
  non-root Benutzer `voicestt`.
- **D. Free/Pro bleibt Build-Time-Authority:** `voice-stt-server` /
  `voice-stt-server-pro`; Kroko-Runtime-Key nie Build-Input.
- **E. Health-Vertrag - Liveness ungleich Readiness:** Docker-/Compose-
  `HEALTHCHECK` prueft nur noch `GET /health` antwortet mit HTTP 200, nie
  `ready`/`ok`; `/health` selbst bleibt unveraendert.
- **F. Offline-Flags bleiben gesetzt:** Codepruefung zeigt, dass sie den W4B-
  Provisionierungspfad (`urllib.request.urlopen`) nicht blockieren.
- **G. Isolierter oeffentlicher Docker-Smoke ohne private Infrastruktur:**
  eigenes Compose-Projekt, temporaerer Daten-/Modellroot, freier lokaler
  Port, kein Reverse Proxy, kein bestehendes Deployment, keine privaten
  Hostpfade/Netzwerke - direkt mit `docker compose -f docker-compose.yml -p
  <isoliertes-projekt>`, bewusst nicht ueber `tools/compose.py`/`config.yaml`.

## Prompt SHA256

- Quelle: `_workflow-tools/AP-SRV-070/Prompts/2026-09-05_AP-SRV-070_W4C_RUN01_SONNET5.md`
- Kopie: `_workflow-tools/AP-SRV-070/Runs/W4C-R01/00_PROMPT.md`
- SHA256 (beide identisch): `661f1515d270ccd9619845294cd6e9b697c60d6b3a1d20932e93beeef29d6811`

Siehe `Evidence/00_Preflight/04_prompt_sha256.txt`.
