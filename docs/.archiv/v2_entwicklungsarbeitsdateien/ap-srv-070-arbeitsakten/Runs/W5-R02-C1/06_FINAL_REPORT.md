READY FOR ROOT REVIEW

# AP-SRV-070 / W5-R02-C1 - Final Report

## Identity

- Parent qualification: W5-R02 / W5-RC1 - ended `NOT READY FOR ROOT
  REVIEW` (archive: `_workflow-tools/AP-SRV-070/Runs/W5-R02/`); remains
  frozen and failed, unmodified by this run.
- W5-RC1 source commit: `bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602`
- W5-RC1 source tree: `f7b304b1959e48457a8eefd8919484f55214633b`
- Correction commit: `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`
- Correction tree: `9c51c365701357e3b35dece563b156fc611b2c6e`
- VERSION: `2.0.0` (unchanged)

## Exact files changed

```
release_tooling/cli.py                        |  36 ++++-
tests/unit/test_fastapi_server_multi_user.py |  36 ++++-
tests/unit/test_kroko_onnx_engine.py         |  66 ++++++++-
tests/unit/test_release_cli.py               | 205 +++++++++++++++++++++++++++
4 files changed, 328 insertions(+), 15 deletions(-)
```

## Windows fix summary (D1-Windows)

Four tests in `tests/unit/test_kroko_onnx_engine.py` compared a resolved
Kroko model path against an unresolved one via raw string equality,
which legitimately differs on GitHub-hosted Windows runners (8.3 short
vs. long path spelling of the identical file).
`VoiceSTT/transcription_engines/model_resolver.py`'s existing
`.resolve()` behavior is **unchanged** - the tests now assert semantic
file identity via a new `assertSameFile()` helper
(`os.path.samefile()`), which still fails for a genuinely wrong file or
directory. One new test proves alternate legal spellings of the same
file are accepted as identity-equivalent.

## Ubuntu fix summary (D1-Ubuntu)

`test_store_outage_closes_live_stream_and_recovery_allows_new_stream`
in `tests/unit/test_fastapi_server_multi_user.py` assumed the replay
window after subscribing is always empty; a legitimate event can commit
between the client's cursor snapshot and the server's own replay query.
Production replay/event-store behavior is **unchanged** - the test now
consumes and validates any such `log.event` frames (strict cursor
monotonicity, no unexpected message types, no arbitrary swallowing)
before requiring `log.replay_completed`, mirroring the already-correct
pattern used elsewhere in the same file. Verified deterministic across
20/20 consecutive runs.

## Manifest fix summary (D3)

`tools/build_production.py` (**unchanged**, remains the compatibility
anchor) writes the Kroko artifact hash as `wheelSha256`;
`release_tooling/cli.py`'s `manifest build` subcommand read `sha256` at
the same nested path and crashed with `KeyError` on real production
output. `release_tooling/cli.py` now reads the canonical `wheelSha256`
field via a new `_extract_kroko_artifact_sha256()` helper, tolerates a
legacy `sha256` fallback for compatibility, and fails closed
(`ManifestError`) if both are present and disagree. New test coverage
(`ManifestBuildCommandTests` in `tests/unit/test_release_cli.py`)
exercises this against a manifest assembled from the **real**
`tools.build_production.resolve_kroko_wheel()` output (via the existing
no-Docker fake-runner test infrastructure `test_build_production.py`
already provides), not another hand-typed synthetic fixture - closing
the exact gap that let the original bug go undetected.

## Targeted tests

- `tests/unit/test_kroko_onnx_engine.py` (Windows): 29 passed, 1
  skipped, 4 subtests - all four previously-failing tests now pass.
- `tests/unit/test_fastapi_server_multi_user.py`::the corrected test,
  run 20x consecutively (Ubuntu): 20/20 pass. Full file (Ubuntu, native
  filesystem): 113 passed, 1 skipped, 10 subtests, 0 failed.
- `tests/unit/test_release_cli.py` (Windows): 16 passed (13 pre-existing
  + 3 new).
- Full `tests/unit/test_release_*.py` set + `test_build_production.py`
  (Windows): 174 passed, 11 subtests, 0 failed.

## Full Windows tests

`python -m pytest -q tests/unit` (isolated venv, no concurrent Docker/
native builds): **1709 passed, 13 skipped, 3 warnings, 985 subtests
passed, 0 failed** in 665.12s. Reconciles exactly against the prior
1704/14/985/0 baseline plus the 4 new tests this correction adds (see
`Evidence/05_Windows_Regression/`).

## Full Ubuntu tests

`python -m pytest -q tests/unit` (WSL2 Ubuntu 24.04.4, Python 3.12.3,
native filesystem): **1708 passed, 14 skipped, 4 warnings, 985 subtests
passed, 0 failed** in 327.24s. Reconciles exactly against the prior
baseline plus the 4 new tests (skip count unchanged at 14, since the
Windows-only path issue never affected Ubuntu). Two environment issues
were hit and resolved along the way (a Windows-mounted-CWD SQLite/WAL
interaction, and a missing `libssl-dev` system package) - both fully
documented in `05_DEVIATIONS.md` and `Evidence/06_Ubuntu_Regression/`;
neither touched or required touching any source file.

## Package/release-tool smoke

`python -m build` + `twine check`: both artifacts PASSED.
`release.py --help`: lists all subcommands. `release.py manifest build`
against real production-shaped Free/Pro manifests (real CLI invocation,
not just the unit test): succeeds, writes a valid manifest.
`release.py manifest validate`: `VALID`. `release.py dry-run`:
`"sideEffectFree": true`, exact fixed W6 step order, zero steps
executed. No `release_state/` was created; `release.py publish` was
never invoked; no public write of any kind occurred.

## Gate tally

28/28 PASS, 0 FAIL, 0 BLOCKED. Full detail: `04_GATE_INDEX.md`.

## Workspace clean / one commit ahead / remote unchanged

`git status --porcelain`: empty. Exactly one local commit
(`7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`) ahead of
`origin/feat/einheitliche-triggerarchitektur-distributed`, which remains
at `bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602` - unchanged throughout this
entire run. Full detail: `Evidence/08_Final_Git_State/`.

## No public write

No push, no tag, no PyPI/GHCR/Docker Hub upload, no GitHub Release, and
no `release.py publish` invocation occurred at any point in this run.

## D4/D5/D7 remain open qualification items - not falsely closed by C1

This correction fixed exactly the two confirmed source-level blocker
groups (D1 across both platforms, D3) and nothing else. It did **not**
address, does **not** close, and must **not** be read as having closed:

- **D4** (Faster-Whisper/Kroko Free live E2E inconclusive result) -
  unchanged; no ASR engine, session, or E2E-harness source was touched.
- **D5** (Kroko Pro live E2E, now credential-available via the external
  secret bundle) - **not attempted**; the secret bundle's content was
  never read, printed, or used anywhere in this run. Remains a W5-RC2
  qualification item.
- **D7** (read-only custom-model-source gate) - **not tested**; remains
  a W5-RC2 qualification item, not marked as passed.

All three are explicitly deferred to the next frozen qualification run
(W5-RC2), consistent with the prompt's Section 2/11 scope boundary.

## Disposition

This correction is complete, self-contained, and evidenced: exactly the
D1 (both platforms) and D3 blockers from the frozen W5-RC1 qualification
are fixed, with zero product/protocol/resolver behavior changes, exactly
one local commit, a fully clean and fully explained full regression on
both required platforms, and no public write of any kind. **READY FOR
ROOT REVIEW.** Per the prompt's governance, this commit must not be
pushed until external Root Review approves it; only after that approval
and a subsequent push, followed by a green GitHub Actions run on the
exact new commit, may it be frozen as the source basis for W5-RC2 (still
product version `2.0.0`). W5-RC1 itself remains, and will remain, a
frozen, failed candidate regardless of this correction's outcome.
