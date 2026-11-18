NOT READY FOR ROOT REVIEW

# AP-SRV-070 / W5-R02 - Final Report

## Candidate

- Candidate ID: W5-RC1
- Product version: 2.0.0 (unchanged throughout this run)
- Source commit: `bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602`
- Source tree: `f7b304b1959e48457a8eefd8919484f55214633b`
- Target integration branch: `feat/einheitliche-triggerarchitektur-distributed`

## Package identities

- Wheel: `voicestt-2.0.0-py3-none-any.whl`, sha256
  `a1902b76e886b05775b5ff134d1b616824063ba14e78897084c62c2f2bed9f3f`
- Sdist: `voicestt-2.0.0.tar.gz`, sha256
  `5c8dad084fa62968d5c0c76646531ce4a44b9cd55d62c793dabc345f638a0133`
- `twine check`: PASSED for both artifacts.

## Kroko identities

- Free (Linux/AMD64): fingerprint `ab8986fd7fb93756`, wheel sha256
  `df99ecb1def4a9a62cede4f708e76d0e42953f61e17541f0f7ec20641ed74952`
  (the identity actually baked into the Free production image).
- Pro (Linux/AMD64, build identity only): fingerprint `36b440630c0a9475`,
  wheel sha256 `37ae1630cf239f0bbe41abb1b47f90623eb0a8402803af98e27048c382f6ef43`.
- Free/Pro namespaces and build-identity separation confirmed distinct;
  no runtime credential ever participated in either build.

## Image identities

- Free: `voice-stt-server:2.0.0`, image ID
  `sha256:69bd531084f10dce09a612ea40a5be65910b62fc8a8d9e7319bb33e2cf5ddc73`
- Pro: `voice-stt-server-pro:2.0.0`, image ID
  `sha256:fa58f19f73f988dab410817083125da9632f12ef0b053e85b21d2ba29422dfcd`
- Both: linux/amd64, `ubuntu:24.04` runtime stage, non-root user
  `voicestt` (UID/GID 10001), OCI `version`/`revision` labels exactly
  matching this candidate, liveness-only healthcheck, no editable
  install, no native Kroko compilation inside the production Dockerfile,
  no secrets or bundled STT models (confirmed via `docker history` and a
  filesystem scan).

## GitHub Actions result

**FAIL**, reproducibly, on both platforms, across two independent full
CI attempts against the exact RC commit (the original push and one safe
`gh run rerun --failed`, no source change, no new commit):

- Windows (`build-and-test (windows-latest)`): 4 failed / 1700 passed,
  deterministic (2/2), root-caused to
  `VoiceSTT/transcription_engines/model_resolver.py::resolve_kroko_model()`
  calling `Path.resolve()`, which returns the 8.3 short filename form on
  GitHub-hosted Windows runners.
- Ubuntu (`build-and-test (ubuntu-24.04)`): 1 failed / 1703 passed,
  reproduced identically twice, a replay-window timing race in
  `tests/unit/test_fastapi_server_multi_user.py`.
- All steps before the unit-test-suite step (build, `twine check`,
  fresh wheel install, `pip check`, import/version/script/asset checks)
  were green on both platforms, both attempts.

This workflow (`.github/workflows/ci.yml`) was introduced by this exact
commit; this qualification is the first time it has ever run on real
GitHub Actions infrastructure. Both failures require a source-controlled
fix, forbidden during W5-R02 - see `Evidence/01_GitHub_Actions/` and
`04_DEVIATIONS.md` (D1).

## Windows result

PASS. Fresh install from the built wheel into an isolated venv outside
the repository checkout; `pip check` clean; version/console-scripts/
assets all present and correct; server starts from the installed
distribution and correctly reports `NOT_READY` with no implicit model
download.

## Ubuntu result

PASS. Fresh install on native WSL2 Ubuntu 24.04.4 (Python 3.12.3), same
wheel byte-identity as Windows; same checks, same clean result.

## Live E2E results (three required)

- Faster-Whisper: **INCONCLUSIVE.** Real model, real audio, real
  Protocol-equivalent session; produced a correct, non-hallucinated
  transcript for roughly the first half of the reference audio, but the
  session did not reach full-audio completion in this specific load-test
  harness. See `Evidence/10_Live_E2E_FasterWhisper/`.
- Kroko Free: **INCONCLUSIVE**, same pattern, reproduced with a
  structurally different engine (rules out an engine-specific defect;
  points at the test harness/fixture interaction instead). See
  `Evidence/11_Live_E2E_Kroko_Free/`.
- Kroko Pro: **BLOCKED.** No Kroko Pro runtime credential exists in this
  environment; honestly reported as such, not faked. See
  `Evidence/12_Live_E2E_Kroko_Pro/`.

## Unit regression result

**FAIL** (same underlying finding as the GitHub Actions result - the
same 5 unique tests, same root causes). GitHub Actions' clean, isolated
runs are the authoritative signal; three local full-suite attempts on
this session's own host were additionally confounded by unrelated
resource contention (documented in `04_DEVIATIONS.md`, D2) and are not
treated as authoritative.

## Negative/security summary

PASS. Live smoke-tested against a running installed instance: public
`/health` open, admin endpoints correctly reject missing/wrong
credentials with no credential reflection, malformed JSON fails with a
structured 422 (no crash), unknown-model config is accepted as intent
only and never silently activated, no secret value appeared in any
response body, `docker history` and image filesystem scans of both
production images are clean, wheel/sdist content boundaries are clean,
and the Evidence directory itself was swept for accidental secrets
(clean).

## Model management / persistence / shutdown

PASS. Canonical `/var/lib/voicestt` root and both managed model paths
(`models/stt/fasterwhisper`, `models/stt/kroko_asr`) present, owned by
the runtime user, and writable in a live container. A missing-model
container stayed healthy with correct `NOT_READY` reporting and no
restart loop. A full container recreate (remove + fresh create against
the same volume) preserved a probe file with an identical SHA256 and
left the managed paths intact and writable. `docker stop` produced the
exact required ASGI shutdown lifecycle log lines and exited cleanly (0).
One environment-only finding (a Windows Docker Desktop bind-mount
limitation, worked around with a named volume, not a product defect) is
documented in `04_DEVIATIONS.md` (D6). One area (read-only custom model
source) was not tested this run for time-budget reasons (`04_DEVIATIONS.md`, D7).

## Release preflight/dry-run result

PASS, with one additional genuine source-level finding. `release.py
preflight` passed every check in this qualification's scope (VERSION,
exact commit/tree, clean source, release notes, tool availability, no
conflicting state); the registry-repo/credential checks correctly FAIL/
WARN because no real publish configuration exists in this environment,
as required. `release.py dry-run` reported `sideEffectFree: true`, the
exact fixed W6 operation order, and zero executed steps. All 157 targeted
release-tooling unit tests (11 subtests) passed, matching the W5-R01-C1
baseline exactly. However, the documented `release.py manifest build`
CLI path crashes (`KeyError: 'sha256'`) when fed real
`tools/build_production.py` output, due to a genuine schema-naming
mismatch between the two tools (`wheelSha256` vs `sha256` at the same
JSON path) - a real, previously-undetected finding, documented in
`04_DEVIATIONS.md` (D3). The RC manifest itself was still produced
correctly, by calling the underlying canonical helper module directly
with independently-verified values and validating the result through the
CLI's own separate, working `manifest validate` subcommand - no source
file was touched to achieve this.

## Final gate count

- PASS: 49
- FAIL: 5 (W5Q-G07, W5Q-G08, W5Q-G10 - one finding; W5Q-G39; W5Q-G53 -
  worked around, manifest itself valid)
- BLOCKED: 1 (W5Q-G38)
- INCONCLUSIVE: 2 (W5Q-G36, W5Q-G37)
- NOT TESTED: 1 (W5Q-G42)

Full detail: `03_GATE_INDEX.md`.

## Source-clean verification

Confirmed at both the start and the end of this run:
HEAD `bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602`, tree
`f7b304b1959e48457a8eefd8919484f55214633b`, `git status --porcelain`
empty, `git diff --check` clean, remote Distributed unchanged at the
same commit. See `Evidence/00_RC_Freeze/` and `Evidence/18_Final_Git_State/`.

## No source commit/tag/push/publication statement

No source-controlled file was created, edited, or deleted at any point
during W5-R02. No `git commit`, `git tag`, or `git push` was ever issued
against this workspace or its branch. No PyPI/GHCR/Docker Hub upload, no
GitHub Release, and no real `release.py publish` was executed - only
`preflight`, `dry-run`, and a direct call to the manifest-assembly helper
module ran, all read-only or side-effect-free by construction and
confirmed as such in their own output (`sideEffectFree: true` for the
dry-run).

## RC manifest

`05_RC_MANIFEST.json`, sha256
`33ce8dd8a3dcc43fd6787f9c1db4014be0490ae0cc982700f5c4f97109ad5d1e`,
independently validated via `release.py manifest validate`,
`releaseReadiness: "NOT_QUALIFIED"` - consistent with this report's
verdict.

## Disposition

This candidate (W5-RC1, commit `bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602`,
version 2.0.0) is **NOT READY FOR ROOT REVIEW**. Two independent,
well-evidenced, source-level findings (D1: two real GitHub Actions CI
failures; D3: an RC-manifest tooling schema mismatch) each individually
require a source-controlled fix that this qualification-only run is
forbidden from making. A Correction Run should address both, creating a
new internal RC candidate while the product version remains 2.0.0, and
should also resolve the two inconclusive live-E2E findings (D4) and
complete the one untested gate (D7, read-only custom model source)
before the next full qualification attempt. Every other area attempted
in this run - packaging, both fresh installs, Kroko Free/Pro build
identity, both production images, model management, persistence,
graceful shutdown, and negative/security behavior - passed with real,
live evidence and needs no rework.
