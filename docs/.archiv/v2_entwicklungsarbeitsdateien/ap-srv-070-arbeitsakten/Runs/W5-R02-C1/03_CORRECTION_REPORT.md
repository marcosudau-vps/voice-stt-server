# AP-SRV-070 / W5-R02-C1 - Correction Report (Soll/Ist)

Written 2026-09-07, after implementation, against `02_PLAN.md` (written
before any source edit).

## D1-Windows: planned vs. actual

Planned: add `assertSameFile()` (via `os.path.samefile()`) to
`KrokoOnnxEngineTests`; use it in the four previously-failing tests; add
one new test proving alternate spellings are accepted; do not touch
`model_resolver.py`.

Actual: exactly as planned. One implementation detail not fully
anticipated in the plan: the new "alternate spellings" test's first
attempt used `os.path.relpath()`, which raised `ValueError: path is on
mount 'C:', start on mount 'P:'` because the temp directory and the
checkout can legitimately be on different Windows drives - fixed by
computing the relative spelling from within the temp directory itself
(`os.chdir` + bare filename) instead, which still produces a genuinely
different, legitimate string spelling of the same file without the
cross-drive problem. This is a test-authoring correction, not a plan
deviation in substance.

## D1-Ubuntu: planned vs. actual

Planned: replace the fixed 3-assertion sequence with a loop mirroring
the file's own existing pattern, adding cursor-monotonicity and
unexpected-message-type strictness; do not touch production replay code.

Actual: exactly as planned, implemented as designed. 20/20 repeated runs
passed; the full surrounding file passed once run from native WSL2
storage (see the two environment issues below).

## D3: planned vs. actual

Planned: add `_extract_kroko_artifact_sha256()` reading `wheelSha256`
with a `sha256` fallback, fail-closed on conflict via `ManifestError`;
add `ManifestBuildCommandTests` using the real
`tools.build_production.resolve_kroko_wheel()` with a fake, no-Docker
runner (reusing `test_build_production.py`'s existing
`RecordingRunner`/`contains()` infrastructure) instead of a hand-typed
fixture.

Actual: exactly as planned. Three tests added (success path, legacy
fallback, fail-closed conflict), all passing; end-to-end real CLI
invocation with production-shaped manifests (not just the unit test)
additionally proves the fix via `release.py manifest build` +
`manifest validate` (see `Evidence/07_Package_Release_Tooling/`).

## Environment issues encountered and resolved during validation (not plan deviations - no source impact)

1. Running Ubuntu pytest from this session's usual Windows-mounted
   `/mnt/p/...` working directory produced 8 unrelated test failures
   (`sqlite3.OperationalError: disk I/O error`) in tests that default to
   a relative log-store path under the process CWD - a DrvFs/SQLite-WAL
   interaction, not a defect. Resolved by copying the workspace into
   native WSL2 storage for test execution (source untouched;
   `~/w5r02c1-native-src` is a disposable test copy, not a second source
   of truth).
2. That native copy's WSL2 Ubuntu distro was missing the `libssl-dev`
   system package (among a few build-toolchain siblings), causing 27
   unrelated failures in `tests/unit/test_kroko_artifact_store.py` /
   `test_kroko_fingerprint.py` (neither file touched by this
   correction). The user installed the missing packages
   (`sudo apt-get install -y libssl-dev build-essential cmake
   pybind11-dev zlib1g-dev`); the re-run suite was then fully clean.

Neither issue is a plan deviation, a scope change, or a product finding
- both are documented in detail in `05_DEVIATIONS.md` and in the
relevant `Evidence/` files.

## Exact files changed (matches the plan's "Exact intended files" exactly)

```
release_tooling/cli.py                        |  36 ++++-
tests/unit/test_fastapi_server_multi_user.py |  36 ++++-
tests/unit/test_kroko_onnx_engine.py         |  66 ++++++++-
tests/unit/test_release_cli.py               | 205 +++++++++++++++++++++++++++
4 files changed, 328 insertions(+), 15 deletions(-)
```

No other file was touched. `VoiceSTT/transcription_engines/model_resolver.py`
and `tools/build_production.py` were read for context and confirmed
unedited, as planned.

## W5-RC1 remains failed/frozen

This correction does not modify, supersede, or retroactively "pass" the
frozen W5-R02 qualification archive
(`_workflow-tools/AP-SRV-070/Runs/W5-R02/`) or its `NOT READY FOR ROOT
REVIEW` verdict for W5-RC1 (commit `bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602`
as originally qualified). No file under that archive was edited by this
run. W5-RC1 stays exactly as it was found: a frozen, failed candidate.

## Path to W5-RC2 (not performed in this run)

The single correction commit produced here (`7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`,
on local branch `work/ap-srv-070-w5-r02-c1`, one commit ahead of
Distributed's `bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602`) has **not**
been pushed. Per the prompt's governance (Section 3.2, Section 21): only
after external Root Review approves this correction may the coordinator
fast-forward this exact commit to Distributed; only after that push
succeeds and GitHub Actions runs green on the exact new commit may it be
frozen as the source basis for a new internal candidate, W5-RC2 (product
version still `2.0.0`). None of that happened in this session.
