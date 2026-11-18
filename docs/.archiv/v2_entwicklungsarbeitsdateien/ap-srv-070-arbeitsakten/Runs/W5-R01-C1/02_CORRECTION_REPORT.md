# AP-SRV-070 / W5-R01-C1 - Correction Report

Describes only the delta against W5-R01 (`_workflow-tools/AP-SRV-070/Runs/W5-R01/`).
Everything W5-R01 already delivered and that this run did not touch
(package build/twine check, installed-wheel smoke, CI workflow shape,
RC manifest schema, RELEASE_NOTES.md 2.0.0 section) remains valid there.

## Delta table

| Area | File(s) | W5-R01 state | C1 correction | Why | Gate |
|---|---|---|---|---|---|
| Publication engine | `release_tooling/engine.py` (new) | Did not exist; `pipeline.py` only had a hand-written static plan list | New `run_engine()` walks `STEP_DEFINITIONS` for both real publish and dry-run, differing only by `ExecutionMode` | Root Review: dry-run and real publish must share one operation graph, not two implementations | W5C1-G08 |
| Publication adapters | `release_tooling/adapters.py` (new) | Did not exist | `PyPIAdapter` (Twine), `GHCRAdapter`/`DockerHubAdapter` (`docker tag`/`push`), `GitTagAdapter` (`git tag`/`push`), `GitHubReleaseAdapter` (`gh release create`), `AggregateVerificationAdapter` (external/final verification) - each real, W6-capable, verify-before-write | Root Review blocker: real, W6-capable execution paths must exist and be testable now | W5C1-G01 - G07 |
| Pipeline facade | `release_tooling/pipeline.py` | Owned `PIPELINE_STEPS`/`DryRunReport`/`dry_run(state)` | Now a thin facade re-exporting `engine.STEP_DEFINITIONS` and wrapping `engine.run_engine(..., mode=DRY_RUN)`; `dry_run()` now takes `(state, manifest, adapters=None)` | Avoid a second, competing operation graph | W5C1-G08, G09 |
| CLI `dry-run` | `release_tooling/cli.py` | Built a placeholder state, called `pipeline.dry_run(state)` | Also builds/loads an RC manifest (`--manifest`, else an obvious placeholder identity) and calls the real engine with the real default adapter bundle; every adapter's `verify()` degrades to "unavailable" instead of crashing when a tool/registry/network is not reachable | Dry-run must exercise the real adapters' read-only checks, not a fictional plan | W5C1-G08, G09 |
| CLI `publish` | `release_tooling/cli.py` | Printed "not implemented", exit code 3 | Requires `--manifest` and `--yes`; runs a full preflight; only then builds the real adapter bundle and calls `run_engine(..., mode=REAL, persist=save_state)`; refuses at every step before touching anything if preconditions are not met | Root blocker: `publish` must have real execution logic, but this run must still perform zero public writes | W5C1-G01 - G07, G11 |
| Registry conflict detection | `release_tooling/remote_checks.py` | `check_registry_image()` treated *any* non-zero `docker manifest inspect` exit as `ABSENT` | Now only treats a real "no such manifest"/"manifest unknown" stderr as `ABSENT`; anything else (missing tool, daemon down, permission) raises `VerificationUnavailableError` | A missing/unreachable Docker must never be silently reported as "safe to publish" - this is load-bearing now that adapters call it for real conflict decisions | W5C1-G18, G19 |
| Git tag identity | `release_tooling/gitinfo.py` | Only local tag lookup (`local_tag_commit`) | Added read-only `remote_tag_commit()` (`git ls-remote`), plus real write helpers `create_tag()`/`push_tag()` (never force-push) | The tag barrier/conflict logic needs to see the *remote* tag, not just a local one, and the real adapter needs an actual write path | W5C1-G05, G20 |
| Tool-missing robustness | `release_tooling/gitinfo.py`, `release_tooling/adapters.py` | `subprocess.run` calls were not guarded against the binary itself being missing | `gitinfo._run()` and `adapters.default_runner()` convert `FileNotFoundError` into a normal "cannot proceed" result/`GitError` instead of an unhandled crash | A missing `git`/`twine`/`docker`/`gh` on a real W6 runner must degrade to "unavailable", never crash the whole engine walk | W5C1-G09 |
| Errors | `release_tooling/errors.py` | No distinction between "conflict" and "cannot check" | Added `VerificationUnavailableError` | The engine must react differently to "I know it conflicts" (hard stop, always) vs. "I could not check" (hard stop in REAL, keep planning in DRY_RUN) | W5C1-G08 |
| Config | `release_tooling/config.py` | No GitHub repo/remote identity | Added `GITHUB_REPO_SLUG` (the project's own, already-public GitHub repo - not a guess) and `GIT_REMOTE_NAME` | `GitHubReleaseAdapter`/`GitTagAdapter` need a concrete target | W5C1-G05, G06 |
| State | `release_tooling/state.py` | No copy primitive | Added `ReleaseState.clone()` | The engine must never mutate the caller's state object during a dry-run | W5C1-G09 |
| Documentation | `build/BUILD.md` | Described `release.py publish` as "intentionally not implemented in W5" | Describes the shared engine, the five real adapters, the credential-contract-only design, and that `publish` requires `--manifest --yes` plus a passing preflight | Must match the corrected execution model | W5C1-G28 |
| Archive | `docs/.archiv/.../2026-09-06_W5_R01_UMSETZUNGSVERGLEICH.md` | Recorded the stub `publish()` and the plan-before-code violation as an open (uncoordinated) finding | Updated to record the corrected engine capability and AW-01's coordinator acceptance | Section 13: "Record AW-01 honestly as an accepted historical process waiver" | W5C1-G29 |
| Tests | `tests/unit/test_release_adapters.py` (new), `tests/unit/test_release_engine.py` (new), `tests/unit/test_release_pipeline.py` (updated), `tests/unit/test_release_cli.py` (updated), `tests/unit/test_release_remote_checks.py` (updated) | 91 tests + 11 subtests | 157 tests + 11 subtests; every new/changed test uses injected fakes, never a real network/subprocess call | Section 12 requires exhaustive resume/conflict/barrier/secret coverage | W5C1-G12 - G27 |

## Publication adapters

Five real, W6-capable adapters now exist in `release_tooling/adapters.py`,
each exposing exactly `verify()` (always read-only) and `publish()` (the
one real write, gated by the engine). PyPI uses Twine; GHCR/Docker Hub use
`docker tag`+`docker push` against the immutable version tag; the Git tag
uses `git tag`+`git push` (never force); GitHub Releases use `gh release
create`. No adapter reads, logs, or stores a credential - each tool reads
its own already-established environment contract directly.

## Shared operation model

`release_tooling/engine.py:run_engine()` is the one function both
`release.py dry-run` and `release.py publish` call. Every step first calls
the adapter's `verify()` (real, read-only, safe in either mode). Only in
`ExecutionMode.REAL`, and only when `verify()` says the artifact is
`ABSENT`, does the engine call `publish()` - a structural guarantee, not a
convention, proven in `tests/unit/test_release_engine.py::DryRunNeverWritesTests`
and `tests/unit/test_release_pipeline.py::DryRunSideEffectFreedomTests`
with adapters that raise `AssertionError` if `publish()` is ever invoked.

## Resume / reconciliation

Because every step re-verifies before deciding to publish, resuming after
a partial failure and reconciling a stale local state (an external
operation succeeded but local state was never persisted, e.g. after a
crash) are the *same* code path, not two special cases:
`tests/unit/test_release_engine.py::ResumeAfterPartialSuccessTests` covers
all six failure points named in the correction prompt (after PyPI, after
GHCR, after Docker Hub, after external verification, after tag, after
GitHub Release); `StaleLocalStateReconciliationTests` covers the crash
window explicitly (local state stuck at `PREPARED`, remote already has the
artifact - the engine resumes without re-publishing; a genuine remote
conflict still stops the run even with stale local state).

## Conflict safety

Every adapter's `verify()` raises `ConflictError` on a mismatched remote
identity (PyPI file hash, registry digest, tag commit, release tag) and
`VerificationUnavailableError` when the check itself could not complete
(no network, missing tool, unconfigured registry root). The engine treats
a `ConflictError` as an immediate hard stop in *both* modes (a dry-run
reports the exact wall a real run would hit); it treats
`VerificationUnavailableError` as a hard stop only in `REAL` mode (a
dry-run keeps walking the rest of the independently-checkable graph). This
correction also tightened `remote_checks.check_registry_image()` itself:
previously *any* non-zero `docker manifest inspect` exit was read as
"absent" (safe to publish), which would have misreported a missing/broken
Docker installation the same as a genuinely free tag; it now requires a
specific "no such manifest"/"manifest unknown" message to conclude
`ABSENT`, and raises `VerificationUnavailableError` for anything else.

## Tag / release barriers

`state.assert_tag_allowed()`/`assert_github_release_allowed()` are called
a second time, defensively, directly inside `GitTagAdapter.publish()`/
`GitHubReleaseAdapter.publish()` - so the barrier holds even if an adapter
were ever invoked outside the engine's own step ordering, not only because
the engine happens to walk the steps in order.

## Secret handling

No adapter ever reads a credential into this process: Twine, `docker`,
git, and `gh` each read their own already-established environment contract
directly when the OS spawns them as a subprocess. Every test that could
plausibly leak a secret uses an obvious synthetic sentinel value (e.g.
`ghp_SENTINELSECRETVALUE...`) and asserts it never appears in a captured
command line, stdout, stderr, or a raised exception's message; subprocess
stderr that reaches an exception message is passed through
`redaction.redact_text()` first.

## Tests

Targeted: 157 tests + 11 `subTest` cases across
`tests/unit/test_release_*.py`, all PASS - see `Evidence/07_Tests/`. Full
suite and `git diff --check`: see the same evidence folder.

## Documentation

`build/BUILD.md`'s release-orchestrator section was rewritten to describe
the shared engine, the five real adapters, the credential-contract-only
design, and the exact `publish --manifest --yes` precondition chain. The
W5-R01 archive Soll-/Ist-Vergleich was updated to reflect the corrected
engine capability and to record AW-01 as coordinator-accepted, per prompt
section 13.

## Deliberate non-changes

No change to `VoiceSTT._version`, `tools/build_production.py`, Kroko
artifact authority, Docker build architecture, package build architecture,
STT Model Management, Protocol v2, Trigger/Activation, Settings, Wake Word,
or client behavior. `RELEASE_NOTES.md`'s 2.0.0 section is unchanged (the
new engine is release-process infrastructure, not a product-facing
change warranting its own note beyond what W5-R01 already recorded). No
public write of any kind was performed.
