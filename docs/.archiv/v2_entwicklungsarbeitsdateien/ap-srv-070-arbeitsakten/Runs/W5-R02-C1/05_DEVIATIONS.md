# AP-SRV-070 / W5-R02-C1 - Deviations

## Prompt self-reference inconsistencies (documentation-only, no effect on the correction)

- The prompt's own Section 0 "Prompt source" field names
  `2026-09-07_AP-SRV-070_W5_R02_C1_SONNET5.md`, but the file the user
  actually pointed at (and which was copied byte-identically as
  `00_PROMPT.md`) is
  `2026-09-07_AP-SRV-070_W5_R02_C1_SONNET5_SECRET-AWARE.md`. The
  actually-supplied file was treated as authoritative.
- The prompt gives two different paths for the operator secret bundle
  (`P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env`
  in Section 0's main line vs. a WSL view implying
  `P:\Secrets\VoiceSTT\voice-stt.env` on the very next line), and the
  user's chat instruction separately named the latter path too. Only
  `P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env`
  exists on disk (existence/size checked via `ls -la` metadata only -
  245 bytes - never opened/read/printed/copied). Since this run never
  needed or used the secret bundle's content either way, this
  discrepancy had no effect on the correction itself. See
  `Evidence/00_Preflight/01_starting_state.txt`.

## Environment issues during validation (not source-level, fully resolved)

### E1: Windows-mounted CWD breaks SQLite WAL mode for some Ubuntu tests

Running the Ubuntu suite from this session's usual working directory
(`/mnt/p/GithubRepos/...`, a DrvFs mount of the Windows P: drive) caused
8 unrelated test failures (`sqlite3.OperationalError: disk I/O error`)
in tests whose `ServerSettings` defaults leave the event-store path
relative to CWD. Resolved by copying the workspace to native WSL2
storage (`~/w5r02c1-native-src`) for test execution only; the source of
truth remains the git worktree on `P:`. This is arguably a *more*
faithful proxy for real GitHub Actions (which always runs from a native
checkout) than the mounted path was, not a workaround that weakens the
proof.

### E2: WSL2 Ubuntu distro missing `libssl-dev` and build-toolchain siblings

The native WSL2 copy's first full-suite run hit 27 failures, all in
`tests/unit/test_kroko_artifact_store.py` /
`test_kroko_fingerprint.py` (unrelated to any file this correction
touches), because `libssl-dev` (and `build-essential`, `cmake`,
`pybind11-dev`, `zlib1g-dev`) were not installed as system packages on
this particular WSL2 Ubuntu distro - a local machine setup gap, not
present on real GitHub Actions Ubuntu runner images (which ship these by
default). No `sudo` password was available to this session to install
them directly; the user installed them. The full suite was then
re-run and passed completely (1708 passed, 14 skipped, 985 subtests,
0 failed).

Neither E1 nor E2 touched, or required touching, any source-controlled
file. Both are fully detailed in `Evidence/02_Ubuntu_Replay_Race/` and
`Evidence/06_Ubuntu_Regression/`.

## Explicitly not addressed in C1 (per prompt Section 2/11 - by design, not an oversight)

- D2 (parent run's local resource contention): environment-only, no
  action needed here.
- D4 (Faster-Whisper/Kroko Free live E2E inconclusive): not touched. No
  reproducible source defect was found or manufactured; ASR engine/
  session/harness code was not modified.
- D5 (Kroko Pro credential now available via the external secret
  bundle): **not consumed**. No Kroko Pro live E2E was run or attempted
  in this correction. The secret bundle's content was never read,
  printed, hashed, or otherwise accessed.
- D6 (Docker Desktop Windows bind-mount limitation): environment-only;
  this correction needed no Docker at all.
- D7 (read-only custom-model-source gate): not tested; not marked as
  passed.

These remain qualification items for the next frozen qualification run
(W5-RC2), not closed by C1.

## Secret handling compliance statement

At no point in this run was the file
`P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env`
(or any other candidate path) opened, read, printed, `cat`'d, copied,
hashed, or otherwise had its content accessed. No environment variable
dump, log, or evidence file in this run contains, or was checked for
consistency against, any value from that file. `VOICESTT_API_KEY`,
`VOICESTT_ADMIN_API_KEY`, and `VOICESTT_KROKO_ONNX_KEY` were never set,
referenced, or required by anything this correction did.
