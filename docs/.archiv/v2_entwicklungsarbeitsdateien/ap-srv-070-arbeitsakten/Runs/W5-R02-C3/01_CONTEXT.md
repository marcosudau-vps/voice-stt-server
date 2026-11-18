# AP-SRV-070 / W5-R02-C3 — Context

## Identity

- Project: AP-SRV-070, Phase W5 (Release Candidate Qualification)
- Correction run: W5-R02-C3 (parents: W5-R02 -> C1 -> C2)
- Model: Anthropic Opus 5, new session
- Repository: `marcosudau-vps/voice-stt-server`
- Distributed branch: `feat/einheitliche-triggerarchitektur-distributed`
- Binding start commit: `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`
- Binding start tree: `9c51c365701357e3b35dece563b156fc611b2c6e`
- Binding parent: `bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602`
- Product version: `2.0.0` (must remain unchanged)
- New C3 worktree: `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r02-c3`
  on local branch `work/ap-srv-070-w5-r02-c3`, created clean from the binding commit
- C2 workspace `...\workspaces\ap-srv-070-w5-r02-c2`: READ-ONLY reference. It was
  opened only with `git status --porcelain`, `git rev-parse`, `git diff` and
  `sha256sum` (all read-only). No write, no commit, no checkout there.

## Prompt provenance

- Source: `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\2026-09-07_AP-SRV-070_W5_R02_C3_OPUS5.md`
- SHA256 (source and `00_PROMPT.md`, byte-identical, verified with `cmp`):
  `43243b2d171115db1c17d1889c271944dc4b553acb509bab89430c02599718db`

## Inherited state

W5-R02-C1 is Root-approved and pushed as `7f1ad1f...`. Real GitHub Actions run
`34135266167` on that exact commit: Windows PASS, Ubuntu 24.04 one failure in
`test_store_outage_closes_live_stream_and_recovery_allows_new_stream`
(`'log.event' != 'log.error'`).

W5-R02-C2 produced a correct, never-committed, test-only ordering correction for
that failure (bounded receive loop, strict cursor monotonicity, canonical-store
verification, explicit `outage.not_committed` rejection, unexpected-frame
failure). C2 stopped at `NOT READY FOR ROOT REVIEW` because its mandatory stress
campaign uncovered a separate intermittent hang, measured at:

- C2 tree, isolated target test: 96/100 PASS, 4/100 hang
- C1 binding tree, unmodified, isolated target test: 94/100 PASS, 6/100 hang

The hang therefore predates C2. C2's own diff is not implicated. The exact C2
diff is archived verbatim in `Evidence/01_C2_Evidence_Review/01_c2_uncommitted_diff.txt`.

## Root Review corrections carried into C3 bookkeeping

Per prompt Section 4, C2's gate accounting is not reused. C3 applies literal
gate semantics: the plan must exist before the very first tracked edit (no
edit/revert workaround), "exactly one local commit" is met or not met (never
N/A), and "final workspace clean" means `git status --porcelain` is empty.

## Environments used

- Ubuntu: WSL2 `Ubuntu` 24.04.4 LTS, Linux 6.6.87.2-microsoft-standard-WSL2,
  Python 3.12.3, native ext4 copy of the C3 worktree at
  `/home/marco/w5r02c3-native-src` (avoids the DrvFs/SQLite artefact already
  documented in W5-R02-C1). Packages: fastapi 0.141.1, starlette 1.6.0,
  anyio 4.15.1, httpx 0.28.1, httpcore 1.0.9, h11 0.16.0, uvicorn 0.52.4,
  websockets 16.0, websocket-client 1.9.0, pytest 9.1.1.
- Windows: Windows 11 Pro 10.0.26200, Python 3.12.10, fastapi 0.135.4,
  starlette 1.3.1, anyio 4.14.2, httpx 0.28.1, uvicorn 0.44.0,
  websockets 16.0, pytest 9.1.1.

No dependency version was changed at any point. Full capture:
`Evidence/00_Preflight/02_environment_versions.txt`.

## Secret boundary

`P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env` lies
outside every worktree, is not needed by this run, and was not read, printed,
copied, hashed or loaded.
