# Needs Operator Input: Registry Target Identities (AP-SRV-070 / W5-R03-E1)

**Date:** 2026-09-08
**Run:** W5-R03-E1
**Status:** BLOCKED ON OPERATOR INPUT (RR-1 / W5Q2-G50)

---

## 1. Context

Root Review RR-1 identified that `W5Q2-G50` was previously marked `PASS` despite `release.py preflight` returning `"passed": false` due to:
```text
ghcr_repo_configured      = FAIL (VOICESTT_RELEASE_GHCR_REPO=<unset>)
dockerhub_repo_configured = FAIL (VOICESTT_RELEASE_DOCKERHUB_REPO=<unset>)
```

Per AP-SRV-070 specification Section 3:
- Registry repository roots are release target identities and must be exact.
- They must **never** be guessed or inferred from GitHub usernames or existing URLs.
- They must be resolved strictly from an operator-provided authoritative source.
- If either variable cannot be resolved from existing operator configuration, `NEEDS_OPERATOR_INPUT.md` must be written under `Evidence/18_RootReview_Completion/` and the status remains `NOT READY FOR ROOT REVIEW` until the operator supplies them.

---

## 2. Missing Variables

The following environment variables are currently unset and unconfigured in all local operator configurations:

1. `VOICESTT_RELEASE_GHCR_REPO`
   - Purpose: Canonical repository root for GHCR container images (Free and Pro).
   - Example format: `ghcr.io/<org-or-user>/voice-stt-server` (exact target required)

2. `VOICESTT_RELEASE_DOCKERHUB_REPO`
   - Purpose: Canonical repository root for Docker Hub container images (Free and Pro).
   - Example format: `<dockerhub-namespace>/voice-stt-server` (exact target required)

---

## 3. Required Action

Please supply the exact authoritative values for:
- `VOICESTT_RELEASE_GHCR_REPO`
- `VOICESTT_RELEASE_DOCKERHUB_REPO`

Once supplied, they will be exported process-locally to:
1. Re-run `python release.py preflight` -> verify `"passed": true` (zero FAIL checks) -> write `03_release_preflight_pass.txt`.
2. Re-run `python release.py dry-run` -> verify exact W6 execution graph with targets configured -> write `04_release_dryrun_with_targets.txt`.
3. Refresh and validate `05_RC_MANIFEST.json` -> write `06_manifest_refresh.txt`.
4. Update `03_GATE_INDEX.md`, `04_DEVIATIONS.md`, `06_QUALIFICATION_REPORT.md`, and set `07_FINAL_REPORT.md` to `READY FOR ROOT REVIEW`.
