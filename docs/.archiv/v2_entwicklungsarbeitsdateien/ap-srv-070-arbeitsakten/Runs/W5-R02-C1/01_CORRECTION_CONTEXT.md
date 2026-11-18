# AP-SRV-070 / W5-R02-C1 - Correction Context

## Identity

- Parent qualification: W5-R02 / W5-RC1 - ended `NOT READY FOR ROOT REVIEW`
  (archive: `_workflow-tools/AP-SRV-070/Runs/W5-R02/`)
- Correction run: W5-R02-C1
- Model: Anthropic Sonnet 5, continuing the existing W5-R02 session
- Binding start commit: `bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602`
- Binding start tree: `f7b304b1959e48457a8eefd8919484f55214633b`
- Product version: `2.0.0` (must remain unchanged)

## Workspaces

- Existing frozen W5-R02 qualification workspace (untouched by this run):
  `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r02`
- New correction workspace (this run works only here):
  `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r02-c1`,
  git worktree on new local branch `work/ap-srv-070-w5-r02-c1`, created
  directly from `bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602`.

## Prompt source/copy

- Source: `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\2026-09-07_AP-SRV-070_W5_R02_C1_SONNET5_SECRET-AWARE.md`
  (this is the exact file the user pointed at in chat; the prompt's own
  internal Section 0 "Prompt source" field names a slightly different
  filename without the `_SECRET-AWARE` suffix - the actually-supplied
  file is treated as authoritative and copied byte-identically below)
- Copy: `W5-R02-C1\00_PROMPT.md`
- SHA256 (source and copy, identical):
  `91260af632782ef379e5dbfdfd79fc1ee8ae3d31c4b09ec20a6450ce5f2193be`

## Scope

This is a narrow correction: fix exactly the two confirmed source-level
blocker groups from W5-R02 (D1: two GitHub Actions CI failures; D3: an
RC-manifest CLI schema-mismatch bug), and nothing else. D2, D4, D5, D6,
D7 are explicitly out of scope (see `02_PLAN.md` "No-go scope" and the
parent run's `04_DEVIATIONS.md`).

## Secret bundle (not consumed in this run)

An operator secret bundle exists at
`P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env`
(existence/size verified via `ls -la` metadata only - 245 bytes - never
opened, read, printed, copied, or hashed). Two other candidate paths
named in the prompt/chat instructions do not exist on this host - see
`Evidence/00_Preflight/01_starting_state.txt`. Per the prompt's own
Section 0/2 (D5) and the user's explicit instruction, this file's
content is not needed and must not be used to correct D1/D3, and is not
touched anywhere in this run.

## Explicit statement: single-commit, no push

This run will produce exactly one local git commit on
`work/ap-srv-070-w5-r02-c1`, directly on top of the binding start commit.
No push, tag, or public release of any kind occurs. External Root Review
happens after this session; only after Root PASS may the exact approved
commit be fast-forwarded to Distributed by the coordinator.
