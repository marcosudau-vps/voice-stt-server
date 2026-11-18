# AP-SRV-070 / W5-R02-C3-R1 — Context

## Identity

- Project: AP-SRV-070, Phase W5 (Release Candidate Qualification)
- Run: W5-R02-C3-R1, Root Review correction of W5-R02-C3
- Model: Anthropic Opus 5, continuing the existing W5-R02-C3 session as the
  prompt requires
- Repository: `marcosudau-vps/voice-stt-server`
- Remote Distributed branch: `feat/einheitliche-triggerarchitektur-distributed`
- Binding remote start commit: `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`
- Binding remote start tree: `9c51c365701357e3b35dece563b156fc611b2c6e`
- Rejected/unpushed C3 reference commit: `d60936c509d7b95e406c671fd3f91cc5f2af5add`
  (tree `71da4a1ab4d75844825c90a28c91644d18f01d3e`)
- Correction workspace: `...\workspaces\ap-srv-070-w5-r02-c3-r1`, branch
  `work/ap-srv-070-w5-r02-c3-r1`, created **directly from the remote binding
  commit** — `git merge-base --is-ancestor d60936c… HEAD` returns non-zero, so
  the branch is provably not based on the rejected C3 commit
- Product version: `2.0.0`, must remain unchanged

## Prompt provenance

- Source: `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\2026-09-07_AP-SRV-070_W5_R02_C3_R1_OPUS5.md`
- SHA256 (source and `00_PROMPT.md`, byte-identical, verified with `cmp`):
  `9497e99c30ed99547590f125b6e033141435c2364ddacf13bdaecb6b41aa731a`

## The blocker this run had to settle

External Root Review accepted C3's factual findings about the intermittent
`/ws/logs` hang but refused the additional claim C3 made:

> a successful canonical read is entitled to re-mark the whole canonical store
> `ready` even when canonical writes are still failing.

Two things had to be decided from authority and reproducible behaviour rather
than from the current implementation:

1. whether that recovery rule is correct at all;
2. whether the C3 test may prove canonical identity with `events.query()`,
   which itself mutates the state under test.

## Read-only reference material

`...\workspaces\ap-srv-070-w5-r02-c3` and
`_workflow-tools\AP-SRV-070\Runs\W5-R02-C3\` were used read-only. The workspace
was inspected with `git rev-parse`, `git status --porcelain` and `git show`
only, and is verified unchanged at `d60936c…` with an empty status both before
and after this run.

## Environments used

- Ubuntu: WSL2 `Ubuntu` 24.04.4 LTS, Linux 6.6.87.2-microsoft-standard-WSL2,
  Python 3.12.3, native ext4 copy of the R1 worktree at
  `/home/marco/w5r02c3r1-native-src`. Packages: fastapi 0.141.1,
  starlette 1.6.0, anyio 4.15.1, httpx 0.28.1, httpcore 1.0.9, h11 0.16.0,
  uvicorn 0.52.4, websockets 16.0, pytest 9.1.1.
- Windows: Windows 11 Pro 10.0.26200, Python 3.12.10, fastapi 0.135.4,
  starlette 1.3.1, anyio 4.14.2, httpx 0.28.1, uvicorn 0.44.0,
  websockets 16.0, pytest 9.1.1.

No dependency version was changed at any point. The real-network probes use
`uvicorn`, `websockets` and `httpx`, all already project dependencies; nothing
was installed for them.

## Secret boundary

`P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env` lies
outside every worktree, was not needed by this run, and was not read, printed,
copied, hashed, loaded or archived.
