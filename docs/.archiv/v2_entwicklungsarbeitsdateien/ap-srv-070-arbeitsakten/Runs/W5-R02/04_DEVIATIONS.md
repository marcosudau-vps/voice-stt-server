# AP-SRV-070 / W5-R02 - Deviations

This run found real qualification prerequisites that were unavailable or
that revealed genuine, reproducible source-level issues in the exact
frozen RC. Each is documented below with expected/actual/cause, whether
source is implicated, affected gates, and whether a Correction Run is
required. Nothing here was hidden, and no gate was faked to PASS.

## D1: GitHub Actions CI fails on both platforms (Windows deterministic, Ubuntu reproduced twice)

- Expected: `.github/workflows/ci.yml` green on both `windows-latest`
  and `ubuntu-24.04` for the exact frozen commit.
- Actual: Windows job failed identically across 2 independent full runs
  (4 tests in `tests/unit/test_kroko_onnx_engine.py`); Ubuntu job failed
  identically across the same 2 runs (1 test in
  `tests/unit/test_fastapi_server_multi_user.py`).
- Cause: Windows - `VoiceSTT/transcription_engines/model_resolver.py::
  resolve_kroko_model()` calls `Path.resolve()`, which returns the 8.3
  short form of the GitHub-hosted Windows runner's home directory,
  breaking exact-string-equality test assertions. Ubuntu - a timing race
  between a client-side event-cursor snapshot and the server's own
  replay-window query in the presence of a real background
  `AutoScheduler` task.
- Source implicated: Yes, on both counts (a product function on
  Windows; a test's own race-sensitivity on Ubuntu). Fixing either
  requires editing source-controlled files, forbidden in W5-R02.
- Affected gates: W5Q-G07, W5Q-G08, W5Q-G09 (package/install steps
  unaffected and PASS), W5Q-G10, W5Q-G39 (indirectly, via the overall
  verdict).
- Correction Run required: **Yes.** This is the primary blocker. A new
  internal RC candidate (product version remains 2.0.0) should fix
  both issues (Windows: normalize the resolved path consistently on
  both sides of the comparison, e.g. via `os.path.samefile()` or
  resolving both sides identically; Ubuntu: make the replay-window
  assertion robust to interleaved background-scheduler events, or
  disable/stub the scheduler for that specific assertion window) and
  re-run CI to confirm green before the next qualification attempt.
  Full root-cause detail: `Evidence/01_GitHub_Actions/01_ci_run_and_root_cause.txt`.

## D2: Local full unit-suite runs on this session's own host were confounded by resource contention

- Expected: a clean local `python -m pytest -q tests/unit` run
  supplementing the GitHub Actions evidence.
- Actual: three local attempts on this session's Windows host all hit
  environment-level failures unrelated to the source under test - two
  distinct `MemoryError` crashes and one `PermissionError` from a locked
  shared temp directory - all while this session was also running heavy
  concurrent work (native Kroko C/C++ compiles via Docker, a large
  network-flaky WSL2 package install).
- Cause: this session's own concurrent orchestration, on a host that
  went into visible memory/process-management distress partway through
  the run (process-listing commands like `tasklist`/`taskkill` began
  timing out; `vmmemWSL` grew past 16 GB). The user manually intervened
  (killed stray processes, then a full PC restart), after which a
  `wsl --shutdown` was also needed once mid-run to recover ballooned
  WSL2 memory following the production-image Docker builds.
- Source implicated: No. GitHub Actions' clean, isolated runs
  (Deviation D1) are the authoritative regression signal.
- Affected gates: W5Q-G10 (uses the CI result as authoritative;
  local attempts noted as non-authoritative supplementary data only).
- Correction Run required: No additional action beyond D1 - this is an
  orchestration/environment note, not a product finding.

## D3: `release_tooling` RC-manifest CLI crashes on real `tools/build_production.py` output

- Expected: `release.py manifest build --free-build-manifest ...
  --pro-build-manifest ...` (Section 24's documented path) consumes
  `dist/build-manifest.json` from `tools/build_production.py all`
  directly.
- Actual: `release_tooling/cli.py::_cmd_manifest_build` raises
  `KeyError: 'sha256'` reading
  `variants.<variant>.kroko.artifact.sha256`; the real field written by
  `tools/build_production.py` at that path is named `wheelSha256`.
- Cause: two tools in the same commit disagree on their own shared JSON
  schema. No existing unit test (`tests/unit/test_release_*.py`, all 157
  passing) exercises `_cmd_manifest_build` against real
  `tools/build_production.py` output - only against self-consistent
  synthetic fixtures.
- Source implicated: Yes - either `tools/build_production.py`'s writer
  or `release_tooling/cli.py`'s reader needs to change (or both need to
  agree on one key name), forbidden in W5-R02.
- Affected gates: W5Q-G53 (worked around without a source change by
  calling `release_tooling.rc_manifest.build_rc_manifest()` - the actual
  canonical manifest-assembly helper - directly with independently
  verified values, then validating the result through the CLI's own
  separate, working `manifest validate` subcommand; `05_RC_MANIFEST.json`
  itself is correct and schema-valid despite this).
- Correction Run required: **Yes**, alongside D1 - rename one side's
  field (or add a small compatibility read in the CLI) so
  `release.py manifest build` works end-to-end against real
  `tools/build_production.py` output, and add a regression test that
  feeds the CLI real (or realistically-shaped) build-manifest JSON.

## D4: Real-engine live E2E sessions did not reach full-audio completion

- Expected: a clean, complete real transcription of the full
  `tests/unit/audio/asr-reference.wav` fixture through both
  Faster-Whisper and Kroko Free, via
  `tests.unit.test_fastapi_server_multi_user_asr_integration`.
- Actual: both engines produced correct, coherent, non-hallucinated
  transcriptions of roughly the first half of the audio (reference
  utterances 0-3 of 9), then the session ended - the test's own
  `lastFinalAfterAudioEnd` metric showed the last final transcription
  event landing ~22 seconds before the audio finished streaming, in
  both runs, at almost the same point in the audio.
- Cause: not conclusively determined within this session's time budget.
  Because the exact same pattern reproduced across two structurally
  different, independently-running engines (ctranslate2/faster-whisper
  on Windows; Kroko ONNX on WSL2 Ubuntu) against the same fixture and
  harness, the most likely explanation is an interaction between this
  specific *load-test* harness (built for multi-client parallel runs
  per `docs/testing.md`, single-client here) and VAD/silence-duration
  defaults around a longer pause in the source audio - not a defect in
  either qualified engine or in the core server session/protocol
  pipeline (both of which are otherwise exercised correctly by the
  substantial portion of audio that *did* transcribe correctly).
- Source implicated: Unclear / not established either way.
- Affected gates: W5Q-G36, W5Q-G37 (INCONCLUSIVE, not PASS and not a
  fabricated FAIL), W5Q-G39 (FAIL as a consequence).
- Correction Run required: Recommended - either re-run this specific
  check with the product's own real-time client instead of this
  load-test harness, or investigate the harness's single-client
  stop/completion logic against this fixture, to get an unambiguous
  pass/fail read.

## D5: Kroko Pro live E2E and runtime license qualification are BLOCKED

- Expected: a real Kroko Pro transcription through the licensed runtime.
- Actual: no Kroko Pro runtime credential (`KROKO_API_KEY` or any
  documented alias) exists anywhere in this environment - confirmed
  absent from the process environment on both the Windows host and the
  WSL2 Ubuntu distro, and from every `.env`/config file checked.
- Cause: environment limitation, not a product or source issue. The Pro
  *build* identity (fingerprint, native compile, image) was fully
  qualified without needing a key, per build/BUILD.md's documented
  contract that a runtime key is never a build input.
- Source implicated: No.
- Affected gates: W5Q-G38 (BLOCKED, not faked PASS, not silently N/A).
- Correction Run required: Only if/when a genuine Kroko Pro trial or
  commercial credential becomes available in the qualification
  environment; this should not gate the current run's own conclusions
  about D1-D4.

## D6: Windows Docker Desktop bind-mount limitation (environment-only, resolved without a workaround affecting the RC)

- Expected: `docker-compose.yml`'s documented bind-mount pattern for
  `/var/lib/voicestt` works against a fresh host directory.
- Actual: the container crash-looped with `PermissionError` writing to
  the bind-mounted directory, even after explicitly `chown`-ing the host
  directory to the container's UID/GID (10001) from another container -
  ruling out an actual ownership mismatch.
- Cause: a known Docker Desktop for Windows limitation with non-root
  container UIDs writing through its Windows-host bind-mount
  translation layer (gRPC-FUSE/virtiofs), not specific to VoiceSTT. This
  environment (Docker Desktop on Windows) is not the product's actual
  production target (native Linux Docker hosts). Using a Docker **named
  volume** instead of a host bind mount (identical image, identical
  everything else) worked correctly and was used for all subsequent
  model-management/persistence/shutdown checks.
- Source implicated: No.
- Affected gates: none - fully worked around; W5Q-G34/G45/G46 all PASS
  using the named-volume setup, which is a faithful substitute for a
  correctly-permissioned production Linux volume.
- Correction Run required: No. Documented for transparency only.

## D7: Not attempted within this session's time budget

- W5Q-G42 (read-only custom model source discovery/non-mutation) was
  not tested live this run, given the cumulative time already spent on
  D1-D6 and this session's repeated environment recovery interruptions
  (a mid-run PC restart and a WSL2 memory-pressure recovery, both
  requested/approved by the user in real time as the host showed
  distress). It is marked NOT TESTED, not PASS and not FAIL, in
  `03_GATE_INDEX.md`.
- Source implicated: No - simply not exercised.
- Correction Run required: Recommended as a quick addition to the next
  qualification attempt; the mechanism itself (`custom_paths` /
  `VOICESTT_FASTER_WHISPER_MODEL_ROOT`/`VOICESTT_KROKO_MODEL_ROOT`) is
  already exercised at the unit level by `tests/unit/test_stt_model_management.py`,
  all passing in this RC's regression run.

## Overall disposition

D1 and D3 are genuine, reproducible, source-level findings that force
`NOT READY FOR ROOT REVIEW` on their own (per Section 33's explicit stop
condition: a mandatory gate cannot pass without a forbidden source
change). D2 and D6 are environment/orchestration notes with no bearing
on the RC itself. D4 is a real but inconclusive finding worth
investigating further. D5 and D7 are honest scope limitations, reported
as such rather than faked.
