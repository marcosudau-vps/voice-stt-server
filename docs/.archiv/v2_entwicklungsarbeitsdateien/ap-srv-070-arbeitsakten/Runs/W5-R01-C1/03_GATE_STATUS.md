# AP-SRV-070 / W5-R01-C1 - Gate Status

## Publication implementation

| Gate | Status | Kurzbeweis | Evidence | Command/Test | Result |
|---|---|---|---|---|---|
| W5C1-G01 | PASS | `PyPIAdapter` implemented: `verify()` via the existing read-only `check_pypi_release()`, `publish()` via `twine upload --non-interactive --skip-existing` | `release_tooling/adapters.py`, `Evidence/01_Publish_Engine/01_adapter_and_engine_tests.txt` | `tests/unit/test_release_adapters.py::PyPIAdapterTests` | 7 tests PASS |
| W5C1-G02 | PASS | `GHCRAdapter` implemented on shared `_RegistryAdapter`: `verify()` via `check_registry_image()`, `publish()` via `docker tag`+`docker push`, per-variant idempotent | `release_tooling/adapters.py` | `tests/unit/test_release_adapters.py::RegistryAdapterTests` | PASS |
| W5C1-G03 | PASS | `DockerHubAdapter` implemented on the same shared `_RegistryAdapter`, own repo-root env var | `release_tooling/adapters.py` | `tests/unit/test_release_adapters.py::RegistryAdapterTests::test_dockerhub_adapter_uses_its_own_repo_env` | PASS |
| W5C1-G04 | PASS | External verification implemented as `AggregateVerificationAdapter(sub_adapters=[pypi, ghcr, dockerhub])` - requires all three `MATCH` | `release_tooling/adapters.py`, `engine.STEP_DEFINITIONS["external_verification"]` | `tests/unit/test_release_adapters.py::AggregateVerificationAdapterTests`, `tests/unit/test_release_engine.py::VerifyOnlyBarrierTests` | PASS |
| W5C1-G05 | PASS | `GitTagAdapter` implemented: `verify()` via local+remote (`git ls-remote`) tag lookup, `publish()` via `git tag`+`git push` (never force); late-tag barrier enforced both by fixed step order and defensively inside `publish()` via `state.assert_tag_allowed()` | `release_tooling/adapters.py`, `release_tooling/gitinfo.py` | `tests/unit/test_release_adapters.py::GitTagAdapterTests`, `Evidence/05_Ordering_Barriers/01_...txt` | PASS |
| W5C1-G06 | PASS | `GitHubReleaseAdapter` implemented via `gh release view`/`gh release create`; TAGGED barrier enforced both by fixed step order and defensively via `state.assert_github_release_allowed()` | `release_tooling/adapters.py` | `tests/unit/test_release_adapters.py::GitHubReleaseAdapterTests` | PASS |
| W5C1-G07 | PASS | Final verification implemented as `AggregateVerificationAdapter(sub_adapters=[pypi, ghcr, dockerhub, git_tag, github_release])` | `release_tooling/adapters.py:build_default_adapters()` | `tests/unit/test_release_engine.py::ResumeAfterPartialSuccessTests::test_resume_after_github_release_verifies_existing_release_and_finishes` | PASS |

## Shared execution model

| Gate | Status | Kurzbeweis | Evidence | Command/Test | Result |
|---|---|---|---|---|---|
| W5C1-G08 | PASS | `release_tooling.engine.run_engine()` is the one function both `dry-run` and `publish` call; only `ExecutionMode` differs; module-level assertion pins `STEP_DEFINITIONS` to `STATE_ORDER` | `release_tooling/engine.py`, `release_tooling/pipeline.py`, `release_tooling/cli.py` | `tests/unit/test_release_engine.py::SharedGraphTests` | PASS |
| W5C1-G09 | PASS | `publish()` on any adapter is structurally unreachable when `mode == DRY_RUN` - proven with adapters that raise `AssertionError` if `publish()` is ever called, at both the engine and pipeline-facade layer; real CLI `dry-run` smoke with poisoned network/subprocess also completes with `anyExecuted: False` | `Evidence/04_Dry_Run_Safety/01_...txt` | `tests/unit/test_release_engine.py::DryRunNeverWritesTests`, `tests/unit/test_release_pipeline.py::DryRunSideEffectFreedomTests` | PASS |
| W5C1-G10 | PASS | `VERSION` file unchanged at `2.0.0` throughout this run | `Evidence/08_Git_Final/` | `cat VERSION` | `2.0.0` |
| W5C1-G11 | PASS | No PyPI upload, GHCR/Docker Hub push, Git tag, or GitHub Release occurred; `publish` was only ever exercised via unit tests with fake adapters plus CLI-level refusal paths (missing `--manifest`/`--yes`, failing preflight) that stop before any adapter is constructed | `tests/unit/test_release_cli.py::PublishRefusesSafelyTests`, `Evidence/08_Git_Final/` | `python -m pytest -q tests/unit/test_release_cli.py::PublishRefusesSafelyTests` | 4 passed |

## Resume / conflict safety

| Gate | Status | Kurzbeweis | Evidence | Command/Test | Result |
|---|---|---|---|---|---|
| W5C1-G12 | PASS | Resume after PyPI success / GHCR failure tested: PyPI never re-uploaded, engine resumes at GHCR | `Evidence/02_State_Resume/01_...txt` | `test_resume_after_pypi_success_ghcr_failure`, `test_resume_starts_at_ghcr_when_state_already_says_pypi_published` | PASS |
| W5C1-G13 | PASS | Resume after GHCR success / Docker Hub failure tested | `Evidence/02_State_Resume/01_...txt` | `test_resume_after_ghcr_success_dockerhub_failure` | PASS |
| W5C1-G14 | PASS | Resume after Docker Hub success starts at external verification | `Evidence/02_State_Resume/01_...txt` | `test_resume_after_dockerhub_success_starts_at_external_verification` | PASS |
| W5C1-G15 | PASS | Resume after external verification proceeds to tag; resume after tag verifies existing tag and continues to release; resume after GitHub Release verifies existing release and finishes | `Evidence/02_State_Resume/01_...txt` | `test_resume_after_external_verification_may_proceed_to_tag`, `test_resume_after_tag_verifies_existing_tag_and_continues_to_release`, `test_resume_after_github_release_verifies_existing_release_and_finishes` | PASS |
| W5C1-G16 | PASS | Crash-window reconciliation tested: stale local state (`PREPARED`) but remote already has the artifact - engine resumes without republishing; a genuine remote conflict still stops even with stale local state | `Evidence/02_State_Resume/01_...txt` | `StaleLocalStateReconciliationTests` (2 tests) | PASS |
| W5C1-G17 | PASS | PyPI conflicting identity fails closed (both at the adapter level and the engine level) | `Evidence/01_Publish_Engine/`, `Evidence/03_Remote_Conflict/` | `PyPIAdapterTests::test_verify_conflicting_release_fails_closed`, `ConflictFailsClosedTests::test_pypi_conflict_stops_real_run` | PASS |
| W5C1-G18 | PASS | GHCR conflicting digest fails closed; a missing/unreachable Docker tool is distinguished from a genuinely absent tag (tightened `check_registry_image()`) and also fails closed as "unavailable", never as "safe to publish" | `Evidence/03_Remote_Conflict/01_...txt` | `RegistryAdapterTests::test_verify_conflicting_digest_fails_closed`, `test_unavailable_tool_fails_closed_instead_of_claiming_absent` | PASS |
| W5C1-G19 | PASS | Docker Hub uses the same conflict logic as GHCR (`_RegistryAdapter`) | `Evidence/03_Remote_Conflict/01_...txt` | `RegistryConflictTests` (remote_checks, shared) | PASS |
| W5C1-G20 | PASS | Git tag on the wrong commit fails closed (local or remote) | `Evidence/05_Ordering_Barriers/01_...txt` | `GitTagAdapterTests::test_verify_wrong_commit_fails_closed` | PASS |
| W5C1-G21 | PASS | GitHub Release bound to an incompatible tag fails closed | `Evidence/05_Ordering_Barriers/01_...txt` | `GitHubReleaseAdapterTests::test_verify_incompatible_tag_fails_closed` | PASS |
| W5C1-G22 | PASS | Illegal state/order transitions fail closed: cannot skip ahead, cannot move backwards, unknown target state rejected, tag/release barriers enforced twice (state + adapter) | `Evidence/03_Remote_Conflict/01_...txt`, `Evidence/05_Ordering_Barriers/01_...txt` | `test_release_state.py::StateOrderTests`, `TagAndReleaseBarrierTests` | PASS |
| W5C1-G23 | PASS | No automatic new version after partial failure: `state.version` unchanged after a stopped real run; `ensure_same_version()`/`ensure_same_identity()` unchanged from W5-R01 and still enforced by the CLI publish path | `tests/unit/test_release_engine.py::NoAutomaticVersionBumpTests`, `tests/unit/test_release_state.py` | pytest | PASS |

## Security / validation

| Gate | Status | Kurzbeweis | Evidence | Command/Test | Result |
|---|---|---|---|---|---|
| W5C1-G24 | PASS | Synthetic sentinel secrets (`ghp_SENTINEL...`, `TWINE_PASSWORD`, `GH_TOKEN`) never appear in a constructed command line, stdout, stderr, or a raised exception message; subprocess stderr routed through `redaction.redact_text()` before reaching an exception | `Evidence/06_Secret_Redaction/01_...txt` | `test_release_adapters.py -k secret`, `test_release_cli.py -k secret` | PASS |
| W5C1-G25 | PASS | Targeted correction tests PASS: 157 tests + 11 subtests across all `tests/unit/test_release_*.py` (up from 91+11 in W5-R01) | `Evidence/07_Tests/01_targeted_release_tooling_tests.txt` | `python -m pytest -q tests/unit/test_release_*.py` | 157 passed, 11 subtests passed |
| W5C1-G26 | PASS | Full unit suite PASS | `Evidence/07_Tests/03_full_unit_suite.txt` | `python -m pytest -q tests/unit` | see evidence for exact counts |
| W5C1-G27 | PASS | `git diff --check` PASS | `Evidence/08_Git_Final/` | `git diff --check` | Exit 0 |
| W5C1-G28 | PASS | `build/BUILD.md` documents the shared engine, the five real adapters, the credential-contract-only design, and the `publish --manifest --yes` precondition chain | `Evidence/07_Tests/02_documentation_matches_corrected_model.txt` | `grep` against `build/BUILD.md` | all terms found |

## Git / governance

| Gate | Status | Kurzbeweis | Evidence | Command/Test | Result |
|---|---|---|---|---|---|
| W5C1-G29 | PASS | AW-01 recorded as `ACCEPTED BY COORDINATOR`; no historical rewrite, no faked earlier timestamp, no retroactive W5P-G03 PASS attempted | `04_DEVIATIONS_AND_WAIVERS.md` | Document review | PASS |
| W5C1-G30 | PASS | Corrected W5-R01 history is exactly one local commit ahead of Distributed (the existing unpushed commit was amended in place, not a second commit added) | `Evidence/08_Git_Final/01_...txt` | `git rev-list --count e5f76bf1...HEAD` | `1` |
| W5C1-G31 | PASS | Workspace clean at final state | `Evidence/08_Git_Final/01_...txt` | `git status` | clean |
| W5C1-G32 | PASS | Remote Distributed unchanged at `e5f76bf1e4fd28e68624f30140fcf8ec6876db96`; no push performed | `Evidence/08_Git_Final/01_...txt` | `git fetch origin`; `git rev-parse origin/...`; no upstream configured | unchanged, no push |

## Summary

- PASS: 32
- FAIL: 0
- BLOCKED: 0
- N/A: 0
