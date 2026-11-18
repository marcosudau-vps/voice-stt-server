# AP-SRV-070 / W5-R03 - RC Context

## Run identity

- Run: W5-R03
- Model: Gemini 3.8 Flash
- Session: NEW SESSION
- RC candidate: W5-RC2
- Product version: 2.0.0
- Target branch: `feat/einheitliche-triggerarchitektur-distributed`
- Workspace: `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r03`
- Suggested local branch: `qual/ap-srv-070-w5-r03`
- Run/evidence root: `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R03\`

## Exact RC identity

- Frozen RC commit: `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`
- Frozen RC tree: `2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb`
- Direct parent: `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`
- VERSION: `2.0.0`

## Distributed verification (start of run)

```text
git fetch origin
git rev-parse origin/feat/einheitliche-triggerarchitektur-distributed
  -> 934e3be7c78aa9358f9b42b9fa4dc282bed54d6c
git rev-parse HEAD (workspace)
  -> 934e3be7c78aa9358f9b42b9fa4dc282bed54d6c
git rev-parse HEAD^{tree}
  -> 2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb
git status --porcelain (workspace, at creation)
  -> (empty)
```

## Host / environment identity

- Windows host: Windows 11 Pro, build 10.0.26200, 30.1 GB RAM.
- Windows Python: Python 3.12.10 (`python` on PATH).
- Ubuntu environment: WSL2 distro `Ubuntu`, Ubuntu 24.04.4 LTS (`lsb_release -a`), Python 3.12.3 (`/usr/bin/python3`).
- Docker: Docker Desktop 29.7.2, build a7dcaa6, WSL2 backend.
- `gh` CLI: 2.87.3 (2026-02-23), authenticated as `marcosudau-vps`.
- Git: 2.53.0.windows.1.

## Prompt source / copy identity

- Prompt source: `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\2026-09-07_AP-SRV-070_W5_R03_GEMINI38FLASH.md`
- Copy: `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R03\00_PROMPT.md`
- SHA256 (source and copy, byte-identical):
  `690342a698739356c827db01c5a21fdef8e183e2f037b4c3d22c0e6effe7b582`

## GitHub Actions run identity

- Workflow run ID: `34155005726`
- Branch: `feat/einheitliche-triggerarchitektur-distributed`
- Commit: `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`
- Conclusion: `success`
- Job `build-and-test (ubuntu-24.04)`: `success`
- Job `build-and-test (windows-latest)`: `success`

## Authoritative Runtime Secret

- Location: `P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env`
- Status: Confirmed present on host outside git worktrees.
- Usage: Exclusively process-only for Kroko Pro live qualification; no secret values or content hashes shall be logged or captured.

## Frozen RC constraint statement

No tracked source code, docs, workflow files, or VERSION in `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r03` shall be modified during W5-R03.
No commit, tag, push, or public release will be performed.
All qualification harnesses, test scripts, temporary artifacts, and evidence logs are placed strictly outside the git tree under `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R03\`.
