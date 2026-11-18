# AP-SRV-070 / W5-R02-C2 - Correction Context

## Identity

- Parent correction: W5-R02-C1 - Root-approved and pushed as
  `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a` (archive:
  `_workflow-tools/AP-SRV-070/Runs/W5-R02-C1/`)
- Correction run: W5-R02-C2
- Model: Anthropic Sonnet 5, continuing the existing W5-R02-C1 session
- Binding start commit: `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`
- Binding start tree: `9c51c365701357e3b35dece563b156fc611b2c6e`
- Direct parent: `bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602`
- Product version: `2.0.0` (must remain unchanged)

## Workspaces

- Frozen W5-R02 qualification workspace (untouched):
  `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r02`
- C1 correction workspace (untouched by this run):
  `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r02-c1`
- New C2 correction workspace (this run works only here):
  `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r02-c2`,
  git worktree on new local branch `work/ap-srv-070-w5-r02-c2`, created
  directly from `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`.

## Prompt source/copy

- Source: `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\2026-09-07_AP-SRV-070_W5_R02_C2_SONNET5.md`
- Copy: `W5-R02-C2\00_PROMPT.md`
- SHA256 (source and copy, identical):
  `6cf1b0bdeac639b4bde244361cfc0f22bd37cd662204def835df4fd2d8650ca4`

## Scope

Extremely narrow: correct exactly one remaining race-sensitive assertion
in `test_store_outage_closes_live_stream_and_recovery_allows_new_stream`,
exposed by real GitHub Actions (run `34135266167`) after the C1
correction was pushed. Test-only unless a new, reproducible product
defect is found (none is expected or has been found). No other scope.

## Secret bundle (not consumed in this run)

Per Section 7 of the prompt, the operator secret bundle at
`P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env`
(confirmed in the prior W5-R02-C1 run to sit outside all Git worktrees,
as a sibling of `main`) is irrelevant to this test-only correction and
was not read, printed, copied, hashed, or loaded into the environment at
any point in this run.

## Explicit statement: single commit, no push

This run will produce exactly one local git commit on
`work/ap-srv-070-w5-r02-c2`, directly on top of the binding start
commit. No push, tag, or public release of any kind occurs. External
Root Review happens after this session; only after Root PASS may the
coordinator fast-forward the exact approved commit to Distributed, and
only after that push and a green GitHub Actions run on both platforms
for the exact new commit may it be frozen as the source basis for
W5-RC2.
