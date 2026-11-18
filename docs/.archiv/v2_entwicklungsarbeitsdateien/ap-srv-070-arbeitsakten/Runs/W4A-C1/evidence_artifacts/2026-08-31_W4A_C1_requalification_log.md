# AP-SRV-070 W4A-C1 — Real Artifact Re-Qualification Log

The BUILDER_REVISION bump (1 → 2, Root Findings B/C) changes the default
fingerprint for a build on this host. Per the C1 prompt's explicit allowance,
the already-existing real qualified wheel was re-registered under the new
fingerprint rather than triggering a new native build, since its provenance
still matches the declared build inputs exactly (same upstream revision, same
patch set, same variant, same platform/arch/ABI - only the two declared
revision constants changed).

## Fingerprints

| | Before C1 (BUILDER_REVISION=1) | After C1 (BUILDER_REVISION=2) |
|---|---|---|
| free (windows/amd64/cp312) | `32c947609a9be925` | `9055547da3ba4d66` |
| pro (windows/amd64/cp312) | `1a447cbd22b3cf0b` | `2469fd1a25e86b97` |

## Re-qualification steps (all via PowerShell, real `install_kroko` code paths)

1. `install_kroko.fingerprint_for(args)` on this host, default args → `9055547da3ba4d66`.
2. `store.store(wheel_path=<real wheel>, fingerprint=..., inputs=...)` → stored
   without modification (`verify_artifact` passed, including the new Finding D
   platform-tag check: `win_amd64` tag against a `windows`/`amd64` target).
3. `store.lookup(...)` → hit, `problems == []`.
4. Real, non-stubbed `python VoiceSTT\install_kroko.py --build --skip-install
   --artifact-store <store>` → printed `Reusing verified Kroko artifact: ...`,
   **no build was invoked**.
5. Installed the re-qualified wheel into a disposable venv (outside the
   worktree, deleted afterward): `import kroko_onnx` succeeded,
   `verify_installed_runtime("free")` → `ok: true`, `verify_installed_runtime("pro")`
   → `ok: false` (correct negative).

Full JSON: `2026-08-31_W4A_C1_requalified_installed_runtime_consumption.json`.

## Wheel identity (unchanged bytes)

| Field | Value |
|---|---|
| Filename | `kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl` |
| SHA-256 | `ac26db5d8c063649028924d4b55b14019b2370e8c457841ea278a8e48dd50041` |
| Bytes | 12 549 957 |
| Wheel Build tag | `1free` |

## Incident during verification (see Root Correction Report §7 for full account)

A verification script of mine mixed a POSIX-style Bash path into a Python
`Path` literal, which `pathlib` resolved as drive-relative on Windows,
pointing the artifact store at the wrong location. The resulting cache miss
caused the real CLI to fall through to a real build attempt on Windows
(Docker, now working again - see §8 of the correction report), which failed
on an unrelated external download and, as a side effect, cleared the
`release_artifacts\windows` output directory that held the original qualified
wheel.

No data was lost: a byte-identical copy (verified by SHA-256) already existed
in this session's own scratch artifact store from an earlier step in this same
run. That copy was used to restore `release_artifacts\windows` (hash
re-verified after restore) and for the correct re-qualification above. The
root cause was my own tooling, not the product code; the real
`install_kroko.main()` reuse path performed correctly once the store path was
resolved correctly (step 4 above: clean reuse hit, no build attempt).
