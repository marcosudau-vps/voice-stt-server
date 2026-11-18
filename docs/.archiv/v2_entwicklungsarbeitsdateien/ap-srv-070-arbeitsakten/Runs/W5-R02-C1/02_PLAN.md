# AP-SRV-070 / W5-R02-C1 - Correction Plan

Written before any source-controlled file is edited (Section 5).

## Confirmed defects (from W5-R02, re-verified by direct source reading in this run)

### D1-Windows: `tests/unit/test_kroko_onnx_engine.py`

Four tests compare a raw path *string* returned through
`KrokoOnnxBackend` (which flows through
`VoiceSTT/transcription_engines/model_resolver.py::resolve_kroko_model()`,
confirmed by direct reading to call `.resolve()` at three return points:
lines 119, 135, 145) against an unresolved `tempfile.TemporaryDirectory()`-
based path built by the test's own `make_model_file()` helper. On
GitHub-hosted Windows runners `.resolve()` returns the 8.3 short form of
the runner's home directory; the raw comparison string does not, so
`assertEqual` fails even though both spellings name the identical file.

Affected tests (all in `class KrokoOnnxEngineTests`):
- `test_resolves_absolute_model_path` (line 237)
- `test_resolves_relative_model_under_download_root` (line 252)
- `test_engine_option_model_path_overrides_config_model` (line 270)
- `test_model_dir_selects_single_data_file` (line 288) - here
  `resolve_kroko_model`'s `model_dir` single-data-file-glob branch (line
  144-145 of `model_resolver.py`) also calls `.resolve()`, so this test
  hits the identical mismatch even though it does not go through the
  `model_path`/`download_root` branches the other three exercise.

Coordinator disposition (prompt Section 8): preserve
`resolve_kroko_model()`'s existing `.resolve()` behavior (a resolved,
canonical path is a legitimate and arguably better contract than an
unresolved one); fix the *tests* to assert semantic file identity
(`os.path.samefile()`) instead of raw string spelling.

### D1-Ubuntu: `tests/unit/test_fastapi_server_multi_user.py`

`test_store_outage_closes_live_stream_and_recovery_allows_new_stream`
(class `FastAPIMultiUserWebSocketTests`, starts line 1729) subscribes
with `afterCursor: events.latest_cursor()` (a cursor snapshot taken
*before* the WebSocket subscribe message is even sent) and then asserts
the next three received frames are exactly `log.hello`, `log.subscribed`,
`log.replay_completed` in that order (lines 1752-1757) - i.e. an
unconditionally empty replay window. The server (`AutoScheduler` is a
real, live background scheduler in this test's `create_app(...,
scheduler_factory=AutoScheduler, ...)`) can legitimately commit an event
between that client-side snapshot and the server's own replay-window
query; if it does, one or more `log.event` frames validly precede
`log.replay_completed`, and the current fixed 3-assertEqual sequence
fails. The *same file* already has the *correct* pattern for the second
subscription later in this very test (lines 1803-1809: loop, collect
`log.event`, break on `log.replay_completed`) - the fix is to apply that
same, already-established, protocol-correct pattern to the first
subscription block too, with added cursor-monotonicity and no-unexpected-
message-type strictness (Section 9.2's requirements go slightly beyond
what the existing second-block pattern checks).

No production code is implicated for this defect - the server's replay
behavior is already correct per its own protocol contract; only this
one test's assumption of empty-replay is wrong.

### D3: `release_tooling/cli.py::_cmd_manifest_build` vs `tools/build_production.py`

Confirmed by direct reading: `tools/build_production.py::resolve_kroko_wheel()`
returns a payload whose `artifact` sub-dict carries the Kroko wheel hash
under the key `wheelSha256` (confirmed both by the real captured
`dist/build-manifest.json` from the W5-R02 parent run, and independently
by the *existing* test fixture `_describe_payload()` in
`tests/unit/test_build_production.py` line 117, which already writes
`"wheelSha256": "0" * 64` - i.e. the test infrastructure for the producer
side already agrees on the real field name). `release_tooling/cli.py`
line 212/214 (`_cmd_manifest_build`) reads
`variants.<variant>.kroko.artifact["sha256"]` at the same nested path -
a different key - and raises an uncaught `KeyError` when fed real
production-shaped input. No existing test in `tests/unit/test_release_*.py`
exercises `_cmd_manifest_build` at all (confirmed by grep: only
`manifest validate` has CLI-level tests, in
`class ManifestValidateCommandTests`) - this is why the bug was never
caught.

## Exact intended files

1. `tests/unit/test_kroko_onnx_engine.py` (test-only) - add a
   `assertSameFile(a, b)` helper to `KrokoOnnxEngineTests` using
   `os.path.samefile()`; use it in the four affected tests in place of
   raw `assertEqual`; add one new small test demonstrating two different
   legal spellings of the same file are accepted as identity-equivalent
   (Section 8.3, "if practical").
2. `tests/unit/test_fastapi_server_multi_user.py` (test-only) - replace
   the three fixed `assertEqual` calls at the first subscription in
   `test_store_outage_closes_live_stream_and_recovery_allows_new_stream`
   with a loop matching the file's own existing pattern at lines
   1803-1809, plus cursor-monotonicity and unexpected-message-type
   assertions per Section 9.2.
3. `release_tooling/cli.py` (production code) - add a small
   `_extract_kroko_artifact_sha256(manifest, variant)` helper that reads
   the canonical `wheelSha256` field, tolerates a legacy `sha256` field
   as a fallback, and raises `release_tooling.errors.ManifestError`
   (already the correct exception class for "an RC manifest ... fails a
   required identity check", already caught cleanly by `main()`) if
   both are present and disagree, or if neither is present. Use it for
   both the free and pro manifests in `_cmd_manifest_build`. Add
   `ManifestError` to the existing `from .errors import ReleaseError`
   import line.
4. New test coverage for (3): add a `ManifestBuildCommandTests` class to
   `tests/unit/test_release_cli.py` (matching that file's existing
   `unittest` + `cli.main([...])` convention) that:
   - calls the *real* `tools.build_production.resolve_kroko_wheel()`
     (imported the same way `tests/unit/test_build_production.py`
     already does, via `sys.path` injection for the `tools/` directory)
     against a `RecordingRunner`-style fake, exactly like
     `test_build_production.py::test_resolve_kroko_wheel_reuses_a_verified_artifact_without_building`
     already does - so the Kroko `artifact` payload used in the new
     manifest-build test is genuine production-code output, not another
     hand-typed fixture;
   - assembles a full free/pro build-manifest dict around that real
     payload, mirroring (not re-implementing) the literal dict shape
     `tools.build_production.run()` writes (`gitCommit`,
     `voicesttVersion`, `voicesttWheel`, `variants.<v>.kroko`,
     `variants.<v>.image`, `imageId`);
   - writes both to temp JSON files and calls `release_tooling.cli.main(["manifest", "build", ...])`
     against them, asserting exit code 0, a valid resulting manifest
     (via `rc_manifest.load_rc_manifest`), and that
     `kroko.free.artifactSha256`/`kroko.pro.artifactSha256` equal the
     real `wheelSha256` values from the injected payload;
   - a second test proves the legacy-`sha256`-fallback path works when
     `wheelSha256` is absent;
   - a third test proves a `wheelSha256`/`sha256` mismatch fails closed
     (non-zero exit, `ManifestError` message, no manifest file written).

No other file is touched. In particular: `VoiceSTT/transcription_engines/model_resolver.py`
(production Kroko/Faster-Whisper path-resolution logic) is **not**
edited - its `.resolve()` behavior is preserved exactly, per the
coordinator's explicit instruction in Section 8.1.
`tools/build_production.py` is **not** edited - it is already the
correct/canonical producer; only the CLI *consumer* changes.

## AGENTS.md "Größere Änderungsaktion" assessment

None of the three corrections touch architecture, a public protocol/API,
a persisted data format, a security boundary, or deployment structure,
and none span multiple product modules in a way that changes cross-
module behavior: (A) and (B) are test-assertion-only fixes with zero
production behavior change; (C) is a narrow internal release-engineering
CLI bug fix (an unpublished, maintainer-only tool) that makes an
already-intended data flow actually work, not a new architectural
decision. This correction therefore does not trigger the
`docs/.archiv/README.md` dated-action-folder process; this plan plus
`03_CORRECTION_REPORT.md`'s dated Soll/Ist comparison (Section 15 of the
prompt) serve as this run's equivalent record, both filed here under
`_workflow-tools/AP-SRV-070/Runs/W5-R02-C1/`.

## Test strategy

- Targeted: the 4 previously-failing Windows Kroko tests, plus the full
  `tests/unit/test_kroko_onnx_engine.py` file, on Windows.
- Targeted: the previously-failing Ubuntu replay test, run repeatedly
  (target >=20 consecutive PASS, or a justified >=10) in WSL2 Ubuntu
  24.04, plus the full `tests/unit/test_fastapi_server_multi_user.py`
  file.
- Targeted: the new `ManifestBuildCommandTests`, plus the full
  `tests/unit/test_release_*.py` set (all 9 files) and
  `tests/unit/test_build_production.py`.
- Full regression: `python -m pytest -q tests/unit` on Windows (isolated,
  no concurrent Docker/native builds - this correction run needs no
  Docker or native Kroko compilation at all, unlike the parent W5-R02
  qualification, so this should be materially lower-risk for resource
  contention) and on WSL2 Ubuntu 24.04, both compared against the
  1704/14/985/0 baseline plus the handful of new tests added here.
- `git diff --check`.
- Package/release-tool smoke: `python -m build`, `twine check`,
  `release.py --help`, `release.py manifest build` with
  production-shaped input (using the real fake-runner-produced payload
  from the new test, written to real temp files, not just via pytest),
  `release.py manifest validate`, `release.py dry-run`.

## No-go scope (explicitly out of bounds for C1)

- D2 (local resource contention): no source change, environment note only.
- D4 (inconclusive live E2E): no ASR engine/session/harness change without
  a separately established, reproducible product defect - none was
  found, none will be manufactured here.
- D5 (Kroko Pro credential now available): C1 does not read, use, print,
  hash, or otherwise touch the secret bundle at
  `P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env`
  (the path that actually exists on disk in this environment - see
  `Evidence/00_Preflight/01_starting_state.txt` for the three
  inconsistent candidate paths encountered and which one was verified
  to exist). No Kroko Pro live E2E is attempted in C1.
- D6 (Docker Desktop Windows bind-mount limitation): environment-only,
  no source change; C1 needs no Docker at all.
- D7 (read-only custom-model-source gate): not tested here, remains a
  W5-RC2 qualification item; not marked as passed.
- `VoiceSTT/transcription_engines/model_resolver.py`: read for context,
  not edited.
- Any change to `.github/workflows/ci.yml`: not needed for this
  correction and not touched.

## Expected single-commit outcome

Exactly one local commit on `work/ap-srv-070-w5-r02-c1`, directly on top
of `bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602`, touching exactly:
`tests/unit/test_kroko_onnx_engine.py`,
`tests/unit/test_fastapi_server_multi_user.py`,
`release_tooling/cli.py`, `tests/unit/test_release_cli.py`, plus this
run's own archive files under `_workflow-tools/AP-SRV-070/Runs/W5-R02-C1/`
(outside the repository, not part of the commit). `VERSION` remains
`2.0.0`. No tag, no push, no publish.
