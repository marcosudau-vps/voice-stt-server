# AP-SRV-070 / W5-R01 - Run Context

- **Run-ID:** W5-R01
- **Modell:** Anthropic Sonnet 5 (claude-sonnet-5)
- **Session:** NEW SESSION
- **Startzeit (UTC):** 2026-09-06T06:15Z (ca.)
- **Session-Startordner:** `P:\GithubRepos\marcosudau-vps\voice-stt-server`
- **Workspace:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r01`
- **Zielbranch (Distributed):** `feat/einheitliche-triggerarchitektur-distributed`
- **Lokaler Arbeitsbranch:** `work/ap-srv-070-w5-r01`
- **Run-Akte:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R01`

## Start SHA/Tree

| | Erwartet (Prompt) | Tatsaechlich (Remote, verifiziert) |
|---|---|---|
| Commit | `e5f76bf1e4fd28e68624f30140fcf8ec6876db96` | `e5f76bf1e4fd28e68624f30140fcf8ec6876db96` |
| Tree | `f3eb03728dd1d0a4d57855a6154430b7142c8995` | `f3eb03728dd1d0a4d57855a6154430b7142c8995` |

Exakte Uebereinstimmung bestaetigt via `git fetch origin` +
`git rev-parse origin/feat/einheitliche-triggerarchitektur-distributed` (und
`^{tree}`) aus `P:\GithubRepos\marcosudau-vps\voice-stt-server\main` - siehe
`Evidence/00_Preflight/01_remote_fetch_verify.txt`.

Der Worktree wurde direkt vom verbindlichen Start-Commit erzeugt:

```text
git worktree add -b work/ap-srv-070-w5-r01 <pfad> e5f76bf1e4fd28e68624f30140fcf8ec6876db96
```

siehe `Evidence/00_Preflight/02_worktree_identity.txt`. Der Zielpfad existierte
vor diesem Run nicht (frisch angelegt, kein Reuse-Fall).

## Tool-Versionen (Host)

- Python 3.12.10
- Git 2.53.0.windows.1
- Docker 29.7.2 (Docker Desktop, Server OSType=linux, Architecture=x86_64)
- Docker Compose v5.4.0
- Host-OS: Windows 11 Pro 10.0.26200 (MINGW64/Git-Bash-Shell)

Siehe `Evidence/00_Preflight/03_tool_versions.txt`.

## Bindende W5-R01-Autoritaeten (gelesen vor Umsetzung)

- `AGENTS.md`
- `build/BUILD.md`
- `docs/.archiv/README.md`
- `VERSION` (= `2.0.0`), `VoiceSTT/_version.py`
- `setup.py` (Entry-Points, `extras_require`, `package_data`), `MANIFEST.in`
- `requirements.txt`, `requirements-dev.txt`
- `README.md`, `RELEASE_NOTES.md`, `docs/testing.md`
- `tools/build_production.py` (Free/Pro-Image-Namensauthority,
  Build-Manifest-Struktur - Vorbild fuer das RC-Manifest)
- `Dockerfile`, `docker-compose.yml` (W4C-Vertraege, OCI-Labels)
- `VoiceSTT/kroko/{fingerprint,artifacts,buildinputs}.py` (Fingerprint-/
  Artefakt-Feldnamen fuer das RC-Manifest)
- `tests/unit/test_version_authority.py`,
  `tests/unit/test_build_production.py` (Testkonventionen: `unittest.TestCase`,
  `sys.path`-Einfuegung fuer `tools/`, Stub-`CommandRunner`-Muster)
- `docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/2026-09-05_W4C_PLAN.md`
  und `..._W4C_UMSETZUNGSVERGLEICH.md` (Vorlage fuer Archiv-Stil und
  Entscheidungsdokumentation)

Ausdruecklich **nicht** als W5-R01-Authority verwendet oder veraendert:
`build/vps/*`, private Werte in `config.yaml`, `Dockerfile.pro-upgrade`.

## Bindende W5-Entscheidungen (siehe Plan fuer volle Begruendung)

Volle Begruendung in
`docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/2026-09-06_W5_R01_PLAN.md`
(Entscheidungen A-H dort). Kurzform:

- **A.** `release_tooling/`-Paket, `release.py` bleibt duenner Wrapper.
- **B.** Keine zweite Versions-/Image-Namensauthority (Reuse von
  `VoiceSTT._version` und `tools.build_production.IMAGE_NAMES`).
- **C.** GHCR-/Docker-Hub-Repository-Wurzeln bleiben unkonfiguriert (Env-Var,
  Preflight meldet FAIL statt geraten).
- **D.** `release.py publish` bewusst nicht implementiert (Exit-Code 3,
  nachweislich kein Subprocess-/Netzwerkaufruf).
- **E.** Release-State unter `/release_state/` (git-ignoriert), nicht unter
  `dist/`.
- **F.** `prepare-next-version` ohne `--apply` rein lesend.
- **G.** CI durchgehend `shell: bash` (Windows-Runner haben Git Bash).
- **H.** CI trennt Wheel-Install-Smoke (isolierte venv, Nicht-Checkout-
  Verzeichnis) von der regulaeren `pytest`-Suite gegen den Checkout.

## Prompt SHA256

- Quelle: `_workflow-tools/AP-SRV-070/Prompts/2026-09-06_AP-SRV-070_W5_R01_SONNET5.md`
- Kopie: `_workflow-tools/AP-SRV-070/Runs/W5-R01/00_PROMPT.md`
- SHA256 (beide identisch):
  `7f539c6f67871898044841cd145a256c0c9fe70d12021e661edcc0b17de0fb93`

Siehe `Evidence/00_Preflight/04_prompt_sha256.txt`.

## Bekannte, dokumentierte Umgebungsbesonderheit (kein Regressions-Signal)

Ein voller `python -m pytest -q tests/unit`-Lauf in dieser Sandbox kann mit
`PermissionError: [WinError 5] Zugriff verweigert:
'...\AppData\Local\Temp\pytest-of-marco'` fehlschlagen, wenn dieses von
pytest verwaltete Standard-Temp-Basisverzeichnis in der Sandbox gesperrt ist
(nicht dasselbe wie die in `docs/testing.md` "Windows Notes" dokumentierte
Multiprocessing-Pipe-`PermissionError`). Ein gezielter Retry derselben Tests
mit ueberschriebenem `TEMP`/`TMP` (Projektunterordner statt OS-Standard)
bestaetigt, dass es sich um eine Umgebungs-, keine Code-Eigenschaft handelt;
siehe `Evidence/07_Tests/`.
