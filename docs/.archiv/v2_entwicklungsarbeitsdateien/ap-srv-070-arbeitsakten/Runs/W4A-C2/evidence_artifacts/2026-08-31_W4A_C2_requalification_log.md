# AP-SRV-070 W4A-C2 — Real Artifact Re-Qualification Log — EVIDENCE_BLOCKED

## Fingerprint change

The `BUILDER_REVISION` bump (2 → 3, Root Findings F/G/H bumped the guarded
builder surface) changes the default fingerprint for a build on this host,
computed via the real `install_kroko.fingerprint_for(args)` path (no stubs):

| | Before C2 (`BUILDER_REVISION=2`, from the C1 log) | After C2 (`BUILDER_REVISION=3`) |
|---|---|---|
| free (windows/amd64/cp312) | `9055547da3ba4d66` | `a11549d157f478b6` |
| pro (windows/amd64/cp312) | `2469fd1a25e86b97` | `0599c1a1bdc8e1c2` |

## Provenance analysis (see Root Correction Report §6)

The C2 changes (Findings E, F, G, H) were analyzed against the real Windows
build path:

- Finding E's ambient-strip extension (`KROKO_LICENSE` added to
  `sanitize_build_subprocess_env`) is shared by `windows_build_env()`, but
  that function's own pre-existing (C1) docstring already states the Windows
  build has no build-effective ambient variables beyond the secret boundary,
  and the pinned Windows builder is controlled by `--variant`/`BUILD_VARIANT`,
  not by `KROKO_LICENSE`.
- Finding F's `materialize_pristine_checkout` changes future checkout
  behavior (pristine before patching), not any declared fingerprint value or
  the already-completed historical build's provenance.
- Finding G (C++ toolchain identity, pre-installed-ONNXRuntime CMake flag) is
  Linux-only: the Windows build uses the generic
  `kroko-docker-windows-crossbuild` toolchain identity and its own upstream
  CMake invocation, unaffected by `LINUX_CMAKE_FLAGS` or Linux toolchain
  probing.

This analysis supports that re-registering the existing qualified wheel under
the new fingerprint would be legitimate - **provided the wheel's actual bytes
are available to re-register.**

## Blocker: the wheel file itself could not be located

Attempted re-qualification steps, mirroring the W4A-C1 procedure:

1. Located the real default artifact store
   (`resolve_store_root()` → `C:\Users\user\AppData\Local\VoiceSTT\kroko-artifacts`
   on this host): both `free` and `pro` variant directories are empty/absent.
2. Checked the session-scratch artifact store used for the W4A-C1
   re-qualification (recorded there as a path under this session's own
   scratchpad directory): **no longer exists** - the directory is gone,
   presumably cleared by an intervening temp-directory cleanup between
   sessions.
3. Searched the entire `P:` drive for `kroko_onnx_onnx-1.12.9*.whl` by
   filename: two matches, both under unrelated local projects
   (`P:\LokaleProjekte\Legacy-STT-kroko-debug\...` and
   `P:\LokaleProjekte\RealtimeVoiceProjekte\Legacy-STT\...`) that are not
   part of this `voice-stt-server` repository or worktree.
4. Compared both candidates against the recorded original
   (`kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl`,
   12 549 957 bytes, SHA-256 `ac26db5d8c063649028924d4b55b14019b2370e8c457841ea278a8e48dd50041`):

   | Candidate | Size (bytes) | SHA-256 | Match? |
   |---|---|---|---|
   | Recorded original | 12 549 957 | `ac26db5d8c063649028924d4b55b14019b2370e8c457841ea278a8e48dd50041` | — |
   | `Legacy-STT-kroko-debug\...\kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl` | 12 549 956 | `620b64798c5942f1414234e6d96c713b2fd95d430cca799402427ebac03cc94` | **No** |
   | `RealtimeVoiceProjekte\Legacy-STT\...\kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl` | 12 549 955 | `45e3c86fce28dfff0a0d6f96856a20f747391aed40646d7a6ea5b22054762084` | **No** |

   Both candidates differ in size and hash from the recorded original. They
   are unrelated artifacts from unrelated local projects, not copies of the
   qualified wheel this project's evidence chain refers to. Neither was used.
5. A byte-size-only search (12 549 957 bytes, ignoring filename) across the
   accessible parts of the `voice-stt-server` repository tree found no match
   either.

## Determination: EVIDENCE_BLOCKED

Per the C2 prompt's §7 ("Wenn diese Provenienzbedingung nicht sicher erfüllt
ist: nicht umdeuten, sondern EVIDENCE_BLOCKED für genau diesen
Real-Artifact-Teil melden"), and consistent with it: the actual qualified
wheel bytes are not available on this machine to re-register under the new
fingerprint. This is reported as **EVIDENCE_BLOCKED for the real-artifact
re-qualification only.**

Explicitly **not done**, per the same prompt's constraints:

- No unrelated wheel was substituted or misrepresented as the qualified
  artifact.
- No new native Kroko build was triggered to regenerate a replacement -
  Section 7 explicitly forbids forcing a new ~30-minute build just for C2,
  and no other part of C2 required one.

This blocker affects only the real-artifact bookkeeping step. It does not
affect the four Root Finding (E-H) implementations, their RED-first tests, or
the full regression result, all of which are otherwise complete and green.
